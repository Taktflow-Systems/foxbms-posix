"""Warning flag test runner.

Contains run_warning_flag_test which expects a DIAG bit to be set
while BMS stays in NORMAL state (no contactor open).
"""

import time
from typing import TYPE_CHECKING, List

from fi.models import TestCase, TestOutcome, TestResult
from fi.parsers import resolve_diag_bit

if TYPE_CHECKING:
    from fi.executor_base import TestExecutor


def run_warning_flag_test(executor: "TestExecutor", tc: TestCase, cmd: int,
                           indices: List[int], value: int) -> TestOutcome:
    """Run a test expecting WARNING_FLAG reaction (no contactor open)."""
    diag_bit = resolve_diag_bit(tc.diag_id, tc.severity_tier)

    t_start = time.monotonic()
    timeout_s = executor.timeout_ms / 1000.0

    executor.injector.inject_multi(cmd, indices, value)

    diag_detected = False
    t_diag = 0.0

    deadline = t_start + timeout_s
    while time.monotonic() < deadline:
        executor.injector.monitor_and_update(executor.monitor, 0.005)

        # Sustained injection
        if tc.fault_method in ("STUCK_AT_0", "STUCK_AT_MAX", "STUCK_AT_LAST",
                                "OUT_OF_RANGE_HIGH", "OUT_OF_RANGE_LOW",
                                "STEP_TO_VALUE", "INVERTED", "CONTINUOUS",
                                "OFFSET_POS", "OFFSET_NEG"):
            executor.injector.inject_multi(cmd, indices, value)

        if not diag_detected and diag_bit is not None:
            if executor.monitor.diag_bit_set(diag_bit):
                diag_detected = True
                t_diag = time.monotonic() - t_start

        # Check for unexpected contactor open / ERROR state
        if executor.monitor.bms_in_error():
            elapsed_ms = (time.monotonic() - t_start) * 1000
            return TestOutcome(
                test_id=tc.test_id, result=TestResult.FAIL,
                elapsed_ms=elapsed_ms,
                detail="BMS entered ERROR (expected WARNING only)",
                category=tc.category, priority=tc.priority,
            )

        if diag_detected:
            # Verify BMS is still NORMAL and contactors still closed
            time.sleep(0.05)
            executor.injector.monitor_and_update(executor.monitor, 0.02)
            if executor.monitor.bms_in_normal() and not executor.monitor.contactors_open():
                elapsed_ms = t_diag * 1000
                return TestOutcome(
                    test_id=tc.test_id, result=TestResult.PASS,
                    elapsed_ms=elapsed_ms,
                    detail=f"DIAG bit {diag_bit} set; BMS stays NORMAL",
                    category=tc.category, priority=tc.priority,
                )

    # Timeout — diag flag was never set
    elapsed_ms = executor.timeout_ms
    detail = f"{elapsed_ms}ms TIMEOUT | expected WARNING_FLAG, got nothing"
    if diag_bit is None:
        detail = f"{elapsed_ms}ms TIMEOUT | unknown DIAG bit for {tc.diag_id}/{tc.severity_tier}"
    return TestOutcome(
        test_id=tc.test_id, result=TestResult.FAIL,
        elapsed_ms=elapsed_ms, detail=detail,
        category=tc.category, priority=tc.priority,
    )
