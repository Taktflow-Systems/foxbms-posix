"""SocketCAN raw socket wrapper for fault injection tests.

Provides send, receive, and drain operations on a Linux SocketCAN interface.
"""

import socket
import struct
from typing import Optional, Tuple


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
        """Close the socket."""
        self.sock.close()
