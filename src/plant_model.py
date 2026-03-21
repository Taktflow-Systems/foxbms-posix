#!/usr/bin/env python3
"""
Minimal plant model for foxBMS POSIX vECU.
Sends fake battery data on SocketCAN so foxBMS transitions to NORMAL state.

CAN Messages sent:
  0x521 - IVT Current (0A)
  0x522 - IVT Voltage (66600 mV = 66.6V for 18S pack)
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

# foxBMS CAN big-endian encoding using the exact same lookup table as foxBMS
CAN_BIG_ENDIAN_TABLE = [
    56, 57, 58, 59, 60, 61, 62, 63, 48, 49, 50, 51, 52, 53, 54, 55,
    40, 41, 42, 43, 44, 45, 46, 47, 32, 33, 34, 35, 36, 37, 38, 39,
    24, 25, 26, 27, 28, 29, 30, 31, 16, 17, 18, 19, 20, 21, 22, 23,
     8,  9, 10, 11, 12, 13, 14, 15,  0,  1,  2,  3,  4,  5,  6,  7,
]

def foxbms_encode_signal(msg_data, start_bit, bit_length, value):
    """Encode a CAN signal using foxBMS's big-endian bit numbering.
    msg_data: 64-bit integer (message data, MSB=bit63, LSB=bit0)
    start_bit: DBC-style big-endian start bit (MSB of signal)
    bit_length: signal length in bits
    value: unsigned integer value
    Returns updated msg_data.
    """
    # Convert DBC start bit to actual MSB position
    msb_pos = CAN_BIG_ENDIAN_TABLE[start_bit]
    # LSB position
    lsb_pos = msb_pos - (bit_length - 1)
    # Place value at the correct position
    mask = ((1 << bit_length) - 1) << lsb_pos
    msg_data &= ~mask  # clear bits
    msg_data |= (value & ((1 << bit_length) - 1)) << lsb_pos
    return msg_data

def msg_data_to_bytes(msg_data):
    """Convert 64-bit message data to 8-byte CAN frame (big-endian byte order)."""
    return struct.pack(">Q", msg_data)

def encode_cell_voltage_msg(mux, voltages_mv):
    """Encode foxBMS cell voltage message (0x270) using exact foxBMS encoding."""
    d = 0
    d = foxbms_encode_signal(d, 7, 8, mux)          # Mux
    d = foxbms_encode_signal(d, 12, 1, 1)            # Invalid flag 0: 1=VALID (DECAN_DATA_IS_VALID=1)
    d = foxbms_encode_signal(d, 13, 1, 1)            # Invalid flag 1: 1=VALID
    d = foxbms_encode_signal(d, 14, 1, 1)            # Invalid flag 2: 1=VALID
    d = foxbms_encode_signal(d, 15, 1, 1)            # Invalid flag 3: 1=VALID
    d = foxbms_encode_signal(d, 11, 13, voltages_mv[0])  # Voltage 0
    d = foxbms_encode_signal(d, 30, 13, voltages_mv[1])  # Voltage 1
    d = foxbms_encode_signal(d, 33, 13, voltages_mv[2])  # Voltage 2
    d = foxbms_encode_signal(d, 52, 13, voltages_mv[3])  # Voltage 3
    return msg_data_to_bytes(d)

def encode_cell_temp_msg(mux, temps_ddegc):
    """Encode foxBMS cell temperature message (0x280)."""
    d = 0
    d = foxbms_encode_signal(d, 7, 8, mux)
    d = foxbms_encode_signal(d, 12, 1, 1)  # Invalid flag 0: 1=VALID
    d = foxbms_encode_signal(d, 13, 1, 1)  # Invalid flag 1: 1=VALID
    d = foxbms_encode_signal(d, 14, 1, 1)  # Invalid flag 2: 1=VALID
    d = foxbms_encode_signal(d, 11, 13, temps_ddegc[0] if len(temps_ddegc) > 0 else 0)
    d = foxbms_encode_signal(d, 30, 13, temps_ddegc[1] if len(temps_ddegc) > 1 else 0)
    d = foxbms_encode_signal(d, 33, 13, temps_ddegc[2] if len(temps_ddegc) > 2 else 0)
    return msg_data_to_bytes(d)

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

        # IVT messages: Isabellenhuette IVT-S format
        # Byte 0: measurement counter (bits 7:2) + status bits (1:0)
        # Byte 1: status (channel error = bit 5, system error = bit 4, etc.)
        # Byte 2-5: measurement value (int32 big-endian)
        # Status bytes must be 0 (no errors) to avoid triggering foxBMS error handling
        msg_counter = (tick & 0x3F) << 2  # 6-bit counter in bits [7:2], status bits [1:0] = 0

        # IVT Current (0x521)
        current_ma = 0  # 0 A
        can_send(0x521, struct.pack(">BBi", msg_counter & 0xFF, 0, current_ma)[:6])

        # IVT Voltage 1 (0x522): pack voltage = 18 cells × 3700mV = 66600mV
        pack_voltage_mv = 66600
        can_send(0x522, struct.pack(">BBi", msg_counter & 0xFF, 0, pack_voltage_mv)[:6])

        # IVT Voltage 2 (0x523)
        can_send(0x523, struct.pack(">BBi", msg_counter & 0xFF, 0, pack_voltage_mv)[:6])

        # IVT Voltage 3 (0x524) — used by redundancy module for HV bus voltage
        can_send(0x524, struct.pack(">BBi", msg_counter & 0xFF, 0, pack_voltage_mv)[:6])

        # IVT Temperature (0x527)
        temp_degc = 250  # 25.0°C * 10
        can_send(0x527, struct.pack(">BBi", msg_counter & 0xFF, 0, temp_degc)[:6])

        # BMS State Request (0x210):
        # Signal: start_bit=1, length=2, big-endian
        # Value 0=STANDBY, 1=NORMAL, 2=CHARGE
        # Send STANDBY first, then NORMAL repeatedly
        if tick < 30:
            can_send(0x210, bytes([0x00, 0, 0, 0, 0, 0, 0, 0]))  # STANDBY
        else:
            can_send(0x210, bytes([0x02, 0, 0, 0, 0, 0, 0, 0]))  # NORMAL

        if tick == 30:
            print("[plant] Switching to NORMAL request")

        # Cell Voltages (0x270): 18 cells, 4 per message, need 5 mux values (0-4)
        # BS_NR_OF_CELL_BLOCKS_PER_MODULE = 18
        for mux in range(5):  # 5 × 4 = 20 slots (18 used, 2 unused)
            data = encode_cell_voltage_msg(mux, [3700, 3700, 3700, 3700])
            can_send(0x270, data)

        # Cell Temperatures (0x280)
        data = encode_cell_temp_msg(0, [250, 250, 250])
        can_send(0x280, data)

        if tick % 100 == 0:
            print(f"[plant] tick={tick} sent IVT data")

        time.sleep(0.1)  # 100ms cycle

except KeyboardInterrupt:
    print("\nPlant model stopped")
    s.close()
