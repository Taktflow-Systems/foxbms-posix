"""CSV test case loading and filtering.

Loads test cases from the fault injection CSV matrix and applies
CLI-based filters (pattern, category, priority, quick mode, max count).
"""

import argparse
import csv
from typing import List

from fi.models import TestCase


def load_test_cases(csv_path: str) -> List[TestCase]:
    """Load test cases from the CSV matrix."""
    cases = []
    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tc = TestCase(
                test_id=row.get("TEST_ID", "").strip(),
                category=row.get("CATEGORY", "").strip(),
                signal=row.get("SIGNAL", "").strip(),
                fault_method=row.get("FAULT_METHOD", "").strip(),
                injection_value=row.get("INJECTION_VALUE", "").strip(),
                target=row.get("TARGET_CELL_OR_SENSOR", "").strip(),
                bms_state=row.get("BMS_STATE", "").strip(),
                severity_tier=row.get("SEVERITY_TIER", "").strip(),
                diag_id=row.get("DIAG_ID", "").strip(),
                threshold=row.get("THRESHOLD", "").strip(),
                expected_reaction=row.get("EXPECTED_REACTION", "").strip(),
                pass_criteria=row.get("PASS_CRITERIA", "").strip(),
                priority=row.get("PRIORITY", "").strip(),
            )
            if tc.test_id:
                cases.append(tc)
    return cases


def filter_tests(cases: List[TestCase], args: argparse.Namespace) -> List[TestCase]:
    """Apply CLI filters to the test case list."""
    filtered = cases

    if args.filter:
        pattern = args.filter.upper()
        filtered = [tc for tc in filtered if pattern in tc.test_id.upper()
                     or pattern in tc.category.upper()
                     or pattern in tc.signal.upper()
                     or pattern in tc.fault_method.upper()]

    if args.category:
        cat = args.category.upper()
        filtered = [tc for tc in filtered if tc.category.upper() == cat]

    if args.priority:
        pri = args.priority.upper()
        filtered = [tc for tc in filtered if tc.priority.upper() == pri]

    if args.quick:
        filtered = [tc for tc in filtered
                     if tc.priority.upper() == "P1"
                     and tc.fault_method == "STEP_TO_VALUE"]

    if args.max and args.max > 0:
        filtered = filtered[:args.max]

    return filtered
