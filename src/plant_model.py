#!/usr/bin/env python3
"""
Minimal plant model for foxBMS POSIX vECU.
Sends fake battery data on SocketCAN so foxBMS transitions to NORMAL state.

CAN Messages sent:
  0x521 - IVT Current (0A)
  0x522 - IVT Voltage (22200 mV = 22.2V for 6S pack)
  0x523 - IVT Voltage 2
  0x524 - IVT Voltage 3
  0x525 - IVT Current counter
  0x526 - IVT Energy counter
"""

import socket
import struct
import time
import sys

CAN_INTERFACE = sys.argv[1] if len(sys.argv) > 1 else "vcan1"

# Open SocketCAN
s = socket.socket(socket.AF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
s.bind((CAN_INTERFACE,))
print(f"Plant model sending on {CAN_INTERFACE}")

def can_send(can_id, data):
    """Send a CAN frame"""
    dlc = len(data)
    data_padded = data + bytes(8 - dlc)
    frame = struct.pack("=IB3x8s", can_id, dlc, data_padded)
    s.send(frame)

tick = 0
try:
    while True:
        tick += 1

        # IVT Current (0x521): int32 current in mA, big-endian, DLC=6
        # Byte 0-1: message counter + status
        # Byte 2-5: current in mA (int32 big-endian)
        current_ma = 0  # 0 A
        can_send(0x521, struct.pack(">HI", tick & 0xFFFF, current_ma)[:6])

        # IVT Voltage 1 (0x522): pack voltage in mV
        # Byte 0-1: counter + status
        # Byte 2-5: voltage in mV (int32 big-endian)
        pack_voltage_mv = 22200  # 22.2V (6 cells * 3.7V)
        can_send(0x522, struct.pack(">HI", tick & 0xFFFF, pack_voltage_mv)[:6])

        # IVT Voltage 2 (0x523)
        can_send(0x523, struct.pack(">HI", tick & 0xFFFF, pack_voltage_mv)[:6])

        # IVT Temperature (0x527)
        temp_degc = 250  # 25.0°C * 10
        can_send(0x527, struct.pack(">HI", tick & 0xFFFF, temp_degc)[:6])

        # BMS State Request (0x210):
        # Signal: start_bit=1, length=2, big-endian
        # Value 0=STANDBY, 1=NORMAL, 2=CHARGE
        # Big-endian start_bit=1 length=2: byte 0 bits [1:0]
        # STANDBY: value 0 → byte0 = 0x00
        # NORMAL: value 1 → byte0 = 0x02 (bit 1 set)
        if tick == 30:
            can_send(0x210, bytes([0x00, 0, 0, 0, 0, 0, 0, 0]))
            print("[plant] Sent STANDBY request (0x210) signal=0")

        if tick == 50:
            can_send(0x210, bytes([0x02, 0, 0, 0, 0, 0, 0, 0]))
            print("[plant] Sent NORMAL request (0x210) signal=1")

        if tick % 100 == 0:
            print(f"[plant] tick={tick} sent IVT data")

        time.sleep(0.1)  # 100ms cycle

except KeyboardInterrupt:
    print("\nPlant model stopped")
    s.close()
