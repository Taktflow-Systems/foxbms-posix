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
| GA-01 | ~~HIGH~~ **FIXED** | Cyclic tasks run at 1ms/10ms/100ms | **FIXED**: Cycle time measurement added. Each task execution is timed; warnings logged if deadline exceeded. Summary printed at exit showing max execution times and violation count. |
| GA-02 | HIGH (**ACCEPTED**) | foxBMS logic runs same as production | Single-threaded cooperative mode. Real foxBMS has 7 concurrent tasks. Data races and priority-dependent behavior won't surface. **Accepted**: FreeRTOS POSIX port proved unreliable for foxBMS. Cooperative mode is the only stable approach. Documented in COVERAGE.md. |
| GA-03 | MEDIUM | Database read/write works | `DATA_IterateOverDatabaseEntries` called synchronously inside `OS_SendToBackOfQueue`. In real foxBMS, write and read happen in different task contexts with queue buffering. Subtle ordering differences possible. |
| GA-21 | LOW | Plant model and vECU start independently | No startup synchronization. If vECU starts before plant model, first ~3s of CAN RX data is missing. No `READY` barrier. |
| GA-22 | ~~LOW~~ **FIXED** | vECU shuts down cleanly | **FIXED**: SIGINT handler sets `running=0`, main loop exits, calls `SPS_SwitchOffAllGeneralIoChannels()` to open all contactors, then prints timing summary. |

---

## 2. HIL Test Engineer

| Gap | Severity | What we claim | What's actually true |
|-----|----------|---------------|---------------------|
| GA-04 | MEDIUM | Plant model sends realistic data | Plant sends static values (3700mV, 0A, 25°C) — never varies. Real battery data has noise, drift, IR drop. Not a gap in functionality, but in realism. |
| GA-05 | ~~MEDIUM~~ **FIXED** | Contactor control works | **FIXED**: SPS simulation now has configurable per-channel delay counter (`SPS_CONTACTOR_DELAY_CYCLES`, default 10 = ~10ms). Transition logged with old→new state. |

---

## 3. Functional Safety Engineer

| Gap | Severity | What we claim | What's actually true |
|-----|----------|---------------|---------------------|
| GA-06 | ~~CRITICAL~~ **FIXED** | BMS runs foxBMS safety logic | **FIXED**: Selective DIAG_Handler implemented. 24 hardware-absent IDs return OK. 61 software-checkable IDs (overvoltage, overcurrent, overtemperature, plausibility) log faults and return ERR_OCCURRED. |
| GA-07 | ~~CRITICAL~~ **FIXED** | `FAS_ASSERT` is set to NO_OP | **FIXED**: `FAS_StoreAssertLocation()` overridden to log pc/line to stderr and call `exit(1)`. Assertions now crash visibly instead of silently continuing. |
| GA-08 | HIGH (**ACCEPTED**) | BMS reaches NORMAL state | BMS bypasses: SBC init (stubbed), RTC init (stubbed), current sensor presence (forced true). **Accepted**: These are POSIX-specific bypasses required because the hardware doesn't exist. Cannot be removed without the physical ICs. Documented in COVERAGE.md. |
| GA-23 | MEDIUM | Interlock chain functional | Interlock chain is hardcoded always-closed. Cannot simulate interlock-break → safe-state transition path. |
| GA-24 | MEDIUM | Watchdog protects against hangs | SBC bypass (GA-08) also removes hardware watchdog. No timeout → safe-state transition possible. Real foxBMS has SBC watchdog that triggers ERROR if not serviced. |
| GA-25 | MEDIUM | IVT current redundancy works | Real foxBMS cross-checks IVT primary and secondary current paths. Only primary is simulated. Cross-check code never exercises a mismatch scenario. |

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
| GA-26 | MEDIUM | 15+ CAN messages transmit periodically | `canTransmit` fires whenever the cooperative loop reaches it, not at DBC-specified periods. No period enforcement or drift detection. A "100ms" message may fire at 1ms or 500ms depending on loop speed. |
| GA-27 | MEDIUM | CAN messages have AUTOSAR E2E protection | Real foxBMS uses AUTOSAR E2E checksums on CAN messages. POSIX port bypasses all E2E checks entirely. Messages have no integrity verification. |

---

## 6. Test Automation Engineer

| Gap | Severity | What we claim | What's actually true |
|-----|----------|---------------|---------------------|
| GA-13 | ~~HIGH~~ **FIXED** | foxBMS can be tested on POSIX | **FIXED**: `test_smoke.py` starts plant model + vECU, monitors CAN for BMS NORMAL state, returns exit code 0=PASS / 1=FAIL / 2=ERROR. |
| GA-14 | ~~MEDIUM~~ **MITIGATED** | Process lifecycle managed | **Mitigated**: `test_smoke.py` handles clean process start/stop with SIGINT + timeout kill. `--timeout N` flag enables self-termination. Cooperative loop still uses significant CPU but `usleep(500)` limits it. |
| GA-28 | ~~MEDIUM~~ **FIXED** | vECU supports CI automation | **FIXED**: `--timeout N` argument added to foxbms-vecu. Exits cleanly after N seconds with timing summary. |
| GA-29 | MEDIUM | Plant model supports fault testing | Faults can only be introduced by editing `plant_model.py` source code. No runtime API (socket, CAN control message) for programmatic fault injection from test scripts. |

---

## 7. DevOps / CI Engineer

| Gap | Severity | What we claim | What's actually true |
|-----|----------|---------------|---------------------|
| GA-15 | ~~HIGH~~ **PARTIAL** | Reproducible build | **PARTIAL**: `apply_all.sh` consolidates all 13 patches in correct order with version check. Patches still fragile if foxBMS changes — tracked as remaining risk. |
| GA-16 | MEDIUM | HALCoGen headers available | Must copy headers from Windows build. No automated way to generate them on Linux. |

---

## 8. Embedded Software Engineer (Portability)

| Gap | Severity | What we claim | What's actually true |
|-----|----------|---------------|---------------------|
| GA-17 | HIGH (**ACCEPTED**) | Same code as production | 18 source files excluded (spi.c, i2c.c, dma.c, sbc/*, diag.c, fassert.c). **Accepted**: These files contain TMS570-specific hardware access that cannot compile on x86. Stubs in hal_stubs_posix.c match function signatures. Documented in COVERAGE.md. |
| GA-18 | MEDIUM | Queue operations work | AFE queue copies 16 bytes. Actual `CAN_CAN2AFE_CELL_VOLTAGES_QUEUE_s` is ~13 bytes with compiler-dependent padding. Size mismatch risk on different compilers. |

---

## 9. End User

| Gap | Severity | What we claim | What's actually true |
|-----|----------|---------------|---------------------|
| GA-19 | ~~MEDIUM~~ **FIXED** | Easy to run | **FIXED**: `setup.sh` does everything — submodule init, apply patches, build, vcan setup, smoke test. Single command: `./setup.sh` |
| GA-30 | ~~MEDIUM~~ **FIXED** | No troubleshooting guide | **FIXED**: `TROUBLESHOOTING.md` written — 10 failure modes with symptoms, diagnosis commands, and fixes. Includes key discoveries reference table. |

---

## 10. Project Manager

| Gap | Severity | What we claim | What's actually true |
|-----|----------|---------------|---------------------|
| GA-20 | ~~MEDIUM~~ **FIXED** | Complete documentation | **FIXED**: `COVERAGE.md` written — 51 features tracked across 7 categories (32 working, 12 suppressed, 7 not implemented). |
| GA-31 | ~~HIGH~~ **FIXED** | Documentation paths are correct | **FIXED**: STATUS.md Build & Run section updated to use relative paths from repo root. |
| GA-32 | ~~LOW~~ **FIXED** | Dead code removed | **FIXED**: `posix_inject_cell_data()` call removed from main loop. |
| GA-33 | ~~LOW~~ **FIXED** | Plant model docstring accurate | **FIXED**: Docstring updated to "66600 mV = 66.6V for 18S pack". |

---

## Summary

| Severity | Count | Key Gaps |
|----------|-------|----------|
| CRITICAL | ~~2~~ 0 | ~~DIAG disabled (GA-06), FAS_ASSERT disabled (GA-07)~~ **BOTH FIXED** |
| HIGH | ~~6~~ 0 fixed/accepted | GA-02, GA-08, GA-17 accepted (architectural). GA-01, GA-13, GA-31 fixed. GA-15 partial. |
| MEDIUM | ~~17~~ 12 remaining | ~~GA-05, GA-14, GA-19, GA-20, GA-28, GA-30~~ FIXED/MITIGATED. Remaining: GA-03, GA-04, GA-09, GA-11, GA-16, GA-18, GA-23, GA-24, GA-25, GA-26, GA-27, GA-29 |
| LOW | ~~8~~ 4 remaining | ~~GA-22, GA-32, GA-33~~ FIXED. Remaining: GA-10, GA-12, GA-21 |

**Total**: 33 gaps identified. **14 fixed/mitigated, 1 partial, 3 accepted** → 15 remaining (12 MEDIUM, 3 LOW).

> **Note**: 47 additional future-phase gaps (Docker, XCP, FMU/FMI, academic framing, performance benchmarks, etc.) are documented in [archive/GAP-ANALYSIS-MULTI-PERSPECTIVE.md](archive/GAP-ANALYSIS-MULTI-PERSPECTIVE.md). Those are planned work, not Phase 1 gaps.

### All Actions Completed

| # | Gap | Status |
|---|-----|--------|
| 1 | GA-06: Selective DIAG_Handler | **DONE** — 24 HW suppressed, 61 SW enabled |
| 2 | GA-07: FAS_ASSERT crash handler | **DONE** — log + exit(1) |
| 3 | GA-13: Smoke test script | **DONE** — `test_smoke.py` + `make test` |
| 4 | GA-01: Cycle time measurement | **DONE** — deadline violations logged |
| 5 | GA-15: Unified patch script | **DONE** — `apply_all.sh` |
| 6 | GA-05: Contactor delay | **DONE** — 10-cycle configurable delay |
| 7 | GA-28: Timeout flag | **DONE** — `--timeout N` |
| 8 | GA-30: Troubleshooting guide | **DONE** — `TROUBLESHOOTING.md` |
| 9 | GA-22: Graceful shutdown | **DONE** — contactor-open on exit |
| 10 | GA-19: Setup script | **DONE** — `setup.sh` |
| 11 | GA-20: Coverage matrix | **DONE** — `COVERAGE.md` |
| 12 | GA-31: Fix stale doc paths | **DONE** |
| 13 | GA-32: Remove dead code | **DONE** |
| 14 | GA-33: Fix stale docstring | **DONE** |
| 15 | GA-02: Single-threaded mode | **ACCEPTED** — architectural |
| 16 | GA-08: BMS bypasses | **ACCEPTED** — required for POSIX |
| 17 | GA-17: Excluded source files | **ACCEPTED** — TMS570-specific |

### Remaining (15 gaps — no CRITICAL or HIGH)

**MEDIUM** (12): GA-03 (DB ordering), GA-04 (static plant), GA-09 (SOC static), GA-11 (no TX arbitration), GA-16 (HALCoGen headers), GA-18 (queue size), GA-23 (interlock), GA-24 (watchdog), GA-25 (IVT redundancy), GA-26 (CAN TX period), GA-27 (E2E), GA-29 (fault injection API)

**LOW** (3): GA-10 (balancing), GA-12 (CAN node pointer), GA-21 (startup sync)

Most remaining MEDIUM gaps are either architectural limitations of the POSIX approach (GA-03, GA-11, GA-16, GA-18, GA-26, GA-27) or require Phase 2+ work to address (GA-04, GA-09, GA-23, GA-24, GA-25, GA-29).
