# Plan: SIL Probe Bus — Internal State Visibility for Debug + Synchronization

**Date**: 2026-03-21
**Status**: PROPOSED
**Goal**: Expose all foxBMS internal state on CAN debug IDs for plant synchronization, test verification, and debugging
**Effort**: 2 days
**Impact**: Unlocks Phase 3 (fault injection), fixes SOC resolution, enables real contactor physics

---

## Why

In SIL we own the entire chain. Parsing CAN bytes to guess internal state is backwards — we can just publish it. Every debugging session, every fault injection test, every plausibility check benefits from direct visibility into foxBMS internals.

Without probes:
- Plant guesses contactor state from 0x220 byte (delayed, lossy)
- Test checks SOC from 0x235 byte (0.25% resolution, can't see changes)
- Debugging requires grepping stderr logs (thousands of lines)
- Fault injection has no way to verify DIAG counter progression
- No way to know if a value reached the database vs was dropped

With probes:
- Plant reads exact contactor state per channel → correct physics
- Test reads float SOC → deterministic pass/fail
- Every internal state machine visible on CAN → candump is the debugger
- DIAG counters readable → fault injection verification
- Database values readable → end-to-end data path verification

---

## Probe ID Map (0x7F0–0x7FF reserved for SIL probes)

### Contactor / Power Path

| ID | Signal | Bytes | Update | Scenario |
|----|--------|-------|--------|----------|
| `0x7F0` | SPS channel actual state | B0-1: ch0-15 actual (1 bit each), B2-3: ch0-15 requested | Every SPS_Ctrl() | Plant: gate current on contactor close. Precharge: model I=(V-Vcap)/R. Fault injection: verify contactors open on fault. |
| `0x7F1` | SPS channel pending + delay | B0-1: ch0-15 pending, B2-3: ch0-15 delay counter (4 bits each) | Every SPS_Ctrl() | Debug: verify contactor delay model works. Test: measure close/open timing. |

### SOC / Algorithm

| ID | Signal | Bytes | Update | Scenario |
|----|--------|-------|--------|----------|
| `0x7F2` | Internal SOC (float32) | B0-3: SOC_pct float32 LE, B4-7: SOC_Wh float32 LE | Every 100ms | Test: verify SOC changes at full precision. Debug: compare with plant model SOC. ML sidecar: validate LSTM vs foxBMS. |
| `0x7F3` | SOC integrator state | B0-3: integrated_As (float32), B4-7: dt_us (uint32) | Every 100ms | Debug: verify coulomb counting works. Test: check integration direction matches current sign. |

### Voltage / Cell Data

| ID | Signal | Bytes | Update | Scenario |
|----|--------|-------|--------|----------|
| `0x7F4` | Cell voltage summary | B0-1: V_min (uint16 mV), B2-3: V_max (uint16 mV), B4-5: V_avg (uint16 mV), B6-7: V_delta (uint16 mV) | Every 100ms | Test: verify plant data reaches DB. Debug: precharge voltage mismatch. Fault injection: confirm OV/UV values in DB. |
| `0x7F5` | Pack voltage from DB | B0-3: string_voltage_mV (int32), B4-7: bus_voltage_mV (int32) | Every 100ms | Test: verify pack vs string voltage match. Debug: precharge delta. Plausibility: string_V ≈ bus_V. |

### Temperature

| ID | Signal | Bytes | Update | Scenario |
|----|--------|-------|--------|----------|
| `0x7F6` | Cell temperature summary | B0-1: T_min (int16 ddegC), B2-3: T_max (int16 ddegC), B4-5: T_avg (int16 ddegC), B6-7: T_delta (int16 ddegC) | Every 100ms | Test: verify temp data reaches DB. Fault injection: confirm OT values. |

### Diagnostics

| ID | Signal | Bytes | Update | Scenario |
|----|--------|-------|--------|----------|
| `0x7F7` | DIAG status | B0-3: total_fault_count (uint32), B4: last_fault_id (uint8), B5: last_fault_event (uint8), B6-7: reserved | Every DIAG call | Test: verify fault count after injection. Debug: which DIAG ID fired. Phase 3: confirm fault → contactor open chain. |
| `0x7F8` | DIAG active faults bitmap | B0-7: 64-bit bitmap of active fault IDs (1=fault active) | Every 100ms | Test: verify specific fault ID is set/cleared. Fault injection: confirm exactly which IDs fired. |

### State Machine

| ID | Signal | Bytes | Update | Scenario |
|----|--------|-------|--------|----------|
| `0x7F9` | SYS state machine | B0: sys_state, B1: sys_substate, B2-3: sys_timer (uint16), B4: bms_state, B5: bms_substate, B6-7: bms_timer (uint16) | Every 10ms | Debug: trace state transitions at full fidelity. Test: verify exact state sequence. Timing: measure time in each state. |

### Current / IVT

| ID | Signal | Bytes | Update | Scenario |
|----|--------|-------|--------|----------|
| `0x7FA` | Current from DB | B0-3: current_mA (int32 from DB), B4-7: current_mA_redundant (int32) | Every 100ms | Test: verify IVT data reaches DB. Debug: compare plant TX vs DB value. Redundancy: primary vs secondary match. |

### Timing / Performance

| ID | Signal | Bytes | Update | Scenario |
|----|--------|-------|--------|----------|
| `0x7FB` | Loop timing | B0-1: max_1ms_us (uint16), B2-3: max_10ms_us (uint16), B4-5: max_100ms_us (uint16), B6-7: tick_count (uint16) | Every 1s | Debug: identify timing bottlenecks. Test: verify no deadline violations. CI: performance regression detection. |

### Database

| ID | Signal | Bytes | Update | Scenario |
|----|--------|-------|--------|----------|
| `0x7FC` | Database write count | B0-3: db_write_count (uint32), B4-7: db_read_count (uint32) | Every 1s | Debug: verify DB passthrough is active. Test: data staleness detection. |

### Reserved

| ID | Purpose |
|----|---------|
| `0x7FD` | Future: balancing state |
| `0x7FE` | Future: ML sidecar feedback |
| `0x7FF` | Probe heartbeat (tick counter + uptime) |

---

## Architecture

```
foxbms-vecu (C)                    plant_model (Python)         test_harness (Python)
    |                                   |                            |
    |-- foxBMS logic runs --            |                            |
    |                                   |                            |
    |== SPS_Ctrl() ==                   |                            |
    |  posix_probe(0x7F0, sps_state)    |                            |
    |  --------CAN TX-------->  reads 0x7F0                          |
    |                           if ch0 CLOSED: I = trip_current      |
    |                           if ch0 OPEN: I = 0                   |
    |                                   |                            |
    |== 100ms task ==                   |                            |
    |  posix_probe(0x7F2, soc_float)    |                            |
    |  posix_probe(0x7F4, cell_v)       |                            |
    |  posix_probe(0x7F7, diag_status)  |                            |
    |  --------CAN TX-------->         reads 0x7F2: SOC float        |
    |                                  reads 0x7F4: verify cell data |
    |                                  reads 0x7F7: check fault count|
    |                                   |                            |
    |== DIAG_Handler() ==              |                            |
    |  posix_probe(0x7F8, fault_bitmap) |                            |
    |  --------CAN TX-------->         reads 0x7F8: verify fault set |
```

## Implementation

### Step 1: `posix_probe_send()` function in hal_stubs_posix.c

```c
void posix_probe_send(uint16_t probe_id, const uint8_t *data, uint8_t len) {
    posix_can_send(0x7F0 + probe_id, data, len);
}
```

Called from:
- `SPS_Ctrl()` → probe 0x7F0, 0x7F1
- `DIAG_Handler()` → probe 0x7F7
- Main loop 100ms block → probe 0x7F2-0x7F6, 0x7F9-0x7FC
- Main loop 1s block → probe 0x7FB, 0x7FF

### Step 2: Read probes in plant_model_replay.py

Replace `0x220` state byte parsing with `0x7F0` SPS channel state:
```python
if rx_id == 0x7F0:
    sps_actual = struct.unpack("<H", rx_data[0:2])[0]
    main_closed = bool(sps_actual & 0x01)  # ch0
    precharge_closed = bool(sps_actual & 0x04)  # ch2
```

### Step 3: Read probes in test_asil.py

Replace SOC byte check with float probe:
```python
if can_id == 0x7F2:
    soc_float = struct.unpack("<f", data[0:4])[0]  # full precision
```

### Step 4: DIAG probe for Phase 3 fault injection

```python
# Inject overvoltage → check probe
plant.send_cell_voltage(4500)  # OV
time.sleep(2)
# Read 0x7F8 fault bitmap
assert fault_bitmap & (1 << 18)  # DIAG_ID_CELL_VOLTAGE_OVERVOLTAGE_MSL
# Read 0x7F0 SPS state
assert sps_actual == 0  # all contactors open
```

---

## What This Enables (by phase)

### Phase 2 (now)
- Plant synchronizes current on real contactor state (0x7F0) — not delayed BMS state byte
- Test verifies SOC at float precision (0x7F2) — SOC.04 becomes deterministic
- Test verifies cell voltage reaches database (0x7F4) — end-to-end data path

### Phase 3 (fault injection)
- Inject fault → read 0x7F7 fault count → verify DIAG detected it
- Read 0x7F8 fault bitmap → verify exactly which fault ID fired
- Read 0x7F0 SPS state → verify contactors opened
- Read 0x7F9 BMS state → verify state machine went to ERROR
- Full fault → detection → response → recovery chain verifiable via CAN probes

### Phase 4 (Docker/HIL)
- Probes work on real CAN bus too (just filter 0x7Fx IDs in CANoe)
- ML sidecar reads 0x7F2 SOC → compare with LSTM prediction
- Grafana dashboard reads probes via CAN-to-MQTT bridge

### Debugging (any time)
- `candump vcan1 | grep 7F` shows all internal state in real time
- No need to parse stderr logs or add fprintf statements
- State machine trace at 10ms resolution (0x7F9)
- Timing profile at 1s resolution (0x7FB)

---

## What we need to read from foxBMS internals

These are the C variables/functions we need to access from hal_stubs_posix.c:

| Probe | foxBMS internal | How to access |
|-------|----------------|---------------|
| 0x7F0 | `sps_channel_actual_state[]` | Already in hal_stubs_posix.c (our SPS sim) |
| 0x7F1 | `sps_channel_pending[]`, `sps_channel_delay_ctr[]` | Already in hal_stubs_posix.c |
| 0x7F2 | SOC value | Need extern to `DATA_BLOCK_SOC_s` or read from DB after `DATA_READ_DATA` |
| 0x7F4 | Cell voltage min/max | Need extern to `DATA_BLOCK_CELL_VOLTAGE_s` |
| 0x7F5 | String/bus voltage | Need extern to `DATA_BLOCK_PACK_VALUES_s` |
| 0x7F6 | Cell temperature min/max | Need extern to `DATA_BLOCK_CELL_TEMPERATURE_s` |
| 0x7F7 | DIAG counter | Already in hal_stubs_posix.c (`posix_diag_fault_count`) |
| 0x7F9 | SYS/BMS state | Need extern to `sys_state` and `bms_state` |
| 0x7FA | Current from DB | Need extern to `DATA_BLOCK_CURRENT_SENSOR_s` |
| 0x7FB | Timing | Already in foxbms_posix_main.c (`max_1ms_us` etc.) |
| 0x7FC | DB write/read count | Can add counter in `DATA_IterateOverDatabaseEntries` |

The probes that read foxBMS database structs (0x7F2, 0x7F4-0x7F6, 0x7FA) need access to the database. Two approaches:
1. **Extern the database struct pointers** — fragile, depends on foxBMS internals
2. **Call DATA_READ_DATA in the probe function** — correct but needs the foxBMS API

Approach 2 is cleaner but requires including foxBMS headers in hal_stubs_posix.c (type conflicts). Approach 1 works because we know the struct layouts from the foxBMS source.

**Recommended**: Start with probes we already have data for (0x7F0, 0x7F1, 0x7F7, 0x7FB) — these are all in our own code. Add database probes later when we resolve the header include issue.

---

## Files

| File | Action | Changes |
|------|--------|---------|
| `hal_stubs_posix.c` | MODIFY | Add `posix_probe_send()`, probe calls in SPS_Ctrl, DIAG_Handler |
| `foxbms_posix_main.c` | MODIFY | Add probe calls in 100ms and 1s blocks |
| `plant_model_replay.py` | MODIFY | Read 0x7F0 instead of 0x220 for contactor sync |
| `plant_model.py` | MODIFY | Same — read 0x7F0 for contactor sync |
| `test_asil.py` | MODIFY | Read 0x7F2 for SOC float, 0x7F0 for contactor verification |
| `test_integration.py` | MODIFY | Add probe-based checks |

---

## Exit Criteria

| # | Criterion | Test |
|---|-----------|------|
| PRB.01 | `candump vcan1 \| grep 7F0` shows SPS state updating | Manual verify |
| PRB.02 | Plant model reads 0x7F0 and gates current correctly | CUR.06 passes in test_asil.py |
| PRB.03 | 0x7F7 DIAG probe shows fault count on injected fault | Phase 3 test |
| PRB.04 | 0x7FB timing probe matches stderr timing summary | Cross-check |
| PRB.05 | test_asil.py 50/50 with probe-based checks | Full regression |
