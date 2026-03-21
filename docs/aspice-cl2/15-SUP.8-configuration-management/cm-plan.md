# Configuration Management Plan

| Document ID | Rev | Date | Classification |
|---|---|---|---|
| SUP.8-001 | 1.0 | 2026-03-21 | Confidential |

## Revision History

| Rev | Date | Author | Reviewer | Description |
|---|---|---|---|---|
| 1.0 | 2026-03-21 | An Dao | -- | Initial release |

## 1. Purpose

This document defines the configuration management plan for the foxBMS 2 POSIX vECU project in accordance with ASPICE SUP.8 (Configuration Management). It establishes how configuration items are identified, controlled, versioned, and maintained throughout the project lifecycle.

## 2. Scope

Configuration management covers all project artifacts: source code, patches, build scripts, test scripts, documentation, plant model, and third-party dependencies.

## 3. References

| ID | Title |
|---|---|
| [MAN.3-001] | Project Management Plan |
| [SUP.1-001] | Quality Assurance Plan |

## 4. Configuration Items

### 4.1 Item Identification

| CI Category | Items | Naming Convention | Location |
|---|---|---|---|
| foxBMS base | foxBMS v1.10.0 source | Git submodule | foxbms-2/ |
| POSIX patches | 13 patch files | NN-description.patch | patches/ |
| HAL stubs | hal_stubs_posix.c, posix_can.c, etc. | Module name | src/ |
| Plant model | plant_model.py | Script name | plant/ or root |
| Test scripts | test_smoke.py, test_integration.py, test_asil.py | test_*.py | tests/ |
| Build system | Makefile, setup.sh, apply_all.sh | Standard names | Root |
| HALCoGen headers | 91 header files (BSD-licensed) | Original names | halcogen-headers/ |
| ASPICE documents | 18 work products | AREA-description.md | docs/aspice/ |
| CL2 evidence | Assessment documents | Per folder convention | docs/aspice-cl2/ |
| Gap analysis | GAP-ANALYSIS.md | Fixed name | Root |
| Coverage matrix | COVERAGE.md | Fixed name | Root |

### 4.2 Configuration Item States

| State | Definition |
|---|---|
| DRAFT | Work in progress, not yet reviewed |
| REVIEWED | Reviewed against checklist, ready for baseline |
| BASELINED | Part of a release baseline, changes require CR |
| SUPERSEDED | Replaced by a newer version |

## 5. Git Workflow

### 5.1 Repository Structure

```
foxbms-posix/                    # Main repository
  foxbms-2/                      # Git submodule (pinned to v1.10.0)
  patches/                       # POSIX adaptation patches
  src/                           # POSIX-specific source files
  tests/                         # Test scripts
  docs/                          # Documentation
    aspice/                      # ASPICE work products (flat)
    aspice-cl2/                  # CL2 assessor hierarchy
  halcogen-headers/              # HALCoGen-generated headers
  build/                         # Build output (not tracked)
```

### 5.2 Branch Strategy

| Branch | Purpose | Protection |
|---|---|---|
| main | Stable, tested code; each commit passes smoke test | Default branch |
| feature/* | Development branches for new capabilities | Merge to main after test pass |
| phase/* | Phase-level development branches | Merge at phase gate |

### 5.3 Commit Conventions

- Each commit message describes the change purpose
- Safety-relevant changes reference the affected DIAG IDs or requirements
- Patch modifications include the patch number in the commit message

### 5.4 Submodule Management

The foxBMS 2 source is included as a Git submodule pinned to version v1.10.0.

| Parameter | Value |
|---|---|
| Submodule path | foxbms-2/ |
| Remote URL | foxBMS 2 official repository |
| Pinned version | v1.10.0 |
| Version verification | apply_all.sh checks version before patching |

**Rationale**: Pinning to v1.10.0 ensures build reproducibility. The version check in apply_all.sh prevents accidental patching of a different foxBMS version.

## 6. Patch Management

### 6.1 Patch Workflow

The POSIX adaptation requires 13 patches applied to the foxBMS v1.10.0 source tree. These patches are managed as discrete files in the patches/ directory.

| # | Patch | Purpose |
|---|---|---|
| 01 | POSIX HAL types | Replace TMS570 types with POSIX equivalents |
| 02 | CAN SocketCAN | Replace HW CAN with SocketCAN |
| 03 | DIAG selective | Selective DIAG_Handler (24 HW suppressed) |
| 04 | OS cooperative | Cooperative loop replacing FreeRTOS |
| 05 | SPS simulation | Contactor delay simulation |
| 06 | Database passthrough | Synchronous DB access |
| 07 | Assert handler | FAS_ASSERT log + exit(1) |
| 08 | AFE stub | AFE measurement stub |
| 09 | Timing measurement | Cycle time tracking |
| 10 | Timeout flag | --timeout N support |
| 11 | Watchdog | Software watchdog (100ms stall detection) |
| 12 | SIL probes | CAN 0x7E0 override system |
| 13 | Build fixes | Miscellaneous compilation fixes |

### 6.2 Patch Application

```bash
./apply_all.sh
```

The apply_all.sh script:
1. Checks foxBMS version is v1.10.0
2. Applies patches 01-13 in order
3. Reports success or failure for each patch
4. Exits with non-zero code if any patch fails

### 6.3 Patch Integrity

| Control | Implementation |
|---|---|
| Version check | apply_all.sh verifies foxBMS v1.10.0 before patching |
| Order enforcement | Patches numbered 01-13; applied sequentially |
| Idempotency | Script detects already-applied patches |
| Failure handling | Stops on first failure; reports which patch failed |

## 7. Build Reproducibility

### 7.1 Deterministic Build

| Factor | Control |
|---|---|
| Source version | foxBMS v1.10.0 (Git submodule, pinned) |
| Compiler | GCC 13 |
| OS | Ubuntu 24.04 LTS |
| Python | 3.12 |
| Build command | `make -C build/` |
| Full setup | `./setup.sh` (clone, patch, build, test) |

### 7.2 Build Verification

The setup.sh script performs the complete build and verification:

1. Initialize and update Git submodules
2. Apply all patches via apply_all.sh
3. Compile foxbms-vecu with GCC 13
4. Configure vcan0 interface
5. Run smoke test (test_smoke.py)

A successful setup.sh run is the baseline verification that the build is reproducible.

## 8. Tool Environment

### 8.1 Tool Versions

| Tool | Required Version | Purpose |
|---|---|---|
| GCC | 13.x | C compilation |
| GNU Make | 4.x | Build orchestration |
| Python | 3.12.x | Plant model, test scripts |
| Git | 2.43+ | Version control |
| python-can | Latest | SocketCAN Python binding |
| can-utils | System | CAN debugging tools |
| Ceedling | Latest | Unit test framework |
| Ubuntu | 24.04 LTS | Host operating system |

### 8.2 Tool Qualification

For ASIL-D development per ISO 26262 Part 8, the following tool classifications apply:

| Tool | TCL | Rationale |
|---|---|---|
| GCC 13 | TCL2 | Compiler output directly affects safety function |
| Ceedling | TCL1 | Test tool; does not generate production code |
| python-can | TCL1 | Test infrastructure only |
| SocketCAN | TCL1 | Simulation interface only |

TCL2 tools require qualification or validation. GCC is validated through the comprehensive test suite (183+ unit tests, 147 integration/ASIL criteria) which serves as a back-to-back test of compiler correctness.

## 9. Release Process

### 9.1 Release Criteria

A release baseline is established when:

| # | Criterion | Verification |
|---|---|---|
| 1 | setup.sh passes on a fresh clone | Manual test on clean machine |
| 2 | test_smoke.py reports PASS | Automated |
| 3 | test_integration.py 21/21 pass | Automated |
| 4 | test_asil.py 50/50 pass | Automated |
| 5 | GAP-ANALYSIS.md has 0 open CRITICAL/HIGH | Manual review |
| 6 | All ASPICE documents reviewed and current | Manual review |

### 9.2 Baseline Identification

Baselines are identified by Git tags:

| Tag Format | Example | Description |
|---|---|---|
| vX.Y.Z | v1.0.0 | Release version |
| phase-N | phase-3 | Phase gate baseline |

### 9.3 Current Baseline Status

| Baseline | Tag | Date | Status |
|---|---|---|---|
| Phase 1: BMS NORMAL | phase-1 | 2026-03-01 | Released |
| Phase 2: Realistic Sim | phase-2 | 2026-03-10 | Released |
| Phase 2.5: SIL Probes | phase-2.5 | 2026-03-17 | Released |
| Phase 3: Fault Injection | phase-3 | 2026-03-21 | In progress |

## 10. CL2 Gaps for SUP.8

| Gap | Description | Action Required |
|---|---|---|
| No formal baseline record | Git tags exist but no baseline report document | Create baseline report template |
| No configuration audit | Items not formally audited against baseline | Perform configuration audit at Phase 3 gate |
| No CM status accounting | No report of CI states and changes over time | Generate CM status report |
