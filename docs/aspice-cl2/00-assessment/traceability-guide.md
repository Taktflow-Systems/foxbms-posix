# Traceability Guide

How to use `scripts/trace-gen.py` to generate and maintain the full V-model traceability matrix for the foxBMS POSIX vECU project.

| Field | Value |
|---|---|
| Document ID | TRACE-GUIDE-001 |
| Applicable Standards | ASPICE SWE.1-6, ISO 26262 Part 8 Clause 9 |
| Date | 2026-03-21 |
| Status | Released |

---

## 1. What It Does

`trace-gen.py` scans all requirement documents, source code, and test files to build a complete bidirectional traceability graph from stakeholder requirements down to test evidence. It:

1. **Parses 12 levels of requirement IDs** from markdown docs in `docs/aspice-cl2/`
2. **Scans source code** in `src/` for `@safety_req` and `@verifies` tags
3. **Builds a bidirectional graph** resolving all parent/child links
4. **Validates links** detecting broken references, orphans, untested leaf requirements, and asymmetric links
5. **Generates** `docs/aspice-cl2/00-assessment/traceability-matrix-generated.md`

No pip dependencies -- pure Python 3 stdlib.

## 2. How to Run

```bash
# Generate the traceability matrix (overwrites the existing file)
python scripts/trace-gen.py

# CI mode -- exit 1 if broken links or untested leaf requirements exist
python scripts/trace-gen.py --check

# Print summary statistics only (no file output)
python scripts/trace-gen.py --stats

# Output as machine-readable JSON
python scripts/trace-gen.py --json

# Custom output path
python scripts/trace-gen.py --output path/to/output.md
python scripts/trace-gen.py --json --output path/to/output.json
```

## 3. Requirement ID Scheme

The project uses the following requirement ID prefixes, organized in a V-model hierarchy:

| Level | ID Pattern | Example | Document Location |
|---|---|---|---|
| STKH-REQ | `STKH-REQ-NNN` | STKH-REQ-001 | `03-SYS.1-stakeholder-requirements/` |
| SYS-REQ | `SYS-REQ-NNN` | SYS-REQ-020 | `04-SYS.2-system-requirements/` |
| SG | `SG-NNN` | SG-001 | `18-safety/part3-concept/` |
| HZ | `HZ-NNN` | HZ-001 | `18-safety/part3-concept/` |
| FSR | `FSR-NNN` | FSR-01 | `18-safety/part4-system/` (FSC) |
| TSR | `TSR-NNN` | TSR-01 | `18-safety/part4-system/` (TSC) |
| SW-REQ | `SW-REQ-NNN` | SW-REQ-001 | `08-SWE.1-software-requirements/` |
| SSR | `SSR-NNN` | SSR-001 | `18-safety/part6-software/` |
| FM | `FM-NNN` | FM-01 | `18-safety/part5-hardware/` |
| UT | `UT-NNN` | UT-001 | `11-SWE.4-software-unit-verification/` |
| IT | `IT-NNN` | IT-001 | `12-SWE.5-software-integration-test/` |
| QT | `QT-NNN` | QT-001 | `13-SWE.6-software-qualification-test/` |

### 3.1 ID Normalization

The script normalizes all IDs to three-digit zero-padded format. These all refer to the same requirement:

- `SG-01` -> `SG-001`
- `SG-1` -> `SG-001`
- `SG-001` -> `SG-001`

### 3.2 Hierarchy

The requirement hierarchy follows the V-model with two parallel chains:

```
Functional chain:
  STKH-REQ --> SYS-REQ --> SW-REQ --> Code --> Tests (UT/IT/QT)

Safety chain:
  HZ --> SG --> FSR --> TSR --> SSR --> Code --> Tests (UT/IT/QT)
```

Both chains converge at the code and test levels. Every SW-REQ and SSR (leaf requirements) must have at least one test (UT, IT, or QT) verifying it.

## 4. How to Add Trace Tags

### 4.1 In Requirement Documents (Markdown Tables)

Most requirements are defined in markdown tables. The script parses these automatically.

**Table with "Derives From" column:**

```markdown
| ID | Requirement | Derives From | ASIL |
|---|---|---|---|
| SW-REQ-001 | The SOA module shall compare each cell voltage... | SYS-REQ-020 | D |
```

**Table with "Traces To" column:**

```markdown
| ID | Requirement | Stakeholder | Priority | Traces To |
|---|---|---|---|---|
| STKH-REQ-001 | The system shall build from source... | S3 | MUST | SYS-REQ-001 |
```

**Test table with requirement references:**

```markdown
| ID | Test Case | Module | Expected Result | Traces To |
|---|---|---|---|---|
| UT-001 | DIAG_Handler increments counter | diag.c | Counter increases | SW-REQ-031 |
```

### 4.2 In Requirement Documents (Inline Tags)

For documents using heading-based requirements (safety docs), add trace tags as bold fields:

```markdown
### TSR-01: Cell Overvoltage Detection and Reaction (FSR-01, ASIL D)

**Traces up**: FSR-01, SG-001
**Traces down**: SSR-001, SSR-020
```

The parenthetical reference in headings `(FSR-01, ASIL D)` is also parsed automatically.

### 4.3 In Source Code

Use comment tags to link code to requirements:

**`@safety_req` -- marks code that implements a safety requirement:**

```c
/**
 * @safety_req SSR-001
 * @safety_req SW-REQ-001
 * Checks cell voltage against overvoltage MSL threshold.
 */
void SOA_CheckVoltage(void) {
    // ...
}
```

**`@verifies` -- marks test code that verifies a requirement:**

```python
def test_overvoltage_msl():
    """
    @verifies SW-REQ-001
    @verifies SSR-001
    Inject cell voltage above 2800 mV and verify ERROR state.
    """
    # ...
```

### 4.4 Supported Tag Formats

| Tag | Where | Example |
|---|---|---|
| `@safety_req SSR-NNN` | C/Python source | Links code to a safety requirement |
| `@safety_req SW-REQ-NNN` | C/Python source | Links code to a software requirement |
| `@verifies SW-REQ-NNN` | Test files | Links test to a software requirement |
| `@verifies SYS-REQ-NNN` | Test files | Links test to a system requirement |
| `@verifies SSR-NNN` | Test files | Links test to a safety requirement |

## 5. How CI Validates Traceability

The GitHub Actions workflow (`.github/workflows/ci.yml`) runs the traceability check on every push and PR:

### 5.1 Traceability Job

```yaml
traceability:
  name: Traceability Check
  steps:
    - run: python scripts/trace-gen.py --check
```

The `--check` flag causes `trace-gen.py` to exit with code 1 if:

1. **Broken links exist** -- a requirement references an ID that is not defined in any document
2. **Untested leaf requirements exist** -- a SW-REQ or SSR has no UT, IT, or QT verifying it

The traceability job runs with `continue-on-error: true` so it reports status without blocking the build. The generated matrix is uploaded as a CI artifact for review.

### 5.2 PR Summary

The workflow posts a summary to the GitHub Actions step summary, showing:
- The level-by-level statistics table
- Counts of broken links and untested requirements
- A warning banner if issues are found

### 5.3 When the Check Fails

If `trace-gen.py --check` exits with code 1, review the generated `traceability-matrix-generated.md` artifact. It contains:

- **Broken Links** table: shows which document references a non-existent ID
- **Untested Requirements** table: shows which leaf requirements lack test coverage
- **Orphan Requirements** table: shows requirements with no parent and no child
- **Asymmetric Links** table: shows one-directional traces that should be bidirectional

## 6. How to Fix Issues

### 6.1 Broken Link

**Symptom**: `trace-gen.py` reports `SW-REQ-999` referenced in `SWE.4-unit-test-spec.md` but not defined.

**Fix**: Either:
- Add the missing requirement to the appropriate document
- Correct the typo in the reference (e.g., `SW-REQ-099` instead of `SW-REQ-999`)

### 6.2 Untested Leaf Requirement

**Symptom**: `SW-REQ-080` has no test verifying it.

**Fix**: Either:
- Add a test case to the appropriate test spec document (UT/IT/QT table)
- Add `@verifies SW-REQ-080` to an existing test in `src/`
- If the requirement is intentionally not tested in SIL (e.g., hardware-only), document the rationale

### 6.3 Orphan Requirement

**Symptom**: `SYS-REQ-050` has no parent stakeholder requirement and no child software requirement.

**Fix**: Either:
- Add a "Derives From" link in the system requirements document
- Add a "Traces To" link in the stakeholder requirements document
- If this is a derived requirement with no stakeholder origin, document that in the requirement itself

### 6.4 Asymmetric Link

**Symptom**: `SW-REQ-001` traces up to `SYS-REQ-020`, but `SYS-REQ-020` does not list `SW-REQ-001` as tracing down.

**Fix**: Add the reverse reference. In the system requirements document, ensure `SYS-REQ-020` has `SW-REQ-001` in its "Traces To" or downstream references. Alternatively, this is often acceptable because the script builds bidirectional links automatically from table columns -- asymmetric warnings usually indicate documents that use different linking conventions.

## 7. Output Format

The generated `traceability-matrix-generated.md` contains:

| Section | Content |
|---|---|
| Summary | Per-level statistics: defined, traced up, traced down, tested, coverage % |
| Forward Trace | STKH-REQ -> SYS-REQ -> SW-REQ -> SSR -> Code -> Test mapping |
| Safety Trace | HZ -> SG -> FSR -> TSR -> SSR -> Test mapping |
| Broken Links | References to undefined requirement IDs |
| Untested Requirements | Leaf requirements with no test coverage |
| Orphan Requirements | Requirements with no parent and no child |
| Asymmetric Links | One-directional traces |
| Source Code Tags | `@safety_req` and `@verifies` tags found in `src/` |

## 8. Relationship to ISO 26262 and ASPICE

| Standard | Clause | How trace-gen.py Satisfies It |
|---|---|---|
| ISO 26262-8 Clause 9 | Bidirectional traceability | Forward and backward trace tables |
| ASPICE SYS.2 BP5 | Bidirectional traceability | STKH-REQ <-> SYS-REQ links |
| ASPICE SWE.1 BP6 | Bidirectional traceability | SYS-REQ <-> SW-REQ links |
| ASPICE SWE.4 BP4 | Test to requirement traceability | UT -> SW-REQ links |
| ASPICE SWE.5 BP4 | Integration test traceability | IT -> SW-REQ links |
| ASPICE SWE.6 BP4 | Qualification test traceability | QT -> SYS-REQ links |

---
*End of Document*
