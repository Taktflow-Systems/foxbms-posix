# CLAUDE.md — Working Agreement (tuned for Claude Opus 5, ASIL-relevant codebase)

This repository contains safety-relevant embedded software (AURIX TC3xx, ISO 26262
context) and its verification infrastructure (SIL platform, HIL/TRACE32 scripts).
Correct-looking-but-wrong output here is worse than no output. Every rule below
exists because of an observed failure mode — treat them as hard constraints, not
style preferences.

INTENT RULE: every prohibition in this file forbids the *outcome*, not just the
named method. "Do not modify X" means no path to X changing — not via scripts,
not via regeneration, not via a helper that rewrites it. If a task seems to
require violating an intent, stop and ask.

---

## 1. Plan gate — no writes before an approved plan

Before the FIRST tool call that modifies anything (edit, create, delete, git),
post a plan containing:

1. **Goal** restated in one sentence (so mismatches surface immediately).
2. **Files to touch** — explicit list. Anything not listed is out of scope.
3. **Files explicitly NOT touched** — name the nearby risky ones.
4. **Order of operations.**
5. **Done-criterion** — the exact command(s) that must pass (see §3).
6. **Assumptions** — anything the task description didn't specify that you
   are filling in. If an assumption affects safety-relevant behavior, it is
   not an assumption — it is a question. Ask it.

Wait for approval. Exceptions (no plan needed): read-only exploration, running
existing tests, single-file changes under ~10 lines that the operator asked
for verbatim.

Once approved, run the plan to completion without check-in pauses — but any
deviation from the approved file list re-triggers the gate.

## 2. Forbidden zones — never modify without an instruction naming the file

- Safety mechanism implementation code (SMU/ACC EN handling, fault reaction
  paths, `processFaults()` and its suppression-window logic).
- Generated code, NVM layouts, linker scripts, flash region manifests.
- HIL configs and TRACE32 `.cmm` scripts under test-infrastructure control.
- Test oracles / expected values: never change an expected value to make a
  test pass. An oracle change requires a cited source (requirement ID,
  datasheet section, or safety manual reference) in the same change.
- Never weaken, skip, `xfail`, or delete a failing test to get green.
- Never commit, push, rebase, or tag. Stage nothing. The operator commits.
- No dependency, toolchain, or build-config changes unless that IS the task.

## 3. Done = a command that passes. Nothing else counts.

A task is complete only when its done-criterion command exits 0. "The code
looks correct" is not a completion state.

Default done-criteria for this repo (plan may add, never remove):

- Build: `just build` (or the target the plan names)
- Fast SIL: `just sil-run <suite>` for any change touching fault handling
- Unit tests: the affected test target, run, output shown

If no executable check can exist for a change, say so explicitly in the plan
and mark the change UNVERIFIED-BY-EXECUTION in the final report.

**Concurrency / ISR / hardware-register carve-out:** for anything involving
interrupt context, shared state, register access order, or timing windows,
reasoning about the code is insufficient — these are documented model weak
spots. Execute a test or state plainly that the behavior was not executed.

## 4. Evidence and confidence discipline

Documented model failure: stating uncertain conclusions as certain.
Countermeasures, mandatory:

- Every claim about code behavior carries `file:line` or command output.
- Label conclusions: **VERIFIED** (executed, output shown), **INFERRED**
  (read the code, not executed), **ASSUMED** (neither). Never present
  INFERRED as VERIFIED.
- "Root cause" is a protected term: use it only after a reproduction
  demonstrates the mechanism. Before that, write "hypothesis".
- Never state SFR addresses, register bit meanings, or peripheral behavior
  from memory. Quote the header file or datasheet file in the repo. If it
  is not in the repo, say so and ask.
- If a search/read comes back empty, report "not found", not a guess.

## 5. Stop conditions — halt and report instead of pushing through

Stop, summarize state, and ask when ANY of these fire:

- The fix wants to touch a file outside the approved plan list.
- The change is growing past ~3 files or ~150 changed lines beyond plan.
- A test fails for a reason unrelated to the current task.
- Two consecutive attempts at the same sub-problem have failed. No third
  blind attempt — instead produce a diagnosis: what was tried, what the
  outputs showed, current best hypothesis, what evidence would decide it.
- The task turns out to need a forbidden-zone change (§2).
- Anything suggests the environment differs from what the plan assumed
  (missing tool, unexpected repo state, failing baseline before any change).

A stop is a success state. Grinding past a stop condition is the failure.

## 6. Scope hygiene

No drive-by refactors, no formatting sweeps, no "while I'm here" fixes, no
speculative generality. Anything worth fixing outside scope goes into a
`FOLLOWUP:` list at the end of the report — one line each — and is otherwise
left untouched.

## 7. Review and reporting style

- When asked to review code: report EVERYTHING found, tagged by severity.
  Do not self-filter to "important" findings — the operator filters.
- Final reports: diff summary, evidence per §4, done-criterion output,
  FOLLOWUP list. Concise — no narrative padding, no restating the diff in
  prose, no superlatives about the fix.
- Findings are posted once, with file:line. No re-arguing across turns.

## 8. Corrections log — LIVING SECTION

Any correction the operator makes twice gets a line here. Read this section
before every task; it outranks your instincts.

- TRACE32 SFR reads (SMU_AGC*, ACCEN*) on cold sessions: never plain `D:`
  access class under `SYStem.Option.DUALPORT ON` — use `ED:` or
  `CONVert.ADDRESSTODUALPORT()`. Bus-default values (0x00000000/0xFFFFFFFF)
  from a `D:` read are an access-routing artifact, not device state.
- Suppression-window logic in `processFaults()` has a known re-arming
  hazard class (ref BSBS-16676). Any change near it requires a Fast SIL run
  of the fault-injection suite, not just build + unit tests.
- Preprocessor variant gates (MultiString et al.) have silently excluded
  code from safety paths before (ref BSBS-16157). When touching guarded
  code, list which build variants compile it and which don't.
- (append here)

---

## Operator notes — for the human, not instructions to the model

- **Effort:** Opus 5's levels are recalibrated vs 4.8 — don't carry old
  settings. Default is high; use xhigh for exploratory debugging and hard
  multi-file work; low/medium are genuinely fine for mechanical edits.
  If it commits to bad paths early, check effort before blaming the prompt.
- **Keep thinking enabled.** Disabling it can leak tool calls as plain text
  that never execute and then poison later agentic turns.
- **Spec up front, then hands off.** This model is tuned for a complete
  task specification followed by an uninterrupted run. The plan gate in §1
  replaces mid-stream steering — invest the effort there, not in interrupts.
- **Don't add "double-check your work" instructions.** It self-verifies;
  redundant verification prompts cost tokens and add nothing.
- **Avoid conservative filter language** in prompts ("only report severe
  issues") — it is followed literally and suppresses recall. Ask for
  everything, filter afterward (§7 encodes this).
- **Model weak spots to compensate for in review:** logic errors, race
  conditions, API misuse. Pair its output with execution (§3) and, for
  correctness-critical diffs, a second reviewer — human or a separate
  verifier pass.
- Prune this file. A bloated CLAUDE.md dilutes itself; every rule that no
  longer earns its place weakens the ones that do.
