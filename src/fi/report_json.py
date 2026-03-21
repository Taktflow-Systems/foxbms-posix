"""JSON report generation for fault injection test results.

Builds the structured JSON report dict for ASPICE CL2-auditable
fault injection test reports.
"""

import json
import platform
from datetime import datetime
from typing import Any, Dict, List, Tuple

from fi.models import TestOutcome, TestResult


def _classify_aspice_level(tc_outcome: TestOutcome) -> str:
    """Classify a test into ASPICE test level (SWE.5 or SWE.6)."""
    if tc_outcome.category in ("COMBO", "PLAUS"):
        return "SWE.6"
    return "SWE.5"


def build_json_report(
    outcomes: List[TestOutcome],
    overall: str,
    total: int,
    pass_count: int,
    fail_count: int,
    skip_count: int,
    error_count: int,
    pass_rate: float,
    start_time: datetime,
    duration_s: float,
    can_interface: str,
    csv_basename: str,
    csv_total: int,
    vecu_hash: str,
    plant_hash: str,
    category_stats: Dict[str, Dict[str, int]],
    level_stats: Dict[str, Dict[str, int]],
    det_stats: Dict[str, Dict[str, Any]],
    precond_stats: Tuple[int, int, int],
    restart_count: int,
) -> Dict[str, Any]:
    """Build the JSON report dictionary."""
    precond_total, precond_passed, precond_failed = precond_stats

    return {
        "report_type": "FAULT_INJECTION_TEST_REPORT",
        "project": "foxBMS POSIX vECU (SIL)",
        "test_level": "SWE.5",
        "platform": f"{platform.system()} {platform.machine()}",
        "foxbms_version": "v1.10.0",
        "test_matrix": csv_basename,
        "test_matrix_total": csv_total,
        "date": start_time.isoformat(),
        "duration_s": duration_s,
        "tester": "automated (test_fault_injection.py)",
        "environment": {
            "can_interface": can_interface,
            "vecu_sha256": vecu_hash,
            "plant_sha256": plant_hash,
            "platform_detail": f"{platform.system()} {platform.release()} {platform.machine()}",
            "battery_config": {
                "chemistry": "NMC",
                "ov_msl_mv": 4250, "uv_msl_mv": 2500,
                "ot_msl_ddegc": 550, "ut_msl_ddegc": -200,
            },
            "diag_config": {"disabled": 42, "enabled": 43},
            "sil_probes": {"count": 14, "range": "0x7F0-0x7FF"},
        },
        "summary": {
            "overall_result": overall,
            "total": total, "pass": pass_count, "fail": fail_count,
            "skip": skip_count, "error": error_count,
            "pass_rate_runnable": round(pass_rate, 1),
        },
        "preconditions": {
            "checks_total": precond_total, "checks_passed": precond_passed,
            "checks_failed": precond_failed, "restarts": restart_count,
        },
        "results_by_category": {
            cat: {
                "total": s["total"], "pass": s["PASS"], "fail": s["FAIL"],
                "skip": s["SKIP"], "error": s["ERROR"],
                "pass_rate": round(s["PASS"] / max(1, s["total"] - s["SKIP"]) * 100, 1),
            }
            for cat, s in sorted(category_stats.items())
        },
        "results_by_aspice_level": {
            level: {
                "total": s["total"], "pass": s["PASS"], "fail": s["FAIL"],
                "skip": s["SKIP"], "error": s["ERROR"],
            }
            for level, s in sorted(level_stats.items())
        },
        "detection_time_stats": {
            cat: {
                "name": d["name"], "threshold": d["threshold"],
                "min_ms": round(d["min_ms"], 1), "max_ms": round(d["max_ms"], 1),
                "avg_ms": round(d["avg_ms"], 1), "sample_count": d["count"],
            }
            for cat, d in sorted(det_stats.items())
        },
        "tests": [
            {
                "test_id": o.test_id, "category": o.category,
                "signal": o.signal, "fault_method": o.fault_method,
                "target": o.target, "injection_value": o.injection_value,
                "expected_reaction": o.expected_reaction,
                "severity_tier": o.severity_tier, "result": o.result,
                "elapsed_ms": round(o.elapsed_ms, 1),
                "diag_time_ms": round(o.diag_time_ms, 1),
                "contactor_time_ms": round(o.contactor_time_ms, 1),
                "precondition_detail": o.precondition_detail,
                "detail": o.detail, "bms_state_trace": o.bms_state_trace,
                "skip_reason": o.skip_reason,
                "aspice_level": _classify_aspice_level(o),
            }
            for o in outcomes
        ],
        "failed_tests": [
            {"test_id": o.test_id, "expected": o.expected_reaction, "actual": o.detail}
            for o in outcomes if o.result == TestResult.FAIL
        ],
        "skipped_tests": [
            {"test_id": o.test_id, "reason": o.skip_reason or o.detail}
            for o in outcomes if o.result == TestResult.SKIP
        ],
    }


def write_json_report(json_report: Dict[str, Any], json_path: str) -> None:
    """Write JSON report to file."""
    with open(json_path, "w") as f:
        json.dump(json_report, f, indent=2)
