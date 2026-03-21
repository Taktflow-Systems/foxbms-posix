# Getting Started with foxBMS 2

**Source**: [docs.foxbms.org — Getting Started](https://iisb-foxbms.iisb.fraunhofer.de/foxbms/docs/latest/getting-started/getting-started.html)

---

## Setup Steps

1. **Read definitions and naming conventions** — used throughout documentation
2. **Software Installation** — toolchain (TI ARM CGT compiler, HALCoGen, Python)
3. **Repository Structure** — understand project layout
4. **Create Workspace** — VS Code configuration for browsing source
5. **fox CLI** — command-line interface for build/test/flash
6. **First Steps on Hardware** — build, flash, run on TMS570

## Key Commands (Production Build)

```bash
# Configure build
python fox.py waf configure

# Build application
python fox.py waf build_app

# Build and run unit tests (Windows)
python fox.py waf clean_app_host_unit_test build_app_host_unit_test
python fox.py ceedling test:all

# Flash to hardware
python fox.py waf flash
```

## Repository Structure

```
foxbms-2/
├── conf/               Build configuration
├── docs/               Sphinx documentation source
├── hardware/           Schematics, BOM, layout
├── src/
│   └── app/
│       ├── application/    BMS, SOA, algorithm, balancing, plausibility, redundancy
│       ├── driver/         CAN, SPI, I2C, SBC, SPS, contactor, AFE, IMD, etc.
│       ├── engine/         Database, DIAG, SYS, SYS_MON
│       ├── main/           main.c, fassert.h, startup
│       └── task/           FTASK, OS abstraction
├── tests/              Unit tests (Ceedling)
├── tools/
│   ├── dbc/            CAN DBC file (foxbms.dbc)
│   └── precharge/      Precharge dimensioning notebook
├── fox.py              CLI entry point
└── wscript             Waf build script
```

## POSIX Port Comparison

| Production Build | POSIX Port |
|-----------------|------------|
| `python fox.py waf build_app` | `cd src && make -j4` |
| TI ARM CGT compiler | GCC 13 (x86-64) |
| HALCoGen headers generated | Pre-generated headers copied |
| Flash to TMS570 | Run `./foxbms-vecu` on Linux |
| FreeRTOS scheduler | Cooperative main loop |
| CAN hardware | SocketCAN (vcan1) |
