# KodOS: Integrating the Lua Declarative Ideas + Language Options

Date: 2026-09-10
Status: Analysis only — no implementation decided.
Inputs: `ideas-lua-declarative.md`, current codebase (~6.9k LOC Python), online research.

---

## 1. Current state (facts)

- KodOS is a **Python CLI** (`kod`, click-based, ~6,900 LOC in `src/kod/`).
- Lua is used **only as a configuration DSL**: `configuration.lua` and program
  modules are evaluated with `lupa.LuaRuntime()` (PUC Lua) in
  `src/kod/_core.py:139`, `src/kod/config/loader.py`,
  `src/kod/registry/loader.py:128`. The result is converted to a plain Python
  dict (`_lua_to_python`) and all orchestration happens in Python.
- There is **no plan/dry-run phase**: config → validate → execute directly.
- Phase 5 (custom/source packages) is designed but `build_templates.py` is an
  empty stub.
- Distribution model today: boot live ISO → `git clone` + `uv run kod`.

## 2. Integration map: ideas-lua-declarative.md → KodOS

| Idea from the doc | KodOS today | Gap / integration point |
|---|---|---|
| **Derivable** (type, name, inputs, params, outputs) | Program registry entries with `schema`, `scope`, `install()`, optional `service` field | Programs already *are* derivables minus explicit `inputs` (deps on other artifacts) and typed `outputs`. Add: named inputs/outputs so a program/service can declare "I need artifact X". |
| **Config = desired state** + merge/layering | `configuration.lua` returning a table; modules via `require()`/`imports` | Already declarative data. Formalize `mergeConfig()`-style deep merge for layering (base → site → user). Low effort, high value. |
| **BuildPlan / planner** (collect graph → topo sort → cache check → ordered steps) | `config/compiler.py` flattens + auto-enables deps; then execution begins | Missing: a real dependency graph between artifacts, and a **plan/execute split** (`kod plan` / dry-run). This is the single most useful idea to adopt — it gives you inspectable/diffable plans and cheap validation. |
| **Registry with lifecycle hooks** (pre/post build/install/start) | Program registry: builtin programs + plugin loader (`~/.kod/plugins/programs/`) | Hooks don't exist yet. Trivial to add as a callback list fired by the executor; plugins register them. |
| **Store** (content-addressed, hash → path, `.built` marker) | Btrfs **generations** (whole-system snapshots + rollback) | Different granularity, complementary. Do **not** replace generations with a Nix-style store. Instead: add a small content-addressed **build cache** for source builds (Phase 5), keyed by hash of (source URL + build command + params). Cache hit = skip rebuild. |
| **Core builders** (program/file/service/environment/package) | `system/packages.py`, `services.py`, `users.py`, `boot.py`; Phase 5 build templates | Map 1:1. The "package" builder is the new one: fetch source → build → install into prefix, per-distro adapter (see §3). |
| **Extensibility** (register new type / hooks / compose configs) | Plugin loader already exists for programs | New derivable *types* (not just programs) would extend the plugin format. Keep it optional until a real need appears. |

**Bottom line:** ~80% of the ideas doc is a more formal name for things KodOS
already has or has started (registry, plugins, modular config). The genuinely
new pieces are: **(a) plan/execute split with a dependency graph**,
**(b) lifecycle hooks**, **(c) content-addressed build cache for source builds**.

## 3. "Install from source" on an established distro

KodOS's premise (reuse the distro, don't build its own ecosystem) fits cleanly:

- **Arch**: pacman for repos; AUR via `yay`/`paru` already supported — AUR *is*
  source building (`makepkg`). The "source package" builder can be a thin
  wrapper: fetch tarball or PKGBUILD → build in a temp dir with the right
  template (autotools/cmake/meson/make/cargo, i.e. the Phase 5 stub) →
  install into a prefix → record outputs. Reuse `makepkg` where possible instead
  of reimplementing build logic.
- **Debian**: apt for repos; source builds via `dpkg-buildpackage` or the same
  meson/cmake templates + `checkinstall`/prefix install.
- Keep builders **distro-agnostic** (they emit commands); the existing
  `distributions/base.py | arch.py | debian.py` adapters provide
  fetch/build/install primitives. No new architecture needed.

## 4. Language options for glue/orchestration

The question: Lua for description + *what* orchestrates? Constraints that matter:
runs on a live ISO, needs root, shells out to pacman/btrfs/systemctl, must be
easy to bootstrap (today: `git clone` + `uv`).

### Option A — Keep Python + lupa (status quo)
- (+) Zero migration. 420+ tests exist. Fastest path to adopt ideas (a), (b), (c).
- (+) Lua stays exactly where it is: a DSL, not the engine.
- (−) No true single binary. `uv`/pip needed on the live ISO.
- **Verdict: do this now.**

### Option B — Rust thin host + embedded Lua (`mlua-rs/mlua`)
- mlua supports Lua 5.1–5.5 **and LuaJIT**, compiled in from source → one static
  binary, ~5–15 MB, instant start, no runtime deps on the target.
- The Rust side is a *thin host*: CLI parsing + an `exec(cmd, args) -> (code,
  stdout, stderr)` bridge + file helpers (~a few hundred LOC). Everything else —
  planner, registry, builders, store/cache — is Lua, i.e. **the ideas-doc code
  runs almost verbatim inside the binary**.
- The port from Python is mostly mechanical: current orchestration is "shell out
  and parse", which is exactly what an exec bridge gives Lua. Risk is re-testing
  the install path on a VM (btrfs/partitioning edge cases), not language risk.
- (−) One-time rewrite cost; you maintain two ecosystems (Rust + Lua).
- **Verdict: best long-term if single binary becomes a hard requirement.**

### Option C — Go + gopher-lua
- Single static binary, pure-Go Lua (no C toolchain needed to build).
- (−) gopher-lua is a partial Lua 5.x implementation, slower (interpreted in
  Go), low maintenance cadence; subtle semantics differences are exactly the
  kind of thing that bites a config DSL later.
- **Verdict: dominated by Option B.** Same goal, worse VM.

### Option D — "All in Lua" (no host language)
- Not actually possible as stated: Lua still needs an interpreter to run, so you
  end up writing a small C/Rust/Go host anyway (that *is* Option B). Pure
  `luajit -b` bundles bytecode but not the runtime; FFI-based subprocess
  management in raw Lua is painful and less safe than a bridge.
- **Verdict: reject as a separate path — it collapses into Option B.**

### Option E — Python, packaged as one file (PyInstaller/Nuitka)
- No rewrite; ship a single executable that the live ISO can run directly.
- (−) 30–100 MB, slow cold start, fragile with hidden imports and root-level
  filesystem operations; "single binary" in name only.
- **Verdict: acceptable stopgap** if the *only* goal is one-file distribution
  from the live ISO. Cheaper than B, worse artifact.

### Option F — Nim (compiles to C, first-class FFI)
- Single static binary: yes — Nim compiles to C and statically links
  PUC-Lua/LuaJIT; no runtime on the target, instant start. Same end state as
  Option B.
- Lua embedding: possible via `cimport`/FFI against `lua.h`. No maintained
  high-level binding comparable to mlua — `jangko/nimLUA` (glue-code generator)
  is the main package and it's niche. You would own a hand-written binding layer.
- Known sharp edge: Lua's C API does error handling via `longjmp`, which cannot
  safely cross Nim stack frames on the C backend — every fallible call needs
  wrapper discipline (exactly what nimLUA automates). This is manageable but is
  real maintenance surface.
- Maturity: language itself is mature (2.x), stdlib adequate; community and
  package ecosystem far smaller than Rust/Go, "write your own stdlib" culture.
- **Verdict: technically a credible alternative to Option B** — same artifact,
  but you write and maintain the Lua bindings yourself. Choose it only if you
  prefer Nim over Rust and accept owning that binding layer.

### Option G — V (vlang) + `abuss.vlua`
- Single binary: yes, by default (self-contained except libc; fully static via
  `-cc musl-gcc`). Very fast compiles.
- Lua embedding: **already solved** — `abuss.vlua` (github.com/abuss/vlua)
  embeds PUC-Lua 5.4 via C FFI with exactly the thin-host surface this design
  needs: `dofile`/`dostring`, nested-table read (`LuaValue` tree with lossless
  integers), V-function registration for an exec bridge, `call_function`,
  registry refs, `load_string`. CI-tested on Ubuntu/macOS, V pinned to 0.5.2.
- Distribution detail to close: vlua currently links `liblua5.4` dynamically,
  so the target would need that package. For a dependency-free live-ISO binary,
  compile PUC-Lua's ~5 `.c` files into `liblua.a` and link it statically —
  same FFI declarations, different link input; PUC-Lua static builds are
  trivial (LuaJIT is the fiddly one, not needed here).
- Maturity: V is still **0.5 beta** with acknowledged pre-1.0 breaking changes.
  That risk is real but it's *your* bet now — the embedding layer you'd have to
  write for any Option-B-style design already exists and has tests.
- Security parity note: `safe_dostring` runs full Lua stdlib (`os.execute`,
  `io`, `package.loadlib`) — same trust level as today's Python+lupa setup,
  which also evaluates user-authored config with full power. No regression,
  but keep configs developer-trusted only.
- **Verdict: viable single-binary path, now much cheaper than previously
  estimated.** Remaining risk is V pre-1.0 churn + re-testing the install path
  on a VM — not binding work.

### Evaluation matrix

| | A: Python+lupa | B: Rust+mlua | C: Go+gopher-lua | D: all-Lua | E: PyInstaller/Nuitka | F: Nim | G: V |
|---|---|---|---|---|---|---|---|
| Migration cost | none | high (one-time) | medium-high | = B | low | high (one-time) | high (one-time) |
| True single binary | no | **yes** | yes | n/a (is B) | no (fat file) | yes | yes |
| Startup on live ISO | needs uv | instant | instant | — | slow-ish | instant | instant |
| Reuse of ideas-doc code | in Python ports | **near-verbatim Lua** | near-verbatim | verbatim | in Python ports | near-verbatim | near-verbatim |
| Lua binding layer | lupa (maintained) | mlua (maintained) | gopher-lua (niche) | — | lupa | **hand-written** | vlua (author-maintained, CI-tested) |
| Language maturity | high | high | high | n/a | high | high | **beta (pre-1.0)** |
| Target runtime deps | uv + Python | none | none | — | none | none | none (if Lua linked statically) |
| Risk to working install path | none | re-test on VM | VM + VM-semantics | = B | low | re-test on VM + binding bugs | re-test on VM + beta churn |

## 5. Recommendation (simple, phased)

1. **Now, in Python:** adopt the three genuinely-new ideas — plan/execute split
   (`kod plan` / dry-run output), lifecycle hooks in the registry, and a small
   content-addressed build cache for Phase 5 source builds. Keep Lua as the
   config DSL; keep btrfs generations as the rollback mechanism (do **not**
   build a Nix-style store).
2. **Write new logic in portable Lua-first style from day one** even while it
   runs under lupa: pure data + table functions, no Python-specific behavior
   inside `configuration.lua`/program modules. This makes a future Option B port
   "move the files", not "rewrite the logic".
3. **Only if single binary becomes a hard requirement:** the realistic field is
   now B vs G. Both yield a dependency-free static binary with the orchestration
   in Lua. Tie-breakers: B has a more mature host language and a broadly
   maintained binding (mlua); G reuses `abuss.vlua`, which already implements
   the thin-host bridge this design needs (and is yours to evolve). Choose by
   which language you'll still enjoy maintaining in 3 years — the embedding
   work is no longer the differentiator. Nim (Option F) remains a fallback if
   you'd rather own a fresh binding layer than bet on V pre-1.0.
4. **Skip:** Go/gopher-lua, all-Lua-without-host, full Nix store, and for now
   PyInstaller (revisit only if live-ISO bootstrap friction becomes a real complaint).

## 6. Open questions

1. Is single-binary distribution a **hard requirement** or convenience?
   (Today's flow — `git clone` + `uv run kod` on the live ISO — works; if it
   never bothers you, Option A is the whole answer.)
2. Should `kod plan` (dry-run showing ordered steps + what would change) be a
   first-class command? Recommended: yes, smallest high-value adoption of the ideas doc.
3. Source-build scope for Phase 5: wrap `makepkg`/AUR only, or also generic
   tarball + meson/cmake/autotools templates?
