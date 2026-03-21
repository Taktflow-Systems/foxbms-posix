#!/usr/bin/env python3
"""Run untested high-risk scenarios for foxBMS POSIX vECU."""

import socket
import struct
import time
import subprocess
import os
import sys

CAN_IF = sys.argv[1] if len(sys.argv) > 1 else "vcan1"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

results = []

def inject(s, cmd, idx, val):
    data = struct.pack('<BBBi', cmd, idx, 1, val) + b'\x00'
    s.send(struct.pack('=IB3x8s', 0x7E0, 8, data))

def clear_all(s):
    for cmd in [0x01, 0x02, 0x03, 0x05]:
        for idx in range(18):
            data = struct.pack('<BBBi', cmd, idx, 0, 0)
            s.send(struct.pack('=IB3x8s', 0x7E0, 8, data))

def check_reaction(s, timeout_s=8):
    """Monitor for DIAG bitmap or BMS ERROR."""
    t0 = time.monotonic()
    diag_bitmap = 0
    bms_error = False
    while time.monotonic() - t0 < timeout_s:
        try:
            f = s.recv(16)
            cid = struct.unpack('=I', f[0:4])[0] & 0x7FF
            if cid == 0x7F8:
                bitmap = struct.unpack('<Q', f[8:16])[0]
                if bitmap != 0:
                    diag_bitmap = bitmap
            if cid == 0x220 and (f[8] & 0x0F) == 10:
                bms_error = True
            if diag_bitmap != 0 or bms_error:
                return {"diag": diag_bitmap, "error": bms_error, "time_s": time.monotonic() - t0}
        except BlockingIOError:
            pass
        time.sleep(0.005)
    return {"diag": diag_bitmap, "error": bms_error, "time_s": timeout_s}

def start_system():
    plant = subprocess.Popen(
        ["python3", os.path.join(SCRIPT_DIR, "plant_model.py"), CAN_IF],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.5)
    env = os.environ.copy()
    env["FOXBMS_CAN_IF"] = CAN_IF
    vecu = subprocess.Popen(
        [os.path.join(SCRIPT_DIR, "foxbms-vecu")],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    return plant, vecu

def wait_for_normal(s, timeout_s=30):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            f = s.recv(16)
            cid = struct.unpack('=I', f[0:4])[0] & 0x7FF
            if cid == 0x220 and (f[8] & 0x0F) == 7:
                return True
        except BlockingIOError:
            pass
        time.sleep(0.01)
    return False

def restart_and_stabilize(s, plant, vecu):
    vecu.kill()
    plant.kill()
    time.sleep(1)
    plant, vecu = start_system()
    if not wait_for_normal(s):
        print("  WARNING: BMS didn't reach NORMAL")
    time.sleep(4)  # stabilize
    return plant, vecu

def run_test(name, expect_trip, reaction):
    t = reaction["time_s"]
    tripped = reaction["diag"] != 0 or reaction["error"]
    if expect_trip and tripped:
        status = "PASS"
    elif not expect_trip and not tripped:
        status = "PASS"
    elif expect_trip and not tripped:
        status = "FAIL"
    else:
        status = "FAIL"

    detail = ""
    if reaction["diag"]:
        bits = [i for i in range(64) if reaction["diag"] & (1 << i)]
        detail = f"DIAG bits {bits}"
    if reaction["error"]:
        detail += " BMS=ERROR"
    if not tripped:
        detail = "no reaction"

    print(f"  [{status}] {name} | {t:.1f}s | {detail}")
    results.append((name, status, t, detail))
    return status == "PASS"

# ================================================================
# Setup
# ================================================================
s = socket.socket(socket.AF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
s.bind((CAN_IF,))
s.setblocking(False)

plant, vecu = start_system()
print("Waiting for NORMAL...")
if not wait_for_normal(s):
    print("ERROR: BMS didn't reach NORMAL")
    sys.exit(1)
time.sleep(4)
print("NORMAL + stabilized\n")

# ================================================================
# TEST 1-3: Per-cell coverage
# ================================================================
print("=== PER-CELL COVERAGE ===")

inject(s, 0x01, 8, 5000)
r = check_reaction(s, 5)
run_test("OV cell 8 (middle)", True, r)
clear_all(s)
plant, vecu = restart_and_stabilize(s, plant, vecu)

inject(s, 0x01, 17, 5000)
r = check_reaction(s, 5)
run_test("OV cell 17 (last)", True, r)
clear_all(s)
plant, vecu = restart_and_stabilize(s, plant, vecu)

for c in range(18):
    inject(s, 0x01, c, 1000)
r = check_reaction(s, 5)
run_test("UV ALL 18 cells", True, r)
clear_all(s)
plant, vecu = restart_and_stabilize(s, plant, vecu)

# ================================================================
# TEST 4-5: Contactor faults
# ================================================================
print("\n=== CONTACTOR FAULTS ===")

# Welding: trigger OV to open contactors, then override feedback to CLOSED
inject(s, 0x01, 0, 5000)
time.sleep(3)
clear_all(s)  # clear voltage override
inject(s, 0x05, 0, 1)  # feedback ch0 = CLOSED (welding)
inject(s, 0x05, 1, 1)  # feedback ch1 = CLOSED
r = check_reaction(s, 8)
run_test("Contactor WELDING (feedback=CLOSED while open)", True, r)
clear_all(s)
plant, vecu = restart_and_stabilize(s, plant, vecu)

# Stuck-open: override feedback to OPEN while BMS has contactors closed
inject(s, 0x05, 0, 0)  # feedback ch0 = OPEN
inject(s, 0x05, 1, 0)  # feedback ch1 = OPEN
r = check_reaction(s, 8)
run_test("Contactor STUCK-OPEN (feedback=OPEN while closed)", True, r)
clear_all(s)
plant, vecu = restart_and_stabilize(s, plant, vecu)

# ================================================================
# TEST 6-8: Boundary Value Analysis
# ================================================================
print("\n=== BOUNDARY VALUE ANALYSIS (OV MSL = 4250mV) ===")

inject(s, 0x01, 0, 4249)
r = check_reaction(s, 3)
run_test("BVA: 4249mV (MSL-1) — should NOT trip", False, r)
clear_all(s)

inject(s, 0x01, 0, 4250)
r = check_reaction(s, 3)
# foxBMS uses >= for MSL check, so 4250 should trip
tripped = r["diag"] != 0 or r["error"]
print(f"  [INFO] BVA: 4250mV (exact MSL) — {'tripped' if tripped else 'no trip'} ({r['time_s']:.1f}s)")
results.append(("BVA: 4250mV (exact MSL)", "INFO", r["time_s"], "tripped" if tripped else "no trip"))
clear_all(s)
if tripped:
    plant, vecu = restart_and_stabilize(s, plant, vecu)

inject(s, 0x01, 0, 4251)
r = check_reaction(s, 3)
run_test("BVA: 4251mV (MSL+1) — should trip", True, r)
clear_all(s)
plant, vecu = restart_and_stabilize(s, plant, vecu)

# ================================================================
# TEST 9: Multi-cell opposing faults
# ================================================================
print("\n=== MULTI-CELL FAULTS ===")

inject(s, 0x01, 0, 5000)   # OV on cell 0
inject(s, 0x01, 17, 1000)  # UV on cell 17
r = check_reaction(s, 5)
run_test("OV cell 0 + UV cell 17 simultaneously", True, r)
clear_all(s)
plant, vecu = restart_and_stabilize(s, plant, vecu)

# ================================================================
# TEST 10: Thermal gradient
# ================================================================
print("\n=== THERMAL GRADIENT ===")

inject(s, 0x02, 0, 600)  # 60°C on sensor 0 (above OT_DIS MSL 550)
r = check_reaction(s, 10)
run_test("Sensor 0 = 600ddegC (60C), others normal", True, r)
clear_all(s)

# ================================================================
# Summary
# ================================================================
s.close()
vecu.kill()
plant.kill()

print("\n" + "=" * 60)
print("SCENARIO TEST SUMMARY")
print("=" * 60)
passes = sum(1 for _, st, _, _ in results if st == "PASS")
fails = sum(1 for _, st, _, _ in results if st == "FAIL")
infos = sum(1 for _, st, _, _ in results if st == "INFO")
total = passes + fails
print(f"Total: {total} | PASS: {passes} | FAIL: {fails} | INFO: {infos}")
print()
for name, status, t, detail in results:
    print(f"  [{status}] {name} | {t:.1f}s | {detail}")
