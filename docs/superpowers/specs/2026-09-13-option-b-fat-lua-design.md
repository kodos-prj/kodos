# KodOS Option B — "Fat Lua" Command Emission — Design Specification

**Date:** September 13, 2026
**Status:** Design Review Required
**Scope:** Move the remaining domain command emission from Python host callables into Lua so the host runs only raw shell steps + btrfs/state. Ports three verb categories (rebuild packages, services, boot/system verbs) to raw command steps; deletes the now-orphaned Python callables and their dispatch branches.
**Not a scope change to:** host language (Python + lupa stays), distribution model, generation/rollback mechanism, `kod shell` (separate requirement doc).

---

## 1. Purpose

Complete the Option A → B progression. After Option A, *planning* is Lua; the host still *executes* three domain verbs via Python callables (`manage_packages`, `enable/disable_services`, boot hooks) reached through `dispatch.step`. Option B removes that last domain coupling: every step becomes a raw shell command the generic runner already executes. The host's only remaining job is running raw steps + owning btrfs generations and state files, which makes an embeddable single-binary host trivial (no Python domain logic to ship beyond the runner).

## 2. Current state — what's already Fat-Lua

Two of the four domain categories are *already* emitted as raw command steps on every path; they need no work:

- **users** — `sections/users.lua:83` emits `useradd -m -s <shell> <name>` + config-file steps. No `kind="user"` verb exists anywhere in the codebase.
- **install packages** — `sections/packages.lua:25` emits `{ command = Repos.install_cmd(distro, list), chroot = true }`.

The remaining delta is exactly three verb categories, each a 1:1 flip from a `kind=X` verb step to a raw command step:

| Verb | Emitters today | Distro fork? |
|---|---|---|
| `package` (rebuild only) | `lib/rebuild.lua:72` (remove), `:88` (install) | yes — reuses existing `Repos.install_cmd` pattern |
| `service` | `sections/services.lua:28`, `desktop.lua:66,156`, `programs.lua:69`, `rebuild.lua:55,97` | no (`systemctl` uniform) |
| `system` (kernel-update / initramfs-update / boot-entry) | `sections/boot.lua:60,68,98`, `rebuild.lua:92,93,100` | yes (mkinitcpio/grub vs update-initramfs/grub) |

## 3. Step contract (unchanged)

Two step shapes already exist; Option B only changes which one each domain emits. No runner change.

- **Raw command step** — carries the shell command; `executor.lua` runs it under `timeout` + optional `chroot`. Two equivalent encodings, both normalized to `program` at the Python bridge (`planner.py:50`: `program = lua_step.program or lua_step.command`):
  - `{ name, description, command = "<full shell string>", chroot = bool }` — the `packages.lua` form; **this is what Option B builders emit** (simplest for multi-arg systemctl/pacman/grub commands).
  - `{ kind = "disk", program = "...", args = {...} }` — the disk-step form (`planner.py:329`).
- **Verb step** — `{ kind ∈ {package, service, system}, name, meta, on_error }`, no command → routed to `dispatch.step` (`executor.lua:57`). This is what Option B eliminates for these three kinds.

## 4. Command builders (new)

New `lib/domains/` modules. Each is a thin `(distro, inputs) → command string` function mirroring the existing `Repos.install_cmd(distro, …)` precedent. The builder is the *only* place that knows the CLI; sections just wrap its return value in a raw step. Builders receive the same inputs the current Python callable receives (e.g. `repos`, `kernel`) — passed through `ctx`/`meta` — so no capability is dropped; only the location of the CLI knowledge moves.

- `domains/services.lua` — distro-uniform: `enable(svc)` / `disable(svc)` → `systemctl enable|disable <svc>`.
- `domains/packages-{arch,debian}.lua` — extend the `Repos` install/remove pattern: pacman `-S`/`-R` vs apt-get install/remove. (Install already works via `packages.lua`; this adds rebuild's remove + install-as-command.)
- `domains/boot-{arch,debian}.lua` — the three ops per distro, taking the kernel version as a param (mkinitcpio/grub-mkconfig vs update-initramfs/grub).

Each existing emitter swaps its `{ kind=… }` table for `{ command = <builder>(distro, …) }`. The `meta.kernel` that rebuild/boot thread through becomes a builder argument.

## 5. Porting order

Each flip is the same three actions, and the suite must be green before starting the next:

1. **Flip emitters** — change the listed section/rebuild lines to emit raw command steps via the new builder.
2. **Regen goldens** — step-list goldens change from `{kind=…}` to `{command="…"}`; `KODOS_WRITE_GOLDEN=1 .venv/bin/python -m pytest tests/test_planner.py::TestGolden -q`.
3. **Delete Python** — remove the now-orphaned callable(s) and their `dispatch` branch in `executor.py`; stop passing the env callable from `kod.py`.

Order (lowest blast radius first):

1. **packages/rebuild** — reuses `Repos.install_cmd`, only `rebuild.lua` emits; deletes `manage_packages` + the `package` dispatch branch.
2. **services** — distro-uniform, proves the multi-emitter → shared-builder pattern (4 files); deletes `enable/disable_services` + the `service` branch.
3. **boot/system verbs** — hardest last: 3 ops × 2 distros with kernel-version threading; deletes the boot hooks + the `system` branch.

After all three, `dispatch_step` has no domain branches left (only the unknown-kind error at `executor.lua:73`), and `kod.py` stops passing those env callables.

## 6. Error handling

Unchanged. A raw command step failing → non-zero exit → `StepError`; per-step `on_error` warn/abort is already applied in `executor.lua:76-81`. No fallback added — the "no mid-execution degradation" invariant holds as-is.

## 7. Testing strategy

- **Builder unit tests** — one small test per new builder: inputs → expected command string (fast, no VM).
- **Golden step-lists** — regen after each flip; rebuild goldens go from `{kind=package,…}` to `{command="pacman -R …"}`, etc. Install goldens already show `command` steps for packages/users.
- **Suite green per verb** — full `.venv/bin/python -m pytest tests/ -q` green after each of the three flips (incremental, not one big bang).
- `test_hooks.py` unaffected (tests hook firing paths, not verbs).

## 8. Final deletions & success criteria

Deleted once orphaned:

- `system/packages.py`: `manage_packages` (+ its pacman/apt exec path).
- `system/services.py`: `enable_services` / `disable_services`.
- `system/boot.py`: the three hooks (`kernel-update`, `initramfs-update`, `boot-entry`).
- `executor.py`: the `package`, `service`, `system` dispatch branches.
- `kod.py`: the env callables passed for those verbs.

**Success ("embeddable host"):** zero domain-execution callables remain in Python — the host only runs raw command steps + manages btrfs generations and state files. A single static binary then ships no domain logic beyond the runner.

## 9. Out of scope / deferred

- `kod shell` redesign (separate requirement doc).
- Packaging/shipping the binary (host is "embeddable," not packaged, in this plan).
- State-gathering code that rebuild's Python state-gatherer still imports (e.g. reading installed packages for the diff) — stays in the host; exact line-level split worked out in the implementation plan.

## 10. References

- `docs/superpowers/plans/2026-09-13-kod-reorganization.md` — Option A/B definitions (Option B "Fat Lua").
- `docs/superpowers/plans/2026-09-13-option-a-foundation.md` — completed Tasks 1–4 (planner convergence).
- `src/kod/lib/executor.lua`, `src/kod/planner.py:50` — step contract & normalization.
