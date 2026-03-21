# Balancing Module

**Source**: [docs.foxbms.org — Balancing](https://iisb-foxbms.iisb.fraunhofer.de/foxbms/docs/latest/software/modules/application/bal/bal.html)
**Files**: `src/app/application/bal/bal.c`, `bal.h`, `bal_cfg.h`
**Strategies**: `bal_strategy_voltage.c`, `bal_strategy_history.c`, `bal_strategy_none.c`

---

## Strategy 1: Voltage-Based Balancing

1. Find minimum cell voltage in pack
2. Balance all cells with voltage > `V_min + BAL_GetBalancingThreshold_mV()`
3. When equalization complete, new threshold = `V_min + threshold + BAL_HYSTERESIS_mV` (prevents oscillation)

## Strategy 2: History-Based Balancing (SOC-Based)

1. Wait for rest period (voltages stabilize)
2. Convert cell voltages to SOC via lookup table
3. Convert SOC to DOD: `DOD = Capacity × (1 - SOC)`
4. Most discharged cell becomes reference (DOD = 0)
5. Calculate charge difference for each cell: `Charge_diff = DOD_ref - DOD_cell`
6. Balance continuously: every second, `I_bal = V_cell / R_balancing`
7. Reduce charge difference by `I_bal × 1s` each second
8. Deactivate when charge difference = 0

**Requirements**:
- `SLV_BALANCING_RESISTANCE_ohm` must match physical balancing resistors
- `SE_GetStateOfChargeFromVoltage()` lookup table must be configured

## Strategy 3: No Balancing

Disables all cell equalization.

## POSIX Port Status

Balancing logic runs but has nothing to balance — all cells are identical (3700mV). GAP-ANALYSIS GA-10: need per-cell voltage variation (Phase 2 remaining work) to exercise balancing decisions.
