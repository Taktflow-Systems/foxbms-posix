#!/usr/bin/env python3
"""
foxBMS POSIX vECU — SOC Drift Estimator for CAN Drops

Calculates expected SOC error given CAN message drop rate.
Adapted from mebms-classic tools/soc-drift-calc.py for foxBMS 18S/3Ah pack.

foxBMS SOC counting: uses latest IVT current value × time delta since last
received message. When messages drop, the time delta grows but the stale
current value may not reflect actual current — this causes drift.

Usage:
    python soc-drift-calc.py --drop-rate 0.2 --current 1.0 --duration 3600
    python soc-drift-calc.py --sweep
"""
import argparse
import math
import random
import sys
import os

# Allow importing from tools/ directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from foxbms_constants import (
    CELL_CAPACITY_MAH,
    CELL_COUNT,
    OCV_TABLE,
    ocv_to_voltage_mv,
    voltage_to_soc_permille,
)

# foxBMS 18S/3Ah pack
_CAPACITY_AH = CELL_CAPACITY_MAH / 1000.0  # 3.0 Ah


def estimate_soc_drift(drop_rate, current_a, capacity_ah=_CAPACITY_AH, msg_period_ms=100,
                       duration_s=3600, current_ramp=None):
    """
    Simulate SOC calculation with intermittent CAN message drops.

    foxBMS receives IVT current via CAN 0x521 at 100ms period (plant model rate).
    SOC counting: deltaSOC = current * timeStep / capacity
    Pack: {CELL_COUNT}S, {CELL_CAPACITY_MAH}mAh capacity.
    OCV lookup via foxbms_constants.ocv_to_voltage_mv().
    """
    msg_period_s = msg_period_ms / 1000
    n_messages = int(duration_s / msg_period_s)

    # Perfect SOC change
    perfect_charge_ah = current_a * duration_s / 3600
    perfect_soc_change = perfect_charge_ah / capacity_ah * 100  # percent

    # Simulate dropped messages
    soc_actual = 50.0
    soc_measured = 50.0
    prev_timestamp = 0
    max_gap_s = 0
    total_dropped = 0
    soc_errors = []

    for i in range(n_messages):
        timestamp_s = i * msg_period_s

        # Current profile
        if current_ramp:
            t_frac = timestamp_s / duration_s
            actual_current = current_a * (1 + 0.5 * math.sin(2 * math.pi * t_frac * 10))
        else:
            actual_current = current_a

        # Perfect SOC update
        soc_actual += actual_current * msg_period_s / 3600 / capacity_ah * 100

        # Dropped?
        if random.random() < drop_rate:
            total_dropped += 1
            continue

        # foxBMS behavior: uses time delta since last received message
        time_delta_s = timestamp_s - prev_timestamp
        if time_delta_s > max_gap_s:
            max_gap_s = time_delta_s

        # foxBMS uses CURRENT message's current value * time_delta
        # (not average over the gap — this is the drift source)
        soc_measured += actual_current * time_delta_s / 3600 / capacity_ah * 100
        prev_timestamp = timestamp_s

        # Track error
        soc_errors.append(abs(soc_actual - soc_measured))

    actual_drop_rate = total_dropped / n_messages if n_messages > 0 else 0
    final_error = abs(soc_actual - soc_measured)
    max_error = max(soc_errors) if soc_errors else 0
    avg_error = sum(soc_errors) / len(soc_errors) if soc_errors else 0

    # OCV context: show what voltage the drift corresponds to
    soc_permille_actual = int(soc_actual * 10)
    soc_permille_measured = int(soc_measured * 10)
    v_actual = ocv_to_voltage_mv(soc_permille_actual)
    v_measured = ocv_to_voltage_mv(soc_permille_measured)

    print(f"\n{'='*65}")
    print(f"  SOC DRIFT ESTIMATION — foxBMS {CELL_COUNT}S/{capacity_ah:.0f}Ah Pack")
    print(f"{'='*65}")
    print(f"  Drop rate:          {drop_rate*100:.0f}% (actual: {actual_drop_rate*100:.1f}%)")
    print(f"  Discharge current:  {current_a:.1f} A ({current_a/capacity_ah:.2f}C)")
    print(f"  Pack capacity:      {capacity_ah:.1f} Ah ({CELL_CAPACITY_MAH} mAh)")
    print(f"  Cell count:         {CELL_COUNT}S")
    print(f"  IVT msg period:     {msg_period_ms} ms (CAN 0x521)")
    print(f"  Duration:           {duration_s:.0f} s ({duration_s/60:.0f} min)")
    print(f"  Current profile:    {'Sinusoidal (dynamic)' if current_ramp else 'Constant'}")
    print()
    print(f"  Messages expected:  {n_messages}")
    print(f"  Messages dropped:   {total_dropped}")
    print(f"  Max gap:            {max_gap_s*1000:.0f} ms ({max_gap_s/msg_period_s:.0f} consecutive)")
    print()
    print(f"  Perfect SOC change: {perfect_soc_change:+.2f}%")
    print(f"  Measured SOC change:{soc_measured - 50:+.2f}%")
    print(f"  Final SOC error:    {final_error:.3f}%")
    print(f"  Max SOC error:      {max_error:.3f}%")
    print(f"  Avg SOC error:      {avg_error:.3f}%")
    print()
    print(f"  OCV at actual SOC:  {v_actual} mV (SOC={soc_actual:.1f}%)")
    print(f"  OCV at measured:    {v_measured} mV (SOC={soc_measured:.1f}%)")
    print(f"  Voltage error:      {abs(v_actual - v_measured)} mV")
    print()

    # Compare with ML SOC accuracy
    ML_SOC_RMSE = 1.83  # % from SOC LSTM (BMW i3 validation)
    print(f"  ML SOC LSTM RMSE:   {ML_SOC_RMSE:.2f}% (reference from taktflow-bms-ml)")
    if final_error > ML_SOC_RMSE:
        print(f"  >> CAN drift ({final_error:.2f}%) EXCEEDS ML accuracy ({ML_SOC_RMSE}%)")
        print(f"     ML sidecar would provide better SOC estimate at this drop rate")
    else:
        print(f"  >> CAN drift ({final_error:.2f}%) within ML accuracy ({ML_SOC_RMSE}%)")
        print(f"     Coulomb counting still viable at this drop rate")
    print()

    if final_error < 0.5:
        print(f"  VERDICT: LOW RISK — SOC error < 0.5%")
    elif final_error < 2.0:
        print(f"  VERDICT: MEDIUM RISK — SOC error {final_error:.1f}%")
        print(f"  Dashboard SOC may visibly jump on message recovery.")
    elif final_error < 5.0:
        print(f"  VERDICT: HIGH RISK — SOC error {final_error:.1f}%")
        print(f"  SOC unreliable. Range estimation will be wrong.")
        print(f"  ML sidecar recommended for independent SOC estimate.")
    else:
        print(f"  VERDICT: CRITICAL — SOC error {final_error:.1f}%")
        print(f"  SOC meaningless. Fix CAN drops before trusting SOC.")
        print(f"  ML sidecar essential for any SOC-dependent function.")

    return final_error


def sweep():
    """Sweep across drop rates, comparing constant and dynamic current profiles."""
    cap_ah = _CAPACITY_AH
    print(f"\nSOC drift sweep: 1A discharge, {cap_ah:.0f}Ah pack ({CELL_COUNT}S), 1 hour")
    print(f"IVT period: 100ms (CAN 0x521), ML SOC RMSE reference: 1.83%\n")
    print(f"  {'Drop%':>6} {'Const err':>10} {'Dynamic err':>12} {'Max gap':>10} {'Risk':>10} {'ML better?':>11}")
    print(f"  {'-'*6} {'-'*10} {'-'*12} {'-'*10} {'-'*10} {'-'*11}")

    for rate in [0.01, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50]:
        msg_period_s = 0.1  # 100ms (plant model rate)
        n = int(3600 / msg_period_s)

        # Constant current
        random.seed(42)
        soc_a = 50.0
        soc_m = 50.0
        prev_t = 0
        max_gap = 0
        for i in range(n):
            t = i * msg_period_s
            soc_a += 1.0 * msg_period_s / 3600 / cap_ah * 100
            if random.random() < rate:
                continue
            dt = t - prev_t
            if dt > max_gap:
                max_gap = dt
            soc_m += 1.0 * dt / 3600 / cap_ah * 100
            prev_t = t
        err_const = abs(soc_a - soc_m)

        # Dynamic current (sinusoidal)
        random.seed(42)
        soc_a2 = 50.0
        soc_m2 = 50.0
        prev_t2 = 0
        for i in range(n):
            t = i * msg_period_s
            cur = 1.0 * (1 + 0.5 * math.sin(2 * math.pi * t / 3600 * 10))
            soc_a2 += cur * msg_period_s / 3600 / cap_ah * 100
            if random.random() < rate:
                continue
            dt = t - prev_t2
            soc_m2 += cur * dt / 3600 / cap_ah * 100
            prev_t2 = t
        err_dyn = abs(soc_a2 - soc_m2)

        risk = "LOW" if err_const < 0.5 else "MEDIUM" if err_const < 2 else "HIGH" if err_const < 5 else "CRITICAL"
        ml_better = "YES" if err_const > 1.83 else "no"
        print(f"  {rate*100:>5.0f}% {err_const:>9.3f}% {err_dyn:>11.3f}% {max_gap*1000:>9.0f}ms {risk:>10} {ml_better:>11}")


def main():
    parser = argparse.ArgumentParser(
        description="SOC Drift Estimator for foxBMS CAN Drops",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python soc-drift-calc.py --drop-rate 0.2 --current 1.0
  python soc-drift-calc.py --sweep
  python soc-drift-calc.py --drop-rate 0.1 --current 3.0 --dynamic

foxBMS receives IVT current via CAN 0x521 at 100ms period.
When messages drop, SOC counting uses stale current × larger time delta,
causing drift proportional to current variability and drop rate.

ML SOC LSTM (1.83%% RMSE) provides an independent estimate that doesn't
depend on message continuity — useful when CAN drops degrade coulomb counting.
""")
    parser.add_argument("--drop-rate", type=float, default=0.2,
                        help="Message drop rate 0-1 (default: 0.2)")
    parser.add_argument("--current", type=float, default=1.0,
                        help="Discharge current in A (default: 1.0 = 0.33C)")
    parser.add_argument("--capacity", type=float, default=_CAPACITY_AH,
                        help=f"Pack capacity in Ah (default: {_CAPACITY_AH:.1f})")
    parser.add_argument("--duration", type=float, default=3600,
                        help="Duration in seconds (default: 3600)")
    parser.add_argument("--period-ms", type=float, default=100,
                        help="IVT message period in ms (default: 100)")
    parser.add_argument("--dynamic", action="store_true",
                        help="Use dynamic (sinusoidal) current profile")
    parser.add_argument("--sweep", action="store_true",
                        help="Sweep drop rates 1%%-50%%")
    args = parser.parse_args()

    if args.sweep:
        sweep()
    else:
        estimate_soc_drift(args.drop_rate, args.current, args.capacity,
                          args.period_ms, args.duration, args.dynamic)


if __name__ == "__main__":
    main()
