#!/usr/bin/env python3
"""
foxBMS POSIX vECU — Comprehensive Integration Test

Tests every Phase 1 + Phase 2 exit criterion by monitoring CAN data
over a 30-second run. Reports PASS/FAIL per criterion.

Usage:
    python3 test_integration.py <can_interface> [trip_csv]

If trip_csv is provided, uses plant_model_replay.py.
Otherwise, uses plant_model.py (dynamic).

Exit codes:
    0 = ALL PASS
    1 = SOME FAIL
    2 = ERROR (process startup failure)
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
RUN_DURATION_S = 30
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ================================================================
# Test result tracking
# ================================================================
results = {}

def check(test_id, description, passed, detail=""):
    results[test_id] = {"desc": description, "pass": passed, "detail": detail}
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {test_id}: {description}")
    if detail:
        print(f"         {detail}")

# ================================================================
# CAN data collection
# ================================================================
class CANCollector:
    def __init__(self, interface):
        self.sock = sock.socket(sock.PF_CAN, sock.SOCK_RAW, sock.CAN_RAW)
        self.sock.bind((interface,))
        self.sock.settimeout(0.1)

        # Collected data per CAN ID
        self.frames = {}          # {can_id: [(timestamp, data_bytes), ...]}
        self.first_seen = {}      # {can_id: timestamp}
        self.bms_states = []      # [(timestamp, state, connected_strings)]
        self.soc_values = []      # [(timestamp, raw_byte5)]
        self.cell_voltage_mux = set()  # mux values seen on 0x270
        self.temp_mux = set()          # mux values seen on 0x280
        self.ivt_currents = []         # [(timestamp, current_ma)]
        self.ivt_voltages = []         # [(timestamp, voltage_mv)]

    def collect(self, duration_s):
        """Collect CAN frames for duration_s seconds."""
        start = time.time()
        while (time.time() - start) < duration_s:
            try:
                frame = self.sock.recv(16)
                if len(frame) < 16:
                    continue
                ts = time.time() - start
                can_id = struct.unpack("=I", frame[0:4])[0]

                # Skip extended/error/RTR frames
                if can_id & 0xE0000000:
                    continue
                can_id &= 0x7FF
                data = frame[8:16]

                # Store raw
                if can_id not in self.frames:
                    self.frames[can_id] = []
                    self.first_seen[can_id] = ts
                self.frames[can_id].append((ts, data))

                # Parse specific messages
                if can_id == 0x220:
                    state = data[0] & 0x0F
                    strings = (data[0] >> 4) & 0x0F
                    self.bms_states.append((ts, state, strings))

                elif can_id == 0x235:
                    self.soc_values.append((ts, data[5]))

                elif can_id == 0x270:
                    self.cell_voltage_mux.add(data[0])  # first byte = mux

                elif can_id == 0x280:
                    self.temp_mux.add(data[0])  # first byte = mux

                elif can_id == 0x521:
                    # IVT current: bytes 2-5 big-endian int32
                    if len(data) >= 6:
                        current_ma = struct.unpack(">i", data[2:6])[0]
                        self.ivt_currents.append((ts, current_ma))

                elif can_id == 0x522:
                    # IVT voltage: bytes 2-5 big-endian int32
                    if len(data) >= 6:
                        voltage_mv = struct.unpack(">i", data[2:6])[0]
                        self.ivt_voltages.append((ts, voltage_mv))

            except sock.timeout:
                continue

    def close(self):
        self.sock.close()

# ================================================================
# Main
# ================================================================
def main():
    print(f"=== foxBMS Integration Test ===")
    print(f"CAN: {CAN_IF}, Duration: {RUN_DURATION_S}s")
    if TRIP_CSV:
        print(f"Trip: {TRIP_CSV}")
    print()

    # Setup vcan
    ret = subprocess.run(["ip", "link", "show", CAN_IF], capture_output=True)
    if ret.returncode != 0:
        print(f"ERROR: {CAN_IF} not available")
        return 2

    # Start plant model
    if TRIP_CSV:
        plant_cmd = [sys.executable, os.path.join(SCRIPT_DIR, "plant_model_replay.py"),
                     CAN_IF, TRIP_CSV, "--speed", "10", "--loop"]
    else:
        plant_cmd = [sys.executable, os.path.join(SCRIPT_DIR, "plant_model.py"), CAN_IF]

    plant_proc = subprocess.Popen(plant_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Start vECU
    vecu_path = os.path.join(SCRIPT_DIR, "foxbms-vecu")
    if not os.path.isfile(vecu_path):
        print(f"ERROR: {vecu_path} not found")
        plant_proc.terminate()
        return 2

    env = os.environ.copy()
    env["FOXBMS_CAN_IF"] = CAN_IF
    vecu_log = open("/tmp/foxbms-vecu-integration.log", "w")
    vecu_proc = subprocess.Popen([vecu_path], env=env,
                                  stdout=subprocess.DEVNULL, stderr=vecu_log)

    print(f"Plant PID={plant_proc.pid}, vECU PID={vecu_proc.pid}")
    print(f"Collecting CAN data for {RUN_DURATION_S}s...\n")

    # Collect CAN data
    collector = CANCollector(CAN_IF)
    collector.collect(RUN_DURATION_S)
    collector.close()

    # ================================================================
    # Phase 1 Tests
    # ================================================================
    print("--- Phase 1: BMS NORMAL State ---")

    # 1.1 BMS reaches NORMAL
    states_seen = set(s[1] for s in collector.bms_states)
    normal_reached = 7 in states_seen
    check("P1.1", "BMS reaches NORMAL state",
          normal_reached,
          f"States seen: {sorted(states_seen)}")

    # 1.2 Full state transition
    expected_sequence = [0, 1, 2, 3, 5, 6, 7]  # UNINIT→INIT→INITIALIZED→IDLE→STANDBY→PRECHARGE→NORMAL
    actual_sequence = []
    seen = set()
    for _, state, _ in collector.bms_states:
        if state not in seen and state in expected_sequence:
            actual_sequence.append(state)
            seen.add(state)
    sequence_ok = all(s in actual_sequence for s in expected_sequence)
    check("P1.2", "Full state transition (UNINIT→...→NORMAL)",
          sequence_ok,
          f"Sequence: {actual_sequence}")

    # 1.3 At least 15 CAN message types
    can_ids = sorted(collector.frames.keys())
    check("P1.3", "At least 15 CAN message types on bus",
          len(can_ids) >= 15,
          f"{len(can_ids)} unique IDs: {[f'0x{x:03X}' for x in can_ids[:20]]}")

    # 1.4 SOC reported non-zero
    soc_nonzero = any(v[1] != 0 for v in collector.soc_values)
    check("P1.4", "SOC reported non-zero on 0x235",
          soc_nonzero,
          f"{len(collector.soc_values)} SOC frames, non-zero: {soc_nonzero}")

    # 1.5 Connected strings > 0 at NORMAL
    normal_strings = [s[2] for s in collector.bms_states if s[1] == 7]
    strings_ok = any(s > 0 for s in normal_strings)
    check("P1.5", "Connected strings > 0 when NORMAL",
          strings_ok,
          f"Strings at NORMAL: {set(normal_strings) if normal_strings else 'none'}")

    # 1.6 CAN TX includes contactor-related messages
    contactor_ids = [0x240, 0x241, 0x242, 0x243, 0x244, 0x245]
    contactor_seen = [cid for cid in contactor_ids if cid in collector.frames]
    check("P1.6", "Contactor status messages on CAN bus",
          len(contactor_seen) > 0,
          f"Contactor IDs seen: {[f'0x{x:03X}' for x in contactor_seen]}")

    # 1.7 Time to NORMAL < 15s
    normal_times = [s[0] for s in collector.bms_states if s[1] == 7]
    time_to_normal = normal_times[0] if normal_times else RUN_DURATION_S
    check("P1.7", "Time to NORMAL < 15s",
          time_to_normal < 15.0,
          f"{time_to_normal:.1f}s")

    print()

    # ================================================================
    # Phase 2 Tests
    # ================================================================
    print("--- Phase 2: Realistic Simulation ---")

    # 2.1 SOC changes over time (not stuck at one value)
    if len(collector.soc_values) >= 10:
        soc_unique = set(v[1] for v in collector.soc_values)
        check("P2.1", "SOC value changes over time",
              len(soc_unique) >= 2,
              f"{len(soc_unique)} unique SOC values seen: {sorted(soc_unique)[:10]}")
    else:
        check("P2.1", "SOC value changes over time", False, "Not enough SOC frames")

    # 2.2 Cell voltage varies (not constant 3700mV)
    # Check 0x270 frames for different data payloads
    if 0x270 in collector.frames:
        voltage_payloads = set(f[1].hex() for f in collector.frames[0x270][:100])
        check("P2.2", "Cell voltage data varies over time",
              len(voltage_payloads) >= 3,
              f"{len(voltage_payloads)} unique 0x270 payloads in first 100 frames")
    else:
        check("P2.2", "Cell voltage data varies over time", False, "No 0x270 frames")

    # 2.3 IVT voltage changes (IR drop under load)
    if len(collector.ivt_voltages) >= 10:
        v_unique = set(v[1] for v in collector.ivt_voltages)
        v_min = min(v[1] for v in collector.ivt_voltages)
        v_max = max(v[1] for v in collector.ivt_voltages)
        check("P2.3", "Pack voltage varies (IR drop visible)",
              len(v_unique) >= 2,
              f"V range: {v_min}–{v_max} mV ({len(v_unique)} unique values)")
    else:
        check("P2.3", "Pack voltage varies (IR drop visible)", False, "Not enough IVT frames")

    # 2.4 Current is non-zero during NORMAL
    normal_start = normal_times[0] if normal_times else RUN_DURATION_S
    post_normal_currents = [c[1] for c in collector.ivt_currents if c[0] > normal_start + 2]
    nonzero_currents = [c for c in post_normal_currents if c != 0]
    check("P2.4", "Current non-zero during NORMAL",
          len(nonzero_currents) > 0,
          f"{len(nonzero_currents)}/{len(post_normal_currents)} non-zero current readings after NORMAL")

    # 2.5 Cell voltage mux covers all 5 groups
    check("P2.5", "Cell voltage mux 0-4 all present",
          len(collector.cell_voltage_mux) >= 5,
          f"Mux values seen: {sorted(collector.cell_voltage_mux)}")

    # 2.6 Temperature mux covers multiple groups
    check("P2.6", "Temperature mux covers multiple groups",
          len(collector.temp_mux) >= 2,
          f"Temp mux values seen: {sorted(collector.temp_mux)}")

    # 2.7 Negative current seen (regen/charge)
    if TRIP_CSV:
        negative_currents = [c for c in collector.ivt_currents if c[1] < -100]  # < -0.1A
        check("P2.7", "Negative current (regen/charge) observed",
              len(negative_currents) > 0,
              f"{len(negative_currents)} frames with I < -100mA")
    else:
        # Dynamic plant model only discharges, no regen
        check("P2.7", "Negative current (regen/charge) observed",
              False, "SKIP — dynamic plant model has no regen. Use --trip for this test.")

    # 2.8 IVT current values are plausible (within ±50A scaled)
    if collector.ivt_currents:
        i_min = min(c[1] for c in collector.ivt_currents)
        i_max = max(c[1] for c in collector.ivt_currents)
        plausible = i_min > -50000 and i_max < 50000  # ±50A in mA
        check("P2.8", "IVT current within plausible range (±50A)",
              plausible,
              f"I range: {i_min/1000:.2f}A – {i_max/1000:.2f}A")
    else:
        check("P2.8", "IVT current within plausible range", False, "No IVT current frames")

    print()

    # ================================================================
    # Data Quality Tests
    # ================================================================
    print("--- Data Quality ---")

    # DQ.1 No CAN gaps > 2s for critical IDs
    critical_ids = [0x220, 0x270, 0x521]
    gaps_ok = True
    gap_detail = []
    for cid in critical_ids:
        if cid in collector.frames and len(collector.frames[cid]) >= 2:
            timestamps = [f[0] for f in collector.frames[cid]]
            max_gap = max(timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1))
            if max_gap > 2.0:
                gaps_ok = False
                gap_detail.append(f"0x{cid:03X}: max gap {max_gap:.1f}s")
        else:
            gaps_ok = False
            gap_detail.append(f"0x{cid:03X}: missing or <2 frames")
    check("DQ.1", "No CAN gaps > 2s for critical IDs (0x220, 0x270, 0x521)",
          gaps_ok,
          "; ".join(gap_detail) if gap_detail else "All gaps < 2s")

    # DQ.2 foxBMS did not crash (process still running)
    vecu_alive = vecu_proc.poll() is None
    check("DQ.2", "foxBMS vECU did not crash during test",
          vecu_alive,
          f"exit code: {vecu_proc.returncode}" if not vecu_alive else "still running")

    # DQ.3 Frame counts reasonable (>100 for periodic messages)
    for cid, min_count in [(0x220, 100), (0x270, 100), (0x521, 50)]:
        count = len(collector.frames.get(cid, []))
        check(f"DQ.3.{cid:03X}", f"0x{cid:03X} frame count > {min_count}",
              count > min_count,
              f"{count} frames")

    # DQ.4 BMS never enters ERROR state permanently
    # Allow transient state 10 (OPEN_CONTACTORS) but must recover to 7
    if normal_reached:
        final_states = [s[1] for s in collector.bms_states[-20:]]
        still_normal = 7 in final_states
        check("DQ.4", "BMS still in NORMAL at end of test",
              still_normal,
              f"Last 20 states: {final_states}")
    else:
        check("DQ.4", "BMS still in NORMAL at end of test", False, "Never reached NORMAL")

    print()

    # ================================================================
    # Summary
    # ================================================================
    cleanup(vecu_proc, plant_proc, vecu_log)

    total = len(results)
    passed = sum(1 for r in results.values() if r["pass"])
    failed = total - passed

    print(f"=== RESULTS: {passed}/{total} PASS, {failed} FAIL ===")
    if failed > 0:
        print(f"\nFailed tests:")
        for tid, r in results.items():
            if not r["pass"]:
                print(f"  {tid}: {r['desc']} — {r['detail']}")

    return 0 if failed == 0 else 1


def cleanup(vecu_proc, plant_proc, vecu_log):
    print("[TEST] Stopping processes...")
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


if __name__ == "__main__":
    sys.exit(main())
