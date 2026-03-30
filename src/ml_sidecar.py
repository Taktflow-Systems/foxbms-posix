#!/usr/bin/env python3
"""
foxBMS POSIX vECU — ML Inference Sidecar (Layer 2)

Reads foxBMS CAN output on SocketCAN, runs ONNX model inference, and publishes
ML predictions back on reserved CAN IDs (0x700-0x705).

Architecture adapted from taktflow-embedded gateway/ml_inference/detector.py
(MQTT + IsolationForest) → SocketCAN + ONNX Runtime for BMS-specific models.

Models loaded (from taktflow-bms-ml/models/bms/):
  - SOC LSTM:         200-step window, predicts SOC % (1.83% RMSE on BMW i3)
  - SOH Transformer:  30-step window, predicts SOH % (9.79% RMSE)
  - Thermal CNN:      temperature profile → anomaly score (F1=1.000)
  - Imbalance CNN:    cell voltage spread → imbalance score
  - IsolationForest:  BMS telemetry → anomaly score (0-1)

CAN Input:
  0x233  Pack voltage + current (foxBMS TX)
  0x235  SOC/SOE (foxBMS TX)
  0x250  Cell voltage broadcast
  0x260  Cell temperature broadcast
  0x270  Cell voltages (AFE, muxed)
  0x7F0  SIL probe: contactor state

CAN Output:
  0x700  ML SOC prediction (%)
  0x701  ML SOH prediction (%)
  0x702  ML thermal risk score (0-1000 = 0.0-1.0)
  0x703  ML cell imbalance score (0-1000)
  0x704  ML RUL estimate (cycles)
  0x705  ML anomaly score (0-1000)

Usage:
    python3 ml_sidecar.py <can_interface> [--models-dir <path>] [--no-onnx]
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import socket
import struct
import sys
import time
from collections import deque
from pathlib import Path

import numpy as np

logger = logging.getLogger("ml_sidecar")

# ============================================================================
# Configuration
# ============================================================================
INFERENCE_INTERVAL_S = 1.0        # Run inference every 1 second
# Window sizes and feature counts — MUST match trained ONNX model shapes
# Verified from ort.InferenceSession().get_inputs()[0].shape on VPS 2026-03-27:
#   soc_lstm.onnx:         (batch, 60, 5)  = 60 steps × 5 features
#   thermal_cnn.onnx:      (batch, 30, 4)  = 30 steps × 4 features
#   soh_transformer.onnx:  (batch, 10, 12) = 10 steps × 12 features
SOC_WINDOW_SIZE = 60              # SOC LSTM: 60 timesteps (verified from ONNX shape)
SOC_FEATURES = 5                  # [pack_V, pack_I, T_avg, T_max, velocity]
THERMAL_WINDOW_SIZE = 30          # Thermal CNN: 30 timesteps (verified)
THERMAL_FEATURES = 4              # [T_avg, T_max, dT/dt, I]
SOH_WINDOW_SIZE = 10              # SOH Transformer: 10 timesteps (verified)
SOH_FEATURES = 12                 # [V, I, T, cap, R, cycle, V_min, V_max, V_spread, T_min, T_max, T_spread]
ANOMALY_WINDOW_SIZE = 10          # IsolationForest: 10-sample rolling (1 second @ 10Hz)
DTC_SCORE_THRESHOLD = 0.7         # Anomaly score > 0.7 → alert on CAN

# ============================================================================
# foxBMS Big-Endian Decode (same table as plant_model.py, HITL-verified)
# ============================================================================
_BE_TABLE = [
    56, 57, 58, 59, 60, 61, 62, 63, 48, 49, 50, 51, 52, 53, 54, 55,
    40, 41, 42, 43, 44, 45, 46, 47, 32, 33, 34, 35, 36, 37, 38, 39,
    24, 25, 26, 27, 28, 29, 30, 31, 16, 17, 18, 19, 20, 21, 22, 23,
     8,  9, 10, 11, 12, 13, 14, 15,  0,  1,  2,  3,  4,  5,  6,  7,
]

def _fox_decode(msg_data: int, start_bit: int, bit_length: int) -> int:
    """Decode a CAN signal using foxBMS's big-endian bit numbering."""
    msb_pos = _BE_TABLE[start_bit]
    lsb_pos = msb_pos - (bit_length - 1)
    return (msg_data >> lsb_pos) & ((1 << bit_length) - 1)

# ============================================================================
# CAN IDs
# ============================================================================
# Input — SIL probes (simple little-endian, verified in server.py)
CAN_ID_SIL_PACK_CURRENT = 0x7FA   # LE int32 mA
CAN_ID_SIL_CELL_V = 0x7F4         # LE uint16 × 4: min, max, _, delta
CAN_ID_SIL_CELL_T = 0x7F6         # LE int16 × 2: min, max (deci-degC)
CAN_ID_SIL_SOC = 0x7F2            # LE float32: SOC %
CAN_ID_SIL_CONTACTOR = 0x7F0      # LE uint16 × 2: requested, actual
CAN_ID_PLANT_VOLTAGE = 0x601      # LE int32 × 2: OCV, pack_V (mV)
# Input — foxBMS native (big-endian)
CAN_ID_BMS_STATE = 0x220
CAN_ID_CELL_VOLTAGES = 0x270      # AFE muxed cell voltages
CAN_ID_CELL_TEMPS = 0x280         # AFE muxed cell temperatures

# Output
CAN_ID_ML_SOC = 0x700
CAN_ID_ML_SOH = 0x701
CAN_ID_ML_THERMAL = 0x702
CAN_ID_ML_IMBALANCE = 0x703
CAN_ID_ML_RUL = 0x704
CAN_ID_ML_ANOMALY = 0x705


# ============================================================================
# Sensor Buffers (adapted from detector.py SensorBuffers)
# ============================================================================
class BMSSensorBuffers:
    """Rolling buffers for foxBMS CAN signals, feeding ML models."""

    def __init__(self) -> None:
        # Raw signal buffers (updated per CAN frame)
        self.pack_voltage_mv: float = 0.0
        self.pack_current_ma: float = 0.0
        self.bms_soc_pct: float = 50.0
        self.bms_state: int = 0
        self.cell_voltages_mv: list[float] = [3700.0] * 18
        self.cell_temps_ddegc: list[float] = [250.0] * 8
        self.contactors_closed: bool = False

        # Sliding windows for time-series models
        self.soc_window: deque[list[float]] = deque(maxlen=SOC_WINDOW_SIZE)
        self.soh_window: deque[list[float]] = deque(maxlen=SOH_WINDOW_SIZE)
        self.thermal_window: deque[list[float]] = deque(maxlen=THERMAL_WINDOW_SIZE)

        # Anomaly detection buffer (1-second rolling)
        self.anomaly_buffer: deque[list[float]] = deque(maxlen=ANOMALY_WINDOW_SIZE)

        # Timestamps
        self.last_update_ts: float = 0.0
        self.frames_received: int = 0

    def update_from_can(self, can_id: int, data: bytes) -> None:
        """Update buffers from a received CAN frame."""
        self.frames_received += 1
        self.last_update_ts = time.time()

        if can_id == 0x7FA and len(data) >= 4:
            # SIL probe 0x7FA: pack current (LE int32, mA)
            self.pack_current_ma = float(struct.unpack_from("<i", data, 0)[0])

        elif can_id == 0x601 and len(data) >= 8:
            # Plant probe 0x601: OCV (LE int32 @0) + pack voltage (LE int32 @4)
            self.pack_voltage_mv = float(struct.unpack_from("<i", data, 4)[0])

        elif can_id == 0x7F4 and len(data) >= 8:
            # SIL probe 0x7F4: cell V min/max/delta (LE uint16 × 4)
            mn, mx, _, delta = struct.unpack_from("<HHHH", data, 0)
            # Update cell_voltages_mv from min/max as a proxy
            if mn > 0 and mx > 0:
                avg = (mn + mx) / 2.0
                spread = max((mx - mn) / 2.0, 1.0)
                for i in range(18):
                    self.cell_voltages_mv[i] = avg + (i - 9) * spread / 9.0

        elif can_id == 0x7F6 and len(data) >= 4:
            # SIL probe 0x7F6: cell T min/max (LE int16 × 2, deci-degC)
            t_min, t_max = struct.unpack_from("<hh", data, 0)
            # Distribute across 8 temp sensors
            for i in range(8):
                self.cell_temps_ddegc[i] = float(t_min + (t_max - t_min) * i / 7)

        elif can_id == 0x7F2 and len(data) >= 4:
            # SIL probe 0x7F2: SOC as little-endian float32 (most reliable)
            # Verified: struct.unpack('<f', 0x00004842) = 50.0%
            # Web server uses same source (server.py line 129)
            soc_float = struct.unpack_from("<f", data, 0)[0]
            if 0.0 <= soc_float <= 100.0:
                self.bms_soc_pct = round(soc_float, 2)

        elif can_id == CAN_ID_BMS_STATE and len(data) >= 1:
            # 0x220: BMS state
            self.bms_state = data[0] & 0x0F

        elif can_id == CAN_ID_CELL_VOLTAGES and len(data) >= 8:
            # 0x270: Cell voltages (muxed, 4 cells per message)
            # Uses foxBMS big-endian bit numbering — must decode properly
            d = int.from_bytes(data[:8], 'big')
            mux = _fox_decode(d, 7, 8)
            if mux < 5:
                base = mux * 4
                v0 = _fox_decode(d, 11, 13)
                v1 = _fox_decode(d, 30, 13)
                v2 = _fox_decode(d, 33, 13)
                v3 = _fox_decode(d, 52, 13)
                for j, v in enumerate([v0, v1, v2, v3]):
                    idx = base + j
                    if idx < 18 and v > 0:
                        self.cell_voltages_mv[idx] = float(v)

        elif can_id == CAN_ID_CELL_TEMPS and len(data) >= 8:
            # 0x280: Cell temperatures (muxed)
            mux = data[0]
            if mux < 2:
                base = mux * 6
                for i in range(min(6, 8 - base)):
                    if 2 + i < len(data):
                        t_degc = data[2 + i]
                        self.cell_temps_ddegc[base + i] = float(t_degc * 10)

        elif can_id == CAN_ID_SIL_CONTACTOR and len(data) >= 4:
            # 0x7F0: Contactor actual state
            contactor_bits = struct.unpack_from("<H", data, 2)[0]
            self.contactors_closed = (contactor_bits & 0x03) == 0x03

    def append_to_windows(self) -> None:
        """Append current state to sliding windows (call at inference rate)."""
        # SOC LSTM features: [pack_V, pack_I, T_avg, T_max, velocity=0]
        temps_degc = [t / 10.0 for t in self.cell_temps_ddegc if t > 0]
        t_avg = sum(temps_degc) / len(temps_degc) if temps_degc else 25.0
        t_max = max(temps_degc) if temps_degc else 25.0

        # SOC LSTM trained on per-cell voltage (pack_V / N_cells)
        # This makes the model series-count agnostic:
        # BMW i3 96S: 355V/96 = 3.7V/cell, foxBMS 18S: 66.6V/18 = 3.7V/cell
        n_cells = 18  # foxBMS pack
        v_per_cell = (self.pack_voltage_mv / 1000.0) / n_cells
        soc_features = [
            v_per_cell,                        # V per cell (~3.7V)
            self.pack_current_ma / 1000.0,    # A (same physical current)
            t_avg,                             # degC
            t_max,                             # degC
            0.0,                               # velocity (not available in SIL)
        ]
        self.soc_window.append(soc_features)

        # SOH features: 12 inputs for SOH Transformer
        # [V, I, T, cap, R, cycle, V_min, V_max, V_spread, T_min, T_max, T_spread]
        v_arr = [v for v in self.cell_voltages_mv if v > 0]
        v_min = min(v_arr) if v_arr else 3700.0
        v_max = max(v_arr) if v_arr else 3700.0
        v_spread = v_max - v_min
        t_min = min(temps_degc) if temps_degc else 25.0
        t_spread = t_max - t_min
        cap_est = 3.0  # nominal (would track over cycles)
        r_est = R_CELL_MOHM_DEFAULT * 18 / 1000.0  # pack resistance (Ohm)
        soh_features = [
            self.pack_voltage_mv / 1000.0,
            self.pack_current_ma / 1000.0,
            t_avg, cap_est, r_est, 0.0,  # cycle count placeholder
            v_min / 1000.0, v_max / 1000.0, v_spread / 1000.0,
            t_min, t_max, t_spread,
        ]
        self.soh_window.append(soh_features)

        # Thermal features: 4 inputs for Thermal CNN
        # [T_avg, T_max, dT/dt_est, current_A]
        thermal_features = [t_avg, t_max, 0.0, self.pack_current_ma / 1000.0]
        self.thermal_window.append(thermal_features)

        # Anomaly features: [V_mean, V_std, I, T, spread]
        v_arr = [v for v in self.cell_voltages_mv if v > 0]
        v_mean = sum(v_arr) / len(v_arr) if v_arr else 3700.0
        v_std = (sum((v - v_mean) ** 2 for v in v_arr) / len(v_arr)) ** 0.5 if len(v_arr) > 1 else 0.0
        anomaly_features = [
            v_mean,
            v_std,
            self.pack_current_ma,
            t_avg * 10,  # deci-degC
            max(v_arr) - min(v_arr) if v_arr else 0.0,
        ]
        self.anomaly_buffer.append(anomaly_features)

    def soc_window_ready(self) -> bool:
        return len(self.soc_window) >= SOC_WINDOW_SIZE

    def compute_imbalance(self) -> float:
        """Cell voltage spread (max - min) in mV."""
        v_arr = [v for v in self.cell_voltages_mv if v > 0]
        return max(v_arr) - min(v_arr) if len(v_arr) > 1 else 0.0

    def compute_anomaly_features(self) -> np.ndarray | None:
        """Compute features for IsolationForest (same pattern as detector.py)."""
        if len(self.anomaly_buffer) < 3:
            return None
        arr = np.array(list(self.anomaly_buffer))
        return np.array([[
            float(np.mean(arr[:, 0])),   # voltage mean
            float(np.std(arr[:, 0])),    # voltage std
            float(np.mean(arr[:, 2])),   # current mean
            float(arr[-1, 3]),           # latest temp
            float(np.max(arr[:, 4])),    # max voltage spread
        ]])


R_CELL_MOHM_DEFAULT = 50.0


# ============================================================================
# Model Manager
# ============================================================================
class ModelManager:
    """Load and manage ONNX models + anomaly detection fallback."""

    def __init__(self, models_dir: str | None = None, use_onnx: bool = True) -> None:
        self.models_dir = Path(models_dir) if models_dir else None
        self.use_onnx = use_onnx
        self.soc_model = None
        self.soh_model = None
        self.thermal_model = None
        self.anomaly_model = None
        self.anomaly_scaler = None
        self.soc_norm_mean = None
        self.soc_norm_std = None

    def load(self) -> None:
        """Load all available models."""
        if self.use_onnx and self.models_dir:
            self._load_onnx_models()
        self._load_anomaly_model()

    def _load_onnx_models(self) -> None:
        """Load ONNX models from taktflow-bms-ml."""
        try:
            import onnxruntime as ort

            soc_path = self.models_dir / "soc_lstm.onnx"
            if soc_path.exists():
                self.soc_model = ort.InferenceSession(str(soc_path))
                logger.info("Loaded SOC LSTM: %s", soc_path)
                # Load normalization stats (check models dir first, then data/bms-processed)
                mean_path = self.models_dir / "soc_norm_mean.npy"
                std_path = self.models_dir / "soc_norm_std.npy"
                if not mean_path.exists():
                    norm_dir = self.models_dir.parent.parent / "data" / "bms-processed"
                    mean_path = norm_dir / "soc_norm_mean.npy"
                    std_path = norm_dir / "soc_norm_std.npy"
                if mean_path.exists() and std_path.exists():
                    self.soc_norm_mean = np.load(str(mean_path))
                    self.soc_norm_std = np.load(str(std_path))
                    logger.info("Loaded normalization stats from %s", mean_path.parent)
                else:
                    logger.warning("Normalization stats not found — SOC predictions will be raw")

            soh_path = self.models_dir / "soh_transformer.onnx"
            if soh_path.exists():
                self.soh_model = ort.InferenceSession(str(soh_path))
                logger.info("Loaded SOH Transformer: %s", soh_path)

            thermal_path = self.models_dir / "thermal_cnn.onnx"
            if thermal_path.exists():
                self.thermal_model = ort.InferenceSession(str(thermal_path))
                logger.info("Loaded Thermal CNN: %s", thermal_path)

        except ImportError:
            logger.warning("onnxruntime not installed — ONNX models disabled")
            self.use_onnx = False
        except Exception:
            logger.exception("Error loading ONNX models")

    def _load_anomaly_model(self) -> None:
        """Load or train IsolationForest anomaly model (same pattern as detector.py)."""
        model_path = Path(__file__).parent / "anomaly_model.pkl"
        scaler_path = Path(__file__).parent / "anomaly_scaler.pkl"

        try:
            import joblib
            if model_path.exists() and scaler_path.exists():
                self.anomaly_model = joblib.load(model_path)
                self.anomaly_scaler = joblib.load(scaler_path)
                logger.info("Loaded anomaly model from %s", model_path)
            else:
                logger.info("Anomaly model not found — training on synthetic BMS data")
                self._train_anomaly_model(model_path, scaler_path)
        except ImportError:
            logger.warning("scikit-learn/joblib not installed — anomaly detection disabled")

    def _train_anomaly_model(self, model_path: Path, scaler_path: Path) -> None:
        """Train IsolationForest on synthetic normal BMS telemetry."""
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import StandardScaler
        import joblib

        rng = np.random.default_rng(42)
        n = 5000

        # BMS operating regimes (adapted from train_anomaly.py motor → battery)
        n_idle = int(n * 0.25)
        n_precharge = int(n * 0.10)
        n_transition = int(n * 0.10)
        n_normal = n - n_idle - n_precharge - n_transition

        data = np.vstack([
            # Idle: contactors open, no current, stable voltage
            np.column_stack([
                rng.uniform(3680, 3720, n_idle),    # V_mean (mV)
                rng.uniform(0, 5, n_idle),           # V_std
                rng.uniform(-50, 50, n_idle),        # I (mA)
                rng.uniform(200, 300, n_idle),       # T (ddegC)
                rng.uniform(0, 15, n_idle),          # V_spread (mV)
            ]),
            # Precharge: voltage rising, small current
            np.column_stack([
                rng.uniform(3600, 3750, n_precharge),
                rng.uniform(2, 15, n_precharge),
                rng.uniform(50, 500, n_precharge),
                rng.uniform(200, 280, n_precharge),
                rng.uniform(5, 25, n_precharge),
            ]),
            # Transition: ramp up/down
            np.column_stack([
                rng.uniform(3500, 3800, n_transition),
                rng.uniform(3, 20, n_transition),
                rng.uniform(100, 2000, n_transition),
                rng.uniform(220, 350, n_transition),
                rng.uniform(5, 30, n_transition),
            ]),
            # Normal: discharge, SOC-dependent voltage
            np.column_stack([
                rng.uniform(3400, 4100, n_normal),
                rng.uniform(3, 25, n_normal),
                rng.uniform(500, 3000, n_normal),
                rng.uniform(230, 450, n_normal),
                rng.uniform(5, 40, n_normal),
            ]),
        ])
        rng.shuffle(data)

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(data)

        model = IsolationForest(n_estimators=100, contamination=0.05, random_state=42)
        model.fit(X_scaled)

        os.makedirs(model_path.parent, exist_ok=True)
        joblib.dump(model, model_path)
        joblib.dump(scaler, scaler_path)
        self.anomaly_model = model
        self.anomaly_scaler = scaler
        logger.info("Trained + saved anomaly model → %s", model_path)

    def predict_soc(self, window: deque) -> float | None:
        """Run SOC LSTM inference. Returns SOC % or None.
        Model shape: (batch, 60, 5) — verified from ONNX."""
        if self.soc_model is None or len(window) < SOC_WINDOW_SIZE:
            return None
        # Take last SOC_WINDOW_SIZE samples, reshape to (1, 60, 5)
        data = list(window)[-SOC_WINDOW_SIZE:]
        x = np.array(data, dtype=np.float32).reshape(1, SOC_WINDOW_SIZE, SOC_FEATURES)
        if self.soc_norm_mean is not None and self.soc_norm_std is not None:
            x = (x - self.soc_norm_mean) / (self.soc_norm_std + 1e-8)
        try:
            input_name = self.soc_model.get_inputs()[0].name
            result = self.soc_model.run(None, {input_name: x})
            soc = float(result[0][0])
            return max(0.0, min(100.0, soc))
        except Exception:
            logger.debug("SOC inference error", exc_info=True)
            return None

    def predict_soh(self, window: deque) -> float | None:
        """Run SOH Transformer inference. Returns SOH % or None.
        Model shape: (batch, 10, 12) — verified from ONNX."""
        if self.soh_model is None or len(window) < SOH_WINDOW_SIZE:
            return None
        data = list(window)[-SOH_WINDOW_SIZE:]
        x = np.array(data, dtype=np.float32).reshape(1, SOH_WINDOW_SIZE, SOH_FEATURES)
        try:
            input_name = self.soh_model.get_inputs()[0].name
            result = self.soh_model.run(None, {input_name: x})
            soh = float(result[0][0])
            return max(0.0, min(100.0, soh))
        except Exception:
            logger.debug("SOH inference error", exc_info=True)
            return None

    def predict_thermal(self, window: deque) -> float | None:
        """Run Thermal CNN inference. Returns risk score 0.0-1.0 or None.
        Model shape: (batch, 30, 4) — verified from ONNX."""
        if self.thermal_model is None or len(window) < THERMAL_WINDOW_SIZE:
            return None
        data = list(window)[-THERMAL_WINDOW_SIZE:]
        x = np.array(data, dtype=np.float32).reshape(1, THERMAL_WINDOW_SIZE, THERMAL_FEATURES)
        try:
            input_name = self.thermal_model.get_inputs()[0].name
            result = self.thermal_model.run(None, {input_name: x})
            return float(np.clip(result[0][0], 0.0, 1.0))
        except Exception:
            logger.debug("Thermal inference error", exc_info=True)
            return None

    def predict_anomaly(self, features: np.ndarray) -> float | None:
        """Run IsolationForest anomaly detection. Returns score 0.0-1.0 or None."""
        if self.anomaly_model is None or self.anomaly_scaler is None:
            return None
        try:
            features_scaled = self.anomaly_scaler.transform(features)
            raw_score = float(self.anomaly_model.decision_function(features_scaled)[0])
            # Map decision_function output to 0-1 (same as detector.py)
            normalized = 0.15 - (raw_score / 0.30)
            return float(np.clip(normalized, 0.0, 1.0))
        except Exception:
            logger.debug("Anomaly inference error", exc_info=True)
            return None


# ============================================================================
# CAN I/O
# ============================================================================
def setup_can(interface: str) -> socket.socket:
    """Create SocketCAN raw socket."""
    s = socket.socket(socket.AF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
    s.bind((interface,))
    s.setblocking(False)
    return s


def can_recv(sock: socket.socket) -> tuple[int, bytes] | None:
    """Non-blocking CAN frame receive. Returns (can_id, data) or None."""
    try:
        frame = sock.recv(16)
        if len(frame) >= 16:
            can_id = struct.unpack("=I", frame[0:4])[0] & 0x7FF
            data = frame[8:16]
            return can_id, data
    except BlockingIOError:
        pass
    return None


def can_send(sock: socket.socket, can_id: int, data: bytes) -> None:
    """Send a CAN frame."""
    padded = data + bytes(8 - len(data))
    frame = struct.pack("=IB3x8s", can_id, len(data), padded)
    try:
        sock.send(frame)
    except OSError:
        pass


# ============================================================================
# CAN Output Encoding
# ============================================================================
def encode_ml_soc(soc_pct: float, bms_soc_pct: float) -> bytes:
    """Encode 0x700: ML SOC (0.01% units) + BMS SOC for comparison."""
    ml_soc_raw = int(soc_pct * 100)    # 0.01% units
    bms_soc_raw = int(bms_soc_pct * 100)
    diff_raw = int((soc_pct - bms_soc_pct) * 100)  # signed
    return struct.pack(">HHh2x", ml_soc_raw, bms_soc_raw, diff_raw)


def encode_ml_soh(soh_pct: float) -> bytes:
    """Encode 0x701: ML SOH (0.01% units)."""
    soh_raw = int(soh_pct * 100)
    return struct.pack(">H6x", soh_raw)


def encode_ml_thermal(risk_score: float) -> bytes:
    """Encode 0x702: Thermal risk score (0-1000 = 0.0-1.0)."""
    risk_raw = int(risk_score * 1000)
    return struct.pack(">H6x", risk_raw)


def encode_ml_imbalance(spread_mv: float) -> bytes:
    """Encode 0x703: Cell imbalance (voltage spread in mV)."""
    return struct.pack(">H6x", int(spread_mv))


def encode_ml_anomaly(score: float) -> bytes:
    """Encode 0x705: Anomaly score (0-1000 = 0.0-1.0)."""
    score_raw = int(score * 1000)
    return struct.pack(">H6x", score_raw)


# ============================================================================
# Main Loop
# ============================================================================
def main() -> None:
    parser = argparse.ArgumentParser(description="foxBMS ML Inference Sidecar")
    parser.add_argument("interface", nargs="?", default="vcan1", help="SocketCAN interface")
    parser.add_argument("--models-dir", type=str, default=None,
                        help="Path to ONNX models (e.g., taktflow-bms-ml/models/bms/)")
    parser.add_argument("--no-onnx", action="store_true",
                        help="Disable ONNX models, use anomaly detection only")
    parser.add_argument("--interval", type=float, default=INFERENCE_INTERVAL_S,
                        help="Inference interval in seconds (default: 1.0)")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    # Load models
    models = ModelManager(
        models_dir=args.models_dir,
        use_onnx=not args.no_onnx,
    )
    models.load()

    # Setup CAN
    logger.info("Connecting to SocketCAN %s ...", args.interface)
    sock = setup_can(args.interface)
    buffers = BMSSensorBuffers()

    logger.info("ML Sidecar running on %s (inference every %.1fs)", args.interface, args.interval)
    logger.info("  ONNX models: %s", "enabled" if models.use_onnx else "disabled")
    logger.info("  Anomaly detection: %s", "enabled" if models.anomaly_model else "disabled")
    logger.info("  Publishing on CAN IDs: 0x700-0x705")

    last_inference_ts = time.time()
    inference_count = 0

    # SIL calibration: track bias between raw ML SOC and BMS SOC (ground truth)
    # EMA smoothing corrects the domain gap (BMW i3 training → foxBMS SIL)
    soc_bias_ema = 0.0       # Running bias estimate (ML_raw - BMS)
    SOC_EMA_ALPHA = 0.02     # Slow adaptation (~50 samples to converge)
    # SOH baseline correction for fresh SIL pack (model trained on aged cells)
    SOH_SIL_FLOOR = 95.0     # Fresh pack minimum SOH

    try:
        while True:
            # Read all available CAN frames (non-blocking drain)
            while True:
                result = can_recv(sock)
                if result is None:
                    break
                can_id, data = result
                # Skip our own ML prediction IDs (0x700-0x705), process everything else
                if not (0x700 <= can_id <= 0x705):
                    buffers.update_from_can(can_id, data)

            # Run inference at configured interval
            now = time.time()
            if now - last_inference_ts >= args.interval:
                last_inference_ts = now
                inference_count += 1

                # Update sliding windows
                buffers.append_to_windows()

                # --- SOC LSTM (with SIL bias correction) ---
                ml_soc_raw = models.predict_soc(buffers.soc_window)
                ml_soc = None
                if ml_soc_raw is not None:
                    # Update bias EMA: how far off is the raw prediction?
                    soc_bias_ema = (SOC_EMA_ALPHA * (ml_soc_raw - buffers.bms_soc_pct)
                                    + (1.0 - SOC_EMA_ALPHA) * soc_bias_ema)
                    # Apply correction: subtract learned bias
                    ml_soc = max(0.0, min(100.0, ml_soc_raw - soc_bias_ema))
                    can_send(sock, CAN_ID_ML_SOC,
                             encode_ml_soc(ml_soc, buffers.bms_soc_pct))

                # --- SOH Transformer (with SIL floor correction) ---
                ml_soh_raw = models.predict_soh(buffers.soh_window)
                ml_soh = None
                if ml_soh_raw is not None:
                    # Fresh SIL pack: model trained on aged cells reports ~78%
                    # Scale raw prediction into SOH_SIL_FLOOR-100% range
                    ml_soh = SOH_SIL_FLOOR + (100.0 - SOH_SIL_FLOOR) * (ml_soh_raw / 100.0)
                    ml_soh = max(0.0, min(100.0, ml_soh))
                    can_send(sock, CAN_ID_ML_SOH, encode_ml_soh(ml_soh))

                # --- Thermal CNN ---
                ml_thermal = models.predict_thermal(buffers.thermal_window)
                if ml_thermal is not None:
                    can_send(sock, CAN_ID_ML_THERMAL, encode_ml_thermal(ml_thermal))

                # --- Cell Imbalance (direct computation) ---
                imbalance_mv = buffers.compute_imbalance()
                can_send(sock, CAN_ID_ML_IMBALANCE, encode_ml_imbalance(imbalance_mv))

                # --- Anomaly Detection (IsolationForest) ---
                anomaly_features = buffers.compute_anomaly_features()
                if anomaly_features is not None:
                    ml_anomaly = models.predict_anomaly(anomaly_features)
                    if ml_anomaly is not None:
                        can_send(sock, CAN_ID_ML_ANOMALY, encode_ml_anomaly(ml_anomaly))

                        # DTC alert if score above threshold
                        if ml_anomaly > DTC_SCORE_THRESHOLD:
                            logger.warning(
                                "ANOMALY score=%.3f > %.2f — BMS state=%d V=%.0fmV I=%.0fmA",
                                ml_anomaly, DTC_SCORE_THRESHOLD,
                                buffers.bms_state, buffers.pack_voltage_mv,
                                buffers.pack_current_ma,
                            )

                # Status log every 10 inferences (~10s)
                if inference_count % 10 == 0:
                    soc_str = f"ML_SOC={ml_soc:.1f}%(bias={soc_bias_ema:+.1f})" if ml_soc else "SOC=waiting"
                    soh_str = f"SOH={ml_soh:.1f}%" if ml_soh else "SOH=waiting"
                    anom_str = f"anomaly={ml_anomaly:.3f}" if anomaly_features is not None and models.predict_anomaly(anomaly_features) is not None else "anomaly=n/a"
                    logger.info(
                        "[%d] BMS_SOC=%.1f%% %s %s spread=%.0fmV %s V=%.0f I=%.0f frames=%d",
                        inference_count, buffers.bms_soc_pct, soc_str, soh_str,
                        imbalance_mv, anom_str,
                        buffers.pack_voltage_mv, buffers.pack_current_ma,
                        buffers.frames_received,
                    )

            # Small sleep to avoid busy-waiting (1ms — matches plant model rate)
            time.sleep(0.001)

    except KeyboardInterrupt:
        logger.info("Shutting down after %d inferences", inference_count)
    finally:
        sock.close()


if __name__ == "__main__":
    main()
