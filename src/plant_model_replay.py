#!/usr/bin/env python3
"""
foxBMS POSIX vECU — Trip Replay Plant Model (ML Layer 1)

Replays real BMW i3 driving data through foxBMS CAN interface.
Scales 96S/94Ah pack data → 18S/3Ah foxBMS configuration.

Physics scaling:
  - Current scaled by capacity ratio (3/94) to maintain same C-rate
  - Cell voltage = pack_V / 96 (same NMC chemistry)
  - IR drop preserves naturally (R × C ≈ constant for same chemistry)
  - SOC rate of change identical (same C-rate → same dSOC/dt)
  - Temperature replayed directly (dT/dt scales at same C-rate)

Usage:
    python3 plant_model_replay.py <can_interface> <trip_csv> [--speed N] [--loop]
"""

import socket
import struct
import time
import sys
import csv
import random
import os

# ================================================================
# Configuration
# ================================================================
CAN_INTERFACE = sys.argv[1] if len(sys.argv) > 1 else "vcan1"
TRIP_CSV = sys.argv[2] if len(sys.argv) > 2 else None

# Parse optional flags
SPEED = 1.0
LOOP = False
for i, arg in enumerate(sys.argv[3:], 3):
    if arg == "--speed" and i + 1 < len(sys.argv):
        SPEED = float(sys.argv[i + 1])
    if arg == "--loop":
        LOOP = True

if not TRIP_CSV:
    print("Usage: python3 plant_model_replay.py <can_interface> <trip.csv> [--speed N] [--loop]")
    sys.exit(1)

# ================================================================
# Pack scaling: BMW i3 96S/94Ah → foxBMS 18S/3Ah
# ================================================================
BMW_CELLS_SERIES = 96
BMW_CAPACITY_AH = 94.0
FOX_CELLS_SERIES = 18
FOX_CAPACITY_AH = 3.0

CAPACITY_RATIO = FOX_CAPACITY_AH / BMW_CAPACITY_AH  # 0.0319
# Current scaling: I_fox = I_bmw × CAPACITY_RATIO (same C-rate)
# Voltage: V_cell = pack_V / BMW_CELLS_SERIES (same NMC chemistry)

# Per-cell manufacturing variation (fixed at startup)
CELL_OFFSETS_MV = [random.gauss(0, 8) for _ in range(FOX_CELLS_SERIES)]

# ================================================================
# foxBMS CAN encoding (same as plant_model.py)
# ================================================================
CAN_BIG_ENDIAN_TABLE = [
    56, 57, 58, 59, 60, 61, 62, 63, 48, 49, 50, 51, 52, 53, 54, 55,
    40, 41, 42, 43, 44, 45, 46, 47, 32, 33, 34, 35, 36, 37, 38, 39,
    24, 25, 26, 27, 28, 29, 30, 31, 16, 17, 18, 19, 20, 21, 22, 23,
     8,  9, 10, 11, 12, 13, 14, 15,  0,  1,  2,  3,  4,  5,  6,  7,
]

def foxbms_encode_signal(msg_data, start_bit, bit_length, value):
    msb_pos = CAN_BIG_ENDIAN_TABLE[start_bit]
    lsb_pos = msb_pos - (bit_length - 1)
    mask = ((1 << bit_length) - 1) << lsb_pos
    msg_data &= ~mask
    msg_data |= (value & ((1 << bit_length) - 1)) << lsb_pos
    return msg_data

def msg_data_to_bytes(msg_data):
    return struct.pack(">Q", msg_data)

def encode_cell_voltage_msg(mux, voltages_mv):
    d = 0
    d = foxbms_encode_signal(d, 7, 8, mux)
    d = foxbms_encode_signal(d, 12, 1, 1)  # VALID
    d = foxbms_encode_signal(d, 13, 1, 1)
    d = foxbms_encode_signal(d, 14, 1, 1)
    d = foxbms_encode_signal(d, 15, 1, 1)
    d = foxbms_encode_signal(d, 11, 13, voltages_mv[0])
    d = foxbms_encode_signal(d, 30, 13, voltages_mv[1])
    d = foxbms_encode_signal(d, 33, 13, voltages_mv[2])
    d = foxbms_encode_signal(d, 52, 13, voltages_mv[3])
    return msg_data_to_bytes(d)

def encode_cell_temp_msg(mux, temps_ddegc):
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
# Load trip CSV
# ================================================================
def load_trip(csv_path):
    """Load BMW i3 trip CSV. Returns list of (voltage_v, current_a, temp_c, soc_pct)."""
    rows = []
    with open(csv_path, encoding="latin-1") as f:
        reader = csv.reader(f, delimiter=";")
        header = next(reader)  # skip header
        for line in reader:
            try:
                voltage_v = float(line[7])    # Battery Voltage [V]
                current_a = float(line[8])    # Battery Current [A]
                temp_c = float(line[9])       # Battery Temperature [°C]
                soc_pct = float(line[11])     # SoC [%]
                rows.append((voltage_v, current_a, temp_c, soc_pct))
            except (ValueError, IndexError):
                continue  # skip malformed rows
    return rows

print(f"[replay] Loading {TRIP_CSV}...")
trip_data = load_trip(TRIP_CSV)
if not trip_data:
    print(f"[replay] ERROR: No valid data in {TRIP_CSV}")
    sys.exit(1)

print(f"[replay] {len(trip_data)} samples at 10Hz = {len(trip_data)/10:.0f}s trip")
print(f"[replay] V: {trip_data[0][0]:.1f}–{max(r[0] for r in trip_data):.1f}V, "
      f"I: {min(r[1] for r in trip_data):.1f}–{max(r[1] for r in trip_data):.1f}A, "
      f"T: {trip_data[0][2]:.1f}°C, SOC: {trip_data[0][3]:.1f}–{trip_data[-1][3]:.1f}%")
print(f"[replay] Scaling: {BMW_CELLS_SERIES}S/{BMW_CAPACITY_AH:.0f}Ah → "
      f"{FOX_CELLS_SERIES}S/{FOX_CAPACITY_AH:.0f}Ah (ratio={CAPACITY_RATIO:.4f})")
print(f"[replay] Speed: {SPEED}x, Loop: {LOOP}")

# ================================================================
# SocketCAN
# ================================================================
s = socket.socket(socket.AF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
s.bind((CAN_INTERFACE,))
s.setblocking(False)  # non-blocking for closed-loop RX

bms_state_normal = False  # True when foxBMS reports NORMAL (contactors closed)

def can_send(can_id, data):
    dlc = len(data)
    data_padded = data + bytes(8 - dlc)
    frame = struct.pack("=IB3x8s", can_id, dlc, data_padded)
    s.send(frame)

# ================================================================
# Main replay loop
# ================================================================
# Playback at 100ms intervals (10 samples per second from CSV at 10Hz)
# With --speed N, advance N rows per 100ms tick
rows_per_tick = max(1, int(SPEED))
tick_interval_s = 0.1  # 100ms

data_idx = 0
tick = 0
last_soc = trip_data[0][3]

try:
    while True:
        tick += 1

        # Get current data row
        if data_idx >= len(trip_data):
            if LOOP:
                data_idx = 0
                print(f"[replay] Looping trip from start")
            else:
                print(f"[replay] Trip complete. Final row {len(trip_data)}.")
                break

        bmw_v, bmw_i, bmw_t, bmw_soc = trip_data[data_idx]
        data_idx += rows_per_tick

        # ========================================================
        # Closed-loop: read foxBMS 0x220 for contactor state
        # ========================================================
        try:
            while True:
                rx_frame = s.recv(16)
                if len(rx_frame) >= 16:
                    rx_id = struct.unpack("=I", rx_frame[0:4])[0] & 0x7FF
                    if rx_id == 0x220:
                        bms_state = rx_frame[8] & 0x0F
                        if bms_state == 7 and not bms_state_normal:
                            bms_state_normal = True
                            print(f"[replay] foxBMS NORMAL detected at tick {tick} — enabling current")
                        elif bms_state != 7 and bms_state_normal:
                            bms_state_normal = False
                            print(f"[replay] foxBMS left NORMAL (state={bms_state}) — zeroing current")
        except BlockingIOError:
            pass

        # ========================================================
        # Scale BMW → foxBMS
        # ========================================================
        # Cell voltage from pack (same NMC chemistry)
        v_cell_mv = int(bmw_v / BMW_CELLS_SERIES * 1000.0)
        v_cell_mv = max(2500, min(4500, v_cell_mv))

        # Per-cell voltages with manufacturing offset
        cell_voltages = []
        for i in range(FOX_CELLS_SERIES):
            v = v_cell_mv + int(CELL_OFFSETS_MV[i])
            cell_voltages.append(max(2500, min(4500, v)))

        # Pack voltage for IVT (sum of cells — consistent by construction)
        pack_voltage_mv = sum(cell_voltages)

        # Current: only flow when contactors are closed (NORMAL state)
        # Before NORMAL: 0A (contactors open — no physical current path)
        if bms_state_normal:
            current_fox_ma = int(bmw_i * CAPACITY_RATIO * 1000.0)
        else:
            current_fox_ma = 0

        # Temperature in deci-°C
        temp_ddegc = int(bmw_t * 10.0)
        temp_ddegc = max(0, min(800, temp_ddegc))

        # ========================================================
        # IVT messages
        # ========================================================
        msg_counter = (tick & 0x3F) << 2

        # IVT Current (0x521) — negative = discharge (IVT convention)
        can_send(0x521, struct.pack(">BBi", msg_counter & 0xFF, 0, current_fox_ma)[:6])

        # IVT Voltage 1/2/3 (0x522-0x524)
        can_send(0x522, struct.pack(">BBi", msg_counter & 0xFF, 0, pack_voltage_mv)[:6])
        can_send(0x523, struct.pack(">BBi", msg_counter & 0xFF, 0, pack_voltage_mv)[:6])
        can_send(0x524, struct.pack(">BBi", msg_counter & 0xFF, 0, pack_voltage_mv)[:6])

        # IVT Temperature (0x527)
        can_send(0x527, struct.pack(">BBi", msg_counter & 0xFF, 0, temp_ddegc)[:6])

        # ========================================================
        # BMS State Request (0x210)
        # ========================================================
        if tick < 30:
            can_send(0x210, bytes([0x00, 0, 0, 0, 0, 0, 0, 0]))  # STANDBY
        else:
            can_send(0x210, bytes([0x02, 0, 0, 0, 0, 0, 0, 0]))  # NORMAL

        if tick == 30:
            print(f"[replay] Switching to NORMAL request")

        # ========================================================
        # Cell Voltages (0x270) — 5 mux groups
        # ========================================================
        for mux in range(5):
            base = mux * 4
            volts = []
            for j in range(4):
                idx = base + j
                if idx < FOX_CELLS_SERIES:
                    volts.append(cell_voltages[idx])
                else:
                    volts.append(0)
            can_send(0x270, encode_cell_voltage_msg(mux, volts))

        # ========================================================
        # Cell Temperatures (0x280) — 5 mux groups with gradient
        # ========================================================
        for mux in range(5):
            # Small thermal gradient: center cells slightly warmer
            gradient = (mux - 2) * 5  # ±10 deci-°C (±1°C)
            t = max(0, temp_ddegc + gradient)
            n_sensors = min(4, FOX_CELLS_SERIES - mux * 4)
            temps = [t] * max(1, n_sensors)
            if len(temps) < 3:
                temps.extend([0] * (3 - len(temps)))
            can_send(0x280, encode_cell_temp_msg(mux, temps[:3]))

        # ========================================================
        # Status log
        # ========================================================
        if tick % 50 == 0:
            c_rate = abs(bmw_i) / BMW_CAPACITY_AH
            print(f"[replay] t={data_idx/10:.0f}s Vcell={v_cell_mv}mV "
                  f"I_bmw={bmw_i:.1f}A I_fox={current_fox_ma/1000:.2f}A "
                  f"C={c_rate:.2f}C T={bmw_t:.1f}°C SOC_bmw={bmw_soc:.1f}%")

        time.sleep(tick_interval_s)

except KeyboardInterrupt:
    print(f"\n[replay] Stopped at sample {data_idx}/{len(trip_data)}")
finally:
    s.close()
