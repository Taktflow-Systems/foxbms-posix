#!/usr/bin/env python3
"""
foxBMS POSIX vECU — Regression Trend Analyzer

Reads JUnit XML test results from multiple runs and identifies flaky tests,
regressions, and pass-rate trends.
Adapted from mebms-classic tools/trend-analyze.py for foxBMS test suite.

Usage:
    python trend-analyze.py results/        Analyze all XML files in directory
    python trend-analyze.py --demo          Run with synthetic foxBMS test history
"""
import argparse
import sys
import os
import glob
from datetime import datetime, timedelta
from xml.etree import ElementTree as ET
from collections import defaultdict


def parse_junit_xml(filepath):
    """Parse JUnit XML. Returns list of {name, classname, status, duration}."""
    tree = ET.parse(filepath)
    root = tree.getroot()
    results = []

    suites = root.findall("testsuite") if root.tag == "testsuites" else [root] if root.tag == "testsuite" else []

    for suite in suites:
        suite_name = suite.get("name", "unknown")
        for tc in suite.findall("testcase"):
            name = tc.get("name", "unknown")
            classname = tc.get("classname", suite_name)
            duration = float(tc.get("time", "0"))
            status = "pass"
            if tc.find("failure") is not None:
                status = "fail"
            elif tc.find("error") is not None:
                status = "error"
            elif tc.find("skipped") is not None:
                status = "skip"
            results.append({
                "name": name,
                "classname": classname,
                "status": status,
                "duration": duration,
                "fqn": f"{classname}::{name}",
            })
    return results


def load_runs(directory):
    """Load all JUnit XML files from a directory as separate runs."""
    xml_files = sorted(glob.glob(os.path.join(directory, "*.xml")))
    if not xml_files:
        xml_files = sorted(glob.glob(os.path.join(directory, "**/*.xml"), recursive=True))

    runs = []
    for xf in xml_files:
        try:
            results = parse_junit_xml(xf)
        except Exception as e:
            print(f"  Warning: skipping {xf}: {e}")
            continue
        mtime = os.path.getmtime(xf)
        run_date = datetime.fromtimestamp(mtime)
        runs.append((os.path.basename(xf), run_date, results))

    runs.sort(key=lambda x: x[1])
    return runs


def analyze_trends(runs):
    """Analyze test trends across runs."""
    test_history = defaultdict(list)
    run_summaries = []

    for idx, (name, date, results) in enumerate(runs):
        passed = sum(1 for r in results if r["status"] == "pass")
        failed = sum(1 for r in results if r["status"] in ("fail", "error"))
        skipped = sum(1 for r in results if r["status"] == "skip")
        total = len(results)
        run_summaries.append({
            "name": name,
            "date": date,
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "pass_rate": (passed / total * 100) if total > 0 else 0,
        })
        for r in results:
            test_history[r["fqn"]].append((idx, r["status"]))

    # Flaky tests
    flaky_tests = []
    for fqn, history in test_history.items():
        if len(history) < 2:
            continue
        statuses = [s for _, s in history if s != "skip"]
        if not statuses:
            continue
        unique = set(statuses)
        if len(unique) > 1:
            pass_count = statuses.count("pass")
            total_count = len(statuses)
            flaky_tests.append({
                "fqn": fqn,
                "pass_rate": pass_count / total_count * 100,
                "runs": total_count,
                "history": [(runs[idx][0], s) for idx, s in history],
            })
    flaky_tests.sort(key=lambda x: x["pass_rate"])

    # New failures / passes
    new_failures = []
    new_passes = []
    if len(runs) >= 2:
        last_results = {r["fqn"]: r["status"] for r in runs[-1][2]}
        prev_results = {r["fqn"]: r["status"] for r in runs[-2][2]}
        for fqn, status in last_results.items():
            prev_status = prev_results.get(fqn)
            if prev_status == "pass" and status in ("fail", "error"):
                new_failures.append(fqn)
            elif prev_status in ("fail", "error") and status == "pass":
                new_passes.append(fqn)

    return test_history, flaky_tests, new_failures, new_passes, run_summaries


def print_report(test_history, flaky_tests, new_failures, new_passes, run_summaries):
    """Print trend analysis report."""
    print("\n" + "=" * 78)
    print("  REGRESSION TREND ANALYSIS — foxBMS POSIX vECU")
    print("=" * 78)

    # Run summary
    print(f"\nRUN HISTORY ({len(run_summaries)} runs):")
    print("-" * 78)
    print(f"  {'Run':<30s} {'Date':<18s} {'Total':>5s} {'Pass':>5s} {'Fail':>5s} {'Skip':>5s} {'Rate':>7s}")
    print("-" * 78)
    for rs in run_summaries:
        print(f"  {rs['name']:<30s} {rs['date'].strftime('%Y-%m-%d %H:%M'):<18s} "
              f"{rs['total']:5d} {rs['passed']:5d} {rs['failed']:5d} {rs['skipped']:5d} "
              f"{rs['pass_rate']:6.1f}%")

    if len(run_summaries) >= 2:
        first_rate = run_summaries[0]["pass_rate"]
        last_rate = run_summaries[-1]["pass_rate"]
        diff = last_rate - first_rate
        arrow = "^" if diff > 0 else "v" if diff < 0 else "="
        print(f"\n  Trend: {first_rate:.1f}% -> {last_rate:.1f}% ({arrow} {abs(diff):.1f}pp)")

    # New failures
    if new_failures:
        print(f"\nNEW FAILURES (vs previous run): {len(new_failures)}")
        print("-" * 78)
        for fqn in sorted(new_failures):
            print(f"  REGRESSION  {fqn}")
    else:
        print(f"\n  No new failures vs previous run.")

    # New passes
    if new_passes:
        print(f"\nNEWLY PASSING (vs previous run): {len(new_passes)}")
        print("-" * 78)
        for fqn in sorted(new_passes):
            print(f"  FIXED  {fqn}")

    # Flaky tests
    if flaky_tests:
        print(f"\nFLAKY TESTS (inconsistent across runs): {len(flaky_tests)}")
        print("-" * 78)
        print(f"  {'Test':<50s} {'Rate':>7s} {'Runs':>5s} {'History'}")
        print("-" * 78)
        for ft in flaky_tests:
            short_name = ft["fqn"]
            if len(short_name) > 50:
                short_name = "..." + short_name[-47:]
            hist_str = " ".join("P" if s == "pass" else "F" if s in ("fail", "error") else "S"
                                for _, s in ft["history"])
            print(f"  {short_name:<50s} {ft['pass_rate']:6.1f}% {ft['runs']:5d}  [{hist_str}]")
    else:
        print(f"\n  No flaky tests detected.")

    # Per-test pass rate (non-100% only)
    print(f"\nTEST PASS RATES (non-100% only):")
    print("-" * 78)
    rate_list = []
    for fqn, history in test_history.items():
        statuses = [s for _, s in history if s != "skip"]
        if not statuses:
            continue
        pass_count = statuses.count("pass")
        rate = pass_count / len(statuses) * 100
        if rate < 100.0:
            rate_list.append((fqn, rate, len(statuses)))
    rate_list.sort(key=lambda x: x[1])
    if rate_list:
        for fqn, rate, count in rate_list:
            short = fqn if len(fqn) <= 55 else "..." + fqn[-52:]
            print(f"  {short:<55s} {rate:6.1f}% ({count} runs)")
    else:
        print("  All tests pass at 100%!")

    # Verdict
    print()
    print("=" * 78)
    if new_failures:
        print(f"  WARNING: {len(new_failures)} new regression(s) detected")
    elif flaky_tests:
        print(f"  CAUTION: {len(flaky_tests)} flaky test(s) - investigate for stability")
    else:
        print(f"  OK: No regressions or flaky tests")
    print("=" * 78)

    return len(new_failures)


def generate_demo():
    """Generate synthetic test history matching foxBMS POSIX test suite."""
    import random
    random.seed(42)

    # foxBMS-specific test names (matches actual test_*.py files)
    test_names = [
        # test_smoke.py
        ("TestSmoke", "test_bms_reaches_normal"),
        ("TestSmoke", "test_can_tx_active"),
        ("TestSmoke", "test_soc_broadcast"),
        # test_fault_injection.py
        ("TestFaultInjection", "test_overvoltage_detection"),
        ("TestFaultInjection", "test_overcurrent_detection"),
        ("TestFaultInjection", "test_overtemperature_detection"),
        ("TestFaultInjection", "test_undervoltage_detection"),
        ("TestFaultInjection", "test_contactor_open_on_fault"),
        ("TestFaultInjection", "test_recovery_after_fault_clear"),
        # test_asil.py
        ("TestASIL", "test_overvoltage_msl_contactor_open"),
        ("TestASIL", "test_overcurrent_msl_contactor_open"),
        ("TestASIL", "test_overtemp_msl_contactor_open"),
        ("TestASIL", "test_deep_discharge_protection"),
        ("TestASIL", "test_interlock_check"),
        # test_state_machine.py
        ("TestStateMachine", "test_init_to_idle"),
        ("TestStateMachine", "test_idle_to_standby"),
        ("TestStateMachine", "test_precharge_sequence"),
        ("TestStateMachine", "test_precharge_to_normal"),
        ("TestStateMachine", "test_normal_to_error"),
        ("TestStateMachine", "test_error_recovery"),
        # test_can_signals.py
        ("TestCAN", "test_0x220_bms_state"),
        ("TestCAN", "test_0x233_pack_values"),
        ("TestCAN", "test_0x235_soc_broadcast"),
        ("TestCAN", "test_0x270_cell_voltage_encoding"),
        ("TestCAN", "test_0x280_cell_temp_encoding"),
        # test_sil_probes.py
        ("TestSILProbes", "test_contactor_probe"),
        ("TestSILProbes", "test_soc_probe"),
        ("TestSILProbes", "test_heartbeat_probe"),
        # test_integration.py
        ("TestIntegration", "test_plant_to_vecu_data_flow"),
        ("TestIntegration", "test_closed_loop_soc"),
        # ML sidecar tests (future)
        ("TestMLSidecar", "test_sidecar_starts"),
        ("TestMLSidecar", "test_anomaly_score_published"),
    ]

    # Profiles: most pass, some flaky (timing-sensitive), one new failure
    flaky = {"test_precharge_sequence", "test_closed_loop_soc", "test_overcurrent_detection"}
    newly_failing = {"test_recovery_after_fault_clear"}

    runs = []
    base_date = datetime(2026, 3, 10, 10, 0, 0)
    for run_idx in range(8):
        run_date = base_date + timedelta(days=run_idx * 2)
        run_name = f"foxbms_{run_date.strftime('%Y-%m-%d')}.xml"
        results = []
        for classname, name in test_names:
            fqn = f"{classname}::{name}"
            if name in flaky:
                status = "pass" if random.random() > 0.35 else "fail"
            elif name in newly_failing and run_idx >= 6:
                status = "fail"
            elif name == "test_sidecar_starts" and run_idx < 4:
                status = "skip"  # ML sidecar not available in early runs
            else:
                status = "pass"
            results.append({
                "name": name,
                "classname": classname,
                "status": status,
                "duration": random.uniform(0.1, 15.0),
                "fqn": fqn,
            })
        runs.append((run_name, run_date, results))

    return runs


def main():
    parser = argparse.ArgumentParser(
        description="Regression Trend Analyzer — foxBMS POSIX vECU",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python trend-analyze.py results/           Analyze all XML files in directory
  python trend-analyze.py --demo             Run with synthetic foxBMS test history

Identifies:
  - Flaky tests (pass rate < 100%% over multiple runs)
  - Newly failing tests (regression from previous run)
  - Newly passing tests (fixed since previous run)
  - Per-test pass rate trends

foxBMS test suites supported:
  test_smoke.py, test_fault_injection.py, test_asil.py, test_state_machine.py,
  test_can_signals.py, test_sil_probes.py, test_integration.py
""")
    parser.add_argument("directory", nargs="?", help="Directory containing JUnit XML result files")
    parser.add_argument("--demo", action="store_true", help="Run with synthetic foxBMS demo data")
    args = parser.parse_args()

    if args.demo:
        print("Generating synthetic foxBMS test history (8 runs, 32 tests)...\n")
        runs = generate_demo()
    elif args.directory:
        if not os.path.isdir(args.directory):
            print(f"ERROR: {args.directory} is not a directory")
            sys.exit(1)
        runs = load_runs(args.directory)
        if not runs:
            print(f"ERROR: No JUnit XML files found in {args.directory}")
            sys.exit(1)
        print(f"Loaded {len(runs)} test runs from {args.directory}")
    else:
        parser.print_help()
        sys.exit(1)

    test_history, flaky, new_failures, new_passes, summaries = analyze_trends(runs)
    regressions = print_report(test_history, flaky, new_failures, new_passes, summaries)
    sys.exit(1 if regressions > 0 else 0)


if __name__ == "__main__":
    main()
