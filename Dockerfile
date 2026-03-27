# foxBMS POSIX vECU — Multi-stage Docker build
#
# Prerequisites:
#   git submodule update --init   (foxbms-2 source must be present)
#
# Usage:
#   docker build -t foxbms-vecu .
#   docker run --privileged --rm foxbms-vecu
#
# The --privileged flag is required for vcan interface setup inside the container.
# Alternatively, create vcan on the host and pass --network=host.

# ============================================================
# Stage 1: Builder — compile the vECU binary
# ============================================================
FROM ubuntu:24.04 AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    make \
    python3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /foxbms-posix

# Copy repo (excluding items in .dockerignore)
# NOTE: foxbms-2 submodule must be initialized before docker build.
#       .dockerignore strips .git/ dirs but keeps source files.
COPY . .

# Apply all patches
RUN bash patches/apply_all.sh --force

# Build the vECU binary
RUN cd src && make clean && make -j$(nproc)

# ============================================================
# Stage 2: Runtime — slim image with binary + tests
# ============================================================
FROM ubuntu:24.04 AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip \
    can-utils \
    iproute2 \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install ML dependencies (optional — sidecar works without ONNX too)
COPY src/requirements-ml.txt /tmp/requirements-ml.txt
RUN pip install --no-cache-dir --break-system-packages -r /tmp/requirements-ml.txt 2>/dev/null || true

WORKDIR /foxbms-posix

# Copy the built binary
COPY --from=builder /foxbms-posix/src/foxbms-vecu /foxbms-posix/src/foxbms-vecu

# Copy test scripts, plant model, ML sidecar, and fault injection framework
COPY src/test_smoke.py src/test_fault_injection.py src/plant_model.py src/foxbms_signals.dbc /foxbms-posix/src/
COPY src/ml_sidecar.py src/train_anomaly_bms.py /foxbms-posix/src/
COPY src/fi/ /foxbms-posix/src/fi/
COPY tools/ /foxbms-posix/tools/

# Copy test matrix CSV (needed by fault injection tests)
COPY docs/test/ /foxbms-posix/docs/test/

# Copy entrypoint
COPY entrypoint.sh /foxbms-posix/entrypoint.sh
RUN chmod +x /foxbms-posix/entrypoint.sh

ENTRYPOINT ["/foxbms-posix/entrypoint.sh"]
