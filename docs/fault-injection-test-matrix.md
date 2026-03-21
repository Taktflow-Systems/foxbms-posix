# foxBMS POSIX vECU — Fault Injection Test Matrix

## Applicable Standards

| Standard | Requirement | Our Coverage |
|----------|------------|-------------|
| ISO 26262 Part 6 | SW fault injection for ASIL C/D | Full — real diag.c with real thresholds |
| IEC 62619 | Cut-off within 200ms on abnormality | Overcurrent path: 10ms (10 events × 1ms) |
| ISO 26262 Part 5 | System-level fault injection | Via SIL probe override (0x7E0) |

## Configuration (NMC Chemistry — Patched)

### Voltage Thresholds (battery_cell_cfg.h)

| Parameter | MSL | RSL | MOL | Nominal |
|-----------|-----|-----|-----|---------|
| Max voltage (OV) | 4250 mV | 4200 mV | 4150 mV | 3700 mV |
| Min voltage (UV) | 2500 mV | 2600 mV | 2700 mV | 3700 mV |

### Temperature Thresholds (battery_cell_cfg.h, unpatched)

| Parameter | MSL (ddegC) | RSL (ddegC) | MOL (ddegC) |
|-----------|-------------|-------------|-------------|
| Max temp discharge | 550 (55.0°C) | 500 (50.0°C) | 450 (45.0°C) |
| Min temp discharge | -200 (-20.0°C) | -150 (-15.0°C) | -100 (-10.0°C) |
| Max temp charge | 450 (45.0°C) | 400 (40.0°C) | 350 (35.0°C) |
| Min temp charge | -200 (-20.0°C) | -150 (-15.0°C) | -100 (-10.0°C) |

### Current Thresholds

| Parameter | Value |
|-----------|-------|
| Cell max charge/discharge MSL | 180000 mA (180A — not reachable in SIL) |
| String current limit | 15000 mA (15A) — patched from 2400 |
| Pack current limit | 15000 mA × BS_NR_OF_STRINGS — patched from 2400 |
| Rest current | 200 mA |
| Positive = discharge | true (BS_POSITIVE_DISCHARGE_CURRENT) |

### DIAG Threshold Timing

| Fault Type | Threshold | Delay | Events to trip (at 1ms SIL) | Total reaction |
|-----------|-----------|-------|----------------------------|----------------|
| Overvoltage MSL | 50 | 200ms | 50 cycles | ~250ms |
| Undervoltage MSL | 50 | 200ms | 50 cycles | ~250ms |
| Overtemp MSL | 500 | 1000ms | 500 cycles | ~1500ms |
| Undertemp MSL | 500 | 1000ms | 500 cycles | ~1500ms |
| Overcurrent cell MSL | 10 | 100ms | 10 cycles | ~110ms |
| Overcurrent string MSL | 10 | 100ms | 10 cycles | ~110ms |
| Overcurrent pack MSL | 10 | 100ms | 10 cycles | ~110ms |

---

## Enabled DIAG IDs (Software-Checkable)

### Voltage Faults (IDs 18–23)

| Enum | ID | Name | Threshold | Severity | Callback |
|------|-----|------|-----------|----------|----------|
| 18 | CELL_VOLTAGE_OVERVOLTAGE_MSL | OV cell MSL | 50 | FATAL_ERROR | DIAG_ErrorOvervoltage |
| 19 | CELL_VOLTAGE_OVERVOLTAGE_RSL | OV cell RSL | 50 | WARNING | DIAG_ErrorOvervoltage |
| 20 | CELL_VOLTAGE_OVERVOLTAGE_MOL | OV cell MOL | 50 | INFO | DIAG_ErrorOvervoltage |
| 21 | CELL_VOLTAGE_UNDERVOLTAGE_MSL | UV cell MSL | 50 | FATAL_ERROR | DIAG_ErrorUndervoltage |
| 22 | CELL_VOLTAGE_UNDERVOLTAGE_RSL | UV cell RSL | 50 | WARNING | DIAG_ErrorUndervoltage |
| 23 | CELL_VOLTAGE_UNDERVOLTAGE_MOL | UV cell MOL | 50 | INFO | DIAG_ErrorUndervoltage |

### Temperature Faults (IDs 24–35)

| Enum | ID | Name | Threshold | Severity | Callback |
|------|-----|------|-----------|----------|----------|
| 24 | TEMP_OVERTEMPERATURE_CHARGE_MSL | OT charge MSL | 500 | FATAL_ERROR | DIAG_ErrorOvertemperatureCharge |
| 25 | TEMP_OVERTEMPERATURE_CHARGE_RSL | OT charge RSL | 500 | WARNING | DIAG_ErrorOvertemperatureCharge |
| 26 | TEMP_OVERTEMPERATURE_CHARGE_MOL | OT charge MOL | 500 | INFO | DIAG_ErrorOvertemperatureCharge |
| 27 | TEMP_OVERTEMPERATURE_DISCHARGE_MSL | OT discharge MSL | 500 | FATAL_ERROR | DIAG_ErrorOvertemperatureDischarge |
| 28 | TEMP_OVERTEMPERATURE_DISCHARGE_RSL | OT discharge RSL | 500 | WARNING | DIAG_ErrorOvertemperatureDischarge |
| 29 | TEMP_OVERTEMPERATURE_DISCHARGE_MOL | OT discharge MOL | 500 | INFO | DIAG_ErrorOvertemperatureDischarge |
| 30 | TEMP_UNDERTEMPERATURE_CHARGE_MSL | UT charge MSL | 500 | FATAL_ERROR | DIAG_ErrorUndertemperatureCharge |
| 31 | TEMP_UNDERTEMPERATURE_CHARGE_RSL | UT charge RSL | 500 | WARNING | DIAG_ErrorUndertemperatureCharge |
| 32 | TEMP_UNDERTEMPERATURE_CHARGE_MOL | UT charge MOL | 500 | INFO | DIAG_ErrorUndertemperatureCharge |
| 33 | TEMP_UNDERTEMPERATURE_DISCHARGE_MSL | UT discharge MSL | 500 | FATAL_ERROR | DIAG_ErrorUndertemperatureDischarge |
| 34 | TEMP_UNDERTEMPERATURE_DISCHARGE_RSL | UT discharge RSL | 500 | WARNING | DIAG_ErrorUndertemperatureDischarge |
| 35 | TEMP_UNDERTEMPERATURE_DISCHARGE_MOL | UT discharge MOL | 500 | INFO | DIAG_ErrorUndertemperatureDischarge |

### Current Faults (IDs 36–49)

| Enum | ID | Name | Threshold | Severity | Callback |
|------|-----|------|-----------|----------|----------|
| 36 | OVERCURRENT_CHARGE_CELL_MSL | OC charge cell MSL | 10 | FATAL_ERROR | DIAG_ErrorOvercurrentCharge |
| 37 | OVERCURRENT_CHARGE_CELL_RSL | OC charge cell RSL | 10 | WARNING | DIAG_ErrorOvercurrentCharge |
| 38 | OVERCURRENT_CHARGE_CELL_MOL | OC charge cell MOL | 10 | INFO | DIAG_ErrorOvercurrentCharge |
| 39 | OVERCURRENT_DISCHARGE_CELL_MSL | OC discharge cell MSL | 10 | FATAL_ERROR | DIAG_ErrorOvercurrentDischarge |
| 40 | OVERCURRENT_DISCHARGE_CELL_RSL | OC discharge cell RSL | 10 | WARNING | DIAG_ErrorOvercurrentDischarge |
| 41 | OVERCURRENT_DISCHARGE_CELL_MOL | OC discharge cell MOL | 10 | INFO | DIAG_ErrorOvercurrentDischarge |
| 42 | STRING_OVERCURRENT_CHARGE_MSL | OC charge string MSL | 10 | FATAL_ERROR | DIAG_ErrorOvercurrentCharge |
| 43 | STRING_OVERCURRENT_CHARGE_RSL | OC charge string RSL | 10 | WARNING | DIAG_ErrorOvercurrentCharge |
| 44 | STRING_OVERCURRENT_CHARGE_MOL | OC charge string MOL | 10 | INFO | DIAG_ErrorOvercurrentCharge |
| 45 | STRING_OVERCURRENT_DISCHARGE_MSL | OC discharge string MSL | 10 | FATAL_ERROR | DIAG_ErrorOvercurrentDischarge |
| 46 | STRING_OVERCURRENT_DISCHARGE_RSL | OC discharge string RSL | 10 | WARNING | DIAG_ErrorOvercurrentDischarge |
| 47 | STRING_OVERCURRENT_DISCHARGE_MOL | OC discharge string MOL | 10 | INFO | DIAG_ErrorOvercurrentDischarge |
| 48 | PACK_OVERCURRENT_CHARGE_MSL | OC charge pack MSL | 10 | FATAL_ERROR | DIAG_ErrorOvercurrentCharge |
| 49 | PACK_OVERCURRENT_DISCHARGE_MSL | OC discharge pack MSL | 10 | FATAL_ERROR | DIAG_ErrorOvercurrentDischarge |

### Plausibility / CAN Faults (IDs 7–8, 12, 16–17)

| Enum | ID | Name | Threshold | Severity | Callback |
|------|-----|------|-----------|----------|----------|
| 7 | CAN_RX_QUEUE_FULL | CAN RX queue full | 1 | WARNING | DIAG_ErrorCanRxQueueFull |
| 8 | CAN_TX_QUEUE_FULL | CAN TX queue full | 1 | WARNING | DIAG_ErrorCanTxQueueFull |
| 12 | PLAUSIBILITY_CELL_VOLTAGE | Cell V plausibility | 1 | WARNING | DIAG_PlausibilityCheck |
| 15 | PLAUSIBILITY_CELL_TEMP | Cell T plausibility | 1 | WARNING | DIAG_PlausibilityCheck |
| 16 | PLAUSIBILITY_CELL_VOLTAGE_SPREAD | V spread | 1 | WARNING | DIAG_PlausibilityCheck |
| 17 | PLAUSIBILITY_CELL_TEMPERATURE_SPREAD | T spread | 1 | WARNING | DIAG_PlausibilityCheck |

### Precharge Faults (IDs 67–68)

| Enum | ID | Name | Threshold | Severity | Callback |
|------|-----|------|-----------|----------|----------|
| 67 | PRECHARGE_ABORT_REASON_VOLTAGE | Precharge V abort | 1 | WARNING | DIAG_PrechargeProcess |
| 68 | PRECHARGE_ABORT_REASON_CURRENT | Precharge I abort | 1 | WARNING | DIAG_PrechargeProcess |

---

## Fault Injection Test Cases

### Injection Method

All faults injected via SIL probe override CAN (0x7E0) or by modifying plant model output.

| Method | CAN ID | How |
|--------|--------|-----|
| Cell voltage override | 0x7E0 cmd 0x01 | Set cell_id, voltage_mV |
| Temperature override | 0x7E0 cmd 0x03 | Set sensor_id, temp_ddegC |
| Current override | 0x7E0 cmd 0x02 | Set current_mA |
| Plant model direct | 0x270/0x280/0x521 | Change plant model output values |

### Verification Method

| Probe | CAN ID | Content |
|-------|--------|---------|
| DIAG status | 0x7F7 | fault_count (4B), last_id (1B), last_event (1B) |
| DIAG bitmap | 0x7F8 | 64-bit active faults |
| SPS contactor | 0x7F0 | per-channel requested/actual state |
| BMS state | 0x7F9 | sys_state, bms_state |

---

### Category A: Cell Voltage Faults

| Test | Fault | Injection | Threshold | Expected Reaction | Verify |
|------|-------|-----------|-----------|-------------------|--------|
| A.01 | OV single cell step | Cell 0 → 4500 mV (>MSL 4250) | 50 events | FATAL → contactor open → ERROR state | Probe 0x7F8 bit 18 set, 0x7F0 contactors open |
| A.02 | OV single cell ramp | Cell 0 ramp +10 mV/ms from 3700 → 4500 | 50 events | Detect at 4250 crossing, not before | Timestamp first DIAG fault vs injection time |
| A.03 | OV all cells step | All 18 cells → 4500 mV | 50 events | Same as A.01 | Same |
| A.04 | OV RSL warning | Cell 0 → 4210 mV (>RSL 4200, <MSL 4250) | 50 events | RSL flag set, contactors STAY CLOSED | Probe: RSL flag set, BMS stays NORMAL |
| A.05 | OV MOL info | Cell 0 → 4160 mV (>MOL 4150, <RSL 4200) | 50 events | MOL flag only | Probe: MOL flag set |
| A.06 | OV recovery | A.04 → return cell to 3700 mV | 50 OK events | RSL flag clears | Probe: bit 19 clears in 0x7F8 |
| A.07 | UV single cell step | Cell 0 → 2000 mV (<MSL 2500) | 50 events | FATAL → contactor open | Probe 0x7F8 bit 21 set |
| A.08 | UV gradual discharge | SOC → 0% via plant, V_cell → 2400 mV | 50 events | Detect at 2500 crossing | Timestamp |
| A.09 | UV RSL warning | Cell 0 → 2550 mV (<RSL 2600, >MSL 2500) | 50 events | RSL flag, contactors stay | Same as A.04 pattern |
| A.10 | UV recovery | A.09 → return to 3700 mV | 50 OK events | RSL clears | |
| A.11 | Voltage spread | Cell 0=4100 mV, Cell 17=3300 mV (800 mV spread) | 1 event | WARNING: spread plausibility | Probe: bit 16 |
| A.12 | OV intermittent (bounce at threshold) | Cell 0 alternates 4240/4260 mV every 10ms | Should NOT trip | Counter increments then decrements, never reaches 50 | Verify NO contactor open after 5s |
| A.13 | OV edge-of-threshold | Cell 0 = exactly 4250 mV | Depends on >= vs > | Verify correct boundary behavior | |

### Category B: Temperature Faults

| Test | Fault | Injection | Threshold | Expected Reaction | Verify |
|------|-------|-----------|-----------|-------------------|--------|
| B.01 | OT discharge MSL | Temp → 600 ddegC (60°C > MSL 550) | 500 events | FATAL → contactor open | Probe 0x7F8 bit 27 |
| B.02 | OT discharge RSL | Temp → 510 ddegC (51°C > RSL 500, < MSL 550) | 500 events | WARNING flag, contactors stay | |
| B.03 | OT charge MSL | Temp → 460 ddegC (46°C > charge MSL 450), current negative (charge) | 500 events | FATAL → charge path cut | |
| B.04 | UT discharge MSL | Temp → -250 ddegC (-25°C < MSL -200) | 500 events | FATAL → contactor open | Probe 0x7F8 bit 33 |
| B.05 | UT charge MSL | Temp → -250 ddegC, current negative (charge) | 500 events | FATAL → charge cut | |
| B.06 | OT recovery | B.01 → return to 250 ddegC (25°C) | 500 OK events | Fault clears | |
| B.07 | OT ramp | Temp ramp +1 ddegC/10ms from 250 → 600 | 500 events | Detect at 550 crossing | |
| B.08 | Temperature spread | Sensor 0=400 ddegC, Sensor 4=250 ddegC (15°C spread) | 1 event | WARNING: T spread plausibility | Probe bit 17 |
| B.09 | OT intermittent | Temp alternates 540/560 ddegC every 50ms | Should NOT trip (500 threshold) | Counter oscillates, never reaches 500 | |

### Category C: Current Faults

| Test | Fault | Injection | Threshold | Expected Reaction | Verify |
|------|-------|-----------|-----------|-------------------|--------|
| C.01 | OC discharge string MSL | IVT current → +16000 mA (>15000 string limit) | 10 events | FATAL → contactor open in ~10ms | Probe 0x7F8 bit 45 |
| C.02 | OC charge string MSL | IVT current → -16000 mA (charge direction) | 10 events | FATAL → contactor open | Probe bit 42 |
| C.03 | OC discharge pack MSL | Pack current → +16000 mA | 10 events | FATAL → contactor open | Probe bit 49 |
| C.04 | OC charge pack MSL | Pack current → -16000 mA | 10 events | FATAL → contactor open | Probe bit 48 |
| C.05 | OC RSL warning | Current → 14500 mA (below string 15000 MSL but check RSL) | N/A | RSL has DISCARD delay — may not trigger | Check RSL flag |
| C.06 | OC recovery | C.01 → return to 5000 mA | 10 OK events | Fault clears | |
| C.07 | OC step response timing | Inject 16000 mA, measure ms until contactor probe shows open | 10 events | Must be ≤ 110ms (10 events + 100ms delay) | Probe 0x7F0 timestamp |
| C.08 | OC intermittent | Current alternates 14000/16000 every 5ms | Should NOT trip (debounce) | Counter oscillates | |

### Category D: Cascade Faults

| Test | Fault | Injection | Expected Cascade | Verify |
|------|-------|-----------|-----------------|--------|
| D.01 | OV → contactor open → current stops | Cell 0 → 4500 mV | 1. OV detected (50 events) 2. Contactor opens 3. BMS → ERROR 4. Plant sees ERROR → stops current | Full chain via probes |
| D.02 | OC → contactor open → V recovers | Current → 20000 mA | 1. OC detected (10 events) 2. Contactor opens 3. IR drop disappears → V jumps | Verify V probe changes after contactor opens |
| D.03 | OT during charge → contactor open | Temp → 460 ddegC during charge | 1. OT charge (500 events) 2. Charge path cut 3. BMS → ERROR | |

### Category E: Multi-Fault Scenarios

| Test | Faults | Injection | Expected | Verify |
|------|--------|-----------|----------|--------|
| E.01 | OV + OC simultaneous | Cell 0=4500mV AND current=20000mA | First fault to reach threshold triggers contactor | Check which DIAG ID fires first |
| E.02 | OV + OT simultaneous | Cell 0=4500mV AND temp=600ddegC | OV trips first (50 events < 500 events) | Verify OV fires before OT |
| E.03 | All MSL faults at once | V=4500, I=20000, T=600 | All thresholds exceeded, OC first (10 events) | Verify response is not worse than single fault |

### Category F: State Transition Faults

| Test | Fault | When | Expected | Verify |
|------|-------|------|----------|--------|
| F.01 | OV during PRECHARGE | Inject OV while BMS in PRECHARGE state | Precharge aborted → ERROR | BMS never reaches NORMAL |
| F.02 | OC during PRECHARGE | Current spike during precharge | Precharge aborted | |
| F.03 | OV during STANDBY→NORMAL transition | Inject OV at tick when state=STANDBY | BMS goes to ERROR, not NORMAL | |
| F.04 | Fault → recovery → re-enter NORMAL | OV → clear → request NORMAL again | BMS goes NORMAL again (if no latching) | Full cycle test |

### Category G: Injection Profiles

For each of the top 5 faults (OV, UV, OT, UT, OC), test with all profiles:

| Profile | Method | Purpose | Applies to |
|---------|--------|---------|-----------|
| Step | Instant value change | Worst-case latency | All |
| Ramp | +1 unit/ms toward fault | Verify detection threshold | V, T |
| Intermittent | Oscillate around threshold every 10ms | Verify debounce | All |
| Sustained | Hold fault for 30s | Verify contactor stays open | All |
| Recovery | Return to nominal after fault | Verify counter decrement | All |
| Multi-cell | Same fault on cells 0, 5, 10, 17 | Per-cell vs average check | V, T |

---

## Test Execution Summary

| Category | # Tests | Priority |
|----------|---------|----------|
| A: Voltage | 13 | HIGH |
| B: Temperature | 9 | HIGH |
| C: Current | 8 | HIGH |
| D: Cascade | 3 | MEDIUM |
| E: Multi-fault | 3 | MEDIUM |
| F: State transition | 4 | HIGH |
| G: Profile variants | 30 (5 faults × 6 profiles) | MEDIUM |
| **Total** | **70** | |

## Pass/Fail Criteria (per ISO 26262)

1. **FATAL_ERROR faults**: Contactor MUST open within threshold + delay
2. **WARNING faults**: Flag MUST be set, contactor MUST stay closed
3. **Recovery**: Counter MUST decrement on OK events, fault MUST clear
4. **No false positives**: Intermittent faults below threshold MUST NOT trip
5. **Cascade**: Secondary effects MUST be consistent (e.g., contactor open → current stops)
6. **Timing**: Reaction time MUST be measurable via SIL probe timestamps
7. **State machine**: BMS MUST transition to ERROR on FATAL, MUST NOT on WARNING
