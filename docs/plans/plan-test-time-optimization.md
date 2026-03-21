# Plan: Cut Down Fault Injection Test Time

## Current Problem

| Phase | Time | Why |
|-------|------|-----|
| vECU startup | 8s | STANDBY 3s + PRECHARGE 4s + margin 1s |
| Per-test (WARNING) | 2s | Inject + wait + verify + clear |
| Per-test (FATAL) | 2s + 8s restart | Fault triggers ERROR → must restart |
| 200 tests (naive) | ~30 min | Most tests are FATAL → 200 restarts |

## Optimization Strategy

### O1: Sort tests — WARNING first, FATAL last (saves ~50%)

WARNING/RSL/MOL tests don't trigger ERROR. Run them all without restarting.
FATAL/MSL tests trigger ERROR. Batch them at the end — one restart per batch.

| Test type | Count (est.) | Restarts | Time |
|-----------|-------------|----------|------|
| WARNING (RSL+MOL) | ~1,100 | 0 | 1,100 × 2s = 37 min |
| FATAL (MSL) | ~900 | 900 | 900 × 10s = 150 min |
| **Total naive** | 2,005 | 900 | **~187 min** |

### O2: Fast restart — reduce startup from 8s to 2s (saves ~70%)

Current startup bottleneck:
- Plant STANDBY period: 3s (3000 ticks) → reduce to 0.5s (500 ticks)
- PRECHARGE duration: 4s → cannot reduce (foxBMS timing)
- DIAG grace period: 2s → reduce to 0.5s (with 1ms plant, data arrives in 1ms)

Potential: 0.5s plant + 4s precharge + 0.5s grace = **5s startup** (was 8s).

### O3: Parallel test runners (saves ~75%)

Run 4 vECU instances on vcan1, vcan2, vcan3, vcan4 simultaneously.
Each runs 500 tests. Total time = max(individual) ≈ 187/4 = 47 min.

```bash
python3 test_fault_injection.py vcan1 --filter 'FI-VOLT' &
python3 test_fault_injection.py vcan2 --filter 'FI-TEMP' &
python3 test_fault_injection.py vcan3 --filter 'FI-CURR|FI-PLAUS|FI-COMBO' &
python3 test_fault_injection.py vcan4 --filter 'FI-STATE|FI-RECOV|FI-TIMING' &
wait
```

### O4: Checkpoint/restore (saves ~90% on restarts)

Instead of full restart after ERROR:
1. At first NORMAL state, save process state with CRIU (Checkpoint/Restore In Userspace)
2. After FATAL test → kill → restore from checkpoint → back to NORMAL in <1s

Requires: CRIU installed, compatible kernel, SocketCAN state restore.

### O5: In-process reset (saves ~95% on restarts)

Add `--reset` command via CAN 0x7E0 that:
1. Clears all DIAG counters
2. Resets BMS state machine to INITIALIZED
3. Re-triggers STANDBY → PRECHARGE → NORMAL

This avoids process restart entirely. foxBMS doesn't support this natively,
but we can add it via patch (reset diag.state, bms_state.state, etc.).

## Recommended Approach

**Phase 1 (now)**: O1 + O2 — sort tests + reduce startup. Easy, no new infrastructure.
**Phase 2 (CI)**: O3 — parallel runners. Needs 4 vcan interfaces.
**Phase 3 (later)**: O5 — in-process reset. Most impactful but needs patch work.

## Expected Times

| Scenario | 200 tests | 2,005 tests |
|----------|-----------|-------------|
| Current (naive) | 30 min | 5 hours |
| O1+O2 (sort+fast) | 12 min | 2 hours |
| O1+O2+O3 (parallel×4) | 3 min | 30 min |
| O1+O2+O3+O5 (reset) | 2 min | 15 min |
