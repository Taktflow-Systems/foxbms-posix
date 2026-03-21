# Problem Resolution Management Process

| Document ID | Rev | Date | Classification |
|---|---|---|---|
| SUP.9-001 | 1.0 | 2026-03-21 | Confidential |

## Revision History

| Rev | Date | Author | Reviewer | Description |
|---|---|---|---|---|
| 1.0 | 2026-03-21 | An Dao | -- | Initial release |

## 1. Purpose

This document defines the problem resolution management process for the foxBMS 2 POSIX vECU project in accordance with ASPICE SUP.9 (Problem Resolution Management). It establishes how problems (defects, gaps, anomalies) are identified, recorded, analyzed, resolved, and closed.

## 2. Scope

The process covers all problems discovered during development, testing, review, and assessment activities for the foxBMS POSIX vECU project. This includes code defects, specification gaps, test failures, process deviations, and architectural limitations.

## 3. References

| ID | Title |
|---|---|
| [SUP.1-001] | Quality Assurance Plan |
| [MAN.3-001] | Project Management Plan |
| [GAP-ANALYSIS] | foxBMS POSIX vECU Gap Analysis |

## 4. Problem Tracking System

### 4.1 Primary Register

The GAP-ANALYSIS.md document serves as the project's problem register. Each problem is assigned a unique identifier and tracked through its lifecycle.

| Field | Format | Example |
|---|---|---|
| Problem ID | GA-xx | GA-06 |
| Severity | CRITICAL / HIGH / MEDIUM / LOW | CRITICAL |
| Title | Short description | Selective DIAG_Handler |
| What we claim | Expected behavior | BMS runs foxBMS safety logic |
| What's actually true | Actual behavior | All DIAG IDs returning OK (including safety-critical ones) |
| Status | OPEN / FIXED / ACCEPTED / CLOSED | FIXED |
| Resolution | Description of fix or acceptance rationale | 24 HW suppressed, 61 SW enabled |

### 4.2 Problem ID Allocation

Problem IDs are allocated sequentially from GA-01. The current range is GA-01 through GA-33, with additional IDs available for future discoveries.

## 5. Severity Classification

| Severity | Definition | Response | Examples |
|---|---|---|---|
| CRITICAL | Safety function is incorrect, missing, or produces wrong results. System cannot fulfill its safety purpose. | Immediate fix required. Blocks all releases. | GA-06: DIAG_Handler returning OK for all IDs. GA-07: FAS_ASSERT silently continuing. |
| HIGH | Core functionality broken, significant deviation from specification, or build/test infrastructure failure. | Fix within current phase. | GA-01: No cycle time measurement. GA-13: No automated test. GA-17: 18 source files excluded. |
| MEDIUM | Deviation from specification with workaround available, or missing feature that does not affect core function. | Fix or accept within next phase. | GA-03: DB synchronous passthrough. GA-11: No CAN TX arbitration. GA-29: No fault injection API. |
| LOW | Minor deviation, cosmetic issue, or theoretical concern with no observed impact. | Track for future resolution. | GA-10: Balancing inactive (correct behavior). GA-12: CAN node pointer comparison. |

## 6. Problem Resolution Workflow

### 6.1 Process Flow

```
  IDENTIFY
     |
     v
  RECORD (assign GA-xx ID, severity, description)
     |
     v
  ANALYZE (root cause, impact, affected requirements)
     |
     v
  RESOLVE -----> ACCEPT (with documented rationale)
     |                |
     v                v
  VERIFY          DOCUMENT (why accepted, what limitations)
     |                |
     v                v
  CLOSE           CLOSE
```

### 6.2 Step Details

#### 6.2.1 Identify

Problems are discovered through:
- Multi-perspective audit (10-role audit: Safety, CAN, Battery, RTOS, HW, Test, Build, Data, Contactor, Code Quality)
- Test execution (smoke, integration, ASIL test failures)
- Code review and static analysis
- User feedback (build failures, unexpected behavior)
- Gap analysis review at phase gates

#### 6.2.2 Record

Each problem is recorded in GAP-ANALYSIS.md with:
- Unique GA-xx identifier
- Severity classification (CRITICAL/HIGH/MEDIUM/LOW)
- "What we claim" vs. "What's actually true" comparison
- Categorization by audit role (System Architect, HIL Test Engineer, etc.)

#### 6.2.3 Analyze

Analysis determines:
- Root cause of the problem
- Affected requirements (SYS-REQ, SW-REQ, STKH-REQ)
- Affected test criteria
- Impact on safety (ASIL classification relevance)
- Feasibility of fix vs. acceptance

#### 6.2.4 Resolve

Resolution options:

| Option | Criteria | Action |
|---|---|---|
| FIX | Root cause can be addressed; fix is feasible and tested | Implement fix, update tests, verify |
| ACCEPT | Architectural limitation; fix is infeasible or unnecessary for SIL scope | Document rationale, update COVERAGE.md |
| CLOSE | Problem is not a real gap (e.g., correct behavior, out of scope) | Document reasoning |

#### 6.2.5 Verify

For FIXED problems:
- Run relevant test suite (smoke, integration, or ASIL)
- Verify the specific scenario that exposed the problem
- Confirm no regression in related functionality

#### 6.2.6 Close

Update GAP-ANALYSIS.md:
- Strike through original severity: `~~CRITICAL~~ **FIXED**`
- Add resolution description
- Update summary table counts

## 7. Current Problem Status

### 7.1 Summary

| Status | Count |
|---|---|
| FIXED | 23 |
| ACCEPTED (architectural/SIL-valid) | 10 |
| Open CRITICAL | 0 |
| Open HIGH | 0 |
| Open MEDIUM | 0 |
| Open LOW | 0 |
| **Total** | **33** |

### 7.2 Resolution History

| Phase | Problems Found | Fixed | Accepted | Remaining |
|---|---|---|---|---|
| Phase 1 (BMS NORMAL) | 20 | 12 | 5 | 3 |
| Phase 2 (Realistic Sim) | 5 | 4 | 1 | 0 |
| Phase 2.5 (SIL Probes) | 8 | 7 | 4 | 0 |
| **Total** | **33** | **23** | **10** | **0** |

### 7.3 Severity Resolution

| Original Severity | Count | All Resolved |
|---|---|---|
| CRITICAL | 2 | Yes (GA-06 FIXED, GA-07 FIXED) |
| HIGH | 6 | Yes (3 FIXED, 3 ACCEPTED) |
| MEDIUM | 17 | Yes (all FIXED or ACCEPTED) |
| LOW | 8 | Yes (all FIXED or ACCEPTED) |

## 8. Accepted Problems Register

The following problems are permanently accepted with documented rationale:

| GA ID | Problem | Rationale for Acceptance |
|---|---|---|
| GA-02 | Single-threaded cooperative mode | FreeRTOS POSIX port unreliable. Cooperative mode is deterministic for SIL. |
| GA-08 | BMS bypasses (SBC, RTC, current sensor) | Hardware does not exist on POSIX; bypasses are required. |
| GA-17 | 18 source files excluded | TMS570-specific hardware access; cannot compile on x86. |
| GA-03 | DB synchronous passthrough | Single-threaded = no data races = deterministic. Better for SIL. |
| GA-11 | No CAN TX arbitration | Single sender on vcan; no contention. HIL-only concern. |
| GA-18 | AFE queue 16-byte copy | Works on x86-64 GCC. Theoretical padding concern only. |
| GA-26 | No CAN TX period enforcement | 1ms cooperative loop matches cycle rate. SIL tests logic, not bus timing. |
| GA-27 | No E2E protection | SocketCAN pipe has zero corruption. Bus noise is a HIL concern. |
| GA-10 | Balancing inactive | Correct behavior: identical cells = nothing to balance. |
| GA-12 | CAN node pointer comparison | Single CAN node in SIL. Works for CAN_NODE_1. |

## 9. Escalation Process

| Condition | Escalation Action |
|---|---|
| CRITICAL problem discovered | Block current phase; fix immediately |
| HIGH problem not resolved within phase | Escalate to phase gate review for accept/defer decision |
| Accepted problem impacts safety claim | Review HARA and ASIL decomposition; update safety case |
| Problem recurs after fix | Root cause analysis; strengthen verification |

## 10. CL2 Gaps for SUP.9

| Gap | Description | Action Required |
|---|---|---|
| No trend analysis | Problem discovery rate not tracked over time | Create problem trend chart |
| No formal escalation records | Escalation decisions not documented separately | Add escalation log to GAP-ANALYSIS.md |
| No problem review meetings | Single-person team; no meeting minutes | Document review decisions with date/rationale |
