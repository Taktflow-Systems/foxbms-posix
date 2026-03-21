"""Contactor open and no-reaction test runners.

Contains run_contactor_open_test (expecting CONTACTOR_OPEN reaction)
and run_no_reaction_test (expecting NO_REACTION / NO_CONTACTOR_OPEN).
"""

import time
from typing import TYPE_CHECKING, List

from fi.models import TestCase, TestOutcome, TestResult
from fi.parsers import parse_threshold, resolve_diag_bit

if TYPE_CHECKING:
    from fi.executor_base import TestExecutor


def run_contactor_open_test(executor: "TestExecutor", tc: TestCase, cmd: int,
                            indices: List[int], value: int) -> TestOutcome:
    """Run a test expecting CONTACTOR_OPEN reaction."""
    events, delay_ms = parse_threshold(tc.threshold)
    diag_bit = resolve_diag_bit(tc.diag_id, tc.severity_tier)

    pre_fault_count = executor.monitor.diag_fault_count
    pre_bitmap = executor.monitor.diag_bitmap

    t_start = time.monotonic()
    timeout_s = executor.timeout_ms / 1000.0

    executor.injector.inject_multi(cmd, indices, value)

    contactor_opened = False
    diag_detected = False
    bms_error = False
    t_contactor = 0.0
    t_diag = 0.0

    deadline = t_start + timeout_s
    while time.monotonic() < deadline:
        executor.injector.monitor_and_update(executor.monitor, 0.005)

        # Re-inject for sustained fault methods
        if tc.fault_method in ("STUCK_AT_0", "STUCK_AT_MAX", "STUCK_AT_LAST",
                                "OUT_OF_RANGE_HIGH", "OUT_OF_RANGE_LOW",
                                "STEP_TO_VALUE", "INVERTED", "CONTINUOUS",
                                "OFFSET_POS", "OFFSET_NEG"):
            executor.injector.inject_multi(cmd, indices, value)

        if not diag_detected and diag_bit is not None:
            if executor.monitor.diag_bit_set(diag_bit):
                diag_detected = True
                t_diag = time.monotonic() - t_start

        if not bms_error and executor.monitor.bms_in_error():
            bms_error = True

        if not contactor_opened and executor.monitor.contactors_open():
            contactor_opened = True
            t_contactor = time.monotonic() - t_start

        if contactor_opened:
            elapsed_ms = t_contactor * 1000
            detail = "contactor open confirmed"
            if diag_detected:
                detail += f"; DIAG bit {diag_bit} set at {t_diag*1000:.0f}ms"
            return TestOutcome(
                test_id=tc.test_id, result=TestResult.PASS,
                elapsed_ms=elapsed_ms, detail=detail,
                category=tc.category, priority=tc.priority,
                diag_time_ms=t_diag * 1000 if diag_detected else 0.0,
                contactor_time_ms=t_contactor * 1000,
                bms_state_trace=f"NORMAL -> ERROR at {elapsed_ms:.0f}ms" if bms_error else "",
            )

    # Timeout
    elapsed_ms = executor.timeout_ms
    parts = []
    if not diag_detected:
        parts.append(f"DIAG bit {diag_bit} not set")
    if not bms_error:
        parts.append("BMS did not enter ERROR")
    if not contactor_opened:
        parts.append("contactor did not open")
    detail = f"{elapsed_ms}ms TIMEOUT | " + "; ".join(parts)
    return TestOutcome(
        test_id=tc.test_id, result=TestResult.FAIL,
        elapsed_ms=elapsed_ms, detail=detail,
        category=tc.category, priority=tc.priority,
        diag_time_ms=t_diag * 1000 if diag_detected else 0.0,
        contactor_time_ms=t_contactor * 1000 if contactor_opened else 0.0,
    )


def run_no_reaction_test(executor: "TestExecutor", tc: TestCase, cmd: int,
                          indices: List[int], value: int) -> TestOutcome:
    """Run a test expecting NO_REACTION or NO_CONTACTOR_OPEN."""
    t_start = time.monotonic()

    executor.injector.inject_multi(cmd, indices, value)

    observe_s = min(executor.timeout_ms / 1000.0, 2.0)
    deadline = t_start + observe_s

    while time.monotonic() < deadline:
        executor.injector.monitor_and_update(executor.monitor, 0.01)
        executor.injector.inject_multi(cmd, indices, value)

        if executor.monitor.bms_in_error():
            elapsed_ms = (time.monotonic() - t_start) * 1000
            return TestOutcome(
                test_id=tc.test_id, result=TestResult.FAIL,
                elapsed_ms=elapsed_ms,
                detail="BMS entered ERROR (expected no reaction)",
                category=tc.category, priority=tc.priority,
            )

        if executor.monitor.contactors_open():
            elapsed_ms = (time.monotonic() - t_start) * 1000
            return TestOutcome(
                test_id=tc.test_id, result=TestResult.FAIL,
                elapsed_ms=elapsed_ms,
                detail="contactor opened (expected no reaction)",
                category=tc.category, priority=tc.priority,
            )

    elapsed_ms = (time.monotonic() - t_start) * 1000
    return TestOutcome(
        test_id=tc.test_id, result=TestResult.PASS,
        elapsed_ms=elapsed_ms, detail="no reaction as expected",
        category=tc.category, priority=tc.priority,
    )
