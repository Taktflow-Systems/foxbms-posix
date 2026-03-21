"""Fault injector — sends SIL override commands via CAN.

Provides inject, inject_multi, clear, and monitor_and_update operations
for controlling the vECU through CAN 0x7E0 override frames.
"""

import struct
import time
from typing import List

from fi.can_bus import CanBus
from fi.constants import (
    CAN_OVERRIDE_ID,
    SIL_CELL_TEMP,
    SIL_CELL_VOLTAGE,
    SIL_PACK_CURRENT,
)
from fi.probe_monitor import ProbeMonitor


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
