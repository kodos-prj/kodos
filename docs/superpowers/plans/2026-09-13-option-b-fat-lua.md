# KodOS Option B — "Fat Lua" Command Emission — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the remaining *command* verbs — service enable/disable and package install/remove (rebuild) — from Python host callables into Lua-emitted **raw command steps**, then delete the now-orphaned Python callables and their dispatch branches. After this, `dispatch_step` handles only the `system` kind (the three boot hooks + the no-op `update-packages`).

**Architecture:** Option A already made planning Lua; the host still executed some steps via Python callables reached through `dispatch.step`. The generic runner (`kod/lib/executor.lua`) **already runs raw command steps** (program-first, under `timeout` + optional `chroot`). So each port is: (1) make the section/rebuild emitters emit `{kind=…, name=…, command="<shell>", chroot=bool}` instead of a verb step, (2) regen goldens / update absolute assertions, (3) delete the orphaned callable + its dispatch branch + env wiring. No runner change.

**Tech Stack:** Python 3 + lupa (LuaJIT bridge), pytest. Lua emitters in `src/kod/sections/*.lua` and `src/kod/lib/rebuild.lua`; Python bridge in `src/kod/planner.py`; execution in `src/kod/executor.py`.

**Spec:** `docs/superpowers/specs/2026-09-13-option-b-fat-lua-design.md`

## Global Constraints

These hold for every task. Do not deviate.

- **Step contract (unchanged).** A raw command step is `{ name, description?, command = "<full shell string>", chroot = bool }`. The Python bridge normalizes `program = lua_step.program or lua_step.command` (`planner.py:50`). The runner runs program-first: a step with a non-empty `program`/`command` goes to `run_shell`; only program-less steps fall through to `dispatch.step` (`executor.lua`).
- **KEEP `kind` on ported steps.** Hooks fire by `pre:<kind>`/`post:<kind>` and goldens label `[kind]`. Ported steps keep `kind="service"` / `kind="package"` — only `command` + `chroot` are added and `meta={action=…}` is dropped. Do NOT drop `kind` (it would default to `"system"` at `planner.py:48` and break hook keys).
- **chroot mapping.** Install always chroots → install emitters hardcode `chroot = true`. Rebuild: `use_chroot == new_generation` exactly (`kod.py:503/509`). In rebuild, live (not `new_generation`) means append `--now` to systemctl and `chroot = false`; `new_generation` means no `--now` and `chroot = true`. This mirrors `enable_services`/`disable_services` (`system/services.py:158-213`).
- **No mid-execution fallback.** A raw step failing → non-zero exit → `StepError`; per-step `on_error` warn/abort already applied in the runner. Add no fallback.
- **Rebuild package commands are official-repo only** (`pacman`/`apt-get`), matching install's existing "repo-prefix passed through unparsed" ponytail (`test_planner.py:218`). Multi-repo privilege wrapping from `manage_packages` is intentionally dropped for rebuild (spec §4); it matches install behavior.
- **Test command:** `.venv/bin/python -m pytest tests/ -q`.
- **Golden regen:** `KODOS_WRITE_GOLDEN=1 .venv/bin/python -m pytest tests/test_planner.py::TestGolden -q` (only `tests/golden/plan-testvm-empty.txt` exists — the install/empty baseline).
- **Commit policy:** one commit per task (functional code + its test updates together; exclude this plan `.md`). Message style: `type: summary`.

## File Structure

Modified (no new files):
- `src/kod/sections/services.lua`, `programs.lua`, `desktop.lua` — install service emitters → command steps.
- `src/kod/lib/rebuild.lua` — rebuild service + package verb steps → command steps; add `distro`/`Repos` usage.
- `src/kod/lib/repos.lua` — add `remove_cmd(distro, packages)` (mirror `install_cmd`).
- `src/kod/planner.py` — `plan_rebuild` state dict: add `"distro"`.
- `src/kod/executor.py` — delete `package` + `service` dispatch branches (keep `system`).
- `src/kod/kod.py` — remove env entries + imports for the deleted callables.
- `src/kod/system/services.py` — delete `disable_services` (keep `enable_services`).
- `src/kod/system/packages.py` — delete `manage_packages`.
- `src/kod/core/__init__.py` — drop re-export names for the two deleted functions.

Tests updated:
- `tests/test_planner.py` — install service emission; rebuild service/package absolute assertions.
- `tests/test_rebuild_lua.py` — `test_combined_diff_ordering` lines (service in Task 1, package in Task 2).
- `tests/test_executor_lua.py` — delete the two dispatch-routing tests; rework the two hook tests to command steps.
- `tests/system/test_services.py` — delete `test_disable_services_callable`.
- `tests/system/test_packages.py` — delete the `manage_packages` tests + import.

---

## Task 1: services → raw command steps

Emitters (all install) currently emit `{kind="service", name=…, command="", meta={action="enable"}}`; rebuild emits verb steps via `add("service", svc, {action=…})`. Flip them to carry the `systemctl` command. Then delete the `service` dispatch branch + `disable_services`.

- [ ] **1.1 Write failing test — install service emission.** Add to `TestPlanInstall` in `tests/test_planner.py`:
  ```python
      @patch("kod.system.packages.get_base_packages", return_value=BASE_PKGS)
      def test_service_emits_systemctl_enable(self, _mock):
          from kod.planner import plan_install

          conf = make_conf(services={"sshd": {"enable": True}})
          svc = next(s for s in plan_install(conf) if s.name == "sshd")
          assert svc.kind == "service"
          assert svc.program == "systemctl enable sshd"
          assert svc.chroot is True
  ```
- [ ] **1.2 Run it — confirm it FAILS** (currently `program == ""`):
  `.venv/bin/python -m pytest tests/test_planner.py::TestPlanInstall::test_service_emits_systemctl_enable -q`

- [ ] **1.3 Flip the four install emitters.** In each, replace `command = ""` + `meta = { action = "enable" }` with the real command + `chroot = true`.
  - `src/kod/sections/services.lua` (~line 27):
    ```lua
                    table.insert(steps, {
                        kind = "service",
                        name = service_name,
                        description = "Enable service on boot: " .. service_name,
                        command = "systemctl enable " .. service_name,
                        chroot = true,
                        order = 700,
                    })
    ```
  - `src/kod/sections/programs.lua` (~line 68): set `command = "systemctl enable " .. unit`, `chroot = true`; remove `meta`.
  - `src/kod/sections/desktop.lua` (two blocks, ~line 65 and ~line 155): set `command = "systemctl enable " .. dm_service`, `chroot = true`; remove `meta`. Keep each block's existing `order` + `depends_on`.
  - Note: user-level services (e.g. `users.bob.services.*`) are funneled into `config.services` by `merge_user_programs_services` (`lib/planner.lua:102`) before sections run, so `services.lua` is the single install service-enable emitter — no users-section change needed.

- [ ] **1.4 Flip rebuild service steps.** In `src/kod/lib/rebuild.lua`:
  - Add after line 47 (`local next_kernel = …`): `local new_gen = state.new_generation`
  - Disable block (~line 53) — disable only runs when NOT `new_generation`, so it is always live (`--now`, no chroot). Replace the inner `add("service", svc, { action = "disable" })`:
    ```lua
        for _, svc in ipairs(sorted_diff(to_set(state.current_services), to_set(state.next_services))) do
            table.insert(steps, { kind = "service", name = svc,
                command = "systemctl disable --now " .. svc, chroot = false })
        end
    ```
  - Enable block (~line 96) — runs for both generations; live appends `--now`. Replace the inner `add("service", svc, { action = "enable" })`:
    ```lua
        for _, svc in ipairs(sorted_diff(to_set(state.next_services), to_set(state.current_services))) do
            table.insert(steps, { kind = "service", name = svc,
                command = "systemctl enable " .. svc .. (new_gen and "" or " --now"), chroot = new_gen })
        end
    ```
  - Keep the `add` helper (still used by the four `system` verb steps) and the `update-packages`/`kernel-update`/`initramfs-update`/`boot-entry` steps unchanged.

- [ ] **1.5 Update affected assertions.**
  - `tests/test_planner.py::TestPlanInstall::test_services_users_programs` (~line 233): replace the `svcs`/`("gpg", {"action":"enable"})` assertion with:
    ```python
        gpg = next(s for s in steps if s.kind == "service" and s.name == "gpg")
        assert gpg.program == "systemctl enable gpg"
        assert gpg.chroot is True
    ```
  - `tests/test_planner.py::TestPlanRebuild::test_service_diff_and_order` (~line 260): replace the `acts = {…meta["action"]…}` assertion with:
    ```python
        prog = {s.name: s.program for s in steps if s.kind == "service"}
        assert prog == {"oldsvc": "systemctl disable --now oldsvc",
                        "newsvc": "systemctl enable --now newsvc"}
    ```
    (default `new_generation=False` → live `--now`).
  - `tests/test_rebuild_lua.py::TestRebuildPlanAbsolute::test_combined_diff_ordering` (~line 104): change ONLY the service line to the command form; leave package lines for Task 2:
    ```python
            "002 [service] oldsvc: systemctl disable --now oldsvc",
    ```

- [ ] **1.5b Regen the install golden.** The install golden has service lines (`tests/golden/plan-testvm-empty.txt:62-66`) that now render as `systemctl enable …`:
  `KODOS_WRITE_GOLDEN=1 .venv/bin/python -m pytest tests/test_planner.py::TestGolden -q`

- [ ] **1.6 Delete the `service` dispatch branch + `disable_services`.**
  - `src/kod/executor.py`: remove the `elif kind == "service":` block (lines ~72-77). Keep `package` (Task 2), `system`, and the `else raise`.
  - `src/kod/kod.py`: remove `"enable_services"` + `"disable_services"` from both env dicts (install ~line 309; rebuild ~line 548-549) and from the `from kod.core import (…)` list.
  - `src/kod/system/services.py`: delete `def disable_services(…)` (~line 187-213). **Keep** `enable_services` — it is still called by `enable_services_from_programs` (`services.py:279`).
  - `src/kod/core/__init__.py`: remove `'disable_services'` from the service re-export set (~line 42) and from `__all__` (~line 79). Keep `enable_services`.
  - `tests/system/test_services.py`: delete `test_disable_services_callable` (~line 16-20).
  - `tests/test_executor_lua.py`: delete `test_service_dispatch` (~line 109-119) — the service dispatch path no longer exists (shell execution is covered by `test_shell_step_through_bridge`).

- [ ] **1.7 Verify orphanhood + suite green.**
  - Grep to confirm `disable_services` has zero remaining references: `.venv/bin/python -c "import subprocess,sys"` not needed — run: search `disable_services` across `src/` and `tests/`; expect only the (now-removed) sites. If any live caller remains, STOP and re-scope instead of deleting.
  - `.venv/bin/python -m pytest tests/ -q` → all green.

- [ ] **1.8 Commit.** `git add -A && git commit -m "refactor: emit service steps as raw systemctl commands; drop service dispatch"` (exclude this plan `.md`).

---

## Task 2: packages/rebuild → raw command steps

Rebuild is the only place package steps are verbs (`rebuild.lua` remove/install). Install already emits one bulk command step. Flip rebuild's package verb steps to `Repos.install_cmd`/new `remove_cmd`, add `distro` to the rebuild state, then delete `manage_packages` + the `package` dispatch branch.

- [ ] **2.1 Write failing test — rebuild package emission.** Add to `TestPlanRebuild` in `tests/test_planner.py`:
  ```python
      @patch("kod.system.packages.get_base_packages", return_value=BASE_PKGS)
      def test_package_commands_official(self, _mock):
          from kod.planner import plan_rebuild

          conf = make_conf(packages=["keep", "new"])
          current_packages = {"packages": ["keep", "gone"], "kernel": "linux"}
          steps = plan_rebuild(conf, make_dist(), current_packages, [], {})
          prog = {s.name: s.program for s in steps if s.kind == "package"}
          assert prog == {"gone": "pacman -Rscn --noconfirm gone",
                          "new": "pacman -S --noconfirm new"}
  ```
- [ ] **2.2 Run it — confirm it FAILS** (currently `program == ""`):
  `.venv/bin/python -m pytest tests/test_planner.py::TestPlanRebuild::test_package_commands_official -q`

- [ ] **2.3 Add `remove_cmd` to `src/kod/lib/repos.lua`.** Mirror `install_cmd` (line 89) and add to the export table (line ~104):
  ```lua
  local function remove_cmd(distro, packages)
      local pkg_str = type(packages) == "string" and packages or table.concat(packages, " ")
      if distro == "arch" then
          return "pacman -Rscn --noconfirm " .. pkg_str
      elseif distro == "debian" then
          return "apt-get remove -y " .. pkg_str
      end
      return nil
  end
  ```
  and add `remove_cmd = remove_cmd,` to the returned table.

- [ ] **2.4 Add `distro` to rebuild state.** In `src/kod/planner.py::plan_rebuild`, add one key to the state dict passed to `compose_rebuild_steps_lua` (~line 385):
  ```python
          "new_generation": new_generation,
          "kernel_update_required": kernel_update_required,
          "distro": conf.base_distribution or "arch",
  ```

- [ ] **2.5 Flip rebuild package steps.** In `src/kod/lib/rebuild.lua`:
  - Add near the top (after `local Rebuild = {}`): `local Repos = require('kod.lib.repos')`
  - Add after the `new_gen` line from Task 1: `local distro = state.distro`
  - Remove loop (~line 71) — replace `add("package", p, { action = "remove" }, "warn")`:
    ```lua
        for _, p in ipairs(removes) do
            local cmd = Repos.remove_cmd(distro, p)
            if cmd then
                table.insert(steps, { kind = "package", name = p, command = cmd, chroot = new_gen, on_error = "warn" })
            end
        end
    ```
  - Install loop (~line 87) — replace `add("package", p, { action = "install" })`:
    ```lua
        for _, p in ipairs(installs) do
            local cmd = Repos.install_cmd(distro, p)
            if cmd then
                table.insert(steps, { kind = "package", name = p, command = cmd, chroot = new_gen })
            end
        end
    ```

- [ ] **2.6 Update affected assertions.**
  - `tests/test_planner.py::TestPlanRebuild::test_diff_mapping` (~line 255): replace the `acts = {…meta["action"]…}` assertion with:
    ```python
        prog = {s.name: s.program for s in steps if s.kind == "package"}
        assert prog == {"gone": "pacman -Rscn --noconfirm gone", "new": "pacman -S --noconfirm new"}
        removed = next(s for s in steps if s.name == "gone")
        assert removed.on_error == "warn"
    ```
  - `tests/test_rebuild_lua.py::TestRebuildPlanAbsolute::test_combined_diff_ordering` (~lines 105-108): change the package lines to:
    ```python
            '003 [package] extra: pacman -Rscn --noconfirm extra',
            '004 [package] gone: pacman -Rscn --noconfirm gone',
            '005 [package] linux-lts: pacman -S --noconfirm linux-lts',
            '006 [package] new: pacman -S --noconfirm new',
    ```
  - `tests/test_executor_lua.py`: delete `test_package_dispatch_gets_python_types` (~line 97-107). Rework the two hook tests to command steps (drop the `fake_manage`/`called` tracking):
    ```python
        def test_pre_hook_failure_aborts(self):
            def bad_pre(step, ctx):
                raise ValueError("pre boom")
            with pytest.raises(StepError):
                execute_steps([Step("package", "git", program="true")],
                              {}, "/mnt", True, hooks={"pre:package": [bad_pre]})

        def test_post_hook_failure_is_swallowed(self):
            def bad_post(step, ctx):
                raise ValueError("post boom")
            results = execute_steps([Step("package", "git", program="true")],
                                    {}, "/mnt", True, hooks={"post:package": [bad_post]})
            assert results[0].success
    ```

- [ ] **2.7 Delete the `package` dispatch branch + `manage_packages`.**
  - `src/kod/executor.py`: remove the `if kind == "package":` block (lines ~64-71). Now only `system` + `else raise` remain; drop the now-unused `uc = ctx_lua.use_chroot` line if it becomes dead.
  - `src/kod/kod.py`: remove `"manage_packages"` from both env dicts (~line 308, ~547) and from the import list.
  - `src/kod/system/packages.py`: delete `def manage_packages(…)` (~line 367-449). **Keep** `manage_packages_shell` (used at `kod.py:659`) and `update_all_packages`.
  - `src/kod/core/__init__.py`: remove `'manage_packages'` from the packages re-export set (~line 27) and from `__all__` (~line 69).
  - `tests/system/test_packages.py`: delete the import of `manage_packages` (~line 8) and all `test_manage_packages_*` tests (~line 97-231).

- [ ] **2.8 Verify orphanhood + suite green.**
  - Grep `manage_packages` across `src/` and `tests/`; expect only `manage_packages_shell` (different function) to remain. If a live caller of `manage_packages` remains, STOP and re-scope.
  - `.venv/bin/python -m pytest tests/ -q` → all green.

- [ ] **2.9 Commit.** `git add -A && git commit -m "refactor: emit rebuild package steps as raw pacman/apt commands; drop manage_packages"` (exclude this plan `.md`).

---

## Out of scope / deferred: `update-packages`

The spec lists a third verb (`update-packages`, `rebuild.lua:50`). Exploration found it is **not** a clean command-builder port, so it is deferred rather than half-done:

- The emitted step name is `"update-packages"`, but the rebuild env key is `"update_all_packages"` (`kod.py:550`) — they don't match, so the step is currently a **no-op** through the `system` dispatch branch.
- The real full-update runs directly at `kod.py:528` (`update_all_packages(new_root_path, new_generation, repos)`), which iterates **all repos** and applies per-repo privilege wrapping (`_get_privilege_level`/`_build_privilege_command`). That needs the host-side `repos` dict — not just `distro` — so it does not fit the thin `(distro, inputs) → command` builder shape the other ports use.
- It is independent of the end-state: after Tasks 1+2, `dispatch_step` already handles only the `system` kind. Deferring leaves everything consistent (no-op step + direct host call, as today).

Add it later as its own task if a visible full-update plan step is wanted: thread `repos` into the rebuild state, emit one command per repo's `update` template, and remove the direct `kod.py:528` call to avoid a double update.

---

## Self-review (run before handing off)

- **Spec coverage:** §2 "moves" table → services (Task 1), package install/remove (Task 2). §8 deletions → `manage_packages`, `disable_services`, both dispatch branches, env callables all covered. `enable_services` intentionally kept (still referenced by `enable_services_from_programs`). update-packages deferred with reason (above) — flag to user.
- **Placeholder scan:** every edit shows the exact replacement code; no "TBD"/"similar to Task N".
- **Type/name consistency:** ported steps keep `kind` + `name`; add `command` + `chroot`; drop `meta={action=…}`. Rebuild uses `state.new_generation` (existing) + `state.distro` (added in 2.4). `Repos.remove_cmd` mirrors `Repos.install_cmd`.
- **Green gate:** full suite green at the end of each task before starting the next; golden regenerated only if install goldens change (service lines do — run the regen command in Task 1 step between 1.5 and 1.7).
