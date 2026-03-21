# Plan: Plant Model Real Integration (Phase 2)

**Date**: 2026-03-21
**Status**: IN PROGRESS
**Goal**: Replace static plant model with dynamic closed-loop battery simulation

---

## Current State (shortcuts)

| What | Current | Target |
|------|---------|--------|
| Current | 0 A always | 10 A discharge when NORMAL, 0 A when contactors open |
| Cell voltage | 3700 mV static | OCV(SOC) curve: 3.4V @ 0% → 4.2V @ 100% |
| Pack voltage | 66600 mV static | N × V_cell(SOC) − I × R_internal |
| Temperature | 25.0°C static | Keep static for now (Phase 3) |
| SOC | 50% never changes | Coulomb counting: SOC decreases under load |
| Cell variation | All identical | ±10 mV Gaussian noise per cell |
| Contactor feedback | Open-loop | Read foxBMS 0x220 for state, adjust current |

## Steps

### Step 1: Add SOC state and coulomb counter
- Initial SOC = 50%
- Q_cell = 3000 mAh (typical 18650)
- dt = 0.1s (100ms loop)
- SOC -= (I_mA / 1000) / Q_cell_Ah * (dt / 3600) * 100

### Step 2: SOC → OCV lookup
- Linear approximation: V_OCV = 3400 + 800 × (SOC / 100) mV
- Per cell, with ±10 mV Gaussian noise

### Step 3: Dynamic current based on contactor state
- Read foxBMS CAN TX (non-blocking RX on same socket)
- When BMS state = NORMAL (0x220 byte 0 lower nibble = 7): I = 10000 mA
- When contactors open: I = 0 mA

### Step 4: IR drop on pack voltage
- R_internal = 50 mΩ per cell × 18 = 900 mΩ
- V_pack = 18 × V_OCV − I_A × R_total_mΩ / 1000

### Step 5: Update IVT messages
- 0x521: current = I_load_mA (signed, negative = discharge per IVT convention)
- 0x522/523/524: V_pack_mV (dynamic)

### Step 6: Update cell voltage messages
- 0x270 mux groups: per-cell V_OCV ± noise

### Step 7: Verify
- Run smoke test — BMS should still reach NORMAL
- Check 0x235 SOC decreases over time
- Check candump shows changing voltages

## Also fix (from audit)

- [ ] Delete dead `posix_inject_cell_data()` function from hal_stubs_posix.c
- [ ] Fix canTransmit DLC (use actual DLC from mailbox, not hardcoded 8)
- [ ] Fix `__curpc()` to use `__builtin_return_address(0)`
- [ ] Gate MEAS_Control() to 1ms rate instead of every loop iteration
