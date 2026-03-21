# Software Architecture Description

| Document ID | Rev | Date | Classification |
|---|---|---|---|
| SWE.2-001 | 1.0 | 2026-03-21 | Confidential |

## Revision History

| Rev | Date | Author | Reviewer | Description |
|---|---|---|---|---|
| 1.0 | 2026-03-21 | An Dao | -- | Initial release |

## 1. Purpose

This document describes the software architecture of the foxBMS 2 POSIX port,
satisfying ASPICE SWE.2 base practices. It defines the static structure (modules and
their dependencies), the dynamic behavior (task scheduling and data flow), and the
interfaces between software components.

## 2. Scope

The architecture encompasses 170+ source files organized into four layers, compiled
for x86-64 with GCC 13.

## 3. References

| ID | Title |
|---|---|
| [SYS.3-001] | System Architecture Description |
| [SWE.1-001] | Software Requirements Specification |
| [SWE.3-001] | Software Detailed Design |
| [ISO-HSI-001] | Hardware-Software Interface Specification |

## 4. Static Architecture

### 4.1 Module Dependency Diagram

```
                        +-------------------+
                        |    main.c         |
                        | (POSIX entry)     |
                        +--------+----------+
                                 |
                        +--------v----------+
                        |    sys.c          |
                        | SYS State Machine |
                        +--------+----------+
                                 |
              +------------------+------------------+
              |                  |                  |
     +--------v------+  +-------v-------+  +-------v--------+
     |   bms.c       |  |  database.c   |  |   diag.c       |
     | BMS State     |  | Data Store    |  | Diagnostic     |
     | Machine       |  |               |  | Handler        |
     +-------+-------+  +-------+-------+  +-------+--------+
             |                  ^                  ^
             |                  |                  |
     +-------v-------+         |                  |
     | contactor.c   |  +------+-------+   +------+-------+
     | Contactor     |  |   soa.c      |   | plausibility |
     | Driver        |  | Safe Op Area |   |    .c        |
     +-------+-------+  +------+-------+   +--------------+
             |                  |
     +-------v-------+  +------v-------+
     |   sps.c       |  | algorithm.c  |
     | Smart Power   |  | SOC/SOE/SOH  |
     | Switch        |  +--------------+
     +-------+-------+
             |                  +---------------+
     +-------v-------+         |  balancing.c  |
     |   HAL / POSIX |         |               |
     |   stubs       |         +---------------+
     +---------------+

     +---------------+  +---------------+  +---------------+
     |   can.c       |  |   spi.c       |  |   i2c.c       |
     | CAN Driver    |  | SPI Driver    |  | I2C Driver    |
     +-------+-------+  +-------+-------+  +-------+-------+
             |                  |                  |
     +-------v-------+  +------v--------+  +------v--------+
     | SocketCAN     |  | POSIX SPI     |  | POSIX I2C     |
     | (Linux)       |  | stub          |  | stub          |
     +---------------+  +---------------+  +---------------+
```

### 4.2 Module Catalog

| Module | Layer | Source Files | Responsibility | Key Dependencies |
|---|---|---|---|---|
| sys | Engine | sys.c, sys.h | System state machine | database, diag |
| bms | Application | bms.c, bms.h | BMS state machine | database, diag, contactor, soa |
| database | Engine | database.c, database.h | Central data store | None (leaf module) |
| diag | Engine | diag.c, diag.h, diag_cfg.c | Diagnostic handler | database |
| soa | Application | soa.c, soa.h, soa_cfg.c | Safe operating area checks | database, diag |
| algorithm | Application | algorithm.c, algorithm.h | SOC/SOE estimation | database |
| balancing | Application | balancing.c, balancing.h | Cell balancing logic | database, sps |
| plausibility | Application | plausibility.c | Measurement cross-checks | database, diag |
| redundancy | Application | redundancy.c | Redundant measurement mgmt | database |
| contactor | Driver | contactor.c, contactor.h | Contactor actuation/feedback | sps, database, diag |
| can | Driver | can.c, can.h, can_cfg.c | CAN communication | database (SocketCAN on POSIX) |
| spi | Driver | spi.c, spi.h | SPI communication | HAL (stub on POSIX) |
| i2c | Driver | i2c.c, i2c.h | I2C communication | HAL (stub on POSIX) |
| sbc | Driver | sbc.c, sbc.h | System Basis Chip | HAL (stub on POSIX) |
| sps | Driver | sps.c, sps.h | Smart Power Switch | HAL (stub on POSIX) |
| imd | Driver | imd.c, imd.h | Insulation monitoring | HAL (stub on POSIX) |
| interlock | Driver | interlock.c, interlock.h | Interlock circuit | HAL (stub on POSIX) |
| HAL stubs | HAL | 80+ files | TMS570 register emulation | RAM buffers |

### 4.3 Design Rules

1. **No upward dependencies**: Lower layers shall not depend on upper layers.
2. **Single writer**: Each database entry has exactly one writing module.
3. **No direct hardware access**: Application and Engine layers access hardware only through the Driver layer.
4. **Uniform diagnostic reporting**: All modules report faults through `DIAG_Handler()`, never through direct state manipulation.

## 5. Dynamic Architecture

### 5.1 Task Execution Sequence (POSIX)

```
Time -->

|-- 1ms tick --|-- 1ms tick --|-- 1ms tick --|-- ...

 ENGINE  1ms  AFE  10ms  100ms  I2C  ALGO
   |      |    |    |      |     |    |
   v      v    v    v      v     v    v
  [E1]  [T1] [A1]  .      .     .    .      <-- tick 0
  [E2]  [T2] [A2]  .      .     .    .      <-- tick 1
  ...   ...  ...   ...    ...   ...  ...
  [E10] [T10][A10][T10m]  .     .    .      <-- tick 9 (10ms fires)
  ...   ...  ...   ...    ...   ...  ...
  [E100][T100][A100][T10m][T100m][I1][AL1]  <-- tick 99 (100ms fires)
```

### 5.2 Interrupt-Free Model

The POSIX port has no hardware interrupts. All processing is synchronous within the
cooperative loop. This simplifies concurrency analysis: there are no race conditions
or priority inversions to consider.

### 5.3 Data Flow: Measurement to Safety Action

| Step | Module | Action | Timing |
|---|---|---|---|
| 1 | AFE Task | Read cell voltages and temperatures via SPI (stub returns configured values) | Async |
| 2 | AFE Driver | Write measurements to Database[CELL_VOLTAGE], Database[CELL_TEMPERATURE] | Async |
| 3 | CAN Driver | Receive IVT current frames from SocketCAN, write to Database[CURRENT] | 10 ms |
| 4 | SOA | Read database entries, compare against MOL/RSL/MSL thresholds | 100 ms |
| 5 | SOA | On violation: call DIAG_Handler(event_id) | 100 ms |
| 6 | DIAG | Increment threshold counter; if >= threshold, set FATAL flag | 100 ms |
| 7 | BMS | Read DIAG flags; on FATAL, transition to ERROR | 100 ms |
| 8 | Contactor | In ERROR state, open string+, string-, precharge contactors | 100 ms |

### 5.4 Data Flow: State Request to Contactor Actuation

| Step | Module | Action | Timing |
|---|---|---|---|
| 1 | CAN Driver | Receive state request from CAN ID 0x210 | 10 ms |
| 2 | CAN Driver | Write requested state to Database[STATE_REQUEST] | 10 ms |
| 3 | BMS | Read Database[STATE_REQUEST], validate transition | 100 ms |
| 4 | BMS | If valid: update BMS state, command contactor sequence | 100 ms |
| 5 | Contactor | Actuate contactors in sequence (precharge, string-, string+) | 1 ms ticks |

## 6. Interface Definitions

### 6.1 Database API

```c
/* Write a database entry (single-writer only) */
STD_RETURN_TYPE_e DATA_Write_1_DataBlock(DATA_BLOCK_HEADER_s *pDataBlockHeader);

/* Read a database entry (any module may read) */
STD_RETURN_TYPE_e DATA_Read_1_DataBlock(DATA_BLOCK_HEADER_s *pDataBlockHeader);
```

### 6.2 DIAG API

```c
/* Report a diagnostic event */
STD_RETURN_TYPE_e DIAG_Handler(
    DIAG_ID_e       diagId,
    DIAG_EVENT_e    event,       /* DIAG_EVENT_OK or DIAG_EVENT_NOT_OK */
    DIAG_IMPACT_e   impact,
    uint32_t        data
);

/* Check if any FATAL flag is set */
bool DIAG_IsAnyFatalErrorSet(void);
```

### 6.3 BMS API

```c
/* Get current BMS state */
BMS_STATE_e BMS_GetState(void);

/* BMS state machine trigger (called from 100ms task) */
void BMS_Trigger(void);
```

### 6.4 Contactor API

```c
/* Request contactor state */
STD_RETURN_TYPE_e CONT_SetContactorState(
    CONT_NAMES_e    contactor,
    CONT_STATE_e    requestedState
);

/* Get contactor feedback */
CONT_STATE_e CONT_GetContactorFeedback(CONT_NAMES_e contactor);
```

### 6.5 CAN API (POSIX SocketCAN)

```c
/* Initialize SocketCAN interface */
STD_RETURN_TYPE_e CAN_Initialize(const char *interface);  /* e.g., "vcan0" */

/* Transmit a CAN frame */
STD_RETURN_TYPE_e CAN_Send(uint32_t id, const uint8_t *data, uint8_t dlc);

/* Receive a CAN frame (non-blocking) */
STD_RETURN_TYPE_e CAN_Receive(uint32_t *id, uint8_t *data, uint8_t *dlc);
```

## 7. Resource Budgets (POSIX Target)

| Resource | Budget | Notes |
|---|---|---|
| RAM (heap) | < 50 MB | RAM-mapped registers + database + stack |
| CPU | Single core | Cooperative loop, no parallelism |
| SocketCAN bandwidth | < 1 Mbit/s | Virtual CAN, no physical bus load |
| Startup time | < 2 s | From main() to SYS RUNNING |

## 8. Design Decisions

| Decision | Rationale | Alternatives Considered |
|---|---|---|
| Cooperative loop instead of pthreads | Preserves single-threaded execution semantics of FreeRTOS task model; eliminates concurrency bugs | pthreads with mutexes (rejected: adds complexity, changes timing model) |
| SocketCAN for CAN | Linux-native, well-tested, supports virtual CAN for testing | TCP sockets (rejected: non-standard framing), shared memory (rejected: no standard tooling) |
| RAM-mapped registers | Minimal code changes to driver layer; register read/write code executes normally | Conditional compilation (rejected: excessive #ifdefs), mock objects (rejected: requires refactoring) |
| 24 DIAG IDs suppressed | Hardware-dependent diagnostics cannot trigger meaningfully without physical hardware | Emulate hardware faults (deferred to Phase 3) |

---
*End of Document*
