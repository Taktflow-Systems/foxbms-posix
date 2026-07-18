# Fast-SIL Improvement Plan — Debug-Platform Context (2026-07-18)

## How to read this

Audience: a future AI worker (or the SIL's creator) landing cold, with no
prior conversation context. Each step below is self-contained: Step ID,
Goal, Inputs, Deliverables, Acceptance criteria, Gate, Definition of done.
Steps are ordered by ROI **for the SIL's current role as an interactive
GDB/DWARF debug platform** — not as a regression suite. Regression-suite
work is explicitly deferred (see final section). Paths are given
repo-relative to the SIL workspace; adapt names to the local layout.

Context recap: a gap audit of the fast SIL (native x86-64 build of the
firmware, ~41 link-time fakes, single-threaded tick scheduler, pytest +
GDB/DWARF harness) found four disease classes: (1) fakes that replace
production *logic*, not just hardware; (2) canned-success stub returns
instead of plant-driven values; (3) tautological test oracles; (4) a single
benign interleaving standing in for real concurrency. For a **debug
platform**, classes 1–2 are fatal (you step into code that is not real, or
cannot reproduce the scenario), class 3 is irrelevant for now, class 4 is
an accepted limitation.

Guiding doctrine for all steps: **fake nothing that is logic; simulate
chips behind buses; script-mock only the raw register edge.** Fidelity
ladder: stub (canned) < mock (scripted per test) < simulation model (real
code runs against a modeled environment; behavior emerges from plant
physics).

---

## D1 — Re-cut the fake boundary: restore all faked logic

- **Goal**: Every production module containing decision logic executes for
  real inside the SIL binary, so it can be stepped through under GDB.
- **Why first**: A fake in the binary is a dead-end under a debugger — you
  step into `return OK;` and the investigation ends, or the bug lives in
  code that is not even linked. For a debug platform this is not a
  coverage gap; it makes whole classes of investigation impossible.
- **Inputs**: the gap audit's stub/fake inventory (section 4); the SIL
  CMake source lists.
- **Deliverables**:
  - Updated SIL CMake source lists linking the REAL: cell-monitoring
    algorithm, AFE/CMB SPI driver (mock the bus beneath it, not the
    driver), ISO-TP stack, overcurrent callback path, CRC/crypto tables.
  - A pruned fake inventory containing hardware-edge entries only, with a
    one-line rule at the top: "a fake may replace hardware access, never
    production logic."
- **Acceptance criteria**:
  - `nm` / map-file inspection shows the production symbols for the
    restored modules present in the SIL binary.
  - A GDB session can set a breakpoint inside each restored module and
    hit it during a normal run.
  - No production `.cpp` containing decision logic remains
    link-substituted (checkable by diffing target vs SIL source lists).
- **Gate / review**: creator self-review against the audit's section 4
  inventory; each remaining fake justified as hardware-edge.
- **Definition of done**: every module the audit flagged as "logic
  replaced by stub" is back in the binary and breakpointable.

## D2 — Plant-driven signals instead of canned values

- **Goal**: Voltage / current / temperature / pack signals entering the
  firmware come from the plant model each tick, so field scenarios are
  reproduced by dialing plant state, not by hand-crafting mock returns.
- **Why**: Debugging starts with reproduction. "Cell 7 sags to 2.9 V under
  load at tick 12000" should be one line of scenario script, after which
  the real protection path fires on its own. With canned `ADC_OK` /
  constant returns, reproducing a field issue means reverse-engineering
  which mock values produce the symptom — hours instead of minutes.
- **Inputs**: D1 complete (real consumers in the binary); existing plant
  model (Python or C).
- **Deliverables**:
  - A plant→signal binding layer: per tick, the central voltage/current/
    temperature fakes read from plant state; zero hardcoded ADC-OK or
    constant-value returns on these channels.
  - Three worked scenario scripts as templates: overvoltage trip,
    overcurrent trip, precharge + contactor close.
  - A `set_plant(param, value)` / maneuver API callable from the pytest
    harness AND from the GDB Python layer (so plant state can be changed
    mid-debug-session).
- **Acceptance criteria**:
  - Setting a plant cell to 4.5 V trips the real OV protection path with
    no per-test mock scripting.
  - Grep of the central signal fakes shows no constant success returns.
- **Gate / review**: run the three template scenarios under GDB; confirm
  the firmware reaction is produced by production code (D1 symbols).
- **Definition of done**: a field-style scenario is reproducible by plant
  maneuver alone.

## D3 — Re-arm asserts in the SIL build

- **Goal**: Firmware asserts are compiled in and each failure stops the
  process (distinct exit code; under GDB, a trap at the assert site).
- **Why**: An armed assert under GDB is a free breakpoint at the exact
  moment state goes bad. With NDEBUG you notice the corruption thousands
  of ticks later and have to walk backwards by hand.
- **Inputs**: SIL compiler-flags file (the audit found NDEBUG set via the
  RelWithDebInfo-style config).
- **Deliverables**: one build-config change removing NDEBUG for the SIL
  configuration; assert handler that raises SIGTRAP (debugger-friendly)
  and exits with a distinct code when not under a debugger.
- **Acceptance criteria**: a deliberately violated assert (a) stops GDB at
  the assert site with full backtrace; (b) fails the harness run with the
  distinct exit code when run headless.
- **Gate / review**: none beyond the two checks above (trivial change).
- **Definition of done**: assert firing is observable in both interactive
  and scripted runs.

## D4 — Record/replay with rr (reverse execution)

- **Goal**: Any SIL run can be recorded once with Mozilla `rr` and
  replayed deterministically with reverse-continue / reverse-step.
- **Why**: This is the single biggest debugging superpower available to a
  native x86-64 SIL and does not exist on target, ever. Workflow:
  `rr record ./sil_app <scenario>`, then in replay set a watchpoint on the
  corrupted variable and `reverse-continue` — you land on the exact write
  that corrupted it. Heisenbugs become one-shot captures: record when it
  happens, debug the recording forever.
- **Inputs**: D3 (asserts as stop points make recordings self-locating);
  Linux host with `rr` installed (needs perf counters; WSL2 may require
  nested-virtualization perf support — verify, and fall back to a native
  Linux box or UndoDB-style alternative if unavailable).
- **Deliverables**:
  - `tools/sil-rr` wrapper script: record a scenario, replay latest
    recording, replay under the D5 GDB layer.
  - A short HOWTO (one page) with the watchpoint + reverse-continue
    recipe and the two or three rr flags that matter (`rr record -n` for
    no-syscall-buffering if the binary trips it, chaos mode option).
- **Acceptance criteria**: record a run where an assert fires; in replay,
  set a watchpoint on the asserted variable and reverse-continue to the
  writing instruction.
- **Gate / review**: HOWTO walked through once end-to-end by the creator.
- **Definition of done**: the watchpoint + reverse-continue recipe works
  on a real recording.

## D5 — Tick-aware GDB tooling

- **Goal**: Raw DWARF poking becomes a workflow: tick-stepping, state
  pretty-printing, safety-event breakpoints.
- **Inputs**: scheduler's tick variable and task-dispatch function names;
  core firmware structs (BMS state, contactor state, DE/DTC table).
- **Deliverables**: a GDB Python package (`tools/gdb-sil/`) providing:
  - `step-tick [N]` — run to the end of the Nth next tick.
  - `run-to-tick N` — run until tick counter == N.
  - `break-on-de <id>` — break when diagnostic event <id> is set
    (watchpoint or hook on the DE-set function).
  - Pretty-printers for the core state structs (readable enums instead of
    raw ints; cell arrays summarized min/max/argmin).
  - `plant <param> <value>` — call the D2 binding API from inside GDB.
- **Acceptance criteria**: each command demonstrated in a scripted GDB
  session checked into the repo (`gdb -x demo_session.gdb` runs clean).
- **Gate / review**: creator uses the layer for one real debugging session
  and records missing commands as follow-ups.
- **Definition of done**: the demo session script runs green.

## D6 — Scenario scripts as a reproduction library

- **Goal**: Every debugged bug leaves behind a runnable reproducer:
  plant maneuver + fault injection + tick count + expected observation.
- **Why**: This is how the debug platform grows into a regression suite
  for free — one closed bug at a time — instead of building a suite up
  front. It also means "did the fix hold" is one command, forever.
- **Inputs**: D2 scenario API; D5 tooling.
- **Deliverables**:
  - `test/sil/repros/` directory, one script per closed bug, named after
    the ticket/issue id.
  - A 10-line template (setup / maneuver / observe) plus the discipline
    rule written into the SIL README: no bug is closed without its repro
    script landing here.
- **Acceptance criteria**: the next three bugs debugged on the platform
  each land a repro script that fails before the fix and passes after.
- **Gate / review**: none (process rule); reviewed at the next audit.
- **Definition of done**: directory exists, template exists, rule is in
  the README, first real repro landed.

## D7 — Arithmetic parity for flagged computations

- **Goal**: Values watched in a SIL debug session transfer to target —
  no false conclusions from double-vs-target-float divergence.
- **Why**: The audit found the integrator/accumulator typedef differs
  between SIL (hardware binary64) and target (soft-float double with
  different mantissa behavior), with divergence accumulating over
  45–200-minute soaks. On a debug platform the risk is subtle: you watch
  a value, conclude "this is fine," and the conclusion is false on target.
- **Inputs**: audit section 3 (arithmetic findings, file:line of the
  accumulator typedef).
- **Deliverables**:
  - Either the SIL typedef matched to target-faithful semantics (soft-
    float lib or explicit rounding), or — if that is disproportionate — a
    documented divergence bound: dual-run the accumulator against a
    target-faithful reference over the soak profile and record the max
    delta in the SIL README under "values that do not transfer."
  - DSYNC/barrier-dependent code paths listed in the same README section
    as "correctness untested in SIL" (they compile to no-ops here).
- **Acceptance criteria**: every arithmetic finding from audit section 3
  is either fixed or has a written, bounded caveat.
- **Gate / review**: cross-check against audit section 3 line by line.
- **Definition of done**: a debug-session reader can look up whether a
  watched value is target-faithful.

---

## Explicitly deferred (regression-suite economics — zero ROI while the
## SIL's job is interactive debugging)

Revisit when the platform's role expands to CI regression:

- Mutation/seeded-bug detection-rate baseline and re-measurement.
- Oracle-independence sweep (expected values from plant/SYSREQ/reference
  calc, never from the firmware variable or mock that produced the
  actual; fix the DWARF-vs-debug-CAN mirror compares).
- Faults-armed CI profile (re-arm the ~14 diagnostic events currently
  disarmed as session preconditions; run without pre-warmed NvM).
- Interleaving stress (seeded task-order permutation and frame-jitter
  within legal bounds; replayable by seed).

## Standing limitation (never fixable in this architecture)

A single-threaded SIL explores exactly one benign interleaving per boot.
Concurrency bugs (ISR preemption, cross-core races, TOCTOU on shared
channels) cannot reproduce here **by construction**. Operational
consequence for a debug platform: if a target bug will not reproduce in
SIL after D1+D2 are in place, that non-reproduction is itself a signal —
suspect timing/preemption and move the investigation to PIL/HIL instead
of spending more effort in SIL. Green fast-SIL remains a screen, not a
verification gate.
