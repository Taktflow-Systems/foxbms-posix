# SYS.4 System Integration Test Specification — HIL

| Document ID | Rev | Date | Classification |
|---|---|---|---|
| FOX-SIT-001 | 1.0 | 2026-03-23 | Confidential |

## Revision History

| Rev | Date | Author | Reviewer | Description |
|---|---|---|---|---|
| 1.0 | 2026-03-23 | An Dao | Pending: Phase 3 audit panel | Initial release — 50 HIL test cases |

## 1. Purpose

This document specifies the System Integration Test (SIT) cases for the foxBMS 2 BMS,
executed on a Hardware-in-the-Loop (HIL) bench with a custom Python test framework.
Every test case traces to a TSR (FOX-SAF-TSC-001), a signal path (SYS.3 §11.5), and a
fault injection point (SYS.3 §11.6). This satisfies ASPICE SYS.4 and ISO 26262 Part 4
§8 (system integration and testing).

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
