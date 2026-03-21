# foxBMS POSIX vECU — Gap Analysis (Phase 1: BMS NORMAL State)

**Date**: 2026-03-21
**Scope**: Only gaps in what is currently implemented and claimed working.
**NOT included**: Future phases (dynamic SOC, fault injection, Docker, GUI) — those are planned work, not gaps.

---

## What We Claim Works

1. foxBMS compiles and runs on Linux x86-64
2. BMS reaches NORMAL state through legitimate state transitions
3. 15+ CAN message types transmit periodically
4. Plant model sends realistic cell/IVT data
5. Contactor control works (SPS simulation)
6. CAN RX processes incoming messages
7. Database passthrough stores data
8. SOC reports 50%

---

## 1. System Architect (SIL)

| Gap | Severity | What we claim | What's actually true |
|-----|----------|---------------|---------------------|
| GA-01 | HIGH | Cyclic tasks run at 1ms/10ms/100ms | No timing verification. Loop runs as fast as CPU. `usleep(500)` is approximate. A 10ms task may run at 3ms or 50ms. |
| GA-02 | HIGH | foxBMS logic runs same as production | Single-threaded cooperative mode. Real foxBMS has 7 concurrent tasks. Data races and priority-dependent behavior won't surface. |
| GA-03 | MEDIUM | Database read/write works | `DATA_IterateOverDatabaseEntries` called synchronously inside `OS_SendToBackOfQueue`. In real foxBMS, write and read happen in different task contexts with queue buffering. Subtle ordering differences possible. |

---

## 2. HIL Test Engineer

| Gap | Severity | What we claim | What's actually true |
|-----|----------|---------------|---------------------|
| GA-04 | MEDIUM | Plant model sends realistic data | Plant sends static values (3700mV, 0A, 25°C) — never varies. Real battery data has noise, drift, IR drop. Not a gap in functionality, but in realism. |
| GA-05 | MEDIUM | Contactor control works | SPS simulation copies requested→actual in 1 cycle (instant). Real contactors have mechanical delay (5-20ms). |

---

## 3. Functional Safety Engineer

| Gap | Severity | What we claim | What's actually true |
|-----|----------|---------------|---------------------|
| GA-06 | **CRITICAL** | BMS runs foxBMS safety logic | `DIAG_Handler` always returns OK. foxBMS CANNOT detect overvoltage, overcurrent, overtemperature, or any other fault. All safety monitoring is disabled. |
| GA-07 | **CRITICAL** | `FAS_ASSERT` is set to NO_OP | Real software bugs (null pointers, array out of bounds, logic errors) are silently ignored. A crash in production would be a silent continue on POSIX. |
| GA-08 | HIGH | BMS reaches NORMAL state | BMS bypasses: SBC init (stubbed), RTC init (stubbed), current sensor presence (forced true). These are POSIX-specific bypasses, not production behavior. |

---

## 4. BMS Application Developer

| Gap | Severity | What we claim | What's actually true |
|-----|----------|---------------|---------------------|
| GA-09 | MEDIUM | SOC reports 50% | SOC never changes because current is always 0A. The counting algorithm runs but produces no change. Cannot verify SOC calculation correctness. |
| GA-10 | LOW | Balancing logic active | All cells identical (3700mV). Balancing calculates but has nothing to balance. Cannot verify balancing decisions. |

---

## 5. CAN Communication Engineer

| Gap | Severity | What we claim | What's actually true |
|-----|----------|---------------|---------------------|
| GA-11 | MEDIUM | CAN TX sends correct data | `canTransmit` writes via SocketCAN but doesn't simulate hardware mailbox behavior. No TX arbitration, no bus-off, no TX confirmation callback. |
| GA-12 | LOW | CAN RX processes messages | CAN node matching uses pointer comparison (`canNode == CAN_NODE_1`). If the pointer doesn't match exactly, messages are silently dropped. Only tested with CAN_NODE_1. |

---

## 6. Test Automation Engineer

| Gap | Severity | What we claim | What's actually true |
|-----|----------|---------------|---------------------|
| GA-13 | HIGH | foxBMS can be tested on POSIX | No automated test exists. Must manually start processes, wait, inspect candump output. No pass/fail criteria defined. |
| GA-14 | MEDIUM | Process lifecycle managed | foxBMS runs at 100% CPU in cooperative loop. `timeout` kills it but zombie child processes (candump, plant_model) may remain. Must manually cleanup. |

---

## 7. DevOps / CI Engineer

| Gap | Severity | What we claim | What's actually true |
|-----|----------|---------------|---------------------|
| GA-15 | HIGH | Reproducible build | Patches applied via Python scripts to upstream source. If foxBMS updates (even whitespace changes), patches may fail silently or with wrong line numbers. |
| GA-16 | MEDIUM | HALCoGen headers available | Must copy headers from Windows build. No automated way to generate them on Linux. |

---

## 8. Embedded Software Engineer (Portability)

| Gap | Severity | What we claim | What's actually true |
|-----|----------|---------------|---------------------|
| GA-17 | HIGH | Same code as production | 18 source files excluded (spi.c, i2c.c, dma.c, sbc/*, diag.c, etc.). Stubs may not match real function signatures exactly (void* vs typed pointers). |
| GA-18 | MEDIUM | Queue operations work | AFE queue copies 16 bytes. Actual `CAN_CAN2AFE_CELL_VOLTAGES_QUEUE_s` is ~13 bytes with compiler-dependent padding. Size mismatch risk on different compilers. |

---

## 9. End User

| Gap | Severity | What we claim | What's actually true |
|-----|----------|---------------|---------------------|
| GA-19 | MEDIUM | Easy to run | Requires 7 patch scripts applied in correct order, HALCoGen headers from Windows, vcan setup with sudo. No single-command setup. |

---

## 10. Project Manager

| Gap | Severity | What we claim | What's actually true |
|-----|----------|---------------|---------------------|
| GA-20 | MEDIUM | Complete documentation | STATUS.md describes all 14 fixes but doesn't quantify what percentage of foxBMS features actually work. No coverage matrix. |

---

## Summary

| Severity | Count | Key Gaps |
|----------|-------|----------|
| CRITICAL | 2 | DIAG disabled (GA-06), FAS_ASSERT disabled (GA-07) |
| HIGH | 5 | No timing (GA-01), single-threaded (GA-02), no auto-test (GA-13), fragile patches (GA-15), excluded files (GA-17) |
| MEDIUM | 10 | Static plant data, instant contactors, SOC static, queue sizes, etc. |
| LOW | 3 | Balancing untested, CAN node matching, no coverage matrix |

**Total**: 20 gaps in current Phase 1 implementation.

### Top 5 Actions (for what we have now)

1. **GA-06**: Implement selective DIAG_Handler — enable for software faults, suppress for hardware-absent faults. Without this, the BMS simulation is functionally unsafe.
2. **GA-07**: Add crash handler for FAS_ASSERT — log assertion location and exit, don't silently continue.
3. **GA-13**: Write a single smoke test script that verifies BMS reaches NORMAL and returns pass/fail.
4. **GA-01**: Add cycle time measurement — log warning if any cyclic function exceeds its deadline.
5. **GA-15**: Consolidate 14 patches into a single `apply_all.sh` with version check.
