# ISO 26262-4: Technical Safety Concept (TSC)

| Field               | Value                                                        |
|---------------------|--------------------------------------------------------------|
| Document ID         | FOX-SAF-TSC-001                                              |
| Applicable Standard | ISO 26262:2018 Part 4 — Product Development: System Level    |
| System              | foxBMS 2 Battery Management System v1.10.0                   |
| Item Definition     | Li-ion BMS: 1 string, 1 module, 18s1p, NMC cells 3500 mAh   |
| Date                | 2026-03-21                                                   |
| Status              | Released for Review                                          |
| Related Documents   | FOX-SAF-HARA-001, FOX-SAF-FSC-001, FOX-SAF-FMEA-001         |

---

## 1  Scope

This Technical Safety Concept (TSC) maps each functional safety requirement from the FSC (FOX-SAF-FSC-001) to specific hardware and software elements in the foxBMS 2 system. For each safety mechanism, the document identifies:

- The detection mechanism (DIAG ID, SOA check function, sensor element)
- The diagnostic threshold counter configuration
- The reaction chain (callback → BMS state transition → contactor command)
- The timing budget (detection time + reaction time = FTTI contribution)
- The hardware elements involved in the safety path

---

## 2  System Architecture Overview

### 2.1  Hardware Safety Path

```
┌──────────┐    SPI     ┌──────────┐   GPIO/SPI   ┌──────────────┐
│  Battery  │◄─────────►│   AFE     │◄────────────►│              │
│  Cells    │  (voltage, │ (LTC681x) │              │              │
│  18s1p    │   temp)    └──────────┘              │  TMS570       │
│           │                                      │  Micro-       │
│           │            ┌──────────┐    CAN       │  controller   │
│           │◄──────────►│  IVT     │◄────────────►│              │
│  Current  │  (shunt)   │ Current  │              │  (ARM Cortex  │
│  path     │            │ Sensor   │              │   R4F, dual   │
│           │            └──────────┘              │   core,       │
│           │                                      │   lockstep)   │
└─────┬─────┘            ┌──────────┐   SPI       │              │
      │                  │  SPS     │◄────────────►│              │
      │    ┌──────────┐  │  Smart   │              │              │
      ├───►│Contactor  │◄─┤  Power   │              │              │
      │    │String +   │  │  Switch  │              │              │
      │    └──────────┘  └──────────┘              │              │
      │    ┌──────────┐                            │              │
      ├───►│Contactor  │◄──────────────────────────┤              │
      │    │String -   │  (via SPS)                │              │
      │    └──────────┘                            │              │
      │    ┌──────────┐                            │              │
      └───►│Precharge  │◄──────────────────────────┤              │
           │Contactor  │  (via SPS)                │              │
           └──────────┘                            │              │
                                                   │              │
           ┌──────────┐   SPI                      │              │
           │  SBC     │◄──────────────────────────►│              │
           │ (FS8x)   │  watchdog, Vdd, RSTB       │              │
           └──────────┘                            └──────┬───────┘
                                                          │
           ┌──────────┐   GPIO                            │
           │Interlock │◄──────────────────────────────────┘
           │Loop      │
           └──────────┘
```

### 2.2  Software Safety Path

```
Sensor Acquisition → SOA Check → DIAG Handler → BMS State Machine → Contactor Control
     (1ms/10ms)       (10ms)       (10ms)           (10ms)              (10ms)
```

Detailed call chain:
1. AFE driver acquires cell voltages and temperatures (1 ms task triggers SPI transaction, results available within 1–3 ms)
2. `SOA_CheckCellVoltage()` / `SOA_CheckTemperatures()` / `SOA_CheckCurrent()` called from 10 ms task context
3. SOA check compares measured value against MOL/RSL/MSL thresholds from `soa_cfg.c`
4. If MSL threshold violated: `DIAG_Handler(DIAG_ID_xxx_MSL, DIAG_EVENT_NOT_OK, ...)` called
5. `DIAG_Handler()` increments threshold counter for the DIAG ID
6. When counter reaches configured threshold: FATAL flag set, callback function executed
7. Callback (e.g., `DIAG_ErrorOvervoltage()`) may perform additional actions
8. `BMS_Trigger()` calls `DIAG_IsAnyFatalErrorSet()` every 10 ms
9. If any FATAL flag is set: BMS transitions from current state to `BMS_STATEMACHINE_ERROR`
10. Error state handler commands all contactors open via `CONT_OpenContactor()` → SPS driver

---

## 3  Technical Safety Requirements

### 3.1  TSR-01: Cell Overvoltage Detection and Reaction (FSR-01, ASIL D)

#### 3.1.1  Detection Mechanism

| Parameter              | Value                                                      |
|------------------------|------------------------------------------------------------|
| **Sensor**             | AFE (LTC681x family) — per-cell voltage measurement         |
| **Measurement range**  | 0–5000 mV, 16-bit ADC resolution (~0.1 mV/LSB)            |
| **Measurement rate**   | Every AFE conversion cycle (~1–3 ms per complete scan of 18 cells) |
| **SOA Check Function** | `SOA_CheckCellVoltage()` in `soa_cfg.c`                    |
| **MSL Threshold**      | 2800 mV (BC_VOLTAGE_MAX_MSL in `battery_cell_cfg.h`)       |
| **DIAG ID**            | DIAG_ID_CELL_VOLTAGE_OVERVOLTAGE_MSL                       |
| **DIAG Threshold**     | 50 consecutive events                                       |
| **DIAG Delay**         | 200 ms                                                      |
| **DIAG Severity**      | FATAL                                                       |
| **Callback**           | DIAG_ErrorOvervoltage                                       |

#### 3.1.2  Reaction Chain

1. `SOA_CheckCellVoltage()` detects cell_voltage > 2800 mV
2. Calls `DIAG_Handler(DIAG_ID_CELL_VOLTAGE_OVERVOLTAGE_MSL, DIAG_EVENT_NOT_OK, ...)`
3. DIAG increments threshold counter (0 → 1 → ... → 50)
4. After 50 consecutive NOT_OK events (500 ms at 10 ms period): threshold reached
5. 200 ms debounce delay elapses
6. FATAL flag set for DIAG_ID_CELL_VOLTAGE_OVERVOLTAGE_MSL
7. `DIAG_ErrorOvervoltage()` callback executed (sets SOF flags, updates CAN signals)
8. Next `BMS_Trigger()` call: `DIAG_IsAnyFatalErrorSet()` returns true
9. BMS transitions to BMS_STATEMACHINE_ERROR
10. Error state opens string+, string-, and precharge contactors via SPS

#### 3.1.3  Timing Budget

| Phase               | Duration     | Source                                    |
|----------------------|-------------|-------------------------------------------|
| Sensor acquisition   | 1–3 ms      | AFE SPI transaction time                  |
| SOA check execution  | <1 ms       | Software comparison (negligible)          |
| Threshold accumulation| 500 ms     | 50 × 10 ms task period                    |
| Debounce delay       | 200 ms      | diag_cfg.c delay_ms                       |
| BMS state transition | 10 ms       | Next BMS_Trigger cycle                    |
| Contactor command    | <1 ms       | SPS SPI write                             |
| Contactor mechanical | 20–50 ms    | Relay/contactor opening time              |
| **Total FTTI**       | **~750 ms** | Detection + reaction + actuation          |

#### 3.1.4  Hardware Elements in Safety Path

| Element          | Function                          | Failure Mode Covered By        |
|------------------|-----------------------------------|--------------------------------|
| AFE (LTC681x)   | Cell voltage measurement          | DIAG_ID_AFE_SPI, AFE_COMMUNICATION_INTEGRITY, AFE_MUX, AFE_CONFIG |
| SPI Bus (AFE)    | Data transport AFE ↔ MCU          | DIAG_ID_AFE_SPI (CRC check)   |
| TMS570 MCU       | SOA comparison, DIAG logic, BMS SM| DIAG_ID_SYSTEM_MONITORING, SBC watchdog, lockstep CPU |
| SPS Driver       | Contactor power switching         | SPS feedback (implicit)        |
| Contactors       | Current path interruption         | DIAG_ID_STRING_*_CONTACTOR_FEEDBACK |
| SBC (FS8x)       | Watchdog, power supply supervision| DIAG_ID_SBC_RSTB_ERROR        |

#### 3.1.5  Redundancy Analysis (ASIL D Requirement)

For ASIL D, ISO 26262 requires independence of safety mechanisms. The following redundancy is provided:

- **Primary detection:** AFE per-cell voltage measurement → SOA_CheckCellVoltage → DIAG_ID_CELL_VOLTAGE_OVERVOLTAGE_MSL
- **Secondary detection:** IVT pack voltage (V1) → plausibility check (sum of AFE cells vs. IVT pack voltage) → DIAG_ID_PLAUSIBILITY_PACK_VOLTAGE
- **Tertiary protection:** SBC watchdog timeout (if software hangs due to fault) → MCU reset → contactors open (fail-safe default state)
- **Independence:** AFE and IVT are physically separate devices with separate communication buses (SPI vs. CAN), separate power supplies, and independent measurement principles (direct cell tapping vs. pack-level shunt + ADC)

---

### 3.2  TSR-02: Cell Undervoltage Detection and Reaction (FSR-02, ASIL C)

#### 3.2.1  Detection Mechanism

| Parameter              | Value                                                      |
|------------------------|------------------------------------------------------------|
| **Sensor**             | AFE — per-cell voltage measurement                          |
| **MSL Threshold**      | 1500 mV (BC_VOLTAGE_MIN_MSL in `battery_cell_cfg.h`)       |
| **DIAG ID**            | DIAG_ID_CELL_VOLTAGE_UNDERVOLTAGE_MSL                      |
| **DIAG Threshold**     | 50 consecutive events                                       |
| **DIAG Delay**         | 200 ms                                                      |
| **Callback**           | DIAG_ErrorUndervoltage                                      |

#### 3.2.2  Reaction Chain

Identical structure to TSR-01 with undervoltage-specific callback:
1. `SOA_CheckCellVoltage()` detects cell_voltage < 1500 mV
2. DIAG threshold counter accumulates 50 events over 500 ms
3. 200 ms debounce delay
4. FATAL flag → BMS ERROR → contactors open

#### 3.2.3  Timing Budget

| Phase                  | Duration | Total FTTI |
|------------------------|----------|------------|
| Threshold accumulation | 500 ms   |            |
| Debounce delay         | 200 ms   |            |
| Actuation              | 50 ms    |            |
| **Total**              |          | **750 ms** |

---

### 3.3  TSR-03: Deep Discharge Detection (FSR-03, QM)

| Parameter              | Value                                                      |
|------------------------|------------------------------------------------------------|
| **DIAG ID**            | DIAG_ID_DEEP_DISCHARGE_DETECTED                            |
| **DIAG Threshold**     | 1 event (immediate trigger)                                 |
| **DIAG Delay**         | 100 ms                                                      |
| **Detection**          | Deep discharge flag set by cell monitoring logic when cell voltage is critically low (well below UV cutoff) or when cell SOC indicates irreversible state |
| **Reaction**           | Single event → FATAL → BMS ERROR → contactors open          |
| **FTTI**               | 10 ms + 100 ms + 50 ms = **160 ms**                        |

---

### 3.4  TSR-04: Overcurrent Discharge Detection (FSR-04, ASIL B)

#### 3.4.1  Detection Mechanism

| Parameter              | Value                                                      |
|------------------------|------------------------------------------------------------|
| **Sensor**             | IVT current sensor (Isabellenhuette) via CAN                |
| **Cell-level DIAG ID** | DIAG_ID_OVERCURRENT_DISCHARGE_CELL_MSL                     |
| **Cell-level limit**   | 180000 mA (BC_CURRENT_MAX_DISCHARGE_MSL)                   |
| **String-level DIAG ID**| DIAG_ID_STRING_OVERCURRENT_DISCHARGE_MSL                   |
| **String-level limit** | 2400 mA (BS_MAX_DISCHARGE_CURRENT_MSL)                     |
| **Pack-level DIAG ID** | DIAG_ID_PACK_OVERCURRENT_DISCHARGE_MSL                     |
| **DIAG Threshold**     | 10 consecutive events (all levels)                          |
| **DIAG Delay**         | 100 ms (all levels)                                         |
| **Callback**           | DIAG_ErrorOvercurrentDischarge                              |

#### 3.4.2  Timing Budget

| Phase                  | Duration | Notes                                     |
|------------------------|----------|-------------------------------------------|
| IVT measurement        | ~1 ms    | Current sensor conversion time             |
| CAN transmission       | ~1 ms    | CAN message latency                        |
| SOA check              | <1 ms    | Software comparison                        |
| Threshold accumulation | 100 ms   | 10 × 10 ms task period                    |
| Debounce delay         | 100 ms   | diag_cfg.c delay_ms                        |
| Actuation              | 50 ms    | Contactor opening                          |
| **Total FTTI**         |          | **~250 ms**                                |

#### 3.4.3  Hardware Elements

| Element          | Function                          | Safety Relevance             |
|------------------|-----------------------------------|------------------------------|
| IVT Shunt        | Current-to-voltage conversion     | Primary current measurement  |
| IVT Electronics  | ADC, CAN transmission             | Signal conditioning          |
| CAN Bus          | IVT ↔ MCU data transport          | DIAG_ID_CAN_TIMING monitors bus health |
| TMS570 MCU       | SOA comparison, DIAG logic        | Processing                   |
| SPS + Contactors | Current path interruption         | Actuation                    |

---

### 3.5  TSR-05: Overcurrent Charge Detection (FSR-05, ASIL C)

| Parameter              | Value                                                      |
|------------------------|------------------------------------------------------------|
| **Cell-level DIAG ID** | DIAG_ID_OVERCURRENT_CHARGE_CELL_MSL                        |
| **Cell-level limit**   | 180000 mA (BC_CURRENT_MAX_CHARGE_MSL)                      |
| **String-level DIAG ID**| DIAG_ID_STRING_OVERCURRENT_CHARGE_MSL                      |
| **String-level limit** | 2400 mA (BS_MAX_CHARGE_CURRENT_MSL)                        |
| **Pack-level DIAG ID** | DIAG_ID_PACK_OVERCURRENT_CHARGE_MSL                        |
| **DIAG Threshold**     | 10 consecutive events                                       |
| **DIAG Delay**         | 100 ms                                                      |
| **Callback**           | DIAG_ErrorOvercurrentCharge                                 |
| **FTTI**               | 100 ms + 100 ms + 50 ms = **250 ms**                       |

Detection and reaction chain identical to TSR-04 with charge-direction sign convention.

---

### 3.6  TSR-06: Overtemperature Detection (FSR-06, ASIL C)

#### 3.6.1  Detection Mechanism

| Parameter              | Value                                                      |
|------------------------|------------------------------------------------------------|
| **Sensor**             | 8× NTC thermistors connected via AFE multiplexer            |
| **Charge OT DIAG ID** | DIAG_ID_TEMP_OVERTEMPERATURE_CHARGE_MSL                    |
| **Charge OT limit**   | 45 °C                                                       |
| **Discharge OT DIAG ID**| DIAG_ID_TEMP_OVERTEMPERATURE_DISCHARGE_MSL                 |
| **Discharge OT limit**| 55 °C                                                       |
| **DIAG Threshold**     | 500 consecutive events                                      |
| **DIAG Delay**         | 1000 ms                                                     |
| **Callback**           | DIAG_ErrorOvertemperatureCharge / DIAG_ErrorOvertemperatureDischarge |

#### 3.6.2  Timing Budget

| Phase                  | Duration | Notes                                     |
|------------------------|----------|-------------------------------------------|
| NTC measurement        | ~2 ms    | AFE MUX scan time                          |
| Threshold accumulation | 5000 ms  | 500 × 10 ms task period                   |
| Debounce delay         | 1000 ms  | diag_cfg.c delay_ms                        |
| Actuation              | 50 ms    | Contactor opening                          |
| **Total FTTI**         |          | **~6050 ms (6.05 s)**                      |

#### 3.6.3  Rationale for Extended Detection Time

The 500-event threshold with 1000 ms delay (total 6.05 s FTTI) is justified by:

1. **Thermal inertia:** Cell temperature change is a slow process. The thermal time constant of a pouch/prismatic cell is typically 30–120 s. Temperature cannot change by more than ~1 °C in 6 s under normal operating conditions.
2. **Noise rejection:** NTC measurement through the AFE MUX is susceptible to noise and transient errors. The high threshold count filters out measurement artifacts.
3. **False positive prevention:** In automotive environments with rapid ambient temperature changes (e.g., engine bay heat soak after parking), brief temperature excursions should not trigger unnecessary shutdowns.

---

### 3.7  TSR-07: Undertemperature Detection (FSR-07, ASIL B)

| Parameter              | Value                                                      |
|------------------------|------------------------------------------------------------|
| **Charge UT DIAG ID**  | DIAG_ID_TEMP_UNDERTEMPERATURE_CHARGE_MSL                   |
| **Discharge UT DIAG ID**| DIAG_ID_TEMP_UNDERTEMPERATURE_DISCHARGE_MSL                |
| **Limit**              | -20 °C (both charge and discharge)                          |
| **DIAG Threshold**     | 500 consecutive events                                      |
| **DIAG Delay**         | 1000 ms                                                     |
| **Callback**           | DIAG_ErrorUndertemperatureCharge / DIAG_ErrorUndertemperatureDischarge |
| **FTTI**               | 5000 ms + 1000 ms + 50 ms = **6050 ms (6.05 s)**           |

Same thermal inertia justification as TSR-06 applies. Ambient temperature changes that would push cell temperature through the -20 °C threshold occur over minutes, not seconds.

---

### 3.8  TSR-08: Contactor Feedback Monitoring (FSR-08, ASIL B)

#### 3.8.1  Detection Mechanism

| Parameter              | Value                                                      |
|------------------------|------------------------------------------------------------|
| **String- DIAG ID**    | DIAG_ID_STRING_MINUS_CONTACTOR_FEEDBACK                    |
| **String+ DIAG ID**    | DIAG_ID_STRING_PLUS_CONTACTOR_FEEDBACK                     |
| **Precharge DIAG ID**  | DIAG_ID_PRECHARGE_CONTACTOR_FEEDBACK                       |
| **DIAG Threshold**     | 20 consecutive events (all three)                           |
| **DIAG Delay**         | 100 ms                                                      |
| **Detection principle**| GPIO feedback pin from contactor auxiliary contact compared against SPS commanded state. Mismatch = fault. |

#### 3.8.2  Timing Budget

| Phase                  | Duration | Notes                                     |
|------------------------|----------|-------------------------------------------|
| Feedback GPIO read     | <1 ms    | Direct GPIO sampling                       |
| Threshold accumulation | 200 ms   | 20 × 10 ms task period                    |
| Debounce delay         | 100 ms   | diag_cfg.c delay_ms                        |
| Actuation              | 50 ms    | Open remaining contactors                  |
| **Total FTTI**         |          | **350 ms**                                 |

#### 3.8.3  Welding Detection Logic

The 20-event threshold provides debounce against transient feedback signal glitches (contact bounce, EMC disturbance on feedback wiring). The detection covers two scenarios:

1. **Open-command / closed-feedback (welding):** BMS commands contactor open, but feedback indicates it remains closed. This indicates contact welding.
2. **Close-command / open-feedback (sticking open):** BMS commands contactor closed, but feedback indicates it remains open. This indicates a mechanical failure or wiring fault.

Both cases result in FATAL flag and ERROR state transition.

---

### 3.9  TSR-09: Current Sensor Communication Monitoring (FSR-09, ASIL B)

#### 3.9.1  Detection Mechanism — Multi-Channel Monitoring

| Channel                | DIAG ID                                    | Threshold | Delay    |
|------------------------|--------------------------------------------|-----------|----------|
| Main current           | DIAG_ID_CURRENT_SENSOR_RESPONDING          | 100       | 200 ms   |
| Coulomb counting       | DIAG_ID_CURRENT_SENSOR_CC_RESPONDING       | 100       | 2000 ms  |
| Energy counting        | DIAG_ID_CURRENT_SENSOR_EC_RESPONDING       | 100       | 2000 ms  |
| Voltage channel V1     | DIAG_ID_CURRENT_SENSOR_V1_MEASUREMENT_TIMEOUT | 1      | 100 ms   |
| Voltage channel V2     | DIAG_ID_CURRENT_SENSOR_V2_MEASUREMENT_TIMEOUT | 1      | 100 ms   |
| Voltage channel V3     | DIAG_ID_CURRENT_SENSOR_V3_MEASUREMENT_TIMEOUT | 1      | 100 ms   |

#### 3.9.2  Timing Analysis

**Main current channel (critical for overcurrent protection):**
- T_detection = 100 × 10 ms = 1000 ms
- T_reaction = 200 ms
- T_actuator = 50 ms
- **FTTI = 1250 ms**

**Voltage channels V1/V2/V3 (critical for pack voltage plausibility):**
- T_detection = 1 × 10 ms = 10 ms
- T_reaction = 100 ms
- T_actuator = 50 ms
- **FTTI = 160 ms**

**Coulomb/Energy counting (critical for SOC accuracy):**
- T_detection = 100 × 10 ms = 1000 ms
- T_reaction = 2000 ms
- T_actuator = 50 ms
- **FTTI = 3050 ms**

The longer FTTI for CC/EC channels is acceptable because loss of coulomb counting does not immediately create a hazardous condition — voltage-based SOA checks provide independent protection.

---

### 3.10  TSR-10: AFE Communication Monitoring (ASIL D Support)

The AFE is a critical element in the ASIL D safety path for cell voltage and temperature monitoring. Multiple DIAG IDs monitor AFE health:

| DIAG ID                          | Failure Mode                  | Threshold | Delay  |
|----------------------------------|-------------------------------|-----------|--------|
| DIAG_ID_AFE_SPI                  | SPI communication failure     | 5         | 100 ms |
| DIAG_ID_AFE_COMMUNICATION_INTEGRITY | CRC/PEC error on AFE data   | 5         | 100 ms |
| DIAG_ID_AFE_MUX                  | Temperature MUX failure       | 5         | 100 ms |
| DIAG_ID_AFE_CONFIG               | AFE register config mismatch  | 1         | 100 ms |

**AFE SPI / Communication Integrity FTTI:**
- T_detection = 5 × 10 ms = 50 ms
- T_reaction = 100 ms
- T_actuator = 50 ms
- **FTTI = 200 ms**

**AFE Config FTTI:**
- T_detection = 1 × 10 ms = 10 ms
- T_reaction = 100 ms
- T_actuator = 50 ms
- **FTTI = 160 ms**

AFE configuration mismatch (threshold=1) triggers on a single detection because it indicates either a register corruption (SEU — Single Event Upset) or a hardware fault that could cause incorrect voltage/temperature readings without detectable communication errors.

---

### 3.11  TSR-11: CAN Communication Monitoring

| Parameter              | Value                                                      |
|------------------------|------------------------------------------------------------|
| **DIAG ID**            | DIAG_ID_CAN_TIMING                                        |
| **DIAG Threshold**     | 100 consecutive events                                      |
| **DIAG Delay**         | 200 ms                                                      |
| **Detection principle**| CAN message receive timeout. Expected messages from vehicle controller and/or charger not received within configured period. |
| **FTTI**               | 100 × 10 ms + 200 ms + 50 ms = **1250 ms**                |

Loss of CAN communication means the BMS cannot communicate current limits or warnings to the vehicle controller. The BMS treats this as FATAL because the vehicle controller may request currents beyond safe limits without BMS guidance.

---

### 3.12  TSR-12: System Monitoring and Flash Integrity

| DIAG ID                    | Failure Mode                    | Threshold | Delay | FTTI    |
|----------------------------|---------------------------------|-----------|-------|---------|
| DIAG_ID_SYSTEM_MONITORING  | RTOS task overrun/hang          | 1         | 0 ms  | ~60 ms  |
| DIAG_ID_FLASHCHECKSUM      | Flash memory corruption (SEU)   | 1         | 0 ms  | ~60 ms  |
| DIAG_ID_ALERT_MODE         | SBC alert condition             | 1         | 0 ms  | ~60 ms  |

These system-level monitors have threshold=1 and no delay because they indicate fundamental integrity failures of the safety platform itself:

- **System monitoring:** Uses the TMS570 hardware-supported system monitoring (memory protection, CPU self-test, ECC). A single violation indicates a hardware defect or SEU that compromises all safety functions.
- **Flash checksum:** Runtime CRC verification of program code. A mismatch indicates flash corruption that could cause incorrect program execution.
- **Alert mode:** SBC has entered alert mode due to watchdog failure or voltage supervisor trip.

---

### 3.13  TSR-13: Interlock Loop Monitoring (FSR-10)

| Parameter              | Value                                                      |
|------------------------|------------------------------------------------------------|
| **DIAG ID**            | DIAG_ID_INTERLOCK_FEEDBACK                                 |
| **DIAG Threshold**     | 10 consecutive events                                       |
| **DIAG Delay**         | 100 ms                                                      |
| **Detection principle**| Interlock loop current/voltage monitoring via dedicated GPIO or ADC input. Open loop = fault. |
| **FTTI**               | 10 × 10 ms + 100 ms + 50 ms = **250 ms**                  |

---

### 3.14  TSR-14: SBC Reset Monitoring

| Parameter              | Value                                                      |
|------------------------|------------------------------------------------------------|
| **DIAG ID**            | DIAG_ID_SBC_RSTB_ERROR                                    |
| **DIAG Threshold**     | 1 event                                                     |
| **DIAG Delay**         | 100 ms                                                      |
| **Detection principle**| SBC RSTB (Reset B) pin state monitoring. If SBC asserts reset, the MCU detects this before reset takes effect and logs the event. |
| **FTTI**               | 1 × 10 ms + 100 ms + 50 ms = **160 ms**                   |

---

### 3.15  TSR-15: Current on Open String Detection

| Parameter              | Value                                                      |
|------------------------|------------------------------------------------------------|
| **DIAG ID**            | DIAG_ID_CURRENT_ON_OPEN_STRING                             |
| **DIAG Threshold**     | 10 consecutive events                                       |
| **DIAG Delay**         | 100 ms                                                      |
| **Detection principle**| IVT measures non-zero current while all contactors are commanded open. This indicates a welded contactor, an external fault path, or a current sensor offset error. |
| **FTTI**               | 10 × 10 ms + 100 ms + 50 ms = **250 ms**                  |

---

## 4  Safety Path Timing Summary

| TSR   | DIAG ID(s)                              | Threshold | Task (ms) | T_detect (ms) | Delay (ms) | T_act (ms) | FTTI (ms) |
|-------|-----------------------------------------|-----------|-----------|---------------|------------|------------|-----------|
| TSR-01| CELL_VOLTAGE_OVERVOLTAGE_MSL            | 50        | 10        | 500           | 200        | 50         | 750       |
| TSR-02| CELL_VOLTAGE_UNDERVOLTAGE_MSL           | 50        | 10        | 500           | 200        | 50         | 750       |
| TSR-03| DEEP_DISCHARGE_DETECTED                 | 1         | 10        | 10            | 100        | 50         | 160       |
| TSR-04| OVERCURRENT_DISCHARGE_*_MSL             | 10        | 10        | 100           | 100        | 50         | 250       |
| TSR-05| OVERCURRENT_CHARGE_*_MSL                | 10        | 10        | 100           | 100        | 50         | 250       |
| TSR-06| TEMP_OVERTEMPERATURE_*_MSL              | 500       | 10        | 5000          | 1000       | 50         | 6050      |
| TSR-07| TEMP_UNDERTEMPERATURE_*_MSL             | 500       | 10        | 5000          | 1000       | 50         | 6050      |
| TSR-08| *_CONTACTOR_FEEDBACK                    | 20        | 10        | 200           | 100        | 50         | 350       |
| TSR-09| CURRENT_SENSOR_RESPONDING               | 100       | 10        | 1000          | 200        | 50         | 1250      |
| TSR-10| AFE_SPI / AFE_COMMUNICATION_INTEGRITY   | 5         | 10        | 50            | 100        | 50         | 200       |
| TSR-11| CAN_TIMING                              | 100       | 10        | 1000          | 200        | 50         | 1250      |
| TSR-12| SYSTEM_MONITORING / FLASHCHECKSUM       | 1         | 1         | 1             | 0          | 50         | ~51       |
| TSR-13| INTERLOCK_FEEDBACK                      | 10        | 10        | 100           | 100        | 50         | 250       |
| TSR-14| SBC_RSTB_ERROR                          | 1         | 10        | 10            | 100        | 50         | 160       |
| TSR-15| CURRENT_ON_OPEN_STRING                  | 10        | 10        | 100           | 100        | 50         | 250       |

---

## 5  Hardware Diagnostic Coverage

### 5.1  AFE Diagnostic Coverage (ASIL D)

| Failure Mode             | Detection Mechanism                     | Coverage |
|--------------------------|-----------------------------------------|----------|
| SPI bus stuck/open       | DIAG_ID_AFE_SPI (timeout/CRC)          | High     |
| Data corruption          | DIAG_ID_AFE_COMMUNICATION_INTEGRITY (PEC) | High   |
| MUX channel stuck        | DIAG_ID_AFE_MUX (channel verification)  | Medium   |
| Register SEU             | DIAG_ID_AFE_CONFIG (periodic readback)  | High     |
| ADC offset drift         | Pack voltage plausibility (AFE vs IVT)  | Medium   |
| ADC gain drift           | Pack voltage plausibility (AFE vs IVT)  | Medium   |
| Open sense wire          | AFE built-in open-wire detection        | High     |

### 5.2  IVT Diagnostic Coverage (ASIL B)

| Failure Mode             | Detection Mechanism                     | Coverage |
|--------------------------|-----------------------------------------|----------|
| CAN communication loss   | DIAG_ID_CURRENT_SENSOR_RESPONDING       | High     |
| Current channel failure  | DIAG_ID_CURRENT_SENSOR_CC_RESPONDING    | High     |
| Voltage channel failure  | DIAG_ID_CURRENT_SENSOR_V*_TIMEOUT       | High     |
| Measurement drift        | Plausibility (IVT voltage vs AFE sum)   | Medium   |

### 5.3  Contactor Diagnostic Coverage (ASIL B)

| Failure Mode             | Detection Mechanism                     | Coverage |
|--------------------------|-----------------------------------------|----------|
| Welding (stuck closed)   | Contactor feedback vs. SPS command      | High     |
| Stuck open               | Contactor feedback vs. SPS command      | High     |
| Feedback wire broken     | Current-on-open-string detection        | Medium   |
| SPS driver failure       | Contactor feedback (indirect)           | Medium   |

### 5.4  MCU Diagnostic Coverage (ASIL D)

| Failure Mode             | Detection Mechanism                     | Coverage |
|--------------------------|-----------------------------------------|----------|
| CPU logic fault          | TMS570 lockstep (hardware comparator)   | High     |
| RAM corruption           | ECC (hardware) + periodic test          | High     |
| Flash corruption         | DIAG_ID_FLASHCHECKSUM (CRC)            | High     |
| Task scheduling fault    | DIAG_ID_SYSTEM_MONITORING (RTOS check)  | High     |
| Software hang            | SBC watchdog (FS8x)                     | High     |
| Power supply fault       | SBC voltage supervisor → ALERT_MODE     | High     |

---

## 6  References

| Ref  | Document                                                                  |
|------|---------------------------------------------------------------------------|
| [1]  | ISO 26262:2018 Part 4 — Product Development: System Level                 |
| [2]  | FOX-SAF-HARA-001 — Hazard Analysis and Risk Assessment                    |
| [3]  | FOX-SAF-FSC-001 — Functional Safety Concept                               |
| [4]  | FOX-SAF-FMEA-001 — Software FMEA                                          |
| [5]  | FOX-SAF-FTTI-001 — FTTI Calculation Report                                |
| [6]  | foxBMS v1.10.0 `src/app/engine/diag/diag_cfg.c`                          |
| [7]  | foxBMS v1.10.0 `src/app/application/config/battery_cell_cfg.h`           |
| [8]  | foxBMS v1.10.0 `src/app/application/config/battery_system_cfg.h`         |
| [9]  | foxBMS v1.10.0 `src/app/application/config/soa_cfg.c`                    |

---

## Traceability: TSR → Downstream (SSR / SW-REQ)

<!-- HITL-LOCK START:TSC-TRACE-DOWN -->
| TSR ID | Description | Traces Down To |
|--------|-------------|---------------|
| TSR-001 | Voltage monitoring | SSR-001, SSR-002, SW-REQ-001, SW-REQ-002 |
| TSR-002 | Current monitoring | SSR-005, SSR-006, SW-REQ-010, SW-REQ-011 |
| TSR-003 | Temperature monitoring | SSR-007, SSR-008, SSR-009, SW-REQ-020, SW-REQ-021, SW-REQ-022, SW-REQ-023 |
| TSR-004 | DIAG threshold | SSR-010, SW-REQ-030, SW-REQ-031 |
| TSR-005 | Contactor control | SSR-004, SW-REQ-044 |
| TSR-006 | Precharge check | SSR-004, SW-REQ-042 |
| TSR-007 | Interlock monitoring | SSR-010 |
| TSR-008 | CAN timing | SSR-010, SW-REQ-110 |
| TSR-009 | Current sensor | SSR-010, SW-REQ-111 |
| TSR-010 | SBC watchdog | SSR-010 |
| TSR-011 | Insulation monitoring | SSR-010 |
| TSR-012 | Cell balancing | SW-REQ-080 |
| TSR-013 | SOC estimation | SW-REQ-070 |
| TSR-014 | Redundancy check | SSR-003 |
| TSR-015 | Plausibility check | SSR-003, SW-REQ-060 |
<!-- HITL-LOCK END:TSC-TRACE-DOWN -->
<!-- REVIEW: Dr. K. Richter, FuSa Engineer, 2026-03-21
Status: REVIEWED
Comment: REVIEWED by Dr. K. Richter, FuSa Engineer, 2026-03-21. Safety chain FSR→TSR→SSR mapping verified against DIAG configuration table. All 15 TSRs trace to at least one FSR. All 12 FSRs have at least one TSR child.
-->

## Traceability: TSR → FSR (Upstream)

<!-- HITL-LOCK START:TSC-TRACE-UP -->
| TSR ID | Description | Traces Up To FSR |
|--------|-------------|-----------------|
| TSR-001 | Voltage monitoring | FSR-001, FSR-002, FSR-003 |
| TSR-002 | Current monitoring | FSR-004, FSR-005 |
| TSR-003 | Temperature monitoring | FSR-006, FSR-007 |
| TSR-004 | DIAG threshold | FSR-009 |
| TSR-005 | Contactor control | FSR-008 |
| TSR-006 | Precharge check | FSR-008 |
| TSR-007 | Interlock monitoring | FSR-010 |
| TSR-008 | CAN timing | FSR-009 |
| TSR-009 | Current sensor | FSR-009 |
| TSR-010 | SBC watchdog | FSR-009 |
| TSR-011 | Insulation monitoring | FSR-011 |
| TSR-012 | Cell balancing | FSR-012 |
| TSR-013 | SOC estimation | FSR-012 |
| TSR-014 | Redundancy check | FSR-009 |
| TSR-015 | Plausibility check | FSR-009 |
<!-- HITL-LOCK END:TSC-TRACE-UP -->
<!-- REVIEW: Dr. K. Richter, FuSa Engineer, 2026-03-21
Status: REVIEWED
Comment: REVIEWED by Dr. K. Richter, FuSa Engineer, 2026-03-21. Safety chain FSR→TSR→SSR mapping verified against DIAG configuration table. All 15 TSRs trace to at least one FSR. All 12 FSRs have at least one TSR child.
-->

---

*End of Document FOX-SAF-TSC-001*
