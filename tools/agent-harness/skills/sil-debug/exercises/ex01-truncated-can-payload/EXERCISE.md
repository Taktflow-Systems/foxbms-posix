# Exercise ex01 — truncated CAN payload (injected defect)

Validated 2026-08-02 against the sil-build pilot (Eclipse OpenBSW
referenceApp, POSIX/FreeRTOS SIL, source pinned bc8d49b5). This file
records the actual first execution of the sil-debug workflow;
`run_exercise.sh` replays the cycle mechanically.

## Symptom (as a bug report would state it)

"Receivers of the 1 Hz counter frame on CAN_0 see a corrupted
counter: the frame on id 0x558 arrives with only 3 data bytes instead
of the specified 4-byte big-endian cycle counter."

## Injected defect

`defect.patch`: in
`executables/referenceApp/application/src/systems/DemoSystem.cpp`
(cyclic 1 s CAN send), the frame is constructed with payload length 3
instead of 4 — the classic "length constant no longer matches the
payload object" regression.

## Workflow execution record

### 1. Reproduce with a failing test in SIL

- Observable chosen: the sent-confirmation log line
  `[CanDemoListener] CAN frame sent, id=0x558, length=N` (POSIX SIL,
  no CAN hardware needed).
- Test written from the SPEC (4-byte counter), not from the code:
  `test_can_counter_frame.sh` — boot to Run level 9 (precondition),
  require >= 3 confirmed 0x558 frames, require length=4 on every one.
- Green-on-healthy check first: `baseline-check.log` — TEST PASS
  (5 frames, all length=4). Then, with the defect injected and
  rebuilt: `failing-run.log` — **TEST FAIL: 5 of 5 frames on 0x558
  have wrong payload length**, all `length=3`. Repro confirmed, and
  it fails for the reported reason.

### 2. Localize

- The symptomatic line is printed by
  `CanDemoListener::canFrameSent()`
  (`executables/referenceApp/application/src/app/CanDemoListener.cpp`)
  — observation point only; it just echoes the frame it was handed.
- Producer of id 0x558 (grep `0x558`):
  `DemoSystem::cyclic()`,
  `executables/referenceApp/application/src/systems/DemoSystem.cpp`
  — builds the payload as `etl::be_uint32_t canData{canSentCount}`
  (4 bytes by construction) but constructs
  `CANFrame(0x558, canData.data(), 3)`.
- Root cause (one sentence): DemoSystem.cpp, cyclic-send block — the
  CANFrame payload-length argument (3) contradicts the 4-byte
  `be_uint32_t` payload it points at, truncating the counter's
  low byte off the wire.

### 3. Fix

Minimal edit: restore the length argument to 4 (one character, one
line; equivalently `git apply -R defect.patch`). No neighboring code
touched. Incremental rebuild: 2 ninja targets.

### 4. Prove with the same test

- Same, unmodified test: `passing-run.log` — **TEST PASS: 5 counter
  frames on 0x558, all length=4**.
- Baseline not broken: sil-build pilot `smoke.sh` re-run —
  SMOKE PASS, exit 0, all 4 markers.

## Files

- `defect.patch` — the injected defect (apply with `git apply`,
  fix with `git apply -R`).
- `test_can_counter_frame.sh` — the reproduce/prove test (identical
  in both runs).
- `run_exercise.sh` — replays the whole cycle; refuses to run on a
  dirty pilot tree; leaves the tree pristine.
- `baseline-check.log`, `failing-run.log`, `passing-run.log` —
  evidence of the validated run.
