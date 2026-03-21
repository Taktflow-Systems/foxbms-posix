"""Test executor base class with precondition verification and dispatch.

Contains the TestExecutor class which handles test execution lifecycle:
precondition checks, wait helpers, and dispatch to specific test runners.
"""

import copy
import random
import time
from typing import List, Tuple

from fi.can_bus import CanBus
from fi.constants import BMS_STATE_NAMES, STARTUP_TIMEOUT_S, RECOVERY_TIMEOUT_S
from fi.injector import FaultInjector
from fi.models import TestCase, TestOutcome, TestResult
from fi.parsers import (
    parse_injection_value,
    parse_target,
    resolve_diag_bit,
    resolve_override_cmd,
    resolve_recov_override_cmd,
    should_skip,
    SIL_CELL_VOLTAGE,
    SIL_CELL_TEMP,
)
from fi.probe_monitor import ProbeMonitor


class TestExecutor:
    """Runs individual fault injection test cases."""

    def __init__(self, bus: CanBus, injector: FaultInjector,
                 monitor: ProbeMonitor, timeout_ms: int):
        self.bus = bus
        self.injector = injector
        self.monitor = monitor
        self.timeout_ms = timeout_ms

    def wait_for_normal(self, timeout_s: float = STARTUP_TIMEOUT_S) -> bool:
        """Wait for BMS to reach NORMAL state."""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            self.injector.monitor_and_update(self.monitor, 0.05)
            if self.monitor.bms_in_normal():
                return True
        return False

    def wait_for_current_flowing(self, timeout_s: float = 5.0) -> bool:
        """Wait for plant discharge current to reach foxBMS database."""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            self.injector.monitor_and_update(self.monitor, 0.05)
            if self.monitor.bms_in_normal():
                elapsed = time.monotonic() - (deadline - timeout_s)
                if elapsed > 4.0:
                    return True
        return False

    def verify_preconditions(self, timeout_s: float = 15.0) -> Tuple[bool, str]:
        """Verify all 6 preconditions. Returns (success, detail_string)."""
        deadline = time.monotonic() + timeout_s
        m = self.monitor
        ok = [False] * 6  # BMS_NORMAL, CURRENT, VOLTAGE, TEMP, DIAG, CONTACTOR

        while time.monotonic() < deadline:
            self.injector.monitor_and_update(m, 0.05)
            if not ok[0] and m.bms_in_normal():
                ok[0] = True
                print("  [precond] 1/6 BMS state = NORMAL")
            if ok[0] and not ok[1]:
                cur_ok = abs(m.pack_current_ma) > 200
                t_in = (time.monotonic() - m.normal_entry_time) if m.normal_entry_time > 0 else 0.0
                if cur_ok or t_in > 4.0:
                    ok[1] = True
                    print(f"  [precond] 2/6 Current: {m.pack_current_ma}mA" if cur_ok
                          else f"  [precond] 2/6 Current: {t_in:.1f}s in NORMAL")
            if not ok[2]:
                v_min, v_max = m.cell_voltage_min_mv, m.cell_voltage_max_mv
                if v_min > 0 and 2700 <= v_min and v_max <= 4150:
                    ok[2] = True
                    print(f"  [precond] 3/6 Voltage OK: {v_min}-{v_max}mV")
                elif v_min == 0 and v_max == 0 and ok[0]:
                    ok[2] = True
                    print("  [precond] 3/6 Voltage OK: inferred from NORMAL")
            if not ok[3]:
                t_min, t_max = m.temperature_min_ddegc, m.temperature_max_ddegc
                if 0 <= t_min and t_max <= 400:
                    ok[3] = True
                    print(f"  [precond] 4/6 Temperature OK: {t_min}-{t_max} ddegC")
                elif t_min == 0 and t_max == 0 and ok[0]:
                    ok[3] = True
                    print("  [precond] 4/6 Temperature OK: inferred from NORMAL")
            if not ok[4] and m.diag_bitmap == 0:
                ok[4] = True
                print("  [precond] 5/6 DIAG bitmap clear")
            if not ok[5] and m.sps_actual != 0:
                ok[5] = True
                print(f"  [precond] 6/6 Contactors closed (SPS={m.sps_actual:#06x})")
            if all(ok):
                return (True, f"all 6 preconditions met (BMS=NORMAL, I={m.pack_current_ma}mA, "
                        f"V={m.cell_voltage_min_mv}-{m.cell_voltage_max_mv}mV, "
                        f"T={m.temperature_min_ddegc}-{m.temperature_max_ddegc}ddegC, DIAG=0, CONT=CLOSED)")

        # Timeout — report failures
        names = ["BMS_NORMAL", "CURRENT", "VOLTAGE", "TEMPERATURE", "DIAG", "CONTACTORS"]
        fail_info = {
            0: f"BMS={BMS_STATE_NAMES.get(m.bms_state, '?')}",
            1: f"I={m.pack_current_ma}mA",
            2: f"V={m.cell_voltage_min_mv}-{m.cell_voltage_max_mv}mV",
            3: f"T={m.temperature_min_ddegc}-{m.temperature_max_ddegc}ddegC",
            4: f"DIAG={m.diag_bitmap:#018x}",
            5: f"SPS={m.sps_actual:#06x}",
        }
        reasons = [fail_info[i] for i in range(6) if not ok[i]]
        return (False, f"precondition {sum(ok)}/6 met, failed: {', '.join(reasons)}")

    def wait_for_recovery(self, timeout_s: float = RECOVERY_TIMEOUT_S) -> bool:
        """Wait for BMS to return to NORMAL after clearing a fault."""
        self.injector.clear()
        time.sleep(0.05)
        return self.wait_for_normal(timeout_s)

    def execute(self, tc: TestCase, precondition_detail: str = "") -> TestOutcome:
        """Execute a single test case with metadata enrichment."""
        outcome = self._execute_inner(tc)
        # Enrich with test case metadata for audit report
        outcome.signal = tc.signal
        outcome.fault_method = tc.fault_method
        outcome.target = tc.target
        outcome.injection_value = tc.injection_value
        outcome.expected_reaction = tc.expected_reaction
        outcome.severity_tier = tc.severity_tier
        outcome.precondition_detail = precondition_detail
        if outcome.result == TestResult.SKIP:
            outcome.skip_reason = outcome.detail
        return outcome

    def _execute_inner(self, tc: TestCase) -> TestOutcome:
        """Execute a single test case. Returns TestOutcome."""
        # Avoid circular imports by importing test runners here
        from fi.test_contactor import run_contactor_open_test, run_no_reaction_test
        from fi.test_warning import run_warning_flag_test
        from fi.test_dynamic import run_drift_test, run_noise_test, _run_oscillate_test
        from fi.test_combo import (run_combo_simultaneous_test, run_combo_sequential_test,
                                    run_plaus_mismatch_test, run_plaus_spread_test)
        from fi.test_recovery import run_recovery_test, run_persist_test, run_fault_clears_test

        def _skip(detail):
            return TestOutcome(test_id=tc.test_id, result=TestResult.SKIP,
                               elapsed_ms=0, detail=detail,
                               category=tc.category, priority=tc.priority)

        skip_reason = should_skip(tc)
        if skip_reason:
            return _skip(skip_reason)

        # ---- Category-level dispatch for PLAUS, COMBO, RECOV ----
        try:
            if tc.category == "PLAUS":
                if tc.fault_method == "INJECTED_MISMATCH":
                    return run_plaus_mismatch_test(self, tc)
                elif tc.fault_method == "INJECTED_SPREAD":
                    return run_plaus_spread_test(self, tc)
                else:
                    return _skip(f"PLAUS method {tc.fault_method} not implemented")

            if tc.category == "COMBO":
                if tc.fault_method == "SIMULTANEOUS":
                    return run_combo_simultaneous_test(self, tc)
                elif tc.fault_method in ("SEQUENTIAL", "TIMED_INJECTION"):
                    return run_combo_sequential_test(self, tc)
                else:
                    return _skip(f"COMBO method {tc.fault_method} not implemented")

            if tc.category == "RECOV":
                if tc.fault_method == "INJECT_THEN_CLEAR":
                    return run_recovery_test(self, tc)
                elif tc.fault_method == "CONTINUOUS":
                    return run_persist_test(self, tc)
                elif tc.fault_method == "OSCILLATE":
                    cmd = resolve_recov_override_cmd(tc.signal)
                    if cmd == SIL_CELL_VOLTAGE:
                        indices = list(range(18))
                    elif cmd == SIL_CELL_TEMP:
                        indices = list(range(5))
                    else:
                        indices = [0]
                    osc_val = tc.injection_value
                    if "oscillate=" in osc_val:
                        try:
                            osc_parts = osc_val.split("=")[1].split("<>")
                            fault_v = int(osc_parts[0])
                            tc_osc = copy.copy(tc)
                            tc_osc.injection_value = str(fault_v)
                            return _run_oscillate_test(self, tc_osc, cmd, indices)
                        except (ValueError, IndexError):
                            pass
                    return _run_oscillate_test(self, tc, cmd, indices)
                elif tc.fault_method == "INJECT_PARTIAL_CLEAR":
                    return _skip("INJECT_PARTIAL_CLEAR requires counter manipulation")
                else:
                    return _skip(f"RECOV method {tc.fault_method} not implemented")
        except Exception as e:
            return TestOutcome(
                test_id=tc.test_id, result=TestResult.ERROR,
                elapsed_ms=0, detail=f"exception in category dispatch: {e}",
                category=tc.category, priority=tc.priority,
            )

        # ---- Generic dispatch for VOLT, TEMP, CURR, etc. ----
        target_type, raw_indices = parse_target(tc.target)
        if target_type == "compound" and isinstance(raw_indices, list) and raw_indices:
            if isinstance(raw_indices[0], tuple):
                indices = raw_indices[0][1]
            else:
                indices = raw_indices
        else:
            indices = raw_indices
        cmd = resolve_override_cmd(tc.category, tc.signal)

        value = parse_injection_value(tc.injection_value, tc.fault_method)

        try:
            if tc.fault_method in ("DRIFT_UP", "DRIFT_DOWN", "RATE_OF_CHANGE"):
                return run_drift_test(self, tc, cmd, indices, tc.fault_method)

            if tc.fault_method == "NOISE":
                return run_noise_test(self, tc, cmd, indices)

            if tc.fault_method == "CORRUPTED":
                if value is None:
                    value = random.choice([0, 5000, -100, 65535])

            if tc.fault_method == "DELAYED":
                delay_ms = 500
                if "@+" in tc.injection_value:
                    try:
                        delay_str = tc.injection_value.split("@+")[1].replace("ms", "")
                        delay_ms = int(delay_str)
                    except ValueError:
                        pass
                time.sleep(delay_ms / 1000.0)

            if tc.fault_method == "OSCILLATE":
                return _run_oscillate_test(self, tc, cmd, indices)

            if tc.fault_method == "INJECT_THEN_CLEAR":
                if value is None:
                    return TestOutcome(
                        test_id=tc.test_id, result=TestResult.ERROR,
                        elapsed_ms=0,
                        detail=f"cannot parse inject value: {tc.injection_value}",
                        category=tc.category, priority=tc.priority,
                    )
                if tc.expected_reaction in ("FAULT_CLEARS", "STATE_NORMAL"):
                    return run_fault_clears_test(self, tc, cmd, indices, value)

            if tc.fault_method == "INJECT_PARTIAL_CLEAR":
                pass

            if value is None:
                return _skip(f"cannot resolve injection value: {tc.injection_value}")

            if tc.category == "TEMP" and ("DIS" in tc.signal):
                if not self.wait_for_current_flowing(5.0):
                    return _skip("plant not discharging — current not flowing after 5s")

            # Reaction dispatch — map expected reactions to test runners
            _CONTACTOR_OPEN_REACTIONS = {
                "CONTACTOR_OPEN", "CONTACTOR_OPEN_LATCHED", "ERROR_FLAG",
                "PLAUSIBILITY_ERROR", "PLAUSIBILITY_CHECK", "TIMEOUT_ERROR",
                "PRECHARGE_ABORT", "ERROR_HANDLING", "FAULT_ACTIVE",
                "BOTH_DETECTED", "COUNTER_RESETS", "LATCH_OR_CLEAR",
                "NORMAL_CHARGE", "NORMAL_DISCHARGE", "REST_OR_CHARGE",
                "REST_OR_DISCHARGE", "REST_STATE", "OC_CHARGE", "OC_DISCHARGE",
            }
            if tc.expected_reaction in _CONTACTOR_OPEN_REACTIONS:
                return run_contactor_open_test(self, tc, cmd, indices, value)
            if tc.expected_reaction == "WARNING_FLAG":
                return run_warning_flag_test(self, tc, cmd, indices, value)
            if tc.expected_reaction in ("NO_REACTION", "NO_CONTACTOR_OPEN"):
                return run_no_reaction_test(self, tc, cmd, indices, value)
            if tc.expected_reaction in ("FAULT_CLEARS", "FAULT_PERSISTS"):
                return run_fault_clears_test(self, tc, cmd, indices, value)

            return _skip(f"unhandled reaction type: {tc.expected_reaction}")

        except Exception as e:
            return TestOutcome(
                test_id=tc.test_id, result=TestResult.ERROR,
                elapsed_ms=0, detail=f"exception: {e}",
                category=tc.category, priority=tc.priority,
            )
