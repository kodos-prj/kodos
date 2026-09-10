# KodOS Planner, Lifecycle Hooks, Build-Step Integration — Design Specification

**Date:** September 10, 2026
**Status:** Design Review Required
**Scope:** Plan/execute split for `install` and `rebuild`, lifecycle hooks as a first-class extension point, Phase 5 source builds wired in as plan steps.
**Not a scope change to:** host language (Python + lupa stays), distribution model, generation/rollback mechanism.

---

## 1. Purpose

Introduce an inspectable, diffable execution plan between configuration and execution:

1. **Planner + executor split** — `kod plan` previews every action (including disk operations) before anything runs; `install` and `rebuild` execute the same plan object they print.
2. **Lifecycle hooks** — a fixed, uniform extension point for plugins, replacing the ad-hoc hook list in `rebuild`.
3. **Build-step integration** — Phase 5 custom packages become first-class plan steps using the cache already designed in the Phase 5 spec.

All new logic is written **portable-Lua-first**: config, program modules, plugin modules, and bootstrap emitters stay pure data + table functions with no Python-specific behavior, so a future host migration (V+vlua / Rust+mlua, per the analysis doc) is "move files", not "rewrite logic". The executor is the only non-portable surface (~200 lines).

## 2. Current state (why this is needed)

- `install` (kod.py:152) and `rebuild` (kod.py:269) already compute desired state through shared functions (`get_packages_to_install`, `get_services_to_enable`) but execute immediately — no preview, no dry-run.
- Bootstrap (partitions, mkfs/mount, fstab, locale, hostname/network, bootloader) is imperative Python inside the install flow: the most dangerous code in the project, with zero preview capability.
- Hooks exist only as an ad-hoc `hooks_to_run` list executed in `rebuild` (kod.py:384).
- Phase 5 (custom/source packages) is designed but unimplemented; its standalone `kod package build` command would operate outside any plan.

## 3. Step model

A step is structured data, never a raw shell string:

```
{
  kind:      package | service | program | user | build
  name:      str
  program:   str          # executable to run
  args:      [str]        # argument vector (no shell interpretation)
  chroot:    bool         # run via exec_chroot variant
  timeout_s: int
  on_error:  abort | warn
  meta:      {}           # kind-specific payload (e.g. pkg name, service unit)
}
```

Rules:
- **Flat list + metadata only.** No conditionals or loops inside a plan; all branching happens at plan-build time (the compiler). Plan output must be fully inspectable without executing anything.
- Rendering of a plan (`kod plan` output) is deterministic → golden-file testable.
- `on_error` defaults to `abort`; the emitter may set `warn` only for steps it explicitly marks non-critical.

## 4. Planner

- **Inputs:** validated config (including `custom_packages`) + a baseline state.
- **Baselines:**
  - `empty` — fresh rootfs; used for install previews.
  - `current` — generation N's `installed_packages` / `enabled_services` files; the default for rebuilds.
- **Process:** collect artifacts from config → dependency graph → topological sort → diff against baseline → ordered step list, skipping anything already satisfied by the baseline.
- **One planner, two baselines.** `install` = executor-gated bootstrap phase + plan over `empty`. `rebuild` = generation bookkeeping + plan over `current` + existing rollback-on-failure. Both execute the *same* plan object that `kod plan` would print — one code path, so dry-run output can never drift from what actually runs.
- **CLI:**
  - `kod plan -c <config> [--baseline empty|current]` (default: `current`).
  - On a system without `/kod/generations` (e.g. live ISO), default baseline fails with a hint to use `--baseline empty`.
  - `kod rebuild --dry-run` ≡ plan over `current`, no execution.

## 5. Executor

- Runs steps in order; per-step timeout; chroot variant via existing `exec_chroot`; per-step `on_error` policy.
- **Policy lives only here, never in Lua/config:**
  - Destructive steps (wipe/partition/format) require interactive confirmation before running, regardless of what the plan contains.
  - `build` steps require the Phase 5 approval workflow (show generated commands → y/N).
  - `pre:*` hook errors abort the current step; `post:*` hook errors are logged and execution continues (a broken logging hook must not roll back a successful install).
- Failure mid-plan → existing generation rollback path, unchanged.

## 6. Bootstrap expressed as steps (two-step port)

1. **First:** Python emits bootstrap steps (partitions, mkfs/mount, fstab, locale, hostname/network, bootloader) into the same step list. Outcome: `kod plan --baseline empty` previews the *entire* install including disk operations.
2. **Then:** port the emission logic into Lua modules behind the same step interface, verified by golden-file diff — the Python emitter and the Lua emitter must produce identical plan output for `example/testvm`.
- Arch vs Debian bootstrap differences become separate Lua modules instead of Python branches.
- The executor remains in the host language (Python now); it is the only part that does not move in a future V/Rust migration.

## 7. Lifecycle hooks

- **Fixed set, uniform:** `pre:<kind>` / `post:<kind>` for `kind ∈ {package, service, program, user}`. No other names in v1; `build` steps have no hooks (the approval workflow is their gate).
- **Registration:** optional field in the existing plugin/program module format (`~/.kod/plugins/programs/*.lua`), same shape as the existing `install = function(config, exec_fn)`:

```lua
return {
    name = "my_app",
    -- ...existing schema/install...
    hooks = {
        ["post:service"] = function(step, ctx)
            -- e.g. restart-if-running after enable
        end,
    }
}
```

- **Semantics:** `pre:*` errors abort the step; `post:*` errors log and continue. Signature `(step, ctx)` matches existing plugin conventions.
- **Plan visibility:** `kod plan` lists which hooks will fire per step but never executes them.
- **Replaces** the ad-hoc `hooks_to_run` list in `rebuild` — one hook mechanism for the whole system.
- **No builtin hooks in v1.** Mechanism + docs examples only (the canonical example: restart a service if already running after enable).

## 8. Build-step integration (Phase 5)

- **Adopt the Phase 5a cache design as-is** (`package_cache.py`: save/lookup, metadata JSON, invalidation on any build-affecting field change; integrity verification in 5b). No new content-addressing scheme, no Nix-style store.
- `custom_packages` (Phase 5 schema) joins the planner inputs → each becomes a `build:<name>` step followed by its install step. The plan shows expected cache state (`hit` / `miss` / `rebuild`); the executor performs the real cache lookup at run time.
- Build approval gate stays in the executor (Phase 5 workflow).
- The standalone `kod package build -n <name>` command from the Phase 5 spec remains — it is a plan filtered to one build step.

## 9. CLI surface (net new)

| Command | Purpose |
|---|---|
| `kod plan -c <config> [--baseline empty\|current]` | Print the full execution plan; never executes |
| `kod rebuild --dry-run` | Alias: plan over `current`, no execution |

No other changes to existing commands.

## 10. Testing strategy

- **Unit:** planner diff/topo logic (both baselines); hook firing semantics (`pre` abort / `post` continue); step serialization determinism; plan rendering.
- **Golden files:** bootstrap port — Python emitter vs Lua emitter must produce identical plan output for `example/testvm`.
- **Integration (VM):** install from live ISO with plan preview; `rebuild --dry-run` output matches actual execution diff; rollback on mid-plan failure still works.
- **Regression:** existing suite (422+ tests) stays green throughout; the ad-hoc `hooks_to_run` path is removed only after the hook mechanism replaces it.

## 11. Out of scope / deferred

- Host language migration (V+vlua / Rust+mlua). Decision criterion unchanged: only when single-binary distribution becomes a hard requirement (see analysis doc §5).
- `rebuild-user` flow adopting the planner (separate, later).
- Nix-style content-addressed store — btrfs generations remain the rollback mechanism.
- Builtin hooks; Phase 5b sandboxing (ships per its own spec and phase gate).

## 12. References

- `docs/superpowers/analysis/2026-09-10-lua-integration-language-options.md` — language options, integration map, recommendation
- `docs/superpowers/specs/2026-09-10-phase-5-custom-packages-design.md` — custom package schema, cache, approval, sandbox (adopted in §8)
- `ideas-lua-declarative.md` — source of the planner/hooks/store concepts
