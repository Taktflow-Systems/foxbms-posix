"""Combo and plausibility test runners.

Contains run_combo_simultaneous_test, run_combo_sequential_test,
run_plaus_mismatch_test, run_plaus_spread_test, and shared helpers
_inject_combo_values and _monitor_for_reaction.
"""

import time
from typing import TYPE_CHECKING, Dict, List, Optional

from fi.constants import SIL_CELL_TEMP, SIL_CELL_VOLTAGE, SIL_PACK_CURRENT
from fi.models import TestCase, TestOutcome, TestResult
from fi.parsers import parse_compound_injection, parse_target, resolve_diag_bit

if TYPE_CHECKING:
    from fi.executor_base import TestExecutor


def run_plaus_mismatch_test(executor: "TestExecutor", tc: TestCase) -> TestOutcome:
    """Run a PLAUS INJECTED_MISMATCH test."""
    vals = parse_compound_injection(tc.injection_value)
    if not vals:
        return TestOutcome(
            test_id=tc.test_id, result=TestResult.ERROR,
            elapsed_ms=0,
            detail=f"cannot parse PLAUS value: {tc.injection_value}",
            category=tc.category, priority=tc.priority,
        )

    diag_bit = resolve_diag_bit(tc.diag_id, tc.severity_tier)
    t_start = time.monotonic()
    timeout_s = executor.timeout_ms / 1000.0

    if "cell" in vals:
        cell_val = vals["cell"]
        executor.injector.inject_multi(SIL_CELL_VOLTAGE, list(range(18)), cell_val)
    elif "T" in vals and "I" in vals:
        executor.injector.inject_multi(SIL_CELL_TEMP, list(range(5)), vals["T"])
        executor.injector.inject(SIL_PACK_CURRENT, 0, vals["I"])
    elif "SOC" in vals and "V" in vals:
        executor.injector.inject_multi(SIL_CELL_VOLTAGE, list(range(18)), vals["V"])
    elif "V" in vals and "T" in vals and "I" in vals:
        executor.injector.inject_multi(SIL_CELL_VOLTAGE, list(range(18)), vals["V"])
        executor.injector.inject_multi(SIL_CELL_TEMP, list(range(5)), vals["T"])
        executor.injector.inject(SIL_PACK_CURRENT, 0, vals["I"])
    else:
        return TestOutcome(
            test_id=tc.test_id, result=TestResult.SKIP,
            elapsed_ms=0,
            detail=f"unsupported PLAUS key combination: {list(vals.keys())}",
            category=tc.category, priority=tc.priority,
        )

    return _monitor_for_reaction(executor, tc, diag_bit, t_start, timeout_s,
                                  sustain_fn=None)


def run_plaus_spread_test(executor: "TestExecutor", tc: TestCase) -> TestOutcome:
    """Run a PLAUS INJECTED_SPREAD test."""
    vals = parse_compound_injection(tc.injection_value)
    spread = vals.get("spread")
    if spread is None:
        return TestOutcome(
            test_id=tc.test_id, result=TestResult.ERROR,
            elapsed_ms=0,
            detail=f"cannot parse spread value: {tc.injection_value}",
            category=tc.category, priority=tc.priority,
        )

    diag_bit = resolve_diag_bit(tc.diag_id, tc.severity_tier)
    t_start = time.monotonic()
    timeout_s = executor.timeout_ms / 1000.0

    nominal = 3700
    half_spread = spread // 2
    for i in range(18):
        cell_val = nominal + half_spread - (spread * i // 17)
        executor.injector.inject(SIL_CELL_VOLTAGE, i, cell_val)

    return _monitor_for_reaction(executor, tc, diag_bit, t_start, timeout_s,
                                  sustain_fn=None)


def run_combo_simultaneous_test(executor: "TestExecutor", tc: TestCase) -> TestOutcome:
    """Run a COMBO SIMULTANEOUS test: inject multiple faults at once."""
    vals = parse_compound_injection(tc.injection_value)
    if not vals:
        return TestOutcome(
            test_id=tc.test_id, result=TestResult.ERROR,
            elapsed_ms=0,
            detail=f"cannot parse COMBO value: {tc.injection_value}",
            category=tc.category, priority=tc.priority,
        )

    t_start = time.monotonic()
    timeout_s = executor.timeout_ms / 1000.0

    target_type, sub_targets = parse_target(tc.target)
    _inject_combo_values(executor, vals, tc,
                          sub_targets if target_type == "compound" else [])

    return _monitor_for_reaction(executor, tc, None, t_start, timeout_s,
                                  sustain_fn=lambda: _inject_combo_values(
                                      executor, vals, tc,
                                      sub_targets if target_type == "compound" else []))


def run_combo_sequential_test(executor: "TestExecutor", tc: TestCase) -> TestOutcome:
    """Run a COMBO SEQUENTIAL test: inject faults with a time gap."""
    t_start = time.monotonic()
    timeout_s = executor.timeout_ms / 1000.0

    parts = tc.injection_value.split("/")
    injections = []
    for part in parts:
        part = part.strip()
        if "@t" not in part:
            continue
        fault_type = part.split("@")[0]
        time_spec = part.split("@")[1]
        delay_ms = 0
        if "+=" in time_spec or "+" in time_spec:
            try:
                delay_str = time_spec.replace("t+", "").replace("t=", "").replace("ms", "")
                delay_ms = int(delay_str)
            except ValueError:
                pass
        injections.append((fault_type, delay_ms))

    for fault_type, delay_ms in injections:
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)

        ft = fault_type.upper()
        if ft == "OV":
            executor.injector.inject_multi(SIL_CELL_VOLTAGE, [0], 4260)
        elif ft == "UV":
            executor.injector.inject_multi(SIL_CELL_VOLTAGE, [0], 2490)
        elif ft == "OC":
            executor.injector.inject(SIL_PACK_CURRENT, 0, 16000)
        elif ft == "OT":
            executor.injector.inject_multi(SIL_CELL_TEMP, [0], 560)
        elif ft == "UT":
            executor.injector.inject_multi(SIL_CELL_TEMP, [0], -210)

    return _monitor_for_reaction(executor, tc, None, t_start, timeout_s,
                                  sustain_fn=None)


def _inject_combo_values(executor: "TestExecutor", vals: Dict[str, int],
                          tc: TestCase, sub_targets: list) -> None:
    """Inject multiple override values for COMBO tests."""
    if "CELL_V" in vals or "V" in vals:
        v = vals.get("CELL_V", vals.get("V", 3700))
        cell_indices = [0]
        for st in sub_targets:
            if isinstance(st, tuple) and st[0] == "cell":
                cell_indices = st[1]
                break
        executor.injector.inject_multi(SIL_CELL_VOLTAGE, cell_indices, v)

    if "I" in vals:
        executor.injector.inject(SIL_PACK_CURRENT, 0, vals["I"])

    if "T" in vals:
        sensor_indices = [0]
        for st in sub_targets:
            if isinstance(st, tuple) and st[0] == "sensor":
                sensor_indices = st[1]
                break
        executor.injector.inject_multi(SIL_CELL_TEMP, sensor_indices, vals["T"])

    for key, val in vals.items():
        if key.startswith("C") and key[1:].isdigit():
            cell_idx = int(key[1:])
            executor.injector.inject(SIL_CELL_VOLTAGE, cell_idx, val)


def _monitor_for_reaction(executor: "TestExecutor", tc: TestCase,
                           diag_bit: Optional[int],
                           t_start: float, timeout_s: float,
                           sustain_fn=None) -> TestOutcome:
    """Shared monitor loop for PLAUS/COMBO tests."""
    deadline = t_start + timeout_s
    diag_detected = False
    contactor_opened = False
    t_diag = 0.0

    while time.monotonic() < deadline:
        executor.injector.monitor_and_update(executor.monitor, 0.005)

        if sustain_fn is not None:
            sustain_fn()

        if not diag_detected and diag_bit is not None:
            if executor.monitor.diag_bit_set(diag_bit):
                diag_detected = True
                t_diag = time.monotonic() - t_start

        if not contactor_opened and executor.monitor.contactors_open():
            contactor_opened = True

        if tc.expected_reaction in ("CONTACTOR_OPEN", "PLAUSIBILITY_ERROR",
                                    "BOTH_DETECTED", "FAULT_ACTIVE"):
            if contactor_opened:
                elapsed_ms = (time.monotonic() - t_start) * 1000
                detail = "contactor open confirmed"
                if diag_detected:
                    detail += f"; DIAG bit {diag_bit} at {t_diag*1000:.0f}ms"
                return TestOutcome(
                    test_id=tc.test_id, result=TestResult.PASS,
                    elapsed_ms=elapsed_ms, detail=detail,
                    category=tc.category, priority=tc.priority,
                )

        elif tc.expected_reaction == "WARNING_FLAG":
            if diag_detected and executor.monitor.bms_in_normal():
                elapsed_ms = t_diag * 1000
                return TestOutcome(
                    test_id=tc.test_id, result=TestResult.PASS,
                    elapsed_ms=elapsed_ms,
                    detail=f"DIAG bit {diag_bit} set; BMS stays NORMAL",
                    category=tc.category, priority=tc.priority,
                )

        elif tc.expected_reaction in ("NO_REACTION", "NO_CONTACTOR_OPEN"):
            pass

    # Timeout reached
    elapsed_ms = (time.monotonic() - t_start) * 1000

    if tc.expected_reaction in ("NO_REACTION", "NO_CONTACTOR_OPEN"):
        if not contactor_opened and not executor.monitor.bms_in_error():
            return TestOutcome(
                test_id=tc.test_id, result=TestResult.PASS,
                elapsed_ms=elapsed_ms, detail="no reaction as expected",
                category=tc.category, priority=tc.priority,
            )

    parts = []
    if diag_bit is not None and not diag_detected:
        parts.append(f"DIAG bit {diag_bit} not set")
    if not contactor_opened:
        parts.append("contactor did not open")
    detail = f"{elapsed_ms:.0f}ms TIMEOUT | " + "; ".join(parts) if parts else f"{elapsed_ms:.0f}ms TIMEOUT"
    return TestOutcome(
        test_id=tc.test_id, result=TestResult.FAIL,
        elapsed_ms=elapsed_ms, detail=detail,
        category=tc.category, priority=tc.priority,
    )
