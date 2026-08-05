---
name: sil-debug
description: Debug embedded firmware on the PC using a SIL build —
  reproduce the defect with a failing automated test against the SIL
  executable, localize it, fix it, and prove the fix with the same
  test. Use when a firmware bug can be exercised without target
  hardware (requires a sil-build product).
---

# W5 — SIL-based debugging

Use the SIL executable produced by the `sil-build` skill (W4) to turn
a reported firmware misbehavior into a proven fix. The invariant of
this workflow: **the same automated test that demonstrated the bug
must demonstrate the fix.** No "it looks right now" — the evidence is
a failing-then-passing test.

## Workflow

### 1. Reproduce with a failing test in SIL

- Translate the symptom report into an observable SIL behavior:
  a log line, console response, emitted frame, file content, or exit
  code. If the symptom is not observable in SIL (needs real hardware
  timing/peripherals), stop — this skill does not apply; say so.
- Write a scripted test against the SIL binary that asserts the
  EXPECTED behavior (from the spec/requirement, not from current
  code): drive stdin/sockets, capture the log, grep hard markers,
  exit 0/1. Include a sanity precondition (e.g. "system booted to run
  state") so a crashed SIL fails loudly, not silently-green.
- Run it. It must FAIL, and fail for the reported reason. A test that
  passes means the repro is wrong — do not proceed on vibes.

### 2. Localize

Work from the observable symptom backwards to the writing code:

- Find who produces the symptomatic output (grep the log format
  string) — that is the observation point, not necessarily the bug.
- Trace the data to its producer: who constructs the value/frame/
  message that arrives wrong? Follow it across module boundaries;
  in layered firmware the symptom usually surfaces one or more layers
  away from the defect (listener logs it, demo/app code built it).
- Compare the constructing code against the spec (payload layout,
  units, endianness, timing constants). The SIL advantage: add
  temporary printf/log instrumentation or run under gdb/valgrind
  freely — no flash cycles. Remove instrumentation before the fix
  commit.
- State the root cause in one sentence naming file:line before
  editing anything.

### 3. Fix

- Minimal edit at the root cause. Do not also "improve" neighboring
  code; a debugging fix that changes unrelated behavior invalidates
  the proof step.
- Rebuild through the normal SIL build script (idempotent, so this is
  cheap).

### 4. Prove with the same test

- Re-run the unmodified test from step 1: it must now PASS.
- Re-run the SIL smoke test from the sil-build skill: the fix must
  not have broken the baseline scenario.
- Keep both logs (failing run + passing run) as the exercise/ticket
  evidence.

## Deliverables of applying this skill

- The test script (unchanged between failing and passing run).
- Root-cause statement (file:line + one sentence).
- The minimal fix diff.
- Failing-run and passing-run logs, plus a green baseline smoke.

## Exercises

`exercises/ex01-truncated-can-payload/` is the validated
injected-defect exercise against the OpenBSW pilot SIL: a payload
length regression (4-byte counter frame sent as 3 bytes) reproduced,
localized across two modules, fixed, and proven. `EXERCISE.md` there
records the full cycle; `run_exercise.sh` replays it mechanically.
