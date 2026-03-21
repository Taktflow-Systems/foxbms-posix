#!/usr/bin/env python3
"""
foxBMS POSIX vECU — Dynamic Battery Plant Model

Simulates a realistic 18S Li-ion battery pack with:
- Coulomb-counting SOC (decreases under load)
- OCV(SOC) voltage curve per cell
- IR drop on pack voltage under load
- Per-cell voltage noise (±10 mV Gaussian)
- Closed-loop: reads foxBMS contactor state from CAN TX

CAN Messages sent:
  0x521 - IVT Current (dynamic, based on contactor state)
  0x522 - IVT Voltage 1 (pack voltage with IR drop)
  0x523 - IVT Voltage 2 (same)
  0x524 - IVT Voltage 3 (same, for redundancy module)
  0x527 - IVT Temperature (25.0°C)
  0x270 - Cell voltages (18 cells, OCV-based + noise)
  0x280 - Cell temperatures (25.0°C)
  0x210 - BMS state request (STANDBY → NORMAL)
"""

import socket
import struct
import time
import sys
import random
import fcntl
import os

CAN_INTERFACE = sys.argv[1] if len(sys.argv) > 1 else "vcan1"

# ================================================================
# Battery parameters
# ================================================================
N_CELLS = 18
Q_CELL_MAH = 3000.0        # Cell capacity (mAh)
R_CELL_MOHM = 50.0          # Internal resistance per cell (mΩ)
R_TOTAL_MOHM = R_CELL_MOHM * N_CELLS  # Total string resistance (mΩ)
I_DISCHARGE_MA = 10000      # Discharge current when NORMAL (10 A)
DT_S = 0.1                  # Loop period (100 ms)

# OCV(SOC) lookup — linear approximation (mV)
# 3400 mV @ 0% SOC → 4200 mV @ 100% SOC
def ocv_mv(soc_pct):
    """Open-circuit voltage from SOC (linear model)."""
    return int(3400.0 + 800.0 * (soc_pct / 100.0))

# ================================================================
# foxBMS CAN big-endian encoding (same lookup table as foxBMS)
# ================================================================
CAN_BIG_ENDIAN_TABLE = [
    56, 57, 58, 59, 60, 61, 62, 63, 48, 49, 50, 51, 52, 53, 54, 55,
    40, 41, 42, 43, 44, 45, 46, 47, 32, 33, 34, 35, 36, 37, 38, 39,
    24, 25, 26, 27, 28, 29, 30, 31, 16, 17, 18, 19, 20, 21, 22, 23,
     8,  9, 10, 11, 12, 13, 14, 15,  0,  1,  2,  3,  4,  5,  6,  7,
]

def foxbms_encode_signal(msg_data, start_bit, bit_length, value):
    """Encode a CAN signal using foxBMS's big-endian bit numbering."""
    msb_pos = CAN_BIG_ENDIAN_TABLE[start_bit]
    lsb_pos = msb_pos - (bit_length - 1)
    mask = ((1 << bit_length) - 1) << lsb_pos
    msg_data &= ~mask
    msg_data |= (value & ((1 << bit_length) - 1)) << lsb_pos
    return msg_data

def msg_data_to_bytes(msg_data):
    """Convert 64-bit message data to 8-byte CAN frame."""
    return struct.pack(">Q", msg_data)

def encode_cell_voltage_msg(mux, voltages_mv):
    """Encode foxBMS cell voltage message (0x270)."""
    d = 0
    d = foxbms_encode_signal(d, 7, 8, mux)
    d = foxbms_encode_signal(d, 12, 1, 1)   # Invalid flag 0: 1=VALID
    d = foxbms_encode_signal(d, 13, 1, 1)   # Invalid flag 1: 1=VALID
    d = foxbms_encode_signal(d, 14, 1, 1)   # Invalid flag 2: 1=VALID
    d = foxbms_encode_signal(d, 15, 1, 1)   # Invalid flag 3: 1=VALID
    d = foxbms_encode_signal(d, 11, 13, voltages_mv[0])
    d = foxbms_encode_signal(d, 30, 13, voltages_mv[1])
    d = foxbms_encode_signal(d, 33, 13, voltages_mv[2])
    d = foxbms_encode_signal(d, 52, 13, voltages_mv[3])
    return msg_data_to_bytes(d)

def encode_cell_temp_msg(mux, temps_ddegc):
    """Encode foxBMS cell temperature message (0x280)."""
    d = 0
    d = foxbms_encode_signal(d, 7, 8, mux)
    d = foxbms_encode_signal(d, 12, 1, 1)
    d = foxbms_encode_signal(d, 13, 1, 1)
    d = foxbms_encode_signal(d, 14, 1, 1)
    d = foxbms_encode_signal(d, 11, 13, temps_ddegc[0] if len(temps_ddegc) > 0 else 0)
    d = foxbms_encode_signal(d, 30, 13, temps_ddegc[1] if len(temps_ddegc) > 1 else 0)
    d = foxbms_encode_signal(d, 33, 13, temps_ddegc[2] if len(temps_ddegc) > 2 else 0)
    return msg_data_to_bytes(d)

# ================================================================
# SocketCAN setup
# ================================================================
s = socket.socket(socket.AF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
s.bind((CAN_INTERFACE,))

# Set non-blocking for RX (closed-loop feedback)
s.setblocking(False)

print(f"[plant] Dynamic plant model on {CAN_INTERFACE}")
print(f"[plant] {N_CELLS}S pack, {Q_CELL_MAH} mAh, R_int={R_CELL_MOHM} mΩ/cell")
print(f"[plant] Discharge current: {I_DISCHARGE_MA/1000:.0f} A when NORMAL")

def can_send(can_id, data):
    """Send a CAN frame."""
    dlc = len(data)
    data_padded = data + bytes(8 - dlc)
    frame = struct.pack("=IB3x8s", can_id, dlc, data_padded)
    s.send(frame)

# ================================================================
# Battery state
# ================================================================
soc_pct = 50.0              # Initial SOC (%)
current_ma = 0              # Current flowing (mA, positive = discharge)
bms_state_normal = False     # True when foxBMS reports NORMAL
per_cell_offset = [random.gauss(0, 5) for _ in range(N_CELLS)]  # Fixed per-cell variation

tick = 0
try:
    while True:
        tick += 1

        # ============================================================
        # Closed-loop: read foxBMS CAN TX to detect NORMAL state
        # ============================================================
        try:
            while True:
                rx_frame = s.recv(16)
                if len(rx_frame) >= 16:
                    rx_id = struct.unpack("=I", rx_frame[0:4])[0] & 0x1FFFFFFF
                    rx_data = rx_frame[8:16]
                    if rx_id == 0x220 and len(rx_data) >= 1:
                        bms_state = rx_data[0] & 0x0F  # Lower nibble = BMS state
                        if bms_state == 7 and not bms_state_normal:
                            bms_state_normal = True
                            print(f"[plant] foxBMS NORMAL detected at tick {tick} — starting discharge")
                        elif bms_state != 7 and bms_state_normal:
                            bms_state_normal = False
                            print(f"[plant] foxBMS left NORMAL (state={bms_state}) — stopping discharge")
        except BlockingIOError:
            pass  # No more frames to read

        # ============================================================
        # Current model
        # ============================================================
        if bms_state_normal:
            current_ma = I_DISCHARGE_MA  # 10 A discharge
        else:
            current_ma = 0

        # ============================================================
        # SOC integration (coulomb counting)
        # ============================================================
        if current_ma > 0:
            # dSOC = I × dt / (Q × 3600) × 100%
            soc_pct -= (current_ma / 1000.0) / (Q_CELL_MAH / 1000.0) * (DT_S / 3600.0) * 100.0
            soc_pct = max(0.0, min(100.0, soc_pct))

        # ============================================================
        # Cell voltage model
        # ============================================================
        v_ocv = ocv_mv(soc_pct)

        # Per-cell voltages with fixed offset + random noise
        cell_voltages = []
        for i in range(N_CELLS):
            v = v_ocv + per_cell_offset[i] + random.gauss(0, 5)  # ±5 mV noise per tick
            cell_voltages.append(max(2500, min(4500, int(v))))

        # Pack voltage with IR drop: V_pack = N × V_OCV − I × R_total
        ir_drop_mv = int((current_ma / 1000.0) * R_TOTAL_MOHM)
        pack_voltage_mv = sum(cell_voltages) - ir_drop_mv
        pack_voltage_mv = max(0, pack_voltage_mv)

        # ============================================================
        # IVT messages
        # ============================================================
        msg_counter = (tick & 0x3F) << 2  # 6-bit counter, status bits = 0

        # IVT Current (0x521) — IVT convention: negative = discharge
        ivt_current = -current_ma if current_ma > 0 else 0
        can_send(0x521, struct.pack(">BBi", msg_counter & 0xFF, 0, ivt_current)[:6])

        # IVT Voltage 1/2/3 (0x522-0x524)
        can_send(0x522, struct.pack(">BBi", msg_counter & 0xFF, 0, pack_voltage_mv)[:6])
        can_send(0x523, struct.pack(">BBi", msg_counter & 0xFF, 0, pack_voltage_mv)[:6])
        can_send(0x524, struct.pack(">BBi", msg_counter & 0xFF, 0, pack_voltage_mv)[:6])

        # IVT Temperature (0x527)
        can_send(0x527, struct.pack(">BBi", msg_counter & 0xFF, 0, 250)[:6])  # 25.0°C

        # ============================================================
        # BMS State Request (0x210)
        # ============================================================
        if tick < 30:
            can_send(0x210, bytes([0x00, 0, 0, 0, 0, 0, 0, 0]))  # STANDBY
        else:
            can_send(0x210, bytes([0x02, 0, 0, 0, 0, 0, 0, 0]))  # NORMAL

        if tick == 30:
            print("[plant] Switching to NORMAL request")

        # ============================================================
        # Cell Voltages (0x270)
        # ============================================================
        for mux in range(5):  # 5 × 4 = 20 slots (18 cells used)
            base = mux * 4
            volts = []
            for j in range(4):
                idx = base + j
                if idx < N_CELLS:
                    volts.append(cell_voltages[idx])
                else:
                    volts.append(0)  # Unused slots
            can_send(0x270, encode_cell_voltage_msg(mux, volts))

        # Cell Temperatures (0x280)
        can_send(0x280, encode_cell_temp_msg(0, [250, 250, 250]))

        # ============================================================
        # Status log
        # ============================================================
        if tick % 50 == 0:  # Every 5 seconds
            print(f"[plant] tick={tick} SOC={soc_pct:.1f}% I={current_ma/1000:.1f}A "
                  f"Vcell={v_ocv}mV Vpack={pack_voltage_mv}mV IR={ir_drop_mv}mV "
                  f"{'NORMAL' if bms_state_normal else 'idle'}")

        time.sleep(DT_S)

except KeyboardInterrupt:
    print(f"\n[plant] Stopped. Final SOC={soc_pct:.1f}%")
finally:
    s.close()
