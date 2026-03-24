# Software Detailed Design

| Document ID | Rev | Date | Classification |
|---|---|---|---|
| SWE.3-001 | 1.0 | 2026-03-21 | Confidential |

## Revision History

| Rev | Date | Author | Reviewer | Description |
|---|---|---|---|---|
| 1.0 | 2026-03-21 | An Dao | L. Fischer | Initial release |

## 1. Purpose

This document provides the detailed design for safety-critical software modules of the
foxBMS 2 POSIX port. It satisfies ASPICE SWE.3 and ISO 26262 Part 6 Clause 8 (software
unit design and implementation). The document focuses on the DIAG module configuration,
the SOA module check functions, and the BMS state machine transitions.

## 2. Scope

Detailed design of three modules:
- DIAG (Diagnostic Handler) -- 85-entry configuration table
- SOA (Safe Operating Area) -- threshold check functions
- BMS (Battery Management State Machine) -- state transitions

## 3. References

| ID | Title |
|---|---|
| [SWE.1-001] | Software Requirements Specification |
| [SWE.2-001] | Software Architecture Description |
| [ISO-SSR-001] | Software Safety Requirements |

## 4. DIAG Module Detailed Design

### 4.1 Overview

The DIAG module maintains a configuration table (`diag_cfg`) with 85 entries. Each
entry defines a diagnostic identifier, its threshold counter limit, severity level,
evaluation delay, and callback function. The `DIAG_Handler()` function is the sole
entry point for reporting diagnostic events.

### 4.2 DIAG Handler Algorithm

```
DIAG_Handler(diagId, event, impact, data):
    entry = diag_cfg[diagId]

    if event == DIAG_EVENT_OK:
        if entry.counter > 0:
            entry.counter -= 1
        return STD_OK

    // event == DIAG_EVENT_NOT_OK
    now = OS_GetTickCount()
    if (now - entry.lastEvaluation) < entry.delay:
        return STD_OK  // debounce: too soon to re-evaluate

    entry.lastEvaluation = now
    entry.counter += 1

    if entry.counter >= entry.threshold:
        entry.fatalFlag = true
        if entry.callback != NULL:
            entry.callback(diagId, event, impact, data)

    return STD_NOT_OK
```

### 4.3 DIAG Configuration Table -- FATAL Entries

The following table lists all 29 diagnostic IDs configured with FATAL severity. These
are the entries that, when their threshold counter is reached, cause the BMS to
transition to ERROR state and open contactors.

Traces to: SW-REQ-030, SW-REQ-031, SW-REQ-035

| # | DIAG ID | Threshold | Severity | Delay (ms) | Traces To |
|---|---|---|---|---|---|
| 1 | CELL_VOLTAGE_OVERVOLTAGE_MSL | 50 | FATAL | 200 | SW-REQ-001 |
| 2 | CELL_VOLTAGE_UNDERVOLTAGE_MSL | 50 | FATAL | 200 | SW-REQ-002 |
| 3 | TEMP_OVERTEMPERATURE_CHARGE_MSL | 500 | FATAL | 1000 | SW-REQ-022 |
| 4 | TEMP_OVERTEMPERATURE_DISCHARGE_MSL | 500 | FATAL | 1000 | SW-REQ-020 |
| 5 | TEMP_UNDERTEMPERATURE_CHARGE_MSL | 500 | FATAL | 1000 | SW-REQ-023 |
| 6 | TEMP_UNDERTEMPERATURE_DISCHARGE_MSL | 500 | FATAL | 1000 | SW-REQ-021 |
| 7 | OVERCURRENT_CHARGE_CELL_MSL | 10 | FATAL | 100 | SW-REQ-011 |
| 8 | OVERCURRENT_DISCHARGE_CELL_MSL | 10 | FATAL | 100 | SW-REQ-010 |
| 9 | STRING_OVERCURRENT_CHARGE_MSL | 10 | FATAL | 100 | SW-REQ-012 |
| 10 | STRING_OVERCURRENT_DISCHARGE_MSL | 10 | FATAL | 100 | SW-REQ-012 |
| 11 | PACK_OVERCURRENT_DISCHARGE_MSL | 10 | FATAL | 100 | SW-REQ-013 |
| 12 | PACK_OVERCURRENT_CHARGE_MSL | 10 | FATAL | 100 | SW-REQ-013 |
| 13 | CURRENT_ON_OPEN_STRING | 10 | FATAL | 100 | SW-REQ-014 |
| 14 | DEEP_DISCHARGE_DETECTED | 1 | FATAL | 100 | SW-REQ-005 |
| 15 | PLAUSIBILITY_PACK_VOLTAGE | 10 | FATAL | 100 | SW-REQ-060 |
| 16 | INTERLOCK_FEEDBACK | 10 | FATAL | 100 | SW-REQ-030 |
| 17 | AFE_SPI | 5 | FATAL | 100 | SW-REQ-030 |
| 18 | AFE_COMMUNICATION_INTEGRITY | 5 | FATAL | 100 | SW-REQ-030 |
| 19 | AFE_MUX | 5 | FATAL | 100 | SW-REQ-030 |
| 20 | AFE_CONFIG | 1 | FATAL | 100 | SW-REQ-030 |
| 21 | CAN_TIMING | 100 | FATAL | 200 | SW-REQ-110 |
| 22 | CURRENT_SENSOR_RESPONDING | 100 | FATAL | 200 | SW-REQ-111 |
| 23 | SBC_RSTB_ERROR | 1 | FATAL | 100 | SW-REQ-030 |
| 24 | STRING_MINUS_CONTACTOR_FEEDBACK | 20 | FATAL | 100 | SW-REQ-044 |
| 25 | STRING_PLUS_CONTACTOR_FEEDBACK | 20 | FATAL | 100 | SW-REQ-044 |
| 26 | PRECHARGE_CONTACTOR_FEEDBACK | 20 | FATAL | 100 | SW-REQ-044 |
| 27 | SYSTEM_MONITORING | 1 | FATAL | 0 | SW-REQ-030 |
| 28 | FLASHCHECKSUM | 1 | FATAL | 0 | SW-REQ-030 |
| 29 | ALERT_MODE | 1 | FATAL | 0 | SW-REQ-030 |

### 4.4 POSIX Port DIAG Adjustments

Of the 85 total DIAG IDs:
- **61 retained** with original FATAL/non-FATAL severity (including all 29 FATAL entries listed above that are software-checkable)
- **24 suppressed** (hardware-dependent entries whose absence would cause false FATAL triggers)

Suppressed categories include hardware-specific watchdog, power supply monitoring, and
physical pin-level diagnostics that have no meaningful analog in the POSIX environment.

### 4.5 Threshold Counter Design Rationale

| DIAG Category | Threshold | Delay | Rationale |
|---|---|---|---|
| Cell voltage (OV/UV) | 50 | 200 ms | High threshold + delay allows transient ADC noise rejection |
| Temperature | 500 | 1000 ms | Thermal events are slow; high threshold prevents nuisance trips |
| Overcurrent | 10 | 100 ms | Current events are fast and dangerous; low threshold for quick response |
| AFE communication | 5 | 100 ms | Communication failures need quick detection but some retry tolerance |
| CAN/sensor timing | 100 | 200 ms | High threshold accommodates bus load variations |
| Contactor feedback | 20 | 100 ms | Moderate threshold for electromechanical bounce rejection |
| Critical system (monitoring, flash, alert) | 1 | 0 | Immediate response required; no debounce |

## 5. SOA Module Detailed Design

### 5.1 Overview

The SOA module implements safe operating area checks for cell voltage, current, and
temperature. It is called from the 100ms task and reads measurement data from the
database, comparing each value against the three-tier threshold structure (MOL, RSL, MSL).

### 5.2 SOA Check Functions

#### 5.2.1 SOA_CheckVoltages

```
SOA_CheckVoltages(pCellVoltages):
    for each cell i in [0..17]:
        v = pCellVoltages->cellVoltage_mV[i]

        // Overvoltage checks (ascending severity)
        if v > 2720:
            DIAG_Handler(CELL_VOLTAGE_OVERVOLTAGE_MOL, NOT_OK, ...)
        if v > 2750:
            DIAG_Handler(CELL_VOLTAGE_OVERVOLTAGE_RSL, NOT_OK, ...)
        if v > 2800:
            DIAG_Handler(CELL_VOLTAGE_OVERVOLTAGE_MSL, NOT_OK, ...)
        else:
            DIAG_Handler(CELL_VOLTAGE_OVERVOLTAGE_MSL, OK, ...)

        // Undervoltage checks (descending severity)
        if v < 1580:
            DIAG_Handler(CELL_VOLTAGE_UNDERVOLTAGE_MOL, NOT_OK, ...)
        if v < 1550:
            DIAG_Handler(CELL_VOLTAGE_UNDERVOLTAGE_RSL, NOT_OK, ...)
        if v < 1500:
            DIAG_Handler(CELL_VOLTAGE_UNDERVOLTAGE_MSL, NOT_OK, ...)
            DIAG_Handler(DEEP_DISCHARGE_DETECTED, NOT_OK, ...)
        else:
            DIAG_Handler(CELL_VOLTAGE_UNDERVOLTAGE_MSL, OK, ...)
```

Traces to: SW-REQ-001 through SW-REQ-005

#### 5.2.2 SOA_CheckCurrents

```
SOA_CheckCurrents(pCurrentData):
    // Cell-level discharge
    if abs(pCurrentData->current_mA) > 170000:
        DIAG_Handler(OVERCURRENT_DISCHARGE_CELL_MOL, NOT_OK, ...)
    if abs(pCurrentData->current_mA) > 175000:
        DIAG_Handler(OVERCURRENT_DISCHARGE_CELL_RSL, NOT_OK, ...)
    if abs(pCurrentData->current_mA) > 180000:
        DIAG_Handler(OVERCURRENT_DISCHARGE_CELL_MSL, NOT_OK, ...)
    else:
        DIAG_Handler(OVERCURRENT_DISCHARGE_CELL_MSL, OK, ...)

    // String-level checks
    if stringCurrent > stringOvercurrentThreshold:
        DIAG_Handler(STRING_OVERCURRENT_DISCHARGE_MSL, NOT_OK, ...)
    if stringCurrent > stringOvercurrentChargeThreshold:
        DIAG_Handler(STRING_OVERCURRENT_CHARGE_MSL, NOT_OK, ...)

    // Pack-level checks
    if packCurrent > packOvercurrentThreshold:
        DIAG_Handler(PACK_OVERCURRENT_DISCHARGE_MSL, NOT_OK, ...)
    if packCurrent > packOvercurrentChargeThreshold:
        DIAG_Handler(PACK_OVERCURRENT_CHARGE_MSL, NOT_OK, ...)

    // Open string current detection
    if contactorsOpen AND abs(current) > restCurrentThreshold:
        DIAG_Handler(CURRENT_ON_OPEN_STRING, NOT_OK, ...)
```

Traces to: SW-REQ-010 through SW-REQ-014

#### 5.2.3 SOA_CheckTemperatures

```
SOA_CheckTemperatures(pTempData, chargingState):
    for each sensor i in [0..7]:
        t = pTempData->cellTemperature_degC[i]

        if chargingState == DISCHARGING:
            // Overtemperature discharge
            if t > 45: DIAG_Handler(TEMP_OVERTEMPERATURE_DISCHARGE_MOL, NOT_OK, ...)
            if t > 50: DIAG_Handler(TEMP_OVERTEMPERATURE_DISCHARGE_RSL, NOT_OK, ...)
            if t > 55: DIAG_Handler(TEMP_OVERTEMPERATURE_DISCHARGE_MSL, NOT_OK, ...)
            else:      DIAG_Handler(TEMP_OVERTEMPERATURE_DISCHARGE_MSL, OK, ...)

            // Undertemperature discharge
            if t < -10: DIAG_Handler(TEMP_UNDERTEMPERATURE_DISCHARGE_MOL, NOT_OK, ...)
            if t < -15: DIAG_Handler(TEMP_UNDERTEMPERATURE_DISCHARGE_RSL, NOT_OK, ...)
            if t < -20: DIAG_Handler(TEMP_UNDERTEMPERATURE_DISCHARGE_MSL, NOT_OK, ...)
            else:       DIAG_Handler(TEMP_UNDERTEMPERATURE_DISCHARGE_MSL, OK, ...)

        if chargingState == CHARGING:
            // Overtemperature charge
            if t > 35: DIAG_Handler(TEMP_OVERTEMPERATURE_CHARGE_MOL, NOT_OK, ...)
            if t > 40: DIAG_Handler(TEMP_OVERTEMPERATURE_CHARGE_RSL, NOT_OK, ...)
            if t > 45: DIAG_Handler(TEMP_OVERTEMPERATURE_CHARGE_MSL, NOT_OK, ...)
            else:      DIAG_Handler(TEMP_OVERTEMPERATURE_CHARGE_MSL, OK, ...)

            // Undertemperature charge
            if t < -10: DIAG_Handler(TEMP_UNDERTEMPERATURE_CHARGE_MOL, NOT_OK, ...)
            if t < -15: DIAG_Handler(TEMP_UNDERTEMPERATURE_CHARGE_RSL, NOT_OK, ...)
            if t < -20: DIAG_Handler(TEMP_UNDERTEMPERATURE_CHARGE_MSL, NOT_OK, ...)
            else:       DIAG_Handler(TEMP_UNDERTEMPERATURE_CHARGE_MSL, OK, ...)
```

Traces to: SW-REQ-020 through SW-REQ-023

## 6. BMS State Machine Detailed Design

### 6.1 State Diagram

```
                    +-------------------+
                    |    STANDBY (5)    |<---------+
                    +--------+----------+          |
                             |                     |
                    CAN 0x210 request               |
                    (NORMAL requested)              |
                             |                     |
                    +--------v----------+          |
                    |  PRECHARGE (6)    |          |
                    +--------+----------+          |
                             |                     |
                    Precharge complete              | Fault cleared
                    (voltage in tolerance)          | AND
                             |                     | STANDBY requested
                    +--------v----------+          |
                    |   NORMAL (7)      |          |
                    +--------+----------+          |
                             |                     |
                    Any FATAL diag                  |
                             |                     |
                    +--------v----------+          |
                    |   ERROR (9)       +----------+
                    | Open contactors   |
                    +-------------------+
```

### 6.2 State Transition Table

| Current State | Event | Guard Condition | Next State | Action | Traces To |
|---|---|---|---|---|---|
| STANDBY | State request via CAN 0x210 | Request == NORMAL | PRECHARGE | Begin precharge sequence | SW-REQ-041 |
| STANDBY | FATAL diag | -- | ERROR | Open all contactors | SW-REQ-043 |
| PRECHARGE | Precharge complete | Voltage within tolerance | NORMAL | Close string+ contactor | SW-REQ-042 |
| PRECHARGE | Precharge timeout | Timeout expired | ERROR | Open all contactors | SW-REQ-043 |
| PRECHARGE | FATAL diag | -- | ERROR | Open all contactors | SW-REQ-043 |
| NORMAL | FATAL diag | -- | ERROR | Open all contactors | SW-REQ-043 |
| NORMAL | State request via CAN 0x210 | Request == STANDBY | STANDBY | Open all contactors | SW-REQ-041 |
| ERROR | Fault cleared + STANDBY request | Both conditions met | STANDBY | Reset error flags | SW-REQ-045 |

### 6.3 BMS_Trigger Implementation

```
BMS_Trigger():
    // Check for FATAL diagnostic -- highest priority
    if DIAG_IsAnyFatalErrorSet():
        if bmsState != ERROR:
            bmsState = ERROR
            CONT_SetContactorState(STRING_PLUS, OPEN)
            CONT_SetContactorState(STRING_MINUS, OPEN)
            CONT_SetContactorState(PRECHARGE, OPEN)
        return

    switch (bmsState):
        case STANDBY:
            request = DATA_Read(STATE_REQUEST)
            if request == NORMAL_REQUESTED:
                bmsState = PRECHARGE
                CONT_SetContactorState(PRECHARGE, CLOSE)
                CONT_SetContactorState(STRING_MINUS, CLOSE)
                prechargeTimer = OS_GetTickCount()

        case PRECHARGE:
            if prechargeVoltageInTolerance():
                CONT_SetContactorState(STRING_PLUS, CLOSE)
                CONT_SetContactorState(PRECHARGE, OPEN)
                bmsState = NORMAL
            elif prechargeTimedOut():
                bmsState = ERROR
                openAllContactors()

        case NORMAL:
            request = DATA_Read(STATE_REQUEST)
            if request == STANDBY_REQUESTED:
                openAllContactors()
                bmsState = STANDBY

        case ERROR:
            if NOT DIAG_IsAnyFatalErrorSet():
                request = DATA_Read(STATE_REQUEST)
                if request == STANDBY_REQUESTED:
                    bmsState = STANDBY
```

Traces to: SW-REQ-040 through SW-REQ-045

### 6.4 Contactor Sequence Timing

| Phase | Action | Duration | Constraint |
|---|---|---|---|
| Precharge start | Close precharge contactor, close string- | Immediate | -- |
| Precharge monitor | Wait for pack voltage to reach string voltage | Configurable timeout | Max 2 seconds |
| Precharge complete | Close string+, open precharge | Immediate | Current < 3500 mA (contactor break limit) |
| Normal disconnect | Open string+, open string-, open precharge | Sequenced 10 ms apart | Break current < 3500 mA |
| Emergency disconnect | Open all simultaneously | Immediate | Safety priority overrides break current limit |

## 7. Data Structures

### 7.1 DIAG Configuration Entry

```c
typedef struct {
    DIAG_ID_e           id;             /* Unique diagnostic identifier */
    uint16_t            threshold;      /* Counter limit before FATAL */
    DIAG_SEVERITY_e     severity;       /* FATAL or non-FATAL */
    uint32_t            delay_ms;       /* Minimum re-evaluation interval */
    DIAG_CALLBACK_f     callback;       /* Optional callback on threshold breach */
    /* Runtime state (not configured, initialized to zero) */
    uint16_t            counter;        /* Current fault count */
    uint32_t            lastEvaluation; /* Tick of last evaluation */
    bool                fatalFlag;      /* True when counter >= threshold */
} DIAG_CFG_s;
```

### 7.2 BMS State

```c
typedef enum {
    BMS_STANDBY   = 5,
    BMS_PRECHARGE = 6,
    BMS_NORMAL    = 7,
    BMS_ERROR     = 9,
} BMS_STATE_e;
```

### 7.3 SYS State

```c
typedef enum {
    SYS_UNINITIALIZED  = 0,
    SYS_INITIALIZATION = 1,
    SYS_INITIALIZED    = 2,
    SYS_IDLE           = 3,
    SYS_RUNNING        = 5,
} SYS_STATE_e;
```

---
*End of Document*
