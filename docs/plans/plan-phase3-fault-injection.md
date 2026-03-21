# Plan: Phase 3 — Fault Injection

**Date**: 2026-03-21
**Status**: PROPOSED — awaiting manual review
**Goal**: foxBMS detects injected faults via SIL override (0x7E0) and responds correctly (opens contactors, enters ERROR)
**Effort**: 5-7 days
**Risk**: MEDIUM — requires patching foxBMS source files + reimplementing DIAG threshold logic

---

## What We Learned from foxBMS DIAG Implementation

The real `diag.c` uses per-ID threshold counters:

```
DIAG_EVENT_NOT_OK → counter++ → if counter == threshold → SET fault → callback → FATAL
DIAG_EVENT_OK     → counter-- → if counter == 0 → CLEAR fault → callback
```

Key thresholds (from `diag_cfg.c`):

| Fault | Threshold | Events to confirm | Delay before contactor open |
|-------|-----------|-------------------|----------------------------|
| Overvoltage MSL | 50 | 50 consecutive NOT_OK | 200ms |
| Overcurrent MSL | 10 | 10 consecutive NOT_OK | 100ms |
| Overtemperature MSL | 500 | 500 consecutive NOT_OK | 1000ms |

Hysteresis: clearing a fault requires the same number of consecutive OK events (symmetric).

---

## Two Approaches

### Approach A: Re-include real `diag.c` in the build

- Remove `! -name 'diag.c'` from Makefile exclusion
- Remove DIAG_Handler/DIAG_Initialize stubs from hal_stubs_posix.c
- Fix compilation issues (diag.c depends on `timer.h`, `can_cbs_tx_fatal-error.h`)
- Real threshold counters, real callbacks, real fatal error tracking

**Pro**: Exact production behavior. No reimplementation.
**Con**: FreeRTOS timer dependency (`diag_fatalErrorResendTimer`). Needs stub for `xTimerCreateStatic`. Callbacks may call contactor functions that need SPS simulation.

### Approach B: Implement threshold counters in hal_stubs_posix.c

- Keep diag.c excluded
- Add per-ID counter array and threshold lookup in our DIAG_Handler stub
- Match the real threshold values from diag_cfg.c
- Call foxBMS's existing callback functions (they're compiled from diag_cfg.c)

**Pro**: No new dependencies. Full control.
**Con**: Must keep threshold values in sync with foxBMS. Reimplementation risk.

**Recommended: Approach B** — we already have the stub infrastructure, and the threshold logic is simple (counter + compare). The callbacks are in diag_cfg.c which IS compiled.

---

## Implementation Steps

### Step 1: Add per-ID threshold counters in hal_stubs_posix.c

```c
#define DIAG_ID_COUNT 85u
static uint16_t diag_occurrence_counter[DIAG_ID_COUNT] = {0};

// Threshold lookup — matches diag_cfg.c diag_diagnosisIdConfiguration[]
static const uint16_t diag_thresholds[DIAG_ID_COUNT] = {
    [18] = 49u,   // CELL_VOLTAGE_OVERVOLTAGE_MSL — 50 events
    [19] = 19u,   // CELL_VOLTAGE_OVERVOLTAGE_RSL — 20 events
    [21] = 49u,   // CELL_VOLTAGE_UNDERVOLTAGE_MSL — 50 events
    [36] = 9u,    // OVERCURRENT_CHARGE_CELL_MSL — 10 events
    [39] = 9u,    // OVERCURRENT_DISCHARGE_CELL_MSL — 10 events
    [24] = 499u,  // TEMP_OVERTEMPERATURE_CHARGE_MSL — 500 events
    [27] = 499u,  // TEMP_OVERTEMPERATURE_DISCHARGE_MSL — 500 events
    // ... all 85 IDs from diag_cfg.c
};
```

### Step 2: Modify DIAG_Handler to use counters

```c
uint32_t DIAG_Handler(uint32_t id, uint32_t event, ...) {
    if (posix_diag_is_hardware_id(id)) return OK;  // unchanged

    if (event == NOT_OK) {
        if (counter[id] <= threshold[id]) {
            counter[id]++;
        }
        if (counter[id] > threshold[id]) {
            // FAULT CONFIRMED — set fatal error flag
            posix_diag_fatal_set |= (1ULL << id);
            return DIAG_HANDLER_RETURN_ERR_OCCURRED;  // ← THIS is the change
        }
        return OK;  // still counting, not yet confirmed
    }
    if (event == OK) {
        if (counter[id] > 0) counter[id]--;
        if (counter[id] == 0) {
            posix_diag_fatal_set &= ~(1ULL << id);  // clear fault
        }
    }
    return OK;
}
```

### Step 3: Fix DIAG_IsAnyFatalErrorSet

```c
uint8_t DIAG_IsAnyFatalErrorSet(void) {
    return (posix_diag_fatal_set != 0u) ? 1u : 0u;
}
```

This is the gate that SYS checks — when it returns true, SYS transitions to ERROR and opens contactors.

### Step 4: Add SIL override intercept patches in foxBMS source

Patch these foxBMS files with `#ifdef FOXBMS_SIL_PROBES` hooks:

**patch_probe_soa.py** — patches `src/app/application/config/soa_cfg.c`:
```c
// Inside SOA voltage check loop:
int32_t cellVoltage_mV = pCellVoltage->cellVoltage_mV[s][c];
#ifdef FOXBMS_SIL_PROBES
extern int sil_override_active(uint8_t id, uint8_t idx);
extern int32_t sil_override_get_i32(uint8_t id, uint8_t idx);
if (sil_override_active(0x01, c)) cellVoltage_mV = sil_override_get_i32(0x01, c);
#endif
```

**patch_probe_soa_temp.py** — patches temperature check similarly.

**patch_probe_soa_current.py** — patches current check.

### Step 5: Write fault injection test

`test_fault_injection.py`:
```python
# Test 1: Overvoltage
sil.override_cell_voltage(0, 4500)  # 4.5V — above MSL
time.sleep(10)  # 50 events at ~10Hz = 5s + 200ms delay
assert sil.read_probe_diag_bitmap() & (1 << 18)  # OV MSL fault set
assert sil.read_probe_sps_state() == 0  # contactors open
assert sil.read_probe_bms_state() != 7  # not NORMAL

# Release → verify recovery
sil.release_cell_voltage(0)
time.sleep(10)  # 50 OK events to clear
assert sil.read_probe_bms_state() == 7  # back to NORMAL
```

### Step 6: Fix test_sil_probes.py deferred tests

OVR.04 (temp), OVR.05 (current), PER.01 should now pass because overrides intercept the foxBMS data pipeline via the SOA patches.

### Step 7: Run full regression

- `test_smoke.py` — still PASS (no faults injected)
- `test_asil.py` — still 50/50
- `test_sil_probes.py` — still 77/77
- `test_fault_injection.py` — NEW, target 11/11

---

## Exit Criteria (from PLAN.md Phase 3)

| # | Criterion | How to verify |
|---|-----------|---------------|
| 3.1 | OV → contactors open | Override cell to 4500mV, wait 5s, check probe 0x7F0 = 0, probe 0x7F9 ≠ 7 |
| 3.2 | UV → contactors open | Override cell to 2500mV, wait 5s |
| 3.3 | OT → contactors open | Override temp to 800 ddegC, wait 50s (500 events at 10Hz) |
| 3.4 | OC → contactors open | Override current to 200000mA, wait 1s (10 events) |
| 3.5 | Cell imbalance → balancing | Override cells to spread, check BAL probe |
| 3.6 | Sensor loss → DIAG fault | Stop plant 0x270, check DIAG bitmap |
| 3.7 | Recovery after fault | Release override, wait for counter decrement, check NORMAL |
| 3.8 | Temp override in pipeline | test_sil_probes OVR.04 passes |
| 3.9 | Current override in pipeline | test_sil_probes OVR.05 passes |
| 3.10 | Override persistence | test_sil_probes PER.01 passes |
| 3.11 | All automated in CI | `make test-faults` |

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| DIAG threshold values wrong (enum reorder) | MEDIUM | HIGH | Use diag_cfg.c array directly if possible, or static_assert on key IDs |
| DIAG_IsAnyFatalErrorSet=true blocks startup | HIGH | HIGH | Only enable threshold counting AFTER BMS reaches NORMAL first time |
| SOA patch breaks precharge | MEDIUM | MEDIUM | Override only active when explicitly set via 0x7E0, not during normal operation |
| foxBMS callbacks crash on POSIX | LOW | HIGH | Callbacks are in diag_cfg.c (compiled), they set database flags — should work |
| Recovery takes too long (500 OK events for OT) | LOW | LOW | Use DIAG_EVENT_RESET for fast clear, or reduce threshold for SIL |

---

## Files to Change

| File | Action | What |
|------|--------|------|
| `src/hal_stubs_posix.c` | MODIFY | Per-ID counters, threshold lookup, DIAG_IsAnyFatalErrorSet |
| `src/foxbms_posix_main.c` | MODIFY | Enable thresholds only after first NORMAL |
| `patches/patch_probe_soa.py` | CREATE | Inject SIL override into SOA voltage check |
| `patches/patch_probe_soa_temp.py` | CREATE | Inject SIL override into SOA temperature check |
| `patches/patch_probe_soa_current.py` | CREATE | Inject SIL override into SOA current check |
| `src/test_fault_injection.py` | CREATE | 11 fault injection tests |
| `src/test_sil_probes.py` | MODIFY | Re-enable OVR.04, OVR.05 |
| `src/Makefile` | MODIFY | Add `make test-faults` target |
| `PLAN.md` | UPDATE | Mark Phase 3 progress |

---

## Dependencies

- Phase 2 COMPLETE ✓
- Phase 2.5 SIL Probes COMPLETE ✓ (77/77)
- foxBMS source patches apply cleanly ✓
- BMW i3 trip data available ✓

No new external dependencies. All work is in existing files.
