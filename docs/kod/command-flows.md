# KodOS command flows

Complete flow of each CLI command, based on the current code (branch
`feat/architecture-redesign`). Each stage is tagged **[Lua]** or **[Py]**.
`plan` is documented last as a read-only variant of `install`/`rebuild`.

## Architecture in one picture

```
 configuration.lua ──> load_config()  [Py bridge, persistent lupa runtime]
                             │
                      conf (Lua table)
                             │
         ┌──────────────────┴──────────────────┐
         │ baseline=empty            baseline=current
         ▼                                  ▼
  plan_install                     plan_rebuild
  (compose_steps_lua →            (Python gathers current/next state;
   planner.lua + 13 sections       lib/rebuild.lua emits the diff steps)
   from sections/*.lua)
         │                                  │
         └────────────┬─────────────────────┘
                      ▼
        execute_steps [Py bridge]  (executor.py)
          → lib/executor.lua [Lua runner], dispatch by step.kind:
            package  → env["manage_packages"]           (Py callback)
            service  → env["enable_services"/"disable_services"]
            system   → env[step.name] if callable, else shell
                        (chroot-wrapped when step.chroot), no-op if program==""
            disk     → shell
                      ▼
        hooks.py pre:/post: per kind [Py]
```

Shared building blocks:

| Block | Where | Lang |
|---|---|---|
| Config load | `_core.load_config` → `get_lua_runtime()` | Lua file, Py bridge |
| Distro select | `set_base_distribution` → `kod.arch` / `kod.debian` | Py |
| Hooks | `hooks.collect_hooks(conf.users)` | Py |
| Runner | `execute_steps()` → `lib/executor.lua` | both |
| Package mgmt | `system/packages.py` (`manage_packages`, …) | Py |
| Service mgmt | `system/services.py` (`enable_services`, …) | Py |
| Boot hooks | `system/boot.py` (`update_kernel_hook`, …) | Py |
| Lua composer | `lib/planner.lua` + `sections/*.lua` | Lua |
| Rebuild diff | `lib/rebuild.lua` (emits diff steps from state) | Lua |
| User config closures | `lib/configs.lua` (closures run by Py or recorded at plan time) | both |

---

## 1. `kod install <mount_point>` — kod.py:279

Installs a fresh generation-0 system into `mount_point`, chrooted.

```
 load_config(config)                    [Lua]
        │
 build_plan(baseline="empty")          [Py entry]
        │
 compose_steps_lua → lib/planner.lua   [Lua]
   composes 13 sections: base_distribution, repos, devices,
   boot, hardware, locale, network, users, desktop, fonts,
   packages, services, programs        [Lua, sections/*.lua]
   → converted to Python Step objects  [Py bridge]
        │
 collect_hooks(conf.users)               [Py]
        │
 execute_steps(steps, env, mount_point, use_chroot=True, hooks=…)  [Py bridge → Lua runner]
   env = {manage_packages, enable_services,
          kernel-update / initramfs-update / boot-entry hooks}
        │
        ├─ [system] raw shell steps from Lua sections
        │    → subprocess, wrapped: chroot <mount_point> sh -c '…'   [Py]
        ├─ packages: packages.lua emits ONE bulk pacman [system] step
        │    (not kind=package) — atomic install                [Lua plan, Py exec]
        ├─ kind=service → enable_services(use_chroot=True)        [Py dispatch]
        └─ kernel-update / initramfs-update / boot-entry
             → system/boot.py hooks (boot entry for generation 0)   [Py]
        │
 Finalization:
   store_packages_services(<mount>/kod/generations/0, …)            [Py]
   dist.generale_package_lock(mount_point, state_path)              [Py]
```

Notes:
- Install env has **no `repos` key** — fine, since install packages are a
  single raw pacman `[system]` step (not `kind=package`).
- The users section also plans per-user program/service config closures via
  a recording context: `configs.lua` closures run with a fake `execute` that
  captures shell commands, emitted as chrooted `[system]` steps. Only
  closures whose `stages` include `"install"` are planned here.

---

## 2. `kod rebuild [--new-generation] [--update]` — kod.py:442

Rebuilds the live system into a new (or updated) generation. **Diff-only** —
Python gathers the current/next state; `lib/rebuild.lua` emits the diff steps
(no install sections).

```
 load_config(config)                    [Lua]
        │
 Generation bookkeeping:
   get_max_generation()                                   [Py]
   read /.generation → current_generation                [Py]
   load_packages_services(/kod/generations/<cur>)         [Py]
        │
 if --new-generation:
   btrfs subvolume snapshot / <next>/rootfs               [shell via exec]
   create_next_generation(boot, root, gen_id)            [Py system/filesystem.py]
     (mount /.next_current, subvolumes, fstab)           [Py + shell]
   use_chroot = True, new_root_path = <mounted>
 else:
   snapshot / → /kod/current/old-rootfs                  [shell via exec]
   copy state files, use_chroot = False, new_root_path = "/"
        │
 Repos:
   load_repos()                                          [Py]
   dist.proc_repos(conf, repos, update, mount_point)     [Py arch.py]
        │
 if --update:
   dist.refresh_package_db + update_all_packages         [Py]
        │
 plan_rebuild(conf, dist, current_packages, current_services, …)  [Py]
   Python gathers state (get_packages_to_install, get_services_to_enable,
   kernel_update_required), then compose_rebuild_steps_lua emits:      [Lua]
     Step("system","update-packages")      (if --update)
     Step("package", …, action=remove/install)
     Step("service", …, action=disable/enable)
     Step("system","kernel-update"/"initramfs-update")  (if kernel changed)
     Step("system","boot-entry", meta={kernel})         [always]
   + hook names attached                                 [Py]
        │
 execute_steps(steps, env, new_root_path, use_chroot, repos=repos, hooks=…)  [Py bridge → Lua runner]
   env = {manage_packages, enable_services, disable_services,
          update_all_packages, kernel-update/initramfs-update/boot-entry}
        │
 Finalization:
   store_packages_services(<next>, …)                    [Py]
   dist.generale_package_lock(new_root_path, <next>)     [Py]
   if not --new-generation:
     mv rootfs between generations                       [shell via exec]
     change_subvol + generate_fstab                      [Py system/filesystem.py]
   write <next>/rootfs/.generation = generation_id       [Py]
   if --new-generation: umount -R new_root_path          [shell via exec]
        │
 on failure: _cleanup_failed_generation (unmount, delete subvols)  [Py + shell]
```

Notes:
- Rebuild is the only flow that dispatches `kind=package` steps through
  `manage_packages` with a real `repos` dict.
- The boot entry is written by the `boot-entry` plan step during execution,
  not in finalization.

---

## 3. `kod rebuild-user [--user U]` — kod.py:616

Re-applies one user's configuration on the **live system** (no chroot, no
plan/runner). This is the runtime dispatch path for the Lua closures that
install only *records*.

```
 load_config(config)                    [Lua]
        │
 ctx = Context(user, mount_point="/", use_chroot=False, stage="rebuild-user")  [Py]
        │
 Per user:
   user_dotfile_manager(info)           [Py _core.py]
   user_configs(user, info)             [Py _core.py]
   proc_user_home(ctx, user, info)      [Py system/users.py]
   configure_user_dotfiles(ctx, user, configs, dotfile_mngrs)  [Py core/user_config.py]
     → runs Lua closures from configs.lua (dotfile managers)      [Lua closures]
   configure_user_scripts(ctx, user, configs)                     [Py core/user_config.py]
     → runs Lua closures filtered by stage == "rebuild-user"
       (e.g. dconf; install-stage closures are skipped)           [Lua closures]
   user_services(user, info)            [Py _core.py]
   enable_user_services(ctx, user, svcs)  [Py system/services.py]
```

Notes:
- Bypasses plan/runner entirely: no preview, no lifecycle hooks.
- `core/user_config.py` cannot be ported to Lua — it dispatches closures at
  runtime on the live system; install only records them.
- Stage filtering is hardcoded in Python (`stage="rebuild-user"`).

---

## 4. `kod shell [--package PKG …]` — kod.py:648

Interactive root shell inside the KodOS chroot, with optional package install.

```
 exec("schroot -c virtual_env -b")      [shell] → session id
        │
 if --package:
   load_repos()                         [Py]
   manage_packages_shell(repos, "install", packages, chroot=session)  [Py]
        │
 exec("schroot -r -c <session> -p")     [shell] interactive root shell
 exec("schroot -e -c <session>")        [shell] exit/cleanup
```

Note: depends on `/etc/schroot/chroot.d/virtual_env.conf` existing — see GAPS §2.

---

## 5. `kod plan [--baseline empty|current]` — kod.py:419

Read-only preview of the exact steps install/rebuild would run.

- `--baseline empty` → `plan_install` (same Lua composer as install).
- `--baseline current` → `_load_current_state()` + `plan_rebuild` (same diff
  planner as rebuild).
- Output: `render_plan(steps, baseline, config)` — deterministic text,
  golden-file tested.

---

## Incomplete / gaps (as of this branch)

1. **Dead Lua sections.** `dotfiles.lua`, `users-advanced.lua`, and
   `ssh-keys.lua` are not in `planner.lua`'s section list, so per-user
   `dotfiles` blocks and `ssh_keys` are never deployed during install. The
   logic exists but is unreachable.
2. **os-release + schroot config gone.** `configure_system` was deleted;
   nothing writes `/etc/os-release` or `/etc/schroot/chroot.d/*`. On a fresh
   install, `kod shell` will not work (it works on legacy hosts where the
   files already exist).
3. **rollback commented out** (kod.py:663–686).
4. **rebuild-user bypasses plan/runner**: no preview, no hooks; stage filter
   hardcoded in Python.
5. **deploy_config / dotfile_manager legacy path**: `configure_user_dotfiles`
   uses `info.dotfile_manager`; the example config doesn't use it and
   users.lua never plans a deploy_config step.
6. **Rebuild plan is diff-only by design** (`lib/rebuild.lua`). Install-only
   features (users-section config closures, desktop, fonts, …) never appear in
   a rebuild plan; that's expected since the snapshot already contains them.
