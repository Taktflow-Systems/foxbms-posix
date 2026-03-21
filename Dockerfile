# foxBMS POSIX vECU — Multi-stage Docker build
# Usage:
#   docker build -t foxbms-vecu .
#   docker run --privileged --rm foxbms-vecu
#
# The --privileged flag is required for vcan interface setup inside the container.

# ============================================================
# Stage 1: Builder — compile the vECU binary
# ============================================================
FROM ubuntu:24.04 AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    make \
    python3 \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /foxbms-posix

# Copy repo (excluding items in .dockerignore)
COPY . .

# Initialize foxbms-2 submodule
RUN git init && \
    git submodule update --init --depth 1

# Apply all patches
RUN bash patches/apply_all.sh --force

# Build the vECU binary
RUN cd src && make clean && make -j$(nproc)

# ============================================================
# Stage 2: Runtime — slim image with binary + tests
# ============================================================
FROM ubuntu:24.04 AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    can-utils \
    iproute2 \
    procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /foxbms-posix

# Copy the built binary
COPY --from=builder /foxbms-posix/src/foxbms-vecu /foxbms-posix/src/foxbms-vecu

# Copy test scripts, plant model, and fault injection framework
COPY src/test_smoke.py src/test_fault_injection.py src/plant_model.py src/foxbms_signals.dbc /foxbms-posix/src/
COPY src/fi/ /foxbms-posix/src/fi/

# Copy test matrix CSV (needed by fault injection tests)
COPY docs/test/ /foxbms-posix/docs/test/

# Entrypoint: set up vcan1 and run smoke test
COPY <<'ENTRYPOINT_SCRIPT' /foxbms-posix/entrypoint.sh
#!/bin/bash
set -e

CAN_IF="${FOXBMS_CAN_IF:-vcan1}"

# Set up vcan (requires --privileged)
if ! ip link show "$CAN_IF" > /dev/null 2>&1; then
    ip link add "$CAN_IF" type vcan
    ip link set "$CAN_IF" up
    echo "[docker] $CAN_IF created and up"
else
    echo "[docker] $CAN_IF already exists"
fi

cd /foxbms-posix/src

# Default: run smoke test. Override with: docker run ... <command>
if [ $# -eq 0 ]; then
    echo "[docker] Running smoke test..."
    exec python3 test_smoke.py "$CAN_IF"
else
    exec "$@"
fi
ENTRYPOINT_SCRIPT

RUN chmod +x /foxbms-posix/entrypoint.sh

ENTRYPOINT ["/foxbms-posix/entrypoint.sh"]
