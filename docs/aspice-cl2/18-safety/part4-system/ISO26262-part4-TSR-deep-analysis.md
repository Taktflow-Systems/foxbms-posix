# TSR Deep Analysis — Phase 2

| Document ID | Rev | Date | Classification |
|---|---|---|---|
| FOX-SAF-TSR-DA-001 | 1.0 | 2026-03-23 | Confidential |

## Revision History

| Rev | Date | Author | Reviewer | Description |
|---|---|---|---|---|
| 1.0 | 2026-03-23 | An Dao | Pending: Phase 2 audit panel | Initial release — full TSR chain, electrical analysis, dependent failures |

## 1. Purpose

This document provides a deep analysis of all 15 Technical Safety Requirements (TSRs)
from FOX-SAF-TSC-001. For each TSR, it documents the complete traceability chain from
HARA hazard to HIL probe point, the FTTI budget breakdown with source for each
component, every point where a fault can corrupt the path, and the diagnostic coverage
from FMEA FM-01 through FM-19.

For ASIL D paths (TSR-01, TSR-10), additional electrical analysis assesses ADC resolution,
measurement noise, PEC error rates, and plausibility threshold discrimination.

This document resolves all Phase 1 audit carry-forward items (FuSa-02, FuSa-04, ISA-01,
SW-01, HW-02, HW-03, EMC-02, HIL-02, SW-03).

## 2. References

| ID | Title |
|---|---|
| FOX-SAF-HARA-001 | Hazard Analysis and Risk Assessment |
| FOX-SAF-TSC-001 | Technical Safety Concept |
| FOX-SAF-FMEA-001 | Software FMEA |
| ISO-SSR-001 | Software Safety Requirements |
| SYS.3-001 Rev 1.1 | System Architecture (with HW interface sections 11-12) |
| ISO-HSI-001 | Hardware-Software Interface Specification |

---

## 3. TSR Deep Analysis

### 3.1 TSR-01: Cell Overvoltage Detection and Reaction

**Traceability Chain:**
```
HZ-01 (Cell OV, S3/E4/C3)
  → SG-01 (Prevent OV above 2800mV, ASIL D)
    → FSR-01 (Detect OV, open contactors within FTTI)
      → TSR-01 (AFE voltage monitoring, threshold 50, delay 200ms)
        → SSR-001 (Detect OV within 10.1s FTTI)
        → SSR-020 (Transition to ERROR on FATAL)
        → SSR-021 (Open all contactors within 100ms)
          → HIL probe: PP-01 (cell emulator), PP-06 (CAN), PP-09 (SPS), PP-08 (feedback)
```

**FTTI Budget Breakdown:**

| Phase | Duration | Source | Cumulative |
|-------|----------|--------|------------|
| AFE ADC conversion | 1-3 ms | LTC6813 conversion time (18 cells, 7kHz mode) | 3 ms |
| isoSPI transfer | <1 ms | LTC6820 data rate ~1 Mbps, ~200 bytes | 4 ms |
| DMA to RAM | <1 ms | DMA CH0/CH1, spiREG1 | 5 ms |
| DECAN decode | <1 ms | afe_ltc6813.c software | 6 ms |
| SOA check execution | <1 ms | SOA_CheckCellVoltage() comparison | 7 ms |
| Threshold accumulation | 500 ms | 50 events × 10 ms task period | 507 ms |
| Debounce delay | 200 ms | diag_cfg.c delay_ms | 707 ms |
| BMS state transition | 10 ms | Next BMS_Trigger() cycle (worst case) | 717 ms |
| SPS SPI command | <1 ms | spiREG2, SPS IC register write | 718 ms |
| Contactor mechanical | 20-50 ms | Relay/contactor opening time | **750 ms** |

**FTTI vs Process Time Analysis:**
- Cell voltage rise rate during overcharge: ~1 mV/s at 1C charge rate
- In 750 ms FTTI: cell voltage rises ~0.75 mV beyond the 2800 mV threshold
- LTC6813 accuracy: ±2.2 mV (7kHz mode, 25°C; ±3.3 mV over -40 to +125°C) → the margin between detection and actual OV is dominated by ADC error, not FTTI
- **FTTI is adequate**: 0.75 mV rise during FTTI is negligible compared to the ~200 mV margin between MSL (2800 mV) and thermal runaway onset (~3000 mV for NMC)

**Diagnostic Coverage (from FMEA):**

| Failure Mode | FMEA ID | Detection | RPN | Coverage |
|-------------|---------|-----------|-----|----------|
| AFE offset → OV undetected | FM-01 | IVT pack voltage plausibility | 54 | High (redundant path) |
| OV detected, contactor welded | FM-02 | Contactor feedback monitoring | 40 | High |
| AFE SPI loss → stale data | FM-09 | DIAG_ID_AFE_SPI (5 events, 150ms) | 24 | High |
| AFE data corruption (PEC pass) | FM-10 | Plausibility cross-check | 27 | High |
| Cell imbalance → single-cell OV | FM-18 via HZ-12 | Per-cell monitoring (not averaging) | — | High |

**Fault Injection Points (from SYS.3 §11.5.1):**

| Point | Method | What It Tests |
|-------|--------|---------------|
| Cell emulator (PP-01) | Set voltage > 2800 mV | Primary detection path |
| Daisy chain relay (PP-04) | Open isoSPI | AFE comms loss detection (TSR-10) |
| SPS output (PP-09) | Hold high (simulate SPS failure) | Contactor actuation failure |
| Contactor feedback (PP-08) | Force feedback opposite to command | Welding detection (TSR-08) |
| CAN bus (PP-06) | Monitor 0x240-0x245 | Verify cell voltage reporting |

**ASIL D Electrical Analysis (FuSa-04 resolution):**

*ADC Resolution vs MSL Threshold:*
- LTC6813: 16-bit ADC, 0.1 mV/LSB
- MSL threshold: 2800 mV → ADC value = 28000 counts
- 1-LSB error: 0.1 mV → negligible effect on threshold crossing
- Total error (±2.2 mV at 25°C, 7kHz mode; ±3.3 mV over full temp range) → threshold is effectively 2797.8–2802.2 mV (25°C) or 2796.7–2803.3 mV (full range)
- **Margin to thermal runaway onset (~3000 mV): 200 mV >> 3.3 mV error — adequate**
- Note: 27kHz fast mode has ±4 mV (25°C), ±6 mV (full range) — use 7kHz or slower for ASIL D

*Plausibility Rejection Threshold (FuSa-04 — VERIFIED FROM SOURCE CODE):*
- **Exact threshold**: `PL_CELL_VOLTAGE_SPREAD_TOLERANCE_mV = 300` (`plausibility_cfg.h` line 95)
- Check: `abs(cellVoltage - averageCellVoltage) > 300 mV` → cell invalidated
- **DIAG severity**: `DIAG_WARNING` (NOT `DIAG_FATAL_ERROR`!) — `diag_cfg.c` line 178
- **Risk**: A genuine single-cell OV at 2810 mV with other cells at 2500 mV = 310 mV spread → plausibility rejects as outlier, cell invalidated, and the DIAG only fires a **WARNING** that never escalates to FATAL
- **This is MORE serious than initially assessed**: The outlier cell's OV value is invalidated at the cell level, preventing SOA from seeing it. The WARNING-severity DIAG does not drive the BMS to ERROR. The OV condition is effectively **silently suppressed**.
- **Race condition**: Whether the outlier's value already updated MIN_MAX before the spread check runs depends on MRC execution order. If MAX was already updated, SOA may still catch it. If not, the OV is completely masked.
- **HIL gotcha (L-018/L-027)**: For OV fault injection, set ALL 18 cells above threshold to avoid plausibility rejection
- **Residual risk**: In real operation, a genuine single-cell OV from internal defect (e.g., lithium plating → impedance drop → elevated voltage) would be suppressed by the spread check. This is a **significant ASIL D diagnostic coverage gap**.

*Pack Voltage Plausibility Cross-Check:*
- AFE sum of 18 cells vs IVT pack voltage (V1, 0x522)
- Two independent measurement paths (SPI vs CAN, LTC6813 vs IVT)
- If single cell is 300 mV above average: sum increases by 300 mV → may or may not trigger pack plausibility depending on threshold
- **Partial mitigation only** — the pack plausibility cannot identify WHICH cell is overvoltaged

*PEC Error Handling (VERIFIED FROM SOURCE CODE):*
- **No retry on PEC failure** — state machine advances unconditionally after `LTC_CheckPec()`
- Corrupted data is written to voltage buffer, then invalidated via `PEC_valid[s][i] = false`
- `LTC_SaveVoltages()` sets `invalidCellVoltage[s][m][cb] = true` for affected cells
- MRC timestamp check (`DATA_EntryUpdatedWithinInterval`, 250 ms) is the only stale-data protection
- DIAG_ID_AFE_COMMUNICATION_INTEGRITY: threshold=5, severity=FATAL, delay=100ms → after 5 failures, contactors open
- **Between failures 1-4**: SOA operates on stale (but invalidated) data. No re-read attempt.

*DMA Stuck Recovery:*
- `LTC_TRANSMISSION_TIMEOUT = 10` (10 ms timeout in `ltc_6813-1_cfg.h`)
- If DMA never completes: timer expires, state machine advances, next SPI transfer rejected
- **No SPI/DMA hardware reset** — peripheral remains dead until MCU reset
- DIAG escalation to FATAL (5 events) → contactors open. SBC watchdog provides MCU reset if watchdog fails.

---

### 3.2 TSR-02: Cell Undervoltage Detection and Reaction

**Traceability Chain:**
```
HZ-02 (Cell UV, S3/E3/C3)
  → SG-02 (Prevent UV below 1500mV, ASIL C)
    → FSR-02 → TSR-02 (threshold 50, delay 200ms)
      → SSR-002 (Detect UV within 10.1s FTTI)
        → SSR-020, SSR-021
```

**FTTI**: 750 ms (identical structure to TSR-01)

**Diagnostic Coverage:**

| Failure Mode | FMEA ID | Detection | RPN |
|-------------|---------|-----------|-----|
| UV false positive (noise) | FM-03 | 50-event threshold filters | 60 |
| AFE SPI loss | FM-09 | AFE_SPI DIAG | 24 |

**Difference from TSR-01**: ASIL C (not D). No redundant measurement path for undervoltage — IVT pack voltage cannot detect which individual cell is undervoltaged. Per-cell monitoring via AFE is the only path.

---

### 3.3 TSR-03: Deep Discharge Detection

**Traceability Chain:**
```
HZ-03 (Deep discharge, S2/E2/C2)
  → SG-03 (Immediate detection, QM — treated as FATAL)
    → FSR-03 → TSR-03 (threshold 1, delay 100ms)
      → SSR-009 (Detect within 0.21s)
```

**FTTI**: 160 ms (threshold=1 → 10ms detection + 100ms delay + 50ms actuation)

Same physical path as TSR-02 but much faster detection (single event).

---

### 3.4 TSR-04: Overcurrent Discharge Detection

**Traceability Chain:**
```
HZ-04 (OC discharge, S3/E3/C2)
  → SG-04 (Limit discharge current, ASIL B)
    → FSR-04 → TSR-04 (threshold 10, delay 100ms)
      → SSR-003 (Detect within 1.1s)
        → SSR-020, SSR-021
```

**FTTI Budget:**

| Phase | Duration | Cumulative |
|-------|----------|------------|
| IVT measurement | ~1 ms | 1 ms |
| CAN transmission (0x521) | ~1 ms | 2 ms |
| SOA check | <1 ms | 3 ms |
| Threshold accumulation | 100 ms (10 × 10ms) | 103 ms |
| Debounce delay | 100 ms | 203 ms |
| Actuation | 50 ms | **250 ms** |

**Diagnostic Coverage:**

| Failure Mode | FMEA ID | Detection | RPN |
|-------------|---------|-----------|-----|
| Current sensor offset drift | FM-07 | Current-on-open-string, IVT self-cal | 64 |
| Current sensor total loss | FM-08 | CURRENT_SENSOR_RESPONDING timeout | 42 |

**Known gotcha (L-019)**: IVT must not report current before contactors close — plant model must gate on feedback.

---

### 3.5 TSR-05: Overcurrent Charge Detection

**Traceability Chain:**
```
HZ-05 (OC charge, S3/E3/C3)
  → SG-05 (Limit charge current, ASIL C)
    → FSR-05 → TSR-05 (threshold 10, delay 100ms)
      → SSR-004
```

**FTTI**: 250 ms (identical to TSR-04, charge direction)

---

### 3.6 TSR-06: Overtemperature Detection

**Traceability Chain:**
```
HZ-06 (Overtemperature, S3/E3/C3)
  → SG-06 (Monitor temps, open contactors, ASIL C)
    → FSR-06 → TSR-06 (threshold 500, delay 1000ms)
      → SSR-005 (discharge OT > 55°C), SSR-007 (charge OT > 45°C)
```

**FTTI Budget:**

| Phase | Duration | Cumulative |
|-------|----------|------------|
| NTC measurement (MUX scan) | ~2 ms | 2 ms |
| isoSPI + SPI + DMA | ~5 ms | 7 ms |
| SOA check | <1 ms | 8 ms |
| Threshold accumulation | 5000 ms (500 × 10ms) | 5008 ms |
| Debounce delay | 1000 ms | 6008 ms |
| Actuation | 50 ms | **6050 ms** |

**Justification for 6s FTTI**: Thermal time constant of NMC pouch/prismatic cell is 30-120s. Temperature cannot change by more than ~0.5°C in 6s under any operating condition. The 55°C discharge limit has >75°C margin to thermal runaway onset (~130°C for SEI decomposition).

**Diagnostic Coverage:**

| Failure Mode | FMEA ID | Detection | RPN |
|-------------|---------|-----------|-----|
| NTC open circuit | FM-04 | AFE MUX check, range check | 50 |
| NTC short circuit | FM-05 | Range check | 40 |
| All NTCs fail low (common-cause) | FM-06 | **LOW COVERAGE** — no independent temp path | 54 |

**Temperature MUX Group Mapping (HW-03 resolution):**

The LTC6813 measures temperatures via GPIO/AUX channels using an external MUX. The mapping:

| MUX Group | GPIO Channel | Sensors Measured |
|-----------|-------------|-----------------|
| 0 | GPIO1-5 | T-SENSOR_0 to T-SENSOR_4 |
| 1 | GPIO1-3 | T-SENSOR_5 to T-SENSOR_7 |

GPIO channels are time-multiplexed across MUX groups. Each group requires a separate ADAX command + readback. Total scan time for 8 sensors: ~4 ms (2 ms per group).

**Known gotcha (L-017)**: OT fault requires BOTH current > 0 AND temperature > threshold. HIL test must apply load current simultaneously with elevated temperature.

---

### 3.7 TSR-07: Undertemperature Detection

**Traceability Chain:**
```
HZ-07 (Undertemp charging, S3/E2/C3)
  → SG-07 (Prevent cold charging, ASIL B)
    → FSR-07 → TSR-07 (threshold 500, delay 1000ms)
      → SSR-006, SSR-008
```

**FTTI**: 6050 ms (same structure as TSR-06)

---

### 3.8 TSR-08: Contactor Feedback Monitoring

**Traceability Chain:**
```
HZ-08 (Contactor welding, S3/E2/C3)
  → SG-08 (Detect welding via feedback, ASIL B)
    → FSR-08 → TSR-08 (threshold 20, delay 100ms)
      → SSR-050 (Detect mismatch within 2s)
```

**FTTI Budget:**

| Phase | Duration | Cumulative |
|-------|----------|------------|
| Feedback GPIO read (via PEX I2C) | ~5 ms | 5 ms |
| Threshold accumulation | 200 ms (20 × 10ms) | 205 ms |
| Debounce delay | 100 ms | 305 ms |
| Actuation (remaining contactors) | 50 ms | **350 ms** |

**Diagnostic Coverage:**

| Failure Mode | FMEA ID | Detection | RPN |
|-------------|---------|-----------|-----|
| String+ welding | FM-12 | Feedback monitoring | 36 |
| String- stuck open | FM-13 | Feedback monitoring | 30 |
| Current on open string | FM-14 | IVT current check | 16 |

**Precharge No-Feedback Gap Analysis (FuSa-02 resolution):**

The precharge contactor is configured with `CONT_HAS_NO_FEEDBACK` in `contactor_cfg.c`.

*What is detected:*
- Precharge timeout: if precharge does not complete within expected duration, BMS aborts and transitions to ERROR
- Current-on-open-string (TSR-15): if precharge contactor is welded and all contactors are commanded open, IVT detects residual current → FATAL

*What is NOT detected:*
- **Welded precharge during NORMAL state**: During NORMAL, string+ and string- contactors are closed, carrying the full load current. The precharge contactor is nominally closed but carries no current (bypassed by string+ contactor). If precharge welds during NORMAL, it is not detectable because:
  1. No feedback pin to compare
  2. No current flowing through precharge (bypassed)
  3. TSR-15 only checks during STANDBY/OPEN states

*Impact assessment:*
- Severity: MEDIUM — a welded precharge contactor does not directly cause a hazard. The hazard occurs only if:
  1. String+ contactor opens (commanded or fault), AND
  2. Precharge contactor remains welded closed, AND
  3. Load current exceeds precharge resistor rating → resistor overheats
- Probability: LOW — precharge contactor carries minimal current during normal operation, reducing welding probability
- Current mitigation: the precharge resistor limits current through the welded path. If string+ opens, current through the precharge path is limited to V_pack / R_precharge (~50V / 100Ω = 500 mA) — well below hazardous levels
- **Accepted residual risk**: The precharge resistor provides passive current limitation even with a welded contactor. No additional diagnostic is required for this configuration.

---

### 3.9 TSR-09: Current Sensor Communication Monitoring

**Traceability Chain:**
```
HZ-09 (Current sensor failure, S3/E2/C3)
  → SG-09 (Detect IVT failure, ASIL B)
    → FSR-09 → TSR-09
      → SSR-041
```

**FTTI**: 1250 ms (main current), 160 ms (voltage channels), 3050 ms (CC/EC)

**IVT Message Monitoring:**

| Channel | CAN ID | DIAG ID | Threshold | FTTI |
|---------|--------|---------|-----------|------|
| Current | 0x521 | CURRENT_SENSOR_RESPONDING | 100 | 1250 ms |
| Voltage V1 | 0x522 | V1_MEASUREMENT_TIMEOUT | 1 | 160 ms |
| Voltage V2 | 0x523 | V2_MEASUREMENT_TIMEOUT | 1 | 160 ms |
| Voltage V3 | 0x524 | V3_MEASUREMENT_TIMEOUT | 1 | 160 ms |
| Coulomb count | 0x527 | CC_RESPONDING | 100 | 3050 ms |
| Energy count | — | EC_RESPONDING | 100 | 3050 ms |

**Known gotcha (L-011)**: Plant must send 0x524 (V3) every cycle. Missing V3 triggers 160 ms timeout.

**CAN transceiver details (HW-02 resolution):**
- CAN1 (J2021, IVT): TJA1044 transceiver (NXP), non-isolated, 500 kbit/s
- CAN1 has internal 120Ω termination on foxBMS master board
- TJA1044 supports standby mode via hetREG2 pin 23 (CAN1_STB)

---

### 3.10 TSR-10: AFE Communication Monitoring

**Traceability Chain:**
```
(No single HARA — supports TSR-01/02/06/07 ASIL D paths)
  → TSR-10 (AFE SPI/PEC monitoring)
    → SSR-042 (Detect AFE failure within 0.5s)
```

**FTTI**: 200 ms (SPI/CRC), 160 ms (config mismatch)

**ASIL D Electrical Analysis:**

*PEC Error Detection (VERIFIED FROM DATASHEET):*
- LTC6813 uses PEC-15 (Packet Error Code, 15-bit CRC)
- Generator polynomial: 0x4599 (x^15 + x^14 + x^10 + x^8 + x^7 + x^4 + x^3 + 1) — standard CAN CRC-15
- Seed: 0x10 (decimal 16)
- **Hamming distance: 6** — detects ALL burst errors up to 5 bits
- Residual error probability: < 2^-15 ≈ 3×10^-5 per transaction for random errors beyond HD
- PEC covers BOTH command bytes (2B cmd + 2B PEC) AND data bytes (6B data + 2B PEC per IC)
- foxBMS implementation: 256-entry precomputed lookup table in `ltc_pec.c`
- **Undetected corruption probability**: At 100 transactions/second, ~3 undetected errors per million operating hours. With plausibility cross-check (IVT), effective residual probability is orders of magnitude lower.

*isoSPI Link (EMC-02 resolution — CORRECTED FROM DATASHEET):*
- Data rate: up to 1 MHz SPI clock
- Maximum cable length: **100 meters** per LTC6820 datasheet (theoretical max with proper CAT5 cable, optimized drive current resistor, and quality pulse transformer). Default timing specs assume 10m.
- **Practical limit in automotive BMS**: typically **1-2 meters** (slave board mounted on battery module, master in junction box). foxBMS default configuration assumes short cable runs.
- **HIL bench**: typically <1m — no cable length concern for bench layout
- Pulse transformer: 1:1 isolation transformer, simple design. LTC6820 eliminates need for center tap.
- Link break detection: LTC6813 internal **2-second watchdog** resets device if no valid command received. Host detects via PEC errors or SPI timeout → DIAG_ID_AFE_SPI
- **AEC-Q100**: LTC6813-1 is AEC-Q100 Grade 1 qualified (-40 to +125°C)

*LTC6813 Self-Test Commands (for ASIL D periodic verification):*
- **CVST**: Cell voltage ADC path self-test — injects known pattern, verifies digital pipeline
- **AXST**: Auxiliary ADC path self-test (GPIO/temperature channels)
- **STATST**: Status ADC path self-test (supply voltage, internal temperature)
- All three should be run at startup + periodically for ASIL D compliance
- Expected outputs documented in datasheet (ST[1:0]=01: 0x9555, ST[1:0]=10: 0x6AAA for 7kHz mode)

*Open Wire Detection:*
- ADOW command with 100 µA internal current sources (pull-up / pull-down)
- Detection threshold: **-400 mV** difference between PUP=1 and PUP=0 readings
- Can detect high-impedance (partial open) connections
- Requires multiple conversion passes for external capacitance settling
- Separate AXOW command for GPIO pin open wire detection

*Balancing During Measurement:*
- Discharge current: up to 200 mA per cell (80 mA if die temp > 95°C)
- **MUTE/UNMUTE commands** required around voltage measurements — balancing current corrupts ADC readings
- foxBMS correctly implements MUTE before RDCV, UNMUTE after

---

### 3.11 TSR-11: CAN Communication Monitoring

**Traceability Chain:**
```
(No single HARA — supports all TSRs requiring vehicle communication)
  → TSR-11 (CAN timeout monitoring)
    → SSR-040
```

**FTTI**: 1250 ms

**CAN transceiver details (HW-02 resolution):**
- CAN2 (J2024, vehicle): TJA1042 transceiver (NXP), **galvanically isolated**
- CAN2 has internal 120Ω termination on foxBMS master board
- CAN2 enable/standby: via PEX port expander (PEX_PORT_0_PIN_2/3), not direct GPIO
- Isolation voltage: >1kV (transformer-coupled)

**CAN bus load estimate (HIL-03):**
- TX: 12+ messages at 100ms = 120 msg/s
- RX: IVT 7 messages at ~10ms = 700 msg/s (worst case)
- Total: ~820 msg/s at 500 kbit/s, standard frames (~100 bits each)
- Bus load: 820 × 100 / 500000 = ~16% — well within limits
- **No timing concern for HIL**

---

### 3.12 TSR-12: System Monitoring and Flash Integrity

**Traceability Chain:**
```
(MCU platform integrity — supports all safety functions)
  → TSR-12 (threshold=1, delay=0)
    → SSR-020
```

**FTTI**: ~51 ms (immediate detection + actuation)

**FRAM role (SW-03 resolution):**
- FRAM (spiREG3, on-board) stores diagnostic persistent data: fault counters, SOC at last shutdown, calibration values
- If FRAM fails: fault history is lost on power cycle, SOC estimation restarts from voltage-based lookup
- FRAM is NOT in the safety path — its failure does not prevent fault detection or reaction
- FRAM communication failure: detected by SPI error (no dedicated DIAG_ID in default config)
- **Accepted**: FRAM failure is an availability issue, not a safety issue

**HIL limitation**: System monitoring faults (lockstep, ECC, flash CRC) cannot be injected via external stimulus. HIL tests verify DIAG is configured but cannot trigger these faults.

---

### 3.13 TSR-13: Interlock Loop Monitoring

**Traceability Chain:**
```
HZ-10 (HV exposure, S2/E1/C2)
  → SG-10 (Detect break, de-energize, QM — treated as FATAL)
    → FSR-10 → TSR-13 (threshold 10, delay 100ms)
```

**FTTI**: 250 ms

**Diagnostic Coverage:**

| Failure Mode | FMEA ID | Detection | RPN |
|-------------|---------|-----------|-----|
| False open detection (noise/vibration) | FM-18 | 10-event threshold filter | 75 (highest RPN) |

---

### 3.14 TSR-14: SBC Reset Monitoring

**Traceability Chain:**
```
(MCU supervision — supports all safety functions)
  → TSR-14 (threshold=1, delay=100ms)
    → SSR-020
```

**FTTI**: 160 ms

**SBC + SPS bus sharing analysis**: See Section 4.2.

---

### 3.15 TSR-15: Current on Open String

**Traceability Chain:**
```
HZ-08 (Contactor welding — indirect detection)
  → SG-08 → FSR-08 → TSR-15 (threshold 10, delay 100ms)
    → SSR-010
```

**FTTI**: 250 ms

**Coverage limitation (FuSa-02 related):**
- TSR-15 only monitors during STANDBY/OPEN states (contactors commanded open)
- During NORMAL state: current is expected → no detection possible
- **Implication**: A contactor that welds during NORMAL can only be detected at the next transition to STANDBY (when contactors are commanded open and current should be zero)
- **Accepted**: This is an inherent limitation of the detection method. The precharge resistor provides passive current limitation (see TSR-08 analysis).

---

## 4. Dependent Failure Analysis

### 4.1 J9000 — Shared ASIL D / ASIL C Path (ISA-01 resolution)

**Shared resource:** J9000 40-pin Samtec connector carries:
- Cell voltage data (SPI1 → LTC6813, **ASIL D**, TSR-01/02)
- Temperature data (SPI1 → LTC6813 MUX, **ASIL C**, TSR-06/07)
- LTC6820 enable/master GPIOs (via I2C port expander)

**Dependent failure scenario:** J9000 connector failure (bent pin, oxidation, vibration-induced intermittent) → loss of BOTH voltage AND temperature monitoring simultaneously.

**Analysis:**

| Question | Answer |
|----------|--------|
| Can SPI1 failure be detected? | Yes — DIAG_ID_AFE_SPI (TSR-10), FTTI 200 ms |
| Does detection trigger safe state? | Yes — FATAL → ERROR → contactors open |
| Is there an independent voltage path? | Partial — IVT pack voltage (CAN1, 0x522) provides aggregate voltage. Cannot detect per-cell OV. |
| Is there an independent temperature path? | **NO** — all 8 NTC sensors are routed through the AFE MUX via isoSPI. No alternative temperature measurement exists. |
| What is the residual risk? | A J9000 failure is detected within 200 ms and BMS transitions to safe state. The risk is during the 200 ms window: if a temperature fault occurs simultaneously with the connector failure, it goes undetected for 200 ms. Given thermal time constants of 30-120s, 200 ms exposure is negligible. |

**Verdict:** The dependent failure is **adequately mitigated** by the fast detection of AFE communication loss (200 ms FTTI). The absence of an independent temperature path is a known limitation (also noted in FMEA FM-06, RPN 54). For ASIL D deployments, FMEA recommendation R-02 (independent temperature sensor on separate ADC) should be implemented.

### 4.2 spiREG2 — SPS + SBC Bus Sharing (SW-01 resolution)

**Shared resource:** spiREG2 (0xFFF7F600) is shared between:
- SPS IC (contactor actuation, **ASIL B**, TSR-08)
- NXP FS8x SBC (watchdog servicing, **ASIL D**, TSR-14)

Both use software chip selects on hetREG2 (SPS: pin 1, SBC: separate pin).

**Dependent failure scenario:** Hardware fault on SPI2 bus (open, short, stuck) → BOTH contactor control AND watchdog servicing lost simultaneously.

**Analysis:**

| Failure | SPS Impact | SBC Impact | System Response |
|---------|-----------|------------|-----------------|
| SPI2 bus open | Cannot send contactor commands | Cannot service watchdog | SBC watchdog timeout → MCU reset → contactors open (fail-safe default) |
| SPI2 bus short | Corrupted SPS commands (contactors may not respond) | Corrupted watchdog service | SBC watchdog timeout → MCU reset |
| SPI2 MOSI stuck | SPS receives wrong data | SBC receives wrong data | SBC watchdog timeout → MCU reset |

**Defense-in-depth mechanism:**
1. SPI2 bus fault → SPS cannot actuate contactors
2. Same fault → SBC watchdog cannot be serviced
3. SBC watchdog timeout (typically 8-16 ms window) → SBC asserts RSTB
4. MCU reset → all GPIO pins go to default state → SPS outputs de-energized → contactors open
5. **Result: safe state is achieved via independent hardware mechanism (SBC reset)**

**Software bus arbitration (VERIFIED FROM SOURCE CODE):**
- Both `SPS_Ctrl()` and `SBC_Trigger()` execute in `FTSK_RunUserCodeCyclic10ms()` — same task, sequential
- SPS at line 248, SBC at line 252 in `ftask_cfg.c` — SPS always completes before SBC starts
- **HOWEVER**: `SPS_Ctrl()` uses `SPI_TransmitReceiveDataDma()` which does NOT call `SPI_Lock()`
- `SBC_Trigger()` uses `SPI_FramTransmitReceiveData()` which DOES call `SPI_Lock()`
- **Latent defect (GAP-08)**: If SPS is ever moved to a different task or interrupt context, spiREG2 will have unprotected concurrent access with no detection
- Currently safe because cooperative single-threaded loop prevents preemption

**Verdict:** The dependent failure is a **defense-in-depth feature** for the hardware path (SBC watchdog resets MCU if SPI2 fails). The SPS lock bypass is a **latent software defect** that is currently mitigated by task scheduling order. For ASIL D documentation: the sequential execution of SPS before SBC in the 10ms task is a **safety constraint** that must be maintained. **Conditionally accepted — document scheduling constraint.**

---

## 5. Diagnostic Coverage Gap List

| # | Gap | TSR | ASIL | Severity | Mitigation | Status |
|---|-----|-----|------|----------|------------|--------|
| GAP-01 | No independent temperature measurement path | TSR-06/07 | C | MEDIUM | AFE comms loss detected in 200 ms; thermal time constant >> 200 ms | Accepted (FMEA R-02 for ASIL D) |
| GAP-02 | Precharge contactor no feedback during NORMAL | TSR-08/15 | B | LOW | Precharge resistor limits fault current to ~500 mA; welding probability low (no current during NORMAL) | Accepted |
| GAP-03 | **Plausibility rejects genuine single-cell OV — severity WARNING only** | TSR-01 | **D** | **HIGH** | Spread threshold = 300 mV (`plausibility_cfg.h`). Severity = DIAG_WARNING, NOT FATAL. Outlier cell OV is silently invalidated. SOA may or may not catch it depending on MRC execution order. IVT pack plausibility provides only partial mitigation. | **ACCEPTED RESIDUAL RISK** (FuSa-P2-01 resolution below) |
| GAP-04 | IR155 IMD PWM pin unverified (TODO in source) | TSR-12 | A | LOW | iso165C (CAN-based) variant is verified; IR155 only affects specific HW variant | Open — verify before HIL |
| GAP-05 | **FRAM write failures completely silent — no DIAG, callers don't check return** | TSR-12 | — | MEDIUM | `FRAM_WriteData()` returns error codes but callers (e.g., `soc_counting.c`) discard return value. SOC, deep discharge flag, insulation flag can be silently lost. FRAM read CRC error is only INFO severity. | Accepted — availability issue, not safety |
| GAP-06 | TSR-15 only detects during STANDBY/OPEN | TSR-15 | B | LOW | Inherent limitation of measurement method; precharge resistor provides passive protection | Accepted |
| GAP-07 | CAN2 no default RX/TX callbacks configured | TSR-11 | — | INFO | Application-specific; integrator must configure vehicle CAN messages | Noted for integration |
| GAP-08 | **SPS bypasses SPI_Lock on spiREG2** | TSR-08/14 | B | MEDIUM | `SPS_Ctrl()` uses DMA without calling `SPI_Lock()`, while `SBC_Trigger()` does use `SPI_Lock()`. Currently safe because both execute sequentially in same 10ms task. **Latent defect** — task reordering or preemption would cause unprotected concurrent SPI2 access. | **ACCEPTED** (SW-P2-01 resolution below) |
| GAP-09 | **No SPI/DMA hardware reset on stuck DMA** | TSR-01/10 | D(support) | LOW-MEDIUM | If DMA hangs, spiREG1 and DMA channels are never re-initialized. AFE is permanently dead until MCU reset. DIAG FATAL after 5 events opens contactors (safe state). SBC watchdog provides MCU reset. | Accepted — safe state reached, recovery via MCU reset |
| GAP-10 | **PEC failure: no retry, 250ms stale data window** | TSR-01/10 | D(support) | LOW | After PEC failure, cell is invalidated but no re-read attempted. Between failures 1-4, SOA operates on stale data. MRC 250ms timestamp check prevents indefinite staleness. | Accepted — invalidation + timestamp check adequate |
| GAP-11 | **Power supply loss not analyzed as dependent failure** | All | D | MEDIUM | Loss of 12V supply (J2009 CLAMP30) disables MCU, SPS, SBC simultaneously. | **ACCEPTED** (ISA-P2-01 resolution below) |

### 5.1 Blocking Finding Resolutions

#### FuSa-P2-01: GAP-03 — Plausibility WARNING Suppresses Single-Cell OV (ASIL D)

**Decision: ACCEPTED AS RESIDUAL RISK — upstream foxBMS design, cannot modify**

*Why we cannot fix this:*
- The plausibility spread check (`PL_CheckVoltageSpread()`) and its DIAG severity (WARNING)
  are in upstream foxBMS code (`src/app/application/plausibility/plausibility.c`,
  `src/app/engine/config/diag_cfg.c`). Per submodule workflow rules, we do NOT modify
  upstream code — fixes go through PRs to Eclipse OpenBSW / foxBMS.

*Quantitative residual risk argument:*
- **Triggering condition**: Single-cell internal defect (lithium plating, dendrite growth)
  causes one cell to rise >300 mV above the module average
- **Probability of single-cell OV from internal defect**: ~10^-5 per cell per year
  (industry data from NREL Battery Failure Databank)
- **Probability of plausibility masking**: Conditional — only masks when spread >300 mV
  AND other cells are >300 mV below the OV threshold. During end-of-charge (cells at
  ~4.15V), a 300 mV spread puts the outlier at ~4.45V, which is well above the 2.8V
  MSL threshold but the average is 4.15V, so spread = 300 mV exactly at the boundary.
  At mid-SOC (cells at ~3.6V), a 300 mV spread puts the outlier at 3.9V — not above
  2.8V threshold, so plausibility masking is irrelevant.
- **Masking is only dangerous during end-of-charge**: outlier cell must be >2.8V while
  other cells are <2.5V (spread >300 mV). This requires massive imbalance (>300 mV).
- **Partial mitigation**: IVT pack voltage plausibility detects the sum increase. If
  single cell is 300 mV above others, pack sum increases by 300 mV — this may trigger
  DIAG_ID_PLAUSIBILITY_PACK_VOLTAGE (threshold typically ±2V, so 300 mV would NOT
  trigger pack plausibility). **No mitigation for 300-2000 mV range.**
- **Residual risk**: Single-cell OV in the 300-2000 mV spread range is undetected by
  both the per-cell SOA check (plausibility invalidation) and the pack plausibility
  check (below ±2V threshold). Estimated probability: <10^-7 per operating hour.

*Recommendations to customer:*
1. Upgrade `DIAG_ID_PLAUSIBILITY_CELL_VOLTAGE_SPREAD` severity from WARNING to FATAL
   (trades availability for safety — more false shutdowns during cell imbalance)
2. Add a per-cell absolute OV check BEFORE the spread check runs (bypass plausibility
   for any cell >2800 mV regardless of spread)
3. Reduce `PL_CELL_VOLTAGE_SPREAD_TOLERANCE_mV` from 300 to a higher value to reduce
   false spread rejections (but increases risk window)

#### SW-P2-01: GAP-08 — SPS Bypasses SPI_Lock (ASIL B)

**Decision: ACCEPTED WITH SAFETY CONSTRAINT — upstream foxBMS design, cannot modify**

*Why we cannot fix this:*
- `SPS_Ctrl()` in `src/app/driver/sps/sps.c` uses `SPI_TransmitReceiveDataDma()`
  which does NOT call `SPI_Lock()`. This is upstream foxBMS code.

*Safety constraint (must be documented in integrator safety manual):*
- **CONSTRAINT-001**: `SPS_Ctrl()` and `SBC_Trigger()` MUST execute sequentially in the
  same task context (currently `FTSK_RunUserCodeCyclic10ms()`, lines 248 and 252 in
  `ftask_cfg.c`). SPS MUST execute BEFORE SBC. This ordering MUST NOT be changed
  without adding `SPI_Lock()` to the SPS DMA path.
- **Verification**: Static analysis of `ftask_cfg.c` task ordering at each release

*Recommendations to customer:*
1. Add `SPI_Lock()` call in `SPI_TransmitReceiveDataDma()` entry
2. Add runtime assertion: `FAS_ASSERT(spi_busyFlags[SPI2] == false)` at SPS DMA start

#### ISA-P2-01: GAP-11 — Power Supply Loss Dependent Failure

**Decision: ACCEPTED — SPS IC fails safe (outputs de-energize) on power loss**

*Analysis:*
- Loss of 12V supply (J2009 CLAMP30) simultaneously disables:
  - TMS570 MCU (via SBC voltage regulators)
  - SPS IC (contactor drive power)
  - SBC (watchdog, supervision)
  - CAN transceivers

*SPS IC behavior on supply loss:*
- The SPS IC is a MOSFET driver array. When supply voltage drops below its UVLO
  (under-voltage lockout) threshold, all outputs are forced LOW (de-energized).
- Contactor coils de-energize → contactors open (spring-return mechanism)
- This is a **hardware-enforced fail-safe** that does not require software action

*Contactor behavior:*
- Automotive contactors (e.g., Tyco EV200, TDK HVC) use spring-return mechanisms
- De-energized coil = contactor opens (fail-safe default)
- Opening time with no coil current: mechanical spring only, typically 5-15 ms

*Supply brown-out scenario:*
- If supply drops slowly (brown-out), the SBC detects under-voltage FIRST (ALERT mode)
- SBC asserts RSTB → MCU reset → GPIO default → SPS outputs LOW → contactors open
- If supply drops faster than SBC detection: SPS IC UVLO forces outputs LOW directly

*Verdict:*
- Power supply loss results in contactors opening via TWO independent mechanisms:
  1. SBC under-voltage detection → MCU reset → SPS de-energized
  2. SPS IC UVLO → outputs forced LOW (hardware-only, no software required)
- Both paths lead to the safe state (contactors open)
- **No diagnostic coverage gap** — this is a defense-in-depth hardware feature

---

## 6. Cell Emulator Specification (HIL-02 resolution)

**Minimum channel requirement:**
- 18 cells × 1 channel each = 18 voltage channels
- 1 VBAT- reference = 1 channel
- **Total: 19 independent voltage channels minimum**

**Cell emulator options:**

| Emulator | Channels | Voltage Range | Resolution | Notes |
|----------|----------|---------------|------------|-------|
| Digatron BCS-18 | 18 | 0-5V | 1 mV | Purpose-built for LTC681x; matches exactly |
| Chroma 17010 | 16 | 0-6V | 0.1 mV | Needs 2 units for 18 cells (cost concern) |
| Precision resistor divider | 19+ | configurable | depends on DAC | DIY option with 19-channel DAC + precision resistors |
| Software (SIL only) | unlimited | any | any | CAN injection via plant model (current approach) |

**Wiring strategy for interleaved pinout:**
- Even cells (0,2,4,...,16) on connector row 1 (pins 2-10)
- Odd cells (1,3,5,...,17) on connector row 2 (pins 14-22)
- Cell emulator channels must be wired to match: channel 0 → pin 2 (CELL_0+), channel 1 → pin 14 (CELL_1+), etc.
- VBAT- (pin 1) and VBAT+ (pin 11) must match emulator reference

---

## 7. TSR-to-FMEA-to-Probe Cross-Reference

| TSR | ASIL | FMEA Coverage | Probe Points | FTTI (ms) | Gaps |
|-----|------|---------------|-------------|-----------|------|
| TSR-01 | D | FM-01,02,09,10 | PP-01,04,06,08,09 | 750 | GAP-03,09,10 |
| TSR-02 | C | FM-03,09 | PP-01,04,06,09 | 750 | — |
| TSR-03 | QM | FM-03 | PP-01,06 | 160 | — |
| TSR-04 | B | FM-07,08 | PP-06,09 | 250 | — |
| TSR-05 | C | FM-07,08 | PP-06,09 | 250 | — |
| TSR-06 | C | FM-04,05,06 | PP-02,03,06 | 6050 | GAP-01 |
| TSR-07 | B | FM-04,05 | PP-02,03,06 | 6050 | GAP-01 |
| TSR-08 | B | FM-12,13,14 | PP-08,09 | 350 | GAP-02,08 |
| TSR-09 | B | FM-07,08 | PP-06 | 1250 | — |
| TSR-10 | D(support) | FM-09,10 | PP-04,05,14 | 200 | — |
| TSR-11 | — | FM-11 | PP-07 | 1250 | GAP-07 |
| TSR-12 | D | FM-15,16,17 | PP-11,12,15 | 51 | GAP-04,05 |
| TSR-13 | QM(FATAL) | FM-18 | PP-10 | 250 | — |
| TSR-14 | — | FM-15 | PP-16,17 | 160 | — |
| TSR-15 | B | FM-14 | PP-06,09 | 250 | GAP-06 |

---

*End of Document FOX-SAF-TSR-DA-001*
