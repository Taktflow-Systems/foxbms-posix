# BMS Module

**Source**: [docs.foxbms.org — BMS](https://iisb-foxbms.iisb.fraunhofer.de/foxbms/docs/latest/software/modules/application/bms/bms.html)
**Files**: `src/app/application/bms/bms.c`, `bms.h`, `bms_cfg.h`

---

## State Machine

Main states (from CAN 0x220 `BmsState` field):

| State | Value | Description |
|-------|-------|-------------|
| STANDBY | 5 | All contactors open, no current flow |
| PRECHARGE | 6 | Precharge contactor closed, waiting for voltage match |
| NORMAL | 7 | All contactors closed, current allowed |
| ERROR | 9 | Safety-triggered, contactors forced open |

## State Transitions

- Transitions driven by **CAN requests** read from the database module
- `f_BmsStateRequest` (0x210) carries mode commands
- ERROR state activates automatically on hazardous condition detection
- Exiting ERROR requires: fault resolved AND explicit STANDBY request

## Error Handling

- **Info/Warning** flags: informational only, transmitted on CAN
- **Error** flags: trigger automatic transition to ERROR with configurable delay
- On error: `EmergencyShutoff` flag set in `f_BmsState` (0x220) CAN message

## Overcurrent Protection

Special handling: when disconnecting under overcurrent, BMS waits for the fuse to trigger and current to interrupt before opening contactors. This prevents contactor welding from breaking current exceeding the contactor's maximum breaking rating.

## POSIX Port Impact

- State machine logic runs identically (same source code)
- CAN request path works (plant_model.py → 0x210 → database → BMS)
- ERROR state path requires DIAG threshold propagation (Phase 3 blocker)
- Overcurrent fuse-wait behavior needs dynamic current from plant model
