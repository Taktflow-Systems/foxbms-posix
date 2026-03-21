# System Architecture Description

| Document ID | Rev | Date | Classification |
|---|---|---|---|
| SYS.3-001 | 1.0 | 2026-03-21 | Confidential |

## Revision History

| Rev | Date | Author | Reviewer | Description |
|---|---|---|---|---|
| 1.0 | 2026-03-21 | An Dao | M. Weber (AI-simulated) | Initial release |

## 1. Purpose

This document describes the system architecture of the foxBMS 2 POSIX port BMS. It
decomposes the system into layers, tasks, and communication interfaces, satisfying
ASPICE SYS.3 base practices and ISO 26262 Part 4 system design requirements.

## 2. Scope

The architecture covers the full BMS software stack from application-level algorithms
down to the hardware abstraction layer, including the POSIX-specific adaptations.

## 3. References

| ID | Title |
|---|---|
| [SYS.2-001] | System Requirements Specification |
| [SWE.2-001] | Software Architecture Description |
| [ISO-HSI-001] | Hardware-Software Interface Specification |

## 4. System Context

The BMS manages a single battery string (18s1p) connected to a vehicle load via three
contactors (string+, string-, precharge). External interfaces are:

- CAN bus to vehicle controller
- SPI bus to analog front end (AFE) for cell voltage and temperature measurement
- I2C bus to peripherals
- Current sensor (Isabellenhuette IVT) via CAN
- Interlock circuit for physical safety loop

## 5. System Block Diagram

```
+-------------------------------------------------------------------+
|                     APPLICATION LAYER                              |
|                                                                    |
|  +-------+  +-----+  +-----------+  +----------+  +----------+   |
|  |  BMS  |  | SOA |  | Algorithm |  | Balancing|  |Plausibil.|   |
|  | State |  |Check|  | (SOC/SOE) |  |          |  |          |   |
|  | Mach. |  |     |  |           |  |          |  |Redundancy|   |
|  +---+---+  +--+--+  +-----+-----+  +----+-----+  +----+-----+   |
|      |         |            |              |              |        |
+------+---------+------------+--------------+--------------+--------+
       |         |            |              |              |
+------+---------+------------+--------------+--------------+--------+
|                      ENGINE LAYER                                  |
|                                                                    |
|  +----------+       +-----------+       +----------+               |
|  | Database |       |   DIAG    |       |   SYS    |               |
|  | (R/W)    |       | Handler   |       |  State   |               |
|  +----+-----+       +-----+-----+       +----+-----+               |
|       |                   |                   |                    |
+-------+-------------------+-------------------+--------------------+
        |                   |                   |
+-------+-------------------+-------------------+--------------------+
|                      DRIVER LAYER                                  |
|                                                                    |
|  +-----+ +-----+ +-----+ +-----+ +-----+ +-----+ +-----+ +----+ |
|  | CAN | | SPI | | I2C | | SBC | | SPS | |Cont.| | IMD | |Intl| |
|  +--+--+ +--+--+ +--+--+ +--+--+ +--+--+ +--+--+ +--+--+ +-+--+ |
|     |       |       |       |       |       |       |       |     |
+-----+-------+-------+-------+-------+-------+-------+-------+-----+
      |       |       |       |       |       |       |       |
+-----+-------+-------+-------+-------+-------+-------+-------+-----+
|                 HARDWARE ABSTRACTION LAYER                         |
|                                                                    |
|             +-------------+  OR  +-------------+                   |
|             |   TMS570    |      |    POSIX    |                   |
|             | (hardware)  |      |   (stubs)   |                   |
|             +-------------+      +-------------+                   |
|                                                                    |
+-------------------------------------------------------------------+
```

## 6. Layer Descriptions

### 6.1 Application Layer

The Application layer implements the BMS functional logic. It is hardware-independent
and operates exclusively through the Engine and Driver layer APIs.

| Module | Responsibility | Traces To |
|---|---|---|
| BMS State Machine | Manages pack states (STANDBY, PRECHARGE, NORMAL, ERROR) | SYS-REQ-071, SYS-REQ-073 |
| SOA (Safe Operating Area) | Checks cell voltages, currents, temperatures against MOL/RSL/MSL | SYS-REQ-020 to SYS-REQ-043 |
| Algorithm | SOC, SOE, and SOH estimation | SYS-REQ-010 to SYS-REQ-012 |
| Balancing | Cell balancing decisions | SYS-REQ-003 |
| Plausibility | Cross-checks redundant measurements | SYS-REQ-050 |
| Redundancy | Manages redundant measurement paths | SYS-REQ-050 |

### 6.2 Engine Layer

The Engine layer provides core services to the Application layer.

| Module | Responsibility | Traces To |
|---|---|---|
| Database | Central data store; producer/consumer pattern with single-writer per entry | SYS-REQ-060 |
| DIAG | Diagnostic handler; threshold counters, severity evaluation, FATAL flagging | SYS-REQ-050 to SYS-REQ-055 |
| SYS | System state machine (UNINITIALIZED through RUNNING) | SYS-REQ-070 |

### 6.3 Driver Layer

The Driver layer abstracts hardware peripherals into software-callable interfaces.

| Module | Responsibility | Traces To |
|---|---|---|
| CAN | CAN bus transmission and reception | SYS-REQ-060 to SYS-REQ-063 |
| SPI | SPI bus for AFE communication | SYS-REQ-005 |
| I2C | I2C bus for peripheral communication | SYS-REQ-005 |
| SBC | System Basis Chip supervision | SYS-REQ-050 |
| SPS | Smart Power Switch control | SYS-REQ-006 |
| Contactor | Contactor state control and feedback | SYS-REQ-006, SYS-REQ-054 |
| IMD | Insulation Monitoring Device | SYS-REQ-050 |
| Interlock | Physical safety interlock monitoring | SYS-REQ-050 |

### 6.4 Hardware Abstraction Layer

| Variant | Description | Traces To |
|---|---|---|
| TMS570 (production) | Direct register access to TI TMS570 MCU peripherals | -- |
| POSIX (SIL) | 80+ stub modules mapping 60+ register bases to RAM buffers; SocketCAN replaces HW CAN | SYS-REQ-080 to SYS-REQ-086 |

## 7. Task Architecture

### 7.1 FreeRTOS Tasks (Production Target)

| Task | Trigger | Period | Responsibility |
|---|---|---|---|
| Engine | Event-driven | -- | SYS state machine, system-level coordination |
| 1ms Task | Periodic | 1 ms | Fast control loops, contactor timing |
| AFE Task | Asynchronous | -- | AFE communication via SPI (measurement cycle) |
| 10ms Task | Periodic | 10 ms | CAN transmit/receive, database updates |
| 100ms Task | Periodic | 100 ms | SOA checks, DIAG evaluation, BMS state machine |
| I2C Task | Asynchronous | -- | I2C peripheral communication |
| 100ms Algorithm | Periodic | 100 ms | SOC, SOE, SOH computation |

### 7.2 POSIX Cooperative Loop (SIL Target)

The FreeRTOS scheduler is replaced by a single-threaded cooperative main loop that
calls each task function in sequence. The loop executes in the order listed in
Section 7.1, preserving the relative priority and data-flow dependencies.

```
main():
    SYSTEM_Init()
    while (running):
        ENGINE_Task()
        TASK_1ms()
        AFE_Task()
        TASK_10ms()
        TASK_100ms()
        I2C_Task()
        ALGO_100ms()
        usleep(1000)  // 1ms tick approximation
```

## 8. Data Flow

### 8.1 Measurement Path

```
AFE (SPI) --> AFE Driver --> Database[CELL_VOLTAGE] --> SOA --> DIAG --> BMS
AFE (SPI) --> AFE Driver --> Database[CELL_TEMPERATURE] --> SOA --> DIAG --> BMS
IVT (CAN) --> CAN Driver --> Database[CURRENT] --> SOA --> DIAG --> BMS
```

### 8.2 Safety Path

```
SOA check (threshold comparison)
    |
    v
DIAG_Handler (increment threshold counter)
    |
    v
Counter >= threshold? --> Yes --> Set FATAL flag
    |
    v
BMS state machine reads FATAL --> Transition to ERROR
    |
    v
ERROR state --> Open all contactors (string+, string-, precharge)
```

### 8.3 Command Path

```
Vehicle Controller --> CAN 0x210 (State Request)
    |
    v
CAN RX Handler --> Database[STATE_REQUEST]
    |
    v
BMS State Machine --> Evaluate transition
    |
    v
Contactor Driver --> Actuate contactors
```

## 9. CAN Interface Specification

### 9.1 Transmit Messages

| CAN ID | Name | Cycle | Content |
|---|---|---|---|
| 0x220 | BmsState | 100 ms | BMS state, SYS state, error flags |
| 0x221 | BmsDetails | 100 ms | SOC, SOE, pack voltage, pack current |
| 0x231 | Values1 | 100 ms | Min/max cell voltage |
| 0x232 | Values2 | 100 ms | Min/max cell temperature |
| 0x233 | Values3 | 100 ms | Balancing state |
| 0x234 | Values4 | 100 ms | Insulation resistance |
| 0x235 | Values5 | 100 ms | String current |
| 0x236 | Values6 | 100 ms | Pack current |
| 0x240-0x245 | CellVoltages | 100 ms | Individual cell voltages (18 cells) |
| 0x250 | MuxVoltages | 100 ms | Multiplexed voltage data |
| 0x260 | MuxTemps | 100 ms | Multiplexed temperature data |
| 0x301 | SlaveInfo | 1000 ms | AFE slave status |

### 9.2 Receive Messages

| CAN ID | Name | Content |
|---|---|---|
| 0x210 | StateRequest | Requested BMS state transition |
| 0x270 | AFE CellVoltages | 50 mux cycles x 4 voltages per frame |
| 0x280 | AFE CellTemperatures | 30 mux cycles x 6 temperatures per frame |
| 0x521 | IVT Current | Current measurement |
| 0x522 | IVT Voltage 1 | Voltage measurement 1 |
| 0x523 | IVT Voltage 2 | Voltage measurement 2 |
| 0x524 | IVT Voltage 3 | Voltage measurement 3 |
| 0x525 | IVT Temperature | Sensor temperature |
| 0x526 | IVT Power | Calculated power |
| 0x527 | IVT Coulomb Count | Charge counter |

## 10. Safety Architecture Summary

The safety concept follows a defense-in-depth approach:

1. **Layer 1 -- SOA**: Continuous comparison of measurements against MOL/RSL/MSL.
2. **Layer 2 -- DIAG**: Debounced threshold counters prevent single-event false trips.
3. **Layer 3 -- BMS**: ERROR state latching with dual-condition exit (fault clear + explicit request).
4. **Layer 4 -- Contactors**: Physical disconnection of the battery string.

This architecture is preserved in the POSIX port for all software-checkable paths.

---
*End of Document*
