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
| [STATUS.md](STATUS.md) | Implementation history, 14 fixes, architecture details |
| [PLAN.md](PLAN.md) | Roadmap: Phase 1-2.5 done, Phase 3-4 planned |
| [docs/project/gap-analysis.md](docs/project/gap-analysis.md) | 33 gaps identified, 17 fixed, 3 accepted |
| [docs/project/coverage.md](docs/project/coverage.md) | 51 features across 7 categories |
| [docs/project/troubleshooting.md](docs/project/troubleshooting.md) | 10 failure modes with fixes |
| [docs/project/build-guide.md](docs/project/build-guide.md) | Detailed build instructions |
| [docs/project/audit-10-role.md](docs/project/audit-10-role.md) | 10-auditor review (1 CRITICAL, 9 HIGH findings) |
| [docs/aspice-cl2/](docs/aspice-cl2/) | **27 ASPICE CL2 + ISO 26262 ASIL-D documents** |
| [docs/foxbms-upstream/](docs/foxbms-upstream/) | 24 upstream foxBMS reference docs |

## Repository Structure

```
foxbms-posix/
├── README.md, STATUS.md, PLAN.md    ← Top-level project docs
├── setup.sh                          ← Single-command setup + build + test
├── foxbms-2/                         ← Upstream foxBMS v1.10.0 (submodule)
├── src/                              ← POSIX port source + tests
│   ├── foxbms_posix_main.c           Entry point + cooperative main loop
│   ├── hal_stubs_posix.c             80+ HAL stubs + selective DIAG + SPS sim
│   ├── sil_layer.c/h                 SIL probe + override instrumentation
│   ├── posix_overrides.h             ARM asm + assert overrides
│   ├── plant_model.py                Python battery simulator
│   ├── test_smoke.py                 Smoke test (BMS NORMAL, SOC, strings)
│   ├── test_integration.py           21 integration criteria
│   ├── test_asil.py                  50 ASIL safety criteria
│   └── test_sil_probes.py            76 SIL probe criteria
├── patches/                          ← Python scripts to patch foxBMS source
│   └── apply_all.sh                  Apply all patches in correct order
├── scripts/
│   └── trace-gen.py                  Traceability matrix generator (308 IDs)
├── .github/workflows/ci.yml          ← CI: smoke test + traceability + tests
├── halcogen-headers/                 ← Pre-generated TMS570 headers
└── docs/
    ├── aspice-cl2/                   27 ASPICE CL2 + ASIL-D documents
    │   ├── 00-assessment/            Scope, CL2 gap assessment, traceability
    │   ├── 01-MAN.3.../             Project management
    │   ├── 03-SYS.1.../            Stakeholder requirements (20)
    │   ├── 04-SYS.2.../            System requirements (36)
    │   ├── 05-SYS.3.../            System architecture
    │   ├── 06-SYS.4.../            System integration test
    │   ├── 07-SYS.5.../            System qualification test
    │   ├── 08-SWE.1.../            Software requirements (42)
    │   ├── 09-SWE.2.../            Software architecture (18 modules)
    │   ├── 10-SWE.3.../            Detailed design (85 DIAG entries)
    │   ├── 11-SWE.4.../            Unit test spec (45 cases)
    │   ├── 12-SWE.5.../            Integration test spec (34 cases)
    │   ├── 13-SWE.6.../            Qualification test spec (8 scenarios)
    │   ├── 14-SUP.1.../            Quality assurance plan
    │   ├── 15-SUP.8.../            Configuration management
    │   ├── 16-SUP.9.../            Problem resolution (33 gaps tracked)
    │   ├── 17-SUP.10../            Change request process
    │   └── 18-safety/               ISO 26262 (HARA, FSC, TSC, FMEA, FTTI, HSI)
    ├── foxbms-upstream/              24 reference docs from docs.foxbms.org
    ├── project/                      Gap analysis, coverage, troubleshooting
    ├── business/                     ML integration, pipeline, service plans
    ├── test/                         Fault injection test matrices
    └── archive/                      Superseded plans and analyses
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
