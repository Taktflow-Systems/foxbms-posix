# IMD Module (Insulation Monitoring Device)

**Source**: [docs.foxbms.org — IMD](https://iisb-foxbms.iisb.fraunhofer.de/foxbms/docs/latest/software/modules/driver/imd/imd.html)
**Files**: `src/app/driver/imd/imd.c`, `imd.h`
**Supported devices**: Bender IR155, Bender iso165c, Dummy IMD

---

## State Machine

| State | Description |
|-------|-------------|
| HAS_NEVER_RUN | Post-startup |
| UNINITIALIZED | Waiting for init request |
| INITIALIZATION | Setting up peripherals |
| IMD_ENABLE | Activating device |
| RUNNING | Active monitoring |
| SHUTDOWN | Deactivating |
| ERROR | Fault condition |

## Interface Functions

- `IMD_ProcessInitializationState()` — prepare peripherals
- `IMD_ProcessEnableState()` — activate, begin measurement
- `IMD_ProcessRunningState()` — acquire + process measurements
- `IMD_ProcessShutdownState()` — disable device

Trigger function executes from 100ms task cycle.

## POSIX Port Status

IMD suppressed in DIAG (hardware-absent). Insulation resistance value hardcoded in foxBMS as 0 or max. Not critical for SIL validation.
