#!/bin/bash
# foxBMS BMS Web — Docker entrypoint
# Starts vECU + plant model + ML sidecar + web dashboard server
set -e

CAN_IF="${FOXBMS_CAN_IF:-vcan1}"
WEB_PORT="${BMS_WEB_PORT:-8092}"

# Set up vcan (requires --privileged or host vcan module)
if ! ip link show "$CAN_IF" > /dev/null 2>&1; then
    modprobe vcan 2>/dev/null || true
    ip link add "$CAN_IF" type vcan 2>/dev/null || true
    ip link set "$CAN_IF" up
    echo "[bms-web] $CAN_IF created and up"
else
    ip link set "$CAN_IF" up 2>/dev/null || true
    echo "[bms-web] $CAN_IF already exists"
fi

cd /foxbms-posix

# Start plant model in background
echo "[bms-web] Starting plant model on $CAN_IF..."
python3 src/plant_model.py "$CAN_IF" &
PLANT_PID=$!
sleep 0.5

# Start vECU in background
echo "[bms-web] Starting foxBMS vECU on $CAN_IF..."
FOXBMS_CAN_IF="$CAN_IF" src/foxbms-vecu &
VECU_PID=$!
sleep 1

# Start ML sidecar in background (non-critical — continue if it fails)
echo "[bms-web] Starting ML sidecar on $CAN_IF..."
python3 src/ml_sidecar.py "$CAN_IF" --no-onnx &
ML_PID=$!

# Start web server (foreground — Docker tracks this process)
echo "[bms-web] Starting web dashboard on port $WEB_PORT..."
exec python3 web/server.py --can "$CAN_IF" --port "$WEB_PORT" --host 0.0.0.0
