# Contactor Module

**Source**: [docs.foxbms.org — Contactor](https://iisb-foxbms.iisb.fraunhofer.de/foxbms/docs/latest/software/modules/driver/contactor/contactor.html)
**Files**: `src/app/driver/contactor/contactor.c`, `contactor.h`, `contactor_cfg.c`, `contactor_cfg.h`
**Status**: Upstream documentation marked "not yet complete"

---

## Function

Higher-level contactor management above SPS:
- Manages contactor state machine (requested, closed, opening)
- Handles feedback verification (did contactor actually close?)
- Implements contactor welding detection

## POSIX Port Status

Contactor feedback suppressed in DIAG (hardware-absent). SPS simulation handles the actual open/close tracking.
