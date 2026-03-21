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
BMS_STATE_CAN_ID = 0x220
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
        stderr=subprocess.PIPE
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
    vecu_proc = subprocess.Popen(
        [vecu_path],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE
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

    while (time.time() - start_time) < TIMEOUT_S:
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
                    # Byte 0 of 0x220: bits [7:4] = state, bits [3:0] = connected strings
                    state_byte = data[0]
                    bms_state = (state_byte >> 4) & 0x0F
                    connected_strings = state_byte & 0x0F

                    if bms_state not in bms_state_seen:
                        state_names = {
                            0: "UNINITIALIZED", 1: "INITIALIZATION", 2: "INITIALIZED",
                            3: "IDLE", 5: "STANDBY", 6: "PRECHARGE", 7: "NORMAL",
                            8: "CHARGE", 9: "ERROR"
                        }
                        name = state_names.get(bms_state, f"UNKNOWN({bms_state})")
                        elapsed = time.time() - start_time
                        print(f"[SMOKE] BMS state: {name} (0x{state_byte:02X}) at {elapsed:.1f}s")
                        bms_state_seen[bms_state] = elapsed

                    if bms_state == BMS_STATE_NORMAL:
                        elapsed = time.time() - start_time
                        print(f"[SMOKE] PASS: BMS reached NORMAL state after {elapsed:.1f}s")
                        result = 0
                        break

        except sock.timeout:
            continue
        except Exception as e:
            print(f"[SMOKE] CAN read error: {e}")
            continue

    s.close()

    if result == 1:
        elapsed = time.time() - start_time
        print(f"[SMOKE] FAIL: BMS did not reach NORMAL within {elapsed:.1f}s")
        print(f"[SMOKE] States seen: {bms_state_seen}")

    # Cleanup
    print("[SMOKE] Stopping processes...")
    vecu_proc.send_signal(signal.SIGINT)
    plant_proc.send_signal(signal.SIGINT)
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
