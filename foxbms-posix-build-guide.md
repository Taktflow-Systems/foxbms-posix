# foxBMS POSIX vECU — Build & Setup Guide

## Prerequisites
- Ubuntu 24.04
- GCC 13+ (`sudo apt install gcc`)
- Python 3.12+ (`sudo apt install python3`)
- foxBMS 2 v1.10.0 cloned as submodule (`git submodule update --init foxbms-2`)
- HALCoGen headers copied from Windows build at `foxbms-2/build/app_host_unit_test/include/`
- vcan1 interface (see below)

## Directory Structure
```
foxbms-posix/
+-- src/                            <-- Our POSIX port
|   +-- Makefile                    <-- Build system
|   +-- foxbms_posix_main.c         <-- Entry point (replaces main.c)
|   +-- hal_stubs_posix.c           <-- 80+ HAL function stubs
|   +-- posix_overrides.h           <-- Force-included, overrides ARM asm/asserts
|   +-- config_cpu_clock_hz.h       <-- CPU clock for FreeRTOS config
|   +-- plant_model.py              <-- Python script sending fake battery data
+-- patches/                        <-- Patch scripts for upstream foxBMS
|   +-- patch_sbc.py                <-- SBC_GetState -> RUNNING
|   +-- patch_sbc2.py               <-- SBC_SetStateRequest -> OK
|   +-- patch_rtc.py                <-- RTC_IsRtcModuleInitialized -> true
|   +-- patch_can_sensor.py         <-- CAN_IsCurrentSensorPresent -> true
|   +-- patch_database.py           <-- DATA_IterateOverDatabaseEntries -> extern
|   +-- patch_database2.py          <-- Database iterate trace
|   +-- patch_ftask.py              <-- ftask_cfg.c trace prints
|   +-- patch_sys2.py               <-- sys.c state trace
|   +-- patch_bms2.py               <-- bms.c state trace
|   +-- patch_all_regs.py           <-- All register bases -> RAM
|   +-- patch_canreg.py             <-- CAN register bases -> RAM (subset of above)
|   +-- patch_10ms2.py              <-- 10ms task trace
|   +-- patch_precharge.py          <-- Precharge debug trace
+-- foxbms-2/                       <-- Upstream foxBMS 2 v1.10.0 (submodule)
+-- STATUS.md                       <-- Detailed implementation history
+-- PLAN.md                         <-- Consolidated roadmap
+-- GAP-ANALYSIS-HANDOFF.md         <-- Gap analysis for handoff
```

## Source File Patches

Patches modify upstream foxBMS files in-place. They must be reapplied after any `git checkout` or `git clean` in `foxbms-2/`.

### Required Patches (apply in this order)

| # | Patch | Target File | What It Does |
|---|-------|-------------|-------------|
| 1 | `patch_all_regs.py` | `HL_reg_*.h` headers | Redirects all 60+ TMS570 register bases to RAM buffers |
| 2 | `patch_sbc.py` | `sbc.c` | `SBC_GetState` returns RUNNING on POSIX |
| 3 | `patch_sbc2.py` | `sbc.c` | `SBC_SetStateRequest` returns OK on POSIX |
| 4 | `patch_rtc.py` | `rtc.c` | `RTC_IsRtcModuleInitialized` returns true on POSIX |
| 5 | `patch_can_sensor.py` | `can.c` | `CAN_IsCurrentSensorPresent` returns true on POSIX |
| 6 | `patch_database.py` | `database.c` | `DATA_IterateOverDatabaseEntries` made non-static on POSIX |

### Optional Patches (debug tracing)

| Patch | Target | What It Does |
|-------|--------|-------------|
| `patch_ftask.py` | `ftask_cfg.c` | Debug trace prints in engine/precyclic init |
| `patch_sys2.py` | `sys.c` | SYS_Trigger state trace (first 50 + every 500th call) |
| `patch_bms2.py` | `bms.c` | BMS_Trigger state trace |
| `patch_database2.py` | `database.c` | Database iterate trace |
| `patch_10ms2.py` | 10ms task | 10ms task execution trace |
| `patch_precharge.py` | precharge | Precharge state debug output |

### Applying Patches
```bash
cd foxbms-posix/foxbms-2

# Required patches
python3 ../patches/patch_all_regs.py
python3 ../patches/patch_sbc.py
python3 ../patches/patch_sbc2.py
python3 ../patches/patch_rtc.py
python3 ../patches/patch_can_sensor.py
python3 ../patches/patch_database.py

# Optional: debug tracing
python3 ../patches/patch_ftask.py
python3 ../patches/patch_sys2.py
python3 ../patches/patch_bms2.py
```

Note: `patch_all_regs.py` must run first — it patches the HALCoGen headers that all other source files include. Order of remaining patches does not matter.

## Source Files Excluded from Build

| File | Reason |
|------|--------|
| `main.c` | Replaced by `foxbms_posix_main.c` |
| `fstartup.c` | TMS570 startup assembly |
| `io.c` | Direct GIO register dereference |
| `crc.c` | Hardware CRC peripheral (software CRC in stubs) |
| `spi.c`, `spi_cfg.c` | SPI register access |
| `dma.c` | DMA register access |
| `i2c.c` | I2C register access |
| `fram.c` | SPI FRAM (RAM stub in stubs) |
| `sps.c`, `sps_cfg.c` | Smart Power Switch (SPS stub in stubs) |
| `pex.c`, `pex_cfg.c` | Port Expander I2C (PEX stub in stubs) |
| `htsensor.c` | Humidity/Temp sensor I2C |
| `sbc/*` | NXP FS85xx Safety Basis Chip SPI |
| `diag.c` | Diagnostics (always-OK stub in stubs) |
| `os_freertos.c` | FreeRTOS OS wrapper (cooperative stubs) |
| `ftask_freertos.c` | FreeRTOS task/queue creation |
| AFE variants | adi, nxp, maxim, ltc, ti, debug/default (keep debug/can only) |
| SOC/SOE/SOH variants | debug, none (keep counting) |
| TS variants | All except epcos b57251v5103j060 |
| ethernet, bal variants | Not needed |

## Build Commands

```bash
cd foxbms-posix/src
make clean && make -j4
```

Output: `foxbms-vecu` binary in `src/`.

## Run Commands

```bash
# Create virtual CAN interface (requires root, once per boot)
sudo ip link add vcan1 type vcan
sudo ip link set vcan1 up

# Terminal 1: Start plant model
cd foxbms-posix/src
python3 plant_model.py vcan1

# Terminal 2: Start foxBMS vECU
cd foxbms-posix/src
FOXBMS_CAN_IF=vcan1 ./foxbms-vecu

# Terminal 3: Monitor CAN output
candump vcan1 -t z
```

To use real CAN hardware instead of virtual:
```bash
FOXBMS_CAN_IF=can0 ./foxbms-vecu
```

## Smoke Test Checklist

After starting both `plant_model.py` and `foxbms-vecu`:

- [ ] stderr shows `[init] HAL done`
- [ ] stderr shows `[init] Engine done`
- [ ] stderr shows `[init] PreCyclic done`
- [ ] stderr shows `[run] Entering main loop`
- [ ] stderr shows `[CAN-RX] Dequeued id=0x521` (IVT current received)
- [ ] stderr shows `[SPS] RequestContactor ch=X state=1` (precharge starting)
- [ ] candump shows CAN ID 0x220 (BMS State)
- [ ] candump shows CAN ID 0x235 (SOC — should show 50%)
- [ ] candump shows 15+ different CAN IDs within 10 seconds

## Key Design Decisions

### No FreeRTOS Scheduler
- Cooperative mode: `while(1)` loop calls cyclic functions at 1ms/10ms/100ms
- FreeRTOS kernel compiled but scheduler never started
- Queue operations go through ring buffers in `hal_stubs_posix.c`
- `OS_DelayTaskUntil` -> `usleep()`
- `OS_GetTickCount` -> `clock_gettime(CLOCK_MONOTONIC)`

### FAS_ASSERT = NO_OPERATION
- `posix_overrides.h` sets `FAS_ASSERT_LEVEL = 2` (no-op)
- Without this, ~100+ assertions halt the process on missing hardware
- foxBMS continues past all hardware checks

### DIAG_Handler = Always OK
- `diag.c` excluded, stub returns 0 (`DIAG_HANDLER_RETURN_OK`)
- Prevents ERROR state transitions from hardware-absent checks
- Future work: selective DIAG (suppress hardware errors, keep software checks)

### CAN via SocketCAN
- `canInit()` opens SocketCAN via `FOXBMS_CAN_IF` env var (default: `vcan1`)
- `canTransmit()` routes to `posix_can_send()` via SocketCAN
- CAN RX: main loop reads SocketCAN non-blocking -> ring buffer -> `OS_ReceiveFromQueue`

### Hardware Register RAM Buffers
- All TMS570 register bases (0xFFF7...) redirected to 4KB RAM buffers
- foxBMS writes to RAM instead of hardware — harmless but functional
- ~60 buffers defined in `hal_stubs_posix.c`

## Debugging Tips

### Reading BMS State from CAN
CAN ID 0x220 byte[0] encodes BMS state:
- `0x00` = UNINITIALIZED
- `0x03` = IDLE
- `0x06` = STANDBY
- `0x08` = PRECHARGE
- `0x0A` = NORMAL
- `0x0C` = CHARGE
- `0x0E` = ERROR

Filter candump: `candump vcan1,220:7FF -t z`

### Adding Trace Prints
foxBMS state machines are in:
- `src/app/engine/sys/sys.c` — SYS_Trigger() (system state machine)
- `src/app/application/bms/bms.c` — BMS_Trigger() (BMS state machine)

Add `fprintf(stderr, ...)` inside the state switch cases. The `patch_sys2.py` and `patch_bms2.py` scripts show this pattern.

### Identifying Assertion Fires
With `FAS_ASSERT_LEVEL=2`, assertions don't halt but they still execute the macro body. Add a trace to `FAS_ASSERT` in `posix_overrides.h` to log which file/line fires:
```c
#define FAS_ASSERT(x) do { if (!(x)) fprintf(stderr, "[ASSERT] %s:%d\n", __FILE__, __LINE__); } while(0)
```

## Windows Unit Test Setup

For running foxBMS unit tests on Windows (separate from POSIX vECU):

### Tools
- Ruby 3.4.4 + Ceedling 1.0.1
- GCC 15.2 (MSYS2 ucrt64)
- Python 3.12 + gcovr

### GCC 15 Compatibility Fixes (conf/unit/app_project_win32.yml)
```yaml
flags:
  test:
    compile:
      '*':
        - -Wno-enum-conversion
        - -Wno-incompatible-pointer-types
        - -Wno-attributes
        - -Wno-unterminated-string-initialization
        - -Wno-absolute-value
        - -fcommon
```

### Build Commands
```bash
export PATH="/c/Users/$USER/AppData/Local/Programs/Python/Python312/Scripts:$PATH"
python fox.py waf configure
python fox.py waf clean_app_host_unit_test
python fox.py ceedling test:all
```

**Critical**: Always `clean_app_host_unit_test` before a full test run. Stale Ceedling cache causes mock generation failures for files with hyphens in names.
