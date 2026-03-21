"""Data classes for fault injection test cases and outcomes.

Contains TestCase (parsed from CSV), TestResult (verdict constants),
and TestOutcome (result of a single test execution).
"""

from dataclasses import dataclass


@dataclass
class TestCase:
    """Parsed test case from CSV row."""
    test_id: str
    category: str
    signal: str
    fault_method: str
    injection_value: str
    target: str
    bms_state: str
    severity_tier: str
    diag_id: str
    threshold: str
    expected_reaction: str
    pass_criteria: str
    priority: str


class TestResult:
    """Test verdict constants."""
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"
    ERROR = "ERROR"


@dataclass
class TestOutcome:
    """Result of a single test execution."""
    test_id: str
    result: str
    elapsed_ms: float
    detail: str
    category: str = ""
    priority: str = ""
    # Extended fields for ASPICE audit report
    diag_time_ms: float = 0.0
    contactor_time_ms: float = 0.0
    precondition_detail: str = ""
    skip_reason: str = ""
    signal: str = ""
    fault_method: str = ""
    target: str = ""
    injection_value: str = ""
    expected_reaction: str = ""
    severity_tier: str = ""
    bms_state_trace: str = ""
