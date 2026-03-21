"""Parsing functions for fault injection test values and targets.

Handles injection values, targets, thresholds, DIAG bit resolution,
override command resolution, and skip logic.
"""

import random
from typing import Dict, List, Optional, Tuple

# Re-export load_test_cases and filter_tests for backward compatibility
from fi.csv_loader import filter_tests, load_test_cases  # noqa: F401

from fi.constants import (
    DIAG_ID_MAP,
    SEVERITY_OFFSET,
    SIL_CELL_TEMP,
    SIL_CELL_VOLTAGE,
    SIL_PACK_CURRENT,
    SIL_PACK_VOLTAGE,
    SKIP_FAULT_METHODS,
    SKIP_REACTIONS,
    SKIP_TARGET_TYPES,
)
from fi.models import TestCase


def parse_target(target_str: str) -> Tuple:
    """Parse TARGET_CELL_OR_SENSOR into (type, [indices])."""
    target_str = target_str.strip()

    if target_str in ("ALL_CELLS", "ALL_18_CELLS", "ALL"):
        return ("cell", list(range(18)))

    if target_str == "ALL_SENSORS":
        return ("sensor", list(range(5)))

    if target_str.startswith("CELL_") and "+" not in target_str:
        try:
            idx = int(target_str.split("_")[1])
            return ("cell", [idx])
        except (ValueError, IndexError):
            pass

    if target_str.startswith("SENSOR_") and "+" not in target_str:
        try:
            idx = int(target_str.split("_")[1])
            return ("sensor", [idx])
        except (ValueError, IndexError):
            pass

    if target_str.startswith("STRING_") and "+" not in target_str:
        try:
            idx = int(target_str.split("_")[1])
            return ("string", [idx])
        except (ValueError, IndexError):
            pass

    if "+" in target_str:
        # Parse compound target: "CELL_0+STRING_0" -> [("cell", [0]), ("string", [0])]
        parts = target_str.split("+")
        sub_targets = []
        for part in parts:
            sub_type, sub_indices = parse_target(part.strip())
            sub_targets.append((sub_type, sub_indices))
        return ("compound", sub_targets)

    if target_str.startswith("IVT") or target_str.startswith("0x") or target_str.startswith("CAN_"):
        return ("special", [])

    if target_str.startswith("FROM_"):
        return ("state_transition", [])

    return ("unknown", [])


def resolve_override_cmd(category: str, signal: str) -> int:
    """Map category/signal to the SIL override command byte."""
    sig = signal.upper()
    if "CELL_V" in sig or category == "VOLT" and "PACK" not in sig:
        return SIL_CELL_VOLTAGE
    if "TEMP" in sig or category == "TEMP":
        return SIL_CELL_TEMP
    if "CURR" in sig or "PACK_CURR" in sig or category == "CURR":
        return SIL_PACK_CURRENT
    if "PACK_V" in sig:
        return SIL_PACK_VOLTAGE
    return SIL_CELL_VOLTAGE  # Default fallback


def parse_injection_value(value_str: str, fault_method: str) -> Optional[int]:
    """Parse INJECTION_VALUE into int, or None for complex patterns (DRIFT, NOISE, etc.)."""
    value_str = value_str.strip()

    # Simple integer
    try:
        return int(value_str)
    except ValueError:
        pass

    # DRIFT: "3700>4300" — return the target value
    if ">" in value_str and fault_method in ("DRIFT_UP", "DRIFT_DOWN", "RATE_OF_CHANGE"):
        parts = value_str.split(">")
        target = parts[-1].split("@")[0]
        try:
            return int(target)
        except ValueError:
            pass

    # DELAYED: "4260@+500ms" — extract the value before @
    if "@" in value_str and fault_method == "DELAYED":
        try:
            return int(value_str.split("@")[0])
        except ValueError:
            pass

    # OFFSET_POS/NEG: "+500mV(eff=4200)" — extract effective value
    if "eff=" in value_str:
        try:
            eff_str = value_str.split("eff=")[1].rstrip(")")
            return int(eff_str)
        except (ValueError, IndexError):
            pass

    # NOISE: "+-200mV@4250" — extract center value
    if value_str.startswith("+-") and "@" in value_str:
        try:
            center = int(value_str.split("@")[1])
            return center
        except ValueError:
            pass

    # CORRUPTED: "RANDOM_VALID" — pick an out-of-range value
    if value_str == "RANDOM_VALID":
        return random.choice([0, 5000, -100, 65535])

    # STEP_TO_VALUE with @event suffix: "4260@event_50"
    if "@event" in value_str:
        try:
            return int(value_str.split("@")[0])
        except ValueError:
            pass

    # NO_SIGNAL (MISSING_TIMEOUT)
    if value_str == "NO_SIGNAL":
        return None

    # COMBO values: "CELL_V=4260/I=16000" — not directly injectable as single int
    if "=" in value_str and "/" in value_str and "inject=" not in value_str:
        return None

    # inject=4260/clear=3700 (RECOV patterns)
    if "inject=" in value_str:
        try:
            return int(value_str.split("inject=")[1].split("/")[0])
        except (ValueError, IndexError):
            pass

    return None


def parse_compound_injection(value_str: str) -> Dict[str, int]:
    """Parse "key=val/key=val" into {key: int_val}. Strips mV/mA/ms/%/ddegC units."""
    result = {}
    value_str = value_str.strip()

    for part in value_str.split("/"):
        part = part.strip()
        if "=" not in part:
            continue
        key, val_str = part.split("=", 1)
        # Strip units: mV, mA, ms, %, ddegC
        val_str = (val_str.replace("mV", "").replace("mA", "")
                   .replace("ms", "").replace("%", "").replace("ddegC", ""))
        try:
            result[key] = int(val_str)
        except ValueError:
            pass

    return result


def parse_recov_injection(value_str: str) -> Dict[str, object]:
    """Parse RECOV values like "inject=4260/clear=3700" or "inject=X/duration=10s/check_latch"."""
    result: Dict[str, object] = {}
    value_str = value_str.strip()

    for part in value_str.split("/"):
        part = part.strip()
        if part == "check_latch":
            result["check_latch"] = True
            continue
        if "=" not in part:
            continue
        key, val_str = part.split("=", 1)
        if key == "duration":
            try:
                result["duration_s"] = int(val_str.replace("s", ""))
            except ValueError:
                result["duration_s"] = 10
        elif key == "request":
            result["request"] = val_str
        else:
            try:
                result[key] = int(val_str)
            except ValueError:
                result[key] = val_str

    return result


def resolve_recov_override_cmd(signal: str) -> int:
    """Map RECOV signal name to the SIL override command byte."""
    sig = signal.upper()
    if "_OT_" in sig or "_UT_" in sig:
        return SIL_CELL_TEMP
    if "_OC_" in sig:
        return SIL_PACK_CURRENT
    if "_OV_" in sig or "_UV_" in sig or "DEEP_DISCHARGE" in sig:
        return SIL_CELL_VOLTAGE
    return SIL_CELL_VOLTAGE  # Default


def parse_drift_range(value_str: str) -> Tuple[int, int]:
    """Parse DRIFT value "3700>4300" into (start, end)."""
    parts = value_str.split(">")
    return (int(parts[0]), int(parts[1].split("@")[0]))


def parse_noise_params(value_str: str) -> Tuple[int, int]:
    """Parse NOISE value "+-200mV@4250" into (amplitude, center)."""
    return (int(value_str.split("@")[0].replace("+-", "").replace("mV", "")),
            int(value_str.split("@")[1]))


def parse_threshold(threshold_str: str) -> Tuple[int, int]:
    """Parse threshold "50ev/200ms" into (event_count, delay_ms)."""
    threshold_str = threshold_str.strip()
    events = 50
    delay_ms = 200

    if "/" in threshold_str:
        parts = threshold_str.split("/")
        try:
            events = int(parts[0].replace("ev", ""))
        except ValueError:
            pass
        try:
            delay_ms = int(parts[1].replace("ms", ""))
        except ValueError:
            pass
    elif threshold_str.endswith("ev"):
        try:
            events = int(threshold_str.replace("ev", ""))
        except ValueError:
            pass

    return (events, delay_ms)


def resolve_diag_bit(diag_id_str: str, severity_tier: str) -> Optional[int]:
    """Resolve DIAG_ID string + severity tier to a bitmap bit index."""
    if "+" in diag_id_str:
        return None  # Cannot check a single bit for compound faults

    base_id = DIAG_ID_MAP.get(diag_id_str)
    if base_id is None:
        return None

    offset = SEVERITY_OFFSET.get(severity_tier, 0)
    return base_id + offset


def should_skip(tc: TestCase) -> Optional[str]:
    """Return a skip reason string, or None if the test should run."""
    if tc.fault_method in SKIP_FAULT_METHODS:
        return f"requires {tc.fault_method} (not implemented)"

    if tc.bms_state != "NORMAL" and tc.bms_state not in ("", "N/A"):
        return f"requires {tc.bms_state} state"

    target_type, _ = parse_target(tc.target)
    if target_type in SKIP_TARGET_TYPES:
        return f"requires {tc.target} target (not supported)"

    if tc.expected_reaction in SKIP_REACTIONS:
        return f"requires {tc.expected_reaction} verification"

    if tc.category == "PLAUS":
        diag = tc.diag_id
        if diag not in DIAG_ID_MAP and diag not in ("", "N/A"):
            return f"DIAG ID {diag} not mapped (may be disabled)"

    if tc.category == "COMBO":
        if "NO_SIGNAL" in tc.injection_value:
            return "COMBO with NO_SIGNAL (requires timeout injection)"

    return None
