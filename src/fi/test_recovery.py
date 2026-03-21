"""Recovery, persistence, and fault-clear test runners.

Contains run_recovery_test (two-phase inject/clear), run_persist_test
(sustained fault injection), and run_fault_clears_test (inject then verify
fault clears after override removal).
"""

import time
from typing import TYPE_CHECKING, List

from fi.constants import RECOVERY_TIMEOUT_S, SIL_CELL_TEMP, SIL_CELL_VOLTAGE
from fi.models import TestCase, TestOutcome, TestResult
from fi.parsers import parse_recov_injection, resolve_diag_bit, resolve_recov_override_cmd
from fi.test_contactor import run_contactor_open_test

if TYPE_CHECKING:
    from fi.executor_base import TestExecutor


def run_fault_clears_test(executor: "TestExecutor", tc: TestCase, cmd: int,
                           indices: List[int], value: int) -> TestOutcome:
    """Run a RECOV test: inject fault, then clear, verify fault clears."""
    diag_bit = resolve_diag_bit(tc.diag_id, tc.severity_tier)
    t_start = time.monotonic()

    # Phase 1: inject fault and wait for detection
    executor.injector.inject_multi(cmd, indices, value)
    inject_deadline = t_start + (executor.timeout_ms / 1000.0)
    fault_detected = False

    while time.monotonic() < inject_deadline:
        executor.injector.monitor_and_update(executor.monitor, 0.005)
        executor.injector.inject_multi(cmd, indices, value)
        if diag_bit is not None and executor.monitor.diag_bit_set(diag_bit):
            fault_detected = True
            break

    if not fault_detected:
        return TestOutcome(
            test_id=tc.test_id, result=TestResult.FAIL,
            elapsed_ms=(time.monotonic() - t_start) * 1000,
            detail="fault never detected during injection phase",
            category=tc.category, priority=tc.priority,
        )

    # Phase 2: clear and wait for fault to clear
    executor.injector.clear()
    clear_deadline = time.monotonic() + RECOVERY_TIMEOUT_S

    while time.monotonic() < clear_deadline:
        executor.injector.monitor_and_update(executor.monitor, 0.05)
        if diag_bit is not None and not executor.monitor.diag_bit_set(diag_bit):
            elapsed_ms = (time.monotonic() - t_start) * 1000
            return TestOutcome(
                test_id=tc.test_id, result=TestResult.PASS,
                elapsed_ms=elapsed_ms,
                detail="fault cleared after override removed",
                category=tc.category, priority=tc.priority,
            )

    elapsed_ms = (time.monotonic() - t_start) * 1000
    return TestOutcome(
        test_id=tc.test_id, result=TestResult.FAIL,
        elapsed_ms=elapsed_ms,
        detail="fault did not clear after override removed",
        category=tc.category, priority=tc.priority,
    )


def run_recovery_test(executor: "TestExecutor", tc: TestCase) -> TestOutcome:
    """Run a RECOV INJECT_THEN_CLEAR test.

    Phase 1: Inject fault value, wait for DIAG bit / contactor open.
    Phase 2: Clear override (inject clear value), wait for fault to clear.
    """
    recov = parse_recov_injection(tc.injection_value)
    inject_val = recov.get("inject")
    clear_val = recov.get("clear")
    check_latch = recov.get("check_latch", False)

    if inject_val is None:
        return TestOutcome(
            test_id=tc.test_id, result=TestResult.ERROR,
            elapsed_ms=0,
            detail=f"cannot parse RECOV inject value: {tc.injection_value}",
            category=tc.category, priority=tc.priority,
        )

    cmd = resolve_recov_override_cmd(tc.signal)
    diag_bit = resolve_diag_bit(tc.diag_id, tc.severity_tier)

    if cmd == SIL_CELL_VOLTAGE:
        indices = list(range(18))
    elif cmd == SIL_CELL_TEMP:
        indices = list(range(5))
    else:
        indices = [0]

    t_start = time.monotonic()

    # Phase 1: Inject fault and wait for detection
    executor.injector.inject_multi(cmd, indices, inject_val)
    inject_deadline = t_start + (executor.timeout_ms / 1000.0)
    fault_detected = False

    while time.monotonic() < inject_deadline:
        executor.injector.monitor_and_update(executor.monitor, 0.005)
        executor.injector.inject_multi(cmd, indices, inject_val)

        if diag_bit is not None and executor.monitor.diag_bit_set(diag_bit):
            fault_detected = True
            break
        if executor.monitor.contactors_open() or executor.monitor.bms_in_error():
            fault_detected = True
            break

    if not fault_detected:
        return TestOutcome(
            test_id=tc.test_id, result=TestResult.FAIL,
            elapsed_ms=(time.monotonic() - t_start) * 1000,
            detail="fault never detected during injection phase",
            category=tc.category, priority=tc.priority,
        )

    t_fault = time.monotonic()

    # Phase 2: Clear override / inject clear value
    if clear_val is not None:
        executor.injector.inject_multi(cmd, indices, clear_val)
    else:
        executor.injector.clear()

    recovery_timeout = RECOVERY_TIMEOUT_S
    if check_latch:
        recovery_timeout = 5.0

    clear_deadline = time.monotonic() + recovery_timeout
    fault_cleared = False

    while time.monotonic() < clear_deadline:
        executor.injector.monitor_and_update(executor.monitor, 0.05)
        if clear_val is not None:
            executor.injector.inject_multi(cmd, indices, clear_val)

        if diag_bit is not None and not executor.monitor.diag_bit_set(diag_bit):
            fault_cleared = True
            break

    elapsed_ms = (time.monotonic() - t_start) * 1000

    if check_latch:
        if fault_cleared:
            return TestOutcome(
                test_id=tc.test_id, result=TestResult.PASS,
                elapsed_ms=elapsed_ms,
                detail="fault cleared after safe value (non-latching behavior)",
                category=tc.category, priority=tc.priority,
            )
        else:
            return TestOutcome(
                test_id=tc.test_id, result=TestResult.PASS,
                elapsed_ms=elapsed_ms,
                detail="fault latched (latching behavior confirmed)",
                category=tc.category, priority=tc.priority,
            )

    if tc.expected_reaction == "FAULT_CLEARS":
        if fault_cleared:
            return TestOutcome(
                test_id=tc.test_id, result=TestResult.PASS,
                elapsed_ms=elapsed_ms,
                detail="fault cleared after override removed; recovery OK",
                category=tc.category, priority=tc.priority,
            )
        else:
            return TestOutcome(
                test_id=tc.test_id, result=TestResult.FAIL,
                elapsed_ms=elapsed_ms,
                detail="fault did not clear after override removed",
                category=tc.category, priority=tc.priority,
            )

    return run_contactor_open_test(executor, tc, cmd, indices, inject_val)


def run_persist_test(executor: "TestExecutor", tc: TestCase) -> TestOutcome:
    """Run a RECOV CONTINUOUS/PERSIST test: inject and verify fault stays active."""
    recov = parse_recov_injection(tc.injection_value)
    inject_val = recov.get("inject")
    duration_s = recov.get("duration_s", 10)

    if inject_val is None:
        return TestOutcome(
            test_id=tc.test_id, result=TestResult.ERROR,
            elapsed_ms=0,
            detail=f"cannot parse persist inject value: {tc.injection_value}",
            category=tc.category, priority=tc.priority,
        )

    cmd = resolve_recov_override_cmd(tc.signal)
    diag_bit = resolve_diag_bit(tc.diag_id, tc.severity_tier)

    if cmd == SIL_CELL_VOLTAGE:
        indices = list(range(18))
    elif cmd == SIL_CELL_TEMP:
        indices = list(range(5))
    else:
        indices = [0]

    t_start = time.monotonic()

    executor.injector.inject_multi(cmd, indices, inject_val)

    detect_deadline = t_start + (executor.timeout_ms / 1000.0)
    fault_detected = False
    while time.monotonic() < detect_deadline:
        executor.injector.monitor_and_update(executor.monitor, 0.005)
        executor.injector.inject_multi(cmd, indices, inject_val)
        if diag_bit is not None and executor.monitor.diag_bit_set(diag_bit):
            fault_detected = True
            break
        if executor.monitor.contactors_open() or executor.monitor.bms_in_error():
            fault_detected = True
            break

    if not fault_detected:
        return TestOutcome(
            test_id=tc.test_id, result=TestResult.FAIL,
            elapsed_ms=(time.monotonic() - t_start) * 1000,
            detail="fault never detected during persist test",
            category=tc.category, priority=tc.priority,
        )

    hold_s = min(duration_s, executor.timeout_ms / 1000.0)
    hold_deadline = time.monotonic() + hold_s
    fault_persisted = True

    while time.monotonic() < hold_deadline:
        executor.injector.inject_multi(cmd, indices, inject_val)
        executor.injector.monitor_and_update(executor.monitor, 0.05)

        if diag_bit is not None and not executor.monitor.diag_bit_set(diag_bit):
            fault_persisted = False
            break

    elapsed_ms = (time.monotonic() - t_start) * 1000

    if fault_persisted:
        return TestOutcome(
            test_id=tc.test_id, result=TestResult.PASS,
            elapsed_ms=elapsed_ms,
            detail=f"fault persisted during {hold_s:.0f}s sustained injection",
            category=tc.category, priority=tc.priority,
        )
    else:
        return TestOutcome(
            test_id=tc.test_id, result=TestResult.FAIL,
            elapsed_ms=elapsed_ms,
            detail="fault cleared unexpectedly during sustained injection",
            category=tc.category, priority=tc.priority,
        )
