# SYS.4 System Integration Test Specification — HIL

| Document ID | Rev | Date | Classification |
|---|---|---|---|
| FOX-SIT-001 | 1.0 | 2026-03-23 | Confidential |

## Revision History

| Rev | Date | Author | Reviewer | Description |
|---|---|---|---|---|
| 1.0 | 2026-03-23 | An Dao | Phase 3 audit panel (10/10 approved) | Initial release — 42 HIL test cases |
| 2.0 | 2026-03-23 | An Dao | Pending review | Expanded: +38 tests (SYS.3 architecture, ASIL D OV/AFE depth, endurance, EMC) |
| 3.0 | 2026-03-23 | An Dao | Pending review | Full ASIL D: +33 tests (UV depth, SSR reaction chain, contactor safety, DIAG coverage, comm safety, system monitoring) |

## 1. Purpose

This document specifies the System Integration Test (SIT) cases for the foxBMS 2 BMS,
executed on a Hardware-in-the-Loop (HIL) bench with a custom Python test framework.
Test cases trace to both:
- **TSRs** (FOX-SAF-TSC-001) for safety function verification
- **SYS.3** (SYS.3-001) for architecture verification (interfaces, data flows, timing, state machines)

This satisfies ASPICE SYS.4 BP.1-BP.5 and ISO 26262 Part 4 §8. ASIL D paths have
extended coverage with MOL/RSL/MSL levels, boundary tests, state-specific tests, and
statistical timing measurements.

## 2. References

| ID | Title |
|---|---|
| FOX-SAF-TSC-001 | Technical Safety Concept (15 TSRs) |
| FOX-SAF-TSR-DA-001 | TSR Deep Analysis (Phase 2) |
| SYS.3-001 Rev 1.1 | System Architecture (HW interface §11-12) |
| FOX-SAF-FMEA-001 | Software FMEA (19 failure modes) |
| FOX-SAF-HARA-001 | Hazard Analysis and Risk Assessment |

## 3. Test Environment

### 3.1 HIL Bench Configuration

```
┌─────────────────────────────────────────────────────────┐
│                    HOST PC                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐  │
│  │  pytest   │  │ python-  │  │  cantools (DBC)      │  │
│  │ framework │  │ can      │  │  + report generator  │  │
│  └─────┬─────┘  └────┬─────┘  └──────────┬───────────┘  │
│        │              │                    │              │
│        └──────────────┼────────────────────┘              │
│                       │ USB                               │
└───────────────────────┼──────────────────────────────────┘
                        │
              ┌─────────┴──────────┐
              │  PCAN USB adapter  │
              │  (CAN1 + CAN2)     │
              └─────────┬──────────┘
                        │ CAN H/L
    ┌───────────────────┼───────────────────────────────┐
    │                   │                               │
    │  ┌────────────────┴────────────────┐              │
    │  │     foxBMS MASTER BOARD         │              │
    │  │     (TMS570LC4357)              │              │
    │  │                                 │              │
    │  │  J2021 ← CAN1 (IVT sim)        │              │
    │  │  J2024 ← CAN2 (vehicle sim)    │              │
    │  │  J2033 ← Interlock (relay)      │              │
    │  │  J200x ← SPS (contactor sim)   │              │
    │  │  J9000 → Interface board        │              │
    │  └──────────┬──────────────────────┘              │
    │             │ J9000 (SPI1 + GPIO)                 │
    │  ┌──────────┴──────────────────────┐              │
    │  │     INTERFACE BOARD (LTC6820)   │              │
    │  └──────────┬──────────────────────┘              │
    │             │ isoSPI (<1m cable)                   │
    │  ┌──────────┴──────────────────────┐              │
    │  │     SLAVE BOARD (LTC6813)       │              │
    │  │                                 │              │
    │  │  Cell connector ← Cell emulator │              │
    │  │  Temp connector ← Resistor bank │              │
    │  └─────────────────────────────────┘              │
    │                                                   │
    │  ┌─────────────────────────────────┐              │
    │  │  RELAY BOARD (USB-controlled)   │              │
    │  │  - Interlock relay (PP-10)      │              │
    │  │  - Daisy chain relay (PP-04)    │              │
    │  │  - Contactor feedback sim       │              │
    │  └─────────────────────────────────┘              │
    └───────────────────────────────────────────────────┘
```

### 3.2 Equipment List

| Item | Specification | Probe Points |
|------|--------------|-------------|
| Cell emulator | 19+ channels, 0-5V, ≤0.5 mV accuracy | PP-01 |
| NTC resistor bank | 8× switched precision resistors (1k-100kΩ) | PP-02 |
| PCAN USB Pro FD | Dual-channel CAN adapter | PP-06, PP-07 |
| USB relay board | 8+ relays (Numato/Devantech) | PP-04, PP-08, PP-10 |
| DC power supply | 12V / 5A (CLAMP30) | PP-13 |
| Digital multimeter | For CAN termination verification | PP-18, PP-19 |
| Logic analyzer (optional) | For SPI1 monitoring | PP-14 |
| JTAG debugger (optional) | For gcov coverage extraction | PP-15 |

### 3.3 Pre-Test Checklist

Before every test session:
- [ ] Kill stale processes: `killall -9 foxbms-vecu` (L-014)
- [ ] Verify CAN bus clean: no frames for 2s after power-on
- [ ] Verify CAN termination: 60Ω between CAN_H and CAN_L (2× 120Ω)
- [ ] Cell emulator: all 18 cells at 3600 mV (nominal)
- [ ] NTC bank: all 8 channels at 10 kΩ (25°C equivalent)
- [ ] Interlock relay: CLOSED
- [ ] All contactor feedback relays: match SPS commanded state
- [ ] IVT simulation: sending 0x521-0x527 at 10ms, `invalidFlag=1` (L-009)
- [ ] IVT current: 0 mA until contactors close (L-019)
- [ ] Cell voltage mux groups: cycling 0-4 for all 18 cells (L-010)
- [ ] IVT V3 (0x524): present every cycle (L-011)

---

## 4. Test Cases

### Category 1: Normal Operation Verification

---

#### HIL-SIT-001: BMS Startup Sequence

| Field | Value |
|-------|-------|
| **TSR** | — (functional, not safety) |
| **Objective** | Verify BMS transitions from UNINITIALIZED through IDLE to STANDBY |
| **Preconditions** | Power OFF, all emulators at nominal |
| **Stimulus** | Apply 12V to J2009 (CLAMP15 + CLAMP30) |
| **Observation** | CAN 0x220 (BmsState): SYS state transitions, BMS state = STANDBY |
| **Pass criteria** | BMS reaches STANDBY within 5s of power-on; CAN messages appear on bus |
| **Runs** | 3 |
| **Gotchas** | L-015: Read BMS state from 0x220 carefully (flicker possible) |

---

#### HIL-SIT-002: Precharge and Transition to NORMAL

| Field | Value |
|-------|-------|
| **TSR** | TSR-08 (contactor control) |
| **HARA chain** | HZ-08 → SG-08 → TSR-08 → SSR-050/051 |
| **Objective** | Verify precharge sequence: STANDBY → PRECHARGE → NORMAL |
| **Preconditions** | BMS in STANDBY, all cells 3600 mV, temp 25°C, IVT 0 mA |
| **Stimulus** | Send CAN 0x210 state request = NORMAL |
| **Observation** | 1. String- contactor closes (SPS CH1, PP-09) 2. Precharge contactor closes (SPS CH2) 3. Voltage ramp on DC-link (IVT V1 0x522) 4. String+ contactor closes (SPS CH0) 5. Precharge contactor opens 6. CAN 0x220 BMS state = NORMAL |
| **Pass criteria** | Precharge completes within 2s; all 3 contactors actuate in correct sequence; BMS state = NORMAL |
| **Runs** | 5 |
| **Gotchas** | L-019: Start IVT current only after contactor feedback confirms closed |

---

#### HIL-SIT-003: CAN Message Content Verification

| Field | Value |
|-------|-------|
| **TSR** | TSR-11 |
| **Objective** | Verify all TX CAN messages contain correct data in NORMAL state |
| **Preconditions** | BMS in NORMAL, nominal conditions |
| **Stimulus** | None (steady state) |
| **Observation** | Decode all TX messages (0x220-0x260, 0x301) against DBC |
| **Pass criteria** | BmsState=NORMAL, SOC within expected range, min/max cell voltage matches emulator setpoints (±5mV), temperatures match NTC resistance (±2°C) |
| **Runs** | 3 |

---

#### HIL-SIT-004: Graceful Shutdown (NORMAL → STANDBY)

| Field | Value |
|-------|-------|
| **TSR** | TSR-08, SSR-022/023 |
| **Objective** | Verify controlled shutdown via CAN state request |
| **Preconditions** | BMS in NORMAL, no faults |
| **Stimulus** | Send CAN 0x210 state request = STANDBY |
| **Observation** | 1. Contactors open in sequence 2. BMS state → STANDBY 3. IVT current → 0 mA |
| **Pass criteria** | All contactors OPEN; BMS state = STANDBY; no ERROR transition |
| **Runs** | 3 |

---

#### HIL-SIT-005: CAN Cell Voltage Multiplexing (18 cells)

| Field | Value |
|-------|-------|
| **TSR** | TSR-01/02 |
| **Objective** | Verify all 18 individual cell voltages are reported correctly |
| **Preconditions** | BMS in NORMAL, set each cell to a unique voltage (3500 + cell_id × 10 mV) |
| **Stimulus** | None (verify data) |
| **Observation** | CAN 0x240-0x245: decode all 18 cell voltages |
| **Pass criteria** | Each reported voltage matches emulator setpoint ±3 mV (LTC6813 TME at 25°C) |
| **Runs** | 3 |
| **Gotchas** | L-010: Need all 5 mux groups cycling for 18 cells |

---

### Category 2: Safety Function Verification (per TSR)

---

#### HIL-SIT-010: TSR-01 Cell Overvoltage — All Cells (ASIL D)

| Field | Value |
|-------|-------|
| **TSR** | TSR-01 (ASIL D) |
| **HARA chain** | HZ-01 → SG-01 → FSR-01 → TSR-01 → SSR-001 → SSR-020/021 |
| **Objective** | Verify BMS detects overvoltage and opens contactors within FTTI |
| **Preconditions** | BMS in NORMAL, all cells 3600 mV, 5s stable |
| **Stimulus** | Set ALL 18 cells to 2850 mV simultaneously (above 2800 mV MSL) |
| **Observation** | 1. CAN 0x220: BMS state → ERROR 2. PP-09: all SPS outputs de-energize 3. PP-08: contactor feedback → OPEN 4. Timing: t_start = stimulus, t_end = contactor open |
| **Pass criteria** | BMS state = ERROR; all contactors OPEN; reaction time ≤ 750 ms |
| **Statistical** | 10 runs; report mean/min/max/σ; FAIL if ANY run > 750 ms |
| **Gotchas** | L-018/L-027: MUST set ALL 18 cells above threshold. Single-cell OV is rejected by plausibility (GAP-03, spread > 300 mV) |
| **Probe points** | PP-01 (emulator), PP-06 (CAN), PP-09 (SPS), PP-08 (feedback) |
| **Cross-check** | hw-datasheet-oracle: VERIFIED; data-flow-checker: VERIFIED; lessons: WARNING L-018 |

---

#### HIL-SIT-011: TSR-01 Cell Overvoltage — Threshold Boundary (ASIL D)

| Field | Value |
|-------|-------|
| **TSR** | TSR-01 |
| **Objective** | Verify OV detection exactly at threshold boundary |
| **Preconditions** | BMS in NORMAL, all cells 2790 mV (10 mV below threshold), 5s stable |
| **Stimulus** | Ramp all 18 cells from 2790 → 2810 mV at 1 mV/step, 100 ms/step |
| **Observation** | Record exact voltage at which ERROR triggers |
| **Pass criteria** | ERROR triggers between 2798 and 2803 mV (threshold ± ADC TME of ±2.2 mV) |
| **Runs** | 5 |

---

#### HIL-SIT-012: TSR-02 Cell Undervoltage (ASIL C)

| Field | Value |
|-------|-------|
| **TSR** | TSR-02 |
| **HARA chain** | HZ-02 → SG-02 → FSR-02 → TSR-02 → SSR-002 |
| **Objective** | Verify BMS detects undervoltage and opens contactors within FTTI |
| **Preconditions** | BMS in NORMAL, all cells 2000 mV, 5s stable |
| **Stimulus** | Set ALL 18 cells to 1450 mV (below 1500 mV MSL) |
| **Pass criteria** | BMS state = ERROR; all contactors OPEN; reaction time ≤ 750 ms |
| **Statistical** | 10 runs |

---

#### HIL-SIT-013: TSR-03 Deep Discharge (QM)

| Field | Value |
|-------|-------|
| **TSR** | TSR-03 |
| **Objective** | Verify deep discharge single-event detection (threshold=1) |
| **Preconditions** | BMS in NORMAL, all cells 1600 mV |
| **Stimulus** | Set ALL 18 cells to 1000 mV |
| **Pass criteria** | ERROR within 160 ms; reaction much faster than TSR-01/02 (threshold=1 vs 50) |
| **Runs** | 5 |

---

#### HIL-SIT-014: TSR-04 Overcurrent Discharge (ASIL B)

| Field | Value |
|-------|-------|
| **TSR** | TSR-04 |
| **HARA chain** | HZ-04 → SG-04 → FSR-04 → TSR-04 → SSR-003 |
| **Objective** | Verify BMS detects discharge overcurrent within FTTI |
| **Preconditions** | BMS in NORMAL, IVT reporting 500 mA discharge |
| **Stimulus** | IVT 0x521: inject 3000 mA discharge (above BS_MAX_DISCHARGE_CURRENT_MSL = 2400 mA) |
| **Pass criteria** | ERROR; contactors OPEN; reaction ≤ 250 ms |
| **Statistical** | 10 runs |
| **Gotchas** | L-019: Current must start after contactors confirmed closed |

---

#### HIL-SIT-015: TSR-05 Overcurrent Charge (ASIL C)

| Field | Value |
|-------|-------|
| **TSR** | TSR-05 |
| **Objective** | Verify BMS detects charge overcurrent within FTTI |
| **Preconditions** | BMS in NORMAL, IVT reporting 500 mA charge |
| **Stimulus** | IVT 0x521: inject 3000 mA charge |
| **Pass criteria** | ERROR; contactors OPEN; reaction ≤ 250 ms |
| **Statistical** | 10 runs |

---

#### HIL-SIT-016: TSR-06 Overtemperature Discharge (ASIL C)

| Field | Value |
|-------|-------|
| **TSR** | TSR-06 |
| **HARA chain** | HZ-06 → SG-06 → FSR-06 → TSR-06 → SSR-005 |
| **Objective** | Verify BMS detects overtemperature during discharge |
| **Preconditions** | BMS in NORMAL, IVT 500 mA discharge, all NTCs at 25°C |
| **Stimulus** | Switch all 8 NTC resistors to value equivalent to 60°C (above 55°C discharge MSL) |
| **Pass criteria** | ERROR; contactors OPEN; reaction ≤ 6050 ms |
| **Statistical** | 10 runs |
| **Gotchas** | L-017: MUST have current flowing (IVT > 0) simultaneously with elevated temperature |

---

#### HIL-SIT-017: TSR-07 Undertemperature Charge (ASIL B)

| Field | Value |
|-------|-------|
| **TSR** | TSR-07 |
| **Objective** | Verify BMS detects undertemperature during charge |
| **Preconditions** | BMS in NORMAL, IVT 500 mA charge, all NTCs at 0°C |
| **Stimulus** | Switch all 8 NTC resistors to value equivalent to -25°C (below -20°C MSL) |
| **Pass criteria** | ERROR; contactors OPEN; reaction ≤ 6050 ms |
| **Statistical** | 10 runs |

---

#### HIL-SIT-018: TSR-08 Contactor Feedback Mismatch — Welding (ASIL B)

| Field | Value |
|-------|-------|
| **TSR** | TSR-08 |
| **HARA chain** | HZ-08 → SG-08 → FSR-08 → TSR-08 → SSR-050 |
| **Objective** | Verify BMS detects contactor welding (commanded open, feedback closed) |
| **Preconditions** | BMS in ERROR (contactors commanded OPEN) |
| **Stimulus** | Force PP-08 relay: simulate string+ feedback = CLOSED while SPS commands OPEN |
| **Pass criteria** | DIAG_ID_STRING_PLUS_CONTACTOR_FEEDBACK triggers; BMS remains in ERROR |
| **Runs** | 5 |

---

#### HIL-SIT-019: TSR-09 IVT Communication Loss (ASIL B)

| Field | Value |
|-------|-------|
| **TSR** | TSR-09 |
| **HARA chain** | HZ-09 → SG-09 → FSR-09 → TSR-09 → SSR-041 |
| **Objective** | Verify BMS detects IVT communication loss |
| **Preconditions** | BMS in NORMAL, IVT transmitting normally |
| **Stimulus** | Stop transmitting all IVT CAN messages (0x521-0x527) |
| **Pass criteria** | ERROR; contactors OPEN; reaction ≤ 1250 ms |
| **Statistical** | 10 runs |

---

#### HIL-SIT-020: TSR-10 AFE Communication Loss (ASIL D support)

| Field | Value |
|-------|-------|
| **TSR** | TSR-10 |
| **Objective** | Verify BMS detects AFE SPI/isoSPI failure |
| **Preconditions** | BMS in NORMAL |
| **Stimulus** | Open daisy chain relay (PP-04) — breaks isoSPI link |
| **Pass criteria** | ERROR; contactors OPEN; reaction ≤ 200 ms |
| **Statistical** | 10 runs |

---

#### HIL-SIT-021: TSR-11 CAN Communication Loss

| Field | Value |
|-------|-------|
| **TSR** | TSR-11 |
| **Objective** | Verify BMS detects vehicle CAN communication loss |
| **Preconditions** | BMS in NORMAL, vehicle CAN active |
| **Stimulus** | Stop transmitting all vehicle CAN messages on CAN2 |
| **Pass criteria** | ERROR; contactors OPEN; reaction ≤ 1250 ms |
| **Runs** | 5 |

---

#### HIL-SIT-022: TSR-12 System Monitoring (HIL limitation)

| Field | Value |
|-------|-------|
| **TSR** | TSR-12 |
| **Objective** | Verify DIAG_ID_SYSTEM_MONITORING and FLASHCHECKSUM are configured |
| **Preconditions** | BMS in STANDBY |
| **Stimulus** | None — read DIAG configuration via CAN debug interface or JTAG |
| **Pass criteria** | DIAG entries exist with threshold=1, delay=0, severity=FATAL |
| **Runs** | 1 |
| **Note** | Cannot inject lockstep/ECC/flash faults externally. SIL covers software path. |

---

#### HIL-SIT-023: TSR-13 Interlock Loop Break

| Field | Value |
|-------|-------|
| **TSR** | TSR-13 |
| **HARA chain** | HZ-10 → SG-10 → TSR-13 |
| **Objective** | Verify BMS detects interlock loop break |
| **Preconditions** | BMS in NORMAL |
| **Stimulus** | Open interlock relay (PP-10) |
| **Pass criteria** | ERROR; contactors OPEN; reaction ≤ 250 ms |
| **Statistical** | 10 runs |

---

#### HIL-SIT-024: TSR-15 Current on Open String

| Field | Value |
|-------|-------|
| **TSR** | TSR-15 |
| **HARA chain** | HZ-08 → SG-08 → TSR-15 → SSR-010 |
| **Objective** | Verify BMS detects current flowing when contactors are open |
| **Preconditions** | BMS in STANDBY (all contactors OPEN) |
| **Stimulus** | IVT 0x521: inject 500 mA current (should be 0 with contactors open) |
| **Pass criteria** | ERROR; DIAG_ID_CURRENT_ON_OPEN_STRING triggers; reaction ≤ 250 ms |
| **Statistical** | 10 runs |

---

### Category 3: Fault Injection — Electrical (per FMEA)

---

#### HIL-SIT-030: FM-01 Single-Cell OV Undetected (ADC Offset)

| Field | Value |
|-------|-------|
| **FMEA** | FM-01 |
| **Objective** | Verify IVT pack plausibility catches AFE offset error |
| **Preconditions** | BMS in NORMAL, all cells 3600 mV, IVT V1 reports 64800 mV (18 × 3600) |
| **Stimulus** | Set 1 cell emulator to 2900 mV (OV) but keep IVT V1 at 64800 mV (simulating AFE reading lower than actual) |
| **Pass criteria** | DIAG_ID_PLAUSIBILITY_PACK_VOLTAGE triggers (AFE sum ≠ IVT) |
| **Runs** | 3 |
| **Note** | Tests redundancy path, not primary OV detection |

---

#### HIL-SIT-031: FM-02 OV Detected + Contactor Welded

| Field | Value |
|-------|-------|
| **FMEA** | FM-02 |
| **Objective** | Verify welding detection after OV-triggered contactor open |
| **Preconditions** | BMS in NORMAL |
| **Stimulus** | 1. Set all cells to 2850 mV → BMS enters ERROR 2. Force string+ feedback relay = CLOSED (simulate welding) |
| **Pass criteria** | DIAG_ID_STRING_PLUS_CONTACTOR_FEEDBACK triggers within 350 ms |
| **Runs** | 5 |

---

#### HIL-SIT-032: FM-03 UV False Positive (Noise Rejection)

| Field | Value |
|-------|-------|
| **FMEA** | FM-03 |
| **Objective** | Verify 50-event threshold filters transient UV |
| **Preconditions** | BMS in NORMAL, all cells 1600 mV (above UV threshold) |
| **Stimulus** | Briefly dip all cells to 1400 mV for 200 ms, then back to 1600 mV |
| **Pass criteria** | BMS does NOT enter ERROR (threshold counter resets before reaching 50) |
| **Runs** | 5 |

---

#### HIL-SIT-033: FM-04 NTC Open Circuit

| Field | Value |
|-------|-------|
| **FMEA** | FM-04 |
| **Objective** | Verify AFE MUX detects NTC open circuit |
| **Preconditions** | BMS in NORMAL |
| **Stimulus** | Disconnect 1 NTC channel (open circuit on PP-02 channel 0) |
| **Pass criteria** | DIAG_ID_AFE_MUX or range-check diagnostic triggers; BMS → ERROR |
| **Runs** | 3 |

---

#### HIL-SIT-034: FM-07 IVT Current Sensor Offset

| Field | Value |
|-------|-------|
| **FMEA** | FM-07 |
| **Objective** | Verify current-on-open-string detects IVT offset |
| **Preconditions** | BMS in STANDBY (contactors OPEN) |
| **Stimulus** | IVT 0x521: inject 200 mA offset (should be 0 mA with contactors open) |
| **Pass criteria** | DIAG_ID_CURRENT_ON_OPEN_STRING triggers |
| **Runs** | 3 |

---

#### HIL-SIT-035: FM-12 String+ Contactor Welding

| Field | Value |
|-------|-------|
| **FMEA** | FM-12 |
| **Objective** | Verify welding detection on string+ contactor |
| **Preconditions** | BMS transitions to ERROR (any fault), contactors commanded OPEN |
| **Stimulus** | Force string+ feedback relay = CLOSED (PP-08 CH0) |
| **Pass criteria** | DIAG_ID_STRING_PLUS_CONTACTOR_FEEDBACK triggers within 350 ms |
| **Runs** | 5 |

---

#### HIL-SIT-036: FM-13 String- Stuck Open

| Field | Value |
|-------|-------|
| **FMEA** | FM-13 |
| **Objective** | Verify stuck-open detection on string- contactor |
| **Preconditions** | BMS in STANDBY, requesting NORMAL |
| **Stimulus** | Force string- feedback relay = OPEN (PP-08 CH1) while BMS commands CLOSE |
| **Pass criteria** | DIAG_ID_STRING_MINUS_CONTACTOR_FEEDBACK triggers; precharge aborts |
| **Runs** | 3 |

---

#### HIL-SIT-037: FM-18 Interlock False Open (Noise)

| Field | Value |
|-------|-------|
| **FMEA** | FM-18 (highest RPN = 75) |
| **Objective** | Verify 10-event threshold filters interlock noise |
| **Preconditions** | BMS in NORMAL |
| **Stimulus** | Toggle interlock relay rapidly: 5 cycles of 20ms open / 80ms closed |
| **Pass criteria** | BMS does NOT enter ERROR (threshold counter resets between bursts) |
| **Runs** | 5 |

---

### Category 4: Fault Injection — Communication

---

#### HIL-SIT-040: IVT Voltage Channel V3 Missing

| Field | Value |
|-------|-------|
| **TSR** | TSR-09 |
| **Objective** | Verify V3 timeout detection (L-011 gotcha) |
| **Preconditions** | BMS in NORMAL, IVT sending all messages |
| **Stimulus** | Stop sending 0x524 (IVT V3) only; keep 0x521-0x523 active |
| **Pass criteria** | DIAG_ID_CURRENT_SENSOR_V3_MEASUREMENT_TIMEOUT triggers; ERROR within 160 ms |
| **Runs** | 5 |

---

#### HIL-SIT-041: IVT All Messages Lost

| Field | Value |
|-------|-------|
| **TSR** | TSR-09 |
| **Objective** | Verify complete IVT communication loss detection |
| **Preconditions** | BMS in NORMAL |
| **Stimulus** | Stop all IVT messages (0x521-0x527) |
| **Pass criteria** | ERROR; DIAG_ID_CURRENT_SENSOR_RESPONDING triggers; reaction ≤ 1250 ms |
| **Runs** | 5 |

---

#### HIL-SIT-042: isoSPI Chain Break (AFE Loss)

| Field | Value |
|-------|-------|
| **TSR** | TSR-10 |
| **Objective** | Verify isoSPI break detection via daisy chain relay |
| **Preconditions** | BMS in NORMAL |
| **Stimulus** | Open relay on daisy chain input (PP-04) |
| **Pass criteria** | DIAG_ID_AFE_SPI triggers; ERROR within 200 ms |
| **Runs** | 5 |

---

#### HIL-SIT-043: CAN Bus-Off Recovery

| Field | Value |
|-------|-------|
| **TSR** | TSR-11 |
| **Objective** | Verify BMS handles CAN bus-off condition |
| **Preconditions** | BMS in NORMAL |
| **Stimulus** | Inject dominant CAN frame to force bus-off on CAN1 |
| **Pass criteria** | BMS detects CAN error; CAN timing DIAG triggers |
| **Runs** | 3 |

---

#### HIL-SIT-044: Invalid IVT Data (invalidFlag=0)

| Field | Value |
|-------|-------|
| **Gotcha** | L-009 |
| **Objective** | Verify BMS rejects IVT data with invalidFlag=0 |
| **Preconditions** | BMS in NORMAL, IVT sending normally |
| **Stimulus** | Set invalidFlag=0 in all IVT messages |
| **Pass criteria** | BMS rejects data; current sensor timeout DIAG triggers; ERROR |
| **Runs** | 3 |

---

### Category 5: Multi-Fault and Priority

---

#### HIL-SIT-050: Simultaneous OV + Overcurrent

| Field | Value |
|-------|-------|
| **TSR** | TSR-01 + TSR-04 |
| **Objective** | Verify BMS handles two simultaneous faults |
| **Preconditions** | BMS in NORMAL |
| **Stimulus** | Simultaneously: all cells → 2850 mV AND IVT current → 3000 mA discharge |
| **Pass criteria** | ERROR; contactors OPEN; fastest FTTI wins (overcurrent 250 ms < OV 750 ms) |
| **Runs** | 5 |

---

#### HIL-SIT-051: OV + isoSPI Break (Dual Path Failure)

| Field | Value |
|-------|-------|
| **TSR** | TSR-01 + TSR-10 |
| **Objective** | Verify safe state on simultaneous sensor fault + measurement fault |
| **Preconditions** | BMS in NORMAL |
| **Stimulus** | 1. Set cells to 2850 mV 2. Immediately open daisy chain relay (PP-04) |
| **Pass criteria** | ERROR via AFE comms loss (200 ms) even though OV data cannot reach BMS |
| **Runs** | 3 |
| **Note** | Tests defense-in-depth: even when OV detection is disabled by comms loss, the comms loss itself triggers safe state |

---

#### HIL-SIT-052: Interlock Break During Precharge

| Field | Value |
|-------|-------|
| **TSR** | TSR-13 + TSR-08 |
| **Objective** | Verify interlock break aborts precharge sequence |
| **Preconditions** | BMS in STANDBY, requesting NORMAL |
| **Stimulus** | Open interlock relay (PP-10) during precharge (before NORMAL reached) |
| **Pass criteria** | Precharge aborts; all contactors OPEN; BMS → ERROR |
| **Runs** | 3 |

---

### Category 6: Recovery and Restart

---

#### HIL-SIT-060: Error Recovery — Fault Clear + STANDBY Request

| Field | Value |
|-------|-------|
| **TSR** | SSR-022, SSR-023, SSR-024 |
| **Objective** | Verify dual-condition ERROR exit (fault clear AND STANDBY request) |
| **Preconditions** | BMS in ERROR (triggered by OV test) |
| **Stimulus** | 1. Restore all cells to 3600 mV (clear fault condition) 2. Send CAN 0x210 state request = STANDBY |
| **Pass criteria** | BMS exits ERROR → STANDBY; BOTH conditions required (AND logic) |
| **Runs** | 3 |

---

#### HIL-SIT-061: Error Recovery — Fault Clear Only (No Request)

| Field | Value |
|-------|-------|
| **TSR** | SSR-024 |
| **Objective** | Verify BMS does NOT exit ERROR on fault clear alone |
| **Preconditions** | BMS in ERROR (triggered by OV test) |
| **Stimulus** | Restore all cells to 3600 mV (clear fault) but do NOT send STANDBY request |
| **Pass criteria** | BMS REMAINS in ERROR state indefinitely |
| **Runs** | 3 |

---

#### HIL-SIT-062: Error Recovery — Request Only (Fault Not Cleared)

| Field | Value |
|-------|-------|
| **TSR** | SSR-022 |
| **Objective** | Verify BMS does NOT exit ERROR on request alone |
| **Preconditions** | BMS in ERROR, cells still at 2850 mV (fault persists) |
| **Stimulus** | Send CAN 0x210 state request = STANDBY (fault NOT cleared) |
| **Pass criteria** | BMS REMAINS in ERROR state |
| **Runs** | 3 |

---

### Category 7: Known Gap Verification (Negative Tests)

---

#### HIL-SIT-070: GAP-03 Verification — Plausibility Suppresses Single-Cell OV

| Field | Value |
|-------|-------|
| **GAP** | GAP-03 (ASIL D residual risk) |
| **Objective** | PROVE that plausibility spread check suppresses single-cell OV — this is a NEGATIVE test that verifies the known limitation exists |
| **Preconditions** | BMS in NORMAL, all cells 2500 mV, 5s stable |
| **Stimulus** | Set ONLY cell 0 to 2850 mV (spread = 350 mV > 300 mV threshold). Keep other 17 cells at 2500 mV. |
| **Expected** | BMS does NOT enter ERROR (plausibility rejects cell 0 as outlier) |
| **Pass criteria** | After 10s: BMS remains in NORMAL. DIAG_ID_PLAUSIBILITY_CELL_VOLTAGE_SPREAD fires (WARNING level). No contactor action. |
| **Counter-test** | Then set ALL 18 cells to 2850 mV → BMS MUST enter ERROR within 750 ms |
| **Runs** | 5 |
| **Significance** | This test documents the GAP-03 residual risk as verifiable evidence. The test PASSES by proving the gap exists. |

---

#### HIL-SIT-071: GAP-02 Verification — Precharge No Feedback

| Field | Value |
|-------|-------|
| **GAP** | GAP-02 |
| **Objective** | Verify precharge contactor has no feedback monitoring |
| **Preconditions** | BMS in NORMAL |
| **Stimulus** | Force precharge feedback relay to mismatch SPS command |
| **Pass criteria** | No DIAG triggers for precharge contactor (CONT_HAS_NO_FEEDBACK confirmed) |
| **Runs** | 3 |

---

#### HIL-SIT-072: GAP-06 Verification — Current on Open String During NORMAL

| Field | Value |
|-------|-------|
| **GAP** | GAP-06 |
| **Objective** | Verify TSR-15 does NOT trigger during NORMAL state |
| **Preconditions** | BMS in NORMAL, IVT reporting 500 mA |
| **Stimulus** | None — verify current-on-open-string check is inactive during NORMAL |
| **Pass criteria** | No DIAG_ID_CURRENT_ON_OPEN_STRING triggered (expected: check only runs during STANDBY/OPEN) |
| **Runs** | 3 |

### Category 8: SYS.3 Architecture Verification

These tests verify that the system architecture works as documented in SYS.3-001.
They test interfaces, data flows, timing, and state machines — not safety functions.

---

#### HIL-SIT-080: CAN1 TX Message Verification (All 12 Messages)

| Field | Value |
|-------|-------|
| **SYS.3 Ref** | §9.1 Transmit Messages |
| **Objective** | Verify all 12 TX CAN messages appear on CAN1 with correct IDs and cycle times |
| **Preconditions** | BMS in NORMAL, nominal conditions, 30s capture |
| **Stimulus** | None (observe steady-state) |
| **Pass criteria** | All 12 IDs (0x220, 0x221, 0x231-0x236, 0x240-0x245, 0x250, 0x260, 0x301) present; cycle time 100ms ±10ms (1000ms for 0x301) |
| **Runs** | 3 |

---

#### HIL-SIT-081: CAN1 RX State Request Processing

| Field | Value |
|-------|-------|
| **SYS.3 Ref** | §9.2 Receive Messages |
| **Objective** | Verify CAN 0x210 state request is received and processed |
| **Preconditions** | BMS in STANDBY |
| **Stimulus** | Send 0x210 with NORMAL request, then STANDBY request |
| **Pass criteria** | BMS transitions STANDBY → PRECHARGE → NORMAL → STANDBY in response |
| **Runs** | 3 |

---

#### HIL-SIT-082: CAN2 Isolation Verification

| Field | Value |
|-------|-------|
| **SYS.3 Ref** | §11.7 Galvanic Isolation |
| **Objective** | Verify CAN2 (J2024) is galvanically isolated from CAN1 (J2021) |
| **Preconditions** | BMS powered off |
| **Stimulus** | Measure resistance between CAN1 H/L and CAN2 H/L |
| **Pass criteria** | Isolation resistance > 1 MΩ (transformer-coupled TJA1042) |
| **Runs** | 1 |

---

#### HIL-SIT-083: CAN Bus Termination Verification

| Field | Value |
|-------|-------|
| **SYS.3 Ref** | §11.6 PP-18/PP-19 |
| **Objective** | Verify 120Ω termination on CAN1 and CAN2 |
| **Preconditions** | BMS powered off |
| **Stimulus** | Measure resistance between CAN_H and CAN_L on each connector |
| **Pass criteria** | CAN1: 120Ω ±5%; CAN2: 120Ω ±5% |
| **Runs** | 1 |

---

#### HIL-SIT-084: Data Flow — Cell Voltage End-to-End

| Field | Value |
|-------|-------|
| **SYS.3 Ref** | §8.1 Measurement Path, §11.5.1 |
| **Objective** | Verify cell voltage flows from emulator → LTC6813 → isoSPI → SPI1 → database → CAN TX |
| **Preconditions** | BMS in NORMAL |
| **Stimulus** | Set cell 5 to 3700 mV (unique value), wait 2s |
| **Pass criteria** | CAN 0x240-0x245: cell 5 voltage = 3700 mV ±3 mV |
| **Runs** | 3 |

---

#### HIL-SIT-085: Data Flow — Temperature End-to-End

| Field | Value |
|-------|-------|
| **SYS.3 Ref** | §8.1 Measurement Path |
| **Objective** | Verify temperature flows from NTC → LTC6813 MUX → CAN TX |
| **Preconditions** | BMS in NORMAL |
| **Stimulus** | Set NTC 0 to 15 kΩ (≈20°C), NTC 3 to 5 kΩ (≈40°C) |
| **Pass criteria** | CAN 0x260: sensor 0 ≈ 20°C ±2°C, sensor 3 ≈ 40°C ±2°C |
| **Runs** | 3 |

---

#### HIL-SIT-086: Data Flow — IVT Current End-to-End

| Field | Value |
|-------|-------|
| **SYS.3 Ref** | §8.1 Measurement Path, §11.5.2 |
| **Objective** | Verify IVT current flows from CAN RX → database → CAN TX |
| **Preconditions** | BMS in NORMAL |
| **Stimulus** | Inject IVT 0x521 with 1500 mA current |
| **Pass criteria** | CAN 0x235/0x236: string/pack current = 1500 mA ±50 mA |
| **Runs** | 3 |

---

#### HIL-SIT-087: BMS State Machine — Full Cycle

| Field | Value |
|-------|-------|
| **SYS.3 Ref** | §7a.2 BMS State Machine |
| **Objective** | Verify complete state machine cycle: STANDBY → PRECHARGE → NORMAL → ERROR → recovery → STANDBY |
| **Preconditions** | BMS in STANDBY |
| **Stimulus** | 1. Request NORMAL (→PRECHARGE→NORMAL) 2. Inject OV fault (→ERROR) 3. Clear fault + request STANDBY (→STANDBY) |
| **Pass criteria** | All transitions occur in correct sequence; no unexpected states |
| **Runs** | 5 |

---

#### HIL-SIT-088: BMS State Machine — Invalid Transition Rejection

| Field | Value |
|-------|-------|
| **SYS.3 Ref** | §7a.2, SSR-051 |
| **Objective** | Verify BMS rejects invalid state requests |
| **Preconditions** | BMS in STANDBY |
| **Stimulus** | Send CAN 0x210 with invalid state value (e.g., 0xFF) |
| **Pass criteria** | BMS remains in STANDBY; no state change; no crash |
| **Runs** | 3 |

---

#### HIL-SIT-089: Task Timing — 10ms Task Period

| Field | Value |
|-------|-------|
| **SYS.3 Ref** | §7a.4 Task Scheduling |
| **Objective** | Verify 10ms task executes at correct period |
| **Preconditions** | BMS in NORMAL |
| **Stimulus** | Monitor CAN TX message timestamps over 10s |
| **Pass criteria** | Message interval = 100ms ±5ms (10ms task updates CAN at 100ms cycle) |
| **Runs** | 3 |

---

#### HIL-SIT-090: SPI1 AFE Communication — Continuous Operation

| Field | Value |
|-------|-------|
| **SYS.3 Ref** | §11.2.8 J9000, §11.1.1 SPI1 |
| **Objective** | Verify SPI1 → LTC6813 communication runs continuously without errors |
| **Preconditions** | BMS in NORMAL, 5 min soak |
| **Stimulus** | None (observe) |
| **Pass criteria** | No DIAG_ID_AFE_SPI or AFE_COMMUNICATION_INTEGRITY events in 5 min; cell voltages update every cycle |
| **Runs** | 1 (5 min duration) |

---

#### HIL-SIT-091: Interlock Loop — Closed State Verification

| Field | Value |
|-------|-------|
| **SYS.3 Ref** | §11.2.5 J2033 |
| **Objective** | Verify interlock loop reads as CLOSED when physically closed |
| **Preconditions** | BMS in STANDBY, interlock relay CLOSED |
| **Stimulus** | None (verify steady state) |
| **Pass criteria** | No DIAG_ID_INTERLOCK_FEEDBACK events; BMS remains in STANDBY |
| **Runs** | 3 |

---

#### HIL-SIT-092: Contactor Sequencing — Precharge Timing

| Field | Value |
|-------|-------|
| **SYS.3 Ref** | §7a.2 PRECHARGE state |
| **Objective** | Verify precharge contactor sequence and timing |
| **Preconditions** | BMS in STANDBY |
| **Stimulus** | Request NORMAL; monitor SPS outputs with timestamps |
| **Pass criteria** | Sequence: STR- first → PRE second → wait → STR+ third → PRE open; total < 2s |
| **Runs** | 5 |

---

#### HIL-SIT-093: SPS Output — Contactor De-energize on Power Loss

| Field | Value |
|-------|-------|
| **SYS.3 Ref** | §11.7, GAP-11 (SPS UVLO) |
| **Objective** | Verify contactors open when supply power is removed |
| **Preconditions** | BMS in NORMAL, all contactors CLOSED |
| **Stimulus** | Remove 12V supply from J2009 |
| **Pass criteria** | All SPS outputs go LOW within 50ms; contactor feedback shows OPEN |
| **Runs** | 3 |

---

### Category 9: ASIL D Depth — TSR-01 Cell Overvoltage (Extended)

ASIL D requires thorough testing. These tests extend TSR-01 coverage beyond the basic
threshold test with boundary values, state-specific behavior, and edge cases.

---

#### HIL-SIT-100: TSR-01 OV — MOL Threshold (Warning Only)

| Field | Value |
|-------|-------|
| **TSR** | TSR-01 (MOL level) |
| **Objective** | Verify MOL overvoltage triggers warning but NOT contactor open |
| **Preconditions** | BMS in NORMAL, all cells 3600 mV |
| **Stimulus** | Set all cells to MOL threshold (e.g., 2700 mV or configured value) |
| **Pass criteria** | DIAG warning fires; BMS stays in NORMAL; no contactor action |
| **Runs** | 5 |

---

#### HIL-SIT-101: TSR-01 OV — RSL Threshold (Current Limiting)

| Field | Value |
|-------|-------|
| **TSR** | TSR-01 (RSL level) |
| **Objective** | Verify RSL overvoltage triggers current limiting but NOT contactor open |
| **Preconditions** | BMS in NORMAL |
| **Stimulus** | Set all cells to RSL threshold |
| **Pass criteria** | DIAG RSL fires; current limit reduced in CAN TX; BMS stays in NORMAL |
| **Runs** | 5 |

---

#### HIL-SIT-102: TSR-01 OV — MSL During PRECHARGE State

| Field | Value |
|-------|-------|
| **TSR** | TSR-01 |
| **Objective** | Verify OV detection works during PRECHARGE (not just NORMAL) |
| **Preconditions** | BMS transitioning to PRECHARGE |
| **Stimulus** | Set all cells to 2850 mV during precharge sequence |
| **Pass criteria** | Precharge aborts; BMS → ERROR; all contactors OPEN |
| **Runs** | 5 |

---

#### HIL-SIT-103: TSR-01 OV — MSL During STANDBY State

| Field | Value |
|-------|-------|
| **TSR** | TSR-01 |
| **Objective** | Verify OV detection works during STANDBY |
| **Preconditions** | BMS in STANDBY |
| **Stimulus** | Set all cells to 2850 mV |
| **Pass criteria** | DIAG FATAL fires; BMS → ERROR (already in safe state, contactors already open) |
| **Runs** | 3 |

---

#### HIL-SIT-104: TSR-01 OV — Gradual Ramp (1 mV/s)

| Field | Value |
|-------|-------|
| **TSR** | TSR-01 |
| **Objective** | Verify OV detection with slow voltage rise (realistic charging scenario) |
| **Preconditions** | BMS in NORMAL, all cells 2750 mV |
| **Stimulus** | Ramp all cells at 1 mV/s from 2750 → 2850 mV |
| **Pass criteria** | ERROR triggers between 2798-2803 mV (threshold ±ADC TME); reaction time ≤ 750ms from crossing |
| **Runs** | 5 |

---

#### HIL-SIT-105: TSR-01 OV — Threshold Counter Reset (Intermittent)

| Field | Value |
|-------|-------|
| **TSR** | TSR-01, SSR-033 |
| **Objective** | Verify DIAG counter decrements when fault clears before threshold |
| **Preconditions** | BMS in NORMAL, all cells 3600 mV |
| **Stimulus** | Set all cells to 2820 mV for 200ms, then back to 3600 mV; repeat 3 times |
| **Pass criteria** | BMS does NOT enter ERROR (counter resets between bursts) |
| **Runs** | 5 |

---

#### HIL-SIT-106: TSR-01 OV — Single Cell vs All Cells (GAP-03 Deep Dive)

| Field | Value |
|-------|-------|
| **TSR** | TSR-01, GAP-03 |
| **ASIL** | D |
| **Objective** | Quantify the plausibility rejection at different spread values |
| **Preconditions** | BMS in NORMAL, 17 cells at 2500 mV |
| **Stimulus** | Step cell 0 through: 2600, 2700, 2750, 2800, 2850, 2900 mV. Record which triggers ERROR. |
| **Pass criteria** | ERROR should trigger when cell 0 is within 300 mV of average (spread ≤ 300 mV). Above 300 mV spread: WARNING only (GAP-03 confirmed). |
| **Runs** | 5 per step |

---

#### HIL-SIT-107: TSR-01 OV — Plausibility Cross-Check (AFE vs IVT)

| Field | Value |
|-------|-------|
| **TSR** | TSR-01, FM-01 |
| **Objective** | Verify pack voltage plausibility catches AFE/IVT disagreement |
| **Preconditions** | BMS in NORMAL |
| **Stimulus** | Set cells to 2850 mV (sum = 51300 mV) but IVT V1 (0x522) reports 46800 mV (mismatch > 2V) |
| **Pass criteria** | DIAG_ID_PLAUSIBILITY_PACK_VOLTAGE triggers |
| **Runs** | 3 |

---

#### HIL-SIT-108: TSR-01 OV — With Active Cell Balancing

| Field | Value |
|-------|-------|
| **TSR** | TSR-01 |
| **Objective** | Verify OV detection accuracy is not degraded during cell balancing |
| **Preconditions** | BMS in NORMAL, balancing active on cells 2,5,8 |
| **Stimulus** | Set all cells to 2850 mV |
| **Pass criteria** | ERROR within 750ms FTTI (balancing MUTE/UNMUTE does not delay detection) |
| **Runs** | 5 |

---

### Category 10: ASIL D Depth — TSR-10 AFE Communication (Extended)

---

#### HIL-SIT-110: TSR-10 — PEC Error Detection (Single Corruption)

| Field | Value |
|-------|-------|
| **TSR** | TSR-10 |
| **Objective** | Verify AFE PEC error is detected and counted |
| **Preconditions** | BMS in NORMAL |
| **Stimulus** | Break isoSPI chain momentarily (relay toggle, 50ms) then reconnect |
| **Pass criteria** | DIAG_ID_AFE_COMMUNICATION_INTEGRITY counter increments; if < 5 events, BMS stays NORMAL (threshold not reached) |
| **Runs** | 5 |

---

#### HIL-SIT-111: TSR-10 — Sustained AFE Loss → FTTI Measurement

| Field | Value |
|-------|-------|
| **TSR** | TSR-10 |
| **ASIL** | D (support) |
| **Objective** | Measure exact reaction time from AFE loss to contactor open |
| **Preconditions** | BMS in NORMAL, stable 5s |
| **Stimulus** | Open daisy chain relay (PP-04) and hold open |
| **Pass criteria** | ERROR within 200ms FTTI; measure exact timing over 10 runs |
| **Statistical** | 10 runs; report mean/min/max/σ; FAIL if ANY run > 200ms |

---

#### HIL-SIT-112: TSR-10 — AFE Recovery After Transient Error

| Field | Value |
|-------|-------|
| **TSR** | TSR-10 |
| **Objective** | Verify AFE communication recovers after brief interruption |
| **Preconditions** | BMS in NORMAL |
| **Stimulus** | Open daisy chain relay for 30ms (< 5 events), then close |
| **Pass criteria** | Cell voltage data resumes within 500ms; no ERROR transition |
| **Runs** | 5 |

---

### Category 11: ASIL D Depth — Overcurrent (Extended)

---

#### HIL-SIT-120: TSR-04 OC — Threshold Boundary (ASIL B)

| Field | Value |
|-------|-------|
| **TSR** | TSR-04 |
| **Objective** | Verify exact overcurrent detection threshold |
| **Preconditions** | BMS in NORMAL |
| **Stimulus** | Ramp IVT 0x521 from 2000 → 3000 mA in 100 mA steps, 200ms per step |
| **Pass criteria** | ERROR triggers at 2400 mA (BS_MAX_DISCHARGE_CURRENT_MSL ±measurement error) |
| **Runs** | 5 |

---

#### HIL-SIT-121: TSR-04 OC — During PRECHARGE

| Field | Value |
|-------|-------|
| **TSR** | TSR-04 |
| **Objective** | Verify overcurrent protection during precharge (limited current expected) |
| **Preconditions** | BMS in PRECHARGE |
| **Stimulus** | IVT 0x521 reports 3000 mA during precharge |
| **Pass criteria** | Precharge aborts; ERROR within 250ms |
| **Runs** | 3 |

---

### Category 12: Temperature (Extended)

---

#### HIL-SIT-130: TSR-06 OT — Charge vs Discharge Threshold Difference

| Field | Value |
|-------|-------|
| **TSR** | TSR-06 |
| **Objective** | Verify different OT thresholds for charge (45°C) vs discharge (55°C) |
| **Preconditions** | BMS in NORMAL |
| **Stimulus** | Test 1: Set NTCs to 50°C with discharge current → no ERROR (below 55°C) Test 2: Set NTCs to 50°C with charge current → ERROR (above 45°C) |
| **Pass criteria** | Discharge at 50°C: NORMAL maintained; Charge at 50°C: ERROR |
| **Runs** | 5 each |

---

#### HIL-SIT-131: TSR-06 OT — Thermal Inertia Justification

| Field | Value |
|-------|-------|
| **TSR** | TSR-06 |
| **Objective** | Verify 6050ms FTTI is adequate by demonstrating temperature cannot change dangerously in that time |
| **Preconditions** | BMS in NORMAL, NTCs at 54°C (1°C below discharge MSL) |
| **Stimulus** | Step NTCs to 60°C; measure time to ERROR |
| **Pass criteria** | ERROR within 6050ms; during the FTTI window, cell temperature rise from internal heating is < 0.5°C (measured via NTC response) |
| **Runs** | 3 |

---

#### HIL-SIT-132: TSR-07 UT — Cold Soak + Charge Attempt

| Field | Value |
|-------|-------|
| **TSR** | TSR-07 |
| **Objective** | Verify BMS prevents charging at -25°C |
| **Preconditions** | BMS in NORMAL, NTCs at -25°C equivalent resistance |
| **Stimulus** | IVT reports charge current (negative value) |
| **Pass criteria** | ERROR within 6050ms; contactors OPEN |
| **Runs** | 3 |

---

### Category 13: Endurance and Soak Tests

---

#### HIL-SIT-140: 1-Hour Soak — No Spurious Faults

| Field | Value |
|-------|-------|
| **Objective** | Verify BMS runs for 1 hour without false errors under nominal conditions |
| **Preconditions** | BMS in NORMAL, all sensors nominal |
| **Stimulus** | None (continuous monitoring) |
| **Pass criteria** | No DIAG errors; no state transitions; all CAN messages continuous |
| **Runs** | 1 (1 hour) |

---

#### HIL-SIT-141: Power Cycle Stress — 50 Cycles

| Field | Value |
|-------|-------|
| **Objective** | Verify BMS starts up correctly after repeated power cycles |
| **Preconditions** | Automated power cycle via relay on J2009 CLAMP15 |
| **Stimulus** | 50 power cycles: ON 30s → OFF 5s → ON |
| **Pass criteria** | All 50 cycles: BMS reaches STANDBY within 5s; no stuck states |
| **Runs** | 1 (50 cycles) |

---

#### HIL-SIT-142: SOC Persistence — Power Cycle Recovery

| Field | Value |
|-------|-------|
| **Objective** | Verify SOC value is preserved across power cycle (FRAM persistence) |
| **Preconditions** | BMS in NORMAL, SOC stabilized at ~50% |
| **Stimulus** | Power cycle; read SOC after restart |
| **Pass criteria** | SOC after restart = SOC before shutdown ±5% (FRAM read OK) |
| **Runs** | 3 |
| **Gotcha** | GAP-05: FRAM write may fail silently; SOC may recalculate from voltage |

---

### Category 14: EMC and Robustness

---

#### HIL-SIT-150: CAN Error Frame Injection

| Field | Value |
|-------|-------|
| **Objective** | Verify BMS handles CAN error frames gracefully |
| **Preconditions** | BMS in NORMAL |
| **Stimulus** | Inject 100 error frames on CAN1 over 1s |
| **Pass criteria** | BMS stays NORMAL; IVT data recovery within 200ms after burst; no crash |
| **Runs** | 3 |

---

#### HIL-SIT-151: CAN Bus Load — 80% Saturation

| Field | Value |
|-------|-------|
| **Objective** | Verify BMS functions at high CAN bus load |
| **Preconditions** | BMS in NORMAL |
| **Stimulus** | Inject additional CAN traffic to bring bus to 80% load |
| **Pass criteria** | BMS messages still transmitted; IVT messages still received; FTTI not degraded |
| **Runs** | 3 |

---

#### HIL-SIT-152: Supply Brown-Out — Voltage Dip

| Field | Value |
|-------|-------|
| **Objective** | Verify BMS behavior during brief supply voltage dip |
| **Preconditions** | BMS in NORMAL |
| **Stimulus** | Dip J2009 supply from 12V to 8V for 500ms, then back to 12V |
| **Pass criteria** | Either: BMS recovers and returns to NORMAL, or BMS enters ERROR (clean shutdown). No undefined behavior. |
| **Runs** | 3 |

### Category 15: ASIL D Depth — TSR-02 Cell Undervoltage

Mirror of TSR-01 depth for the undervoltage path (ASIL C rated but SSR-002 is ASIL D).

---

#### HIL-SIT-200: TSR-02 UV — MOL Threshold (Warning Only)

| Field | Value |
|-------|-------|
| **TSR** | TSR-02 (MOL) |
| **Objective** | Verify MOL undervoltage triggers warning but NOT contactor open |
| **Preconditions** | BMS in NORMAL, all cells 2000 mV |
| **Stimulus** | Set all cells to MOL threshold (e.g., 1800 mV) |
| **Pass criteria** | DIAG warning fires; BMS stays NORMAL |
| **Runs** | 5 |

---

#### HIL-SIT-201: TSR-02 UV — RSL Threshold

| Field | Value |
|-------|-------|
| **TSR** | TSR-02 (RSL) |
| **Objective** | Verify RSL undervoltage triggers current limiting |
| **Preconditions** | BMS in NORMAL |
| **Stimulus** | Set all cells to RSL threshold |
| **Pass criteria** | DIAG RSL fires; discharge current limit reduced; BMS stays NORMAL |
| **Runs** | 5 |

---

#### HIL-SIT-202: TSR-02 UV — MSL During PRECHARGE

| Field | Value |
|-------|-------|
| **TSR** | TSR-02 |
| **Objective** | Verify UV detection during PRECHARGE state |
| **Preconditions** | BMS transitioning to PRECHARGE |
| **Stimulus** | Set all cells to 1450 mV during precharge |
| **Pass criteria** | Precharge aborts; ERROR; contactors OPEN |
| **Runs** | 5 |

---

#### HIL-SIT-203: TSR-02 UV — MSL During STANDBY

| Field | Value |
|-------|-------|
| **TSR** | TSR-02 |
| **Objective** | Verify UV detection during STANDBY |
| **Preconditions** | BMS in STANDBY |
| **Stimulus** | Set all cells to 1450 mV |
| **Pass criteria** | FATAL fires; ERROR (contactors already open) |
| **Runs** | 3 |

---

#### HIL-SIT-204: TSR-02 UV — Gradual Drain (1 mV/s)

| Field | Value |
|-------|-------|
| **TSR** | TSR-02 |
| **Objective** | Verify UV detection with slow voltage drop (realistic discharge) |
| **Preconditions** | BMS in NORMAL, all cells 1600 mV |
| **Stimulus** | Ramp all cells down at 1 mV/s from 1600 → 1400 mV |
| **Pass criteria** | ERROR triggers at 1500 mV ±3 mV; reaction ≤ 750ms from crossing |
| **Runs** | 5 |

---

#### HIL-SIT-205: TSR-02 UV — Counter Reset (Intermittent)

| Field | Value |
|-------|-------|
| **TSR** | TSR-02, SSR-033 |
| **Objective** | Verify counter decrements when UV fault clears before threshold |
| **Preconditions** | BMS in NORMAL, all cells 1600 mV |
| **Stimulus** | Set all cells to 1480 mV for 200ms, then back to 1600 mV; repeat 3× |
| **Pass criteria** | BMS does NOT enter ERROR |
| **Runs** | 5 |

---

#### HIL-SIT-206: TSR-02 UV — Single Cell (Plausibility Check)

| Field | Value |
|-------|-------|
| **TSR** | TSR-02, GAP-03 |
| **Objective** | Test if single-cell UV is also affected by plausibility rejection |
| **Preconditions** | BMS in NORMAL, 17 cells at 2500 mV |
| **Stimulus** | Set cell 0 to 1450 mV (spread = 1050 mV >> 300 mV threshold) |
| **Pass criteria** | Cell 0 is rejected as outlier (WARNING only). Verify plausibility applies to UV path too. |
| **Runs** | 5 |

---

### Category 16: ASIL D Depth — SSR Fault Reaction Chain

Tests the core ASIL D reaction: FATAL → ERROR → CONT_OpenAll → safe state.

---

#### HIL-SIT-210: SSR-020 — FATAL Flag → ERROR Transition

| Field | Value |
|-------|-------|
| **SSR** | SSR-020 |
| **ASIL** | D |
| **Objective** | Verify ANY DIAG FATAL triggers ERROR transition |
| **Preconditions** | BMS in NORMAL |
| **Stimulus** | Trigger 5 different FATAL sources sequentially (OV, UV, OC, OT, AFE loss) |
| **Pass criteria** | Each triggers ERROR within one BMS task cycle (100ms) |
| **Runs** | 5 per source (25 total) |

---

#### HIL-SIT-211: SSR-021 — Contactor Open Within 100ms of ERROR

| Field | Value |
|-------|-------|
| **SSR** | SSR-021 |
| **ASIL** | D |
| **Objective** | Measure time from ERROR state entry to contactor de-energize |
| **Preconditions** | BMS in NORMAL |
| **Stimulus** | Trigger OV fault; measure t_ERROR to t_SPS_output_LOW |
| **Pass criteria** | SPS command issued within 100ms of ERROR entry; all 3 contactors commanded open |
| **Statistical** | 10 runs; report mean/min/max/σ |

---

#### HIL-SIT-212: SSR-022 — ERROR Exit Requires Fault Clear

| Field | Value |
|-------|-------|
| **SSR** | SSR-022 |
| **ASIL** | D |
| **Objective** | Verify ERROR cannot exit while fault condition persists |
| **Preconditions** | BMS in ERROR (OV fault active, cells still at 2850 mV) |
| **Stimulus** | Send CAN 0x210 STANDBY request (without clearing fault) |
| **Pass criteria** | BMS remains in ERROR |
| **Runs** | 5 |

---

#### HIL-SIT-213: SSR-023 — ERROR Exit Requires CAN Request

| Field | Value |
|-------|-------|
| **SSR** | SSR-023 |
| **ASIL** | D |
| **Objective** | Verify ERROR cannot exit without explicit STANDBY request |
| **Preconditions** | BMS in ERROR, fault cleared (cells back to 3600 mV) |
| **Stimulus** | Wait 60s without sending any CAN request |
| **Pass criteria** | BMS remains in ERROR for full 60s (no auto-recovery) |
| **Runs** | 3 |

---

#### HIL-SIT-214: SSR-024 — ERROR Exit AND Logic

| Field | Value |
|-------|-------|
| **SSR** | SSR-024 |
| **ASIL** | D |
| **Objective** | Verify both conditions must be TRUE simultaneously for ERROR exit |
| **Preconditions** | BMS in ERROR |
| **Stimulus** | 1. Clear fault first, wait 5s, THEN send STANDBY request. 2. Send request first, THEN clear fault. Both must work. |
| **Pass criteria** | ERROR exits ONLY when both conditions met in same evaluation cycle |
| **Runs** | 5 |

---

#### HIL-SIT-215: SSR-020 — Double Fault (OV + OC Simultaneously)

| Field | Value |
|-------|-------|
| **SSR** | SSR-020 |
| **ASIL** | D |
| **Objective** | Verify ERROR handling with two simultaneous FATAL flags |
| **Preconditions** | BMS in NORMAL |
| **Stimulus** | Set cells to 2850 mV AND IVT current to 3000 mA simultaneously |
| **Pass criteria** | ERROR; BOTH DIAG IDs flagged; contactor open within fastest FTTI (250ms) |
| **Runs** | 5 |

---

#### HIL-SIT-216: SSR-020 — ERROR During Recovery Attempt

| Field | Value |
|-------|-------|
| **SSR** | SSR-020, SSR-024 |
| **ASIL** | D |
| **Objective** | Verify new fault during ERROR recovery re-latches ERROR |
| **Preconditions** | BMS in ERROR, fault cleared, about to send STANDBY request |
| **Stimulus** | Inject new OC fault just before sending STANDBY request |
| **Pass criteria** | ERROR persists; new DIAG ID flagged; recovery blocked |
| **Runs** | 3 |

---

### Category 17: ASIL D Depth — Contactor Safety (SSR-050/051/052)

---

#### HIL-SIT-220: SSR-050 — Feedback Mismatch All 3 Contactors

| Field | Value |
|-------|-------|
| **SSR** | SSR-050 |
| **ASIL** | D |
| **Objective** | Verify feedback mismatch detection on each contactor individually |
| **Preconditions** | BMS in ERROR (contactors commanded OPEN) |
| **Stimulus** | Force feedback relay: 1. String+ CLOSED 2. String- CLOSED 3. (Precharge — no feedback, GAP-02) |
| **Pass criteria** | DIAG fires for String+ and String- within 350ms each; Precharge: no DIAG (confirms GAP-02) |
| **Runs** | 5 per contactor |

---

#### HIL-SIT-221: SSR-051 — Contactor Close Only in Valid States

| Field | Value |
|-------|-------|
| **SSR** | SSR-051 |
| **ASIL** | D |
| **Objective** | Verify contactors cannot close from ERROR state without proper recovery |
| **Preconditions** | BMS in ERROR |
| **Stimulus** | Send CAN 0x210 = NORMAL request (invalid from ERROR) |
| **Pass criteria** | Contactors remain OPEN; BMS remains in ERROR |
| **Runs** | 5 |

---

#### HIL-SIT-222: SSR-051 — Contactor Close Rejected During STANDBY Without Request

| Field | Value |
|-------|-------|
| **SSR** | SSR-051 |
| **ASIL** | D |
| **Objective** | Verify contactors don't close spontaneously in STANDBY |
| **Preconditions** | BMS in STANDBY, no CAN state requests sent |
| **Stimulus** | Wait 60s, monitor SPS outputs |
| **Pass criteria** | All SPS outputs remain LOW for 60s; no contactor actuation |
| **Runs** | 3 |

---

### Category 18: ASIL D Depth — DIAG Coverage (SSR-030/031/032/033)

---

#### HIL-SIT-230: SSR-030 — Threshold Counter Configuration Verification

| Field | Value |
|-------|-------|
| **SSR** | SSR-030 |
| **ASIL** | D |
| **Objective** | Verify DIAG threshold counters are configured correctly for all ASIL D IDs |
| **Preconditions** | BMS in STANDBY |
| **Stimulus** | Read DIAG configuration via CAN debug or JTAG |
| **Pass criteria** | OV threshold=50, OC threshold=10, OT threshold=500, AFE threshold=5. All match diag_cfg.c |
| **Runs** | 1 |

---

#### HIL-SIT-231: SSR-031 — Noise Rejection (No False FATAL)

| Field | Value |
|-------|-------|
| **SSR** | SSR-031 |
| **ASIL** | D |
| **Objective** | Verify threshold counting prevents false FATAL from measurement noise |
| **Preconditions** | BMS in NORMAL, all cells 2790 mV (10 mV below OV threshold) |
| **Stimulus** | Add ±5 mV noise to cell voltage (rapid oscillation above/below 2800 mV, 1 ms period) |
| **Pass criteria** | BMS does NOT enter ERROR (noise is too fast for 50-event threshold at 10ms period) |
| **Runs** | 5 |

---

#### HIL-SIT-232: SSR-032 — Persistent Fault Reaches Threshold

| Field | Value |
|-------|-------|
| **SSR** | SSR-032 |
| **ASIL** | D |
| **Objective** | Verify persistent fault IS detected (counter reaches threshold) |
| **Preconditions** | BMS in NORMAL |
| **Stimulus** | Set all cells to 2810 mV (sustained, above threshold) |
| **Pass criteria** | ERROR within 750ms; counter reached 50 (verified via DIAG data) |
| **Runs** | 5 |

---

#### HIL-SIT-233: SSR-033 — Counter Decrement on Recovery

| Field | Value |
|-------|-------|
| **SSR** | SSR-033 |
| **ASIL** | D |
| **Objective** | Verify counter decrements when fault clears |
| **Preconditions** | BMS in NORMAL, trigger 30 OV events (below threshold of 50) |
| **Stimulus** | Clear fault (cells to 3600 mV); wait 3s; re-trigger OV |
| **Pass criteria** | On re-trigger, counter starts from 0 (not 30). Counter was fully decremented during clear period. |
| **Runs** | 3 |

---

### Category 19: ASIL D Depth — Communication Safety (SSR-040/041/042)

---

#### HIL-SIT-240: SSR-040 — CAN Loss Detection Timing Accuracy

| Field | Value |
|-------|-------|
| **SSR** | SSR-040 |
| **ASIL** | D |
| **Objective** | Measure exact time from CAN loss to ERROR |
| **Preconditions** | BMS in NORMAL, vehicle CAN active |
| **Stimulus** | Stop all CAN2 traffic; measure time to ERROR |
| **Pass criteria** | ERROR within 1250ms FTTI |
| **Statistical** | 10 runs; report mean/min/max/σ; FAIL if ANY > 1250ms |

---

#### HIL-SIT-241: SSR-041 — IVT Loss Detection per Channel

| Field | Value |
|-------|-------|
| **SSR** | SSR-041 |
| **ASIL** | D |
| **Objective** | Verify each IVT channel timeout independently |
| **Preconditions** | BMS in NORMAL, all IVT messages active |
| **Stimulus** | Stop one IVT message at a time: 1. 0x521 only 2. 0x522 only 3. 0x524 only |
| **Pass criteria** | Each triggers its specific DIAG_ID within its FTTI (current: 1250ms, V1-V3: 160ms) |
| **Runs** | 3 per channel (9 total) |

---

#### HIL-SIT-242: SSR-042 — AFE Loss Detection Accuracy

| Field | Value |
|-------|-------|
| **SSR** | SSR-042 |
| **ASIL** | D |
| **Objective** | Measure exact AFE loss to ERROR timing (200ms FTTI) |
| **Preconditions** | BMS in NORMAL |
| **Stimulus** | Open daisy chain relay (PP-04) |
| **Pass criteria** | ERROR within 200ms |
| **Statistical** | 10 runs; report mean/min/max/σ; FAIL if ANY > 200ms |

---

#### HIL-SIT-243: SSR-040 — CAN Recovery After Brief Loss

| Field | Value |
|-------|-------|
| **SSR** | SSR-040 |
| **ASIL** | D |
| **Objective** | Verify CAN timeout counter resets on message reception |
| **Preconditions** | BMS in NORMAL |
| **Stimulus** | Stop CAN2 for 500ms (below 1250ms FTTI), then resume |
| **Pass criteria** | BMS stays NORMAL; counter resets; no ERROR |
| **Runs** | 5 |

---

### Category 20: ASIL D — System Monitoring Extended (TSR-12)

---

#### HIL-SIT-250: TSR-12 — DIAG Configuration Presence

| Field | Value |
|-------|-------|
| **TSR** | TSR-12 |
| **ASIL** | D |
| **Objective** | Verify SYSTEM_MONITORING, FLASHCHECKSUM, ALERT_MODE are configured with threshold=1, delay=0 |
| **Preconditions** | BMS in STANDBY |
| **Stimulus** | Read DIAG table via debug interface |
| **Pass criteria** | All 3 IDs present, threshold=1, delay=0, severity=FATAL |
| **Runs** | 1 |

---

#### HIL-SIT-251: TSR-12 — SBC Watchdog Service Verification

| Field | Value |
|-------|-------|
| **TSR** | TSR-12, TSR-14 |
| **ASIL** | D |
| **Objective** | Verify SBC watchdog is being serviced (no RSTB assertion during normal operation) |
| **Preconditions** | BMS in NORMAL, 10 min observation |
| **Stimulus** | None (observe) |
| **Pass criteria** | No SBC_RSTB events; no MCU resets; BMS remains NORMAL for 10 min |
| **Runs** | 1 (10 min) |

---

#### HIL-SIT-252: TSR-12 — FRAM Read-Back Integrity

| Field | Value |
|-------|-------|
| **TSR** | TSR-12, GAP-05 |
| **Objective** | Verify FRAM stores and retrieves SOC correctly |
| **Preconditions** | BMS in NORMAL, SOC at known value |
| **Stimulus** | 1. Record SOC. 2. Power cycle. 3. Read SOC after restart. |
| **Pass criteria** | SOC after restart matches pre-cycle value ±5% |
| **Runs** | 5 |
| **Note** | If FRAM write fails silently (GAP-05), SOC recalculates from voltage — may differ more than 5% |

---

## 5. Test Summary Matrix

| Test ID | Category | TSR/FM/GAP | ASIL | FTTI (ms) | Runs | Probe Points |
|---------|----------|-----------|------|-----------|------|-------------|
| HIL-SIT-001 | Normal | — | — | — | 3 | PP-06 |
| HIL-SIT-002 | Normal | TSR-08 | B | — | 5 | PP-06,09 |
| HIL-SIT-003 | Normal | TSR-11 | — | — | 3 | PP-06 |
| HIL-SIT-004 | Normal | TSR-08 | B | — | 3 | PP-06,09 |
| HIL-SIT-005 | Normal | TSR-01/02 | D | — | 3 | PP-01,06 |
| HIL-SIT-010 | Safety | TSR-01 | D | 750 | 10 | PP-01,06,08,09 |
| HIL-SIT-011 | Safety | TSR-01 | D | 750 | 5 | PP-01,06 |
| HIL-SIT-012 | Safety | TSR-02 | C | 750 | 10 | PP-01,06,09 |
| HIL-SIT-013 | Safety | TSR-03 | QM | 160 | 5 | PP-01,06 |
| HIL-SIT-014 | Safety | TSR-04 | B | 250 | 10 | PP-06,09 |
| HIL-SIT-015 | Safety | TSR-05 | C | 250 | 10 | PP-06,09 |
| HIL-SIT-016 | Safety | TSR-06 | C | 6050 | 10 | PP-02,06,09 |
| HIL-SIT-017 | Safety | TSR-07 | B | 6050 | 10 | PP-02,06,09 |
| HIL-SIT-018 | Safety | TSR-08 | B | 350 | 5 | PP-08,09 |
| HIL-SIT-019 | Safety | TSR-09 | B | 1250 | 10 | PP-06 |
| HIL-SIT-020 | Safety | TSR-10 | D | 200 | 10 | PP-04 |
| HIL-SIT-021 | Safety | TSR-11 | — | 1250 | 5 | PP-07 |
| HIL-SIT-022 | Safety | TSR-12 | D | 51 | 1 | PP-15 |
| HIL-SIT-023 | Safety | TSR-13 | QM | 250 | 10 | PP-10 |
| HIL-SIT-024 | Safety | TSR-15 | B | 250 | 10 | PP-06,09 |
| HIL-SIT-030 | Fault-E | FM-01 | D | — | 3 | PP-01,06 |
| HIL-SIT-031 | Fault-E | FM-02 | D | 350 | 5 | PP-01,08,09 |
| HIL-SIT-032 | Fault-E | FM-03 | C | — | 5 | PP-01 |
| HIL-SIT-033 | Fault-E | FM-04 | C | — | 3 | PP-02 |
| HIL-SIT-034 | Fault-E | FM-07 | B | — | 3 | PP-06 |
| HIL-SIT-035 | Fault-E | FM-12 | B | 350 | 5 | PP-08 |
| HIL-SIT-036 | Fault-E | FM-13 | B | — | 3 | PP-08 |
| HIL-SIT-037 | Fault-E | FM-18 | QM | — | 5 | PP-10 |
| HIL-SIT-040 | Fault-C | TSR-09 | B | 160 | 5 | PP-06 |
| HIL-SIT-041 | Fault-C | TSR-09 | B | 1250 | 5 | PP-06 |
| HIL-SIT-042 | Fault-C | TSR-10 | D | 200 | 5 | PP-04 |
| HIL-SIT-043 | Fault-C | TSR-11 | — | — | 3 | PP-06 |
| HIL-SIT-044 | Fault-C | L-009 | — | — | 3 | PP-06 |
| HIL-SIT-050 | Multi | TSR-01+04 | D | 250 | 5 | PP-01,06,09 |
| HIL-SIT-051 | Multi | TSR-01+10 | D | 200 | 3 | PP-01,04 |
| HIL-SIT-052 | Multi | TSR-13+08 | B | 250 | 3 | PP-09,10 |
| HIL-SIT-060 | Recovery | SSR-022/23/24 | D | — | 3 | PP-06 |
| HIL-SIT-061 | Recovery | SSR-024 | D | — | 3 | PP-06 |
| HIL-SIT-062 | Recovery | SSR-022 | D | — | 3 | PP-06 |
| HIL-SIT-070 | Gap-Neg | GAP-03 | D | — | 5 | PP-01,06 |
| HIL-SIT-071 | Gap-Neg | GAP-02 | B | — | 3 | PP-08 |
| HIL-SIT-072 | Gap-Neg | GAP-06 | B | — | 3 | PP-06 |

**Total: 42 test cases, 217 runs**

---

## 6. Traceability Coverage

### 6.1 TSR Coverage

| TSR | Test Cases | Coverage |
|-----|-----------|----------|
| TSR-01 | HIL-SIT-010, 011, 030, 050, 051, 070 | Full |
| TSR-02 | HIL-SIT-012 | Full |
| TSR-03 | HIL-SIT-013 | Full |
| TSR-04 | HIL-SIT-014, 050 | Full |
| TSR-05 | HIL-SIT-015 | Full |
| TSR-06 | HIL-SIT-016, 033 | Full |
| TSR-07 | HIL-SIT-017 | Full |
| TSR-08 | HIL-SIT-002, 004, 018, 031, 035, 036, 071 | Full |
| TSR-09 | HIL-SIT-019, 040, 041, 044 | Full |
| TSR-10 | HIL-SIT-020, 042, 051 | Full |
| TSR-11 | HIL-SIT-003, 021, 043 | Full |
| TSR-12 | HIL-SIT-022 | Partial (HIL limitation) |
| TSR-13 | HIL-SIT-023, 037, 052 | Full |
| TSR-14 | — | Not testable (SBC internal, HIL limitation) |
| TSR-15 | HIL-SIT-024, 034, 072 | Full |

**Coverage: 14/15 TSRs fully covered, 1 partial (TSR-12 HIL limitation), 1 not testable (TSR-14)**

### 6.2 FMEA Coverage

| FMEA | Test Cases |
|------|-----------|
| FM-01 (OV undetected) | HIL-SIT-030 |
| FM-02 (OV + weld) | HIL-SIT-031 |
| FM-03 (UV false pos) | HIL-SIT-032 |
| FM-04 (NTC open) | HIL-SIT-033 |
| FM-07 (IVT offset) | HIL-SIT-034 |
| FM-12 (weld string+) | HIL-SIT-035 |
| FM-13 (stuck open) | HIL-SIT-036 |
| FM-18 (interlock noise) | HIL-SIT-037 |

**8/19 FMEAs directly tested. Remaining 11 are covered indirectly by TSR tests or are not HIL-injectable (FM-05/06 NTC short/common-cause, FM-08/09/10/11 comms via TSR tests, FM-14/15/16/17/19 system-level).**

---

## 7. Tool Strategy

### 7.1 Python HIL Framework (Primary)

```python
# Example test structure (pytest)
import pytest
from hil_framework import BmsHil, CellEmulator, CanMonitor

class TestSafetyFunctions:

    def test_hil_sit_010_overvoltage(self, bms: BmsHil):
        """TSR-01: Cell overvoltage detection within FTTI"""
        # Precondition
        bms.set_all_cells(3600)
        bms.request_state("NORMAL")
        bms.wait_state("NORMAL", timeout=10)
        bms.wait_stable(5)

        # Stimulus
        t_start = time.monotonic_ns()
        bms.set_all_cells(2850)  # Above 2800 mV MSL

        # Observation
        bms.wait_state("ERROR", timeout=2)
        t_end = bms.get_contactor_open_time_ns()

        # Pass criteria
        reaction_ms = (t_end - t_start) / 1e6
        assert bms.state == "ERROR"
        assert bms.all_contactors_open()
        assert reaction_ms <= 750, f"FTTI exceeded: {reaction_ms:.1f} ms > 750 ms"

        return reaction_ms  # For statistical reporting
```

### 7.2 Complementary Tools (Recommended to Customer)

| Tool | Purpose | When to Use |
|------|---------|------------|
| **cantools** (Python) | DBC-based CAN encode/decode | Always — integrates into Python framework |
| **CANoe + vTestStudio** | Formal ASPICE SYS.4 evidence | If assessor requires Vector-format reports |
| **gcov/lcov** | Code coverage during HIL | After JTAG integration (PP-15) |
| **Oscilloscope** | Sub-ms timing measurements | For FTTI < 200 ms (TSR-10, TSR-12) |
| **USB relay board** | Needle bed automation | All relay-based fault injection tests |

### 7.3 Python Timing Accuracy

Python `time.monotonic_ns()` resolution is typically 100 ns on Linux. Python GC can add
up to 10 ms jitter. For FTTI measurements:
- **FTTI > 200 ms** (TSR-01/02/04-09/11/13/15): Python timing adequate (10 ms jitter << FTTI)
- **FTTI ≤ 200 ms** (TSR-10, TSR-12): Use hardware timestamp (CAN adapter hardware timestamp or oscilloscope) for sub-ms accuracy

---

*End of Document FOX-SIT-001*
