# foxBMS POSIX vECU — Status Report (2026-03-21)

## What We Built
A complete foxBMS 2 v1.10.0 Battery Management System running as a native Linux x86-64 process, communicating via SocketCAN. No TMS570 hardware required.

## Architecture
```
Plant Model (Python)  ←→  SocketCAN (vcan1)  ←→  foxBMS vECU (C binary)
   - IVT current             CAN frames           - BMS state machine
   - IVT voltage                                  - SOC estimation
   - Cell voltages                                - Contactor control
   - State requests                               - 15 CAN TX messages
```

## Step-by-Step Progress

### Step 1: Compile foxBMS for x86-64 Linux
**Problem**: foxBMS is designed for TMS570 (ARM Cortex-R5, big-endian) with TI CGT compiler.
**Solution**: Compile with GCC 13 on Ubuntu. Created `Makefile` with auto-discovery of 170+ source files and all include paths.
**Key fixes**: `-DFOXBMS_POSIX`, `-include posix_overrides.h`, suppress GCC 15 warnings.

### Step 2: Stub all hardware
**Problem**: 60+ TMS570 register bases (canREG1, systemREG1, spiREG1...) point to MMIO addresses (0xFFF7xxxx) → segfault on x86.
**Solution**:
- Patched ALL `HL_reg_*.h` headers: `#ifdef FOXBMS_POSIX → extern char posix_regX[]; #define regX ((type*)posix_regX)`
- 60+ RAM buffers (4KB each) in `hal_stubs_posix.c`
- Excluded hardware-access source files: `io.c`, `crc.c`, `spi.c`, `i2c.c`, `dma.c`, `fram.c`, `sps.c`, `pex.c`, `htsensor.c`, `sbc/*`, `diag.c`
- Provided 80+ function stubs returning OK/default values

### Step 3: Replace FreeRTOS scheduler with cooperative loop
**Problem**: FreeRTOS POSIX port (pthreads + SIGALRM) doesn't preempt tasks correctly. Engine task at REAL_TIME priority starves all other tasks.
**Solution**:
- Removed FreeRTOS scheduler entirely (no `vTaskStartScheduler`)
- Custom `foxbms_posix_main.c` with `while(1)` loop calling cyclic functions:
  - `FTSK_RunUserCodeCyclic1ms()` every 1ms
  - `FTSK_RunUserCodeCyclic10ms()` every 10ms (calls SYS_Trigger, BMS_Trigger, CAN_MainFunction)
  - `FTSK_RunUserCodeCyclic100ms()` every 100ms
- `OS_DelayTaskUntil` → `usleep()`, `OS_GetTickCount` → `clock_gettime()`
- Queue operations: ring buffers for CAN RX, direct-call for database

### Step 4: Fix FAS_ASSERT
**Problem**: foxBMS has ~100+ assertions that check hardware state. Without hardware, all fail → infinite loop (assert level 0).
**Solution**: `posix_overrides.h` sets `FAS_ASSERT_LEVEL = 2` (NO_OPERATION). Assertions fire but don't halt.

### Step 5: Fix DIAG_Handler
**Problem**: Even with no-op asserts, `DIAG_Handler` records errors → SYS state machine enters ERROR → BMS never initializes.
**Solution**: Excluded `diag.c`, stubbed `DIAG_Handler` to always return OK. `DIAG_IsAnyFatalErrorSet` returns false.

### Step 6: Fix SBC bypass
**Problem**: SYS state machine waits for SBC (NXP FS85xx safety chip) to initialize via SPI. SPI doesn't work on POSIX.
**Solution**:
- Excluded `sbc/*`, stubbed `SBC_GetState` → returns `SBC_STATEMACHINE_RUNNING` (value **2**, not 3!)
- `SBC_SetStateRequest` → returns `SBC_OK`
- **Bug found**: initial stub used enum value 3 (ERROR) instead of 2 (RUNNING). Caused SYS timeout → ERROR.

### Step 7: Fix CAN TX via SocketCAN
**Problem**: `canTransmit()` writes to hardware mailbox registers. foxBMS uses `canUpdateID` to set CAN ID, then `canTransmit` to send.
**Solution**:
- `canUpdateID` stores CAN ID per mailbox in RAM table
- `canTransmit` reads stored ID and calls `posix_can_send()` via SocketCAN
- SocketCAN opened in constructor (before `canInit`) because foxBMS sends CAN before SYS reaches CAN init

### Step 8: Fix CAN RX via SocketCAN
**Problem**: CAN RX path: hardware ISR → FreeRTOS queue → `CAN_ReadRxBuffer`. No ISR on POSIX.
**Solution**:
- Main loop reads SocketCAN non-blocking → fills ring buffer
- `OS_ReceiveFromQueue(ftsk_canRxQueue)` returns from ring buffer
- CAN node pointer set to `&can_node1` (matches foxBMS's `CAN_NODE_1`)

### Step 9: Fix database passthrough
**Problem**: `DATA_WRITE_DATA` sends to FreeRTOS database queue. `DATA_Task` reads queue and copies data. Without real queue, data is lost.
**Solution**:
- Made `DATA_IterateOverDatabaseEntries` non-static (`#ifdef FOXBMS_POSIX`)
- `OS_SendToBackOfQueue(ftsk_databaseQueue)` calls `DATA_IterateOverDatabaseEntries` directly
- Data is copied to database immediately, no queue needed

### Step 10: Fix contactor simulation
**Problem**: foxBMS controls contactors via SPS driver. `SPS_GetChannelPexFeedback` returns 0 (OPEN) → precharge fails.
**Solution**:
- SPS stubs track per-channel requested/actual state
- `SPS_RequestContactorState(ch, ON)` stores state=1
- `SPS_Ctrl()` copies requested → actual (1-cycle delay)
- `SPS_GetChannelPexFeedback` returns actual state

### Step 11: Fix IVT message encoding
**Problem**: Plant model IVT messages (0x521) had tick counter in status bytes. After 32 ticks, bit 5 of byte 1 sets "channel error" flag → foxBMS marks current as invalid.
**Solution**: Status bytes set to 0 (no errors). Message counter in bits [7:2] only, status bits [1:0] = 0.

### Step 12: Fix current sensor presence
**Problem**: SYS state machine checks `CAN_IsCurrentSensorPresent()` which reads `can_state.currentSensorPresent[]`. Flag only set when IVT messages processed through CAN ISR path (which doesn't exist on POSIX).
**Solution**: Patched `can.c`: `CAN_IsCurrentSensorPresent` returns true on `#ifdef FOXBMS_POSIX`.

### Step 13: Fix RTC bypass
**Problem**: SYS state machine waits for `RTC_IsRtcModuleInitialized()` which checks I2C RTC chip.
**Solution**: Patched `rtc.c`: returns true on POSIX.

## Current State

### What Works
- **SYS state machine**: RUNNING (state=5)
- **BMS state machine**: IDLE → STANDBY → PRECHARGE (contactors close!)
- **CAN TX**: 15 message types periodic (0x220, 0x221, 0x231-235, 0x240-245, 0x250, 0x260, 0x301)
- **CAN RX**: Plant model → SocketCAN → foxBMS callbacks
- **Database**: Direct passthrough (no queue)
- **SOC**: 50% initial (counting method)
- **Contactors**: SPS simulation tracks open/close per channel
- **Plant model**: Sends IVT current (0A), voltage (22.2V), state requests

### What Doesn't Work Yet
- **BMS NORMAL state**: Precharge voltage check fails
  - Root cause: cell voltages (0x270) not properly encoded in big-endian DBC format
  - foxBMS reads string voltage = 0mV (no valid cell data)
  - IVT pack voltage = 22200mV
  - Voltage difference > threshold → precharge abort → ERROR
- **Cell voltage encoding**: DBC big-endian signal encoding is complex (start_bit=11, length=13, Motorola byte order). Encoding function written but not yet verified.
- **Cell temperature encoding**: Similar to voltage, not yet verified

### Next Steps (to reach NORMAL)
1. Verify cell voltage 0x270 encoding by checking database values
2. If encoding wrong, use `cantools` Python library for correct DBC encoding
3. Once string voltage matches IVT voltage, precharge passes → contactors close → NORMAL
4. Add cell temperature 0x280 for plausibility checks
5. Implement dynamic current model for SOC changes

## File Inventory

### Our Source (src/)
| File | Lines | Purpose |
|------|-------|---------|
| `foxbms_posix_main.c` | ~200 | Entry point, cooperative loop, SocketCAN RX |
| `hal_stubs_posix.c` | ~500 | 80+ HAL stubs, SPS sim, DB passthrough, OS wrappers |
| `posix_overrides.h` | ~20 | Force-included: __asm stub, FAS_ASSERT no-op |
| `config_cpu_clock_hz.h` | 1 | CPU clock for FreeRTOS config |
| `Makefile` | ~90 | Auto-discovers 170+ source files |
| `plant_model.py` | ~100 | IVT data + state requests + cell voltages |

### Patches Applied to foxBMS (patches/)
| Patch | Target | What it does |
|-------|--------|-------------|
| `patch_sbc.py` | sbc.c | SBC_GetState → RUNNING |
| `patch_sbc2.py` | sbc.c | SBC_SetStateRequest → OK |
| `patch_rtc.py` | rtc.c | RTC_IsRtcModuleInitialized → true |
| `patch_can_sensor.py` | can.c | CAN_IsCurrentSensorPresent → true |
| `patch_database.py` | database.c | DATA_IterateOverDatabaseEntries → extern |
| `patch_database2.py` | database.c | Database iterate trace |
| `patch_ftask.py` | ftask_cfg.c | Init trace prints |
| `patch_sys2.py` | sys.c | SYS_Trigger state trace |
| `patch_bms2.py` | bms.c | BMS_Trigger state trace |
| `patch_all_regs.py` | HL_reg_*.h | All register bases → RAM |
| `patch_canreg.py` | HL_reg_can.h | CAN register bases → RAM |

### Source Files Excluded from Build
Total: 18 files excluded due to hardware register access
- `main.c`, `fstartup.c`, `io.c`, `crc.c`, `spi.c`, `spi_cfg.c`, `dma.c`, `i2c.c`
- `fram.c`, `sps.c`, `sps_cfg.c`, `pex.c`, `pex_cfg.c`, `htsensor.c`
- `sbc/*` (all), `diag.c`, `os_freertos.c`, `ftask_freertos.c`
