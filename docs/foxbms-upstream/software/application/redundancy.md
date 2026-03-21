# Redundancy Module

**Source**: [docs.foxbms.org — Redundancy](https://iisb-foxbms.iisb.fraunhofer.de/foxbms/docs/latest/software/modules/application/redundancy/redundancy.html)
**Files**: `src/app/application/redundancy/redundancy.c`, `redundancy.h`
**Status**: Upstream documentation marked "not yet complete"

---

## Function

Cross-checks measurements from primary and redundant sources:
- `MRC_ValidateAfeMeasurement()` — validates AFE cell voltage/temperature readings
- Writes validated data to `DATA_BLOCK_ID_CELL_VOLTAGE` and `DATA_BLOCK_ID_CELL_TEMPERATURE`
- Base (`XXX_BASE`) and redundant (`XXX_REDUNDANCY0`) entries are only read by this module

## Key Discovery (POSIX Port)

**IVT Voltage 3 (0x524) is used for HV bus voltage**, not Voltage 1 (0x522).

The redundancy module reads `highVoltage_mV[s][2]` (index 2 = IVT Voltage 3). Sending only 0x522 and 0x523 is not enough — the precharge voltage check will fail because the bus voltage reads as 0.

## POSIX Port Status

IVT redundancy path untested (GA-25). Only primary measurement simulated. Cross-check code never exercises a mismatch scenario.
