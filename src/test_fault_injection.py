#!/usr/bin/env python3
"""
foxBMS POSIX vECU — ASIL-D Fault Injection Test Runner

Executes fault injection tests from the CSV matrix against a running
foxbms-vecu + plant_model.py on a SocketCAN interface.

Usage:
    python3 test_fault_injection.py vcan1
    python3 test_fault_injection.py vcan1 --filter FI-VOLT-0001
    python3 test_fault_injection.py vcan1 --category VOLT --priority P1 --quick
    python3 test_fault_injection.py vcan1 --max 10 --report results.txt
"""
# @verifies SW-REQ-001
# @verifies SW-REQ-002
# @verifies SW-REQ-010
# @verifies SW-REQ-020
# @verifies SW-REQ-030
# @verifies SW-REQ-043
# @verifies SW-REQ-044
# @verifies SSR-001
# @verifies SSR-002
# @verifies SSR-005
# @verifies SSR-007
# @verifies SSR-010
# @verifies SW-REQ-201

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fi.can_bus import CanBus
from fi.constants import (
    BMS_STATE_NAMES,
    DEFAULT_TIMEOUT_MS,
    STARTUP_TIMEOUT_S,
)
from fi.executor_base import TestExecutor
from fi.injector import FaultInjector
from fi.models import TestOutcome, TestResult
from fi.parsers import filter_tests, load_test_cases
from fi.probe_monitor import ProbeMonitor
from fi.report import generate_audit_report
from fi.vecu_manager import VecuManager


def main() -> int:
    parser = argparse.ArgumentParser(
        description="foxBMS POSIX vECU — ASIL-D Fault Injection Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("can_interface", help="SocketCAN interface (e.g., vcan1)")
    parser.add_argument("--csv", default=None,
                        help="Path to CSV matrix (default: auto-detect)")
    parser.add_argument("--filter", default=None,
                        help="Only run tests matching pattern")
    parser.add_argument("--category", default=None,
                        help="Only run tests in category (VOLT, TEMP, CURR, etc.)")
    parser.add_argument("--priority", default=None,
                        help="Only run P1 or P2 tests")
    parser.add_argument("--max", type=int, default=0,
                        help="Run at most N tests")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_MS,
                        help="Per-test timeout in ms (default: 5000)")
    parser.add_argument("--report",
                        default=f"fault-injection-report-{datetime.now().strftime('%Y%m%d')}.txt",
                        help="Output report file (default: fault-injection-report-<date>.txt)")
    parser.add_argument("--quick", action="store_true",
                        help="Run only P1 STEP_TO_VALUE tests (fastest subset)")
    parser.add_argument("--vecu", default=None,
                        help="Path to foxbms-vecu binary (default: auto-detect)")
    parser.add_argument("--plant", default=None,
                        help="Path to plant_model.py (default: auto-detect)")
    parser.add_argument("--no-start", action="store_true",
                        help="Do not start vECU/plant (assume already running)")
    args = parser.parse_args()

    # Resolve paths
    script_dir = Path(__file__).parent.resolve()

    if args.csv is None:
        args.csv = str(script_dir.parent / "docs" / "fault-injection-test-matrix-asild.csv")

    if args.vecu is None:
        args.vecu = str(script_dir / "foxbms-vecu")

    if args.plant is None:
        args.plant = str(script_dir / "plant_model.py")

    # Validate CSV exists
    if not Path(args.csv).is_file():
        print(f"[ERROR] CSV not found: {args.csv}")
        return 1

    # Load and filter test cases
    print(f"[runner] Loading test matrix: {args.csv}")
    all_cases = load_test_cases(args.csv)
    print(f"[runner] Loaded {len(all_cases)} test cases")

    cases = filter_tests(all_cases, args)
    print(f"[runner] After filtering: {len(cases)} test cases to run")

    if not cases:
        print("[runner] No test cases match the filter criteria.")
        return 0

    # Start vECU + plant (unless --no-start)
    vecu_mgr: Optional[VecuManager] = None
    if not args.no_start:
        if not Path(args.vecu).is_file():
            print(f"[ERROR] vECU binary not found: {args.vecu}")
            print("[HINT]  Build with: cd src && make -j4")
            return 1
        if not Path(args.plant).is_file():
            print(f"[ERROR] plant_model.py not found: {args.plant}")
            return 1

        vecu_mgr = VecuManager(args.can_interface, args.vecu, args.plant)
        if not vecu_mgr.start():
            print("[ERROR] Failed to start vECU + plant model")
            return 1

    # Open CAN bus
    try:
        bus = CanBus(args.can_interface)
    except OSError as e:
        print(f"[ERROR] Cannot open CAN interface {args.can_interface}: {e}")
        if vecu_mgr:
            vecu_mgr.stop()
        return 1

    monitor = ProbeMonitor()
    injector = FaultInjector(bus)
    executor = TestExecutor(bus, injector, monitor, args.timeout)

    # Initial precondition verification
    print(f"[runner] Verifying initial preconditions (up to {STARTUP_TIMEOUT_S}s)...")
    precond_ok, precond_detail = executor.verify_preconditions(timeout_s=STARTUP_TIMEOUT_S)
    if not precond_ok:
        print(f"[ERROR] Initial preconditions not met: {precond_detail}")
        print(f"[DEBUG] Last BMS state: {BMS_STATE_NAMES.get(monitor.bms_state, '?')} "
              f"({monitor.bms_state})")
        bus.close()
        if vecu_mgr:
            vecu_mgr.stop()
        return 1

    print(f"[runner] {precond_detail}")
    print(f"[runner] Starting test execution")
    print(f"[runner] Per-test timeout: {args.timeout}ms")
    print("")

    # Execute tests
    start_time = datetime.now(timezone.utc)
    outcomes: List[TestOutcome] = []
    restart_count = 0
    precond_checks_total = 0
    precond_checks_passed = 0
    precond_checks_failed = 0

    for i, tc in enumerate(cases):
        progress = f"[{i+1}/{len(cases)}]"

        # Full 6-point precondition verification before each test
        precond_checks_total += 1
        precond_ok, precond_detail = executor.verify_preconditions(timeout_s=15.0)

        if not precond_ok:
            precond_checks_failed += 1
            print(f"{progress} Preconditions failed: {precond_detail}")

            # Attempt 1: clear overrides and retry
            injector.clear()
            time.sleep(0.2)
            precond_ok, precond_detail = executor.verify_preconditions(timeout_s=15.0)

            if not precond_ok and vecu_mgr:
                # Attempt 2: restart vECU
                restart_attempts = 0
                while not precond_ok and restart_attempts < 2:
                    restart_attempts += 1
                    print(f"{progress} Restart attempt {restart_attempts}/2...")
                    if vecu_mgr.is_alive():
                        vecu_mgr.restart()
                    else:
                        print(f"{progress} [ERROR] vECU crashed — restarting")
                        vecu_mgr.restart()
                    bus.close()
                    bus = CanBus(args.can_interface)
                    injector = FaultInjector(bus)
                    executor = TestExecutor(bus, injector, monitor, args.timeout)
                    restart_count += 1
                    precond_ok, precond_detail = executor.verify_preconditions(
                        timeout_s=STARTUP_TIMEOUT_S)

            if not precond_ok:
                print(f"{progress} [SKIP] {tc.test_id} — preconditions failed after 2 restarts")
                outcomes.append(TestOutcome(
                    test_id=tc.test_id, result=TestResult.SKIP,
                    elapsed_ms=0,
                    detail=f"preconditions failed: {precond_detail}",
                    category=tc.category, priority=tc.priority,
                    precondition_detail=precond_detail,
                    skip_reason=f"preconditions failed: {precond_detail}",
                    signal=tc.signal, fault_method=tc.fault_method,
                    target=tc.target, injection_value=tc.injection_value,
                    expected_reaction=tc.expected_reaction,
                    severity_tier=tc.severity_tier,
                ))
                continue

        precond_checks_passed += 1

        # Run the test
        outcome = executor.execute(tc, precondition_detail=precond_detail)
        outcomes.append(outcome)

        # Print result line
        short_desc = f"{tc.signal} {tc.fault_method} {tc.target}"
        if len(short_desc) > 40:
            short_desc = short_desc[:37] + "..."
        print(f"{progress} [{outcome.result:4s}] {tc.test_id:20s} | "
              f"{short_desc:40s} | {outcome.elapsed_ms:.0f}ms | {outcome.detail}")

        # Clear overrides after each test
        injector.clear()

        # Brief settle time between tests
        if outcome.result in (TestResult.PASS, TestResult.FAIL):
            if tc.expected_reaction in ("CONTACTOR_OPEN", "CONTACTOR_OPEN_LATCHED",
                                         "ERROR_FLAG"):
                time.sleep(0.2)
                bus.drain()
                injector.monitor_and_update(monitor, 0.1)
            else:
                time.sleep(0.05)

    end_time = datetime.now(timezone.utc)

    # Generate ASPICE-auditable report (both .txt and .json)
    report_base = args.report
    if report_base.endswith(".txt"):
        report_base = report_base[:-4]
    txt_path = f"{report_base}.txt"
    json_path = f"{report_base}.json"

    generate_audit_report(
        outcomes=outcomes,
        txt_path=txt_path,
        json_path=json_path,
        start_time=start_time,
        end_time=end_time,
        can_interface=args.can_interface,
        csv_path=args.csv,
        vecu_path=args.vecu if not args.no_start else None,
        plant_path=args.plant if not args.no_start else None,
        restart_count=restart_count,
        precond_stats=(precond_checks_total, precond_checks_passed, precond_checks_failed),
    )

    if restart_count > 0:
        print(f"\n[runner] vECU was restarted {restart_count} time(s) during test run")

    # Cleanup
    bus.close()
    if vecu_mgr:
        vecu_mgr.stop()

    # Exit code: 0 if no failures, 1 if any failures
    fail_count = sum(1 for o in outcomes if o.result == TestResult.FAIL)
    error_count = sum(1 for o in outcomes if o.result == TestResult.ERROR)
    return 1 if (fail_count > 0 or error_count > 0) else 0


if __name__ == "__main__":
    sys.exit(main())
