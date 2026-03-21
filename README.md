# foxBMS POSIX vECU

foxBMS 2 v1.10.0 Battery Management System running as a native Linux x86-64 process via SocketCAN. No TMS570 hardware required.

## Architecture

```
Plant Model (Python)  <-->  SocketCAN (vcan1)  <-->  foxBMS vECU (C binary)
   - IVT current             CAN frames           - BMS state machine
   - IVT voltage                                  - SOC estimation
   - Cell voltages                                - Contactor control
   - State requests                               - 15 CAN TX messages
```

```
+---------------------------------------------+
|  plant_model.py (Python)                     |
|  +-------------+  +----------------------+  |
|  | Cell Model   |  | Contactor Feedback   |  |
|  | 6x 3.7V +/- |  | Track open/close     |  |
|  | noise        |  | from foxBMS 0x240    |  |
|  +------+-------+  +----------+-----------+  |
|         | 0x270/280/521/522    | contactor    |
|         v                      | state        |
+---------+----------------------+-------------+
          | SocketCAN (vcan1)    |
+---------+----------------------+-------------+
|  foxbms-vecu (C)               |              |
|  +-------------+  +-----------+-----------+  |
|  | CAN RX      |  | SPS Stub              |  |
|  | -> Database  |  | contactor feedback    |  |
|  | -> BMS Logic |  | from plant state      |  |
|  +-------------+  +-----------------------+  |
|  +-------------+  +-----------------------+  |
|  | BMS State   |  | CAN TX                |  |
|  | Machine     |--| 0x220 State           |  |
|  | SOC/SOE/SOF |  | 0x235 SOC             |  |
|  +-------------+  | 0x240 Contactors      |  |
|                    +-----------------------+  |
+-----------------------------------------------+
```

## Current Status (2026-03-21)

- **SYS state machine**: RUNNING (state=5)
- **BMS state machine**: IDLE -> STANDBY -> PRECHARGE (contactors close)
- **CAN TX**: 15 message types periodic
- **CAN RX**: Plant model -> SocketCAN -> foxBMS callbacks
- **SOC**: 50% (counting method, 0A current)
- **Blocker**: BMS cannot reach NORMAL — cell voltage CAN encoding (0x270) not verified

See [STATUS.md](STATUS.md) for the full 13-step implementation history.
See [GAP-ANALYSIS-HANDOFF.md](GAP-ANALYSIS-HANDOFF.md) for the gap analysis and student onboarding plan.

## Quick Start

### Prerequisites
- Ubuntu 24.04
- GCC 13+ (`sudo apt install gcc`)
- Python 3.12+ (`sudo apt install python3`)
- foxBMS 2 v1.10.0 cloned as submodule (see `.gitmodules`)
- HALCoGen headers from Windows build at `foxbms-2/build/app_host_unit_test/include/`

### Build & Run
```bash
# Set up virtual CAN
sudo ip link add vcan1 type vcan
sudo ip link set vcan1 up

# Apply patches to foxBMS source
cd foxbms-2
for p in ../patches/patch_sbc.py ../patches/patch_sbc2.py ../patches/patch_rtc.py \
         ../patches/patch_can_sensor.py ../patches/patch_database.py \
         ../patches/patch_ftask.py ../patches/patch_sys2.py \
         ../patches/patch_bms2.py ../patches/patch_all_regs.py; do
    python3 "$p"
done

# Build
cd ../src
make clean && make -j4

# Run plant model (terminal 1)
python3 plant_model.py vcan1 &

# Run foxBMS vECU (terminal 2)
FOXBMS_CAN_IF=vcan1 ./foxbms-vecu

# Monitor CAN (terminal 3)
candump vcan1 -t z
```

### Smoke Test
After starting both `plant_model.py` and `foxbms-vecu`, you should see:
1. stderr: `[init] Engine done`, `[init] PreCyclic done`, `[run] Entering main loop`
2. stderr: `[SPS] RequestContactor ch=X state=1` (contactors closing during PRECHARGE)
3. candump: CAN IDs 0x220, 0x221, 0x231-0x235, 0x240-0x245, 0x250, 0x260, 0x301

### Environment Variables
- `FOXBMS_CAN_IF=can0` — use real CAN hardware instead of vcan1

## File Layout

```
foxbms-posix/
+-- src/
|   +-- foxbms_posix_main.c    Entry point, cooperative loop, CAN RX
|   +-- hal_stubs_posix.c      80+ HAL stubs, SPS sim, OS wrappers
|   +-- posix_overrides.h      Force-included: ARM asm stubs, FAS_ASSERT no-op
|   +-- config_cpu_clock_hz.h  CPU clock for FreeRTOS config
|   +-- plant_model.py         Python plant model (IVT + cell data)
|   +-- Makefile               Auto-discovers 170+ foxBMS sources
+-- patches/                   Python scripts to patch upstream foxBMS
+-- foxbms-2/                  Upstream foxBMS 2 v1.10.0 (submodule)
+-- STATUS.md                  Detailed 13-step implementation history
+-- GAP-ANALYSIS-HANDOFF.md    Gap analysis and student onboarding
+-- PLAN.md                    Consolidated roadmap (remaining work)
```

## Key Design Decisions

1. **No FreeRTOS scheduler** — cooperative `while(1)` loop instead of pthreads. Simpler and avoids priority inversion issues on POSIX.
2. **FAS_ASSERT = NO_OPERATION** — 100+ hardware assertions would halt the process. Level 2 (no-op) lets foxBMS continue.
3. **DIAG_Handler = always OK** — all diagnostics suppressed to prevent ERROR state from missing hardware.
4. **Database passthrough** — `DATA_IterateOverDatabaseEntries` called inline instead of via FreeRTOS queue.
5. **SocketCAN** — standard Linux CAN interface, works with virtual (`vcan`) and real (`can0`) hardware.
