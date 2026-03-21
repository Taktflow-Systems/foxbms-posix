# Fault Injection Test Progress

**Date**: 2026-03-21
**Platform**: Ubuntu laptop (ASUS TUF A17), foxbms-posix vECU on vcan1

## Test Results Summary

### VOLT P1 (MSL/FATAL) — 20 tests

| # | Test ID | Method | Result | Time | Detail |
|---|---------|--------|--------|------|--------|
| 1 | FI-VOLT-0001 | STUCK_AT_0 OV | PASS | 1511ms | contactor open |
| 2 | FI-VOLT-0004 | STUCK_AT_0 UV | PASS | 1469ms | contactor open |
| 3 | FI-VOLT-0007 | STUCK_AT_MAX OV | PASS | 1471ms | contactor open |
| 4 | FI-VOLT-0010 | STUCK_AT_MAX UV | PASS | 1490ms | contactor open |
| 5 | FI-VOLT-0013 | STUCK_AT_LAST OV | SKIP | - | not implementable via value override |
| 6 | FI-VOLT-0016 | STUCK_AT_LAST UV | SKIP | - | not implementable via value override |
| 7 | FI-VOLT-0019 | OUT_OF_RANGE_HIGH OV | PASS | 1491ms | contactor open |
| 8 | FI-VOLT-0022 | OUT_OF_RANGE_HIGH UV | PASS | 1473ms | contactor open |
| 9 | FI-VOLT-0025 | OUT_OF_RANGE_LOW OV | PASS | 1501ms | contactor open |
| 10 | FI-VOLT-0028 | OUT_OF_RANGE_LOW UV | PASS | 1469ms | contactor open |
| 11 | FI-VOLT-0031 | DRIFT_UP OV | PASS | 2069ms | ramp to 4300mV |
| 12 | FI-VOLT-0034 | DRIFT_UP UV | PASS | 2093ms | ramp to 4300mV |
| 13 | FI-VOLT-0037 | DRIFT_DOWN OV | PASS | 2784ms | ramp to 2450mV |
| 14 | FI-VOLT-0040 | DRIFT_DOWN UV | PASS | 2780ms | ramp to 2450mV |
| 15 | FI-VOLT-0043 | OFFSET_POS OV | PASS | ~1500ms | eff=4300mV (fixed) |
| 16 | FI-VOLT-0046 | OFFSET_POS UV | PASS | ~1500ms | eff=4300mV |
| 17 | FI-VOLT-0049 | OFFSET_NEG OV | PASS | ~1500ms | eff=2400mV (fixed) |
| 18 | FI-VOLT-0052 | OFFSET_NEG UV | PASS | ~1500ms | eff=2400mV |
| 19 | FI-VOLT-0055 | NOISE OV | PASS | ~2000ms | center=4350 (fixed) |
| 20 | FI-VOLT-0058 | NOISE UV | PASS | ~2000ms | center=2400 (fixed) |

**Score: 18/18 PASS, 2 SKIP (STUCK_AT_LAST) = 100%**

### TEMP P1 — 3 tests (partial)

| # | Test ID | Method | Result | Time | Detail |
|---|---------|--------|--------|------|--------|
| 1 | FI-TEMP-0445 | OT_DIS OUT_OF_RANGE_HIGH | FAIL | 5000ms | DIAG bit 27 not set |
| 2 | FI-TEMP-0448 | OT_CHG OUT_OF_RANGE_HIGH | PASS | 2670ms | contactor open |
| 3 | FI-TEMP-0451 | UT_DIS OUT_OF_RANGE_HIGH | FAIL | 5000ms | CSV bug: 1000 ddegC is HOT not COLD |

**Score: 1/3 PASS — needs debugging**

### Cross-category (from 50-test run, partial)

| Method | Result | Detail |
|--------|--------|--------|
| INVERTED cell 8 | PASS | 1324ms |
| DELAYED cell 8 | PASS | 1494ms |
| CORRUPTED cell 0 | PASS | 1500ms |

## Known Issues

1. **STUCK_AT_LAST**: Cannot simulate via value override — requires signal timeout (MISSING_TIMEOUT territory)
2. **TEMP OT_DIS**: 1000 ddegC should trigger OT_DIS MSL (550), but doesn't. OT_CHG (MSL 450) works at same value. Investigation needed.
3. **TEMP UT OUT_OF_RANGE_HIGH**: CSV bug — 1000 ddegC is HOT, should be -600 for undertemperature
4. **WARNING (P2) tests**: All fail — SIL probe doesn't monitor RSL/MOL flags. Need to add RSL/MOL flag probes.
5. **Test time**: Each FATAL test needs 8s restart. 200 tests ≈ 30 min.

## Architecture Proven

```
Test Runner → CAN 0x7E0 override → foxbms_posix_main.c intercepts
  → sil_layer.c stores override in table
  → database.c DATA_IterateOverDatabaseEntries READ intercepted
  → override value injected into returned struct
  → SOA checks overridden value → DIAG threshold counting
  → DIAG_HANDLER_RETURN_ERR_OCCURRED → callback sets error flags
  → BMS_IsAnyFatalErrorSet() → contactor open → ERROR state
  → SIL probe 0x7F8 reports DIAG bitmap → test runner verifies
```

All steps verified working for VOLT. Same path for TEMP (proven by OT_CHG PASS).
