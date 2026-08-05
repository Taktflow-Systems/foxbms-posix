#!/usr/bin/env bash
# Held-out overfitting check (SELF_IMPROVEMENT_LOOP.md: every ~10
# iterations, run 10 tasks NOT in the fixed subset to detect
# overfitting of harness changes to the subset).
#
# Usage: ./run_heldout.sh <job-name> [template|notemplate] [extra harbor args...]
#   e.g. ./run_heldout.sh heldout-baseline notemplate
#        ./run_heldout.sh heldout-template template
#
# "notemplate" disables the harness prompt template so the same 10
# tasks can be measured under baseline behavior; comparing the two
# runs is what makes the overfitting check interpretable (a low
# template-only score cannot distinguish "template hurts" from
# "these tasks are just harder").
#
# The 10-task held-out set is FIXED (chosen once, 2026-08-02) and must
# not overlap the fixed 15-task subset in run_subset.sh. Selection
# mirrors the subset's W1-W5 coverage from the full 89-task TB2 list;
# GPU-dependent tasks excluded (laptop has no CUDA).
set -euo pipefail

JOB_NAME="${1:?usage: run_heldout.sh <job-name> [template|notemplate] [extra harbor args...]}"
TEMPLATE_MODE="${2:-template}"
shift || true
shift || true

# Fixed held-out set — DO NOT EDIT (disjoint from run_subset.sh SUBSET).
HELDOUT=(
  extract-moves-from-video   # W1: visual input -> structured output
  regex-log                  # W2: log parsing -> structured output
  count-dataset-tokens       # W2: aggregate computation (recount clause)
  filter-js-from-html        # W3: implement-from-spec
  cobol-modernization        # W3: legacy replica implementation
  build-pov-ray              # W4: legacy C/C++ build
  sqlite-with-gcov           # W4: instrumented build
  fix-git                    # W5: repo-state debugging/repair
  git-leak-recovery          # W5: destructive-risk recovery (backup clause)
  sqlite-db-truncate         # W5: data recovery
)

HARNESS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL="${SUBSET_MODEL:-claude-sonnet-5}"
CONCURRENCY="${SUBSET_CONCURRENCY:-3}"

# Fresh OAuth token every launch (host CLI rotates it ~8-hourly).
# No CLAUDE_FORCE_OAUTH — see run_subset.sh / logs/bench-baseline.md.
TOKEN="$(python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/.claude/.credentials.json')))['claudeAiOauth']['accessToken'])")"

INCLUDE_ARGS=()
for t in "${HELDOUT[@]}"; do INCLUDE_ARGS+=(-i "$t"); done

PROMPT_ARGS=()
PROMPT_FILE="$HARNESS_DIR/prompts/task-template.j2"
if [[ "$TEMPLATE_MODE" == "template" && -f "$PROMPT_FILE" ]]; then
  PROMPT_ARGS+=(--ak prompt_template_path="$PROMPT_FILE")
fi

export PATH="$HOME/.local/bin:$PATH"
cd "$HARNESS_DIR"

# Same launch-retry + trial-retry hardening as run_subset.sh (T03/T04).
for attempt in 1 2 3; do
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
