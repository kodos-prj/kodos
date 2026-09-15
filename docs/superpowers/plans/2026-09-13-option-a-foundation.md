# Option A — Foundation Implementation Plan (Phase 0 + Phase 1)

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:subagent-driven-development
> or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax. This plan covers the *foundation* of Option A (green
> suite + one planner/executor). Phases 2–5 are outlined at the end and get their
> own plans when reached.

**Goal:** Make the Lua runner the single executor, delete the dead Python
planner/executor stack, and standardize package/service steps so install and
rebuild share one host code path.

**Architecture (Option A — thin host):** Lua plans steps; the host runs them. A
step with a non-empty `program` is a **shell step** (host runs it, chroot +
timeout). A program-less step of kind `package`/`service`/`system` is a **named
verb** dispatched to the host's small verb table. Everything else is an error.

**Tech Stack:** Python 3 + `lupa`, Click, btrfs/systemd/pacman. Lua under
`src/kod/lib/` and `src/kod/sections/`.

**Spec:** `docs/superpowers/plans/2026-09-13-kod-reorganization.md` (Option A).

## Global Constraints
- Test command: `.venv/bin/python -m pytest tests/ -q`. Must end **green**.
- Install golden: `tests/golden/plan-testvm-empty.txt`. Regenerate with
  `KODOS_WRITE_GOLDEN=1 .venv/bin/python -m pytest tests/test_planner.py -q`
  only when a plan's *shape* intentionally changes.
- No mid-execution fallback: a planner failure must **raise**, not silently
  degrade to a second implementation (matches `kod.py` install/rebuild policy).
- The host verb table is the ONLY host-side domain logic; do not add new
  planning/diff/schema logic to Python.

## File structure
| File | Action | Responsibility |
|---|---|---|
| `src/kod/lib/executor.lua` | Modify | Per-step dispatch: shell vs named-verb (Task 1). |
| `src/kod/planner.py` | Modify | Delete Python fallbacks in `plan_install`/`plan_rebuild`; raise on Lua failure. |
| `src/kod/executor.py` | Modify | Delete `Executor` class; keep/rename `execute_steps_lua` → `execute_steps`. |
| `src/kod/kod.py` | Modify | Call the single executor unconditionally; drop flag branch. |
| `src/kod/sections/packages.lua` | Modify | Emit verb steps, not a bulk shell command (Task 4). |
| `tests/test_executor_lua.py` | (exists) | Locks Task 1. |
| `tests/test_rebuild_lua.py` | Modify | Re-lock rebuild diff after Python diff deleted. |

---

### Task 1: Fix the Lua runner dispatch (Phase 0) — unblock the 7 red tests

**Files:**
- Modify: `src/kod/lib/executor.lua:53-67`
- Test: `tests/test_executor_lua.py` (already written, currently failing)

**Interfaces:**
- Consumes: step tables `{kind,name,program,args,chroot,timeout_s,on_error,meta}`,
  `ctx.mount_point`, `dispatch.step(step, ctx)` (may be absent).
- Produces: same `Executor.run(steps, ctx, dispatch, hooks)` signature; results
  `{success, error?, is_warning?}`.

The root cause: the runner sends *every* `system` step to `dispatch.step`, but a
step that carries a `program` is a shell command and must be run directly (and in
the pure-Lua tests `dispatch` has no `.step` at all). Fix the invariant:
**`program ~= ""` ⇒ shell step; otherwise named verb.**

- [ ] **Step 1: Confirm the failures**

Run: `.venv/bin/python -m pytest tests/test_executor_lua.py -q`
Expected: 7 failed (all in this file).

- [ ] **Step 2: Replace the per-step dispatch block in `executor.lua`**

Replace the current block (the `local result` / `if step.kind == "package" …`
through the `else … Unknown step kind … end`) with:

```lua
        local result
        if step.program and step.program ~= "" then
            -- Any step carrying a command is a shell step (system or disk).
            result = Executor.run_shell(step, ctx.mount_point)
        elseif step.kind == "package" or step.kind == "service" or step.kind == "system" then
            -- No command: a named verb. The host may run it, return "shell",
            -- or be absent (metadata-only no-op).
            if dispatch and dispatch.step then
                local ok, r = pcall(dispatch.step, step, ctx)
                if not ok then
                    result = { success = false, error = tostring(r) }
                elseif r == "shell" then
                    result = Executor.run_shell(step, ctx.mount_point)
                else
                    result = { success = true }
                end
            else
                result = { success = true }
            end
        else
            result = { success = false, error = "Unknown step kind: " .. tostring(step.kind) }
        end
```

- [ ] **Step 3: Run the file's tests**

Run: `.venv/bin/python -m pytest tests/test_executor_lua.py -q`
Expected: all pass (13).

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: **0 failed**, 17 skipped.

- [ ] **Step 5: Commit**

```bash
git add src/kod/lib/executor.lua
git commit -m "fix(executor): run program-bearing steps as shell, dispatch only verbs"
```

---

### Task 2: Delete the dead Python planner fallbacks (Phase 1)

**Files:**
- Modify: `src/kod/planner.py` (`plan_install` ~358-467, `plan_rebuild` ~470-557)
- Test: `tests/test_planner.py` (install golden), `tests/test_rebuild_lua.py`

The Lua planner is the default and the only functional path; the Python fallbacks
are broken dead code (`kind=program`/`user` steps the executor rejects,
`repos=None` crash). Delete them and make a Lua failure raise.

- [ ] **Step 1: Re-lock the rebuild diff before deleting its oracle**

The Python diff in `plan_rebuild` is currently the only reference for
`tests/test_rebuild_lua.py`'s equivalence test. Capture the exact step sequence
`rebuild.lua` produces for a representative state and assert it absolutely, so the
lock survives deletion. In `tests/test_rebuild_lua.py`, replace the
Lua-vs-Python equivalence assertion with an assertion against the expected literal
step list (kinds/names/actions in order).

- [ ] **Step 2: Delete the `plan_install` fallback**

In `plan_install`, remove the `# Fallback to Python planner` block and the
`try/except` degradation around `compose_steps_lua`. The function becomes: call
`compose_steps_lua(conf, distro)` (let it raise on failure), attach hooks, return.

- [ ] **Step 3: Delete the `plan_rebuild` fallback**

Same: remove the Python diff block; keep the Lua path (`compose_rebuild_steps_lua`)
and let it raise on failure.

- [ ] **Step 4: Delete now-orphaned helpers**

Grep for references, then delete helpers used only by the removed fallbacks
(candidates: `plan_disk_steps`, `predict_partition_list`). Keep anything still
imported (verify with a grep before deleting each).

```bash
grep -rn "plan_disk_steps\|predict_partition_list" src tests
```

- [ ] **Step 5: Run suite + install golden**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: green. If the install golden changed shape, inspect the diff first —
deleting a fallback must not change plan output; if it did, that is a bug, not a
regen.

- [ ] **Step 6: Commit**

```bash
git add src/kod/planner.py tests/test_rebuild_lua.py
git commit -m "refactor(planner): remove dead Python fallbacks, raise on Lua failure"
```

---

### Task 3: Unify execution on the Lua runner; drop the flag (Phase 1)

**Files:**
- Modify: `src/kod/executor.py` (delete `Executor` class), `src/kod/kod.py`,
  `src/kod/planner.py` (`KOD_USE_LUA_PLANNER`).
- Test: full suite.

With one planner, there is one executor. Remove the Python `Executor` class and
the flag branch so install/rebuild always use the Lua runner.

- [ ] **Step 1: Rename `execute_steps_lua` → `execute_steps`** (Lua is now the only
  path; the `_lua` suffix is noise). Update all references (`kod.py`, tests).

- [ ] **Step 2: Delete the `Executor` class** from `executor.py` (keep `StepError`,
  `StepResult`, `execute_steps`).

- [ ] **Step 3: Drop the flag branch in `kod.py`** install (~326-330) and rebuild
  (~570-575): always call `execute_steps(...)`. Remove `KOD_USE_LUA_PLANNER` from
  `planner.py` and any imports of it.

- [ ] **Step 4: Run suite**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: green.

- [ ] **Step 5: Commit**

```bash
git add src/kod/executor.py src/kod/kod.py src/kod/planner.py tests/
git commit -m "refactor(executor): single Lua runner, drop Python Executor + flag"
```

---

### Task 4: Standardize package/service steps on verbs; plumb repos into install (Phase 1)

**Files:**
- Modify: `src/kod/sections/packages.lua`, `src/kod/kod.py` (install env), possibly
  `src/kod/system/packages.py`.
- Test: `tests/golden/plan-testvm-empty.txt` (will change shape — intentional).

Today install installs packages as one bulk shell command (`packages.lua:25`) while
rebuild uses per-package verb steps through `manage_packages`. Two host paths for
one job. Standardize on **verb steps** so both share the host's package verb; this
requires install to provide `repos` (it currently doesn't).

- [ ] **Step 1: Emit verb steps from `packages.lua`**

Replace the single bulk `command=` step with one `kind="package"` verb step per
package, mirroring how `rebuild.lua` emits them:

```lua
    emit_steps = function(config, distro)
        local steps = {}
        if not config then return steps end
        for _, pkg in ipairs(config) do
            table.insert(steps, {
                kind = "package", name = pkg,
                meta = { action = "install" },
                order = 500,
            })
        end
        return steps
    end
```

- [ ] **Step 2: Plumb `repos` into the install executor env**

In `kod.py` install, build repos like rebuild does (`load_repos()` +
`dist.proc_repos(conf, current_repos, update=False, mount_point=mount_point)`) and
pass `repos=repos` to `execute_steps(...)`. Confirm `manage_packages` works for the
install chroot (fresh rootfs) — this is the riskiest step; verify with a real/VM run
or a focused test if one exists.

- [ ] **Step 3: Regenerate the install golden and eyeball the diff**

Run: `KODOS_WRITE_GOLDEN=1 .venv/bin/python -m pytest tests/test_planner.py -q`
Then inspect `git diff tests/golden/plan-testvm-empty.txt`: the one bulk pacman line
should become per-package `[package]` lines. Anything else changing is a bug.

- [ ] **Step 4: Run full suite**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: green with the updated golden committed.

- [ ] **Step 5: Commit**

```bash
git add src/kod/sections/packages.lua src/kod/kod.py tests/golden/plan-testvm-empty.txt
git commit -m "refactor(packages): install uses package verb steps + repos like rebuild"
```

---

## Follow-up plans (write when reached — not part of this plan)
- **Phase 2 — `rebuild-user` through the pipeline:** emit one user's steps
  (deploy-config closures, stage-filtered run-commands, user services) via the
  same closure-recording install uses, with `stage="rebuild-user"`, no chroot; run
  through `execute_steps`; delete the bypass in `kod.py:622`.
- **Phase 3 — `shell` reuse:** route `shell --package` through the shared package
  verb; keep the interactive TTY as host orchestration.
- **Phase 4 — host contract (objective 2):** write `docs/host-contract.md` — step
  schema, verb signatures, on_error/hooks/timeout semantics, lifecycle calls.
- **Phase 5 — docs:** mark the 2026-09-09 spec superseded; refresh extending guide.
