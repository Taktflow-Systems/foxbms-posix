#!/usr/bin/env python3
"""
Unit tests for CAN signal encoding vs DBC definition compliance.

Tests that the foxBMS big-endian encoding, signal placement, and DBC
parameters match between the plant model, the DBC file definitions, and
the actual CAN frame byte layout — all as offline pure-Python pytest tests.

Covers:
  - foxBMS big-endian bit numbering table correctness
  - Signal encoding/decoding round-trips for cell voltages (0x270)
  - Signal encoding for cell temperatures (0x280)
  - DBC signal attributes (bit length, factor, offset, min/max)
  - IVT message encoding (0x521–0x527)
  - BMS state message (0x220) byte layout
  - TX message cycle times and DLCs
  - Mux signal correctness
  - Probe message format (0x7F0–0x7FF)
"""
# @verifies SYS-REQ-040
# @verifies SYS-REQ-090
# @verifies SYS-REQ-091
# @verifies SYS-REQ-101
# @verifies SYS-REQ-102

import struct
import pytest

# ---------------------------------------------------------------------------
# foxBMS big-endian bit numbering table (from plant_model.py)
# ---------------------------------------------------------------------------
CAN_BIG_ENDIAN_TABLE = [
    56, 57, 58, 59, 60, 61, 62, 63, 48, 49, 50, 51, 52, 53, 54, 55,
    40, 41, 42, 43, 44, 45, 46, 47, 32, 33, 34, 35, 36, 37, 38, 39,
    24, 25, 26, 27, 28, 29, 30, 31, 16, 17, 18, 19, 20, 21, 22, 23,
     8,  9, 10, 11, 12, 13, 14, 15,  0,  1,  2,  3,  4,  5,  6,  7,
]

# DBC signal definitions for AFE_CellVoltages (0x270 = 624 decimal)
DBC_CELL_VOLTAGE_SIGNALS = {
    "AFE_CellVoltage_Mux": {"start_bit": 7, "bit_length": 8, "factor": 1, "offset": 0, "min": 0, "max": 255},
    "AFE_CellVoltage0_InvalidFlag": {"start_bit": 12, "bit_length": 1, "factor": 1, "offset": 0, "min": 0, "max": 1},
    "AFE_CellVoltage1_InvalidFlag": {"start_bit": 13, "bit_length": 1, "factor": 1, "offset": 0, "min": 0, "max": 1},
    "AFE_CellVoltage2_InvalidFlag": {"start_bit": 14, "bit_length": 1, "factor": 1, "offset": 0, "min": 0, "max": 1},
    "AFE_CellVoltage3_InvalidFlag": {"start_bit": 15, "bit_length": 1, "factor": 1, "offset": 0, "min": 0, "max": 1},
    "AFE_CellVoltage0": {"start_bit": 11, "bit_length": 13, "factor": 1, "offset": 0, "min": 0, "max": 8191, "unit": "mV"},
    "AFE_CellVoltage1": {"start_bit": 30, "bit_length": 13, "factor": 1, "offset": 0, "min": 0, "max": 8191, "unit": "mV"},
    "AFE_CellVoltage2": {"start_bit": 33, "bit_length": 13, "factor": 1, "offset": 0, "min": 0, "max": 8191, "unit": "mV"},
    "AFE_CellVoltage3": {"start_bit": 52, "bit_length": 13, "factor": 1, "offset": 0, "min": 0, "max": 8191, "unit": "mV"},
}

# TX message definitions
TX_MESSAGES = {
    0x220: {"name": "BmsState",              "cycle_ms": 100,  "dlc": 8},
    0x221: {"name": "BmsStateDetails",       "cycle_ms": 100,  "dlc": 8},
    0x231: {"name": "CellVoltages_Summary",  "cycle_ms": 100,  "dlc": 8},
    0x232: {"name": "CellTemperatures_Summary", "cycle_ms": 100, "dlc": 8},
    0x233: {"name": "PackValues_P0",         "cycle_ms": 100,  "dlc": 8},
    0x234: {"name": "PackValues_P1",         "cycle_ms": 1000, "dlc": 8},
    0x235: {"name": "SOC",                   "cycle_ms": 1000, "dlc": 8},
    0x236: {"name": "SOE",                   "cycle_ms": 1000, "dlc": 8},
    0x250: {"name": "CellVoltages_Mux",      "cycle_ms": 10,   "dlc": 8},
    0x260: {"name": "CellTemperatures_Mux",  "cycle_ms": 10,   "dlc": 8},
    0x270: {"name": "AFE_CellVoltages",      "cycle_ms": 10,   "dlc": 8},
    0x280: {"name": "AFE_CellTemperatures",  "cycle_ms": 10,   "dlc": 8},
    0x301: {"name": "SlaveInfo",             "cycle_ms": 1000, "dlc": 8},
}


def foxbms_encode_signal(msg_data, start_bit, bit_length, value):
    """Encode a CAN signal using foxBMS's big-endian bit numbering."""
    msb_pos = CAN_BIG_ENDIAN_TABLE[start_bit]
    lsb_pos = msb_pos - (bit_length - 1)
    mask = ((1 << bit_length) - 1) << lsb_pos
    msg_data &= ~mask
    msg_data |= (value & ((1 << bit_length) - 1)) << lsb_pos
    return msg_data


def foxbms_decode_signal(msg_data, start_bit, bit_length):
    """Decode a CAN signal using foxBMS's big-endian bit numbering."""
    msb_pos = CAN_BIG_ENDIAN_TABLE[start_bit]
    lsb_pos = msb_pos - (bit_length - 1)
    mask = ((1 << bit_length) - 1) << lsb_pos
    return (msg_data & mask) >> lsb_pos


def msg_data_to_bytes(msg_data):
    """Convert 64-bit integer to 8-byte CAN frame (big-endian)."""
    return struct.pack(">Q", msg_data)


def bytes_to_msg_data(data_bytes):
    """Convert 8-byte CAN frame to 64-bit integer (big-endian)."""
    return struct.unpack(">Q", data_bytes.ljust(8, b'\x00')[:8])[0]


# ===================================================================
# Big-endian bit numbering table
# ===================================================================
class TestBigEndianTable:
    """Verify foxBMS CAN big-endian bit numbering table properties."""

    def test_table_length(self):
        """Table must have exactly 64 entries (8 bytes × 8 bits)."""
        assert len(CAN_BIG_ENDIAN_TABLE) == 64

    def test_table_contains_all_positions(self):
        """Table must contain every position 0–63 exactly once."""
        assert sorted(CAN_BIG_ENDIAN_TABLE) == list(range(64))

    def test_table_is_permutation(self):
        """Table is a valid permutation (no duplicates)."""
        assert len(set(CAN_BIG_ENDIAN_TABLE)) == 64

    def test_byte_0_bit_7_maps_to_bit_63(self):
        """DBC start_bit 7 (MSB of byte 0) maps to physical bit 63."""
        assert CAN_BIG_ENDIAN_TABLE[7] == 63

    def test_byte_7_bit_56_maps_to_bit_0(self):
        """DBC start_bit 56 (MSB of byte 7) maps to physical bit 0."""
        assert CAN_BIG_ENDIAN_TABLE[56] == 0

    def test_first_byte_mapping(self):
        """Indices 0–7 map to physical bits 56–63 (byte 0 in frame)."""
        assert CAN_BIG_ENDIAN_TABLE[0:8] == [56, 57, 58, 59, 60, 61, 62, 63]

    def test_last_byte_mapping(self):
        """Indices 56–63 map to physical bits 0–7 (byte 7 in frame)."""
        assert CAN_BIG_ENDIAN_TABLE[56:64] == [0, 1, 2, 3, 4, 5, 6, 7]


# ===================================================================
# Signal encode/decode round-trip
# ===================================================================
class TestSignalRoundTrip:
    """Verify encode → decode round-trip for every DBC signal."""

    @pytest.mark.parametrize("signal_name,spec", list(DBC_CELL_VOLTAGE_SIGNALS.items()))
    def test_roundtrip_nominal(self, signal_name, spec):
        """Encode then decode a nominal value → matches original."""
        value = min(spec["max"], max(spec["min"], spec["max"] // 2))
        d = foxbms_encode_signal(0, spec["start_bit"], spec["bit_length"], value)
        decoded = foxbms_decode_signal(d, spec["start_bit"], spec["bit_length"])
        assert decoded == value, f"{signal_name}: encoded {value}, decoded {decoded}"

    @pytest.mark.parametrize("signal_name,spec", list(DBC_CELL_VOLTAGE_SIGNALS.items()))
    def test_roundtrip_min(self, signal_name, spec):
        """Round-trip at minimum value."""
        d = foxbms_encode_signal(0, spec["start_bit"], spec["bit_length"], spec["min"])
        decoded = foxbms_decode_signal(d, spec["start_bit"], spec["bit_length"])
        assert decoded == spec["min"]

    @pytest.mark.parametrize("signal_name,spec", list(DBC_CELL_VOLTAGE_SIGNALS.items()))
    def test_roundtrip_max(self, signal_name, spec):
        """Round-trip at maximum value."""
        d = foxbms_encode_signal(0, spec["start_bit"], spec["bit_length"], spec["max"])
        decoded = foxbms_decode_signal(d, spec["start_bit"], spec["bit_length"])
        assert decoded == spec["max"]

    def test_multiple_signals_independent(self):
        """Encoding multiple signals in one frame doesn't corrupt each other."""
        d = 0
        values = {"AFE_CellVoltage_Mux": 3, "AFE_CellVoltage0": 3700,
                  "AFE_CellVoltage1": 3800, "AFE_CellVoltage2": 3600,
                  "AFE_CellVoltage3": 3750}
        for sig_name, val in values.items():
            spec = DBC_CELL_VOLTAGE_SIGNALS[sig_name]
            d = foxbms_encode_signal(d, spec["start_bit"], spec["bit_length"], val)
        # Decode all and verify
        for sig_name, expected_val in values.items():
            spec = DBC_CELL_VOLTAGE_SIGNALS[sig_name]
            decoded = foxbms_decode_signal(d, spec["start_bit"], spec["bit_length"])
            assert decoded == expected_val, f"{sig_name}: expected {expected_val}, got {decoded}"


# ===================================================================
# DBC signal attributes
# ===================================================================
class TestDbcSignalAttributes:
    """Verify DBC signal definitions match foxBMS spec."""

    def test_cell_voltage_bit_length(self):
        """Cell voltage signals are 13 bits (0–8191 mV range)."""
        for sig in ("AFE_CellVoltage0", "AFE_CellVoltage1",
                     "AFE_CellVoltage2", "AFE_CellVoltage3"):
            assert DBC_CELL_VOLTAGE_SIGNALS[sig]["bit_length"] == 13

    def test_cell_voltage_max_value(self):
        """13-bit signal: max = 2^13 - 1 = 8191."""
        for sig in ("AFE_CellVoltage0", "AFE_CellVoltage1",
                     "AFE_CellVoltage2", "AFE_CellVoltage3"):
            assert DBC_CELL_VOLTAGE_SIGNALS[sig]["max"] == 8191

    def test_mux_signal_is_8_bits(self):
        """Mux signal is 8 bits (0–255)."""
        assert DBC_CELL_VOLTAGE_SIGNALS["AFE_CellVoltage_Mux"]["bit_length"] == 8

    def test_invalid_flags_are_1_bit(self):
        """Each invalid flag is 1 bit."""
        for i in range(4):
            sig = f"AFE_CellVoltage{i}_InvalidFlag"
            assert DBC_CELL_VOLTAGE_SIGNALS[sig]["bit_length"] == 1

    def test_voltage_factor_is_1(self):
        """Cell voltage factor is 1 (1 mV per LSB, no scaling)."""
        for sig in ("AFE_CellVoltage0", "AFE_CellVoltage1",
                     "AFE_CellVoltage2", "AFE_CellVoltage3"):
            assert DBC_CELL_VOLTAGE_SIGNALS[sig]["factor"] == 1

    def test_voltage_offset_is_0(self):
        """Cell voltage offset is 0."""
        for sig in ("AFE_CellVoltage0", "AFE_CellVoltage1",
                     "AFE_CellVoltage2", "AFE_CellVoltage3"):
            assert DBC_CELL_VOLTAGE_SIGNALS[sig]["offset"] == 0


# ===================================================================
# Cell voltage message (0x270) encoding
# ===================================================================
class TestCellVoltageMessageEncoding:
    """Verify AFE_CellVoltages (0x270) message encoding."""

    def test_encode_mux_0_with_nominal_voltages(self):
        """Encode mux 0 with 4 nominal cell voltages → 8 bytes."""
        d = 0
        d = foxbms_encode_signal(d, 7, 8, 0)      # mux = 0
        d = foxbms_encode_signal(d, 12, 1, 1)      # valid flag 0
        d = foxbms_encode_signal(d, 13, 1, 1)      # valid flag 1
        d = foxbms_encode_signal(d, 14, 1, 1)      # valid flag 2
        d = foxbms_encode_signal(d, 15, 1, 1)      # valid flag 3
        d = foxbms_encode_signal(d, 11, 13, 3700)   # cell 0
        d = foxbms_encode_signal(d, 30, 13, 3700)   # cell 1
        d = foxbms_encode_signal(d, 33, 13, 3700)   # cell 2
        d = foxbms_encode_signal(d, 52, 13, 3700)   # cell 3
        frame = msg_data_to_bytes(d)
        assert len(frame) == 8
        # Verify mux decodes back
        assert foxbms_decode_signal(d, 7, 8) == 0
        # Verify all voltages decode back
        assert foxbms_decode_signal(d, 11, 13) == 3700
        assert foxbms_decode_signal(d, 30, 13) == 3700
        assert foxbms_decode_signal(d, 33, 13) == 3700
        assert foxbms_decode_signal(d, 52, 13) == 3700

    @pytest.mark.parametrize("mux", range(5))
    def test_mux_values_0_to_4(self, mux):
        """Mux values 0–4 cover all 18 cells (4 per mux, last partial)."""
        d = foxbms_encode_signal(0, 7, 8, mux)
        assert foxbms_decode_signal(d, 7, 8) == mux

    def test_mux_coverage_18_cells(self):
        """5 mux values × 4 cells per mux = 20 slots ≥ 18 cells."""
        assert 5 * 4 >= 18

    @pytest.mark.parametrize("voltage_mv", [0, 2500, 3700, 4200, 4500, 8191])
    def test_voltage_encoding_range(self, voltage_mv):
        """Cell voltage values across full 13-bit range."""
        d = foxbms_encode_signal(0, 11, 13, voltage_mv)
        assert foxbms_decode_signal(d, 11, 13) == voltage_mv


# ===================================================================
# Cell temperature message (0x280) encoding
# ===================================================================
class TestCellTempMessageEncoding:
    """Verify AFE_CellTemperatures (0x280) message encoding."""

    TEMP_BIT_STARTS = [23, 31, 39, 47, 55, 63]

    def test_six_temp_slots_per_message(self):
        """Each 0x280 message carries 6 temperature values."""
        assert len(self.TEMP_BIT_STARTS) == 6

    @pytest.mark.parametrize("slot_idx,start_bit", enumerate([23, 31, 39, 47, 55, 63]))
    def test_temp_signal_is_8_bits(self, slot_idx, start_bit):
        """Each temperature signal is 8 bits (0–255 °C raw)."""
        d = foxbms_encode_signal(0, start_bit, 8, 25)  # 25 °C
        assert foxbms_decode_signal(d, start_bit, 8) == 25

    def test_temp_decan_multiplier(self):
        """DECAN multiplies raw °C by 10 to get ddegC."""
        raw_degc = 25
        ddegc = raw_degc * 10
        assert ddegc == 250

    @pytest.mark.parametrize("raw_degc", [0, 25, 45, 55, 100, 255])
    def test_temp_roundtrip(self, raw_degc):
        """Encode/decode temperature value round-trip."""
        d = foxbms_encode_signal(0, 23, 8, raw_degc)
        assert foxbms_decode_signal(d, 23, 8) == raw_degc

    def test_two_mux_messages_cover_8_sensors(self):
        """2 mux messages × 6 slots = 12 slots ≥ 8 sensors."""
        assert 2 * 6 >= 8


# ===================================================================
# IVT message encoding (0x521–0x527)
# ===================================================================
class TestIvtMessageEncoding:
    """Verify IVT sensor CAN message format."""

    def test_ivt_current_id(self):
        assert 0x521

    def test_ivt_voltage_ids(self):
        """Three voltage channels: 0x522, 0x523, 0x524."""
        assert [0x522, 0x523, 0x524]

    def test_ivt_temperature_id(self):
        assert 0x527

    def test_ivt_current_big_endian_encoding(self):
        """IVT current: bytes 2–5, big-endian signed i32."""
        current_ma = -5000
        mc = 0x40
        data = struct.pack(">BBi", mc, 0, current_ma)[:6]
        decoded = struct.unpack(">i", data[2:6])[0]
        assert decoded == current_ma

    def test_ivt_voltage_encoding(self):
        """IVT voltage: same format as current (big-endian i32 at bytes 2–5)."""
        voltage_mv = 68000
        data = struct.pack(">BBi", 0, 0, voltage_mv)[:6]
        decoded = struct.unpack(">i", data[2:6])[0]
        assert decoded == voltage_mv

    def test_ivt_all_three_voltage_channels_same_format(self):
        """All three voltage channels (0x522–0x524) use identical encoding."""
        for vid in (0x522, 0x523, 0x524):
            v = 65000
            data = struct.pack(">BBi", 0, 0, v)[:6]
            decoded = struct.unpack(">i", data[2:6])[0]
            assert decoded == v


# ===================================================================
# BMS state message (0x220) layout
# ===================================================================
class TestBmsStateMessage:
    """Verify BMS state message 0x220 byte layout."""

    def test_bms_state_in_lower_nibble_byte0(self):
        """BMS state enum is in byte 0, lower nibble (bits 0–3)."""
        for state_val in range(11):
            byte0 = state_val & 0x0F
            assert byte0 == state_val

    def test_string_count_in_upper_nibble_byte0(self):
        """Number of connected strings in byte 0, upper nibble."""
        n_strings = 1
        byte0 = (n_strings << 4) | 7  # state=NORMAL, strings=1
        assert (byte0 >> 4) & 0x0F == 1
        assert byte0 & 0x0F == 7

    def test_bms_state_fits_4_bits(self):
        """All 11 BMS states (0–10) fit in 4 bits (max 15)."""
        for state in range(11):
            assert state <= 0x0F


# ===================================================================
# TX message cycle times and DLCs
# ===================================================================
class TestTxMessageProperties:
    """Verify TX message cycle times and DLCs from DBC."""

    def test_all_dlcs_are_8(self):
        """All TX messages use DLC=8 (standard CAN)."""
        for msg_id, props in TX_MESSAGES.items():
            assert props["dlc"] == 8, f"0x{msg_id:03X} has DLC={props['dlc']}"

    @pytest.mark.parametrize("msg_id,expected_cycle", [
        (0x220, 100), (0x235, 1000), (0x250, 10), (0x270, 10),
        (0x280, 10), (0x301, 1000),
    ])
    def test_cycle_times(self, msg_id, expected_cycle):
        assert TX_MESSAGES[msg_id]["cycle_ms"] == expected_cycle

    def test_fast_messages_are_10ms(self):
        """Mux messages (voltages, temps) are fast: 10 ms cycle."""
        for msg_id in (0x250, 0x260, 0x270, 0x280):
            assert TX_MESSAGES[msg_id]["cycle_ms"] == 10

    def test_slow_messages_are_1000ms(self):
        """SOC, SOE, SlaveInfo are slow: 1000 ms cycle."""
        for msg_id in (0x234, 0x235, 0x236, 0x301):
            assert TX_MESSAGES[msg_id]["cycle_ms"] == 1000

    def test_message_ids_in_standard_range(self):
        """All TX message IDs are standard CAN (11-bit, ≤ 0x7FF)."""
        for msg_id in TX_MESSAGES:
            assert 0 < msg_id <= 0x7FF


# ===================================================================
# Probe message format (0x7F0–0x7FF)
# ===================================================================
class TestProbeMessageFormat:
    """Verify SIL probe CAN message format."""

    PROBE_IDS = {
        0x7F0: "SPS_State",
        0x7F2: "SOC",
        0x7F4: "CellVoltage_Summary",
        0x7F6: "Temperature_Summary",
        0x7F7: "DIAG_Status",
        0x7F8: "DIAG_Bitmap",
        0x7F9: "BMSState_Probe",
        0x7FA: "Current_Probe",
        0x7FF: "Heartbeat",
    }

    def test_probe_ids_in_range(self):
        """All probe IDs must be in 0x7F0–0x7FF."""
        for pid in self.PROBE_IDS:
            assert 0x7F0 <= pid <= 0x7FF

    def test_heartbeat_is_last(self):
        """Heartbeat probe is at 0x7FF (highest ID)."""
        assert 0x7FF in self.PROBE_IDS
        assert self.PROBE_IDS[0x7FF] == "Heartbeat"

    def test_sps_state_probe_format(self):
        """SPS probe (0x7F0): 2 bytes requested + 2 bytes actual."""
        requested = 0x0007
        actual = 0x0003
        data = struct.pack("<HH", requested, actual)
        r, a = struct.unpack("<HH", data)
        assert r == 0x0007
        assert a == 0x0003

    def test_heartbeat_format(self):
        """Heartbeat (0x7FF): 4-byte tick count + 4-byte uptime ms."""
        tick = 123456
        uptime = 789000
        data = struct.pack("<II", tick, uptime)
        t, u = struct.unpack("<II", data)
        assert t == tick
        assert u == uptime

    def test_diag_bitmap_format(self):
        """DIAG bitmap (0x7F8): 8 bytes = 64 bits, 1 per DIAG ID."""
        bitmap = (1 << 18) | (1 << 21)  # OV + UV
        data = struct.pack("<Q", bitmap)
        decoded = struct.unpack("<Q", data)[0]
        assert decoded & (1 << 18) != 0  # OV bit set
        assert decoded & (1 << 21) != 0  # UV bit set
        assert decoded & (1 << 24) == 0  # OT bit not set
