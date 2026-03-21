# ASIL-D Fault Injection Test Matrix Summary

**Target**: foxBMS POSIX vECU (Battery Management System)
**Standard**: ISO 26262-5 Table 5 fault injection methods
**Date**: 2026-03-21
**Total Test Cases**: 2,005

## System Configuration

| Parameter | Value |
|-----------|-------|
| Cells per module | 18 (BS_NR_OF_CELL_BLOCKS_PER_MODULE) |
| Strings | 1 (BS_NR_OF_STRINGS) |
| Chemistry | NMC (patched thresholds) |
| DIAG threshold counting | Real (enabled) |
| Plant model rate | 1 ms |
| SIL probe range | CAN 0x7F0-0x7FF |
| Current sign convention | Positive = discharge |

### Thresholds

| Fault | MSL | RSL | MOL | Events | Delay |
|-------|-----|-----|-----|--------|-------|
| Overvoltage | 4250 mV | 4200 mV | 4150 mV | 50 | 200 ms |
| Undervoltage | 2500 mV | 2600 mV | 2700 mV | 50 | 200 ms |
| Overtemp discharge | 550 ddegC | 500 | 450 | 500 | 1000 ms |
| Overtemp charge | 450 ddegC | 400 | 350 | 500 | 1000 ms |
| Undertemp discharge | -200 ddegC | -150 | -100 | 500 | 1000 ms |
| Undertemp charge | -200 ddegC | -150 | -100 | 500 | 1000 ms |
| String overcurrent | 15000 mA | - | - | 10 | 100 ms |
| Cell overcurrent | 180000 mA | - | - | 10 | 100 ms |

## Test Count by Category

| Category | Code | Count | Percentage |
|----------|------|------:|----------:|
| Cell Voltage | VOLT | 743 | 37.1% |
| Cell Temperature | TEMP | 780 | 38.9% |
| Pack Current | CURR | 70 | 3.5% |
| Plausibility | PLAUS | 92 | 4.6% |
| Combinatorial | COMBO | 71 | 3.5% |
| State Machine | STATE | 107 | 5.3% |
| Recovery | RECOV | 68 | 3.4% |
| Timing | TIMING | 74 | 3.7% |
| **Total** | | **2,005** | **100%** |

## Signal Coverage

### Primary Signals (15 fault methods each x 3 severity tiers)

| Signal | CAN ID | Cells/Sensors Tested | Tests |
|--------|--------|---------------------|------:|
| Cell Voltage OV | 0x270 | Cell 0, 8, 17 individually + all 18 + pair (0,1) | 270+ |
| Cell Voltage UV | 0x270 | Cell 0, 8, 17 individually + all 18 + pair (0,1) | 270+ |
| Temp OT Discharge | 0x280 | Sensor 0, 2, 4 individually + all | 150+ |
| Temp OT Charge | 0x280 | Sensor 0, 2, 4 individually + all | 150+ |
| Temp UT Discharge | 0x280 | Sensor 0, 2, 4 individually + all | 150+ |
| Temp UT Charge | 0x280 | Sensor 0, 2, 4 individually + all | 150+ |
| Pack Current Discharge | 0x521 | String 0 | 15+ |
| Pack Current Charge | 0x521 | String 0 | 15+ |
| Pack Voltage V1 | 0x522 | IVT channel 1 | 30 |
| Pack Voltage V2 | 0x523 | IVT channel 2 | 30 |
| Pack Voltage V3 | 0x524 | IVT channel 3 | 30 |

### Per-Cell Coverage (all 18 cells)

Each of the 18 cells is tested individually with 4 key OV methods and 4 key UV methods = 144 tests ensuring no cell is missed.

### Boundary Value Analysis (BVA)

| Parameter | Boundary | Values Tested |
|-----------|----------|---------------|
| OV | MSL (4250 mV) | 4249, 4250, 4251 |
| OV | RSL (4200 mV) | 4199, 4200, 4201 |
| OV | MOL (4150 mV) | 4149, 4150, 4151 |
| UV | MSL (2500 mV) | 2499, 2500, 2501 |
| UV | RSL (2600 mV) | 2599, 2600, 2601 |
| UV | MOL (2700 mV) | 2699, 2700, 2701 |
| OT Dis | MSL (550 ddegC) | 549, 550, 551 |
| OT Chg | MSL (450 ddegC) | 449, 450, 451 |
| UT Dis | MSL (-200 ddegC) | -201, -200, -199 |
| UT Chg | MSL (-200 ddegC) | -201, -200, -199 |
| OC Dis | MSL (15000 mA) | 14999, 15000, 15001 |
| OC Chg | MSL (15000 mA) | -14999, -15000, -15001 |

## Fault Method Coverage

| # | Fault Method | ISO 26262-5 Ref | Tests |
|---|-------------|-----------------|------:|
| 1 | STUCK_AT_0 | Stuck-at fault | 114 |
| 2 | STUCK_AT_MAX | Stuck-at fault | 118 |
| 3 | STUCK_AT_LAST | Frozen value | 71 |
| 4 | OUT_OF_RANGE_HIGH | Range violation | 102 |
| 5 | OUT_OF_RANGE_LOW | Range violation | 101 |
| 6 | DRIFT_UP | Drift fault | 117 |
| 7 | DRIFT_DOWN | Drift fault | 113 |
| 8 | OFFSET_POS | Offset fault | 71 |
| 9 | OFFSET_NEG | Offset fault | 71 |
| 10 | NOISE | Signal noise | 71 |
| 11 | INVERTED | Polarity inversion | 71 |
| 12 | MISSING_TIMEOUT | Communication loss | 140 |
| 13 | DELAYED | Latency fault | 96 |
| 14 | CORRUPTED | Data corruption | 77 |
| 15 | RATE_OF_CHANGE | Rate violation | 83 |
| - | STEP_TO_VALUE | Boundary analysis | 285 |
| - | INJECT_THEN_CLEAR | Recovery test | 41 |
| - | SIMULTANEOUS | Combinatorial | 39 |
| - | SEQUENTIAL | Ordering test | 20 |
| - | TIMED_INJECTION | Timing verification | 40 |
| - | INVALID_TRANSITION | State machine | 64 |
| - | CAN_BUS_FAULT | Bus-level fault | 28 |
| - | INJECTED_MISMATCH | Plausibility | 44 |
| - | Other (oscillate, partial, spread, continuous) | Special | 28 |

## State Coverage

| BMS State | ID | Tests | Notes |
|-----------|---:|------:|-------|
| UNINITIALIZED | 0 | 13 | Boot-time fault injection |
| INITIALIZATION | 1 | 13 | Boot-time fault injection |
| INITIALIZED | 2 | 13 | Boot-time fault injection |
| IDLE | 3 | 58 | Multi-state OV/UV/OT coverage |
| SYS_CHECK | 4 | 7 | State transition validation |
| STANDBY | 5 | 74 | Pre-contactor close faults |
| PRECHARGE | 6 | 86 | Critical: fault during contactor closing |
| NORMAL | 7 | 1,666 | Primary operating state (bulk of tests) |
| ERROR | 10 | 75 | Recovery and re-entry tests |
| **Total** | | **2,005** | |

## Priority Distribution

| Priority | Description | Count | Percentage |
|----------|-------------|------:|----------:|
| P1 | Must have (safety-critical, ASIL-D required) | 905 | 45.1% |
| P2 | Should have (warning-level, robustness) | 1,100 | 54.9% |
| **Total** | | **2,005** | **100%** |

## Test Categories Explained

### VOLT (743 tests)
Cell voltage fault injection covering overvoltage and undervoltage conditions across all 18 cells, all 15 ISO 26262-5 fault methods, all 3 severity tiers (MSL/RSL/MOL), boundary value analysis, and multi-state coverage.

### TEMP (780 tests)
Temperature sensor fault injection covering overtemperature and undertemperature in both charge and discharge directions, across 3 representative sensors plus all-sensor simultaneous faults.

### CURR (70 tests)
Pack and cell current fault injection covering overcurrent in both discharge and charge directions, sign convention validation, and boundary value analysis.

### PLAUS (92 tests)
Plausibility checks including cell-vs-pack voltage consistency, sensor disagreement, voltage gradient analysis, SOC-voltage correlation, IVT timeout detection, and CAN bus-level faults (BUS_OFF, CRC, DLC mismatch, etc.).

### COMBO (71 tests)
Combinatorial faults testing simultaneous failure modes: OV+OC, OV+OT, UV+UT, triple faults, opposing faults on different cells, fault masking verification, and fault-during-precharge scenarios.

### STATE (107 tests)
State machine validation including all invalid state transitions (64 tests), invalid CAN state request values, rapid state toggling stress tests, state requests during active faults, and boot-sequence fault handling.

### RECOV (68 tests)
Recovery and persistence tests for all 8 fault types: fault clearing, return to NORMAL, fault persistence under continuous injection, latch behavior, threshold oscillation, counter reset verification, and recovery in different states.

### TIMING (74 tests)
FTTI (Fault Tolerant Time Interval) verification: reaction time measurement, exact threshold count verification, sub-threshold non-triggering, delay boundary testing, worst-case timing, and CAN message jitter tolerance.

## Coverage Matrix

| | Cell V | Cell T | Pack I | Pack V | State | Plaus |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Stuck-at-0 | Y | Y | Y | Y | - | - |
| Stuck-at-max | Y | Y | Y | Y | - | - |
| Stuck-at-last | Y | Y | Y | Y | - | - |
| Out-of-range high | Y | Y | Y | Y | - | - |
| Out-of-range low | Y | Y | Y | Y | - | - |
| Drift up | Y | Y | Y | Y | - | - |
| Drift down | Y | Y | Y | Y | - | - |
| Offset positive | Y | Y | Y | Y | - | - |
| Offset negative | Y | Y | Y | Y | - | - |
| Noise | Y | Y | Y | Y | - | - |
| Inverted | Y | Y | Y | Y | - | - |
| Missing/timeout | Y | Y | Y | Y | - | Y |
| Delayed | Y | Y | Y | Y | - | - |
| Corrupted | Y | Y | Y | Y | Y | - |
| Rate-of-change | Y | Y | Y | Y | Y | - |
| BVA (MSL/RSL/MOL) | Y | Y | Y | - | - | - |
| Multi-state | Y | Y | Y | - | Y | - |
| Combinatorial | Y | Y | Y | - | Y | Y |
| Recovery | Y | Y | Y | - | - | - |
| Timing/FTTI | Y | Y | Y | - | - | - |

## File Reference

- **Test Matrix CSV**: `fault-injection-test-matrix-asild.csv`
- **Generator Script**: Generated via Python cross-product approach
- **CSV Columns**: TEST_ID, CATEGORY, SIGNAL, FAULT_METHOD, INJECTION_VALUE, TARGET_CELL_OR_SENSOR, BMS_STATE, SEVERITY_TIER, DIAG_ID, THRESHOLD, EXPECTED_REACTION, PASS_CRITERIA, PRIORITY
