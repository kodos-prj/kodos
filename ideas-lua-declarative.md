This is a well-scoped system. Let me design it concretely — the abstractions, how they fit together, and where extensibility plugs in.

---

## The Core Abstractions (Four of Them)

Everything in your system reduces to four concepts:

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                   │
│   Derivable          Config           BuildPlan        Registry    │
│   "how to make     "what I want"    "ordered steps   "known      │
│    something"       (desired state)   to get there"   types &    │
│                                                               kinds"    │
└─────────────────────────────────────────────────────────────────────┘
```

Everything else is composition of these four.

---

## 1. Derivable — A Description of an Artifact

A **derivable** is a table that describes *what* something is and *how* to produce it. It is data, not execution.

```lua
-- A derivable has:
--   .type       string   — which builder handles it (looked up in Registry)
--   .name       string   — human-readable identifier
--   .inputs    table     — named dependencies (other derivables or literals)
--   .params    table     — type-specific parameters
--   .outputs   table     — what this derivable produces (paths, env vars, etc.)

local Derivable = {}
Derivable.__index = Derivable

function Derivable.new(type_, name, inputs, params)
  return setmetatable({
    type    = type_,
    name    = name,
    inputs  = inputs or {},   -- { depName = Derivable | literal }
    params  = params or {},
    outputs = {},             -- filled in at build time
  }, Derivable)
end

function Derivable:__tostring()
  return string.format("<%s:%s>", self.type, self.name)
end
```

Concrete examples:

```lua
-- A program (compiled from source)
local hello = Derivable.new("program", "hello", {
    src = "https://example.com/hello-2.12.tar.gz",
  }, {
    buildCommand  = "./configure && make -j$(nproc)",
    installCommand = "make install PREFIX=$OUT",
    deps          = { "gcc", "glibc" },   -- other derivables by name
  })

-- A generated file (e.g., a config template)
local nginxConf = Derivable.new("file", "nginx.conf", {
    template = "./templates/nginx.conf.tmpl",
  }, {
    content = function(inputs, params, env)
      -- `env` gives access to resolved inputs at build time
      return string.format([[
        worker_processes %d;
        server { listen %d; }
      ]], env.cpuCount, params.port or 8080)
    end,
  })

-- A service (runs a program with a config)
local nginxSvc = Derivable.new("service", "nginx", {
    program = hello,           -- depends on the derivable above
    config  = nginxConf,       -- and this one
  }, {
    startCommand = "nginx -c $CONFIG",
    stopCommand  = "nginx -s quit",
    restartPolicy = "on-failure",
  })

-- An environment (like `nix develop`)
local devEnv = Derivable.new("environment", "dev-shell", {
    gcc   = Derivable.new("package", "gcc", {}, { version = "13" }),
    make  = Derivable.new("package", "make", {}, {}),
  }, {
    envVars = { EDITOR = "vim", CFLAGS = "-O2" },
  })
```

Notice: **nothing is executed here.** These are descriptions. The `content` function in the file derivable and the `buildCommand` string in the program derivable are *data that will be used later*. This is the key separation: **describe now, execute later.**

---

## 2. Config — The Desired State

A **config** is a plain table of named values. Values can be literals, derivables, or references to other config entries. It's declarative: you state *what*, not *how*.

```lua
local config = {
  system = {
    hostname   = "myserver",
    cpuCount   = 4,            -- could come from an impure query phase
  },

  packages = {
    hello  = hello,            -- a Derivable
    nginx  = nginxSvc,         -- a Derivable (service)
  },

  services = {
    nginx = {
      enable = true,
      port   = 8080,
    },
  },

  users = {
    deploy = {
      shell = "/bin/bash",
      home  = "/home/deploy",
    },
  },
}
```

This is the "attribute set" from Nix. It's just a table. The structure is **convention, not enforcement** — you can organize it however makes sense for your domain.

### Composition (Merging Partial Configs)

Just like Nix's `//`, you merge partial configs:

```lua
local function mergeConfig(base, override)
  local result = {}
  for k, v in pairs(base) do result[k] = v end
  for k, v in pairs(override) do
    if type(result[k]) == "table" and type(v) == "table"
       and not isArray(result[k]) and not isArray(v) then
      result[k] = mergeConfig(result[k], v)
    else
      result[k] = v
    end
  end
  return result
end

-- User extends the base config:
local userConfig = {
  services = { nginx = { port = 9090 } },  -- override just this
  packages = { vim = Derivable.new("package", "vim", {}, {}) },
}

local finalConfig = mergeConfig(baseConfig, userConfig)
```

This is how you get NixOS-style layering: a base config, a site-specific config, a per-user config — all merged.

---

## 3. BuildPlan — Resolved, Ordered Steps

The **build plan** is what you get after resolving the config into a concrete sequence of actions. It's produced by a **planner** that:

1. Collects all derivables referenced in the config
2. Resolves the dependency graph (topological sort)
3. Checks which are already built (cache)
4. Produces an ordered list of steps

```lua
local BuildPlan = {}
BuildPlan.__index = BuildPlan

function BuildPlan.new()
  return setmetatable({
    steps   = {},      -- ordered list of { derivable = D, action = "build"|"install"|"start" }
    built   = {},      -- name → output path (for already-cached items)
  }, BuildPlan)
end

function BuildPlan:execute(registry, store)
  for _, step in ipairs(self.steps) do
    local builder = registry.getBuilder(step.derivable.type)
    if not builder then
      error("No builder registered for type: " .. step.derivable.type)
    end
    local outputs = builder(buildContext, step.derivable, store)
    step.derivable.outputs = outputs
  end
end
```

The **planner** is the function that turns a `Config` into a `BuildPlan`:

```lua
local function plan(config, registry, store)
  local plan   = BuildPlan.new()
  local graph  = {}   -- name → Derivable (all derivables in this config)
  local visited = {}

  -- Phase 1: collect all derivables from the config
  local function collect(value)
    if getmetatable(value) == Derivable then
      graph[value.name] = value
      for depName, dep in pairs(value.inputs) do
        if getmetatable(dep) == Derivable then
          collect(dep)
        end
      end
    elseif type(value) == "table" then
      for _, v in pairs(value) do collect(v) end
    end
  end
  collect(config)

  -- Phase 2: topological sort (Kahn's algorithm)
  local inDegree, queue, sorted = {}, {}, {}
  for name, d in pairs(graph) do
    inDegree[name] = 0
  end
  for name, d in pairs(graph) do
    for depName, dep in pairs(d.inputs) do
      if getmetatable(dep) == Derivable then
        inDegree[name] = (inDegree[name] or 0) + 1
      end
    end
  end
  for name, deg in pairs(inDegree) do
    if deg == 0 then table.insert(queue, name) end
  end

  while #queue > 0 do
    local n = table.remove(queue, 1)
    table.insert(sorted, n)
    for name, d in pairs(graph) do
      for depName, dep in pairs(d.inputs) do
        if dep.name == n then
          inDegree[name] = inDegree[name] - 1
          if inDegree[name] == 0 then table.insert(queue, name) end
        end
      end
    end
  end

  -- Phase 3: check cache, add steps for what needs building
  for _, name in ipairs(sorted) do
    local d = graph[name]
    local cachedPath = store.check(d)   -- hash-based lookup
    if cachedPath then
      plan.built[name] = cachedPath
    else
      table.insert(plan.steps, { derivable = d, action = "build" })
    end
  end

  return plan
end
```

---

## 4. Registry — The Extension Point

This is the piece that makes the system **open for extension**. The registry maps derivation types to their builders. Core types are registered at startup; users register new ones.

```lua
local Registry = {}
Registry.__index = Registry

function Registry.new()
  return setmetatable({ _builders = {}, _hooks = {} }, Registry)
end

-- Register a builder for a derivable type
function Registry:register(typeName, builder)
  self._builders[typeName] = builder
end

function Registry:getBuilder(typeName)
  return self._builders[typeName]
end

-- Lifecycle hooks (extension points)
-- Hooks: "pre-build", "post-build", "pre-install", "post-install",
--        "pre-start", "post-start"
function Registry:on(hookName, fn)
  table.insert(self._hooks[hookName] or {}, fn)
  self._hooks[hookName] = self._hooks[hookName] or {}
end

function Registry:fire(hookName, ...)
  for _, fn in ipairs(self._hooks[hookName] or {}) do
    fn(...)
  end
end

return Registry
```

### Core Builders (Shipped With the System)

Each builder is a function with a standard signature:

```lua
-- Builder signature:
--   function(builderCtx, derivable, store) → outputs table
--
--   builderCtx: access to registry, config, logger
--   derivable:  the Derivable being built
--   store:      the build store (paths, caching)
--   returns:    { outPath = "...", envVars = {...}, ... }

local coreBuilders = {

  program = function(ctx, d, store)
    ctx:fire("pre-build", d)

    local srcDir = store:unpack(d.inputs.src)
    local outDir = store:createOutputDir(d)

    -- Execute the build (this is where impurity lives — in the runtime, not the config)
    shell(d.params.buildCommand, { DIR = srcDir, OUT = outDir })
    shell(d.params.installCommand, { DIR = srcDir, OUT = outDir })

    ctx:fire("post-build", d)
    return { outPath = outDir }
  end,

  file = function(ctx, d, store)
    local content
    if type(d.params.content) == "function" then
      content = d.params.content(d.inputs, d.params, ctx.env)
    else
      content = d.params.content   -- static string
    end
    local path = store:writeFile(d.name, content)
    return { outPath = path }
  end,

  service = function(ctx, d, store)
    local programOut = d.inputs.program.outputs.outPath
    local configOut  = d.inputs.config and d.inputs.config.outputs.outPath or nil

    -- Generate a unit file (systemd, launchd, etc.)
    local unitFile = string.format([[
      [Unit]
      Description=%s
      [Service]
      ExecStart=%s
      Restart=%s
      [Install]
      WantedBy=multi-user.target
    ]], d.name, programOut, d.params.restartPolicy or "no")

    local unitPath = store:writeFile(d.name .. ".service", unitFile)
    return { unitPath = unitPath, outPath = programOut }
  end,

  environment = function(ctx, d, store)
    -- Produce a shell script that sets up the environment
    local lines = { "#!/bin/sh" }
    for name, dep in pairs(d.inputs) do
      if getmetatable(dep) == Derivable and dep.outputs.outPath then
        table.insert(lines, string.format('export PATH="%s/bin:$PATH"', dep.outputs.outPath))
      end
    end
    for k, v in pairs(d.params.envVars or {}) do
      table.insert(lines, string.format("export %s=%s", k, v))
    end
    local script = store:writeFile(d.name .. "-env.sh", table.concat(lines, "\n"))
    return { outPath = script }
  end,

  package = function(ctx, d, store)
    -- Fetch a pre-built binary or build from source
    -- (implementation depends on your package source)
    local path = store:fetch(d.name, d.params.version)
    return { outPath = path }
  end,
}
```

---

## 5. The Store — Content-Addressed Output Directory

```lua
local Store = {}
Store.__index = Store

function Store.new(root)
  local s = setmetatable({ root = root }, Store)
  s:_init()
  return s
end

function Store:_init()
  mkdirp(self.root)
end

-- Compute a hash for a derivable (all inputs + params + type)
function Store:hash(derivable)
  local canonical = canonicalEncode({
    type   = derivable.type,
    name   = derivable.name,
    params = derivable.params,
    inputs = self:_hashInputs(derivable),
  })
  return sha256(canonical):sub(1, 32)
end

function Store:_hashInputs(d)
  local h = {}
  for name, input in pairs(d.inputs) do
    if getmetatable(input) == Derivable then
      h[name] = self:hash(input)
    else
      h[name] = tostring(input)
    end
  end
  return h
end

function Store:createOutputDir(derivable)
  local h = self:hash(derivable)
  local dir = string.format("%s/%s-%s", self.root, h, derivable.name)
  mkdirp(dir)
  return dir
end

function Store:check(derivable)
  local h = self:hash(derivable)
  local dir = string.format("%s/%s-%s", self.root, h, derivable.name)
  if fileExists(dir .. "/.built") then
    return dir
  end
  return nil
end

function Store:writeFile(name, content)
  -- Write to a temp location, then move into the store
  local path = string.format("%s/tmp/%s", self.root, name)
  writeFile(path, content)
  return path
end

return Store
```

The key property: **the output path is a function of the inputs.** Same derivable → same hash → same path. If the path already exists and is marked `.built`, you skip the build. This gives you caching and reproducibility *within the relaxed model* — as long as the derivable's description hasn't changed.

---

## 6. Tying It Together — The User-Facing API

```lua
-- ═══════════════════════════════════════════
--  main.lua — the entry point
-- ═══════════════════════════════════════════

local Registry  = require("registry")
local Derivable = require("derivable")
local Store     = require("store")
local Planner   = require("planner")
local Core      = require("core.builders")

-- 1. Set up the registry and register core builders
local registry = Registry.new()
for typeName, builder in pairs(Core) do
  registry:register(typeName, builder)
end

-- 2. Load the user's config (a Lua file that returns a table)
local userConfig = require("config")   -- → { system=..., packages=..., services=... }

-- 3. Merge with defaults
local config = Planner.mergeConfigs(Planner.defaults(), userConfig)

-- 4. Plan
local store = Store.new("/var/mylix/store")
local plan  = Planner.plan(config, registry, store)

-- 5. Execute
for _, step in ipairs(plan.steps) do
  print(("Building [%s] %s"):format(step.derivable.type, step.derivable.name))
  registry:fire("pre-build", step.derivable)

  local builder = registry:getBuilder(step.derivable.type)
  local ctx = { registry = registry, config = config, env = config.system }
  step.derivable.outputs = builder(ctx, step.derivable, store)

  registry:fire("post-build", step.derivable)
end

-- 6. Activate (start services, set up users, etc.)
Planner.activate(config, store, registry)
```

---

## 7. Extensibility — How a User Adds New Functionality

This is where the design pays off. A user extends the system in three ways:

### a) Register a new derivable type

```lua
-- myplugins/docker_image.lua
local Derivable = require("derivable")

return {
  name = "docker_image",

  -- Validate/normalize params when the derivable is created
  validate = function(params)
    assert(params.dockerfile, "docker_image requires a 'dockerfile' param")
    assert(params.tag, "docker_image requires a 'tag' param")
  end,

  -- The builder
  build = function(ctx, d, store)
    local outDir = store:createOutputDir(d)
    -- Copy Dockerfile and context into outDir
    -- Run: docker build -t <tag> <context>
    shell("docker build -t " .. d.params.tag .. " " .. outDir, { DIR = outDir })
    return { outPath = outDir, imageTag = d.params.tag }
  end,
}
```

The user registers it:

```lua
-- In their config or a plugin loader:
local dockerImage = require("myplugins.docker_image")
registry:register(dockerImage.name, dockerImage.build)
```

Now they can use it in configs like any core type:

```lua
local myImage = Derivable.new("docker_image", "webapp", {
    app = hello,   -- depends on another derivable
  }, {
    dockerfile = "./Dockerfile",
    tag        = "webapp:latest",
  })
```

### b) Add lifecycle hooks

```lua
-- Log every build
registry:on("pre-build", function(d)
  io.stdout:write(string.format("[build] starting %s at %s\n", d.name, os.date()))
end)

-- Auto-restart services after rebuild
registry:on("post-build", function(d)
  if d.type == "service" then
    shell("systemctl restart " .. d.name)
  end
end)
```

### c) Compose configs (the NixOS module pattern)

```lua
-- mysite/config.lua
local Derivable = require("derivable")

return {
  system = { hostname = "prod-server-01" },

  packages = {
    app = Derivable.new("program", "myapp", {
      src = "./src",
    }, {
      buildCommand  = "cargo build --release",
      installCommand = "cp target/release/myapp $OUT/bin/",
    }),
  },

  services = {
    myapp = {
      enable = true,
      port   = 3000,
    },
  },

  -- User-specific extension: add a monitoring service
  _postMerge = function(config)
    -- Modify the merged config before planning
    config.services.alertmanager = { enable = true }
    return config
  end,
}
```

---

## 8. How This Maps Back to Your Four Goals

| Goal | How it's covered |
|---|---|
| **Describe system configurations for install/rebuild** | `Config` table + `BuildPlan` + `Store`. Rebuild = re-plan (cache hits skip unchanged derivables) + re-execute. |
| **Describe features/configs for programs and services** | `Derivable` with type-specific `params`. A `service` derivable wraps a `program` derivable + config files. The structure is open — add fields as needed. |
| **Describe creation of derivables (programs, files, environments)** | `Derivable.new(type, name, inputs, params)`. Each type has a registered builder. New types = new builders. |
| **User-extensible** | `Registry:register()` for new types, `Registry:on()` for lifecycle hooks, `mergeConfig()` for layering configs, plain Lua tables for arbitrary structure. |

---

## 9. What This Design Concedes (vs. Nix)

Being explicit about the trade-offs you're making by using Lua:

| Nix property | Status here | Mitigation |
|---|---|---|
| Pure evaluation | ❌ Relaxed — builders run shell commands, read files | The *config* is still pure data; impurity is confined to builders (the "execution" phase) |
| Immutability | ❌ Relaxed — Lua tables are mutable | Derivables are conventionally treated as immutable after creation; the store uses content hashes for integrity |
| Laziness | ❌ Eager — the planner walks the whole graph | For reasonable config sizes this is fine. You could add lazy thunks (Layer 1/2 from earlier) if configs get huge |
| Content-addressed store | ✅ Yes — `Store:hash()` gives you this | Same inputs → same hash → same path → cache hit |
| Reproducibility | ⚠️ Partial — reproducible *given the same derivable descriptions* | If a user hardcodes `os.time()` in a builder, reproducibility is on them. The system can't enforce it. |
| Atomic rollback | ⚠️ Partial — you'd need to track generations | Add a `generations/` directory with symlinks; each build creates a new generation; rollback = switch symlink |

The key architectural choice: **impurity is confined to builders.** The config, the plan, the graph — all pure data. Only when a builder runs does the system touch the outside world. This gives you most of the *reasoning* benefits of purity (you can inspect the plan, serialize it, diff two plans) without requiring the language itself to be pure.
