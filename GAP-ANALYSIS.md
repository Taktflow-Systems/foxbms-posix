# foxBMS POSIX vECU — Gap Analysis (10 Perspectives)

**Date**: 2026-03-21
**Baseline**: foxBMS in NORMAL state, 15+ CAN messages, plant model feeding data

---

## 1. System Architect (SIL Integration)

**Strengths**:
- Cooperative main loop is deterministic — no threading races
- Database passthrough eliminates queue timing issues
- SocketCAN interface is standard — works with any CAN tool

**Gaps**:
| Gap | Severity | Description |
|-----|----------|-------------|
| GA-SYS-001 | HIGH | No timing verification — cooperative loop runs as fast as CPU allows, not at real 1ms/10ms/100ms rates. `usleep(500)` is approximate. |
| GA-SYS-002 | HIGH | Single-threaded — real foxBMS has 7 concurrent FreeRTOS tasks. Race conditions or timing-dependent bugs won't be caught. |
| GA-SYS-003 | MEDIUM | No watchdog simulation — foxBMS feeds external TPS3823 watchdog. On POSIX, WDI pin toggle is a no-op. |
| GA-SYS-004 | MEDIUM | `FAS_ASSERT = NO_OP` hides real software bugs. Need selective assertion: enable for BMS logic, disable only for hardware checks. |
| GA-SYS-005 | LOW | `DIAG_Handler` always returns OK — masks legitimate diagnostic events from BMS application. |

**Recommendation**: Implement cycle time measurement. Log if any cycle exceeds its deadline. Add selective FAS_ASSERT per module.

---

## 2. HIL Test Engineer

**Strengths**:
- SocketCAN works with real CAN hardware (canable) — can connect to physical ECUs
- Plant model is Python — easy to modify test scenarios
- Same CAN IDs as real foxBMS hardware

**Gaps**:
| Gap | Severity | Description |
|-----|----------|-------------|
| GA-HIL-001 | HIGH | Plant model is open-loop — doesn't read foxBMS CAN TX to adjust behavior. No closed-loop battery simulation. |
| GA-HIL-002 | HIGH | No contactor feedback via CAN — SPS simulation is internal only. Real HIL bench needs contactor state on CAN bus. |
| GA-HIL-003 | MEDIUM | No interlock simulation — interlock always reports CLOSED. Can't test interlock-open scenarios. |
| GA-HIL-004 | MEDIUM | IVT message timing not validated — plant sends every 100ms but foxBMS expects specific timing windows. |
| GA-HIL-005 | LOW | No CAN error frame injection — can't test bus-off recovery, CRC errors, missing messages. |

**Recommendation**: Make plant model read 0x240 (contactor state) to close the loop. Add CAN message timeout simulation.

---

## 3. Functional Safety Engineer (ISO 26262)

**Strengths**:
- BMS state machine runs unmodified foxBMS code — same logic as production
- Contactor control sequence is realistic (precharge, voltage check, close)
- Error detection paths exist (DIAG, plausibility)

**Gaps**:
| Gap | Severity | Description |
|-----|----------|-------------|
| GA-SAFE-001 | CRITICAL | DIAG_Handler stubbed — ALL safety-relevant errors suppressed. Overvoltage, overcurrent, overtemperature detection non-functional. |
| GA-SAFE-002 | CRITICAL | No ESM (Error Signaling Module) — hardware error escalation path doesn't exist. |
| GA-SAFE-003 | HIGH | No lockstep CPU simulation — TMS570 CCM-R5F lockstep comparison not modeled. |
| GA-SAFE-004 | HIGH | No memory protection — MPU regions not simulated. Stack overflow, buffer overrun not caught. |
| GA-SAFE-005 | MEDIUM | FAS_ASSERT disabled — defensive programming assertions bypassed. |

**Recommendation**: Implement selective DIAG_Handler — allow software-detectable faults (overvoltage, overtemp) while suppressing hardware-absent faults (SPI timeout, I2C NACK). This is the highest-priority gap.

---

## 4. BMS Application Developer

**Strengths**:
- Full BMS state machine runs — can develop and test state transitions
- Cell voltage, current, temperature data flows through standard foxBMS paths
- SOC estimation running (counting method)
- Balancing logic active

**Gaps**:
| Gap | Severity | Description |
|-----|----------|-------------|
| GA-APP-001 | MEDIUM | SOC never changes — plant sends 0A, so coulomb counting stays at 50%. |
| GA-APP-002 | MEDIUM | Balancing has no effect — cell voltages are all identical (3700mV). No imbalance to correct. |
| GA-APP-003 | MEDIUM | SOF (State of Function) calculates but all cells identical — power limits are uniform. |
| GA-APP-004 | LOW | No FRAM persistence — SOC resets to 50% on every startup. |
| GA-APP-005 | LOW | No deep discharge flag handling — FRAM stub returns defaults. |

**Recommendation**: Add dynamic current in plant model. Vary cell voltages for imbalance testing. Implement FRAM as file-backed RAM for persistence.

---

## 5. CAN Communication Engineer

**Strengths**:
- 15+ CAN message types with correct IDs and encoding
- foxBMS big-endian encoding verified with roundtrip test
- SocketCAN compatible with any CAN analysis tool

**Gaps**:
| Gap | Severity | Description |
|-----|----------|-------------|
| GA-CAN-001 | HIGH | CAN RX only processes known IDs — no error handling for unknown/malformed frames. |
| GA-CAN-002 | MEDIUM | canTransmit sends via SocketCAN but doesn't simulate TX mailbox behavior (arbitration, bus-off). |
| GA-CAN-003 | MEDIUM | No DBC file for all foxBMS messages — only cell voltage/temp defined in foxbms_signals.dbc. |
| GA-CAN-004 | LOW | CAN message counters/CRC not validated — E2E protection not active in POSIX mode. |
| GA-CAN-005 | LOW | CAN2 (isolated) not simulated — only CAN1 node implemented. |

**Recommendation**: Create complete DBC file for all foxBMS messages. Enable E2E protection for critical messages.

---

## 6. Test Automation Engineer

**Strengths**:
- Plant model is scriptable Python — easy to automate test sequences
- foxBMS exits cleanly on timeout or Ctrl+C
- CAN capture via candump for post-processing

**Gaps**:
| Gap | Severity | Description |
|-----|----------|-------------|
| GA-TEST-001 | HIGH | No test framework — plant_model.py is a single script, not a test suite. |
| GA-TEST-002 | HIGH | No pass/fail criteria — must manually inspect candump output. |
| GA-TEST-003 | MEDIUM | Zombie processes — foxBMS runs at 100% CPU, timeout doesn't always kill cleanly. |
| GA-TEST-004 | MEDIUM | No regression test suite — can't verify fixes don't break previous functionality. |
| GA-TEST-005 | LOW | Plant model has no assertions — doesn't check foxBMS responses. |

**Recommendation**: Build pytest-based test framework. Each test: start plant → start foxBMS → wait → check CAN output → assert. Kill processes in teardown.

---

## 7. DevOps / CI Engineer

**Strengths**:
- Builds with standard GCC on Linux — CI-friendly
- No special hardware required — runs in any VM/container

**Gaps**:
| Gap | Severity | Description |
|-----|----------|-------------|
| GA-CI-001 | HIGH | No CI pipeline — build and test not automated. |
| GA-CI-002 | HIGH | Patches applied manually — fragile, breaks if foxBMS source changes. |
| GA-CI-003 | MEDIUM | HALCoGen headers must be copied from Windows — not automated. |
| GA-CI-004 | MEDIUM | No Docker image — can't deploy to Netcup or other servers easily. |
| GA-CI-005 | LOW | Build warnings not treated as errors — potential issues hidden. |

**Recommendation**: Create GitHub Actions workflow: checkout → apply patches → build → run 10-second smoke test → check BMS state in CAN output. Dockerize for deployment.

---

## 8. End User (BMS Integrator)

**Strengths**:
- Can test BMS behavior without purchasing foxBMS hardware ($5000+)
- Standard SocketCAN — integrates with existing CAN tools
- Quick iteration — compile + test in <30 seconds

**Gaps**:
| Gap | Severity | Description |
|-----|----------|-------------|
| GA-USER-001 | HIGH | No GUI — must use command-line tools (candump, grep) to monitor BMS state. |
| GA-USER-002 | HIGH | Battery config hardcoded (18 cells, 1 string) — can't easily change to match real pack. |
| GA-USER-003 | MEDIUM | No documentation for changing battery parameters. |
| GA-USER-004 | MEDIUM | Error messages go to stderr mixed with debug traces — hard to parse. |
| GA-USER-005 | LOW | No Windows support — Linux only. |

**Recommendation**: Add structured JSON logging. Create battery_config.py for easy parameter changes. Consider web dashboard.

---

## 9. Embedded Software Engineer (Portability)

**Strengths**:
- Same C source as production — no code divergence
- Patches are external (Python scripts) — upstream source untouched
- Submodule pins exact foxBMS version

**Gaps**:
| Gap | Severity | Description |
|-----|----------|-------------|
| GA-PORT-001 | HIGH | Patches are fragile — string matching breaks if foxBMS reformats code. |
| GA-PORT-002 | HIGH | 14 separate patches — hard to maintain, no dependency tracking between them. |
| GA-PORT-003 | MEDIUM | HALCoGen headers patched in-place — needs re-patching after every HALCoGen regeneration. |
| GA-PORT-004 | MEDIUM | Queue buffer sizes hardcoded (16 entries, 16 bytes) — may not match all foxBMS data structures. |
| GA-PORT-005 | LOW | No upgrade path — moving to foxBMS v1.11+ requires re-verifying all patches. |

**Recommendation**: Consolidate patches into a single `apply_patches.sh`. Add version check. Use `git apply` format instead of Python scripts.

---

## 10. Project Manager / Reviewer

**Strengths**:
- Clear documentation (STATUS.md, PLAN.md, README.md)
- Git history tracks every decision and fix
- Separate submodule — clean separation from upstream

**Gaps**:
| Gap | Severity | Description |
|-----|----------|-------------|
| GA-PM-001 | HIGH | No metrics — can't quantify code coverage, test coverage, or BMS feature coverage. |
| GA-PM-002 | MEDIUM | No comparison matrix — which foxBMS features work vs don't work on POSIX. |
| GA-PM-003 | MEDIUM | Lessons learned scattered across multiple files — need consolidation. |
| GA-PM-004 | LOW | No effort tracking — total hours invested not documented. |
| GA-PM-005 | LOW | No risk register — known risks not formally documented. |

**Recommendation**: Create feature coverage matrix. Track foxBMS modules: fully working / partially working / stubbed / not applicable.

---

## Summary: Top 10 Priority Gaps

| Rank | Gap ID | Severity | Description | Effort |
|------|--------|----------|-------------|--------|
| 1 | GA-SAFE-001 | CRITICAL | DIAG_Handler suppresses all safety errors | 4h |
| 2 | GA-SAFE-002 | CRITICAL | No ESM error escalation | 2h |
| 3 | GA-HIL-001 | HIGH | Plant model is open-loop | 4h |
| 4 | GA-TEST-001 | HIGH | No test framework | 8h |
| 5 | GA-CI-001 | HIGH | No CI pipeline | 4h |
| 6 | GA-SYS-001 | HIGH | No timing verification | 2h |
| 7 | GA-APP-001 | MEDIUM | SOC never changes (0A current) | 1h |
| 8 | GA-CAN-003 | MEDIUM | No complete DBC file | 4h |
| 9 | GA-PORT-001 | HIGH | Patches are fragile | 4h |
| 10 | GA-USER-001 | HIGH | No GUI/dashboard | 8h |

**Total estimated effort for top 10**: ~41 hours
