# Diagnosis Module (DIAG)

**Source**: [docs.foxbms.org — DIAG](https://iisb-foxbms.iisb.fraunhofer.de/foxbms/docs/latest/software/modules/engine/diag/diag.html)
**Files**: `src/app/engine/diag/diag.c`, `diag.h`, `diag_cfg.c`, `diag_cfg.h`
**Callbacks**: `src/app/engine/diag/cbs/diag_cbs_*.c` (CAN, contactor, current, temperature, voltage, etc.)

---

## Architecture

Central configuration table `diag_diagnosisIdConfiguration[]` maps each `DIAG_ID_e` entry to:
1. **Callback function** — what to do when fault occurs
2. **Threshold counter** — how many consecutive occurrences before escalation
3. **Severity** — Info, Warning, or Fatal
4. **Delay** — time between error flag set and BMS state change

## Threshold Counter Mechanism

```
DIAG_Handler(diag_id, event) called by application code
    │
    ├── event = EVENT_OK → decrement counter (recovery)
    │
    └── event = EVENT_NOT_OK
         │
         ├── counter < threshold → increment counter, return DIAG_HANDLER_RETURN_OK
         │                         (fault detected but not yet confirmed)
         │
         └── counter >= threshold → set error flag bit
                                    clear warning flag bit
                                    call callback
                                    return DIAG_HANDLER_RETURN_ERR_OCCURRED
```

## Configuration Per DIAG ID

Each entry in `diag_diagnosisIdConfiguration[]`:

| Field | Description |
|-------|-------------|
| `diagId` | Enum value from `DIAG_ID_e` |
| `threshold` | Number of consecutive faults before escalation |
| `severity` | `DIAG_FATAL_ERROR`, `DIAG_WARNING`, `DIAG_INFO` |
| `delay_ms` | Time between flag-set and BMS ERROR transition |
| `callback` | Function pointer to specific handler |
| `enable` | Whether this diagnostic check is active |

## How Errors Propagate to BMS State Machine

1. Application code calls `DIAG_Handler(id, EVENT_NOT_OK)`
2. Threshold counter increments
3. When threshold reached → error flag set in `diag_flags`
4. `DIAG_IsAnyFatalErrorSet()` returns true
5. BMS state machine reads this → transitions to ERROR
6. After configurable delay → contactors open

## Callback Categories

- `diag_cbs_voltage.c` — overvoltage, undervoltage (cell, string, pack)
- `diag_cbs_current.c` — overcurrent (charge, discharge, string)
- `diag_cbs_temperature.c` — overtemperature, undertemperature
- `diag_cbs_contactor.c` — contactor feedback mismatch
- `diag_cbs_can.c` — CAN timeout, missing messages
- `diag_cbs_plausibility.c` — voltage/temp spread, pack voltage mismatch

## POSIX Port Impact — CRITICAL

**Current state (broken)**: `DIAG_Handler` in `hal_stubs_posix.c` logs faults but always returns OK for hardware-absent checks. The real `diag.c` with threshold counters is excluded from the build.

**Fix for Phase 3**:
1. Include real `diag.c` in build (remove from Makefile exclusion)
2. Keep hardware-absent callbacks returning OK (SPI timeout, I2C, SBC)
3. Let software-checkable callbacks (voltage, current, temp) run real logic
4. `DIAG_IsAnyFatalErrorSet()` will then return true when thresholds are reached
5. BMS state machine will transition to ERROR
6. Contactors will open via SPS simulation

This is the #1 priority for Phase 3 (audit finding A3-01).
