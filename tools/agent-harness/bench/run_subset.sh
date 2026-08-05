#!/usr/bin/env bash
# One-command repeatable Terminal-Bench 2.0 subset run (S-CH-01).
#
# Usage: ./run_subset.sh <job-name> [extra harbor args...]
#   e.g. ./run_subset.sh baseline-run1
#        ./run_subset.sh iter03-after --ak max_turns=200
#
# The 15-task subset is FIXED (chosen once at S-CH-01, 2026-08-02) and
# must be identical for every iteration so results are comparable.
# Selection rationale: docs/HARNESS_IMPROVEMENT_PLAN.md + logs/bench-baseline.md.
set -euo pipefail

JOB_NAME="${1:?usage: run_subset.sh <job-name> [extra harbor args...]}"
shift || true

# Fixed subset — DO NOT EDIT (W1..W5 coverage + 2 calibration anchors).
SUBSET=(
  code-from-image                  # W1: image -> code/issue capture
  log-summary-date-ranges          # W2: parse logs -> structured output
  multi-source-data-merger         # W2: merge unstructured sources to files
  financial-document-processor     # W2: document -> structured records
  make-mips-interpreter            # W3: replica implementation (ISA spec)
  schemelike-metacircular-eval     # W3: replica implementation (interpreter)
  write-compressor                 # W3: replica implementation (format spec)
  build-cython-ext                 # W4: native build wrangling
  build-pmars                      # W4: legacy C build
  extract-elf                      # W4: embedded binary analysis
  custom-memory-heap-crash         # W5: C memory-bug debugging
  db-wal-recovery                  # W5: recovery debugging
  fix-ocaml-gc                     # W5: hard runtime debugging
  gpt2-codegolf                    # anchor: known-fail at baseline (timeout)
  llm-inference-batching-scheduler # anchor: known-pass at baseline
)

HARNESS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL="${SUBSET_MODEL:-claude-sonnet-5}"
# Iteration 05 tried -n 2 (contention hypothesis): no benefit, ~2x
# wall-clock — reverted to 3. The real flake source was container DNS,
# fixed by the dns-overlay (change 007).
CONCURRENCY="${SUBSET_CONCURRENCY:-3}"

# Fresh OAuth token every launch (host CLI rotates it ~8-hourly).
# NOTE: no CLAUDE_FORCE_OAUTH here. It is unnecessary (no API key exists
# on this host, so the CLI falls back to the OAuth token on its own) and
# harmful: Harbor scrubs values of AUTH-matching env keys from trial
# artifacts, and the value "1" wiped every literal 1 from the
# baseline-run1/2 logs. See logs/bench-baseline.md.
TOKEN="$(python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/.claude/.credentials.json')))['claudeAiOauth']['accessToken'])")"

INCLUDE_ARGS=()
for t in "${SUBSET[@]}"; do INCLUDE_ARGS+=(-i "$t"); done

# Harness prompt template: if harness/prompts/task-template.j2 exists,
# every task instruction is rendered through it host-side (Jinja2,
# {{ instruction }} placeholder). Absent file = baseline behavior. The
# template file IS the measurable harness change.
# Do NOT use --ak append_system_prompt: Harbor inserts flag values into
# the shell command unquoted (build_cli_flags), so any multi-word value
# word-splits and corrupts the agent invocation (broke iter01-runA).
PROMPT_ARGS=()
PROMPT_FILE="$HARNESS_DIR/prompts/task-template.j2"
if [[ -f "$PROMPT_FILE" ]]; then
  PROMPT_ARGS+=(--ak prompt_template_path="$PROMPT_FILE")
fi

export PATH="$HOME/.local/bin:$PATH"
cd "$HARNESS_DIR"

# -r 1: one retry per trial on exceptions — container-network flakes
# (apt mirror, downloads.claude.ai, registry) killed trials in
# baseline-run1 and iter01-runA; a retry re-runs the trial cleanly and
# cannot change agent behavior within a trial (T03).
# Launch retry (T04): the registry fetch happens once at job start and
# intermittently fails ("Error getting dataset"); a failed launch kills
# the whole job before any trial runs, so retrying it is measurement-safe.
for attempt in 1 2 3; do
  # Custom agent (change 008): ClaudeCode + best-effort uv pre-install
  # so verifiers survive github.com download flakes.
  export PYTHONPATH="$HARNESS_DIR/agents${PYTHONPATH:+:$PYTHONPATH}"
  harbor run -d terminal-bench@2.0 -a claude_code_uvsafe:ClaudeCodeUvSafe -m "$MODEL" \
    "${INCLUDE_ARGS[@]}" \
    -n "$CONCURRENCY" -o logs/runs --job-name "$JOB_NAME" -r 1 \
    --extra-docker-compose "$HARNESS_DIR/bench/dns-overlay.yaml" \
    --ae CLAUDE_CODE_OAUTH_TOKEN="$TOKEN" \
    "${PROMPT_ARGS[@]}" \
    -y -q "$@" 2>&1 | tee "logs/runs/${JOB_NAME}-console.log"
  rc=${PIPESTATUS[0]}
  if [[ $rc -eq 0 || -f "logs/runs/$JOB_NAME/result.json" ]]; then
    exit $rc
  fi
  if ! grep -q "Error getting dataset" "logs/runs/${JOB_NAME}-console.log"; then
    exit $rc   # real failure, not the registry flake
  fi
  echo "registry flake on launch attempt $attempt; retrying in 5m" >&2
  sleep 300
done
exit 1
