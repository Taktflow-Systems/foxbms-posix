# Plan: Web Demo Phase 2 — SWE.6 Plant Manipulation + State History

**Date**: 2026-03-21
**Status**: PLANNING

## Goal

1. Customer can manipulate the battery (plant model) from the web UI
2. BMS reacts through normal CAN path (black-box, SWE.6 level)
3. RESET restarts the full system — visible state machine walk-through
4. State transition history with timestamps

## Feature 1: Plant-Level Fault Injection (SWE.6)

### Architecture

```
Browser UI                Web Server              Plant Model           foxBMS
   │                         │                        │                    │
   │ "set cell 5 = 4500mV"  │                        │                    │
   │ ───────────────────────>│                        │                    │
   │                         │  CAN 0x6E0 override   │                    │
   │                         │ ──────────────────────>│                    │
   │                         │                        │ CAN 0x270          │
   │                         │                        │ (cell 5 = 4500mV) │
   │                         │                        │ ──────────────────>│
   │                         │                        │                    │ SOA detects OV
   │                         │                        │                    │ DIAG threshold
   │                         │                        │                    │ contactor open
   │                         │                        │   CAN 0x220        │
   │                         │                        │ <──────────────────│
   │                         │   CAN 0x220 = ERROR   │                    │
   │  state = ERROR          │<──────────────────────                     │
   │ <───────────────────────│                                            │
```

No internal probes used. Pure CAN stimulus → CAN response.

### Plant Override Protocol (CAN 0x6E0)

```
Byte 0: command type
  0x01 = cell voltage override (mV)
  0x02 = temperature override (ddegC)
  0x03 = current override (mA)
  0xFF = clear all overrides
Byte 1: index (cell 0-17, sensor 0-7)
Byte 2: active (0=clear, 1=set)
Bytes 3-6: value (int32 LE)
```

Same format as SIL probe 0x7E0 but for the PLANT, not the BMS.

### Plant Model Changes

- Listen on CAN 0x6E0 for override commands (non-blocking read in main loop)
- When override active: use override value instead of computed value for that cell
- Override affects CAN 0x270/0x280/0x521 output (what foxBMS sees via CAN)
- Override also affects 0x603-0x607 web telemetry (battery panel shows changed value)
- Clear restores computed value

### Web UI Changes

- "Battery — Physical" panel gets clickable cells
- Click a cell → popup/slider to set voltage (or quick buttons: "OV 4500", "UV 2000", "Normal")
- The injection goes through the PLANT (0x6E0), not the BMS (0x7E0)
- Rename fault injection panel: split into "SWE.5: BMS Override" and "SWE.6: Plant Override"
- Or simpler: add a toggle "Inject at: [Plant] [BMS]" that routes to 0x6E0 or 0x7E0

### SWE.6 Test Evidence

When customer manipulates plant voltage:
- Battery panel cell turns red (plant output changed)
- BMS perception shows changed min/max (after CAN propagation)
- State machine transitions to ERROR
- Evidence: "stimulus on CAN 0x270, response on CAN 0x220" — pure black-box

## Feature 2: RESET with Full State Walk-Through

### What happens on RESET

1. Kill foxbms-vecu process
2. Kill plant_model.py process
3. Clear all plant overrides
4. Restart plant_model.py (starts sending STANDBY request for 3s)
5. Restart foxbms-vecu
6. BMS walks through: UNINITIALIZED → INITIALIZATION → INITIALIZED → IDLE → STANDBY → PRECHARGE → NORMAL

### Web UI shows the walk-through

- State machine panel highlights each state as it transitions
- Transition history log below state list:
  ```
  21:15:00.000  UNINITIALIZED
  21:15:00.800  INITIALIZATION
  21:15:00.900  INITIALIZED
  21:15:01.000  IDLE
  21:15:01.800  STANDBY
  21:15:04.000  PRECHARGE
  21:15:07.200  NORMAL        ← current
  ```
- Each transition has timestamp and duration
- History persists across resets (shows previous runs dimmed)

### Server Changes

- RESET action: kill processes, wait, restart
- VecuManager class (from test runner) handles process lifecycle
- Server tracks state transitions with timestamps
- Broadcasts state_history to web clients

### Web UI Changes

- State history panel (below state machine, scrollable)
- Each entry: timestamp + state name + duration in state
- Current state: bold/highlighted
- Previous run entries: dimmed
- RESET button triggers full restart + clears state history

## Feature 3: State Transition History Tracker

### Data Model

```json
{
  "state_history": [
    {"state": 0, "name": "UNINITIALIZED", "entered_at": 1711046400.0, "duration_ms": 800},
    {"state": 1, "name": "INITIALIZATION", "entered_at": 1711046400.8, "duration_ms": 100},
    {"state": 2, "name": "INITIALIZED", "entered_at": 1711046400.9, "duration_ms": 100},
    {"state": 3, "name": "IDLE", "entered_at": 1711046401.0, "duration_ms": 800},
    {"state": 5, "name": "STANDBY", "entered_at": 1711046401.8, "duration_ms": 2200},
    {"state": 6, "name": "PRECHARGE", "entered_at": 1711046404.0, "duration_ms": 3200},
    {"state": 7, "name": "NORMAL", "entered_at": 1711046407.2, "duration_ms": null}
  ]
}
```

### Server Tracking

- In CAN reader, when 0x220 or 0x7F9 shows a new BMS state:
  - Close previous entry (set duration_ms)
  - Add new entry (state, name, entered_at)
- On RESET: add separator entry, keep history

## Implementation Order

1. State transition history tracker (server + UI) — independent of everything else
2. RESET with process restart — uses VecuManager pattern
3. Plant override protocol (0x6E0) — plant model changes
4. Plant-level fault injection UI — web frontend

## Files to Modify

| File | Changes |
|------|---------|
| `web/server.py` | State history tracker, RESET process management, plant override routing |
| `web/index.html` | State history panel, plant cell click, inject toggle |
| `src/plant_model.py` | Listen on 0x6E0, apply overrides to CAN output |

## Exit Criteria

| # | Criterion | Test |
|---|-----------|------|
| 1 | Click cell in battery panel → plant sends OV → BMS enters ERROR | Visual on dashboard |
| 2 | RESET button restarts system, state machine walks through all states | Visual on dashboard |
| 3 | State history shows timestamped transitions | Visual on dashboard |
| 4 | SWE.6 evidence: CAN 0x270 stimulus → CAN 0x220 response (no probes) | CAN monitor shows both |
| 5 | Plant override clears on RESET | Cell returns to green after reset |
