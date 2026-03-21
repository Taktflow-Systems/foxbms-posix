# foxBMS 2 v1.10.0 — Upstream Documentation Reference

**Source**: [docs.foxbms.org](https://docs.foxbms.org/) (Fraunhofer IISB)
**Fetched**: 2026-03-21
**Purpose**: Local reference for foxBMS POSIX port development. Not a replacement for upstream docs.

---

## Documentation Map

```
docs/foxbms-upstream/
├── INDEX.md                          ← This file
├── general/
│   └── safety.md                     Safety warnings, standards, user responsibility
├── getting-started/
│   └── getting-started.md            Prerequisites, setup, build, first run
├── software/
│   ├── modules-index.md              Complete list of 41 software modules
│   ├── application/
│   │   ├── bms.md                    BMS state machine (STANDBY→NORMAL→ERROR)
│   │   ├── algorithm.md              SOC/SOE/SOF estimation framework
│   │   ├── balancing.md              Voltage-based + history-based balancing
│   │   ├── plausibility.md           Sensor data validation (incomplete upstream)
│   │   ├── redundancy.md             IVT cross-checking (incomplete upstream)
│   │   └── soa.md                    Safe Operating Area (MOL/RSL/MSL thresholds)
│   ├── engine/
│   │   ├── database.md               Producer/consumer data exchange module
│   │   ├── diag.md                   DIAG handler, threshold counters, callbacks
│   │   ├── sys.md                    SYS state machine (init → RUNNING)
│   │   └── sys-mon.md               System monitoring (task timing compliance)
│   ├── driver/
│   │   ├── can.md                    CAN TX/RX, callbacks, mailbox config, E2E
│   │   ├── sbc.md                    System Basis Chip (NXP FS8x), watchdog
│   │   ├── sps.md                    Smart Power Switch (contactor control)
│   │   ├── contactor.md              Contactor driver (incomplete upstream)
│   │   ├── interlock.md              Interlock circuit, feedback, safe state
│   │   └── imd.md                    Insulation Monitoring Device (Bender)
│   ├── task/
│   │   └── ftask.md                  7 FreeRTOS tasks, priorities, cyclic periods
│   └── main/
│       └── fassert.md                FAS_ASSERT levels (incomplete upstream)
├── system/
│   └── precharging.md                Precharge sequence, RC timing, failure detection
├── tools/
│   └── dbc.md                        DBC file location and tool info
└── dbc/
    └── foxbms-signals-summary.md     CAN message/signal summary from foxbms.dbc
```

---

## Quick Reference: What's Where

| I need to understand... | Read this | Relevance to POSIX port |
|---|---|---|
| BMS state transitions | [bms.md](software/application/bms.md) | Why states change, how ERROR works |
| How DIAG triggers ERROR | [diag.md](software/engine/diag.md) | **Phase 3 critical** — threshold counters |
| What SOA checks do | [soa.md](software/application/soa.md) | MOL/RSL/MSL thresholds we must not bypass |
| CAN message encoding | [can.md](software/driver/can.md) | TX callback structure, period config |
| Task structure | [ftask.md](software/task/ftask.md) | What runs in each cyclic task |
| Precharge logic | [precharging.md](system/precharging.md) | Why voltage must match |
| Interlock behavior | [interlock.md](software/driver/interlock.md) | What we hardcoded to always-closed |
| SBC/watchdog | [sbc.md](software/driver/sbc.md) | Why we stub to RUNNING (value 2) |
| Balancing strategy | [balancing.md](software/application/balancing.md) | Threshold + hysteresis logic |
| Database architecture | [database.md](software/engine/database.md) | Why single-producer matters |
| DBC signal definitions | [foxbms-signals-summary.md](dbc/foxbms-signals-summary.md) | CAN IDs, signals, encoding |

---

## Upstream Documentation Gaps

These modules have **incomplete documentation** on docs.foxbms.org (marked "not yet complete"):
- SPS (contactor control details)
- Contactor (state machine, feedback)
- Plausibility (what checks run)
- Redundancy (cross-checking logic)
- fassert (assert level definitions)
- Algorithm/State Estimation (SOC/SOE/SOF methods)

For these, **read the source code** in `foxbms-2/src/app/` directly.
