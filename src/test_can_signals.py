#!/usr/bin/env python3
"""
foxBMS POSIX vECU -- CAN Signal Verification Test Specification

Comprehensive test catalog for every CAN signal, cycle time, DLC, RX path,
and endianness constraint in the foxBMS vECU.  This file is a TEST
SPECIFICATION: it defines WHAT to test as a machine-readable catalog (list of
dicts).  The test runner framework consumes ``get_tests()`` and executes each
entry against the live vECU over SocketCAN + plant model.

Category breakdown
------------------
  SIG-TX-xxxx  TX signal content (nominal, boundary, state-dependent)   450 tests
  SIG-CYC-xxxx TX cycle time verification                               26 tests
  SIG-DLC-xxxx TX DLC verification                                      13 tests
  SIG-RX-xxxx  RX processing (inject via plant -> observe in TX/probe)  56 tests
  SIG-END-xxxx Endianness / byte-order verification                     19 tests
  --------------------------------------------------------------------------
  TOTAL                                                                 564 tests

Test-case dict schema
---------------------
  id           : str   -- unique ID  <Category>-<Direction>-<MsgID>-<Seq>
  category     : str   -- SIG-TX | SIG-CYC | SIG-DLC | SIG-RX | SIG-END
  msg_id       : int   -- CAN arbitration ID
  signal       : str   -- signal name (empty for message-level tests)
  test_type    : str   -- nominal | min_boundary | max_boundary | invalid |
                          cycle_time | dlc | endianness | state_dependent
  description  : str   -- human-readable intent
  stimulus     : dict  -- how to set up the test (plant inject, state req, wait)
  expected     : dict  -- what to observe
  asil         : str   -- ASIL rating if applicable
  tsr          : str   -- test-specification-requirement traceability
  verifies     : list  -- SYS-REQ / SW-REQ IDs
  priority     : str   -- P1 (must) | P2 (should) | P3 (nice-to-have)

Usage:
    # Print summary
    python3 test_can_signals.py

    # Import in runner
    from test_can_signals import get_tests
    for tc in get_tests():
        runner.execute(tc)
"""
# @verifies SYS-REQ-040
# @verifies SYS-REQ-041
# @verifies SYS-REQ-042
# @verifies SYS-REQ-050
# @verifies SYS-REQ-051
# @verifies SYS-REQ-052
# @verifies SYS-REQ-053
# @verifies SYS-REQ-060
# @verifies SYS-REQ-070
# @verifies SYS-REQ-071
# @verifies SYS-REQ-073
# @verifies SYS-REQ-090
# @verifies SYS-REQ-091
# @verifies SYS-REQ-101
# @verifies SYS-REQ-102
# @verifies SYS-REQ-110
# @verifies SYS-REQ-120
# @verifies SYS-REQ-200
# @verifies SYS-REQ-201
# @verifies SYS-REQ-202

from collections import Counter

# ============================================================================
# TX message definitions
# ============================================================================
TX_MESSAGES = {
    0x220: {"name": "BmsState",              "cycle_ms": 100, "dlc": 8},
    0x221: {"name": "BmsStateDetails",       "cycle_ms": 100, "dlc": 8},
    0x231: {"name": "CellVoltages_Summary",  "cycle_ms": 100, "dlc": 8},
    0x232: {"name": "CellTemperatures_Summary", "cycle_ms": 100, "dlc": 8},
    0x233: {"name": "PackValues_P0",         "cycle_ms": 100, "dlc": 8},
    0x234: {"name": "PackValues_P1",         "cycle_ms": 1000, "dlc": 8},
    0x235: {"name": "SOC",                   "cycle_ms": 1000, "dlc": 8},
    0x236: {"name": "SOE",                   "cycle_ms": 1000, "dlc": 8},
    0x250: {"name": "CellVoltages_Mux",      "cycle_ms": 10,  "dlc": 8},
    0x260: {"name": "CellTemperatures_Mux",  "cycle_ms": 10,  "dlc": 8},
    0x270: {"name": "AFE_CellVoltages",      "cycle_ms": 10,  "dlc": 8},
    0x280: {"name": "AFE_CellTemperatures",  "cycle_ms": 10,  "dlc": 8},
    0x301: {"name": "SlaveInfo",             "cycle_ms": 1000, "dlc": 8},
}

# RX message definitions
RX_MESSAGES = {
    0x521: {"name": "IVT_Current",     "cycle_ms": 100},
    0x522: {"name": "IVT_Voltage1",    "cycle_ms": 100},
    0x523: {"name": "IVT_Voltage2",    "cycle_ms": 100},
    0x524: {"name": "IVT_Voltage3",    "cycle_ms": 100},
    0x527: {"name": "IVT_Temperature", "cycle_ms": 1000},
    0x210: {"name": "StateRequest",    "cycle_ms": 100},
}

# Probe message IDs (for RX verification readback)
PROBE_IDS = {
    0x7F0: "SPS_Contactor",
    0x7F4: "CellVoltage_Probe",
    0x7F6: "Temperature_Probe",
    0x7F7: "DIAG_Probe",
    0x7F9: "BmsState_Probe",
    0x7FA: "Current_Probe",
}

# Plant override command types
OVERRIDE_CMD = {"voltage": 0x01, "temperature": 0x02, "current": 0x03}

# BMS state enum (byte[0] lower nibble of 0x220)
BMS_STATES = {
    "UNINITIALIZED": 0,
    "INITIALIZATION": 1,
    "IDLE": 3,
    "STANDBY": 5,
    "NORMAL": 7,
    "CHARGE": 8,
    "ERROR": 10,
}


# ============================================================================
# Helper to build test dicts
# ============================================================================
def _tc(id_, category, msg_id, signal, test_type, description,
        stimulus, expected, verifies, priority="P1", asil="", tsr=""):
    return {
        "id": id_,
        "category": category,
        "msg_id": msg_id,
        "signal": signal,
        "test_type": test_type,
        "description": description,
        "stimulus": stimulus,
        "expected": expected,
        "asil": asil,
        "tsr": tsr,
        "verifies": verifies,
        "priority": priority,
    }


# ============================================================================
# 1) TX Signal Content  (SIG-TX-xxxx)
# ============================================================================
_tx_tests = []
_seq = {}  # per msg_id sequence counter


def _next_seq(msg_id):
    _seq.setdefault(msg_id, 0)
    _seq[msg_id] += 1
    return _seq[msg_id]


def _tx_id(msg_id):
    return f"SIG-TX-{msg_id:04X}-{_next_seq(msg_id):03d}"


# ---- 0x220  BmsState -------------------------------------------------------
# Signals: BmsState (4-bit enum), 20+ error flags, insulation kOhm
for state_name, state_val in [("STANDBY", 5), ("NORMAL", 7), ("ERROR", 10),
                               ("IDLE", 3), ("INITIALIZATION", 1)]:
    _tx_tests.append(_tc(
        _tx_id(0x220), "SIG-TX", 0x220, "BmsState", "nominal",
        f"BMS state reports {state_name} ({state_val})",
        {"wait_for_state": state_name},
        {"signal": "BmsState", "value": state_val, "tolerance": 0,
         "byte": 0, "mask": 0x0F},
        ["SYS-REQ-040"], "P1", "QM",
    ))

# Error flags in STANDBY (all clear)
_err_flags_220 = [
    "OverVoltage", "UnderVoltage", "OverCurrent_Charge",
    "OverCurrent_Discharge", "OverTemperature_Charge",
    "OverTemperature_Discharge", "UnderTemperature_Charge",
    "UnderTemperature_Discharge", "CellImbalance",
    "OpenWireFault", "PlausibilityError",
    "ContactorFault", "InsulationFault",
    "CommunicationFault_AFE", "CommunicationFault_IVT",
    "DeepDischargeFault", "PackOvervoltage",
    "PackUndervoltage", "PrechargeTimeout",
    "ContactorOpenUnexpected",
]
for i, flag_name in enumerate(_err_flags_220):
    # Nominal: flag clear in STANDBY
    _tx_tests.append(_tc(
        _tx_id(0x220), "SIG-TX", 0x220, f"Err_{flag_name}", "nominal",
        f"Error flag {flag_name} is 0 in STANDBY (no fault)",
        {"wait_for_state": "STANDBY"},
        {"signal": f"Err_{flag_name}", "value": 0, "tolerance": 0},
        ["SYS-REQ-040", "SYS-REQ-070"], "P1", "ASIL-B",
    ))
    # Active: flag set in ERROR after corresponding fault injection
    _tx_tests.append(_tc(
        _tx_id(0x220), "SIG-TX", 0x220, f"Err_{flag_name}", "state_dependent",
        f"Error flag {flag_name} is 1 after fault injection",
        {"inject_fault": flag_name, "wait_for_state": "ERROR"},
        {"signal": f"Err_{flag_name}", "value": 1, "tolerance": 0},
        ["SYS-REQ-070", "SYS-REQ-071"], "P1", "ASIL-B",
    ))

# Insulation resistance
_tx_tests.append(_tc(
    _tx_id(0x220), "SIG-TX", 0x220, "InsulationResistance", "nominal",
    "Insulation resistance > 500 kOhm in STANDBY",
    {"wait_for_state": "STANDBY"},
    {"signal": "InsulationResistance", "min": 500, "unit": "kOhm"},
    ["SYS-REQ-090"], "P1", "ASIL-B",
))
_tx_tests.append(_tc(
    _tx_id(0x220), "SIG-TX", 0x220, "InsulationResistance", "min_boundary",
    "Insulation resistance = 0 kOhm (fault condition)",
    {"inject_fault": "InsulationFault"},
    {"signal": "InsulationResistance", "value": 0, "tolerance": 0},
    ["SYS-REQ-090"], "P2",
))
_tx_tests.append(_tc(
    _tx_id(0x220), "SIG-TX", 0x220, "InsulationResistance", "max_boundary",
    "Insulation resistance saturates at 65535 kOhm",
    {"wait_for_state": "STANDBY"},
    {"signal": "InsulationResistance", "max": 65535},
    ["SYS-REQ-090"], "P3",
))

# ---- 0x221  BmsStateDetails ------------------------------------------------
_tx_tests.append(_tc(
    _tx_id(0x221), "SIG-TX", 0x221, "BmsSubstate", "nominal",
    "BMS substate reports valid substate in STANDBY",
    {"wait_for_state": "STANDBY"},
    {"signal": "BmsSubstate", "min": 0, "max": 15},
    ["SYS-REQ-040"], "P1",
))
for state_name in ["STANDBY", "NORMAL", "ERROR", "IDLE"]:
    _tx_tests.append(_tc(
        _tx_id(0x221), "SIG-TX", 0x221, "BmsSubstate", "state_dependent",
        f"BMS substate value in {state_name} state",
        {"wait_for_state": state_name},
        {"signal": "BmsSubstate", "min": 0, "max": 15},
        ["SYS-REQ-040"], "P2",
    ))

_tx_tests.append(_tc(
    _tx_id(0x221), "SIG-TX", 0x221, "ConnectedStrings", "nominal",
    "Connected strings count in STANDBY",
    {"wait_for_state": "STANDBY"},
    {"signal": "ConnectedStrings", "min": 0, "max": 255},
    ["SYS-REQ-040"], "P1",
))
_tx_tests.append(_tc(
    _tx_id(0x221), "SIG-TX", 0x221, "ConnectedStrings", "state_dependent",
    "Connected strings = 1 in NORMAL (contactors closed)",
    {"wait_for_state": "NORMAL"},
    {"signal": "ConnectedStrings", "value": 1, "tolerance": 0},
    ["SYS-REQ-040", "SYS-REQ-110"], "P1",
))
_tx_tests.append(_tc(
    _tx_id(0x221), "SIG-TX", 0x221, "ConnectedStrings", "state_dependent",
    "Connected strings = 0 in ERROR (contactors open)",
    {"wait_for_state": "ERROR"},
    {"signal": "ConnectedStrings", "value": 0, "tolerance": 0},
    ["SYS-REQ-040", "SYS-REQ-110"], "P1",
))

# ---- 0x231  CellVoltages_Summary -------------------------------------------
_volt_summary_signals = [
    ("MinCellVoltage_mV",  "min cell voltage",  2500, 4200, 0, 65535),
    ("MaxCellVoltage_mV",  "max cell voltage",  2500, 4200, 0, 65535),
    ("AvgCellVoltage_mV",  "avg cell voltage",  2500, 4200, 0, 65535),
    ("StringVoltage_mV",   "string voltage",     30000, 50400, 0, 65535),
]
for sig_name, label, nom_lo, nom_hi, phys_min, phys_max in _volt_summary_signals:
    for state in ["STANDBY", "NORMAL", "ERROR"]:
        _tx_tests.append(_tc(
            _tx_id(0x231), "SIG-TX", 0x231, sig_name, "nominal",
            f"{label} in {state} within [{nom_lo}, {nom_hi}] mV",
            {"wait_for_state": state},
            {"signal": sig_name, "min": nom_lo, "max": nom_hi, "unit": "mV"},
            ["SYS-REQ-050"], "P1", "ASIL-B",
        ))
    _tx_tests.append(_tc(
        _tx_id(0x231), "SIG-TX", 0x231, sig_name, "min_boundary",
        f"{label} at physical minimum ({phys_min} mV)",
        {"plant_override": {"type": "voltage", "all_cells": phys_min}},
        {"signal": sig_name, "value": phys_min, "tolerance": 1},
        ["SYS-REQ-050"], "P2",
    ))
    _tx_tests.append(_tc(
        _tx_id(0x231), "SIG-TX", 0x231, sig_name, "max_boundary",
        f"{label} at physical maximum ({phys_max} mV)",
        {"plant_override": {"type": "voltage", "all_cells": phys_max}},
        {"signal": sig_name, "value": phys_max, "tolerance": 1},
        ["SYS-REQ-050"], "P2",
    ))

# ---- 0x232  CellTemperatures_Summary ---------------------------------------
_temp_summary_signals = [
    ("MinCellTemp_ddegC",  "min cell temperature",  200, 450, -1000, 81910),
    ("MaxCellTemp_ddegC",  "max cell temperature",  200, 450, -1000, 81910),
    ("AvgCellTemp_ddegC",  "avg cell temperature",  200, 450, -1000, 81910),
]
for sig_name, label, nom_lo, nom_hi, phys_min, phys_max in _temp_summary_signals:
    for state in ["STANDBY", "NORMAL", "ERROR"]:
        _tx_tests.append(_tc(
            _tx_id(0x232), "SIG-TX", 0x232, sig_name, "nominal",
            f"{label} in {state} within [{nom_lo}, {nom_hi}] ddegC",
            {"wait_for_state": state},
            {"signal": sig_name, "min": nom_lo, "max": nom_hi, "unit": "ddegC"},
            ["SYS-REQ-051"], "P1", "ASIL-B",
        ))
    _tx_tests.append(_tc(
        _tx_id(0x232), "SIG-TX", 0x232, sig_name, "min_boundary",
        f"{label} at physical minimum ({phys_min} ddegC)",
        {"plant_override": {"type": "temperature", "all_sensors": phys_min}},
        {"signal": sig_name, "value": phys_min, "tolerance": 10},
        ["SYS-REQ-051"], "P2",
    ))
    _tx_tests.append(_tc(
        _tx_id(0x232), "SIG-TX", 0x232, sig_name, "max_boundary",
        f"{label} at physical maximum ({phys_max} ddegC)",
        {"plant_override": {"type": "temperature", "all_sensors": phys_max}},
        {"signal": sig_name, "value": phys_max, "tolerance": 10},
        ["SYS-REQ-051"], "P2",
    ))

# ---- 0x233  PackValues_P0 --------------------------------------------------
# Pack voltage (32-bit mV) and pack current (32-bit mA signed)
for state in ["STANDBY", "NORMAL", "ERROR"]:
    _tx_tests.append(_tc(
        _tx_id(0x233), "SIG-TX", 0x233, "PackVoltage_mV", "nominal",
        f"Pack voltage in {state} within [20000, 60000] mV",
        {"wait_for_state": state},
        {"signal": "PackVoltage_mV", "min": 20000, "max": 60000, "unit": "mV"},
        ["SYS-REQ-052"], "P1", "ASIL-B",
    ))
    _tx_tests.append(_tc(
        _tx_id(0x233), "SIG-TX", 0x233, "PackCurrent_mA", "nominal",
        f"Pack current in {state} within [-200000, 200000] mA",
        {"wait_for_state": state},
        {"signal": "PackCurrent_mA", "min": -200000, "max": 200000, "unit": "mA"},
        ["SYS-REQ-053"], "P1", "ASIL-B",
    ))

# Pack voltage boundaries
_tx_tests.append(_tc(
    _tx_id(0x233), "SIG-TX", 0x233, "PackVoltage_mV", "min_boundary",
    "Pack voltage at 0 mV (all cells dead)",
    {"plant_override": {"type": "voltage", "all_cells": 0}},
    {"signal": "PackVoltage_mV", "value": 0, "tolerance": 100},
    ["SYS-REQ-052"], "P2",
))
_tx_tests.append(_tc(
    _tx_id(0x233), "SIG-TX", 0x233, "PackVoltage_mV", "max_boundary",
    "Pack voltage at max (all cells 8191 mV)",
    {"plant_override": {"type": "voltage", "all_cells": 8191}},
    {"signal": "PackVoltage_mV", "max": 4294967295},
    ["SYS-REQ-052"], "P2",
))

# Pack current boundaries
_tx_tests.append(_tc(
    _tx_id(0x233), "SIG-TX", 0x233, "PackCurrent_mA", "min_boundary",
    "Pack current at max negative (max regen / charge)",
    {"plant_override": {"type": "current", "index": 0, "value": -2000000}},
    {"signal": "PackCurrent_mA", "max": -1},
    ["SYS-REQ-053"], "P2",
))
_tx_tests.append(_tc(
    _tx_id(0x233), "SIG-TX", 0x233, "PackCurrent_mA", "max_boundary",
    "Pack current at max positive (max discharge)",
    {"plant_override": {"type": "current", "index": 0, "value": 2000000}},
    {"signal": "PackCurrent_mA", "min": 1},
    ["SYS-REQ-053"], "P2",
))

# ---- 0x234  PackValues_P1 --------------------------------------------------
for state in ["STANDBY", "NORMAL"]:
    _tx_tests.append(_tc(
        _tx_id(0x234), "SIG-TX", 0x234, "PackPower_mW", "nominal",
        f"Pack power in {state} within [0, 100000000] mW",
        {"wait_for_state": state},
        {"signal": "PackPower_mW", "min": 0, "max": 100000000, "unit": "mW"},
        ["SYS-REQ-052"], "P1",
    ))
_tx_tests.append(_tc(
    _tx_id(0x234), "SIG-TX", 0x234, "PackPower_mW", "min_boundary",
    "Pack power = 0 mW in STANDBY (no current flow)",
    {"wait_for_state": "STANDBY"},
    {"signal": "PackPower_mW", "value": 0, "tolerance": 100},
    ["SYS-REQ-052"], "P2",
))
_tx_tests.append(_tc(
    _tx_id(0x234), "SIG-TX", 0x234, "PackPower_mW", "max_boundary",
    "Pack power at max (saturated)",
    {"plant_override": {"type": "current", "index": 0, "value": 2000000}},
    {"signal": "PackPower_mW", "max": 4294967295},
    ["SYS-REQ-052"], "P3",
))

# ---- 0x235  SOC -------------------------------------------------------------
_soc_signals = [
    ("MinSOC_pct",  "minimum SOC",  0, 10000),
    ("MaxSOC_pct",  "maximum SOC",  0, 10000),
    ("AvgSOC_pct",  "average SOC",  0, 10000),
]
for sig_name, label, phys_min, phys_max in _soc_signals:
    for state in ["STANDBY", "NORMAL", "ERROR"]:
        _tx_tests.append(_tc(
            _tx_id(0x235), "SIG-TX", 0x235, sig_name, "nominal",
            f"{label} in {state} within [0, 10000] (0.00-100.00%)",
            {"wait_for_state": state},
            {"signal": sig_name, "min": phys_min, "max": phys_max, "unit": "%",
             "factor": 0.01},
            ["SYS-REQ-060"], "P1",
        ))
    _tx_tests.append(_tc(
        _tx_id(0x235), "SIG-TX", 0x235, sig_name, "min_boundary",
        f"{label} at 0% (fully discharged)",
        {"plant_override": {"type": "voltage", "all_cells": 2500}},
        {"signal": sig_name, "value": 0, "tolerance": 100},
        ["SYS-REQ-060"], "P2",
    ))
    _tx_tests.append(_tc(
        _tx_id(0x235), "SIG-TX", 0x235, sig_name, "max_boundary",
        f"{label} at 100% (fully charged)",
        {"plant_override": {"type": "voltage", "all_cells": 4200}},
        {"signal": sig_name, "value": 10000, "tolerance": 100},
        ["SYS-REQ-060"], "P2",
    ))

# ---- 0x236  SOE -------------------------------------------------------------
_soe_signals = [
    ("MinSOE",  "minimum SOE"),
    ("MaxSOE",  "maximum SOE"),
    ("AvgSOE",  "average SOE"),
]
for sig_name, label in _soe_signals:
    for state in ["STANDBY", "NORMAL"]:
        _tx_tests.append(_tc(
            _tx_id(0x236), "SIG-TX", 0x236, sig_name, "nominal",
            f"{label} in {state} within [0, 65535]",
            {"wait_for_state": state},
            {"signal": sig_name, "min": 0, "max": 65535},
            ["SYS-REQ-060"], "P2",
        ))
    _tx_tests.append(_tc(
        _tx_id(0x236), "SIG-TX", 0x236, sig_name, "min_boundary",
        f"{label} at minimum (0)",
        {"plant_override": {"type": "voltage", "all_cells": 2500}},
        {"signal": sig_name, "value": 0, "tolerance": 10},
        ["SYS-REQ-060"], "P3",
    ))
    _tx_tests.append(_tc(
        _tx_id(0x236), "SIG-TX", 0x236, sig_name, "max_boundary",
        f"{label} at maximum (65535)",
        {"plant_override": {"type": "voltage", "all_cells": 4200}},
        {"signal": sig_name, "max": 65535},
        ["SYS-REQ-060"], "P3",
    ))

# ---- 0x250  CellVoltages_Mux -----------------------------------------------
# Mux 0-4, 4 cells per frame = 20 cells
for mux_idx in range(5):
    for cell_in_frame in range(4):
        cell_global = mux_idx * 4 + cell_in_frame
        sig_name = f"CellVoltage{cell_in_frame}"
        for state in ["STANDBY", "NORMAL"]:
            _tx_tests.append(_tc(
                _tx_id(0x250), "SIG-TX", 0x250, sig_name, "nominal",
                f"Cell {cell_global} voltage (mux {mux_idx}) in {state} within [2500, 4200] mV",
                {"wait_for_state": state, "mux_value": mux_idx},
                {"signal": sig_name, "min": 2500, "max": 4200, "unit": "mV",
                 "mux": mux_idx},
                ["SYS-REQ-050"], "P1", "ASIL-B",
            ))
        _tx_tests.append(_tc(
            _tx_id(0x250), "SIG-TX", 0x250, sig_name, "min_boundary",
            f"Cell {cell_global} voltage (mux {mux_idx}) at 0 mV",
            {"plant_override": {"type": "voltage", "index": cell_global, "value": 0},
             "mux_value": mux_idx},
            {"signal": sig_name, "value": 0, "tolerance": 1, "mux": mux_idx},
            ["SYS-REQ-050"], "P2",
        ))
        _tx_tests.append(_tc(
            _tx_id(0x250), "SIG-TX", 0x250, sig_name, "max_boundary",
            f"Cell {cell_global} voltage (mux {mux_idx}) at 8191 mV",
            {"plant_override": {"type": "voltage", "index": cell_global, "value": 8191},
             "mux_value": mux_idx},
            {"signal": sig_name, "value": 8191, "tolerance": 1, "mux": mux_idx},
            ["SYS-REQ-050"], "P2",
        ))
        # ERROR state: cell voltage still reported (diagnostics)
        _tx_tests.append(_tc(
            _tx_id(0x250), "SIG-TX", 0x250, sig_name, "state_dependent",
            f"Cell {cell_global} voltage (mux {mux_idx}) in ERROR still readable",
            {"wait_for_state": "ERROR", "mux_value": mux_idx},
            {"signal": sig_name, "min": 0, "max": 8191, "unit": "mV",
             "mux": mux_idx},
            ["SYS-REQ-050"], "P2",
        ))
        # Invalid flag per cell
        _tx_tests.append(_tc(
            _tx_id(0x250), "SIG-TX", 0x250, f"CellVoltage{cell_in_frame}_InvalidFlag",
            "nominal",
            f"Cell {cell_global} invalid flag = 0 in STANDBY (valid reading)",
            {"wait_for_state": "STANDBY", "mux_value": mux_idx},
            {"signal": f"CellVoltage{cell_in_frame}_InvalidFlag",
             "value": 0, "tolerance": 0, "mux": mux_idx},
            ["SYS-REQ-050"], "P1",
        ))
        # Invalid flag = 1 after AFE fault injection
        _tx_tests.append(_tc(
            _tx_id(0x250), "SIG-TX", 0x250, f"CellVoltage{cell_in_frame}_InvalidFlag",
            "state_dependent",
            f"Cell {cell_global} invalid flag = 1 after AFE comm fault",
            {"inject_fault": "CommunicationFault_AFE", "mux_value": mux_idx},
            {"signal": f"CellVoltage{cell_in_frame}_InvalidFlag",
             "value": 1, "tolerance": 0, "mux": mux_idx},
            ["SYS-REQ-050", "SYS-REQ-120"], "P2",
        ))

# ---- 0x260  CellTemperatures_Mux -------------------------------------------
# Mux 0-1, 6 temps per frame (3 per mux page based on DBC pattern)
for mux_idx in range(2):
    for temp_in_frame in range(3):
        temp_global = mux_idx * 3 + temp_in_frame
        sig_name = f"CellTemp{temp_in_frame}"
        for state in ["STANDBY", "NORMAL"]:
            _tx_tests.append(_tc(
                _tx_id(0x260), "SIG-TX", 0x260, sig_name, "nominal",
                f"Temp sensor {temp_global} (mux {mux_idx}) in {state} within [200, 450] ddegC",
                {"wait_for_state": state, "mux_value": mux_idx},
                {"signal": sig_name, "min": 200, "max": 450, "unit": "ddegC",
                 "factor": 10, "offset": -1000, "mux": mux_idx},
                ["SYS-REQ-051"], "P1", "ASIL-B",
            ))
        _tx_tests.append(_tc(
            _tx_id(0x260), "SIG-TX", 0x260, sig_name, "min_boundary",
            f"Temp sensor {temp_global} (mux {mux_idx}) at -1000 ddegC (physical min)",
            {"plant_override": {"type": "temperature", "index": temp_global, "value": -1000},
             "mux_value": mux_idx},
            {"signal": sig_name, "value": -1000, "tolerance": 10, "mux": mux_idx},
            ["SYS-REQ-051"], "P2",
        ))
        _tx_tests.append(_tc(
            _tx_id(0x260), "SIG-TX", 0x260, sig_name, "max_boundary",
            f"Temp sensor {temp_global} (mux {mux_idx}) at 81910 ddegC (physical max)",
            {"plant_override": {"type": "temperature", "index": temp_global, "value": 81910},
             "mux_value": mux_idx},
            {"signal": sig_name, "value": 81910, "tolerance": 10, "mux": mux_idx},
            ["SYS-REQ-051"], "P2",
        ))
        # ERROR state: temperature still reported
        _tx_tests.append(_tc(
            _tx_id(0x260), "SIG-TX", 0x260, sig_name, "state_dependent",
            f"Temp sensor {temp_global} (mux {mux_idx}) in ERROR still readable",
            {"wait_for_state": "ERROR", "mux_value": mux_idx},
            {"signal": sig_name, "min": -1000, "max": 81910, "unit": "ddegC",
             "mux": mux_idx},
            ["SYS-REQ-051"], "P2",
        ))
        # Invalid flag
        _tx_tests.append(_tc(
            _tx_id(0x260), "SIG-TX", 0x260, f"CellTemp{temp_in_frame}_InvalidFlag",
            "nominal",
            f"Temp sensor {temp_global} invalid flag = 0 in STANDBY",
            {"wait_for_state": "STANDBY", "mux_value": mux_idx},
            {"signal": f"CellTemp{temp_in_frame}_InvalidFlag",
             "value": 0, "tolerance": 0, "mux": mux_idx},
            ["SYS-REQ-051"], "P1",
        ))
        # Invalid flag set after AFE fault
        _tx_tests.append(_tc(
            _tx_id(0x260), "SIG-TX", 0x260, f"CellTemp{temp_in_frame}_InvalidFlag",
            "state_dependent",
            f"Temp sensor {temp_global} invalid flag = 1 after AFE comm fault",
            {"inject_fault": "CommunicationFault_AFE", "mux_value": mux_idx},
            {"signal": f"CellTemp{temp_in_frame}_InvalidFlag",
             "value": 1, "tolerance": 0, "mux": mux_idx},
            ["SYS-REQ-051", "SYS-REQ-120"], "P2",
        ))

# ---- 0x270  AFE_CellVoltages (DBC: BO_ 624) --------------------------------
for mux_idx in range(5):
    for cell_in_frame in range(4):
        cell_global = mux_idx * 4 + cell_in_frame
        sig_name = f"AFE_CellVoltage{cell_in_frame}"
        _tx_tests.append(_tc(
            _tx_id(0x270), "SIG-TX", 0x270, sig_name, "nominal",
            f"AFE cell {cell_global} voltage (mux {mux_idx}) in STANDBY [2500, 4200] mV",
            {"wait_for_state": "STANDBY", "mux_value": mux_idx},
            {"signal": sig_name, "min": 2500, "max": 4200, "unit": "mV",
             "mux": mux_idx, "bits": 13, "factor": 1, "offset": 0},
            ["SYS-REQ-050"], "P1",
        ))
        _tx_tests.append(_tc(
            _tx_id(0x270), "SIG-TX", 0x270, sig_name, "nominal",
            f"AFE cell {cell_global} voltage (mux {mux_idx}) in NORMAL [2500, 4200] mV",
            {"wait_for_state": "NORMAL", "mux_value": mux_idx},
            {"signal": sig_name, "min": 2500, "max": 4200, "unit": "mV",
             "mux": mux_idx},
            ["SYS-REQ-050"], "P1",
        ))
        _tx_tests.append(_tc(
            _tx_id(0x270), "SIG-TX", 0x270, sig_name, "min_boundary",
            f"AFE cell {cell_global} voltage (mux {mux_idx}) at 0 mV",
            {"plant_override": {"type": "voltage", "index": cell_global, "value": 0},
             "mux_value": mux_idx},
            {"signal": sig_name, "value": 0, "tolerance": 1, "mux": mux_idx},
            ["SYS-REQ-050"], "P2",
        ))
        _tx_tests.append(_tc(
            _tx_id(0x270), "SIG-TX", 0x270, sig_name, "max_boundary",
            f"AFE cell {cell_global} voltage (mux {mux_idx}) at 8191 mV",
            {"plant_override": {"type": "voltage", "index": cell_global, "value": 8191},
             "mux_value": mux_idx},
            {"signal": sig_name, "value": 8191, "tolerance": 1, "mux": mux_idx},
            ["SYS-REQ-050"], "P2",
        ))
        _tx_tests.append(_tc(
            _tx_id(0x270), "SIG-TX", 0x270, f"AFE_CellVoltage{cell_in_frame}_InvalidFlag",
            "nominal",
            f"AFE cell {cell_global} invalid flag (mux {mux_idx}) = 0",
            {"wait_for_state": "STANDBY", "mux_value": mux_idx},
            {"signal": f"AFE_CellVoltage{cell_in_frame}_InvalidFlag",
             "value": 0, "tolerance": 0, "mux": mux_idx},
            ["SYS-REQ-050"], "P1",
        ))

# ---- 0x280  AFE_CellTemperatures (DBC: BO_ 640) ----------------------------
for mux_idx in range(2):
    for temp_in_frame in range(3):
        temp_global = mux_idx * 3 + temp_in_frame
        sig_name = f"AFE_CellTemp{temp_in_frame}"
        _tx_tests.append(_tc(
            _tx_id(0x280), "SIG-TX", 0x280, sig_name, "nominal",
            f"AFE temp {temp_global} (mux {mux_idx}) in STANDBY [200, 450] ddegC",
            {"wait_for_state": "STANDBY", "mux_value": mux_idx},
            {"signal": sig_name, "min": 200, "max": 450, "unit": "ddegC",
             "factor": 10, "offset": -1000, "mux": mux_idx, "bits": 13},
            ["SYS-REQ-051"], "P1",
        ))
        _tx_tests.append(_tc(
            _tx_id(0x280), "SIG-TX", 0x280, sig_name, "nominal",
            f"AFE temp {temp_global} (mux {mux_idx}) in NORMAL [200, 450] ddegC",
            {"wait_for_state": "NORMAL", "mux_value": mux_idx},
            {"signal": sig_name, "min": 200, "max": 450, "unit": "ddegC",
             "factor": 10, "offset": -1000, "mux": mux_idx},
            ["SYS-REQ-051"], "P1",
        ))
        _tx_tests.append(_tc(
            _tx_id(0x280), "SIG-TX", 0x280, sig_name, "min_boundary",
            f"AFE temp {temp_global} (mux {mux_idx}) at -1000 ddegC",
            {"plant_override": {"type": "temperature", "index": temp_global, "value": -1000},
             "mux_value": mux_idx},
            {"signal": sig_name, "value": -1000, "tolerance": 10, "mux": mux_idx},
            ["SYS-REQ-051"], "P2",
        ))
        _tx_tests.append(_tc(
            _tx_id(0x280), "SIG-TX", 0x280, sig_name, "max_boundary",
            f"AFE temp {temp_global} (mux {mux_idx}) at 81910 ddegC",
            {"plant_override": {"type": "temperature", "index": temp_global, "value": 81910},
             "mux_value": mux_idx},
            {"signal": sig_name, "value": 81910, "tolerance": 10, "mux": mux_idx},
            ["SYS-REQ-051"], "P2",
        ))
        _tx_tests.append(_tc(
            _tx_id(0x280), "SIG-TX", 0x280, f"AFE_CellTemp{temp_in_frame}_InvalidFlag",
            "nominal",
            f"AFE temp {temp_global} invalid flag (mux {mux_idx}) = 0",
            {"wait_for_state": "STANDBY", "mux_value": mux_idx},
            {"signal": f"AFE_CellTemp{temp_in_frame}_InvalidFlag",
             "value": 0, "tolerance": 0, "mux": mux_idx},
            ["SYS-REQ-051"], "P1",
        ))

# ---- 0x301  SlaveInfo -------------------------------------------------------
_tx_tests.append(_tc(
    _tx_id(0x301), "SIG-TX", 0x301, "AFE_Status", "nominal",
    "AFE status byte reports OK (0) in STANDBY",
    {"wait_for_state": "STANDBY"},
    {"signal": "AFE_Status", "value": 0, "tolerance": 0},
    ["SYS-REQ-120"], "P1",
))
_tx_tests.append(_tc(
    _tx_id(0x301), "SIG-TX", 0x301, "AFE_Status", "state_dependent",
    "AFE status reports fault after AFE communication error",
    {"inject_fault": "CommunicationFault_AFE"},
    {"signal": "AFE_Status", "min": 1},
    ["SYS-REQ-120"], "P1",
))
_tx_tests.append(_tc(
    _tx_id(0x301), "SIG-TX", 0x301, "AFE_Version", "nominal",
    "AFE version is non-zero",
    {"wait_for_state": "STANDBY"},
    {"signal": "AFE_Version", "min": 1, "max": 255},
    ["SYS-REQ-120"], "P2",
))
for state in ["STANDBY", "NORMAL", "ERROR"]:
    _tx_tests.append(_tc(
        _tx_id(0x301), "SIG-TX", 0x301, "AFE_Status", "state_dependent",
        f"AFE status in {state}",
        {"wait_for_state": state},
        {"signal": "AFE_Status", "min": 0, "max": 255},
        ["SYS-REQ-120"], "P2",
    ))


# ============================================================================
# 2) TX Cycle Time  (SIG-CYC-xxxx)
# ============================================================================
_cyc_tests = []
_cyc_seq = {}


def _cyc_id(msg_id):
    _cyc_seq.setdefault(msg_id, 0)
    _cyc_seq[msg_id] += 1
    return f"SIG-CYC-{msg_id:04X}-{_cyc_seq[msg_id]:03d}"


for msg_id, info in TX_MESSAGES.items():
    period_ms = info["cycle_ms"]
    name = info["name"]
    tol_pct = 20  # +/- 20%

    _cyc_tests.append(_tc(
        _cyc_id(msg_id), "SIG-CYC", msg_id, "", "cycle_time",
        f"{name} (0x{msg_id:03X}) period = {period_ms}ms +/- {tol_pct}%",
        {"wait_for_state": "STANDBY", "collect_duration_s": 10},
        {"period_ms": period_ms, "tolerance_pct": tol_pct},
        ["SYS-REQ-200"], "P1",
    ))
    _cyc_tests.append(_tc(
        _cyc_id(msg_id), "SIG-CYC", msg_id, "", "cycle_time",
        f"{name} (0x{msg_id:03X}) no gaps > {period_ms * 2}ms in 10s window",
        {"wait_for_state": "STANDBY", "collect_duration_s": 10},
        {"max_gap_ms": period_ms * 2, "min_frame_count": int(10000 / period_ms * 0.8)},
        ["SYS-REQ-200"], "P1",
    ))


# ============================================================================
# 3) TX DLC  (SIG-DLC-xxxx)
# ============================================================================
_dlc_tests = []
_dlc_seq = {}


def _dlc_id(msg_id):
    _dlc_seq.setdefault(msg_id, 0)
    _dlc_seq[msg_id] += 1
    return f"SIG-DLC-{msg_id:04X}-{_dlc_seq[msg_id]:03d}"


for msg_id, info in TX_MESSAGES.items():
    _dlc_tests.append(_tc(
        _dlc_id(msg_id), "SIG-DLC", msg_id, "", "dlc",
        f"{info['name']} (0x{msg_id:03X}) DLC = {info['dlc']}",
        {"collect_any_frame": True},
        {"dlc": info["dlc"]},
        ["SYS-REQ-201"], "P1",
    ))


# ============================================================================
# 4) RX Processing  (SIG-RX-xxxx)
# ============================================================================
_rx_tests = []
_rx_seq = {}


def _rx_id(msg_id):
    _rx_seq.setdefault(msg_id, 0)
    _rx_seq[msg_id] += 1
    return f"SIG-RX-{msg_id:04X}-{_rx_seq[msg_id]:03d}"


# ---- 0x521  IVT_Current ----------------------------------------------------
_rx_tests.append(_tc(
    _rx_id(0x521), "SIG-RX", 0x521, "IVT_Current_mA", "nominal",
    "Inject IVT current 0 mA -> pack current reports ~0 mA",
    {"inject_rx": {"msg_id": 0x521, "signal": "IVT_Current_mA", "value": 0,
                   "encoding": "big_endian_32bit_signed"}},
    {"observe_tx": 0x233, "signal": "PackCurrent_mA", "value": 0, "tolerance": 100},
    ["SYS-REQ-053"], "P1", "ASIL-B",
))
_rx_tests.append(_tc(
    _rx_id(0x521), "SIG-RX", 0x521, "IVT_Current_mA", "nominal",
    "Inject IVT current 50000 mA -> pack current reports ~50000 mA",
    {"inject_rx": {"msg_id": 0x521, "signal": "IVT_Current_mA", "value": 50000,
                   "encoding": "big_endian_32bit_signed"}},
    {"observe_tx": 0x233, "signal": "PackCurrent_mA", "value": 50000, "tolerance": 500},
    ["SYS-REQ-053"], "P1", "ASIL-B",
))
_rx_tests.append(_tc(
    _rx_id(0x521), "SIG-RX", 0x521, "IVT_Current_mA", "nominal",
    "Inject IVT current -30000 mA (regen) -> pack current negative",
    {"inject_rx": {"msg_id": 0x521, "signal": "IVT_Current_mA", "value": -30000,
                   "encoding": "big_endian_32bit_signed"}},
    {"observe_tx": 0x233, "signal": "PackCurrent_mA", "value": -30000, "tolerance": 500},
    ["SYS-REQ-053"], "P1", "ASIL-B",
))
_rx_tests.append(_tc(
    _rx_id(0x521), "SIG-RX", 0x521, "IVT_Current_mA", "min_boundary",
    "Inject IVT current at min int32 -> pack current saturates",
    {"inject_rx": {"msg_id": 0x521, "signal": "IVT_Current_mA", "value": -2147483648,
                   "encoding": "big_endian_32bit_signed"}},
    {"observe_tx": 0x233, "signal": "PackCurrent_mA", "max": 0},
    ["SYS-REQ-053"], "P2",
))
_rx_tests.append(_tc(
    _rx_id(0x521), "SIG-RX", 0x521, "IVT_Current_mA", "max_boundary",
    "Inject IVT current at max int32 -> pack current saturates",
    {"inject_rx": {"msg_id": 0x521, "signal": "IVT_Current_mA", "value": 2147483647,
                   "encoding": "big_endian_32bit_signed"}},
    {"observe_tx": 0x233, "signal": "PackCurrent_mA", "min": 0},
    ["SYS-REQ-053"], "P2",
))
_rx_tests.append(_tc(
    _rx_id(0x521), "SIG-RX", 0x521, "IVT_Current_mA", "invalid",
    "Stop IVT_Current for 500ms -> BMS detects IVT communication timeout",
    {"stop_rx": {"msg_id": 0x521, "duration_ms": 500}},
    {"observe_tx": 0x220, "signal": "Err_CommunicationFault_IVT", "value": 1},
    ["SYS-REQ-070", "SYS-REQ-073"], "P1", "ASIL-B",
))

# ---- 0x522  IVT_Voltage1 ---------------------------------------------------
for v_label, v_val in [("nominal 36000", 36000), ("low 20000", 20000), ("high 55000", 55000)]:
    _rx_tests.append(_tc(
        _rx_id(0x522), "SIG-RX", 0x522, "IVT_Voltage1_mV", "nominal",
        f"Inject IVT_Voltage1 {v_label} mV -> observable in pack voltage",
        {"inject_rx": {"msg_id": 0x522, "signal": "IVT_Voltage1_mV", "value": v_val,
                       "encoding": "big_endian_32bit_signed"}},
        {"observe_tx": 0x233, "signal": "PackVoltage_mV", "value": v_val, "tolerance": 1000},
        ["SYS-REQ-052"], "P1",
    ))
_rx_tests.append(_tc(
    _rx_id(0x522), "SIG-RX", 0x522, "IVT_Voltage1_mV", "min_boundary",
    "Inject IVT_Voltage1 = 0 mV",
    {"inject_rx": {"msg_id": 0x522, "signal": "IVT_Voltage1_mV", "value": 0,
                   "encoding": "big_endian_32bit_signed"}},
    {"observe_tx": 0x233, "signal": "PackVoltage_mV", "value": 0, "tolerance": 100},
    ["SYS-REQ-052"], "P2",
))
_rx_tests.append(_tc(
    _rx_id(0x522), "SIG-RX", 0x522, "IVT_Voltage1_mV", "max_boundary",
    "Inject IVT_Voltage1 = 100000 mV (over-range)",
    {"inject_rx": {"msg_id": 0x522, "signal": "IVT_Voltage1_mV", "value": 100000,
                   "encoding": "big_endian_32bit_signed"}},
    {"observe_tx": 0x233, "signal": "PackVoltage_mV", "min": 0},
    ["SYS-REQ-052"], "P2",
))
_rx_tests.append(_tc(
    _rx_id(0x522), "SIG-RX", 0x522, "IVT_Voltage1_mV", "invalid",
    "Stop IVT_Voltage1 for 500ms -> communication fault detected",
    {"stop_rx": {"msg_id": 0x522, "duration_ms": 500}},
    {"observe_tx": 0x220, "signal": "Err_CommunicationFault_IVT", "value": 1},
    ["SYS-REQ-073"], "P1",
))

# ---- 0x523  IVT_Voltage2 ---------------------------------------------------
for v_label, v_val in [("nominal 36000", 36000), ("zero", 0)]:
    _rx_tests.append(_tc(
        _rx_id(0x523), "SIG-RX", 0x523, "IVT_Voltage2_mV", "nominal",
        f"Inject IVT_Voltage2 {v_label} mV -> processed by BMS",
        {"inject_rx": {"msg_id": 0x523, "signal": "IVT_Voltage2_mV", "value": v_val,
                       "encoding": "big_endian_32bit_signed"}},
        {"observe_probe": 0x7FA, "no_error": True},
        ["SYS-REQ-052"], "P2",
    ))
_rx_tests.append(_tc(
    _rx_id(0x523), "SIG-RX", 0x523, "IVT_Voltage2_mV", "min_boundary",
    "Inject IVT_Voltage2 = 0 mV",
    {"inject_rx": {"msg_id": 0x523, "signal": "IVT_Voltage2_mV", "value": 0,
                   "encoding": "big_endian_32bit_signed"}},
    {"observe_probe": 0x7FA, "no_error": True},
    ["SYS-REQ-052"], "P3",
))
_rx_tests.append(_tc(
    _rx_id(0x523), "SIG-RX", 0x523, "IVT_Voltage2_mV", "max_boundary",
    "Inject IVT_Voltage2 = 100000 mV (over-range)",
    {"inject_rx": {"msg_id": 0x523, "signal": "IVT_Voltage2_mV", "value": 100000,
                   "encoding": "big_endian_32bit_signed"}},
    {"observe_probe": 0x7FA, "no_error": True},
    ["SYS-REQ-052"], "P3",
))
_rx_tests.append(_tc(
    _rx_id(0x523), "SIG-RX", 0x523, "IVT_Voltage2_mV", "invalid",
    "Stop IVT_Voltage2 for 500ms -> communication fault",
    {"stop_rx": {"msg_id": 0x523, "duration_ms": 500}},
    {"observe_tx": 0x220, "signal": "Err_CommunicationFault_IVT", "value": 1},
    ["SYS-REQ-073"], "P1",
))

# ---- 0x524  IVT_Voltage3 ---------------------------------------------------
for v_label, v_val in [("nominal 36000", 36000), ("zero", 0)]:
    _rx_tests.append(_tc(
        _rx_id(0x524), "SIG-RX", 0x524, "IVT_Voltage3_mV", "nominal",
        f"Inject IVT_Voltage3 {v_label} mV -> processed by BMS",
        {"inject_rx": {"msg_id": 0x524, "signal": "IVT_Voltage3_mV", "value": v_val,
                       "encoding": "big_endian_32bit_signed"}},
        {"observe_probe": 0x7FA, "no_error": True},
        ["SYS-REQ-052"], "P2",
    ))
_rx_tests.append(_tc(
    _rx_id(0x524), "SIG-RX", 0x524, "IVT_Voltage3_mV", "min_boundary",
    "Inject IVT_Voltage3 = 0 mV",
    {"inject_rx": {"msg_id": 0x524, "signal": "IVT_Voltage3_mV", "value": 0,
                   "encoding": "big_endian_32bit_signed"}},
    {"observe_probe": 0x7FA, "no_error": True},
    ["SYS-REQ-052"], "P3",
))
_rx_tests.append(_tc(
    _rx_id(0x524), "SIG-RX", 0x524, "IVT_Voltage3_mV", "max_boundary",
    "Inject IVT_Voltage3 = 100000 mV",
    {"inject_rx": {"msg_id": 0x524, "signal": "IVT_Voltage3_mV", "value": 100000,
                   "encoding": "big_endian_32bit_signed"}},
    {"observe_probe": 0x7FA, "no_error": True},
    ["SYS-REQ-052"], "P3",
))
_rx_tests.append(_tc(
    _rx_id(0x524), "SIG-RX", 0x524, "IVT_Voltage3_mV", "invalid",
    "Stop IVT_Voltage3 for 500ms -> communication fault",
    {"stop_rx": {"msg_id": 0x524, "duration_ms": 500}},
    {"observe_tx": 0x220, "signal": "Err_CommunicationFault_IVT", "value": 1},
    ["SYS-REQ-073"], "P1",
))

# ---- 0x527  IVT_Temperature ------------------------------------------------
_rx_tests.append(_tc(
    _rx_id(0x527), "SIG-RX", 0x527, "IVT_Temperature", "nominal",
    "Inject IVT internal temperature 25.0 degC -> processed without fault",
    {"inject_rx": {"msg_id": 0x527, "signal": "IVT_Temperature", "value": 250,
                   "encoding": "big_endian_32bit_signed"}},
    {"observe_probe": 0x7FA, "no_error": True},
    ["SYS-REQ-091"], "P2",
))
_rx_tests.append(_tc(
    _rx_id(0x527), "SIG-RX", 0x527, "IVT_Temperature", "min_boundary",
    "Inject IVT temperature -40 degC -> no fault (within range)",
    {"inject_rx": {"msg_id": 0x527, "signal": "IVT_Temperature", "value": -400,
                   "encoding": "big_endian_32bit_signed"}},
    {"observe_probe": 0x7FA, "no_error": True},
    ["SYS-REQ-091"], "P3",
))
_rx_tests.append(_tc(
    _rx_id(0x527), "SIG-RX", 0x527, "IVT_Temperature", "max_boundary",
    "Inject IVT temperature 120 degC -> possible warning or fault",
    {"inject_rx": {"msg_id": 0x527, "signal": "IVT_Temperature", "value": 1200,
                   "encoding": "big_endian_32bit_signed"}},
    {"observe_probe": 0x7FA, "check_warning": True},
    ["SYS-REQ-091"], "P3",
))
_rx_tests.append(_tc(
    _rx_id(0x527), "SIG-RX", 0x527, "IVT_Temperature", "invalid",
    "Stop IVT_Temperature for 2000ms -> communication fault detected",
    {"stop_rx": {"msg_id": 0x527, "duration_ms": 2000}},
    {"observe_tx": 0x220, "signal": "Err_CommunicationFault_IVT", "value": 1},
    ["SYS-REQ-073"], "P2",
))

# ---- 0x210  StateRequest ---------------------------------------------------
for mode_name, mode_val in [("STANDBY", 5), ("NORMAL", 7), ("CHARGE", 8)]:
    _rx_tests.append(_tc(
        _rx_id(0x210), "SIG-RX", 0x210, "ModeRequest", "nominal",
        f"Inject StateRequest mode={mode_name} ({mode_val}) -> BMS transitions",
        {"inject_rx": {"msg_id": 0x210, "signal": "ModeRequest", "value": mode_val,
                       "encoding": "byte0"}},
        {"observe_tx": 0x220, "signal": "BmsState", "value": mode_val, "tolerance": 0,
         "timeout_s": 5},
        ["SYS-REQ-040", "SYS-REQ-041"], "P1", "ASIL-B",
    ))
_rx_tests.append(_tc(
    _rx_id(0x210), "SIG-RX", 0x210, "ModeRequest", "min_boundary",
    "Inject StateRequest mode=0 (UNINITIALIZED) -> BMS ignores or rejects",
    {"inject_rx": {"msg_id": 0x210, "signal": "ModeRequest", "value": 0,
                   "encoding": "byte0"}},
    {"observe_tx": 0x220, "signal": "BmsState", "not_value": 0},
    ["SYS-REQ-040"], "P1",
))
_rx_tests.append(_tc(
    _rx_id(0x210), "SIG-RX", 0x210, "ModeRequest", "max_boundary",
    "Inject StateRequest mode=255 (invalid) -> BMS ignores or goes ERROR",
    {"inject_rx": {"msg_id": 0x210, "signal": "ModeRequest", "value": 255,
                   "encoding": "byte0"}},
    {"observe_tx": 0x220, "signal": "BmsState", "not_value": 255},
    ["SYS-REQ-040"], "P1",
))
_rx_tests.append(_tc(
    _rx_id(0x210), "SIG-RX", 0x210, "ModeRequest", "invalid",
    "Stop StateRequest for 500ms -> BMS detects vehicle comm timeout",
    {"stop_rx": {"msg_id": 0x210, "duration_ms": 500}},
    {"observe_tx": 0x220, "check_no_crash": True},
    ["SYS-REQ-040"], "P2",
))

# ---- 0x7E0  Plant Override (verify override mechanism itself) ---------------
# Voltage override
for cell_idx in range(4):
    for ov_val, label in [(3500, "nominal"), (0, "min"), (8191, "max")]:
        _rx_tests.append(_tc(
            _rx_id(0x7E0), "SIG-RX", 0x7E0, f"Override_Voltage_Cell{cell_idx}",
            "nominal" if label == "nominal" else f"{label}_boundary",
            f"Plant override cell {cell_idx} voltage to {ov_val} mV -> reflected in 0x250 mux 0",
            {"inject_rx": {"msg_id": 0x7E0, "byte0": 0x01, "byte1": cell_idx,
                           "value": ov_val}},
            {"observe_tx": 0x250, "signal": f"CellVoltage{cell_idx}",
             "value": ov_val, "tolerance": 1, "mux": 0},
            ["SYS-REQ-202"], "P1",
        ))

# Temperature override
for temp_idx in range(3):
    for ov_val, label in [(250, "nominal"), (-1000, "min"), (81910, "max")]:
        _rx_tests.append(_tc(
            _rx_id(0x7E0), "SIG-RX", 0x7E0, f"Override_Temp_Sensor{temp_idx}",
            "nominal" if label == "nominal" else f"{label}_boundary",
            f"Plant override temp sensor {temp_idx} to {ov_val} ddegC -> reflected in 0x260",
            {"inject_rx": {"msg_id": 0x7E0, "byte0": 0x02, "byte1": temp_idx,
                           "value": ov_val}},
            {"observe_tx": 0x260, "signal": f"CellTemp{temp_idx}",
             "value": ov_val, "tolerance": 10, "mux": 0},
            ["SYS-REQ-202"], "P2",
        ))

# Current override
for ov_val, label in [(0, "nominal"), (-200000, "min"), (200000, "max")]:
    _rx_tests.append(_tc(
        _rx_id(0x7E0), "SIG-RX", 0x7E0, "Override_Current",
        "nominal" if label == "nominal" else f"{label}_boundary",
        f"Plant override current to {ov_val} mA -> reflected in 0x233",
        {"inject_rx": {"msg_id": 0x7E0, "byte0": 0x03, "byte1": 0,
                       "value": ov_val}},
        {"observe_tx": 0x233, "signal": "PackCurrent_mA",
         "value": ov_val, "tolerance": 500},
        ["SYS-REQ-202"], "P2",
    ))


# ============================================================================
# 5) Endianness  (SIG-END-xxxx)
# ============================================================================
_end_tests = []
_end_seq = {}


def _end_id(msg_id):
    _end_seq.setdefault(msg_id, 0)
    _end_seq[msg_id] += 1
    return f"SIG-END-{msg_id:04X}-{_end_seq[msg_id]:03d}"


# All messages that need endianness verification
_all_msg_ids = sorted(set(list(TX_MESSAGES.keys()) + list(RX_MESSAGES.keys())))

for msg_id in _all_msg_ids:
    if msg_id in TX_MESSAGES:
        name = TX_MESSAGES[msg_id]["name"]
        direction = "TX"
    else:
        name = RX_MESSAGES[msg_id]["name"]
        direction = "RX"

    _end_tests.append(_tc(
        _end_id(msg_id), "SIG-END", msg_id, "", "endianness",
        f"{name} (0x{msg_id:03X}, {direction}) byte order matches CAN_BIG_ENDIAN_TABLE",
        {"inject_known_pattern": True, "msg_id": msg_id},
        {"byte_order": "big_endian" if msg_id in [0x521, 0x522, 0x523, 0x524, 0x527]
         else "little_endian",
         "verify_against": "foxbms_signals.dbc"},
        ["SYS-REQ-201"], "P1",
    ))


# ============================================================================
# Assemble full catalog
# ============================================================================
_ALL_TESTS = _tx_tests + _cyc_tests + _dlc_tests + _rx_tests + _end_tests


def get_tests():
    """Return the complete test catalog as a list of dicts."""
    return list(_ALL_TESTS)


def get_tests_by_category(category):
    """Return tests filtered by category prefix (e.g. 'SIG-TX', 'SIG-CYC')."""
    return [t for t in _ALL_TESTS if t["category"] == category]


def get_tests_by_msg_id(msg_id):
    """Return all tests for a given CAN message ID."""
    return [t for t in _ALL_TESTS if t["msg_id"] == msg_id]


def get_tests_by_priority(priority):
    """Return all tests at the given priority level ('P1', 'P2', 'P3')."""
    return [t for t in _ALL_TESTS if t["priority"] == priority]


def get_coverage_summary():
    """Return a dict summarizing test coverage per message ID and category."""
    by_cat = Counter(t["category"] for t in _ALL_TESTS)
    by_msg = Counter(f"0x{t['msg_id']:03X}" for t in _ALL_TESTS)
    by_type = Counter(t["test_type"] for t in _ALL_TESTS)
    by_prio = Counter(t["priority"] for t in _ALL_TESTS)
    all_reqs = set()
    for t in _ALL_TESTS:
        all_reqs.update(t["verifies"])
    return {
        "total": len(_ALL_TESTS),
        "by_category": dict(by_cat),
        "by_message": dict(by_msg),
        "by_test_type": dict(by_type),
        "by_priority": dict(by_prio),
        "unique_requirements": sorted(all_reqs),
    }


# ============================================================================
# CLI summary
# ============================================================================
if __name__ == "__main__":
    summary = get_coverage_summary()
    total = summary["total"]

    print(f"foxBMS CAN Signal Verification Test Specification")
    print(f"=" * 55)
    print(f"Total test cases: {total}")
    print()

    print("By category:")
    for cat in sorted(summary["by_category"]):
        print(f"  {cat:12s}  {summary['by_category'][cat]:4d}")
    print()

    print("By test type:")
    for tt in sorted(summary["by_test_type"]):
        print(f"  {tt:18s}  {summary['by_test_type'][tt]:4d}")
    print()

    print("By priority:")
    for p in sorted(summary["by_priority"]):
        print(f"  {p}  {summary['by_priority'][p]:4d}")
    print()

    print("By CAN message ID:")
    for mid in sorted(summary["by_message"]):
        print(f"  {mid}  {summary['by_message'][mid]:4d}")
    print()

    print(f"Unique requirements traced: {len(summary['unique_requirements'])}")
    for req in summary["unique_requirements"]:
        print(f"  {req}")
    print()

    # Validate no duplicate IDs
    ids = [t["id"] for t in _ALL_TESTS]
    dupes = [i for i, c in Counter(ids).items() if c > 1]
    if dupes:
        print(f"WARNING: {len(dupes)} duplicate test IDs found:")
        for d in dupes:
            print(f"  {d}")
    else:
        print(f"OK: All {total} test IDs are unique.")
