# Phase 3: Program Registry - Implementation Plan

**Date:** 2026-09-09  
**Duration:** ~8-10 hours (estimated)  
**Success Criteria:** All 59+ tests passing, 3 builtin programs working, user plugins discoverable, CLI commands functional

---

## Overview

Implement the Program Registry system as designed in `2026-09-09-phase3-program-registry.md`. This phase introduces Lua-based, user-extensible program definitions with schema validation and inheritance support.

**Key Deliverables:**
1. `kod/registry/programs.py` — Program class and registry
2. `kod/registry/loader.py` — PluginLoader with discovery, loading, merging
3. `kod/registry/builtin/` — Three builtin programs (git, neovim, syncthing)
4. CLI commands: `kod registry list|info|schema|generate`
5. Config system integration: recognize `programs` section
6. Full test coverage (20-25 new tests)

---

## Implementation Tasks

### Task 1: Core Program Class & Registry (2 hours)

**What:**
- Implement `Program` class: wraps Lua definitions, provides Python interface
- Implement `ProgramRegistry` class: manages loaded programs, caching
- Implement error types: `ProgramError`, `ProgramNotFound`, `ProgramLoadError`, etc.

**Where:** `kod/registry/programs.py`

**Detailed Steps:**

1. Define error hierarchy:
   ```python
   class ProgramError(Exception): ...
   class ProgramNotFound(ProgramError): ...
   class ProgramLoadError(ProgramError): ...
   class CircularExtendError(ProgramLoadError): ...
   class ConfigValidationError(ProgramError): ...
   class SchemaError(ProgramError): ...
   ```

2. Implement `Program` class:
   - `__init__(name, lua_def, parent=None)`: Store definition, parent reference
   - `get_schema()`: Return merged schema (builtin + user extensions)
   - `validate_config(options)`: Validate against merged schema (use existing validator)
   - `generate_config(options)`: Call Lua generate_config method
   - `run_hook(hook_name, *args)`: Execute lifecycle hooks (validate, post_install, etc.)
   - `_merge_schema(parent_schema, child_schema)`: Compose schemas with JSON schema `allOf`
   - `_call_parent_method(method_name, *args)`: Support inheritance in Lua

3. Implement `ProgramRegistry` class:
   - `__init__()`: Initialize caches (builtin, user, merged)
   - `_load_lua_def(file_path)`: Parse and load Lua file using lupa
   - `get_program(name)`: Load program by name (return cached or load+merge)
   - `list_programs()`: Return all available program names
   - `get_program_info(name)`: Return metadata dict

4. Tests:
   - Load simple program definition (no inheritance)
   - Detect missing required fields (name, schema, generate_config)
   - Validate schema format (JSON schema spec)
   - Error on circular inheritance
   - Cache works correctly

**Acceptance Criteria:**
- Program class loads and wraps Lua definitions correctly
- Schema validation works (uses existing kod.config validator)
- No circular inheritance allowed
- All error types raised appropriately

---

### Task 2: PluginLoader with Discovery & Merging (2.5 hours)

**What:**
- Implement `PluginLoader` class: discovers builtin programs, loads user plugins, merges them
- Implement schema composition and inheritance resolution
- Handle all edge cases (missing parent, conflicting fields, etc.)

**Where:** `kod/registry/loader.py`

**Detailed Steps:**

1. Implement `PluginLoader` class:
   - `__init__(config_home=None)`: Setup paths for builtin_dir, plugin_dir
     - builtin_dir: `kod/registry/builtin/`
     - plugin_dir: `~/.kod/plugins/programs/`
   - `discover_builtin()`: Find all .lua files in builtin_dir → {name: path}
   - `discover_user_plugins()`: Find all .lua files in plugin_dir → {name: path}
   - `load_program(name)`: Core method that loads, merges, returns Program
   - `list_programs()`: Return sorted list of all names
   - `get_program_info(name)`: Return {name, source, schema, default_config, extends}

2. Implement discovery:
   - Use `pathlib.Path.glob("*.lua")` to find files
   - Extract program name from filename (git.lua → "git")
   - Handle case sensitivity (warn if both git.lua and Git.lua exist)

3. Implement loading:
   - Use lupa to execute Lua file
   - Catch Lua syntax errors → raise `ProgramLoadError` with clear message
   - Validate returned dict has required fields: name, schema, default_config, generate_config
   - Return dict as-is (let Program class wrap it)

4. Implement merging (core complexity):
   - If user plugin has `_extends` field, find parent builtin
   - Detect circular extends: track visited programs, raise `CircularExtendError`
   - Merge schemas:
     - If no parent: use user schema as-is
     - If parent exists: create `{"allOf": [parent_schema, user_schema]}`
     - Validate no conflicting required fields (warn if same field name, different types)
   - Merge default_config:
     - Start with parent defaults
     - Override with user defaults
   - Merge methods:
     - Store parent reference in Program object
     - User can call `self:_parent_method()` in Lua
   - Return merged Program with parent chain

5. Tests:
   - Discover builtin programs (git, neovim, syncthing)
   - Discover user plugins from temp directory
   - Load program with no parent
   - Load program extending parent (schema merge, method calls)
   - Detect circular extends
   - Error on missing parent program
   - Error on malformed Lua files
   - Cache works (same name loaded once)

**Acceptance Criteria:**
- All builtin programs discoverable
- User plugins discoverable in ~/.kod/plugins/programs/
- Inheritance chain works (up to 3 levels)
- Schema merging produces valid JSON schema
- Circular extends detected and reported
- Clear error messages for all failure cases

---

### Task 3: Three Builtin Programs (1.5 hours)

**What:**
- Implement git.lua, neovim.lua, syncthing.lua builtin programs
- Each has schema, default_config, generate_config, optional hooks

**Where:** `kod/registry/builtin/git.lua`, `neovim.lua`, `syncthing.lua`

**Detailed Steps:**

1. Create `kod/registry/builtin/` directory

2. Implement `git.lua`:
   - Schema: user_name (required), email (required, email format), signing_key (optional)
   - Default: "Default User", "user@localhost", nil
   - generate_config: Return git config commands
   - Test with sample options

3. Implement `neovim.lua`:
   - Schema: python_provider, ruby_provider, node_provider (all boolean)
   - Default: python=false, ruby=false, node=true
   - generate_config: Build package list based on options
   - Test with different provider combinations

4. Implement `syncthing.lua`:
   - Schema: auto_start (boolean), listen_address (string)
   - Default: auto_start=true, listen_address="127.0.0.1:8384"
   - generate_config: Return systemctl commands
   - Test with and without auto_start

5. Tests:
   - Load each builtin program
   - Validate schema structure
   - Generate config with sample options
   - Test generate_config output format (shell commands)

**Acceptance Criteria:**
- All 3 builtin programs load without errors
- Schema matches specification
- generate_config produces valid shell commands
- All tests pass

---

### Task 4: Config System Integration (1.5 hours)

**What:**
- Update config validator to recognize and validate `programs` section
- Add `programs_schema.json` to config schemas
- Update config compiler to handle programs
- Ensure backward compatibility (existing configs still work)

**Where:** `kod/config/schemas/programs_schema.json`, `kod/config/validator.py`, `kod/config/compiler.py`

**Detailed Steps:**

1. Create `kod/config/schemas/programs_schema.json`:
   - Define schema for `programs` section in config
   - Each program name maps to config dict
   - Example:
     ```json
     {
       "type": "object",
       "properties": {
         "programs": {
           "type": "object",
           "additionalProperties": {
             "type": "object"
           }
         }
       }
     }
     ```

2. Update `kod/config/validator.py`:
   - Add `programs` to main schema (optional field)
   - During validation, if `programs` present:
     - Load each program via PluginLoader
     - Validate program options against program's schema
     - Report all validation errors together

3. Update `kod/config/compiler.py`:
   - If `programs` in config, compile to intermediate format
   - Store loaded Program objects in compiled config
   - Make available to install workflow

4. Tests:
   - Config with no `programs` section → validates fine
   - Config with valid programs → validates fine
   - Config with invalid program options → validation error with clear message
   - Config with unknown program name → error
   - Backward compatibility: existing configs still work

**Acceptance Criteria:**
- Programs section optional (no breaking changes)
- Invalid program options caught with clear error message
- All existing config tests still pass
- Program validation integrates cleanly with config validator

---

### Task 5: CLI Commands Implementation (1.5 hours)

**What:**
- Implement CLI commands: `kod registry list`, `info`, `schema`, `generate`
- Add to existing CLI structure (use Click framework)
- Provide clear, formatted output

**Where:** `kod/cli/registry.py` (new), `kod/cli/__init__.py` (update)

**Detailed Steps:**

1. Create `kod/cli/registry.py`:
   - Define Click command group `@click.group("registry")`

2. Implement `kod registry list`:
   - Load all programs via PluginLoader
   - Group by source (builtin, user)
   - Show inheritance notation: "git (extends builtin)"
   - Output:
     ```
     Builtin Programs:
       - git
       - neovim
       - syncthing
     
     User Programs:
       - git (extends builtin)
     ```

3. Implement `kod registry info <name>`:
   - Load program, show:
     - Name
     - Source (builtin / user / merged)
     - Schema (formatted, with descriptions)
     - Default config
     - Parent program (if inherited)
   - Example output:
     ```
     Program: git
     Source: merged (builtin + user)
     
     Schema:
       user_name (string, required)
         Git committer name
       email (string, required, format=email)
         Git committer email
       signing_key (string, optional)
         GPG key ID for signing commits
       sign_commits (boolean, optional) [user extension]
         Automatically sign all commits
     
     Default Config:
       user_name: Default User
       email: user@localhost
       signing_key: (none)
       sign_commits: false
     ```

4. Implement `kod registry schema <name>`:
   - Load program schema
   - Output as formatted JSON
   - Shows merged schema (parent + user)

5. Implement `kod registry generate <name> [OPTIONS]`:
   - Load program
   - Parse command-line options (--user-name "Alice" --email "alice@example.com")
   - Validate options against schema
   - Call generate_config()
   - Output generated shell commands
   - Example:
     ```
     $ kod registry generate git --user-name "Alice" --email "alice@example.com"
     git config --global user.name 'Alice'
     git config --global user.email 'alice@example.com'
     ```

6. Update `kod/cli/__init__.py`:
   - Import registry commands
   - Add to main CLI group

7. Tests:
   - `kod registry list` shows all programs
   - `kod registry info git` shows complete info
   - `kod registry schema git` outputs valid JSON schema
   - `kod registry generate git --user-name "Alice" --email "alice@example.com"` works
   - Error handling: unknown program, invalid options

**Acceptance Criteria:**
- All 4 commands work correctly
- Output is clear and formatted well
- Error messages are helpful
- All CLI tests pass

---

### Task 6: Full Test Suite (1.5 hours)

**What:**
- Write comprehensive tests for all new functionality
- Cover happy path, edge cases, error cases
- Ensure 100% coverage of new code

**Where:** `tests/test_registry.py` (new)

**Detailed Steps:**

1. Create `tests/test_registry.py`:
   - Test imports and basic setup

2. Test `Program` class:
   - test_load_simple_program
   - test_program_with_parent
   - test_schema_merging
   - test_generate_config
   - test_validate_config_valid
   - test_validate_config_invalid
   - test_circular_inheritance_error
   - test_missing_required_field_error

3. Test `PluginLoader` class:
   - test_discover_builtin_programs
   - test_discover_user_plugins
   - test_load_builtin_program
   - test_load_user_plugin
   - test_load_merged_program
   - test_list_programs
   - test_get_program_info
   - test_cache_works
   - test_load_error_syntax_error
   - test_load_error_missing_parent
   - test_circular_extends_error

4. Test builtin programs:
   - test_git_program_loads
   - test_git_generate_config
   - test_neovim_program_loads
   - test_neovim_generate_config
   - test_syncthing_program_loads
   - test_syncthing_generate_config

5. Test config integration:
   - test_config_with_programs_section
   - test_config_program_validation_valid
   - test_config_program_validation_invalid
   - test_config_unknown_program_error

6. Test CLI commands:
   - test_registry_list_command
   - test_registry_info_command
   - test_registry_schema_command
   - test_registry_generate_command
   - test_registry_error_handling

7. Integration test:
   - test_full_workflow: load config with programs → validate → generate configs → verify

**Acceptance Criteria:**
- 25+ new tests, all passing
- Coverage: 90%+ of new code
- Edge cases covered (empty schema, no defaults, etc.)
- Error cases tested

---

### Task 7: Documentation & Examples (1 hour)

**What:**
- Update README with Phase 3 examples
- Create "Extending Kodos" guide
- Add examples of custom programs
- Update SCAFFOLD.md progress

**Where:** `README.md`, `docs/extending.md`, `SCAFFOLD.md`

**Detailed Steps:**

1. Create `docs/extending.md`:
   - "How to write custom programs"
   - Example: custom git program extending builtin
   - Example: custom tool program (new)
   - Explain schema, generate_config, hooks
   - Link to spec for details

2. Update `README.md`:
   - Add "Program Registry" section
   - Show example of using programs in config
   - Show CLI commands
   - Link to extending guide

3. Update `SCAFFOLD.md`:
   - Mark Phase 3 complete
   - Update counts (tests, lines, modules)
   - Add Phase 4 (Polish) estimate

4. Create example custom program:
   - `docs/examples/custom_program.lua`
   - Full commented example with all fields

**Acceptance Criteria:**
- Documentation is clear and complete
- Examples are runnable
- Links are correct
- Progress tracking updated

---

## Task Dependencies

```
Task 1 (Program class)
  ↓
Task 2 (PluginLoader) ← depends on Task 1
  ↓
Task 3 (Builtin programs) ← depends on Task 2
  ├→ Task 4 (Config integration) ← depends on Task 2
  ├→ Task 5 (CLI commands) ← depends on Task 2 & 3
  └→ Task 6 (Tests) ← depends on all above
      ↓
Task 7 (Documentation) ← depends on all above
```

**Parallelizable:** Tasks 4, 5, 6 can start once Task 2 is done.

---

## Verification Steps

After all tasks complete:

1. **Run tests:**
   ```bash
   pytest tests/test_registry.py -v
   pytest tests/ -v  # All tests including Phase 1, 2
   ```
   Expected: 59+ old tests pass, 25+ new tests pass, 10 skipped, 1 pre-existing failure

2. **Try CLI commands:**
   ```bash
   kod registry list
   kod registry info git
   kod registry schema git
   kod registry generate git --user-name "Alice" --email "alice@example.com"
   ```

3. **Load config with programs:**
   ```bash
   # Create test config with programs section
   # Validate it
   # Verify programs loaded correctly
   ```

4. **User plugin test:**
   - Create `~/.kod/plugins/programs/git.lua` extending builtin
   - Verify loader finds it
   - Verify inheritance works
   - Verify merged schema correct

---

## Estimated Timeline

| Task | Hours | Notes |
|------|-------|-------|
| 1. Program class | 2.0 | Core foundation |
| 2. PluginLoader | 2.5 | Most complex (merging) |
| 3. Builtin programs | 1.5 | Straightforward |
| 4. Config integration | 1.5 | Parallel with 5 |
| 5. CLI commands | 1.5 | Parallel with 4 |
| 6. Tests | 1.5 | Throughout |
| 7. Documentation | 1.0 | Final touch |
| **Total** | **~11 hours** | Buffer: 1-2 hours |

---

## Success Criteria (Phase 3)

✅ **Functionality:**
- [x] Program class loads and wraps Lua definitions
- [x] PluginLoader discovers builtin + user programs
- [x] Schema merging works (no conflicts)
- [x] Inheritance via `_extends` works
- [x] All 3 builtin programs loadable
- [x] User plugins discoverable
- [x] Config system recognizes programs section
- [x] 4 CLI commands (list, info, schema, generate)
- [x] Validation at load-time, merge-time, config-time

✅ **Quality:**
- [x] 25+ new tests passing
- [x] No breaking changes to Phase 1-2
- [x] Clear error messages
- [x] Full type hints

✅ **Integration:**
- [x] Config system integration smooth
- [x] CLI commands functional
- [x] Documentation clear

---

## Git Commit Plan

After all tasks:
```bash
git add -A
git commit -m "Phase 3: Program Registry implementation

- Implement Program class with schema validation & inheritance
- Implement PluginLoader with discovery & merging
- Add 3 builtin programs: git, neovim, syncthing
- Integrate with config system (programs section)
- Add CLI commands: registry list|info|schema|generate
- Full test suite (25+ tests)
- Documentation & examples

Tests: 84 passing (59 old + 25 new), 10 skipped, 1 pre-existing failure
"
```

---
