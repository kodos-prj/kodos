# Lifecycle Hooks — v1 Implementation

**Version:** 1.0 (no built-in hooks; mechanism + examples)

## Overview

Lifecycle hooks allow programs to run custom logic before/after rebuild steps of specific kinds.

**Fixed event names:** `pre:<kind>` and `post:<kind>`, where `kind ∈ {package, service, program, user}`.

**Where they run:** During install/rebuild execution (via the Lua runner, `execute_steps`). `kod plan` lists which hooks would fire but never executes them.

**Semantics:**
- `pre:*` hook error → step aborts (on_error becomes "abort" regardless of step's on_error field).
- `post:*` hook error → logged as warning, step remains successful, execution continues.

## Example: Restart Service if Running

Program module `~/.kod/plugins/programs/nginx.lua`:

```lua
return {
    name = "nginx",
    scope = "system",
    schema = { ... },
    default_config = { ... },
    generate_config = function(self, options) ... end,
    
    -- NEW: Lifecycle hooks (optional)
    hooks = {
        ["post:service"] = function(step, ctx)
            -- After any service enable step, restart if already running
            if step.name == "nginx" then
                os.execute("systemctl is-active --quiet nginx && systemctl restart nginx || true")
            end
        end,
    }
}
```

**Signature:** `hook(step, ctx)`
- `step`: Step object (fields: kind, name, program, args, meta, ...)
- `ctx`: Context dict (fields: mount_point, repos, generation_id, use_chroot, ...)

**Return:** Hook return value is ignored (side-effects only).

## Registering Hooks

1. Add `hooks` table to your program module (same .lua file as name, schema, generate_config).
2. Use keys from the fixed set: `pre:package`, `post:package`, etc.
3. Values are Lua functions with signature `(step, ctx) -> any`.
4. Unknown hook names raise ValidationError during `kod rebuild` (fail loud).

## Built-in Hooks (v2+)

Future versions may include built-in hooks for common patterns (e.g., restart systemd-user-sessions after user creation). For now, hook everything custom via plugin modules.

## Testing Your Hooks

Write a `post:service` hook that prints to `/tmp/hook-test.log`, then:

```bash
kod rebuild --dry-run  # Verify hook name appears in plan output
kod rebuild            # Execute; check /tmp/hook-test.log
```

## Hook Signature Reference

All hooks receive two arguments:

### `step` (Step object)
- `kind`: Step kind (e.g., "service", "package", "system")
- `name`: Step name (e.g., "nginx", "vim", "kernel-update")
- `program`: Program name (if applicable)
- `args`: Program arguments list
- `meta`: Metadata dict (includes "action", "hooks", etc.)
- `on_error`: Error policy ("abort" | "warn")
- `timeout_s`: Timeout in seconds (optional)

### `ctx` (Context dict)
- `mount_point`: Filesystem mount point for changes (default "/")
- `repos`: Repository configuration dict
- `generation_id`: Current generation ID (integer)
- `use_chroot`: Whether to chroot during execution (boolean)

## Error Handling

### Pre-hook Errors (abort the step)

```lua
hooks = {
    ["pre:package"] = function(step, ctx)
        -- If this raises or returns error, the package step will NOT execute
        if step.name == "dangerous-package" then
            error("Cannot install dangerous-package in this context")
        end
    end,
}
```

Any exception in a pre-hook causes the corresponding step to be skipped and execution to abort (unless the step has `on_error="warn"`, in which case it still records a warning but continues with the next step).

### Post-hook Errors (logged, execution continues)

```lua
hooks = {
    ["post:service"] = function(step, ctx)
        -- If this raises, it's logged as a warning but the service enable is still
        -- considered successful and the rebuild continues
        os.execute("systemctl is-active --quiet nginx && systemctl restart nginx || true")
    end,
}
```

Post-hook errors are logged via `kod` logging but do not prevent further steps from executing.

## Examples

### Example 1: Conditional Restart on Service Enable

```lua
hooks = {
    ["post:service"] = function(step, ctx)
        if step.name == "nginx" then
            os.execute("systemctl is-active --quiet nginx && systemctl restart nginx || true")
        end
    end,
}
```

After any service enable step, if it was nginx, restart nginx if already running.

### Example 2: Pre-step Validation

```lua
hooks = {
    ["pre:package"] = function(step, ctx)
        if step.name == "glibc" then
            -- Prevent package step for glibc in this context
            error("glibc must be installed manually in this version")
        end
    end,
}
```

Raises an error before attempting to install glibc.

### Example 3: Logging Hook Execution

```lua
hooks = {
    ["post:package"] = function(step, ctx)
        io.open("/tmp/hook-log.txt", "a"):write(
            string.format("Package %s was %sed at %s\n", 
                step.name, step.meta.action, os.date())
        )
    end,
}
```

Logs each package operation to a file for auditing.
