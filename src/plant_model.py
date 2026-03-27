#!/usr/bin/env python3
"""foxBMS POSIX vECU — Dynamic Battery Plant Model with override protocol (0x6E0)."""
# @satisfies SW-REQ-091 IVT current sensor simulation
# @satisfies SW-REQ-092 Cell voltage simulation (OCV + noise + averaging)
# @satisfies SW-REQ-093 Cell temperature simulation
# @satisfies SW-REQ-101 IVT voltage simulation
# @satisfies SW-REQ-102 AFE cell voltage via CAN 0x270
# @satisfies SW-REQ-103 AFE cell temperature via CAN 0x280
import socket, struct, time, sys, random, fcntl, os

CAN_INTERFACE = sys.argv[1] if len(sys.argv) > 1 else "vcan1"

# ================================================================
# Battery parameters
# ================================================================
N_CELLS = 18
Q_CELL_MAH = 3000.0        # Cell capacity (mAh)
R_CELL_MOHM = 50.0          # Internal resistance per cell (mΩ)
R_TOTAL_MOHM = R_CELL_MOHM * N_CELLS  # Total string resistance (mΩ)
I_DISCHARGE_MA = 1000       # Discharge current when NORMAL (1 A, 0.33C — slow for demo)
DT_S = 0.001                # Loop period (1 ms) — SIL rate, synced with foxBMS cycle

# OCV(SOC) lookup — piecewise linear NMC 811 S-curve (mV)
# Source: NMC 811 cell datasheets (Samsung SDI / LG Chem)
# Steep at extremes, flat plateau at 30-70% SOC
OCV_TABLE = [
    (0.0,  2800), (2.5,  3000), (5.0,  3200), (10.0, 3350),
    (15.0, 3450), (20.0, 3520), (30.0, 3580), (40.0, 3620),
    (50.0, 3650), (60.0, 3700), (70.0, 3780), (80.0, 3880),
    (85.0, 3950), (90.0, 4020), (95.0, 4100), (100.0, 4200),
]

def ocv_mv(soc_pct):
    """Open-circuit voltage from SOC (piecewise linear NMC S-curve)."""
    soc_pct = max(0.0, min(100.0, soc_pct))
    for i in range(len(OCV_TABLE) - 1):
        s0, v0 = OCV_TABLE[i]
        s1, v1 = OCV_TABLE[i + 1]
        if s0 <= soc_pct <= s1:
            frac = (soc_pct - s0) / (s1 - s0) if s1 != s0 else 0
            return int(v0 + frac * (v1 - v0))
    return OCV_TABLE[-1][1]

# ================================================================
# foxBMS CAN big-endian encoding (same lookup table as foxBMS)
# ================================================================
# HITL-LOCK START:PLANT-BE-TABLE
CAN_BIG_ENDIAN_TABLE = [
    56, 57, 58, 59, 60, 61, 62, 63, 48, 49, 50, 51, 52, 53, 54, 55,
    40, 41, 42, 43, 44, 45, 46, 47, 32, 33, 34, 35, 36, 37, 38, 39,
    24, 25, 26, 27, 28, 29, 30, 31, 16, 17, 18, 19, 20, 21, 22, 23,
     8,  9, 10, 11, 12, 13, 14, 15,  0,  1,  2,  3,  4,  5,  6,  7,
]
# HITL-LOCK END:PLANT-BE-TABLE

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
    # HITL-LOCK START:PLANT-DECAN-VALID
    # DECAN_DATA_IS_VALID = 1 (not 0) — verified by roundtrip testing
    d = foxbms_encode_signal(d, 12, 1, 1)   # Invalid flag 0: 1=VALID
    d = foxbms_encode_signal(d, 13, 1, 1)   # Invalid flag 1: 1=VALID
    d = foxbms_encode_signal(d, 14, 1, 1)   # Invalid flag 2: 1=VALID
    d = foxbms_encode_signal(d, 15, 1, 1)   # Invalid flag 3: 1=VALID
    # HITL-LOCK END:PLANT-DECAN-VALID
    d = foxbms_encode_signal(d, 11, 13, voltages_mv[0])
    d = foxbms_encode_signal(d, 30, 13, voltages_mv[1])
    d = foxbms_encode_signal(d, 33, 13, voltages_mv[2])
    d = foxbms_encode_signal(d, 52, 13, voltages_mv[3])
    return msg_data_to_bytes(d)

def encode_cell_temp_msg(mux, temps_ddegc):
    """Encode foxBMS cell temperature message (0x280).

    6 temperature slots per message, each 8-bit (unit: °C, not ddegC!).
    foxBMS DECAN multiplies by 10 to get ddegC internally.
    Invalid flags: bits 8-13 (1=VALID, same as voltage).
    Temperature signals: bits 23,31,39,47,55,63 — 8 bits each.
    """
    d = 0
    d = foxbms_encode_signal(d, 7, 8, mux)  # Mux value
    # Invalid flags (bits 8-13): 1 = VALID
    for i in range(6):
        d = foxbms_encode_signal(d, 8 + i, 1, 1 if i < len(temps_ddegc) else 0)
    # Temperature values (8-bit, unit: °C — DECAN multiplies by 10)
    temp_bit_starts = [23, 31, 39, 47, 55, 63]
    for i in range(6):
        t_degc = temps_ddegc[i] // 10 if i < len(temps_ddegc) else 0  # ddegC → °C
        t_degc = max(0, min(255, t_degc))  # clamp to uint8
        d = foxbms_encode_signal(d, temp_bit_starts[i], 8, t_degc)
    return msg_data_to_bytes(d)

# -- SocketCAN setup -------------------------------------------------------
s = socket.socket(socket.AF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
s.bind((CAN_INTERFACE,))
s.setblocking(False)  # Non-blocking for RX (closed-loop + overrides)
print(f"[plant] {N_CELLS}S pack on {CAN_INTERFACE}, {Q_CELL_MAH}mAh, R={R_CELL_MOHM}mΩ/cell, I={I_DISCHARGE_MA/1000:.0f}A")

def can_send(can_id, data):
    s.send(struct.pack("=IB3x8s", can_id, len(data), data + bytes(8 - len(data))))

# -- Thermal model parameters -----------------------------------------------
THERMAL_MASS_J_K = 50.0           # Thermal mass per cell (J/K) — NMC pouch typical
AMBIENT_TEMP_C = 25.0              # Ambient temperature
COOLING_COEFF_W_K = 0.5            # Natural convection cooling (W/K per cell)

# -- Battery state ---------------------------------------------------------
soc_pct = 50.0; current_ma = 0; bms_state_normal = False
random.seed(42)
per_cell_offset = [random.gauss(0, 5.0) for _ in range(N_CELLS)]
cell_temp_c = [AMBIENT_TEMP_C] * N_CELLS  # Per-cell temperature tracking

# AFE-style moving average filter (16 samples, like ADI ADES1830)
AFE_AVG_DEPTH = 16
# Pre-fill with initial OCV so first report isn't averaged with zeros
initial_ocv = ocv_mv(soc_pct)
cell_voltage_history = [[initial_ocv + per_cell_offset[i]] * AFE_AVG_DEPTH for i in range(N_CELLS)]
afe_sample_idx = 0

# Plant override table (populated by 0x6E0 commands from web server)
plant_overrides = {}  # key = (type, index), value = int

tick = 0
try:
    while True:
        tick += 1

        # ============================================================
        # Closed-loop: read foxBMS CAN TX + plant override commands
        # ============================================================
        try:
            while True:
                rx_frame = s.recv(16)
                if len(rx_frame) >= 16:
                    rx_id = struct.unpack("=I", rx_frame[0:4])[0] & 0x1FFFFFFF
                    rx_data = rx_frame[8:16]
                    if rx_id == 0x7F0 and len(rx_data) >= 4:
                        # SIL probe: contactor actual state (reliable, no mux issues)
                        # Bytes 2-3 = actual state bitmask. If Main+ and Main- closed → NORMAL
                        contactor_actual = struct.unpack_from("<H", rx_data, 2)[0]
                        contactors_closed = (contactor_actual & 0x03) == 0x03  # bits 0+1
                        if contactors_closed and not bms_state_normal:
                            bms_state_normal = True
                            print(f"[plant] Contactors CLOSED at tick {tick} — starting discharge")
                        elif not contactors_closed and bms_state_normal:
                            bms_state_normal = False
                            print(f"[plant] Contactors OPENED at tick {tick} — stopping discharge")
                    elif rx_id == 0x6E0 and len(rx_data) >= 7:
                        cmd, idx, active = rx_data[0], rx_data[1], rx_data[2]
                        value = struct.unpack_from('<i', rx_data, 3)[0]
                        if cmd == 0xFF:  # clear all
                            plant_overrides.clear()
                            print(f"[plant] Override: CLEAR ALL")
                        elif active:
                            plant_overrides[(cmd, idx)] = value
                            print(f"[plant] Override: cmd=0x{cmd:02X} idx={idx} val={value}")
                        else:
                            plant_overrides.pop((cmd, idx), None)
                            print(f"[plant] Override removed: cmd=0x{cmd:02X} idx={idx}")
        except BlockingIOError:
            pass  # No more frames to read

        # -- Current model -------------------------------------------------
        current_ma = I_DISCHARGE_MA if bms_state_normal else 0
        if (0x03, 0) in plant_overrides: current_ma = plant_overrides[(0x03, 0)]

        # -- Thermal model (I²R heating + ambient cooling) ------------------
        for ci in range(N_CELLS):
            # I²R heating: P = I² × R_cell
            power_w = (current_ma / 1000.0) ** 2 * R_CELL_MOHM / 1000.0
            # Center cells heat ~20% more (worse airflow in pack center)
            heat_factor = 1.0 + 0.2 * (1.0 - abs(ci - N_CELLS / 2) / (N_CELLS / 2))
            dT_heat = power_w * heat_factor * DT_S / THERMAL_MASS_J_K
            # Newton cooling toward ambient
            dT_cool = COOLING_COEFF_W_K * (cell_temp_c[ci] - AMBIENT_TEMP_C) * DT_S / THERMAL_MASS_J_K
            cell_temp_c[ci] += dT_heat - dT_cool
            # Apply override if set
            if (0x02, ci) in plant_overrides:
                cell_temp_c[ci] = plant_overrides[(0x02, ci)] / 10.0  # override is in ddegC

        # -- SOC integration (coulomb counting) ----------------------------
        if current_ma > 0:
            soc_pct -= (current_ma / 1000.0) / (Q_CELL_MAH / 1000.0) * (DT_S / 3600.0) * 100.0
            soc_pct = max(0.0, min(100.0, soc_pct))

        # -- Cell voltage model (OCV + noise + AFE averaging) --------------
        v_ocv = ocv_mv(soc_pct)
        cell_voltages = []
        for i in range(N_CELLS):
            v_raw = v_ocv + per_cell_offset[i] + random.gauss(0, 3.0)
            cell_voltage_history[i][afe_sample_idx % AFE_AVG_DEPTH] = v_raw
            cell_voltages.append(max(2500, min(4500, int(sum(cell_voltage_history[i]) / AFE_AVG_DEPTH))))
        afe_sample_idx += 1
        # Apply plant overrides to cell voltages
        for i in range(N_CELLS):
            if (0x01, i) in plant_overrides: cell_voltages[i] = plant_overrides[(0x01, i)]
        # Pack voltage with IR drop
        ir_drop_mv = int((current_ma / 1000.0) * R_TOTAL_MOHM)
        pack_voltage_mv = max(0, sum(cell_voltages) - ir_drop_mv)

        # -- IVT messages --------------------------------------------------
        mc = (tick & 0x3F) << 2
        can_send(0x521, struct.pack(">BBi", mc & 0xFF, 0, current_ma)[:6])
        for vid in (0x522, 0x523, 0x524):
            can_send(vid, struct.pack(">BBi", mc & 0xFF, 0, pack_voltage_mv)[:6])
        # IVT Temperature — use average cell temperature
        avg_temp_ddegc = int(sum(cell_temp_c) / N_CELLS * 10)
        can_send(0x527, struct.pack(">BBi", mc & 0xFF, 0, avg_temp_ddegc)[:6])

        # -- BMS State Request (0x210) -------------------------------------
        can_send(0x210, bytes([0x00 if tick < 3000 else 0x02, 0, 0, 0, 0, 0, 0, 0]))
        if tick == 3000: print("[plant] Switching to NORMAL request")

        # -- Cell Voltages (0x270) -----------------------------------------
        for mux in range(5):
            base = mux * 4
            volts = [cell_voltages[base+j] if base+j < N_CELLS else 0 for j in range(4)]
            can_send(0x270, encode_cell_voltage_msg(mux, volts))

        # -- Cell Temperatures (0x280) — use per-cell thermal model ---------
        for mux in range(2):
            n_sens = min(6, 8 - mux * 6)
            temps = []
            for si in range(max(1, n_sens)):
                cell_idx = min(mux * 6 + si, N_CELLS - 1)
                temps.append(int(cell_temp_c[cell_idx] * 10))  # °C → ddegC
            can_send(0x280, encode_cell_temp_msg(mux, temps))

        # -- Plant telemetry (0x600-0x607) for web dashboard ---------------
        if tick % 100 == 0:
            can_send(0x600, struct.pack('<fi', soc_pct, current_ma))
            can_send(0x601, struct.pack('<ii', v_ocv, pack_voltage_mv))
            can_send(0x602, struct.pack('<iBB', ir_drop_mv, int(bms_state_normal), N_CELLS) + b'\x00\x00')
            for grp in range(5):
                can_send(0x603 + grp, b''.join(
                    struct.pack('<H', cell_voltages[grp*4+j] if grp*4+j < N_CELLS else 0) for j in range(4)))

        # -- Status log (every 5s) ----------------------------------------
        if tick % 5000 == 0:
            ovr = f" OVR={len(plant_overrides)}" if plant_overrides else ""
            t_min = min(cell_temp_c); t_max = max(cell_temp_c)
            print(f"[plant] tick={tick} SOC={soc_pct:.1f}% I={current_ma/1000:.1f}A "
                  f"Vcell={v_ocv}mV Vpack={pack_voltage_mv}mV IR={ir_drop_mv}mV "
                  f"T={t_min:.1f}-{t_max:.1f}°C "
                  f"{'NORMAL' if bms_state_normal else 'idle'}{ovr}")

        time.sleep(DT_S)

except KeyboardInterrupt:
    print(f"\n[plant] Stopped. Final SOC={soc_pct:.1f}%")
finally:
    s.close()
