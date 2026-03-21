# foxBMS POSIX Port

foxBMS 2 v1.10.0 Battery Management System running as a native Linux x86-64 process via SocketCAN. No TMS570 hardware required.

## Status: BMS in NORMAL Operation

Full state transition verified — no hacks, proper CAN data flow:
```
UNINITIALIZED → INITIALIZATION → IDLE → STANDBY → PRECHARGE → NORMAL
```

- 15+ periodic CAN message types on SocketCAN
- 18 cells × 3700mV, string voltage 66600mV
- SOC 50% (counting method), 3 contactors closed
- Plant model feeds realistic IVT + cell voltage data
- Precharge passes with matching string/bus voltages

## Quick Start

```bash
# Prerequisites: Ubuntu 24.04, GCC 13+, Python 3.12
git clone --recursive https://github.com/nhuvaoanh123/foxbms-posix.git
cd foxbms-posix

# Apply patches to foxBMS source
cd foxbms-2
for p in ../patches/patch_*.py; do python3 "$p"; done
cd ..

# Build
cd src && make clean && make -j4 && cd ..

# Set up virtual CAN
sudo ip link add vcan1 type vcan && sudo ip link set vcan1 up

# Run plant model (background)
cd src && python3 plant_model.py vcan1 &

# Run foxBMS vECU
FOXBMS_CAN_IF=vcan1 ./foxbms-vecu
```

### Smoke Test
After starting both processes, verify with `candump vcan1`:
- `0x220` BMS State: first byte `0x17` = state 7 (NORMAL) + 1 connected string
- `0x235` SOC: byte 5 = `0xC8` = 50%
- `0x250` Cell Voltages: non-zero data with mux cycling

## Architecture

```
Plant Model (Python)  <-->  SocketCAN (vcan1)  <-->  foxBMS vECU (C binary)
  sends:                                              processes:
  - 18 cell voltages (0x270)                          - BMS state machine
  - IVT current 0A (0x521)                            - SOC estimation
  - IVT voltages 66.6V (0x522-524)                    - Contactor control
  - Cell temps 25C (0x280)                             - Precharge sequence
  - State requests (0x210)                             - 15+ CAN TX messages
```

## Documentation

| Document | Description |
|----------|-------------|
| [STATUS.md](STATUS.md) | Full implementation history, 14 fixes, architecture details |
| [PLAN.md](PLAN.md) | Roadmap: completed work + next phases |
| [GAP-ANALYSIS.md](GAP-ANALYSIS.md) | 33 gaps identified, 17 fixed/accepted, 16 remaining |
| [COVERAGE.md](COVERAGE.md) | Feature coverage matrix: 51 features across 7 categories |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | 10 common failure modes with diagnosis + fixes |
| [foxbms-posix-build-guide.md](foxbms-posix-build-guide.md) | Detailed build instructions, all patches listed |

## Repository Structure

```
foxbms-posix/
├── foxbms-2/              ← Upstream foxBMS v1.10.0 (git submodule)
├── src/                   ← POSIX port source files
│   ├── Makefile                   Build system (auto-discovers 170+ sources)
│   ├── foxbms_posix_main.c        Entry point + cooperative main loop
│   ├── hal_stubs_posix.c          80+ HAL stubs + selective DIAG + SPS sim
│   ├── posix_overrides.h          ARM asm + assert overrides
│   ├── config_cpu_clock_hz.h      CPU clock for FreeRTOS config
│   ├── plant_model.py             Python battery simulator
│   ├── test_smoke.py              Automated smoke test (pass/fail)
│   └── foxbms_signals.dbc         CAN signal definitions
├── patches/               ← Python scripts to patch foxBMS source
│   └── apply_all.sh               Apply all patches in correct order
├── setup.sh               ← Single-command setup + build + test
├── GAP-ANALYSIS.md        ← 33 gaps, 17 resolved
├── COVERAGE.md            ← Feature coverage matrix
├── TROUBLESHOOTING.md     ← 10 failure modes with fixes
├── STATUS.md
├── PLAN.md
└── README.md
```

## Key Discoveries

1. **DECAN_DATA_IS_VALID = 1** (not 0) — cell voltage invalid flag is inverted
2. **SBC_STATEMACHINE_RUNNING = 2** (not 3) — enum value mismatch caused SYS timeout
3. **18 cells per module** — battery config uses BS_NR_OF_CELL_BLOCKS_PER_MODULE=18
4. **IVT Voltage 3 (0x524)** — redundancy module uses `highVoltage_mV[s][2]`, not [s][0]
5. **AFE runs in own FreeRTOS task** — must call `MEAS_Control()` explicitly in cooperative mode
6. **FreeRTOS POSIX port doesn't preempt** — cooperative mode is the only reliable approach

## Environment Variables

- `FOXBMS_CAN_IF=vcan1` — SocketCAN interface (default: vcan1)

## License

POSIX port files: Taktflow Systems 2026
foxBMS 2: BSD-3-Clause (Fraunhofer IISB)
