---
name: parse-to-files
description: Convert unstructured input (issue records, pasted
  logs/transcripts, notes) into a deterministic set of well-named
  files. The rules leave zero naming freedom — the same input must
  always produce the byte-identical file set, no matter who or what
  applies the skill, or when.
---

# W2 — parse and save as files

Input: a blob of unstructured material plus a target root directory.
Output: a small tree of files whose names, layout, and content are a
pure function of the input. Idempotency is the acceptance test: apply
the skill twice to the same input and `diff -r` of the two outputs
must be empty.

## Determinism rules (these make or break the skill)

1. **No execution-time data.** Never use the current date/time, run
   counters, random IDs, hostnames, usernames, or absolute paths of
   the machine you happen to be on. Every name is derived from the
   input content only.
2. **Content date, not processing date.** Extract the date FROM the
   material (log timestamps, stated dates). Format `YYYY-MM-DD`. If
   the material spans dates, use the earliest. If no date exists in
   the content, use `undated` — do not substitute today.
3. **Slugs.** ASCII lowercase kebab-case, `[a-z0-9-]` only, max 40
   chars, derived by: take the source's own primary identifier (job
   name, ticket id, component name, first heading), lowercase,
   replace runs of non-alphanumerics with `-`, trim `-`, truncate.
   No creative renaming: if the input says `iter07-runH`, the slug is
   `iter07-runh`.
4. **Ordering.** Where multiple items need numbering, number by order
   of appearance in the input (`01`, `02`, …, zero-padded to 2). Slug
   collisions: keep both, suffix the later one `-2`, `-3`, … by
   appearance order.
5. **Verbatim raw copy.** Always save the original input unmodified
   (byte-preserved after ANSI-escape stripping, which is itself a
   deterministic transform) so no extraction error is ever lossy.
6. **Redaction is deterministic too.** If the target root is
   git-tracked or otherwise publishable, apply the standing
   private-data rules (IPs, usernames, emails, serials, absolute home
   paths → angle-bracket placeholders) as a pure text substitution,
   the same way every time, and state in the summary file that
   redaction was applied.
7. **Overwrite-identical only.** If the target files already exist
   with identical content, do nothing. If they exist with different
   content, stop and report — never silently clobber.

## Target-folder layout

```
<target-root>/<class>/<content-date>-<source-slug>/
    raw.txt                  # rule 5 verbatim copy
    summary.md               # what this input is, extracted key facts
    NN-<item-slug>.md        # one per extracted item, rule 4 ordering
```

`<class>` is one of:

- `issues/` — structured issue records (input class 1, produced by
  the issue-capture skill; schema follows S-CH-04).
- `logs/` — pasted console logs, tool transcripts, terminal captures
  (input class 2).
- `notes/` — everything else prose-like.

## Per-class extraction: `logs/`

For a pasted console/tool log, `summary.md` is EXACTLY this template —
same field order, one line per field, every value a verbatim token
copied from the input (no rephrasing, no unit conversion, no title
casing), `unknown` if genuinely absent, never guessed:

```
# <content-date>-<source-slug>

- source: <tool/product name as printed in the log>
- job: <run/job identifier verbatim>
- date: <content date(s) or undated>
- result: <each headline metric copied WITH its label exactly as printed (e.g. `Mean: 0.867`; a number printed without a label is copied bare), comma-separated, in order of first appearance, first-mention only>
- runtime: <duration verbatim>
- exceptions: <name xCount for each, in table order; or none>
- artifacts: <paths exactly as written in the log, comma-separated; or none>
- redaction: <none | applied>
```

Extracted items (`NN-<item-slug>.md`) for logs: one file per row of
an exception/error table (slug = the exception name lowercased per
rule 3), each containing exactly the fixed header
`# <exception-name>` followed by a fenced code block with the verbatim
log lines that mention it. Logs with no exceptions/errors produce
only `raw.txt` + `summary.md` — do not invent items.

## Per-class extraction: `issues/`

Input class 1 — waits on S-CH-04 (issue-capture) for its schema; the
folder rules and determinism rules above already apply unchanged.

## Workflow

1. Classify the input (`issues` / `logs` / `notes`) — by content, not
   by how it was delivered.
2. Extract content date + source slug (rules 2-3). State them before
   writing anything.
3. Write `raw.txt`, then `summary.md`, then item files (rule 4).
4. Self-check idempotency: re-derive every path from the input a
   second time and confirm no name depended on anything outside the
   input. If any did, fix the derivation, not the instance.

## Demonstrations

- `demo/` — validated idempotency demonstration on input class 2
  (real bench console log): the same input was processed twice by two
  independent cold agents into separate roots; `diff -r` empty. See
  `demo/DEMO.md` and `logs/iteration-13.md`.
- Input class 1 demonstration: pending S-CH-04 samples.
