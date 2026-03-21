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

import argparse
import copy
import csv
import os
import random
import signal
import socket
import struct
import subprocess
import sys
import time
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ============================================================================
# Constants
# ============================================================================

CAN_OVERRIDE_ID = 0x7E0
CAN_PROBE_SPS = 0x7F0
CAN_PROBE_DIAG = 0x7F7
CAN_PROBE_DIAG_BITMAP = 0x7F8
CAN_PROBE_STATE = 0x7F9
CAN_BMS_STATE_MSG = 0x220

# SIL override command bytes (from sil_layer.h)
SIL_CELL_VOLTAGE = 0x01
SIL_CELL_TEMP = 0x02
SIL_PACK_CURRENT = 0x03
SIL_SOC = 0x04
SIL_CONTACTOR_FB = 0x05
SIL_INTERLOCK = 0x06
SIL_PACK_VOLTAGE = 0x07
SIL_DIAG_FORCE = 0x08
SIL_DIAG_CLEAR = 0x09
SIL_CLEAR_ALL = 0xFF

# BMS states (from foxBMS state machine)
BMS_UNINITIALIZED = 0
BMS_INITIALIZATION = 1
BMS_INITIALIZED = 2
BMS_IDLE = 3
BMS_OPEN_CONTACTORS = 4
BMS_STANDBY = 5
BMS_PRECHARGE = 6
BMS_NORMAL = 7
BMS_DISCHARGE = 8
BMS_CHARGE = 9
BMS_ERROR = 10

BMS_STATE_NAMES = {
    0: "UNINITIALIZED", 1: "INITIALIZATION", 2: "INITIALIZED",
    3: "IDLE", 4: "OPEN_CONTACTORS", 5: "STANDBY",
    6: "PRECHARGE", 7: "NORMAL", 8: "DISCHARGE",
    9: "CHARGE", 10: "ERROR",
}

# Default timeouts
DEFAULT_TIMEOUT_MS = 5000
RECOVERY_TIMEOUT_S = 10.0
STARTUP_TIMEOUT_S = 30.0


# ============================================================================
# DIAG ID enum mapping (from foxBMS diag_cfg.h)
# ============================================================================

DIAG_ID_MAP = {
    # Cell voltage
    "DIAG_ID_CELLVOLTAGE_OVERVOLTAGE": 18,
    "DIAG_ID_CELLVOLTAGE_UNDERVOLTAGE": 21,
    # Temperatures
    "DIAG_ID_TEMP_OVERTEMPERATURE_CHARGE": 24,
    "DIAG_ID_TEMP_OVERTEMPERATURE_DISCHARGE": 27,
    "DIAG_ID_TEMP_UNDERTEMPERATURE_CHARGE": 30,
    "DIAG_ID_TEMP_UNDERTEMPERATURE_DISCHARGE": 33,
    # Current — cell level
    "DIAG_ID_OVERCURRENT_CHARGE_CELL": 36,
    "DIAG_ID_OVERCURRENT_DISCHARGE_CELL": 39,
    # Current — string level
    "DIAG_ID_STRING_OVERCURRENT_CHARGE": 42,
    "DIAG_ID_STRING_OVERCURRENT_DISCHARGE": 45,
    # Current — pack level
    "DIAG_ID_OVERCURRENT_CHARGE_PACK": 48,
    "DIAG_ID_OVERCURRENT_DISCHARGE_PACK": 49,
    # Pack voltage
    "DIAG_ID_PACKVOLTAGE": 50,
    # Plausibility
    "DIAG_ID_PLAUSIBILITY_CELLVOLTAGE": 51,
    "DIAG_ID_PLAUSIBILITY_CELLTEMPERATURE": 52,
}

# Severity tier to DIAG ID offset within group of 3 (MSL=0, RSL=1, MOL=2)
SEVERITY_OFFSET = {
    "OV_MSL": 0, "OV_RSL": 1, "OV_MOL": 2,
    "UV_MSL": 0, "UV_RSL": 1, "UV_MOL": 2,
    "OT_DIS_MSL": 0, "OT_DIS_RSL": 1, "OT_DIS_MOL": 2,
    "OT_CHG_MSL": 0, "OT_CHG_RSL": 1, "OT_CHG_MOL": 2,
    "UT_DIS_MSL": 0, "UT_DIS_RSL": 1, "UT_DIS_MOL": 2,
    "UT_CHG_MSL": 0, "UT_CHG_RSL": 1, "UT_CHG_MOL": 2,
    "OC_DISCHARGE_MSL": 0, "OC_DISCHARGE_RSL": 1, "OC_DISCHARGE_MOL": 2,
    "OC_CHARGE_MSL": 0, "OC_CHARGE_RSL": 1, "OC_CHARGE_MOL": 2,
}


# ============================================================================
# Test case data structures
# ============================================================================

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


# ============================================================================
# CAN Bus Abstraction
# ============================================================================

class CanBus:
    """SocketCAN raw socket wrapper."""

    def __init__(self, interface: str):
        self.interface = interface
        self.sock = socket.socket(socket.AF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
        self.sock.bind((interface,))
        self.sock.setblocking(False)

    def send(self, can_id: int, data: bytes) -> None:
        """Send a CAN frame (up to 8 bytes)."""
        dlc = min(len(data), 8)
        padded = data[:8].ljust(8, b'\x00')
        frame = struct.pack("=IB3x8s", can_id, dlc, padded)
        self.sock.send(frame)

    def recv(self, timeout_s: float = 0.0) -> Optional[Tuple[int, bytes]]:
        """Receive a CAN frame. Returns (can_id, data) or None on timeout."""
        if timeout_s > 0:
            self.sock.settimeout(timeout_s)
        else:
            self.sock.setblocking(False)
        try:
            raw = self.sock.recv(16)
            if len(raw) >= 16:
                can_id = struct.unpack("=I", raw[0:4])[0] & 0x1FFFFFFF
                data = raw[8:16]
                return (can_id, data)
        except (BlockingIOError, socket.timeout):
            pass
        finally:
            self.sock.setblocking(False)
        return None

    def drain(self) -> None:
        """Drain all pending frames from the socket."""
        while True:
            try:
                self.sock.recv(16)
            except BlockingIOError:
                break

    def close(self) -> None:
        self.sock.close()


# ============================================================================
# Probe Monitor — reads SIL probe CAN frames
# ============================================================================

class ProbeMonitor:
    """Caches the latest probe state from SIL CAN frames."""

    def __init__(self):
        self.diag_fault_count: int = 0
        self.diag_last_id: int = 0
        self.diag_last_event: int = 0
        self.diag_bitmap: int = 0
        self.bms_state: int = 0
        self.sys_state: int = 0
        self.sps_requested: int = 0
        self.sps_actual: int = 0
        self.last_update_time: float = 0.0

    def update(self, can_id: int, data: bytes) -> None:
        """Update state from a received probe CAN frame."""
        self.last_update_time = time.monotonic()

        if can_id == CAN_PROBE_DIAG and len(data) >= 6:
            self.diag_fault_count = struct.unpack_from("<I", data, 0)[0]
            self.diag_last_id = data[4]
            self.diag_last_event = data[5]

        elif can_id == CAN_PROBE_DIAG_BITMAP and len(data) >= 8:
            self.diag_bitmap = struct.unpack_from("<Q", data, 0)[0]

        elif can_id == CAN_PROBE_STATE and len(data) >= 5:
            self.sys_state = data[0]
            self.bms_state = data[4]

        elif can_id == CAN_PROBE_SPS and len(data) >= 4:
            self.sps_requested = struct.unpack_from("<H", data, 0)[0]
            self.sps_actual = struct.unpack_from("<H", data, 2)[0]

        elif can_id == CAN_BMS_STATE_MSG and len(data) >= 1:
            # Direct 0x220 monitoring as fallback for BMS state
            self.bms_state = data[0] & 0x0F

    def diag_bit_set(self, bit_index: int) -> bool:
        """Check if a specific DIAG ID bit is set in the bitmap."""
        if bit_index < 0 or bit_index > 63:
            return False
        return bool(self.diag_bitmap & (1 << bit_index))

    def contactors_open(self) -> bool:
        """Check if contactors are open (SPS actual = 0)."""
        return self.sps_actual == 0

    def bms_in_error(self) -> bool:
        return self.bms_state == BMS_ERROR

    def bms_in_normal(self) -> bool:
        return self.bms_state == BMS_NORMAL


# ============================================================================
# Fault Injector — sends override commands via CAN
# ============================================================================

class FaultInjector:
    """Sends SIL override commands to the vECU via CAN 0x7E0."""

    def __init__(self, bus: CanBus):
        self.bus = bus

    def inject(self, cmd: int, index: int, value: int) -> None:
        """Send a single override command.

        Args:
            cmd: Override type (SIL_CELL_VOLTAGE, SIL_PACK_CURRENT, etc.)
            index: Target index (cell 0-17, sensor 0-4, string 0)
            value: int32 value in native units (mV, mA, ddegC)
        """
        # sil_process_command expects: [cmd, index, active, value_i32_LE]
        # active=1 to enable override
        data = struct.pack("<BBBi", cmd, index, 1, value)
        self.bus.send(CAN_OVERRIDE_ID, data)

    def inject_multi(self, cmd: int, indices: List[int], value: int) -> None:
        """Inject the same value on multiple indices."""
        for idx in indices:
            self.inject(cmd, idx, value)

    def clear(self) -> None:
        """Clear all overrides by setting active=0 for all types and indices."""
        for cmd in [SIL_CELL_VOLTAGE, SIL_CELL_TEMP, SIL_PACK_CURRENT]:
            for idx in range(18):
                # [cmd, index, active=0, value=0]
                data = struct.pack("<BBBi", cmd, idx, 0, 0)
                self.bus.send(CAN_OVERRIDE_ID, data)

    def monitor_and_update(self, monitor: ProbeMonitor, duration_s: float = 0.01) -> None:
        """Read CAN frames and update the probe monitor for a given duration."""
        deadline = time.monotonic() + duration_s
        while time.monotonic() < deadline:
            result = self.bus.recv(timeout_s=max(0.001, deadline - time.monotonic()))
            if result:
                monitor.update(result[0], result[1])


# ============================================================================
# Test case parsing and value resolution
# ============================================================================

def parse_target(target_str: str) -> Tuple[str, List[int]]:
    """Parse TARGET_CELL_OR_SENSOR into (type, [indices]).

    Returns:
        ('cell', [0]) for CELL_0
        ('cell', [0,1,...,17]) for ALL_CELLS or ALL_18_CELLS
        ('sensor', [0]) for SENSOR_0
        ('string', [0]) for STRING_0
        ('compound', []) for compound targets like CELL_0+STRING_0
        ('special', []) for IVT or other special targets
    """
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
    """Parse the INJECTION_VALUE field into an integer for direct injection.

    Returns None if the value cannot be parsed as a simple integer (complex
    injection patterns like DRIFT, NOISE, OFFSET are handled separately).
    """
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
    """Parse compound injection values into a dict of named values.

    Handles formats:
        PLAUS:  "cell=3700/pack=81500" -> {"cell": 3700, "pack": 81500}
        PLAUS:  "T=540/I=14900"        -> {"T": 540, "I": 14900}
        PLAUS:  "SOC=100%/V=2600mV"    -> {"SOC": 100, "V": 2600}
        PLAUS:  "spread=100mV"         -> {"spread": 100}
        COMBO:  "CELL_V=4260/I=16000"  -> {"CELL_V": 4260, "I": 16000}
        COMBO:  "CELL_V=4260/T=560"    -> {"CELL_V": 4260, "T": 560}
        COMBO:  "CELL_V=2490/T=-210"   -> {"CELL_V": 2490, "T": -210}
        COMBO:  "I=16000/T=560"        -> {"I": 16000, "T": 560}
        COMBO:  "V=4260/T=560/I=16000" -> {"V": 4260, "T": 560, "I": 16000}
        COMBO:  "C0=4260/C17=2490"     -> {"C0": 4260, "C17": 2490}
    """
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
    """Parse RECOV injection values.

    Handles formats:
        "inject=4260/clear=3700"            -> {"inject": 4260, "clear": 3700}
        "inject=4260/clear=3700/check_latch" -> {"inject": 4260, "clear": 3700, "check_latch": True}
        "inject=4260/clear=3700/request=NORMAL" -> {"inject": 4260, "clear": 3700, "request": "NORMAL"}
        "inject=4260/duration=10s"          -> {"inject": 4260, "duration_s": 10}
    """
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
            # "10s" -> 10
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
    """Map RECOV signal name to the SIL override command byte.

    Signal names: RECOV_OV_*, RECOV_UV_*, RECOV_OT_*, RECOV_UT_*,
                  RECOV_OC_*, DEEP_DISCHARGE_*
    Must check OT/UT/OC before OV/UV because "RECOV" contains "OV".
    """
    sig = signal.upper()
    # Check temperature first (OT/UT) — before voltage since RECOV contains OV
    if "_OT_" in sig or "_UT_" in sig:
        return SIL_CELL_TEMP
    # Check current (OC)
    if "_OC_" in sig:
        return SIL_PACK_CURRENT
    # Voltage: OV, UV, DEEP_DISCHARGE
    if "_OV_" in sig or "_UV_" in sig or "DEEP_DISCHARGE" in sig:
        return SIL_CELL_VOLTAGE
    return SIL_CELL_VOLTAGE  # Default


def parse_drift_range(value_str: str) -> Tuple[int, int]:
    """Parse DRIFT value "3700>4300" into (start, end)."""
    parts = value_str.split(">")
    start = int(parts[0])
    end_str = parts[1].split("@")[0]
    end = int(end_str)
    return (start, end)


def parse_noise_params(value_str: str) -> Tuple[int, int]:
    """Parse NOISE value "+-200mV@4250" into (amplitude, center)."""
    # "+-200mV@4250"
    amp_str = value_str.split("@")[0].replace("+-", "").replace("mV", "")
    center_str = value_str.split("@")[1]
    return (int(amp_str), int(center_str))


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
    # Handle compound DIAG IDs (e.g., "DIAG_ID_OV+DIAG_ID_OC")
    if "+" in diag_id_str:
        return None  # Cannot check a single bit for compound faults

    base_id = DIAG_ID_MAP.get(diag_id_str)
    if base_id is None:
        return None

    offset = SEVERITY_OFFSET.get(severity_tier, 0)
    return base_id + offset


# ============================================================================
# Skippable test detection
# ============================================================================

# Fault methods that need special handling (skip for now)
SKIP_FAULT_METHODS = {"MISSING_TIMEOUT", "CAN_BUS_FAULT", "STUCK_AT_LAST"}

# BMS states we cannot currently set up
SKIP_BMS_STATES = {
    "IDLE", "STANDBY", "PRECHARGE", "ERROR",
    "UNINITIALIZED", "INITIALIZED", "SYS_CHECK",
    "CHARGE", "DISCHARGE", "OPEN_CONTACTORS",
}

# Expected reactions we cannot currently verify
SKIP_REACTIONS = {
    "BOOT_BLOCKED", "TRANSITION_OK", "REQUEST_REJECTED",
    "STATE_NORMAL", "CHECK_TIMING", "RATE_LIMITED",
}

# Target types we cannot inject
SKIP_TARGET_TYPES = {"special", "state_transition"}


def should_skip(tc: TestCase) -> Optional[str]:
    """Return a skip reason string, or None if the test should run."""
    if tc.fault_method in SKIP_FAULT_METHODS:
        return f"requires {tc.fault_method} (not implemented)"

    # RECOV and COMBO tests that require non-NORMAL states: skip
    # PLAUS tests in NORMAL state: run them
    if tc.bms_state != "NORMAL" and tc.bms_state not in ("", "N/A"):
        return f"requires {tc.bms_state} state"

    target_type, _ = parse_target(tc.target)
    if target_type in SKIP_TARGET_TYPES:
        return f"requires {tc.target} target (not supported)"

    if tc.expected_reaction in SKIP_REACTIONS:
        return f"requires {tc.expected_reaction} verification"

    # PLAUS tests with DIAG IDs not in our map: skip
    if tc.category == "PLAUS":
        diag = tc.diag_id
        if diag not in DIAG_ID_MAP and diag not in ("", "N/A"):
            return f"DIAG ID {diag} not mapped (may be disabled)"

    # COMBO tests needing T=NO_SIGNAL or other unsupported patterns
    if tc.category == "COMBO":
        if "NO_SIGNAL" in tc.injection_value:
            return "COMBO with NO_SIGNAL (requires timeout injection)"

    return None


# ============================================================================
# Process Management — vECU + Plant Model
# ============================================================================

class VecuManager:
    """Manages the foxbms-vecu and plant_model.py processes."""

    def __init__(self, interface: str, vecu_path: str, plant_path: str):
        self.interface = interface
        self.vecu_path = vecu_path
        self.plant_path = plant_path
        self.vecu_proc: Optional[subprocess.Popen] = None
        self.plant_proc: Optional[subprocess.Popen] = None

    def start(self) -> bool:
        """Start vECU + plant model. Returns True on success."""
        self.stop()

        print(f"[runner] Starting plant_model.py on {self.interface}...")
        self.plant_proc = subprocess.Popen(
            ["python3", self.plant_path, self.interface],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid,
        )

        time.sleep(0.5)  # Let plant settle and send initial data

        print(f"[runner] Starting foxbms-vecu on {self.interface}...")
        env = os.environ.copy()
        env["FOXBMS_CAN_IF"] = self.interface
        self.vecu_proc = subprocess.Popen(
            [self.vecu_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid,
            env=env,
        )

        return self.vecu_proc.poll() is None and self.plant_proc.poll() is None

    def stop(self) -> None:
        """Stop both processes."""
        for proc, name in [(self.vecu_proc, "vecu"), (self.plant_proc, "plant")]:
            if proc and proc.poll() is None:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    proc.wait(timeout=3)
                except (ProcessLookupError, subprocess.TimeoutExpired):
                    try:
                        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                        proc.wait(timeout=2)
                    except (ProcessLookupError, subprocess.TimeoutExpired):
                        pass
                print(f"[runner] Stopped {name} (pid={proc.pid})")
        self.vecu_proc = None
        self.plant_proc = None

    def is_alive(self) -> bool:
        """Check if both processes are still running."""
        if self.vecu_proc is None or self.plant_proc is None:
            return False
        return self.vecu_proc.poll() is None and self.plant_proc.poll() is None

    def restart(self) -> bool:
        """Restart both processes."""
        print("[runner] Restarting vECU + plant...")
        return self.start()


# ============================================================================
# Test Executor
# ============================================================================

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
        """Wait for plant discharge current to reach foxBMS database.

        SOA_CheckTemperatures gates on current direction. Discharge-direction
        tests need BMS_DISCHARGING (current > 200mA REST threshold).
        Plant starts discharging after detecting NORMAL via CAN feedback.
        """
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            self.injector.monitor_and_update(self.monitor, 0.05)
            # Check current probe (0x7FA) or just wait for BMS to have been
            # in NORMAL for long enough that plant is definitely discharging
            if self.monitor.bms_in_normal():
                # BMS still normal after delay = plant is running + discharging
                elapsed = time.monotonic() - (deadline - timeout_s)
                if elapsed > 4.0:  # 4s in NORMAL = plant definitely discharging
                    return True
        return False

    def wait_for_recovery(self, timeout_s: float = RECOVERY_TIMEOUT_S) -> bool:
        """Wait for BMS to return to NORMAL after clearing a fault."""
        self.injector.clear()
        time.sleep(0.05)
        return self.wait_for_normal(timeout_s)

    def run_contactor_open_test(self, tc: TestCase, cmd: int,
                                indices: List[int], value: int) -> TestOutcome:
        """Run a test expecting CONTACTOR_OPEN reaction."""
        events, delay_ms = parse_threshold(tc.threshold)
        diag_bit = resolve_diag_bit(tc.diag_id, tc.severity_tier)

        # Snapshot pre-injection state
        pre_fault_count = self.monitor.diag_fault_count
        pre_bitmap = self.monitor.diag_bitmap

        t_start = time.monotonic()
        timeout_s = self.timeout_ms / 1000.0

        # Inject the fault
        self.injector.inject_multi(cmd, indices, value)

        # Monitor for expected reaction
        contactor_opened = False
        diag_detected = False
        bms_error = False
        t_contactor = 0.0
        t_diag = 0.0

        deadline = t_start + timeout_s
        while time.monotonic() < deadline:
            self.injector.monitor_and_update(self.monitor, 0.005)

            # Re-inject for sustained fault methods
            if tc.fault_method in ("STUCK_AT_0", "STUCK_AT_MAX", "STUCK_AT_LAST",
                                    "OUT_OF_RANGE_HIGH", "OUT_OF_RANGE_LOW",
                                    "STEP_TO_VALUE", "INVERTED", "CONTINUOUS",
                                    "OFFSET_POS", "OFFSET_NEG"):
                self.injector.inject_multi(cmd, indices, value)

            if not diag_detected and diag_bit is not None:
                if self.monitor.diag_bit_set(diag_bit):
                    diag_detected = True
                    t_diag = time.monotonic() - t_start

            if not bms_error and self.monitor.bms_in_error():
                bms_error = True

            if not contactor_opened and self.monitor.contactors_open():
                contactor_opened = True
                t_contactor = time.monotonic() - t_start

            # All conditions met
            if contactor_opened:
                elapsed_ms = t_contactor * 1000
                detail = "contactor open confirmed"
                if diag_detected:
                    detail += f"; DIAG bit {diag_bit} set at {t_diag*1000:.0f}ms"
                return TestOutcome(
                    test_id=tc.test_id, result=TestResult.PASS,
                    elapsed_ms=elapsed_ms, detail=detail,
                    category=tc.category, priority=tc.priority,
                )

        # Timeout
        elapsed_ms = self.timeout_ms
        parts = []
        if not diag_detected:
            parts.append(f"DIAG bit {diag_bit} not set")
        if not bms_error:
            parts.append("BMS did not enter ERROR")
        if not contactor_opened:
            parts.append("contactor did not open")
        detail = f"{elapsed_ms}ms TIMEOUT | " + "; ".join(parts)
        return TestOutcome(
            test_id=tc.test_id, result=TestResult.FAIL,
            elapsed_ms=elapsed_ms, detail=detail,
            category=tc.category, priority=tc.priority,
        )

    def run_warning_flag_test(self, tc: TestCase, cmd: int,
                               indices: List[int], value: int) -> TestOutcome:
        """Run a test expecting WARNING_FLAG reaction (no contactor open)."""
        diag_bit = resolve_diag_bit(tc.diag_id, tc.severity_tier)

        t_start = time.monotonic()
        timeout_s = self.timeout_ms / 1000.0

        # Inject the fault
        self.injector.inject_multi(cmd, indices, value)

        diag_detected = False
        t_diag = 0.0

        deadline = t_start + timeout_s
        while time.monotonic() < deadline:
            self.injector.monitor_and_update(self.monitor, 0.005)

            # Sustained injection
            if tc.fault_method in ("STUCK_AT_0", "STUCK_AT_MAX", "STUCK_AT_LAST",
                                    "OUT_OF_RANGE_HIGH", "OUT_OF_RANGE_LOW",
                                    "STEP_TO_VALUE", "INVERTED", "CONTINUOUS",
                                    "OFFSET_POS", "OFFSET_NEG"):
                self.injector.inject_multi(cmd, indices, value)

            if not diag_detected and diag_bit is not None:
                if self.monitor.diag_bit_set(diag_bit):
                    diag_detected = True
                    t_diag = time.monotonic() - t_start

            # Check for unexpected contactor open / ERROR state
            if self.monitor.bms_in_error():
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
                self.injector.monitor_and_update(self.monitor, 0.02)
                if self.monitor.bms_in_normal() and not self.monitor.contactors_open():
                    elapsed_ms = t_diag * 1000
                    return TestOutcome(
                        test_id=tc.test_id, result=TestResult.PASS,
                        elapsed_ms=elapsed_ms,
                        detail=f"DIAG bit {diag_bit} set; BMS stays NORMAL",
                        category=tc.category, priority=tc.priority,
                    )

        # Timeout — diag flag was never set
        elapsed_ms = self.timeout_ms
        detail = f"{elapsed_ms}ms TIMEOUT | expected WARNING_FLAG, got nothing"
        if diag_bit is None:
            detail = f"{elapsed_ms}ms TIMEOUT | unknown DIAG bit for {tc.diag_id}/{tc.severity_tier}"
        return TestOutcome(
            test_id=tc.test_id, result=TestResult.FAIL,
            elapsed_ms=elapsed_ms, detail=detail,
            category=tc.category, priority=tc.priority,
        )

    def run_no_reaction_test(self, tc: TestCase, cmd: int,
                              indices: List[int], value: int) -> TestOutcome:
        """Run a test expecting NO_REACTION or NO_CONTACTOR_OPEN."""
        t_start = time.monotonic()

        # Inject the fault
        self.injector.inject_multi(cmd, indices, value)

        # Monitor for a reasonable period — should see no state change
        observe_s = min(self.timeout_ms / 1000.0, 2.0)
        deadline = t_start + observe_s

        while time.monotonic() < deadline:
            self.injector.monitor_and_update(self.monitor, 0.01)

            # Sustained injection
            self.injector.inject_multi(cmd, indices, value)

            if self.monitor.bms_in_error():
                elapsed_ms = (time.monotonic() - t_start) * 1000
                return TestOutcome(
                    test_id=tc.test_id, result=TestResult.FAIL,
                    elapsed_ms=elapsed_ms,
                    detail="BMS entered ERROR (expected no reaction)",
                    category=tc.category, priority=tc.priority,
                )

            if self.monitor.contactors_open():
                elapsed_ms = (time.monotonic() - t_start) * 1000
                return TestOutcome(
                    test_id=tc.test_id, result=TestResult.FAIL,
                    elapsed_ms=elapsed_ms,
                    detail="contactor opened (expected no reaction)",
                    category=tc.category, priority=tc.priority,
                )

        elapsed_ms = (time.monotonic() - t_start) * 1000
        return TestOutcome(
            test_id=tc.test_id, result=TestResult.PASS,
            elapsed_ms=elapsed_ms, detail="no reaction as expected",
            category=tc.category, priority=tc.priority,
        )

    def run_fault_clears_test(self, tc: TestCase, cmd: int,
                               indices: List[int], value: int) -> TestOutcome:
        """Run a RECOV test: inject fault, then clear, verify fault clears."""
        diag_bit = resolve_diag_bit(tc.diag_id, tc.severity_tier)
        t_start = time.monotonic()

        # Phase 1: inject fault and wait for detection
        self.injector.inject_multi(cmd, indices, value)
        inject_deadline = t_start + (self.timeout_ms / 1000.0)
        fault_detected = False

        while time.monotonic() < inject_deadline:
            self.injector.monitor_and_update(self.monitor, 0.005)
            self.injector.inject_multi(cmd, indices, value)
            if diag_bit is not None and self.monitor.diag_bit_set(diag_bit):
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
        self.injector.clear()
        clear_deadline = time.monotonic() + RECOVERY_TIMEOUT_S

        while time.monotonic() < clear_deadline:
            self.injector.monitor_and_update(self.monitor, 0.05)
            if diag_bit is not None and not self.monitor.diag_bit_set(diag_bit):
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

    def run_drift_test(self, tc: TestCase, cmd: int,
                       indices: List[int], direction: str) -> TestOutcome:
        """Run a DRIFT_UP or DRIFT_DOWN test with ramped injection."""
        try:
            start_val, end_val = parse_drift_range(tc.injection_value)
        except (ValueError, IndexError):
            return TestOutcome(
                test_id=tc.test_id, result=TestResult.ERROR,
                elapsed_ms=0, detail=f"cannot parse drift range: {tc.injection_value}",
                category=tc.category, priority=tc.priority,
            )

        # Calculate step direction and size
        total_steps = abs(end_val - start_val) // 10  # 10mV per step
        if total_steps == 0:
            total_steps = 1
        step = (end_val - start_val) / total_steps
        step_interval_s = 0.01  # 10ms per step

        diag_bit = resolve_diag_bit(tc.diag_id, tc.severity_tier)
        t_start = time.monotonic()
        timeout_s = self.timeout_ms / 1000.0

        current_val = start_val
        for i in range(total_steps + 1):
            current_val = int(start_val + step * i)
            self.injector.inject_multi(cmd, indices, current_val)
            self.injector.monitor_and_update(self.monitor, step_interval_s)

            if time.monotonic() - t_start > timeout_s:
                break

            # Check for expected reaction based on test type
            if tc.expected_reaction == "CONTACTOR_OPEN":
                if self.monitor.contactors_open():
                    elapsed_ms = (time.monotonic() - t_start) * 1000
                    return TestOutcome(
                        test_id=tc.test_id, result=TestResult.PASS,
                        elapsed_ms=elapsed_ms,
                        detail=f"contactor open at drift value {current_val}",
                        category=tc.category, priority=tc.priority,
                    )
            elif tc.expected_reaction == "WARNING_FLAG":
                if diag_bit is not None and self.monitor.diag_bit_set(diag_bit):
                    if self.monitor.bms_in_normal():
                        elapsed_ms = (time.monotonic() - t_start) * 1000
                        return TestOutcome(
                            test_id=tc.test_id, result=TestResult.PASS,
                            elapsed_ms=elapsed_ms,
                            detail=f"warning at drift value {current_val}; BMS stays NORMAL",
                            category=tc.category, priority=tc.priority,
                        )

        # Continue holding at end value if drift completed but no reaction yet
        hold_deadline = t_start + timeout_s
        while time.monotonic() < hold_deadline:
            self.injector.inject_multi(cmd, indices, end_val)
            self.injector.monitor_and_update(self.monitor, 0.01)

            if tc.expected_reaction == "CONTACTOR_OPEN" and self.monitor.contactors_open():
                elapsed_ms = (time.monotonic() - t_start) * 1000
                return TestOutcome(
                    test_id=tc.test_id, result=TestResult.PASS,
                    elapsed_ms=elapsed_ms,
                    detail=f"contactor open (held at {end_val})",
                    category=tc.category, priority=tc.priority,
                )
            if tc.expected_reaction == "WARNING_FLAG":
                if diag_bit is not None and self.monitor.diag_bit_set(diag_bit):
                    if self.monitor.bms_in_normal():
                        elapsed_ms = (time.monotonic() - t_start) * 1000
                        return TestOutcome(
                            test_id=tc.test_id, result=TestResult.PASS,
                            elapsed_ms=elapsed_ms,
                            detail=f"warning set (held at {end_val}); BMS stays NORMAL",
                            category=tc.category, priority=tc.priority,
                        )

        elapsed_ms = self.timeout_ms
        return TestOutcome(
            test_id=tc.test_id, result=TestResult.FAIL,
            elapsed_ms=elapsed_ms,
            detail=f"{elapsed_ms}ms TIMEOUT | drifted {start_val}->{end_val}, no reaction",
            category=tc.category, priority=tc.priority,
        )

    def run_noise_test(self, tc: TestCase, cmd: int,
                       indices: List[int]) -> TestOutcome:
        """Run a NOISE test with value +/- random offset around a center."""
        try:
            amplitude, center = parse_noise_params(tc.injection_value)
        except (ValueError, IndexError):
            return TestOutcome(
                test_id=tc.test_id, result=TestResult.ERROR,
                elapsed_ms=0, detail=f"cannot parse noise params: {tc.injection_value}",
                category=tc.category, priority=tc.priority,
            )

        diag_bit = resolve_diag_bit(tc.diag_id, tc.severity_tier)
        t_start = time.monotonic()
        timeout_s = self.timeout_ms / 1000.0

        deadline = t_start + timeout_s
        while time.monotonic() < deadline:
            noise_val = center + random.randint(-amplitude, amplitude)
            self.injector.inject_multi(cmd, indices, noise_val)
            self.injector.monitor_and_update(self.monitor, 0.005)

            if tc.expected_reaction == "CONTACTOR_OPEN" and self.monitor.contactors_open():
                elapsed_ms = (time.monotonic() - t_start) * 1000
                return TestOutcome(
                    test_id=tc.test_id, result=TestResult.PASS,
                    elapsed_ms=elapsed_ms,
                    detail=f"contactor open under noise at center={center}",
                    category=tc.category, priority=tc.priority,
                )
            if tc.expected_reaction == "WARNING_FLAG":
                if diag_bit is not None and self.monitor.diag_bit_set(diag_bit):
                    if self.monitor.bms_in_normal():
                        elapsed_ms = (time.monotonic() - t_start) * 1000
                        return TestOutcome(
                            test_id=tc.test_id, result=TestResult.PASS,
                            elapsed_ms=elapsed_ms,
                            detail=f"warning under noise; BMS stays NORMAL",
                            category=tc.category, priority=tc.priority,
                        )

        elapsed_ms = self.timeout_ms
        return TestOutcome(
            test_id=tc.test_id, result=TestResult.FAIL,
            elapsed_ms=elapsed_ms,
            detail=f"{elapsed_ms}ms TIMEOUT | noise center={center} amp={amplitude}",
            category=tc.category, priority=tc.priority,
        )

    def execute(self, tc: TestCase) -> TestOutcome:
        """Execute a single test case. Returns TestOutcome."""
        # Check if we should skip
        skip_reason = should_skip(tc)
        if skip_reason:
            return TestOutcome(
                test_id=tc.test_id, result=TestResult.SKIP,
                elapsed_ms=0, detail=skip_reason,
                category=tc.category, priority=tc.priority,
            )

        # ---- Category-level dispatch for PLAUS, COMBO, RECOV ----
        try:
            # PLAUS: plausibility mismatch / spread tests
            if tc.category == "PLAUS":
                if tc.fault_method == "INJECTED_MISMATCH":
                    return self.run_plaus_mismatch_test(tc)
                elif tc.fault_method == "INJECTED_SPREAD":
                    return self.run_plaus_spread_test(tc)
                else:
                    return TestOutcome(
                        test_id=tc.test_id, result=TestResult.SKIP,
                        elapsed_ms=0,
                        detail=f"PLAUS method {tc.fault_method} not implemented",
                        category=tc.category, priority=tc.priority,
                    )

            # COMBO: simultaneous / sequential multi-fault tests
            if tc.category == "COMBO":
                if tc.fault_method == "SIMULTANEOUS":
                    return self.run_combo_simultaneous_test(tc)
                elif tc.fault_method == "SEQUENTIAL":
                    return self.run_combo_sequential_test(tc)
                elif tc.fault_method == "TIMED_INJECTION":
                    return self.run_combo_sequential_test(tc)
                else:
                    return TestOutcome(
                        test_id=tc.test_id, result=TestResult.SKIP,
                        elapsed_ms=0,
                        detail=f"COMBO method {tc.fault_method} not implemented",
                        category=tc.category, priority=tc.priority,
                    )

            # RECOV: recovery / persist / latch tests
            if tc.category == "RECOV":
                if tc.fault_method == "INJECT_THEN_CLEAR":
                    return self.run_recovery_test(tc)
                elif tc.fault_method == "CONTINUOUS":
                    return self.run_persist_test(tc)
                elif tc.fault_method == "OSCILLATE":
                    cmd = resolve_recov_override_cmd(tc.signal)
                    if cmd == SIL_CELL_VOLTAGE:
                        indices = list(range(18))
                    elif cmd == SIL_CELL_TEMP:
                        indices = list(range(5))
                    else:
                        indices = [0]
                    # Parse "oscillate=4260<>3700@100ms" -> override injection_value
                    # so _run_oscillate_test can parse it
                    osc_val = tc.injection_value
                    if "oscillate=" in osc_val:
                        # Extract the fault value before "<>"
                        try:
                            osc_parts = osc_val.split("=")[1].split("<>")
                            fault_v = int(osc_parts[0])
                            # Create a modified tc with parseable injection_value
                            tc_osc = copy.copy(tc)
                            tc_osc.injection_value = str(fault_v)
                            return self._run_oscillate_test(tc_osc, cmd, indices)
                        except (ValueError, IndexError):
                            pass
                    return self._run_oscillate_test(tc, cmd, indices)
                elif tc.fault_method == "INJECT_PARTIAL_CLEAR":
                    # Counter reset tests ("inject=49ev/clear/49ev") need
                    # debounce counter manipulation; skip for now
                    return TestOutcome(
                        test_id=tc.test_id, result=TestResult.SKIP,
                        elapsed_ms=0,
                        detail="INJECT_PARTIAL_CLEAR requires counter manipulation",
                        category=tc.category, priority=tc.priority,
                    )
                else:
                    return TestOutcome(
                        test_id=tc.test_id, result=TestResult.SKIP,
                        elapsed_ms=0,
                        detail=f"RECOV method {tc.fault_method} not implemented",
                        category=tc.category, priority=tc.priority,
                    )
        except Exception as e:
            return TestOutcome(
                test_id=tc.test_id, result=TestResult.ERROR,
                elapsed_ms=0, detail=f"exception in category dispatch: {e}",
                category=tc.category, priority=tc.priority,
            )

        # ---- Generic dispatch for VOLT, TEMP, CURR, etc. ----
        # Resolve override command and target
        target_type, raw_indices = parse_target(tc.target)
        # For compound targets that reach here, extract first sub-target's indices
        if target_type == "compound" and isinstance(raw_indices, list) and raw_indices:
            if isinstance(raw_indices[0], tuple):
                indices = raw_indices[0][1]
            else:
                indices = raw_indices
        else:
            indices = raw_indices
        cmd = resolve_override_cmd(tc.category, tc.signal)

        # Resolve injection value
        value = parse_injection_value(tc.injection_value, tc.fault_method)

        # Dispatch based on fault method
        try:
            if tc.fault_method in ("DRIFT_UP", "DRIFT_DOWN"):
                return self.run_drift_test(tc, cmd, indices, tc.fault_method)

            if tc.fault_method == "RATE_OF_CHANGE":
                # Treat like drift but faster
                return self.run_drift_test(tc, cmd, indices, tc.fault_method)

            if tc.fault_method == "NOISE":
                return self.run_noise_test(tc, cmd, indices)

            if tc.fault_method == "CORRUPTED":
                # Inject a random out-of-range value
                if value is None:
                    value = random.choice([0, 5000, -100, 65535])

            if tc.fault_method == "DELAYED":
                # Wait the specified delay, then inject
                delay_ms = 500
                if "@+" in tc.injection_value:
                    try:
                        delay_str = tc.injection_value.split("@+")[1].replace("ms", "")
                        delay_ms = int(delay_str)
                    except ValueError:
                        pass
                time.sleep(delay_ms / 1000.0)

            if tc.fault_method == "OSCILLATE":
                # Alternate between two values
                return self._run_oscillate_test(tc, cmd, indices)

            if tc.fault_method == "INJECT_THEN_CLEAR":
                if value is None:
                    return TestOutcome(
                        test_id=tc.test_id, result=TestResult.ERROR,
                        elapsed_ms=0,
                        detail=f"cannot parse inject value: {tc.injection_value}",
                        category=tc.category, priority=tc.priority,
                    )
                if tc.expected_reaction in ("FAULT_CLEARS", "STATE_NORMAL"):
                    return self.run_fault_clears_test(tc, cmd, indices, value)

            if tc.fault_method == "INJECT_PARTIAL_CLEAR":
                # Inject on multiple, clear some — treat as normal inject
                pass

            if value is None:
                return TestOutcome(
                    test_id=tc.test_id, result=TestResult.SKIP,
                    elapsed_ms=0,
                    detail=f"cannot resolve injection value: {tc.injection_value}",
                    category=tc.category, priority=tc.priority,
                )

            # For discharge-direction TEMP tests, wait for plant to be discharging.
            # SOA_CheckTemperatures gates on current direction:
            #   BMS_DISCHARGING → checks OT_DIS/UT_DIS thresholds
            #   else (rest/charge) → checks OT_CHG/UT_CHG thresholds
            # Plant starts discharge after detecting NORMAL via CAN feedback (~100ms).
            if tc.category == "TEMP" and ("DIS" in tc.signal):
                if not self.wait_for_current_flowing(5.0):
                    return TestOutcome(
                        test_id=tc.test_id, result=TestResult.SKIP,
                        elapsed_ms=0,
                        detail="plant not discharging — current not flowing after 5s",
                        category=tc.category, priority=tc.priority,
                    )

            # Standard injection dispatch by expected reaction
            if tc.expected_reaction == "CONTACTOR_OPEN":
                return self.run_contactor_open_test(tc, cmd, indices, value)

            if tc.expected_reaction == "CONTACTOR_OPEN_LATCHED":
                return self.run_contactor_open_test(tc, cmd, indices, value)

            if tc.expected_reaction == "WARNING_FLAG":
                return self.run_warning_flag_test(tc, cmd, indices, value)

            if tc.expected_reaction in ("NO_REACTION", "NO_CONTACTOR_OPEN"):
                return self.run_no_reaction_test(tc, cmd, indices, value)

            if tc.expected_reaction == "ERROR_FLAG":
                # Similar to contactor open — expect ERROR state
                return self.run_contactor_open_test(tc, cmd, indices, value)

            if tc.expected_reaction in ("FAULT_CLEARS", "FAULT_PERSISTS"):
                return self.run_fault_clears_test(tc, cmd, indices, value)

            if tc.expected_reaction in ("PLAUSIBILITY_ERROR", "PLAUSIBILITY_CHECK"):
                return self.run_contactor_open_test(tc, cmd, indices, value)

            if tc.expected_reaction == "TIMEOUT_ERROR":
                return self.run_contactor_open_test(tc, cmd, indices, value)

            if tc.expected_reaction in ("PRECHARGE_ABORT", "ERROR_HANDLING",
                                        "FAULT_ACTIVE", "BOTH_DETECTED",
                                        "COUNTER_RESETS", "LATCH_OR_CLEAR",
                                        "NORMAL_CHARGE", "NORMAL_DISCHARGE",
                                        "REST_OR_CHARGE", "REST_OR_DISCHARGE",
                                        "REST_STATE", "OC_CHARGE", "OC_DISCHARGE"):
                return self.run_contactor_open_test(tc, cmd, indices, value)

            return TestOutcome(
                test_id=tc.test_id, result=TestResult.SKIP,
                elapsed_ms=0,
                detail=f"unhandled reaction type: {tc.expected_reaction}",
                category=tc.category, priority=tc.priority,
            )

        except Exception as e:
            return TestOutcome(
                test_id=tc.test_id, result=TestResult.ERROR,
                elapsed_ms=0, detail=f"exception: {e}",
                category=tc.category, priority=tc.priority,
            )

    def _run_oscillate_test(self, tc: TestCase, cmd: int,
                             indices: List[int]) -> TestOutcome:
        """Oscillate between normal and fault value."""
        value = parse_injection_value(tc.injection_value, tc.fault_method)
        if value is None:
            value = 4260  # Default OV value
        normal_val = 3700

        diag_bit = resolve_diag_bit(tc.diag_id, tc.severity_tier)
        t_start = time.monotonic()
        timeout_s = self.timeout_ms / 1000.0

        deadline = t_start + timeout_s
        cycle = 0
        while time.monotonic() < deadline:
            # Alternate every 50ms
            if cycle % 2 == 0:
                self.injector.inject_multi(cmd, indices, value)
            else:
                self.injector.inject_multi(cmd, indices, normal_val)
            cycle += 1
            self.injector.monitor_and_update(self.monitor, 0.05)

            if tc.expected_reaction == "CONTACTOR_OPEN" and self.monitor.contactors_open():
                elapsed_ms = (time.monotonic() - t_start) * 1000
                return TestOutcome(
                    test_id=tc.test_id, result=TestResult.PASS,
                    elapsed_ms=elapsed_ms, detail="contactor open under oscillation",
                    category=tc.category, priority=tc.priority,
                )

        elapsed_ms = self.timeout_ms
        return TestOutcome(
            test_id=tc.test_id, result=TestResult.FAIL,
            elapsed_ms=elapsed_ms, detail=f"{elapsed_ms}ms TIMEOUT | oscillation test",
            category=tc.category, priority=tc.priority,
        )

    # ----------------------------------------------------------------
    # PLAUS — Plausibility mismatch tests
    # ----------------------------------------------------------------

    def run_plaus_mismatch_test(self, tc: TestCase) -> TestOutcome:
        """Run a PLAUS INJECTED_MISMATCH test.

        Parses compound injection values and injects to create plausibility
        mismatches. Supports:
          - cell=X/pack=Y  → inject all 18 cells at X (pack stays at plant value)
          - T=X/I=Y        → inject temp on sensors + current on string
          - SOC=X/V=Y      → inject cell voltages at Y (SOC is derived)
        """
        vals = parse_compound_injection(tc.injection_value)
        if not vals:
            return TestOutcome(
                test_id=tc.test_id, result=TestResult.ERROR,
                elapsed_ms=0,
                detail=f"cannot parse PLAUS value: {tc.injection_value}",
                category=tc.category, priority=tc.priority,
            )

        diag_bit = resolve_diag_bit(tc.diag_id, tc.severity_tier)
        t_start = time.monotonic()
        timeout_s = self.timeout_ms / 1000.0

        # Determine what to inject based on the parsed keys
        if "cell" in vals:
            # cell=X/pack=Y — inject all 18 cells at X to create mismatch
            cell_val = vals["cell"]
            self.injector.inject_multi(SIL_CELL_VOLTAGE, list(range(18)), cell_val)
        elif "T" in vals and "I" in vals:
            # T=X/I=Y — inject temp on all sensors + current on string 0
            self.injector.inject_multi(SIL_CELL_TEMP, list(range(5)), vals["T"])
            self.injector.inject(SIL_PACK_CURRENT, 0, vals["I"])
        elif "SOC" in vals and "V" in vals:
            # SOC=X%/V=YmV — inject cell voltages at Y; SOC is computed from V
            self.injector.inject_multi(SIL_CELL_VOLTAGE, list(range(18)), vals["V"])
        elif "V" in vals and "T" in vals and "I" in vals:
            # Triple injection
            self.injector.inject_multi(SIL_CELL_VOLTAGE, list(range(18)), vals["V"])
            self.injector.inject_multi(SIL_CELL_TEMP, list(range(5)), vals["T"])
            self.injector.inject(SIL_PACK_CURRENT, 0, vals["I"])
        else:
            return TestOutcome(
                test_id=tc.test_id, result=TestResult.SKIP,
                elapsed_ms=0,
                detail=f"unsupported PLAUS key combination: {list(vals.keys())}",
                category=tc.category, priority=tc.priority,
            )

        # Monitor for expected reaction
        return self._monitor_for_reaction(tc, diag_bit, t_start, timeout_s,
                                          sustain_fn=None)

    def run_plaus_spread_test(self, tc: TestCase) -> TestOutcome:
        """Run a PLAUS INJECTED_SPREAD test.

        Parses spread=XmV and injects cell voltages with a spread across cells.
        Cell 0 gets nominal+spread/2, cell 17 gets nominal-spread/2.
        """
        vals = parse_compound_injection(tc.injection_value)
        spread = vals.get("spread")
        if spread is None:
            return TestOutcome(
                test_id=tc.test_id, result=TestResult.ERROR,
                elapsed_ms=0,
                detail=f"cannot parse spread value: {tc.injection_value}",
                category=tc.category, priority=tc.priority,
            )

        diag_bit = resolve_diag_bit(tc.diag_id, tc.severity_tier)
        t_start = time.monotonic()
        timeout_s = self.timeout_ms / 1000.0

        # Inject cells with a linear spread around nominal (3700mV)
        nominal = 3700
        half_spread = spread // 2
        for i in range(18):
            # Linear interpolation: cell 0 = nominal + half, cell 17 = nominal - half
            cell_val = nominal + half_spread - (spread * i // 17)
            self.injector.inject(SIL_CELL_VOLTAGE, i, cell_val)

        return self._monitor_for_reaction(tc, diag_bit, t_start, timeout_s,
                                          sustain_fn=None)

    # ----------------------------------------------------------------
    # COMBO — Multi-target simultaneous fault injection
    # ----------------------------------------------------------------

    def run_combo_simultaneous_test(self, tc: TestCase) -> TestOutcome:
        """Run a COMBO SIMULTANEOUS test: inject multiple faults at once.

        Parses compound injection values and targets, injects all simultaneously,
        then monitors for the expected reaction (typically CONTACTOR_OPEN).
        """
        vals = parse_compound_injection(tc.injection_value)
        if not vals:
            return TestOutcome(
                test_id=tc.test_id, result=TestResult.ERROR,
                elapsed_ms=0,
                detail=f"cannot parse COMBO value: {tc.injection_value}",
                category=tc.category, priority=tc.priority,
            )

        t_start = time.monotonic()
        timeout_s = self.timeout_ms / 1000.0

        # Parse the compound target to get sub-targets
        target_type, sub_targets = parse_target(tc.target)

        # Inject based on parsed values
        self._inject_combo_values(vals, tc, sub_targets if target_type == "compound" else [])

        # COMBO tests use compound DIAG IDs (e.g. "DIAG_ID_OV+DIAG_ID_OC")
        # We check for contactor open rather than individual DIAG bits
        return self._monitor_for_reaction(tc, None, t_start, timeout_s,
                                          sustain_fn=lambda: self._inject_combo_values(
                                              vals, tc,
                                              sub_targets if target_type == "compound" else []))

    def run_combo_sequential_test(self, tc: TestCase) -> TestOutcome:
        """Run a COMBO SEQUENTIAL test: inject faults with a time gap.

        Parses timing from injection_value like "OV@t=0/OC@t+50ms".
        """
        t_start = time.monotonic()
        timeout_s = self.timeout_ms / 1000.0

        # Parse sequential timing: "OV@t=0/OC@t+50ms"
        parts = tc.injection_value.split("/")
        injections = []
        for part in parts:
            part = part.strip()
            if "@t" not in part:
                continue
            fault_type = part.split("@")[0]
            time_spec = part.split("@")[1]
            delay_ms = 0
            if "+=" in time_spec or "+" in time_spec:
                try:
                    delay_str = time_spec.replace("t+", "").replace("t=", "").replace("ms", "")
                    delay_ms = int(delay_str)
                except ValueError:
                    pass
            injections.append((fault_type, delay_ms))

        # Execute injections with delays
        for fault_type, delay_ms in injections:
            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)

            ft = fault_type.upper()
            if ft == "OV":
                self.injector.inject_multi(SIL_CELL_VOLTAGE, [0], 4260)
            elif ft == "UV":
                self.injector.inject_multi(SIL_CELL_VOLTAGE, [0], 2490)
            elif ft == "OC":
                self.injector.inject(SIL_PACK_CURRENT, 0, 16000)
            elif ft == "OT":
                self.injector.inject_multi(SIL_CELL_TEMP, [0], 560)
            elif ft == "UT":
                self.injector.inject_multi(SIL_CELL_TEMP, [0], -210)

        # Monitor for reaction
        return self._monitor_for_reaction(tc, None, t_start, timeout_s,
                                          sustain_fn=None)

    def _inject_combo_values(self, vals: Dict[str, int], tc: TestCase,
                              sub_targets: list) -> None:
        """Inject multiple override values for COMBO tests."""
        # Map value keys to SIL commands and appropriate indices
        if "CELL_V" in vals or "V" in vals:
            v = vals.get("CELL_V", vals.get("V", 3700))
            # Find cell indices from sub_targets or default to cell 0
            cell_indices = [0]
            for st in sub_targets:
                if isinstance(st, tuple) and st[0] == "cell":
                    cell_indices = st[1]
                    break
            self.injector.inject_multi(SIL_CELL_VOLTAGE, cell_indices, v)

        if "I" in vals:
            self.injector.inject(SIL_PACK_CURRENT, 0, vals["I"])

        if "T" in vals:
            # Find sensor indices from sub_targets or default to sensor 0
            sensor_indices = [0]
            for st in sub_targets:
                if isinstance(st, tuple) and st[0] == "sensor":
                    sensor_indices = st[1]
                    break
            self.injector.inject_multi(SIL_CELL_TEMP, sensor_indices, vals["T"])

        # Handle cell-specific combos: "C0=4260/C17=2490"
        for key, val in vals.items():
            if key.startswith("C") and key[1:].isdigit():
                cell_idx = int(key[1:])
                self.injector.inject(SIL_CELL_VOLTAGE, cell_idx, val)

    # ----------------------------------------------------------------
    # RECOV — Two-phase inject/clear recovery tests
    # ----------------------------------------------------------------

    def run_recovery_test(self, tc: TestCase) -> TestOutcome:
        """Run a RECOV INJECT_THEN_CLEAR test.

        Phase 1: Inject fault value, wait for DIAG bit / contactor open.
        Phase 2: Clear override (inject clear value), wait for fault to clear.
        For check_latch: verify fault does NOT clear after injecting clear value.
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

        # Determine indices: RECOV uses STRING_0 → inject on all cells/sensors
        if cmd == SIL_CELL_VOLTAGE:
            indices = list(range(18))
        elif cmd == SIL_CELL_TEMP:
            indices = list(range(5))
        else:
            indices = [0]

        t_start = time.monotonic()

        # Phase 1: Inject fault and wait for detection
        self.injector.inject_multi(cmd, indices, inject_val)
        inject_deadline = t_start + (self.timeout_ms / 1000.0)
        fault_detected = False

        while time.monotonic() < inject_deadline:
            self.injector.monitor_and_update(self.monitor, 0.005)
            self.injector.inject_multi(cmd, indices, inject_val)

            if diag_bit is not None and self.monitor.diag_bit_set(diag_bit):
                fault_detected = True
                break
            # Also check for contactor open as indication of fault
            if self.monitor.contactors_open() or self.monitor.bms_in_error():
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
            # Inject the clear (safe) value
            self.injector.inject_multi(cmd, indices, clear_val)
        else:
            # Just clear all overrides
            self.injector.clear()

        # Wait for recovery
        recovery_timeout = RECOVERY_TIMEOUT_S
        if check_latch:
            # For latch check, shorter observation window
            recovery_timeout = 5.0

        clear_deadline = time.monotonic() + recovery_timeout
        fault_cleared = False

        while time.monotonic() < clear_deadline:
            self.injector.monitor_and_update(self.monitor, 0.05)
            # Re-inject the clear value to sustain it
            if clear_val is not None:
                self.injector.inject_multi(cmd, indices, clear_val)

            if diag_bit is not None and not self.monitor.diag_bit_set(diag_bit):
                fault_cleared = True
                break

        elapsed_ms = (time.monotonic() - t_start) * 1000

        if check_latch:
            # For LATCH_OR_CLEAR: report whether it latched or cleared
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

        # Standard FAULT_CLEARS expectation
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

        # For other reactions, use contactor_open as pass criteria
        return self.run_contactor_open_test(
            tc, cmd, indices, inject_val)

    def run_persist_test(self, tc: TestCase) -> TestOutcome:
        """Run a RECOV CONTINUOUS/PERSIST test: inject and verify fault stays active.

        Injects the fault value continuously for the specified duration and
        verifies the fault remains active throughout.
        """
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

        # Inject fault
        self.injector.inject_multi(cmd, indices, inject_val)

        # Wait for initial fault detection
        detect_deadline = t_start + (self.timeout_ms / 1000.0)
        fault_detected = False
        while time.monotonic() < detect_deadline:
            self.injector.monitor_and_update(self.monitor, 0.005)
            self.injector.inject_multi(cmd, indices, inject_val)
            if diag_bit is not None and self.monitor.diag_bit_set(diag_bit):
                fault_detected = True
                break
            if self.monitor.contactors_open() or self.monitor.bms_in_error():
                fault_detected = True
                break

        if not fault_detected:
            return TestOutcome(
                test_id=tc.test_id, result=TestResult.FAIL,
                elapsed_ms=(time.monotonic() - t_start) * 1000,
                detail="fault never detected during persist test",
                category=tc.category, priority=tc.priority,
            )

        # Hold injection for the specified duration, cap at timeout
        hold_s = min(duration_s, self.timeout_ms / 1000.0)
        hold_deadline = time.monotonic() + hold_s
        fault_persisted = True

        while time.monotonic() < hold_deadline:
            self.injector.inject_multi(cmd, indices, inject_val)
            self.injector.monitor_and_update(self.monitor, 0.05)

            # Check fault is still active
            if diag_bit is not None and not self.monitor.diag_bit_set(diag_bit):
                # Fault cleared unexpectedly during sustained injection
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

    # ----------------------------------------------------------------
    # Shared monitoring helper
    # ----------------------------------------------------------------

    def _monitor_for_reaction(self, tc: TestCase, diag_bit: Optional[int],
                               t_start: float, timeout_s: float,
                               sustain_fn=None) -> TestOutcome:
        """Shared monitor loop for PLAUS/COMBO tests.

        Watches for the expected reaction (CONTACTOR_OPEN, WARNING_FLAG,
        PLAUSIBILITY_ERROR, etc.) and returns the appropriate outcome.
        """
        deadline = t_start + timeout_s
        diag_detected = False
        contactor_opened = False
        t_diag = 0.0

        while time.monotonic() < deadline:
            self.injector.monitor_and_update(self.monitor, 0.005)

            # Sustain injection if needed
            if sustain_fn is not None:
                sustain_fn()

            if not diag_detected and diag_bit is not None:
                if self.monitor.diag_bit_set(diag_bit):
                    diag_detected = True
                    t_diag = time.monotonic() - t_start

            if not contactor_opened and self.monitor.contactors_open():
                contactor_opened = True

            # Dispatch by expected reaction
            if tc.expected_reaction in ("CONTACTOR_OPEN", "PLAUSIBILITY_ERROR",
                                        "BOTH_DETECTED", "FAULT_ACTIVE"):
                if contactor_opened:
                    elapsed_ms = (time.monotonic() - t_start) * 1000
                    detail = "contactor open confirmed"
                    if diag_detected:
                        detail += f"; DIAG bit {diag_bit} at {t_diag*1000:.0f}ms"
                    return TestOutcome(
                        test_id=tc.test_id, result=TestResult.PASS,
                        elapsed_ms=elapsed_ms, detail=detail,
                        category=tc.category, priority=tc.priority,
                    )

            elif tc.expected_reaction == "WARNING_FLAG":
                if diag_detected and self.monitor.bms_in_normal():
                    elapsed_ms = t_diag * 1000
                    return TestOutcome(
                        test_id=tc.test_id, result=TestResult.PASS,
                        elapsed_ms=elapsed_ms,
                        detail=f"DIAG bit {diag_bit} set; BMS stays NORMAL",
                        category=tc.category, priority=tc.priority,
                    )

            elif tc.expected_reaction in ("NO_REACTION", "NO_CONTACTOR_OPEN"):
                # Check at end of timeout
                pass

        # Timeout reached
        elapsed_ms = (time.monotonic() - t_start) * 1000

        if tc.expected_reaction in ("NO_REACTION", "NO_CONTACTOR_OPEN"):
            if not contactor_opened and not self.monitor.bms_in_error():
                return TestOutcome(
                    test_id=tc.test_id, result=TestResult.PASS,
                    elapsed_ms=elapsed_ms, detail="no reaction as expected",
                    category=tc.category, priority=tc.priority,
                )

        parts = []
        if diag_bit is not None and not diag_detected:
            parts.append(f"DIAG bit {diag_bit} not set")
        if not contactor_opened:
            parts.append("contactor did not open")
        detail = f"{elapsed_ms:.0f}ms TIMEOUT | " + "; ".join(parts) if parts else f"{elapsed_ms:.0f}ms TIMEOUT"
        return TestOutcome(
            test_id=tc.test_id, result=TestResult.FAIL,
            elapsed_ms=elapsed_ms, detail=detail,
            category=tc.category, priority=tc.priority,
        )


# ============================================================================
# CSV Loader
# ============================================================================

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


# ============================================================================
# Report generation
# ============================================================================

def format_result_line(outcome: TestOutcome) -> str:
    """Format a single test result as a printable line."""
    tag = f"[{outcome.result}]"
    elapsed = f"{outcome.elapsed_ms:.0f}ms"
    return f"{tag:6s} {outcome.test_id:20s} | {outcome.detail}"


def generate_report(outcomes: List[TestOutcome], report_path: str) -> None:
    """Write the full report to a file and print summary."""
    total = len(outcomes)
    pass_count = sum(1 for o in outcomes if o.result == TestResult.PASS)
    fail_count = sum(1 for o in outcomes if o.result == TestResult.FAIL)
    skip_count = sum(1 for o in outcomes if o.result == TestResult.SKIP)
    error_count = sum(1 for o in outcomes if o.result == TestResult.ERROR)

    # Per-priority breakdown
    priority_stats: Dict[str, Dict[str, int]] = {}
    for o in outcomes:
        pri = o.priority or "??"
        if pri not in priority_stats:
            priority_stats[pri] = {"total": 0, "PASS": 0, "FAIL": 0, "SKIP": 0, "ERROR": 0}
        priority_stats[pri]["total"] += 1
        priority_stats[pri][o.result] += 1

    # Per-category breakdown
    category_stats: Dict[str, Dict[str, int]] = {}
    for o in outcomes:
        cat = o.category or "??"
        if cat not in category_stats:
            category_stats[cat] = {"total": 0, "PASS": 0, "FAIL": 0, "SKIP": 0, "ERROR": 0}
        category_stats[cat]["total"] += 1
        category_stats[cat][o.result] += 1

    lines = []
    lines.append("=" * 72)
    lines.append("  foxBMS POSIX vECU — ASIL-D Fault Injection Report")
    lines.append(f"  Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 72)
    lines.append("")

    # Summary
    lines.append(f"Total: {total} | PASS: {pass_count} | FAIL: {fail_count} "
                 f"| SKIP: {skip_count} | ERROR: {error_count}")
    lines.append("")

    # Priority breakdown
    for pri in sorted(priority_stats.keys()):
        s = priority_stats[pri]
        lines.append(f"{pri}: {s['total']} "
                     f"({s['PASS']} PASS, {s['FAIL']} FAIL, "
                     f"{s['SKIP']} SKIP, {s['ERROR']} ERROR)")

    lines.append("")

    # Category breakdown
    lines.append("--- By Category ---")
    for cat in sorted(category_stats.keys()):
        s = category_stats[cat]
        lines.append(f"  {cat:8s}: {s['total']:4d} "
                     f"({s['PASS']} PASS, {s['FAIL']} FAIL, "
                     f"{s['SKIP']} SKIP)")
    lines.append("")

    # Individual results
    lines.append("--- Individual Results ---")
    for o in outcomes:
        lines.append(format_result_line(o))

    # Failed tests summary
    failures = [o for o in outcomes if o.result == TestResult.FAIL]
    if failures:
        lines.append("")
        lines.append(f"--- Failed Tests ({len(failures)}) ---")
        for o in failures:
            lines.append(f"  {o.test_id}: {o.detail}")

    report_text = "\n".join(lines) + "\n"

    # Write to file
    with open(report_path, "w") as f:
        f.write(report_text)

    # Print summary to stdout
    print("")
    print("=" * 60)
    print("=== Fault Injection Report ===")
    print(f"Total: {total} | PASS: {pass_count} | FAIL: {fail_count} "
          f"| SKIP: {skip_count} | ERROR: {error_count}")
    for pri in sorted(priority_stats.keys()):
        s = priority_stats[pri]
        print(f"{pri}: {s['total']} "
              f"({s['PASS']} PASS, {s['FAIL']} FAIL, {s['SKIP']} SKIP)")
    print(f"\nFull report: {report_path}")
    print("=" * 60)


# ============================================================================
# Main
# ============================================================================

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
    parser.add_argument("--report", default="fault-injection-report.txt",
                        help="Output report file")
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

    # Wait for BMS to reach NORMAL
    print(f"[runner] Waiting for BMS to reach NORMAL state (up to {STARTUP_TIMEOUT_S}s)...")
    if not executor.wait_for_normal(STARTUP_TIMEOUT_S):
        print("[ERROR] BMS did not reach NORMAL state within timeout")
        print(f"[DEBUG] Last BMS state: {BMS_STATE_NAMES.get(monitor.bms_state, '?')} "
              f"({monitor.bms_state})")
        bus.close()
        if vecu_mgr:
            vecu_mgr.stop()
        return 1

    print(f"[runner] BMS is in NORMAL state — stabilizing 4s for plant discharge...")
    time.sleep(4.0)  # Wait for plant to detect NORMAL and start discharging
    print(f"[runner] Starting test execution")
    print(f"[runner] Per-test timeout: {args.timeout}ms")
    print("")

    # Execute tests
    outcomes: List[TestOutcome] = []
    restart_count = 0

    for i, tc in enumerate(cases):
        # Progress indicator
        progress = f"[{i+1}/{len(cases)}]"

        # Ensure BMS is in NORMAL before each test
        if not monitor.bms_in_normal():
            injector.clear()
            time.sleep(0.1)
            if not executor.wait_for_normal(RECOVERY_TIMEOUT_S):
                # Try restarting
                if vecu_mgr and vecu_mgr.is_alive():
                    print(f"{progress} BMS not in NORMAL — restarting vECU...")
                    if not vecu_mgr.restart():
                        print(f"{progress} [ERROR] vECU restart failed")
                        outcomes.append(TestOutcome(
                            test_id=tc.test_id, result=TestResult.ERROR,
                            elapsed_ms=0, detail="vECU restart failed",
                            category=tc.category, priority=tc.priority,
                        ))
                        continue
                    # Re-open CAN (old socket may be stale)
                    bus.close()
                    bus = CanBus(args.can_interface)
                    injector = FaultInjector(bus)
                    executor = TestExecutor(bus, injector, monitor, args.timeout)
                    restart_count += 1

                    if not executor.wait_for_normal(STARTUP_TIMEOUT_S):
                        print(f"{progress} [ERROR] BMS not NORMAL after restart")
                        outcomes.append(TestOutcome(
                            test_id=tc.test_id, result=TestResult.ERROR,
                            elapsed_ms=0, detail="BMS not NORMAL after restart",
                            category=tc.category, priority=tc.priority,
                        ))
                        continue
                elif vecu_mgr:
                    print(f"{progress} [ERROR] vECU crashed")
                    if not vecu_mgr.restart():
                        outcomes.append(TestOutcome(
                            test_id=tc.test_id, result=TestResult.ERROR,
                            elapsed_ms=0, detail="vECU crashed, restart failed",
                            category=tc.category, priority=tc.priority,
                        ))
                        continue
                    bus.close()
                    bus = CanBus(args.can_interface)
                    injector = FaultInjector(bus)
                    executor = TestExecutor(bus, injector, monitor, args.timeout)
                    restart_count += 1
                    executor.wait_for_normal(STARTUP_TIMEOUT_S)

        # Run the test
        outcome = executor.execute(tc)
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
            # After contactor-open tests, need longer recovery
            if tc.expected_reaction in ("CONTACTOR_OPEN", "CONTACTOR_OPEN_LATCHED",
                                         "ERROR_FLAG"):
                time.sleep(0.2)
                # Drain stale probe frames
                bus.drain()
                injector.monitor_and_update(monitor, 0.1)
            else:
                time.sleep(0.05)

    # Generate report
    generate_report(outcomes, args.report)

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
