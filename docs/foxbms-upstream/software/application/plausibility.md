# Plausibility Module

**Source**: [docs.foxbms.org — Plausibility](https://iisb-foxbms.iisb.fraunhofer.de/foxbms/docs/latest/software/modules/application/plausibility/plausibility.html)
**Files**: `src/app/application/plausibility/plausibility.c`, `plausibility.h`, `plausibility_cfg.h`
**Status**: Upstream documentation marked "not yet complete"

---

## Function

Validates sensor data consistency. Checks include:
- Cell voltage spread (max - min across all cells)
- Cell temperature spread
- Pack voltage vs sum of cell voltages
- Sensor data freshness (timeout)

## POSIX Port Status

Plausibility checks enabled in selective DIAG (GA-06, part of 61 software-checkable IDs). With static plant model data (all cells identical), spread checks always pass. Needs per-cell variation (Phase 2) to exercise.
