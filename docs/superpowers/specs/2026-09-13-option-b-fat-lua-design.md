# KodOS Option B — "Fat Lua" Command Emission — Design Specification

**Date:** September 13, 2026
**Status:** Design Review Required
**Scope:** Move the remaining *command* emission from Python host callables into Lua so the host runs only raw shell steps + owns generation layout. Ports three verb categories (services; package install/remove on rebuild; full package update) to raw command steps; deletes the now-orphaned `manage_packages` / `enable_services` / `disable_services` callables and their dispatch branches. Kernel/bootloader file management (kernel-update, initramfs-update, boot-entry) stays host-side.
**Not a scope change to:** host language (Python + lupa stays), distribution model, generation/rollback mechanism, `kod shell` (separate requirement doc).

---

## 1. Purpose

Complete the Option A → B progression for the *command* verbs. After Option A, planning is Lua; the host still executes some steps via Python callables reached through `dispatch.step`. Option B converts the true command verbs — package install/remove, service enable/disable, full package update — into raw shell steps the generic runner already executes, and deletes their Python callables + dispatch branches.

The kernel/bootloader file-management hooks (`kernel-update`, `initramfs-update`, `boot-entry`) are **deliberately kept host-side**: they derive (in-chroot `pacman -Ql … | grep vmlinuz` → kver) and write files (systemd-boot `.conf` + `loader.conf`, reading the root device from `/etc/fstab`). That is on-disk generation layout — the same category as the btrfs generations + state files the host already owns — not pure data→command. Forcing it into a shell string would hide multi-step file I/O from the plan preview and fork badly per distro (pacman-specific). See §9.

## 2. Current state — what's already Fat-Lua, what moves, what stays

Two domain categories are *already* emitted as raw command steps on every path; no work:

- **users** — `sections/users.lua:83` emits `useradd -m -s <shell> <name>` + config-file steps. No `kind="user"` verb exists anywhere.
- **install packages** — `sections/packages.lua:25` emits `{ command = Repos.install_cmd(distro, list), chroot = true }`.

**Moves to raw command steps (this plan):**

| Verb | Emitters today | Distro fork? |
|---|---|---|
| `service` | `sections/services.lua:28`, `desktop.lua:66,156`, `programs.lua:69`, `rebuild.lua:55,97` | no (`systemctl` uniform) |
| `package` (rebuild only) | `lib/rebuild.lua:72` (remove), `:88` (install) | yes — reuses `Repos.install_cmd` + a new remove cmd |
| `update-packages` | `lib/rebuild.lua:50` | yes — distro full-update |

**Stays host-side (kept as `system` verb steps → Python hooks):**

| Verb | Why it stays |
|---|---|
| `kernel-update` (`rebuild.lua:92`, `sections/boot.lua:60`) | in-chroot `pacman -Ql <pkg> \| grep vmlinuz` → kver, then `cp … /boot/vmlinuz-<kver>`; Arch-specific derivation |
| `initramfs-update` (`rebuild.lua:93`, `sections/boot.lua:68`) | same kver derivation + `dracut --kver <kver> …` |
| `boot-entry` (`rebuild.lua:100`, `sections/boot.lua:98`) | reads `/etc/fstab` root device, derives kver, writes `entries/kodos-<gen>.conf` + `loader.conf` — file I/O, not a command |

## 3. Step contract (unchanged)

Two step shapes already exist; Option B only changes which one each domain emits. No runner change.

- **Raw command step** — carries the shell command; `executor.lua` runs it under `timeout` + optional `chroot`. Two equivalent encodings, both normalized to `program` at the Python bridge (`planner.py:50`: `program = lua_step.program or lua_step.command`):
  - `{ name, description, command = "<full shell string>", chroot = bool }` — the `packages.lua` form; **this is what Option B builders emit** (simplest for multi-arg systemctl/pacman commands).
  - `{ kind = "disk", program = "...", args = {...} }` — the disk-step form (`planner.py:329`).
- **Verb step** — `{ kind ∈ {package, service, system}, name, meta, on_error }`, no command → routed to `dispatch.step` (`executor.lua:57`). Option B eliminates the `package` and `service` kinds; `system` remains for the three boot hooks.

## 4. Command builders (new)

New `lib/domains/` modules. Each is a thin `(distro, inputs) → command string` function mirroring the existing `Repos.install_cmd(distro, …)` precedent. The builder is the *only* place that knows the CLI; sections just wrap its return value in a raw step. Builders receive the same inputs the current Python callable receives (e.g. `repos`) — passed through `ctx`/`meta` — so no capability is dropped; only the location of the CLI knowledge moves.

- `domains/services.lua` — distro-uniform: `enable(svc)` / `disable(svc)` → `systemctl enable|disable <svc>` (the chroot form plan steps use; the live `--now` variant is not emitted by any section).
- `domains/packages-{arch,debian}.lua` — extend the `Repos` install/remove templates: pacman `-S`/`-Rscn` vs apt-get install/remove. Rebuild emits one raw step per package (install or remove), matching `manage_packages`' per-repo command for the official repo.
- Full-update command for `update-packages`: distro full-update (`pacman -Syu …` / apt upgrade) sourced from the same `Repos` update template.

No boot builders — those verbs stay host-side (§2, §9).

## 5. Porting order

Each flip is the same three actions, and the suite must be green before starting the next:

1. **Flip emitters** — change the listed section/rebuild lines to emit raw command steps via the new builder.
2. **Regen goldens** — step-list goldens change from `{kind=…}` to `{command="…"}`; `KODOS_WRITE_GOLDEN=1 .venv/bin/python -m pytest tests/test_planner.py::TestGolden -q`.
3. **Delete Python** — remove the now-orphaned callable(s) and their `dispatch` branch in `executor.py`; stop passing the env callable from `kod.py`.

Order (lowest blast radius first):

1. **services** — distro-uniform, proves the multi-emitter → shared-builder pattern (4 files); deletes `enable/disable_services` + the `service` dispatch branch.
2. **packages/rebuild** — reuses `Repos` install/remove; only `rebuild.lua` emits; deletes `manage_packages` + the `package` dispatch branch.
3. **update-packages** — one step, distro full-update; removes that callable / inlines the command.

After all three, `dispatch_step` handles only the `system` kind (the three boot hooks); the `package` and `service` branches are gone.

## 6. Error handling

Unchanged. A raw command step failing → non-zero exit → `StepError`; per-step `on_error` warn/abort is already applied in `executor.lua:76-81`. No fallback added — the "no mid-execution degradation" invariant holds as-is.

## 7. Testing strategy

- **Builder unit tests** — one small test per new builder: inputs → expected command string (fast, no VM).
- **Golden step-lists** — regen after each flip; rebuild goldens go from `{kind=package,…}` to `{command="pacman -Rscn …"}`, etc. Install goldens already show `command` steps for packages/users.
- **Suite green per verb** — full `.venv/bin/python -m pytest tests/ -q` green after each of the three flips (incremental, not one big bang).
- `test_hooks.py` unaffected (tests hook firing paths, not verbs).

## 8. Final deletions & success criteria

Deleted once orphaned:

- `system/packages.py`: `manage_packages` (+ its exec path) — *only if* rebuild is the last caller (verify no other caller before deleting).
- `system/services.py`: `enable_services` / `disable_services`.
- `executor.py`: the `package`, `service` dispatch branches.
- `kod.py`: the env callables passed for those verbs.

**Stays:** `system/boot.py` hooks + `arch.get_kernel_file` (kernel/bootloader file mgmt); any `system/packages.py` state-gathering that rebuild's Python state-gatherer still imports; btrfs/state in the host.

**Success ("embeddable host"):** the host runs raw command steps for all package/service/update work and owns kernel/bootloader/btrfs/state layout. Dispatch shrinks to the three boot hooks. (Not "zero Python" — the host legitimately owns generation layout.)

## 9. Why the boot verbs stay host-side

- They are file management + derivation, not single invocations (esp. `boot-entry`: reads fstab, writes two files with computed content). A raw step is one inspectable command; wrapping this in `sh -c '<heredoc>'` hides multi-step file I/O from `kod plan`.
- Arch/systemd-boot-specific: `get_kernel_file` = in-chroot `pacman -Ql <pkg> | grep vmlinuz` + kver-from-path; no clean Debian twin. Porting re-implements pacman output parsing in bash and forks per distro — fragile.
- Same category as the btrfs/state the host already owns (on-disk generation layout), so it is consistent with the locked boundary, not a hole.
- Reversible: porting them later is additive and does not block the command ports.

## 10. References

- `docs/superpowers/plans/2026-09-13-kod-reorganization.md` — Option A/B definitions (Option B "Fat Lua").
- `docs/superpowers/plans/2026-09-13-option-a-foundation.md` — completed Tasks 1–4 (planner convergence).
- `src/kod/lib/executor.lua`, `src/kod/planner.py:50` — step contract & normalization.
