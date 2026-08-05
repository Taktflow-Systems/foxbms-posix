# parse-to-files idempotency demonstration (input class 2: pasted logs)

Validated 2026-08-02. Input: `input.txt` — a real bench console log
(ANSI-stripped `logs/runs/iter07-runH-console.log`; checked free of
private data). Method: the same input was processed by INDEPENDENT
cold agents (no shared context, separate target roots) each following
only `../SKILL.md`; idempotency = empty `diff -r` between their
output trees. This is a stronger test than re-running one process —
it proves the file set is a pure function of input + rules, with no
freedom left to the executor.

## Round 1 — runA vs runB: divergence found

File sets and layout identical
(`logs/undated-iter07-runh/{raw.txt,summary.md,01-agenttimeouterror.md}`;
class/date/slug all derived identically), but `diff -r` showed ONE
differing line: summary `result:` field — `15/15, Mean: 0.867` vs
`15/15, 0.867`. Root cause: the template said "headline numbers
verbatim" without stating whether a metric's printed label travels
with it.

## Fix (derivation, not instance)

SKILL.md result-field spec tightened: each headline metric is copied
WITH its label exactly as printed; unlabeled numbers are copied bare;
first-mention only. runA/runB kept as evidence of the divergence.

## Round 2 — runC vs runD: byte-identical

Two fresh independent cold agents under the tightened spec:
`diff -r runC runD` → empty, exit 0. All three files byte-identical,
including the previously ambiguous field (both now
`15/15, Mean: 0.867`). raw.txt verified byte-identical to the input
by both agents (`cmp`).

## Conclusion

Same input twice ⇒ same file set, demonstrated at byte level on input
class 2. Input class 1 (issue records) demonstration pending S-CH-04
samples.
