# FTASK Module (Task Configuration)

**Source**: [docs.foxbms.org — FTASK](https://iisb-foxbms.iisb.fraunhofer.de/foxbms/docs/latest/software/modules/task/ftask/ftask.html)
**Files**: `src/app/task/ftask/ftask.c`, `ftask.h`, `ftask_freertos.c`, `ftask_cfg.c`, `ftask_cfg.h`

---

## Task Structure (7 Tasks)

| Task | Period | Priority | Creator | User Code Function |
|------|--------|----------|---------|-------------------|
| **Engine** | Event-driven | Highest | `FTSK_CreateTaskEngine` | `FTSK_RunUserCodeEngine` |
| **1ms Cyclic** | 1ms | High | `FTSK_CreateTaskCyclic1ms` | `FTSK_RunUserCodeCyclic1ms` |
| **AFE** | Non-cyclic | Above-normal | `FTSK_CreateTaskAfe` | `FTSK_RunUserCodeAfe` |
| **10ms Cyclic** | 10ms | Normal | `FTSK_CreateTaskCyclic10ms` | `FTSK_RunUserCodeCyclic10ms` |
| **100ms Cyclic** | 100ms | Below-normal | `FTSK_CreateTaskCyclic100ms` | `FTSK_RunUserCodeCyclic100ms` |
| **I2C** | Non-cyclic | Low | `FTSK_CreateTaskI2c` | `FTSK_RunUserCodeI2c` |
| **100ms Algorithm** | 100ms | Lowest | `FTSK_CreateTaskCyclicAlgorithm100ms` | `FTSK_RunUserCodeCyclicAlgorithm100ms` |

## What Runs Where

### Engine Task (DO NOT MODIFY)
- `DATA_Task()` — copies queue data into database variables
- `SYSM_CheckNotifications()` — system monitoring
- Triggered by database queue events

### 1ms Task
- `FTSK_RunUserCodeCyclic1ms()`
- OS timer tick
- DIAG flag evaluation
- CAN RX buffer processing (`CAN_ReadRxBuffer()`)

### 10ms Task
- `FTSK_RunUserCodeCyclic10ms()`
- `SYS_Trigger()` — system state machine
- `BMS_Trigger()` — BMS state machine
- `CAN_MainFunction()` — CAN periodic TX

### 100ms Task
- `FTSK_RunUserCodeCyclic100ms()`
- Balancing, LED, SPS contactor control

### 100ms Algorithm Task
- `FTSK_RunUserCodeCyclicAlgorithm100ms()`
- SOC/SOE/SOF estimation
- Lower priority than 100ms task

### AFE Task
- `FTSK_RunUserCodeAfe()`
- `MEAS_Control()` — triggers AFE measurement cycle
- Non-cyclic, must yield CPU

### I2C Task
- `FTSK_RunUserCodeI2c()`
- PEX, RTC, humidity sensor communication

## Initialization Sequence

```
1. FTSK_InitializeUserCodeEngine()    → DATA_Initialize(), etc.
   os_boot = OS_ENGINE_RUNNING

2. FTSK_InitializeUserCodePreCyclicTasks()  → CAN_Initialize(), SPI_Initialize(), etc.
   os_boot = OS_PRE_CYCLIC_INIT_DONE

3. Cyclic tasks start running
```

## POSIX Port Mapping

| Production Task | POSIX Equivalent |
|----------------|-----------------|
| Engine task (event-driven) | Called in 1ms loop: `FTSK_RunUserCodeEngine()` |
| 1ms cyclic | `if (now - last_1ms >= 1000)` |
| 10ms cyclic | `if (now - last_10ms >= 10000)` |
| 100ms cyclic | `if (now - last_100ms >= 100000)` |
| 100ms algorithm | Called after 100ms cyclic |
| AFE task | `MEAS_Control()` called in 1ms loop |
| I2C task | Not needed (no I2C hardware) |

**Key difference**: All tasks run sequentially in one thread. No preemption. No priority. No concurrent database access. This is GAP-ANALYSIS GA-02 (accepted).
