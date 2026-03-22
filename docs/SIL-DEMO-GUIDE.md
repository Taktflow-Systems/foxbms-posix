# foxBMS 2 — Battery Management System SIL Demo Guide

## Live Demo (no setup required)

**Open in your browser right now:**

| Link | What you see |
|------|-------------|
| [sil.taktflow-systems.com/bms/](https://sil.taktflow-systems.com/bms/) | Live BMS dashboard with fault injection |
| [sil.taktflow-systems.com/bms-docs/](https://sil.taktflow-systems.com/bms-docs/) | Full portfolio documentation (60 pages) |

The BMS is running 24/7 on a Netcup VPS in Germany. No login required. You can inject faults and watch the BMS react in real-time.

---

## Interview Demo Script (3 minutes)

Use this walkthrough to demonstrate the system in a live interview:

| Step | Action | What to say |
|------|--------|-------------|
| 1 | Open [sil.taktflow-systems.com/bms/](https://sil.taktflow-systems.com/bms/) | "This is a live foxBMS 2 BMS running on Linux. The same C code that runs on the TMS570 microcontroller is executing here with SocketCAN." |
| 2 | Point to BMS State: NORMAL | "The BMS started from UNINITIALIZED, went through INIT, IDLE, STANDBY, PRECHARGE, and reached NORMAL. Contactors are closed, 18 cells are balanced at ~3700mV." |
| 3 | Select **Overvoltage**, range **C0–C17**, click **Inject** | "I'm injecting an overvoltage fault on all 18 cells via the plant model — this is SWE.6 black-box testing through the full CAN path." |
| 4 | Watch event log + state transition | "The BMS detected the fault in ~585ms via the DIAG threshold counter (50 events). It transitions to ERROR and opens all contactors — fail-safe." |
| 5 | Click **Clear** | "After clearing the fault, the BMS recovers through the normal startup sequence. No manual restart needed." |
| 6 | Show **SWE.5 method selector** | "For white-box testing, I can inject faults directly into the BMS database using 11 ISO 26262 Part 5 methods — STUCK_AT, DRIFT, NOISE, etc. This bypasses CAN and tests the safety logic directly." |

**If asked about test coverage:** "We have 2,005 ASIL-D fault injection test cases. 29 of 31 scenarios PASS — the 2 deferred tests are for cell balancing timeout and deep discharge recovery, documented in the test results."

---

## What This Is

A complete Software-in-the-Loop (SIL) simulation of the foxBMS 2 open-source Battery Management System, running as a native Linux process with a web-based visualization dashboard. The foxBMS C source code (v1.10.0) compiles and runs on x86-64 with hardware abstracted — the same safety logic that runs on the TMS570 microcontroller executes here with full CAN communication via SocketCAN.

**Key capabilities:**
- Live 18-cell battery pack visualization
- Real foxBMS state machine: UNINIT → INIT → IDLE → STANDBY → PRECHARGE → NORMAL → ERROR
- Real DIAG threshold counting (OV: 50 events, OT: 500 events, OC: 10 events)
- Contactor control with welding/stuck-open detection
- Fault injection at two levels:
  - **SWE.6 (Plant/Black-box)**: change battery physics → BMS reacts via CAN
  - **SWE.5 (BMS/White-box)**: override BMS internal database → bypass CAN path
- 11 ISO 26262-5 fault injection methods (STUCK_AT, DRIFT, NOISE, etc.)
- 2,005 automated test cases (ASIL-D fault injection matrix), 29/31 PASS
- CAN monitor showing live bus traffic
- Event log showing fault chain reaction

**Measured detection times:**
| Fault | Detection time | Threshold |
|-------|---------------|-----------|
| Overvoltage (OV) | 585 ms | 50 events + 200ms delay |
| Overcurrent (OC) | 116 ms | 10 events + 100ms delay |
| Overtemperature (OT) | 5,510 ms | 500 events + 1000ms delay |

---

## Prerequisites

### Hardware
- Linux PC or laptop (Ubuntu 22.04+ recommended)
- 4+ GB RAM, any modern x86-64 CPU
- No special hardware needed — everything runs in software

### Software
```bash
sudo apt-get install -y gcc make python3 python3-pip can-utils iproute2 git
pip3 install --user aiohttp   # for web dashboard
```

### Network (for remote access)
- Web dashboard accessible on port 8080
- If accessing from another machine, both must be on the same network

---

## Quick Start — Docker (2 minutes)

The fastest way to run the BMS locally:

```bash
git clone --recursive https://github.com/nhuvaoanh123/foxbms-posix.git
cd foxbms-posix
docker compose up --build
```

Open **http://localhost:8080** — done. The Docker image handles vCAN setup, build, plant model, and web server automatically.

To stop: `docker compose down`

---

## Quick Start — Manual (5 minutes)

### Step 1: Clone the repository

```bash
git clone --recursive https://github.com/nhuvaoanh123/foxbms-posix.git
cd foxbms-posix
```

### Step 2: Copy HALCoGen headers and apply patches

```bash
mkdir -p foxbms-2/build/app_host_unit_test/include
cp halcogen-headers/* foxbms-2/build/app_host_unit_test/include/

# Copy FreeRTOS POSIX port
mkdir -p foxbms-2/src/os/freertos/freertos/portable/ThirdParty/GCC/Posix/utils
cp freertos-posix-port/port.c freertos-posix-port/portmacro.h \
   foxbms-2/src/os/freertos/freertos/portable/ThirdParty/GCC/Posix/
cp freertos-posix-port/utils/* \
   foxbms-2/src/os/freertos/freertos/portable/ThirdParty/GCC/Posix/utils/

# Apply all foxBMS source patches
bash patches/apply_all.sh
```

### Step 3: Build

```bash
cd src
make -j$(nproc)
# Output: foxbms-vecu binary
```

### Step 4: Set up virtual CAN interface

```bash
sudo modprobe vcan
sudo ip link add vcan1 type vcan
sudo ip link set vcan1 up
```

### Step 5: Run the SIL demo

Open three terminals (or use `&` for background):

**Terminal 1 — Plant model (battery simulator):**
```bash
python3 src/plant_model.py vcan1
```

**Terminal 2 — foxBMS vECU:**
```bash
FOXBMS_CAN_IF=vcan1 src/foxbms-vecu
```

**Terminal 3 — Web dashboard:**
```bash
python3 web/server.py --can vcan1 --port 8080 --host 0.0.0.0
```

### Step 6: Open the dashboard

Browse to: **http://localhost:8080**

(Or from another machine: `http://<laptop-ip>:8080`)

You should see:
- Battery pack with 18 green cells at ~3700mV
- BMS state progressing: UNINITIALIZED → ... → NORMAL (takes ~7 seconds)
- SOC slowly decreasing (1A discharge at 0.33C)
- CAN monitor showing live traffic

---

## One-Command Start

After building once, use this to start everything:

```bash
cd foxbms-posix
python3 src/plant_model.py vcan1 &>/dev/null &
FOXBMS_CAN_IF=vcan1 src/foxbms-vecu &>/dev/null &
python3 web/server.py --can vcan1 --port 8080 --host 0.0.0.0
```

Stop everything:
```bash
killall foxbms-vecu python3
```

---

## Dashboard Guide

### Battery — Physical (Plant Model)

The left panel shows 18 battery cells in a 3×6 grid. These represent the **physical reality** — what the battery actually produces. Each cell shows:
- Cell ID (C0–C17)
- Voltage in mV
- Temperature dot (blue=cold, green=normal, red=hot)
- Color: green (normal), yellow (warning), red (fault)

### Plant Model — Physics

Shows the battery simulation parameters:
- **SOC**: State of Charge (decreases under discharge)
- **OCV**: Open-circuit voltage from SOC lookup
- **Pack Voltage**: Sum of cell voltages minus IR drop
- **IR Drop**: Voltage loss due to internal resistance (I × R_total)
- **Current**: Discharge current (positive = discharge)
- **Status**: DISCHARGING / IDLE / CHARGING

### BMS Inputs (What foxBMS Sees)

Shows what the BMS actually reads from the battery via CAN/SPI:
- **AFE**: Cell voltage min/max/delta, cell temperature min/max
- **IVT**: Pack current, pack voltage, pack power

When you inject a fault via SWE.6 (Plant), these values change because the plant's CAN output changes. When you inject via SWE.5 (BMS), these values change because the internal database is overridden.

### BMS State Machine

Shows the foxBMS state machine with the current state highlighted:
- **UNINITIALIZED** → **INITIALIZATION** → **INITIALIZED** → **IDLE**
- **STANDBY** → **PRECHARGE** → **NORMAL** (operating state)
- **ERROR** (fault detected, contactors opened)

State history shows timestamped transitions.

### Contactors

Three contactors:
- **Main+** (String Plus): connects positive terminal
- **Main-** (String Minus): connects negative terminal
- **Precharge**: pre-charges the bus capacitance (opens after precharge sequence)

In NORMAL state: Main+ CLOSED, Main- CLOSED, Precharge OPEN.
On fault: all three OPEN.

### Fault Injection

Two modes:

**Plant (SWE.6)** — Black-box testing:
- Changes the plant model's CAN output
- foxBMS receives the fault through normal CAN path
- Battery panel shows the changed values
- Tests the complete data path: CAN RX → DECAN → Database → SOA → DIAG

**BMS (SWE.5)** — White-box testing:
- Overrides the foxBMS internal database on READ
- Battery panel stays unchanged (plant not affected)
- Tests the safety logic: SOA → DIAG → State Machine → Contactor
- Method selector with 11 ISO 26262-5 fault methods

Inject types:
- **Overvoltage**: Set cell voltage above OV MSL (4250mV). Range: C0 to C17.
- **Undervoltage**: Set cell voltage below UV MSL (2500mV). Range: C0 to C17.
- **Overtemperature**: Set sensor temperature above OT MSL (55°C). Range: S0 to S7.
- **Overcurrent**: Set pack current above OC MSL (15A). Fixed 200A.

### Event Log

Shows the fault chain reaction with timestamps:
```
22:15:00  ⚡ PLANT: cell_voltage [0] = 4500
22:15:01  🔍 FAULT: OV_MSL (DIAG ID 18)
22:15:01  🔄 NORMAL → ERROR
22:15:01  🔓 Main+ OPENED
22:15:01  🔓 Main- OPENED
```

### Diagnostics

- **Fault count**: Number of unique DIAG IDs that exceeded threshold
- **Last ID**: Most recent DIAG event ID
- **Bitmap**: Active fault IDs (e.g., "IDs: 18,19,20" for OV MSL/RSL/MOL)

### CAN Monitor

Live CAN bus traffic, color-coded:
- **Green** (0x2xx): foxBMS CAN TX (state, SOC, cell voltages)
- **Blue** (0x6xx): Plant telemetry (SOC, OCV, IR drop)
- **Purple** (0x7Fx): SIL probes (internal state)

---

## Running Automated Tests

### Smoke test (15 seconds)
```bash
python3 src/test_smoke.py vcan1
```

### Fault injection tests (P1, 10 tests, ~2 minutes)
```bash
python3 src/test_fault_injection.py vcan1 --max 10 --priority P1 \
  --csv docs/test/fault-injection-test-matrix-asild.csv --timeout 10000
```

### Full test suite (2,005 tests, ~5 hours)
```bash
python3 src/test_fault_injection.py vcan1 \
  --csv docs/test/fault-injection-test-matrix-asild.csv --timeout 15000
```

### Scenario tests (high-risk scenarios)
```bash
python3 src/test_scenarios.py vcan1
```

---

## Architecture

```
┌─────────────────┐     SocketCAN (vcan1)      ┌──────────────────┐
│                 │                              │                  │
│  Plant Model    │ ──── 0x270 Cell Voltages ──→ │                  │
│  (Python)       │ ──── 0x280 Cell Temps    ──→ │  foxBMS vECU     │
│                 │ ──── 0x521 IVT Current   ──→ │  (C binary)      │
│  Battery +      │ ──── 0x210 State Request ──→ │                  │
│  IVT Sensor     │                              │  Same C code as  │
│  Simulation     │ ←── 0x220 BMS State      ─── │  TMS570 target   │
│                 │ ←── 0x7F0 SIL Probes     ─── │                  │
│                 │                              │  170+ source     │
│  Reads 0x7F0    │     CAN 0x6E0 (plant cmd)    │  files compiled  │
│  for contactor  │ ←────────────────────────── │  for x86-64      │
│  feedback       │                              │                  │
└─────────────────┘                              └──────────────────┘
        │                                                │
        │ CAN 0x600-0x607                    CAN 0x7F0-0x7FF
        │ (plant telemetry)                  (SIL probes)
        │                                                │
        └──────────────────┐    ┌────────────────────────┘
                           │    │
                    ┌──────┴────┴──────┐
                    │                  │
                    │  Web Server      │
                    │  (Python aiohttp)│
                    │                  │
                    │  HTTP :8080      │
                    │  WebSocket /ws   │
                    │                  │
                    └──────────────────┘
                           │
                    ┌──────┴──────┐
                    │             │
                    │  Browser    │
                    │  Dashboard  │
                    │             │
                    └─────────────┘
```

### CAN Message Map

| CAN ID | Direction | Content |
|--------|-----------|---------|
| 0x210 | Plant → BMS | State request (STANDBY/NORMAL) |
| 0x270 | Plant → BMS | Cell voltages (18 cells, multiplexed) |
| 0x280 | Plant → BMS | Cell temperatures (8 sensors, multiplexed) |
| 0x521 | Plant → BMS | IVT current (mA) |
| 0x522-524 | Plant → BMS | IVT voltage (mV) |
| 0x527 | Plant → BMS | IVT temperature |
| 0x220 | BMS → all | BMS state (multiplexed) |
| 0x600-602 | Plant → Web | Plant telemetry (SOC, OCV, IR) |
| 0x603-607 | Plant → Web | Per-cell voltages (for dashboard) |
| 0x6E0 | Web → Plant | Plant override commands (SWE.6) |
| 0x7E0 | Web → BMS | BMS DB override commands (SWE.5) |
| 0x7F0-7FF | BMS → Web | SIL probes (state, DIAG, contactor) |

### foxBMS Configuration (NMC Chemistry)

| Parameter | MSL | RSL | MOL |
|-----------|-----|-----|-----|
| Overvoltage | 4250 mV | 4200 mV | 4150 mV |
| Undervoltage | 2500 mV | 2600 mV | 2700 mV |
| OT Discharge | 55.0°C | 50.0°C | 45.0°C |
| OT Charge | 45.0°C | 40.0°C | 35.0°C |
| String Current | 15000 mA | — | — |
| OV threshold | 50 events + 200ms delay |
| OT threshold | 500 events + 1000ms delay |
| OC threshold | 10 events + 100ms delay |

### Battery Pack Configuration

| Parameter | Value |
|-----------|-------|
| Cells in series | 18 |
| Cell capacity | 3000 mAh (3 Ah) |
| Cell resistance | 50 mΩ |
| Discharge current | 1 A (0.33C) |
| Nominal voltage | 3700 mV (50% SOC) |
| OCV range | 3400 mV (0%) – 4200 mV (100%) |
| AFE averaging | 16-sample moving average |
| Measurement noise | ±3 mV Gaussian |

---

## Patches Applied to foxBMS

The foxBMS source (v1.10.0) is unmodified in the submodule. All changes are applied at build time via Python patch scripts in `patches/`:

| Patch | What it does |
|-------|-------------|
| patch_all_regs.py | Redirect TMS570 register bases to RAM |
| patch_canreg.py | CAN register redirect |
| patch_sbc.py/sbc2.py | SBC returns RUNNING (no physical SBC) |
| patch_rtc.py | RTC returns initialized |
| patch_can_sensor.py | Current sensor present = true |
| patch_database.py | DATA_IterateOverDatabaseEntries extern |
| patch_database2.py | Database trace |
| patch_ftask.py | Engine/precyclic trace |
| patch_sys2.py | SYS_Trigger trace |
| patch_bms2.py | BMS_Trigger trace |
| patch_10ms2.py | 10ms task trace |
| patch_precharge.py | Precharge always OK |
| patch_battery_cfg.py | NMC voltage/current thresholds |
| patch_diag_posix.py | Disable 42 hardware-absent DIAG IDs |
| patch_diag_probe.py | SIL probe + startup grace period in DIAG |
| patch_db_inject.py | Deep fault injection at DB READ path |

---

## File Structure

```
foxbms-posix/
├── foxbms-2/              # foxBMS v1.10.0 submodule (unmodified)
├── halcogen-headers/      # 91 HALCoGen generated headers (BSD)
├── freertos-posix-port/   # FreeRTOS POSIX port (MIT)
├── patches/               # 16 Python patch scripts
│   └── apply_all.sh       # Apply all patches in order
├── src/
│   ├── foxbms_posix_main.c   # Main loop + SIL probes
│   ├── hal_stubs_posix.c     # 80+ HAL stubs + SPS simulation
│   ├── sil_layer.c/h         # SIL override + probe system
│   ├── posix_overrides.h     # FAS_ASSERT + portmacro
│   ├── plant_model.py        # Dynamic battery simulator
│   ├── plant_model_replay.py # BMW i3 trip replay
│   ├── Makefile              # Build system
│   ├── test_smoke.py         # Smoke test
│   ├── test_fault_injection.py # Automated FI test runner
│   ├── test_scenarios.py     # High-risk scenario tests
│   └── fi/                   # 17-module test framework
├── web/
│   ├── server.py             # CAN-to-WebSocket bridge
│   └── index.html            # Dashboard (single file)
├── docs/
│   ├── test/                 # Test matrix (2,005 cases)
│   ├── plans/                # Implementation plans
│   ├── lessons-learned.md    # 9 lessons documented
│   ├── test-progress.md      # Test execution results
│   └── aspice-cl2/           # ASPICE folder structure
│       ├── 11-SWE.4-.../test-results/  # Unit test report
│       ├── 12-SWE.5-.../test-results/  # Integration test report
│       └── 13-SWE.6-.../test-results/  # Qualification test report
├── GAP-ANALYSIS.md           # 33/33 gaps closed
├── PLAN.md                   # Phase 1-4 roadmap (96% complete)
├── Dockerfile                # Docker build
└── docker-compose.yml        # Docker compose
```

---

## Troubleshooting

### BMS doesn't reach NORMAL
- Ensure plant_model.py is running BEFORE foxbms-vecu
- Check vcan1 is up: `ip link show vcan1`
- Wait 8-10 seconds (startup + precharge takes time)

### Web dashboard shows no data
- Ensure all 3 processes are running: `ps aux | grep -E 'plant|foxbms|server'`
- Check web server log: `cat /tmp/bms-web.log`
- Verify CAN traffic: `candump vcan1 -n 5`

### Cell voltages all zero
- The plant needs ~1 second to start sending data
- Hard refresh browser: Ctrl+Shift+R

### Fault injection doesn't trigger BMS reaction
- **SWE.6 (Plant)**: For voltage, inject ALL cells (C0 to C17) — single cell gets rejected by plausibility check
- **SWE.5 (BMS)**: Single cell works (bypasses plausibility)
- Temperature needs 500 events (~5.5s) — wait longer
- Check event log for DIAG events

### Processes die after SSH disconnect
- Use `nohup` or `screen`/`tmux`:
  ```bash
  nohup python3 src/plant_model.py vcan1 &>/dev/null &
  nohup env FOXBMS_CAN_IF=vcan1 src/foxbms-vecu &>/dev/null &
  nohup python3 web/server.py --can vcan1 --port 8080 --host 0.0.0.0 &>/dev/null &
  ```

---

## License

- foxBMS 2: BSD-3-Clause (Fraunhofer IISB)
- HALCoGen headers: BSD-3-Clause (Texas Instruments)
- FreeRTOS POSIX port: MIT (Amazon)
- foxbms-posix (our code): proprietary (Taktflow Systems)
