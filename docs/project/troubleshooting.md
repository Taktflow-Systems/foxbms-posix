# foxBMS POSIX vECU — Troubleshooting Guide

**Covers**: foxBMS 2 v1.10.0 POSIX port (GA-30)
**Last updated**: 2026-03-21

---

## Quick Reference: BMS State Values (CAN 0x220 byte[0])

| Hex | Decimal | State |
|-----|---------|-------|
| 0x00 | 0 | UNINITIALIZED |
| 0x10 | 16 | INITIALIZATION (state 1) |
| 0x30 | 48 | IDLE (state 3) |
| 0x50 | 80 | STANDBY (state 5) |
| 0x60 | 96 | PRECHARGE (state 6) |
| 0x71 | 113 | NORMAL, 1 string connected (state 7) |
| 0x90 | 144 | ERROR (state 9) |

Read live state:
```bash
candump vcan1,220:7FF -t z | head -20
```

---

## 1. BMS Stuck in IDLE

**Symptom**: `candump vcan1,220:7FF` shows byte[0] = `0x30` indefinitely. BMS does not transition to STANDBY.

**Possible causes**:

### 1a. State request 0x210 not arriving

**Diagnose**:
```bash
candump vcan1,210:7FF -t z
```
If no `0x210` frames appear, the plant model is not running or is on the wrong interface.

**Fix**:
```bash
# Make sure plant model is running and on the correct interface
cd foxbms-posix/src
python3 plant_model.py vcan1 &

# Verify it sends 0x210
candump vcan1,210:7FF -t z | head -5
```

### 1b. State request encoding wrong

**Diagnose**: In `candump`, `0x210` appears but byte[0] is `0x00`. That encodes STANDBY. After ~3 seconds the plant model switches to NORMAL (`0x02`). Watch for the transition.

Expected sequence:
- First 3s: `210#0000000000000000` (STANDBY request)
- After 3s: `210#0200000000000000` (NORMAL request)

If stuck on `0x00` forever, `tick` counter is not advancing — plant model may have crashed.

### 1c. CAN RX not routing to database

**Diagnose**: Check stderr of foxbms-vecu for:
```
[CAN-RX] Dequeued id=0x210
```
If this line never appears, the ring buffer is not being dequeued or the callback is not firing.

**Fix options**:
1. Verify `FOXBMS_CAN_IF` is set: `echo $FOXBMS_CAN_IF` — must match the interface the plant model is on.
2. Verify vcan is up: `ip link show vcan1` — state must be `UNKNOWN` (vcan does not show UP).
3. If no `[CAN-RX]` lines at all, the patches were not applied. Reapply:
   ```bash
   cd foxbms-posix/foxbms-2
   python3 ../patches/apply_all.sh   # or run each patch manually
   cd ../src && make clean && make -j4
   ```

### 1d. Plant model started after vECU

**Diagnose**: If foxbms-vecu was started first and the plant model started more than ~5s later, the BMS may have timed out waiting for current sensor presence.

**Fix**: Always start the plant model first, wait for `Plant model sending on vcan1`, then start foxbms-vecu. Or use `test_smoke.py` which handles the ordering automatically.

---

## 2. BMS Stuck in STANDBY

**Symptom**: CAN 0x220 byte[0] = `0x50` (STANDBY). BMS received the state request but precharge will not start.

**Possible causes**:

### 2a. String voltage does not match IVT pack voltage (precharge voltage check fails)

The precharge check requires: `|string_voltage - bus_voltage| < threshold`

- **String voltage** = sum of all cell voltages from 0x270. With 18 cells × 3700mV = 66600mV.
- **Bus voltage** = IVT Voltage 3 from 0x524 (`highVoltage_mV[s][2]`).

**Diagnose**: Run with precharge debug patch applied:
```bash
cd foxbms-posix/foxbms-2
python3 ../patches/patch_precharge.py
cd ../src && make -j4
FOXBMS_CAN_IF=vcan1 ./foxbms-vecu 2>&1 | grep -i precharge
```

**Fix**: The plant model must send `0x524` with the same voltage as the total cell voltage sum.

Key discovery: foxBMS redundancy module uses `highVoltage_mV[s][2]` (index 2), NOT `[s][0]`. This means **IVT Voltage 3 (0x524) is required** — sending only 0x522 and 0x523 is not enough.

Verify the plant model sends all three:
```bash
candump vcan1,522:FFF -t z | head -10  # should show 0x522, 0x523, 0x524
```

### 2b. DECAN_DATA_IS_VALID misunderstood

**Common mistake**: Setting the invalid flag to `0` thinking `0 = not invalid = valid`.

**Reality**: `DECAN_DATA_IS_VALID = 1`. The flag is inverted. Setting `invalid_flag = 0` marks the data as **invalid**, causing foxBMS to discard all cell voltages.

**Diagnose**: Check `plant_model.py` — the invalid flags in `encode_cell_voltage_msg` must be `1`:
```python
d = foxbms_encode_signal(d, 12, 1, 1)  # Invalid flag 0: 1=VALID
d = foxbms_encode_signal(d, 13, 1, 1)  # Invalid flag 1: 1=VALID
```
If any of these are `0`, cell voltages are ignored and string voltage = 0, which will never match bus voltage.

### 2c. Cell voltage mux not covering all 18 cells

foxBMS expects `BS_NR_OF_CELL_BLOCKS_PER_MODULE = 18`. Four cells per mux group → need 5 mux values (0–4) to cover 18 cells.

**Diagnose**: Check `plant_model.py` sends `mux in range(5)`:
```python
for mux in range(5):   # 5 × 4 = 20 slots (18 used, 2 unused)
    can_send(0x270, encode_cell_voltage_msg(mux, [3700, 3700, 3700, 3700]))
```
If only `range(4)` or `range(3)`, some cells get 0mV, reducing string voltage and failing the precharge check.

---

## 3. BMS Goes to ERROR After PRECHARGE

**Symptom**: CAN 0x220 shows state transitions STANDBY → PRECHARGE → ERROR (0x90) instead of PRECHARGE → NORMAL.

**Possible causes**:

### 3a. String voltage / bus voltage mismatch

Same root cause as §2a but now foxBMS actually started precharge and then failed the final voltage check.

**Diagnose**:
```bash
FOXBMS_CAN_IF=vcan1 ./foxbms-vecu 2>&1 | grep -i "precharge\|voltage\|string"
```
Apply `patch_precharge.py` for more verbose output.

**Fix**: Ensure `0x524` value = `18 × cell_voltage_mV`. Default: `66600`.

### 3b. Contactor feedback not matching request

foxBMS checks that contactors actually close when requested. If SPS simulation returns wrong state, a mismatch triggers ERROR.

**Diagnose**:
```bash
FOXBMS_CAN_IF=vcan1 ./foxbms-vecu 2>&1 | grep "\[SPS\]"
```
Expected output during precharge:
```
[SPS] RequestContactor ch=0 state=1
[SPS] RequestContactor ch=1 state=1
[SPS] RequestContactor ch=2 state=1
```
If `[SPS]` lines are absent, the HAL stub for SPS is not routing correctly.

### 3c. Precharge timeout

foxBMS has a maximum time allowed for precharge. If the BMS is running slowly (CPU overloaded, debugger attached, extremely long `usleep`), the precharge timeout fires before voltage equilibrates.

**Fix**: Make sure the cooperative loop delay is `usleep(500)` (500 microseconds), not `usleep(500000)`. The main loop must run at roughly 1ms.

---

## 4. No CAN Output

**Symptom**: `candump vcan1` shows nothing, or only traffic from the plant model.

### 4a. SocketCAN interface not created

**Diagnose**:
```bash
ip link show vcan1
```
If the command fails or shows `does not exist`, vcan was never created.

**Fix**:
```bash
sudo modprobe vcan
sudo ip link add vcan1 type vcan
sudo ip link set vcan1 up
```
This must be done once per boot. vcan is not persistent.

### 4b. Wrong FOXBMS_CAN_IF

**Diagnose**:
```bash
echo $FOXBMS_CAN_IF
```
If empty, foxbms-vecu defaults to `vcan1`. If you have both `vcan0` and `vcan1`, make sure both foxbms-vecu and `candump` are on the same interface.

**Fix**:
```bash
FOXBMS_CAN_IF=vcan1 ./foxbms-vecu
# Monitor on the same interface
candump vcan1
```

### 4c. vcan created but not brought up

**Diagnose**:
```bash
ip link show vcan1
# Look for: state UNKNOWN (correct) vs state DOWN (wrong)
```
A newly added vcan interface in DOWN state will not pass frames.

**Fix**:
```bash
sudo ip link set vcan1 up
```

### 4d. canTransmit never called (BMS never left UNINITIALIZED)

If foxbms-vecu exits immediately or gets stuck before the main loop, `canTransmit` is never called.

**Diagnose**:
```bash
FOXBMS_CAN_IF=vcan1 ./foxbms-vecu 2>&1 | head -20
```
Expect to see:
```
[init] HAL done
[init] Engine done
[init] PreCyclic done
[run] Entering main loop
```
If output stops before `[run] Entering main loop`, a crash or assert fired during init.

---

## 5. Segfault on Startup

**Symptom**: foxbms-vecu prints nothing (or just `[init] HAL done`) then dies with `Segmentation fault`.

### 5a. Register buffer patches not applied

foxBMS accesses TMS570 hardware registers at physical MMIO addresses (e.g., `0xFFF7xxxx`). On x86-64 Linux these are unmapped and cause an immediate segfault.

**Fix**: `patch_all_regs.py` must be applied before building:
```bash
cd foxbms-posix/foxbms-2
python3 ../patches/patch_all_regs.py
cd ../src && make clean && make -j4
```

**Verify the patch was applied**:
```bash
grep -r "FOXBMS_POSIX" foxbms-posix/foxbms-2/src/os/freertos/portable/GCC/ARM_CR5F/portASM.h 2>/dev/null | head -3
```
If nothing found, check `HL_reg_*.h` headers in the HALCoGen include path:
```bash
grep "posix_reg_buf" foxbms-posix/foxbms-2/build/app_host_unit_test/include/HL_reg_can.h 2>/dev/null | head -3
```

### 5b. Patches not reapplied after git checkout

Patches modify upstream foxBMS files in-place. A `git checkout` or `git submodule update` in `foxbms-2/` resets them.

**Fix**: Reapply all required patches in order:
```bash
cd foxbms-posix/foxbms-2
python3 ../patches/patch_all_regs.py   # MUST be first
python3 ../patches/patch_sbc.py
python3 ../patches/patch_sbc2.py
python3 ../patches/patch_rtc.py
python3 ../patches/patch_can_sensor.py
python3 ../patches/patch_database.py
cd ../src && make clean && make -j4
```
Or use the consolidated script:
```bash
cd foxbms-posix/foxbms-2
bash ../patches/apply_all.sh
```

### 5c. fassert.c conflict

If `fassert.c` was not excluded from the build and the linker picks up two definitions of `FAS_StoreAssertLocation`, the binary may crash on any assert.

**Diagnose**:
```bash
nm foxbms-posix/src/foxbms-vecu | grep FAS_StoreAssertLocation
```
Should show exactly one definition. If two appear, check `Makefile` exclusions.

---

## 6. 100% CPU Usage

**Symptom**: `top` shows foxbms-vecu consuming 99–100% of a CPU core. The system feels sluggish.

**This is expected behavior.** The cooperative main loop runs as fast as possible with only a `usleep(500)` (500 microseconds) delay per iteration. This is intentional — foxBMS uses FreeRTOS with a 1ms tick, and the POSIX port approximates this.

**Mitigation**: Use `timeout` to bound execution time in scripts:
```bash
FOXBMS_CAN_IF=vcan1 timeout 30 ./foxbms-vecu
```

Or use `test_smoke.py` which starts foxbms-vecu as a subprocess and kills it after receiving NORMAL state or on timeout.

**Do not** increase `usleep()` significantly (e.g., to 10ms) — the 1ms/10ms/100ms cyclic tasks will not fire at the correct rate and the BMS may not transition states properly.

---

## 7. Zombie Processes

**Symptom**: After a test run, `pgrep foxbms-vecu` or `pgrep plant_model` still returns PIDs. A subsequent test run fails because a stale process is also sending/receiving on vcan1, causing duplicate CAN frames or unexpected state transitions.

**Diagnose**:
```bash
pgrep -a foxbms-vecu
pgrep -a plant_model.py
```

**Fix** (manual cleanup):
```bash
pkill -f foxbms-vecu
pkill -f plant_model.py
```

**Fix** (automated — preferred): Use `test_smoke.py` for all automated test runs. It starts both processes, monitors for NORMAL state, then sends SIGINT to both and waits for clean exit. Leftover processes are killed if they do not exit within 5 seconds.
```bash
cd foxbms-posix/src
python3 test_smoke.py vcan1
echo "Exit code: $?"  # 0=PASS, 1=FAIL, 2=ERROR
```

**Before any new test**, always verify no stale processes:
```bash
pgrep -a foxbms 2>/dev/null; pgrep -a plant_model 2>/dev/null
```

---

## 8. Build Fails with Missing Headers

**Symptom**: `make` fails with errors like:
```
fatal error: HL_reg_can.h: No such file or directory
fatal error: HL_sys_vim.h: No such file or directory
```

### 8a. HALCoGen headers not copied

The foxBMS build system generates headers from TI HALCoGen. These are not in the foxBMS source tree — they must be generated by a Windows build first, then copied.

**Fix**: Copy the pre-generated headers from a Windows build:
```bash
# On Windows (Git Bash), from foxbms-2 root:
python fox.py waf configure
python fox.py waf clean_app_host_unit_test build_app_host_unit_test

# Then copy to Linux:
scp -r build/app_host_unit_test/include/ user@ubuntu:/path/to/foxbms-posix/foxbms-2/build/app_host_unit_test/include/
```

Expected location: `foxbms-posix/foxbms-2/build/app_host_unit_test/include/HL_reg_can.h`

### 8b. foxbms-2 submodule not initialized

**Diagnose**:
```bash
ls foxbms-posix/foxbms-2/src/
```
If the directory is empty or missing, the submodule was not initialized.

**Fix**:
```bash
cd foxbms-posix
git submodule update --init foxbms-2
```

### 8c. Stale Ceedling cache (unit tests only)

For the Windows unit test suite (`python fox.py ceedling test:all`), stale generated mocks cause header errors.

**Fix**:
```bash
python fox.py waf clean_app_host_unit_test
python fox.py ceedling test:all
```
Always clean before a full unit test run.

---

## 9. DIAG Faults Flooding stderr

**Symptom**: stderr is full of lines like:
```
[DIAG] fault id=42 event=EVENT_OK
[DIAG] fault id=7 event=EVENT_OK
```

**This is expected behavior after GA-06 selective DIAG implementation.**

The DIAG system distinguishes two categories:

| Category | Behavior | Examples |
|----------|----------|---------|
| Hardware-absent faults (24 IDs) | Suppressed — return OK silently | SBC watchdog, SPI timeout, I2C not responding |
| Software-checkable faults (61 IDs) | Logged to stderr and return ERR_OCCURRED | Overvoltage, overcurrent, overtemperature, plausibility checks |

Lines beginning with `[DIAG]` are software-layer safety checks that actually ran. They are informational during normal operation. If a fault reaches ERR_OCCURRED for a software-checkable fault, the BMS will eventually transition to ERROR state.

**If you see unexpected fault floods** during normal operation (e.g., every 10ms with `event=EVENT_OK`), that is a DIAG check firing and clearing rapidly — normal for periodic checks.

**If the BMS enters ERROR** and you see `[DIAG]` lines with event values other than `EVENT_OK`, those are the root-cause faults. Cross-reference the fault ID against:
```
foxbms-posix/foxbms-2/src/app/engine/diag/diag_cfg.h
```

---

## 10. FAS_ASSERT Crash on Startup

**Symptom**: foxbms-vecu starts, prints one or two `[init]` lines, then:
```
[FAS] ASSERT FAILED: src/app/application/bms/bms.c:247
Aborted
```

**This is intentional behavior after GA-07 crash handler fix.**

Before GA-07, `FAS_ASSERT_LEVEL = 2` silently ignored all assertion failures. After GA-07, `FAS_StoreAssertLocation()` is overridden to log the file and line to stderr, then call `exit(1)`. This catches real bugs instead of hiding them.

**Diagnosis steps**:

1. Note the file and line from the message.
2. Open that file in `foxbms-posix/foxbms-2/src/`.
3. Find the assertion — typically `FAS_ASSERT(condition)`.
4. Check what the condition is testing. Common assertions:
   - Null pointer checks on queue handles
   - Enum range checks
   - Initialization order requirements

**Common root cause**: A queue handle that is `NULL` because the relevant FreeRTOS task was not created. In cooperative mode, some task creation is skipped. If a new foxBMS version adds a queue and the code assumes it was created:

**Fix options**:
- Add a stub in `hal_stubs_posix.c` to create/return a valid fake handle for that queue.
- If the assertion is in a path that should never be reached in POSIX mode, add the relevant guard to `posix_overrides.h`:
  ```c
  // In posix_overrides.h, add to the FAS_ASSERT override:
  #define FAS_ASSERT(x) do { \
      if (!(x)) { \
          fprintf(stderr, "[FAS] ASSERT FAILED: %s:%d\n", __FILE__, __LINE__); \
          exit(1); \
      } \
  } while(0)
  ```
  This is already the GA-07 behavior. Do not revert to `NO_OPERATION` — real bugs will be hidden.

---

## Quick Diagnostic Checklist

Run this sequence when something is not working:

```bash
# 1. Is vcan up?
ip link show vcan1

# 2. Are both processes running?
pgrep -a foxbms-vecu
pgrep -a plant_model

# 3. Is there any CAN traffic at all?
timeout 5 candump vcan1 | wc -l

# 4. What BMS state is being reported?
timeout 10 candump vcan1,220:7FF -t z

# 5. Is the plant model sending all required IDs?
timeout 5 candump vcan1 | awk '{print $2}' | sort -u

# Expected IDs from plant model: 210 270 280 521 522 523 524 527
# Expected IDs from foxbms-vecu: 220 221 231 232 233 234 235 240 241 242 243 244 245 250 260 301

# 6. Check foxbms-vecu stderr for init errors
FOXBMS_CAN_IF=vcan1 timeout 10 ./foxbms-vecu 2>&1 | grep -E "\[init\]|\[FAS\]|\[DIAG\]|ERROR|error" | head -30
```

---

## Reference: Key Architecture Facts

| Item | Value | Notes |
|------|-------|-------|
| `DECAN_DATA_IS_VALID` | `1` | Invalid flag = 1 means VALID. Counterintuitive. |
| `SBC_STATEMACHINE_RUNNING` | `2` | Not 3. Wrong value causes SYS timeout in INITIALIZATION. |
| Cells per module | `18` | `BS_NR_OF_CELL_BLOCKS_PER_MODULE = 18`. 5 mux groups needed. |
| IVT Voltage for HV bus | `0x524` | Redundancy module reads `highVoltage_mV[s][2]` (index 2 = Voltage 3). |
| CAN big-endian encoding | `CAN_BIG_ENDIAN_TABLE` | Lookup table maps DBC start bit to actual bit position. |
| Loop rate | `usleep(500)` | 500us = ~2 kHz loop. 1ms/10ms/100ms tasks fire on elapsed time. |
| `FAS_ASSERT_LEVEL` | `2` override in GA-07 | Crashes on assert failure, logging file+line. This is correct. |
| FOXBMS_CAN_IF | env var | Default: `vcan1`. Must match interface used by plant model and candump. |
