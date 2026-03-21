#!/usr/bin/env python3
"""
GA-13: foxBMS POSIX vECU smoke test.

Starts plant_model.py + foxbms-vecu, waits for BMS NORMAL state on CAN,
and returns pass/fail exit code.

Usage:
    python3 test_smoke.py [vcan_interface]

Exit codes:
    0 = PASS (BMS reached NORMAL state)
    1 = FAIL (BMS did not reach NORMAL within timeout)
    2 = ERROR (process startup failure)
"""

import subprocess
import sys
import os
import time
import struct
import signal

# Configuration
CAN_IF = sys.argv[1] if len(sys.argv) > 1 else "vcan1"
TIMEOUT_S = 30         # max seconds to wait for NORMAL state
POST_NORMAL_S = 5      # seconds to continue monitoring after NORMAL detected
BMS_STATE_CAN_ID = 0x220
BMS_SOC_CAN_ID = 0x235
BMS_STATE_NORMAL = 7   # foxBMS BMS_NORMAL state value
POLL_INTERVAL = 0.5    # seconds between CAN checks

def setup_vcan(interface):
    """Ensure vcan interface exists."""
    ret = subprocess.run(
        ["ip", "link", "show", interface],
        capture_output=True, text=True
    )
    if ret.returncode != 0:
        print(f"[SMOKE] Setting up {interface}...")
        subprocess.run(
            ["sudo", "ip", "link", "add", interface, "type", "vcan"],
            check=True
        )
        subprocess.run(
            ["sudo", "ip", "link", "set", interface, "up"],
            check=True
        )
    print(f"[SMOKE] CAN interface {interface} is up")


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Ensure vcan is available
    try:
        setup_vcan(CAN_IF)
    except Exception as e:
        print(f"[SMOKE] ERROR: Cannot setup {CAN_IF}: {e}")
        return 2

    # Start plant model
    plant_proc = subprocess.Popen(
        [sys.executable, os.path.join(script_dir, "plant_model.py"), CAN_IF],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    print(f"[SMOKE] Plant model started (PID {plant_proc.pid})")

    # Start foxBMS vECU
    vecu_path = os.path.join(script_dir, "foxbms-vecu")
    if not os.path.isfile(vecu_path):
        # Try build directory
        vecu_path = os.path.join(script_dir, "..", "foxbms-vecu")
    if not os.path.isfile(vecu_path):
        print(f"[SMOKE] ERROR: foxbms-vecu binary not found")
        plant_proc.terminate()
        return 2

    env = os.environ.copy()
    env["FOXBMS_CAN_IF"] = CAN_IF
    vecu_log = open("/tmp/foxbms-vecu-smoke.log", "w")
    vecu_proc = subprocess.Popen(
        [vecu_path],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=vecu_log
    )
    print(f"[SMOKE] foxbms-vecu started (PID {vecu_proc.pid})")

    # Monitor CAN for BMS NORMAL state
    try:
        import socket as sock
        # Open raw CAN socket
        s = sock.socket(sock.PF_CAN, sock.SOCK_RAW, sock.CAN_RAW)
        s.bind((CAN_IF,))
        s.settimeout(POLL_INTERVAL)
    except Exception as e:
        print(f"[SMOKE] ERROR: Cannot open CAN socket: {e}")
        vecu_proc.terminate()
        plant_proc.terminate()
        return 2

    print(f"[SMOKE] Monitoring CAN {CAN_IF} for BMS NORMAL state (timeout={TIMEOUT_S}s)...")

    start_time = time.time()
    bms_state_seen = {}
    result = 1  # FAIL by default
    normal_time = None
    connected_strings_at_normal = 0
    soc_nonzero_seen = False

    state_names = {
        0: "UNINITIALIZED", 1: "INITIALIZATION", 2: "INITIALIZED",
        3: "IDLE", 5: "STANDBY", 6: "PRECHARGE", 7: "NORMAL",
        8: "CHARGE", 9: "ERROR"
    }

    while True:
        elapsed = time.time() - start_time

        # Phase 1: waiting for NORMAL — enforce overall timeout
        if normal_time is None and elapsed >= TIMEOUT_S:
            break

        # Phase 2: post-NORMAL monitoring — enforce 5-second window
        if normal_time is not None and (time.time() - normal_time) >= POST_NORMAL_S:
            break

        # Check if processes are still alive
        if vecu_proc.poll() is not None:
            print(f"[SMOKE] ERROR: foxbms-vecu exited with code {vecu_proc.returncode}")
            result = 2
            break

        try:
            frame = s.recv(16)  # CAN frame: 4 bytes ID + 4 bytes DLC + 8 bytes data
            if len(frame) >= 16:
                can_id = struct.unpack("=I", frame[0:4])[0] & 0x1FFFFFFF
                data = frame[8:16]

                if can_id == BMS_STATE_CAN_ID and len(data) >= 1:
                    # Byte 0 of 0x220: BmsState signal is 4 bits at DBC start_bit=3
                    # In big-endian DBC notation, this is the LOWER nibble of byte 0
                    state_byte = data[0]
                    bms_state = state_byte & 0x0F
                    connected_strings = (state_byte >> 4) & 0x0F

                    if bms_state not in bms_state_seen:
                        name = state_names.get(bms_state, f"UNKNOWN({bms_state})")
                        print(f"[SMOKE] BMS state: {name} (0x{state_byte:02X}) at {elapsed:.1f}s")
                        bms_state_seen[bms_state] = elapsed

                    if bms_state == BMS_STATE_NORMAL and normal_time is None:
                        normal_time = time.time()
                        connected_strings_at_normal = connected_strings
                        print(f"[SMOKE] BMS reached NORMAL state after {elapsed:.1f}s "
                              f"(connected_strings={connected_strings})")
                        print(f"[SMOKE] Monitoring SOC for {POST_NORMAL_S}s...")

                elif can_id == BMS_SOC_CAN_ID and normal_time is not None and len(data) >= 6:
                    # 0x235 SOC message: byte 5 is SOC value (non-zero = SOC > 0%)
                    soc_byte5 = data[5]
                    if soc_byte5 != 0:
                        soc_nonzero_seen = True

        except sock.timeout:
            continue
        except Exception as e:
            print(f"[SMOKE] CAN read error: {e}")
            continue

    s.close()

    if normal_time is None:
        elapsed = time.time() - start_time
        print(f"[SMOKE] FAIL: BMS did not reach NORMAL within {elapsed:.1f}s")
        print(f"[SMOKE] States seen: {bms_state_seen}")
    else:
        # Assertions after post-NORMAL monitoring window
        assertion_ok = True

        if connected_strings_at_normal == 0:
            print(f"[SMOKE] FAIL: connected_strings is 0 when NORMAL — expected > 0")
            assertion_ok = False
        else:
            print(f"[SMOKE] OK: connected_strings={connected_strings_at_normal} when NORMAL")

        if not soc_nonzero_seen:
            print(f"[SMOKE] FAIL: 0x235 byte 5 was always 0 during post-NORMAL window — SOC not reported")
            assertion_ok = False
        else:
            print(f"[SMOKE] OK: SOC non-zero seen on 0x235")

        if assertion_ok:
            print(f"[SMOKE] PASS: BMS NORMAL, connected_strings > 0, SOC > 0% confirmed")
            result = 0
        else:
            result = 1

    # Cleanup
    print("[SMOKE] Stopping processes...")
    try:
        vecu_proc.send_signal(signal.SIGINT)
    except ProcessLookupError:
        pass
    try:
        plant_proc.send_signal(signal.SIGINT)
    except ProcessLookupError:
        pass
    try:
        vecu_proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        vecu_proc.kill()
    try:
        plant_proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        plant_proc.kill()

    return result


if __name__ == "__main__":
    sys.exit(main())
