# foxBMS POSIX vECU — Lessons Learned

## 2026-03-21 — Phase 3 Fault Injection

### 1. RSL/MOL test values must be tier-specific

**Context**: Generated 2,005 test cases via cross-product (signals × methods × tiers).
**Mistake**: STUCK_AT_0 used value 0 for all tiers (MSL, RSL, MOL). 0mV is way below MSL (2500mV), so RSL/MOL tests triggered FATAL instead of WARNING.
**Fix**: Each tier gets a value between its boundaries: OV_RSL=4210mV (between RSL 4200 and MSL 4250).
**Principle**: Cross-product test generation must be followed by tier-aware value validation. Generic fault methods + severity tiers ≠ valid test cases without domain-specific value constraints.

### 2. subprocess.PIPE blocks vECU when buffer fills

**Context**: Test runner started foxbms-vecu with `stdout=subprocess.PIPE` to capture logs.
**Mistake**: foxBMS generates heavy stderr trace output (~50KB/s). PIPE buffer is 64KB. Filled in ~4s → vECU blocked on write → BMS stuck in PRECHARGE forever.
**Fix**: Use `subprocess.DEVNULL` instead. Logs go to /dev/null. If needed, redirect to file, never PIPE.
**Principle**: Never use PIPE for long-running high-output processes unless actively reading the pipe.

### 3. foxBMS default cell config is NOT NMC

**Context**: foxBMS ships with cell thresholds for a low-voltage chemistry (2500mV nominal, 1500-2800mV range).
**Mistake**: Assumed foxBMS defaults match NMC. Plant model sent 3700mV → immediate overvoltage fault.
**Fix**: Patch `battery_cell_cfg.h` for NMC (3700mV nominal, 2500-4250mV range).
**Principle**: Always verify cell chemistry config matches the simulated battery. Read the actual #define values, don't assume.

### 4. IVT current sign convention is configurable

**Context**: Plant model sent negative current for discharge (common IVT convention).
**Mistake**: foxBMS has `BS_POSITIVE_DISCHARGE_CURRENT = true` — positive = discharge. Our negative current was interpreted as charge → overcurrent charge fault.
**Fix**: Check `BS_POSITIVE_DISCHARGE_CURRENT` in battery_system_cfg.h and match plant model sign.
**Principle**: Sign conventions are config-dependent. Read the config. Don't assume "negative = discharge" is universal.

### 5. DIAG grace period must be time-based, not call-based

**Context**: Added startup grace period using a call counter (8000 calls ≈ 8s).
**Mistake**: DIAG_Handler is called from 1ms + 10ms + 100ms tasks. 8000 calls ≈ 1.5s, not 8s.
**Fix**: Use `OS_GetTickCount()` for real elapsed time.
**Principle**: Call count ≠ wall time when function is called from multiple periodic tasks.

### 6. SIL override command format has active byte

**Context**: Test runner packed override as `[cmd, idx, value_BE]`.
**Mistake**: `sil_process_command` expects `[cmd, idx, active, value_LE]`. Missing active byte, wrong endianness.
**Fix**: Pack as `struct.pack("<BBBi", cmd, idx, 1, value)`.
**Principle**: Always read the receiver code to verify the wire format. Don't guess.

### 7. Contactor feedback should not echo command

**Context**: SPS stub set `feedback = currentSet` (command echoed as feedback).
**Mistake**: No independent feedback path → welding/stuck-open impossible to simulate.
**Fix**: Contactor feedback reads from SIL override table first, then falls back to SPS simulation. Re-enabled DIAG IDs 51-53 for contactor feedback mismatch.
**Principle**: Feedback must be independent of command. In SIL, use override table. In HIL, use real GPIO.

### 8. 3D arrays in foxBMS database structs

**Context**: Patch injected `pCV->cellVoltage_mV[s][c] = v;`
**Mistake**: Array is 3D: `[BS_NR_OF_STRINGS][BS_NR_OF_MODULES_PER_STRING][BS_NR_OF_CELL_BLOCKS_PER_MODULE]`.
**Fix**: Use `pCV->cellVoltage_mV[s][m][c]` with module loop.
**Principle**: Always check struct definition before writing array access. foxBMS uses 3D arrays even with 1 module.

## 2026-03-21 — Test Execution Time

### 9. vECU restart dominates test time

**Context**: Each FATAL fault test triggers ERROR → must restart vECU (~8s startup).
**Mistake**: Ran all tests sequentially with restart between each. 200 tests × 8s = 27 min.
**Principle**: Sort tests to minimize restarts. Run all WARNING tests first (no restart needed), then all FATAL tests batched together.
