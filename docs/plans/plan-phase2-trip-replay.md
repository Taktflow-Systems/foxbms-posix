# Plan: Phase 2 Completion — Trip Replay Plant Model (ML Layer 1)

**Date**: 2026-03-21
**Status**: PROPOSED — awaiting approval
**Goal**: Complete Phase 2 exit criteria (5/8 → 8/8) using real BMW i3 driving data
**Effort**: 2-3 days
**Risk**: LOW — Python only, no C code changes, no model inference

---

## Problem

Phase 2 has 3 remaining exit criteria:

| # | Criterion | Why it's blocked |
|---|-----------|-----------------|
| 2.5 | Per-cell noise without precharge failure | Synthetic Gaussian noise causes CAN frame ordering mismatch → precharge abort |
| 2.6 | Temperature mux covers all sensors | Plant only sends mux=0 (3 of 18 sensors) |
| 2.7 | Charge current path (SOC increases) | No regenerative braking in current model |

Our synthetic plant model is the bottleneck. Real driving data solves all three.

## Solution

Replace the synthetic plant model with a **trip replay** mode that reads BMW i3 driving CSVs and encodes them into foxBMS CAN format.

### Data Available

- **70 BMW i3 trips** in `taktflow-bms-ml/data/bms-raw/bmw-i3-driving/`
- **10 Hz** sampling (0.1s intervals), 28-48 columns per CSV
- **Key signals**: Battery Voltage (V), Battery Current (A), Battery Temperature (°C), SoC (%)
- **Regenerative braking** present (Battery Current goes negative)
- **Temperature variation** present (ambient + battery temp change over trip)

### Domain Gap: BMW i3 (96S) → foxBMS (18S)

| Signal | BMW i3 raw | foxBMS 18S conversion |
|--------|-----------|----------------------|
| Pack voltage | ~385 V (96S NMC) | Scale: V_cell = pack_V / 96 → use same V_cell × 18 |
| Pack current | ±100 A | Same — current is string-level, identical |
| Cell voltage | Not in CSV (pack only) | Derive: V_cell_mV = int(pack_V / 96 × 1000) |
| Cell variation | Not in CSV | Add per-cell fixed offset from real cell data (±15mV) |
| Temperature | 1 value (pack) | Replicate across all 18 sensor slots with small gradient |
| SOC | BMS-reported % | Use as ground truth for validation |

**Key insight**: Per-cell voltage is derived from pack voltage (V_cell = pack_V / 96). This naturally includes all driving transients (acceleration, regen, IR drop under load) without synthetic noise. The voltage variation comes from real physics, not Gaussian randomness → no precharge mismatch.

---

## Steps

### Step 1: Create `plant_model_replay.py`

New file alongside existing `plant_model.py`. Reads BMW i3 CSV, converts to foxBMS CAN.

**Inputs**:
- `--trip <csv_path>` — path to BMW i3 trip CSV
- `--can <interface>` — SocketCAN interface (default vcan1)
- `--speed <multiplier>` — playback speed (default 1.0, 10.0 for fast-forward)
- `--loop` — loop trip continuously

**Outputs** (same CAN IDs as existing plant model):
- `0x521` IVT Current — from `Battery Current [A]` column
- `0x522-524` IVT Voltage — derived pack voltage (V_cell × 18)
- `0x527` IVT Temperature — from `Battery Temperature [°C]` column
- `0x270` Cell voltages — V_cell ± per-cell offset (5 mux groups)
- `0x280` Cell temperatures — battery temp with gradient across all mux groups
- `0x210` BMS state request — STANDBY first 3s, then NORMAL

**Data conversion**:
```python
# BMW i3 96S → foxBMS 18S
v_cell_mv = int(pack_voltage_v / 96.0 * 1000.0)  # per-cell mV
pack_voltage_18s_mv = v_cell_mv * 18               # 18S pack voltage
current_ma = int(pack_current_a * 1000.0)           # mA (sign preserved)
temp_ddegc = int(battery_temp_c * 10.0)             # deci-°C
```

**Per-cell variation** (fixed per-cell offsets, no per-tick noise):
```python
# Realistic cell-to-cell spread from manufacturing tolerance
# ±15mV is typical for production packs (from NASA cell data)
cell_offsets = [random.gauss(0, 8) for _ in range(18)]  # fixed at startup
cell_voltages = [v_cell_mv + int(cell_offsets[i]) for i in range(18)]
```

**Temperature across all mux groups**:
```python
# Small gradient across 18 sensors: center cells ~2°C warmer
for mux in range(5):  # 5 mux × 4 sensors = 20 slots
    base_temp = temp_ddegc
    gradient = (mux - 2) * 5  # ±10 deci-°C (±1°C) gradient
    temps = [base_temp + gradient] * min(4, 18 - mux * 4)
    can_send(0x280, encode_cell_temp_msg(mux, temps))
```

**Timing**: BMW i3 data is 10 Hz. With `--speed 1.0`, send one row every 100ms (matches existing plant model rate). With `--speed 10.0`, send 10 rows per 100ms (10× real-time).

### Step 2: Update smoke test to support trip replay

`test_smoke.py` should accept an optional `--trip` argument. If provided, use `plant_model_replay.py` instead of `plant_model.py`.

Default (no `--trip`): use dynamic `plant_model.py` (existing behavior).

### Step 3: Verify exit criterion 2.5 — per-cell variation without precharge failure

Run trip replay with a BMW i3 trip. Cell voltages will have natural per-cell offsets (±8mV from manufacturing tolerance). Precharge should pass because:
- All cell voltages are derived from the same pack voltage in the same tick
- Pack voltage (0x522-524) = sum(cell_voltages) — they match by construction
- No CAN frame ordering mismatch (all sent in one burst per tick)

**Test**: `python3 test_smoke.py vcan1 --trip ../taktflow-bms-ml/data/bms-raw/bmw-i3-driving/TripA01.csv`
**Pass**: BMS reaches NORMAL state.

### Step 4: Verify exit criterion 2.6 — temperature mux coverage

Check candump for 0x280 with mux values 0-4 (not just mux=0).

**Test**: `candump vcan1 | grep 280` — should show 5 different first bytes (mux 0-4).
**Pass**: All 5 mux values present with non-zero temperature data.

### Step 5: Verify exit criterion 2.7 — charge current (SOC increases)

BMW i3 trips have regenerative braking where Battery Current goes negative. During regen:
- IVT current (0x521) should be negative
- SOC should increase momentarily

**Test**: Run trip with known regen braking, check plant log for negative current periods.
**Pass**: Plant log shows `I=-XX.XA` during regen, and foxBMS 0x235 SOC value increases (even briefly).

### Step 6: Run full 20-second trip segment, verify SOC tracks

Run a BMW i3 trip at 10× speed (20 seconds real-time = 200 seconds trip time). Check:
- SOC decreases during discharge
- SOC increases during regen braking
- Cell voltages change with SOC
- No foxBMS faults or state machine errors

**Test**: `python3 test_smoke.py vcan1 --trip TripA01.csv --speed 10`
**Pass**: Smoke test PASS + plant log shows SOC movement in both directions.

### Step 7: Update PLAN.md exit criteria

Mark 2.5, 2.6, 2.7 as PASS. Phase 2: 8/8 COMPLETE.

---

## What We DON'T Do (Phase 3/4)

- No ML model inference (Layer 2 — Phase 3/4)
- No fault injection (Layer 3 — Phase 3)
- No DIAG threshold implementation (Phase 3 prerequisite)
- No Docker (Phase 4)
- No FOBSS dataset download (Layer 2 validation)

---

## Files

| File | Action | Lines |
|------|--------|-------|
| `src/plant_model_replay.py` | CREATE | ~120 |
| `src/test_smoke.py` | MODIFY | +15 (--trip arg) |
| `PLAN.md` | UPDATE | mark 2.5-2.7 |
| `src/plant_model.py` | NO CHANGE | stays as fallback |

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| BMW i3 CSV parsing fails (encoding, delimiter) | LOW | LOW | CSV format verified: semicolon delimited, latin-1, 28 columns |
| Per-cell voltage from pack_V/96 triggers plausibility | LOW | MEDIUM | V_cell = 4010mV at 385V pack — within foxBMS OV threshold (4200mV) |
| foxBMS rejects negative current (charge) | LOW | LOW | IVT format supports signed int32 — same encoding as discharge |
| Temperature gradient triggers overtemp fault | LOW | LOW | ±1°C gradient on 25°C base = 24-26°C — well within limits |
| Trip CSV has gaps or NaN values | MEDIUM | LOW | Add NaN/gap handling: interpolate or repeat last valid value |

---

## Success Criteria

Phase 2 is COMPLETE when ALL 8 exit criteria pass:

| # | Criterion | Currently | After this plan |
|---|-----------|-----------|-----------------|
| 2.1 | SOC decreases under discharge | PASS | PASS |
| 2.2 | Cell voltage tracks SOC via OCV | PASS | PASS (real data replaces OCV model) |
| 2.3 | Pack voltage shows IR drop | PASS | PASS (real data has natural IR drop) |
| 2.4 | Closed-loop: discharge at NORMAL | PASS | PASS |
| 2.5 | Per-cell noise without precharge failure | **NOT DONE** | PASS (real cell offsets, consistent pack voltage) |
| 2.6 | Temperature mux covers all sensors | **NOT DONE** | PASS (gradient across mux 0-4) |
| 2.7 | Charge current path works | **NOT DONE** | PASS (BMW i3 regen braking) |
| 2.8 | 20-second monotonic SOC decrease | PASS | PASS |
