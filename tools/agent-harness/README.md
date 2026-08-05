# agent-harness — evidence-tuned Claude Code harness package

A portable snapshot of an agent-harness improvement effort: every
piece in here was landed as a single measured change and kept only if
it did not regress a fixed benchmark (Terminal-Bench 2.0, official
verifiers). Full change-by-change provenance is in `CHANGELOG.md`;
the measurement discipline that produced it is in
`docs/SELF_IMPROVEMENT_LOOP.md`.

Measured effect at packaging time (claude-sonnet-5, Claude Code CLI
2.1.220, Harbor 0.20.0): fixed 15-task TB2 subset from a 13-14/15
baseline band to a stable 14/15 ceiling (remaining miss is a chronic
timeout task); 10-task held-out set 6/10 -> 8/10. Scores are
machine- and version-specific — see "Porting caveats".

## Contents

| Path | What it is |
|---|---|
| `prompts/task-template.j2` | The core improvement: a Jinja2 wrapper (`{{ instruction }}` placeholder) adding earned rules to every task — time-budget discipline, requirements-beat-speed, work-in-designated-locations, backup-before-mutation, independent recomputation of aggregates, byte-preservation of provided inputs |
| `skills/sil-build/` | Skill: turn embedded firmware into a PC-hosted SIL build (boundary -> stub -> host build -> smoke). Pilot: Eclipse OpenBSW referenceApp, POSIX preset; `pilot/build.sh` auto-clones the public upstream pinned at the validated commit |
| `skills/sil-debug/` | Skill: reproduce-with-failing-test -> localize -> fix -> prove-with-same-test, plus a replayable injected-defect exercise (`exercises/ex01-truncated-can-payload/run_exercise.sh`) |
| `skills/parse-to-files/` | Skill: deterministic parse-anything-to-files (naming convention, folder rules, verbatim extraction templates), with a byte-level idempotency demo (two independent cold agents produced `diff -r`-identical trees) |
| `skills/issue-capture/`, `skills/replica/` | Skeletons (workflow slots W1/W3); content pending owner inputs in the origin workspace |
| `agents/claude_code_uvsafe.py` | Harbor agent subclass: best-effort uv/uvx pre-install during agent setup so verifiers survive network flakes |
| `bench/run_subset.sh` | One-command reproducible 15-task TB2 subset run (the regression gate) |
| `bench/run_heldout.sh` | 10-task overfitting check, with/without the template |
| `bench/dns-overlay.yaml` | Docker compose overlay pinning task-container DNS (kills a class of intermittent verifier-download failures) |
| `CHANGELOG.md` | Every change with its measurement and keep/revert verdict (T-prefixed = tooling; numbered = agent-behavior, one per iteration) |
| `docs/SELF_IMPROVEMENT_LOOP.md` | The loop methodology: run -> analyze failures -> one change -> re-run -> decide by the numbers -> log |

## Adopting on any machine

Two independent levels:

1. **Prompt + skills only (no benchmark needed).** Use the clauses of
   `prompts/task-template.j2` in a project `CLAUDE.md` or system
   prompt, and the `skills/*/SKILL.md` workflows as instructions for
   any Claude Code session. This is where the behavioral improvement
   lives; it has no infrastructure dependencies.
2. **Full benchmark rig.** Requirements: Linux with Docker,
   `harbor` (0.20.x) and `uv` on PATH, Claude Code CLI authenticated
   (the scripts read the OAuth token from the local CLI credentials
   file at launch; no secrets are stored in this package). Then:
   `bench/run_subset.sh <job-name>`. Results land under
   `logs/runs/<job-name>/` (git-ignored here).

## Porting caveats

- **Re-baseline before trusting any gate.** The 13-14 band was
  measured on one specific laptop/network/CLI-version/model. On new
  hardware — or after a CLI or model update — run two back-to-back
  subset runs to establish the local band before using scores for
  keep/revert decisions.
- Benchmark scores have run-to-run variance of at least +/-1 task;
  the changelog's keep/revert decisions were made with pre-committed
  rules to avoid rationalizing borderline results. Keep that
  discipline.
- `CHANGELOG.md` references iteration logs (`logs/iteration-NN.md`)
  from the origin workspace; those logs are not part of this package.
- The sil-build pilot compiles upstream Eclipse OpenBSW (Apache-2.0)
  fetched at build time; no third-party sources are vendored here.

## Sanitization note

This package contains no credentials, private IPs, usernames, home
paths, hardware serials, or private build hashes. The only commit
hash present pins the public upstream OpenBSW repository. Scripts
resolve user-specific data (OAuth token, home directory) at runtime
on the host they run on.
