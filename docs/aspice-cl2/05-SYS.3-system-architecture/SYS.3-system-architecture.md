# System Architecture Description

| Document ID | Rev | Date | Classification |
|---|---|---|---|
| SYS.3-001 | 1.2 | 2026-03-23 | Confidential |

## Revision History

| Rev | Date | Author | Reviewer | Description |
|---|---|---|---|---|
| 1.0 | 2026-03-21 | An Dao | M. Weber | Initial release |
| 1.1 | 2026-03-23 | An Dao | Phase 1 Audit Panel (10 reviewers) | Add Sections 11-12: Hardware interface architecture, signal paths, probe point map, register cross-reference |
| 1.2 | 2026-03-23 | An Dao | ASPICE Researcher + Fault Finder agents | Fix ball assignments (E-02/E-05), ADC accuracy, plausibility threshold. Add ⚠TBV markers for unverified pins. |

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

## 4a. System Element Decomposition (ASPICE SYS.3 BP.1)

The BMS system is decomposed into the following elements per ASPICE SYS.3 BP.1.
Each element has a unique ID for traceability to system requirements (§4b).

### Hardware Elements

| ID | Element | Type | Board | Description | ASIL |
|---|---|---|---|---|---|
| SE-001 | Master ECU | HW | TMS570LC4357 | Main MCU: ARM Cortex-R4F lockstep, FreeRTOS, all safety logic | D |
| SE-002 | Slave Board | HW | LTC6813-1 | Cell voltage + temperature measurement, 18-cell AFE | D |
| SE-003 | Interface Board | HW | LTC6820 ×4 | SPI-to-isoSPI bridge, galvanic isolation | D |
| SE-004 | Current Sensor | HW | IVT-S (Isabellenhuette) | Shunt-based current measurement via CAN | B |
| SE-005 | Insulation Monitor | HW | Bender IR155/iso165C | HV insulation monitoring (PWM or CAN) | A |
| SE-006 | SPS IC | HW | on Master board | 8-ch MOSFET driver for contactor coils, UVLO fail-safe | B |
| SE-007 | SBC | HW | NXP FS8x, on Master | Watchdog, power supervision, ASIL D qualified | D |
| SE-008 | Contactors ×3 | HW | external | String+, String-, Precharge. Spring-return (fail-safe open) | B |
| SE-009 | Interlock Loop | HW | external | Physical safety loop through HV connectors | QM (FATAL) |
| SE-010 | CAN Transceivers | HW | TJA1044/TJA1042 | CAN1 (non-isolated), CAN2 (isolated) | B |
| SE-011 | FRAM | HW | on Master board | Persistent storage for SOC, fault flags, calibration | — |

### Software Elements

| ID | Element | Type | Runs On | Description | ASIL |
|---|---|---|---|---|---|
| SE-020 | BMS Application | SW | SE-001 | State machine, SOA checks, algorithms (SOC/SOE) | D |
| SE-021 | Engine Layer | SW | SE-001 | Database, DIAG handler, SYS state machine | D |
| SE-022 | Driver Layer | SW | SE-001 | CAN, SPI, I2C, SBC, SPS, contactor, IMD, interlock drivers | D |
| SE-023 | HAL (TMS570) | SW | SE-001 | HalCoGen-generated register access, DMA, interrupt config | D |
| SE-024 | HAL (POSIX) | SW | host PC | RAM-mapped stubs, SocketCAN, cooperative loop (SIL variant) | — |
| SE-025 | AFE Driver | SW | SE-001 | LTC6813-1 communication: SPI transactions, PEC check, DECAN | D |
| SE-026 | Plant Model | SW | host PC | CAN-based cell/IVT/contactor simulation (SIL only) | — |

### Element Boundary Diagram

```
External:  Vehicle Controller ←─ CAN2 ─→ ┌──────────────────────────────────────┐
           IVT (SE-004) ←────── CAN1 ──→ │                                      │
                                          │  MASTER ECU (SE-001)                 │
                                          │  ┌─────────────────────────────────┐ │
                                          │  │ SE-020 BMS Application          │ │
                                          │  │ SE-021 Engine (DB, DIAG, SYS)   │ │
                                          │  │ SE-022 Drivers                   │ │
                                          │  │ SE-023 HAL (HalCoGen)           │ │
                                          │  └─────────────────────────────────┘ │
                                          │  SE-006 SPS ──→ SE-008 Contactors   │
                                          │  SE-007 SBC (watchdog)              │
                                          │  SE-010 CAN transceivers            │
                                          │  SE-011 FRAM                        │
                                          └──────────┬─────────────────────────┘
                                                     │ J9000 (SPI1/4)
                                          ┌──────────┴─────────────────────────┐
                                          │  SE-003 Interface Board (LTC6820)  │
                                          └──────────┬─────────────────────────┘
                                                     │ isoSPI (isolated)
                                          ┌──────────┴─────────────────────────┐
                                          │  SE-002 Slave Board (LTC6813)      │
                                          │  ← Cell voltage (24-pin)           │
                                          │  ← Temperature (16-pin)            │
                                          └────────────────────────────────────┘
           SE-009 Interlock Loop ←── J2033
           SE-005 IMD ←───────────── J2034
```

## 4b. Requirements Allocation (ASPICE SYS.3 BP.2)

Each system requirement is allocated to one or more system elements. Full allocation
matrix is maintained in the traceability tool. Summary by element:

| Element | Allocated Requirements | Coverage |
|---|---|---|
| SE-001 (Master ECU) | SYS-REQ-001 to SYS-REQ-086 (all) | Platform for all SW elements |
| SE-002 (Slave Board) | SYS-REQ-020 to SYS-REQ-043 (voltage, temperature) | Cell measurement |
| SE-003 (Interface) | SYS-REQ-005 (SPI/isoSPI communication) | Data transport |
| SE-004 (IVT) | SYS-REQ-010 to SYS-REQ-012 (current, SOC) | Current measurement |
| SE-006 (SPS) | SYS-REQ-006 (contactor control) | Actuation |
| SE-007 (SBC) | SYS-REQ-050 (system monitoring) | MCU supervision |
| SE-008 (Contactors) | SYS-REQ-006, SYS-REQ-054 (safe state) | Physical disconnection |
| SE-009 (Interlock) | SYS-REQ-050 (connector integrity) | HV safety loop |
| SE-020 (BMS App) | SYS-REQ-020 to SYS-REQ-073 (SOA, state machine) | Safety logic |
| SE-021 (Engine) | SYS-REQ-050 to SYS-REQ-060 (DIAG, database) | Diagnostic services |
| SE-022 (Drivers) | SYS-REQ-005, SYS-REQ-060 to SYS-REQ-063 | HW abstraction |
| SE-025 (AFE Driver) | SYS-REQ-005, SYS-REQ-020 to SYS-REQ-043 | AFE communication |

## 4c. Architecture Alternatives Analysis (ASPICE SYS.3 BP.5)

| Decision | Alternatives Considered | Selected | Rationale |
|---|---|---|---|
| MCU | TI TMS570LC4357 vs Infineon Aurix TC3xx vs Renesas RH850 | TMS570LC4357 | foxBMS reference platform. ARM Cortex-R4F lockstep provides ASIL D hardware safety. Mature HalCoGen tool support. |
| AFE | ADI LTC6813-1 vs TI BQ79616 vs Maxim MAX17853 | LTC6813-1 | foxBMS reference AFE. 18-cell support matches configuration. isoSPI provides galvanic isolation without separate isolator ICs. AEC-Q100 Grade 1. |
| RTOS | FreeRTOS vs AUTOSAR OS vs SafeRTOS | FreeRTOS | foxBMS reference RTOS. Open source, well-documented, adequate for the task architecture. SafeRTOS available as drop-in replacement for ASIL D certification. |
| Architecture style | Layered (foxBMS) vs AUTOSAR Classic vs Model-based | Layered | foxBMS uses a proven 4-layer architecture (App/Engine/Driver/HAL). Simpler than AUTOSAR for a single-function ECU. Well-suited for the BMS domain. |
| SIL variant | POSIX cooperative loop vs pthreads vs QEMU emulation | POSIX cooperative loop | Single-threaded preserves deterministic task ordering. SocketCAN provides real CAN integration. Avoids race conditions from threading. |
| Contactor drive | Direct GPIO vs SPS IC (integrated driver) | SPS IC | foxBMS reference design. Integrated current sensing for feedback. MOSFET driver handles inductive kickback. UVLO provides hardware fail-safe. |

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

## 7a. State Machines (ASPICE SYS.3 BP.4)

### 7a.1 SYS State Machine (System Initialization)

```
                    ┌──────────────┐
    Power-on ──────►│UNINITIALIZED │
                    └──────┬───────┘
                           │ Hardware init complete
                           ▼
                    ┌──────────────┐
                    │  INITIALIZED │
                    └──────┬───────┘
                           │ OS started, tasks created
                           ▼
                    ┌──────────────┐
                    │   RUNNING    │──── Normal operation
                    └──────┬───────┘
                           │ Fatal system error
                           ▼
                    ┌──────────────┐
                    │    ERROR     │──── System-level fault
                    └──────────────┘
```

**Transitions**: SYS state machine is one-directional (no recovery from SYS ERROR).
Managed by `SYS_Trigger()` in the Engine task.

### 7a.2 BMS State Machine (Application-Level)

```
                         ┌───────────────┐
    SYS == RUNNING ─────►│    STANDBY    │◄──────────────────────────────┐
                         │               │                               │
                         │ All contactors│                               │
                         │ OPEN          │                               │
                         └───────┬───────┘                               │
                                 │                                       │
                    CAN 0x210    │  State request                        │
                    = NORMAL     │  received                             │
                                 ▼                                       │
                         ┌───────────────┐                               │
                         │  PRECHARGE    │                               │
                         │               │                               │
                         │ 1. Close STR- │                               │
                         │ 2. Close PRE  │                               │
                         │ 3. Wait V_dc  │                               │
                         │    ≈ V_pack   │                               │
                         │ 4. Close STR+ │                               │
                         │ 5. Open PRE   │                               │
                         └──┬─────────┬──┘                               │
                            │         │                                  │
               Precharge    │         │ Precharge                        │
               OK           │         │ FAIL/timeout                     │
                            ▼         ▼                                  │
                   ┌────────────┐  ┌──────────────┐   Fault cleared     │
                   │   NORMAL   │  │    ERROR     │   AND               │
                   │            │  │              │   CAN 0x210         │
                   │ All 3 cont.│  │ All cont.   │   = STANDBY         │
                   │ CLOSED     │  │ OPEN         ├──────────────────────┘
                   │            │  │              │
                   │ Full power │  │ Safe state   │
                   │ operation  │  │ (latched)    │
                   └─────┬──────┘  └──────────────┘
                         │                 ▲
                         │  ANY MSL fault  │
                         │  (DIAG FATAL)   │
                         └─────────────────┘
```

**States**:
| State | Contactors | Entry Condition | Exit Condition |
|---|---|---|---|
| STANDBY | All OPEN | SYS == RUNNING, or ERROR recovery | CAN state request = NORMAL |
| PRECHARGE | STR- + PRE closed | State request received | Voltage match or timeout |
| NORMAL | All CLOSED | Precharge voltage OK | FATAL flag or STANDBY request |
| ERROR | All OPEN | Any DIAG FATAL flag set | Fault cleared AND STANDBY request (SSR-022/023/024) |

**ERROR exit requires BOTH conditions (AND logic)**:
1. The originating fault condition has cleared (SSR-022)
2. An explicit STANDBY request received via CAN 0x210 (SSR-023)

### 7a.3 Fault Reaction Sequence

```
Time ──────────────────────────────────────────────────────────────►

 t0: Fault occurs (e.g., cell voltage > 2800 mV)
  │
  ├─ t0+10ms: SOA_CheckCellVoltage() detects violation
  │            DIAG_Handler(DIAG_ID_CELLVOLTAGE_OV_MSL, NOT_OK)
  │            Threshold counter: 0 → 1
  │
  ├─ t0+20ms: SOA check again → counter: 1 → 2
  │  ...
  ├─ t0+500ms: Counter reaches 50 (threshold)
  │
  ├─ t0+700ms: 200ms debounce delay elapses
  │             FATAL flag SET
  │             DIAG_ErrorOvervoltage() callback executed
  │
  ├─ t0+710ms: BMS_Trigger() reads FATAL flag
  │             BMS state → ERROR
  │             CONT_OpenAll() called
  │
  ├─ t0+711ms: SPS SPI command sent (spiREG2)
  │             Contactor coils de-energized
  │
  ├─ t0+750ms: Contactor mechanical open (spring return)
  │
  └─ t0+750ms: SAFE STATE REACHED
               (Total FTTI: 750 ms for TSR-01)
```

### 7a.4 Task Scheduling Timing

| Task | Period | WCET (est.) | CPU Load (est.) | Priority | Key Functions |
|---|---|---|---|---|---|
| Engine | Event | <1 ms | <1% | Highest | SYS state machine |
| 1ms Task | 1 ms | <0.5 ms | ~50% | High | Contactor timing, fast loops |
| AFE Task | Async | ~3 ms | ~15% | Medium | SPI1 DMA to LTC6813 |
| 10ms Task | 10 ms | ~2 ms | ~20% | Medium | CAN TX/RX, SPS_Ctrl, SBC_Trigger, SOA |
| 100ms Task | 100 ms | ~5 ms | ~5% | Low | BMS state machine, DIAG evaluation |
| Algorithm | 100 ms | ~3 ms | ~3% | Lowest | SOC, SOE, SOH estimation |

**Total estimated CPU load: ~94%** (conservative worst-case). Margin: ~6%.

**POSIX SIL variant**: All tasks execute sequentially in a cooperative loop (`usleep(1000)` between
iterations). No preemption, no priority inversion, deterministic ordering.

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

## 11. Hardware Interface Architecture

This section documents the physical hardware interfaces of the foxBMS 2 system at
connector-pin-signal level, as required for SYS.4 HIL test probe mapping and needle
bed adapter design. All data sourced from foxBMS hardware schematics v1.2.2 (master),
v1.1.3 (slave 18-cell), and v1.0.3 (interface).

**Source Schematics** (in `hardware/schematics/` — not duplicated here to avoid 42 MB bloat):

| File | Path | Board | Version |
|------|------|-------|---------|
| Master schematics | `hardware/schematics/master/Assembly production/pdf/foxbms2-master-schematics-v1.2.3-0.PDF` | TMS570LC4357 | v1.2.3 |
| Slave schematics | `hardware/schematics/slave-18/Assembly automotive/pdf/schematics.PDF` | LTC6813-1 (18-cell) | v1.1.3 |
| Interface schematics | `hardware/schematics/interface/Assembly default/pdf/schematics.PDF` | LTC6820 | v1.0.3 |
| Master placement | `hardware/schematics/master/Assembly production/pdf/foxbms2-master-placement-plan-v1.2.3-0.PDF` | Connector locations | v1.2.3 |
| Master dimensions | `hardware/schematics/master/Assembly production/pdf/foxbms2-master-dimensions-mechanical-v1.2.3-0.PDF` | Board outline | v1.2.3 |

**Pinout CSVs** (in foxBMS upstream repo `D:/workspace_ccstheia/foxbms-2/docs/hardware/`):

| CSV | Connector | Pins |
|-----|-----------|------|
| `master/.../ti-tms570lc4357-v1.2.2_can1.csv` | J2021 CAN1 | 4 |
| `master/.../ti-tms570lc4357-v1.2.2_can2.csv` | J2024 CAN2 | 4 |
| `master/.../ti-tms570lc4357-v1.2.2_sps.csv` | J200x SPS | 4 each |
| `master/.../ti-tms570lc4357-v1.2.2_interlock.csv` | J2033 | 2 |
| `master/.../ti-tms570lc4357-v1.2.2_interface.csv` | J9000 | 40 |
| `master/.../ti-tms570lc4357-v1.2.2_extension.csv` | J9002 | 120 |
| `master/.../ti-tms570lc4357-v1.2.2_supply_ext.csv` | J2009 | 8 |
| `master/.../ti-tms570lc4357-v1.2.2_isomon.csv` | J2034 | 4 |
| `slaves/.../18-ltc-ltc6813-1-v1.1.3_cell_voltage-sense-connector.csv` | Cell voltage | 24 |
| `slaves/.../18-ltc-ltc6813-1-v1.1.3_temperature-sensor-connector.csv` | Temperature | 16 |
| `interfaces/.../ltc-ltc6820-v1.0.3_master_connector.csv` | Interface master | 40 |
| `interfaces/.../ltc-ltc6820-v1.0.3_isospi_connectors.csv` | isoSPI | 2 |

**HalCoGen Pin Mux** (MCU ball assignments):
- Source: `D:/workspace_ccstheia/foxbms-2/conf/hcg/source/HL_pinmux.c`
- Header: `D:/workspace_ccstheia/foxbms-2/conf/hcg/include/HL_pinmux.h`

**Visual Diagrams** (self-contained HTML):

| File | Description |
|------|-------------|
| [views/ecu-pin-mapping.html](views/ecu-pin-mapping.html) | Color-coded ECU pin mapping tables (dark theme, ASIL badges, gap markers) |
| [views/wiring-diagram.html](views/wiring-diagram.html) | SVG wiring diagram with connectors, MCU balls, colored signal paths |

### 11.1 System Board Topology

```
                    ┌──────────────────────────┐
                    │      MASTER BOARD        │
  J2009 ── Supply ──┤   TMS570LC4357 MCU       │
  J2021 ── CAN1 ────┤                          │
  J2024 ── CAN2 ────┤   SPI1 ──► J9000 ──────────► INTERFACE BOARD (LTC6820)
  J2033 ── Intlck ──┤   SPI2 ──► SPS IC ──► J200x      │
  J2034 ── IMD ─────┤   SPI3 ──► FRAM               isoSPI (transformer)
  J200x ── SPS×8 ───┤   I2C1 ──► PEX (feedback)        │
  J3008 ── Debug ───┤   SBC  ──► FS8x (watchdog)       ▼
                    └──────────────────────────┘  SLAVE BOARD (LTC6813)
                                                  ├── Cell voltage (24-pin)
                                                  ├── Temperature (16-pin)
                                                  └── Daisy chain (2+2 pin)
```

### 11.1.1 ECU I/O Pin Mapping (Safety-Critical Signals)

All MCU ball assignments from HalCoGen `HL_pinmux.c` (foxBMS v1.10.0).
Register addresses are the last 4 hex digits of the full `0xFFF7xxxx` base.

**CAN Interfaces:**

| Connector | Pin | Signal | Transceiver | MCU Ball | Mux Function | Register | DMA | SW Module |
|-----------|-----|--------|-------------|----------|-------------|----------|-----|-----------|
| J2021 | 4 | CAN1_H | TJA1044 | dedicated | DCAN1TX | canREG1 (DC00) | — | can.c |
| J2021 | 3 | CAN1_L | TJA1044 | dedicated | DCAN1RX | canREG1 | — | can.c |
| — | — | CAN1_EN | — | N4 | N2HET2[18] | hetREG2 (B900) | — | can_cfg.h |
| — | — | CAN1_STB | ⚠ TBV | N2HET2[23] (DOUT bit, no pinmux entry) | hetREG2 | — | can_cfg.h |
| J2024 | 4 | CAN2_H | TJA1042 (iso) | dedicated | DCAN2TX | canREG2 (DE00) | — | can.c |
| J2024 | 3 | CAN2_L | TJA1042 (iso) | dedicated | DCAN2RX | canREG2 | — | can.c |
| — | — | CAN2_EN | — | PEX | I2C port exp. | i2cREG1 (D400) | — | pex.c |

**SPI1 → AFE (Cell Voltage + Temperature, ASIL D):**

| Connector | Pin | Signal | MCU Ball | Mux Function | Register | DMA | SW Module |
|-----------|-----|--------|----------|-------------|----------|-----|-----------|
| J9000 | 1 | SPI1_SOMI0 | dedicated | MIBSPI1SOMI_0 | spiREG1 (F400) | CH1 (RX) | afe.c |
| J9000 | 3 | SPI1_SIMO0 | dedicated | MIBSPI1SIMO_0 | spiREG1 | CH0 (TX) | afe.c |
| J9000 | 5 | SPI1_CLK | dedicated | MIBSPI1CLK | spiREG1 | — | afe.c |
| J9000 | 6 | SPI1_CS1 | F3 | MIBSPI1NCS_1 | spiREG1 | — | afe.c (isoSPI ch1) |
| J9000 | 7 | SPI1_CS2 | G3 | MIBSPI1NCS_2 | spiREG1 | — | afe.c (isoSPI ch2) |
| J9000 | 14 | SPI4_CS0 | U1 | MIBSPI4NCS_0 | spiREG4 (FA00) | — | afe.c (isoSPI ch3) |
| J9000 | 15 | SPI4_CS1 | B12 | MIBSPI4NCS_1 | spiREG4 | — | afe.c (isoSPI ch4) |
| J9000 | 20 | IF_INT0 | C1 | GIOA_2 | gioREG (BC00) | — | afe.c |
| J9000 | 21 | IF_INT1 | E1 | GIOA_3 | gioREG | — | afe.c |
| J9000 | 22 | IF_INT2 | A6 | GIOA_4 | gioREG | — | — |
| J9000 | 23 | IF_INT3 | H3 | GIOA_6 | gioREG | — | — |
| J9000 | 24-31 | IF_GPIO.0-7 | — | via I2C PEX | i2cREG1 (D400) | — | pex.c (LTC6820 en/mst) |

**SPI2 → SPS + SBC (Contactor Control + Watchdog, shared bus — CONSTRAINT-001):**

| Connector | Pin | Signal | MCU Ball | Mux Function | Register | DMA | SW Module |
|-----------|-----|--------|----------|-------------|----------|-----|-----------|
| J200x | 3 | SPS_OUT_X | D1 | MIBSPI2SIMO | spiREG2 (F600) | CH2 (TX) | sps.c |
| J200x | — | (SPS SOMI) | D2 | MIBSPI2SOMI | spiREG2 | CH3 (RX) | sps.c |
| — | — | (SPS CLK) | E2 | MIBSPI2CLK | spiREG2 | — | sps.c |
| — | — | SPS_CS (SW) | D8 | N2HET2[01] | hetREG2 (B900) | — | spi_cfg.h |
| — | — | SPS_RESET | T5 | N2HET2[20] | hetREG2 | — | sps_cfg.h |
| — | — | SPS_FB_EN | ⚠ TBV | N2HET2[09] | hetREG2 | — | sps_cfg.h |
| on-board | — | SBC_SIMO | D1 | MIBSPI2SIMO | spiREG2 (F600) | — | sbc.c (shared!) |
| on-board | — | SBC_SOMI | D2 | MIBSPI2SOMI | spiREG2 | — | sbc.c |
| J9002 | 80 | SBC_RSTB | — | — | — | — | sbc.c |
| J9002 | 79 | SBC_FS0B | — | — | — | — | sbc.c |

**SPI3 → FRAM (Diagnostic Data Persistence):**

| Connector | Pin | Signal | MCU Ball | Mux Function | Register | DMA | SW Module |
|-----------|-----|--------|----------|-------------|----------|-----|-----------|
| on-board | — | FRAM_CLK | V9 | MIBSPI3CLK | spiREG3 (F800) | — | fram.c |
| on-board | — | FRAM_SIMO | W8 | MIBSPI3SIMO | spiREG3 | — | fram.c |
| on-board | — | FRAM_SOMI | V8 | MIBSPI3SOMI | spiREG3 | — | fram.c |
| on-board | — | FRAM_CS | V10 | MIBSPI3NCS_0 | spiREG3 | — | fram.c |

**Interlock (Safety Loop):**

| Connector | Pin | Signal | MCU Ball | Mux Function | Register | DMA | SW Module |
|-----------|-----|--------|----------|-------------|----------|-----|-----------|
| J2033 | 1 | INTERLOCK_H | B11 | N2HET1[30] (IL_HS_ENABLE) | hetREG1 (B800) | — | interlock.c |
| J2033 | 2 | INTERLOCK_L | A3 | N2HET1[29] (IL_STATE) | hetREG1 | — | interlock.c |
| — | — | IL_HS_VS | — | ADC ch2 | adcREG1 (C000) | — | interlock.c |
| — | — | IL_LS_VS | — | ADC ch3 | adcREG1 | — | interlock.c |
| — | — | IL_HS_CS | — | ADC ch4 | adcREG1 | — | interlock.c |
| — | — | IL_LS_CS | — | ADC ch5 | adcREG1 | — | interlock.c |

**IMD (Insulation Monitoring):**

| Connector | Pin | Signal | MCU Ball | Mux Function | Register | DMA | SW Module |
|-----------|-----|--------|----------|-------------|----------|-----|-----------|
| J2034 | 3 | IMD_OK | A9 | N2HET1[27] | hetREG1 (B800) | — | bender_ir155.c |
| J2034 | 4 | IMD_PWM | D7 | N2HET2[02] | hetREG2 (B900) | — | bender_ir155.c |
| — | — | IR155_EN | M3 | N2HET1[25] | hetREG1 | — | bender_ir155.c |
| — | — | iso165C RX | — | via CAN1 (0x37) | canREG1 | — | bender_iso165c.c |

**Contactor Feedback (via I2C Port Expander):**

| Connector | Pin | Signal | MCU Ball | Path | Register | SW Module |
|-----------|-----|--------|----------|------|----------|-----------|
| J200x | 1 | SPS_FB_0 (String+) | B2/C3 | I2C → PEX1 pin 0 | i2cREG1 (D400) | sps_cfg.c |
| J200x | 1 | SPS_FB_1 (String-) | B2/C3 | I2C → PEX1 pin 1 | i2cREG1 | sps_cfg.c |
| J200x | 1 | SPS_FB_2 (Precharge) | B2/C3 | I2C → PEX1 pin 2 | i2cREG1 | sps_cfg.c (NO_FB!) |

### 11.1.2 Slave Board I/O (LTC6813-1, AEC-Q100 Grade 1)

| Connector | Pin(s) | Signal | LTC6813 Channel | ADC Spec |
|-----------|--------|--------|-----------------|----------|
| Cell voltage | 1 | VBAT- | C0 neg ref | 16-bit, 0.1 mV/LSB |
| Cell voltage | 2,14 | CELL_0+, CELL_1+ | C0+, C1+ | ±2.2 mV TME (7kHz, 25°C) |
| Cell voltage | 3-10, 15-22 | CELL_2+ to CELL_17+ | C2+ to C17+ | ±3.3 mV over -40/+125°C |
| Cell voltage | 11 | VBAT+ | C17+ ref | conversion: 815 µs (18 cells) |
| Temperature | 1-4 | T-SENSOR_0-3 | GPIO1-4 (MUX grp 0) | 10kΩ NTC, ADAX cmd |
| Temperature | 5-8 | T-SENSOR_4-7 | GPIO5+1-3 (MUX grp 1) | scan time: ~4 ms |
| Temperature | 9-16 | FUSED_VBAT- | NTC return | all share common return |
| Daisy In | 1-2 | IN+/IN- | isoSPI input | from prev slave / interface |
| Daisy Out | 1-2 | OUT+/OUT- | isoSPI output | to next slave |

**NOTE**: Cell connector uses interleaved pinout — even cells on row 1 (pins 2-11),
odd cells on row 2 (pins 14-22). Cell emulator wiring must match.

### 11.1.3 Interface Board I/O (LTC6820 × 4 channels)

| MCU Ball | SPI CS | LTC6820 Channel | GPIO Enable | GPIO Master | isoSPI Spec |
|----------|--------|-----------------|-------------|-------------|-------------|
| F3 | MIBSPI1NCS_1 | ch1 | IF_GPIO.0 (PEX IO1_0) | IF_GPIO.1 (PEX IO1_1) | 1 Mbps, 100m max |
| G3 | MIBSPI1NCS_2 | ch2 | IF_GPIO.2 (PEX IO1_2) | IF_GPIO.3 (PEX IO1_3) | practical: <2m |
| U1 | MIBSPI4NCS_0 | ch3 | IF_GPIO.4 (PEX IO1_4) | IF_GPIO.5 (PEX IO1_5) | PEC-15, HD=6 |
| B12 | MIBSPI4NCS_1 | ch4 | IF_GPIO.6 (PEX IO1_6) | IF_GPIO.7 (PEX IO1_7) | 2s watchdog |

### 11.2 Master Board Connectors (v1.2.2)

#### 11.2.1 Supply Connector — J2009 (8-pin Micro-Fit)

| Pin | Signal | Description | HIL Relevance |
|-----|--------|-------------|---------------|
| 1 | CLAMP15/IGNITION | Ignition signal (wake) | Simulate ignition on/off |
| 2 | CLAMP30/SUPPLY+ | Battery supply + | Power supply to BMS |
| 3 | CLAMP30C/CONTACTOR_SUPPLY | Contactor coil supply | Measure contactor power |
| 4 | CLAMP31/SUPPLY- | Battery supply - (GND) | System ground reference |
| 5 | CLAMP31/SUPPLY- | Ground (duplicate) | |
| 6 | CLAMP30/SUPPLY+ | Supply + (duplicate) | |
| 7 | CLAMP30C/CONTACTOR_SUPPLY | Contactor supply (duplicate) | |
| 8 | CLAMP31/SUPPLY- | Ground (duplicate) | |

**Electrical**: Automotive 12V supply. CLAMP15 is logic-level ignition signal.

#### 11.2.2 CAN1 Connector — J2021 (4-pin Micro-Fit)

| Pin | Signal | MCU Peripheral | Register Base |
|-----|--------|----------------|---------------|
| 1 | GND | — | — |
| 2 | — (NC) | — | — |
| 3 | CAN_LOW | DCAN1 | canREG1 (0xFFF7DC00) |
| 4 | CAN_HIGH | DCAN1 | canREG1 (0xFFF7DC00) |

**Function**: IVT current sensor (RX: 0x521-0x527), external communication.
**Not isolated** — direct connection to TMS570 DCAN1 via CAN transceiver.

#### 11.2.3 CAN2 Connector — J2024 (4-pin Micro-Fit)

| Pin | Signal | MCU Peripheral | Register Base |
|-----|--------|----------------|---------------|
| 1 | GND | — | — |
| 2 | — (NC) | — | — |
| 3 | CAN_LOW | DCAN2 | canREG2 (0xFFF7DE00) |
| 4 | CAN_HIGH | DCAN2 | canREG2 (0xFFF7DE00) |

**Function**: Vehicle controller interface (state request RX: 0x210, BMS status TX: 0x220-0x260).
**Galvanically isolated** — transformer-coupled CAN transceiver for HV isolation.

#### 11.2.4 SPS Connectors — J2000, J2002-J2004, J2006-J2008, J2010 (4-pin Micro-Fit each, ×8)

| Pin | Signal | Direction | Description |
|-----|--------|-----------|-------------|
| 1 | SPS_FEEDBACK_X | Input | Contactor auxiliary contact feedback |
| 2 | FEEDBACK_SUPPLY | Output | Supply voltage for feedback circuit |
| 3 | SPS_OUT_X | Output | SPS switched output to contactor coil |
| 4 | GND | — | Ground reference |

**MCU Peripheral**: spiREG2 (0xFFF7F600) → SPS IC, with software CS on hetREG2 pin 1.
**NOTE**: J9002 schematic labels these pins as "MCU_SPI3" but the foxBMS software drives
`spiREG2` for SPS. This is a naming convention difference between the board schematic
and the TMS570 peripheral numbering. Verified via `spi_cfg.c` line 306.
**Contactor assignment** (foxBMS default):
- J2000: SPS channel 0 = String+ contactor
- J2002: SPS channel 1 = String- contactor
- J2003: SPS channel 2 = Precharge contactor
- J2004–J2010: Channels 3-7 (spare)

**Safety-critical**: Pin 1 feedback used by DIAG_ID_STRING_*_CONTACTOR_FEEDBACK (TSR-08).
**Feedback path**: SPS_FEEDBACK_X → PEX_PORT_EXPANDER1 (I2C port expander), NOT direct GPIO.
  - Channel 0 (J2000, String+) → PEX1 pin 0
  - Channel 1 (J2002, String-) → PEX1 pin 1
  - Channel 2 (J2003, Precharge) → PEX1 pin 2 (but `CONT_HAS_NO_FEEDBACK` — not monitored)
  - SPS feedback enable: hetREG2 pin 9 (MOSFET gate for current-sense circuit)
  - SPS reset: hetREG2 pin 16

**Design note**: Precharge contactor has no feedback monitoring (`CONT_HAS_NO_FEEDBACK`).
This is a known foxBMS design choice — precharge welding is detected indirectly via
current-on-open-string (TSR-15) or precharge timeout.

#### 11.2.5 Interlock Connector — J2033 (2-pin Micro-Fit)

| Pin | Signal | MCU Peripheral | Register |
|-----|--------|----------------|----------|
| 1 | INTERLOCK_HIGH | N2HET1[30] ball B11 | hetREG1 (0xFFF7B800) |
| 2 | INTERLOCK_LOW | N2HET1[29] ball A3 | hetREG1 (0xFFF7B800) |

**Function**: Physical safety loop. Current flows through INTERLOCK_HIGH, through external loop
(connectors, service disconnect), returns via INTERLOCK_LOW. Loop open = fault.
**MCU pins**: Feedback (IL_STATE) = hetREG1 pin 29 (input), HS enable = hetREG1 pin 30 (output).
**ADC channels**: IL_HS_VS (ch2), IL_LS_VS (ch3), IL_HS_CS (ch4), IL_LS_CS (ch5).
**DIAG ID**: DIAG_ID_INTERLOCK_FEEDBACK (TSR-13, FTTI 250 ms).

#### 11.2.6 Insulation Monitoring — J2034 (4-pin Micro-Fit)

| Pin | Signal | Direction | Description |
|-----|--------|-----------|-------------|
| 1 | VSUP- | — | Supply ground |
| 2 | VSUP+ | — | Supply voltage |
| 3 | OK/NOK Signal | Input | IMD status (digital) |
| 4 | PWM | Input | IMD measurement (PWM-encoded resistance) |

**Function**: Bender-type insulation monitoring device. Two variants supported:
  - **IR155 (PWM-based)**: OK/NOK on hetREG1 pin 27, PWM on hetREG2 pin 27, supply enable hetREG1 pin 25.
  - **iso165C (CAN-based)**: Communicates on CAN1 (canREG1), RX IDs 0x37 (info) and 0x23 (response), little-endian.
**DIAG ID**: Part of system monitoring suite (TSR-12).
**OPEN ITEM**: IR155 PWM pin assignment has an unresolved `TODO` comment in `bender_ir155_cfg.h`
line 155 (`hetREG2` pin 27) — developer was uncertain. Needs schematic verification before HIL.

#### 11.2.7 RS485 Connector — J2013 (6-pin Micro-Fit)

| Pin | Signal | Description |
|-----|--------|-------------|
| 1 | Y | RS485 differential pair 1+ |
| 2 | A | RS485 differential pair 2+ |
| 3 | GND | Ground |
| 4 | Z | RS485 differential pair 1- |
| 5 | B | RS485 differential pair 2- |
| 6 | GND | Ground |

**Function**: Secondary communication channel. Not used in default foxBMS configuration.

#### 11.2.8 Interface Board Connector — J9000 (40-pin Samtec)

| Pin | Signal | Function | isoSPI Usage |
|-----|--------|----------|-------------|
| 1 | MCU_SPI1.SOMI0 | SPI1 data in | isoSPI ch1/2 MISO |
| 2 | MCU_SPI1.SOMI1 | SPI1 data in (alt) | — |
| 3 | MCU_SPI1.SIMO0 | SPI1 data out | isoSPI ch1/2 MOSI |
| 4 | MCU_SPI1.SIMO1 | SPI1 data out (alt) | — |
| 5 | MCU_SPI1.CLK | SPI1 clock | isoSPI ch1/2 SCK |
| 6 | MCU_SPI1.CS1 | SPI1 chip select 1 | isoSPI channel 1 |
| 7 | MCU_SPI1.CS2 | SPI1 chip select 2 | isoSPI channel 2 |
| 8-10 | MCU_SPI1.CS3-5 | SPI1 chip selects | Spare |
| 11 | MCU_SPI4.SOMI | SPI4 data in | isoSPI ch3/4 MISO |
| 12 | MCU_SPI4.SIMO | SPI4 data out | isoSPI ch3/4 MOSI |
| 13 | MCU_SPI4.CLK | SPI4 clock | isoSPI ch3/4 SCK |
| 14 | MCU_SPI4.CS0 | SPI4 chip select 0 | isoSPI channel 3 |
| 15 | MCU_SPI4.CS1 | SPI4 chip select 1 | isoSPI channel 4 |
| 16-19 | MCU_SPI4.CS2-5 | SPI4 chip selects | Spare |
| 20-23 | IF_INT0-3 | Interrupt pins | GIOA_2/3/4/6 |
| 24-31 | IF_GPIO.0-7 | GPIO via port expander | LTC6820 enable/master |
| 32-33 | GND | Ground | Ground |
| 34-35 | MCU_3.3V | 3.3V supply | Logic power |
| 36-37 | MCU_5.0V_LDO | 5.0V supply | Peripheral power |
| 38 | VBB_12V | 12V from buck-boost | — |
| 39-40 | VSUP | Main supply voltage | — |

**MCU Registers**: spiREG1 (0xFFF7F400) for SPI1, spiREG4 (0xFFF7FA00) for SPI4.
**Safety-critical**: This is the primary path for all cell voltage and temperature data (TSR-01, TSR-02, TSR-06, TSR-07, TSR-10).

#### 11.2.9 Debug Connector — J3008 (38-pin Mictor)

Standard ARM JTAG + ETM trace port. Pins: TDI, TDO, TMS, TCK, TRST, RTCK, TRACECLK, TRACECTL, ETMDATA0-15.
**HIL Relevance**: JTAG access for gcov coverage extraction during HIL execution.

#### 11.2.10 Ethernet Connector — J2001 (RJ45, 12-pin)

Dual-port Ethernet (TX1/RX1, TX2/RX2) with LED indicators. Not used in default BMS configuration.

### 11.3 Slave Board Connectors (18-cell LTC6813-1, v1.1.3)

#### 11.3.1 Cell Voltage Sense Connector (24-pin)

| Pin | Signal | LTC6813 Input | Description |
|-----|--------|---------------|-------------|
| 1 | VBAT- | C0 (negative ref) | Battery module negative terminal |
| 2 | CELL_0+ | C0+ | Cell 0 positive terminal |
| 3 | CELL_2+ | C2+ | Cell 2 positive terminal |
| 4 | CELL_4+ | C4+ | Cell 4 positive terminal |
| 5 | CELL_6+ | C6+ | Cell 6 positive terminal |
| 6 | CELL_8+ | C8+ | Cell 8 positive terminal |
| 7 | CELL_10+ | C10+ | Cell 10 positive terminal |
| 8 | CELL_12+ | C12+ | Cell 12 positive terminal |
| 9 | CELL_14+ | C14+ | Cell 14 positive terminal |
| 10 | CELL_16+ | C16+ | Cell 16 positive terminal |
| 11 | VBAT+ | C17+ (positive ref) | Battery module positive terminal |
| 12 | NC | — | — |
| 13 | CELL_0- | C0- (= VBAT-) | Cell 0 negative terminal |
| 14 | CELL_1+ | C1+ | Cell 1 positive terminal |
| 15 | CELL_3+ | C3+ | Cell 3 positive terminal |
| 16 | CELL_5+ | C5+ | Cell 5 positive terminal |
| 17 | CELL_7+ | C7+ | Cell 7 positive terminal |
| 18 | CELL_9+ | C9+ | Cell 9 positive terminal |
| 19 | CELL_11+ | C11+ | Cell 11 positive terminal |
| 20 | CELL_13+ | C13+ | Cell 13 positive terminal |
| 21 | CELL_15+ | C15+ | Cell 15 positive terminal |
| 22 | CELL_17+ | C17+ | Cell 17 positive terminal |
| 23-24 | NC | — | — |

**Electrical ratings**: Cell voltage range 0–5V, module voltage 16–90V.
**ADC**: LTC6813 internal 16-bit ADC, ~0.1 mV/LSB, total error ±2.2 mV (7kHz, 25°C).
**Safety-critical**: Direct measurement path for TSR-01 (OV, ASIL D) and TSR-02 (UV, ASIL C).

**NOTE**: Pins are NOT sequential — even-numbered cells on pins 2-11 (row 1), odd-numbered
cells on pins 14-22 (row 2). Cell emulator wiring must account for this interleaved layout.

#### 11.3.2 Temperature Sensor Connector (16-pin)

| Pin | Signal | LTC6813 GPIO | Description |
|-----|--------|--------------|-------------|
| 1 | T-SENSOR_0 | GPIO1 (MUX) | NTC sensor 0, terminal 1 |
| 2 | T-SENSOR_1 | GPIO2 (MUX) | NTC sensor 1, terminal 1 |
| 3 | T-SENSOR_2 | GPIO3 (MUX) | NTC sensor 2, terminal 1 |
| 4 | T-SENSOR_3 | GPIO4 (MUX) | NTC sensor 3, terminal 1 |
| 5 | T-SENSOR_4 | GPIO5 (MUX) | NTC sensor 4, terminal 1 |
| 6 | T-SENSOR_5 | GPIO1 (MUX) | NTC sensor 5, terminal 1 |
| 7 | T-SENSOR_6 | GPIO2 (MUX) | NTC sensor 6, terminal 1 |
| 8 | T-SENSOR_7 | GPIO3 (MUX) | NTC sensor 7, terminal 1 |
| 9-16 | FUSED_VBAT- | — | NTC sensor return (all share VBAT-) |

**Electrical**: NTC nominal 10 kΩ. Measured via LTC6813 GPIO/ADC multiplexer.
**Safety-critical**: Measurement path for TSR-06 (OT, ASIL C) and TSR-07 (UT, ASIL B).

#### 11.3.3 Daisy Chain Connectors (2-pin each)

| Connector | Pin 1 | Pin 2 | Function |
|-----------|-------|-------|----------|
| Daisy Input | IN+ | IN- | isoSPI from previous slave (or interface board for first slave) |
| Daisy Output | OUT+ | OUT- | isoSPI to next slave in chain |

**Isolation**: Transformer-coupled differential signaling. Galvanic isolation between
master-side (low-voltage) and slave-side (high-voltage battery domain).

#### 11.3.4 Analog Inputs Connector (18-pin)

Pins 1-16: ANALOG-IN_0 to ANALOG-IN_15 (0-5V range), Pin 17: +3.0V VREF2, Pin 18: FUSED_VBAT- (GND).
Used for auxiliary measurements. Not in primary safety path.

#### 11.3.5 Digital I/O Connector (9-pin)

Pins 1-7: DIGITAL-IO_0 to DIGITAL-IO_6 (0-5V, bidirectional), Pin 8: +5V VREG, Pin 9: FUSED_VBAT-.
Used for GPIO expansion. Not in primary safety path.

### 11.4 Interface Board Connectors (LTC6820, v1.0.3)

#### 11.4.1 Master Connector (40-pin, mates with J9000)

The interface board connects to the master board via J9000. Key signal mapping:

| Master J9000 Pin | Interface Signal | isoSPI Function |
|------------------|-----------------|-----------------|
| 1 (SPI1.SOMI0) | SPI1 MISO | Data from LTC6813 via LTC6820 ch1/2 |
| 3 (SPI1.SIMO0) | SPI1 MOSI | Commands to LTC6813 via LTC6820 ch1/2 |
| 5 (SPI1.CLK) | SPI1 SCK | Clock for ch1/2 |
| 6 (SPI1.CS1) | SPI1 CS1 | Chip select for isoSPI channel 1 |
| 7 (SPI1.CS2) | SPI1 CS2 | Chip select for isoSPI channel 2 |
| 24 (IF_GPIO.0) | Port expander IO1_0 | LTC6820 ch1 ENABLE |
| 25 (IF_GPIO.1) | Port expander IO1_1 | LTC6820 ch1 MASTER select |
| 26 (IF_GPIO.2) | Port expander IO1_2 | LTC6820 ch2 ENABLE |
| 27 (IF_GPIO.3) | Port expander IO1_3 | LTC6820 ch2 MASTER select |

**NOTE**: GPIO pins 24-31 go through an I2C port expander on the interface board, not
direct GPIO from TMS570. The port expander is accessed via I2C from the master.

#### 11.4.2 isoSPI Connectors (2-pin each)

| Pin | Signal | Description |
|-----|--------|-------------|
| 1 | isospi_p | isoSPI positive (differential) |
| 2 | isospi_n | isoSPI negative (differential) |

One connector per daisy chain direction. The LTC6820 converts SPI (single-ended, master domain)
to isoSPI (differential, transformer-coupled, battery domain).

### 11.5 Critical Signal Paths (TSR → Physical Path → Probe Points)

Each signal path maps a TSR to the complete chain from sensor to actuator. Every node
is classified as an observation point (O), fault injection point (F), or both (O/F).

#### 11.5.1 TSR-01/02: Cell Voltage Path (ASIL D / ASIL C)

```
Cell terminal (O/F)
  → Kelvin sense wire → Slave cell connector pin CELL_x+ (O/F)
  → PCB trace → RC filter → LTC6813 ADC input C0-C17
  → LTC6813 internal ADC (16-bit, ±2.2mV @25°C) (O: via RDCV command)
  → isoSPI TX (differential, transformer-coupled) (O/F: break daisy chain)
  → Interface board LTC6820 → SPI1 SOMI0
  → J9000 pin 1 → Master board SPI1 (O: logic analyzer on J9000)
  → TMS570 MibSPI1 (spiREG1, 0xFFF7F400)
  → DMA transfer to RAM buffer
  → afe_ltc6813.c: DECAN decode → DATA_BLOCK_CELL_VOLTAGE (O: database read)
  → SOA_CheckCellVoltage() → compare vs BC_VOLTAGE_MAX_MSL (2800mV) / MIN (1500mV)
  → DIAG_Handler(DIAG_ID_CELLVOLTAGE_*_MSL) → threshold counter (50/10ms)
  → FATAL → BMS_STATEMACHINE_ERROR
  → CONT_OpenAll() → SPS driver → spiREG2 (0xFFF7F600)
  → J9002 → SPS IC → J200x pin 3 (SPS_OUT_X) → contactor coil de-energized (O/F)
  → Contactor mechanical open (20-50ms)
  → J200x pin 1 (SPS_FEEDBACK_X) → PEX_PORT_EXPANDER1 (I2C) → verification (O)
```

**FTTI**: 750 ms (OV/UV)
**HIL probe points**: Cell connector (emulator), J9000 (logic analyzer), J200x (contactor state), CAN bus (0x240-0x245 cell voltages)

#### 11.5.2 TSR-04/05: Current Path (ASIL B / ASIL C)

```
Battery string current path
  → IVT shunt resistor (high-precision, in-line)
  → IVT electronics: ADC → CAN frame encoding
  → CAN bus → J2021 pin 4 (CAN_HIGH) / pin 3 (CAN_LOW) (O/F)
  → CAN transceiver → TMS570 DCAN1 (canREG1, 0xFFF7DC00)
  → CAN RX handler → can_cbs_rx_current-sensor.c
  → DATA_BLOCK_CURRENT (O: database read)
  → SOA_CheckCurrent() → compare vs BC_CURRENT_MAX_*_MSL
  → DIAG_Handler(DIAG_ID_OVERCURRENT_*_MSL) → threshold counter (10/10ms)
  → FATAL → BMS_STATEMACHINE_ERROR → contactor open chain (same as 11.5.1)
```

**FTTI**: 250 ms
**HIL probe points**: J2021 (CAN injection), CAN bus monitoring, J200x (contactor state)
**NOTE**: IVT messages: 0x521 (current), 0x522-0x524 (voltage V1-V3), 0x525 (temp), 0x526 (power), 0x527 (coulomb count)

#### 11.5.3 TSR-06/07: Temperature Path (ASIL C / ASIL B)

```
NTC thermistor (10kΩ nominal)
  → Slave temp connector pin T-SENSOR_x (O/F: substitute with precision resistor)
  → PCB trace → LTC6813 GPIO/ADC multiplexer
  → LTC6813 ADC conversion (MUX scan, ~2ms per channel)
  → isoSPI → Interface → SPI1 → TMS570 (same physical path as cell voltage)
  → afe_ltc6813.c: temperature DECAN → DATA_BLOCK_CELL_TEMPERATURE (O)
  → SOA_CheckTemperatures() → compare vs OT/UT limits (45/55°C, -20°C)
  → DIAG_Handler(DIAG_ID_TEMP_*_MSL) → threshold counter (500/10ms = 5000ms)
  → FATAL → BMS_STATEMACHINE_ERROR → contactor open chain
```

**FTTI**: 6050 ms (justified by thermal inertia)
**HIL probe points**: Temp connector (substitution resistor bank), CAN (0x260 mux temps)
**NOTE**: Shares isoSPI path with cell voltage. AFE MUX failure detected by DIAG_ID_AFE_MUX (TSR-10).

#### 11.5.4 TSR-03: Deep Discharge Path (QM)

Same measurement path as TSR-02 (cell voltage), but with threshold=1 and 100ms delay.
**FTTI**: 160 ms. Triggers on extreme undervoltage below recovery threshold.

#### 11.5.5 TSR-08: Contactor Feedback Path (ASIL B)

```
Contactor auxiliary contact (normally-open or normally-closed)
  → Wiring → J200x pin 1 (SPS_FEEDBACK_X) (O/F: open wire, short to GND/VCC)
  → Feedback conditioning circuit → PEX_PORT_EXPANDER1 (I2C port expander)
  → Contactor driver: compare feedback state vs SPS commanded state
  → Mismatch → DIAG_Handler(DIAG_ID_STRING_*_CONTACTOR_FEEDBACK)
  → Threshold counter (20/10ms = 200ms) + 100ms delay
  → FATAL → BMS_STATEMACHINE_ERROR
```

**FTTI**: 350 ms
**HIL probe points**: J200x pin 1 (relay to simulate feedback), J200x pin 3 (SPS output state)
**Covers**: Welding detection (commanded open, feedback closed) AND stuck-open detection.

#### 11.5.6 TSR-09: Current Sensor Communication Path (ASIL B)

```
IVT current sensor → CAN frame (periodic, ~10ms cycle)
  → J2021 (CAN1) → TMS570 DCAN1
  → CAN RX handler: message receive timestamp
  → Timeout check: if no message received within expected period
  → DIAG_Handler(DIAG_ID_CURRENT_SENSOR_RESPONDING) → counter (100/10ms)
  → 200ms delay → FATAL → ERROR → contactors open
```

**FTTI**: 1250 ms (main current), 160 ms (voltage channels), 3050 ms (CC/EC)
**HIL injection**: Stop transmitting IVT CAN frames to trigger timeout.

#### 11.5.7 TSR-10: AFE Communication Path (ASIL D support)

```
TMS570 SPI1 → J9000 → Interface LTC6820 → isoSPI → Slave LTC6813
  → SPI transaction: command TX + data RX with PEC-15 CRC
  → PEC check in afe_ltc6813.c
  → Failure → DIAG_Handler(DIAG_ID_AFE_SPI or AFE_COMMUNICATION_INTEGRITY)
  → Threshold counter (5/10ms = 50ms) + 100ms delay
  → FATAL → ERROR → contactors open
```

**FTTI**: 200 ms (SPI/CRC), 160 ms (config mismatch)
**HIL injection**: Break isoSPI daisy chain (relay on daisy connector), corrupt SPI data.

#### 11.5.8 TSR-11: CAN Communication Path

```
Vehicle controller → CAN bus → J2024 (CAN2, isolated) or J2021 (CAN1)
  → TMS570 DCAN → CAN RX handler
  → Message receive timeout monitoring
  → DIAG_Handler(DIAG_ID_CAN_TIMING) → counter (100/10ms)
  → 200ms delay → FATAL → ERROR → contactors open
```

**FTTI**: 1250 ms
**HIL injection**: Stop sending expected CAN messages (disconnect CAN tool, or stop TX task).

#### 11.5.9 TSR-12: System Monitoring (ASIL D)

```
TMS570 hardware self-test:
  ├── CPU lockstep comparator → ESM (Error Signaling Module)
  ├── RAM ECC → ESM
  ├── Flash CRC → DIAG_ID_FLASHCHECKSUM
  └── RTOS task timing → DIAG_ID_SYSTEM_MONITORING
→ Any single event → FATAL (threshold=1, delay=0) → ERROR → contactors open
```

**FTTI**: ~51 ms
**HIL limitation**: Hardware self-test faults cannot be injected without modifying MCU silicon.
SIL-only test: POSIX stubs suppress these DIAGs. HIL tests verify the DIAG is configured but
cannot trigger it via external stimulus.

#### 11.5.10 TSR-13: Interlock Loop Path

```
Service disconnect / connector → external wiring loop
  → J2033 pin 1 (INTERLOCK_HIGH) → current source
  → Loop through external connectors, service disconnect switch
  → J2033 pin 2 (INTERLOCK_LOW) → current return
  → hetREG1 pin 29 → interlock.c: compare current/voltage against threshold
  → DIAG_Handler(DIAG_ID_INTERLOCK_FEEDBACK) → counter (10/10ms)
  → 100ms delay → FATAL → ERROR → contactors open
```

**FTTI**: 250 ms
**HIL injection**: Relay on J2033 pins to open interlock loop.

#### 11.5.11 TSR-14: SBC Reset Path

```
NXP FS8x SBC → SPI2 (spiREG2, 0xFFF7F600) ↔ TMS570
  ├── Watchdog: MCU must service within window
  ├── RSTB pin: SBC → MCU reset line (on J9002: SBC_MCU_RESET pin 80)
  └── FS0B pin: SBC → safety output (on J9002: SBC_MCU_FS0B pin 79)
→ RSTB assertion detected → DIAG_Handler(DIAG_ID_SBC_RSTB_ERROR)
→ Threshold=1, delay=100ms → FATAL → ERROR → contactors open
```

**FTTI**: 160 ms
**HIL limitation**: Cannot externally trigger SBC reset without access to SBC watchdog.
Test via: deliberate watchdog miss (software fault injection) or SBC FS0B pin manipulation.

#### 11.5.12 TSR-15: Current on Open String Path

```
All contactors commanded OPEN (SPS_OUT_X = 0)
  → IVT measures string current → CAN → J2021 → DCAN1
  → Current value > threshold (should be ~0A with contactors open)
  → DIAG_Handler(DIAG_ID_CURRENT_ON_OPEN_STRING) → counter (10/10ms)
  → 100ms delay → FATAL → ERROR
```

**FTTI**: 250 ms
**HIL injection**: Apply current through string with contactors open (simulates welded contactor
bypassing the feedback detection, or external fault path).

### 11.6 Probe Point Map for Needle Bed / HIL Adapter

This table maps every testable signal to its physical access point and the TSRs it covers.

| ID | Connector | Pin(s) | Signal | Type | TSR Coverage | Probe Method |
|----|-----------|--------|--------|------|-------------|--------------|
| PP-01 | Slave Cell | 1-22 | CELL_0+ to CELL_17+, VBAT± | O/F | TSR-01,02,03 | Cell emulator channels |
| PP-02 | Slave Temp | 1-8 | T-SENSOR_0 to 7 | O/F | TSR-06,07 | Precision resistor bank |
| PP-03 | Slave Temp | 9-16 | FUSED_VBAT- (return) | O | TSR-06,07 | GND reference |
| PP-04 | Slave Daisy In | 1-2 | IN+/IN- | F | TSR-10 | Relay (break chain) |
| PP-05 | Slave Daisy Out | 1-2 | OUT+/OUT- | F | TSR-10 | Relay (break chain) |
| PP-06 | J2021 CAN1 | 3-4 | CAN_H/CAN_L | O/F | TSR-04,05,09,15 | PCAN/python-can |
| PP-07 | J2024 CAN2 | 3-4 | CAN_H/CAN_L | O/F | TSR-11 | PCAN/python-can |
| PP-08 | J200x SPS | 1 | SPS_FEEDBACK_X | O/F | TSR-08 | Relay (simulate feedback) |
| PP-09 | J200x SPS | 3 | SPS_OUT_X | O/F | TSR-01-15 | Current probe / digital |
| PP-10 | J2033 | 1-2 | INTERLOCK_H/L | O/F | TSR-13 | Relay (break loop) |
| PP-11 | J2034 | 3 | IMD OK/NOK | O/F | TSR-12 | Digital signal |
| PP-12 | J2034 | 4 | IMD PWM | O/F | TSR-12 | PWM generator |
| PP-13 | J2009 | 1 | CLAMP15 | F | — | Relay (ignition control) |
| PP-14 | J9000 | 1,3,5 | SPI1 SOMI/SIMO/CLK | O | TSR-10 | Logic analyzer |
| PP-15 | J3008 | 11,15,17,19 | JTAG TDO/TCK/TMS/TDI | O | — | JTAG debugger |
| PP-16 | J9002 | 79 | SBC_MCU_FS0B | O/F | TSR-14 | Digital signal |
| PP-17 | J9002 | 80 | SBC_MCU_RESET | O | TSR-14 | Digital monitor |
| PP-18 | J2021 CAN1 | 3-4 | CAN1 bus termination | O | TSR-04,05,09 | Verify 120Ω between H/L |
| PP-19 | J2024 CAN2 | 3-4 | CAN2 bus termination | O | TSR-11 | Verify 120Ω between H/L |

**CAN termination note**: The foxBMS master board includes internal 120Ω termination resistors
on both CAN1 and CAN2. The HIL bench CAN interface (PCAN, python-can adapter) typically also
has internal termination. With both endpoints terminated, the bus has 60Ω differential
impedance — this is correct for a two-node bus. If a third CAN node is added (e.g., CANoe
for monitoring), its termination must be DISABLED to avoid triple-termination (40Ω, causing
signal quality issues). Verify termination resistance with a multimeter before first test.

### 11.7 Galvanic Isolation Boundaries

```
          LOW-VOLTAGE DOMAIN                    HIGH-VOLTAGE DOMAIN
    (Master + Interface board)                (Slave + Battery cells)
                                    │
  TMS570 MCU ←→ SPI1 ←→ LTC6820   │    LTC6813 ←→ Cells (16-90V)
                                 ──┤──  Transformer-coupled isoSPI
  CAN2 transceiver               ──┤──  Isolated CAN (J2024)
                                    │
  CAN1 transceiver ←→ IVT          │    IVT shunt (in current path)
     (NOT isolated on CAN1 side)    │
                                    │
  SPS IC ←→ Contactors             │    Contactor main contacts
     (galvanic separation by        │    (high-voltage battery bus)
      contactor coil/contact gap)   │
```

**Critical isolation point**: The isoSPI transformer on the interface board provides the
primary galvanic isolation between the master (low-voltage) and slave (battery-voltage)
domains. All cell voltage and temperature data crosses this boundary.

**CAN1 is NOT isolated**: The IVT current sensor communicates on CAN1 (J2021), which is
not galvanically isolated on the master board. The IVT itself provides isolation internally.

### 11.8 Known Gotchas for HIL Test Design (from Lessons Learned)

These are verified pitfalls discovered during SIL integration that directly affect HIL test
harness design. Each references a lesson ID from the lesson registry at
`foxbms-posix/docs/lessons-learned/embedded/foxbms-integration.md` (28 lessons total).
Full HIL signal path analysis: `docs/lessons-learned/embedded/foxbms-hil-signal-path-analysis.md`.

| # | Lesson | Signal Path | Gotcha | Required Action |
|---|--------|-------------|--------|-----------------|
| 1 | L-009 | Cell/IVT validity | `invalidFlag` uses inverted logic: **1 = VALID**, 0 = invalid | Plant/emulator MUST send `invalidFlag=1` for valid data, or BMS rejects all measurements |
| 2 | L-010 | Cell voltage CAN | Only 8 cells per CAN mux group (0x270). Need **5 mux groups** (0-4) for all 18 cells | Cell emulator must cycle through mux groups 0-4 in plant model; single group = 10 cells missing |
| 3 | L-015 | BMS state (0x220) | BMS state signal on CAN flickers due to multiplexing timing | Test harness must read state via `BMS_GetState()` API or internal database, never by sniffing CAN 0x220 |
| 4 | L-018/L-027 | Cell voltage plausibility | Single-cell OV is rejected as outlier if spread > 300 mV (`PL_CELL_VOLTAGE_SPREAD_TOLERANCE_mV`, WARNING severity only) | OV fault injection must set **ALL 18 cells** to overvoltage simultaneously, not just one cell |
| 5 | L-019 | IVT current (0x521) | Current flowing before contactors close is physically impossible | Plant model must gate IVT current signal on contactor feedback state (0x7F0); send 0 mA until contactors confirmed closed |
| 6 | L-011 | IVT Voltage 3 (0x524) | Missing V3 signal triggers DIAG timeout (TSR-09) | Plant model must send 0x524 every cycle alongside 0x521-0x523; omission = spurious timeout fault |
| 7 | L-017 | OT fault trigger | Temperature alone may not trigger OT fault — requires **both** current > 0 AND temperature > threshold | OT test must apply load current simultaneously with elevated temperature |
| 8 | L-014 | Test infrastructure | Stale foxbms-vecu processes ghost CAN frames at 100× normal rate | `killall -9 foxbms-vecu` before each HIL test run; verify CAN bus is clean before stimulus |

**Impact on SYS.4 test design**: Gotchas 1-6 are **test-blocking** — if not addressed in the plant
model or test harness, the affected test cases will produce false results (either false pass or
false fail). Gotcha 4 is particularly dangerous because a single-cell OV test would appear to
pass (no fault triggered) when in fact the plausibility check is silently rejecting the stimulus.

### 11.9 Cross-Check Verification Status

Agent cross-check performed 2026-03-23 against foxBMS v1.10.0 source code.

| Signal Path | HW CSV | SW Register | DMA | Status | Notes |
|-------------|--------|-------------|-----|--------|-------|
| SPI1 → AFE (LTC6813) | J9000 pins 1-10 | spiREG1 | CH0/CH1 | VERIFIED | CS1 = LTC6820 ch1 |
| SPI2 → SPS | J9002 + J200x | spiREG2 | CH2/CH3 | VERIFIED | SW CS via hetREG2 pin 1 (schematic labels as "SPI3") |
| CAN1 → IVT | J2021 pins 3-4 | canREG1 | N/A (mailbox) | VERIFIED | IDs 0x521-0x527, 6-byte, big-endian |
| CAN2 → Vehicle | J2024 pins 3-4 | canREG2 | N/A (mailbox) | VERIFIED | No default RX/TX callbacks (integrator-specific) |
| Interlock | J2033 pins 1-2 | hetREG1 pins 29/30 | N/A | VERIFIED | ADC channels 2-5 for current/voltage |
| SPS feedback | J200x pin 1 | PEX1 pins 0-2 (I2C) | N/A | VERIFIED | Via I2C port expander, not direct GPIO |
| IMD (iso165C) | J2034 | canREG1, IDs 0x37/0x23 | N/A | VERIFIED | Little-endian (differs from all other foxBMS CAN) |
| IMD (IR155) | J2034 | hetREG1 p25/27, hetREG2 p27 | N/A | **OPEN** | Unresolved TODO on PWM pin in source code |

**Open items requiring resolution before Phase 3 (SYS.4 test cases):**
1. IR155 PWM pin assignment — verify hetREG2 pin 27 against master board schematic
2. Precharge contactor has no feedback monitoring — document as accepted gap in test coverage

---

## 12. Register-to-Connector Cross-Reference

This table maps MCU peripheral register bases to their physical connectors, enabling
software-hardware traceability for HIL test verification.

| MCU Peripheral | Register Base | TMS570 Address | Physical Connector | Signal Type |
|----------------|---------------|----------------|--------------------|-------------|
| DCAN1 | canREG1 | 0xFFF7DC00 | J2021 (CAN1) | CAN H/L |
| DCAN2 | canREG2 | 0xFFF7DE00 | J2024 (CAN2) | CAN H/L (isolated) |
| MibSPI1 | spiREG1 | 0xFFF7F400 | J9000 pins 1-10 | SPI → AFE (LTC6813 via LTC6820) |
| SPI2 | spiREG2 | 0xFFF7F600 | J9002 + J200x | SPI → SPS IC (SW CS via hetREG2 pin 1) |
| SPI3 | spiREG3 | 0xFFF7F800 | On-board | SPI → FRAM (diagnostic data persistence) |
| MibSPI4 | spiREG4 | 0xFFF7FA00 | J9000 pins 11-19 | SPI → isoSPI ch3/4 |
| SPI5 | spiREG5 | 0xFFF7FC00 | J9002 pins 6-18 | SPI → spare |
| N2HET1 | hetREG1 | 0xFFF7B800 | J2033 (interlock), J2034 (IMD) | [B11] ch30 IL_HS_EN, [A3] ch29 IL_STATE, [M3] ch25 IR155_EN, [A9] ch27 IR155_OK |
| N2HET2 | hetREG2 | 0xFFF7B900 | J200x, J2021, J2034 | [D8] ch01 SPS_CS, [T5] ch20 SPS_RST, ch09 SPS_FB_EN, [N4] ch18 CAN1_EN, [D7] ch02 IR155_PWM |
| PEX1 | I2C port expander | via i2cREG1 | J200x pin 1 (feedback) | Contactor feedback: ch0=String+, ch1=String-, ch2=Precharge |
| I2C1 | i2cREG1 | 0xFFF7D400 | J9002 pins 19-20 | I2C → peripherals |
| ADC1 | adcREG1 | 0xFFF7C000 | J9002 pins 58-61 | Analog inputs |
| ADC2 | adcREG2 | 0xFFF7C200 | J9002 pins 62-65 | Analog inputs |
| RTI | rtiREG1 | 0xFFFFFC00 | Internal | Timers, watchdog |
| ESM | esmREG | 0xFFFFF500 | Internal | Error signaling |

**Bus sharing note (CONSTRAINT-001):** spiREG2 is shared between SPS IC and NXP FS8x SBC.
Both use software chip selects on separate hetREG2 pins ([D8] ch01 for SPS, SBC CS TBV).
SPS_Ctrl() must execute before SBC_Trigger() in the 10ms task. A hardware fault on SPI2
disables both contactor actuation and watchdog — SBC timeout resets MCU → fail-safe open.

**⚠ TBV markers:** Items marked `⚠ TBV` (To Be Verified) have HET channel assignments from
`can_cfg.h`/`sps_cfg.h` but their physical ball assignments could not be confirmed from
HalCoGen `HL_pinmux.c` (channel index beyond configured range or not in signal routing table).
These require schematic cross-reference for final verification.

---
*End of Document*
