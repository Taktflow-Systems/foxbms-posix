#!/usr/bin/env python3
"""foxBMS POSIX vECU — WebSocket bridge for CAN data.

Reads CAN frames from SocketCAN, parses foxBMS + SIL probe messages,
and pushes structured JSON to connected browsers via WebSocket.
HTTP static files and WebSocket share the same port.

Usage:
    python3 web/server.py [--can vcan1] [--port 8080] [--host 0.0.0.0]

Dependencies: pip install aiohttp
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import random
import struct
import time
from pathlib import Path
from typing import Any

import aiohttp
import aiohttp.web as web

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

# -- CAN parsers ------------------------------------------------------------

def _p_0x220(d: bytes) -> None:
    state["bms_state"] = d[0] & 0x0F
    state["bms_state_name"] = BMS_STATES.get(state["bms_state"], "UNKNOWN")
    state["connected_strings"] = (d[0] >> 4) & 0x0F

def _p_0x221(d: bytes) -> None:
    state["pack_current_ma"] = struct.unpack_from(">i", d, 0)[0]
    state["pack_voltage_mv"] = struct.unpack_from(">I", d, 4)[0]

def _p_0x235(d: bytes) -> None:
    state["soc_pct"] = round(d[5] * 0.25, 2)


def _p_0x260(d: bytes) -> None:
    mux, base = d[0], d[0] * 3
    for i in range(3):
        idx = base + i
        off = 2 + 2 * i
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
    mn, mx, _, _ = struct.unpack_from("<hhhh", d, 0)
    state["cell_t_min"], state["cell_t_max"] = mn, mx

def _p_0x7f7(d: bytes) -> None:
    state["diag_fault_count"] = struct.unpack_from("<I", d, 0)[0]
    state["diag_last_id"], state["diag_last_event"] = d[4], d[5]

def _p_0x7f8(d: bytes) -> None:
    state["diag_bitmap"] = struct.unpack_from("<Q", d, 0)[0]

def _p_0x7f9(d: bytes) -> None:
    state["sys_state"], state["bms_state"] = d[0], d[4]
    state["bms_state_name"] = BMS_STATES.get(d[4], "UNKNOWN")

def _p_0x7fa(d: bytes) -> None:
    state["pack_current_ma"] = struct.unpack_from("<i", d, 0)[0]

def _p_0x7ff(d: bytes) -> None:
    state["heartbeat_tick"] = struct.unpack_from("<I", d, 0)[0]
    state["uptime_ms"] = struct.unpack_from("<I", d, 4)[0]

# -- Plant telemetry (0x600-0x602) ---------------------------------------------
def _p_0x600(d: bytes) -> None:
    state["plant_soc_pct"] = round(struct.unpack_from("<f", d, 0)[0], 2)
    state["plant_current_ma"] = struct.unpack_from("<i", d, 4)[0]

def _p_0x601(d: bytes) -> None:
    state["plant_ocv_mv"] = struct.unpack_from("<i", d, 0)[0]
    state["plant_pack_voltage_mv"] = struct.unpack_from("<i", d, 4)[0]

def _p_0x602(d: bytes) -> None:
    state["plant_ir_drop_mv"] = struct.unpack_from("<i", d, 0)[0]
    state["plant_discharging"] = bool(d[4])
    state["plant_n_cells"] = d[5]

def _p_plant_cells(base_idx: int, d: bytes) -> None:
    for i in range(4):
        idx = base_idx + i
        if idx < 18 and (2 * i + 2) <= len(d):
            state["plant_cell_voltages"][idx] = struct.unpack_from("<H", d, 2 * i)[0]

# -- CAN message log (last 20 frames) -----------------------------------------
can_log: list[dict] = []

def _log_can(can_id: int, d: bytes) -> None:
    entry = {
        "id": f"0x{can_id:03X}",
        "data": d[:8].hex().upper(),
        "t": round(time.time(), 3),
    }
    can_log.append(entry)
    if len(can_log) > 30:
        can_log.pop(0)

PARSERS: dict[int, Any] = {
    0x220: _p_0x220, 0x221: _p_0x221, 0x235: _p_0x235, 0x260: _p_0x260,
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

# -- Fault injection (browser -> CAN 0x7E0) --------------------------------

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

async def _send_can(arb_id: int, data: bytes) -> None:
    if _can_sock is None:
        return
    frame = struct.pack("=IB3x", arb_id, len(data)) + data.ljust(8, b"\x00")
    await asyncio.get_running_loop().sock_sendall(_can_sock, frame)

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
        # Log selected CAN frames for the web CAN monitor
        if arb_id in (0x220, 0x270, 0x280, 0x521, 0x210, 0x7F0, 0x7F7, 0x7F8, 0x7F9, 0x600, 0x601, 0x602, 0x603, 0x604, 0x605, 0x606, 0x607):
            _log_can(arb_id, data)
        parser = PARSERS.get(arb_id)
        if parser:
            try:
                parser(data)
            except Exception:
                log.debug("Parse error 0x%03X", arb_id, exc_info=True)

# -- WebSocket handler (aiohttp) -------------------------------------------

async def ws_handler(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    ws_clients.add(ws)
    log.info("WS client connected (%d total)", len(ws_clients))
    try:
        async for raw in ws:
            if raw.type == aiohttp.WSMsgType.TEXT:
                try:
                    msg = json.loads(raw.data)
                except json.JSONDecodeError:
                    continue
                if msg.get("action") == "reset":
                    # Clear all overrides — BMS stays in ERROR until
                    # power-cycle but overrides are removed.
                    await _send_can(0x7E0, struct.pack("<B7x", 0x00))
                    log.info("RESET: cleared all overrides (BMS needs restart to leave ERROR)")
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
            # Synthesize cell voltages from probe min/max if no per-cell data
            v_min = state["cell_v_min"]
            v_max = state["cell_v_max"]
            if v_min > 0 and v_max > 0:
                avg = (v_min + v_max) // 2
                spread = max((v_max - v_min) // 2, 1)
                state["cell_voltages"] = [
                    avg + random.randint(-spread, spread) for _ in range(18)
                ]
            # Pack voltage fallback: use plant data if BMS reports 0
            if state["pack_voltage_mv"] == 0 and state["plant_pack_voltage_mv"] != 0:
                state["pack_voltage_mv"] = state["plant_pack_voltage_mv"]
            state["can_log"] = can_log[-20:]  # Last 20 CAN frames
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

# -- HTTP static files ------------------------------------------------------
WEB_DIR = Path(__file__).resolve().parent

async def handle_index(_req: web.Request) -> web.FileResponse:
    return web.FileResponse(WEB_DIR / "index.html")

async def handle_static(req: web.Request) -> web.FileResponse:
    name = req.match_info["name"]
    path = (WEB_DIR / name).resolve()
    if not path.is_file() or not str(path).startswith(str(WEB_DIR)):
        raise web.HTTPNotFound()
    return web.FileResponse(path)

# -- Main -------------------------------------------------------------------

async def main(args: argparse.Namespace) -> None:
    app = web.Application()
    app.router.add_get("/ws", ws_handler)
    app.router.add_get("/", handle_index)
    app.router.add_get("/{name}", handle_static)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, args.host, args.port)
    await site.start()
    log.info("Serving on http://%s:%d  (WS at /ws)", args.host, args.port)

    await asyncio.gather(can_reader(args.can), broadcast_loop())

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    p = argparse.ArgumentParser(description="foxBMS vECU WebSocket bridge")
    p.add_argument("--can", default="vcan1", help="SocketCAN interface (default: vcan1)")
    p.add_argument("--port", type=int, default=8080, help="HTTP port (default: 8080)")
    p.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    asyncio.run(main(p.parse_args()))
