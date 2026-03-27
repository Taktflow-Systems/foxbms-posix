#!/usr/bin/env python3
"""
foxBMS POSIX vECU — BMS Anomaly Detection Model Training

Trains an IsolationForest on synthetic normal BMS telemetry data.
Adapted from taktflow-embedded gateway/ml_inference/train_anomaly.py
(motor telemetry → BMS battery telemetry).

Features (5):
  - cell_voltage_mean     (3400-4200 mV, depends on SOC)
  - cell_voltage_std      (0-25 mV, manufacturing spread)
  - pack_current_ma       (0-3000 mA, normal operation)
  - temperature_ddegc     (200-450 ddegC, 20-45 degC)
  - cell_voltage_spread   (5-40 mV, max-min across 18 cells)

Operating regimes:
  - Idle (~25%):        contactors open, no current, stable voltage
  - Precharge (~10%):   voltage ramping, small current
  - Transition (~10%):  ramp up/down between idle and normal
  - Normal (~55%):      discharge/charge, SOC-dependent voltage

Outputs:
  anomaly_model.pkl  — fitted IsolationForest
  anomaly_scaler.pkl — fitted StandardScaler

Usage:
    python3 train_anomaly_bms.py [--output-dir <path>] [--samples 5000]
"""
from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

import numpy as np
import joblib
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

# ============================================================================
# Constants
# ============================================================================
FEATURE_NAMES = [
    "cell_voltage_mean",
    "cell_voltage_std",
    "pack_current_ma",
    "temperature_ddegc",
    "cell_voltage_spread",
]

N_SAMPLES = 5000
RANDOM_SEED = 42

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent


# ============================================================================
# Synthetic Data Generation
# ============================================================================
def generate_normal_bms_data(n_samples: int = N_SAMPLES, seed: int = RANDOM_SEED) -> np.ndarray:
    """Generate synthetic *normal* BMS telemetry features.

    Four operating regimes matching foxBMS state machine:
      - Idle (~25%):       IDLE/STANDBY — contactors open, no current
      - Precharge (~10%):  PRECHARGE — voltage ramping
      - Transition (~10%): State transitions — ramp up/down
      - Normal (~55%):     NORMAL — active discharge/charge
    """
    rng = np.random.default_rng(seed)

    n_idle = int(n_samples * 0.25)
    n_precharge = int(n_samples * 0.10)
    n_transition = int(n_samples * 0.10)
    n_normal = n_samples - n_idle - n_precharge - n_transition

    # --- Idle: contactors open, no current, voltage at OCV ---
    idle = np.column_stack([
        rng.uniform(3680, 3720, n_idle),       # V_mean (mid-SOC OCV)
        rng.uniform(0, 5, n_idle),              # V_std (very stable)
        rng.uniform(-50, 50, n_idle),           # I (leakage only)
        rng.uniform(200, 300, n_idle),          # T (ambient, 20-30 degC)
        rng.uniform(0, 15, n_idle),             # V_spread (tight)
    ])

    # --- Precharge: small current, voltage rising toward pack voltage ---
    precharge = np.column_stack([
        rng.uniform(3600, 3750, n_precharge),
        rng.uniform(2, 15, n_precharge),
        rng.uniform(50, 500, n_precharge),
        rng.uniform(200, 280, n_precharge),
        rng.uniform(5, 25, n_precharge),
    ])

    # --- Transition: ramp up/down current ---
    transition = np.column_stack([
        rng.uniform(3500, 3800, n_transition),
        rng.uniform(3, 20, n_transition),
        rng.uniform(100, 2000, n_transition),
        rng.uniform(220, 350, n_transition),
        rng.uniform(5, 30, n_transition),
    ])

    # --- Normal: active discharge, voltage tracks SOC ---
    normal = np.column_stack([
        rng.uniform(3400, 4100, n_normal),      # V spans full SOC range
        rng.uniform(3, 25, n_normal),            # V_std (normal spread)
        rng.uniform(500, 3000, n_normal),        # I (discharge, 0.17-1C)
        rng.uniform(230, 450, n_normal),         # T (23-45 degC under load)
        rng.uniform(5, 40, n_normal),            # V_spread (wider under load)
    ])

    data = np.vstack([idle, precharge, transition, normal])
    rng.shuffle(data)
    return data


# ============================================================================
# Training
# ============================================================================
def train_model(
    n_samples: int = N_SAMPLES,
    contamination: float = 0.05,
    n_estimators: int = 100,
    random_state: int = RANDOM_SEED,
) -> tuple[IsolationForest, StandardScaler]:
    """Train IsolationForest on synthetic normal BMS data."""
    logger.info("Generating %d synthetic normal BMS samples ...", n_samples)
    X = generate_normal_bms_data(n_samples=n_samples, seed=random_state)

    logger.info("Fitting StandardScaler ...")
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    logger.info("Training IsolationForest (n_estimators=%d, contamination=%.2f) ...",
                n_estimators, contamination)
    model = IsolationForest(
        n_estimators=n_estimators,
        contamination=contamination,
        random_state=random_state,
    )
    model.fit(X_scaled)

    return model, scaler


def save_model(
    model: IsolationForest,
    scaler: StandardScaler,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> None:
    """Persist model and scaler to disk."""
    os.makedirs(output_dir, exist_ok=True)
    model_path = output_dir / "anomaly_model.pkl"
    scaler_path = output_dir / "anomaly_scaler.pkl"
    joblib.dump(model, model_path)
    joblib.dump(scaler, scaler_path)
    logger.info("Saved model  -> %s", model_path)
    logger.info("Saved scaler -> %s", scaler_path)


# ============================================================================
# CLI
# ============================================================================
def main():
    parser = argparse.ArgumentParser(description="Train BMS anomaly detection model")
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT_DIR),
                        help="Output directory for model files")
    parser.add_argument("--samples", type=int, default=N_SAMPLES,
                        help="Number of training samples")
    parser.add_argument("--contamination", type=float, default=0.05,
                        help="Expected fraction of anomalies (0-0.5)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    model, scaler = train_model(n_samples=args.samples, contamination=args.contamination)
    save_model(model, scaler, output_dir=Path(args.output_dir))

    # Quick validation
    logger.info("Validating model ...")
    X_normal = generate_normal_bms_data(n_samples=100)
    X_scaled = scaler.transform(X_normal)
    scores = model.decision_function(X_scaled)
    preds = model.predict(X_scaled)
    n_anomalies = (preds == -1).sum()
    logger.info("  Normal data: %d/%d flagged as anomaly (expect ~5%%)", n_anomalies, len(preds))
    logger.info("  Score range: [%.4f, %.4f]", scores.min(), scores.max())

    # Inject synthetic anomalies
    rng = np.random.default_rng(99)
    X_anomaly = np.array([
        [4500, 100, 5000, 700, 200],   # OV + overcurrent + overtemp
        [2800, 150, 0, 100, 300],       # UV + no current + cold
        [3700, 500, 1000, 250, 500],    # huge V_std + spread
        [3700, 5, 50000, 250, 10],      # extreme current
        [3700, 5, 1000, 800, 10],       # extreme temperature
    ], dtype=np.float64)
    X_anom_scaled = scaler.transform(X_anomaly)
    anom_scores = model.decision_function(X_anom_scaled)
    anom_preds = model.predict(X_anom_scaled)
    n_detected = (anom_preds == -1).sum()
    logger.info("  Anomaly data: %d/%d correctly flagged", n_detected, len(anom_preds))
    logger.info("  Anomaly scores: %s", [f"{s:.4f}" for s in anom_scores])

    logger.info("Training complete.")


if __name__ == "__main__":
    main()
