# Self-Improvement Loop Protocol

The loop that keeps the harness getting better. It has no completion
condition: it ends only when the owner explicitly says "stop".

## The loop

```
1. RUN      fixed benchmark subset (harness/bench/run_subset.sh)
2. ANALYZE  every failure: read the trajectory, classify the cause
3. CHANGE   make exactly ONE harness change targeting the top cause
4. RE-RUN   the same subset
5. DECIDE   keep the change only if it does not regress; else revert
6. LOG      logs/iteration-NN.md + harness/CHANGELOG.md entry
7. goto 1
```

## Rules

- **One change per iteration.** A change is one coherent edit to the
  harness: a CLAUDE.md rule, a skill, a subagent, a tool config, a
  prompt fragment. Two changes at once make the measurement worthless.
- **Fixed subset.** The same tasks every iteration (chosen at S-CH-01).
  Every ~10 iterations, additionally run a held-out set of 10 different
  tasks to detect overfitting to the subset.
- **Variance-aware crediting.** An improvement smaller than the
  baseline's run-to-run variance band is "no change", not a win.
- **Cost is a first-class metric.** Track tokens and cost per task and
  per solved task. A change that raises accuracy but doubles
  cost-per-solve must say so in its log and CHANGELOG entry.
- **Failure taxonomy.** Classify each failure as one of: wrong-plan,
  wrong-edit, environment/tooling, timeout/budget, verifier-mismatch,
  gave-up-early, context-overflow. The taxonomy drives what to change
  next; extend it when a failure fits nothing.
- **Revert discipline.** A reverted change still gets its CHANGELOG
  entry (marked REVERTED) — negative results are knowledge.

## Change-idea backlog (evidence-based starting points)

Ranked by published impact — see docs/RESEARCH_NOTES.md for sources:

1. Reproduce-first rule: require a failing reproduction (test/script)
   before any fix edit.
2. Multi-attempt with test-based selection on hard tasks (best-of-N,
   reject candidates that break existing checks).
3. Plan/todo discipline: mandatory upfront plan the agent updates.
4. Context hygiene: compaction thresholds, keep windows clean, avoid
   dumping large files into context.
5. Edit-path error-proofing: prefer exact-match edits, lint after each
   edit batch, fail fast on broken syntax.
6. Budget tuning: generous turn limits (published solves take 100+
   turns); track termination reasons so caps stealing solves is
   visible.

## Iteration log template (`logs/iteration-NN.md`)

```markdown
# Iteration NN — <date>
change: <one sentence: what was changed, which file(s)>
hypothesis: <failure class targeted and why>
before: accuracy X/15, cost $Y, tokens Z, variance band ±V
after:  accuracy X/15, cost $Y, tokens Z
decision: KEPT | REVERTED — <one sentence why>
failures-remaining: <class: count, ...>
notes: <anything a cold reader needs>
```
