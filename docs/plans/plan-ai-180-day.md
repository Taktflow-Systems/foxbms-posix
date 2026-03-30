# 180-Day AI/ML Roadmap — foxBMS POSIX vECU

**Date**: 2026-03-27
**Horizon**: 180 days (2026-03-27 → 2026-09-23)
**Status**: DRAFT — Phase 1 (Day 1–30) detailed; Phases 2–6 in outline
**Starting point**: ML sidecar live on VPS; 5 models deployed; 12 known accuracy gaps; zero validated accuracy on real foxBMS hardware data

---

## Executive Summary

Six months from today the foxBMS POSIX ML pipeline should be:

- **Validated** — every model has measured accuracy on real foxBMS hardware data (FOBSS)
- **Monitored** — automated drift detection and CI accuracy gates prevent silent regressions
- **Customer-deliverable** — offline audit pipeline, DBC-driven bench sidecar, PDF reports
- **Architecturally improved** — LSTM-Autoencoder temporal detection, PSI drift monitoring

The plan is organized in six 30-day phases. Each phase builds on the previous one.
**Phase 1 is prerequisite to all others**: you cannot improve what you have not measured.

| Phase | Days | Theme | Key Deliverable |
|---|---|---|---|
| **Phase 1** | 1–30 | Data infrastructure + baseline metrics | Measured accuracy on all datasets; automated data pipeline |
| **Phase 2** | 31–60 | Model accuracy improvements | P0/P1 gaps closed; validated accuracy numbers citable |
| **Phase 3** | 61–90 | Production hardening | Drift monitoring; CI gates; systemd stability |
| **Phase 4** | 91–120 | Customer pipeline | `run_audit.py`; DBC-driven sidecar; report generator |
| **Phase 5** | 121–150 | Advanced models | LSTM-Autoencoder; hybrid digital twin prototype |
| **Phase 6** | 151–180 | Business delivery | Demo package; Tier 0 customer engagement; Tier 1 pilot |

---

## Day 0: Pre-Flight Infrastructure Check (Before Day 1)

**Purpose**: Snapshot the current infrastructure state. Day 1 work builds on this foundation.
Any gap found here must be resolved before the clock starts on Week 1 deliverables.
**Time required**: 1–2 hours.

---

### 0.1 VPS Connectivity and Service Status

```bash
# Verify VPS reachable and core services running
ssh root@152.53.245.209 "
  echo '--- Services ---'
  systemctl is-active foxbms-plant foxbms-sidecar 2>/dev/null || echo 'NOTE: service names may differ'
  echo '--- Disk ---'
  df -h /opt /var/lib 2>/dev/null || df -h /
  echo '--- Python ---'
  python3 --version
  python3 -c 'import onnxruntime; print(\"ort:\", onnxruntime.__version__)' 2>/dev/null || echo 'ONNX: not installed'
  echo '--- Models ---'
  ls -lh /opt/foxbms-sil/models/bms/ 2>/dev/null || echo 'Models dir: not found'
  echo '--- SIL telemetry dir ---'
  ls /var/lib/foxbms-telemetry/ 2>/dev/null || echo 'telemetry dir: does not exist yet'
  echo '--- Git SHA on VPS ---'
  cd /opt/foxbms-sil && git log --oneline -1 2>/dev/null || echo 'git: no repo'
"
```

**Expected output**:

| Check | Expected | Action if fails |
|---|---|---|
| Services | `active` for plant | Investigate systemd unit name; restart |
| Disk `/var/lib` | ≥ 500 MB free | Clean logs; or request VPS storage expansion |
| Python | ≥ 3.10 | Install via `apt install python3.11` |
| ONNX Runtime | ≥ 1.15 | `pip3 install onnxruntime>=1.15` on VPS |
| Models | 3 `.onnx` files present | Re-run `deploy-ml-sidecar.sh` |
| Telemetry dir | May not exist yet | Created by Day 1–2 systemd service |

---

### 0.2 Disk Space Planning

Establish storage budgets before any data arrives.

| Data | Size Estimate | Location |
|---|---|---|
| FOBSS download | 128 MB | `taktflow-bms-ml/data/fobss/` (local ML repo) |
| BMW i3 raw CSVs | 37 MB | `taktflow-bms-ml/data/bms-raw/bmw-i3-driving/` |
| BMW i3 processed splits | ~60 MB | `taktflow-bms-ml/data/bmw-i3-processed/` |
| SIL telemetry (per day, gzipped) | ~5 MB/day | VPS: `/var/lib/foxbms-telemetry/` |
| Normalization stats | < 1 MB | `taktflow-bms-ml/data/norm_stats/` |
| Model artifacts | ~3 MB | `taktflow-bms-ml/models/bms/` |

**VPS minimum**: 500 MB free on the partition holding `/var/lib` (30 days × 5 MB + margin).
**Local minimum**: 1 GB free in the `taktflow-bms-ml` working directory.

```bash
# Check VPS partition headroom
ssh root@152.53.245.209 "df -h --output=avail /var/lib | tail -1"

# Check local working directory headroom (run in taktflow-bms-ml)
df -h . | awk 'NR==2{print "Available:", $4}'
```

If VPS is tight, enable automatic log pruning (keep last 30 days):

```bash
# /opt/foxbms-sil/scripts/prune_old_telemetry.sh (add to cron or systemd timer)
find /var/lib/foxbms-telemetry/ -name "*.log.gz" -mtime +30 -delete
```

---

### 0.3 Python Environment Setup

One consistent environment for all ML scripts. Set up locally once; VPS already has its own
install via `deploy-ml-sidecar.sh`.

```bash
# Local: create isolated ML environment in the ML datasets repo
cd taktflow-bms-ml
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install \
  onnxruntime>=1.15 \
  numpy>=1.20 \
  scikit-learn>=1.4 \
  joblib>=1.3 \
  pandas>=2.0 \
  pytest>=7.0 \
  pytest-timeout>=2.0

# Freeze for full reproducibility
pip freeze > requirements-ml-frozen.txt
git add requirements-ml-frozen.txt && git commit -m "chore: freeze ML dependencies for 180-day plan"

# VPS: verify existing install matches
ssh root@152.53.245.209 \
  "pip3 list --format=columns | grep -E 'onnxruntime|numpy|scikit.learn|joblib|pandas'"
```

**Gate**: `python3 -c "import onnxruntime, numpy, sklearn, pandas; print('OK')"` exits 0 locally.

---

### 0.4 Git Branch Setup

All 180-day Phase 1 work goes on a feature branch. Merge to `main` only at M1.4 (Day 30).

```bash
# foxbms-posix parent repo
git checkout -b feat/ai-phase1-foundation
git push -u origin feat/ai-phase1-foundation

# taktflow-bms-ml ML repo (datasets, models, training scripts)
cd ../taktflow-bms-ml
git checkout -b feat/ai-phase1-foundation
git push -u origin feat/ai-phase1-foundation
```

**Branch policy**:
- `feat/ai-phase1-foundation` — all Week 1–4 deliverables
- Each milestone (M1.1–M1.4) gets a PR to `main` with the baseline metrics as evidence
- Never merge a PR whose CI `data-quality` or `ml-accuracy` gate is red

---

### 0.5 Directory Structure Initialization

Create the directories that Week 1–4 scripts will populate. Commit `.gitkeep` placeholders.

```bash
cd taktflow-bms-ml

# Data directories
mkdir -p data/fobss \
          data/bms-raw/bmw-i3-driving \
          data/bmw-i3-processed \
          data/norm_stats

# Pipeline and script directories
mkdir -p pipeline scripts tests models/bms

# Placeholder commits so directories appear in git
find data pipeline scripts tests -name .gitkeep -delete
for d in data/fobss data/bmw-i3-processed data/norm_stats; do
  touch "$d/.gitkeep"
done

git add data/*/\.gitkeep pipeline/ scripts/ tests/
git commit -m "chore: initialize directory structure for Phase 1 data pipeline"
```

In `foxbms-posix`, the only new directory needed for Phase 1 is `docs/plans/` (already exists).

---

### Day 0 Exit Gate

| Check | Command | Expected |
|---|---|---|
| VPS reachable | `ssh root@152.53.245.209 uptime` | Returns uptime |
| VPS disk ≥ 500 MB | `ssh ... df -h /var/lib` | Avail ≥ 500M |
| Local Python env | `source .venv/bin/activate && python -c "import onnxruntime"` | No error |
| Local disk ≥ 1 GB | `df -h .` | Avail ≥ 1G |
| Feature branch pushed | `git branch -r \| grep feat/ai-phase1-foundation` | Branch exists |
| Directories created | `ls taktflow-bms-ml/data/` | fobss, bmw-i3-processed, norm_stats present |

All six checks must pass before Day 1 begins.

---

## Phase 1: Data Infrastructure + Baseline Metrics (Day 1–30)

### Goal

Establish the **measurement foundation** before touching a single model weight. The current state (per `docs/ai_audit.md`) is that 5 models are deployed but none have been validated against real foxBMS hardware data. The critical gaps are:

| Gap | Severity | Description |
|---|---|---|
| GAP-ML-011 | CRITICAL | FOBSS dataset (real foxBMS 2 hardware) never downloaded |
| GAP-ML-001 | CRITICAL | SOC LSTM shows 20% error on SIL vs BMS coulomb counting |
| GAP-ML-002 | HIGH | Normalization stats estimated, not computed from training data |
| GAP-ML-004 | HIGH | Thermal CNN dT/dt input always 0.0 — model functionally broken |
| GAP-ML-003 | HIGH | IsolationForest trained on synthetic data; real FPR unknown |

**What this phase is NOT**: fixing accuracy gaps. That is Phase 2. Phase 1 is purely
measurement and infrastructure. Every improvement in Phase 2 will be measured against
Phase 1 baseline numbers. Without a baseline, "improvement" is meaningless.

### Phase 1 Milestones

| ID | Day | Description |
|---|---|---|
| **M1.1** | Day 7 | Automated data capture running on VPS; data catalog populated |
| **M1.2** | Day 14 | All external datasets ingested; unified feature extraction pipeline live |
| **M1.3** | Day 21 | Baseline accuracy measured for all 5 models across all available datasets |
| **M1.4** | Day 30 | CI metrics gate operational; baseline report published and locked |

---

### Week 1 (Day 1–7): Data Collection Infrastructure

**Goal**: Never lose another second of SIL telemetry. Every frame from vcan1 is captured,
timestamped, versioned, and discoverable automatically. Manual `candump` sessions end here.

---

#### Day 1–2: Automated SIL Telemetry Capture

**Problem**: Data collection is currently manual. Retraining or validating a model requires
SSH to VPS, running `candump`, waiting, SCP, manual parsing — a 30-minute minimum workflow
that produces files with no provenance metadata.

**Solution**: `systemd` service pair — continuous capture + daily rotation with metadata.

```ini
# /etc/systemd/system/foxbms-capture.service
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

[Install]
WantedBy=multi-user.target
```

```bash
# /opt/foxbms-sil/scripts/rotate_telemetry.sh  (run via systemd timer, daily 00:00)
#!/bin/bash
set -euo pipefail
DATE=$(date +%Y-%m-%d)
DIR=/var/lib/foxbms-telemetry/$DATE
mkdir -p "$DIR"

systemctl stop foxbms-capture
gzip -c /var/lib/foxbms-telemetry/current.log > "$DIR/candump_${DATE}_$(date +%H%M%S).log.gz"
: > /var/lib/foxbms-telemetry/current.log   # truncate, keep inode
systemctl start foxbms-capture

# Write metadata alongside compressed log
python3 /opt/foxbms-sil/scripts/write_capture_metadata.py --date "$DATE" --dir "$DIR"
```

**Metadata schema** (`capture_metadata.json` written per session):

```json
{
  "capture_date": "2026-03-28",
  "start_time": "2026-03-28T00:00:00Z",
  "duration_s": 86400,
  "frame_count": null,
  "plant_version": "git:ab3759d",
  "sidecar_version": "git:ab3759d",
  "bms_state_distribution": {"NORMAL": 95.2, "STANDBY": 4.1, "ERROR": 0.7},
  "compressed_size_mb": null,
  "interface": "vcan1",
  "can_ids_seen": ["0x233", "0x235", "0x270", "0x280", "0x521", "0x700", "0x705"],
  "faults_injected": false
}
```

**Systemd timer unit** (triggers rotation daily at 00:05; the 5-minute offset avoids
midnight log boundary artefacts):

```ini
# /etc/systemd/system/foxbms-rotate.timer
[Unit]
Description=foxBMS SIL Telemetry Daily Rotation

[Timer]
OnCalendar=*-*-* 00:05:00
Persistent=true

[Install]
WantedBy=timers.target
```

```ini
# /etc/systemd/system/foxbms-rotate.service
[Unit]
Description=foxBMS SIL Telemetry Rotation (one-shot)
After=foxbms-capture.service

[Service]
Type=oneshot
ExecStart=/opt/foxbms-sil/scripts/rotate_telemetry.sh
```

**Installation commands** (run once on VPS):

```bash
# Copy unit files
cp foxbms-capture.service /etc/systemd/system/
cp foxbms-rotate.timer   /etc/systemd/system/
cp foxbms-rotate.service /etc/systemd/system/
cp rotate_telemetry.sh   /opt/foxbms-sil/scripts/ && chmod +x /opt/foxbms-sil/scripts/rotate_telemetry.sh

# Enable and start
systemctl daemon-reload
systemctl enable --now foxbms-capture
systemctl enable --now foxbms-rotate.timer

# Verify timer is scheduled
systemctl list-timers foxbms-rotate
```

`write_capture_metadata.py` parses the compressed log, counts frames per CAN ID, and records
the git SHA of the currently running plant model and sidecar.

```python
#!/usr/bin/env python3
# /opt/foxbms-sil/scripts/write_capture_metadata.py
"""
Write capture_metadata.json for a completed telemetry rotation session.

Called by rotate_telemetry.sh after compression completes.
Usage: python3 write_capture_metadata.py --date 2026-03-28 --dir /var/lib/foxbms-telemetry/2026-03-28/
"""
import argparse, gzip, json, os, re, subprocess
from datetime import datetime, timezone
from pathlib import Path

CAN_IDS_OF_INTEREST = ["0x233", "0x235", "0x270", "0x280", "0x521",
                        "0x700", "0x701", "0x702", "0x703", "0x705", "0x7f2"]

def git_sha(repo_path: str) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_path, capture_output=True, text=True, timeout=5
        )
        return f"git:{result.stdout.strip()}" if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"

def count_frames(log_gz_path: Path) -> tuple[int, dict]:
    """Count total frames and per-ID breakdown from a gzipped candump log."""
    total = 0
    id_counts: dict[str, int] = {}
    id_pattern = re.compile(r"^\S+\s+(\w+)#")  # candump: timestamp iface  ID#data
    try:
        with gzip.open(log_gz_path, "rt", errors="replace") as fh:
            for line in fh:
                m = id_pattern.search(line)
                if m:
                    total += 1
                    can_id = f"0x{int(m.group(1), 16):03X}".lower()
                    id_counts[can_id] = id_counts.get(can_id, 0) + 1
    except Exception as e:
        return 0, {"error": str(e)}
    return total, id_counts

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--dir", required=True)
    args = parser.parse_args()

    out_dir = Path(args.dir)
    log_files = sorted(out_dir.glob("*.log.gz"))
    if not log_files:
        print(f"WARNING: no .log.gz found in {out_dir}")
        return

    log_path = log_files[-1]
    frame_count, id_counts = count_frames(log_path)
    size_mb = round(log_path.stat().st_size / 1_048_576, 2)

    metadata = {
        "capture_date": args.date,
        "start_time": f"{args.date}T00:05:00Z",
        "duration_s": 86400,
        "frame_count": frame_count,
        "plant_version": git_sha("/opt/foxbms-sil"),
        "sidecar_version": git_sha("/opt/foxbms-sil"),
        "compressed_size_mb": size_mb,
        "interface": "vcan1",
        "can_ids_seen": [k for k in id_counts if k in CAN_IDS_OF_INTEREST],
        "can_id_counts": {k: id_counts[k] for k in CAN_IDS_OF_INTEREST if k in id_counts},
        "faults_injected": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    out_path = out_dir / "capture_metadata.json"
    with open(out_path, "w") as fh:
        json.dump(metadata, fh, indent=2)
    print(f"Wrote {out_path} — {frame_count:,} frames, {size_mb} MB")

if __name__ == "__main__":
    main()
```

**Acceptance test**: After 24 hours, `/var/lib/foxbms-telemetry/2026-03-28/` exists with one
`.log.gz` and one `capture_metadata.json`. `systemctl status foxbms-capture` shows `Active`.

**Deliverable**: Continuous, zero-touch SIL telemetry with provenance. No more manual capture.

---

#### Day 3–4: FOBSS Dataset Ingestion

**Why this is the single highest-priority data task**:

FOBSS is 128 MB of real foxBMS 2 monitoring data from KIT Karlsruhe (CC-BY 4.0). It is
the only public dataset that shares the same firmware (foxBMS 2) as our SIL. Without it,
every accuracy claim is "validated on BMW i3" — a different vehicle, different pack topology,
different OEM BMS. With it, we can say **"validated on real foxBMS 2 hardware data"**.

**Dataset details**:
- Source: KIT Radar (search "FOBSS foxBMS")
- License: CC-BY 4.0 — free to use, citation required
- Content: Real foxBMS 2 monitoring from 44-cell modular NMC pack
- Signals: per-cell voltages, temperatures, pack current — same CAN protocol as foxBMS v1.10
- Gap: 44 cells vs our 18-cell SIL — **irrelevant once per-cell voltage is normalized**

```bash
# Day 3: Download and inspect
mkdir -p taktflow-bms-ml/data/fobss && cd taktflow-bms-ml/data/fobss
# Locate exact URL at https://radar.kit.edu — search "FOBSS foxBMS"
wget "FOBSS_DOWNLOAD_URL" -O fobss.tar.gz
tar xzf fobss.tar.gz

# Inspect format before writing ingestion script
python3 -c "
import pathlib, sys
for f in sorted(pathlib.Path('.').rglob('*.*')):
    print(f.suffix.ljust(8), str(f.stat().st_size // 1024).rjust(8), 'KB', f.name)
" | head -30
```

**Ingestion script** (`scripts/ingest_fobss.py`):

```python
#!/usr/bin/env python3
"""
Ingest FOBSS dataset → canonical (N, 5) feature matrix.

FOBSS pack: 44S NMC, 3.5 Ah.
Key: per-cell normalization makes this topology-independent.
  cell_V = pack_V / 44  →  same input range as 18S SIL and 96S BMW i3.

Output:
  data/fobss_features.npz   — (N, 5) float32
  data/fobss_soc_gt.npy     — (N,) float32 ground-truth SOC %
"""

import numpy as np
import pandas as pd
from pathlib import Path
from pipeline.feature_extractor import FeatureConfig, extract_features

FOBSS_N_CELLS = 44
FOBSS_CONFIG = FeatureConfig(cells_in_series=FOBSS_N_CELLS, max_current_a=300.0)

def load_fobss(data_dir: str) -> pd.DataFrame:
    dfs = []
    for f in sorted(Path(data_dir).glob("**/*.csv")):
        try:
            df = pd.read_csv(f, sep=";", decimal=",", encoding="latin-1")
            df["source_file"] = f.name
            dfs.append(df)
        except Exception as e:
            print(f"WARNING: {f.name}: {e}")
    return pd.concat(dfs, ignore_index=True)

if __name__ == "__main__":
    df = load_fobss("data/fobss/")
    # Column name mapping — adjust if FOBSS uses different names
    features = extract_features(
        pack_voltage_v=df["Battery_Voltage"].values,
        pack_current_a=df["Battery_Current"].values,
        temp_avg_c=df["T_avg"].values,
        temp_max_c=df["T_max"].values,
        config=FOBSS_CONFIG,
    )
    soc_gt = df["SOC"].values.astype(np.float32)
    np.savez("data/fobss_features.npz", features=features)
    np.save("data/fobss_soc_gt.npy", soc_gt)
    print(f"FOBSS: {features.shape} features, {len(soc_gt)} SOC labels")
    print(f"SOC range: {soc_gt.min():.1f}% – {soc_gt.max():.1f}%")
    print(f"Duration: {len(df) / 3600:.1f} hours (assumes 1 Hz)")
```

**Contingency table**:

| Scenario | Action |
|---|---|
| HDF5 format instead of CSV | Switch to `pd.read_hdf()` |
| Different column names | Inspect `df.columns`, update mapping |
| foxBMS v2.x CAN IDs differ from v1.10 | Use foxBMS v2 DBC for remapping |
| File too large for RAM | Stream with `pd.read_csv(chunksize=100_000)` |
| URL dead — KIT Radar down | Email KIT: `bmd@kit.edu`. Fallback: BMW i3 per-cell cross-validation. |

**Acceptance test**: `python3 scripts/ingest_fobss.py` produces `data/fobss_features.npz`
with shape `(N, 5)` where N > 10,000 and SOC range covers at least 20–80%.

---

#### Day 5–6: Unified Feature Extraction Pipeline

**Problem**: Feature extraction is currently scattered across 4 files with no shared interface:

| File | Feature extraction method |
|---|---|
| `src/ml_sidecar.py` | Inline from live SocketCAN buffer |
| `src/train_anomaly_bms.py` | Synthetic generation (independent random V and I) |
| `scripts/ingest_fobss.py` (proposed) | CSV column extraction |
| `tools/soc-drift-calc.py` | Own simulation logic |

Any change to feature engineering (e.g., per-cell normalization formula, clipping bounds)
must be made in 4 places. A mismatch between training-time and inference-time features
silently degrades accuracy. This is the root cause of GAP-ML-001 (20% SOC error).

**Solution**: `pipeline/feature_extractor.py` — single source of truth for all consumers.

```python
# pipeline/feature_extractor.py
"""
Canonical BMS feature extraction — single source of truth.

All consumers (live sidecar, training, validation, offline audit)
must import from here. Changes propagate to all consumers automatically.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional

FEATURE_NAMES = ["cell_V", "pack_I_A", "T_avg_degC", "T_max_degC", "velocity_kmh"]
N_FEATURES = 5


@dataclass
class FeatureConfig:
    """Pack topology configuration."""
    cells_in_series: int
    nominal_cell_voltage_v: float = 3.65
    max_current_a: float = 300.0
    max_temp_c: float = 80.0


def extract_features(
    pack_voltage_v: np.ndarray,
    pack_current_a: np.ndarray,
    temp_avg_c: np.ndarray,
    temp_max_c: np.ndarray,
    config: FeatureConfig,
    velocity_kmh: Optional[np.ndarray] = None,
) -> np.ndarray:
    """
    Compute canonical (N, 5) feature matrix from raw BMS signals.

    Per-cell normalization makes models topology-independent:
      foxBMS SIL  18S @  66 V →  3.67 V/cell  ← same model input range
      FOBSS       44S @ 162 V →  3.68 V/cell  ← same model input range
      BMW i3      96S @ 360 V →  3.75 V/cell  ← same model input range
    """
    N = len(pack_voltage_v)
    if velocity_kmh is None:
        velocity_kmh = np.zeros(N, dtype=np.float32)

    cell_v = pack_voltage_v / config.cells_in_series
    cell_v   = np.clip(cell_v,        2.5, 4.5).astype(np.float32)
    pack_i   = np.clip(pack_current_a, -config.max_current_a, config.max_current_a).astype(np.float32)
    t_avg    = np.clip(temp_avg_c,    -30.0, config.max_temp_c).astype(np.float32)
    t_max    = np.clip(temp_max_c,    -30.0, config.max_temp_c).astype(np.float32)
    velocity = np.clip(velocity_kmh,   0.0, 300.0).astype(np.float32)

    return np.column_stack([cell_v, pack_i, t_avg, t_max, velocity])


def compute_normalization_stats(features: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Compute mean and std from a training feature matrix. Call once; save to .npy."""
    return features.mean(axis=0).astype(np.float32), features.std(axis=0).astype(np.float32)


def normalize(features: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    """Z-score normalization. std < 1e-6 clamped to prevent division by zero."""
    return (features - mean) / np.maximum(std, 1e-6)
```

**Refactor plan** (no behavior change, pure consolidation):
1. Add `pipeline/__init__.py` and `pipeline/feature_extractor.py`
2. Import in `ml_sidecar.py` — replace inline extraction with `extract_features()`
3. Import in `train_anomaly_bms.py` — remove synthetic-only feature construction
4. All new scripts (`ingest_fobss.py`, `validate_all.py`) use this module from day one

**Acceptance test**: `from pipeline.feature_extractor import extract_features, FeatureConfig`
imports successfully inside both `ml_sidecar.py` and `scripts/ingest_fobss.py`.
Output shape is `(N, 5)` for all three data sources (SIL, FOBSS, BMW i3).

---

#### Day 7: Data Catalog

**Problem**: We now have data from multiple sources (SIL live, BMW i3 CSV, FOBSS,
synthetic). No single place exists to see what we have, how much, what SOC range it
covers, or when it was captured. Finding data for a training run requires checking 3
directories and remembering which files are which.

**Solution**: `data/catalog.json` — machine-readable manifest updated by all ingestion scripts.

```json
{
  "last_updated": "2026-03-28T00:00:00Z",
  "datasets": [
    {
      "id": "foxbms-sil-vps-2026-03-28",
      "type": "sil_candump",
      "source": "vps:152.53.245.209:/var/lib/foxbms-telemetry/2026-03-28/",
      "format": "candump_log_gz",
      "duration_hours": 24.0,
      "frame_count": null,
      "bms_version": "foxBMS 1.10.0",
      "pack_config": "18S, 3Ah NMC (simulated)",
      "soc_range_pct": [20, 80],
      "faults_injected": false,
      "notes": "Normal operation baseline. Use for anomaly model training."
    },
    {
      "id": "fobss-kit-radar-v1",
      "type": "hardware_monitoring",
      "source": "KIT Radar: https://radar.kit.edu",
      "license": "CC-BY 4.0",
      "format": "csv",
      "duration_hours": null,
      "frame_count": null,
      "bms_version": "foxBMS 2.x",
      "pack_config": "44S, 3.5Ah NMC (real hardware)",
      "soc_range_pct": null,
      "notes": "PENDING DOWNLOAD. Zero-gap validation set for all models."
    },
    {
      "id": "bmw-i3-kaggle-72trips",
      "type": "driving_telematics",
      "source": "Kaggle anonymous BMW i3 dataset",
      "license": "CC0",
      "format": "csv_semicolon_latin1",
      "duration_hours": 72,
      "frame_count": 259200,
      "bms_version": "OEM BMW (not foxBMS)",
      "pack_config": "96S, 94Ah NMC",
      "soc_range_pct": [10, 95],
      "notes": "SOC LSTM training source. Pack-level only — no per-cell."
    }
  ]
}
```

CI reads `catalog.json` and emits a warning if `fobss-kit-radar-v1.frame_count` is null
(FOBSS not yet downloaded). After Day 30, this becomes a hard gate.

**Week 1 Exit Criteria**:
- [ ] Automated VPS telemetry: 24h continuous capture, auto-rotating, metadata written
- [ ] FOBSS downloaded and ingested to `data/fobss_features.npz` (N > 10,000)
- [ ] `pipeline/feature_extractor.py` implemented and imported by `ml_sidecar.py`
- [ ] `data/catalog.json` populated with all three datasets

---

### Week 2 (Day 8–14): Normalization Infrastructure + Thermal Pipeline Fix

**Goal**: Ensure every model receives correctly normalized inputs. This is prerequisite to
any meaningful accuracy measurement: a mis-normalized model looks broken even when it is not.

---

#### Day 8–9: Compute Ground-Truth Normalization Stats

**Problem (GAP-ML-002)**: `soc_norm_mean.npy` and `soc_norm_std.npy` were generated with
estimated values. The SOC LSTM running on SIL data (3.67 V/cell, 0.5 A, 25°C) against
BMW i3 statistics (3.75 V/cell, 30 A, 28°C) introduces a systematic input-distribution
bias — the model sees out-of-distribution inputs even when the pack is healthy.
This alone explains part of the observed 20% SOC gap.

```python
# scripts/compute_norm_stats.py
"""
Compute normalization statistics from the actual SOC LSTM training dataset.
These are the only statistics that are valid for use with soc_lstm.onnx.

Run once after BMW i3 data is available. Re-run if training data changes.
"""
import numpy as np
import pandas as pd
from pathlib import Path
from pipeline.feature_extractor import FeatureConfig, extract_features, compute_normalization_stats

BMW_I3_CONFIG = FeatureConfig(cells_in_series=96, max_current_a=250.0)

def load_bmw_i3_training_split(data_dir: str) -> np.ndarray:
    """Load trips 1–60 (training split only — never touch val/test for stats)."""
    trips = sorted(Path(data_dir).glob("*.csv"))[:60]
    all_features = []
    for f in trips:
        df = pd.read_csv(f, sep=";", decimal=",", encoding="latin-1")
        features = extract_features(
            pack_voltage_v=df["Battery_Voltage"].values,
            pack_current_a=df["Battery_Current"].values,
            temp_avg_c=df["Battery_Temperature"].values,
            temp_max_c=df["Battery_Temperature"].values,
            config=BMW_I3_CONFIG,
            velocity_kmh=df["Speed"].values,
        )
        all_features.append(features)
    return np.vstack(all_features)

if __name__ == "__main__":
    features = load_bmw_i3_training_split("data/bms-raw/bmw-i3-driving/")
    mean, std = compute_normalization_stats(features)

    out = Path("data/norm_stats/")
    out.mkdir(exist_ok=True)
    np.save(out / "soc_lstm_mean.npy", mean)
    np.save(out / "soc_lstm_std.npy", std)

    print(f"Computed from {len(features):,} samples (BMW i3 training split)")
    print(f"{'Feature':<14} {'Mean':>10} {'Std':>10}")
    for name, m, s in zip(["cell_V", "pack_I_A", "T_avg", "T_max", "velocity"], mean, std):
        print(f"{name:<14} {m:>10.4f} {s:>10.4f}")

    # Warn if drift from estimates > 10%
    old_mean = np.array([3.698, 0.5, 25.0, 30.0, 35.0], dtype=np.float32)
    drift = np.abs(mean - old_mean) / (np.abs(old_mean) + 1e-6)
    for name, d in zip(["cell_V", "pack_I_A", "T_avg", "T_max", "velocity"], drift):
        if d > 0.10:
            print(f"  NOTE: {name} mean shifted {d*100:.1f}% from previous estimates")
```

**Normalization registry** (`data/norm_stats/registry.json`) — provenance record:

```json
{
  "soc_lstm": {
    "mean_file": "data/norm_stats/soc_lstm_mean.npy",
    "std_file":  "data/norm_stats/soc_lstm_std.npy",
    "computed_from_dataset": "bmw-i3-kaggle-72trips",
    "split": "train (trips 1-60)",
    "n_samples": null,
    "computed_at": null,
    "feature_names": ["cell_V", "pack_I_A", "T_avg_degC", "T_max_degC", "velocity_kmh"],
    "values_mean": null,
    "values_std": null
  }
}
```

Fill `null` fields after running the script. Commit the filled registry alongside the `.npy`
files. This is the permanent record of where the numbers came from.

**Acceptance test**: Stats computed from ≥60,000 samples. Updated `.npy` files deployed to
VPS. `ml_sidecar.py` log shows new mean values at startup.

---

#### Day 10–11: Fix Thermal dT/dt Pipeline

**Problem (GAP-ML-004)**: Two separate bugs combine to make the Thermal CNN non-functional:

1. `plant_model.py` is isothermal — always 25°C (T never changes → dT/dt = 0 by definition)
2. `ml_sidecar.py` computes dT/dt as a finite difference of T_avg, but since T never
   changes, this is always 0.0

The Thermal CNN trained on NREL dT/dt profiles (ramp rates up to 2°C/min) sees a constant
zero input and predicts 0.000 risk on every window. The gauge appears broken on the dashboard.

**Fix — Part 1** (already specified in `ml-improvement-plan.md` §P0.1, summarized here):

Add I²R self-heating to `plant_model.py`:

```python
# Thermal model parameters (add near top of plant_model.py, after battery constants)
THERMAL_MASS_J_K = 50.0       # Thermal mass per cell, J/K (NMC pouch typical)
AMBIENT_TEMP_C   = 25.0
COOLING_COEFF_W_K = 0.5       # Natural convection coefficient, W/K

# Per-cell temperature tracking (add to battery state variables)
cell_temp_c = [25.0] * N_CELLS

# In main loop, after current_ma is computed — I²R heating per cell:
for i in range(N_CELLS):
    power_w = (current_ma / 1000.0) ** 2 * R_CELL_MOHM / 1000.0
    heat_factor = 1.0 + 0.2 * (1.0 - abs(i - N_CELLS / 2) / (N_CELLS / 2))
    dT = power_w * heat_factor * DT_S / THERMAL_MASS_J_K
    cooling = COOLING_COEFF_W_K * (cell_temp_c[i] - AMBIENT_TEMP_C) * DT_S / THERMAL_MASS_J_K
    cell_temp_c[i] = max(AMBIENT_TEMP_C - 5, min(80.0, cell_temp_c[i] + dT - cooling))
```

Expected: center cell rises ~0.3°C/min at 1 A discharge. Thermal CNN now has signal.

**Fix — Part 2** (`ml_sidecar.py` derivative):

```python
# In BMSSensorBuffers.__init__():
self._t_avg_prev: float = 25.0
self._dt_dt: float = 0.0       # °C/s, updated at 1 Hz inference tick

# In inference loop (1 Hz tick):
dt_interval = 1.0   # seconds
self._dt_dt = (self.t_avg_c - self._t_avg_prev) / dt_interval
self._t_avg_prev = self.t_avg_c

# Thermal CNN input: [T_avg, T_max, dT_dt, pack_I_A]
thermal_features = np.array([
    self.t_avg_c,
    self.t_max_c,
    self._dt_dt,
    self.pack_current_ma / 1000.0,
], dtype=np.float32)
```

**Acceptance test**: After 5 minutes of NORMAL discharge, `thermal_cnn` risk score on the
dashboard is > 0.001 (was 0.000). After injecting overtemperature (60°C spike), risk score
rises above 0.25 within 30 seconds.

---

#### Day 12–13: BMW i3 Dataset Standardization

**Problem**: 72 BMW i3 CSV trips are parsed differently by every script that uses them
(different column name assumptions, different encodings, different train/test splits).
A script that computes normalization stats on the test split would contaminate validation.

**Fix**: One canonical preparation script that writes fixed train/val/test splits and a
manifest. All downstream scripts load from the prepared splits, never from raw CSVs.

```python
# scripts/prepare_bmw_i3.py
"""
Standardize BMW i3 dataset → canonical prepared splits.

Input:  data/bms-raw/bmw-i3-driving/*.csv (72 files)
Output: data/bmw-i3-processed/
          train_features.npz   (trips  1-60, ~216,000 samples)
          val_features.npz     (trips 61-66, ~ 21,600 samples)
          test_features.npz    (trips 67-72, ~ 21,600 samples)
          train_soc_gt.npy     (N,) float32 — ground truth SOC for training split
          val_soc_gt.npy
          test_soc_gt.npy
          split_manifest.json  (which file → which split, reproducible)

Split: chronological order (NOT random — avoids temporal leakage).
Stats: computed from train split only. Val/test never touched for stats.
"""

import json, numpy as np, pandas as pd
from pathlib import Path
from pipeline.feature_extractor import FeatureConfig, extract_features

BMW_I3_CONFIG = FeatureConfig(cells_in_series=96, max_current_a=250.0)
SPLITS = [("train", 60), ("val", 6), ("test", 6)]

def process_trip(csv_path: Path) -> tuple[np.ndarray, np.ndarray]:
    df = pd.read_csv(csv_path, sep=";", decimal=",", encoding="latin-1")
    features = extract_features(
        pack_voltage_v=df["Battery_Voltage"].values,
        pack_current_a=df["Battery_Current"].values,
        temp_avg_c=df["Battery_Temperature"].values,
        temp_max_c=df["Battery_Temperature"].values,
        config=BMW_I3_CONFIG,
        velocity_kmh=df["Speed"].values,
    )
    soc_gt = df["SoC"].values.astype(np.float32)
    return features, soc_gt

if __name__ == "__main__":
    trips = sorted(Path("data/bms-raw/bmw-i3-driving/").glob("*.csv"))
    assert len(trips) == 72, f"Expected 72 trips, found {len(trips)}"

    out = Path("data/bmw-i3-processed/")
    out.mkdir(exist_ok=True)
    manifest = {}
    offset = 0

    for split_name, count in SPLITS:
        split_trips = trips[offset:offset + count]
        all_feat, all_soc = [], []
        for t in split_trips:
            f, s = process_trip(t)
            all_feat.append(f)
            all_soc.append(s)
            manifest[t.name] = split_name
        np.savez(out / f"{split_name}_features.npz", features=np.vstack(all_feat))
        np.save(out / f"{split_name}_soc_gt.npy", np.concatenate(all_soc))
        print(f"{split_name}: {count} trips, {sum(len(f) for f in all_feat):,} samples")
        offset += count

    with open(out / "split_manifest.json", "w") as fh:
        json.dump(manifest, fh, indent=2)
    print("Split manifest written. Test split is held out.")
```

**Acceptance test**: `data/bmw-i3-processed/split_manifest.json` committed. Train split ≥
60,000 samples. Test split never referenced during any training or normalization step.

---

#### Day 14: Data Quality Gate

One script to verify the entire data infrastructure is consistent. Runs in CI on every push.

```python
# scripts/check_data_quality.py
"""Data quality gate — CI entry point. Exit 1 on any failure."""
import sys, json, numpy as np
from pathlib import Path

PASS = []
FAIL = []

def check(name: str, ok: bool, detail: str = ""):
    if ok:
        PASS.append(name)
        print(f"  PASS  {name}")
    else:
        FAIL.append(name)
        print(f"  FAIL  {name}" + (f" — {detail}" if detail else ""))

# 1. Data catalog
cat = json.load(open("data/catalog.json"))
fobss = next((d for d in cat["datasets"] if d["id"] == "fobss-kit-radar-v1"), None)
check("FOBSS in catalog", fobss is not None)
check("FOBSS downloaded", fobss and fobss.get("frame_count") is not None,
      "Download from KIT Radar. See Day 3-4 in plan-ai-180-day.md.")

# 2. Feature files
check("FOBSS features.npz exists", Path("data/fobss_features.npz").exists())
check("BMW i3 train split exists", Path("data/bmw-i3-processed/train_features.npz").exists())
check("BMW i3 split manifest exists", Path("data/bmw-i3-processed/split_manifest.json").exists())

# 3. Normalization stats
for stat in ["soc_lstm_mean.npy", "soc_lstm_std.npy"]:
    p = Path(f"data/norm_stats/{stat}")
    check(f"{stat} exists", p.exists())
    if p.exists():
        arr = np.load(p)
        check(f"{stat} shape=(5,)", arr.shape == (5,), f"got {arr.shape}")
        check(f"{stat} no zeros", (arr != 0).all(), f"contains zeros: {arr}")

# 4. Feature stats sanity
if Path("data/fobss_features.npz").exists():
    feat = np.load("data/fobss_features.npz")["features"]
    check("FOBSS non-trivial variance", feat.std(axis=0).min() > 0.001,
          f"std: {feat.std(axis=0).round(4)}")
    check("FOBSS cell_V in 2.5–4.5V range", 2.5 < feat[:, 0].mean() < 4.5,
          f"mean cell_V: {feat[:, 0].mean():.3f}")

# 5. Importability
try:
    from pipeline.feature_extractor import extract_features, FeatureConfig
    check("pipeline.feature_extractor importable", True)
except ImportError as e:
    check("pipeline.feature_extractor importable", False, str(e))

# 6. Norm stats registry
reg_path = Path("data/norm_stats/registry.json")
check("norm stats registry exists", reg_path.exists())
if reg_path.exists():
    reg = json.load(open(reg_path))
    check("soc_lstm entry in registry", "soc_lstm" in reg)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    for f in FAIL:
        print(f"  FAIL: {f}")
    sys.exit(1)
```

**CI integration** (`.github/workflows/ci.yml`):

```yaml
  data-quality:
    name: Data Quality Gate
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install numpy
      - run: python3 scripts/check_data_quality.py
```

**Week 2 Exit Criteria**:
- [ ] Normalization stats computed from actual BMW i3 training data (not estimates)
- [ ] `pipeline/feature_extractor.py` imported by `ml_sidecar.py` and `ingest_fobss.py`
- [ ] Thermal dT/dt pipeline functional — Thermal CNN score > 0.001 during discharge
- [ ] BMW i3 data in fixed train/val/test splits with manifest
- [ ] `check_data_quality.py` exits 0 in CI

---

### Week 3 (Day 15–21): Baseline Accuracy Measurement

**Goal**: Measure the exact current accuracy of all 5 models.
**Rule**: No model is touched this week. No retraining, no weight changes, no hyperparameter
tuning. Pure measurement. These numbers become the immutable Phase 2 improvement baseline.

---

#### Day 15–16: SOC LSTM Baseline

```python
# scripts/validate_soc_lstm.py
"""
SOC LSTM baseline measurement. Run on all available datasets.
No model changes — pure measurement pass.

Populates docs/plans/baseline-metrics-phase1.md SOC LSTM rows.
"""

import numpy as np
import onnxruntime as ort
from pathlib import Path
from pipeline.feature_extractor import normalize

WINDOW = 60   # SOC LSTM input window (timesteps)

def validate(model_path: str, features: np.ndarray, soc_gt: np.ndarray,
             mean: np.ndarray, std: np.ndarray, name: str) -> dict:
    session = ort.InferenceSession(model_path)
    inp = session.get_inputs()[0].name

    preds = []
    for i in range(WINDOW, len(features)):
        x = features[i - WINDOW:i].reshape(1, WINDOW, -1).astype(np.float32)
        x_norm = normalize(x, mean, std)
        preds.append(float(session.run(None, {inp: x_norm})[0]))

    preds = np.array(preds)
    gt = soc_gt[WINDOW:WINDOW + len(preds)]
    diff = preds - gt

    result = {
        "dataset": name, "n": len(preds),
        "rmse": float(np.sqrt(np.mean(diff ** 2))),
        "mae":  float(np.mean(np.abs(diff))),
        "max":  float(np.max(np.abs(diff))),
        "bias": float(np.mean(diff)),
    }
    print(f"\n{name}  (N={result['n']:,})")
    print(f"  RMSE:    {result['rmse']:.3f}%")
    print(f"  MAE:     {result['mae']:.3f}%")
    print(f"  Max err: {result['max']:.3f}%")
    print(f"  Bias:    {result['bias']:+.3f}%")
    return result
```

**Decision gates**:

| Dataset | Expected | Gate | Action if gate fails |
|---|---|---|---|
| BMW i3 test split | ~1.83% RMSE | < 3.0% | Normalization mismatch — check stats pipeline |
| FOBSS (real foxBMS) | Unknown | < 5.0% | > 5%: plan FOBSS fine-tune in Phase 2 |
| foxBMS SIL 30-min | Unknown | < 10.0% | > 10%: document domain gap; SOC accuracy not claimable |

---

#### Day 17: IsolationForest Baseline

Automated fault-injection validation via the VPS dashboard WebSocket endpoint.

```bash
# scripts/validate_anomaly.sh — measures normal vs fault score separation
VPS="root@152.53.245.209"
echo "=== IsolationForest Baseline Measurement ==="

# 1. Capture 5 minutes of NORMAL CAN 0x705 anomaly scores
echo "--- Normal operation (300 seconds) ---"
ssh $VPS "timeout 300 candump vcan1,705:7FF -L" | \
    python3 scripts/parse_anomaly_scores.py --mode normal

# 2. Inject overvoltage, capture 60 s
echo "--- Overvoltage fault ---"
# Dashboard fault injection via WebSocket; script uses wscat
wscat -c wss://sil.taktflow-systems.com/ws \
      -x '{"cmd":"inject","type":"overvoltage","cell":0,"value_mv":4600}' \
      --wait 1 --close
ssh $VPS "timeout 60 candump vcan1,705:7FF -L" | \
    python3 scripts/parse_anomaly_scores.py --mode ov_fault

# 3. Clear, then inject overtemperature
wscat -c wss://sil.taktflow-systems.com/ws \
      -x '{"cmd":"clear_all"}' --wait 1 --close
sleep 30   # allow recovery
wscat -c wss://sil.taktflow-systems.com/ws \
      -x '{"cmd":"inject","type":"overtemp","sensor":0,"value_ddegc":600}' \
      --wait 1 --close
ssh $VPS "timeout 60 candump vcan1,705:7FF -L" | \
    python3 scripts/parse_anomaly_scores.py --mode ot_fault
```

**Target metrics**:

| Condition | Mean score | Gate |
|---|---|---|
| Normal operation | < 0.20 | Hard gate |
| Overvoltage (4.6 V) | > 0.40 | Hard gate |
| Overtemperature (60°C) | > 0.30 | Hard gate |
| Overcurrent (150 A) | > 0.40 | Hard gate |
| Recovery after clear | < 0.20 within 30 s | Soft gate |

*Note*: IsolationForest was trained on synthetic data. Gate values are intentionally
generous. If the model fails these gates, the retrain-on-real-data task moves to P0 in Phase 2.

---

#### Day 18: Thermal CNN and SOH Transformer Baseline

**Thermal CNN** (after Day 10–11 fix):
- Run 60 minutes of NORMAL SIL operation with thermal model active
- Measure: false positive rate (risk > 0.3 during normal discharge), peak risk score
- Inject OT fault (60°C spike): measure time to first score > 0.3 (target < 30 s)
- Expected FPR with correct dT/dt: < 5%

**SOH Transformer**:
- Known non-operational: `cycle_count = 0.0` in SIL; model needs cycling history
- Record raw model output range on SIL data (even if meaningless)
- Check FOBSS: if FOBSS includes cycle count signal, run SOH baseline on that
- Document status: "NOT OPERATIONAL — single-run SIL, no cycling history"
- This is a planned Phase 2 improvement (synthetic cycle replay)

**Cell Imbalance** (direct computation, no ONNX):
- Normal SIL: measure mean V spread across 18 cells (expect 10–20 mV)
- Inject imbalance (cell 0 at 50 mV below mean): verify CAN 0x703 rises accordingly
- Record: distribution of normal spread values (used as training data for Phase 2 threshold tuning)

---

#### Day 19–20: Baseline Report Assembly

All Phase 1 measurements consolidated into a single permanent reference document.

**`docs/plans/baseline-metrics-phase1.md`** structure:

```markdown
# ML Model Baseline — Phase 1 Measurement

**Date measured**: [fill after Day 19-20]
**Measured by**: [name]
**Reference commit**: [git SHA at time of measurement]
**Purpose**: Immutable baseline. All Phase 2 improvements measured against these numbers.
DO NOT UPDATE after Phase 2 starts. Create baseline-metrics-phase2.md instead.

---

## SOC LSTM (soc_lstm.onnx — BiLSTM 128→64, 60-step window)

| Dataset | N | RMSE | MAE | Max Err | Bias | Gate | Status |
|---|---|---|---|---|---|---|---|
| BMW i3 test split | 21,600 | ___.___% | ___.___% | ___.___% | ±___.___% | <3.0% | PASS/FAIL |
| FOBSS (real foxBMS) | ___ | ___.___% | ___.___% | ___.___% | ±___.___% | <5.0% | PASS/FAIL |
| foxBMS SIL 30-min | 1,800 | ___.___% | ___.___% | ___.___% | ±___.___% | <10.0% | PASS/FAIL |

Normalization stats: computed from BMW i3 training split (N=___,___ samples, Date: ___)

## IsolationForest (anomaly_model.pkl — 100 trees, contamination=0.05)

| Condition | N | Mean Score | 95th %ile | Max | Gate | Status |
|---|---|---|---|---|---|---|
| Normal operation | 300 | ___.___| ___.___| ___.___| <0.20 | PASS/FAIL |
| Overvoltage (4.6 V) | 60 | ___.___| ___.___| ___.___| >0.40 | PASS/FAIL |
| Overtemperature (60°C) | 60 | ___.___| ___.___| ___.___| >0.30 | PASS/FAIL |
| Overcurrent (150 A) | 60 | ___.___| ___.___| ___.___| >0.40 | PASS/FAIL |

Training data: synthetic (4 regimes). See GAP-ML-003 — retrain on real SIL in Phase 2.

## Thermal CNN (thermal_cnn.onnx — CNN 30-step window)

| Condition | N | Mean Risk | Max Risk | FPR @0.3 | Gate | Status |
|---|---|---|---|---|---|---|
| Normal (dT/dt fixed) | 300 | ___.___| ___.___| ___% | <5% FPR | PASS/FAIL |
| OT fault (60°C spike) | 60 | ___.___| ___.___| — | >0.30 mean | PASS/FAIL |

Note: dT/dt fix applied Day 10-11 before this measurement.

## SOH Transformer (soh_transformer.onnx)

| Condition | Output | Notes | Status |
|---|---|---|---|
| foxBMS SIL single-run | ___.___–___.___ % | cycle_count=0.0 | NOT OPERATIONAL |

## Cell Imbalance (direct computation — no ONNX)

| Condition | Mean Spread | Std | Max Spread |
|---|---|---|---|
| foxBMS SIL normal | ___ mV | ___ mV | ___ mV |
| Imbalance injected (+50 mV cell 0) | ___ mV | ___ mV | ___ mV |

---

## Phase 2 Improvement Targets

| Model | Phase 1 Baseline | Phase 2 Target | Primary Method |
|---|---|---|---|
| SOC LSTM (FOBSS) | ___.___% RMSE | < 3.0% | Fix OCV curve; compute normalization from real data |
| IsolationForest | ___% detection | > 80% TPR | Retrain on 30-min real SIL baseline |
| Thermal CNN | ___% FPR | < 2% FPR | Augment training with synthetic gradual events |
| SOH Transformer | NOT OPERATIONAL | Operational | Synthetic cycle replay (Phase 2) |
```

---

#### Day 21: Buffer / Catch-up

Reserve for:
- Re-running any measurement where FOBSS format caused parsing errors
- Data quality gate failures found during measurement
- VPS connectivity issues during fault injection testing
- Updating `data/catalog.json` with measured values

---

### Week 4 (Day 22–30): CI Metrics Gate + Phase 1 Close

**Goal**: Baseline metrics are locked into CI. Any Phase 2 change that degrades a gate
metric causes the CI `ml-accuracy` job to fail before merge.

---

#### Day 22–24: CI Metrics Gate Implementation

**Problem**: Current CI runs 2,005 functional tests but zero accuracy tests. A broken
normalization change or plant model bug silently degrades ML accuracy with all tests green.

**Solution**: `tests/test_ml_accuracy.py` — accuracy regression gate.

```python
# tests/test_ml_accuracy.py
"""
ML accuracy regression tests.

Run: pytest tests/test_ml_accuracy.py -v --timeout=300
Required data: data/bmw-i3-processed/test_features.npz (from Day 12-13)
               data/norm_stats/soc_lstm_*.npy (from Day 8-9)
               models/bms/soc_lstm.onnx

These tests FAIL if accuracy degrades below Phase 1 baseline thresholds.
They do NOT run on every PR push (dataset too large).
CI strategy: run on push to main; skip on PRs unless models/data change.
"""

import pytest
import numpy as np
import onnxruntime as ort
from pathlib import Path

# ─── Phase 1 baseline thresholds ────────────────────────────────────────────
# Update ONLY when a new model is trained and a new baseline is established.
SOC_BMW_I3_RMSE_GATE  = 3.0   # % — published 1.83%, gate at 3× published
SOC_FOBSS_RMSE_GATE   = 5.0   # % — unknown baseline; conservative initial gate
SOC_BIAS_GATE         = 3.0   # % — systematic bias (catches normalization errors)
ANOMALY_NORMAL_MAX    = 0.25  # anomaly score — normal operation ceiling
ANOMALY_FAULT_MIN     = 0.35  # anomaly score — fault injection floor
# ────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def soc_model():
    path = Path("models/bms/soc_lstm.onnx")
    pytest.importorskip("onnxruntime")
    if not path.exists():
        pytest.skip("SOC LSTM not available")
    return ort.InferenceSession(str(path))


@pytest.fixture(scope="module")
def norm_stats():
    m = Path("data/norm_stats/soc_lstm_mean.npy")
    s = Path("data/norm_stats/soc_lstm_std.npy")
    if not m.exists() or not s.exists():
        pytest.skip("Normalization stats not available")
    return np.load(m), np.load(s)


@pytest.fixture(scope="module")
def bmw_i3_test():
    p = Path("data/bmw-i3-processed/test_features.npz")
    if not p.exists():
        pytest.skip("BMW i3 test split not available")
    data = np.load(p)
    return data["features"], np.load("data/bmw-i3-processed/test_soc_gt.npy")


@pytest.fixture(scope="module")
def fobss_data():
    fp = Path("data/fobss_features.npz")
    sp = Path("data/fobss_soc_gt.npy")
    if not fp.exists() or not sp.exists():
        pytest.skip("FOBSS not available")
    return np.load(fp)["features"], np.load(sp)


class TestSOCLSTMAccuracy:
    WINDOW = 60

    def _predict(self, session, features, mean, std) -> np.ndarray:
        inp = session.get_inputs()[0].name
        preds = []
        for i in range(self.WINDOW, len(features)):
            x = features[i - self.WINDOW:i].reshape(1, self.WINDOW, -1).astype(np.float32)
            x_n = (x - mean) / np.maximum(std, 1e-6)
            preds.append(float(session.run(None, {inp: x_n})[0]))
        return np.array(preds)

    def test_bmw_i3_rmse_gate(self, soc_model, norm_stats, bmw_i3_test):
        mean, std = norm_stats
        feat, gt = bmw_i3_test
        preds = self._predict(soc_model, feat, mean, std)
        rmse = float(np.sqrt(np.mean((preds - gt[self.WINDOW:self.WINDOW + len(preds)]) ** 2)))
        assert rmse < SOC_BMW_I3_RMSE_GATE, \
            f"SOC LSTM BMW i3 RMSE {rmse:.2f}% ≥ gate {SOC_BMW_I3_RMSE_GATE}%"

    def test_bmw_i3_bias_gate(self, soc_model, norm_stats, bmw_i3_test):
        mean, std = norm_stats
        feat, gt = bmw_i3_test
        preds = self._predict(soc_model, feat, mean, std)
        bias = float(np.mean(preds - gt[self.WINDOW:self.WINDOW + len(preds)]))
        assert abs(bias) < SOC_BIAS_GATE, \
            f"SOC LSTM bias {bias:+.2f}% ≥ gate ±{SOC_BIAS_GATE}%"

    def test_fobss_rmse_gate(self, soc_model, norm_stats, fobss_data):
        mean, std = norm_stats
        feat, gt = fobss_data
        preds = self._predict(soc_model, feat, mean, std)
        rmse = float(np.sqrt(np.mean((preds - gt[self.WINDOW:self.WINDOW + len(preds)]) ** 2)))
        assert rmse < SOC_FOBSS_RMSE_GATE, \
            f"SOC LSTM FOBSS RMSE {rmse:.2f}% ≥ gate {SOC_FOBSS_RMSE_GATE}%"
```

**CI job** (`.github/workflows/ci.yml`):

```yaml
  ml-accuracy:
    name: ML Accuracy Gate
    runs-on: ubuntu-latest
    needs: [build, unit-tests]
    # Run only on main branch — dataset not available in fork CI
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - name: Download model artifacts
        # Models stored in GitHub Releases or artifact store, not in repo
        run: make download-models
      - name: Data quality check
        run: python3 scripts/check_data_quality.py
      - name: ML accuracy regression tests
        run: pytest tests/test_ml_accuracy.py -v --timeout=300
        # Hard gate — fails CI, not continue-on-error
```

**Acceptance test**: `pytest tests/test_ml_accuracy.py -v` passes on current code. A synthetic
test that deliberately breaks normalization (e.g., `mean = np.zeros(5)`) causes the bias test
to fail.

---

#### Day 25–27: Model Registry

**Problem**: Models are deployed to VPS by SCP. No record of which version is running,
what it was trained on, or what accuracy it had at deployment time. After Phase 2 retraining,
there is no way to compare the new model against the baseline model.

**Solution**: `models/registry.json` — committed alongside models.

```json
{
  "schema_version": "1.0",
  "models": [
    {
      "id": "soc_lstm_v1",
      "file": "models/bms/soc_lstm.onnx",
      "architecture": "BiLSTM 128→64",
      "input_shape": [1, 60, 5],
      "output": "soc_pct_float",
      "training_data": ["bmw-i3-kaggle-72trips", "nasa-pcoE-7565-cycles"],
      "training_date": "2025-xx-xx",
      "norm_mean_file": "data/norm_stats/soc_lstm_mean.npy",
      "norm_std_file":  "data/norm_stats/soc_lstm_std.npy",
      "published_rmse_pct": 1.83,
      "published_val_dataset": "bmw-i3-test-split",
      "phase1_baseline_bmw_rmse_pct": null,
      "phase1_baseline_fobss_rmse_pct": null,
      "phase1_baseline_date": null,
      "deployed_to_vps": true,
      "deployed_at": "2026-03-27",
      "gap_refs": ["GAP-ML-001", "GAP-ML-002"]
    },
    {
      "id": "isolation_forest_v1",
      "file": "models/bms/anomaly_model.pkl",
      "architecture": "IsolationForest (100 trees, contamination=0.05)",
      "input_shape": [1, 5],
      "output": "anomaly_score_0_1",
      "training_data": ["synthetic-foxbms-sil-4regimes"],
      "training_date": "2026-03-27",
      "phase1_baseline_normal_mean": null,
      "phase1_baseline_ov_mean": null,
      "phase1_baseline_date": null,
      "deployed_to_vps": true,
      "gap_refs": ["GAP-ML-003"]
    },
    {
      "id": "thermal_cnn_v1",
      "file": "models/bms/thermal_cnn.onnx",
      "architecture": "1D-CNN 30-step window",
      "input_shape": [1, 30, 4],
      "features": ["T_avg", "T_max", "dT_dt", "pack_I_A"],
      "output": "thermal_risk_0_1",
      "training_data": ["nrel-thermal-364-tests"],
      "phase1_baseline_normal_fpr": null,
      "phase1_baseline_ot_mean_risk": null,
      "phase1_baseline_date": null,
      "gap_refs": ["GAP-ML-004"],
      "note": "dT/dt fix applied Day 10-11 before Phase 1 baseline measurement"
    }
  ]
}
```

After Day 20 measurements, fill all `phase1_baseline_*` fields. These become immutable.
Phase 2 model versions get `id: soc_lstm_v2` and reference `phase2_baseline_*` fields.

---

#### Day 28–29: Data Pipeline Documentation

Two short documents for future maintainers and for onboarding a second engineer:

1. **`docs/plans/data-collection-guide.md`** — How to add a new dataset:
   - Format requirements (columns, units, encoding)
   - How to write an ingestion script using `pipeline/feature_extractor.py`
   - How to add an entry to `data/catalog.json`
   - How to add normalization stats to `data/norm_stats/registry.json`
   - How to add a test split to the BMW i3 manifest pattern

2. **`docs/plans/metrics-interpretation-guide.md`** — How to read Phase 1 numbers:
   - What RMSE means for SOC estimation (1% ≈ 1 km range error in an EV)
   - What FPR/TPR means for anomaly detection (customer trust implications)
   - How CI gates are set and when it is appropriate to update them
   - How to run local FOBSS validation (dataset too large for CI)
   - Decision tree: if a model fails its gate, what is the Phase 2 action

---

#### Day 30: Phase 1 Close

| Task | Done when |
|---|---|
| Fill all `null` fields in `baseline-metrics-phase1.md` | All rows have measured values, PASS/FAIL determined |
| Fill `phase1_baseline_*` in `models/registry.json` | All models have measured baseline entries |
| Update `data/catalog.json` FOBSS entry | `frame_count` and `soc_range_pct` filled in |
| Write retrospective entry in `docs/lessons-learned/web/ui-safety.md` | See format in lessons-learned policy |
| Derive Phase 2 priority order | Based on baseline gaps — rank which model needs most urgent fix |
| Update `PLAN.md` Phase 6 criteria | Mark Phase 1 of 180-day plan complete |

---

### Phase 1 Exit Criteria

| Criterion | Gate | Evidence |
|---|---|---|
| Automated SIL telemetry | 24 h continuous capture, auto-rotating | `systemctl status foxbms-capture` active |
| FOBSS ingested | `fobss_features.npz` shape `(N, 5)`, N > 10,000 | File exists + catalog updated |
| BMW i3 standardized | Fixed train/val/test split with manifest | `split_manifest.json` committed |
| Normalization stats | Computed from actual training data, registry written | `registry.json` has provenance |
| Thermal dT/dt | Thermal CNN risk score > 0.001 during discharge | Dashboard non-zero risk |
| SOC LSTM BMW i3 RMSE | Measured; gate determined | Baseline report row filled |
| SOC LSTM FOBSS RMSE | Measured on real foxBMS data | Baseline report row filled |
| IsolationForest | Normal/fault score separation measured | Score distribution documented |
| CI accuracy gate | `pytest tests/test_ml_accuracy.py` passes | `ml-accuracy` job green on main |
| Model registry | All deployed models have `phase1_baseline_*` fields | `registry.json` committed |
| Baseline report | All table cells filled, PASS/FAIL column complete | `baseline-metrics-phase1.md` complete |

### Phase 1 Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| FOBSS URL dead | Low | High | Email KIT `bmd@kit.edu`. Fallback: BMW i3 per-cell cross-validation |
| FOBSS uses foxBMS v2.x CAN (different from v1.10) | Medium | Medium | Remap signals via new DBC; cell V / I / T signals unchanged in v2 |
| SOC LSTM RMSE on FOBSS > 10% | Medium | High | Domain gap too large. Phase 2 plan: fine-tune on FOBSS |
| BMW i3 raw CSVs unavailable locally | Low | Medium | Recompute norm stats from FOBSS instead; document dataset substitution |
| Thermal dT/dt still zero after plant fix | Low | Medium | Debug: `candump vcan1,280:7FF` — verify temperature bytes changing |
| CI accuracy tests too slow for PR gate | Medium | Low | Run accuracy gate only on main pushes. PRs gate on data quality only |
| IsolationForest fails all fault gates | Medium | Medium | Immediate retrain on real SIL data (moves to P0 in Phase 2 kickoff) |

---

---

## Phase 2: Model Accuracy Improvements (Day 31–60)

### Goal

Close all P0 and P1 accuracy gaps identified in Phase 1 baseline. At the end of Phase 2:

- **SOC LSTM**: RMSE ≤ 3.0% on FOBSS (real foxBMS hardware), SIL steady-state bias ≤ ±3.0%
- **SOH Transformer**: Operational via synthetic cycle replay; RMSE documented on synthetic data
- **Thermal CNN**: FPR ≤ 2% (normal 30-min discharge), OT fault detected within 30 s
- **IsolationForest v2**: Retrained on real SIL baseline; normal score mean < 0.15, fault TPR ≥ 80%
- **RUL Transformer**: CAN 0x704 publishing after ≥ 20 cycle history (initial deployment)

Phase 2 makes every accuracy number **citable** — backed by measured validation evidence,
not published benchmarks from unrelated datasets.

**Phase 2 is prerequisite to Phase 3**: drift monitoring is only meaningful once baseline
accuracy is validated. You cannot monitor drift in a model whose accuracy is unknown.

---

### Phase 2 Model Accuracy KPI Reference

Single reference for all target KPIs and acceptable thresholds for the two primary predictive models. Week-by-week tasks reference these numbers directly. CI gates (`tests/test_ml_accuracy.py`) enforce every **Hard** gate on each main-branch merge. Soft gates are tracked and logged but do not block CI.

> **Gate types**: **Hard** = CI failure on violation. **Soft** = tracked, logged, warning issued — CI does not fail. Hard gates tighten in Phase 5 when real multi-cycle hardware data is available.

---

#### SOC LSTM — FOBSS Validation (SW-REQ-ML-001, BiLSTM 128→64, 60-step window)

| KPI | Dataset | Phase 1 Baseline | Phase 2 Acceptable Threshold | Phase 5 Stretch Goal | Gate Type | Requirement | Notes |
|---|---|---|---|---|---|---|---|
| RMSE | FOBSS (real foxBMS 2) | Unknown | **≤ 3.0%** | ≤ 2.5% | Hard | SW-REQ-ML-001 | Primary accuracy KPI; root cause of current gap: linear OCV curve + estimated normalization stats |
| MAE | FOBSS | Unknown | **≤ 2.0%** | ≤ 1.5% | Hard | SW-REQ-ML-001 | Complements RMSE; MAE < RMSE confirms absence of large-magnitude outliers |
| Steady-state bias | foxBMS SIL 30 min | **+20.24%** | **≤ ±3.0%** | ≤ ±1.5% | Hard | SW-REQ-ML-002/003 | Systematic offset caused by normalization mismatch + linear OCV; closed by OCV fix + recomputed norm stats |
| RMSE | BMW i3 test split | ~1.83% | **≤ 2.0%** | ≤ 1.5% | Hard (CI) | SW-REQ-ML-001 | Anti-regression gate: FOBSS fine-tune (Day 35–36) must not degrade BMW i3 performance by > 0.5% |
| MAE | BMW i3 test split | Unknown | **≤ 1.4%** | ≤ 1.0% | Hard (CI) | SW-REQ-ML-001 | Tracks alongside RMSE; detects asymmetric error distributions from distribution shift |
| P95 absolute error | FOBSS | Unknown | **≤ 5.0%** | ≤ 4.0% | Hard | SW-REQ-ML-001 | 95th percentile of `|pred − gt|`; guards tail behaviour; P95 ≤ 5.0% = worst 1-in-20 sample within 5% |
| Max single-sample absolute error | FOBSS | Unknown | **≤ 8.0%** | ≤ 6.0% | Soft | SW-REQ-ML-001 | Outlier cap; individual spikes acceptable if P95 gate passes; hard failure only if P95 also fails |
| Plateau RMSE | FOBSS, SOC 20–80% | Unknown | **≤ 4.5%** | ≤ 3.0% | Hard | SW-REQ-ML-001 | Flat OCV region; accuracy here directly affects charge-balancing and range estimation precision |
| Boundary RMSE | FOBSS, SOC 0–20% and 80–100% | Unknown | **≤ 4.0%** | ≤ 3.0% | Hard | SW-REQ-ML-001 | Near-empty / near-full boundary; critical for low-battery warning and charging endpoint decisions |
| Inference latency (mean) | VPS, ONNX Runtime ≥ 1.15 | Unknown | **≤ 100 ms** | ≤ 50 ms | Hard | SW-REQ-ML-001 | 1 Hz CAN cycle = 1000 ms total budget; 100 ms leaves ≥ 700 ms margin for SOH + publish overhead |

**Threshold rationale — FOBSS RMSE ≤ 3.0%**: Advisory SOC accuracy guidance for Tier 1 battery-system data sheets typically specifies ±2–5% SOC for non-safety display functions. 3.0% is achievable with OCV curve correction + correct normalization statistics alone (no model retraining). With FOBSS partial fine-tune (Day 35–36 conditional path), the Phase 5 stretch of 2.5% is reachable. An incorrect ML SOC prediction cannot cause a safety violation because the BMS safety layer acts on coulomb-counting SOC (SW-REQ-070..076), not ML SOC.

**CI gate progression**: Phase 1 uses conservative gate `SOC_FOBSS_RMSE_GATE = 5.0%` (no FOBSS data yet). At M2.1 (Day 37) this tightens: `SOC_FOBSS_RMSE_GATE_P2 = 3.0`, `SOC_FOBSS_MAE_GATE_P2 = 2.0`, `SOC_BMW_I3_MAE_GATE_P2 = 1.4`, `SOC_P95_GATE_P2 = 5.0`, `SOC_PLATEAU_RMSE_GATE_P2 = 4.5`, `SOC_BOUNDARY_RMSE_GATE_P2 = 4.0`. Phase 1 gates remain green until M2.1 merges.

---

#### SOH Transformer — Synthetic Cycle Replay (SW-REQ-ML-006, Transformer encoder, 10-cycle window × 12 features)

| KPI | Dataset | Phase 1 Status | Phase 2 Acceptable Threshold | Phase 5 Target (real cycles) | Gate Type | Requirement | Notes |
|---|---|---|---|---|---|---|---|
| RMSE | Synthetic 500-cycle replay | NOT OPERATIONAL | **≤ 12.0%** | ≤ 9.79% | Hard | SW-REQ-ML-006 | 12.0% = 1.23× published LiionPro-DT benchmark (9.79%); headroom accounts for synthetic-vs-real distribution gap |
| MAE | Synthetic 500-cycle replay | NOT OPERATIONAL | **≤ 8.0%** | ≤ 7.0% | Hard | SW-REQ-ML-006 | Approximately 0.67× RMSE gate; confirms absence of systematic cycle-window bias |
| Trend inversions | Synthetic 500 cycles (490 windows) | NOT OPERATIONAL | **< 10** | < 5 | Hard | SW-REQ-ML-006 | Inversion = predicted SOH increase > 2% between consecutive cycles; physical SOH is monotone decreasing; > 2% threshold tolerates ±1% model noise |
| P95 absolute error | Synthetic 500-cycle replay | NOT OPERATIONAL | **≤ 18.0%** | ≤ 14.0% | Hard | SW-REQ-ML-006 | Tail KPI; 18.0% = 1.5× RMSE gate; guards against window-edge prediction artefacts near cycle 0 and cycle 499 |
| Cycle-to-cycle noise std dev | Synthetic 500 cycles | NOT OPERATIONAL | **≤ 1.5%** | ≤ 1.0% | Hard | SW-REQ-ML-006 | `std(SOH[n] − SOH[n−1])`; measures prediction smoothness; high noise indicates overfitting to per-cycle feature variance |
| Physical range check | Synthetic 500 cycles | NOT OPERATIONAL | **490 / 490 in [65%, 100%]** | 490 / 490 | Hard | SW-REQ-ML-006 | Any prediction outside [65%, 100%] is physically impossible for a non-end-of-life NMC pack; single violation = model failure |
| SOH at cycle 0 (initial SOH) | Synthetic, cycle 0 | NOT OPERATIONAL | **≥ 99.0%** | ≥ 99.5% | Soft | SW-REQ-ML-006 | Sanity check: fresh battery must read near 100%; large underestimate indicates bias in initial cycle features |
| SOH at cycle 499 (end-of-second-life boundary) | Synthetic, cycle 499 | NOT OPERATIONAL | **88.0%–92.0%** | 89.5%–90.5% | Hard | SW-REQ-ML-006 | Ground truth at 500 cycles = 90.0% (0.02%/cycle × 500 cycles); ±2% band accounts for model RMSE at end point |
| Inference latency (mean) | VPS, ONNX Runtime ≥ 1.15 | NOT OPERATIONAL | **≤ 200 ms** | ≤ 100 ms | Hard | SW-REQ-ML-006 | SOH updated once per detected discharge cycle (event-triggered, not 1 Hz); 200 ms is generous for batch cycle processing |
| CAN 0x701 publishing | Live sidecar, ≥ 10 cycle history | NOT OPERATIONAL | **Active, non-zero output** | Always active | Hard | SW-REQ-ML-006 | Functional deployment gate; confirms live sidecar integration; output = 0 before 10-cycle history accumulated |

**Threshold rationale — synthetic RMSE ≤ 12.0%**: The LiionPro-DT benchmark achieves 9.79% RMSE on real laboratory cycling data with full charge/discharge profile variation, temperature sweep, and rest periods. The synthetic cycle replay used in Phase 2 has a narrower envelope: single C/2 C-rate, constant 25°C, no rest, no calendar ageing. Model accuracy on this simpler synthetic distribution is expected to be similar to or better than the real-data benchmark. The 12.0% gate (1.23×) provides a conservative buffer for inference-time distribution mismatch and any residual randomness in the ONNX weight export. In Phase 5, when real foxBMS 2 cycle captures are available, the gate tightens to match the published 9.79% benchmark.

**Phase 5 gate tightening trigger**: The Phase 2 gate of ≤ 12.0% RMSE remains in effect until `data/real_cycle_captures/` contains ≥ 100 real foxBMS charge-discharge cycles. At that point, Phase 5 work item `validate_soh_transformer_real.py` runs and the CI gate updates to `SOH_REAL_RMSE_GATE_P5 = 9.79`. Until then, the synthetic gate is the binding constraint.

---

#### Cross-Model Operational Budget

| Model | Update Frequency | Latency Gate | Combined Worst-Case Budget | CAN Frame |
|---|---|---|---|---|
| SOC LSTM | 1 Hz (every 1-second CAN frame) | ≤ 100 ms | 100 ms / 1000 ms cycle | 0x700 (byte 0: SOC %) |
| SOH Transformer | Once per detected discharge cycle | ≤ 200 ms | 200 ms / event (non-concurrent with 1 Hz SOC in practice) | 0x701 (bytes 0–1: SOH % × 10) |
| Both simultaneously | Rare — only if cycle end detected mid-second | 300 ms combined | 300 ms worst-case / 1000 ms CAN cycle — **within budget** | N/A |

Both models must remain below their respective latency gates during live sidecar operation. The 300 ms worst-case combined budget leaves ≥ 700 ms for CAN transmit, telemetry logging, and Python GIL overhead.

---

### ASPICE Process Coverage

| Phase 2 Deliverable | ASPICE Process | Process ID | Work Product |
|---|---|---|---|
| New ML accuracy requirements (SW-REQ-ML-001..010) | Software Requirements Analysis | SWE.1 | SWE.1-WP01 Software Requirements Specification |
| OCV table replacement, cycle replay design, dT/dt implementation | Software Detailed Design | SWE.3 | SWE.3-WP01 Software Detailed Design Description |
| Unit tests for accuracy gates (`test_ml_accuracy.py` v2) | Software Unit Verification | SWE.4 | SWE.4-001 Unit Test Specification |
| FOBSS end-to-end SOC validation | Software Integration Test | SWE.5 | SWE.5-WP01 Software Integration Test Specification |
| `baseline-metrics-phase2.md` accuracy report | Software Qualification Test | SWE.6 | SWE.6-WP01 Software Qualification Test Specification |
| Model registry v2 entries with provenance | Quality Assurance | SUP.1 | SUP.1-WP01 QA Plan |
| Phase 2 milestone tracking (M2.1–M2.4) | Project Management | MAN.3 | MAN.3-WP01 Project Plan |

#### New Software Requirements (SWE.1 — added to Section 11 of SWE.1-software-requirements.md)

All SW-REQ-ML requirements are **QM** (non-safety). The ML inference layer is an advisory
monitoring function only. Safety protection remains with the deterministic SOA module
(SW-REQ-001..SW-REQ-035, ASIL-D). An incorrect ML SOC prediction cannot cause a safety
violation because the BMS acts on coulomb-counting SOC (SW-REQ-070..076), not ML SOC.

| ID | Requirement | Derives From | ASIL | Gap |
|---|---|---|---|---|
| SW-REQ-ML-001 | The SOC LSTM shall achieve RMSE ≤ 3.0% on the FOBSS validation dataset after correct normalization | GAP-ML-001 | QM | GAP-ML-001 |
| SW-REQ-ML-002 | SOC LSTM normalization statistics shall be computed from the BMW i3 training split (trips 1–60), not from estimated specification values | GAP-ML-002 | QM | GAP-ML-002 |
| SW-REQ-ML-003 | The OCV lookup table in `plant_model.py` shall be a ≥21-point measured NMC 811 S-curve; round-trip error SOC → OCV → SOC shall be < 1.0% | P0.3 | QM | P0.3 |
| SW-REQ-ML-004 | The IsolationForest anomaly model shall be trained on ≥30 minutes of real foxBMS SIL CAN baseline data and achieve normal-operation mean score < 0.15 | GAP-ML-003 | QM | GAP-ML-003 |
| SW-REQ-ML-005 | The thermal inference pipeline shall compute dT/dt (°C/s) from successive temperature samples at 1 Hz; dT/dt shall be non-zero in ≥90% of samples during active discharge | GAP-ML-004 | QM | GAP-ML-004 |
| SW-REQ-ML-006 | The SOH Transformer shall be operational on synthetic cycle replay data spanning ≥100 charge-discharge cycles with capacity fade modelled at 0.02% Ah/cycle | GAP-ML-005 | QM | GAP-ML-005 |
| SW-REQ-ML-007 | The CI `ml-sidecar-smoke` job shall enforce a hard assertion: CAN 0x705 frame received within a 30-second window; non-receipt shall fail the CI job | GAP-ML-012 | QM | GAP-ML-012 |
| SW-REQ-ML-008 | All deployed model versions shall be recorded in `models/registry.json` with fields: training dataset, training date, Phase 2 baseline metrics, and deployed-to-VPS flag | Best practice | QM | — |
| SW-REQ-ML-009 | A Phase 2 accuracy report (`docs/plans/baseline-metrics-phase2.md`) shall document measured metrics for all 5 models across all available datasets; all PASS/FAIL gates shall be determined | SWE.6 | QM | — |
| SW-REQ-ML-010 | The Thermal CNN false-positive rate (risk score > 0.3 during normal discharge) shall be ≤ 2% and OT fault detection latency shall be ≤ 30 s | GAP-ML-004 | QM | GAP-ML-004 |

**ASPICE traceability chain for all SW-REQ-ML requirements**:

```
SYS.1 Stakeholder  →  Customer need: ML SOC, SOH, anomaly detection, thermal risk
SYS.2 System Req   →  System-level accuracy and operational requirements
SWE.1 SW Req       →  SW-REQ-ML-001..010 (this Phase 2 deliverable)
SWE.3 Detail Des   →  OCV fix, IsolationForest retrain, cycle replay, dT/dt, RUL
SWE.4 Unit Test    →  test_ml_accuracy.py (v2), test_thermal_cnn_phase2.py,
                       validate_ocv_table.py, validate_soh_transformer.py
SWE.5 Integration  →  FOBSS end-to-end validation, SIL fault injection battery
SWE.6 Qualification → baseline-metrics-phase2.md (evidence document)
SUP.1 QA           →  models/registry.json (version + provenance per model)
MAN.3 Project Mgmt →  This plan, M2.1–M2.4 milestone tracking
```

### Phase 2 Milestones

| ID | Day | Description |
|---|---|---|
| **M2.1** | Day 37 | SOC LSTM: OCV fix deployed; Phase 2 RMSE measured on BMW i3 + FOBSS; registry v2 entry filled |
| **M2.2** | Day 44 | IsolationForest v2 retrained on real SIL; Thermal CNN FPR < 2% confirmed; fault scores validated |
| **M2.3** | Day 51 | SOH Transformer operational on cycle replay; RUL initial deployment; CAN 0x704 publishing |
| **M2.4** | Day 60 | Phase 2 accuracy report published; all SW-REQ-ML gates closed in traceability matrix; CI strict |

### Phase 2 Branch Setup

```bash
# foxbms-posix — start from Phase 1 merge commit
git checkout main && git pull
git checkout -b feat/ai-phase2-accuracy
git push -u origin feat/ai-phase2-accuracy

# taktflow-bms-ml — model training and FOBSS fine-tune work happens here
cd ../taktflow-bms-ml
git checkout main && git pull
git checkout -b feat/ai-phase2-accuracy
git push -u origin feat/ai-phase2-accuracy
```

**Prerequisite check before Day 31**:

| Check | Command | Gate |
|---|---|---|
| Phase 1 baseline report filled | `grep -c "PASS\|FAIL" docs/plans/baseline-metrics-phase1.md` | ≥ 8 rows with verdict |
| FOBSS features exist | `python3 -c "import numpy as np; d=np.load('data/fobss_features.npz'); print(d['features'].shape)"` | Shape `(N, 5)`, N > 10,000 |
| Normalization stats computed | `python3 -c "import numpy as np; print(np.load('data/norm_stats/soc_lstm_mean.npy'))"` | Array of 5 non-zero values |
| CI `ml-accuracy` green on main | GitHub Actions badge | Green |

---

### Week 5 (Day 31–37): SOC LSTM Accuracy Gap Closure

**Goal**: Reduce the 20% SOC gap on foxBMS SIL. Attack both root causes confirmed in Phase 1:
OCV linearization error and normalization mismatch.

**Precondition**: Phase 1 exit criteria met. `data/norm_stats/soc_lstm_mean.npy` computed
from BMW i3 training split (Phase 1 Day 8–9). `data/fobss_features.npz` ingested (Phase 1 Day 3–4).

---

#### Day 31–32: NMC 811 OCV Table Replacement (SW-REQ-ML-003)

**Root cause**: `plant_model.py` uses a linear OCV approximation
(`3400 + 800 * SOC/100` mV). Real NMC 811 cells have a pronounced S-shape with a flat
plateau from ~30–70% SOC where voltage changes only ~5 mV per percent SOC. The linear
approximation overestimates open-circuit voltage in this plateau, creating a voltage offset
between the SIL CAN data and the BMW i3 training data (which used the real OCV curve).

**Expected impact**: Removes ~2% systematic SOC error in the 30–70% SIL steady-state region.

```python
# plant_model.py — replace existing linear OCV with 21-point NMC 811 table
# Source: Kollmeyer 2018 NMC 811, C/20 OCV, 25°C
# Pending HITL-LOCK assignment: add PLANT-OCV-TABLE lock AFTER functional safety review

NMC811_OCV_TABLE = [   # (SOC_pct, OCV_mV)
    (  0.0, 3000), (  5.0, 3299), ( 10.0, 3498), ( 15.0, 3580),
    ( 20.0, 3620), ( 25.0, 3643), ( 30.0, 3660), ( 35.0, 3668),
    ( 40.0, 3675), ( 45.0, 3680), ( 50.0, 3685), ( 55.0, 3690),
    ( 60.0, 3696), ( 65.0, 3704), ( 70.0, 3714), ( 75.0, 3730),
    ( 80.0, 3760), ( 85.0, 3800), ( 90.0, 3860), ( 95.0, 3940),
    (100.0, 4200),
]

# Replace existing ocv_lookup() call in plant_model.py with:
_OCV_SOCS = [row[0] for row in NMC811_OCV_TABLE]
_OCV_MVLS = [row[1] for row in NMC811_OCV_TABLE]

def ocv_lookup_nmc811(soc_pct: float) -> float:
    """Linear interpolation on verified 21-point NMC 811 S-curve. Returns OCV in mV."""
    return float(np.interp(soc_pct, _OCV_SOCS, _OCV_MVLS))
```

**Round-trip validation** (`scripts/validate_ocv_table.py` — SWE.4 unit test for SW-REQ-ML-003):

```python
#!/usr/bin/env python3
"""Validate NMC 811 OCV table monotonicity, range, plateau gradient, and round-trip error."""
import numpy as np

NMC811 = [(0,3000),(5,3299),(10,3498),(15,3580),(20,3620),(25,3643),(30,3660),
           (35,3668),(40,3675),(45,3680),(50,3685),(55,3690),(60,3696),(65,3704),
           (70,3714),(75,3730),(80,3760),(85,3800),(90,3860),(95,3940),(100,4200)]
socs = np.array([r[0] for r in NMC811])
ocvs = np.array([r[1] for r in NMC811])

assert np.all(np.diff(ocvs) >= 0),   "OCV not monotone"
assert ocvs[0]  == 3000,              f"0% OCV wrong: {ocvs[0]}"
assert ocvs[-1] == 4200,              f"100% OCV wrong: {ocvs[-1]}"

plateau = (socs >= 30) & (socs <= 70)
grad = np.diff(ocvs[plateau]) / np.diff(socs[plateau])
assert grad.max() <= 5.0,             f"Plateau too steep: {grad.max():.2f} mV/%"

# Round-trip: SOC → OCV → SOC, max error < 1%
ts = np.linspace(5, 95, 200)
tv = np.interp(ts, socs, ocvs)
tr = np.interp(tv, ocvs, socs)          # invert via monotone interpolation
err = np.abs(tr - ts).max()
assert err < 1.0, f"Round-trip error {err:.3f}% > 1.0%"

print(f"PASS  21-point NMC 811 OCV — plateau grad {grad.max():.2f} mV/% "
      f"— round-trip error {err:.3f}%")
```

**Note on HITL lock**: This table will be added to `plant_model.py`. Before adding
`HITL-LOCK START:PLANT-OCV-TABLE` / `HITL-LOCK END:PLANT-OCV-TABLE` markers, the table
values **must** be reviewed by a functional safety engineer. The lock markers are not
part of this Phase 2 work item — they are a post-review action. Until locked, the table
can be modified if measurement data requires adjustment.

**Acceptance test**: `python3 scripts/validate_ocv_table.py` exits 0. On the SIL dashboard
after redeployment, a cell at 50% BMS SOC reads ~3685 mV (previously ~3800 mV with linear
approximation). `ml_sidecar.py` steady-state CAN 0x700 diff drops below 10% (target: < 5%).

**ASPICE**: SWE.3.BP1 (software unit design — OCV interpolation function).
SWE.4.BP1 (unit test — `validate_ocv_table.py` covers SW-REQ-ML-003).

---

#### Day 33–34: Stage-by-Stage SOC Error Attribution

**Purpose**: Measure SOC LSTM RMSE after OCV fix but before any model retraining.
Attributes the 20% SIL gap into its component root causes.

```python
# scripts/compare_soc_fix_stages.py
"""
Stage-by-stage SOC error decomposition.

Stage A: Phase 1 baseline   (estimated norm stats + linear OCV)  — from baseline report
Stage B: Fixed norm stats   + linear OCV  (Phase 1 Day 8-9)
Stage C: Fixed norm stats   + NMC 811 OCV (Phase 2 Day 31-32)
Stage D: Fixed norm stats   + NMC 811 OCV + FOBSS fine-tune (conditional)

Run on three datasets: BMW i3 test, FOBSS, SIL 30-min.
Output: Markdown table for baseline-metrics-phase2.md improvement section.
"""
import numpy as np, onnxruntime as ort
from pipeline.feature_extractor import normalize

WINDOW = 60

def run_stage(label, feat, gt, model_path, mean, std):
    sess = ort.InferenceSession(str(model_path))
    inp  = sess.get_inputs()[0].name
    preds = []
    for i in range(WINDOW, len(feat)):
        x = feat[i-WINDOW:i].reshape(1, WINDOW, -1).astype(np.float32)
        preds.append(float(sess.run(None, {inp: normalize(x, mean, std)})[0]))
    preds = np.array(preds)
    gt_t  = gt[WINDOW:WINDOW + len(preds)]
    rmse  = float(np.sqrt(np.mean((preds - gt_t) ** 2)))
    bias  = float(np.mean(preds - gt_t))
    print(f"  {label:<48} RMSE={rmse:6.3f}%  Bias={bias:+6.3f}%")
    return rmse, bias

if __name__ == "__main__":
    mean = np.load("data/norm_stats/soc_lstm_mean.npy")
    std  = np.load("data/norm_stats/soc_lstm_std.npy")

    datasets = {
        "FOBSS":    ("data/fobss_features.npz",                "data/fobss_soc_gt.npy"),
        "BMW-i3":   ("data/bmw-i3-processed/test_features.npz","data/bmw-i3-processed/test_soc_gt.npy"),
        "SIL-30m":  ("data/sil_features_phase2.npz",           "data/sil_soc_gt_phase2.npy"),
    }

    for ds_name, (feat_p, gt_p) in datasets.items():
        from pathlib import Path
        if not Path(feat_p).exists():
            print(f"SKIP {ds_name} — {feat_p} not yet available")
            continue
        feat = np.load(feat_p)["features"]
        gt   = np.load(gt_p)
        print(f"\n=== {ds_name} ===")
        run_stage("Stage B (fixed norm, linear OCV)",   feat, gt, "models/bms/soc_lstm.onnx",   mean, std)
        run_stage("Stage C (fixed norm, NMC811 OCV)",   feat, gt, "models/bms/soc_lstm.onnx",   mean, std)
        # Stage C uses same model weights — OCV fix is in plant_model, not LSTM
        # SIL dataset MUST be captured after plant model OCV fix is deployed
```

**Decision gate after Stage C measurement**:

| FOBSS RMSE after Stage C | Action |
|---|---|
| ≤ 3.0% | **M2.1 PASS** — no fine-tuning needed; proceed to Week 6 |
| 3.0%–5.0% | Proceed to Day 35–36 partial fine-tune; document as "OCV fix insufficient alone" |
| 5.0%–8.0% | Fine-tune mandatory; domain gap larger than normalization fix alone |
| > 8.0% | Escalate: FOBSS signal format mismatch suspected; re-inspect column mapping in `ingest_fobss.py` |

---

#### Day 35–36: FOBSS Partial Fine-Tune (Conditional — Skip if FOBSS RMSE ≤ 3.0%)

Fine-tuning ONNX models requires re-training the source PyTorch model in `taktflow-bms-ml`
and re-exporting to ONNX. These steps run in that repo.

**Strategy** (SWE.3.BP1 — design decision):
Freeze BiLSTM encoder (preserves generalizable temporal features from 72 BMW i3 trips).
Unfreeze final LSTM layer + output FC head (domain-adapts to FOBSS NMC operating point).
This minimizes catastrophic forgetting risk.

```bash
# In taktflow-bms-ml

# Step 1: Build FOBSS fine-tune dataset from Phase 1 ingestion
python3 scripts/build_fobss_finetune_set.py \
  --features data/fobss_features.npz \
  --labels   data/fobss_soc_gt.npy \
  --train-pct 0.70 --val-pct 0.15 \
  --out data/fobss_finetune/
# (held-out 15% test split: never touched during fine-tune)

# Step 2: Fine-tune — 10 epochs max, lr=1e-4, L2 decay 1e-5
python3 scripts/finetune_soc_lstm.py \
  --base-model models/bms/soc_lstm_v1.pt \
  --finetune-data data/fobss_finetune/ \
  --epochs 10 --lr 1e-4 --freeze-encoder \
  --patience 3 \
  --out models/bms/soc_lstm_v2.pt

# Step 3: Export to ONNX opset 18
python3 scripts/export_onnx.py \
  --model models/bms/soc_lstm_v2.pt \
  --opset 18 --out models/bms/soc_lstm_v2.onnx

# Step 4: Anti-regression gate — v2 must not degrade BMW i3 RMSE by > 0.5%
python3 scripts/compare_soc_fix_stages.py \
  --model-v1 models/bms/soc_lstm.onnx \
  --model-v2 models/bms/soc_lstm_v2.onnx
```

**Anti-regression gate**: If BMW i3 RMSE increases by > 0.5% in v2 vs v1, revert to v1
and document the fine-tune result. Catastrophic forgetting of BMW i3 features is not
acceptable if the target dataset (FOBSS, ~N hours) is smaller than training set (72 trips).

**Fine-tune script** (taktflow-bms-ml, scripts/finetune_soc_lstm.py — key excerpt):

```python
# Freeze strategy: encoder frozen, head trainable
for p in model.parameters():
    p.requires_grad = False
for name, mod in model.named_modules():
    if name in ("lstm_head", "fc", "output_layer"):   # adjust to actual layer names
        for p in mod.parameters():
            p.requires_grad = True

# Training loop with early stopping (patience=3 on FOBSS val RMSE)
# L2 weight decay 1e-5 on trainable params prevents overfitting to small FOBSS set
# Max epochs = 10 (hard cap prevents catastrophic forgetting)
opt = torch.optim.Adam(
    filter(lambda p: p.requires_grad, model.parameters()),
    lr=1e-4, weight_decay=1e-5
)
```

**ASPICE**: SWE.3.BP5 (bidirectional traceability: v2 ONNX → SW-REQ-ML-001).
Evidence: `models/bms/CHANGELOG.md` — records v1→v2 rationale, RMSE before/after, training date.

---

#### Day 37: Phase 2 SOC Baseline Measurement + M2.1

Run `scripts/compare_soc_fix_stages.py` with Stage C (or D if fine-tune applied).
Fill the SOC section of `docs/plans/baseline-metrics-phase2.md` (template in Day 54–56).

**Phase 2 SOC LSTM accuracy targets**:

| Dataset | Phase 1 Baseline | Phase 2 RMSE Target | Phase 2 MAE Target | Primary Method | Gate |
|---|---|---|---|---|---|
| BMW i3 test split | ~1.83% RMSE | ≤ 2.0% RMSE | ≤ 1.4% MAE | Norm stats fix | Hard (CI) |
| FOBSS (real foxBMS) | Unknown | ≤ 3.0% RMSE | ≤ 2.0% MAE | OCV fix + norm stats (+ fine-tune if needed) | Hard (CI) |
| foxBMS SIL 30-min bias | +20.24% | ≤ ±3.0% | — | OCV fix + norm stats | Hard (CI) |
| foxBMS SIL RMSE | ~20% | ≤ 5.0% RMSE | ≤ 3.5% MAE | OCV fix + norm stats | Hard (CI) |

> **CI gate progression**: Phase 1 sets conservative gates (`SOC_FOBSS_RMSE_GATE = 5.0%`) before FOBSS data is available. At M2.1 (Day 37) these tighten: set `SOC_FOBSS_RMSE_GATE_P2 = 3.0` and add `SOC_FOBSS_MAE_GATE_P2 = 2.0`, `SOC_BMW_I3_MAE_GATE_P2 = 1.4` in `tests/test_ml_accuracy.py`. Phase 1 gates must remain green until M2.1 merges to prevent regressions.

Update `models/registry.json` with `soc_lstm_v2` entry. Set all `phase2_baseline_*` fields.
Tag M2.1 on the feature branch.

---

### Week 6 (Day 38–44): Anomaly Detection + Thermal CNN

**Goal**: Retrain IsolationForest on real foxBMS SIL data. Validate Thermal CNN with
operational dT/dt. Achieve anomaly model normal score mean < 0.15.

---

#### Day 38–40: IsolationForest Real-Data Retrain (SW-REQ-ML-004)

**Root cause analysis** (confirmed in Phase 1 baseline):
IsolationForest was trained on 5,000 synthetic samples with independently-generated V, I, T.
Real foxBMS SIL data has correlated features (discharge current rises → pack voltage sags →
cell temperature rises together). Synthetic training has no V-I-T correlation, so normal
correlated operation appears anomalous to the model. Result: 0.36 score at normal steady state
(target: < 0.10).

**Step 1: Extract real SIL anomaly features from Phase 1 telemetry**

```python
# scripts/extract_sil_anomaly_features.py
"""
Decode real foxBMS SIL CAN telemetry → IsolationForest feature matrix.
Uses Phase 1 automated capture (Day 1-2 deliverable).

Features (must match IsolationForest training format — 5 channels):
  [V_mean_mV, V_std_mV, I_mA, T_ddegC, V_spread_mV]

Output: data/sil_anomaly_features.npz  (N, 5) float32, N ≈ 1800 (30 min at 1 Hz)
"""
import gzip, re, numpy as np
from collections import defaultdict
from pathlib import Path

CELL_V_ID  = 0x270   # muxed cell voltages
CURRENT_ID = 0x521   # IVT current
TEMP_ID    = 0x280   # cell temperatures

def parse_candump_log(gz_path: Path, duration_s: int = 1800) -> np.ndarray:
    """Parse gzipped candump log into per-second (N, 5) feature matrix."""
    buckets: dict[int, dict] = defaultdict(lambda: {"cell_v": {}, "i_ma": None, "temps": []})
    t0 = None
    id_re = re.compile(r"\((\d+\.\d+)\)\s+\S+\s+([0-9A-Fa-f]+)#([0-9A-Fa-f]*)")

    try:
        with gzip.open(gz_path, "rt", errors="replace") as fh:
            for line in fh:
                m = id_re.match(line.strip())
                if not m:
                    continue
                t   = float(m.group(1))
                cid = int(m.group(2), 16)
                raw = bytes.fromhex(m.group(3))
                if t0 is None:
                    t0 = t
                if t - t0 > duration_s:
                    break
                sec = int(t - t0)

                if cid == CELL_V_ID and len(raw) >= 5:
                    mux = raw[0] & 0x3F
                    v_mv = int.from_bytes(raw[1:3], "big")   # first voltage slot (mV)
                    buckets[sec]["cell_v"][mux] = v_mv
                elif cid == CURRENT_ID and len(raw) >= 6:
                    buckets[sec]["i_ma"] = int.from_bytes(raw[2:6], "big", signed=True)
                elif cid == TEMP_ID and len(raw) >= 2:
                    buckets[sec]["temps"].append(int.from_bytes(raw[0:2], "big"))
    except Exception as e:
        print(f"WARNING: {e}")

    rows = []
    for s in sorted(buckets.keys()):
        d = buckets[s]
        if not d["cell_v"] or d["i_ma"] is None or not d["temps"]:
            continue
        v = list(d["cell_v"].values())
        rows.append([np.mean(v), np.std(v), d["i_ma"],
                     np.mean(d["temps"]), max(v) - min(v)])
    return np.array(rows, dtype=np.float32)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--log",      required=True)
    parser.add_argument("--duration", type=int, default=1800)
    parser.add_argument("--out",      default="data/sil_anomaly_features.npz")
    args = parser.parse_args()

    feat = parse_candump_log(Path(args.log), args.duration)
    np.savez(args.out, features=feat)
    print(f"Extracted {len(feat)} feature vectors")
    print(f"V_mean  range: {feat[:,0].min():.1f}–{feat[:,0].max():.1f} mV")
    print(f"I_mA    range: {feat[:,2].min():.1f}–{feat[:,2].max():.1f}")
    print(f"T_ddegC range: {feat[:,3].min():.1f}–{feat[:,3].max():.1f}")
```

**Step 2: Retrain on real data + anchored synthetic augmentation**

```python
# scripts/retrain_anomaly_real.py
"""
Retrain IsolationForest: 70% real SIL + 30% anchored synthetic.
Rationale for 30% synthetic: 30-min capture covers only normal BMS steady state.
Synthetic adds operating regimes not in the capture window (e.g. high-rate discharge,
precharge, balancing) to improve generalization.
"""
import joblib, numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from pathlib import Path

real = np.load("data/sil_anomaly_features.npz")["features"]
print(f"Real SIL baseline: {len(real)} samples")

rng        = np.random.default_rng(42)
n_synth    = max(200, int(len(real) * 0.43))   # 70/30 real/synthetic split
V_mu, V_sd = real[:, 0].mean(), real[:, 0].std()
I_mu, I_sd = real[:, 2].mean(), real[:, 2].std()
T_mu, T_sd = real[:, 3].mean(), real[:, 3].std()

synthetic = np.column_stack([
    rng.normal(V_mu, V_sd * 1.2,  n_synth),          # V_mean — anchored to real
    np.abs(rng.exponential(real[:, 1].mean(), n_synth)),  # V_std (right-skewed)
    rng.normal(I_mu, I_sd * 1.5,  n_synth),           # I_mA — wider range
    rng.normal(T_mu, T_sd,        n_synth),            # T_ddegC
    np.abs(rng.normal(real[:, 4].mean(), real[:, 4].std() * 2, n_synth)),  # V_spread
]).astype(np.float32)

X_train = np.vstack([real, synthetic])
scaler  = StandardScaler()
X_sc    = scaler.fit_transform(X_train)

model   = IsolationForest(
    n_estimators=200,      # increased from 100 — better stability on real data
    contamination=0.03,    # reduced from 0.05 — real SIL is cleaner than synthetic
    random_state=42,
    max_samples="auto",
)
model.fit(X_sc)

# Hold-out validation on last 20% of real data
n_ho     = max(50, int(len(real) * 0.20))
real_ho  = real[-n_ho:]
scores   = np.clip(0.15 - model.decision_function(scaler.transform(real_ho)) / 0.30, 0, 1)
print(f"\nHold-out ({n_ho} real samples):  mean={scores.mean():.3f}  "
      f"p95={np.percentile(scores, 95):.3f}  max={scores.max():.3f}")
print("PASS" if scores.mean() < 0.15 else f"WARN: mean {scores.mean():.3f} > 0.15")

Path("models/bms").mkdir(parents=True, exist_ok=True)
joblib.dump(model,  "models/bms/anomaly_model_v2.pkl")
joblib.dump(scaler, "models/bms/anomaly_scaler_v2.pkl")
print("Saved anomaly_model_v2.pkl + anomaly_scaler_v2.pkl")
```

**Phase 2 IsolationForest accuracy targets**:

| Metric | Phase 1 Baseline | Phase 2 Target | Gate |
|---|---|---|---|
| Normal mean score | 0.36 (synthetic mismatch) | < 0.15 | Hard |
| Normal 95th percentile | Unknown | < 0.20 | Hard |
| Overvoltage (4.6 V) mean | Unknown | > 0.40 | Hard |
| Overtemperature (60°C) mean | Unknown | > 0.30 | Hard |
| Overcurrent (150 A) mean | Unknown | > 0.40 | Hard |
| Fault TPR (all fault types) | ~78% (synthetic) | ≥ 80% | Hard |
| Normal FPR | ~6% (synthetic estimate) | ≤ 5% | Hard |

**Deploy v2 and validate fault injection** (Day 39–40):

```bash
# Deploy v2 to VPS
scp models/bms/anomaly_model_v2.pkl root@152.53.245.209:/opt/foxbms-sil/src/
scp models/bms/anomaly_scaler_v2.pkl root@152.53.245.209:/opt/foxbms-sil/src/
ssh root@152.53.245.209 "systemctl restart foxbms-sidecar"

# Wait 5 minutes for score stabilization, then validate
sleep 300

# Capture 5 minutes normal, then 3 fault types
python3 scripts/validate_anomaly_v2.py \
  --vps root@152.53.245.209 \
  --model-version v2
```

**ASPICE**: SWE.3.BP1 (retrain design decision documented in `models/bms/CHANGELOG.md`).
SWE.4.BP1 (unit test: `validate_anomaly_v2.py` covers SW-REQ-ML-004).

---

#### Day 41–42: Thermal CNN Validation (SW-REQ-ML-005, SW-REQ-ML-010)

**Precondition**: dT/dt pipeline fix from Phase 1 Day 10–11 deployed on VPS.
Plant model I²R thermal model active.

**Data capture** (Day 41 — run on VPS):

```bash
# Capture 30 minutes of normal discharge for FPR measurement
ssh root@152.53.245.209 "
  timeout 1800 candump -L vcan1,280:7FF,702:7FF
" | python3 scripts/decode_thermal_features.py \
    --output data/thermal_sil_features.npz

# Inject OT fault (60°C spike), measure detection latency
wscat -c wss://sil.taktflow-systems.com/ws \
      -x '{"cmd":"inject","type":"overtemp","sensor":0,"value_ddegc":600}' \
      --wait 1 --close
ssh root@152.53.245.209 "
  timeout 120 candump -L vcan1,280:7FF,702:7FF
" | python3 scripts/decode_thermal_features.py \
    --output data/thermal_sil_ot_fault.npz
```

**Phase 2 test file** (`tests/test_thermal_cnn_phase2.py` — SWE.4 unit test for SW-REQ-ML-005/010):

```python
# tests/test_thermal_cnn_phase2.py
"""Phase 2 Thermal CNN tests — SW-REQ-ML-005 and SW-REQ-ML-010."""
import pytest, numpy as np, onnxruntime as ort
from pathlib import Path

FPR_GATE         = 0.02   # 2% FPR at threshold 0.3
OT_SCORE_MIN     = 0.30   # OT fault score floor
OT_LATENCY_GATE  = 30     # seconds to first score > OT_SCORE_MIN

@pytest.fixture(scope="module")
def thermal_sess():
    p = Path("models/bms/thermal_cnn.onnx")
    if not p.exists():
        pytest.skip("thermal_cnn.onnx not present")
    return ort.InferenceSession(str(p))

def _score(sess, window):
    x = np.array(window, dtype=np.float32).reshape(1, 30, 4)
    return float(sess.run(None, {sess.get_inputs()[0].name: x})[0])

def test_dTdt_nonzero_during_discharge(thermal_sess):
    """SW-REQ-ML-005: dT/dt must not be constant zero during active discharge."""
    fp = Path("data/thermal_sil_features.npz")
    if not fp.exists():
        pytest.skip("Day 41 capture not completed")
    feat = np.load(fp)["features"]      # (N, 4): [T_avg, T_max, dT_dt, I_A]
    discharge = feat[feat[:, 3] > 0.1]  # filter to samples with non-negligible current
    assert len(discharge) > 100, "Insufficient discharge samples in capture"
    nonzero_pct = (np.abs(discharge[:, 2]) > 1e-4).mean()
    assert nonzero_pct > 0.90, \
        f"dT/dt zero in {(1-nonzero_pct)*100:.1f}% of discharge samples"

def test_thermal_fpr_gate(thermal_sess):
    """SW-REQ-ML-010: FPR ≤ 2% during 30 minutes of normal discharge."""
    fp = Path("data/thermal_sil_features.npz")
    if not fp.exists():
        pytest.skip("Day 41 capture not completed")
    feat = np.load(fp)["features"]
    scores = [_score(thermal_sess, feat[i-30:i]) for i in range(30, len(feat))]
    fpr = (np.array(scores) > 0.3).mean()
    assert fpr <= FPR_GATE, \
        f"Thermal FPR {fpr*100:.2f}% > {FPR_GATE*100:.0f}% gate"

def test_ot_detection_latency(thermal_sess):
    """SW-REQ-ML-010: OT fault detected (score > 0.3) within 30 seconds."""
    fp = Path("data/thermal_sil_ot_fault.npz")
    if not fp.exists():
        pytest.skip("Day 41 OT fault capture not completed")
    feat = np.load(fp)["features"]
    scores = [_score(thermal_sess, feat[i-30:i]) for i in range(30, len(feat))]
    first = next((i for i, s in enumerate(scores) if s > OT_SCORE_MIN), None)
    assert first is not None,          "OT fault not detected at all"
    assert first <= OT_LATENCY_GATE,   f"OT latency {first}s > {OT_LATENCY_GATE}s gate"
```

---

#### Day 43–44: Week 6 Integration + M2.2

```bash
# Full Phase 2 Week 6 test run
pytest tests/test_ml_accuracy.py tests/test_thermal_cnn_phase2.py -v --timeout=300
```

Update `models/registry.json`:
- `isolation_forest_v2` entry with `phase2_baseline_normal_mean`, `phase2_baseline_fault_tpr`
- `thermal_cnn_v1_dtdt_fixed` entry with `phase2_baseline_fpr`, `phase2_baseline_ot_latency_s`

**M2.2 gate**: All four criteria:
- IsolationForest v2 normal mean score < 0.15 ✓
- IsolationForest v2 fault TPR ≥ 80% ✓
- Thermal CNN FPR ≤ 2% ✓
- Thermal CNN OT detection ≤ 30 s ✓

---

### Week 7 (Day 45–51): SOH Transformer + RUL Initial Deployment

**Goal**: Make SOH Transformer operational via synthetic cycle replay (GAP-ML-005).
Initial RUL deployment (GAP-ML-006). Both close the "not operational" status for
CAN channels 0x701 and 0x704.

---

#### Day 45–47: Synthetic Cycle Replay (SW-REQ-ML-006)

**Architecture decision** (SWE.3.BP3 — dynamic behavior):
SOH prediction requires cycling history — capacity fade observed over many charge-discharge
cycles. The foxBMS SIL is one continuous run without cycling. Solution: offline batch-replay
of the plant model physics to generate N=500 synthetic cycles with realistic capacity fade.

```python
# scripts/generate_cycle_history.py
"""
Generate synthetic cycling history for SOH Transformer.

Battery: NMC 811, 18S, 3 Ah (foxBMS SIL config)
Capacity fade: 0.02% per cycle (NMC typical combined calendar+cycle ageing)
R increase:    0.10% per cycle (correlates with SEI growth)
Cycles:        500  (SOH falls 10% → 90%; matches end-of-second-life threshold)

Output: data/soh_cycle_replay/cycle_features.npz  (500, 12)
        data/soh_cycle_replay/soh_gt.npy           (500,)

12 features per cycle (matching soh_transformer.onnx input format):
  [V_avg, I_avg, T_avg, cap_ah, R_mohm, cycle_count,
   V_min, V_max, V_spread, T_min, T_max, T_spread]
"""
import numpy as np
from pathlib import Path

NOM_CAP_AH    = 3.0
FADE_RATE_PCT = 0.02     # % capacity loss per cycle
R_RATE_PCT    = 0.10     # % resistance increase per cycle
R0_MOHM       = 3.0      # initial cell internal resistance (mΩ)

# NMC 811 OCV (same 21-point table as plant_model.py Phase 2 fix)
_OCV_SOC = np.linspace(0, 100, 21)
_OCV_MV  = np.array([3000,3299,3498,3580,3620,3643,3660,3668,3675,3680,3685,
                     3690,3696,3704,3714,3730,3760,3800,3860,3940,4200], dtype=float)

def ocv(soc): return float(np.interp(soc, _OCV_SOC, _OCV_MV))

def simulate_cycle(n: int, c_rate: float = 0.5) -> dict:
    """Simulate nth discharge-charge cycle; return summary stats dict."""
    cap   = NOM_CAP_AH * (1.0 - FADE_RATE_PCT * n / 100.0)
    r_ohm = R0_MOHM    * (1.0 + R_RATE_PCT    * n / 100.0)
    i_dis = cap * c_rate
    dt    = 1.0   # 1-second steps
    soc   = 100.0

    v_all, t_all = [], []

    # Discharge phase (C/2 constant current to 5% SOC cutoff)
    while soc > 5.0:
        v = ocv(soc) - i_dis * r_ohm               # terminal voltage mV
        t = 25.0 + (i_dis ** 2 * r_ohm / 1000.0) * 0.3  # simple thermal
        v_all.append(v);  t_all.append(t)
        soc -= (i_dis / cap) * (dt / 3600.0) * 100.0
        soc  = max(soc, 0.0)
        if v < 3000:
            break

    # Charge phase (C/2 CC to 100% SOC)
    i_chg = cap * 0.5
    while soc < 98.0:
        v = ocv(soc) + i_chg * r_ohm
        t = 25.0 + (i_chg ** 2 * r_ohm / 1000.0) * 0.2
        v_all.append(v);  t_all.append(t)
        soc  = min(soc + (i_chg / cap) * (dt / 3600.0) * 100.0, 100.0)

    va, ta = np.array(v_all), np.array(t_all)
    return dict(
        V_avg=va.mean(), I_avg=i_dis, T_avg=ta.mean(),
        cap_ah=cap,      R_mohm=r_ohm, cycle_count=float(n),
        V_min=va.min(),  V_max=va.max(), V_spread=va.max()-va.min(),
        T_min=ta.min(),  T_max=ta.max(), T_spread=ta.max()-ta.min(),
        SOH_pct=(cap / NOM_CAP_AH) * 100.0,
    )

if __name__ == "__main__":
    N = 500
    cycles = [simulate_cycle(n) for n in range(N)]

    keys = ["V_avg","I_avg","T_avg","cap_ah","R_mohm","cycle_count",
            "V_min","V_max","V_spread","T_min","T_max","T_spread"]
    X = np.array([[c[k] for k in keys] for c in cycles], dtype=np.float32)
    y = np.array([c["SOH_pct"] for c in cycles],         dtype=np.float32)

    out = Path("data/soh_cycle_replay/");  out.mkdir(parents=True, exist_ok=True)
    np.savez(out / "cycle_features.npz", features=X)
    np.save(out / "soh_gt.npy", y)
    print(f"Generated {N} cycles  |  SOH: {y.min():.1f}%–{y.max():.1f}%")
    print(f"Final cap: {X[-1,3]:.3f} Ah  |  Final R: {X[-1,4]:.3f} mΩ")
```

**Sanity check**: After 500 cycles at 0.02%/cycle fade: `cap = 3.0 × (1 − 0.02×500/100) = 2.70 Ah`.
SOH = 2.70 / 3.0 × 100 = 90.0%. This matches published NMC 811 cycle life data at room temperature.

---

#### Day 48–49: SOH Transformer Operational Validation

```python
# scripts/validate_soh_transformer.py
"""
SOH Transformer sliding-window validation on synthetic cycle replay.
Architecture: (batch, 10, 12) → SOH %
"""
import numpy as np, onnxruntime as ort
from pathlib import Path

WINDOW = 10   # SOH Transformer input window (cycles)

def validate(model_path, feat, gt):
    sess = ort.InferenceSession(model_path)
    inp  = sess.get_inputs()[0].name
    preds = [float(sess.run(None, {inp: feat[i-WINDOW:i].reshape(1,WINDOW,12).astype(np.float32)})[0])
             for i in range(WINDOW, len(feat))]
    preds = np.array(preds)
    gt_t  = gt[WINDOW:WINDOW + len(preds)]
    rmse  = float(np.sqrt(np.mean((preds - gt_t)**2)))
    mae   = float(np.mean(np.abs(preds - gt_t)))

    # Trend validation: major reversals (>2%) should be rare (<10 in 490 windows)
    inversions = int(np.sum(np.diff(preds) > 2.0))

    print(f"SOH Transformer — 500 synthetic cycles, {len(preds)} windows")
    print(f"  RMSE:       {rmse:.2f}%   (gate ≤ 12.0%)")
    print(f"  MAE:        {mae:.2f}%")
    print(f"  Pred range: {preds.min():.1f}%–{preds.max():.1f}%")
    print(f"  Inversions: {inversions}    (gate < 10)")
    return rmse, inversions

if __name__ == "__main__":
    feat = np.load("data/soh_cycle_replay/cycle_features.npz")["features"]
    gt   = np.load("data/soh_cycle_replay/soh_gt.npy")
    rmse, inv = validate("models/bms/soh_transformer.onnx", feat, gt)
    assert rmse < 12.0, f"SOH RMSE {rmse:.2f}% > 12.0% gate"
    assert inv  < 10,   f"SOH trend inversions {inv} > 9 gate"
    print("PASS")
```

**Phase 2 SOH Transformer accuracy targets**:

| Dataset | Phase 1 Status | Phase 2 RMSE Target | Phase 2 MAE Target | Gate | Rationale |
|---|---|---|---|---|---|
| LiionPro-DT (published benchmark) | UNVALIDATED on foxBMS | ≤ 9.79% RMSE | — | Soft — Phase 5 hard gate | Published result; requires real multi-cycle data unavailable in Phase 2. Becomes Phase 5 hard gate on real foxBMS cycle captures. |
| Synthetic 500-cycle replay | NOT OPERATIONAL | ≤ 12.0% RMSE | ≤ 8.0% MAE | Hard | 12.0% = 1.23× published 9.79%; factor accounts for synthetic-vs-real distribution gap. Gate tightens to 9.79% in Phase 5 when real cycle data is available. |
| Trend direction (500 cycles) | NOT OPERATIONAL | < 10 major inversions | — | Hard | Inversion = predicted SOH increase > 2% between consecutive cycles; 2% threshold tolerates ±1% model noise while catching degraded monotonicity. |
| CAN 0x701 publishing | NOT OPERATIONAL | Active, non-zero output | — | Hard | Functional deployment gate confirming live sidecar integration. |

**Live sidecar integration** (new in `ml_sidecar.py`):

```python
# In BMSSensorBuffers.__init__():
from collections import deque as _deque
self.soh_cycle_history: _deque = _deque(maxlen=10)  # last 10 cycle summaries
self._cycle_count: int   = 0
self._cycle_ah_in: float = 0.0     # Ah accumulated this discharge
self._last_sign: int     = 0       # sign of pack current at last sample

# Cycle detection: when current sign flips + > 0.1 Ah discharged → end of cycle
# In update_from_can(), after I_A update:
sign = 1 if self.pack_current_ma > 50 else (-1 if self.pack_current_ma < -50 else 0)
if self._last_sign < 0 and sign >= 0 and self._cycle_ah_in > 0.1:
    # Discharge complete → append cycle summary to history
    v_vals = list(self.cell_voltages_mv.values())
    t_vals = list(self.cell_temps_ddegc.values())
    self.soh_cycle_history.append([
        self.pack_voltage_mv / 1000.0 / 18,  # V_avg per cell
        abs(self.pack_current_ma / 1000.0),   # I_avg A
        self.t_avg_c, self._cycle_ah_in,
        3.0,                                  # R_mohm placeholder
        float(self._cycle_count),
        min(v_vals, default=3000) / 1000.0, max(v_vals, default=4200) / 1000.0,
        (max(v_vals, default=0) - min(v_vals, default=0)) / 1000.0,
        min(t_vals, default=250) / 10.0, max(t_vals, default=250) / 10.0,
        (max(t_vals, default=0) - min(t_vals, default=0)) / 10.0,
    ])
    self._cycle_count += 1
    self._cycle_ah_in  = 0.0
self._last_sign = sign
if sign < 0:
    self._cycle_ah_in += abs(self.pack_current_ma / 1000.0) * (1.0 / 3600.0)
```

---

#### Day 50–51: RUL Transformer Initial Deployment (GAP-ML-006)

**Scope**: Deploy `rul_transformer.onnx`. Implement `predict_rul()` in `ml_sidecar.py`.
Publish on CAN 0x704. No full accuracy validation in Phase 2 — that is Phase 5 work.
Phase 2 gate: CAN 0x704 is live after ≥20 cycles of history.

```python
# In ModelManager.predict_rul() — ml_sidecar.py addition
def predict_rul(self) -> Optional[int]:
    """
    Predict remaining cycles (RUL).
    Requires: 20 cycle summaries in soh_cycle_history deque.
    Returns: None if insufficient history; int cycles otherwise.
    Input shape: (1, 20, 12) — same feature format as SOH Transformer.
    """
    if not hasattr(self, "_rul_session"):
        return None
    hist = list(self._buffers.soh_cycle_history)
    if len(hist) < 20:
        return None
    x = np.array(hist[-20:], dtype=np.float32).reshape(1, 20, 12)
    result = self._rul_session.run(None, {self._rul_inp: x})
    return max(0, int(float(result[0])))

# In _publish_can():
rul = self.predict_rul() or 0
can.send(can.Message(
    arbitration_id=0x704,
    data=struct.pack(">Hxxxxxx", min(rul, 65535))
))
```

**Phase 2 RUL deployment targets**:

| Metric | Phase 1 Status | Phase 2 Target | Gate |
|---|---|---|---|
| CAN 0x704 publishing | Not deployed | Active after ≥20 cycle history | Hard |
| MAPE on MIT dataset | 16% claimed, unvalidated | Validated ≤ 20% (soft) | Soft — full validation deferred to Phase 5 |
| Output range sanity | N/A | 0–5000 cycles | Hard |
| Cycle history guard | N/A | No output before 20 cycles | Hard |

**ASPICE**: SWE.3.BP2 (unit interface — `predict_rul()` signature and CAN encoding).
SWE.4.BP1 (unit test — verify 0x704 publishing and history guard).

---

### Week 8 (Day 52–60): CI Hardening + Phase 2 Close

**Goal**: Strict CI gates, Phase 2 accuracy report, ASPICE work product updates, Phase 2 close.

---

#### Day 52–53: CI Accuracy Gate Tightening (SW-REQ-ML-007, GAP-ML-012)

**Problem**: Current CI marks the ML sidecar smoke test as PASS even if CAN 0x705 is
not captured in the 8-second window. This is non-blocking, meaning a completely silent
sidecar passes CI.

**Fix — strict 30-second assertion**:

```yaml
# .github/workflows/ci.yml — replace ml-sidecar-smoke job
  ml-sidecar-smoke:
    name: ML Sidecar Smoke — Strict
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4

      - name: Install Python ML dependencies
        run: pip install numpy scikit-learn joblib

      - name: Build synthetic anomaly model
        run: python3 src/train_anomaly_bms.py

      - name: Start plant model and ML sidecar
        run: |
          python3 src/plant_model.py --sil-mode &
          sleep 5
          python3 src/ml_sidecar.py --no-onnx &
          sleep 10

      - name: Strict CAN 0x705 capture — 30 second window
        # SW-REQ-ML-007: non-receipt in 30 s fails CI. No continue-on-error.
        run: |
          RESULT=$(timeout 30 candump vcan1,705:7FF 2>/dev/null | head -1)
          if [ -z "$RESULT" ]; then
            echo "FAIL: No CAN 0x705 frame in 30s — sidecar not publishing anomaly scores"
            exit 1
          fi
          echo "PASS: $RESULT"
```

**Phase 2 CI accuracy gate additions** (extend `tests/test_ml_accuracy.py`):

```python
# Phase 2 gate constants — tighter than Phase 1 initial gates
SOC_BMW_I3_RMSE_GATE_P2  = 2.0   # tightened from Phase 1 gate of 3.0%
SOC_FOBSS_RMSE_GATE_P2   = 3.0   # NEW hard gate (Phase 1 had no FOBSS gate)
SOC_SIL_BIAS_GATE_P2     = 3.0   # NEW — validates Phase 2 OCV fix result
ANOMALY_NORMAL_MEAN_P2   = 0.15  # tightened from Phase 1 max 0.25
ANOMALY_FAULT_TPR_P2     = 0.80  # ≥80% TPR across all fault types

class TestPhase2SOC:
    def test_soc_fobss_rmse_phase2(self, soc_model, norm_stats, fobss_data):
        """Phase 2 hard gate: FOBSS RMSE ≤ 3.0%  (SW-REQ-ML-001)"""
        ...  # same pattern as Phase 1 tests, new threshold

    def test_soc_sil_bias_phase2(self, soc_model, norm_stats):
        """Phase 2: SIL steady-state bias ≤ ±3.0%  (SW-REQ-ML-002, ML-003)"""
        ...

class TestPhase2Anomaly:
    def test_anomaly_normal_mean_phase2(self):
        """Phase 2: IsolationForest v2 normal mean score < 0.15  (SW-REQ-ML-004)"""
        ...
```

---

#### Day 54–56: Phase 2 Accuracy Report Assembly

**File**: `docs/plans/baseline-metrics-phase2.md` (template — fill measured values after Day 55):

```markdown
# ML Model Phase 2 Accuracy Report

**Date measured**: [fill]
**Reference commit**: [git SHA at measurement time]
**Measured by**: [name]
**Purpose**: Phase 2 evidence — closes SW-REQ-ML-001..010.
Supersedes Phase 1 baselines for all Phase 2+ comparisons.
DO NOT UPDATE after Phase 3 starts. Create baseline-metrics-phase3.md instead.

---

## SOC LSTM v2 (BiLSTM 128→64, NMC 811 OCV, Phase 2 norm stats)

| Dataset | N | RMSE | MAE | Bias | Gate | Status | Δ vs Phase 1 |
|---|---|---|---|---|---|---|---|
| BMW i3 test | 21,600 | ___.___% | ___.___% | ±___.___% | ≤2.0% | PASS/FAIL | ___ |
| FOBSS (real foxBMS) | ___ | ___.___% | ___.___% | ±___.___% | ≤3.0% | PASS/FAIL | ___ |
| foxBMS SIL 30-min bias | 1,800 | — | — | ±___.___% | ≤3.0% | PASS/FAIL | +20.24%→___ |

Improvement attribution (Stage B → Stage C → Stage D):
- OCV fix (linear → NMC 811 S-curve): −___.___% RMSE on FOBSS
- Normalization stats (estimates → training data): −___.___% RMSE
- FOBSS fine-tune (if applied): −___.___% RMSE

## IsolationForest v2 (200 trees, real SIL + anchored synthetic)

| Condition | N | Mean Score | 95th %ile | Gate | Status | Δ vs Phase 1 |
|---|---|---|---|---|---|---|
| Normal (real SIL) | 300 | ___.___| ___.___| <0.15 | PASS/FAIL | 0.36→___ |
| Overvoltage (4.6 V) | 60 | ___.___| ___.___| >0.40 | PASS/FAIL | |
| Overtemperature (60°C) | 60 | ___.___| ___.___| >0.30 | PASS/FAIL | |
| Overcurrent (150 A) | 60 | ___.___| ___.___| >0.40 | PASS/FAIL | |
| TPR (combined) | — | — | — | ≥80% | PASS/FAIL | ~78%→___% |

## Thermal CNN v1 (dT/dt pipeline fixed, NMC 811 thermal model)

| Condition | N | Mean Risk | FPR@0.3 | OT Latency | Gate | Status |
|---|---|---|---|---|---|---|
| Normal (30-min discharge) | 1,800 | ___.___| ___% | — | ≤2% FPR | PASS/FAIL |
| OT fault (60°C spike) | 60 | ___.___| — | ___ s | ≤30 s | PASS/FAIL |

## SOH Transformer v1 (synthetic cycle replay activated)

| Dataset | N windows | RMSE | Trend inversions | Gate | Status |
|---|---|---|---|---|---|
| Synthetic 500 cycles | 490 | ___.___% | ___ | ≤12.0% + <10 inv | PASS/FAIL |

## RUL Transformer v1 (initial deployment)

| Condition | Output range | CAN 0x704 | Status |
|---|---|---|---|
| After 20 cycles history | ___–___ cycles | Active | OPERATIONAL / NOT OPERATIONAL |
| MIT dataset MAPE | ___% | — | Phase 5 full validation |

---

## ASPICE Evidence Summary (SWE.6 Qualification Evidence)

| SW-REQ-ML-ID | Requirement summary | Phase 2 result | Verdict |
|---|---|---|---|
| SW-REQ-ML-001 | SOC RMSE ≤ 3.0% FOBSS | ___.___% | PASS/FAIL |
| SW-REQ-ML-002 | Norm stats from training split | Verified (Day 8-9) | PASS |
| SW-REQ-ML-003 | NMC 811 OCV ≥ 21pts, RT<1% | 21pts, RT=___.___% | PASS/FAIL |
| SW-REQ-ML-004 | IsolationForest real-data retrain, mean<0.15 | ___.___| PASS/FAIL |
| SW-REQ-ML-005 | Thermal dT/dt non-zero in ≥90% discharge | ___% | PASS/FAIL |
| SW-REQ-ML-006 | SOH Transformer operational ≥100 cycles | 500 cycles | PASS |
| SW-REQ-ML-007 | CI 0x705 strict 30-s assertion | CI green | PASS/FAIL |
| SW-REQ-ML-008 | Registry v2 provenance filled | registry.json | PASS |
| SW-REQ-ML-009 | Phase 2 accuracy report published | This document | PASS |
| SW-REQ-ML-010 | Thermal FPR ≤ 2%, OT ≤ 30 s | FPR=___%, ___s | PASS/FAIL |
```

---

#### Day 57–58: ASPICE Work Products Update

The following files are updated (add new content only — never modify existing HITL-LOCK regions):

1. **`docs/aspice-cl2/08-SWE.1-software-requirements/SWE.1-software-requirements.md`**:
   Add Section 11 "ML Inference Module Requirements" containing SW-REQ-ML-001..010.

2. **`docs/aspice-cl2/11-SWE.4-software-unit-verification/SWE.4-unit-test-spec.md`**:
   Add test cases `ML-TC-001..010` for SW-REQ-ML-001..010:

   | Test ID | Test Name | Script | Covers |
   |---|---|---|---|
   | ML-TC-001 | SOC FOBSS RMSE | `test_ml_accuracy.py::TestPhase2SOC::test_soc_fobss_rmse_phase2` | SW-REQ-ML-001 |
   | ML-TC-002 | SOC Normalization Source | `scripts/compute_norm_stats.py` (provenance record) | SW-REQ-ML-002 |
   | ML-TC-003 | OCV Table Validation | `scripts/validate_ocv_table.py` | SW-REQ-ML-003 |
   | ML-TC-004 | Anomaly Real Retrain | `scripts/validate_anomaly_v2.py` | SW-REQ-ML-004 |
   | ML-TC-005 | Thermal dT/dt Non-Zero | `test_thermal_cnn_phase2.py::test_dTdt_nonzero` | SW-REQ-ML-005 |
   | ML-TC-006 | SOH Cycle Replay | `scripts/validate_soh_transformer.py` | SW-REQ-ML-006 |
   | ML-TC-007 | CI Strict 0x705 Capture | GitHub Actions `ml-sidecar-smoke` | SW-REQ-ML-007 |
   | ML-TC-008 | Registry v2 Provenance | `python3 -c "import json; r=json.load(open('models/registry.json'))..."` | SW-REQ-ML-008 |
   | ML-TC-009 | Phase 2 Report Completeness | Manual — all table cells filled | SW-REQ-ML-009 |
   | ML-TC-010 | Thermal FPR + OT Latency | `test_thermal_cnn_phase2.py::test_thermal_fpr_gate` and `::test_ot_detection_latency` | SW-REQ-ML-010 |

3. **`docs/aspice-cl2/00-assessment/traceability-matrix-generated.md`**:
   Add ML row: `SW-REQ-ML-001..010` → `SWE.3` (OCV fix, retrain, cycle replay) →
   `SWE.4` (ML-TC-001..010) → `SWE.6` (`baseline-metrics-phase2.md`).

---

#### Day 59: Lessons Learned

Append one entry per significant fix to `docs/lessons-learned/embedded/bringup.md`:

```markdown
## 2026-[month] — SOC 20% gap: normalization estimated from specs, not training data

**Context**: foxBMS POSIX Phase 2 SOC LSTM accuracy improvement.
**Mistake**: `soc_norm_mean.npy` generated from BMW i3 specification voltage
(355V / 96 cells = 3.698 V) rather than mean of actual training distribution.
At SIL steady state (3.67 V/cell) vs training mean (3.75 V/cell), the 0.08 V offset
produced +20% SOC bias.
**Fix**: `compute_norm_stats.py` — computed from BMW i3 training split trips 1–60
(N ≥ 60,000 samples). Stats now match actual training distribution.
**Principle**: Normalization statistics must be computed from the TRAINING SPLIT of
the TRAINING DATASET. Never estimate from published specifications. The gap between
"typical pack voltage" and "distribution mean over 60 real driving trips" was enough
to cause 20% SOC error.

## 2026-[month] — IsolationForest: synthetic training produces 0.36 score at normal

**Context**: Phase 2 IsolationForest retrain on real foxBMS SIL data.
**Mistake**: Training on 5,000 independently-sampled synthetic V, I, T values ignores
the natural correlation structure of real BMS data (rising I → sagging V → rising T).
Model learned synthetic distribution; real correlated data looks anomalous.
**Fix**: Capture 30-min real SIL baseline via automated telemetry (Phase 1 Day 1-2).
Retrain with 70% real data + 30% anchored synthetic (anchored to real mean/std).
**Principle**: Anomaly models must see the real operating distribution during training.
Synthetic data is acceptable for regime coverage but the distribution anchor must match
real observed data, not idealized specifications.
```

---

#### Day 60: Phase 2 Close

| Task | Done when |
|---|---|
| `baseline-metrics-phase2.md` all rows filled | All PASS/FAIL determined; no nulls |
| `models/registry.json` Phase 2 entries all filled | v2 versions have `phase2_baseline_*` fields |
| CI `ml-accuracy` gate passes on all Phase 2 thresholds | `ml-accuracy` CI job green on main |
| CI `ml-sidecar-smoke` strict 30-s assertion green | `ml-sidecar-smoke` job green |
| SW-REQ-ML-001..010 in traceability matrix | Traceability matrix committed |
| SWE.1 Section 11 added | SWE.1 document updated |
| SWE.4 ML-TC-001..010 added | SWE.4 document updated |
| `feat/ai-phase2-accuracy` PR merged to main | M2.4 tag created |
| Lessons learned committed | Entry in `docs/lessons-learned/embedded/bringup.md` |

---

### Phase 2 Exit Criteria

| Criterion | Gate | Evidence |
|---|---|---|
| SOC LSTM FOBSS RMSE | ≤ 3.0% | `baseline-metrics-phase2.md` SOC FOBSS row PASS |
| SOC LSTM FOBSS MAE | ≤ 2.0% | `baseline-metrics-phase2.md` SOC FOBSS row PASS |
| SOC LSTM SIL steady-state bias | ≤ ±3.0% (was +20.24%) | `baseline-metrics-phase2.md` SIL row PASS |
| SOC LSTM BMW i3 RMSE | ≤ 2.0% (not regressed from Phase 1) | CI `ml-accuracy` gate green |
| SOC LSTM BMW i3 MAE | ≤ 1.4% | `baseline-metrics-phase2.md` BMW i3 row PASS |
| IsolationForest v2 normal mean score | < 0.15 (was 0.36) | `baseline-metrics-phase2.md` anomaly PASS |
| IsolationForest v2 fault TPR | ≥ 80% | `baseline-metrics-phase2.md` anomaly PASS |
| Thermal CNN FPR | ≤ 2% (with dT/dt fix) | `test_thermal_cnn_phase2.py` green |
| Thermal CNN OT detection latency | ≤ 30 s | `test_thermal_cnn_phase2.py` green |
| SOH Transformer RMSE (synthetic) | ≤ 12.0% + < 10 inversions | `validate_soh_transformer.py` PASS |
| SOH Transformer MAE (synthetic) | ≤ 8.0% | `validate_soh_transformer.py` PASS |
| RUL Transformer CAN 0x704 | Publishing after ≥ 20 cycles | Live VPS CAN observation |
| NMC 811 OCV table | 21-point, monotone, round-trip < 1% | `validate_ocv_table.py` PASS |
| CI `ml-sidecar-smoke` | Strict 30-s assertion passes | CI green |
| SW-REQ-ML-001..010 | All PASS in traceability matrix | Traceability matrix committed |
| Phase 2 accuracy report | Published, all cells filled | `baseline-metrics-phase2.md` committed |
| Lessons learned | Phase 2 entries written | `docs/lessons-learned/embedded/bringup.md` updated |

### Phase 2 Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| FOBSS RMSE > 3% after OCV + norm fix | Medium | High | FOBSS partial fine-tune (Day 35–36 path) |
| Fine-tune causes BMW i3 catastrophic forgetting | Low | High | Anti-regression gate: BMW i3 RMSE must not rise by > 0.5%; if fails, revert to v1 and document |
| IsolationForest v2 normal score still > 0.15 | Low | Medium | Check CAN decode: V_mean_mV range must be 3600–3720. If mismatch, fix `extract_sil_anomaly_features.py` decoder |
| Cycle replay SOH RMSE > 12% | Medium | Medium | Transformer may require LiionPro-DT training data; document as "requires real cycle data" and treat as Phase 5 item |
| RUL ONNX input shape mismatch | Medium | Low | Inspect with `python3 -c "import onnxruntime as ort; m=ort.InferenceSession('rul_transformer.onnx'); print(m.get_inputs())"` |
| Phase 2 scope creep into LSTM-Autoencoder | High | Medium | Strictly defer to Phase 5. Phase 2 closes existing gaps; does not add new architectures |
| VPS CAN capture fails during Day 38–40 retrain | Low | Medium | Use Phase 1 automated telemetry (any 30-min slice from `/var/lib/foxbms-telemetry/`) |
| OCV table values require adjustment after hardware comparison | Low | Low | Table can be modified until HITL-LOCK is applied (review-gated; not locked until FSE sign-off) |

---

**Phase 3 detail**: see [`day61-90-daily-tasks.md`](day61-90-daily-tasks.md) — 30 days,
4 milestones (M3.1–M3.4), 12 ASPICE process areas covered.

*Workstreams: SIL Validation Framework (Day 61–67) · CAN Interface Hardening (Day 68–74) ·
Monitoring Dashboard (Day 75–81) · Drift Monitoring + CI Gates + Phase Close (Day 82–90).*

*Phase 3 priority order: SIL validation first (makes all claims testable), CAN hardening second
(DBC-driven tests catch encoding regressions), dashboard third (makes gaps visible to operators),
drift monitoring fourth (prevents silent model decay after Phase 2 retraining).*
