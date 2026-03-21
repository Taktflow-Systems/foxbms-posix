# foxBMS POSIX vECU — Consolidated Roadmap

**Last updated**: 2026-03-21
**Status**: Phase 1 COMPLETE, Phase 2 PARTIAL

---

## Phase 1: BMS NORMAL State — COMPLETE ✓

**Goal**: foxBMS compiles on x86-64 and reaches NORMAL state through legitimate data flow.

### Exit Criteria (all met)

| # | Criterion | Test | Result |
|---|-----------|------|--------|
| 1.1 | BMS reaches NORMAL state | `test_smoke.py` → state 7 on 0x220 | **PASS** (6.3s) |
| 1.2 | Full state transition verified | Smoke test logs all intermediate states | **PASS** (UNINIT→INIT→IDLE→STANDBY→PRECHARGE→NORMAL) |
| 1.3 | At least 15 CAN message types on bus | `candump vcan1` shows 0x220–0x301 | **PASS** (15+ types) |
| 1.4 | SOC reported non-zero | `test_smoke.py` → 0x235 byte 5 ≠ 0 | **PASS** |
| 1.5 | Connected strings > 0 at NORMAL | `test_smoke.py` → 0x220 upper nibble > 0 | **PASS** (1 string) |
| 1.6 | Contactors close during precharge | SPS trace in stderr log | **PASS** (3 channels) |
| 1.7 | No CRITICAL or HIGH gaps in gap analysis | GAP-ANALYSIS.md | **PASS** (0 CRITICAL, 0 HIGH) |
| 1.8 | Automated smoke test exists and passes | `make test` or `python3 test_smoke.py` | **PASS** |
| 1.9 | Build from clean clone works | `git clone --recursive` + `setup.sh` | **PASS** (HALCoGen headers in repo) |
| 1.10 | FAS_ASSERT crashes visibly | FAS_StoreAssertLocation → stderr + exit(1) | **PASS** |

### Completed Work

- 170+ foxBMS sources compiled with GCC 13 on x86-64
- 80+ HAL stubs, 60+ register bases redirected to RAM
- Cooperative main loop (replaces FreeRTOS scheduler)
- CAN TX/RX via SocketCAN, CAN RX filtering (no extended/error frames)
- Database passthrough, AFE queue routing, SPS contactor simulation (10ms delay)
- Selective DIAG_Handler (40 HW suppressed, 45 SW logged)
- `setup.sh`, `apply_all.sh`, `test_smoke.py`, `.gitignore`
- GAP-ANALYSIS.md (33 gaps, 26 resolved), COVERAGE.md, TROUBLESHOOTING.md
- 10-auditor review completed, Phase 1 fixes applied and verified

---

## Phase 2: Realistic Simulation — PARTIAL

**Goal**: Plant model produces dynamic, physics-based battery data. SOC changes over time.

### Exit Criteria

| # | Criterion | Test | Result |
|---|-----------|------|--------|
| 2.1 | SOC decreases under discharge | Run 30s, check 0x235 SOC < 50% | **PASS** (49.5% at 10s) |
| 2.2 | Cell voltage tracks SOC via OCV curve | candump 0x270, decode voltage, compare to OCV(SOC) | **PASS** (3800mV at 50%) |
| 2.3 | Pack voltage shows IR drop under load | candump 0x522 during NORMAL, V_pack < V_OCV × N | **PASS** (9V drop at 10A) |
| 2.4 | Closed-loop: discharge starts only at NORMAL | Plant log shows "foxBMS NORMAL detected" | **PASS** |
| 2.5 | Per-cell noise (±5mV) without precharge failure | Smoke test passes with noise enabled | **NOT DONE** — timing issue |
| 2.6 | Temperature mux covers all sensors (not just mux=0) | candump 0x280 shows mux 0–4 | **NOT DONE** |
| 2.7 | Charge current path works (SOC increases) | Plant sends negative current, SOC rises | **NOT DONE** |
| 2.8 | 20-second run shows monotonic SOC decrease | Plant log: SOC values strictly decreasing | **PASS** |

### Status: 5/8 criteria met

### Remaining Work
- Fix per-cell noise timing (noise causes precharge voltage mismatch via CAN frame ordering)
- Send temperature on all mux values (currently only mux=0)
- Add charge current mode (regenerative braking scenario)

---

## Phase 3: Fault Injection

**Goal**: foxBMS detects injected faults and responds correctly (opens contactors, enters ERROR state).

**Prerequisite**: Implement DIAG threshold counters (currently DIAG_Handler always returns OK — faults are logged but don't propagate to BMS state machine).

### Exit Criteria

| # | Criterion | Test | Result |
|---|-----------|------|--------|
| 3.1 | Overvoltage → contactors open | Plant sends 1 cell at 4500mV, check 0x220 state ≠ 7 within 5s | NOT DONE |
| 3.2 | Undervoltage → contactors open | Plant sends 1 cell at 2500mV | NOT DONE |
| 3.3 | Overtemperature → contactors open | Plant sends 1 sensor at 80°C (800 deci-°C) | NOT DONE |
| 3.4 | Overcurrent → contactors open | Plant sends IVT current 200A | NOT DONE |
| 3.5 | Cell imbalance → balancing activates | Plant sends cells at 3500/3700/3900mV, check BAL state | NOT DONE |
| 3.6 | Sensor loss → foxBMS detects | Plant stops sending 0x270 for 5s, check DIAG fault | NOT DONE |
| 3.7 | Recovery after fault clears | Remove fault → BMS returns to NORMAL | NOT DONE |
| 3.8 | Fault injection via runtime API | `test_fault.py` sends control message, plant injects fault | NOT DONE |
| 3.9 | All 6 fault types automated in CI | `make test-faults` runs all fault tests, returns pass/fail | NOT DONE |

### Status: 0/9 criteria met

### Blockers
- DIAG_Handler must implement per-ID threshold counters (not just log + return OK)
- DIAG_IsAnyFatalErrorSet must track actual fatal state
- Plant model needs fault injection API (runtime control, not source edits)

---

## Phase 4: Integration

**Goal**: foxBMS vECU runs in Docker and connects to real CAN bus for HIL testing.

### Exit Criteria

| # | Criterion | Test | Result |
|---|-----------|------|--------|
| 4.1 | `docker build` produces working image | `docker build -t foxbms-vecu .` succeeds | NOT DONE |
| 4.2 | `docker-compose up` runs vECU + plant | Smoke test passes inside container | NOT DONE |
| 4.3 | Real CAN bus works (`can0`) | `FOXBMS_CAN_IF=can0` → candump on physical bus shows 0x220 | NOT DONE |
| 4.4 | Runs alongside STM32 ECU on HIL bench | Both ECUs on same CAN bus, no errors | NOT DONE |
| 4.5 | CI pipeline green | GitHub Actions builds + runs smoke test | NOT DONE |
| 4.6 | XCP measurement working | CANape connects via XCP-on-TCP, reads SOC variable | NOT DONE |
| 4.7 | E2E checksums on CAN TX | foxBMS CAN messages pass E2E validation | NOT DONE |

### Status: 0/7 criteria met

---

## Overall Progress

| Phase | Criteria | Met | Status |
|-------|----------|-----|--------|
| Phase 1: BMS NORMAL | 10 | **10/10** | **COMPLETE** ✓ |
| Phase 2: Realistic Sim | 8 | **5/8** | PARTIAL (62%) |
| Phase 3: Fault Injection | 9 | **0/9** | NOT STARTED |
| Phase 4: Integration | 7 | **0/7** | NOT STARTED |
| **Total** | **34** | **15/34** | **44%** |
