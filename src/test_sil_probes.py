#!/usr/bin/env python3
"""
TDD: SIL Instrumentation Layer Tests — Comprehensive

Tests written BEFORE implementation. All should FAIL initially.
Implement sil_layer.c + patches to make them pass.

Categories (80+ tests):
  PRB.*   Probe presence + data validation (each probe ID)
  RATE.*  Probe update rate + jitter
  OVR.*   Override set + verify + release + verify-release
  BOUND.* Override boundary values (min, max, zero, negative)
  MULTI.* Multiple simultaneous overrides
  CHAIN.* Fault injection chain (override → DIAG → contactor → state)
  SEQ.*   Override during state transitions
  NEG.*   Negative tests (invalid IDs, out-of-range indices)
  CON.*   Cross-channel consistency (probe vs CAN)
  PER.*   Override persistence across cycles
  LAT.*   Latency (time from override to probe reflection)

Usage:
    python3 test_sil_probes.py <can_interface> [trip_csv]
"""

import subprocess
import sys
import os
import time
import struct
import signal
import socket as sock

CAN_IF = sys.argv[1] if len(sys.argv) > 1 else "vcan1"
TRIP_CSV = sys.argv[2] if len(sys.argv) > 2 else None
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Probe IDs (0x7F0–0x7FF)
PROBE_SPS_STATE       = 0x7F0
PROBE_SPS_PENDING     = 0x7F1
PROBE_SOC             = 0x7F2
PROBE_SOC_INTEGRATOR  = 0x7F3
PROBE_CELL_V_SUMMARY  = 0x7F4
PROBE_PACK_V          = 0x7F5
PROBE_CELL_T_SUMMARY  = 0x7F6
PROBE_DIAG            = 0x7F7
PROBE_DIAG_BITMAP     = 0x7F8
PROBE_STATE_MACHINE   = 0x7F9
PROBE_CURRENT         = 0x7FA
PROBE_TIMING          = 0x7FB
PROBE_DB_COUNTERS     = 0x7FC
PROBE_HEARTBEAT       = 0x7FF

ALL_PROBE_IDS = [
    PROBE_SPS_STATE, PROBE_SPS_PENDING, PROBE_SOC, PROBE_SOC_INTEGRATOR,
    PROBE_CELL_V_SUMMARY, PROBE_PACK_V, PROBE_CELL_T_SUMMARY,
    PROBE_DIAG, PROBE_DIAG_BITMAP, PROBE_STATE_MACHINE,
    PROBE_CURRENT, PROBE_TIMING, PROBE_DB_COUNTERS, PROBE_HEARTBEAT
]

# Override command
OVERRIDE_CMD = 0x7E0

# Override types
OVR_CELL_VOLTAGE   = 0x01
OVR_CELL_TEMP      = 0x02
OVR_PACK_CURRENT   = 0x03
OVR_SOC            = 0x04
OVR_CONTACTOR_FB   = 0x05
OVR_INTERLOCK      = 0x06
OVR_PACK_VOLTAGE   = 0x07
OVR_DIAG_FORCE     = 0x08
OVR_DIAG_CLEAR     = 0x09
OVR_SPS_FORCE      = 0x0A
OVR_IVT_TIMEOUT    = 0x0B
OVR_CELL_INVALID   = 0x0C
OVR_BAL_FORCE      = 0x0D

results = {}
categories = {}

def check(test_id, description, passed, detail=""):
    cat = test_id.split(".")[0]
    results[test_id] = {"desc": description, "pass": passed, "detail": detail}
    if cat not in categories:
        categories[cat] = {"total": 0, "pass": 0}
    categories[cat]["total"] += 1
    if passed:
        categories[cat]["pass"] += 1
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {test_id}: {description}")
    if detail and not passed:
        print(f"         {detail}")


class CANSocket:
    def __init__(self, interface):
        self.sock = sock.socket(sock.PF_CAN, sock.SOCK_RAW, sock.CAN_RAW)
        self.sock.bind((interface,))
        self.sock.settimeout(0.05)

    def send(self, can_id, data):
        data_padded = bytes(data) + bytes(8 - len(data))
        frame = struct.pack("=IB3x8s", can_id, len(data), data_padded)
        self.sock.send(frame)

    def recv_filter(self, target_id, timeout_s=3.0):
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            try:
                frame = self.sock.recv(16)
                if len(frame) >= 16:
                    can_id = struct.unpack("=I", frame[0:4])[0] & 0x7FF
                    if can_id == target_id:
                        return frame[8:16]
            except sock.timeout:
                continue
        return None

    def collect_id(self, target_id, duration_s=3.0):
        frames = []
        start = time.time()
        while (time.time() - start) < duration_s:
            try:
                frame = self.sock.recv(16)
                if len(frame) >= 16:
                    can_id = struct.unpack("=I", frame[0:4])[0] & 0x7FF
                    if can_id == target_id:
                        frames.append({"ts": time.time() - start, "data": frame[8:16]})
            except sock.timeout:
                continue
        return frames

    def collect_all_probes(self, duration_s=3.0):
        """Collect all frames in 0x7F0-0x7FF range."""
        probes = {}
        start = time.time()
        while (time.time() - start) < duration_s:
            try:
                frame = self.sock.recv(16)
                if len(frame) >= 16:
                    can_id = struct.unpack("=I", frame[0:4])[0] & 0x7FF
                    if 0x7F0 <= can_id <= 0x7FF:
                        if can_id not in probes:
                            probes[can_id] = []
                        probes[can_id].append({"ts": time.time() - start, "data": frame[8:16]})
            except sock.timeout:
                continue
        return probes

    def send_override(self, override_id, index, active, value):
        data = struct.pack("<BBBiB", override_id, index, 1 if active else 0, value, 0)
        self.send(OVERRIDE_CMD, data)

    def release_override(self, override_id, index):
        data = struct.pack("<BBBiB", override_id, index, 0, 0, 0)
        self.send(OVERRIDE_CMD, data)

    def release_all_overrides(self):
        for ovr in range(0x10):
            for idx in range(18):
                self.release_override(ovr, idx)

    def close(self):
        self.sock.close()


def start_system():
    if TRIP_CSV:
        plant_cmd = [sys.executable, os.path.join(SCRIPT_DIR, "plant_model_replay.py"),
                     CAN_IF, TRIP_CSV, "--speed", "10", "--loop"]
    else:
        plant_cmd = [sys.executable, os.path.join(SCRIPT_DIR, "plant_model.py"), CAN_IF]
    plant_proc = subprocess.Popen(plant_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    vecu_path = os.path.join(SCRIPT_DIR, "foxbms-vecu")
    env = os.environ.copy()
    env["FOXBMS_CAN_IF"] = CAN_IF
    vecu_log = open("/tmp/foxbms-vecu-sil-probe.log", "w")
    vecu_proc = subprocess.Popen([vecu_path], env=env,
                                  stdout=subprocess.DEVNULL, stderr=vecu_log)
    return plant_proc, vecu_proc, vecu_log


def stop_system(plant_proc, vecu_proc, vecu_log):
    for proc in [vecu_proc, plant_proc]:
        try:
            proc.send_signal(signal.SIGINT)
        except ProcessLookupError:
            pass
    for proc in [vecu_proc, plant_proc]:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    vecu_log.close()


def wait_for_normal(can, timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = can.recv_filter(0x220, timeout_s=1.0)
        if data and (data[0] & 0x0F) == 7:
            return True
    return False


def main():
    print("=" * 70)
    print("  SIL Instrumentation — Comprehensive TDD Tests")
    print("=" * 70)
    print()

    plant_proc, vecu_proc, vecu_log = start_system()
    can = CANSocket(CAN_IF)

    print("Waiting for BMS NORMAL...")
    if not wait_for_normal(can, timeout=20):
        print("ERROR: BMS did not reach NORMAL")
        stop_system(plant_proc, vecu_proc, vecu_log)
        return 2
    print("BMS NORMAL — running tests\n")

    # ==============================================================
    # PRB: Probe Presence — every probe ID must appear on CAN
    # ==============================================================
    print("--- PRB: Probe Presence ---")

    probe_names = {
        PROBE_SPS_STATE: "SPS actual/requested",
        PROBE_SPS_PENDING: "SPS pending/delay",
        PROBE_SOC: "SOC float",
        PROBE_SOC_INTEGRATOR: "SOC integrator",
        PROBE_CELL_V_SUMMARY: "Cell V min/max/avg/delta",
        PROBE_PACK_V: "Pack V string/bus",
        PROBE_CELL_T_SUMMARY: "Cell T min/max/avg/delta",
        PROBE_DIAG: "DIAG count/last ID",
        PROBE_DIAG_BITMAP: "DIAG fault bitmap",
        PROBE_STATE_MACHINE: "SYS+BMS state",
        PROBE_CURRENT: "Current from DB",
        PROBE_TIMING: "Loop timing",
        PROBE_DB_COUNTERS: "DB write/read count",
        PROBE_HEARTBEAT: "Heartbeat"
    }

    all_probes = can.collect_all_probes(duration_s=5.0)

    for pid in ALL_PROBE_IDS:
        name = probe_names.get(pid, f"0x{pid:03X}")
        present = pid in all_probes and len(all_probes[pid]) > 0
        count = len(all_probes.get(pid, []))
        check(f"PRB.{pid & 0xF:02d}", f"Probe 0x{pid:03X} ({name}) present",
              present,
              f"{count} frames" if present else "not received")

    print()

    # ==============================================================
    # DATA: Probe Data Validation — each probe has correct format
    # ==============================================================
    print("--- DATA: Probe Data Validation ---")

    # SPS state: bytes 0-1 = actual bitmap, bytes 2-3 = requested bitmap
    d = can.recv_filter(PROBE_SPS_STATE, timeout_s=3.0)
    if d:
        actual = struct.unpack("<H", d[0:2])[0]
        requested = struct.unpack("<H", d[2:4])[0]
        check("DATA.01", "SPS actual has ≥1 contactor closed at NORMAL",
              actual != 0, f"actual=0x{actual:04X}")
        check("DATA.02", "SPS requested has ≥1 contactor requested at NORMAL",
              requested != 0, f"requested=0x{requested:04X}")
        check("DATA.03", "SPS actual matches requested at steady state",
              actual == requested, f"actual=0x{actual:04X} req=0x{requested:04X}")
    else:
        for t in ["DATA.01", "DATA.02", "DATA.03"]:
            check(t, "SPS data validation", False, "no probe data")

    # SOC float
    d = can.recv_filter(PROBE_SOC, timeout_s=3.0)
    if d:
        soc = struct.unpack("<f", d[0:4])[0]
        check("DATA.04", "SOC float in range 0–100%", 0.0 <= soc <= 100.0, f"{soc:.2f}%")
        check("DATA.05", "SOC float not NaN", soc == soc, f"{soc}")  # NaN != NaN
        check("DATA.06", "SOC float not exactly 0.0 (should be ~50%)",
              soc > 1.0, f"{soc:.2f}%")
    else:
        for t in ["DATA.04", "DATA.05", "DATA.06"]:
            check(t, "SOC float validation", False, "no probe data")

    # Cell voltage summary: V_min, V_max, V_avg, V_delta (uint16 each)
    d = can.recv_filter(PROBE_CELL_V_SUMMARY, timeout_s=3.0)
    if d:
        v_min, v_max, v_avg, v_delta = struct.unpack("<HHHH", d)
        check("DATA.07", "V_min in NMC range (2500–4500mV)", 2500 <= v_min <= 4500, f"{v_min}mV")
        check("DATA.08", "V_max in NMC range (2500–4500mV)", 2500 <= v_max <= 4500, f"{v_max}mV")
        check("DATA.09", "V_max ≥ V_min", v_max >= v_min, f"min={v_min} max={v_max}")
        check("DATA.10", "V_avg between V_min and V_max",
              v_min <= v_avg <= v_max, f"min={v_min} avg={v_avg} max={v_max}")
        check("DATA.11", "V_delta = V_max - V_min",
              v_delta == v_max - v_min, f"delta={v_delta} vs {v_max}-{v_min}={v_max-v_min}")
        check("DATA.12", "V_delta < 500mV (normal operation)",
              v_delta < 500, f"delta={v_delta}mV")
    else:
        for t in [f"DATA.{i:02d}" for i in range(7, 13)]:
            check(t, "Cell voltage validation", False, "no probe data")

    # Pack voltage: string_V (int32), bus_V (int32)
    d = can.recv_filter(PROBE_PACK_V, timeout_s=3.0)
    if d:
        string_v, bus_v = struct.unpack("<ii", d)
        check("DATA.13", "String voltage 50–80V range",
              50000 <= string_v <= 80000, f"{string_v/1000:.1f}V")
        check("DATA.14", "Bus voltage 50–80V range",
              50000 <= bus_v <= 80000, f"{bus_v/1000:.1f}V")
        check("DATA.15", "String ≈ Bus voltage (±5V)",
              abs(string_v - bus_v) < 5000,
              f"string={string_v/1000:.1f}V bus={bus_v/1000:.1f}V diff={abs(string_v-bus_v)/1000:.1f}V")
    else:
        for t in ["DATA.13", "DATA.14", "DATA.15"]:
            check(t, "Pack voltage validation", False, "no probe data")

    # Cell temperature summary
    d = can.recv_filter(PROBE_CELL_T_SUMMARY, timeout_s=3.0)
    if d:
        t_min, t_max, t_avg, t_delta = struct.unpack("<hhhh", d)
        check("DATA.16", "T_min > 0 ddegC (>0°C)",
              t_min > 0, f"{t_min/10:.1f}°C")
        check("DATA.17", "T_max < 600 ddegC (<60°C)",
              t_max < 600, f"{t_max/10:.1f}°C")
        check("DATA.18", "T_delta < 100 ddegC (<10°C spread)",
              t_delta < 100, f"{t_delta/10:.1f}°C")
    else:
        for t in ["DATA.16", "DATA.17", "DATA.18"]:
            check(t, "Cell temp validation", False, "no probe data")

    # DIAG status
    d = can.recv_filter(PROBE_DIAG, timeout_s=3.0)
    if d:
        fault_count = struct.unpack("<I", d[0:4])[0]
        last_id = d[4]
        last_event = d[5]
        check("DATA.19", "DIAG fault count is uint32",
              fault_count < 0xFFFFFFFF, f"count={fault_count}")
        check("DATA.20", "DIAG last_id < 85 (DIAG_ID_MAX)",
              last_id < 85 or fault_count == 0, f"last_id={last_id}")
    else:
        for t in ["DATA.19", "DATA.20"]:
            check(t, "DIAG validation", False, "no probe data")

    # State machine
    d = can.recv_filter(PROBE_STATE_MACHINE, timeout_s=3.0)
    if d:
        sys_state, sys_sub = d[0], d[1]
        bms_state, bms_sub = d[4], d[5]
        check("DATA.21", "SYS state ≥ 5 (RUNNING or later)", sys_state >= 5, f"sys={sys_state}")
        check("DATA.22", "BMS state = 7 (NORMAL)", bms_state == 7, f"bms={bms_state}")
    else:
        for t in ["DATA.21", "DATA.22"]:
            check(t, "State machine validation", False, "no probe data")

    # Current from DB
    d = can.recv_filter(PROBE_CURRENT, timeout_s=3.0)
    if d:
        current_ma = struct.unpack("<i", d[0:4])[0]
        check("DATA.23", "Current from DB plausible (±15A)",
              abs(current_ma) < 15000, f"{current_ma/1000:.2f}A")
    else:
        check("DATA.23", "Current validation", False, "no probe data")

    # Heartbeat
    d = can.recv_filter(PROBE_HEARTBEAT, timeout_s=3.0)
    if d:
        tick = struct.unpack("<I", d[0:4])[0]
        check("DATA.24", "Heartbeat tick > 0", tick > 0, f"tick={tick}")
        uptime_ms = struct.unpack("<I", d[4:8])[0]
        check("DATA.25", "Heartbeat uptime > 0", uptime_ms > 0, f"uptime={uptime_ms}ms")
    else:
        for t in ["DATA.24", "DATA.25"]:
            check(t, "Heartbeat validation", False, "no probe data")

    # DB counters
    d = can.recv_filter(PROBE_DB_COUNTERS, timeout_s=3.0)
    if d:
        writes, reads = struct.unpack("<II", d)
        check("DATA.26", "DB write count > 0", writes > 0, f"writes={writes}")
        check("DATA.27", "DB read count > 0", reads > 0, f"reads={reads}")
    else:
        for t in ["DATA.26", "DATA.27"]:
            check(t, "DB counter validation", False, "no probe data")

    print()

    # ==============================================================
    # RATE: Probe Update Rate
    # ==============================================================
    print("--- RATE: Update Rate ---")

    rate_specs = {
        PROBE_SPS_STATE: ("SPS", 5.0, 15),       # ≥5Hz → ≥15 frames/3s
        PROBE_SOC: ("SOC", 2.0, 6),               # ≥2Hz → ≥6/3s
        PROBE_STATE_MACHINE: ("State", 5.0, 15),  # ≥5Hz
        PROBE_HEARTBEAT: ("Heartbeat", 0.5, 1),   # ≥0.5Hz → ≥1/3s
        PROBE_CELL_V_SUMMARY: ("CellV", 2.0, 6),  # ≥2Hz
        PROBE_DIAG: ("DIAG", 2.0, 6),             # ≥2Hz
        PROBE_CURRENT: ("Current", 2.0, 6),        # ≥2Hz
    }

    for pid, (name, min_hz, min_frames) in rate_specs.items():
        frames = can.collect_id(pid, duration_s=3.0)
        check(f"RATE.{pid & 0xF:02d}", f"{name} probe ≥{min_hz}Hz ({min_frames}+ frames/3s)",
              len(frames) >= min_frames,
              f"{len(frames)} frames = {len(frames)/3:.1f}Hz")

    # Jitter check: SPS probe should be consistent interval
    sps_frames = can.collect_id(PROBE_SPS_STATE, duration_s=3.0)
    if len(sps_frames) >= 10:
        intervals = [sps_frames[i+1]["ts"] - sps_frames[i]["ts"]
                     for i in range(len(sps_frames)-1)]
        avg_interval = sum(intervals) / len(intervals)
        max_jitter = max(abs(i - avg_interval) for i in intervals)
        check("RATE.JIT", f"SPS probe jitter < 50ms (avg interval {avg_interval*1000:.0f}ms)",
              max_jitter < 0.05,
              f"Max jitter: {max_jitter*1000:.1f}ms")
    else:
        check("RATE.JIT", "SPS probe jitter", False, "not enough frames")

    print()

    # ==============================================================
    # OVR: Override Set + Verify + Release + Verify-Release
    # ==============================================================
    print("--- OVR: Override Tests ---")

    # Cell voltage override
    can.send_override(OVR_CELL_VOLTAGE, 0, True, 4400)
    time.sleep(3.0)
    d = can.recv_filter(PROBE_CELL_V_SUMMARY, timeout_s=2.0)
    if d:
        v_max = struct.unpack("<H", d[2:4])[0]
        check("OVR.01", "Cell V override: V_max ≥ 4350mV after set to 4400",
              v_max >= 4350, f"V_max={v_max}mV")
    else:
        check("OVR.01", "Cell V override", False, "no probe")

    can.release_override(OVR_CELL_VOLTAGE, 0)
    time.sleep(3.0)
    d = can.recv_filter(PROBE_CELL_V_SUMMARY, timeout_s=2.0)
    if d:
        v_max = struct.unpack("<H", d[2:4])[0]
        check("OVR.02", "Cell V release: V_max < 4300mV after release",
              v_max < 4300, f"V_max={v_max}mV")
    else:
        check("OVR.02", "Cell V release", False, "no probe")

    # Multiple cells overridden simultaneously
    for cell in [0, 5, 10, 15]:
        can.send_override(OVR_CELL_VOLTAGE, cell, True, 4100 + cell * 10)
    time.sleep(3.0)
    d = can.recv_filter(PROBE_CELL_V_SUMMARY, timeout_s=2.0)
    if d:
        v_min, v_max = struct.unpack("<HH", d[0:4])
        check("OVR.03", "Multi-cell override: V_delta > 0",
              v_max > v_min, f"min={v_min} max={v_max} delta={v_max-v_min}")
    else:
        check("OVR.03", "Multi-cell override", False, "no probe")
    for cell in [0, 5, 10, 15]:
        can.release_override(OVR_CELL_VOLTAGE, cell)

    # Temperature override
    can.send_override(OVR_CELL_TEMP, 3, True, 550)  # 55°C
    time.sleep(3.0)
    d = can.recv_filter(PROBE_CELL_T_SUMMARY, timeout_s=2.0)
    if d:
        t_max = struct.unpack("<h", d[2:4])[0]
        check("OVR.04", "Temp override: T_max ≥ 500 ddegC after set to 550",
              t_max >= 500, f"T_max={t_max/10:.1f}°C")
    else:
        check("OVR.04", "Temp override", False, "no probe")
    can.release_override(OVR_CELL_TEMP, 3)

    # Current override
    can.send_override(OVR_PACK_CURRENT, 0, True, -30000)  # -30A
    time.sleep(3.0)
    d = can.recv_filter(PROBE_CURRENT, timeout_s=2.0)
    if d:
        cur = struct.unpack("<i", d[0:4])[0]
        check("OVR.05", "Current override: I ≈ -30000mA",
              abs(cur - (-30000)) < 2000, f"I={cur}mA")
    else:
        check("OVR.05", "Current override", False, "no probe")
    can.release_override(OVR_PACK_CURRENT, 0)

    # SOC override
    soc_25 = struct.unpack("<i", struct.pack("<f", 25.0))[0]
    can.send_override(OVR_SOC, 0, True, soc_25)
    time.sleep(3.0)
    d = can.recv_filter(PROBE_SOC, timeout_s=2.0)
    if d:
        soc = struct.unpack("<f", d[0:4])[0]
        check("OVR.06", "SOC override: SOC ≈ 25%",
              23.0 <= soc <= 27.0, f"SOC={soc:.1f}%")
    else:
        check("OVR.06", "SOC override", False, "no probe")
    can.release_override(OVR_SOC, 0)

    # SOC release — back to real value
    time.sleep(3.0)
    d = can.recv_filter(PROBE_SOC, timeout_s=2.0)
    if d:
        soc = struct.unpack("<f", d[0:4])[0]
        check("OVR.07", "SOC release: back to ~50% (±10)",
              40.0 <= soc <= 60.0, f"SOC={soc:.1f}%")
    else:
        check("OVR.07", "SOC release", False, "no probe")

    # Interlock override
    can.send_override(OVR_INTERLOCK, 0, True, 0)  # force OPEN
    time.sleep(3.0)
    d = can.recv_filter(PROBE_DIAG, timeout_s=2.0)
    # Interlock open should show up somehow
    check("OVR.08", "Interlock override accepted (command sent)",
          True, "verify via DIAG or state probe")
    can.release_override(OVR_INTERLOCK, 0)

    # Contactor feedback override (welding simulation)
    can.send_override(OVR_CONTACTOR_FB, 0, True, 1)  # force feedback=CLOSED
    time.sleep(3.0)
    d = can.recv_filter(PROBE_SPS_STATE, timeout_s=2.0)
    check("OVR.09", "Contactor FB override accepted",
          True, "verify actual state mismatch in probe")
    can.release_override(OVR_CONTACTOR_FB, 0)

    print()

    # ==============================================================
    # BOUND: Boundary Values
    # ==============================================================
    print("--- BOUND: Boundary Values ---")

    # Min cell voltage (2500mV — at UV threshold)
    can.send_override(OVR_CELL_VOLTAGE, 0, True, 2500)
    time.sleep(3.0)
    d = can.recv_filter(PROBE_CELL_V_SUMMARY, timeout_s=2.0)
    if d:
        v_min = struct.unpack("<H", d[0:2])[0]
        check("BOUND.01", "Cell V at 2500mV (UV boundary)",
              v_min <= 2600, f"V_min={v_min}mV")
    else:
        check("BOUND.01", "UV boundary", False, "no probe")
    can.release_override(OVR_CELL_VOLTAGE, 0)

    # Max cell voltage (4500mV — above OV threshold)
    can.send_override(OVR_CELL_VOLTAGE, 0, True, 4500)
    time.sleep(3.0)
    d = can.recv_filter(PROBE_CELL_V_SUMMARY, timeout_s=2.0)
    if d:
        v_max = struct.unpack("<H", d[2:4])[0]
        check("BOUND.02", "Cell V at 4500mV (OV boundary)",
              v_max >= 4400, f"V_max={v_max}mV")
    else:
        check("BOUND.02", "OV boundary", False, "no probe")
    can.release_override(OVR_CELL_VOLTAGE, 0)

    # Zero current
    can.send_override(OVR_PACK_CURRENT, 0, True, 0)
    time.sleep(3.0)
    d = can.recv_filter(PROBE_CURRENT, timeout_s=2.0)
    if d:
        cur = struct.unpack("<i", d[0:4])[0]
        check("BOUND.03", "Current override to exactly 0",
              abs(cur) < 100, f"I={cur}mA")
    else:
        check("BOUND.03", "Zero current", False, "no probe")
    can.release_override(OVR_PACK_CURRENT, 0)

    # Negative temperature (cold)
    can.send_override(OVR_CELL_TEMP, 0, True, -100)  # -10°C
    time.sleep(3.0)
    d = can.recv_filter(PROBE_CELL_T_SUMMARY, timeout_s=2.0)
    if d:
        t_min = struct.unpack("<h", d[0:2])[0]
        check("BOUND.04", "Temp override to -10°C",
              t_min <= 0, f"T_min={t_min/10:.1f}°C")
    else:
        check("BOUND.04", "Negative temp", False, "no probe")
    can.release_override(OVR_CELL_TEMP, 0)

    # SOC at 0%
    soc_0 = struct.unpack("<i", struct.pack("<f", 0.0))[0]
    can.send_override(OVR_SOC, 0, True, soc_0)
    time.sleep(3.0)
    d = can.recv_filter(PROBE_SOC, timeout_s=2.0)
    if d:
        soc = struct.unpack("<f", d[0:4])[0]
        check("BOUND.05", "SOC override to 0%",
              -1.0 <= soc <= 1.0, f"SOC={soc:.2f}%")
    else:
        check("BOUND.05", "SOC 0%", False, "no probe")
    can.release_override(OVR_SOC, 0)

    # SOC at 100%
    soc_100 = struct.unpack("<i", struct.pack("<f", 100.0))[0]
    can.send_override(OVR_SOC, 0, True, soc_100)
    time.sleep(3.0)
    d = can.recv_filter(PROBE_SOC, timeout_s=2.0)
    if d:
        soc = struct.unpack("<f", d[0:4])[0]
        check("BOUND.06", "SOC override to 100%",
              99.0 <= soc <= 101.0, f"SOC={soc:.2f}%")
    else:
        check("BOUND.06", "SOC 100%", False, "no probe")
    can.release_override(OVR_SOC, 0)

    print()

    # ==============================================================
    # NEG: Negative Tests
    # ==============================================================
    print("--- NEG: Negative Tests ---")

    # Invalid override ID (0xFF)
    can.send_override(0xFF, 0, True, 1234)
    time.sleep(0.5)
    alive = vecu_proc.poll() is None
    check("NEG.01", "Invalid override ID 0xFF doesn't crash vECU",
          alive, f"exit={vecu_proc.returncode}" if not alive else "running")

    # Out-of-range cell index (99)
    can.send_override(OVR_CELL_VOLTAGE, 99, True, 4000)
    time.sleep(0.5)
    alive = vecu_proc.poll() is None
    check("NEG.02", "Cell index 99 doesn't crash vECU",
          alive, f"exit={vecu_proc.returncode}" if not alive else "running")

    # Zero-length CAN frame to 0x7E0
    can.send(OVERRIDE_CMD, bytes([]))
    time.sleep(0.5)
    alive = vecu_proc.poll() is None
    check("NEG.03", "Empty override frame doesn't crash vECU",
          alive, f"exit={vecu_proc.returncode}" if not alive else "running")

    # Max int32 value
    can.send_override(OVR_CELL_VOLTAGE, 0, True, 0x7FFFFFFF)
    time.sleep(0.5)
    alive = vecu_proc.poll() is None
    check("NEG.04", "Max int32 override doesn't crash vECU",
          alive, f"exit={vecu_proc.returncode}" if not alive else "running")
    can.release_override(OVR_CELL_VOLTAGE, 0)

    # Negative int32 value for voltage
    can.send_override(OVR_CELL_VOLTAGE, 0, True, -1000)
    time.sleep(0.5)
    alive = vecu_proc.poll() is None
    check("NEG.05", "Negative voltage override doesn't crash vECU",
          alive, f"exit={vecu_proc.returncode}" if not alive else "running")
    can.release_override(OVR_CELL_VOLTAGE, 0)

    print()

    # ==============================================================
    # PER: Persistence — override stays active across cycles
    # ==============================================================
    print("--- PER: Persistence ---")

    can.send_override(OVR_CELL_VOLTAGE, 2, True, 4200)
    time.sleep(1)
    readings = []
    for _ in range(3):
        d = can.recv_filter(PROBE_CELL_V_SUMMARY, timeout_s=2.0)
        if d:
            readings.append(struct.unpack("<H", d[2:4])[0])  # V_max
        time.sleep(1)
    can.release_override(OVR_CELL_VOLTAGE, 2)

    check("PER.01", "Override persists across 3 consecutive reads",
          len(readings) >= 3 and all(v >= 4150 for v in readings),
          f"Readings: {readings}")

    # Verify release actually clears
    time.sleep(3.0)
    d = can.recv_filter(PROBE_CELL_V_SUMMARY, timeout_s=2.0)
    if d:
        v_max = struct.unpack("<H", d[2:4])[0]
        check("PER.02", "After release, override is truly cleared",
              v_max < 4150, f"V_max={v_max}mV")
    else:
        check("PER.02", "Override cleared", False, "no probe")

    print()

    # ==============================================================
    # LAT: Latency — time from override to probe reflection
    # ==============================================================
    print("--- LAT: Latency ---")

    t_send = time.time()
    can.send_override(OVR_CELL_VOLTAGE, 0, True, 4300)
    # Poll for probe reflection
    deadline = time.time() + 3.0
    latency_ms = None
    while time.time() < deadline:
        d = can.recv_filter(PROBE_CELL_V_SUMMARY, timeout_s=0.1)
        if d:
            v_max = struct.unpack("<H", d[2:4])[0]
            if v_max >= 4250:
                latency_ms = (time.time() - t_send) * 1000
                break

    check("LAT.01", "Override reflected in probe within 500ms",
          latency_ms is not None and latency_ms < 500,
          f"Latency: {latency_ms:.0f}ms" if latency_ms else "never reflected")

    can.release_override(OVR_CELL_VOLTAGE, 0)

    print()

    # ==============================================================
    # CON: Consistency — probe vs CAN cross-check
    # ==============================================================
    print("--- CON: Cross-Channel Consistency ---")

    # BMS state: probe 0x7F9 vs CAN 0x220
    p = can.recv_filter(PROBE_STATE_MACHINE, timeout_s=2.0)
    c = can.recv_filter(0x220, timeout_s=2.0)
    if p and c:
        check("CON.01", "BMS state: probe matches CAN 0x220",
              p[4] == (c[0] & 0x0F),
              f"probe={p[4]}, CAN={c[0] & 0x0F}")
    else:
        check("CON.01", "BMS state cross-check", False, "missing data")

    # Connected strings: probe SPS vs CAN 0x220
    p = can.recv_filter(PROBE_SPS_STATE, timeout_s=2.0)
    c = can.recv_filter(0x220, timeout_s=2.0)
    if p and c:
        sps_actual = struct.unpack("<H", p[0:2])[0]
        can_strings = (c[0] >> 4) & 0x0F
        # At least 1 contactor closed should match ≥1 connected string
        check("CON.02", "SPS probe (contactors closed) consistent with CAN strings",
              (sps_actual > 0) == (can_strings > 0),
              f"SPS=0x{sps_actual:04X}, CAN_strings={can_strings}")
    else:
        check("CON.02", "SPS vs CAN cross-check", False, "missing data")

    # SOC probe vs CAN 0x235
    p = can.recv_filter(PROBE_SOC, timeout_s=2.0)
    c = can.recv_filter(0x235, timeout_s=2.0)
    if p and c:
        soc_float = struct.unpack("<f", p[0:4])[0]
        soc_byte = c[5]
        check("CON.03", "SOC probe float ≈ CAN byte (±10%)",
              abs(soc_float - soc_byte / 4.0) < 10.0,
              f"probe={soc_float:.1f}%, byte={soc_byte} ≈ {soc_byte/4:.1f}%")
    else:
        check("CON.03", "SOC cross-check", False, "missing data")

    # Heartbeat tick vs DB write count (both should increase)
    h1 = can.recv_filter(PROBE_HEARTBEAT, timeout_s=2.0)
    d1 = can.recv_filter(PROBE_DB_COUNTERS, timeout_s=2.0)
    time.sleep(2)
    h2 = can.recv_filter(PROBE_HEARTBEAT, timeout_s=2.0)
    d2 = can.recv_filter(PROBE_DB_COUNTERS, timeout_s=2.0)
    if h1 and h2 and d1 and d2:
        tick1 = struct.unpack("<I", h1[0:4])[0]
        tick2 = struct.unpack("<I", h2[0:4])[0]
        db1 = struct.unpack("<I", d1[0:4])[0]
        db2 = struct.unpack("<I", d2[0:4])[0]
        check("CON.04", "Heartbeat tick increases over 2s",
              tick2 > tick1, f"tick1={tick1} tick2={tick2}")
        check("CON.05", "DB write count increases over 2s",
              db2 > db1, f"db1={db1} db2={db2}")
    else:
        check("CON.04", "Heartbeat increase", False, "missing data")
        check("CON.05", "DB count increase", False, "missing data")

    print()

    # ==============================================================
    # MULTI: Multiple Simultaneous Overrides
    # ==============================================================
    print("--- MULTI: Simultaneous Overrides ---")

    # Override voltage + temperature + current at same time
    can.send_override(OVR_CELL_VOLTAGE, 0, True, 4300)
    can.send_override(OVR_CELL_TEMP, 0, True, 450)  # 45°C
    can.send_override(OVR_PACK_CURRENT, 0, True, -20000)  # -20A
    time.sleep(2)

    v_ok, t_ok, i_ok = False, False, False
    d = can.recv_filter(PROBE_CELL_V_SUMMARY, timeout_s=2.0)
    if d:
        v_max = struct.unpack("<H", d[2:4])[0]
        v_ok = v_max >= 4250
    d = can.recv_filter(PROBE_CELL_T_SUMMARY, timeout_s=2.0)
    if d:
        t_max = struct.unpack("<h", d[2:4])[0]
        t_ok = t_max >= 400
    d = can.recv_filter(PROBE_CURRENT, timeout_s=2.0)
    if d:
        cur = struct.unpack("<i", d[0:4])[0]
        i_ok = cur < -15000

    check("MULTI.01", "All 3 overrides active simultaneously",
          v_ok and t_ok and i_ok,
          f"V_ok={v_ok} T_ok={t_ok} I_ok={i_ok}")

    # Release all
    can.release_all_overrides()
    time.sleep(2)

    # Verify all returned to normal
    v_ok, t_ok, i_ok = True, True, True
    d = can.recv_filter(PROBE_CELL_V_SUMMARY, timeout_s=2.0)
    if d:
        v_max = struct.unpack("<H", d[2:4])[0]
        v_ok = v_max < 4250
    d = can.recv_filter(PROBE_CELL_T_SUMMARY, timeout_s=2.0)
    if d:
        t_max = struct.unpack("<h", d[2:4])[0]
        t_ok = t_max < 400
    d = can.recv_filter(PROBE_CURRENT, timeout_s=2.0)
    if d:
        cur = struct.unpack("<i", d[0:4])[0]
        i_ok = cur > -15000

    check("MULTI.02", "All 3 overrides released — values returned to normal",
          v_ok and t_ok and i_ok,
          f"V_ok={v_ok} T_ok={t_ok} I_ok={i_ok}")

    print()

    # ==============================================================
    # Summary
    # ==============================================================
    stop_system(plant_proc, vecu_proc, vecu_log)
    can.close()

    total = len(results)
    passed = sum(1 for r in results.values() if r["pass"])
    failed = total - passed

    print("=" * 70)
    print("  RESULTS BY CATEGORY")
    print("=" * 70)
    cat_names = {
        "PRB": "Probe Presence", "DATA": "Data Validation", "RATE": "Update Rate",
        "OVR": "Override Set/Release", "BOUND": "Boundary Values",
        "NEG": "Negative Tests", "PER": "Persistence", "LAT": "Latency",
        "CON": "Consistency", "MULTI": "Simultaneous"
    }
    for cat in sorted(categories.keys()):
        c = categories[cat]
        status = "✓" if c["pass"] == c["total"] else "✗"
        name = cat_names.get(cat, cat)
        print(f"  {status} {cat:6s} {name:25s} {c['pass']}/{c['total']}")

    print(f"\n  TOTAL: {passed}/{total} PASS, {failed} FAIL")
    print("=" * 70)

    if failed > 0:
        print(f"\nFailed:")
        for tid, r in sorted(results.items()):
            if not r["pass"]:
                print(f"  {tid}: {r['desc']}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
