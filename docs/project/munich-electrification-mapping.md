# Munich Electrification — Product Map & Learning Path

**Purpose**: Understand ME's products, map them to our foxBMS stack, and learn BMS fastest with what we have.

---

## 1. The Company

Munich Electrification (ME), founded 2014, ~200 employees, Munich. Tier 1 BMS supplier.

**Key customer**: Daimler Truck — BMS for eActros 300/400 electric trucks.

**Certifications**: ISO 26262 ASIL D, ISO 21434 cybersecurity, IATF-16949, OBD compliant.

---

## 2. Product Portfolio

### 2.1 Barcelona SBS (Smart Battery Sensor) — THE MAIN PRODUCT

The central BMS ECU. Equivalent to foxBMS's BMS-Master.

| Feature | Barcelona SBS | foxBMS BMS-Master |
|---|---|---|
| Current sensing | Integrated dual-shunt, rapid overcurrent detection | External IVT (Isabellenhuette) |
| HV measurement | Up to 8 channels | 3 channels (IVT Voltage 1/2/3) |
| Contactor drivers | Built-in, fail-operational mode | Via SPS (Smart Power Switch) over SPI |
| Pyro fuse | Built-in driver + backup energy storage | Not in foxBMS |
| Isolation monitoring | Active + passive | IMD (Bender IR155/iso165c) |
| Max voltage | 950V (Bologna variant) | Depends on slave count (~55V per slave) |
| Safety | ASIL D | Not certified (development platform) |
| Cybersecurity | ISO 21434 | None |
| OTA updates | Yes, with remote monitoring | No |
| Software | "Fully configurable modern BMS software stack" | Open-source C, FreeRTOS on TMS570 |

### 2.2 CMB (Cell Monitoring Board) — THE SLAVE

Measures individual cell voltages and temperatures. Equivalent to foxBMS's BMS-Slave.

| Feature | ME CMB | foxBMS BMS-Slave |
|---|---|---|
| Channels | 18-channel standard (customizable) | Configurable (ADI ADES1830, LTC, Maxim, NXP) |
| Voltage accuracy | "High" (spec not public) | Depends on AFE IC used |
| Temperature inputs | Multiple per board | 8 per module (configurable) |
| Thermal event detection | "Innovative additional sensors" (likely gas/aerosol) | Aerosol sensor support (BAS_AerosolSensor 0x3C4) |
| Form factor | Flex circuits, cell-module integration options | Standard PCB |
| Communication | Daisy-chain SPI to SBS | Daisy-chain SPI to BMS-Master |

### 2.3 wCMB (Wireless Cell Monitoring Board)

Wireless variant of CMB. No equivalent in foxBMS.

| Feature | Detail |
|---|---|
| Advantage | Eliminates wiring harness inside pack |
| Weight saving | Less copper, fewer connectors |
| Reliability | Fewer physical interconnects = fewer failure points |
| Use case | Immersion-cooled packs (wiring inside liquid is problematic) |

### 2.4 BMDU (Battery Management Disconnect Unit)

All-in-one for heavy-duty trucks. No equivalent in foxBMS (foxBMS is software + reference boards).

| Feature | Detail |
|---|---|
| Integrates | BMS ECU + contactors + fuse + precharge + current sensor + busbars |
| Peak current | >600A per string |
| Multistring | Up to 16 BMDUs in parallel (>10kA combined) |
| Precharge | Dual-pole, <500ms |
| **Breaktor** | Patented: replaces contactors AND fuses. Auto-resets after short circuit. |
| Target | MCS (Megawatt Charging System) for electric trucks |

### 2.5 Software & Analytics Platform

| Feature | Detail |
|---|---|
| SOC/SOH algorithms | Optimized per application (automotive vs stationary) |
| ML/AI analytics | Battery health and performance insights |
| Cloud framework | Data engineering + remote monitoring |
| OTA integration | Push algorithm updates to BMS via TCU |
| Telemetry | TCU (Telematics Control Unit) bridges BMS to cloud |

### 2.6 LV/48V BMS

Low-voltage variant for mild hybrids, auxiliary batteries.

| Feature | Detail |
|---|---|
| Disconnect | MOSFET-based (not contactors) |
| Current sensing | Dual-shunt |
| Safety | ASIL D |
| OTA | Yes |
| Target | Low-cost, scalable 48V systems |

### 2.7 Stationary Storage BMS

ESS (Energy Storage System) variant.

| Feature | Detail |
|---|---|
| Voltage | Up to 1500 VDC |
| Interfaces | CAN + Ethernet (automotive is CAN only) |
| Algorithms | SOC/SOH/balancing optimized for stationary (cycle life > range anxiety) |
| Safety | ISO 26262 or ISO 13849 (machinery) |
| Cybersecurity | UL 5500 / UL 9540 |
| Controller | 3-tier: CMB → SBS → Container controller |

---

## 3. Map ME Products to foxBMS + Our Stack

```
Munich Electrification                    Our foxBMS POSIX Stack
─────────────────────                     ──────────────────────

Barcelona SBS (BMS ECU)          ←→       foxBMS BMS-Master (TMS570)
  - Current sensing                         - IVT via CAN (0x521-0x527)
  - Contactor drivers                       - SPS via SPI (stubbed)
  - HV measurement                          - IVT Voltage 1/2/3
  - Isolation monitoring                    - IMD (Bender, stubbed)
  - Safety ASIL D                           - Selective DIAG (61 SW checks)
  - OTA updates                             - Not implemented

                                  ←→       foxbms_posix_main.c (POSIX vECU)
                                            - Cooperative loop (replaces RTOS)
                                            - SocketCAN (replaces HW CAN)
                                            - SIL probes (0x7E0-0x7FF)

CMB (Cell Monitoring)            ←→       foxBMS BMS-Slave (AFE)
  - 18 channels                             - 18 cells (BS_NR_OF_CELL_BLOCKS=18)
  - Temperature sensors                     - 8 temp sensors per module
  - Thermal event detection                 - Aerosol sensor (0x3C4)

                                  ←→       plant_model.py
                                            - Sends cell voltages (0x270)
                                            - Sends cell temperatures (0x280)

BMDU (Disconnect Unit)           ←→       SPS simulation in hal_stubs_posix.c
  - Contactors                              - 3 channels (string+, string-, precharge)
  - Precharge                               - Precharge sequence verified
  - Breaktor (fuse replacement)             - Not simulated (no equivalent)

Software & Analytics             ←→       taktflow-bms-ml
  - SOC/SOH algorithms                     - SOC LSTM (1.83% RMSE)
  - ML/AI analytics                         - SOH LSTM, Thermal CNN, RUL, Imbalance
  - Cloud framework                         - Not implemented
  - OTA to BMS                              - Not implemented

No ME equivalent                 ←→       SIL infrastructure
                                            - test_smoke.py, test_asil.py
                                            - trace-gen.py (308 IDs)
                                            - 29 ASPICE CL2 documents
                                            - 9 ISO 26262 safety docs
```

---

## 4. What foxBMS Teaches You About ME's Products

foxBMS and ME's Barcelona SBS solve the same problems with the same architecture. The concepts transfer directly:

### 4.1 State Machine (SYS + BMS)

**foxBMS**: UNINIT → INIT → IDLE → STANDBY → PRECHARGE → NORMAL → ERROR

**ME Bologna**: Same pattern (required by ISO 26262). Names may differ but the logic is identical:
- Wait for hardware init (SBC, RTC, sensors) → go IDLE
- Receive CAN command → go STANDBY
- Close precharge contactor, check voltage match → go NORMAL
- Fault detected → go ERROR, open contactors

**Learn this in foxBMS**: Read `foxbms-upstream/software/application/bms.md`. Run `test_smoke.py` and watch `candump vcan1,220:7FF` — see state 0x30 → 0x50 → 0x60 → 0x71 in real time.

### 4.2 Diagnostics (DIAG)

**foxBMS**: 85 DIAG IDs, threshold counters, MOL/RSL/MSL severity, configurable delay to ERROR.

**ME Bologna**: Same pattern (ISO 26262 requires it). Three-tier warning system. Threshold debouncing. Fatal → contactor open.

**Learn this in foxBMS**: Read `foxbms-upstream/software/engine/diag.md` — the complete threshold counter mechanism. Read `aspice-cl2/10-SWE.3` — all 85 DIAG entries with thresholds and delays. This is exactly what ME's DIAG system does internally.

### 4.3 Cell Monitoring (AFE → Database)

**foxBMS**: CMB sends cell voltages on CAN 0x270 (multiplexed, 18 cells, 5 mux groups). foxBMS decodes, validates (plausibility, redundancy), stores in database.

**ME CMB**: Same flow — CMB measures cells, sends to SBS over daisy-chain SPI. SBS validates and stores. ME's CMB has 18 channels standard — same as foxBMS default config.

**Learn this in foxBMS**: Watch `candump vcan1,270:7FF` — see 5 mux frames cycling. Read `foxbms-upstream/dbc/foxbms-signals-summary.md` for signal encoding. The big-endian encoding, invalid flags, mux structure — all transfer to any BMS.

### 4.4 Contactor Control (SPS + Precharge)

**foxBMS**: SPS controls 3 contactors via SPI. Precharge sequence: close precharge contactor → wait for V_bus ≈ V_string → close main contactors → open precharge.

**ME BMDU**: Same sequence but with the Breaktor replacing the fuse. Precharge <500ms (foxBMS is configurable).

**Learn this in foxBMS**: Run the vECU and grep stderr for `[SPS]` — see contactor close requests during precharge. Read `foxbms-upstream/system/precharging.md`.

### 4.5 SOC Estimation

**foxBMS**: Coulomb counting. `SOC(t) = SOC(t-1) - (I × dt) / (Capacity × 3600)`. Drifts over time.

**ME Software**: Likely EKF or model-based (proprietary). Their ML/AI platform suggests they also use data-driven methods.

**Learn this in foxBMS**: Watch `candump vcan1,235:7FF` — byte 5 is SOC. With dynamic plant model, SOC decreases under discharge. Compare with our SOC LSTM (1.83% RMSE) in `taktflow-bms-ml`.

### 4.6 CAN Communication

**foxBMS**: 15+ TX message types, DBC-defined, big-endian encoding, 100ms/1000ms periods.

**ME Bologna**: Same protocol layer (CAN 2.0B, likely 500kbps). Different message IDs and DBC, but identical encoding/decoding pattern. ME adds ISO 21434 cybersecurity and E2E protection (AUTOSAR).

**Learn this in foxBMS**: Read `foxbms-upstream/software/driver/can.md` — TX/RX callbacks, mailbox config, helper functions. This is how every automotive CAN stack works.

---

## 5. What ME Has That foxBMS Doesn't

| ME Capability | Why foxBMS Doesn't Have It | How to Learn It |
|---|---|---|
| **Integrated current sensor** | foxBMS uses external IVT | Study IVT CAN protocol (0x521-0x527) |
| **Breaktor** | Patented ME technology | No equivalent; understand contactor + fuse separately |
| **Wireless CMB** | Requires proprietary RF + BMS integration | Study wired CMB first, wireless is an extension |
| **ISO 21434 cybersecurity** | foxBMS has no security layer | Read ISO 21434 separately; not in BMS logic |
| **OTA updates** | foxBMS is bare-metal, no bootloader with OTA | Study A/B partition + secure boot concepts separately |
| **Cloud analytics** | foxBMS is embedded-only | Our taktflow-bms-ml fills this gap |
| **Multi-string (16 BMDUs)** | foxBMS supports multi-string but our config is 1 string | Change `BS_NR_OF_STRINGS` in battery_system_cfg.h |
| **E2E protection** | Bypassed in POSIX port (GA-27) | Study AUTOSAR E2E Profile 1/2 separately |

---

## 6. Fastest BMS Learning Path Using Our Stack

### Week 1: Understand the BMS (read + run)

| Day | Activity | What You Learn |
|---|---|---|
| 1 | Read `foxbms-upstream/INDEX.md` → follow links to bms.md, diag.md, ftask.md | Architecture: state machines, task structure, DIAG |
| 1 | Run `setup.sh` → `candump vcan1` — watch BMS reach NORMAL | See theory become practice |
| 2 | Read `foxbms-upstream/software/application/soa.md` | Safety: MOL/RSL/MSL thresholds |
| 2 | Read `aspice-cl2/10-SWE.3` — the 85-entry DIAG table | Every fault the BMS monitors |
| 3 | Read `foxbms-upstream/dbc/foxbms-signals-summary.md` | CAN protocol: what each message means |
| 3 | Run `candump vcan1 -t z` and decode 0x220, 0x235, 0x270 by hand | CAN encoding fluency |
| 4 | Read `STATUS.md` — 14 fixes, key discoveries | What goes wrong when porting BMS firmware |
| 4 | Read `docs/project/troubleshooting.md` — 10 failure modes | How to debug BMS issues |
| 5 | Read `foxbms-upstream/system/precharging.md` | Precharge: why, how, what can fail |
| 5 | Read `foxbms-upstream/software/application/balancing.md` | Cell balancing strategies |

**By end of Week 1**: You understand BMS state machine, DIAG handler, CAN protocol, safety thresholds, precharge, and balancing. You can explain what every CAN message means. This covers ~80% of what ME's firmware engineers work on daily.

### Week 2: Understand the Safety (read ASPICE + ISO 26262)

| Day | Activity | What You Learn |
|---|---|---|
| 1 | Read `aspice-cl2/18-safety/part3-concept/ISO26262-part3-HARA.md` | 12 battery hazards, ASIL ratings |
| 1 | Read `aspice-cl2/18-safety/part4-system/ISO26262-part4-FSC.md` | Safety goals → functional safety requirements |
| 2 | Read `aspice-cl2/18-safety/part4-system/ISO26262-part4-TSC.md` | Technical safety mechanisms (DIAG → ERROR → contactors) |
| 2 | Read `aspice-cl2/18-safety/part6-software/ISO26262-part6-FTTI-calculations.md` | Timing: how fast must the BMS react? |
| 3 | Read `aspice-cl2/18-safety/part5-hardware/ISO26262-part5-FMEA.md` | 19 failure modes and their RPN |
| 3 | Read `aspice-cl2/18-safety/part5-hardware/ISO26262-part5-hardware-software-interface.md` | What's hardware, what's software, what's stubbed |
| 4 | Read `aspice-cl2/08-SWE.1` through `13-SWE.6` | ASPICE V-model: requirements → architecture → design → test |
| 5 | Run `python scripts/trace-gen.py --stats` | See 308 requirements traced across 29 documents |

**By end of Week 2**: You understand ISO 26262 HARA→FSC→TSC→FTTI chain, ASPICE process areas, and how requirements trace from hazard to test. This is what ME's safety engineers do.

### Week 3: Hands-on SIL Testing

| Day | Activity | What You Learn |
|---|---|---|
| 1 | Run `test_smoke.py` — read the code | How automated BMS testing works |
| 1 | Run `test_integration.py` — 21 criteria | Integration testing: CAN + state machine + SOC |
| 2 | Run `test_asil.py` — 50 criteria | Safety testing: DIAG checks, contactor behavior |
| 2 | Run `test_sil_probes.py` — 76 criteria | SIL instrumentation: probes, overrides, heartbeat |
| 3 | Modify `plant_model.py` — change cell voltage to 4500mV | See foxBMS react (or not — Phase 3 blocker) |
| 3 | Modify `plant_model.py` — change current to 200A | Observe overcurrent path |
| 4 | Read `src/hal_stubs_posix.c` — understand every stub | What each hardware component does |
| 4 | Read `src/sil_layer.c` — understand probes and overrides | How SIL instrumentation works |
| 5 | Read `src/foxbms_posix_main.c` — the cooperative loop | How FreeRTOS tasks map to Linux |

**By end of Week 3**: You can run and modify SIL tests, understand what every stub replaces, and know how to add new test scenarios. This is what ME's HIL/SIL test engineers do.

### Week 4: ML + Business Context

| Day | Activity | What You Learn |
|---|---|---|
| 1 | Read `taktflow-bms-ml/README.md` and `docs/plan-bms-ml-training.md` | ML pipeline: SOC/SOH/Thermal/RUL/Imbalance |
| 2 | Read `docs/business/proposal-ml-integration.md` | How ML connects to BMS CAN |
| 3 | Read `docs/business/pipeline-reusable.md` | Reusable pipeline: any BMS, any customer |
| 4 | Read `docs/business/plan-hil-data-capture.md` | What to do with real bench data |
| 5 | Read `docs/project/audit-10-role-v2.md` | Project status: what works, what's missing |

**By end of Week 4**: You understand the full picture — BMS firmware + safety + testing + ML + business. You can have a technical conversation with any BMS engineer at ME about state machines, DIAG, safety, or ML integration.

---

## 7. SIL vs HIL Testing Map

```
              SIL (what we have)                    HIL (ME's bench)
              ─────────────────                     ─────────────────

Firmware:     foxBMS on Linux (POSIX)               Bologna BMS on TMS570/Aurix
              cooperative loop, SocketCAN            FreeRTOS, HW CAN 500kbps

Battery:      plant_model.py                        Battery emulator / real cells
              OCV curve, IR drop, 10A discharge      Precision V/I/T, cycling profiles

Contactors:   SPS simulation (RAM state)            Real contactors + Breaktor
              instant (configurable delay)           mechanical delay, bounce, weld

Sensors:      Static or scripted values              Real NTC, real IVT, real IMD
              via CAN 0x270/0x280/0x521              via SPI/CAN to real ICs

Faults:       SIL override (0x7E0 CAN command)      External fault box / manual
              cell voltage, temp, current overrides   real overvoltage, heating, shorting

Diagnostics:  Selective DIAG (61 SW checks)         Full DIAG (85 checks)
              24 HW-absent suppressed                all checks active

Timing:       usleep(500) loop, ~1ms effective      Real RTOS tick, deterministic
              deadline violations logged              real deadline enforcement

Output:       candump + test scripts                 CANape/CANoe + test automation
              pytest pass/fail                        dSPACE/Vector test reports

Cost:         $0 (laptop + Linux)                   $50k-500k (bench + tools)
Time to run:  Seconds                                Hours (setup) + minutes (execution)
```

### What SIL Catches That HIL Can't

| SIL Advantage | Why |
|---|---|
| Run 1000 fault scenarios in 10 minutes | No physical setup per test |
| Test edge cases safely | No risk of fire/explosion from real overvoltage |
| Regression on every commit (CI) | HIL bench is shared, limited booking |
| Reproducible timing | No thermal drift, no contact resistance variation |
| Full code observability (SIL probes) | HIL can only observe CAN output |

### What HIL Catches That SIL Can't

| HIL Advantage | Why |
|---|---|
| Real RTOS timing and preemption | Cooperative loop masks concurrency bugs |
| Real CAN arbitration and bus-off | SocketCAN is perfect (no errors) |
| Real contactor dynamics (bounce, weld) | SPS sim is instant state change |
| Real sensor noise and drift | Plant model is clean |
| Real E2E protection and error detection | Bypassed in POSIX (GA-27) |
| Real watchdog recovery | No SBC watchdog in POSIX (GA-24) |
| EMC/ESD effects on communication | No electromagnetic interference in SIL |

### The Right Strategy: SIL First, HIL to Confirm

```
1. Develop algorithm/logic change
2. Test on SIL (seconds, free, on your laptop)
3. Fix all issues found
4. Book HIL bench time (expensive, limited)
5. Run same test cases on bench (confirm SIL results transfer)
6. If HIL finds something SIL missed → add to SIL for next time
```

This is exactly how ME's test process should work. The foxBMS POSIX port is the SIL half. ME's Bologna bench is the HIL half. You bridge both.
