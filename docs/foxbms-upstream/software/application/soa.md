# SOA Module (Safe Operating Area)

**Source**: [docs.foxbms.org — SOA](https://iisb-foxbms.iisb.fraunhofer.de/foxbms/docs/latest/software/modules/application/soa/soa.html)
**Files**: `src/app/application/soa/soa.c`, `soa.h`, `soa_cfg.c`, `soa_cfg.h`

---

## Purpose

Keeping battery cells within the Safe Operating Area (SOA) is a **safety goal** of the BMS.

## Three Error Levels

| Level | Name | What Happens |
|-------|------|-------------|
| **MOL** | Maximum Operating Limit | First threshold — parameters approaching limits. Warning only. |
| **RSL** | Recommended Safety Limit | Second threshold — system should take counter-measures to prevent contactor opening. |
| **MSL** | Maximum Safety Limit | Critical threshold — **safety of system and persons cannot be guaranteed**. Contactors OPEN. |

## Monitored Parameters

| Parameter | Check | Triggers DIAG ID |
|-----------|-------|-----------------|
| Cell voltage (high) | `SOA_CheckVoltages()` | `DIAG_ID_CELL_VOLTAGE_OVERVOLTAGE_{MSL,RSL,MOL}` |
| Cell voltage (low) | `SOA_CheckVoltages()` | `DIAG_ID_CELL_VOLTAGE_UNDERVOLTAGE_{MSL,RSL,MOL}` |
| Cell temperature (high, charge) | `SOA_CheckTemperatures()` | `DIAG_ID_TEMP_OVERTEMPERATURE_CHARGE_{MSL,RSL,MOL}` |
| Cell temperature (high, discharge) | `SOA_CheckTemperatures()` | `DIAG_ID_TEMP_OVERTEMPERATURE_DISCHARGE_{MSL,RSL,MOL}` |
| Cell temperature (low, charge) | `SOA_CheckTemperatures()` | `DIAG_ID_TEMP_UNDERTEMPERATURE_CHARGE_{MSL,RSL,MOL}` |
| Cell temperature (low, discharge) | `SOA_CheckTemperatures()` | `DIAG_ID_TEMP_UNDERTEMPERATURE_DISCHARGE_{MSL,RSL,MOL}` |
| Pack current (charge) | `SOA_CheckCurrent()` | `DIAG_ID_OVERCURRENT_CHARGE_{MSL,RSL,MOL}` |
| Pack current (discharge) | `SOA_CheckCurrent()` | `DIAG_ID_OVERCURRENT_DISCHARGE_{MSL,RSL,MOL}` |

## Flow

```
SOA_Check*() called from 10ms task
    │
    ├── value within MOL → DIAG_Handler(id, EVENT_OK)
    │
    ├── value > MOL but < RSL → DIAG_Handler(DIAG_ID_*_MOL, EVENT_NOT_OK)
    │
    ├── value > RSL but < MSL → DIAG_Handler(DIAG_ID_*_RSL, EVENT_NOT_OK)
    │
    └── value > MSL → DIAG_Handler(DIAG_ID_*_MSL, EVENT_NOT_OK)
                       → after threshold reached → BMS ERROR → contactors open
```

## POSIX Port Impact

SOA checks are **enabled** in the POSIX build (part of the 61 software-checkable DIAG IDs in GA-06). The issue is that DIAG_Handler in `hal_stubs_posix.c` logs these but doesn't track threshold counters. Phase 3 fix: use real `diag.c` so MSL violations actually propagate to BMS ERROR.
