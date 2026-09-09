# Architecture Redesign - Review Findings

**Date:** 2026-09-09
**Status:** In Review
**Overall Assessment:** Strong foundation with several clarifications needed

---

## 1. ✅ Spec Completeness

### Strengths
- [x] All 5 phases clearly defined with goals
- [x] Success criteria are measurable (checkboxes)
- [x] Risk analysis comprehensive (with mitigations)
- [x] Backward compatibility path explicitly addressed
- [x] Integration points documented (Phase 5 → existing repos)
- [x] Example configs show new feature usage

### Minor Issues

#### 1.1 Ambiguity: User Management Split
**Issue:** Spec lists both `kod/core/user_config.py` AND `kod/system/users.py`

**Current state:**
- `kod/core/user_config.py` in scaffold
- Spec mentions both modules

**Clarification needed:**
- `kod/core/user_config.py` — User configuration generation (proc_user_programs → config generators)
- `kod/system/users.py` — User account creation/management (create_user, create_kod_user)

**Recommendation:** Split is correct; update spec to clarify the distinction.

#### 1.2 Missing: Filesystem Module
**Issue:** No mention of filesystem operations (partitioning, mounting, fstab)

**Current state:**
- `src/kod/filesystem.py` exists with 13KB of code
- Not included in refactoring plan

**Recommendation:** Add `kod/system/filesystem.py` in Phase 2 spec

#### 1.3 Missing: CLI Module Design
**Issue:** Spec mentions CLI commands but no CLI architecture sketched

**Current state:**
- Current CLI: `src/kod/kod.py` (15KB, monolithic)
- Phase 4 says "add CLI help" but doesn't specify structure

**Recommendation:** 
- Sketch CLI architecture in Phase 1 or 4
- Should subcommands go in each module or central dispatcher?
- Consider using Click or Argparse wrapper

#### 1.4 Missing: Chroot/Execution Utils
**Issue:** Phase 2 refactoring doesn't mention consolidating exec helpers

**Current state:**
- `common.py` has exec(), exec_chroot(), exec_critical(), exec_warn()
- These are cross-cutting concerns used by all modules
- Not explicitly mentioned in refactoring

**Recommendation:** Document that Phase 2 should keep `common.py` as-is or extend it

---

## 2. ✅ Scaffold Alignment

### Strengths
- [x] Module structure matches spec layout
- [x] All Phase 1-5 modules present
- [x] Tests organized by phase with pytest markers
- [x] Documentation clear and comprehensive
- [x] Each module has docstring + TODO

### Issues

#### 2.1 Missing Modules in Scaffold
**Phase 2 spec lists 7 modules, scaffold has 7 but with splits:**

| Spec | Scaffold | Status |
|------|----------|--------|
| `kod/core/install.py` | ✅ Present | ✓ |
| `kod/core/rebuild.py` | ✅ Present | ✓ |
| `kod/core/user_config.py` | ✅ Present | ✓ |
| `kod/system/packages.py` | ✅ Present | ✓ |
| `kod/system/services.py` | ✅ Present | ✓ |
| `kod/system/users.py` | ❌ Missing | NEED TO ADD |
| `kod/system/boot.py` | ✅ Present | ✓ |
| (implicit) `kod/system/filesystem.py` | ❌ Missing | NEED TO ADD |

**Action:** Create `kod/system/users.py` and `kod/system/filesystem.py` skeletons

#### 2.2 Missing: Base Distribution Class
**Issue:** Spec mentions "Implement Distribution base class" but no skeleton

**Current state:**
- `arch.py`, `debian.py` exist with duplicate code
- No shared interface

**Recommendation:** Create `kod/distributions/base.py` or `kod/system/distributions.py`

#### 2.3 Missing: Exception Hierarchy
**Issue:** Spec defines exception classes (Part 6) but no module for them

**Current state:**
- Some exceptions in `common.py`
- New ones need to be defined for: config, validation, packages, etc.

**Recommendation:** Create `kod/exceptions.py` or `kod/common/exceptions.py`

---

## 3. ✅ Architecture Coherence

### Phase Boundaries - Clean?

#### Phase 1 → Phase 2
**Transition:** Config system produces validated plan → install workflows consume it
- [x] Clear input/output contract
- [x] Phase 1 doesn't depend on Phase 2
- [x] Can implement independently
- **Status:** ✅ CLEAN

#### Phase 2 → Phase 3
**Transition:** Program registry plugs into package/service configuration
- [x] Phase 2 doesn't require Phase 3 (backward compat)
- [x] Phase 3 adds capability, doesn't break Phase 2
- **Status:** ✅ CLEAN

#### Phase 3 → Phase 4
**Transition:** Polish and documentation
- [x] Doesn't change architecture
- ⚠️ Might require backporting (tests, docs) — documented as intentional
- **Status:** ✅ CLEAN

#### Phase 4 → Phase 5
**Transition:** Custom packages layer on top
- [x] Phase 5 uses existing package manager
- [x] Custom packages are opt-in (backward compat)
- **Status:** ✅ CLEAN

### Circular Dependencies?
- [x] Checked modules — no circular imports apparent
- [x] Phase dependencies are DAG (no cycles)
- **Status:** ✅ NO CYCLES

### Integration Points - Clear?

#### Config → Install
Spec: "Config compilation resolves custom packages → adds to dependency graph"
- ✅ Clear
- ✅ Documented in Phase 5
- ✅ Example config shows flow

#### Package repos → Custom packages
Spec: "Package manager groups: `custom:name` works like `aur:name`"
- ✅ Clear
- ✅ Design documented
- ⚠️ Implementation details missing (how does PackageManager route?)

**Recommendation:** Add to Phase 2 spec: "PackageManager.install_packages() routes to distro.install_to_repo(pkg_spec)"

#### Plugins → Registry
Spec: "Users drop .lua files; auto-discovered and loaded"
- ✅ Clear concept
- ⚠️ No error handling strategy for bad plugins
- ⚠️ No version compatibility checking

**Recommendation:** Document plugin validation strategy in Phase 3

---

## 4. 🔴 Missing Pieces (Needs Attention)

### Critical

#### 4.1 Exception Hierarchy
**Status:** RED - Not defined
**Impact:** Phase 2 can't implement error handling without this
**Action:** Create before Phase 2 starts

```python
# kod/exceptions.py (needed)
class KodosError(Exception):
    pass

class ConfigError(KodosError):
    pass

class ValidationError(ConfigError):
    pass

class PackageError(KodosError):
    pass

class SystemError(KodosError):
    pass
```

#### 4.2 Distribution Base Class
**Status:** RED - Not defined
**Impact:** Phase 2 can't refactor distro code without interface
**Action:** Create before Phase 2 starts

#### 4.3 CLI Architecture
**Status:** YELLOW - Not specified
**Impact:** Phase 4 will struggle without upfront design
**Action:** Sketch in Phase 1 spec or create separate CLI design doc

### Important

#### 4.4 Plugin Validation Strategy
**Status:** YELLOW - Not defined
**Impact:** Phase 3 plugin loader could be fragile
**Action:** Document before Phase 3 (what if plugin.lua is invalid?)

#### 4.5 Custom Package Build Sandbox
**Status:** YELLOW - Mentioned but not detailed
**Impact:** Phase 5 security concern
**Action:** Document sandbox strategy (bubblewrap, nix, containers?)

### Nice-to-Have

#### 4.6 CLI Command Definitions
**Status:** GREEN - Sketched in Phase 5
**Impact:** Low (can design during Phase 4)
**Action:** Create CLI schema document during Phase 4

#### 4.7 Lua Library Updates
**Status:** GREEN - Existing libs work
**Impact:** Low (current libs sufficient for Phase 1-5)
**Action:** Plan for Phase 4 or later

---

## 5. ✅ Implementation Concerns - Phase Viability

### Phase 1 → Phase 2 Transition
**Question:** Can Phase 2 start before Phase 1 completes?
- **Answer:** Partially
  - Phase 2 modules can be implemented in parallel with Phase 1
  - But integration testing requires Phase 1 complete
  - **Recommendation:** Do Phase 1 → 2 → 3 sequentially; don't parallelize yet

**Question:** What if Phase 1 schema changes during Phase 2?
- **Answer:** Risk mitigated by:
  - Phase 1 complete before Phase 2 integration
  - Clear contract between phases (schema → plan → execution)
  - **Recommendation:** Freeze schema before Phase 2 production code

### Phase 2 Complexity
**Issue:** Phase 2 is largest (5 weeks, 3-4 developers)
- Refactoring existing code (risky)
- Backward compat required
- Error handling overhaul
- Distro abstraction (two implementations: arch, debian)

**Recommendation:**
- Break Phase 2 into sub-phases
- Option A: Implement new modules first, then refactor old code
- Option B: Do arch first, then debian, then integration
- Consider 2 developers on Phase 2

### Phase 4 Can Be Bottleneck
**Issue:** Phase 4 is "Polish" but spec doesn't detail scope
- "Remove dead code" — what's dead? How much?
- "Simplify error messages" — where? How many?
- "Full test suite" — how much coverage needed?

**Recommendation:**
- Define Phase 4 acceptance criteria upfront (code coverage %, lint score, etc.)
- May need more than 1 week if refactoring is large

### Phase 5 Sandbox Strategy
**Issue:** Custom package building with untrusted scripts is risky
- Spec mentions "Sandbox with bubblewrap" but no details
- No threat model defined
- No user workflow for approval

**Recommendation:**
- Add security review step before Phase 5 implementation
- Document threat model and controls
- Consider MVP without sandboxing (user approval only)

---

## 6. 📋 Issues Found

### Critical (Must Fix Before Implementation)

1. **Missing `kod/system/users.py` in scaffold**
   - Spec lists it; scaffold doesn't have it
   - Impact: Phase 2 will be incomplete
   - Fix: Create skeleton

2. **Missing `kod/system/filesystem.py` in scaffold**
   - Spec doesn't list it (gap); should be in scaffold
   - Impact: Filesystem logic scattered
   - Fix: Create skeleton and add to Phase 2 spec

3. **Exception hierarchy not defined**
   - Spec describes it; no module created
   - Impact: Phase 2 error handling can't start
   - Fix: Create `kod/exceptions.py` with class definitions

4. **Distribution base class not defined**
   - Spec mentions it; no skeleton
   - Impact: Phase 2 refactoring can't start
   - Fix: Create `kod/distributions/base.py` skeleton

### Important (Should Fix Before Phase 1 Ends)

5. **CLI architecture not sketched**
   - Spec lists commands; doesn't define structure
   - Impact: Phase 4 will have to figure it out
   - Fix: Create `docs/cli-architecture.md` during Phase 1

6. **Plugin validation strategy missing**
   - Spec doesn't define what happens if plugin is invalid
   - Impact: Phase 3 error handling will be ad-hoc
   - Fix: Document in Phase 1/3 spec

7. **Custom package sandbox not detailed**
   - Spec mentions bubblewrap; no threat model
   - Impact: Phase 5 security implementation will be guessed
   - Fix: Create `docs/phase5-security.md` before Phase 5

### Minor (Document or Defer)

8. **Spec lists both `kod/core/user_config.py` AND `kod/system/users.py`**
   - Confusing; need to clarify split
   - Fix: Update spec with clear distinction

---

## 7. ✅ Backward Compatibility Review

### Existing Code Impact
- [x] Old `core.py` stays during Phases 1-3
- [x] New code is additive (no deletions)
- [x] Deprecation path for old functions documented in MIGRATION.md
- [x] Old Lua config format still works

### Potential Breaking Changes
- ❓ Exception hierarchy change (problems list → exceptions)
  - **Impact:** Low (internal only)
  - **Mitigation:** Deprecation warnings on old code
  - **Status:** OK

- ❓ Distribution interface change
  - **Impact:** Medium (if external code calls arch.py)
  - **Mitigation:** Keep old functions as wrappers
  - **Status:** Documented in MIGRATION.md

---

## 8. 🎯 Recommendations

### Before Implementation Starts (Week 0)

1. **Create missing skeletons:**
   - [ ] `kod/system/users.py` (user account management)
   - [ ] `kod/system/filesystem.py` (partitioning, mounting, fstab)
   - [ ] `kod/exceptions.py` (exception hierarchy)
   - [ ] `kod/distributions/base.py` (Distribution base class)

2. **Create design documents:**
   - [ ] `docs/cli-architecture.md` (command structure, routing)
   - [ ] `docs/phase3-plugins.md` (plugin validation, error handling)
   - [ ] `docs/phase5-security.md` (sandbox strategy, threat model)

3. **Update spec:**
   - [ ] Clarify `kod/core/user_config.py` vs `kod/system/users.py` distinction
   - [ ] Add `kod/system/filesystem.py` to Phase 2 list
   - [ ] Document CLI architecture decision in Phase 1 or 4

4. **Update scaffold:**
   - [ ] Add skeleton files for missing modules (users.py, filesystem.py, exceptions.py, distributions/base.py)

### Before Phase 1 Completes (Week 2)

5. **Phase 1 outputs should include:**
   - [ ] Schema design document (what options exist, how are they validated?)
   - [ ] Config example showing all new features
   - [ ] CLI examples (kod config --schema, kod config validate, kod config compile)

### Before Phase 2 Starts (Week 3)

6. **Finalize Phase 2 spec:**
   - [ ] Decide on distro abstraction (interface + 2 implementations)
   - [ ] Define PackageManager public API
   - [ ] Decide: parallelize Phase 2 or keep sequential?

---

## 9. 🎓 Overall Assessment

| Category | Grade | Notes |
|----------|-------|-------|
| **Spec Quality** | A- | Clear and comprehensive; minor ambiguities |
| **Scaffold Quality** | B+ | Good foundation; missing 4 critical modules |
| **Phase Design** | A | Clean boundaries, no circular dependencies |
| **Risk Mitigation** | B | Covers most risks; security (Phase 5) under-specified |
| **Backward Compat** | A | Migration path is explicit and viable |
| **Implementation Readiness** | B | Can start Phase 1; Phase 2 needs prep work |

### Verdict
**READY TO IMPLEMENT with pre-work**

The architecture is sound and phases are well-designed. Implementation can begin immediately on Phase 1, but 4 critical modules and 3 design documents should be completed before Phase 2 starts.

**Estimated timeline to be implementation-ready:**
- Now: Start Phase 1
- Week 1 (parallel): Create missing modules and design docs
- Week 2: Finish Phase 1, finalize Phase 2 spec
- Week 3: Begin Phase 2 with confidence

---

## 10. 📝 Next Actions

**High Priority:**
1. Create missing module skeletons
2. Write missing design documents
3. Get spec/scaffold review approval
4. Commit updated scaffold to git

**Medium Priority:**
5. Create Phase 1 detailed implementation plan
6. Identify Phase 2 developer resources (estimated 2 devs)
7. Set up CI/CD for testing

**Low Priority:**
8. Plan Phase 3-5 user communication (docs, examples)
9. Consider demo/screenshot plan for Phase 4

