# foxBMS POSIX vECU — Feature Coverage Matrix

**Date**: 2026-03-21
**foxBMS version**: v1.10.0
**Scope**: Which foxBMS features work on the POSIX port vs production TMS570

---

## State Machines

| Feature | Production | POSIX | Notes |
|---------|-----------|-------|-------|
| SYS state machine | Full | RUNNING | All substates pass |
| BMS state machine | Full | NORMAL | Full transition: UNINIT→INIT→IDLE→STANDBY→PRECHARGE→NORMAL |
| CONT state machine | Full | Works | Contactor open/close with simulated delay (GA-05) |
| BAL state machine | Full | Runs | Logic executes but no voltage delta to balance (GA-10) |
| SOC estimation | Full | 50% static | Counting method runs but current=0A so no change (GA-09) |
| SOE estimation | Full | Runs | Algorithm100ms calls SOE but static values |
| SOF estimation | Full | Runs | Power limits calculated against ideal voltages |

## CAN Communication

| Feature | Production | POSIX | Notes |
|---------|-----------|-------|-------|
| CAN TX (15+ msg types) | HW mailbox | SocketCAN | 0x220-0x301 verified |
| CAN RX processing | HW ISR | Ring buffer | SocketCAN → posix_can_rx_inject() → callbacks |
| CAN message encoding | Big-endian | Same | foxBMS CAN_BIG_ENDIAN_TABLE verified with roundtrip |
| CAN TX arbitration | HW | None | No bus arbitration (GA-11) |
| CAN bus-off handling | HW | None | Errors silently ignored (GA-11) |
| CAN E2E protection | AUTOSAR E2E | Bypassed | No integrity checksums (GA-27) |
| CAN TX period enforcement | Timer ISR | No enforcement | Fires when loop reaches it (GA-26) |

## Diagnostics (GA-06: Selective)

| Feature | Production | POSIX | Notes |
|---------|-----------|-------|-------|
| Overvoltage detection | Full | **Enabled** | MSL/RSL/MOL all active |
| Undervoltage detection | Full | **Enabled** | MSL/RSL/MOL all active |
| Overcurrent detection | Full | **Enabled** | Cell/string/pack level |
| Overtemperature detection | Full | **Enabled** | Charge/discharge MSL/RSL/MOL |
| Undertemperature detection | Full | **Enabled** | Charge/discharge MSL/RSL/MOL |
| Plausibility checks | Full | **Enabled** | Voltage/temp spread, pack voltage |
| AFE SPI errors | Full | Suppressed | No AFE hardware |
| SBC errors | Full | Suppressed | No SBC hardware |
| I2C/RTC/FRAM errors | Full | Suppressed | No I2C bus |
| IMD insulation monitoring | Full | Suppressed | No IMD hardware |
| Interlock feedback | Full | Suppressed | No interlock circuit |
| Contactor feedback | Full | Suppressed | No real feedback pins |

## Hardware Abstraction

| Feature | Production | POSIX | Notes |
|---------|-----------|-------|-------|
| SPI (AFE, SBC, FRAM) | TMS570 SPI | Stubbed | No-op |
| I2C (PEX, RTC, temp) | TMS570 I2C | Stubbed | No-op |
| DMA | TMS570 DMA | Stubbed | No-op |
| GIO pins | TMS570 GPIO | Stubbed | No-op |
| ADC | TMS570 ADC | Stubbed | No-op |
| CRC | TMS570 HW CRC | Software CRC-64 | Functional but different algorithm |
| SPS (contactors) | TMS570 SPI | Simulated | Per-channel with delay (GA-05) |
| Register access | MMIO | RAM buffers | 60+ register bases → 4KB RAM each |

## Safety

| Feature | Production | POSIX | Notes |
|---------|-----------|-------|-------|
| FAS_ASSERT | Infinite loop / watchdog | Log + exit(1) | GA-07: crashes visibly |
| DIAG_Handler | Full evaluation | Selective | GA-06: 24 HW suppressed, 61 SW enabled |
| Watchdog (SBC) | HW watchdog | None | GA-24: no timeout → safe-state |
| Interlock | HW circuit | Always closed | GA-23 |
| Redundancy (IVT) | Dual IVT | Single | GA-25 |

## Plant Model

| Feature | Status | Notes |
|---------|--------|-------|
| Cell voltages (18 cells) | Static 3700mV | GA-04: no noise, no SOC-OCV curve |
| IVT current | Static 0A | GA-09: SOC never changes |
| IVT voltage (3 channels) | Static 66600mV | Matches string voltage |
| Cell temperatures | Static 25°C | GA-04: no thermal model |
| BMS state requests | STANDBY → NORMAL | Timed sequence |
| Contactor feedback | Not read | GA-53 (future): no closed-loop |

## Test Infrastructure

| Feature | Status | Notes |
|---------|--------|-------|
| Smoke test | `test_smoke.py` | GA-13: automated pass/fail |
| Setup script | `setup.sh` | GA-19: single-command setup |
| Patch management | `apply_all.sh` | GA-15: ordered with version check |
| Troubleshooting | `TROUBLESHOOTING.md` | GA-30: 10 failure modes |
| Timeout flag | `--timeout N` | GA-28: for CI automation |
| Cycle timing | Built-in | GA-01: deadline violation warnings |

---

## Summary

| Category | Total Features | Working on POSIX | Suppressed | Not Implemented |
|----------|---------------|-----------------|------------|-----------------|
| State machines | 7 | 7 (all run) | 0 | 0 |
| CAN communication | 7 | 3 | 0 | 4 (arbitration, bus-off, E2E, period) |
| Diagnostics | 12 categories | 6 enabled | 6 suppressed (HW) | 0 |
| Hardware abstraction | 8 | 2 (CRC, SPS) | 6 (stubbed) | 0 |
| Safety | 5 | 2 (assert, diag) | 0 | 3 (watchdog, interlock, redundancy) |
| Plant model | 6 | 6 (all static) | 0 | 0 |
| Test infrastructure | 6 | 6 | 0 | 0 |

**Overall**: 51 features tracked. 32 working, 12 suppressed (hardware-absent), 7 not implemented (architectural gaps).
