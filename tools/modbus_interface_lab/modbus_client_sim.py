#!/usr/bin/env python3
"""Small Modbus/TCP client behavior simulator.

This tool is intentionally dependency-free so it can run on a normal Windows or
Linux test laptop. It supports normal polling as well as hostile-but-realistic
client behavior such as leaked TCP sessions and reconnect storms.
"""

from __future__ import annotations

import argparse
import csv
import json
import socket
import struct
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


FUNCTION_CODES = {
    "coil": 1,
    "coils": 1,
    "discrete": 2,
    "discrete_input": 2,
    "discrete_inputs": 2,
    "input": 4,
    "input_register": 4,
    "input_registers": 4,
    "ireg": 4,
    "holding": 3,
    "holding_register": 3,
    "holding_registers": 3,
    "hreg": 3,
}

TABLE_PREFIXES = {
    1: (1, 10000),
    2: (10001, 10000),
    3: (40001, 10000),
    4: (30001, 10000),
}


@dataclass(frozen=True)
class RegisterSpec:
    name: str
    table: str
    address: int
    offset: int
    count: int
    unit_id: int
    function_code: int
    data_type: str = "raw"
    scale: float = 1.0
    word_order: str = "big"


class ModbusError(Exception):
    pass


class EventLog:
    def __init__(self, json_log: Path | None = None) -> None:
        self._lock = threading.Lock()
        self._file = None
        if json_log:
            json_log.parent.mkdir(parents=True, exist_ok=True)
            self._file = json_log.open("a", encoding="utf-8")

    def close(self) -> None:
        if self._file:
            self._file.close()

    def event(self, event: str, **fields: object) -> None:
        payload = {"ts": round(time.time(), 3), "event": event, **fields}
        line = json.dumps(payload, sort_keys=True)
        with self._lock:
            print(line, flush=True)
            if self._file:
                self._file.write(line + "\n")
                self._file.flush()


class ModbusTcpClient:
    def __init__(
        self,
        host: str,
        port: int,
        connect_timeout: float,
        request_timeout: float,
        log: EventLog,
        label: str,
    ) -> None:
        self.host = host
        self.port = port
        self.connect_timeout = connect_timeout
        self.request_timeout = request_timeout
        self.log = log
        self.label = label
        self.sock: socket.socket | None = None
        self.transaction_id = 0

    def connect(self) -> None:
        started = time.perf_counter()
        self.sock = socket.create_connection(
            (self.host, self.port), timeout=self.connect_timeout
        )
        self.sock.settimeout(self.request_timeout)
        elapsed_ms = elapsed(started)
        local = self.sock.getsockname()
        self.log.event(
            "connect_ok",
            label=self.label,
            host=self.host,
            port=self.port,
            local=f"{local[0]}:{local[1]}",
            elapsed_ms=elapsed_ms,
        )

    def close(self, abrupt: bool = False) -> None:
        if not self.sock:
            return
        try:
            if abrupt:
                self.sock.setsockopt(
                    socket.SOL_SOCKET,
                    socket.SO_LINGER,
                    struct.pack("hh", 1, 0),
                )
            self.sock.close()
            self.log.event("close", label=self.label, abrupt=abrupt)
        finally:
            self.sock = None

    def read(self, spec: RegisterSpec) -> list[int]:
        if not self.sock:
            raise ModbusError("client is not connected")
        if spec.function_code in (1, 2):
            pdu = struct.pack(">BHH", spec.function_code, spec.offset, spec.count)
        elif spec.function_code in (3, 4):
            pdu = struct.pack(">BHH", spec.function_code, spec.offset, spec.count)
        else:
            raise ModbusError(f"unsupported function code {spec.function_code}")

        self.transaction_id = (self.transaction_id + 1) & 0xFFFF
        tid = self.transaction_id
        mbap = struct.pack(">HHHB", tid, 0, len(pdu) + 1, spec.unit_id)
        started = time.perf_counter()
        self.sock.sendall(mbap + pdu)

        header = recv_exact(self.sock, 7)
        rx_tid, protocol_id, length, unit_id = struct.unpack(">HHHB", header)
        body = recv_exact(self.sock, length - 1)
        elapsed_ms = elapsed(started)

        if rx_tid != tid:
            raise ModbusError(f"transaction mismatch tx={tid} rx={rx_tid}")
        if protocol_id != 0:
            raise ModbusError(f"unexpected protocol id {protocol_id}")
        if unit_id != spec.unit_id:
            raise ModbusError(f"unit mismatch tx={spec.unit_id} rx={unit_id}")
        if not body:
            raise ModbusError("empty Modbus PDU")

        rx_fc = body[0]
        if rx_fc == (spec.function_code | 0x80):
            exception_code = body[1] if len(body) > 1 else None
            raise ModbusError(f"Modbus exception {exception_code}")
        if rx_fc != spec.function_code:
            raise ModbusError(f"function mismatch tx={spec.function_code} rx={rx_fc}")

        if spec.function_code in (3, 4):
            if len(body) < 2:
                raise ModbusError("short register response")
            byte_count = body[1]
            data = body[2:]
            if byte_count != len(data):
                raise ModbusError(
                    f"byte count mismatch declared={byte_count} actual={len(data)}"
                )
            if byte_count % 2:
                raise ModbusError(f"odd register byte count {byte_count}")
            values = [
                struct.unpack(">H", data[i : i + 2])[0]
                for i in range(0, len(data), 2)
            ]
        else:
            if len(body) < 2:
                raise ModbusError("short bit response")
            byte_count = body[1]
            data = body[2:]
            if byte_count != len(data):
                raise ModbusError(
                    f"byte count mismatch declared={byte_count} actual={len(data)}"
                )
            values = unpack_bits(data, spec.count)

        self.log.event(
            "read_ok",
            label=self.label,
            name=spec.name,
            table=spec.table,
            address=spec.address,
            offset=spec.offset,
            count=spec.count,
            unit_id=spec.unit_id,
            elapsed_ms=elapsed_ms,
            raw=values,
            decoded=decode_registers(values, spec),
        )
        return values


def recv_exact(sock: socket.socket, count: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < count:
        chunk = sock.recv(count - len(chunks))
        if not chunk:
            raise ModbusError("connection closed while receiving")
        chunks.extend(chunk)
    return bytes(chunks)


def unpack_bits(data: bytes, count: int) -> list[int]:
    bits: list[int] = []
    for byte in data:
        for bit in range(8):
            bits.append((byte >> bit) & 1)
            if len(bits) == count:
                return bits
    return bits


def elapsed(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def decode_registers(values: list[int], spec: RegisterSpec) -> object:
    if spec.function_code in (1, 2):
        return values
    if spec.data_type in ("", "raw"):
        return None

    words = list(values)
    if spec.word_order == "little" and len(words) > 1:
        words.reverse()

    data = b"".join(struct.pack(">H", word) for word in words)
    try:
        if spec.data_type == "uint16":
            value: object = words[0]
        elif spec.data_type == "int16":
            value = struct.unpack(">h", data[:2])[0]
        elif spec.data_type == "uint32":
            value = struct.unpack(">I", data[:4])[0]
        elif spec.data_type == "int32":
            value = struct.unpack(">i", data[:4])[0]
        elif spec.data_type == "float32":
            value = struct.unpack(">f", data[:4])[0]
        elif spec.data_type == "ascii":
            value = data.rstrip(b"\x00 ").decode("ascii", errors="replace")
        else:
            return None
    except (IndexError, struct.error):
        return None

    if isinstance(value, (int, float)) and spec.scale != 1.0:
        return value * spec.scale
    return value


def parse_specs(args: argparse.Namespace) -> list[RegisterSpec]:
    specs: list[RegisterSpec] = []
    if args.registers and args.registers.exists():
        with args.registers.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            for row_index, row in enumerate(reader, start=2):
                if not enabled(row.get("enabled", "1")):
                    continue
                specs.append(spec_from_row(row, row_index, args))

    for item in args.range:
        specs.append(spec_from_range(item, args))

    if args.single_registers:
        specs = expand_single_registers(specs)

    if args.coalesce:
        specs = coalesce_specs(specs, args.max_registers_per_request)

    return specs


def spec_from_row(
    row: dict[str, str], row_index: int, args: argparse.Namespace
) -> RegisterSpec:
    name = clean(row.get("name")) or f"row_{row_index}"
    table = normalize_table(clean(row.get("type") or row.get("table") or "holding"))
    address = parse_int(row.get("address"), f"address at CSV row {row_index}")
    count = parse_int(row.get("count") or "1", f"count at CSV row {row_index}")
    unit_id = parse_int(row.get("unit_id") or str(args.unit_id), "unit_id")
    data_type = clean(row.get("data_type") or "raw").lower()
    scale = parse_float(row.get("scale") or "1")
    word_order = clean(row.get("word_order") or "big").lower()
    address_base = clean(row.get("address_base") or args.address_base).lower()
    function_code = FUNCTION_CODES[table]
    offset = address_to_offset(table, address, address_base)
    validate_spec(name, function_code, offset, count, unit_id)
    return RegisterSpec(
        name=name,
        table=table,
        address=address,
        offset=offset,
        count=count,
        unit_id=unit_id,
        function_code=function_code,
        data_type=data_type,
        scale=scale,
        word_order=word_order,
    )


def spec_from_range(item: str, args: argparse.Namespace) -> RegisterSpec:
    parts = item.split(":")
    if len(parts) not in (3, 4):
        raise SystemExit(
            "--range must use type:address:count or type:address:count:unit_id"
        )
    table = normalize_table(parts[0])
    address = parse_int(parts[1], "--range address")
    count = parse_int(parts[2], "--range count")
    unit_id = parse_int(parts[3], "--range unit_id") if len(parts) == 4 else args.unit_id
    function_code = FUNCTION_CODES[table]
    offset = address_to_offset(table, address, args.address_base)
    name = f"{table}_{address}_{count}"
    validate_spec(name, function_code, offset, count, unit_id)
    return RegisterSpec(
        name=name,
        table=table,
        address=address,
        offset=offset,
        count=count,
        unit_id=unit_id,
        function_code=function_code,
    )


def normalize_table(table: str) -> str:
    key = table.strip().lower().replace(" ", "_").replace("-", "_")
    if key not in FUNCTION_CODES:
        raise SystemExit(f"unsupported register type/table: {table!r}")
    if FUNCTION_CODES[key] == 1:
        return "coil"
    if FUNCTION_CODES[key] == 2:
        return "discrete"
    if FUNCTION_CODES[key] == 3:
        return "holding"
    return "input"


def address_to_offset(table: str, address: int, address_base: str) -> int:
    if address_base in ("zero", "zero_based", "offset", "0"):
        return address
    if address_base in ("one", "one_based", "1"):
        return address - 1
    if address_base != "auto":
        raise SystemExit(f"unsupported address_base: {address_base}")

    function_code = FUNCTION_CODES[table]
    prefix_start, span = TABLE_PREFIXES[function_code]
    if prefix_start <= address < prefix_start + span:
        return address - prefix_start
    return address


def validate_spec(
    name: str, function_code: int, offset: int, count: int, unit_id: int
) -> None:
    if not 0 <= unit_id <= 247:
        raise SystemExit(f"{name}: unit_id must be 0..247")
    if not 0 <= offset <= 0xFFFF:
        raise SystemExit(f"{name}: offset must be 0..65535 after address conversion")
    if count <= 0:
        raise SystemExit(f"{name}: count must be positive")
    if function_code in (3, 4) and count > 125:
        raise SystemExit(f"{name}: Modbus register read count cannot exceed 125")
    if function_code in (1, 2) and count > 2000:
        raise SystemExit(f"{name}: Modbus bit read count cannot exceed 2000")


def expand_single_registers(specs: Iterable[RegisterSpec]) -> list[RegisterSpec]:
    expanded: list[RegisterSpec] = []
    for spec in specs:
        for index in range(spec.count):
            expanded.append(
                RegisterSpec(
                    name=f"{spec.name}_{index}",
                    table=spec.table,
                    address=spec.address + index,
                    offset=spec.offset + index,
                    count=1,
                    unit_id=spec.unit_id,
                    function_code=spec.function_code,
                    data_type="raw",
                )
            )
    return expanded


def coalesce_specs(specs: list[RegisterSpec], max_count: int) -> list[RegisterSpec]:
    if not specs:
        return []
    ordered = sorted(specs, key=lambda s: (s.unit_id, s.function_code, s.offset))
    merged: list[RegisterSpec] = []
    current = ordered[0]
    for spec in ordered[1:]:
        same_group = (
            spec.unit_id == current.unit_id
            and spec.function_code == current.function_code
            and spec.offset == current.offset + current.count
            and current.count + spec.count <= max_count
        )
        if same_group:
            current = RegisterSpec(
                name=f"{current.name}..{spec.name}",
                table=current.table,
                address=current.address,
                offset=current.offset,
                count=current.count + spec.count,
                unit_id=current.unit_id,
                function_code=current.function_code,
            )
        else:
            merged.append(current)
            current = spec
    merged.append(current)
    return merged


def run_normal(args: argparse.Namespace, specs: list[RegisterSpec], log: EventLog) -> int:
    require_specs(specs, args.mode)
    client = ModbusTcpClient(
        args.host, args.port, args.connect_timeout, args.request_timeout, log, "normal"
    )
    failures = 0
    try:
        client.connect()
        for cycle in cycle_range(args.cycles):
            failures += poll_specs(client, specs, cycle, args.stop_on_error)
            sleep_between_cycles(args.interval, cycle, args.cycles)
    except Exception as exc:
        failures += 1
        log.event("session_error", label="normal", error=str(exc))
    finally:
        client.close()
    return failures


def run_clean_reconnect(
    args: argparse.Namespace, specs: list[RegisterSpec], log: EventLog
) -> int:
    require_specs(specs, args.mode)
    failures = 0
    for cycle in cycle_range(args.cycles):
        client = ModbusTcpClient(
            args.host,
            args.port,
            args.connect_timeout,
            args.request_timeout,
            log,
            f"clean_reconnect_{cycle}",
        )
        try:
            client.connect()
            failures += poll_specs(client, specs, cycle, args.stop_on_error)
        except Exception as exc:
            failures += 1
            log.event("session_error", label=client.label, cycle=cycle, error=str(exc))
        finally:
            client.close()
        sleep_between_cycles(args.interval, cycle, args.cycles)
    return failures


def run_parallel(args: argparse.Namespace, specs: list[RegisterSpec], log: EventLog) -> int:
    require_specs(specs, args.mode)
    failures = 0
    failures_lock = threading.Lock()

    def worker(index: int) -> None:
        nonlocal failures
        local_args = argparse.Namespace(**vars(args))
        local_args.cycles = args.cycles
        client = ModbusTcpClient(
            args.host,
            args.port,
            args.connect_timeout,
            args.request_timeout,
            log,
            f"parallel_{index}",
        )
        local_failures = 0
        try:
            client.connect()
            for cycle in cycle_range(local_args.cycles):
                local_failures += poll_specs(
                    client, specs, cycle, local_args.stop_on_error
                )
                sleep_between_cycles(local_args.interval, cycle, local_args.cycles)
        except Exception as exc:
            local_failures += 1
            log.event("session_error", label=client.label, error=str(exc))
        finally:
            client.close()
        with failures_lock:
            failures += local_failures

    threads = [
        threading.Thread(target=worker, args=(index,), daemon=True)
        for index in range(args.sessions)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return failures


def run_leak(args: argparse.Namespace, specs: list[RegisterSpec], log: EventLog) -> int:
    clients: list[ModbusTcpClient] = []
    failures = 0
    for index in range(args.sessions):
        client = ModbusTcpClient(
            args.host,
            args.port,
            args.connect_timeout,
            args.request_timeout,
            log,
            f"leak_{index + 1}",
        )
        try:
            client.connect()
            clients.append(client)
            if args.read_on_open and specs:
                failures += poll_specs(client, specs[:1], 0, args.stop_on_error)
        except Exception as exc:
            failures += 1
            log.event("connect_error", label=client.label, error=str(exc))
            if args.stop_on_error:
                break

    log.event(
        "leak_idle_start",
        open_sessions=len(clients),
        idle_before_extra_seconds=args.idle_before_extra,
    )
    time.sleep(args.idle_before_extra)

    for extra in range(args.extra_sessions):
        label = f"extra_{extra + 1}"
        client = ModbusTcpClient(
            args.host,
            args.port,
            args.connect_timeout,
            args.request_timeout,
            log,
            label,
        )
        try:
            client.connect()
            if specs:
                failures += poll_specs(client, specs[:1], 0, args.stop_on_error)
            client.close()
        except Exception as exc:
            failures += 1
            log.event("extra_session_error", label=label, error=str(exc))

    log.event("leak_hold_start", open_sessions=len(clients), hold_seconds=args.hold_seconds)
    hold_until = time.time() + args.hold_seconds
    while time.time() < hold_until:
        time.sleep(min(1.0, hold_until - time.time()))

    for client in clients:
        if not args.keep_leaked_open:
            client.close()
    log.event("leak_hold_end", remaining_open=args.sessions if args.keep_leaked_open else 0)
    return failures


def run_abrupt_close(
    args: argparse.Namespace, specs: list[RegisterSpec], log: EventLog
) -> int:
    failures = 0
    for index in range(args.sessions):
        client = ModbusTcpClient(
            args.host,
            args.port,
            args.connect_timeout,
            args.request_timeout,
            log,
            f"abrupt_{index + 1}",
        )
        try:
            client.connect()
            if args.read_on_open and specs:
                failures += poll_specs(client, specs[:1], 0, args.stop_on_error)
        except Exception as exc:
            failures += 1
            log.event("session_error", label=client.label, error=str(exc))
        finally:
            client.close(abrupt=True)
        time.sleep(args.interval)
    return failures


def poll_specs(
    client: ModbusTcpClient,
    specs: list[RegisterSpec],
    cycle: int,
    stop_on_error: bool,
) -> int:
    failures = 0
    client.log.event("poll_cycle_start", label=client.label, cycle=cycle, reads=len(specs))
    for spec in specs:
        try:
            client.read(spec)
        except Exception as exc:
            failures += 1
            client.log.event(
                "read_error",
                label=client.label,
                cycle=cycle,
                name=spec.name,
                address=spec.address,
                offset=spec.offset,
                count=spec.count,
                error=str(exc),
            )
            if stop_on_error:
                raise
    client.log.event(
        "poll_cycle_end", label=client.label, cycle=cycle, failures=failures
    )
    return failures


def require_specs(specs: list[RegisterSpec], mode: str) -> None:
    if not specs:
        raise SystemExit(
            f"mode {mode!r} needs registers. Provide --range or enable rows in registers.csv"
        )


def cycle_range(cycles: int) -> Iterable[int]:
    cycle = 0
    while cycles == 0 or cycle < cycles:
        yield cycle
        cycle += 1


def sleep_between_cycles(interval: float, cycle: int, cycles: int) -> None:
    if cycles == 0 or cycle < cycles - 1:
        time.sleep(interval)


def enabled(value: str) -> bool:
    return str(value).strip().lower() not in ("", "0", "false", "no", "n", "off")


def clean(value: str | None) -> str:
    return "" if value is None else value.strip()


def parse_int(value: str | None, label: str) -> int:
    if value is None or not str(value).strip():
        raise SystemExit(f"missing {label}")
    text = str(value).strip().replace("_", "")
    try:
        return int(text, 0)
    except ValueError as exc:
        raise SystemExit(f"invalid {label}: {value!r}") from exc


def parse_float(value: str | None) -> float:
    if value is None or not str(value).strip():
        return 1.0
    return float(str(value).strip())


def parse_args(argv: list[str]) -> argparse.Namespace:
    default_registers = Path(__file__).with_name("registers.csv")
    parser = argparse.ArgumentParser(
        description="Modbus/TCP client behavior simulator for BMS interface testing"
    )
    parser.add_argument("--host", help="BMS Modbus/TCP host or IP")
    parser.add_argument("--port", type=int, default=502)
    parser.add_argument("--unit-id", type=int, default=1)
    parser.add_argument(
        "--registers",
        type=Path,
        default=default_registers,
        help="CSV register map; disabled template rows are ignored",
    )
    parser.add_argument(
        "--range",
        action="append",
        default=[],
        help="Ad-hoc read range: type:address:count[:unit_id], e.g. holding:0:10",
    )
    parser.add_argument(
        "--address-base",
        choices=["auto", "zero", "one", "offset", "zero_based", "one_based", "0", "1"],
        default="auto",
        help="How numeric addresses are converted to Modbus offsets",
    )
    parser.add_argument(
        "--mode",
        choices=[
            "normal",
            "clean-reconnect",
            "parallel",
            "leak",
            "abrupt-close",
        ],
        default="normal",
    )
    parser.add_argument("--cycles", type=int, default=1, help="0 means forever")
    parser.add_argument("--interval", type=float, default=60.0)
    parser.add_argument("--sessions", type=int, default=10)
    parser.add_argument("--extra-sessions", type=int, default=1)
    parser.add_argument(
        "--idle-before-extra",
        type=float,
        default=0.0,
        help="Seconds to leave leaked sessions idle before opening extra clients",
    )
    parser.add_argument("--hold-seconds", type=float, default=120.0)
    parser.add_argument("--connect-timeout", type=float, default=3.0)
    parser.add_argument("--request-timeout", type=float, default=2.0)
    parser.add_argument("--json-log", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--stop-on-error", action="store_true")
    parser.add_argument("--read-on-open", action="store_true")
    parser.add_argument("--keep-leaked-open", action="store_true")
    parser.add_argument("--single-registers", action="store_true")
    parser.add_argument("--coalesce", action="store_true")
    parser.add_argument("--max-registers-per-request", type=int, default=120)
    args = parser.parse_args(argv)
    if not args.dry_run and not args.host:
        parser.error("--host is required unless --dry-run is used")
    return args


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    specs = parse_specs(args)
    log = EventLog(args.json_log)
    try:
        log.event(
            "plan",
            mode=args.mode,
            host=args.host,
            port=args.port,
            unit_id=args.unit_id,
            reads=len(specs),
            sessions=args.sessions,
            cycles=args.cycles,
        )
        for spec in specs:
            log.event(
                "planned_read",
                name=spec.name,
                table=spec.table,
                address=spec.address,
                offset=spec.offset,
                count=spec.count,
                unit_id=spec.unit_id,
                function_code=spec.function_code,
            )
        if args.dry_run:
            return 0

        if args.mode == "normal":
            failures = run_normal(args, specs, log)
        elif args.mode == "clean-reconnect":
            failures = run_clean_reconnect(args, specs, log)
        elif args.mode == "parallel":
            failures = run_parallel(args, specs, log)
        elif args.mode == "leak":
            failures = run_leak(args, specs, log)
        elif args.mode == "abrupt-close":
            failures = run_abrupt_close(args, specs, log)
        else:
            raise SystemExit(f"unsupported mode: {args.mode}")

        log.event("complete", failures=failures)
        return 1 if failures else 0
    finally:
        log.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
