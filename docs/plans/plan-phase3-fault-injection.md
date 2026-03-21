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

## Approach: Re-include real `diag.c` (Approach A)

**Decision**: Use the real foxBMS `diag.c` — no reimplementation. We can modify internals via SIL probes now.

- Remove `! -name 'diag.c'` from Makefile exclusion list
- Remove DIAG_Handler/DIAG_Initialize/DIAG_CheckEvent/DIAG_IsAnyFatalErrorSet stubs from hal_stubs_posix.c
- Stub the FreeRTOS timer dependency (`xTimerCreateStatic` already stubbed in hal_stubs_posix.c)
- Fix `can_cbs_tx_fatal-error.h` include (stub or include the real file)
- Real threshold counters, real callbacks, real fatal error tracking — exact production behavior
- Hardware-absent DIAG IDs: suppress via `DIAG_EVALUATION_DISABLED` in diag_cfg.c patch (not in our stub)

**Startup safety**: Use SIL layer to manage startup sequence. Hardware-absent faults (SPI, I2C, SBC, IMD) are disabled at the diag_cfg.c level via `DIAG_EVALUATION_DISABLED`, so they never fire. Software faults (OV, OC, OT) only fire when real out-of-range data arrives — during normal startup with the plant model providing valid data, no software faults trigger.

**OT threshold**: Keep real 500 events (~50s at 10Hz). Realistic demo behavior — overtemperature faults develop slowly like in real life.

---

## Implementation Steps

### Step 1: Re-include diag.c in the build

**Makefile**: Remove `! -name 'diag.c'` from APP_SRCS exclusion.

**hal_stubs_posix.c**: Remove these stubs (they're now provided by the real diag.c):
- `DIAG_Handler()`
- `DIAG_Initialize()`
- `DIAG_CheckEvent()`
- `DIAG_IsAnyFatalErrorSet()`
- `DIAG_GetDiagnosisEntryState()`
- `DIAG_GetDelay()`
- `DIAG_Reset()`
- `posix_diag_is_hardware_id()` — no longer needed
- `posix_diag_fault_count` — no longer needed

Keep DIAG probe code in SIL layer (read from real diag state instead of our stub variables).

### Step 2: Fix diag.c compilation dependencies

**diag.c includes**:
- `timer.h` → FreeRTOS timer, already have `xTimerCreateStatic` stub
- `can_cbs_tx_fatal-error.h` → CAN TX for fatal error broadcast. Either include the real file (it's in foxBMS source) or stub the function.

**diag.c uses**:
- `diag_fatalErrorResendTimer` — FreeRTOS software timer. `xTimerCreateStatic` returns a dummy pointer (already stubbed). Timer callback never fires (no timer task) — acceptable for SIL since the fatal error CAN message is sent once at fault-set, the resend timer is optional.
- `DIAG_SetFatalErrorById()` / `DIAG_IsAnyFatalErrorSet()` — these are IN diag.c, so they work natively.

### Step 3: Patch diag_cfg.c to disable hardware-absent DIAG IDs

Create `patches/patch_diag_cfg_posix.py`:

Set `DIAG_EVALUATION_DISABLED` for all hardware-absent IDs in the `diag_diagnosisIdConfiguration[]` array. This is the correct foxBMS mechanism — no stub needed.

```python
# For each hardware-absent ID, change enable_evaluate from ENABLED to DISABLED
ids_to_disable = [
    "DIAG_ID_FLASHCHECKSUM", "DIAG_ID_AFE_SPI", "DIAG_ID_AFE_COMMUNICATION_INTEGRITY",
    "DIAG_ID_AFE_MUX", "DIAG_ID_AFE_CONFIG", "DIAG_ID_AFE_OPEN_WIRE",
    "DIAG_ID_SBC_FIN_ERROR", "DIAG_ID_SBC_RSTB_ERROR",
    "DIAG_ID_I2C_PEX_ERROR", "DIAG_ID_I2C_RTC_ERROR",
    "DIAG_ID_RTC_CLOCK_INTEGRITY_ERROR", "DIAG_ID_RTC_BATTERY_LOW_ERROR",
    "DIAG_ID_FRAM_READ_CRC_ERROR", "DIAG_ID_INTERLOCK_FEEDBACK",
    "DIAG_ID_STRING_MINUS_CONTACTOR_FEEDBACK", "DIAG_ID_STRING_PLUS_CONTACTOR_FEEDBACK",
    "DIAG_ID_PRECHARGE_CONTACTOR_FEEDBACK",
    "DIAG_ID_INSULATION_MEASUREMENT_VALID", "DIAG_ID_LOW_INSULATION_RESISTANCE_ERROR",
    "DIAG_ID_LOW_INSULATION_RESISTANCE_WARNING", "DIAG_ID_INSULATION_GROUND_ERROR",
    "DIAG_ID_ALERT_MODE", "DIAG_ID_AEROSOL_ALERT", "DIAG_ID_SUPPLY_VOLTAGE_CLAMP_30C_LOST",
    # Timing-dependent IDs (cooperative loop mismatch):
    "DIAG_ID_CAN_TIMING",
    "DIAG_ID_BASE_CELL_VOLTAGE_MEASUREMENT_TIMEOUT",
    "DIAG_ID_REDUNDANCY0_CELL_VOLTAGE_MEASUREMENT_TIMEOUT",
    "DIAG_ID_BASE_CELL_TEMPERATURE_MEASUREMENT_TIMEOUT",
    "DIAG_ID_REDUNDANCY0_CELL_TEMPERATURE_MEASUREMENT_TIMEOUT",
    "DIAG_ID_CURRENT_MEASUREMENT_TIMEOUT", "DIAG_ID_CURRENT_MEASUREMENT_ERROR",
    "DIAG_ID_CURRENT_SENSOR_V1_MEASUREMENT_TIMEOUT",
    "DIAG_ID_CURRENT_SENSOR_V2_MEASUREMENT_TIMEOUT",
    "DIAG_ID_CURRENT_SENSOR_V3_MEASUREMENT_TIMEOUT",
    "DIAG_ID_CURRENT_SENSOR_POWER_MEASUREMENT_TIMEOUT",
    "DIAG_ID_POWER_MEASUREMENT_ERROR",
    "DIAG_ID_CURRENT_SENSOR_CC_RESPONDING",
    "DIAG_ID_CURRENT_SENSOR_EC_RESPONDING",
    "DIAG_ID_CURRENT_SENSOR_RESPONDING",
    "DIAG_ID_PLAUSIBILITY_PACK_VOLTAGE",
]
```

Software-checkable IDs (OV, UV, OC, OT, plausibility spread) stay ENABLED — these are the ones we want to test.

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
| diag.c doesn't compile (missing headers) | MEDIUM | MEDIUM | Stub `can_cbs_tx_fatal-error.h` functions, FreeRTOS timer already stubbed |
| Real DIAG blocks startup (transient faults) | HIGH | HIGH | Disable timing-dependent IDs via `DIAG_EVALUATION_DISABLED` in diag_cfg.c patch |
| SOA patch breaks precharge | MEDIUM | MEDIUM | Overrides only active when explicitly set via 0x7E0 — no effect during normal startup |
| DIAG callbacks call unsupported functions | LOW | HIGH | Callbacks set database flags — should work. If they call contactor functions, SPS sim handles it |
| OT recovery takes 50s (500 OK events) | LOW | LOW | Acceptable — realistic. Use DIAG_EVENT_RESET for fast test reset if needed |
| diag.c symbol conflicts with hal_stubs_posix.c | HIGH | MEDIUM | Must remove ALL DIAG stubs from hal_stubs_posix.c before re-including diag.c |

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
