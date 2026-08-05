---
name: sil-build
description: Build a PC-hosted SIL (software-in-the-loop) executable
  from embedded firmware sources by stubbing the hardware-access layer,
  then prove it with a smoke scenario. Use when firmware must run,
  be tested, or be debugged on a development machine without target
  hardware.
---

# W4 — SIL creation for embedded systems

Turn an embedded firmware codebase into an executable that builds and
runs on the host PC, with every hardware access stubbed or simulated.
The output is not "the code compiles" — it is a running process that
executes the firmware's real application logic and passes a defined
smoke scenario.

## Workflow

### 1. Identify the hardware boundary

Find the seam between portable application logic and hardware access.
Look for, in order of reliability:

- **An existing platform/port layer**: directories named `platforms/`,
  `bsp/`, `hal/`, `port/`, `mcal/`, `arch/`, or per-target dirs
  (`s32k1xx/`, `stm32/`, …). If a `posix`, `sim`, `host`, or `x86`
  sibling already exists, the boundary is already drawn — use it
  (that is the "plausible POSIX build path" case).
- **The build system's target switch**: a cmake cache variable, Kconfig
  symbol, or Makefile variable that selects the target
  (e.g. `BUILD_TARGET_PLATFORM=POSIX` vs `S32K148EVB`). Whatever it
  gates is the hardware side.
- **Register access as last resort**: grep for volatile register
  access, linker-script symbols, interrupt vector tables, and vendor
  SDK includes. Everything that touches them is below the boundary.

Record the boundary explicitly (which modules are hardware-side, which
are portable) before writing any stub — this list is the spec for
step 2 and the review artifact for the pilot doc.

### 2. Stub the hardware side

For each hardware-side module the application actually links against,
provide a host implementation, choosing per module:

- **Null/log stub** — calls succeed, optionally log; for peripherals
  irrelevant to the scenario under test (PWM, watchdog kick).
- **Host-API adapter** — map to a host equivalent: UART/console →
  stdio, CAN → SocketCAN or an in-process queue, Ethernet → TAP/UDP,
  NVM/EEPROM → a file, system tick → clock_gettime/OS timer.
- **Behavioral model** — only where the scenario needs realistic
  values (e.g. an ADC ramp); keep models minimal and deterministic.

Rules: never edit portable application sources to make them host-safe —
if application code reaches around the boundary, that is a finding to
record, not to patch silently. Keep stubs in a dedicated platform dir
mirroring the real BSP's structure so the diff against the target BSP
stays reviewable. An RTOS is stubbed the same way: use the RTOS's own
POSIX/simulator port (FreeRTOS POSIX port, ThreadX Linux port) rather
than reimplementing scheduling.

### 3. Host build

- Prefer the codebase's native build system with a new/existing host
  target over a parallel hand-written Makefile; wire the platform
  switch, host compiler (native GCC/Clang, no cross toolchain), and
  the stub layer into it.
- Pin the source revision and record exact toolchain versions — SIL
  results are only meaningful against a known source state.
- Wrap the whole thing in one idempotent script (`build.sh`): fetch if
  absent → configure → build → print the binary path. Zero manual
  steps.

### 4. Smoke test

Define a smoke scenario with **hard, greppable pass criteria** before
running it. Minimum bar:

- the process starts and reaches its normal operating state (e.g.
  lifecycle/scheduler running, main loop ticking);
- it performs at least one observable domain action on request
  (console command answered, frame sent, state transition);
- it shuts down cleanly on command and exits 0 — an abort on EOF or a
  kill-by-timeout is a FAIL even if the boot looked healthy.

Script it (`smoke.sh`): drive stdin/sockets, capture the full log,
assert every marker, print PASS/FAIL. Keep the log as evidence.

## Deliverables of applying this skill

- Boundary record (hardware-side vs portable module list).
- Stub layer (or the identified existing one) in the platform dir.
- `build.sh` + `smoke.sh`, both idempotent, both runnable by a cold
  session.
- The smoke log proving the pass criteria.

## Pilot

`pilot/` contains the validated worked example: Eclipse OpenBSW
referenceApp (automotive base software, S32K148 target) built for the
POSIX platform via `cmake --preset posix-freertos` and smoke-tested to
run level 9 with clean poweroff. See `pilot/PILOT.md` for the
boundary analysis and evidence.
