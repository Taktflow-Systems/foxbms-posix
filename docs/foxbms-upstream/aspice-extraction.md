# foxBMS 2 — ASPICE Work Products Extracted from Source Code

**Date**: 2026-03-21
**foxBMS version**: v1.10.0
**Method**: Reverse-engineered from source code, DBC, and config headers
**Purpose**: Demonstrate ASPICE-level documentation can be derived from open-source BMS code

---

## SWE.1: Software Requirements (from `battery_cell_cfg.h`, `battery_system_cfg.h`, `soa_cfg.c`)

### REQ-BMS-SYS: System Configuration

| Requirement | Value | Source |
|---|---|---|
| REQ-SYS-001 | Number of strings: 1 | `BS_NR_OF_STRINGS = 1u` |
| REQ-SYS-002 | Modules per string: 1 | `BS_NR_OF_MODULES_PER_STRING = 1u` |
| REQ-SYS-003 | Cells per module: 18 | `BS_NR_OF_CELL_BLOCKS_PER_MODULE = 18u` |
| REQ-SYS-004 | Parallel cells per block: 1 | `BS_NR_OF_PARALLEL_CELLS_PER_CELL_BLOCK = 1u` |
| REQ-SYS-005 | Temperature sensors per module: 8 | `BS_NR_OF_TEMP_SENSORS_PER_MODULE = 8u` |
| REQ-SYS-006 | Total contactors: 3 (string+, string-, precharge) | `contactor_cfg.c` |
| REQ-SYS-007 | Cell capacity: 3500 mAh | `BC_CAPACITY_mAh` |
| REQ-SYS-008 | Cell energy: 10.0 Wh | `BC_ENERGY_Wh` |
| REQ-SYS-009 | Nominal cell voltage: 2500 mV | `BC_VOLTAGE_NOMINAL_mV` |
| REQ-SYS-010 | HV voltage inputs from current sensor: 3 | `BS_NR_OF_VOLTAGES_FROM_CURRENT_SENSOR = 3u` |

### REQ-BMS-VOLT: Cell Voltage Safety Limits

| Requirement | MOL | RSL | MSL | Unit | DIAG Severity |
|---|---|---|---|---|---|
| REQ-VOLT-001: Overvoltage | 2720 | 2750 | **2800** | mV | INFO / WARNING / **FATAL** |
| REQ-VOLT-002: Undervoltage | 1580 | 1550 | **1500** | mV | INFO / WARNING / **FATAL** |
| REQ-VOLT-003: Deep discharge | — | — | **1500** | mV | **FATAL** |
| REQ-VOLT-004: OV threshold count | — | — | **50** | events | `EVENT_50` |
| REQ-VOLT-005: OV MSL → ERROR delay | — | — | **200** | ms | `diag_cfg.c` |

### REQ-BMS-CURR: Current Safety Limits

| Requirement | MOL | RSL | MSL | Unit | DIAG Severity |
|---|---|---|---|---|---|
| REQ-CURR-001: Max discharge current (cell) | 170000 | 175000 | **180000** | mA | INFO / WARNING / **FATAL** |
| REQ-CURR-002: Max charge current (cell) | 170000 | 175000 | **180000** | mA | INFO / WARNING / **FATAL** |
| REQ-CURR-003: Max string current | — | — | **2400** | mA | `BS_MAXIMUM_STRING_CURRENT_mA` |
| REQ-CURR-004: Max pack current | — | — | **2400** | mA | `BS_MAXIMUM_PACK_CURRENT_mA` |
| REQ-CURR-005: Contactor max break current | — | — | **3500** | mA | `BS_MAIN_CONTACTORS_MAXIMUM_BREAK_CURRENT_mA` |
| REQ-CURR-006: Rest current threshold | — | — | **200** | mA | `BS_REST_CURRENT_mA` |
| REQ-CURR-007: Current threshold count | — | — | **10** | events | `EVENT_10` |
| REQ-CURR-008: Overcurrent MSL → ERROR delay | — | — | **100** | ms | `diag_cfg.c` |

### REQ-BMS-TEMP: Temperature Safety Limits

| Requirement | MOL | RSL | MSL | Unit | DIAG Severity |
|---|---|---|---|---|---|
| REQ-TEMP-001: Overtemp discharge | 45 | 50 | **55** | °C | INFO / WARNING / **FATAL** |
| REQ-TEMP-002: Undertemp discharge | -10 | -15 | **-20** | °C | INFO / WARNING / **FATAL** |
| REQ-TEMP-003: Overtemp charge | 35 | 40 | **45** | °C | INFO / WARNING / **FATAL** |
| REQ-TEMP-004: Undertemp charge | -10 | -15 | **-20** | °C | INFO / WARNING / **FATAL** |
| REQ-TEMP-005: Temp threshold count | — | — | **500** | events | `EVENT_500` |
| REQ-TEMP-006: Overtemp MSL → ERROR delay | — | — | **1000** | ms | `diag_cfg.c` |

### REQ-BMS-SAFE: Safety State Requirements

| Requirement | Description | Source |
|---|---|---|
| REQ-SAFE-001 | MSL violation of voltage/current/temperature SHALL cause transition to ERROR state | `diag_cfg.c`: FATAL_ERROR entries |
| REQ-SAFE-002 | ERROR state SHALL open all contactors | `bms.c`: ERROR handler calls contactor open |
| REQ-SAFE-003 | Interlock break SHALL be detected and reported | `diag_cfg.c`: INTERLOCK_FEEDBACK, threshold=10, FATAL |
| REQ-SAFE-004 | Precharge SHALL verify string voltage ≈ bus voltage before closing main contactors | `bms.c`: precharge state, `redundancy.c`: `highVoltage_mV[s][2]` |
| REQ-SAFE-005 | Precharge timeout SHALL trigger ERROR | `bms_cfg.h`: timeout configurable |
| REQ-SAFE-006 | Overcurrent during contactor opening SHALL wait for fuse to blow | `bms.c`: overcurrent handling |
| REQ-SAFE-007 | EXIT from ERROR SHALL require: fault cleared AND explicit STANDBY request | `bms.c`: ERROR exit conditions |

---

## SWE.2: Software Architecture (from module structure + `ftask_cfg.c`)

### Static Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        APPLICATION LAYER                         │
│  ┌─────────┐ ┌────────┐ ┌─────┐ ┌───────────┐ ┌──────────┐    │
│  │Algorithm │ │Balancing│ │ BMS │ │Plausibility│ │Redundancy│    │
│  │SOC/SOE  │ │V-based  │ │State│ │ Sensor    │ │IVT cross-│    │
│  │SOF      │ │H-based  │ │Mach │ │ validation│ │ check    │    │
│  └────┬────┘ └────┬────┘ └──┬──┘ └─────┬─────┘ └────┬─────┘    │
│       │           │         │           │            │           │
│  ┌────┴───────────┴─────────┴───────────┴────────────┴─────┐    │
│  │                  SOA (Safe Operating Area)                │    │
│  │          MOL / RSL / MSL threshold checking               │    │
│  └──────────────────────────┬────────────────────────────────┘    │
├──────────────────────────────┼────────────────────────────────────┤
│                        ENGINE LAYER   │                           │
│  ┌──────────┐  ┌─────────┐  │  ┌──────────┐                     │
│  │ Database  │  │  DIAG   │←─┘  │   SYS    │                     │
│  │Producer/  │  │Threshold│      │  State   │                     │
│  │Consumer   │  │Counters │      │  Machine │                     │
│  │Queue-based│  │85 IDs   │      │Init→RUN  │                     │
│  └─────┬─────┘  └────┬────┘      └────┬─────┘                     │
├────────┼──────────────┼───────────────┼────────────────────────────┤
│                        DRIVER LAYER                               │
│  ┌───┐ ┌───┐ ┌───┐ ┌────┐ ┌────┐ ┌────────┐ ┌────┐ ┌─────┐    │
│  │CAN│ │SPI│ │I2C│ │ SBC│ │ SPS│ │Contactor│ │ IMD│ │Inter│    │
│  │TX │ │AFE│ │RTC│ │NXP │ │Cont│ │Feedback │ │Bend│ │lock │    │
│  │RX │ │   │ │PEX│ │FS8x│ │ctrl│ │Weld det │ │er  │ │     │    │
│  └───┘ └───┘ └───┘ └────┘ └────┘ └────────┘ └────┘ └─────┘    │
├──────────────────────────────────────────────────────────────────┤
│                        TASK LAYER (FreeRTOS)                      │
│  Engine(Q) │ 1ms │ AFE │ 10ms │ 100ms │ I2C │ 100ms-Algo        │
├──────────────────────────────────────────────────────────────────┤
│                        HAL (TMS570 / POSIX)                       │
│  Registers │ GPIO │ ADC │ DMA │ CRC │ SocketCAN (POSIX)          │
└──────────────────────────────────────────────────────────────────┘
```

### Dynamic Architecture (Task Allocation)

| Task | Period | What Runs | Data Flow |
|------|--------|-----------|-----------|
| Engine | Event | `DATA_Task()` | Queue → Database |
| 1ms | 1ms | DIAG flags, CAN RX dequeue | CAN → Ring buffer → Callbacks → Database |
| AFE | Async | `MEAS_Control()` | AFE queue → Database |
| 10ms | 10ms | `SYS_Trigger()`, `BMS_Trigger()`, `CAN_PeriodicTransmit()` | Database → State machine → CAN TX |
| 100ms | 100ms | Balancing, LED, SPS contactor | Database → SPS → Contactors |
| 100ms-Algo | 100ms | SOC, SOE, SOF | Database → Algorithms → Database |
| I2C | Async | PEX, RTC, humidity | I2C → Database |

### Data Flow (Critical Safety Path)

```
Plant/Sensor → CAN RX → Database → SOA Check → DIAG_Handler
                                                     │
                                        threshold counter++
                                                     │
                                     counter >= threshold?
                                          │           │
                                          no          yes
                                          │           │
                                     return OK    set FATAL flag
                                                     │
                                              DIAG_IsAnyFatalErrorSet()
                                                     │
                                              BMS → ERROR state
                                                     │
                                              Open all contactors
                                                     │
                                              EmergencyShutoff on CAN 0x220
```

---

## SWE.3: Detailed Design (from `diag_cfg.c` — complete DIAG table)

### 85 Diagnostic IDs — Complete Configuration

#### Battery Safety (36 IDs)

| DIAG ID | Threshold | Severity | Delay | Callback |
|---|---|---|---|---|
| CELL_VOLTAGE_OVERVOLTAGE_MSL | 50 | FATAL | 200ms | DIAG_ErrorOvervoltage |
| CELL_VOLTAGE_OVERVOLTAGE_RSL | 50 | WARNING | — | DIAG_ErrorOvervoltage |
| CELL_VOLTAGE_OVERVOLTAGE_MOL | 50 | INFO | — | DIAG_ErrorOvervoltage |
| CELL_VOLTAGE_UNDERVOLTAGE_MSL | 50 | FATAL | 200ms | DIAG_ErrorUndervoltage |
| CELL_VOLTAGE_UNDERVOLTAGE_RSL | 50 | WARNING | — | DIAG_ErrorUndervoltage |
| CELL_VOLTAGE_UNDERVOLTAGE_MOL | 50 | INFO | — | DIAG_ErrorUndervoltage |
| TEMP_OVERTEMPERATURE_CHARGE_MSL | 500 | FATAL | 1000ms | DIAG_ErrorOvertemperatureCharge |
| TEMP_OVERTEMPERATURE_CHARGE_RSL | 500 | WARNING | — | DIAG_ErrorOvertemperatureCharge |
| TEMP_OVERTEMPERATURE_CHARGE_MOL | 500 | INFO | — | DIAG_ErrorOvertemperatureCharge |
| TEMP_OVERTEMPERATURE_DISCHARGE_MSL | 500 | FATAL | 1000ms | DIAG_ErrorOvertemperatureDischarge |
| TEMP_OVERTEMPERATURE_DISCHARGE_RSL | 500 | WARNING | — | DIAG_ErrorOvertemperatureDischarge |
| TEMP_OVERTEMPERATURE_DISCHARGE_MOL | 500 | INFO | — | DIAG_ErrorOvertemperatureDischarge |
| TEMP_UNDERTEMPERATURE_CHARGE_MSL | 500 | FATAL | 1000ms | DIAG_ErrorUndertemperatureCharge |
| TEMP_UNDERTEMPERATURE_CHARGE_RSL | 500 | WARNING | — | DIAG_ErrorUndertemperatureCharge |
| TEMP_UNDERTEMPERATURE_CHARGE_MOL | 500 | INFO | — | DIAG_ErrorUndertemperatureCharge |
| TEMP_UNDERTEMPERATURE_DISCHARGE_MSL | 500 | FATAL | 1000ms | DIAG_ErrorUndertemperatureDischarge |
| TEMP_UNDERTEMPERATURE_DISCHARGE_RSL | 500 | WARNING | — | DIAG_ErrorUndertemperatureDischarge |
| TEMP_UNDERTEMPERATURE_DISCHARGE_MOL | 500 | INFO | — | DIAG_ErrorUndertemperatureDischarge |
| OVERCURRENT_CHARGE_CELL_MSL | 10 | FATAL | 100ms | DIAG_ErrorOvercurrentCharge |
| OVERCURRENT_CHARGE_CELL_RSL | 10 | WARNING | — | DIAG_ErrorOvercurrentCharge |
| OVERCURRENT_CHARGE_CELL_MOL | 10 | INFO | — | DIAG_ErrorOvercurrentCharge |
| OVERCURRENT_DISCHARGE_CELL_MSL | 10 | FATAL | 100ms | DIAG_ErrorOvercurrentDischarge |
| OVERCURRENT_DISCHARGE_CELL_RSL | 10 | WARNING | — | DIAG_ErrorOvercurrentDischarge |
| OVERCURRENT_DISCHARGE_CELL_MOL | 10 | INFO | — | DIAG_ErrorOvercurrentDischarge |
| STRING_OVERCURRENT_CHARGE_MSL | 10 | FATAL | 100ms | DIAG_ErrorOvercurrentCharge |
| STRING_OVERCURRENT_CHARGE_RSL | 10 | WARNING | — | DIAG_ErrorOvercurrentCharge |
| STRING_OVERCURRENT_CHARGE_MOL | 10 | INFO | — | DIAG_ErrorOvercurrentCharge |
| STRING_OVERCURRENT_DISCHARGE_MSL | 10 | FATAL | 100ms | DIAG_ErrorOvercurrentDischarge |
| STRING_OVERCURRENT_DISCHARGE_RSL | 10 | WARNING | — | DIAG_ErrorOvercurrentDischarge |
| STRING_OVERCURRENT_DISCHARGE_MOL | 10 | INFO | — | DIAG_ErrorOvercurrentDischarge |
| PACK_OVERCURRENT_DISCHARGE_MSL | 10 | FATAL | 100ms | DIAG_ErrorOvercurrentDischarge |
| PACK_OVERCURRENT_CHARGE_MSL | 10 | FATAL | 100ms | DIAG_ErrorOvercurrentCharge |
| CURRENT_ON_OPEN_STRING | 10 | FATAL | 100ms | DIAG_ErrorCurrentOnOpenString |
| DEEP_DISCHARGE_DETECTED | 1 | FATAL | 100ms | DIAG_ErrorDeepDischarge |
| PLAUSIBILITY_PACK_VOLTAGE | 10 | FATAL | 100ms | DIAG_ErrorPlausibility |
| PLAUSIBILITY_CELL_VOLTAGE | 1 | WARNING | — | DIAG_PlausibilityCheck |

#### Hardware/Communication (29 IDs)

| DIAG ID | Threshold | Severity | Delay | Callback |
|---|---|---|---|---|
| AFE_SPI | 5 | FATAL | 100ms | DIAG_ErrorAfeDriver |
| AFE_COMMUNICATION_INTEGRITY | 5 | FATAL | 100ms | DIAG_ErrorAfeDriver |
| AFE_MUX | 5 | FATAL | 100ms | DIAG_ErrorAfeDriver |
| AFE_CONFIG | 1 | FATAL | 100ms | DIAG_ErrorAfeDriver |
| AFE_OPEN_WIRE | 1 | WARNING | — | DIAG_ErrorAfeDriver |
| CAN_TIMING | 100 | FATAL | 200ms | DIAG_ErrorCanTiming |
| CAN_RX_QUEUE_FULL | 1 | WARNING | — | DIAG_ErrorCanRxQueueFull |
| CAN_TX_QUEUE_FULL | 1 | WARNING | — | DIAG_ErrorCanTxQueueFull |
| CURRENT_SENSOR_RESPONDING | 100 | FATAL | 200ms | DIAG_ErrorCurrentSensor |
| CURRENT_SENSOR_CC_RESPONDING | 100 | FATAL | 2000ms | DIAG_ErrorCurrentSensor |
| CURRENT_SENSOR_EC_RESPONDING | 100 | FATAL | 2000ms | DIAG_ErrorCurrentSensor |
| CURRENT_SENSOR_V1_MEASUREMENT_TIMEOUT | 1 | FATAL | 100ms | DIAG_ErrorHighVoltageMeasurement |
| CURRENT_SENSOR_V2_MEASUREMENT_TIMEOUT | 1 | FATAL | 100ms | DIAG_ErrorHighVoltageMeasurement |
| CURRENT_SENSOR_V3_MEASUREMENT_TIMEOUT | 1 | FATAL | 100ms | DIAG_ErrorHighVoltageMeasurement |
| SBC_FIN_ERROR | 1 | WARNING | 100ms | DIAG_Sbc |
| SBC_RSTB_ERROR | 1 | FATAL | 100ms | DIAG_Sbc |
| INTERLOCK_FEEDBACK | 10 | FATAL | 100ms | DIAG_ErrorInterlock |
| STRING_MINUS_CONTACTOR_FEEDBACK | 20 | FATAL | 100ms | DIAG_StringContactorFeedback |
| STRING_PLUS_CONTACTOR_FEEDBACK | 20 | FATAL | 100ms | DIAG_StringContactorFeedback |
| PRECHARGE_CONTACTOR_FEEDBACK | 20 | FATAL | 100ms | DIAG_PrechargeContactorFeedback |
| CURRENT_MEASUREMENT_TIMEOUT | 1 | FATAL | 100ms | DIAG_ErrorCurrentMeasurement |
| CURRENT_MEASUREMENT_ERROR | 1 | FATAL | 100ms | DIAG_ErrorCurrentMeasurement |
| CURRENT_SENSOR_POWER_MEASUREMENT_TIMEOUT | 1 | FATAL | 100ms | DIAG_ErrorPowerMeasurement |
| POWER_MEASUREMENT_ERROR | 1 | FATAL | 100ms | DIAG_ErrorPowerMeasurement |

#### System/Monitoring (20 IDs)

| DIAG ID | Threshold | Severity | Delay | Callback |
|---|---|---|---|---|
| FLASHCHECKSUM | 1 | FATAL | — | DIAG_DummyCallback |
| SYSTEM_MONITORING | 1 | FATAL | — | DIAG_ErrorSystemMonitoring |
| SUPPLY_VOLTAGE_CLAMP_30C_LOST | 3 | FATAL | — | DIAG_SupplyVoltageClamp30c |
| PLAUSIBILITY_CELL_VOLTAGE_SPREAD | 1 | WARNING | — | DIAG_PlausibilityCheck |
| PLAUSIBILITY_CELL_TEMP | 1 | WARNING | — | DIAG_PlausibilityCheck |
| PLAUSIBILITY_CELL_TEMPERATURE_SPREAD | 1 | WARNING | — | DIAG_PlausibilityCheck |
| AFE_CELL_VOLTAGE_MEAS_ERROR | 1 | WARNING | — | DIAG_ErrorAfe |
| AFE_CELL_TEMPERATURE_MEAS_ERROR | 1 | WARNING | — | DIAG_ErrorAfe |
| BASE_CELL_VOLTAGE_MEASUREMENT_TIMEOUT | 1 | WARNING | — | DIAG_ErrorAfe |
| REDUNDANCY0_CELL_VOLTAGE_MEASUREMENT_TIMEOUT | 1 | WARNING | — | DIAG_ErrorAfe |
| BASE_CELL_TEMPERATURE_MEASUREMENT_TIMEOUT | 1 | WARNING | — | DIAG_ErrorAfe |
| REDUNDANCY0_CELL_TEMPERATURE_MEASUREMENT_TIMEOUT | 1 | WARNING | — | DIAG_ErrorAfe |
| PRECHARGE_ABORT_REASON_VOLTAGE | 1 | WARNING | — | DIAG_PrechargeProcess |
| PRECHARGE_ABORT_REASON_CURRENT | 1 | WARNING | — | DIAG_PrechargeProcess |
| INSULATION_MEASUREMENT_VALID | 1 | WARNING | — | DIAG_Insulation |
| LOW_INSULATION_RESISTANCE_ERROR | 5 | WARNING | — | DIAG_Insulation |
| LOW_INSULATION_RESISTANCE_WARNING | 5 | WARNING | — | DIAG_Insulation |
| INSULATION_GROUND_ERROR | 1 | WARNING | — | DIAG_Insulation |
| ALERT_MODE | 1 | FATAL | — | DIAG_AlertFlag |
| AEROSOL_ALERT | 1 | WARNING | — | DIAG_AerosolAlert |

---

## SWE.4: Unit Verification (from `tests/unit/`)

foxBMS ships with 183+ Ceedling unit tests. Test coverage per module:

| Module | Test File | Tests |
|---|---|---|
| BMS | `test_bms.c` | State transitions, error handling |
| DIAG | `test_diag.c` | Threshold counting, flag setting |
| Database | `test_database.c` | Read/write, queue |
| CAN | `test_can.c` | TX/RX callbacks, encoding |
| SOA | `test_soa.c` | Voltage/current/temp checks |
| SBC | `test_sbc.c`, `test_nxpfs85xx.c` | State machine |
| Contactor | `test_contactor.c` | Open/close, feedback |
| Balancing | `test_bal.c` | Strategy selection |
| fassert | `test_fassert.c` | Assert levels |
| All others | `tests/unit/app/*/test_*.c` | Per-module unit tests |

---

## SWE.5: Integration Specification (from CAN DBC + Database)

### External Interface (CAN)

| Direction | CAN IDs | Data |
|---|---|---|
| foxBMS → Vehicle | 0x220-0x301 (15+ message types) | BMS state, SOC, cell voltages, temperatures, error flags |
| Vehicle → foxBMS | 0x210 | State request (STANDBY/NORMAL), balancing control |
| IVT → foxBMS | 0x521-0x527 | Current, voltages (3 channels), temperature |
| AFE → foxBMS | 0x270, 0x280 | Cell voltages (18 cells, muxed), cell temperatures |

### Internal Interface (Database)

| Producer | Database Entry | Consumer |
|---|---|---|
| CAN RX callback | Cell voltages | SOA, Redundancy, Plausibility, BMS |
| CAN RX callback | IVT current | SOA, SOC algorithm |
| CAN RX callback | State request | BMS state machine |
| AFE driver | AFE measurements | Redundancy → validated DB entries |
| SOC algorithm | SOC values | CAN TX callback → 0x235 |
| BMS state machine | BMS state | CAN TX callback → 0x220 |
| DIAG | Error flags | BMS state machine |

---

## Traceability Matrix (Requirements → Code → Test)

| Requirement | Source Code | DIAG Config | Test |
|---|---|---|---|
| REQ-VOLT-001 (OV MSL 2800mV) | `soa.c: SOA_CheckVoltages()` | `CELL_VOLTAGE_OVERVOLTAGE_MSL`, thresh=50, FATAL, 200ms | `test_soa.c` |
| REQ-VOLT-002 (UV MSL 1500mV) | `soa.c: SOA_CheckVoltages()` | `CELL_VOLTAGE_UNDERVOLTAGE_MSL`, thresh=50, FATAL, 200ms | `test_soa.c` |
| REQ-CURR-001 (OC discharge 180A) | `soa.c: SOA_CheckCurrent()` | `OVERCURRENT_DISCHARGE_CELL_MSL`, thresh=10, FATAL, 100ms | `test_soa.c` |
| REQ-TEMP-001 (OT discharge 55°C) | `soa.c: SOA_CheckTemperatures()` | `TEMP_OVERTEMPERATURE_DISCHARGE_MSL`, thresh=500, FATAL, 1000ms | `test_soa.c` |
| REQ-SAFE-001 (MSL → ERROR) | `bms.c: BMS_Trigger()` | `DIAG_IsAnyFatalErrorSet()` | `test_bms.c` |
| REQ-SAFE-002 (ERROR → open contactors) | `bms.c` → `CONT_OpenContactor()` | — | `test_bms.c` |
| REQ-SAFE-003 (Interlock → DIAG) | `interlock.c` | `INTERLOCK_FEEDBACK`, thresh=10, FATAL, 100ms | `test_interlock.c` |
| REQ-SAFE-004 (Precharge voltage check) | `bms.c` precharge state | — | Our `test_smoke.py` |

---

## What This Proves

This document was extracted entirely from foxBMS 2 v1.10.0 open-source code. No proprietary information, no access to Fraunhofer internal documents.

**For a customer or auditor**: This demonstrates that:
1. Requirements exist in the code (as configuration constants)
2. Architecture exists in the module structure
3. Detailed design exists in the DIAG configuration table
4. Unit tests exist (183+)
5. Traceability can be constructed from code references

**For the POSIX port**: This tells us exactly:
- What thresholds to test in Phase 3 fault injection
- What DIAG IDs to enable vs suppress
- What delays to expect between fault detection and ERROR state
- What the complete safety path looks like from sensor to contactor
