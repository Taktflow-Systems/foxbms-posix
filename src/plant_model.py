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

def set_can_signal_be(data, start_bit, length, value):
    """Set a CAN signal in big-endian (Motorola) byte order.
    start_bit: DBC-style big-endian start bit
    length: signal length in bits
    value: unsigned integer value to set
    """
    # Convert DBC start bit to bit position in the 64-bit message data
    for i in range(length):
        # Calculate byte and bit from DBC-style big-endian numbering
        byte_pos = start_bit // 8
        bit_in_byte = start_bit % 8
        bit_val = (value >> (length - 1 - i)) & 1
        if bit_val:
            data[byte_pos] |= (1 << bit_in_byte)
        else:
            data[byte_pos] &= ~(1 << bit_in_byte)
        # Move to next bit in big-endian order
        if bit_in_byte == 0:
            start_bit = start_bit + 15  # next byte, MSB
        else:
            start_bit = start_bit - 1

def encode_cell_voltage_msg(mux, voltages_mv):
    """Encode a foxBMS cell voltage CAN message (0x270).
    mux: multiplexer value (0, 1, ...)
    voltages_mv: list of 4 voltages in mV
    Returns 8-byte data.
    """
    data = bytearray(8)
    # Mux: start_bit=7, length=8
    set_can_signal_be(data, 7, 8, mux)
    # Invalid flags: start_bits 12,13,14,15, length=1 each → all 0 (valid)
    # Voltage 0: start_bit=11, length=13
    set_can_signal_be(data, 11, 13, voltages_mv[0] & 0x1FFF)
    # Voltage 1: start_bit=30, length=13
    set_can_signal_be(data, 30, 13, voltages_mv[1] & 0x1FFF)
    # Voltage 2: start_bit=33, length=13
    set_can_signal_be(data, 33, 13, voltages_mv[2] & 0x1FFF)
    # Voltage 3: start_bit=52, length=13
    set_can_signal_be(data, 52, 13, voltages_mv[3] & 0x1FFF)
    return bytes(data)

def encode_cell_temp_msg(mux, temps_ddegc):
    """Encode a foxBMS cell temperature CAN message (0x280).
    mux: multiplexer value
    temps_ddegc: list of temperatures in deci-degrees C
    Returns 8-byte data.
    """
    data = bytearray(8)
    # Mux: start_bit=7, length=8
    set_can_signal_be(data, 7, 8, mux)
    # Temperature signals — check foxBMS source for exact positions
    # For now, use same layout as voltages (approximate)
    set_can_signal_be(data, 11, 13, temps_ddegc[0] & 0x1FFF)
    if len(temps_ddegc) > 1:
        set_can_signal_be(data, 30, 13, temps_ddegc[1] & 0x1FFF)
    if len(temps_ddegc) > 2:
        set_can_signal_be(data, 33, 13, temps_ddegc[2] & 0x1FFF)
    return bytes(data)

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

        # IVT Voltage 1 (0x522)
        pack_voltage_mv = 22200  # 22.2V
        can_send(0x522, struct.pack(">BBi", msg_counter & 0xFF, 0, pack_voltage_mv)[:6])

        # IVT Voltage 2 (0x523)
        can_send(0x523, struct.pack(">BBi", msg_counter & 0xFF, 0, pack_voltage_mv)[:6])

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

        # Cell Voltages (0x270) and Temperatures (0x280)
        # Use CAN signal encoding helper
        for mux in range(2):
            data = encode_cell_voltage_msg(mux, [3700, 3700, 3700, 3700])
            can_send(0x270, data)

        data = encode_cell_temp_msg(0, [250, 250, 250])  # 25.0°C in deci-degrees
        can_send(0x280, data)

        if tick % 100 == 0:
            print(f"[plant] tick={tick} sent IVT data")

        time.sleep(0.1)  # 100ms cycle

except KeyboardInterrupt:
    print("\nPlant model stopped")
    s.close()
