# KodOS Re-organization Plan

> **For agentic workers:** This is a *roadmap*, not a task-by-task code plan. Each
> phase lists concrete tasks; when a phase is chosen for execution, expand that
> phase into a bite-sized TDD plan (superpowers:writing-plans) before coding.

**Goal:** Collapse KodOS from two parallel planner/executor stacks (one Python,
one half-finished Lua) plus two bypass paths (`rebuild-user`, `shell`) into **one
planner + one executor**, so the four actions share common code and the Python
host becomes a thin, swappable layer around an embedded-Lua "brain."

**Architecture:** Lua owns *planning* (schema, validation, step composition/diff).
The host (Python today) owns *orchestration* (config load, generation lifecycle)
and *execution* (a generic step runner + a small dispatch table of domain verbs).
All four actions call the same planner with different parameters and run the same
executor.

**Tech Stack:** Python 3 + `lupa` (embedded Lua), Click CLI, btrfs/systemd/pacman
host tools. Lua modules under `src/kod/lib/` and `src/kod/sections/`.

**Spec:** Replaces the stale `specs/2026-09-09-architecture-redesign.md`, which
describes the *old* direction (Python brain, schema in Python). This doc is now
the source of truth for the *new* direction (Lua brain, swappable host).

---

## 0. State of play (what is actually true today)

Branch `feat/architecture-redesign`. Test baseline: **7 failed, 718 passed,
17 skipped** — all 7 failures in `tests/test_executor_lua.py`.

### The core problem: two parallel stacks that must stay in sync

| Concern | Python stack | Lua stack | Status |
|---|---|---|---|
| Install plan (baseline=empty) | `planner.plan_install` fallback (`src/kod/planner.py:358`) | `compose_steps_lua` → `lib/planner.lua` + 13 `sections/*.lua` | Lua is the default path (`KOD_USE_LUA_PLANNER=true`, `planner.py:14`). Python fallback is **dead/broken** (emits `kind=program`/`user` steps the executor rejects; `repos=None` crash). |
| Rebuild plan (baseline=current) | `planner.plan_rebuild` fallback (`planner.py:470`) | `compose_rebuild_steps_lua` → `lib/rebuild.lua` (pure diff) | Both work. Python fallback is now redundant. |
| Execution | `executor.Executor` class (`executor.py:35`) | `execute_steps_lua` → `lib/executor.lua` | **Lua runner is broken** (see below). Both are wired into `install`/`rebuild` behind the flag. |

### The 7 red tests — one root cause

`lib/executor.lua:54-62` routes package/service/system steps to
`dispatch.step(step, ctx)` and expects it to return the marker `"shell"` when a
step must be run as a shell command. But the bridge `dispatch_step`
(`executor.py:245`) only handles the *named-callable* case (`env.get(name)`) and
returns `None` otherwise — so a system step that carries a `program` (e.g.
`false`, `echo`) is treated as success **without ever running**. Fix: return
`"shell"` for steps with a non-empty `program` and no env callable, and handle
`kind=="disk"` (currently unhandled → would raise). This is the only blocker in
Phase 0.

### The two bypass paths (objective-4 gap)

- **`rebuild-user`** (`kod.py:622`): never builds a plan, never uses the
  executor. Directly calls `_core` helpers + `core/user_config.py`, which run Lua
  closures from `lib/configs.lua` filtered by `stage=="rebuild-user"`. No preview,
  no hooks.
- **`shell`** (`kod.py:655`): schroot session + optional
  `manage_packages_shell` + interactive root shell. Not a plan at all (it's an
  interactive TTY), but it re-implements package install instead of reusing the
  shared primitive.

### What is already correct (do not redo)

- **Schema in Lua** = single source of truth (`lib/schema.lua`, consumed by
  `config/schema.py:get_lua_schema`, validator, CLI). Objective 3 is essentially
  met; extension = add a `Schema.<name>` entry + a `sections/<name>.lua` with
  `emit_steps` + one line in `planner.lua:Planner.sections`.
- **One plan entry point**: `build_plan(conf, dist, baseline=...)`
  (`planner.py:560`) already unifies install/rebuild/plan. Objective 4 is met for
  those three; only rebuild-user and shell are outside it.

---

## 1. Objectives → acceptance criteria

| # | Objective | Acceptance criteria |
|---|---|---|
| 1 | Python orchestrates + executes commands from Lua planning | Every action's side effects come from steps the **Lua** planner produced; Python contains no step-composition or diff logic of its own. |
| 2 | Python replaceable by another language that embeds Lua | The host's role is describable as: *embed Lua → load config → run planner → run steps in order (on_error/hooks/timeout) → a small set of domain verbs.* No planning/diff/schema logic lives in the host. A second host could be written against this contract. |
| 3 | `configuration.lua` declarative; structure + extension defined in Lua | Adding a new config section requires only Lua changes (schema entry + section module). Validation, docs (`kod config schema`), and planning all derive from `lib/schema.lua`. |
| 4 | install / rebuild / rebuild-user / shell share common functions, passing params where needed | All four produce steps through **one** planner (differing only by parameters: baseline, scope, stage, chroot) and run through **one** executor. `shell` reuses the shared package-install verb. No action re-implements planning or execution. |

---

## 2. The one decision that shapes everything: where is the Lua/host line?

Two coherent targets satisfy objectives 1+4; they differ on objective 2's depth
and on how much work is done *now*.

**Option A — Thin host (recommended).**
Lua plans steps. Steps are either shell commands (`program`+`args`) or named
verbs from a small fixed set. The host = generic runner + dispatch table:
`package.install/remove`, `service.enable/disable`, `system.kernel_update`,
`system.initramfs_update`, `system.boot_entry`, `packages.update_all`, plus the
generation/btrfs lifecycle (snapshot, fstab, `.generation`). Swapping hosts =
port the generic loop (~trivial) + ~8 thin verbs that shell out to
pacman/systemctl/btrfs. All domain *planning* stays in Lua and moves with it.

**Option B — Fat Lua.**
Lua emits raw shell commands for *everything* (it builds the `pacman ...`,
`systemctl enable ...`, btrfs, fstab commands itself). The host has **zero**
domain knowledge: it just runs each step's command in order. Swapping hosts is
trivial and a single static binary is easy. Cost now: rewrite all `system/*.py`
modules as Lua command builders; the planner couples to exact CLI invocations
(harder to test, re-learns pacman/systemd flags in Lua).

**Recommendation: A now, B only when you actually swap.**
Rationale (ponytail): objective 1 literally says "Python executes the commands,"
and A satisfies objective 2's *constraint* (the host must embed Lua and be thin)
without paying B's cost today. B is the end-state for the single-binary goal, but
that goal isn't urgent, and A makes the swap surface explicit and small (~8 verbs)
instead of hiding it inside a big Lua rewrite. When you do swap, the port list is
exactly the dispatch table — nothing else.

> **DECISION GATE (Phase 0):** confirm A or B before Phase 1. The plan below is
> written for **A**; choosing B replaces Phases 1 and 4 with "rewrite system
> modules as Lua command builders."

---

## 3. Phased roadmap

### Phase 0 — Unblock + decide (gate; ~half a day)
Goal: green test suite + a committed direction.

- [ ] Fix `dispatch_step` in `executor.py`: return `"shell"` for steps with a
      non-empty `program` and no env callable; handle `kind=="disk"` by returning
      `"shell"`. (Resolves all 7 red tests.)
- [ ] Add the missing equivalence coverage already present in
      `tests/test_executor_lua.py`; run full suite → expect **0 failed**.
- [ ] Confirm Option A vs B (above). Record the decision at the top of this doc.

Acceptance: `.venv/bin/python -m pytest tests/ -q` is green; direction recorded.

### Phase 1 — Converge to one planner + one executor (the big win)
Goal: delete the dead Python stack so there is exactly one of each.

- [ ] Make `KOD_USE_LUA_PLANNER` the only path: remove the Python fallbacks in
      `plan_install` (`planner.py:386-467`) and `plan_rebuild` (`planner.py:518-557`).
      Keep `build_plan` as the single entry. (If B is chosen, this phase is
      "make the Lua planner emit shell commands for packages/services/system ops.")
- [ ] Delete `executor.Executor` class; keep only `execute_steps_lua` (rename to
      `execute_steps`). Update `install`/`rebuild` in `kod.py` to call it directly
      (drop the flag branch).
- [ ] Keep the Python *domain verbs* (`manage_packages`, `enable_services`,
      kernel/initramfs/boot hooks, generation btrfs ops) — they are the dispatch
      table for Option A, not dead code.
- [ ] Update `docs/kod/command-flows.md` (it currently documents the two-stack
      reality and lists gaps that Phase 1 closes).

Acceptance: one planner function per baseline, one executor; grep shows no
second composition path; suite green; install/rebuild/plan still produce identical
golden plans.

### Phase 2 — Route `rebuild-user` through the pipeline (objective 4)
Goal: rebuild-user = plan(scope=user, stage="rebuild-user") → execute.

- [ ] Extend the users section / a new user-scoped planner path to emit steps for
      one user: deploy-config closures, run-commands whose `stages` include
      `rebuild-user`, and user services to enable. Reuse the existing closure
      *recording* context (install already records these as chrooted `[system]`
      steps) — rebuild-user is the same recording with `stage="rebuild-user"` and
      no chroot.
- [ ] Run those steps through the shared executor (no chroot, live system).
- [ ] Remove the direct `_core`/`core/user_config.py` calls from
      `kod.py:622`; delete now-dead helpers.

Acceptance: `kod rebuild-user --user U` produces a plan (visible via `plan`) and
executes through the shared executor; hooks fire; no bypass path remains.

### Phase 3 — `shell` reuses the shared package verb (objective 4)
Goal: no re-implemented package install.

- [ ] Make `shell`'s optional install call the same `package.install` verb the
      executor uses (same repos handling), instead of a separate
      `manage_packages_shell`.
- [ ] Keep the interactive schroot TTY as host orchestration (it is not a plan).

Acceptance: package install logic exists in exactly one place; `shell --package`
uses it.

### Phase 4 — Host-swap preparation (objective 2)
Goal: make the host contract explicit and the swap cheap. *(Option A only.)*

- [ ] Write `docs/host-contract.md`: the exact steps schema, the dispatch-table
      verb signatures, the on_error/hooks/timeout semantics, and the lifecycle
      calls a host must perform around execution.
- [ ] Optionally: move 1–2 verbs toward Lua to prove the pattern (only if the
      swap is imminent — otherwise defer).

Acceptance: a second implementer could build a non-Python host from the contract
alone.

### Phase 5 — Docs/spec convergence
Goal: one source of truth.

- [ ] Mark `specs/2026-09-09-architecture-redesign.md` superseded by this doc.
- [ ] Refresh README/extending guide to describe adding a section (objective 3)
      and the host contract (objective 2).

---

## 4. Explicitly out of scope (do not start without a request)
- Custom-package build system (old spec Phase 5) — not part of these objectives.
- Debian parity beyond what `arch` already exercises.
- The single-binary build itself (that's the *result* of Phase 4, not a task).
