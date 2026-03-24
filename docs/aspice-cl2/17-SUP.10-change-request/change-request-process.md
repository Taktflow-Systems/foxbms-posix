# Change Request Management Process

| Document ID | Rev | Date | Classification |
|---|---|---|---|
| SUP.10-001 | 1.0 | 2026-03-21 | Confidential |

## Revision History

| Rev | Date | Author | Reviewer | Description |
|---|---|---|---|---|
| 1.0 | 2026-03-21 | An Dao | L. Fischer | Initial release |

## 1. Purpose

This document defines the change request management process for the foxBMS 2 POSIX vECU project in accordance with ASPICE SUP.10 (Change Request Management). It establishes how changes to baselined configuration items are proposed, analyzed, approved, implemented, and verified.

## 2. Scope

The process covers changes to all baselined configuration items: foxBMS source patches, POSIX HAL stubs, plant model, test scripts, build scripts, and ASPICE documentation. It does not cover the upstream foxBMS v1.10.0 source (which is treated as an immutable dependency).

## 3. References

| ID | Title |
|---|---|
| [SUP.8-001] | Configuration Management Plan |
| [SUP.9-001] | Problem Resolution Management Process |
| [MAN.3-001] | Project Management Plan |

## 4. Change Categories

| Category | Description | Examples |
|---|---|---|
| Corrective | Fix a defect or gap identified in GAP-ANALYSIS.md | Fix DIAG_Handler, add cycle timing |
| Adaptive | Modify system to accommodate new requirements or environments | Add SIL probe override, add --timeout flag |
| Perfective | Improve quality, performance, or maintainability | Refactor plant model, improve documentation |
| Preventive | Prevent potential future problems | Add version check to apply_all.sh |

## 5. Change Request Workflow

### 5.1 Process Flow

```
  REQUEST (describe change, category, rationale)
      |
      v
  IMPACT ANALYSIS
  - Which patches affected?
  - Which DIAG IDs affected?
  - Which test criteria need re-run?
  - Which documents need update?
      |
      v
  APPROVAL (code review + smoke test pass)
      |
      v
  IMPLEMENTATION
  - Modify patch file(s) or source
  - Update affected tests
  - Update affected documentation
      |
      v
  VERIFICATION
  - apply_all.sh passes
  - test_smoke.py PASS
  - Affected test suites pass
      |
      v
  CLOSURE (commit, update GAP-ANALYSIS if applicable)
```

### 5.2 Step Details

#### 5.2.1 Request

A change request is initiated when:
- A gap in GAP-ANALYSIS.md requires a code change
- A new feature or capability is needed for the next phase
- A test failure reveals a needed correction
- An ASPICE assessment finding requires a process or artifact change

The request is documented in the Git commit message and, for significant changes, in GAP-ANALYSIS.md.

#### 5.2.2 Impact Analysis

Before implementing a change, the following impact analysis is performed:

| Analysis Area | Questions |
|---|---|
| Patches | Which of the 13 patches are affected? Will the change create a new patch or modify an existing one? |
| DIAG IDs | Does the change affect any of the 61 enabled or 24 suppressed DIAG IDs? |
| Safety | Does the change affect ASIL-classified requirements? Is HARA impacted? |
| Test criteria | Which of the 147 integration/ASIL criteria need re-execution? |
| Unit tests | Which of the 183+ Ceedling tests are affected? |
| Documentation | Which ASPICE documents need updating (requirements, architecture, test specs)? |
| Build | Does the change affect setup.sh, apply_all.sh, or Makefile? |
| Traceability | Which requirement-to-test traces are affected? |

#### 5.2.3 Approval

Changes are approved through:

| Approval Gate | Criterion |
|---|---|
| Code review | Change reviewed against QA checklist (SUP.1-001) |
| Build verification | apply_all.sh completes without error |
| Smoke test | test_smoke.py reports PASS |
| Safety review | For ASIL-relevant changes: DIAG ID list verified, test_asil.py pass |

#### 5.2.4 Implementation

Changes follow the patch workflow:

**For foxBMS source modifications**:
1. Identify which patch file to modify (or create new patch)
2. Apply change to working copy
3. Regenerate patch file with `diff -u`
4. Update apply_all.sh if patch count or order changes
5. Verify: `./apply_all.sh` on clean foxBMS checkout

**For POSIX-specific source files** (src/):
1. Modify source directly
2. Ensure compilation with -Wall -Wextra (zero warnings)
3. Run affected unit tests

**For test scripts**:
1. Add or modify test criteria
2. Ensure test still runs within timeout
3. Verify pass/fail verdicts are correct

**For documentation**:
1. Update affected ASPICE work product
2. Update revision history
3. Verify cross-references

#### 5.2.5 Verification

| Verification Activity | When Required |
|---|---|
| apply_all.sh passes | Every patch change |
| test_smoke.py PASS | Every change |
| test_integration.py 21/21 | Integration-affecting changes |
| test_asil.py 50/50 | Safety-affecting changes |
| Ceedling unit tests pass | Module-level changes |
| Document review | Documentation changes |

#### 5.2.6 Closure

- Commit to Git with descriptive message
- Update GAP-ANALYSIS.md if change resolves a gap
- Update COVERAGE.md if change affects feature status

## 6. Patch Change Register

The following table records significant changes to the patch set:

| Date | Patch # | Change | Category | Trigger |
|---|---|---|---|---|
| 2026-02-01 | 01-04 | Initial POSIX HAL patches | Adaptive | Phase 1 start |
| 2026-02-15 | 03 | Selective DIAG_Handler (24/61 split) | Corrective | GA-06 |
| 2026-02-20 | 07 | FAS_ASSERT log + exit(1) | Corrective | GA-07 |
| 2026-02-25 | 05 | Contactor delay simulation | Perfective | GA-05 |
| 2026-03-01 | 09 | Cycle time measurement | Corrective | GA-01 |
| 2026-03-05 | 10 | Timeout flag (--timeout N) | Adaptive | GA-28 |
| 2026-03-14 | 12 | SIL probe override system (CAN 0x7E0) | Adaptive | GA-29 |
| 2026-03-17 | 11 | Software watchdog (100ms stall) | Corrective | GA-24 |

## 7. Change Impact on DIAG IDs

When a change affects diagnostic behavior, the following matrix is consulted:

| Change Type | Affected DIAG IDs | Required Verification |
|---|---|---|
| New DIAG ID suppression | Add to 24-ID suppressed list | test_asil.py re-run; update COVERAGE.md |
| New DIAG ID enablement | Add to 61-ID enabled list | test_asil.py re-run; verify fault injection path |
| Threshold change | Affected SOA threshold IDs | test_asil.py re-run with new threshold values |
| State machine change | BMS/CONT state transitions | test_integration.py re-run |
| Plant model change | Indirectly all enabled IDs | test_smoke.py + test_integration.py re-run |

## 8. Emergency Change Process

For CRITICAL severity problems requiring immediate resolution:

1. Fix is implemented directly on main branch
2. Smoke test must pass before commit
3. Full test suite (integration + ASIL) run immediately after commit
4. GAP-ANALYSIS.md updated with resolution
5. Change documented retroactively in this register

## 9. CL2 Gaps for SUP.10

| Gap | Description | Action Required |
|---|---|---|
| No formal CR form | Changes tracked in Git commits and GAP-ANALYSIS, not formal CR forms | Create CR template with ID, requester, impact, approval |
| No CR status tracking | No separate CR register with status tracking | Maintain CR log in this document or separate register |
| No approval records | Approval is implicit (smoke test pass + commit) | Add explicit approval field to CR records |
