"""Probe monitor for SIL CAN frames.

Tracks all SIL probe state: DIAG flags, SPS contactor state, BMS state
machine, cell voltage ranges, temperature ranges, and pack current.
"""

import struct
import time

from fi.constants import (
    BMS_NORMAL,
    CAN_BMS_STATE_MSG,
    CAN_PROBE_CELL_VOLTAGE,
    CAN_PROBE_CURRENT,
    CAN_PROBE_DIAG,
    CAN_PROBE_DIAG_BITMAP,
    CAN_PROBE_SPS,
    CAN_PROBE_STATE,
    CAN_PROBE_TEMPERATURE,
)


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
        # Cell voltage and temperature tracking (from probes 0x7F4, 0x7F6)
        self.cell_voltage_min_mv: int = 0
        self.cell_voltage_max_mv: int = 0
        self.temperature_min_ddegc: int = 0
        self.temperature_max_ddegc: int = 0
        self.pack_current_ma: int = 0
        self.normal_entry_time: float = 0.0  # monotonic time when BMS entered NORMAL

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
            old_bms_state = self.bms_state
            self.bms_state = data[4]
            # Track when BMS enters NORMAL
            if self.bms_state == BMS_NORMAL and old_bms_state != BMS_NORMAL:
                self.normal_entry_time = time.monotonic()

        elif can_id == CAN_PROBE_SPS and len(data) >= 4:
            self.sps_requested = struct.unpack_from("<H", data, 0)[0]
            self.sps_actual = struct.unpack_from("<H", data, 2)[0]

        elif can_id == CAN_PROBE_CELL_VOLTAGE and len(data) >= 4:
            # Probe 0x7F4: cell voltage min (u16 LE) + max (u16 LE) in mV
            self.cell_voltage_min_mv = struct.unpack_from("<H", data, 0)[0]
            self.cell_voltage_max_mv = struct.unpack_from("<H", data, 2)[0]

        elif can_id == CAN_PROBE_TEMPERATURE and len(data) >= 4:
            # Probe 0x7F6: temperature min (i16 LE) + max (i16 LE) in ddegC
            self.temperature_min_ddegc = struct.unpack_from("<h", data, 0)[0]
            self.temperature_max_ddegc = struct.unpack_from("<h", data, 2)[0]

        elif can_id == CAN_PROBE_CURRENT and len(data) >= 4:
            # Probe 0x7FA: pack current in mA (i32 LE)
            self.pack_current_ma = struct.unpack_from("<i", data, 0)[0]

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
        """Check if BMS is in ERROR state."""
        return self.bms_state == BMS_ERROR

    def bms_in_normal(self) -> bool:
        """Check if BMS is in NORMAL state."""
        return self.bms_state == BMS_NORMAL
