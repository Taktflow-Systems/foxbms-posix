# Day 1–30 Daily Task Breakdown — foxBMS POSIX AI Implementation

**Date**: 2026-03-27
**Phase**: Phase 1 — Data Infrastructure + Baseline Metrics
**Parent plan**: [`plan-ai-180-day.md`](plan-ai-180-day.md)
**Focus**: Data collection, infrastructure setup, and baseline accuracy measurement.
No model weights are changed in Phase 1. Everything here is measurement and plumbing.

---

## Reading This Document

Each day entry contains:
- **Task** — what to build or run
- **Deliverable** — the concrete output (file, service, metric)
- **Acceptance criteria** — the exit condition; do not proceed to the next day until it passes
- **Repo** — which repo the work lands in (`foxbms-posix` or `taktflow-bms-ml`)

**If a day's acceptance criteria are not met**: do not skip them or mark them done. Add
a blocker note in `docs/project/ml-changelog.md`, investigate root cause, and re-attempt
the same day's tasks the next working session before moving on.

---

## Pre-requisite: Day 0 Checklist (Run Before Day 1)

All six items below must pass before starting Day 1 work.

| # | Check | Command | Pass condition |
|---|---|---|---|
| 0-A | VPS reachable | `ssh root@152.53.245.209 uptime` | Returns uptime string |
| 0-B | VPS disk ≥ 500 MB free | `ssh root@152.53.245.209 "df -h /var/lib"` | Avail ≥ 500M |
| 0-C | Python venv created locally | `source taktflow-bms-ml/.venv/bin/activate && python -c "import onnxruntime"` | No ImportError |
| 0-D | Local disk ≥ 1 GB free | `df -h taktflow-bms-ml/` | Avail ≥ 1G |
| 0-E | Feature branch created | `git branch -r \| grep feat/ai-phase1-foundation` | Branch present in both repos |
| 0-F | Directory scaffold committed | `ls taktflow-bms-ml/data/` | `fobss`, `bmw-i3-processed`, `norm_stats` present |

---

## Week 1 (Day 1–7): Automated Data Collection Infrastructure

**Goal**: Every frame from `vcan1` is captured, timestamped, versioned, and discoverable
automatically. Manual `candump` sessions end here.

**Milestone**: M1.1 — Automated data capture running on VPS; data catalog populated.

---

### Day 1 — VPS Telemetry Capture Service

**Task**: Deploy `foxbms-capture.service` on the VPS. This is a `systemd` service that
continuously writes `candump -L vcan1` output to `/var/lib/foxbms-telemetry/current.log`.
The `-L` flag writes the native candump log format (timestamp + interface + frame) which
`python-can` can replay directly — this matters for Day 16 offline validation.

**Actions**:
1. SSH to VPS and create `/etc/systemd/system/foxbms-capture.service`:

```ini
[Unit]
Description=foxBMS SIL CAN Telemetry Capture
After=foxbms-plant.service
Requires=foxbms-plant.service

[Service]
Type=simple
ExecStartPre=/bin/bash -c 'mkdir -p /var/lib/foxbms-telemetry'
ExecStart=/usr/bin/candump -L vcan1
StandardOutput=append:/var/lib/foxbms-telemetry/current.log
Restart=always
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
```

2. Enable and start: `systemctl enable foxbms-capture && systemctl start foxbms-capture`
3. Verify frames accumulate: `wc -l /var/lib/foxbms-telemetry/current.log` (watch for 1 minute)

**Deliverable**: `/etc/systemd/system/foxbms-capture.service` deployed and active on VPS.

**Acceptance criteria**:
- `systemctl is-active foxbms-capture` returns `active`
- `wc -l /var/lib/foxbms-telemetry/current.log` increases by ~300 lines/minute (≈5 CAN
  frames/second from plant + sidecar combined)
- Service survives a `systemctl restart foxbms-capture` without leaving orphan `candump` processes

---

### Day 2 — Daily Rotation Timer + Metadata Script

**Task**: Add the rotation half of the telemetry pipeline. Each night at 00:05, the running
`current.log` is gzip-compressed into a dated directory, and a `capture_metadata.json` is
written with provenance (git SHA, frame count, BMS state distribution, CAN IDs seen).

**Actions**:
1. Write `/opt/foxbms-sil/scripts/rotate_telemetry.sh` (rotation logic from plan §Day 1–2).
2. Write `/opt/foxbms-sil/scripts/write_capture_metadata.py` — reads the rotated `.log.gz`,
   counts frames per CAN ID, samples BMS state distribution from 0x220, writes JSON.
3. Deploy `/etc/systemd/system/foxbms-rotate.service` + `foxbms-rotate.timer` (OnCalendar=00:05).
4. Test manually: `systemctl start foxbms-rotate.service` and verify output in
   `/var/lib/foxbms-telemetry/YYYY-MM-DD/`.
5. Commit service files and scripts to `foxbms-posix` under `scripts/vps/`.

**Deliverable**:
- `/var/lib/foxbms-telemetry/2026-03-28/candump_2026-03-28_000500.log.gz` (or test date)
- `/var/lib/foxbms-telemetry/2026-03-28/capture_metadata.json` with all 9 fields populated

**Acceptance criteria**:
- `jq '.frame_count' capture_metadata.json` returns an integer > 0
- `jq '.can_ids_seen | length' capture_metadata.json` returns ≥ 5 distinct IDs
- `jq '.plant_version' capture_metadata.json` contains the current git SHA (not `null`)
- The compressed log is readable: `zcat candump_*.log.gz | head -5` shows candump-format lines

---

### Day 3 — Download and Verify FOBSS Dataset

**Task**: Download the FOBSS dataset (KIT Karlsruhe, CC-BY 4.0, 128 MB). This is the only
dataset that uses real foxBMS 2 hardware — it is the zero-gap validation target for all
models. Without it, GAP-ML-011 (CRITICAL) is permanently open.

**Dataset**: https://publikationen.bibliothek.kit.edu/1000136901
- Real foxBMS 2 hardware, 44-cell NMC pack, ≥50 charge/discharge cycles
- Formats: CSV + JSON metadata per cycle

**Actions**:
1. Download archive into `taktflow-bms-ml/data/fobss/` (manual download or `wget`).
2. Verify SHA256 checksum against the KIT publication page.
3. Inspect directory structure: `find data/fobss/ -name "*.csv" | head -20`
4. Count cycles available: `find data/fobss/ -name "*.csv" | wc -l`
5. Open one CSV; confirm column names — expected: time, voltage, current, temperature, SOC.
6. Commit a `data/fobss/README.md` with: download URL, access date, SHA256, licence statement,
   column descriptions, and cycle count. Do NOT commit the raw data files.

**Deliverable**:
- `data/fobss/` populated with raw FOBSS CSVs (≥50 files)
- `data/fobss/README.md` committed with SHA256 and column map

**Acceptance criteria**:
- `sha256sum --check data/fobss/CHECKSUMS` exits 0 (or manual SHA verified)
- `python3 -c "import pandas as pd; df = pd.read_csv('data/fobss/<first_cycle>.csv'); print(df.shape)"` prints a shape with ≥5 columns
- Column names include at least voltage, current, temperature, and SOC fields

---

### Day 4 — FOBSS Ingest Script Skeleton

**Task**: Write `scripts/ingest_fobss.py` — reads all FOBSS CSV cycles, maps columns to the
canonical 5-feature schema `[V_per_cell_V, I_A, T_avg_degC, T_max_degC, velocity_kmh]`,
and saves to `data/fobss_features.npz` with shape `(N, 5)`.

The per-cell voltage mapping uses `pack_V / 44` (FOBSS is 44S) — same normalization as
the SIL port uses `pack_V / 18`. This is how one set of model weights serves both topologies.

**Actions**:
1. Write `scripts/ingest_fobss.py` with:
   - `load_cycle(csv_path) -> pd.DataFrame` — reads one CSV, renames columns to canonical names
   - `extract_features(df) -> np.ndarray` — computes V_per_cell from pack voltage, fills
     `velocity_kmh=0.0` (FOBSS is stationary bench test)
   - `main()` — iterates all CSVs, concatenates, saves `.npz`
2. Run script: `python3 scripts/ingest_fobss.py`
3. Verify output: `python3 -c "import numpy as np; d=np.load('data/fobss_features.npz'); print(d['X'].shape)"`

**Deliverable**: `data/fobss_features.npz` with key `X` shape `(N, 5)` and `soc` shape `(N,)`.

**Acceptance criteria**:
- `N` ≥ 10,000 rows (FOBSS has ≥50 cycles × hours of data at 1 Hz)
- No NaN values: `np.isnan(d['X']).sum() == 0`
- `V_per_cell` column (index 0) is in range [2.8, 4.2] V (NMC 811 cell range)
- Script completes without error on a fresh run from the top-level `taktflow-bms-ml/` directory

---

### Day 5 — Canonical Feature Extractor Module

**Task**: Write `pipeline/feature_extractor.py` — the single source of truth for feature
extraction. All consumers (sidecar, training scripts, validation scripts, offline audit) will
import from this module. This eliminates the risk of silent feature mismatches between
training and inference (a common source of deployment accuracy gaps).

**Actions**:
1. Write `pipeline/__init__.py` (empty).
2. Write `pipeline/feature_extractor.py` with:
   - `FEATURE_NAMES = ['V_per_cell_V', 'I_A', 'T_avg_degC', 'T_max_degC', 'velocity_kmh']`
   - `extract_from_can_frame(frame_dict, n_cells) -> np.ndarray` — used by the live sidecar
   - `extract_from_dataframe(df, n_cells) -> np.ndarray` — used by training and validation
   - `extract_window(buffer_deque) -> np.ndarray` — returns `(60, 5)` shaped window for LSTM
   - Docstring per function specifying units and coordinate convention
3. Update `scripts/ingest_fobss.py` to import from `pipeline.feature_extractor` instead of
   duplicating the column mapping logic.
4. Write `tests/test_feature_extractor.py` with 5 unit tests:
   - Round-trip: extract → re-normalize → back to original (within 1e-6)
   - Topology independence: 18S and 44S packs with same V/cell produce identical features
   - Window shape: `extract_window` returns exactly `(60, 5)`
   - NaN propagation: NaN input raises `ValueError` (don't pass silently to ONNX)
   - Range clip: V_per_cell outside [2.5, 4.3] raises `ValueError`

**Deliverable**: `pipeline/feature_extractor.py` + `tests/test_feature_extractor.py`

**Acceptance criteria**:
- `pytest tests/test_feature_extractor.py -v` passes all 5 tests
- `python3 -c "from pipeline.feature_extractor import extract_from_dataframe; print('OK')"` exits 0
- `ingest_fobss.py` still produces the same `.npz` after the refactor (bit-identical output)

---

### Day 6 — Smoke-Test Feature Extractor on FOBSS + SIL Capture

**Task**: End-to-end smoke test of the data pipeline: FOBSS raw → feature extractor →
ONNX SOC LSTM inference → compare output to FOBSS SOC ground truth. This is not the
formal accuracy measurement (that is Day 16); it is a sanity check that the pipeline
is wired correctly before the catalog and CI gate are built.

**Actions**:
1. Write `scripts/smoke_test_pipeline.py`:
   - Load `data/fobss_features.npz`
   - Slice first 60 rows as a window: `window = X[:60].reshape(1, 60, 5)`
   - Load normalization stats from `data/norm_stats/soc_lstm_mean.npy` (if they exist already)
     or use the estimated stats from `models/bms/soc_norm_mean.npy` (flag which was used)
   - Run ONNX inference via `onnxruntime.InferenceSession`
   - Print: `ML_SOC={:.2f}%, FOBSS_SOC_at_t60={:.2f}%, diff={:+.2f}%`
2. Also run on one 30-min candump from VPS (if any have been captured since Day 1). Convert
   candump log to feature matrix using `pipeline/feature_extractor.py`.

**Deliverable**: Console output showing at least one SOC prediction alongside its ground truth.

**Acceptance criteria**:
- Script runs without exception
- ML_SOC is a plausible number (0–100% — not NaN, not negative, not >100)
- Print output clearly labels which normalization stats were used (estimated vs computed)
- If FOBSS SOC diff is > 20%, note it explicitly — this documents the known GAP-ML-001 on
  FOBSS, which becomes a baseline measurement in Week 3

---

### Day 7 — Data Catalog + M1.1 Gate

**Task**: Write `data/catalog.json` — a machine-readable manifest of all datasets. This is
queried by `check_data_quality.py` (Day 14) and `run_audit.py` (Phase 4) to discover
datasets without hard-coded paths.

**Actions**:
1. Write `data/catalog.json`:

```json
{
  "schema_version": "1.0",
  "generated": "2026-04-03",
  "datasets": [
    {
      "id": "fobss",
      "name": "FOBSS — foxBMS 2 Hardware Dataset",
      "source": "https://publikationen.bibliothek.kit.edu/1000136901",
      "licence": "CC-BY 4.0",
      "pack_topology": "44S1P",
      "chemistry": "NMC",
      "format": "csv_per_cycle",
      "raw_path": "data/fobss/",
      "processed_path": "data/fobss_features.npz",
      "n_cells": 44,
      "download_date": "2026-04-03",
      "sha256_archive": "<actual SHA256>",
      "status": "ingested"
    },
    {
      "id": "bmw_i3",
      "name": "BMW i3 Driving Dataset (Kollmeyer, 2018)",
      "source": "https://doi.org/10.17632/cp3473x7xv.1",
      "licence": "CC-BY 4.0",
      "pack_topology": "96S1P",
      "chemistry": "NMC",
      "format": "csv_per_trip",
      "raw_path": "data/bms-raw/bmw-i3-driving/",
      "processed_path": "data/bmw-i3-processed/",
      "n_cells": 96,
      "n_trips": 72,
      "status": "pending"
    },
    {
      "id": "sil_telemetry",
      "name": "foxBMS POSIX SIL vcan1 Captures",
      "source": "VPS 152.53.245.209 /var/lib/foxbms-telemetry/",
      "licence": "proprietary",
      "pack_topology": "18S1P",
      "chemistry": "NMC 811",
      "format": "candump_gz",
      "raw_path": "data/sil-captures/",
      "n_cells": 18,
      "status": "live"
    }
  ]
}
```

2. Commit `data/catalog.json` and `data/catalog.schema.json` (JSON Schema for validation).

**M1.1 Gate** — all four checks must pass:

| Check | Command | Required |
|---|---|---|
| Capture service active | `ssh ... systemctl is-active foxbms-capture` | `active` |
| Rotation produced a file | `ssh ... ls /var/lib/foxbms-telemetry/*/` | At least 1 dated directory |
| FOBSS ingested | `python3 -c "import numpy as np; d=np.load('data/fobss_features.npz'); assert d['X'].shape[0] > 10000"` | Passes |
| Catalog valid | `python3 -c "import json; json.load(open('data/catalog.json'))"` | No error |

**Acceptance criteria**: All four M1.1 gate checks pass. Commit with message `feat: M1.1 data collection infrastructure`.

---

## Week 2 (Day 8–14): Normalization Stats + Thermal Pipeline Fix

**Goal**: Fix the two infrastructure bugs that corrupt model inputs — wrong normalization
stats (GAP-ML-002) and broken dT/dt (GAP-ML-004). Ingest BMW i3 dataset and establish
the canonical train/val/test split.

**Milestone**: M1.2 — All external datasets ingested; unified feature extraction pipeline live.

---

### Day 8 — BMW i3 Dataset Inventory

**Task**: Locate the BMW i3 driving dataset locally and map its directory structure. The
dataset has 72 CSV trip files. Before any processing, establish what the raw files look
like: column names, time resolution, units, and any known quality issues (missing rows,
unit discontinuities).

**Actions**:
1. Confirm dataset location: `ls data/bms-raw/bmw-i3-driving/*.csv | wc -l` (expect 72).
2. Write `scripts/inspect_bmw_i3.py`:
   - Open the first 5 CSVs; print shape, column names, min/max of voltage and current
   - Check time resolution (difference between consecutive timestamps)
   - Check for NaN rows: `df.isna().sum()`
   - Check voltage range: does pack voltage divide cleanly by 96 to give NMC cell voltage?
3. Run and save output to `data/bms-raw/bmw-i3-driving/inspection_report.txt`.

**Deliverable**: `inspection_report.txt` showing column names, shapes, NaN counts, and voltage range.

**Acceptance criteria**:
- 72 CSVs confirmed present
- Pack voltage range maps to [2.8, 4.2] V/cell when divided by 96
- Time resolution is ≤ 1 second (dataset is 1 Hz)
- NaN fraction is < 1% per column (trips with > 5% NaN flagged in report for exclusion)

---

### Day 9 — Compute Normalization Statistics from BMW i3 Training Split

**Task**: Write `scripts/compute_norm_stats.py` — compute mean and std from the BMW i3
training split (trips 1–60, chronological order). This replaces the estimated stats
(`mean=[3.698 V, 0.5 A, 25°C, 30°C, 35 km/h]`) with values derived from real data.

**Why trips 1–60**: The BMW i3 dataset is a time-series; chronological split is required to
avoid data leakage. Trips 1–60 train, 61–66 validate, 67–72 test. Never randomize.

**Actions**:
1. Write `scripts/compute_norm_stats.py`:
   - Load trips 1–60 via `pipeline/feature_extractor.py`
   - Compute per-feature mean and std across all samples in those 60 trips
   - Save to `data/norm_stats/soc_lstm_mean.npy` and `data/norm_stats/soc_lstm_std.npy`
   - Write `data/norm_stats/registry.json`:

```json
{
  "soc_lstm": {
    "computed_from": "bmw_i3_trips_1_60",
    "n_samples": 0,
    "date": "2026-04-04",
    "features": ["V_per_cell_V", "I_A", "T_avg_degC", "T_max_degC", "velocity_kmh"],
    "mean": [],
    "std": []
  }
}
```

2. Compare computed stats vs estimated stats; print delta table.
3. Copy `soc_lstm_mean.npy` + `soc_lstm_std.npy` to VPS with `scp` (replaces estimated files).

**Deliverable**: `data/norm_stats/soc_lstm_mean.npy`, `soc_lstm_std.npy`, `registry.json`.

**Acceptance criteria**:
- V/cell mean is in [3.5, 3.9] V (plausible NMC 811 steady-state)
- Current std is in [5, 40] A (BMW i3 peak current ≈ 200 A, but std is lower than peak)
- `data/norm_stats/registry.json` has `n_samples` > 50,000
- VPS `soc_norm_mean.npy` updated — verify with `ssh ... python3 -c "import numpy as np; print(np.load('/opt/foxbms-sil/models/bms/soc_norm_mean.npy'))"`

---

### Day 10 — Root-Cause the Thermal CNN dT/dt Bug

**Task**: Confirm and document GAP-ML-004. The Thermal CNN expects `dT/dt` (temperature
derivative) as one of its 4 input features. The current `plant_model.py` produces cells
at a constant temperature (isothermal — no self-heating), so every `dT/dt` sent to the
CNN is 0.0. A model receiving only zeros for one feature learns nothing useful from it.

Before fixing anything, **reproduce and measure** the bug explicitly.

**Actions**:
1. In `ml_sidecar.py`, add a temporary `print` or `logging.debug` statement inside the
   thermal window update that prints `dT_dt` value every 10 seconds.
2. SSH to VPS, tail the sidecar log for 60 seconds, observe all `dT_dt` values.
3. Open `plant_model.py` and find where cell temperatures are updated — confirm they are
   constant (or near-constant).
4. Write `docs/project/ml-changelog.md` entry documenting exact code paths involved:
   - `plant_model.py` line(s) where temperature is set/not-updated
   - `ml_sidecar.py` line where `dT_dt` is computed (or absent)
5. Remove the debug `print` before committing.

**Deliverable**: `docs/project/ml-changelog.md` entry with exact root cause and affected code lines.

**Acceptance criteria**:
- Log confirms `dT_dt = 0.0` for all 60 seconds of observation
- Root cause identified in `plant_model.py` (not in sidecar — sidecar correctly computes
  derivative of whatever temperature it receives; the problem is the constant input)
- No code changes made today — that is Day 11

---

### Day 11 — Fix Thermal dT/dt in Sidecar + Add Self-Heating to Plant

**Task**: Two coordinated fixes:

1. **Plant model** (if not HITL-locked): add I²R self-heating so cell temperatures evolve.
   The physics: `Q_gen = I² × R_int`, thermal mass `C_th = 50 J/K`, convection `h = 0.5 W/K`.
   `dT/dt = (Q_gen - h × (T - T_ambient)) / C_th`.

   **CRITICAL**: Check HITL locks in `plant_model.py` before touching any line. The
   `PLANT-BE-TABLE` and `PLANT-DECAN-VALID` blocks MUST NOT be modified. The thermal
   model is in a separate section of the file and should not be locked.

2. **Sidecar**: add stateful temperature tracking in `BMSSensorBuffers` to compute
   `dT_dt = (T_now - T_prev) / dt` where `dt = 1.0` s (sidecar tick rate).

**Actions**:
1. Read HITL locks in `plant_model.py` — confirm thermal update code is outside locked regions.
2. In `plant_model.py`, add self-heating physics to the cell temperature update step.
3. In `ml_sidecar.py`, add `self.T_prev` attribute to `BMSSensorBuffers.__init__`, update
   `dT_dt` computation in `append_to_windows()`.
4. Deploy updated `plant_model.py` and `ml_sidecar.py` to VPS.
5. Monitor CAN 0x702 for 120 seconds — thermal risk score should now vary (not be stuck at 0.000).

**Deliverable**:
- `plant_model.py` with I²R self-heating (HITL locks untouched)
- `ml_sidecar.py` with stateful `T_prev` and live `dT_dt`
- `docs/project/ml-changelog.md` entry recording the fix

**Acceptance criteria**:
- `candump vcan1 | grep "702"` shows varying bytes 0–1 over a 2-minute window (not stuck)
- Center cells heat faster than edge cells (a basic physical sanity check on the model)
- HITL lock regions verified unchanged: `git diff -- src/plant_model.py | grep HITL-LOCK` returns empty
- No regression in `candump vcan1 | grep "700"` (SOC LSTM still publishing)

---

### Day 12 — Standardize BMW i3 Train/Val/Test Splits

**Task**: Write `scripts/prepare_bmw_i3.py` — standardize the 72 BMW i3 CSV trips into
fixed, committed, chronological splits and save feature matrices to `data/bmw-i3-processed/`.
This script must be deterministic (same output on every run) so the train/val/test split
is reproducible without relying on random seeds.

**Actions**:
1. Write `scripts/prepare_bmw_i3.py`:
   - Trips 1–60 → `data/bmw-i3-processed/train_X.npy`, `train_soc.npy`
   - Trips 61–66 → `data/bmw-i3-processed/val_X.npy`, `val_soc.npy`
   - Trips 67–72 → `data/bmw-i3-processed/test_X.npy`, `test_soc.npy`
   - Write `data/bmw-i3-processed/split_manifest.json` with: trip filenames per split,
     n_samples per split, date generated, git SHA of the script
2. Apply `pipeline/feature_extractor.py` for column mapping.
3. Apply updated normalization stats from Day 9 (not estimated stats).

**Deliverable**: 6 `.npy` files + `split_manifest.json` in `data/bmw-i3-processed/`.

**Acceptance criteria**:
- `train_X.npy` shape: `(N_train, 5)` where N_train ≥ 50,000
- `test_X.npy` shape: `(N_test, 5)` where N_test ≥ 5,000
- No sample appears in more than one split: verify by trip filename in `split_manifest.json`
- Script is idempotent: running it twice produces bit-identical `.npy` files

---

### Day 13 — Validate BMW i3 Splits + Commit Manifest

**Task**: Spot-check the processed splits for correctness and commit the split manifest.
This day is a quality-control step — resist the urge to skip it and proceed to inference.
A silent error in the split (e.g., wrong column order, off-by-one on trip numbering,
unit mismatch) will corrupt every accuracy measurement in Week 3.

**Actions**:
1. Write `scripts/validate_splits.py`:
   - For each split (train/val/test): load `.npy`, print shape, min/max per feature, NaN count
   - Verify feature order matches `FEATURE_NAMES` in `pipeline/feature_extractor.py`
   - Verify V/cell range [2.8, 4.2] — flag any out-of-range rows
   - Verify current range: abs(I) < 300 A (BMW i3 peak)
   - Compare train vs test distribution (mean ± std per feature — should be similar within 10%)
2. Run and fix any issues found.
3. Commit `split_manifest.json` (but NOT the `.npy` files — too large for git):
   add `data/bmw-i3-processed/*.npy` to `.gitignore`.

**Deliverable**: Passing `validate_splits.py` output + `split_manifest.json` committed.

**Acceptance criteria**:
- Zero NaN rows in any split
- Feature ranges within physical bounds (no cell voltage 0.0 V or 10.0 V)
- `split_manifest.json` present in git with correct trip counts (60/6/6)
- `.npy` files are excluded from git (confirmed by `git status` showing them as ignored)

---

### Day 14 — CI Data Quality Gate + M1.2 Gate

**Task**: Write `scripts/check_data_quality.py` — a script that runs in CI and fails if
the data infrastructure is broken. This prevents the "works on my machine" problem where
accuracy gates pass locally because the datasets are present but fail in CI because they
are not.

**Actions**:
1. Write `scripts/check_data_quality.py` with these 6 checks:

| Check | What it tests |
|---|---|
| FOBSS present | `data/fobss_features.npz` exists and shape[0] > 10,000 |
| BMW i3 splits present | `train_X.npy`, `val_X.npy`, `test_X.npy` all present |
| Norm stats present | `data/norm_stats/soc_lstm_mean.npy` shape == (5,) |
| Feature extractor importable | `from pipeline.feature_extractor import extract_from_dataframe` |
| Catalog valid | `data/catalog.json` parses and has ≥ 3 datasets |
| No NaN in FOBSS | `np.isnan(fobss_X).sum() == 0` |

2. Script exits 0 on pass, 1 on fail, with a clear per-check PASS/FAIL table printed.
3. Add to CI (GitHub Actions or local CI script): `python3 scripts/check_data_quality.py`
   as a `data-quality` job that gates `ml-accuracy` tests.
4. Note: this job should be skipped (not failed) if datasets are not present in the CI
   environment — use `SKIP_DATA_CHECKS=1` env var to allow PR CI to pass without
   the 128 MB download. Only main-branch CI requires datasets.

**M1.2 Gate** — all four checks must pass:

| Check | Command | Required |
|---|---|---|
| FOBSS ingested | `python3 scripts/check_data_quality.py` | All 6 sub-checks PASS |
| BMW i3 splits valid | `python3 scripts/validate_splits.py` | No errors |
| Norm stats from real data | `jq '.soc_lstm.computed_from' data/norm_stats/registry.json` | `"bmw_i3_trips_1_60"` |
| dT/dt live on VPS | `ssh ... candump vcan1 -n 120 \| awk '$3=="702"{print}' \| uniq -c \| wc -l` | ≥ 5 distinct 0x702 values in 2 min |

**Acceptance criteria**: All four M1.2 gate checks pass. Commit with message `feat: M1.2 dataset pipeline and normalization`.

---

## Week 3 (Day 15–21): Baseline Accuracy Measurement

**Goal**: Measure the actual performance of all 5 deployed models on all available datasets.
Record every number. These numbers become the immutable Phase 1 baseline that Phase 2
improvements are compared against.

**Rule**: No model weights change this week. If a model performs badly, document it.
Do not retrain it. Retraining is Phase 2.

**Milestone**: M1.3 — Baseline accuracy measured for all 5 models across all available datasets.

---

### Day 15 — Capture 30-Minute SIL Baseline Session

**Task**: Capture a clean, annotated 30-minute SIL telemetry session for use as the
"SIL baseline" dataset throughout Phases 1 and 2. Clean means: VPS freshly restarted,
no active fault injections, BMS in NORMAL state for the full 30 minutes.

**Actions**:
1. SSH to VPS; restart plant and sidecar services; wait 2 minutes for BMS to reach NORMAL.
2. Start a named capture: `candump -L vcan1 > sil_baseline_30min_2026-04-10.log &`
3. Wait 30 minutes; stop capture.
4. Verify BMS was in NORMAL: parse 0x220 and confirm NORMAL (state byte = 7) for ≥ 95% of frames.
5. SCP log to `data/sil-captures/sil_baseline_30min_2026-04-10.log`.
6. Run `scripts/write_capture_metadata.py` on the captured log.
7. Commit metadata JSON (not the log file — too large).

**Deliverable**: 30-minute candump log locally + `sil_baseline_metadata.json` committed.

**Acceptance criteria**:
- Log contains ≥ 100,000 frames (≈3,333 frames/minute at normal CAN traffic)
- 0x700 (SOC LSTM output) present in every 1-second window
- 0x702 (Thermal CNN output) varies (not stuck at 0.000 — confirms Day 11 fix is live)
- BMS state 0x220 = 7 (NORMAL) for ≥ 95% of the 30 minutes

---

### Day 16 — SOC LSTM Baseline Accuracy — BMW i3 Test Split

**Task**: Measure SOC LSTM accuracy on the BMW i3 test split (trips 67–72). This is the
model's home domain — the data it was trained on. It should be close to the published
1.83% RMSE. Any large deviation indicates an infrastructure problem (wrong normalization,
wrong column order) not an accuracy problem.

**Actions**:
1. Write `scripts/validate_soc_lstm.py` with a `--dataset` argument:
   - `--dataset bmw_i3_test`: loads `data/bmw-i3-processed/test_X.npy` + `test_soc.npy`
   - Runs ONNX inference with sliding 60-step window (stride=1)
   - Computes: RMSE, MAE, max error, 95th-percentile error, bias (mean signed error)
   - Plots: predicted vs actual SOC over time (saved as `validation_plots/soc_bmw_i3_test.png`)
2. Run: `python3 scripts/validate_soc_lstm.py --dataset bmw_i3_test`
3. Record all 5 metrics in `docs/plans/baseline-metrics-phase1.md`.

**Deliverable**: BMW i3 test metrics in baseline report + plot PNG.

**Acceptance criteria (for infrastructure validation — not accuracy gate)**:
- Script runs without exception on BMW i3 test split
- RMSE is plausible (likely 1.5–4.0% — if RMSE > 10%, there is an infrastructure bug,
  check normalization stats are from Day 9 not the estimated ones)
- All 5 metrics printed and recorded in baseline report

---

### Day 17 — SOC LSTM Baseline Accuracy — FOBSS + SIL

**Task**: Run the same `validate_soc_lstm.py` on FOBSS and on the 30-min SIL capture
from Day 15. These are the out-of-domain datasets. FOBSS and SIL errors are expected to
be larger than BMW i3 (that is the whole point of measuring them).

**Actions**:
1. Add `--dataset fobss` and `--dataset sil_30min` modes to `validate_soc_lstm.py`:
   - FOBSS: load `data/fobss_features.npz`, sliding window inference, compare to `soc` array
   - SIL: parse candump log via `python-can`, extract CAN 0x700 (ML SOC) and 0x235 (BMS SOC),
     compute diff directly from the two CAN signals (no re-inference needed)
2. Run both; record metrics.
3. Document the SIL bias explicitly: if ML_SOC = 70.2% and BMS_SOC = 50.0%, bias = +20.2%.
   This confirms GAP-ML-001 as a measured number, not an estimate.

**Deliverable**: FOBSS and SIL metrics added to `docs/plans/baseline-metrics-phase1.md`.

**Acceptance criteria**:
- Three rows in baseline report: BMW i3, FOBSS, SIL — each with RMSE and bias
- SIL bias documented with a sign (+/−) so Phase 2 improvement direction is unambiguous
- If FOBSS RMSE is unavailable (e.g., SOC labels not present in FOBSS), document "SOC labels
  unavailable — use FOBSS for distribution check only" and log as a data gap

---

### Day 18 — Thermal CNN and SOH Transformer Baseline

**Task**: Measure Thermal CNN false positive rate and overtemperature detection latency.
Document SOH Transformer as NOT OPERATIONAL (requires cycling history).

**Actions for Thermal CNN**:
1. Write `scripts/validate_thermal_cnn.py`:
   - Normal operation (no fault): parse 30-min SIL baseline; compute fraction of 0x702
     frames where thermal risk score > 500 (threshold) → this is the False Positive Rate
   - OT fault injection: trigger `TEMP_HIGH` via WebSocket fault API; measure seconds from
     injection to 0x702 crossing the risk threshold → OT Detection Latency
   - WebSocket fault API: `http://152.53.245.209:8080/api/inject_fault`
2. Record: FPR (%), OT detection latency (s).
3. If thermal is still showing dT/dt = 0 despite Day 11 fix, log as a regression and debug.

**Actions for SOH Transformer**:
1. Inspect current CAN 0x701 output on VPS for 60 seconds.
2. Confirm SOH prediction is stuck at a fixed value (confirming "NOT OPERATIONAL" status).
3. Record in baseline report: `SOH_TRANSFORMER: NOT OPERATIONAL — requires cycling history
   (placeholder cycle_count=0.0). Phase 2 Day 45-48 will add synthetic cycle replay.`

**Deliverable**: Thermal CNN FPR and latency in baseline report; SOH status documented.

**Acceptance criteria**:
- Thermal CNN FPR measured (not estimated) from real SIL data
- OT detection latency measured from fault injection
- SOH documented as NOT OPERATIONAL with specific reason (no cycling history)

---

### Day 19 — IsolationForest Baseline: Normal Score + Fault TPR

**Task**: Measure IsolationForest anomaly score at normal operating conditions and True
Positive Rate across 5 fault scenarios.

**Actions**:
1. Write `scripts/validate_anomaly.py`:
   - Parse 30-min baseline SIL log; extract 0x705 anomaly score for all frames in NORMAL state
   - Compute: mean anomaly score, 95th percentile, fraction > 0.5 (should be 0 in normal operation)
   - For 5 fault scenarios (OV, OT, OC, cell imbalance, recovery from fault): inject via WebSocket,
     record anomaly score trajectory, compute TPR as fraction of frames with score > 0.5 during fault
2. Record baseline:
   - Normal score mean (expected ~0.36 based on current known gap)
   - TPR per fault type
   - Overall TPR across all fault types

**Deliverable**: IsolationForest baseline metrics in `docs/plans/baseline-metrics-phase1.md`.

**Acceptance criteria**:
- Normal score measured (any value — this is just measurement)
- TPR measured for at least 3 of the 5 fault scenarios (some may be hard to inject consistently)
- Numbers are reproducible: run twice; scores should be within 0.02 of each other

---

### Day 20 — RUL Transformer Status + Compile Full Baseline Table

**Task**: Document RUL Transformer status (NOT DEPLOYED) and compile all Phase 1 baseline
numbers into the final baseline table.

**Actions**:
1. Confirm `rul_transformer.onnx` does not exist in `models/bms/`.
2. Document: `RUL_TRANSFORMER: NOT DEPLOYED — ONNX file absent. Phase 2 Day 49–52 will
   implement predict_rul() and deploy initial ONNX model.`
3. Compile full baseline table in `docs/plans/baseline-metrics-phase1.md`:

| Model | Dataset | Metric | Value | Status |
|---|---|---|---|---|
| SOC LSTM | BMW i3 test | RMSE (%) | [measured] | |
| SOC LSTM | BMW i3 test | Bias (%) | [measured] | |
| SOC LSTM | FOBSS | RMSE (%) | [measured] | |
| SOC LSTM | SIL 30-min | Bias (%) | [measured] | |
| Thermal CNN | SIL normal | FPR (%) | [measured] | |
| Thermal CNN | SIL OT fault | Detection latency (s) | [measured] | |
| IsolationForest | SIL normal | Mean anomaly score | [measured] | |
| IsolationForest | SIL faults | TPR (%) | [measured] | |
| SOH Transformer | SIL | Status | NOT OPERATIONAL | No cycling history |
| RUL Transformer | — | Status | NOT DEPLOYED | No ONNX file |

4. For each measured row: assign PASS/FAIL verdict against Phase 2 targets from `plan-ai-180-day.md`.

**Deliverable**: Complete baseline table with all PASS/FAIL verdicts.

**Acceptance criteria**:
- Every deployed model (SOC LSTM, Thermal CNN, IsolationForest) has at least one measured metric
- No placeholder values like `TBD` or `[to be measured]` remain in deployed-model rows
- SOH and RUL rows explicitly say NOT OPERATIONAL / NOT DEPLOYED with reason

---

### Day 21 — Lock Baseline Report + M1.3 Gate

**Task**: Finalize and lock `docs/plans/baseline-metrics-phase1.md`. Once this file is
committed, its measured values become the immutable reference. Phase 2 improvements are
measured against these numbers.

**Actions**:
1. Review all measured values; check for obvious errors (SOC RMSE of 0.001% is suspicious;
   anomaly score of 0.999 at normal is suspicious).
2. Add a `## Verdict Summary` section at the top of the baseline report:

```
P0 GAPS (must fix in Phase 2):
  - SOC LSTM SIL bias: +XX.XX% (target: ≤ ±3%)
  - IsolationForest normal score: X.XX (target: < 0.15)
  - Thermal CNN FPR: XX% (target: ≤ 2%)

P1 GAPS (fix in Phase 2):
  - SOH Transformer: NOT OPERATIONAL
  - RUL Transformer: NOT DEPLOYED

HOLDS (deferred):
  - BMW i3 RMSE anti-regression gate: Phase 2 CI gate
```

3. Add HITL-LOCK comment markers to the measured values table (so Phase 2 work cannot
   accidentally overwrite baseline numbers):
   ```
   <!-- HITL-LOCK START:PHASE1-BASELINE -->
   [baseline table]
   <!-- HITL-LOCK END:PHASE1-BASELINE -->
   ```
4. Commit with message `docs: lock Phase 1 baseline metrics (M1.3)`.

**M1.3 Gate** — all four checks must pass:

| Check | Required |
|---|---|
| All deployed models measured | SOC LSTM, Thermal CNN, IsolationForest each have ≥ 1 metric |
| Non-deployed models documented | SOH = NOT OPERATIONAL, RUL = NOT DEPLOYED with reasons |
| Baseline report committed | `docs/plans/baseline-metrics-phase1.md` present in git |
| Verdict summary present | P0/P1/HOLDS sections populated |

**Acceptance criteria**: All four M1.3 gate checks pass. Commit with message `feat: M1.3 baseline accuracy measurement complete`.

---

## Week 4 (Day 22–30): CI Metrics Gate + Phase 1 Close

**Goal**: Operationalize the baseline — wire it into CI so regressions are caught
automatically. Build model registry and human-readable guides. Close Phase 1.

**Milestone**: M1.4 — CI metrics gate operational; baseline report published and locked.

---

### Day 22 — Write ML Accuracy Test Skeleton

**Task**: Write `tests/test_ml_accuracy.py` — a pytest test suite that re-measures SOC
LSTM RMSE on the BMW i3 test split and fails if it regresses beyond the Phase 1 baseline.

This is an anti-regression gate, not a Phase 2 improvement gate. It prevents model
weight changes from silently degrading accuracy.

**Actions**:
1. Write `tests/test_ml_accuracy.py`:

```python
# tests/test_ml_accuracy.py
import numpy as np
import onnxruntime as ort
import pytest
import os

SKIP_REASON = "Dataset not available in CI — set FOXBMS_DATA_DIR to enable"
DATA_DIR = os.environ.get("FOXBMS_DATA_DIR", "")

@pytest.mark.skipif(not DATA_DIR, reason=SKIP_REASON)
def test_soc_lstm_bmw_i3_rmse():
    """SOC LSTM RMSE on BMW i3 test split must not regress beyond Phase 1 baseline."""
    test_X = np.load(f"{DATA_DIR}/bmw-i3-processed/test_X.npy")
    test_soc = np.load(f"{DATA_DIR}/bmw-i3-processed/test_soc.npy")
    sess = ort.InferenceSession("models/bms/soc_lstm.onnx")
    # ... sliding window inference ...
    rmse = np.sqrt(np.mean((predictions - test_soc[59:]) ** 2))
    PHASE1_BASELINE_RMSE = 2.0  # set from Day 16 measurement (±0.5% tolerance)
    assert rmse < PHASE1_BASELINE_RMSE + 0.5, \
        f"SOC LSTM BMW i3 RMSE={rmse:.3f}% regressed beyond baseline {PHASE1_BASELINE_RMSE}%"

@pytest.mark.skipif(not DATA_DIR, reason=SKIP_REASON)
def test_soc_lstm_no_nan_output():
    """SOC LSTM must never produce NaN — hard gate regardless of data."""
    # ... test with zero-filled window ...
    pass
```

2. Fill in the sliding window inference loop (60 steps, stride=1).
3. Add `test_soc_lstm_no_nan_output` and `test_anomaly_score_plausible` as always-run
   tests (no dataset needed — use synthetic inputs).

**Deliverable**: `tests/test_ml_accuracy.py` with 3 tests.

**Acceptance criteria**:
- `pytest tests/test_ml_accuracy.py -v` without `FOXBMS_DATA_DIR` set: 2 tests skipped (no dataset), 1 passed (no-NaN)
- `pytest tests/test_ml_accuracy.py -v` with `FOXBMS_DATA_DIR` set: all 3 pass
- RMSE threshold in the test is set to the actual Day 16 measurement + 0.5% tolerance

---

### Day 23 — Wire CI Accuracy Gate into Pipeline

**Task**: Add `check_data_quality.py` and `test_ml_accuracy.py` as a named `ml-accuracy`
CI job that runs on pushes to `main` but not on PRs (too large for PR CI).

**Actions**:
1. If using GitHub Actions: add `.github/workflows/ml-accuracy.yml`:

```yaml
name: ML Accuracy Gate
on:
  push:
    branches: [main]
jobs:
  ml-accuracy:
    runs-on: ubuntu-latest
    env:
      FOXBMS_DATA_DIR: /data/foxbms-ml
    steps:
      - uses: actions/checkout@v4
      - name: Restore ML datasets from cache
        uses: actions/cache@v4
        with:
          path: /data/foxbms-ml
          key: foxbms-ml-datasets-v1
      - name: Data quality gate
        run: python3 scripts/check_data_quality.py
      - name: ML accuracy gate
        run: pytest tests/test_ml_accuracy.py -v --tb=short
```

2. If not using GitHub Actions: add to the existing CI shell script as a conditional block
   (only runs on `main`).
3. Commit the CI configuration.

**Deliverable**: CI configuration that runs `ml-accuracy` job on main pushes.

**Acceptance criteria**:
- CI job definition committed
- Job skips gracefully when dataset cache is missing (no false failures on dataset-less machines)
- Job is documented in `docs/plans/data-collection-guide.md` (Day 27)

---

### Day 24 — End-to-End CI Gate Test

**Task**: Deliberately break a model metric and confirm the CI gate catches it.
This validates that the gate actually works (not just that it passes when it should).

**Actions**:
1. Create a branch `test/ci-gate-validation`.
2. In `tests/test_ml_accuracy.py`, temporarily change the RMSE threshold to an impossibly
   tight value (e.g., `PHASE1_BASELINE_RMSE = 0.001`).
3. Run `pytest tests/test_ml_accuracy.py -v` locally — confirm it FAILS.
4. Revert the threshold to the correct value — confirm it PASSES.
5. Delete the test branch. Commit nothing from this day (it is a verification exercise).

**Deliverable**: Written confirmation in `docs/project/ml-changelog.md` that the CI gate
was adversarially tested and behaved correctly.

**Acceptance criteria**:
- Log entry in `ml-changelog.md` states: "CI gate tested: tight threshold → FAIL, correct threshold → PASS"
- No temporary changes committed to main or feat branch
- `pytest tests/test_ml_accuracy.py -v` currently PASSES on the feature branch

---

### Day 25 — Model Registry JSON

**Task**: Write `models/registry.json` — the authoritative record of every deployed model
version, its training provenance, Phase 1 baseline metrics, and whether it is currently
deployed to VPS.

**Actions**:
1. Write `models/registry.json`:

```json
{
  "schema_version": "1.0",
  "last_updated": "2026-04-20",
  "models": [
    {
      "id": "soc_lstm_v1",
      "file": "models/bms/soc_lstm.onnx",
      "architecture": "BiLSTM-128-64",
      "input_shape": [1, 60, 5],
      "training_data": ["bmw_i3_trips_1_60", "nasa_pcoE_7565_cycles"],
      "norm_stats": "data/norm_stats/soc_lstm_mean.npy",
      "phase1_baseline": {
        "bmw_i3_test_rmse_pct": null,
        "fobss_rmse_pct": null,
        "sil_bias_pct": null
      },
      "deployed_vps": true,
      "can_output_id": "0x700",
      "status": "operational"
    },
    {
      "id": "thermal_cnn_v1",
      "file": "models/bms/thermal_cnn.onnx",
      "architecture": "1D-CNN",
      "input_shape": [1, 30, 4],
      "phase1_baseline": {
        "normal_fpr_pct": null,
        "ot_detection_latency_s": null
      },
      "deployed_vps": true,
      "can_output_id": "0x702",
      "status": "operational_after_day11_fix"
    },
    {
      "id": "soh_transformer_v1",
      "file": "models/bms/soh_transformer.onnx",
      "phase1_baseline": {},
      "deployed_vps": true,
      "can_output_id": "0x701",
      "status": "not_operational",
      "reason": "requires_cycling_history"
    },
    {
      "id": "isolation_forest_v1",
      "file": "src/anomaly_model.pkl",
      "phase1_baseline": {
        "normal_mean_score": null,
        "fault_tpr_pct": null
      },
      "deployed_vps": true,
      "can_output_id": "0x705",
      "status": "operational"
    },
    {
      "id": "rul_transformer_v1",
      "file": null,
      "deployed_vps": false,
      "can_output_id": "0x704",
      "status": "not_deployed",
      "reason": "onnx_file_absent"
    }
  ]
}
```

2. Fill the `null` baseline metric fields from the measurements made in Week 3.

**Deliverable**: `models/registry.json` committed with all Phase 1 baseline fields populated.

**Acceptance criteria**:
- `python3 -c "import json; r=json.load(open('models/registry.json')); assert len(r['models'])==5"` exits 0
- No `null` values in `phase1_baseline` for SOC LSTM (which has actual measurements)
- SOH and RUL entries have `status` = `"not_operational"` / `"not_deployed"` with reasons

---

### Day 26 — Fill Baseline Metrics Phase 2 Template

**Task**: Fill the Phase 2 targets template (`docs/plans/baseline-metrics-phase2.md`) with
the Phase 1 measured baselines. This document will be the acceptance evidence for Phase 2.

The Phase 2 template was created with placeholder values. Today: replace the Phase 1 column
with actual measured values, so Phase 2 has a clear starting point.

**Actions**:
1. Open `docs/plans/baseline-metrics-phase2.md`.
2. For each row in the SOC LSTM section: fill in the Phase 1 baseline from Week 3 measurements.
3. For Thermal CNN: fill FPR and detection latency.
4. For IsolationForest: fill normal score and TPR.
5. SOH and RUL rows: mark "NOT OPERATIONAL / NOT DEPLOYED — Phase 2 target is to deploy".
6. Do NOT fill the "Phase 2 measured" column — that is Phase 2 work.

**Deliverable**: `baseline-metrics-phase2.md` with Phase 1 column populated.

**Acceptance criteria**:
- No `___.___` placeholders remain in the "Phase 1 Baseline" column
- Phase 2 target column is unchanged (do not move targets)
- HITL-LOCK markers are not present in this file (it is not a locked file)

---

### Day 27 — Data Collection Guide

**Task**: Write `docs/plans/data-collection-guide.md` — a human-readable guide explaining
how the data collection infrastructure works, how to retrieve SIL captures, and how to
add a new dataset to the catalog.

**Audience**: A future engineer (or future-you) who needs to add a new dataset or debug
why the VPS captures stopped. They should not need to read the plan or the scripts to
understand the system.

**Content**:
1. **Architecture diagram**: plant → vcan1 → candump → current.log → daily rotation → dated gz + metadata
2. **How to retrieve a capture from VPS**: `scp` command, file path pattern, metadata fields
3. **How to add a dataset to the catalog**: JSON schema, required fields, how `check_data_quality.py` uses it
4. **How to run the feature extractor**: example code snippet for `pipeline/feature_extractor.py`
5. **Troubleshooting**: foxbms-capture stopped (why, how to restart), metadata JSON missing a field

**Deliverable**: `docs/plans/data-collection-guide.md` committed.

**Acceptance criteria**:
- Document is ≤ 300 lines (if longer, it is over-documented)
- Contains the `scp` retrieval command with the correct VPS path
- Contains a complete example of adding a new dataset to `catalog.json`

---

### Day 28 — Metrics Interpretation Guide

**Task**: Write `docs/plans/metrics-interpretation-guide.md` — explains what the baseline
metrics mean, how to interpret RMSE vs bias vs FPR, and what the Phase 2 targets require.

**Audience**: A customer or product manager reading the baseline report and asking "is this
good?" They should understand whether 1.83% RMSE is impressive or disappointing.

**Content**:
1. **SOC LSTM RMSE**: what it means in km of range uncertainty for a BMW i3; the 3% target
   means ≈8 km uncertainty on a 260 km range vehicle
2. **SOC bias**: why +20% bias is more dangerous than 20% RMSE (systematic, not random)
3. **Anomaly score**: IsolationForest score of 0 = certain normal, 1 = certain anomaly;
   0.36 at normal means "mildly anomalous" — why this is problematic
4. **TPR vs FPR trade-off**: sensitivity vs specificity; why Thermal CNN FPR matters more
   than TPR in a system that already has deterministic fault detection
5. **NOT OPERATIONAL vs NOT DEPLOYED**: what the difference means and what it costs the customer

**Deliverable**: `docs/plans/metrics-interpretation-guide.md` committed.

**Acceptance criteria**:
- Contains a concrete km-range-uncertainty calculation for SOC RMSE
- Contains an explanation of SOC bias vs RMSE using plain language
- ≤ 200 lines

---

### Day 29 — Final Review and Report Completeness Check

**Task**: Read every Phase 1 deliverable and confirm it is complete before the M1.4 gate.
This is not a new development day — it is a quality control pass.

**Checklist** (go through each item; fix any gaps before Day 30):

- [ ] `foxbms-capture.service` active on VPS: verify with `ssh ... systemctl is-active`
- [ ] At least 7 days of telemetry captured: `ssh ... ls /var/lib/foxbms-telemetry/ | wc -l`
- [ ] `data/fobss_features.npz` present and shape[0] > 10,000
- [ ] `data/bmw-i3-processed/split_manifest.json` committed
- [ ] `data/norm_stats/registry.json` shows `computed_from: bmw_i3_trips_1_60`
- [ ] Thermal dT/dt active: 0x702 varies on VPS
- [ ] `docs/plans/baseline-metrics-phase1.md` locked with HITL-LOCK markers
- [ ] All 5 model rows in baseline report complete (no TBD)
- [ ] `models/registry.json` present with Phase 1 baseline fields populated
- [ ] `tests/test_ml_accuracy.py` passes locally (RMSE threshold = actual + 0.5%)
- [ ] CI `ml-accuracy` job committed
- [ ] `docs/plans/data-collection-guide.md` committed
- [ ] `docs/plans/metrics-interpretation-guide.md` committed
- [ ] `data/catalog.json` committed with 3 datasets

For any unchecked item: fix it today. Day 30 is the gate day, not the fix day.

**Deliverable**: All 14 checklist items checked off and logged in `docs/project/ml-changelog.md`.

**Acceptance criteria**: Zero unchecked items at end of day.

---

### Day 30 — M1.4 Phase 1 Close

**Task**: Run the formal Phase 1 exit gate (all 11 criteria), merge the feature branch to
`main`, and write a lessons-learned entry.

**M1.4 Exit Gate** — all 11 criteria must pass before merging:

| # | Criterion | Verification |
|---|---|---|
| 1 | Automated SIL telemetry capture active | `ssh ... systemctl is-active foxbms-capture` = `active` |
| 2 | ≥ 7 days of telemetry captured and rotated | `ssh ... ls /var/lib/foxbms-telemetry/ \| wc -l` ≥ 7 |
| 3 | FOBSS dataset ingested | `python3 -c "import numpy as np; d=np.load('data/fobss_features.npz'); assert d['X'].shape[0]>10000"` |
| 4 | BMW i3 splits committed (manifest) | `git show HEAD:data/bmw-i3-processed/split_manifest.json` exists |
| 5 | Normalization stats from real data | `jq '.soc_lstm.computed_from' data/norm_stats/registry.json` = `"bmw_i3_trips_1_60"` |
| 6 | Thermal dT/dt active | 0x702 has ≥ 5 distinct values in 2-min VPS candump window |
| 7 | Baseline report locked | `grep "HITL-LOCK" docs/plans/baseline-metrics-phase1.md` returns matches |
| 8 | All 5 models measured | No `null` in registry for deployed models |
| 9 | CI accuracy gate committed | `.github/workflows/ml-accuracy.yml` or equivalent present |
| 10 | Model registry present | `python3 -c "import json; json.load(open('models/registry.json'))"` exits 0 |
| 11 | Guides committed | Both `data-collection-guide.md` and `metrics-interpretation-guide.md` present |

**Actions**:
1. Run all 11 gate checks; fix any failures (they should have been found on Day 29).
2. Create PR from `feat/ai-phase1-foundation` → `main` with the baseline metrics table in
   the PR description.
3. Merge PR after all CI checks pass.
4. Write lessons-learned entry in `docs/lessons-learned/embedded/bringup.md`:
   ```
   2026-04-25 — Phase 1 AI Infrastructure
   Context: First time establishing ML data pipeline for foxBMS POSIX.
   Mistake: Thermal CNN was deployed with dT/dt = 0 for weeks before being noticed.
   Fix: Add infrastructure smoke test (Day 6 smoke_test_pipeline.py) on every model
        deployment — catches silent broken inputs before they go to production.
   Principle: Deploy to measure, not to ship. A model producing a constant output is
              not "operational" — it is a silent failure.
   ```
5. Tag: `git tag -a ml-phase1-baseline -m "Phase 1 baseline metrics locked (M1.4)"`.

**Deliverable**: `feat/ai-phase1-foundation` merged to `main`; tag `ml-phase1-baseline` created.

**Acceptance criteria**:
- All 11 M1.4 gate criteria pass
- PR merged without force-push
- `git tag ml-phase1-baseline` exists on the merge commit
- Lessons-learned entry committed to `docs/lessons-learned/embedded/bringup.md`
- `docs/project/ml-changelog.md` updated with Phase 1 close entry

---

## Quick Reference: Phase 1 Deliverable Map

| Day | Key Deliverable | Repo |
|---|---|---|
| 1 | `foxbms-capture.service` active on VPS | foxbms-posix |
| 2 | Daily rotation + `capture_metadata.json` | foxbms-posix |
| 3 | FOBSS CSVs downloaded; `data/fobss/README.md` | taktflow-bms-ml |
| 4 | `data/fobss_features.npz` shape (N>10000, 5) | taktflow-bms-ml |
| 5 | `pipeline/feature_extractor.py` + 5 unit tests | taktflow-bms-ml |
| 6 | Smoke test: SOC prediction printed from FOBSS | taktflow-bms-ml |
| 7 | `data/catalog.json`; **M1.1 gate** | taktflow-bms-ml |
| 8 | BMW i3 inspection report | taktflow-bms-ml |
| 9 | `data/norm_stats/` from real BMW i3 training split | taktflow-bms-ml |
| 10 | dT/dt bug root-caused and documented | foxbms-posix |
| 11 | Thermal dT/dt fix live on VPS; plant self-heating | foxbms-posix |
| 12 | BMW i3 train/val/test `.npy` files | taktflow-bms-ml |
| 13 | `split_manifest.json` committed | taktflow-bms-ml |
| 14 | `check_data_quality.py`; **M1.2 gate** | taktflow-bms-ml |
| 15 | 30-min SIL baseline capture + metadata | VPS + foxbms-posix |
| 16 | SOC LSTM BMW i3 RMSE and bias measured | taktflow-bms-ml |
| 17 | SOC LSTM FOBSS and SIL metrics measured | taktflow-bms-ml |
| 18 | Thermal CNN FPR + latency; SOH documented | taktflow-bms-ml |
| 19 | IsolationForest normal score + TPR | taktflow-bms-ml |
| 20 | RUL documented; full baseline table compiled | foxbms-posix |
| 21 | Baseline report locked; **M1.3 gate** | foxbms-posix |
| 22 | `tests/test_ml_accuracy.py` with 3 tests | taktflow-bms-ml |
| 23 | CI `ml-accuracy` job configured | both |
| 24 | CI gate adversarially tested | (no commit) |
| 25 | `models/registry.json` with Phase 1 baselines | taktflow-bms-ml |
| 26 | `baseline-metrics-phase2.md` Phase 1 column filled | foxbms-posix |
| 27 | `data-collection-guide.md` | foxbms-posix |
| 28 | `metrics-interpretation-guide.md` | foxbms-posix |
| 29 | All 14 checklist items verified clean | both |
| 30 | PR merged; tag `ml-phase1-baseline`; **M1.4 gate** | both |
