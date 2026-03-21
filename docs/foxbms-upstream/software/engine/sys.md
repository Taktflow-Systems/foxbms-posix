# SYS Module (System State Machine)

**Source**: [docs.foxbms.org — SYS](https://iisb-foxbms.iisb.fraunhofer.de/foxbms/docs/latest/software/modules/engine/sys/sys.html)
**Files**: `src/app/engine/sys/sys.c`, `sys.h`, `sys_cfg.c`, `sys_cfg.h`

---

## Function

Controls top-level system state. Runs in 10ms task via `SYS_Trigger()`.

## State Machine

| State | Value | Description |
|-------|-------|-------------|
| UNINITIALIZED | 0 | After reset |
| INITIALIZATION | 1 | Waiting for SBC, RTC, current sensor |
| INITIALIZED | 2 | All init substates passed |
| IDLE | 3 | Ready, waiting for external command |
| RUNNING | 5 | Normal operation, BMS state machine active |

## Initialization Substates

SYS waits for these before leaving INITIALIZATION:
1. SBC init complete (`SBC_GetState() == SBC_STATEMACHINE_RUNNING`)
2. RTC initialized (`RTC_IsRtcModuleInitialized() == true`)
3. Current sensor present (`CAN_IsCurrentSensorPresent() == true`)
4. IMD measurement running

## POSIX Port Bypasses

| Check | POSIX Stub | Why |
|-------|-----------|-----|
| SBC init | Returns `SBC_STATEMACHINE_RUNNING` (value 2) | No SBC hardware |
| RTC init | Returns `true` | No I2C RTC |
| Current sensor | Returns `true` | Patched to always-present |

These are documented as GA-08 (accepted bypasses).
