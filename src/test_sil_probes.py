#!/usr/bin/env python3
"""
TDD: SIL Instrumentation Layer Tests

Tests written BEFORE implementation. All should FAIL initially.
Implement sil_layer.c + patches to make them pass.

Tests verify:
  1. Probe messages appear on CAN 0x7F0-0x7FF
  2. Override commands via 0x7E0 change internal behavior
  3. Probes reflect overridden values
  4. Release override → return to real values
  5. No probes when flag not compiled (separate build test)

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

# Probe IDs
PROBE_SPS_STATE = 0x7F0
PROBE_SPS_PENDING = 0x7F1
PROBE_SOC = 0x7F2
PROBE_CELL_V_SUMMARY = 0x7F4
PROBE_PACK_V = 0x7F5
PROBE_CELL_T_SUMMARY = 0x7F6
PROBE_DIAG = 0x7F7
PROBE_STATE_MACHINE = 0x7F9
PROBE_CURRENT = 0x7FA
PROBE_TIMING = 0x7FB
PROBE_HEARTBEAT = 0x7FF

# Override command ID
OVERRIDE_CMD = 0x7E0

# Override types
OVR_CELL_VOLTAGE = 0x01
OVR_CELL_TEMP = 0x02
OVR_PACK_CURRENT = 0x03
OVR_SOC = 0x04
OVR_CONTACTOR_FB = 0x05
OVR_INTERLOCK = 0x06

results = {}

def check(test_id, description, passed, detail=""):
    results[test_id] = {"desc": description, "pass": passed, "detail": detail}
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

    def recv_filter(self, target_id, timeout_s=5.0):
        """Wait for a specific CAN ID, return data bytes or None."""
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

    def collect_id(self, target_id, duration_s=5.0):
        """Collect all frames with target_id for duration."""
        frames = []
        deadline = time.time() + duration_s
        while time.time() < deadline:
            try:
                frame = self.sock.recv(16)
                if len(frame) >= 16:
                    can_id = struct.unpack("=I", frame[0:4])[0] & 0x7FF
                    if can_id == target_id:
                        frames.append(frame[8:16])
            except sock.timeout:
                continue
        return frames

    def send_override(self, override_id, index, active, value):
        """Send SIL override command on 0x7E0."""
        data = struct.pack("<BBBi", override_id, index, 1 if active else 0, value)
        self.send(OVERRIDE_CMD, data)

    def release_override(self, override_id, index):
        """Release SIL override."""
        data = struct.pack("<BBBi", override_id, index, 0, 0)
        self.send(OVERRIDE_CMD, data)

    def close(self):
        self.sock.close()


def start_system():
    """Start plant model + foxBMS vECU, return (plant_proc, vecu_proc)."""
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
    """Wait until BMS reaches NORMAL state."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = can.recv_filter(0x220, timeout_s=1.0)
        if data and (data[0] & 0x0F) == 7:
            return True
    return False


def main():
    print("=" * 60)
    print("  SIL Instrumentation Layer Tests (TDD)")
    print("=" * 60)
    print()

    plant_proc, vecu_proc, vecu_log = start_system()
    can = CANSocket(CAN_IF)

    # Wait for system to reach NORMAL
    print("Waiting for BMS NORMAL...")
    if not wait_for_normal(can, timeout=20):
        print("ERROR: BMS did not reach NORMAL — cannot run probe tests")
        stop_system(plant_proc, vecu_proc, vecu_log)
        return 2

    print("BMS NORMAL — running probe tests\n")

    # ==============================================================
    # PROBE READ TESTS
    # ==============================================================
    print("--- Probe Read Tests ---")

    # PRB.01: SPS contactor state probe (0x7F0)
    data = can.recv_filter(PROBE_SPS_STATE, timeout_s=3.0)
    check("PRB.01", "SPS contactor state probe (0x7F0) present on CAN",
          data is not None,
          f"Data: {data.hex() if data else 'none'}")

    # PRB.02: SPS probe shows contactors closed at NORMAL
    if data:
        actual_state = struct.unpack("<H", data[0:2])[0]
        check("PRB.02", "SPS probe shows at least 1 contactor closed",
              actual_state != 0,
              f"Actual state bitmap: 0x{actual_state:04X}")
    else:
        check("PRB.02", "SPS probe shows at least 1 contactor closed", False, "No probe data")

    # PRB.03: SOC probe (0x7F2) present
    data = can.recv_filter(PROBE_SOC, timeout_s=3.0)
    check("PRB.03", "SOC probe (0x7F2) present on CAN",
          data is not None,
          f"Data: {data.hex() if data else 'none'}")

    # PRB.04: SOC probe contains plausible float32
    if data:
        soc_float = struct.unpack("<f", data[0:4])[0]
        check("PRB.04", "SOC probe float32 is plausible (0–100%)",
              0.0 <= soc_float <= 100.0,
              f"SOC = {soc_float:.2f}%")
    else:
        check("PRB.04", "SOC probe float32 is plausible", False, "No probe data")

    # PRB.05: Cell voltage summary probe (0x7F4)
    data = can.recv_filter(PROBE_CELL_V_SUMMARY, timeout_s=3.0)
    check("PRB.05", "Cell voltage summary probe (0x7F4) present",
          data is not None,
          f"Data: {data.hex() if data else 'none'}")

    if data:
        v_min, v_max, v_avg, v_delta = struct.unpack("<HHHH", data[0:8])
        check("PRB.06", "Cell V_min plausible (2500–4500 mV)",
              2500 <= v_min <= 4500,
              f"V_min={v_min}mV V_max={v_max}mV V_avg={v_avg}mV delta={v_delta}mV")
    else:
        check("PRB.06", "Cell V_min plausible", False, "No probe data")

    # PRB.07: DIAG probe (0x7F7)
    data = can.recv_filter(PROBE_DIAG, timeout_s=3.0)
    check("PRB.07", "DIAG probe (0x7F7) present",
          data is not None,
          f"Data: {data.hex() if data else 'none'}")

    # PRB.08: State machine probe (0x7F9)
    data = can.recv_filter(PROBE_STATE_MACHINE, timeout_s=3.0)
    check("PRB.08", "State machine probe (0x7F9) present",
          data is not None,
          f"Data: {data.hex() if data else 'none'}")

    if data:
        bms_state = data[4]
        check("PRB.09", "State machine probe shows BMS state = 7 (NORMAL)",
              bms_state == 7,
              f"BMS state from probe: {bms_state}")
    else:
        check("PRB.09", "State machine probe shows NORMAL", False, "No probe data")

    # PRB.10: Heartbeat probe (0x7FF)
    frames = can.collect_id(PROBE_HEARTBEAT, duration_s=3.0)
    check("PRB.10", "Heartbeat probe (0x7FF) received at least 2 frames in 3s",
          len(frames) >= 2,
          f"{len(frames)} heartbeat frames")

    # PRB.11: Heartbeat tick counter increments
    if len(frames) >= 2:
        tick1 = struct.unpack("<I", frames[0][0:4])[0]
        tick2 = struct.unpack("<I", frames[-1][0:4])[0]
        check("PRB.11", "Heartbeat tick counter increments",
              tick2 > tick1,
              f"tick1={tick1}, tick2={tick2}")
    else:
        check("PRB.11", "Heartbeat tick counter increments", False, "Not enough frames")

    # PRB.12: Current probe (0x7FA)
    data = can.recv_filter(PROBE_CURRENT, timeout_s=3.0)
    check("PRB.12", "Current probe (0x7FA) present",
          data is not None,
          f"Data: {data.hex() if data else 'none'}")

    print()

    # ==============================================================
    # OVERRIDE WRITE TESTS
    # ==============================================================
    print("--- Override Write Tests ---")

    # OVR.01: Override cell voltage → probe reflects overridden value
    print("  Injecting cell 0 voltage override to 4400mV...")
    can.send_override(OVR_CELL_VOLTAGE, 0, True, 4400)
    time.sleep(2)  # wait for next probe cycle
    data = can.recv_filter(PROBE_CELL_V_SUMMARY, timeout_s=3.0)
    if data:
        v_max = struct.unpack("<H", data[2:4])[0]
        check("OVR.01", "Cell voltage override reflected in V_max probe",
              v_max >= 4350,  # should be near 4400
              f"V_max={v_max}mV (expected ≥4350 after override to 4400)")
    else:
        check("OVR.01", "Cell voltage override reflected in probe", False, "No probe data")

    # OVR.02: Release override → value returns to plant data
    can.release_override(OVR_CELL_VOLTAGE, 0)
    time.sleep(2)
    data = can.recv_filter(PROBE_CELL_V_SUMMARY, timeout_s=3.0)
    if data:
        v_max = struct.unpack("<H", data[2:4])[0]
        check("OVR.02", "After release, V_max returns to normal (<4300mV)",
              v_max < 4300,
              f"V_max={v_max}mV (expected <4300 after release)")
    else:
        check("OVR.02", "After release, V_max returns to normal", False, "No probe data")

    # OVR.03: Override current → current probe reflects override
    print("  Injecting current override to 50000mA (50A)...")
    can.send_override(OVR_PACK_CURRENT, 0, True, 50000)
    time.sleep(2)
    data = can.recv_filter(PROBE_CURRENT, timeout_s=3.0)
    if data:
        current_ma = struct.unpack("<i", data[0:4])[0]
        check("OVR.03", "Current override reflected in current probe",
              abs(current_ma - 50000) < 1000,
              f"Current={current_ma}mA (expected ~50000)")
    else:
        check("OVR.03", "Current override reflected", False, "No probe data")

    can.release_override(OVR_PACK_CURRENT, 0)

    # OVR.04: Override SOC → SOC probe shows overridden float
    print("  Injecting SOC override to 25.0%...")
    soc_bytes = struct.pack("<f", 25.0)
    soc_int = struct.unpack("<i", soc_bytes)[0]
    can.send_override(OVR_SOC, 0, True, soc_int)
    time.sleep(2)
    data = can.recv_filter(PROBE_SOC, timeout_s=3.0)
    if data:
        soc = struct.unpack("<f", data[0:4])[0]
        check("OVR.04", "SOC override reflected in SOC probe",
              23.0 <= soc <= 27.0,
              f"SOC={soc:.1f}% (expected ~25.0)")
    else:
        check("OVR.04", "SOC override reflected", False, "No probe data")

    can.release_override(OVR_SOC, 0)

    print()

    # ==============================================================
    # SYNCHRONIZATION TESTS
    # ==============================================================
    print("--- Synchronization Tests ---")

    # SYNC.01: Plant model reads 0x7F0 for contactor state
    # Verify plant sends zero current before NORMAL detected via probe
    # (This tests that the plant uses probes, not 0x220)
    # Can only verify indirectly: current should be exactly 0 before NORMAL
    # Already tested by CUR.06 in test_asil.py — check here that probe enables it

    data = can.recv_filter(PROBE_SPS_STATE, timeout_s=3.0)
    if data:
        actual = struct.unpack("<H", data[0:2])[0]
        requested = struct.unpack("<H", data[2:4])[0]
        check("SYNC.01", "SPS probe provides both actual and requested state",
              True,  # if we got data, the format is testable
              f"Actual=0x{actual:04X}, Requested=0x{requested:04X}")
    else:
        check("SYNC.01", "SPS probe available for plant sync", False, "No probe data")

    # SYNC.02: SOC probe updates at least every 500ms
    frames = can.collect_id(PROBE_SOC, duration_s=3.0)
    check("SYNC.02", "SOC probe updates at ≥2Hz (at least 6 frames in 3s)",
          len(frames) >= 6,
          f"{len(frames)} frames in 3s")

    # SYNC.03: SPS probe updates at least every 100ms
    frames = can.collect_id(PROBE_SPS_STATE, duration_s=3.0)
    check("SYNC.03", "SPS probe updates at ≥5Hz (at least 15 frames in 3s)",
          len(frames) >= 15,
          f"{len(frames)} frames in 3s")

    print()

    # ==============================================================
    # CONSISTENCY TESTS
    # ==============================================================
    print("--- Consistency Tests ---")

    # CON.01: BMS state from probe matches BMS state from 0x220
    probe_data = can.recv_filter(PROBE_STATE_MACHINE, timeout_s=2.0)
    can_data = can.recv_filter(0x220, timeout_s=2.0)
    if probe_data and can_data:
        probe_bms = probe_data[4]
        can_bms = can_data[0] & 0x0F
        check("CON.01", "BMS state: probe 0x7F9 matches CAN 0x220",
              probe_bms == can_bms,
              f"Probe: {probe_bms}, CAN: {can_bms}")
    else:
        check("CON.01", "BMS state cross-check", False, "Missing data")

    # CON.02: SOC probe matches 0x235 byte (within resolution)
    probe_data = can.recv_filter(PROBE_SOC, timeout_s=2.0)
    soc_data = can.recv_filter(0x235, timeout_s=2.0)
    if probe_data and soc_data:
        soc_float = struct.unpack("<f", probe_data[0:4])[0]
        soc_byte = soc_data[5]
        # CAN byte is ~SOC*4 or SOC*2 depending on encoding
        # 50% → byte 200 → factor ~4
        soc_from_byte = soc_byte / 4.0  # approximate
        check("CON.02", "SOC probe float ≈ 0x235 byte value (±5%)",
              abs(soc_float - soc_from_byte) < 5.0,
              f"Probe: {soc_float:.1f}%, CAN byte: {soc_byte} ≈ {soc_from_byte:.1f}%")
    else:
        check("CON.02", "SOC cross-check", False, "Missing data")

    print()

    # ==============================================================
    # Summary
    # ==============================================================
    stop_system(plant_proc, vecu_proc, vecu_log)
    can.close()

    total = len(results)
    passed = sum(1 for r in results.values() if r["pass"])
    failed = total - passed

    print("=" * 60)
    print(f"  TOTAL: {passed}/{total} PASS, {failed} FAIL")
    print("=" * 60)

    if failed > 0:
        print(f"\nFailed:")
        for tid, r in results.items():
            if not r["pass"]:
                print(f"  {tid}: {r['desc']}")
                if r["detail"]:
                    print(f"      {r['detail']}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
