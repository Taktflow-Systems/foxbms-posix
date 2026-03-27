#!/bin/bash
# foxBMS POSIX vECU — Deploy ML Sidecar to Netcup VPS
#
# Deploys ml_sidecar.py + train_anomaly_bms.py + updated web server
# to the live SIL demo at sil.taktflow-systems.com/bms/
#
# Prerequisites:
#   - SSH access to root@152.53.245.209
#   - foxBMS SIL demo already running (vECU + plant_model.py + server.py)
#   - vcan1 interface up
#
# Usage:
#   bash scripts/deploy-ml-sidecar.sh
#   bash scripts/deploy-ml-sidecar.sh --dry-run

set -euo pipefail

VPS_HOST="152.53.245.209"
VPS_USER="root"
VPS_DIR="/opt/foxbms-sil"
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=true
    echo "[dry-run] Would deploy to $VPS_USER@$VPS_HOST:$VPS_DIR"
fi

echo "=== foxBMS ML Sidecar Deployment ==="
echo "Target: $VPS_USER@$VPS_HOST:$VPS_DIR"
echo ""

# Files to deploy
ML_FILES=(
    "src/ml_sidecar.py"
    "src/train_anomaly_bms.py"
    "src/requirements-ml.txt"
    "tools/foxbms_constants.py"
    "tools/soc-drift-calc.py"
    "tools/trend-analyze.py"
)

# Updated files (web dashboard + server with ML support)
UPDATED_FILES=(
    "web/server.py"
    "web/index.html"
)

echo "--- New ML files ---"
for f in "${ML_FILES[@]}"; do
    echo "  $f"
    if [[ ! -f "$SCRIPT_DIR/$f" ]]; then
        echo "  ERROR: $f not found!"
        exit 1
    fi
done

echo "--- Updated files ---"
for f in "${UPDATED_FILES[@]}"; do
    echo "  $f"
done
echo ""

if $DRY_RUN; then
    echo "[dry-run] Would copy ${#ML_FILES[@]} new + ${#UPDATED_FILES[@]} updated files"
    echo "[dry-run] Would install: numpy scikit-learn joblib"
    echo "[dry-run] Would train anomaly model"
    echo "[dry-run] Would start ml_sidecar.py on vcan1"
    echo "[dry-run] Would restart web server"
    exit 0
fi

echo "Step 1: Copy ML files to VPS..."
for f in "${ML_FILES[@]}"; do
    dir=$(dirname "$f")
    ssh "$VPS_USER@$VPS_HOST" "mkdir -p $VPS_DIR/$dir"
    scp "$SCRIPT_DIR/$f" "$VPS_USER@$VPS_HOST:$VPS_DIR/$f"
done

echo "Step 2: Copy updated web files..."
for f in "${UPDATED_FILES[@]}"; do
    scp "$SCRIPT_DIR/$f" "$VPS_USER@$VPS_HOST:$VPS_DIR/$f"
done

echo "Step 3: Install ML dependencies on VPS..."
ssh "$VPS_USER@$VPS_HOST" << 'INSTALL'
cd /foxbms-posix
pip install --quiet numpy scikit-learn joblib 2>/dev/null || \
pip3 install --quiet numpy scikit-learn joblib 2>/dev/null || \
apt-get install -y python3-numpy python3-sklearn 2>/dev/null || true
echo "Dependencies installed."
INSTALL

echo "Step 4: Train anomaly model..."
ssh "$VPS_USER@$VPS_HOST" << 'TRAIN'
cd /foxbms-posix/src
python3 train_anomaly_bms.py --output-dir . 2>&1 | tail -5
if [ -f anomaly_model.pkl ]; then
    echo "Anomaly model trained: $(ls -la anomaly_model.pkl)"
else
    echo "WARNING: anomaly_model.pkl not created"
fi
TRAIN

echo "Step 5: Stop existing ML sidecar (if running)..."
ssh "$VPS_USER@$VPS_HOST" "pkill -f ml_sidecar.py 2>/dev/null || true"

echo "Step 6: Start ML sidecar..."
ssh "$VPS_USER@$VPS_HOST" << 'START_ML'
cd /foxbms-posix/src
# Verify vcan1 is up
if ip link show vcan1 >/dev/null 2>&1; then
    nohup python3 ml_sidecar.py vcan1 --no-onnx --interval 1.0 \
        >> /var/log/foxbms-ml-sidecar.log 2>&1 &
    echo "ML sidecar started (PID: $!)"
    sleep 2
    # Verify it's running
    if pgrep -f ml_sidecar.py >/dev/null; then
        echo "ML sidecar running OK"
    else
        echo "WARNING: ML sidecar may have crashed. Check /var/log/foxbms-ml-sidecar.log"
    fi
else
    echo "ERROR: vcan1 not found. Is the SIL demo running?"
    exit 1
fi
START_ML

echo "Step 7: Restart web server (to pick up ML CAN parsers)..."
ssh "$VPS_USER@$VPS_HOST" << 'RESTART_WEB'
pkill -f "python3.*server.py" 2>/dev/null || true
sleep 1
cd /foxbms-posix/web
nohup python3 server.py --can vcan1 --port 8080 \
    >> /var/log/foxbms-web.log 2>&1 &
echo "Web server restarted (PID: $!)"
sleep 2
if pgrep -f server.py >/dev/null; then
    echo "Web server running OK"
else
    echo "WARNING: Web server may have crashed. Check /var/log/foxbms-web.log"
fi
RESTART_WEB

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Verify at: https://sil.taktflow-systems.com/bms/"
echo "  - ML Intelligence panel should show 'Active' status"
echo "  - Anomaly score should show 0.0xx (normal)"
echo "  - CAN monitor should show 0x705 frames (amber)"
echo ""
echo "Logs:"
echo "  ssh $VPS_USER@$VPS_HOST tail -f /var/log/foxbms-ml-sidecar.log"
echo "  ssh $VPS_USER@$VPS_HOST tail -f /var/log/foxbms-web.log"
