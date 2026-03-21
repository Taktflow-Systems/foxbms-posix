# SBC Module (System Basis Chip)

**Source**: [docs.foxbms.org — SBC](https://iisb-foxbms.iisb.fraunhofer.de/foxbms/docs/latest/software/modules/driver/sbc/sbc.html)
**Files**: `src/app/driver/sbc/sbc.c`, `sbc.h`, `nxpfs85xx.c`, `nxpfs85xx.h`
**Vendor**: NXP FS8x (3-Clause BSD licensed driver)

---

## Function

SBC manages MCU power based on ignition signal:

| Mode | Condition |
|------|-----------|
| **Running** | Ignition present → SBC powers MCU normally |
| **Standby** | Ignition removed → MCU requests SBC standby |
| **Power Down** | No ignition in standby → SBC cuts MCU power |
| **Restart** | Ignition detected → SBC powers MCU again |

## Hardware Watchdog

The SBC includes a hardware watchdog. If the MCU does not service the watchdog within the configured window, the SBC triggers a reset.

## Key Discovery (POSIX Port)

**`SBC_STATEMACHINE_RUNNING = 2`** (not 3)

The SYS state machine waits for `SBC_GetState()` to return `SBC_STATEMACHINE_RUNNING`. The enum value is `2`, not `3` as might be assumed. Using the wrong value causes SYS to time out in INITIALIZATION and never reach RUNNING.

## POSIX Port Status

- SBC init stubbed: `SBC_GetState()` returns `SBC_STATEMACHINE_RUNNING` (value 2)
- `SBC_SetStateRequest()` returns OK
- Hardware watchdog not simulated (GA-24)
- NDA restriction: MC33FS830A0ES programming details not publicly available
