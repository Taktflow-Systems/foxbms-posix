"""ASPICE CL2-auditable test report generation (text format).

Generates the .txt format fault injection test report with summary
statistics, per-category breakdowns, detection time analysis, and
individual test details. Delegates JSON report to report_json module.
"""

import hashlib
import platform
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fi.models import TestOutcome, TestResult
from fi.report_json import build_json_report, write_json_report


def _sha256_file(path: Optional[str]) -> str:
    """Return SHA256 hex digest of a file, or 'N/A' if not available."""
    if path is None or not Path(path).is_file():
        return "N/A"
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _compute_detection_stats(outcomes: List[TestOutcome]) -> Dict[str, Dict[str, Any]]:
    """Compute detection time statistics grouped by fault type category."""
    category_meta = {
        "VOLT": ("Overvoltage/Undervoltage", "50ev+200ms"),
        "TEMP": ("Overtemperature/Undertemperature", "500ev+1s"),
        "CURR": ("Overcurrent", "10ev+100ms"),
        "PLAUS": ("Plausibility", "varies"),
        "COMBO": ("Combined faults", "varies"),
        "RECOV": ("Recovery", "varies"),
    }
    stats: Dict[str, Dict[str, Any]] = {}
    for o in outcomes:
        if o.result != TestResult.PASS or o.elapsed_ms <= 0:
            continue
        cat = o.category or "OTHER"
        if cat not in stats:
            meta = category_meta.get(cat, (cat, "N/A"))
            stats[cat] = {"name": meta[0], "threshold": meta[1],
                          "times": [], "diag_times": [], "contactor_times": []}
        stats[cat]["times"].append(o.elapsed_ms)
        if o.diag_time_ms > 0:
            stats[cat]["diag_times"].append(o.diag_time_ms)
        if o.contactor_time_ms > 0:
            stats[cat]["contactor_times"].append(o.contactor_time_ms)

    result = {}
    for cat, s in stats.items():
        times = s["times"]
        result[cat] = {
            "name": s["name"], "threshold": s["threshold"],
            "min_ms": min(times) if times else 0,
            "max_ms": max(times) if times else 0,
            "avg_ms": sum(times) / len(times) if times else 0,
            "count": len(times),
        }
    return result


def _classify_aspice_level(tc_outcome: TestOutcome) -> str:
    """Classify a test into ASPICE test level (SWE.5 or SWE.6)."""
    return "SWE.6" if tc_outcome.category in ("COMBO", "PLAUS") else "SWE.5"


def format_result_line(outcome: TestOutcome) -> str:
    """Format a single test result as a printable line."""
    return f"[{outcome.result}]{' '*(4-len(outcome.result))} {outcome.test_id:20s} | {outcome.detail}"


def generate_audit_report(
    outcomes: List[TestOutcome], txt_path: str, json_path: str,
    start_time: datetime, end_time: datetime, can_interface: str,
    csv_path: str, vecu_path: Optional[str] = None,
    plant_path: Optional[str] = None, restart_count: int = 0,
    precond_stats: Tuple[int, int, int] = (0, 0, 0),
) -> None:
    """Generate ASPICE CL2-auditable test report in .txt and .json formats."""
    total = len(outcomes)
    pass_count = sum(1 for o in outcomes if o.result == TestResult.PASS)
    fail_count = sum(1 for o in outcomes if o.result == TestResult.FAIL)
    skip_count = sum(1 for o in outcomes if o.result == TestResult.SKIP)
    error_count = sum(1 for o in outcomes if o.result == TestResult.ERROR)
    runnable = total - skip_count
    pass_rate = (pass_count / runnable * 100) if runnable > 0 else 0.0
    duration = end_time - start_time
    duration_str = str(duration).split(".")[0]
    overall = "PASS" if fail_count == 0 and error_count == 0 else (
        "INCOMPLETE" if error_count > 0 else "FAIL")

    category_stats: Dict[str, Dict[str, int]] = {}
    for o in outcomes:
        cat = o.category or "??"
        if cat not in category_stats:
            category_stats[cat] = {"total": 0, "PASS": 0, "FAIL": 0, "SKIP": 0, "ERROR": 0}
        category_stats[cat]["total"] += 1
        category_stats[cat][o.result] += 1

    level_stats: Dict[str, Dict[str, int]] = {}
    for o in outcomes:
        level = _classify_aspice_level(o)
        if level not in level_stats:
            level_stats[level] = {"total": 0, "PASS": 0, "FAIL": 0, "SKIP": 0, "ERROR": 0}
        level_stats[level]["total"] += 1
        level_stats[level][o.result] += 1

    det_stats = _compute_detection_stats(outcomes)
    vecu_hash = _sha256_file(vecu_path)
    plant_hash = _sha256_file(plant_path) if plant_path else "N/A"
    csv_basename = Path(csv_path).name if csv_path else "N/A"
    csv_total = 0
    if csv_path and Path(csv_path).is_file():
        with open(csv_path, "r") as f:
            csv_total = sum(1 for line in f) - 1
    precond_total, precond_passed, precond_failed = precond_stats

    # --- TEXT REPORT ---
    lines = _build_text_report(
        outcomes, overall, total, pass_count, fail_count, skip_count, error_count,
        pass_rate, duration_str, start_time, can_interface, csv_basename, csv_total,
        vecu_hash, plant_hash, category_stats, level_stats, det_stats,
        precond_total, precond_passed, precond_failed, restart_count)
    with open(txt_path, "w") as f:
        f.write("\n".join(lines) + "\n")

    # --- JSON REPORT ---
    json_report = build_json_report(
        outcomes, overall, total, pass_count, fail_count, skip_count, error_count,
        pass_rate, start_time, duration.total_seconds(), can_interface, csv_basename,
        csv_total, vecu_hash, plant_hash, category_stats, level_stats, det_stats,
        precond_stats, restart_count)
    write_json_report(json_report, json_path)

    # --- STDOUT SUMMARY ---
    print(f"\n{'='*60}")
    print(f"=== Fault Injection Report — OVERALL: {overall} ===")
    print(f"Total: {total} | PASS: {pass_count} | FAIL: {fail_count} "
          f"| SKIP: {skip_count} | ERROR: {error_count}")
    print(f"Pass Rate (runnable): {pass_rate:.1f}%")
    print(f"Preconditions: {precond_total} checks, {precond_passed} passed, "
          f"{precond_failed} failed, {restart_count} restarts")
    for cat in sorted(category_stats.keys()):
        s = category_stats[cat]
        r = s["total"] - s["SKIP"]
        print(f"  {cat:8s}: {s['PASS']}/{r} ({s['PASS']/r*100 if r else 0:.0f}%)")
    print(f"\nText report:  {txt_path}\nJSON report:  {json_path}")
    print("=" * 60)


def _build_text_report(outcomes, overall, total, pass_count, fail_count,
                        skip_count, error_count, pass_rate, duration_str,
                        start_time, can_interface, csv_basename, csv_total,
                        vecu_hash, plant_hash, category_stats, level_stats,
                        det_stats, precond_total, precond_passed,
                        precond_failed, restart_count) -> List[str]:
    """Build text report lines."""
    L = []  # noqa: N806
    L += ["=" * 79, "FAULT INJECTION TEST REPORT", "=" * 79]
    L.append(f"Project:        foxBMS POSIX vECU (SIL)")
    L.append(f"Test Level:     SWE.5 (SW Integration Test)")
    L.append(f"Platform:       {platform.system()} {platform.machine()} (POSIX cooperative mode)")
    L.append(f"foxBMS Version: v1.10.0")
    L.append(f"Test Matrix:    {csv_basename} ({csv_total:,} test cases)")
    L.append(f"Date:           {start_time.isoformat()}")
    L.append(f"Duration:       {duration_str}")
    L.append(f"Tester:         automated (test_fault_injection.py)")
    L.append(f"Environment:    {can_interface}, plant_model.py")
    L += ["=" * 79, "", f"OVERALL RESULT: {overall}", ""]
    pct = lambda n: f"{n} ({n*100//total if total else 0}%)"  # noqa: E731
    L.append(f"| {'Metric':<21s} | {'Value':>8s} |")
    L.append(f"|{'-'*22}|{'-'*10}|")
    for label, val in [("Total Executed", f"{total}"), ("PASS", pct(pass_count)),
                        ("FAIL", pct(fail_count)), ("SKIP", pct(skip_count)),
                        ("ERROR", pct(error_count)),
                        ("Pass Rate (runnable)", f"{pass_rate:.1f}%")]:
        L.append(f"| {label:<21s} | {val:>8s} |")
    L += ["", "PRECONDITION VERIFICATION"]
    L.append(f"Precondition checks: {precond_total} performed, {precond_passed} passed, "
             f"{precond_failed} failed ({restart_count} restarts)")
    L += ["", "RESULTS BY CATEGORY"]
    L.append(f"| {'Category':<10s} | {'Total':>5s} | {'PASS':>5s} | {'FAIL':>5s} "
             f"| {'SKIP':>5s} | {'ERROR':>5s} | {'Pass Rate':>9s} |")
    L.append(f"|{'-'*11}|{'-'*7}|{'-'*7}|{'-'*7}|{'-'*7}|{'-'*7}|{'-'*11}|")
    for cat in sorted(category_stats.keys()):
        s = category_stats[cat]
        r = s["total"] - s["SKIP"]
        cr = (s["PASS"] / r * 100) if r > 0 else 0.0
        L.append(f"| {cat:<10s} | {s['total']:>5d} | {s['PASS']:>5d} | {s['FAIL']:>5d} "
                 f"| {s['SKIP']:>5d} | {s['ERROR']:>5d} | {cr:>8.1f}% |")
    L += ["", "RESULTS BY TEST LEVEL (ASPICE)"]
    L.append(f"| {'Level':<7s} | {'Total':>5s} | {'PASS':>5s} | {'FAIL':>5s} | {'SKIP':>5s} |")
    L.append(f"|{'-'*8}|{'-'*7}|{'-'*7}|{'-'*7}|{'-'*7}|")
    for level in sorted(level_stats.keys()):
        s = level_stats[level]
        L.append(f"| {level:<7s} | {s['total']:>5d} | {s['PASS']:>5d} "
                 f"| {s['FAIL']:>5d} | {s['SKIP']:>5d} |")
    L.append("")
    if det_stats:
        L.append("DETECTION TIME STATISTICS")
        L.append(f"| {'Fault Type':<16s} | {'Min (ms)':>8s} | {'Max (ms)':>8s} "
                 f"| {'Avg (ms)':>8s} | {'Threshold':<15s} |")
        L.append(f"|{'-'*17}|{'-'*10}|{'-'*10}|{'-'*10}|{'-'*16}|")
        for cat in sorted(det_stats.keys()):
            d = det_stats[cat]
            L.append(f"| {d['name']:<16s} | {d['min_ms']:>8.0f} | {d['max_ms']:>8.0f} "
                     f"| {d['avg_ms']:>8.0f} | {d['threshold']:<15s} |")
        L.append("")
    L.append("INDIVIDUAL TEST RESULTS")
    for o in outcomes:
        L += ["-" * 78, f"TEST: {o.test_id}",
              f"  Category: {o.category}  Signal: {o.signal}  Method: {o.fault_method}",
              f"  Target: {o.target}  Injection: {o.injection_value}  Expected: {o.expected_reaction}"]
        if o.precondition_detail:
            L.append(f"  Preconditions: {o.precondition_detail}")
        L.append(f"  RESULT: {o.result}  Elapsed: {o.elapsed_ms:.0f}ms")
        if o.diag_time_ms > 0:
            L.append(f"  DIAG bit: SET at {o.diag_time_ms:.0f}ms")
        if o.bms_state_trace:
            L.append(f"  BMS state: {o.bms_state_trace}")
        if o.contactor_time_ms > 0:
            L.append(f"  Contactor: CLOSED -> OPEN at {o.contactor_time_ms:.0f}ms")
        L.append(f"  Detail: {o.detail}")
    L += ["-" * 78, ""]
    failures = [o for o in outcomes if o.result == TestResult.FAIL]
    if failures:
        L.append(f"FAILED TESTS ({len(failures)})")
        L.append("")
        for o in failures:
            L += [f"  {o.test_id}", f"    Expected: {o.expected_reaction}",
                  f"    Actual:   {o.detail}"]
            if "TIMEOUT" in o.detail:
                L.append("    Root cause: Check DIAG threshold or debounce settings.")
            elif "contactor did not open" in o.detail:
                L.append("    Root cause: Check BMS ERROR->OPEN transition.")
            elif "DIAG bit" in o.detail and "not set" in o.detail:
                L.append("    Root cause: DIAG ID may be disabled or threshold too high.")
            L.append("")
    skips = [o for o in outcomes if o.result == TestResult.SKIP]
    if skips:
        L += [f"SKIP JUSTIFICATION ({len(skips)})", ""]
        for o in skips:
            L.append(f"  {o.test_id}: {o.skip_reason or o.detail}")
        L.append("")
    L.append("TEST ENVIRONMENT DETAILS")
    L += [f"  foxbms-vecu binary: {vecu_hash}", f"  plant_model.py: {plant_hash}",
          f"  Battery config: NMC (OV MSL=4250mV, UV MSL=2500mV, OT MSL=550ddegC, UT MSL=-200ddegC)",
          f"  DIAG config: 42 disabled, 43 enabled  SIL probes: 14 active (0x7F0-0x7FF)",
          f"  CAN: {can_interface}  Platform: {platform.system()} {platform.release()} {platform.machine()}",
          ""]
    L += ["=" * 79, "Report generated automatically by test_fault_injection.py",
          "Manual review required for ASPICE CL2 compliance.", "",
          "Reviewer: _________________ Date: _________________",
          "Approver: _________________ Date: _________________", "=" * 79]
    return L
