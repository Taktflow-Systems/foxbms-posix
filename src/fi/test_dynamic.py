"""Dynamic fault injection test runners: drift, noise, and oscillation.

Contains run_drift_test (ramped injection), run_noise_test (random offset
injection), and _run_oscillate_test (alternating between fault/normal values).
"""

import random
import time
from typing import TYPE_CHECKING, List

from fi.models import TestCase, TestOutcome, TestResult
from fi.parsers import (
    parse_drift_range,
    parse_injection_value,
    parse_noise_params,
    resolve_diag_bit,
)

if TYPE_CHECKING:
    from fi.executor_base import TestExecutor


def run_drift_test(executor: "TestExecutor", tc: TestCase, cmd: int,
                   indices: List[int], direction: str) -> TestOutcome:
    """Run a DRIFT_UP or DRIFT_DOWN test with ramped injection."""
    try:
        start_val, end_val = parse_drift_range(tc.injection_value)
    except (ValueError, IndexError):
        return TestOutcome(
            test_id=tc.test_id, result=TestResult.ERROR,
            elapsed_ms=0, detail=f"cannot parse drift range: {tc.injection_value}",
            category=tc.category, priority=tc.priority,
        )

    total_steps = abs(end_val - start_val) // 10
    if total_steps == 0:
        total_steps = 1
    step = (end_val - start_val) / total_steps
    step_interval_s = 0.01

    diag_bit = resolve_diag_bit(tc.diag_id, tc.severity_tier)
    t_start = time.monotonic()
    timeout_s = executor.timeout_ms / 1000.0

    current_val = start_val
    for i in range(total_steps + 1):
        current_val = int(start_val + step * i)
        executor.injector.inject_multi(cmd, indices, current_val)
        executor.injector.monitor_and_update(executor.monitor, step_interval_s)

        if time.monotonic() - t_start > timeout_s:
            break

        if tc.expected_reaction == "CONTACTOR_OPEN":
            if executor.monitor.contactors_open():
                elapsed_ms = (time.monotonic() - t_start) * 1000
                return TestOutcome(
                    test_id=tc.test_id, result=TestResult.PASS,
                    elapsed_ms=elapsed_ms,
                    detail=f"contactor open at drift value {current_val}",
                    category=tc.category, priority=tc.priority,
                )
        elif tc.expected_reaction == "WARNING_FLAG":
            if diag_bit is not None and executor.monitor.diag_bit_set(diag_bit):
                if executor.monitor.bms_in_normal():
                    elapsed_ms = (time.monotonic() - t_start) * 1000
                    return TestOutcome(
                        test_id=tc.test_id, result=TestResult.PASS,
                        elapsed_ms=elapsed_ms,
                        detail=f"warning at drift value {current_val}; BMS stays NORMAL",
                        category=tc.category, priority=tc.priority,
                    )

    # Continue holding at end value if drift completed but no reaction yet
    hold_deadline = t_start + timeout_s
    while time.monotonic() < hold_deadline:
        executor.injector.inject_multi(cmd, indices, end_val)
        executor.injector.monitor_and_update(executor.monitor, 0.01)

        if tc.expected_reaction == "CONTACTOR_OPEN" and executor.monitor.contactors_open():
            elapsed_ms = (time.monotonic() - t_start) * 1000
            return TestOutcome(
                test_id=tc.test_id, result=TestResult.PASS,
                elapsed_ms=elapsed_ms,
                detail=f"contactor open (held at {end_val})",
                category=tc.category, priority=tc.priority,
            )
        if tc.expected_reaction == "WARNING_FLAG":
            if diag_bit is not None and executor.monitor.diag_bit_set(diag_bit):
                if executor.monitor.bms_in_normal():
                    elapsed_ms = (time.monotonic() - t_start) * 1000
                    return TestOutcome(
                        test_id=tc.test_id, result=TestResult.PASS,
                        elapsed_ms=elapsed_ms,
                        detail=f"warning set (held at {end_val}); BMS stays NORMAL",
                        category=tc.category, priority=tc.priority,
                    )

    elapsed_ms = executor.timeout_ms
    return TestOutcome(
        test_id=tc.test_id, result=TestResult.FAIL,
        elapsed_ms=elapsed_ms,
        detail=f"{elapsed_ms}ms TIMEOUT | drifted {start_val}->{end_val}, no reaction",
        category=tc.category, priority=tc.priority,
    )


def run_noise_test(executor: "TestExecutor", tc: TestCase, cmd: int,
                   indices: List[int]) -> TestOutcome:
    """Run a NOISE test with value +/- random offset around a center."""
    try:
        amplitude, center = parse_noise_params(tc.injection_value)
    except (ValueError, IndexError):
        return TestOutcome(
            test_id=tc.test_id, result=TestResult.ERROR,
            elapsed_ms=0, detail=f"cannot parse noise params: {tc.injection_value}",
            category=tc.category, priority=tc.priority,
        )

    diag_bit = resolve_diag_bit(tc.diag_id, tc.severity_tier)
    t_start = time.monotonic()
    timeout_s = executor.timeout_ms / 1000.0

    deadline = t_start + timeout_s
    while time.monotonic() < deadline:
        noise_val = center + random.randint(-amplitude, amplitude)
        executor.injector.inject_multi(cmd, indices, noise_val)
        executor.injector.monitor_and_update(executor.monitor, 0.005)

        if tc.expected_reaction == "CONTACTOR_OPEN" and executor.monitor.contactors_open():
            elapsed_ms = (time.monotonic() - t_start) * 1000
            return TestOutcome(
                test_id=tc.test_id, result=TestResult.PASS,
                elapsed_ms=elapsed_ms,
                detail=f"contactor open under noise at center={center}",
                category=tc.category, priority=tc.priority,
            )
        if tc.expected_reaction == "WARNING_FLAG":
            if diag_bit is not None and executor.monitor.diag_bit_set(diag_bit):
                if executor.monitor.bms_in_normal():
                    elapsed_ms = (time.monotonic() - t_start) * 1000
                    return TestOutcome(
                        test_id=tc.test_id, result=TestResult.PASS,
                        elapsed_ms=elapsed_ms,
                        detail=f"warning under noise; BMS stays NORMAL",
                        category=tc.category, priority=tc.priority,
                    )

    elapsed_ms = executor.timeout_ms
    return TestOutcome(
        test_id=tc.test_id, result=TestResult.FAIL,
        elapsed_ms=elapsed_ms,
        detail=f"{elapsed_ms}ms TIMEOUT | noise center={center} amp={amplitude}",
        category=tc.category, priority=tc.priority,
    )


def _run_oscillate_test(executor: "TestExecutor", tc: TestCase, cmd: int,
                         indices: List[int]) -> TestOutcome:
    """Oscillate between normal and fault value."""
    value = parse_injection_value(tc.injection_value, tc.fault_method)
    if value is None:
        value = 4260  # Default OV value
    normal_val = 3700

    diag_bit = resolve_diag_bit(tc.diag_id, tc.severity_tier)
    t_start = time.monotonic()
    timeout_s = executor.timeout_ms / 1000.0

    deadline = t_start + timeout_s
    cycle = 0
    while time.monotonic() < deadline:
        if cycle % 2 == 0:
            executor.injector.inject_multi(cmd, indices, value)
        else:
            executor.injector.inject_multi(cmd, indices, normal_val)
        cycle += 1
        executor.injector.monitor_and_update(executor.monitor, 0.05)

        if tc.expected_reaction == "CONTACTOR_OPEN" and executor.monitor.contactors_open():
            elapsed_ms = (time.monotonic() - t_start) * 1000
            return TestOutcome(
                test_id=tc.test_id, result=TestResult.PASS,
                elapsed_ms=elapsed_ms, detail="contactor open under oscillation",
                category=tc.category, priority=tc.priority,
            )

    elapsed_ms = executor.timeout_ms
    return TestOutcome(
        test_id=tc.test_id, result=TestResult.FAIL,
        elapsed_ms=elapsed_ms, detail=f"{elapsed_ms}ms TIMEOUT | oscillation test",
        category=tc.category, priority=tc.priority,
    )
