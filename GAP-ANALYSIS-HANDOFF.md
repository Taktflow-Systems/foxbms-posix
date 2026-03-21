# foxBMS POSIX vECU — Gap Analysis & Student Handoff

**Date**: 2026-03-21
**Purpose**: Identify what's done, what's broken, what's missing, and what a student needs to continue this work.

---

## 1. Project Summary

foxBMS 2 v1.10.0 (open-source BMS firmware for TMS570 ARM Cortex-R5) has been ported to run as a native Linux x86-64 process. It communicates via SocketCAN instead of real CAN hardware, and uses a Python plant model to simulate battery data. The goal is a virtual ECU (vECU) for SIL/HIL testing without needing physical hardware.

---

## 2. What Works (Verified)

| Feature | Status | Evidence |
|---------|--------|----------|
| Compilation of 170+ foxBMS source files on x86-64 | DONE | Makefile auto-discovers, GCC 13 builds cleanly |
| 60+ TMS570 register bases redirected to RAM | DONE | `hal_stubs_posix.c` lines 538-567 |
| 80+ HAL function stubs | DONE | `hal_stubs_posix.c` (780 lines) |
| Cooperative main loop (replaces FreeRTOS) | DONE | `foxbms_posix_main.c` — 1ms/10ms/100ms cycling |
| SYS state machine reaches RUNNING (state=5) | DONE | CAN trace verified |
| BMS state machine: IDLE → STANDBY → PRECHARGE | DONE | Contactors close via SPS simulation |
| CAN TX: 15 message types periodic | DONE | candump on vcan1 |
| CAN RX: SocketCAN → ring buffer → foxBMS callbacks | DONE | IVT messages received |
| Plant model sends IVT current/voltage | DONE | `plant_model.py` sends 0x521, 0x522 |
| SPS contactor simulation (track open/close) | DONE | `hal_stubs_posix.c` lines 732-775 |
| Database passthrough (direct call, no queue) | DONE | `DATA_IterateOverDatabaseEntries` called inline |
| SOC at 50% (counting method, 0A current) | DONE | CAN 0x235 |
| Windows unit tests: 183+ passing (Ceedling) | DONE | After clean build + GCC 15 fixes |
| 12 patch scripts for foxBMS source | DONE | `patches/` directory |

---

## 3. What's Broken (Known Blockers)

### 3.1 BMS Cannot Reach NORMAL State
- **Symptom**: BMS transitions IDLE → STANDBY → PRECHARGE → ERROR (loops back)
- **Root cause**: Precharge voltage check fails. foxBMS reads string voltage = 0mV from database because cell voltage CAN messages (0x270) are not properly decoded.
- **Details**:
  - DBC encoding is big-endian Motorola with non-trivial bit positions (start_bit=11, length=13)
  - The `set_can_signal_be()` function in `plant_model.py` (line 22-42) implements DBC encoding but has **not been verified** against actual foxBMS decoding
  - IVT pack voltage = 22200mV is present, but string voltage (from cell voltages) = 0mV
  - Voltage difference > threshold → precharge abort → ERROR
- **What to do**: Verify cell voltage encoding matches foxBMS DBC file. Use `cantools` Python library to encode from the `.dbc` file directly instead of manual bit-banging.

### 3.2 Cell Temperature Encoding Unverified
- `encode_cell_temp_msg()` in `plant_model.py` (line 64-80) uses the **same layout as voltages** with a comment "approximate" — likely wrong
- foxBMS has separate temperature signal definitions in its DBC
- **What to do**: Check the foxBMS DBC file for 0x280 signal definitions and fix encoding

### 3.3 Build Guide References Hardcoded Paths
- `foxbms-posix-build-guide.md` references `/home/an-dao/foxbms-2` and `/tmp/patch_*.py`
- Patch scripts are listed as "stored in /tmp/ on laptop" — these are now in `patches/` but the docs don't reflect this
- **What to do**: Update build guide paths to use relative references

---

## 4. Documentation Gaps

### 4.1 Multiple Overlapping Plans — No Single Source of Truth

There are **3 separate plan documents** with overlapping content and conflicting status:

| Document | Steps | Status Tracking | Conflict |
|----------|-------|-----------------|----------|
| `plan-foxbms-posix-incremental.md` | 12 steps | All "PENDING" | Steps 1-8 are partially or fully done but not updated |
| `plan-foxbms-posix-realistic.md` | 8 steps | Step 1 checked but wrong (`[x] Step 1: PENDING`) | Categories useful but status stale |
| `plan-foxbms-posix-vecu.md` | 5 phases | All "PENDING" | Phase 1-3 are done but not updated |

**Impact**: A student reading these plans will think nothing is done.
**Fix needed**: Consolidate into one plan. Mark completed steps. Remove or archive the others.

### 4.2 STATUS.md vs README.md Inconsistency
- `STATUS.md` is comprehensive (157 lines, 13 implementation steps, current state, next steps) — this is the **best document**
- `README.md` is **empty** (just a title: `# foxBMS POSIX Port`)
- **Fix needed**: README should at minimum link to STATUS.md, or STATUS.md content should be in README

### 4.3 No "How to Debug" Documentation

A student encountering issues has no guide for:
- How to add trace prints to foxBMS state machines (pattern used in `patch_sys2.py`, `patch_bms2.py`)
- How to read CAN output and correlate to BMS states
- What the CAN state bytes mean (e.g., 0x220 byte[0]: 0x03=IDLE, 0x06=STANDBY, etc.)
- How to identify which foxBMS assertion is firing
- How to use `candump` filters effectively

### 4.4 No foxBMS DBC File Reference
- The CAN message format tables in `foxbms-integration.md` are manually transcribed
- The actual DBC file location (in foxBMS source tree) is not documented
- Signal bit positions are critical for encoding — a student needs the DBC as the authoritative reference

### 4.5 Architecture Diagram Missing from Code
- `plan-foxbms-posix-realistic.md` has a good ASCII architecture diagram (lines 128-155)
- Neither `STATUS.md` nor the build guide includes an architecture diagram showing data flow
- **Fix needed**: STATUS.md's architecture section (lines 7-13) is minimal; use the better diagram from the realistic plan

### 4.6 Patch Application Order Not Documented
- `foxbms-posix-build-guide.md` lists patches to run (lines 126-135) but does not document:
  - Why each patch exists (one-line purpose)
  - Whether order matters
  - What happens if you skip one
  - Whether `patch_database2.py`, `patch_10ms2.py`, `patch_precharge.py` (in `patches/` but not in build guide) should also be applied

### 4.7 No Testing/Verification Checklist
- No document describes how to verify the vECU is working correctly after build
- Expected output samples exist in `foxbms-integration.md` (CAN traces) but aren't organized as a test procedure
- **Fix needed**: A "smoke test" checklist: build → run → expect these CAN IDs → expect SYS=RUNNING

---

## 5. Code Gaps

### 5.1 plant_model.py Lacks Dynamic Behavior
- Current model is **static**: 0A current, 22.2V constant, 3700mV per cell constant
- No closed-loop simulation: contactor state changes in foxBMS don't affect plant model output
- No IR drop model, no SOC integration, no thermal model
- **Priority**: P3 (needed for meaningful simulation but not for reaching NORMAL state)

### 5.2 DIAG_Handler Is Fully Suppressed
- All diagnostics return OK — foxBMS cannot detect ANY fault
- This means fault injection testing (Step 9 in incremental plan) is impossible until selective DIAG is implemented
- **Priority**: P4 (implement after NORMAL state works)

### 5.3 No Docker Integration
- Plan mentions Dockerization (incremental Step 10, vECU Phase 5) but nothing exists
- No Dockerfile, no docker-compose fragment
- **Priority**: P5 (after all SIL features work)

### 5.4 posix_overrides.h Not in Repository Listing
- The file is referenced everywhere but its contents are described only in STATUS.md line 132 ("~20 lines")
- Should be documented as it's the key mechanism for ARM→x86 compilation

### 5.5 CAN Socket Opened Twice
- `hal_stubs_posix.c` line 40-47: `posix_early_init()` constructor opens SocketCAN
- `foxbms_posix_main.c` line 132: `main()` opens SocketCAN again
- `hal_stubs_posix.c` line 69-76: `canInit()` opens it a third time
- No harm (reopening replaces fd) but confusing for a student reading the code

### 5.6 Ring Buffer Not Thread-Safe
- `posix_can_rx_buf` uses simple head/tail without atomics or mutex
- In cooperative mode this is fine (single-threaded), but if someone adds threads later, this will race
- **Priority**: P5 (document the assumption, don't fix now)

---

## 6. Inconsistencies Between Docs and Code

| Issue | In Docs | In Code | Resolution |
|-------|---------|---------|------------|
| CAN interface | Build guide says "vcan1", vECU plan says "vcan0" | Code defaults to "vcan1" | Docs should say vcan1 |
| FreeRTOS | vECU plan says "pthreads" (Phase 2), integration doc says "7 FreeRTOS threads" | Cooperative mode, no threads | Old docs describe earlier approach that was abandoned |
| Source location | Build guide says `foxbms-2/posix/` | Actual: `foxbms-posix/src/` | Build guide references laptop layout, not repo layout |
| Patch location | Build guide says `/tmp/patch_*.py` | Actual: `patches/patch_*.py` | Build guide out of date |
| Status checkbox | `plan-foxbms-posix-realistic.md` shows `[x] Step 1: PENDING` | Step 1 (contactor sim) is implemented | Checkbox says done but text says PENDING |

---

## 7. Recommended Student Onboarding Steps

### Week 1: Understand & Reproduce
1. Read `STATUS.md` end-to-end (the best single document)
2. Set up Ubuntu environment per `foxbms-posix-build-guide.md` (adjust paths)
3. Clone foxbms-2 v1.10.0, apply patches, build, run
4. Run `plant_model.py` + `foxbms-vecu` on vcan1, observe CAN output with `candump`
5. Confirm: SYS=RUNNING, BMS=PRECHARGE, then ERROR (expected — cell voltage encoding bug)

### Week 2: Fix Cell Voltage Encoding (The #1 Blocker)
1. Find the foxBMS DBC file: `src/app/driver/config/can_cbs_tx.dbc` (or similar in foxbms-2 repo)
2. Install `cantools`: `pip install cantools`
3. Load the DBC and use `cantools.database.load_file()` to encode 0x270 messages correctly
4. Replace manual `set_can_signal_be()` in `plant_model.py` with `cantools` encoding
5. Verify: BMS transitions PRECHARGE → NORMAL (string voltage matches IVT voltage)

### Week 3: Add Temperature + Dynamic Model
1. Fix 0x280 encoding using same DBC/cantools approach
2. Add dynamic current to plant model (track contactor state from foxBMS 0x240)
3. Verify SOC changes over time (CAN 0x235)

### Week 4: Fault Injection + Documentation Cleanup
1. Implement selective DIAG_Handler (suppress hardware errors, keep software checks)
2. Test overvoltage/undervoltage/overcurrent scenarios
3. Consolidate plan documents into one
4. Update README.md with project overview + quickstart

---

## 8. Key Files for the Student

| File | Purpose | Read Priority |
|------|---------|---------------|
| `STATUS.md` | Best overview of what exists and why | 1 |
| `src/foxbms_posix_main.c` | Entry point, main loop, CAN RX | 2 |
| `src/hal_stubs_posix.c` | All hardware stubs, SPS sim, OS stubs | 2 |
| `src/plant_model.py` | Battery simulator — **this is where the bug is** | 3 |
| `src/Makefile` | Build system | 3 |
| `foxbms-integration.md` | CAN message map, HW findings | 4 |
| `foxbms-posix-build-guide.md` | Build/run instructions (needs path updates) | 4 |
| `patches/*.py` | Source patches applied to upstream foxBMS | 5 |
| `src/posix_overrides.h` | ARM→x86 compilation shim | 5 |

---

## 9. Risks & Gotchas for the Student

1. **Always `make clean` before full rebuild** — stale objects cause mysterious link errors
2. **foxBMS asserts are silent** — `FAS_ASSERT_LEVEL=2` means assertions fire but don't halt. Check stderr for `[DIAG]` or state machine traces if behavior is wrong.
3. **Patches must be reapplied after `git checkout`** on foxbms-2 — they modify upstream files in-place
4. **Big-endian CAN encoding is the #1 pitfall** — foxBMS uses Motorola byte order with DBC-style bit numbering. Manual encoding is error-prone. Use `cantools` library.
5. **`SBC_STATEMACHINE_RUNNING = 2, not 3`** — this was a day-long debugging session (documented in STATUS.md Step 6). Don't change this value.
6. **Ring buffer size is 64 frames** — if plant model sends faster than foxBMS processes, frames drop silently. Increase `POSIX_CAN_RX_BUF_SIZE` if needed.
7. **SocketCAN requires root** — `sudo ip link add vcan1 type vcan` needs root. Consider adding to a setup script.

---

## 10. Summary Scorecard

| Category | Done | Remaining | Confidence |
|----------|------|-----------|------------|
| Compilation & build system | 95% | GCC version warnings | High |
| HAL stubbing | 95% | Selective DIAG | High |
| SYS state machine | 100% | — | High |
| BMS state machine | 70% | NORMAL state blocked | Medium |
| CAN TX | 100% | — | High |
| CAN RX | 90% | Cell voltage decoding path | Medium |
| Plant model | 40% | Dynamic model, correct encoding | Low |
| Documentation accuracy | 40% | Plans stale, paths wrong, no debug guide | Low |
| Testing procedures | 10% | No smoke test, no fault injection | Low |
| Docker/CI integration | 0% | Not started | — |
| HIL bench integration | 0% | Not started | — |
