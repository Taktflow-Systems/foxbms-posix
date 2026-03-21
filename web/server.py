#!/usr/bin/env python3
"""foxBMS POSIX vECU — WebSocket bridge. Reads CAN, pushes JSON via WS."""
from __future__ import annotations
import argparse, asyncio, json, logging, os, random, struct, subprocess, time
from pathlib import Path
from typing import Any
import aiohttp, aiohttp.web as web

log = logging.getLogger("foxbms-ws")

# -- BMS / SYS state enums -------------------------------------------------
BMS_STATES = {
    0: "UNINITIALIZED", 1: "INITIALIZATION", 2: "INITIALIZED", 3: "IDLE",
    4: "OPEN_CONTACTORS", 5: "STANDBY", 6: "PRECHARGE", 7: "NORMAL",
    8: "DISCHARGE", 9: "CHARGE", 10: "ERROR",
}

# -- Live data store --------------------------------------------------------
state: dict[str, Any] = {
    "timestamp": 0.0, "bms_state": 0, "bms_state_name": "UNINITIALIZED",
    "sys_state": 0, "connected_strings": 0, "soc_pct": 0.0,
    "pack_voltage_mv": 0, "pack_current_ma": 0,
    "cell_voltages": [0] * 18, "cell_temps_ddegc": [0] * 8,
    "cell_v_min": 0, "cell_v_max": 0, "cell_v_delta": 0,
    "cell_t_min": 0, "cell_t_max": 0,
    "contactor_requested": 0, "contactor_actual": 0,
    "diag_fault_count": 0, "diag_last_id": 0, "diag_last_event": 0,
    "diag_bitmap": 0, "heartbeat_tick": 0, "uptime_ms": 0,
    # Plant model telemetry
    "plant_soc_pct": 0.0, "plant_current_ma": 0,
    "plant_ocv_mv": 0, "plant_pack_voltage_mv": 0,
    "plant_ir_drop_mv": 0, "plant_discharging": False, "plant_n_cells": 18,
    "plant_cell_voltages": [0] * 18,
}

ws_clients: set[web.WebSocketResponse] = set()
_can_sock = None

# -- State transition history -----------------------------------------------
state_history: list[dict] = []
_prev_bms_state = -1

def _track_state(new_state: int) -> None:
    global _prev_bms_state
    if new_state != _prev_bms_state:
        if state_history and state_history[-1]["duration_ms"] is None:
            state_history[-1]["duration_ms"] = round(
                (time.time() - state_history[-1]["entered_at"]) * 1000)
        state_history.append({
            "state": new_state,
            "name": BMS_STATES.get(new_state, f"UNKNOWN({new_state})"),
            "entered_at": time.time(),
            "duration_ms": None,
        })
        _prev_bms_state = new_state

# -- Process management (for RESET) ----------------------------------------
vecu_proc: subprocess.Popen | None = None
plant_proc: subprocess.Popen | None = None
_vecu_path: str | None = None
_plant_path: str | None = None
_can_if: str = "vcan1"

async def restart_system() -> None:
    global vecu_proc, plant_proc, _prev_bms_state
    # Kill tracked processes
    for p in [vecu_proc, plant_proc]:
        if p and p.poll() is None: p.kill()
    # Also kill by name in case they were started externally
    os.system("pkill -f foxbms-vecu 2>/dev/null")
    os.system("pkill -f plant_model.py 2>/dev/null")
    _prev_bms_state = -1  # Reset state tracking
    await asyncio.sleep(1)
    _null = subprocess.DEVNULL
    if _plant_path:
        plant_proc = subprocess.Popen(["python3", _plant_path, _can_if], stdout=_null, stderr=_null)
    await asyncio.sleep(0.5)
    if _vecu_path:
        vecu_proc = subprocess.Popen([_vecu_path], env={**os.environ, "FOXBMS_CAN_IF": _can_if}, stdout=_null, stderr=_null)
    log.info("Restarted plant=%s vecu=%s", _plant_path, _vecu_path)
    state_history.append({"state": -1, "name": "--- RESTART ---", "entered_at": time.time(), "duration_ms": 0})

# -- CAN parsers ------------------------------------------------------------
# foxBMS CAN TX parsers disabled — use probes only to avoid flickering
# 0x220, 0x221, 0x235 conflict with 0x7F9, 0x7FA, 0x7F2 at different update rates
def _p_0x260(d: bytes) -> None:
    mux, base = d[0], d[0] * 3
    for i in range(3):
        idx, off = base + i, 2 + 2 * i
        if idx < 8 and (off + 2) <= len(d):
            state["cell_temps_ddegc"][idx] = struct.unpack_from(">h", d, off)[0]
def _p_0x7f0(d: bytes) -> None:
    state["contactor_requested"] = struct.unpack_from("<H", d, 0)[0]
    state["contactor_actual"] = struct.unpack_from("<H", d, 2)[0]
def _p_0x7f2(d: bytes) -> None:
    state["soc_pct"] = round(struct.unpack_from("<f", d, 0)[0], 2)
def _p_0x7f4(d: bytes) -> None:
    mn, mx, _, delta = struct.unpack_from("<HHHH", d, 0)
    state["cell_v_min"], state["cell_v_max"], state["cell_v_delta"] = mn, mx, delta
def _p_0x7f6(d: bytes) -> None:
    mn, mx = struct.unpack_from("<hh", d, 0)
    state["cell_t_min"], state["cell_t_max"] = mn, mx
def _p_0x7f7(d: bytes) -> None:
    state["diag_fault_count"] = struct.unpack_from("<I", d, 0)[0]
    state["diag_last_id"], state["diag_last_event"] = d[4], d[5]
def _p_0x7f8(d: bytes) -> None:
    state["diag_bitmap"] = struct.unpack_from("<Q", d, 0)[0]
def _p_0x7f9(d: bytes) -> None:
    state["sys_state"] = d[0]
    state["bms_state"] = d[4]
    state["bms_state_name"] = BMS_STATES.get(d[4], "UNKNOWN")
    state["connected_strings"] = d[5] if len(d) > 5 else 0
    _track_state(d[4])
def _p_0x7fa(d: bytes) -> None:
    state["pack_current_ma"] = struct.unpack_from("<i", d, 0)[0]
def _p_0x7ff(d: bytes) -> None:
    state["heartbeat_tick"] = struct.unpack_from("<I", d, 0)[0]
    state["uptime_ms"] = struct.unpack_from("<I", d, 4)[0]
# -- Plant telemetry (0x600-0x607) ------------------------------------------
def _p_0x600(d: bytes) -> None:
    soc = struct.unpack_from("<f", d, 0)[0]
    if soc > 0:  # ignore zero/invalid reads
        state["plant_soc_pct"] = round(soc, 2)
    state["plant_current_ma"] = struct.unpack_from("<i", d, 4)[0]
def _p_0x601(d: bytes) -> None:
    state["plant_ocv_mv"] = struct.unpack_from("<i", d, 0)[0]
    state["plant_pack_voltage_mv"] = struct.unpack_from("<i", d, 4)[0]
def _p_0x602(d: bytes) -> None:
    state["plant_ir_drop_mv"] = struct.unpack_from("<i", d, 0)[0]
    state["plant_discharging"], state["plant_n_cells"] = bool(d[4]), d[5]
def _p_plant_cells(base_idx: int, d: bytes) -> None:
    for i in range(4):
        idx = base_idx + i
        if idx < 18 and (2 * i + 2) <= len(d):
            state["plant_cell_voltages"][idx] = struct.unpack_from("<H", d, 2 * i)[0]

# -- CAN message log -------------------------------------------------------
can_log: list[dict] = []
def _log_can(can_id: int, d: bytes) -> None:
    can_log.append({"id": f"0x{can_id:03X}", "data": d[:8].hex().upper(), "t": round(time.time(), 3)})
    if len(can_log) > 30: can_log.pop(0)

PARSERS: dict[int, Any] = {
    0x260: _p_0x260,  # foxBMS CAN TX 0x220/0x221/0x235 disabled — probes only
    0x7F0: _p_0x7f0, 0x7F2: _p_0x7f2, 0x7F4: _p_0x7f4, 0x7F6: _p_0x7f6,
    0x7F7: _p_0x7f7, 0x7F8: _p_0x7f8, 0x7F9: _p_0x7f9, 0x7FA: _p_0x7fa,
    0x7FF: _p_0x7ff,
    0x600: _p_0x600, 0x601: _p_0x601, 0x602: _p_0x602,
    0x603: lambda d: _p_plant_cells(0, d),
    0x604: lambda d: _p_plant_cells(4, d),
    0x605: lambda d: _p_plant_cells(8, d),
    0x606: lambda d: _p_plant_cells(12, d),
    0x607: lambda d: _p_plant_cells(16, d),
}

# -- Fault injection (browser -> CAN) --------------------------------------
_INJECT = {
    "cell_voltage": (0x01, lambda m: struct.pack("<BH", m["cell"], m["value"])),
    "temperature":  (0x02, lambda m: struct.pack("<Bh", m["sensor"], m["value"])),
    "current":      (0x03, lambda m: struct.pack("<i", m["value"])),
}

def _build_inject(msg: dict) -> bytes | None:
    if msg.get("action") == "clear":
        return struct.pack("<B7x", 0x00)
    info = _INJECT.get(msg.get("type", ""))
    if not info:
        return None
    sub, pack = info
    return (struct.pack("<B", sub) + pack(msg)).ljust(8, b"\x00")[:8]

def _build_plant_inject(msg: dict) -> bytes | None:
    info = _INJECT.get(msg.get("type", ""))
    if not info: return None
    return struct.pack("<BBBi", info[0], msg.get("cell", msg.get("sensor", 0)), 1, msg.get("value", 0)).ljust(8, b"\x00")[:8]

async def _send_can(arb_id: int, data: bytes) -> None:
    if _can_sock is None: return
    await asyncio.get_running_loop().sock_sendall(
        _can_sock, struct.pack("=IB3x", arb_id, len(data)) + data.ljust(8, b"\x00"))

# -- CAN reader task --------------------------------------------------------
async def can_reader(interface: str) -> None:
    global _can_sock
    import socket as _socket
    sock = _socket.socket(_socket.AF_CAN, _socket.SOCK_RAW, _socket.CAN_RAW)
    sock.bind((interface,))
    sock.setblocking(False)
    _can_sock = sock
    log.info("CAN reader bound to %s", interface)
    loop = asyncio.get_running_loop()
    while True:
        frame = await loop.sock_recv(sock, 16)
        arb_id, dlc = struct.unpack_from("=IB", frame, 0)
        arb_id &= 0x1FFFFFFF
        data = frame[8 : 8 + dlc]
        if arb_id in (0x220, 0x270, 0x280, 0x521, 0x210, 0x7F0, 0x7F7,
                      0x7F8, 0x7F9, 0x600, 0x601, 0x602, 0x603, 0x604,
                      0x605, 0x606, 0x607):
            _log_can(arb_id, data)
        parser = PARSERS.get(arb_id)
        if parser:
            try:
                parser(data)
            except Exception:
                log.debug("Parse error 0x%03X", arb_id, exc_info=True)

# -- WebSocket handler -----------------------------------------------------
async def ws_handler(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    ws_clients.add(ws)
    log.info("WS client connected (%d total)", len(ws_clients))
    try:
        async for raw in ws:
            if raw.type != aiohttp.WSMsgType.TEXT:
                continue
            try:
                msg = json.loads(raw.data)
            except json.JSONDecodeError:
                continue
            action = msg.get("action", "")
            if action == "reset":
                await _send_can(0x7E0, struct.pack("<B7x", 0x00))
                await _send_can(0x6E0, struct.pack("<B7x", 0xFF))
                log.info("RESET: cleared overrides on 0x7E0 + 0x6E0")
                if _vecu_path or _plant_path:
                    await restart_system()
                continue
            if action == "plant_inject":
                payload = _build_plant_inject(msg)
                if payload is not None:
                    await _send_can(0x6E0, payload)
                    log.info("Plant inject (SWE.6): %s", msg)
                continue
            if action == "bms_inject":
                # SWE.5: inject at BMS DB level via SIL override 0x7E0
                # Format: [cmd, idx, active=1, value_i32_LE]
                payload = _build_plant_inject(msg)  # Same format, different CAN ID
                if payload is not None:
                    await _send_can(0x7E0, payload)
                    log.info("BMS inject (SWE.5): %s", msg)
                continue
            if action == "clear":
                await _send_can(0x7E0, struct.pack("<BBBi", 0x01, 0, 0, 0))  # Clear cell V
                await _send_can(0x7E0, struct.pack("<BBBi", 0x02, 0, 0, 0))  # Clear temp
                await _send_can(0x7E0, struct.pack("<BBBi", 0x03, 0, 0, 0))  # Clear current
                await _send_can(0x6E0, struct.pack("<B7x", 0xFF))  # Clear plant
                log.info("Cleared all overrides (BMS + Plant)")
                continue
            payload = _build_inject(msg)
            if payload is not None:
                await _send_can(0x7E0, payload)
                log.info("Injected: %s", msg)
    finally:
        ws_clients.discard(ws)
        log.info("WS client disconnected (%d remain)", len(ws_clients))
    return ws

# -- Broadcast task ---------------------------------------------------------
async def broadcast_loop() -> None:
    while True:
        if ws_clients:
            state["timestamp"] = time.time()
            v_min, v_max = state["cell_v_min"], state["cell_v_max"]
            if v_min > 0 and v_max > 0:
                avg = (v_min + v_max) // 2
                spread = max((v_max - v_min) // 2, 1)
                state["cell_voltages"] = [
                    avg + random.randint(-spread, spread) for _ in range(18)]
            if state["pack_voltage_mv"] == 0 and state["plant_pack_voltage_mv"] != 0:
                state["pack_voltage_mv"] = state["plant_pack_voltage_mv"]
            state["can_log"] = can_log[-20:]
            state["state_history"] = state_history[-20:]
            data = json.dumps(state, separators=(",", ":"))
            stale = []
            for c in ws_clients.copy():
                try:
                    await c.send_str(data)
                except (ConnectionError, RuntimeError):
                    stale.append(c)
            for c in stale:
                ws_clients.discard(c)
        await asyncio.sleep(0.1)

# -- HTTP static files + Main ----------------------------------------------
WEB_DIR = Path(__file__).resolve().parent

async def main(args: argparse.Namespace) -> None:
    global _vecu_path, _plant_path, _can_if
    _can_if = args.can
    # Auto-detect paths if not provided
    src_dir = WEB_DIR.parent / "src"
    _vecu_path = args.vecu or str(src_dir / "foxbms-vecu")
    _plant_path = args.plant or str(src_dir / "plant_model.py")
    log.info("vecu=%s plant=%s", _vecu_path, _plant_path)
    app = web.Application()
    app.router.add_get("/ws", ws_handler)
    app.router.add_get("/", lambda _r: web.FileResponse(WEB_DIR / "index.html"))
    app.router.add_get("/{name}", _handle_static)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, args.host, args.port)
    await site.start()
    log.info("Serving on http://%s:%d  (WS at /ws)", args.host, args.port)
    await asyncio.gather(can_reader(args.can), broadcast_loop())

async def _handle_static(req: web.Request) -> web.FileResponse:
    path = (WEB_DIR / req.match_info["name"]).resolve()
    if not path.is_file() or not str(path).startswith(str(WEB_DIR)):
        raise web.HTTPNotFound()
    return web.FileResponse(path)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s", datefmt="%H:%M:%S")
    p = argparse.ArgumentParser(description="foxBMS vECU WebSocket bridge")
    p.add_argument("--can", default="vcan1"); p.add_argument("--port", type=int, default=8080)
    p.add_argument("--host", default="0.0.0.0"); p.add_argument("--vecu", default=None)
    p.add_argument("--plant", default=None)
    asyncio.run(main(p.parse_args()))
