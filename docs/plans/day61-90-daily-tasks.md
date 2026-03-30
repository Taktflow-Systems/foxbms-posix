# Day 61–90 Daily Task Breakdown — foxBMS POSIX AI Implementation

**Date**: 2026-03-27
**Phase**: Phase 3 — Production Hardening
**Parent plan**: [`plan-ai-180-day.md`](plan-ai-180-day.md)
**Prerequisite**: Phase 2 exit criteria met — SOC RMSE < 3 %, anomaly retrained on real SIL data,
dT/dt live, OCV table validated. See `baseline-metrics-phase2.md`.

**Focus**: Three parallel workstreams, one per week-pair:

| Workstream | Days | Deliverable |
|---|---|---|
| **SIL Validation Framework** | 61–67 | Automated end-to-end validation harness; evidence report |
| **CAN Interface Hardening** | 68–74 | DBC coverage; frame-timing tests; fault-response latency |
| **Monitoring Dashboard** | 75–81 | 10 new metrics; export API; session evidence capture |
| **Drift Monitoring + CI Gates + Phase 3 Close** | 82–90 | PSI monitor; all CI gates strict; Phase 3 merged |

**No model weights are changed in Phase 3.** Accuracy improvement belongs to Phase 2.
Phase 3 is about making the system *observable*, *testable*, and *provably stable*.

---

## Reading This Document

Each day entry contains:
- **Task** — what to build or run
- **Actions** — numbered steps, with concrete commands or code fragments
- **Deliverable** — the exact file, metric, or service that must exist when the day is done
- **Acceptance criteria** — the exit condition; do not proceed until it passes
- **Repo** — `foxbms-posix` (vECU + docs) or `taktflow-bms-ml` (models, training scripts)
- **ASPICE** — process area(s) and base practice(s) satisfied

**Blocker policy**: if a day's acceptance criteria are not met, add a note in
`docs/project/ml-changelog.md`, diagnose root cause, and re-attempt the same day
before advancing. Never mark a day complete on partial evidence.

---

## Phase 3 Entry Gate (Run Before Day 61)

All items below must pass before starting Day 61 work.

| # | Check | Command | Pass Condition |
|---|---|---|---|
| 3-A | Phase 2 tag present | `git tag -l \| grep v2` | `v2.0.0` or higher exists |
| 3-B | SOC RMSE < 3 % on BMW i3 test | `pytest tests/test_ml_accuracy.py::test_soc_rmse_gate` | Exit 0 |
| 3-C | Anomaly retrained on real SIL data | `jq '.training_source' models/bms/isolation_forest_registry.json` | `"sil_real"` |
| 3-D | dT/dt non-zero during discharge | `pytest tests/test_thermal_cnn_phase2.py::test_dTdt_nonzero_during_discharge` | Exit 0 |
| 3-E | Phase 3 branch created | `git branch -r \| grep feat/ai-phase3` | Branch present |
| 3-F | `docs/evidence/` directory exists | `ls docs/evidence/` | Directory present |

---

## Week 7 (Day 61–67): SIL Validation Framework

**Goal**: Replace ad-hoc manual demo runs with a reproducible, automated validation harness.
Every ML accuracy claim must be backed by a captured CAN log and a deterministic test report.
By end of Week 7, running `make sil-validate` produces a timestamped evidence package
that satisfies SWE.5 and SWE.6 exit criteria.

**Milestone**: M3.1 — SIL validation CI job green; evidence report committed.

---

### Day 61 — Phase 3 Branch + Evidence Directory Scaffold

**Task**: Set up the Phase 3 working environment and create the directory structure for
all evidence artifacts produced in Days 61–90.

**Actions**:

1. Create the Phase 3 feature branch from the Phase 2 merge commit:

```bash
git checkout main && git pull
git checkout -b feat/ai-phase3-hardening
git push -u origin feat/ai-phase3-hardening
```

2. Scaffold the evidence directory:

```bash
mkdir -p docs/evidence/sil-validation \
         docs/evidence/can-interface \
         docs/evidence/dashboard \
         docs/evidence/drift
touch docs/evidence/sil-validation/.gitkeep \
      docs/evidence/can-interface/.gitkeep \
      docs/evidence/dashboard/.gitkeep \
      docs/evidence/drift/.gitkeep
```

3. Create `docs/evidence/phase3-index.md` — a living index that lists every evidence
   artifact produced during Phase 3, the test that generated it, and the ASPICE BP it covers.
   Template:

```markdown
# Phase 3 Evidence Index

| Date | Artifact | Generating Test | ASPICE BP | Status |
|---|---|---|---|---|
| [fill] | sil-validation/sil-validation-phase3.md | run_sil_validation.py | SWE.6.BP3 | PENDING |
```

4. Add a `Makefile` target (or extend existing) to run the full Phase 3 validation suite:

```makefile
.PHONY: sil-validate
sil-validate:
	python3 scripts/run_sil_validation.py --output docs/evidence/sil-validation/
```

5. Commit the scaffold:

```bash
git add docs/evidence/ Makefile
git commit -m "chore(phase3): scaffold evidence directory and sil-validate Makefile target"
```

**Deliverable**: `docs/evidence/phase3-index.md` committed; `make sil-validate` exists (exits 1
with "not yet implemented" until Day 62).

**Acceptance criteria**:
- `ls docs/evidence/` shows 4 subdirectories + `phase3-index.md`
- `git log --oneline -1` contains `chore(phase3): scaffold`
- Feature branch pushed to remote

**Repo**: `foxbms-posix`

**ASPICE**: MAN.3.BP1 (project plan updated with Phase 3 work items).
SUP.8.BP1 (configuration items identified: evidence artifacts under version control).

---

### Day 62 — SIL Validation Harness (`run_sil_validation.py`)

**Task**: Write `scripts/run_sil_validation.py` — a Python orchestrator that:
(a) starts the vECU + plant + sidecar as subprocesses,
(b) waits for BMS state NORMAL (polls CAN 0x220),
(c) captures CAN frames for a configurable window (default 300 s),
(d) runs offline accuracy checks against the capture,
(e) writes a timestamped JSON result to `docs/evidence/sil-validation/`.

**Actions**:

1. Write `scripts/run_sil_validation.py`. Core structure:

```python
#!/usr/bin/env python3
"""SIL Validation Harness — Phase 3.
Runs vECU + plant + sidecar; captures 300 s of CAN; checks ML accuracy gates.
"""
import subprocess, time, json, pathlib, datetime, argparse, sys

CAPTURE_DURATION_S = 300
BMS_STATE_NORMAL   = 4  # 0x220 byte 0
GATE_SOC_DELTA_PCT = 5.0   # |ML_SOC - BMS_SOC| mean must be < 5 %
GATE_ANOMALY_NORMAL_MAX = 0.15  # mean anomaly score during normal ops

def wait_for_normal(timeout_s=60) -> bool:
    """Poll candump vcan1,220:7FF until BMS state == NORMAL."""
    deadline = time.time() + timeout_s
    proc = subprocess.Popen(["candump", "vcan1,220:7FF", "-L"],
                             stdout=subprocess.PIPE, text=True)
    try:
        for line in proc.stdout:
            if time.time() > deadline:
                return False
            # candump line: "(ts) vcan1 220#XXYYZZ..."
            parts = line.strip().split()
            if len(parts) >= 3 and "220#" in parts[2]:
                data_hex = parts[2].split("#")[1]
                state = int(data_hex[0:2], 16)
                if state == BMS_STATE_NORMAL:
                    return True
    finally:
        proc.terminate()
    return False

def run(output_dir: pathlib.Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    log_path = output_dir / f"sil_capture_{ts}.log"
    result = {"timestamp": ts, "gates": {}, "passed": False}

    print(f"[SIL-VAL] Waiting for BMS NORMAL state ...")
    if not wait_for_normal(timeout_s=90):
        result["error"] = "BMS did not reach NORMAL within 90 s"
        (output_dir / f"sil_result_{ts}.json").write_text(json.dumps(result, indent=2))
        sys.exit(1)

    print(f"[SIL-VAL] Capturing {CAPTURE_DURATION_S} s → {log_path}")
    with open(log_path, "w") as f:
        proc = subprocess.Popen(["candump", "-L", "vcan1"], stdout=f)
        time.sleep(CAPTURE_DURATION_S)
        proc.terminate()

    # Offline analysis
    from scripts.analyse_sil_capture import (
        check_soc_delta, check_anomaly_score_normal
    )
    result["gates"]["soc_delta_mean_pct"] = check_soc_delta(log_path)
    result["gates"]["anomaly_score_mean"]  = check_anomaly_score_normal(log_path)
    result["passed"] = (
        result["gates"]["soc_delta_mean_pct"] < GATE_SOC_DELTA_PCT and
        result["gates"]["anomaly_score_mean"] < GATE_ANOMALY_NORMAL_MAX
    )

    out_path = output_dir / f"sil_result_{ts}.json"
    out_path.write_text(json.dumps(result, indent=2))
    print(f"[SIL-VAL] {'PASS' if result['passed'] else 'FAIL'} → {out_path}")
    sys.exit(0 if result["passed"] else 1)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="docs/evidence/sil-validation/")
    args = ap.parse_args()
    run(pathlib.Path(args.output))
```

2. Write `scripts/analyse_sil_capture.py` with `check_soc_delta(log_path)` and
   `check_anomaly_score_normal(log_path)`. Both parse candump log format, decode CAN frames
   using constants from `tools/foxbms_constants.py`, and return float metrics.

3. Smoke-test with a manual run (vECU must already be running):

```bash
python3 scripts/run_sil_validation.py --output /tmp/sil-test/
```

**Deliverable**:
- `scripts/run_sil_validation.py`
- `scripts/analyse_sil_capture.py`

**Acceptance criteria**:
- Script runs to completion without Python exceptions on a live SIL session
- `/tmp/sil-test/sil_result_*.json` contains `"timestamp"`, `"gates"`, `"passed"` keys
- `soc_delta_mean_pct` and `anomaly_score_mean` are floats (not `null`)

**Repo**: `foxbms-posix`

**ASPICE**: SWE.5.BP1 (integration test specification — harness defines what is integrated and
how it is exercised). SWE.6.BP1 (software qualification test specification — captures
end-to-end acceptance criteria for ML subsystem).

---

### Day 63 — SIL Validation pytest Suite

**Task**: Convert the JSON gates from Day 62 into a `pytest` test module so that
`make sil-validate` is CI-runnable and failures produce machine-readable JUnit XML.

**Actions**:

1. Write `tests/test_sil_validation.py`:

```python
"""Phase 3 SIL validation test suite.
These tests require a running SIL session (vECU + plant + sidecar on vcan1).
Mark: sil — skipped in standard CI, executed in nightly SIL CI job.
"""
import pytest, json, pathlib, subprocess, time

pytestmark = pytest.mark.sil  # skip unless --run-sil passed

EVIDENCE_DIR = pathlib.Path("docs/evidence/sil-validation")

@pytest.fixture(scope="session")
def sil_result(tmp_path_factory):
    out = tmp_path_factory.mktemp("sil")
    ret = subprocess.run(
        ["python3", "scripts/run_sil_validation.py", "--output", str(out)],
        timeout=450
    )
    results = sorted(out.glob("sil_result_*.json"))
    assert results, "run_sil_validation.py produced no result JSON"
    return json.loads(results[-1].read_text())

def test_sil_validation_overall_pass(sil_result):
    assert sil_result["passed"], (
        f"SIL validation FAILED — gates: {sil_result['gates']}"
    )

def test_soc_delta_gate(sil_result):
    delta = sil_result["gates"]["soc_delta_mean_pct"]
    assert delta < 5.0, f"ML SOC delta {delta:.2f} % >= 5.0 % gate"

def test_anomaly_score_normal_gate(sil_result):
    score = sil_result["gates"]["anomaly_score_mean"]
    assert score < 0.15, f"Anomaly score {score:.3f} >= 0.15 gate during normal ops"

def test_evidence_file_committed():
    """Verify at least one prior SIL result is committed to the evidence directory."""
    committed = list(EVIDENCE_DIR.glob("sil_result_*.json"))
    assert committed, (
        f"No SIL result JSON found in {EVIDENCE_DIR}. "
        "Run 'make sil-validate' and commit the output."
    )
```

2. Add `sil` marker to `pytest.ini`:

```ini
[pytest]
markers =
    sil: requires running SIL session (vECU + plant + sidecar)
```

3. Add nightly SIL CI job stub in `.github/workflows/sil-nightly.yml`:

```yaml
name: SIL Nightly Validation
on:
  schedule:
    - cron: '0 2 * * *'   # 02:00 UTC daily
  workflow_dispatch:
jobs:
  sil-validate:
    runs-on: [self-hosted, sil-runner]
    steps:
      - uses: actions/checkout@v4
      - run: python3 scripts/run_sil_validation.py --output docs/evidence/sil-validation/
      - uses: actions/upload-artifact@v4
        with:
          name: sil-evidence-${{ github.run_id }}
          path: docs/evidence/sil-validation/
```

**Deliverable**:
- `tests/test_sil_validation.py`
- `.github/workflows/sil-nightly.yml`
- `pytest.ini` updated with `sil` marker

**Acceptance criteria**:
- `pytest tests/test_sil_validation.py -v` (without `--run-sil`) skips all 4 tests with
  `pytest.mark.sil` reason (not errors)
- `pytest.ini` contains `sil:` marker definition
- CI YAML parses without syntax error: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/sil-nightly.yml'))"`

**Repo**: `foxbms-posix`

**ASPICE**: SWE.5.BP3 (integration test execution — test cases run and results recorded).
SWE.6.BP3 (software qualification test execution). SUP.8.BP6 (test artifacts committed
and versioned).

---

### Day 64 — Automated Fault-Injection SIL Scenarios

**Task**: Extend the validation harness to cover the 5 fault-injection scenarios defined in
`docs/test/fault-injection-test-matrix.md`. For each fault type, measure the ML anomaly
score rise time (time from fault onset to score > 0.3).

**Actions**:

1. Write `scripts/sil_fault_matrix.py`. Iterates over fault scenarios, injects via
   the dashboard WebSocket API (`POST /api/inject_fault`), captures CAN 0x705 for 60 s,
   and records `{fault_type, injection_ts, detection_ts, latency_s, peak_score}`:

```python
FAULT_SCENARIOS = [
    {"type": "overvoltage",    "cell": 0,  "value_mv": 4600},
    {"type": "undervoltage",   "cell": 5,  "value_mv": 2600},
    {"type": "overcurrent",    "value_ma": 120000},
    {"type": "overtemperature","value_dc": 600},   # deci-°C
    {"type": "open_wire",      "cell": 9},
]
DETECTION_THRESHOLD = 0.30
CAPTURE_WINDOW_S    = 60
```

2. For each scenario:
   - Inject fault via `requests.post("http://localhost:8765/api/inject_fault", json=scenario)`
   - Start candump capture on `vcan1,705:7FF`
   - Parse 0x705 frames: `score = data[0] / 255.0`
   - Record first frame where `score > DETECTION_THRESHOLD` as `detection_ts`
   - Write result to `docs/evidence/sil-validation/fault_matrix_results.json`

3. Add a pytest test wrapping the fault matrix:

```python
# tests/test_sil_fault_matrix.py
@pytest.mark.sil
@pytest.mark.parametrize("fault_type,max_latency_s", [
    ("overvoltage",     10.0),
    ("undervoltage",    10.0),
    ("overcurrent",     10.0),
    ("overtemperature", 30.0),
    ("open_wire",       15.0),
])
def test_fault_detection_latency(sil_fault_results, fault_type, max_latency_s):
    r = sil_fault_results[fault_type]
    assert r["detected"], f"{fault_type}: anomaly score never exceeded 0.30 in {CAPTURE_WINDOW_S}s"
    assert r["latency_s"] <= max_latency_s, (
        f"{fault_type}: detection latency {r['latency_s']:.1f}s > {max_latency_s}s gate"
    )
```

**Deliverable**:
- `scripts/sil_fault_matrix.py`
- `tests/test_sil_fault_matrix.py`
- `docs/evidence/sil-validation/fault_matrix_results.json` (from a manual run)

**Acceptance criteria**:
- `python3 scripts/sil_fault_matrix.py` completes all 5 scenarios without Python exceptions
- `fault_matrix_results.json` has 5 keys, each with `detected`, `latency_s`, `peak_score`
- At minimum overvoltage and overcurrent scenarios report `"detected": true`
  (open-wire and thermal may not yet detect depending on Phase 2 model state — document
  in `docs/project/ml-changelog.md` if not detected; do not mark as failure)

**Repo**: `foxbms-posix`

**ASPICE**: SYS.4.BP1 (system integration test — fault injection tests the ML subsystem
integrated with the vECU fault reactions). SWE.6.BP5 (regression test — latency gates
prevent silent degradation in future phases).

---

### Day 65 — SIL Evidence Report Generator

**Task**: Write `scripts/gen_sil_evidence.py` — reads the JSON outputs from Days 62 and 64
and renders a markdown evidence report at `docs/evidence/sil-validation/sil-validation-phase3.md`.
This document is the ASPICE SWE.6 test report artifact.

**Actions**:

1. Write `scripts/gen_sil_evidence.py`:

```python
#!/usr/bin/env python3
"""Generate SIL validation evidence report from JSON results.
Output: docs/evidence/sil-validation/sil-validation-phase3.md
"""
import json, pathlib, datetime, sys

REPORT_PATH = pathlib.Path("docs/evidence/sil-validation/sil-validation-phase3.md")

def load_latest(glob_pattern: str) -> dict:
    files = sorted(pathlib.Path("docs/evidence/sil-validation").glob(glob_pattern))
    if not files:
        return {}
    return json.loads(files[-1].read_text())

def render(sil: dict, faults: dict) -> str:
    now = datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    lines = [
        "# SIL Validation Evidence Report — Phase 3",
        f"\n**Generated**: {now}  ",
        f"**SIL result**: {'PASS ✓' if sil.get('passed') else 'FAIL ✗'}  ",
        "\n---\n",
        "## 1. Accuracy Gates\n",
        "| Gate | Threshold | Measured | Result |",
        "|---|---|---|---|",
    ]
    g = sil.get("gates", {})
    lines.append(f"| ML SOC delta mean | < 5.0 % | {g.get('soc_delta_mean_pct', 'N/A'):.2f} % | {'PASS' if g.get('soc_delta_mean_pct', 99) < 5.0 else 'FAIL'} |")
    lines.append(f"| Anomaly score (normal) | < 0.15 | {g.get('anomaly_score_mean', 'N/A'):.3f} | {'PASS' if g.get('anomaly_score_mean', 1) < 0.15 else 'FAIL'} |")
    lines += [
        "\n## 2. Fault Detection Latency\n",
        "| Fault Type | Threshold (s) | Measured (s) | Detected | Result |",
        "|---|---|---|---|---|",
    ]
    THRESHOLDS = {"overvoltage": 10, "undervoltage": 10, "overcurrent": 10, "overtemperature": 30, "open_wire": 15}
    for ft, thr in THRESHOLDS.items():
        r = faults.get(ft, {})
        lat = r.get("latency_s", "—")
        det = r.get("detected", False)
        meas = f"{lat:.1f}" if isinstance(lat, float) else str(lat)
        res = "PASS" if det and isinstance(lat, float) and lat <= thr else ("NOT DETECTED" if not det else "FAIL")
        lines.append(f"| {ft} | {thr} | {meas} | {'Yes' if det else 'No'} | {res} |")
    lines += ["\n---\n", "_Generated by scripts/gen_sil_evidence.py — do not edit manually._\n"]
    return "\n".join(lines)

if __name__ == "__main__":
    sil    = load_latest("sil_result_*.json")
    faults = load_latest("fault_matrix_results.json")
    report = render(sil, faults)
    REPORT_PATH.write_text(report)
    print(f"Written: {REPORT_PATH}")
```

2. Run the generator and commit the output:

```bash
python3 scripts/gen_sil_evidence.py
git add docs/evidence/sil-validation/sil-validation-phase3.md
git commit -m "docs(sil): add Phase 3 SIL validation evidence report"
```

3. Update `docs/evidence/phase3-index.md` to mark the row as `GENERATED`.

**Deliverable**:
- `scripts/gen_sil_evidence.py`
- `docs/evidence/sil-validation/sil-validation-phase3.md` (committed)

**Acceptance criteria**:
- Report file is valid markdown: `python3 -c "import pathlib; c=pathlib.Path('docs/evidence/sil-validation/sil-validation-phase3.md').read_text(); assert '## 1. Accuracy Gates' in c"`
- Table rows for all 5 fault types are present
- `phase3-index.md` row status updated to `GENERATED`

**Repo**: `foxbms-posix`

**ASPICE**: SWE.6.BP4 (software qualification test report — evidence document created and
version-controlled). SUP.1.BP4 (quality records — report committed under CM).

---

### Day 66 — Baseline SIL Validation Run (Evidence Capture)

**Task**: Run the full validation suite against the production SIL session and commit the
captured evidence. This is the first formally evidenced validation run for Phase 3.

**Actions**:

1. Start a fresh SIL session:

```bash
# Terminal 1: start vECU (foxbms binary)
./build/foxbms_posix &

# Terminal 2: start plant model
python3 src/plant_model.py

# Terminal 3: start ML sidecar
python3 src/ml_sidecar.py
```

2. Wait 60 s for BMS state NORMAL. Verify: `candump vcan1,220:7FF | head -3`

3. Run the full validation harness:

```bash
make sil-validate
```

4. Run the fault matrix:

```bash
python3 scripts/sil_fault_matrix.py
```

5. Generate the evidence report:

```bash
python3 scripts/gen_sil_evidence.py
```

6. If the overall gate passes (`"passed": true`), commit all evidence artifacts:

```bash
git add docs/evidence/sil-validation/
git commit -m "evidence(sil): Phase 3 baseline SIL validation run — $(date +%Y-%m-%d)"
```

7. If the gate fails: add a blocker note in `docs/project/ml-changelog.md` with the
   failing gate values and root cause. Re-attempt on Day 67 before the M3.1 review.

**Deliverable**:
- `docs/evidence/sil-validation/sil_capture_<ts>.log` (candump log, ≥ 300 s)
- `docs/evidence/sil-validation/sil_result_<ts>.json` (`"passed": true`)
- `docs/evidence/sil-validation/fault_matrix_results.json` (all 5 scenarios)
- `docs/evidence/sil-validation/sil-validation-phase3.md` (rendered report)

**Acceptance criteria**:
- `jq '.passed' docs/evidence/sil-validation/sil_result_*.json | tail -1` returns `true`
- Commit exists with message matching `evidence(sil): Phase 3 baseline`
- Report contains at least 2 `PASS` rows in the accuracy gates table

**Repo**: `foxbms-posix`

**ASPICE**: SWE.6.BP3 (software qualification test execution — test run performed and
results committed). SYS.5.BP1 (system qualification test — ML subsystem validated at
system level in SIL environment).

---

### Day 67 — M3.1 Gate Review

**Task**: Review the Week 7 deliverables against the M3.1 milestone criteria. Update
`docs/aspice-cl2/01-MAN.3-project-management/project-plan.md` with Phase 3 Week 1 status.

**Actions**:

1. Run the M3.1 checklist:

| # | Criterion | Command | Pass |
|---|---|---|---|
| M3.1-A | SIL harness exits 0 | `make sil-validate` | `"passed": true` |
| M3.1-B | All 5 fault scenarios in results | `jq 'keys \| length' fault_matrix_results.json` | `5` |
| M3.1-C | Evidence report committed | `git log --oneline docs/evidence/sil-validation/` | ≥ 1 commit |
| M3.1-D | pytest suite (sans sil marker) passes | `pytest tests/ -v -m "not sil"` | 0 failures |
| M3.1-E | Nightly CI YAML valid | `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/sil-nightly.yml'))"` | No error |

2. For any criterion that fails: add it to `docs/project/ml-changelog.md` as a blocker.
   Resolve before starting Week 8.

3. Update project plan milestone table: set M3.1 status to `ACHIEVED` and record the
   date and git SHA.

4. Commit the updated project plan:

```bash
git add docs/aspice-cl2/01-MAN.3-project-management/project-plan.md
git commit -m "docs(aspice): M3.1 achieved — SIL validation framework complete"
```

**Deliverable**: M3.1 row in project plan updated to `ACHIEVED`.

**Acceptance criteria**:
- All 5 M3.1 criteria pass
- Project plan commit exists

**Repo**: `foxbms-posix`

**ASPICE**: MAN.3.BP4 (project monitoring — milestone review performed and documented).
MAN.3.BP6 (project review — evidence collected and milestone status updated).

---

## Week 8 (Day 68–74): CAN Interface Hardening

**Goal**: Every ML CAN message (0x700–0x705) is formally specified in a DBC file,
tested for encoding correctness, and validated for timing compliance during SIL.
No frame shall go missing for > 2 s during normal operation. By end of Week 8,
`pytest tests/test_can_ml_frames.py` covers all 6 ML frames and passes in CI.

**Milestone**: M3.2 — CAN integration test suite passes; DBC committed.

---

### Day 68 — CAN Signal Completeness Audit

**Task**: Capture a 60-second SIL CAN trace and verify that all 6 ML frame IDs
(0x700–0x705) are present. Document any missing IDs as blockers.

**Actions**:

1. Capture 60 s of live CAN (vECU + plant + sidecar running):

```bash
candump -L vcan1 | timeout 60 tee docs/evidence/can-interface/can_audit_$(date +%Y%m%d).log
```

2. Check which ML frame IDs appear:

```bash
# Extract unique CAN IDs from the capture
awk '{print $3}' docs/evidence/can-interface/can_audit_*.log \
  | cut -d'#' -f1 | sort | uniq -c | sort -rn > docs/evidence/can-interface/can_id_histogram.txt

# Check specifically for ML frames
for id in 700 701 702 703 704 705; do
    count=$(grep -c "^${id}#\|vcan1 ${id}#" docs/evidence/can-interface/can_audit_*.log 2>/dev/null || echo 0)
    printf "0x%s: %d frames\n" "$id" "$count"
done
```

3. Check which BMS states trigger each ML frame. Log state-frame co-occurrence
   (script `scripts/check_ml_frame_presence.py`).

4. Document findings in `docs/evidence/can-interface/can-signal-audit.md`:
   - Frame present / absent per ID
   - Approximate publish rate (frames/min)
   - BMS states during which the frame appeared

**Deliverable**:
- `docs/evidence/can-interface/can_id_histogram.txt`
- `docs/evidence/can-interface/can-signal-audit.md`

**Acceptance criteria**:
- IDs 0x700, 0x702, 0x705 present with ≥ 50 frames each in 60 s (≥ 0.8 Hz)
- Audit document states which IDs are absent (expected: 0x704 RUL = NOT DEPLOYED)
- `can-signal-audit.md` committed

**Repo**: `foxbms-posix`

**ASPICE**: SWE.5.BP1 (integration test specification — CAN interface completeness defined
as an integration test criterion). SUP.9.BP1 (problem resolution — absent or under-rate
frames recorded as problems).

---

### Day 69 — ML CAN Frame Timing Analysis

**Task**: Measure the actual publish interval and jitter for each live ML CAN frame.
The sidecar inference loop targets 1 Hz; measure whether it achieves this and whether
jitter exceeds 200 ms (which would break downstream monitoring).

**Actions**:

1. Write `scripts/measure_can_timing.py`:

```python
"""Measure inter-frame intervals for ML CAN messages.
Usage: python3 scripts/measure_can_timing.py <candump_log> [--ids 700 701 702 ...]
"""
import argparse, pathlib, statistics, collections

def parse_log(path):
    """Yield (timestamp_s, can_id_hex, data_hex) from candump -L log."""
    for line in pathlib.Path(path).read_text().splitlines():
        parts = line.strip().split()
        if len(parts) < 3:
            continue
        ts = float(parts[0].strip("()"))
        frame = parts[2]
        if "#" not in frame:
            continue
        cid, data = frame.split("#", 1)
        yield ts, cid.upper(), data

def analyse(log_path, target_ids):
    frames = collections.defaultdict(list)
    for ts, cid, _ in parse_log(log_path):
        if cid in target_ids:
            frames[cid].append(ts)
    print(f"\n{'ID':<8} {'Count':>6} {'Mean_ms':>9} {'Std_ms':>8} {'Max_ms':>8} {'≤1200ms%':>9}")
    for cid in sorted(target_ids):
        ts_list = frames.get(cid, [])
        if len(ts_list) < 2:
            print(f"0x{cid:<6} {'—':>6}")
            continue
        intervals = [(ts_list[i+1]-ts_list[i])*1000 for i in range(len(ts_list)-1)]
        ok_pct = 100 * sum(1 for x in intervals if x <= 1200) / len(intervals)
        print(f"0x{cid:<6} {len(ts_list):>6} {statistics.mean(intervals):>9.1f} "
              f"{statistics.stdev(intervals):>8.1f} {max(intervals):>8.1f} {ok_pct:>8.1f}%")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("log"); ap.add_argument("--ids", nargs="+",
        default=["700","701","702","703","704","705"])
    args = ap.parse_args()
    analyse(args.log, [i.upper().lstrip("0X").zfill(3).upper() for i in args.ids])
```

2. Run against the Day 68 capture:

```bash
python3 scripts/measure_can_timing.py docs/evidence/can-interface/can_audit_*.log \
  > docs/evidence/can-interface/can_timing_analysis.txt
```

3. If any live frame shows `Max_ms > 2000` (2 s gap): open a blocker in
   `docs/project/ml-changelog.md` referencing the frame ID and the gap value.
   (Expected cause: Python GIL contention or socket buffer overflow in sidecar.)

**Deliverable**:
- `scripts/measure_can_timing.py`
- `docs/evidence/can-interface/can_timing_analysis.txt`

**Acceptance criteria**:
- Script runs without errors on the Day 68 log
- `≤1200ms%` column for 0x700, 0x702, 0x705 is ≥ 90 % (i.e., ≥ 90 % of intervals ≤ 1.2 s)
- Output file committed to `docs/evidence/can-interface/`

**Repo**: `foxbms-posix`

**ASPICE**: SWE.3.BP1 (software unit design — timing requirements for CAN publish loop
derived and measured). SWE.4.BP4 (test coverage — timing measurement closes
SW-REQ-ML-008 latency gate, once that requirement is added Day 88).

---

### Day 70 — CAN Frame Loss Detection

**Task**: Write a CI-runnable test that parses a captured CAN log and fails if any ML frame
has a gap > 2 s during normal BMS operation. Also add a VPS-side health-check script.

**Actions**:

1. Write `tests/test_can_frame_timing.py`:

```python
"""CI test: ML CAN frame timing compliance.
Uses a committed reference capture from docs/evidence/can-interface/.
"""
import pathlib, pytest
from scripts.measure_can_timing import parse_log

ML_FRAME_IDS = ["700", "701", "702", "703", "705"]  # 704 = NOT DEPLOYED
MAX_GAP_MS   = 2000.0

@pytest.fixture(scope="module")
def reference_log():
    logs = sorted(pathlib.Path("docs/evidence/can-interface").glob("can_audit_*.log"))
    if not logs:
        pytest.skip("No reference CAN log in docs/evidence/can-interface/")
    return logs[-1]

@pytest.mark.parametrize("frame_id", ML_FRAME_IDS)
def test_no_frame_gap_exceeds_2s(reference_log, frame_id):
    ts_list = []
    for ts, cid, _ in parse_log(reference_log):
        if cid == frame_id.upper():
            ts_list.append(ts)
    if len(ts_list) < 2:
        pytest.skip(f"0x{frame_id}: fewer than 2 frames in reference log")
    gaps = [(ts_list[i+1]-ts_list[i])*1000 for i in range(len(ts_list)-1)]
    max_gap = max(gaps)
    assert max_gap <= MAX_GAP_MS, (
        f"0x{frame_id}: max gap {max_gap:.0f} ms > {MAX_GAP_MS:.0f} ms gate"
    )
```

2. Write `scripts/check_can_health.sh` — a shell one-liner for the VPS:

```bash
#!/usr/bin/env bash
# Check ML sidecar is publishing live frames on vcan1
for ID in 700 701 702 703 705; do
    COUNT=$(timeout 5 candump -n 3 "vcan1,${ID}:7FF" 2>/dev/null | wc -l)
    if [ "$COUNT" -lt 1 ]; then
        echo "FAIL: 0x${ID} — no frames in 5 s"
        exit 1
    fi
    echo "OK: 0x${ID} — ${COUNT} frames"
done
echo "PASS: all ML CAN frames alive"
```

3. Run the pytest suite against the committed reference log:

```bash
pytest tests/test_can_frame_timing.py -v
```

**Deliverable**:
- `tests/test_can_frame_timing.py`
- `scripts/check_can_health.sh`

**Acceptance criteria**:
- `pytest tests/test_can_frame_timing.py` passes (or skips on missing log — not fails)
- `check_can_health.sh` runs on VPS and outputs `PASS: all ML CAN frames alive`

**Repo**: `foxbms-posix`

**ASPICE**: SWE.5.BP3 (integration test execution — frame gap test run and results recorded).
SUP.1.BP1 (quality assurance — CI gate prevents frame-loss regressions going undetected).

---

### Day 71 — DBC File: ML Messages (0x700–0x705)

**Task**: Create `tools/foxbms_ml.dbc` with formal DBC definitions for all 6 ML CAN
messages. A DBC file is required by ASPICE SWE.5 as the interface specification against
which integration tests are verified.

**Actions**:

1. Write `tools/foxbms_ml.dbc`. Use standard DBC syntax. Derive signal encoding from
   `src/ml_sidecar.py` and `tools/foxbms_constants.py`:

```
VERSION ""

NS_ :

BS_:

BU_: ML_SIDECAR BMS

BO_ 1792 ML_SOC: 2 ML_SIDECAR
 SG_ ML_SOC_Pct : 0|16@1+ (0.001,0) [0|100] "%" BMS
 SG_ BMS_SOC_Pct : 0|8@1+ (0.4,0) [0|100] "%" BMS

BO_ 1793 ML_SOH: 1 ML_SIDECAR
 SG_ ML_SOH_Pct : 0|8@1+ (0.4,0) [0|100] "%" BMS

BO_ 1794 ML_THERMAL: 2 ML_SIDECAR
 SG_ Thermal_Risk_Score : 0|8@1+ (0.00392,0) [0|1] "" BMS
 SG_ Max_Cell_Temp_degC : 8|8@1+ (1,-40) [-40|85] "degC" BMS

BO_ 1795 ML_IMBALANCE: 2 ML_SIDECAR
 SG_ Cell_Imbalance_mV : 0|16@1+ (0.1,0) [0|500] "mV" BMS

BO_ 1796 ML_RUL: 2 ML_SIDECAR
 SG_ RUL_Cycles : 0|16@1+ (1,0) [0|65535] "cycles" BMS

BO_ 1797 ML_ANOMALY: 2 ML_SIDECAR
 SG_ Anomaly_Score : 0|8@1+ (0.00392,0) [0|1] "" BMS
 SG_ Anomaly_Model_ID : 8|8@1+ (1,0) [0|255] "" BMS
```

2. Write `tests/test_can_dbc_ml.py` — loads the DBC and verifies:
   - All 6 message IDs (0x700–0x705) are defined
   - Signal factor/offset matches the values used in `ml_sidecar.py`
   - Round-trip encode/decode for representative values:
     - SOC 72.5 % → encode → decode → within 0.1 %
     - Anomaly score 0.42 → encode → decode → within 0.004

3. Run the test:

```bash
pytest tests/test_can_dbc_ml.py -v
```

**Deliverable**:
- `tools/foxbms_ml.dbc`
- `tests/test_can_dbc_ml.py`

**Acceptance criteria**:
- `pytest tests/test_can_dbc_ml.py` passes
- DBC file parses without error in `cantools`: `python3 -c "import cantools; db=cantools.database.load_file('tools/foxbms_ml.dbc'); print(len(db.messages), 'messages')"`

**Repo**: `foxbms-posix`

**ASPICE**: SWE.3.BP1 (software unit design — CAN interface formally specified in DBC).
SWE.4.BP1 (unit test — DBC roundtrip test covers signal encoding).
SWE.5.BP1 (integration test specification — DBC is the formal interface specification).

---

### Day 72 — CAN Decode Smoke Tests

**Task**: Write `tests/test_can_ml_frames.py` — a pytest module that starts the sidecar,
captures 30 s of live CAN, decodes each ML frame using the DBC, and checks value ranges.

**Actions**:

1. Write `tests/test_can_ml_frames.py`:

```python
"""CAN ML frame smoke tests.
Require: vECU + plant + sidecar running. Mark: sil.
"""
import pytest, subprocess, time, collections, pathlib
import cantools

pytestmark = pytest.mark.sil
DBC = cantools.database.load_file("tools/foxbms_ml.dbc")

@pytest.fixture(scope="module")
def live_frames():
    """Capture 30 s of ML CAN frames."""
    proc = subprocess.Popen(["candump", "-L", "vcan1,700:7F8"],
                             stdout=subprocess.PIPE, text=True)
    time.sleep(30)
    proc.terminate()
    frames = collections.defaultdict(list)
    for line in proc.stdout.read().splitlines():
        parts = line.strip().split()
        if len(parts) < 3 or "#" not in parts[2]:
            continue
        cid_hex, data_hex = parts[2].split("#", 1)
        cid = int(cid_hex, 16)
        data = bytes.fromhex(data_hex)
        try:
            msg = DBC.get_message_by_frame_id(cid)
            decoded = msg.decode(data)
            frames[cid].append(decoded)
        except Exception:
            pass
    return frames

def test_ml_soc_in_range(live_frames):
    assert live_frames[0x700], "No 0x700 ML_SOC frames received"
    for d in live_frames[0x700]:
        assert 0 <= d["ML_SOC_Pct"] <= 100, f"ML SOC out of range: {d}"

def test_anomaly_score_in_range(live_frames):
    assert live_frames[0x705], "No 0x705 ML_ANOMALY frames received"
    for d in live_frames[0x705]:
        assert 0 <= d["Anomaly_Score"] <= 1, f"Anomaly score out of range: {d}"

def test_thermal_risk_in_range(live_frames):
    assert live_frames[0x702], "No 0x702 ML_THERMAL frames received"
    for d in live_frames[0x702]:
        assert 0 <= d["Thermal_Risk_Score"] <= 1, f"Thermal risk out of range: {d}"

def test_soh_in_range(live_frames):
    assert live_frames[0x701], "No 0x701 ML_SOH frames received"
    for d in live_frames[0x701]:
        assert 50 <= d["ML_SOH_Pct"] <= 100, f"SOH out of range: {d}"
```

2. Add `cantools` to `requirements-ml-frozen.txt`:

```bash
pip install cantools && pip freeze > requirements-ml-frozen.txt
git add requirements-ml-frozen.txt && git commit -m "chore: add cantools for DBC-driven CAN tests"
```

**Deliverable**:
- `tests/test_can_ml_frames.py`

**Acceptance criteria**:
- `pytest tests/test_can_ml_frames.py -m "not sil"` collects tests (0 failures, may skip)
- Running with `--run-sil` on a live session: `ML_SOC_Pct in range` and
  `Anomaly_Score in range` both pass

**Repo**: `foxbms-posix`

**ASPICE**: SWE.4.BP1 (unit verification — CAN decode verified against DBC specification).
SWE.5.BP3 (integration test execution — CAN integration confirmed live).

---

### Day 73 — Fault Injection CAN Response Validation

**Task**: Extend `tests/test_sil_fault_matrix.py` with assertions on the raw CAN 0x705
byte values (not just the Python-computed score). Verify the DBC decode matches the
raw bytes for each fault scenario.

**Actions**:

1. In `scripts/sil_fault_matrix.py`, save the raw hex bytes of the first 0x705 frame
   where `score > 0.30` alongside the decoded score:

```python
result[fault["type"]]["detection_frame_hex"] = data_hex  # raw candump hex
result[fault["type"]]["detection_frame_decoded"] = DBC.get_message_by_frame_id(0x705).decode(bytes.fromhex(data_hex))
```

2. Add a new test `test_fault_detection_raw_bytes`:

```python
@pytest.mark.sil
@pytest.mark.parametrize("fault_type", ["overvoltage", "overcurrent"])
def test_fault_detection_raw_bytes(sil_fault_results, fault_type):
    r = sil_fault_results[fault_type]
    if not r.get("detected"):
        pytest.skip(f"{fault_type}: not detected — skip raw byte check")
    raw = bytes.fromhex(r["detection_frame_hex"])
    decoded = DBC.get_message_by_frame_id(0x705).decode(raw)
    assert decoded["Anomaly_Score"] > 0.30, (
        f"DBC-decoded score {decoded['Anomaly_Score']:.3f} < 0.30 "
        f"for {fault_type} detection frame"
    )
```

3. Re-run the fault matrix on a live session and save updated results:

```bash
python3 scripts/sil_fault_matrix.py
git add docs/evidence/sil-validation/fault_matrix_results.json
git commit -m "evidence(can): add raw CAN bytes to fault matrix results"
```

**Deliverable**:
- Updated `sil_fault_matrix.py` (saves raw hex + DBC-decoded values)
- Updated `tests/test_sil_fault_matrix.py` (raw byte assertions)
- Updated `fault_matrix_results.json` committed

**Acceptance criteria**:
- `fault_matrix_results.json` has `detection_frame_hex` key in overvoltage and overcurrent entries
- DBC-decoded `Anomaly_Score` matches Python-computed score within ±0.005

**Repo**: `foxbms-posix`

**ASPICE**: SWE.4.BP1 (unit test — DBC decode of fault detection frame verified).
SYS.4.BP1 (system integration — fault reaction traced from CAN frame to ML response).

---

### Day 74 — M3.2 Gate Review

**Task**: Review Week 8 deliverables. Update project plan with M3.2 status.

**M3.2 Checklist**:

| # | Criterion | Command | Pass |
|---|---|---|---|
| M3.2-A | DBC file committed | `git log --oneline tools/foxbms_ml.dbc` | ≥ 1 commit |
| M3.2-B | DBC test passes | `pytest tests/test_can_dbc_ml.py -v` | 0 failures |
| M3.2-C | Frame timing analysis committed | `ls docs/evidence/can-interface/can_timing_analysis.txt` | File exists |
| M3.2-D | Frame gap test passes | `pytest tests/test_can_frame_timing.py -v` | 0 failures / skips acceptable |
| M3.2-E | `cantools` in requirements | `grep cantools requirements-ml-frozen.txt` | Present |

**Actions**:

1. Run all 5 checklist items. Record pass/fail.
2. For fails: add to `ml-changelog.md`. Do not advance until all pass.
3. Update project plan milestone table.
4. Commit: `docs: M3.2 achieved — CAN interface integration tests complete`

**Deliverable**: M3.2 in project plan set to `ACHIEVED`.

**Repo**: `foxbms-posix`

**ASPICE**: MAN.3.BP4 (project monitoring). MAN.3.BP6 (project review).
SUP.8.BP6 (CAN test artifacts committed under CM).

---

## Week 9 (Day 75–81): Monitoring Dashboard Enhancement

**Goal**: The `web/` dashboard evolves from a 6-gauge live display into a
session-aware evidence capture tool. By end of Week 9, an operator can open the
dashboard, run a fault-injection test, download a session JSON, and attach it to
an ASPICE SWE.6 test report — all from the browser.

**Milestone**: M3.3 — Dashboard shows 10 metrics; export API operational.

---

### Day 75 — Dashboard Audit + Enhancement Specification

**Task**: Read `web/index.html` and `web/server.py` fully. Document the 6 existing
gauges and specify 10 new metrics to add. Produce a written spec before writing
any code.

**Actions**:

1. Read `web/index.html` and `web/server.py` — map every gauge, chart, and API endpoint.

2. Write `docs/plans/dashboard-enhancement-spec.md`:

```markdown
# Dashboard Enhancement Specification — Phase 3

## Existing Metrics (6 gauges, Day 75 baseline)
| # | Gauge | CAN Source | Current behavior |
|---|---|---|---|
| 1 | ML SOC (%) | 0x700 byte 0 | Single value gauge |
| 2 | SOH (%) | 0x701 byte 0 | Single value gauge |
| 3 | Thermal Risk | 0x702 byte 0 | Single value gauge |
| 4 | Cell Imbalance (mV) | 0x703 bytes 0-1 | Single value gauge |
| 5 | Anomaly Score | 0x705 byte 0 | Single value gauge |
| 6 | RUL (cycles) | 0x704 bytes 0-1 | Single value gauge (shows 0 = not deployed) |

## New Metrics to Add (10, Phase 3)
| # | Metric | Source | Widget type |
|---|---|---|---|
| 7  | ML SOC vs BMS SOC delta trend | 0x700 + 0x231 | 2-min rolling time-series chart |
| 8  | Anomaly score history (rolling 5 min) | 0x705 | Time-series chart |
| 9  | Fault injection event log | /api/inject_fault | Table: time, type, latency_ms |
| 10 | BMS state machine history | 0x220 | State timeline widget |
| 11 | Cell voltage heatmap (18 cells) | 0x250 | 18-cell color grid |
| 12 | Per-cell SOC imbalance bar chart | 0x250 + BMS SOC | Horizontal bar chart |
| 13 | SIL session uptime + frame count | server.py internal | Status row |
| 14 | ML inference latency histogram | sidecar 0x700 jitter | Histogram (ms bins) |
| 15 | Drift alert banner | /api/drift_status | Banner: GREEN/YELLOW/RED |
| 16 | Session export button | GET /api/export/session | Download button |
```

3. Mark metrics 7, 8, 9, 13, 15, 16 as **Phase 3 required** (must be done Days 76–80).
   Mark 10–12, 14 as **Phase 3 stretch** (implement if time allows, else Phase 4).

**Deliverable**: `docs/plans/dashboard-enhancement-spec.md` committed.

**Acceptance criteria**:
- Document lists all 6 existing and 10 new metrics
- Required vs stretch designation present for each new metric
- Committed before any `web/` code is modified

**Repo**: `foxbms-posix`

**ASPICE**: SWE.1.BP1 (software requirements specification — new dashboard requirements
captured before implementation). MAN.3.BP1 (project plan — scope defined before work starts).

---

### Day 76 — ML SOC vs BMS SOC Delta Trend Chart

**Task**: Add a 2-minute rolling time-series chart to the dashboard showing
ML SOC minus BMS SOC over time. This makes the 20% SOC gap (GAP-ML-001) visible
without reading CAN logs.

**Actions**:

1. In `web/server.py`, extend the `state_history` ring buffer to store:
   - `ml_soc_pct` (from 0x700 byte 0, scale 0.4 %/LSB)
   - `bms_soc_pct` (from 0x231 byte 0, existing field)
   - `soc_delta_pct` = `ml_soc_pct - bms_soc_pct`
   - `timestamp_s` (monotonic time)

   Ring buffer size: 120 entries (120 s at 1 Hz = 2 min).

2. Add a new WebSocket message type `{"type": "soc_trend", "data": [...]}` that
   broadcasts the ring buffer contents every 5 s.

3. In `web/index.html`, add a `<canvas id="socTrendChart">` and render it using
   Chart.js (already included if present, otherwise add CDN link):

```javascript
const socCtx = document.getElementById('socTrendChart').getContext('2d');
const socChart = new Chart(socCtx, {
    type: 'line',
    data: {
        labels: [],
        datasets: [
            {label: 'ML SOC (%)', borderColor: '#4CAF50', data: [], pointRadius: 0},
            {label: 'BMS SOC (%)', borderColor: '#2196F3', data: [], pointRadius: 0},
            {label: 'Delta (%)', borderColor: '#FF5722', data: [], pointRadius: 0, borderDash: [5,3]}
        ]
    },
    options: {animation: false, scales: {x: {display: false}}}
});
```

**Deliverable**: `web/server.py` and `web/index.html` modified.

**Acceptance criteria**:
- Dashboard loads without JS console errors
- After 30 s of SIL running, SOC trend chart shows 3 lines (ML SOC, BMS SOC, delta)
- Delta line is non-flat (values change as BMS SOC changes during discharge)

**Repo**: `foxbms-posix`

**ASPICE**: SWE.3.BP1 (detailed design — dashboard data model extended with ring buffer).
SWE.4.BP1 (unit test — new server.py WebSocket message type added and testable).

---

### Day 77 — Anomaly Score History Panel

**Task**: Add a 5-minute rolling anomaly score time-series to the dashboard.
During a fault injection event, the score spike must be clearly visible without
any operator action.

**Actions**:

1. In `web/server.py`, add a 300-entry anomaly history ring buffer
   (300 s at 1 Hz = 5 min):
   - Fields: `anomaly_score` (float 0–1), `timestamp_s`, `fault_active` (bool)

2. When `fault_active` is true (set by `/api/inject_fault`), record the start time
   so the chart can draw a vertical marker.

3. In `web/index.html`, add anomaly history chart with:
   - Line chart of `anomaly_score` over time
   - Horizontal reference line at 0.30 (detection threshold — red dashed)
   - Vertical annotation marker at fault injection times

4. Write `tests/test_server_ws.py::test_anomaly_history_message`:

```python
def test_anomaly_history_message(ws_client):
    """Server must broadcast soc_trend and anomaly_history every 5 s."""
    import time, json
    messages = []
    deadline = time.time() + 10
    while time.time() < deadline:
        msg = ws_client.recv_nowait()
        if msg:
            messages.append(json.loads(msg))
    types = {m.get("type") for m in messages}
    assert "anomaly_history" in types, f"Expected anomaly_history broadcast; got {types}"
```

**Deliverable**:
- `web/server.py` updated with anomaly history buffer
- `web/index.html` updated with anomaly chart + threshold line

**Acceptance criteria**:
- Dashboard shows anomaly history chart
- After injecting overvoltage fault, score spike > 0.30 is visible on chart within 30 s
- Threshold dashed line is drawn at 0.30

**Repo**: `foxbms-posix`

**ASPICE**: SWE.3.BP1 (detailed design). SYS.4.BP1 (system integration — fault injection
event visible in dashboard without operator action satisfies observability requirement).

---

### Day 78 — Fault Injection Event Log Table

**Task**: Add a persistent fault event log to the dashboard. Each injected fault records
timestamp, fault type, ML anomaly score before/after, and detection latency.
This log is the human-readable equivalent of `fault_matrix_results.json`.

**Actions**:

1. In `web/server.py`, add `fault_event_log = []` (max 50 entries):

```python
@app.post("/api/inject_fault")
async def inject_fault(req: Request):
    body = await req.json()
    fault_type = body.get("type", "unknown")
    pre_score  = state.get("anomaly_score", 0.0)
    inject_time = time.time()
    # ... existing fault injection logic ...
    fault_event_log.append({
        "time_iso": datetime.utcnow().isoformat(),
        "fault_type": fault_type,
        "pre_score": round(pre_score, 3),
        "inject_time_s": inject_time,
        "detection_time_s": None,  # filled in by CAN listener when score > 0.30
        "latency_ms": None,
        "peak_score": None,
    })
```

2. In the CAN listener (where 0x705 is processed), check if any pending event
   has `detection_time_s == None` and score > 0.30 — if so, fill in latency.

3. In `web/index.html`, add a `<table id="faultLog">` that populates from a new
   `/api/fault_log` endpoint:

```html
<table id="faultLog">
  <thead><tr><th>Time</th><th>Type</th><th>Pre-Score</th><th>Peak</th><th>Latency (ms)</th></tr></thead>
  <tbody></tbody>
</table>
```

4. Add `GET /api/fault_log` endpoint that returns the last 50 events as JSON.

**Deliverable**:
- `web/server.py` updated with fault event log and `/api/fault_log` endpoint
- `web/index.html` updated with fault log table

**Acceptance criteria**:
- After injecting a fault, `curl http://localhost:8765/api/fault_log | jq '.[0]'` returns
  an object with `fault_type`, `pre_score`, `inject_time_s` fields
- After fault detection (anomaly > 0.30), `latency_ms` is non-null

**Repo**: `foxbms-posix`

**ASPICE**: SWE.6.BP4 (software qualification test report — event log constitutes
test execution evidence). SUP.1.BP4 (quality records — fault events logged with timestamps).

---

### Day 79 — SIL Health Status Panel

**Task**: Add a system health panel to the top of the dashboard showing:
vECU alive / plant model alive / ML sidecar alive / VPS CAN capture active.
All four indicators must be green before test results are considered valid.

**Actions**:

1. In `web/server.py`, add a health tracking dict:

```python
health = {
    "vecu":    {"alive": False, "last_seen_s": 0.0},
    "plant":   {"alive": False, "last_seen_s": 0.0},
    "sidecar": {"alive": False, "last_seen_s": 0.0},
    "capture": {"alive": False, "last_seen_s": 0.0},
}
HEALTH_TIMEOUT_S = 5.0
```

   - `vecu`: alive if 0x220 (BMS state) seen within 5 s
   - `plant`: alive if 0x521 (IVT current) seen within 5 s
   - `sidecar`: alive if any 0x70x frame seen within 5 s
   - `capture`: alive if VPS telemetry file size is growing (checked via SSH every 60 s,
     or skip if VPS not configured)

2. Add `GET /api/health` endpoint returning the health dict.

3. In `web/index.html`, add 4 LED indicators at the top of the page:

```html
<div id="healthPanel">
  <span class="led" id="led-vecu">vECU</span>
  <span class="led" id="led-plant">Plant</span>
  <span class="led" id="led-sidecar">Sidecar</span>
  <span class="led" id="led-capture">Capture</span>
</div>
```

   Green = alive, Red = timed out. Updated every 2 s via polling `/api/health`.

**Deliverable**:
- `web/server.py` updated with health tracking + `/api/health`
- `web/index.html` updated with health panel

**Acceptance criteria**:
- `curl http://localhost:8765/api/health` returns valid JSON with `vecu`, `plant`, `sidecar` keys
- Dashboard shows 3 green LEDs (vECU, plant, sidecar) when all 3 are running
- Stopping the sidecar turns `sidecar` LED red within 7 s

**Repo**: `foxbms-posix`

**ASPICE**: SWE.3.BP1 (detailed design — health monitoring architecture defined).
SYS.4.BP1 (system integration — component liveness verified at system boundary).

---

### Day 80 — Session Export API

**Task**: Add `GET /api/export/session` to `web/server.py`. This endpoint serializes
the current session state (all ring buffers, fault event log, health status, BMS state
history) into a single JSON blob suitable for attachment to an ASPICE SWE.6 test report.

**Actions**:

1. Add the export endpoint to `web/server.py`:

```python
@app.get("/api/export/session")
async def export_session():
    import datetime
    snapshot = {
        "export_timestamp_iso": datetime.datetime.utcnow().isoformat() + "Z",
        "git_sha": subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True).strip(),
        "health": health,
        "bms_state_history": list(bms_state_history),
        "soc_trend": list(soc_trend_buffer),
        "anomaly_history": list(anomaly_history_buffer),
        "fault_event_log": fault_event_log[-50:],
        "summary": {
            "session_start_iso": session_start_iso,
            "total_frames": total_frame_count,
            "bms_normal_duration_s": bms_normal_duration_s,
            "soc_delta_mean_pct": _compute_soc_delta_mean(),
            "anomaly_score_mean": _compute_anomaly_mean(),
        }
    }
    return JSONResponse(snapshot)
```

2. Add a download button to `web/index.html`:

```html
<button id="exportBtn" onclick="exportSession()">Download Session JSON</button>
<script>
async function exportSession() {
    const r = await fetch('/api/export/session');
    const blob = await r.blob();
    const url  = URL.createObjectURL(blob);
    const a    = Object.assign(document.createElement('a'), {href: url,
                   download: `foxbms-session-${new Date().toISOString()}.json`});
    a.click();
}
</script>
```

3. Write `tests/test_export_api.py`:

```python
def test_export_session_schema(test_client):
    r = test_client.get("/api/export/session")
    assert r.status_code == 200
    data = r.json()
    for key in ("export_timestamp_iso", "git_sha", "health", "fault_event_log", "summary"):
        assert key in data, f"Missing key: {key}"
    assert "soc_delta_mean_pct" in data["summary"]
```

**Deliverable**:
- `web/server.py` with `/api/export/session`
- `web/index.html` with export button
- `tests/test_export_api.py`

**Acceptance criteria**:
- `curl http://localhost:8765/api/export/session | jq '.summary'` returns non-null object
- `export_timestamp_iso` is a valid ISO 8601 string
- `pytest tests/test_export_api.py` passes

**Repo**: `foxbms-posix`

**ASPICE**: SWE.6.BP4 (software qualification test report — session export provides
machine-readable test evidence). SUP.1.BP4 (quality records — export includes git SHA
for full traceability). SUP.10.BP1 (change request management — export enables operators
to attach evidence to change requests).

---

### Day 81 — M3.3 Gate Review

**Task**: Review Week 9 deliverables. Take a dashboard screenshot as evidence.

**M3.3 Checklist**:

| # | Criterion | How to Check | Pass |
|---|---|---|---|
| M3.3-A | SOC trend chart visible | Manual browser check | ✓ visible |
| M3.3-B | Anomaly history chart visible | Manual browser check | ✓ visible |
| M3.3-C | Fault event log table visible | Manual browser check | ✓ visible |
| M3.3-D | Health panel shows 3+ green LEDs | Manual browser check | ✓ green |
| M3.3-E | Export API returns schema-valid JSON | `pytest tests/test_export_api.py` | 0 failures |
| M3.3-F | Enhancement spec committed | `git log docs/plans/dashboard-enhancement-spec.md` | ≥ 1 commit |

**Actions**:

1. Run all checklist items.
2. Take a screenshot of the dashboard with all 6 new widgets visible.
   Save as `docs/evidence/dashboard/dashboard-phase3-screenshot.png`.
3. Commit: `evidence(dashboard): Phase 3 dashboard screenshot — M3.3 achieved`.
4. Update `docs/evidence/phase3-index.md`: mark dashboard row as `GENERATED`.
5. Update project plan: M3.3 = `ACHIEVED`.

**Deliverable**: Dashboard screenshot committed; M3.3 in project plan = `ACHIEVED`.

**Repo**: `foxbms-posix`

**ASPICE**: MAN.3.BP4 (project monitoring). SUP.1.BP4 (quality records — screenshot is
evidence artifact). MAN.3.BP6 (project review).

---

## Week 10 (Day 82–90): Drift Monitoring, CI Gates, Phase 3 Close

**Goal**: The system is observable (Phase 3 Week 9), stable (Phase 3 Week 10 systemd
hardening), and protected against regression (Phase 3 Week 10 CI gates).
By Day 90, `main` is tagged `v3.0.0` with full Phase 3 evidence committed.

**Milestone**: M3.4 — All CI gates strict; PSI monitor running; Phase 3 merged.

---

### Day 82 — PSI Drift Monitor Skeleton

**Task**: Implement `pipeline/drift_monitor.py` — computes Population Stability Index (PSI)
for each ML input feature (cell_V, pack_I_A, T_avg, T_max, velocity) by comparing the
current day's SIL telemetry against the Phase 2 baseline distribution.

**Actions**:

1. Write `pipeline/drift_monitor.py`:

```python
"""Population Stability Index (PSI) drift monitor.
Compares a new CAN telemetry batch against the Phase 2 baseline feature distribution.
PSI < 0.10 = stable. 0.10–0.20 = minor drift. > 0.20 = significant drift (alert).
"""
import numpy as np, json, pathlib

FEATURE_NAMES = ["cell_V", "pack_I_A", "T_avg", "T_max", "velocity"]
PSI_STABLE    = 0.10
PSI_ALERT     = 0.20
N_BINS        = 10

def _psi_single(baseline: np.ndarray, current: np.ndarray, n_bins=N_BINS) -> float:
    """Compute PSI for one feature."""
    bins = np.percentile(baseline, np.linspace(0, 100, n_bins + 1))
    bins[0]  -= 1e-6
    bins[-1] += 1e-6
    base_hist = np.histogram(baseline, bins=bins)[0] / len(baseline)
    curr_hist = np.histogram(current,  bins=bins)[0] / len(current)
    base_hist = np.where(base_hist == 0, 1e-6, base_hist)
    curr_hist = np.where(curr_hist == 0, 1e-6, curr_hist)
    return float(np.sum((curr_hist - base_hist) * np.log(curr_hist / base_hist)))

def compute_psi(baseline_npz: pathlib.Path, current_npz: pathlib.Path) -> dict:
    base = np.load(baseline_npz)["features"]
    curr = np.load(current_npz)["features"]
    results = {}
    for i, name in enumerate(FEATURE_NAMES):
        psi = _psi_single(base[:, i], curr[:, i])
        results[name] = {
            "psi": round(psi, 4),
            "status": "STABLE" if psi < PSI_STABLE else ("MINOR" if psi < PSI_ALERT else "ALERT"),
        }
    results["overall_status"] = "ALERT" if any(
        r["status"] == "ALERT" for r in results.values() if isinstance(r, dict)
    ) else "STABLE"
    return results

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: drift_monitor.py <baseline.npz> <current.npz>"); sys.exit(1)
    r = compute_psi(pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]))
    print(json.dumps(r, indent=2))
    sys.exit(1 if r["overall_status"] == "ALERT" else 0)
```

2. Write `tests/test_drift_monitor.py`:

```python
import numpy as np, pathlib, pytest
from pipeline.drift_monitor import compute_psi, PSI_ALERT

def make_npz(tmp_path, seed, n=500):
    rng = np.random.default_rng(seed)
    features = rng.normal([3.7, 0.5, 25.0, 30.0, 35.0],
                           [0.05, 0.3, 2.0, 3.0, 5.0], size=(n, 5)).astype(np.float32)
    p = tmp_path / f"feat_{seed}.npz"; np.savez(p, features=features); return p

def test_same_distribution_stable(tmp_path):
    b = make_npz(tmp_path, 0); c = make_npz(tmp_path, 1)
    r = compute_psi(b, c)
    assert r["overall_status"] == "STABLE", f"Same-dist PSI triggered alert: {r}"

def test_shifted_distribution_alerts(tmp_path):
    rng = np.random.default_rng(42)
    b_feat = rng.normal([3.7, 0.5, 25.0, 30.0, 35.0], [0.05, 0.3, 2.0, 3.0, 5.0],
                        size=(500, 5)).astype(np.float32)
    c_feat = b_feat.copy(); c_feat[:, 0] += 0.3  # shift cell_V by 300 mV — big drift
    bp = tmp_path / "base.npz"; np.savez(bp, features=b_feat)
    cp = tmp_path / "curr.npz"; np.savez(cp, features=c_feat)
    r = compute_psi(bp, cp)
    assert r["cell_V"]["psi"] > PSI_ALERT, f"300 mV shift should alert: {r['cell_V']}"
```

3. `pytest tests/test_drift_monitor.py`

**Deliverable**:
- `pipeline/drift_monitor.py`
- `tests/test_drift_monitor.py`

**Acceptance criteria**:
- `pytest tests/test_drift_monitor.py` passes (2 tests, 0 failures)
- `python3 pipeline/drift_monitor.py` prints usage message and exits 0

**Repo**: `taktflow-bms-ml`

**ASPICE**: SWE.1.BP1 (software requirements — PSI drift monitoring requirement will be
captured as SW-REQ-ML-013 on Day 88). SWE.3.BP1 (detailed design — PSI algorithm specified
in code). SWE.4.BP1 (unit test — `test_drift_monitor.py` covers both branches).

---

### Day 83 — PSI Daily Cron Job

**Task**: Deploy `foxbms-drift.service` + `foxbms-drift.timer` on the VPS. Each night
at 01:00, the service converts the prior day's telemetry log to a feature array and
runs `drift_monitor.py` against the Phase 2 baseline. Result is written to
`/var/lib/foxbms-telemetry/drift/YYYY-MM-DD.json`.

**Actions**:

1. Write `/opt/foxbms-sil/scripts/nightly_drift.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
DATE=$(date -d "yesterday" +%Y-%m-%d)
LOG="/var/lib/foxbms-telemetry/${DATE}/candump_${DATE}_*.log.gz"
OUT_DIR="/var/lib/foxbms-telemetry/drift"
BASELINE="/opt/foxbms-sil/data/baseline_phase2_features.npz"
CURR_NPZ="${OUT_DIR}/${DATE}_features.npz"
RESULT="${OUT_DIR}/${DATE}.json"

mkdir -p "$OUT_DIR"
python3 /opt/foxbms-sil/scripts/log_to_features.py "$LOG" --output "$CURR_NPZ"
python3 /opt/foxbms-sil/pipeline/drift_monitor.py "$BASELINE" "$CURR_NPZ" > "$RESULT" || true
# log overall status
STATUS=$(python3 -c "import json,sys; d=json.load(open('${RESULT}')); print(d['overall_status'])")
echo "[drift] ${DATE}: ${STATUS}" >> /var/log/foxbms-drift.log
```

2. Deploy systemd timer:

```ini
# /etc/systemd/system/foxbms-drift.timer
[Unit]
Description=foxBMS ML Drift Monitor (nightly)

[Timer]
OnCalendar=01:00
Persistent=true

[Install]
WantedBy=timers.target
```

3. Write `scripts/log_to_features.py` — reads a candump `.log.gz` and extracts the
   5-feature array (cell_V, pack_I_A, T_avg, T_max, velocity) using
   `tools/foxbms_constants.py` decoders. Output: `.npz` with `features` key.

**Deliverable**:
- `scripts/nightly_drift.sh` deployed on VPS
- `scripts/log_to_features.py` committed to `foxbms-posix`
- `foxbms-drift.timer` enabled on VPS

**Acceptance criteria**:
- `systemctl list-timers foxbms-drift.timer` shows timer scheduled for 01:00
- Manual test: `bash scripts/nightly_drift.sh` completes without error (using yesterday's log)
- `/var/lib/foxbms-telemetry/drift/YYYY-MM-DD.json` has `overall_status` key

**Repo**: `foxbms-posix` (scripts), VPS (service deployment)

**ASPICE**: SWE.3.BP1 (detailed design — nightly drift computation pipeline).
SUP.8.BP1 (configuration management — cron job configuration committed to VCS).

---

### Day 84 — PSI Alert Integration + Dashboard Drift Banner

**Task**: Wire the nightly PSI result into the dashboard drift alert banner
(metric #15 from Day 75 spec) and add a CI gate that fails if any drift JSON shows ALERT.

**Actions**:

1. Add `GET /api/drift_status` to `web/server.py`:

```python
@app.get("/api/drift_status")
async def drift_status():
    import glob, json, pathlib
    files = sorted(glob.glob("/var/lib/foxbms-telemetry/drift/*.json"))
    if not files:
        return {"status": "UNKNOWN", "date": None, "details": {}}
    latest = json.loads(pathlib.Path(files[-1]).read_text())
    latest["date"] = pathlib.Path(files[-1]).stem
    return latest
```

2. In `web/index.html`, add drift banner:

```html
<div id="driftBanner" class="banner banner-unknown">
  Drift: <span id="driftStatus">UNKNOWN</span>
  — <span id="driftDate">no data</span>
</div>
```

   Poll `/api/drift_status` every 60 s. Set CSS class `banner-green` / `banner-yellow` /
   `banner-red` based on `status` value (STABLE / MINOR / ALERT).

3. Write `tests/test_drift_alert.py`:

```python
def test_psi_alert_exits_nonzero(tmp_path):
    """drift_monitor.py must exit 1 when any feature is ALERT."""
    import subprocess, numpy as np
    rng = np.random.default_rng(0)
    b_f = rng.normal([3.7,0.5,25,30,35],[0.05,0.3,2,3,5],size=(500,5)).astype("f4")
    c_f = b_f.copy(); c_f[:,0] += 0.4  # 400 mV shift → PSI >> 0.20
    bp = tmp_path/"b.npz"; cp = tmp_path/"c.npz"
    np.savez(bp, features=b_f); np.savez(cp, features=c_f)
    result = subprocess.run(
        ["python3","pipeline/drift_monitor.py", str(bp), str(cp)], capture_output=True)
    assert result.returncode == 1, "Expected exit 1 on ALERT drift"
```

**Deliverable**:
- `web/server.py` with `/api/drift_status`
- `web/index.html` with drift banner
- `tests/test_drift_alert.py`

**Acceptance criteria**:
- `pytest tests/test_drift_alert.py` passes
- `curl http://localhost:8765/api/drift_status | jq .status` returns `"STABLE"` or `"UNKNOWN"` (not error)
- Drift banner visible in browser (may show UNKNOWN if no VPS data yet)

**Repo**: `foxbms-posix` / `taktflow-bms-ml`

**ASPICE**: SWE.1.BP5 (requirements consistency — drift alert requirement implemented
and testable). SWE.4.BP1 (unit test — `test_drift_alert.py`). SUP.9.BP1 (problem
resolution — drift alerts surface model degradation as a trackable problem).

---

### Day 85 — systemd Stability Hardening

**Task**: Add `WatchdogSec` and restart policies to all three SIL services (plant,
sidecar, vECU) so that a crashed process restarts automatically and the capture service
reconnects. No operator intervention required for transient crashes.

**Actions**:

1. Update `/etc/systemd/system/foxbms-plant.service`:

```ini
[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/foxbms-sil/src/plant_model.py
Restart=always
RestartSec=3
WatchdogSec=30
NotifyAccess=main
StartLimitIntervalSec=60
StartLimitBurst=5
```

2. Update `/etc/systemd/system/foxbms-sidecar.service` identically, adjusting `ExecStart`.

3. For `foxbms-capture.service`, verify `After=foxbms-plant.service` is set so capture
   restarts after plant. Add `BindsTo=foxbms-plant.service`.

4. Add `sd_notify` calls to `plant_model.py` (heartbeat every 10 s):

```python
import subprocess
def sd_watchdog():
    try:
        subprocess.run(["systemd-notify", "WATCHDOG=1"], check=False)
    except FileNotFoundError:
        pass   # not running under systemd — skip silently
```

   Call `sd_watchdog()` in the main loop every 10 s.

5. Deploy: `systemctl daemon-reload && systemctl restart foxbms-plant foxbms-sidecar foxbms-capture`

6. Smoke test: `kill -9 $(pgrep -f plant_model.py)` — verify restart within 5 s:

```bash
sleep 6 && systemctl is-active foxbms-plant  # should print "active"
```

**Deliverable**: Updated systemd unit files committed to `scripts/vps/`; `sd_watchdog()`
added to `src/plant_model.py`.

**Acceptance criteria**:
- `kill -9` test: plant service restarts within 5 s
- `systemctl status foxbms-plant` shows `WatchdogSec=30s`
- Updated service files committed to `scripts/vps/`

**Repo**: `foxbms-posix`

**ASPICE**: SWE.3.BP1 (detailed design — watchdog architecture specified). SWE.4.BP1
(unit test — restart smoke test). MAN.3.BP4 (project monitoring — uptime observable
via health panel from Day 79).

---

### Day 86 — CI Gate Hardening

**Task**: Audit every GitHub Actions workflow in `.github/workflows/`. Remove all
`continue-on-error: true` flags from ML-related jobs. Add `ml-can-timing` as a new
required CI gate. Ensure all gates fail fast.

**Actions**:

1. Search for `continue-on-error` in all workflow files:

```bash
grep -rn "continue-on-error" .github/workflows/
```

2. For each occurrence in ML jobs: remove the flag (or set to `false`). Document the
   change rationale in commit message.

3. Add `ml-can-timing` job to `ci.yml`:

```yaml
ml-can-timing:
  name: CAN Frame Timing Compliance
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - name: Install deps
      run: pip install pytest
    - name: Run CAN timing tests (using committed reference log)
      run: pytest tests/test_can_frame_timing.py -v
```

4. Verify all existing ML CI jobs are present in the required status checks list
   (document in `docs/aspice-cl2/15-SUP.8-configuration-management/cm-plan.md`).

5. Add a `tests/test_ci_gate_completeness.py` test that reads `ci.yml` and asserts
   all 5 required ML jobs are present:

```python
REQUIRED_ML_JOBS = [
    "ml-sidecar-smoke", "ml-accuracy", "ml-can-timing",
    "test-can-dbc", "sil-validate-nightly-stub"
]
def test_all_ml_ci_jobs_present():
    import yaml, pathlib
    ci = yaml.safe_load(pathlib.Path(".github/workflows/ci.yml").read_text())
    jobs = set(ci.get("jobs", {}).keys())
    for j in REQUIRED_ML_JOBS:
        assert j in jobs, f"CI job missing: {j}"
```

**Deliverable**: All `continue-on-error` flags removed from ML CI jobs; `ml-can-timing`
job added; `test_ci_gate_completeness.py` committed.

**Acceptance criteria**:
- `grep -rn "continue-on-error: true" .github/workflows/` returns 0 lines in ML jobs
- `pytest tests/test_ci_gate_completeness.py` passes
- GitHub Actions run (or local `act` dry run) shows all 5 ML jobs execute

**Repo**: `foxbms-posix`

**ASPICE**: SUP.1.BP1 (quality assurance — CI gates enforce quality criteria automatically).
SUP.8.BP6 (configuration management — CI configuration committed and change-controlled).
SUP.10.BP1 (change request management — CI gate changes go through PR review).

---

### Day 87 — Phase 3 Evidence Package

**Task**: Compile all Phase 3 evidence into a single document
`docs/evidence/phase3-package.md`. This is the ASPICE SWE.6 test summary report
that would be presented at a CL2 assessment.

**Actions**:

1. Write `docs/evidence/phase3-package.md`. Structure:

```markdown
# Phase 3 Evidence Package — foxBMS POSIX ML Subsystem

**Date**: [today]
**Git tag**: v3.0.0-rc1
**ASPICE capability level target**: CL2

---
## 1. SIL Validation Evidence
[Embed table from sil-validation-phase3.md]
- SIL result JSON: `sil_result_<ts>.json` — PASS
- Fault matrix: `fault_matrix_results.json` — 5 scenarios
- Reference: SWE.6.BP3, SWE.6.BP4

## 2. CAN Interface Evidence
- CAN signal audit: `can-signal-audit.md`
- Frame timing analysis: `can_timing_analysis.txt`
- DBC file: `tools/foxbms_ml.dbc`
- All 6 ML frames present; no gap > 2 s in reference log
- Reference: SWE.5.BP3, SYS.4.BP1

## 3. Dashboard Evidence
- Screenshot: `dashboard-phase3-screenshot.png`
- Export API test: `test_export_api.py` — PASS
- All 6 required new widgets implemented
- Reference: SWE.6.BP4, SUP.1.BP4

## 4. Drift Monitoring Evidence
- `pipeline/drift_monitor.py` — PSI algorithm verified by test
- Nightly timer deployed on VPS
- `test_drift_monitor.py` — 2/2 pass; `test_drift_alert.py` — 1/1 pass
- Reference: SWE.3.BP1, SWE.4.BP1

## 5. CI Gate Status
[Table of all ML CI jobs: name, status, last run]
- Reference: SUP.1.BP1, SUP.8.BP6

## 6. Open Issues
[List any M3.x criteria that are documented failures, with links to ml-changelog.md]

## 7. ASPICE Process Area Coverage Matrix
| Process Area | BP | Evidence Artifact | Status |
|---|---|---|---|
| SWE.5 | BP1 BP3 | can-signal-audit.md, test_can_frame_timing.py | ACHIEVED |
| SWE.6 | BP1 BP3 BP4 | sil-validation-phase3.md, sil_result_*.json | ACHIEVED |
| SYS.4 | BP1 | fault_matrix_results.json | ACHIEVED |
| SYS.5 | BP1 | sil-validation-phase3.md | ACHIEVED |
| MAN.3 | BP1 BP4 BP6 | project-plan.md M3.x rows | ACHIEVED |
| SUP.1 | BP1 BP4 | test_ci_gate_completeness.py, event logs | ACHIEVED |
| SUP.8 | BP1 BP6 | committed artifacts, CI config | ACHIEVED |
```

2. `git add docs/evidence/phase3-package.md && git commit -m "docs(evidence): Phase 3 evidence package"`

**Deliverable**: `docs/evidence/phase3-package.md` committed.

**Acceptance criteria**:
- Document has all 7 sections
- ASPICE coverage matrix has ≥ 8 rows
- Commit exists

**Repo**: `foxbms-posix`

**ASPICE**: SWE.6.BP4 (test report). SUP.1.BP4 (quality records).
MAN.3.BP6 (project review — evidence compiled for milestone review).

---

### Day 88 — ASPICE Gap Closure: New SW-REQ-ML Requirements

**Task**: Add SW-REQ-ML-013 through SW-REQ-ML-016 to the SWE.1 document to formally
capture the Phase 3 requirements (drift monitoring, CAN timing, dashboard export,
systemd watchdog). These requirements were implemented before specification — adding
them now closes the requirements-before-design traceability gap.

**IMPORTANT**: Check for HITL-LOCK markers in `SWE.1-software-requirements.md`
before any edit. Only add content **outside** locked regions. The new requirements
go in Section 11 after the last existing ML requirement.

**Actions**:

1. Read `docs/aspice-cl2/08-SWE.1-software-requirements/SWE.1-software-requirements.md`
   to find the last SW-REQ-ML-* number and verify no HITL-LOCK covers Section 11.8+.

2. Add Section 11.8 after the last existing ML requirements section:

```markdown
### 11.8 Drift Monitoring

| ID | Requirement | Derives From | ASIL | Verification |
|---|---|---|---|---|
| SW-REQ-ML-013 | The ML pipeline shall compute PSI for each of the 5 input features (cell_V, pack_I_A, T_avg, T_max, velocity) daily, comparing the current day's SIL telemetry against the Phase 2 baseline distribution. A PSI value > 0.20 for any feature shall set `overall_status = "ALERT"` and cause the nightly job to exit 1. **Acceptance**: `tests/test_drift_alert.py` passes; `tests/test_drift_monitor.py::test_shifted_distribution_alerts` passes. | Phase 3 production hardening | QM | ML-TC-013 |

### 11.9 CAN Interface Timing

| ID | Requirement | Derives From | ASIL | Verification |
|---|---|---|---|---|
| SW-REQ-ML-014 | ML CAN messages 0x700, 0x702, and 0x705 shall be published at ≥ 0.8 Hz (inter-frame interval ≤ 1250 ms) during BMS NORMAL state. No inter-frame gap shall exceed 2000 ms during a 5-minute NORMAL operation window. **Acceptance**: `tests/test_can_frame_timing.py` passes. | GAP-ML-008 (timing observable) | QM | ML-TC-014 |

### 11.10 Dashboard Session Export

| ID | Requirement | Derives From | ASIL | Verification |
|---|---|---|---|---|
| SW-REQ-ML-015 | The monitoring dashboard server shall expose a `GET /api/export/session` endpoint that returns a JSON object containing: export timestamp (ISO 8601), git SHA, health status of vECU/plant/sidecar, fault event log (last 50 entries), anomaly score history (last 300 samples), and SOC delta statistics. **Acceptance**: `tests/test_export_api.py` passes. | Phase 3 auditability requirement | QM | ML-TC-015 |

### 11.11 Process Watchdog

| ID | Requirement | Derives From | ASIL | Verification |
|---|---|---|---|---|
| SW-REQ-ML-016 | The `foxbms-plant.service` and `foxbms-sidecar.service` systemd units shall configure `WatchdogSec=30` and `Restart=always`. A killed plant process shall restart within 10 seconds. **Acceptance**: kill-and-restart smoke test documented in `docs/evidence/sil-validation/watchdog-test.md`. | Phase 3 availability requirement | QM | ML-TC-016 |
```

3. Increment document revision to `1.2`:

```markdown
| 1.2 | 2026-[today] | An Dao | — | Section 11.8–11.11: add SW-REQ-ML-013..016 for Phase 3 production hardening (drift, CAN timing, export API, watchdog) |
```

4. Commit: `docs(swe1): add SW-REQ-ML-013..016 — Phase 3 production hardening requirements`

**Deliverable**: `SWE.1-software-requirements.md` updated with 4 new requirements.

**Acceptance criteria**:
- All 4 new requirements present in Section 11.8–11.11
- Each references its verification test case (ML-TC-013..016)
- No HITL-LOCK markers violated
- Revision history updated

**Repo**: `foxbms-posix`

**ASPICE**: SWE.1.BP1 (software requirements specification — all Phase 3 behaviors
formally specified). SWE.1.BP5 (requirements consistency — requirements added after
implementation to close traceability gap; acknowledged in revision rationale).

---

### Day 89 — Phase 3 Final Review Checklist

**Task**: Run the complete 15-item Phase 3 exit gate. Resolve all open issues before Day 90.

**Phase 3 Exit Gate (15 criteria)**:

| # | Criterion | Command / Check | Pass Condition |
|---|---|---|---|
| 3X-01 | SIL harness exit 0 | `make sil-validate` | `"passed": true` |
| 3X-02 | All 5 fault scenarios in matrix | `jq 'keys\|length' fault_matrix_results.json` | `5` |
| 3X-03 | SIL evidence report committed | `git log docs/evidence/sil-validation/sil-validation-phase3.md` | ≥ 1 commit |
| 3X-04 | DBC test passes | `pytest tests/test_can_dbc_ml.py -v` | 0 failures |
| 3X-05 | CAN timing test passes | `pytest tests/test_can_frame_timing.py -v` | 0 failures / skip |
| 3X-06 | ML frame IDs 0x700/702/705 in reference log | `docs/evidence/can-interface/can-signal-audit.md` | All 3 present |
| 3X-07 | Dashboard SOC trend visible | `docs/evidence/dashboard/dashboard-phase3-screenshot.png` | File exists |
| 3X-08 | Export API test passes | `pytest tests/test_export_api.py -v` | 0 failures |
| 3X-09 | Drift monitor tests pass | `pytest tests/test_drift_monitor.py tests/test_drift_alert.py -v` | 0 failures |
| 3X-10 | PSI timer deployed | `ssh VPS systemctl is-active foxbms-drift.timer` | `active` |
| 3X-11 | `continue-on-error` removed | `grep -rn "continue-on-error: true" .github/workflows/` | 0 ML jobs |
| 3X-12 | CI gate completeness test passes | `pytest tests/test_ci_gate_completeness.py -v` | 0 failures |
| 3X-13 | SW-REQ-ML-013..016 in SWE.1 | `grep -c "SW-REQ-ML-01[3-6]" docs/aspice-cl2/08-SWE.1-software-requirements/SWE.1-software-requirements.md` | `4` |
| 3X-14 | Phase 3 evidence package committed | `git log docs/evidence/phase3-package.md` | ≥ 1 commit |
| 3X-15 | All Phase 2 accuracy gates still pass | `pytest tests/test_ml_accuracy.py -v` | 0 failures |

**Actions**:

1. Run all 15 checks in sequence. For each failure: add a blocker entry in
   `docs/project/ml-changelog.md` and resolve before Day 90.

2. Write `docs/evidence/phase3-package.md` section "Exit Gate Results" with the
   pass/fail status of each criterion.

3. If any criterion cannot be resolved today, defer it to `docs/plans/phase3-deferred.md`
   with a root cause explanation and a Phase 4 remediation task.

**Deliverable**: Exit gate results section in `phase3-package.md`; all 15 criteria met
(or formally deferred with rationale).

**Repo**: `foxbms-posix`

**ASPICE**: MAN.3.BP6 (project review — formal phase exit review).
SUP.1.BP1 (quality assurance — systematic checklist against defined criteria).
SWE.6.BP5 (regression testing — Phase 2 accuracy gates re-run to confirm no regression).

---

### Day 90 — M3.4 Phase 3 Close: Merge + Tag

**Task**: Merge the Phase 3 feature branch to `main`, tag `v3.0.0`, and prepare the
Phase 4 kickoff brief.

**Actions**:

1. Run the full test suite one final time on the feature branch:

```bash
pytest tests/ -v -m "not sil" --tb=short
```

2. Verify git log is clean (no debug commits, no accidentally committed secrets):

```bash
git log --oneline feat/ai-phase3-hardening ^main | head -20
git diff main..feat/ai-phase3-hardening -- '*.env' '*.key' '*.secret' | wc -l
# must be 0
```

3. Create a PR from `feat/ai-phase3-hardening` → `main`. PR description must reference:
   - M3.1 commit (SIL validation)
   - M3.2 commit (CAN interface)
   - M3.3 commit (dashboard)
   - M3.4 evidence package commit
   - All 15 exit gate results

4. After PR approval, merge (squash merge acceptable if commit count is large).

5. Tag the merge commit:

```bash
git tag -a v3.0.0 -m "Phase 3 complete: SIL validation, CAN hardening, monitoring dashboard, drift monitoring"
```

6. Write `docs/plans/phase4-kickoff.md` (1 page) summarizing:
   - Phase 3 achievements (metrics, evidence artifacts, new requirements)
   - Phase 4 theme: customer pipeline (`run_audit.py`, DBC-driven bench sidecar, PDF reports)
   - Top 3 Phase 3 deferred items that feed into Phase 4

7. Update `docs/plans/plan-ai-180-day.md`: change Phase 3 status from `*Phase 3 (Day 61–90) will be detailed here*` to `**COMPLETE** — see day61-90-daily-tasks.md`.

**Deliverable**:
- `main` branch updated with Phase 3 work
- Tag `v3.0.0` created
- `docs/plans/phase4-kickoff.md` committed

**Acceptance criteria**:
- `git tag -l | grep v3.0.0` returns `v3.0.0`
- `pytest tests/ -m "not sil"` on `main` exits 0
- `docs/plans/phase4-kickoff.md` exists and has Phase 4 theme described

**Repo**: `foxbms-posix`

**ASPICE**: MAN.3.BP6 (project review — Phase 3 formally closed with tag and evidence).
SUP.8.BP6 (change management — tag creates a named baseline for Phase 3 deliverables).
SUP.10.BP1 (change request management — Phase 3 → Phase 4 transition documented).
SWE.6.BP5 (regression testing — full test suite passes on `main` post-merge).

---

## Phase 3 Milestone Summary

| Milestone | Day | Criteria Count | ASPICE BPs |
|---|---|---|---|
| **M3.1** | 67 | 5 | SWE.5.BP1, SWE.6.BP3, SWE.6.BP4, MAN.3.BP4, MAN.3.BP6 |
| **M3.2** | 74 | 5 | SWE.3.BP1, SWE.4.BP1, SWE.5.BP1, SWE.5.BP3, SUP.8.BP6 |
| **M3.3** | 81 | 6 | SWE.1.BP1, SWE.3.BP1, SWE.6.BP4, MAN.3.BP4, SUP.1.BP4 |
| **M3.4** | 90 | 15 | MAN.3.BP6, SUP.1.BP1, SUP.8.BP6, SUP.10.BP1, SWE.6.BP5 |

---

## ASPICE Process Area Coverage Matrix — Phase 3

| Process Area | BP | Days Covered | Evidence Artifacts |
|---|---|---|---|
| **SWE.1** | BP1, BP5 | 75, 88 | `SWE.1-software-requirements.md` §11.8–11.11 (SW-REQ-ML-013..016); `dashboard-enhancement-spec.md` |
| **SWE.3** | BP1 | 62, 69, 71, 76–79, 82–83, 85 | `run_sil_validation.py`; `foxbms_ml.dbc`; `drift_monitor.py`; updated `server.py` |
| **SWE.4** | BP1, BP4 | 63, 70, 72, 73, 80, 82, 84–86 | `test_sil_validation.py`; `test_can_frame_timing.py`; `test_can_dbc_ml.py`; `test_export_api.py`; `test_drift_monitor.py` |
| **SWE.5** | BP1, BP3 | 62, 68, 70 | `run_sil_validation.py`; `can-signal-audit.md`; `test_can_frame_timing.py` |
| **SWE.6** | BP1, BP3, BP4, BP5 | 63, 65, 66, 87, 89, 90 | `sil-validation-phase3.md`; `sil_result_*.json`; `phase3-package.md` |
| **SYS.4** | BP1 | 64, 73 | `fault_matrix_results.json`; `test_sil_fault_matrix.py` |
| **SYS.5** | BP1 | 66 | `sil-validation-phase3.md` (system-level evidence) |
| **MAN.3** | BP1, BP4, BP6 | 61, 67, 74, 81, 87, 89, 90 | Project plan M3.x rows; `phase3-package.md` exit gate results |
| **SUP.1** | BP1, BP4 | 70, 78, 80, 86, 87 | `test_ci_gate_completeness.py`; fault event log; session export |
| **SUP.8** | BP1, BP6 | 61, 74, 83, 86, 90 | Evidence directory scaffold; committed service files; CI config; v3.0.0 tag |
| **SUP.9** | BP1 | 68, 69, 84 | `ml-changelog.md` blocker entries; drift alert as surfaced problem |
| **SUP.10** | BP1 | 88, 90 | SWE.1 revision history; Phase 4 kickoff document; PR review |

---

*Phase 4 (Day 91–120) will be detailed separately after Phase 3 exit criteria are met.*
*Phase 4 theme: Customer Pipeline — `run_audit.py`, DBC-driven bench sidecar, PDF report generator.*
