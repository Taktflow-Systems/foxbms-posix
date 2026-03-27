#!/usr/bin/env python3
"""
foxBMS POSIX vECU — Centralized Constants
Single source of truth for pack geometry, OCV table, CAN signals, and DTC codes.

Equivalent to mebms-classic tools/zvbms_constants.py, adapted for foxBMS 2 v1.10.0
18S/3Ah NMC pack on SocketCAN (vcan1).
"""
from __future__ import annotations

import struct

# ============================================================================
# Pack Geometry
# ============================================================================
CELL_COUNT = 18                        # BS_NR_OF_CELL_BLOCKS_PER_MODULE
CELL_CAPACITY_MAH = 3000              # 3 Ah NMC cells
PACK_CAPACITY_MAH = CELL_CAPACITY_MAH  # single string, no parallel
TEMP_SENSOR_COUNT = 8                  # 8 temperature sensors (2 mux groups x 6)
STRING_COUNT = 1                       # single string

# Voltage limits (mV)
CELL_V_MIN_MV = 2500                  # deep discharge cutoff
CELL_V_NOM_MV = 3700                  # nominal voltage
CELL_V_MAX_MV = 4200                  # charge cutoff
CELL_V_OV_THRESHOLD_MV = 3600        # foxBMS overvoltage MSL threshold (configurable)
CELL_V_UV_THRESHOLD_MV = 2700        # foxBMS undervoltage MSL threshold

# Temperature limits (deci-degC)
CELL_T_MIN_DDEGC = 0                  # 0.0 degC
CELL_T_NOM_DDEGC = 250               # 25.0 degC
CELL_T_MAX_DDEGC = 600               # 60.0 degC
CELL_T_OT_THRESHOLD_DDEGC = 550      # foxBMS overtemperature threshold

# Internal resistance
R_CELL_MOHM = 50.0                    # per-cell internal resistance (mOhm)
R_PACK_MOHM = R_CELL_MOHM * CELL_COUNT

# ============================================================================
# OCV Table — NMC (piecewise linear, same as plant_model.py)
# Format: (soc_permille, voltage_mV)
# ============================================================================
OCV_TABLE = [
    (0,    2800),   # 0%   -> 2.800V (deep discharge)
    (25,   3000),   # 2.5% -> 3.000V (steep region)
    (50,   3200),   # 5%   -> 3.200V
    (100,  3350),   # 10%  -> 3.350V (knee)
    (150,  3450),   # 15%  -> 3.450V
    (200,  3520),   # 20%  -> 3.520V
    (300,  3580),   # 30%  -> 3.580V (entering flat region)
    (400,  3620),   # 40%  -> 3.620V
    (500,  3650),   # 50%  -> 3.650V (mid-SOC plateau)
    (600,  3700),   # 60%  -> 3.700V
    (700,  3780),   # 70%  -> 3.780V (leaving flat region)
    (800,  3880),   # 80%  -> 3.880V
    (850,  3950),   # 85%  -> 3.950V
    (900,  4020),   # 90%  -> 4.020V (steep region)
    (950,  4100),   # 95%  -> 4.100V
    (1000, 4200),   # 100% -> 4.200V (charge cutoff)
]


def ocv_to_voltage_mv(soc_permille: int) -> int:
    """Piecewise linear OCV interpolation for NMC.
    Input: SOC in permille (0-1000). Returns: voltage in mV."""
    soc_permille = max(0, min(1000, soc_permille))
    for i in range(len(OCV_TABLE) - 1):
        s0, v0 = OCV_TABLE[i]
        s1, v1 = OCV_TABLE[i + 1]
        if s0 <= soc_permille <= s1:
            frac = (soc_permille - s0) / (s1 - s0) if s1 != s0 else 0
            return int(v0 + frac * (v1 - v0))
    return OCV_TABLE[-1][1]


def voltage_to_soc_permille(voltage_mv: int) -> int:
    """Reverse OCV lookup: voltage (mV) -> SOC (permille).
    Returns nearest SOC for given terminal voltage."""
    voltage_mv = max(OCV_TABLE[0][1], min(OCV_TABLE[-1][1], voltage_mv))
    for i in range(len(OCV_TABLE) - 1):
        s0, v0 = OCV_TABLE[i]
        s1, v1 = OCV_TABLE[i + 1]
        if v0 <= voltage_mv <= v1:
            frac = (voltage_mv - v0) / (v1 - v0) if v1 != v0 else 0
            return int(s0 + frac * (s1 - s0))
    return OCV_TABLE[-1][0]


# ============================================================================
# CAN Message IDs — foxBMS TX (from foxBMS DBC + STATUS.md)
# ============================================================================
CAN_TX = {
    0x220: "BMS State",             # BMS state machine + string count
    0x221: "BMS Detail",            # BMS detail state
    0x231: "Pack Values P1",        # min/max cell voltages
    0x232: "SOF Limits",            # State of Function limits
    0x233: "Pack Values P0",        # pack voltage + current
    0x234: "Pack Values P2",        # min/max temperatures
    0x235: "SOC/SOE",               # State of Charge + Energy
    0x240: "Contactor State 0",     # contactor feedback
    0x241: "Contactor State 1",
    0x242: "Contactor State 2",
    0x243: "Contactor State 3",
    0x244: "Contactor State 4",
    0x245: "Contactor State 5",
    0x250: "Cell Voltage Broadcast",
    0x260: "Cell Temperature Broadcast",
    0x301: "Open Wire",
}

# CAN Message IDs — foxBMS RX (plant model sends these)
CAN_RX = {
    0x210: "BMS State Request",      # STANDBY=0x00, NORMAL=0x02
    0x270: "Cell Voltages (AFE)",    # 5 mux groups, 4 cells each
    0x280: "Cell Temperatures",      # 2 mux groups, 6 sensors each
    0x521: "IVT Current",
    0x522: "IVT Voltage 1",
    0x523: "IVT Voltage 2",
    0x524: "IVT Voltage 3",          # used by redundancy module
    0x527: "IVT Temperature",
}

# CAN Message IDs — Plant model telemetry (for web dashboard)
CAN_PLANT = {
    0x600: "Plant SOC + Current",
    0x601: "Plant OCV + PackV",
    0x602: "Plant IR drop + State",
    0x603: "Plant Cells 0-3",
    0x604: "Plant Cells 4-7",
    0x605: "Plant Cells 8-11",
    0x606: "Plant Cells 12-15",
    0x607: "Plant Cells 16-17",
}

# CAN Message IDs — ML Sidecar predictions (reserved, 0x700-0x70F)
CAN_ML = {
    0x700: "ML SOC Prediction",      # ML LSTM SOC estimate (%)
    0x701: "ML SOH Prediction",      # ML SOH estimate (%)
    0x702: "ML Thermal Risk",        # ML thermal anomaly score (0-1000 = 0.0-1.0)
    0x703: "ML Cell Imbalance",      # ML imbalance score (0-1000)
    0x704: "ML RUL Estimate",        # Remaining Useful Life (cycles)
    0x705: "ML Anomaly Score",       # IsolationForest anomaly score (0-1000)
}

# CAN Message IDs — Override/control
CAN_OVERRIDE = {
    0x6E0: "Plant Override",         # fault injection from web UI
    0x7E0: "BMS SIL Override",       # direct BMS state override
}

# SIL Probe IDs
CAN_SIL_PROBES = {
    0x7F0: "Contactor Actual State",
    0x7F1: "SOC Internal",
    0x7F2: "Balancing State",
    0x7F9: "SIL Heartbeat",
}

# ============================================================================
# DTC Codes — foxBMS Diagnostic IDs
# (mapped from DIAG_ID_e in foxBMS diag_cfg.h)
# ============================================================================
DTC_CODES = {
    "CELL_OV":          0x01,   # Cell overvoltage (MSL)
    "CELL_UV":          0x02,   # Cell undervoltage (MSL)
    "TEMP_OVERTEMP_C":  0x03,   # Overtemperature charge (MSL)
    "TEMP_OVERTEMP_D":  0x04,   # Overtemperature discharge (MSL)
    "TEMP_UNDERTEMP_C": 0x05,   # Undertemperature charge
    "TEMP_UNDERTEMP_D": 0x06,   # Undertemperature discharge
    "OVERCURRENT_C":    0x07,   # Overcurrent charge (MSL)
    "OVERCURRENT_D":    0x08,   # Overcurrent discharge (MSL)
    "CURRENT_SENSOR":   0x09,   # Current sensor not present
    "AFE_COMM":         0x0A,   # AFE communication error
    "SBC_FAULT":        0x0B,   # System Basis Chip fault
    "INTERLOCK":        0x0C,   # Interlock open
    "CONTACTOR_STUCK":  0x0D,   # Contactor stuck / welded
    "OPEN_WIRE":        0x0E,   # Open wire detection
    "PLAUSIBILITY":     0x0F,   # Cell voltage plausibility
    "DEEP_DISCHARGE":   0x10,   # Deep discharge (MSL)
}

# ============================================================================
# foxBMS CAN Big-Endian Encoding Table
# (verified by roundtrip testing — HITL-locked in plant_model.py)
# ============================================================================
CAN_BIG_ENDIAN_TABLE = [
    56, 57, 58, 59, 60, 61, 62, 63, 48, 49, 50, 51, 52, 53, 54, 55,
    40, 41, 42, 43, 44, 45, 46, 47, 32, 33, 34, 35, 36, 37, 38, 39,
    24, 25, 26, 27, 28, 29, 30, 31, 16, 17, 18, 19, 20, 21, 22, 23,
     8,  9, 10, 11, 12, 13, 14, 15,  0,  1,  2,  3,  4,  5,  6,  7,
]


def foxbms_encode_signal(msg_data: int, start_bit: int, bit_length: int, value: int) -> int:
    """Encode a CAN signal using foxBMS's big-endian bit numbering."""
    msb_pos = CAN_BIG_ENDIAN_TABLE[start_bit]
    lsb_pos = msb_pos - (bit_length - 1)
    mask = ((1 << bit_length) - 1) << lsb_pos
    msg_data &= ~mask
    msg_data |= (value & ((1 << bit_length) - 1)) << lsb_pos
    return msg_data


def foxbms_decode_signal(msg_data: int, start_bit: int, bit_length: int) -> int:
    """Decode a CAN signal using foxBMS's big-endian bit numbering."""
    msb_pos = CAN_BIG_ENDIAN_TABLE[start_bit]
    lsb_pos = msb_pos - (bit_length - 1)
    mask = ((1 << bit_length) - 1) << lsb_pos
    return (msg_data >> lsb_pos) & ((1 << bit_length) - 1)


def bytes_to_msg_data(data: bytes) -> int:
    """Convert 8-byte CAN frame to 64-bit integer."""
    padded = data + bytes(8 - len(data))
    return struct.unpack(">Q", padded[:8])[0]


def msg_data_to_bytes(msg_data: int) -> bytes:
    """Convert 64-bit integer to 8-byte CAN frame."""
    return struct.pack(">Q", msg_data)


# ============================================================================
# CAN Frame Decoders (for ML sidecar + analysis tools)
# ============================================================================
def decode_0x233(data: bytes) -> tuple[int, int]:
    """Decode Pack Values P0: pack voltage (mV) and pack current (mA).
    Returns: (pack_voltage_mV, pack_current_mA)"""
    d = bytes_to_msg_data(data)
    # Pack voltage: start_bit=7, length=17, factor=1, offset=0 (mV)
    voltage_mv = foxbms_decode_signal(d, 7, 17)
    # Pack current: start_bit=20, length=24 (signed, mA)
    current_raw = foxbms_decode_signal(d, 20, 24)
    # Sign extend 24-bit
    if current_raw & (1 << 23):
        current_raw -= (1 << 24)
    return voltage_mv, current_raw


def decode_0x235(data: bytes) -> tuple[int, int]:
    """Decode SOC/SOE message: SOC (permille) and SOE (permille).
    Returns: (soc_permille, soe_permille)"""
    d = bytes_to_msg_data(data)
    soc = foxbms_decode_signal(d, 7, 16)   # SOC in 0.01% units
    soe = foxbms_decode_signal(d, 23, 16)  # SOE in 0.01% units
    return soc, soe


def decode_0x220(data: bytes) -> tuple[int, int]:
    """Decode BMS State: state code and connected strings.
    Returns: (bms_state, connected_strings)"""
    state = data[0] & 0x0F
    strings = (data[0] >> 4) & 0x0F
    return state, strings


def decode_0x270(data: bytes) -> tuple[int, list[int]]:
    """Decode Cell Voltages (AFE): mux group and 4 cell voltages (mV).
    Returns: (mux, [v0_mV, v1_mV, v2_mV, v3_mV])"""
    d = bytes_to_msg_data(data)
    mux = foxbms_decode_signal(d, 7, 8)
    v0 = foxbms_decode_signal(d, 11, 13)
    v1 = foxbms_decode_signal(d, 30, 13)
    v2 = foxbms_decode_signal(d, 33, 13)
    v3 = foxbms_decode_signal(d, 52, 13)
    return mux, [v0, v1, v2, v3]


# ============================================================================
# BMS State Codes
# ============================================================================
BMS_STATE = {
    0: "UNINITIALIZED",
    1: "INITIALIZATION",
    2: "INITIALIZED",
    3: "IDLE",
    5: "STANDBY",
    6: "PRECHARGE",
    7: "NORMAL",
    8: "CHARGE",
    9: "ERROR",
}

# DECAN_DATA_IS_VALID = 1 (not 0) — verified by roundtrip testing
DECAN_DATA_IS_VALID = 1

# SBC_STATEMACHINE_RUNNING = 2 (not 3) — enum confirmed in sbc.h
SBC_STATEMACHINE_RUNNING = 2
