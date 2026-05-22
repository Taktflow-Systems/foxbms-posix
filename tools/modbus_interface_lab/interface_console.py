#!/usr/bin/env python3
"""Browser GUI for BMS interface E2E Modbus exercises."""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import socket
import struct
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

from modbus_client_sim import (
    FUNCTION_CODES,
    ModbusError,
    ModbusTcpClient,
    RegisterSpec,
    address_to_offset,
    decode_registers,
    normalize_table,
    recv_exact,
    validate_spec,
)


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "interface_gui"
DATA_DIR = ROOT / "data"
BY_SHEET_DIR = DATA_DIR / "by_sheet"
USE_CASE_MD = DATA_DIR / "use_cases.md"
RUN_DIR = ROOT / "runs"
PROFILE_FILE = DATA_DIR / "interface_profiles.json"
MAX_REGISTERS_PER_READ = 120
BACKEND_NOT_AVAILABLE = 0xFFFF


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.name


def load_profile_config(path: Path = PROFILE_FILE) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"profile file not found: {path}")
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data.get("profiles"), dict):
        raise ValueError("profile file must contain a profiles object")
    return data


def load_profiles() -> dict[str, dict[str, Any]]:
    profiles = load_profile_config()["profiles"]
    expanded = {str(key): value for key, value in profiles.items()}
    apply_profile_expansions(expanded)
    return expanded


def apply_profile_expansions(profiles: dict[str, dict[str, Any]]) -> None:
    available_reads = build_available_read_ranges(profiles)
    for profile in profiles.values():
        if profile.get("read_all_available"):
            profile["reads"] = available_reads


def build_available_read_ranges(profiles: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    intervals: dict[tuple[str, int], list[tuple[int, int]]] = {}
    for profile in profiles.values():
        for item in profile.get("reads", []):
            add_available_interval(intervals, item)
        for item in profile.get("writes", []):
            add_available_interval(intervals, {**item, "table": item.get("table", "holding"), "count": 1})

    reads: list[dict[str, Any]] = []
    for (table, unit_id), ranges in sorted(intervals.items()):
        merged = merge_intervals(ranges)
        for start_offset, end_offset in merged:
            current = start_offset
            while current <= end_offset:
                count = min(MAX_REGISTERS_PER_READ, end_offset - current + 1)
                start_address = table_address_from_offset(table, current)
                end_address = start_address + count - 1
                reads.append(
                    {
                        "name": f"All available {table} registers {start_address}-{end_address}",
                        "table": table,
                        "address": start_address,
                        "count": count,
                        "unit_id": unit_id,
                        "address_base": "auto",
                        "data_type": "raw",
                    }
                )
                current += count
    return reads


def add_available_interval(
    intervals: dict[tuple[str, int], list[tuple[int, int]]],
    item: dict[str, Any],
) -> None:
    table = str(item.get("table") or "holding")
    table = normalize_table(table)
    address = int(item["address"])
    count = max(1, int(item.get("count", 1)))
    unit_id = int(item.get("unit_id") or load_defaults().get("unit_id") or 1)
    address_base = str(item.get("address_base") or load_defaults().get("address_base") or "auto")
    offset = address_to_offset(table, address, address_base)
    intervals.setdefault((table, unit_id), []).append((offset, offset + count - 1))


def merge_intervals(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not ranges:
        return []
    ordered = sorted(ranges)
    merged = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end + 1:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def table_address_from_offset(table: str, offset: int) -> int:
    if table == "coil":
        return offset + 1
    if table == "discrete":
        return offset + 10001
    if table == "input":
        return offset + 30001
    return offset + 40001


def load_defaults() -> dict[str, Any]:
    return load_profile_config().get("defaults", {})


def load_adapters() -> dict[str, Any]:
    return load_profile_config().get("adapters", {})


class AppLog:
    def __init__(self, run: "RunState") -> None:
        self.run = run

    def event(self, event: str, **fields: object) -> None:
        self.run.event(event, **fields)


@dataclass
class RunState:
    run_id: str
    scenario_id: str
    title: str
    jsonl_path: Path
    status: str = "queued"
    exit_code: int | None = None

    def __post_init__(self) -> None:
        self.started_at = time.time()
        self.finished_at: float | None = None
        self.events: list[dict[str, Any]] = []
        self.cancel_requested = False
        self.lock = threading.Lock()

    def event(self, event: str, **fields: object) -> None:
        payload = {
            "ts": round(time.time(), 3),
            "event": event,
            "scenario_id": self.scenario_id,
            **fields,
        }
        line = json.dumps(payload, sort_keys=True)
        with self.lock:
            self.events.append(payload)
            self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            with self.jsonl_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
            with self.text_log_path.open("a", encoding="utf-8") as handle:
                handle.write(format_text_event(payload) + "\n")

    @property
    def run_dir(self) -> Path:
        return self.jsonl_path.parent

    @property
    def request_path(self) -> Path:
        return self.run_dir / "request.json"

    @property
    def result_path(self) -> Path:
        return self.run_dir / "result.json"

    @property
    def text_log_path(self) -> Path:
        return self.run_dir / "run.log"

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "run_id": self.run_id,
                "scenario_id": self.scenario_id,
                "title": self.title,
                "status": self.status,
                "exit_code": self.exit_code,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "run_dir": display_path(self.run_dir),
                "jsonl_path": display_path(self.jsonl_path),
                "request_path": display_path(self.request_path),
                "result_path": display_path(self.result_path),
                "text_log_path": display_path(self.text_log_path),
                "events": list(self.events[-500:]),
            }


RUNS: dict[str, RunState] = {}
RUNS_LOCK = threading.Lock()
STARTED_AT = time.time()


def empty_profile() -> dict[str, Any]:
    return {"kind": "manual", "reads": [], "writes": [], "terms": []}


def scenario_log_folder(scenario_id: str) -> str:
    if scenario_id.isdigit():
        return f"use_case_{int(scenario_id):02d}"
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", scenario_id).strip("_") or "unknown"
    return f"use_case_{safe}"


def make_run_jsonl_path(scenario_id: str, run_id: str) -> Path:
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    run_dir = RUN_DIR / scenario_log_folder(scenario_id) / f"{timestamp}-{run_id}"
    return run_dir / "events.jsonl"


def format_text_event(payload: dict[str, Any]) -> str:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(payload["ts"])))
    fields = [
        f"{key}={json.dumps(value, sort_keys=True)}"
        for key, value in payload.items()
        if key not in ("ts", "event")
    ]
    return f"{timestamp} {payload['event']}{' ' + ' '.join(fields) if fields else ''}"


def write_run_request(run: RunState, request: dict[str, Any]) -> None:
    run.run_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run.run_id,
        "scenario_id": run.scenario_id,
        "title": run.title,
        "created_at": round(run.started_at, 3),
        "request": request,
    }
    run.request_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_run_result(run: RunState) -> None:
    run.run_dir.mkdir(parents=True, exist_ok=True)
    with run.lock:
        payload = {
            "run_id": run.run_id,
            "scenario_id": run.scenario_id,
            "title": run.title,
            "status": run.status,
            "exit_code": run.exit_code,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            "event_count": len(run.events),
            "last_event": run.events[-1] if run.events else None,
            "paths": {
                "run_dir": display_path(run.run_dir),
                "request": display_path(run.request_path),
                "events_jsonl": display_path(run.jsonl_path),
                "text_log": display_path(run.text_log_path),
                "result": display_path(run.result_path),
            },
        }
    run.result_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def strip_markdown(text: str) -> str:
    text = text.replace("**", "").replace("`", "")
    text = re.sub(r"<br\s*/?>", " ", text)
    return html.unescape(text).strip()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "action"


def extract_action_flow(raw_scenario: str) -> dict[str, Any]:
    _title, separator, action_source = raw_scenario.partition(" - ")
    if not separator:
        action_source = raw_scenario
    clauses = [clause.strip() for clause in action_source.split(";")]
    actions: list[dict[str, Any]] = []
    from_state = "ready"
    for clause in clauses:
        bold = re.search(r"\*\*(.+?)\*\*", clause)
        if not bold:
            continue
        label = re.sub(r"\s+", " ", strip_markdown(clause)).strip(" .")
        if not label:
            continue
        verb_text = re.sub(r"\s+", " ", strip_markdown(bold.group(1))).strip()
        verb = verb_text.split(maxsplit=1)[0] if verb_text else label.split(maxsplit=1)[0]
        target = label[len(verb) :].strip() if label.lower().startswith(verb.lower()) else label
        index = len(actions) + 1
        action_id = f"a{index}_{slugify(verb)}"
        to_state = f"after_{action_id}"
        actions.append(
            {
                "id": action_id,
                "order": index,
                "label": label,
                "verb": verb,
                "target": target,
                "from_state": from_state,
                "to_state": to_state,
            }
        )
        from_state = to_state
    return {
        "initial_state": "ready",
        "terminal_state": from_state,
        "actions": actions,
    }


def parse_markdown_table(
    path: Path = USE_CASE_MD,
    profiles: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    profiles = profiles or load_profiles()
    cases: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        parts = [part.strip() for part in line.strip().strip("|").split("|")]
        if len(parts) < 5 or not parts[0].isdigit():
            continue
        raw_scenario = parts[1]
        scenario = strip_markdown(raw_scenario)
        title, _, detail = scenario.partition(" - ")
        profile = profiles.get(parts[0], empty_profile())
        action_flow = extract_action_flow(raw_scenario)
        cases.append(
            {
                "id": parts[0],
                "title": title,
                "detail": detail or scenario,
                "available_test": strip_markdown(parts[2]),
                "status": strip_markdown(parts[3]),
                "priority": strip_markdown(parts[4]),
                "kind": profile["kind"],
                "reads": profile.get("reads", []),
                "writes": profile.get("writes", []),
                "terms": profile.get("terms", []),
                "action_flow": action_flow,
            }
        )
    return cases


def count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def build_sheet_summary() -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for lines_path in sorted(BY_SHEET_DIR.glob("*_ocr_lines.csv")):
        sheet_key = lines_path.name.removesuffix("_ocr_lines.csv")
        words_path = BY_SHEET_DIR / f"{sheet_key}_ocr_words.csv"
        summary.append(
            {
                "sheet_key": sheet_key,
                "lines_file": lines_path.name,
                "words_file": words_path.name,
                "line_rows": count_csv_rows(lines_path),
                "word_rows": count_csv_rows(words_path),
            }
        )
    return summary


def snippets_for_terms(terms: list[str], limit: int = 8) -> list[dict[str, Any]]:
    if not terms:
        return []
    lowered = [term.lower() for term in terms]
    snippets: list[dict[str, Any]] = []
    for path in sorted(BY_SHEET_DIR.glob("*_ocr_lines.csv")):
        sheet_key = path.name.removesuffix("_ocr_lines.csv")
        with path.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                text = row.get("text", "")
                haystack = text.lower()
                if any(term.lower() in haystack for term in lowered):
                    snippets.append(
                        {
                            "sheet_key": sheet_key,
                            "source_image": row.get("source_image", ""),
                            "line_index": row.get("line_index", ""),
                            "text": text,
                        }
                    )
                    if len(snippets) >= limit:
                        return snippets
    return snippets


def search_evidence(query: str, limit: int = 25) -> list[dict[str, Any]]:
    terms = [term for term in re.split(r"[\s,;]+", query.strip()) if term]
    if not terms:
        return []
    return snippets_for_terms(terms, limit=max(1, min(limit, 100)))


def file_info(path: Path) -> dict[str, Any]:
    info: dict[str, Any] = {"path": display_path(path), "exists": path.exists()}
    if path.exists():
        stat = path.stat()
        info.update({"size_bytes": stat.st_size, "modified_at": round(stat.st_mtime, 3)})
    return info


def build_file_inventory() -> dict[str, Any]:
    csv_files = []
    if BY_SHEET_DIR.exists():
        csv_files = [file_info(path) for path in sorted(BY_SHEET_DIR.glob("*.csv"))]
    return {
        "profile_file": file_info(PROFILE_FILE),
        "use_case_markdown": file_info(USE_CASE_MD),
        "by_sheet_dir": display_path(BY_SHEET_DIR),
        "run_dir": display_path(RUN_DIR),
        "csv_files": csv_files,
    }


def backend_api_contract() -> dict[str, Any]:
    return {
        "adapter": "backend_polling_api",
        "purpose": "Connect the e2e test console to one backend poller/cache instead of opening browser-driven Modbus sessions.",
        "base_url": "Configured from the GUI Host field. Use a full URL such as http://127.0.0.1:8766, or host plus Port.",
        "required_endpoints": {
            "health": {
                "method": "GET",
                "path": "/api/v1/health",
                "response": {"ok": True, "name": "poller-name", "version": "string"},
            },
            "read_registers": {
                "method": "POST",
                "path": "/api/v1/registers/read",
                "request": {
                    "items": [
                        {
                            "name": "SoC",
                            "table": "holding",
                            "address": 40071,
                            "count": 2,
                            "unit_id": 1,
                            "data_type": "raw",
                        }
                    ],
                    "run_id": "e2e-run-id",
                },
                "response": {
                    "items": [
                        {
                            "name": "SoC",
                            "table": "holding",
                            "address": 40071,
                            "values": [70, 96],
                            "quality": "ok",
                            "timestamp": "ISO-8601 or unix seconds",
                        }
                    ]
                },
            },
        },
        "optional_endpoints": {
            "write_registers": {
                "method": "POST",
                "path": "/api/v1/registers/write",
                "request": {
                    "items": [
                        {
                            "name": "SetCon",
                            "table": "holding",
                            "address": 40171,
                            "value": 1,
                            "unit_id": 1,
                        }
                    ],
                    "run_id": "e2e-run-id",
                    "reason": "bms-interface-e2e",
                },
                "response": {"ok": True, "items": [{"address": 40171, "status": "accepted"}]},
            }
        },
        "compatibility": {
            "plant_model": "The current local plant model can be used through /api/status and /api/registers?q=<address>.",
        },
    }


def build_model() -> dict[str, Any]:
    config = load_profile_config()
    profiles = {str(key): value for key, value in config["profiles"].items()}
    apply_profile_expansions(profiles)
    cases = parse_markdown_table(profiles=profiles)
    for case in cases:
        case["snippets"] = snippets_for_terms(case.get("terms", []))
    return {
        "use_case_markdown": display_path(USE_CASE_MD),
        "profile_file": display_path(PROFILE_FILE),
        "files": build_file_inventory(),
        "adapters": config.get("adapters", {}),
        "sheet_summary": build_sheet_summary(),
        "use_cases": cases,
        "defaults": config.get("defaults", {}),
        "api": {
            "health": "/api/health",
            "files": "/api/files",
            "adapters": "/api/adapters",
            "scenarios": "/api/scenarios",
            "test_plan": "/api/test-plan",
            "evidence_search": "/api/evidence/search?q=SetCon",
            "run": "/api/run",
            "connection_test": "/api/connection/test",
            "action_transition": "/api/action/transition",
            "backend_contract": "/api/backend/contract",
            "backend_status": "/api/backend/status",
            "backend_read": "/api/backend/read",
        },
    }


def make_spec(item: dict[str, Any], unit_id: int, address_base: str) -> RegisterSpec:
    table = item.get("table", "holding")
    address = int(item["address"])
    count = int(item.get("count", 1))
    function_code = FUNCTION_CODES[table]
    offset = address_to_offset(table, address, address_base)
    name = str(item.get("name") or f"{table}_{address}_{count}")
    try:
        validate_spec(name, function_code, offset, count, unit_id)
    except SystemExit as exc:
        raise ValueError(str(exc)) from exc
    return RegisterSpec(
        name=name,
        table=table,
        address=address,
        offset=offset,
        count=count,
        unit_id=unit_id,
        function_code=function_code,
        data_type=str(item.get("data_type", "raw")),
    )


def parse_custom_read_items(text: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    tokens = [token.strip() for token in re.split(r"[,;\n]+", text) if token.strip()]
    for token in tokens:
        parts = [part.strip() for part in token.split(":") if part.strip()]
        if not parts:
            continue
        table = "holding"
        if parts[0].lower() in FUNCTION_CODES:
            table = parts.pop(0).lower()
        if not parts:
            raise ValueError(f"missing address in custom register entry: {token!r}")
        if len(parts) > 2:
            raise ValueError(f"invalid custom register entry: {token!r}")

        address_text = parts[0]
        if "-" in address_text:
            start_text, end_text = [part.strip() for part in address_text.split("-", 1)]
            address = parse_custom_int(start_text, "address", token)
            end = parse_custom_int(end_text, "range end", token)
            if end < address:
                raise ValueError(f"range end before start in custom register entry: {token!r}")
            count = end - address + 1
        else:
            address = parse_custom_int(address_text, "address", token)
            count = 1
        if len(parts) == 2:
            count = parse_custom_int(parts[1], "count", token)

        items.append(
            {
                "name": f"Custom {table} {address} x{count}",
                "table": table,
                "address": address,
                "count": count,
                "data_type": "raw",
            }
        )
    return items


def parse_custom_int(text: str, label: str, token: str) -> int:
    try:
        return int(text, 0)
    except ValueError as exc:
        raise ValueError(f"custom register {label} must be an integer in entry {token!r}") from exc


class GuiModbusClient(ModbusTcpClient):
    def write_single_register(self, spec: RegisterSpec, value: int) -> None:
        if not self.sock:
            raise ModbusError("client is not connected")
        self.transaction_id = (self.transaction_id + 1) & 0xFFFF
        tid = self.transaction_id
        pdu = struct.pack(">BHH", 6, spec.offset, value & 0xFFFF)
        mbap = struct.pack(">HHHB", tid, 0, len(pdu) + 1, spec.unit_id)
        started = time.perf_counter()
        self.sock.sendall(mbap + pdu)

        header = recv_exact(self.sock, 7)
        rx_tid, protocol_id, length, unit_id = struct.unpack(">HHHB", header)
        body = recv_exact(self.sock, length - 1)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        if rx_tid != tid:
            raise ModbusError(f"transaction mismatch tx={tid} rx={rx_tid}")
        if protocol_id != 0:
            raise ModbusError(f"unexpected protocol id {protocol_id}")
        if unit_id != spec.unit_id:
            raise ModbusError(f"unit mismatch tx={spec.unit_id} rx={unit_id}")
        if not body:
            raise ModbusError("empty write response")
        if body[0] == 0x86:
            exception_code = body[1] if len(body) > 1 else None
            raise ModbusError(f"Modbus exception {exception_code}")
        if body != pdu:
            raise ModbusError("write echo mismatch")
        self.log.event(
            "write_ok",
            label=self.label,
            name=spec.name,
            address=spec.address,
            offset=spec.offset,
            value=value,
            elapsed_ms=elapsed_ms,
        )


class HardwareAdapter:
    name = "base"

    def connect(self) -> None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError

    def read(self, spec: RegisterSpec) -> list[int]:
        raise NotImplementedError

    def write_single_register(self, spec: RegisterSpec, value: int) -> None:
        raise NotImplementedError


class ModbusTcpHardwareAdapter(HardwareAdapter):
    name = "modbus_tcp"

    def __init__(
        self,
        host: str,
        port: int,
        connect_timeout: float,
        request_timeout: float,
        run: RunState,
        label: str,
    ) -> None:
        self.client = GuiModbusClient(host, port, connect_timeout, request_timeout, AppLog(run), label)

    def connect(self) -> None:
        self.client.connect()

    def close(self) -> None:
        self.client.close()

    def read(self, spec: RegisterSpec) -> list[int]:
        return read_with_event_decode(self.client, spec)

    def write_single_register(self, spec: RegisterSpec, value: int) -> None:
        self.client.write_single_register(spec, value)


def backend_base_url(host: str, port: int) -> str:
    text = str(host or "").strip()
    if not text:
        raise ValueError("backend URL or host is required")
    if "://" in text:
        return text.rstrip("/")
    return f"http://{text}:{port}".rstrip("/")


def backend_request_json(method: str, url: str, timeout: float, payload: object | None = None) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise ValueError(f"{method} {url} failed with HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise ValueError(f"{method} {url} failed: {exc.reason}") from exc
    if not raw:
        return {}
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{method} {url} returned non-JSON data") from exc
    if not isinstance(decoded, dict):
        raise ValueError(f"{method} {url} returned JSON that is not an object")
    return decoded


def backend_url(base_url: str, path: str, query: dict[str, object] | None = None) -> str:
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    if query:
        url += "?" + urlencode({key: value for key, value in query.items() if value is not None})
    return url


def backend_item_from_spec(spec: RegisterSpec) -> dict[str, Any]:
    return {
        "name": spec.name,
        "table": spec.table,
        "address": spec.address,
        "offset": spec.offset,
        "count": spec.count,
        "unit_id": spec.unit_id,
        "data_type": spec.data_type,
    }


def values_from_register_rows(rows: list[dict[str, Any]], spec: RegisterSpec) -> list[int]:
    by_address: dict[int, int] = {}
    for row in rows:
        try:
            address = int(row.get("address"))
            value = int(row.get("value"))
        except (TypeError, ValueError):
            continue
        table = str(row.get("table") or spec.table).lower()
        if normalize_table(table) == spec.table:
            by_address[address] = value & 0xFFFF
    values = []
    for index in range(spec.count):
        address = table_address_from_offset(spec.table, spec.offset + index)
        values.append(by_address.get(address, BACKEND_NOT_AVAILABLE))
    return values


def normalize_backend_values(values: list[Any], spec: RegisterSpec) -> list[int]:
    normalized = [int(value) & 0xFFFF for value in values[: spec.count]]
    while len(normalized) < spec.count:
        normalized.append(BACKEND_NOT_AVAILABLE)
    return normalized


def values_from_backend_payload(payload: dict[str, Any], spec: RegisterSpec) -> list[int]:
    if isinstance(payload.get("values"), list):
        return normalize_backend_values(payload["values"], spec)
    items = payload.get("items")
    if isinstance(items, list) and items:
        first = items[0]
        if isinstance(first, dict) and isinstance(first.get("values"), list):
            return normalize_backend_values(first["values"], spec)
    registers = payload.get("registers")
    if isinstance(registers, list):
        return values_from_register_rows([row for row in registers if isinstance(row, dict)], spec)
    raise ValueError("backend read response must contain values, items[0].values, or registers")


class BackendPollingApiAdapter(HardwareAdapter):
    name = "backend_polling_api"

    def __init__(self, base_url: str, request_timeout: float, run: RunState, label: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.request_timeout = request_timeout
        self.run = run
        self.label = label
        self.mode = "v1"

    def connect(self) -> None:
        started = time.perf_counter()
        try:
            payload = backend_request_json("GET", backend_url(self.base_url, "/api/v1/health"), self.request_timeout)
            endpoint = "/api/v1/health"
            self.mode = "v1"
        except Exception as v1_error:
            try:
                payload = backend_request_json("GET", backend_url(self.base_url, "/api/status"), self.request_timeout)
                endpoint = "/api/status"
                self.mode = "plant_model_compat"
            except Exception as compat_error:
                raise ValueError(f"backend API health check failed: v1={v1_error}; compat={compat_error}") from compat_error
        self.run.event(
            "connect_ok",
            label=self.label,
            adapter=self.name,
            backend_url=self.base_url,
            endpoint=endpoint,
            mode=self.mode,
            elapsed_ms=int((time.perf_counter() - started) * 1000),
            backend_ok=payload.get("ok", True),
        )

    def close(self) -> None:
        self.run.event("close", label=self.label, adapter=self.name)

    def read(self, spec: RegisterSpec) -> list[int]:
        started = time.perf_counter()
        if self.mode == "v1":
            payload = backend_request_json(
                "POST",
                backend_url(self.base_url, "/api/v1/registers/read"),
                self.request_timeout,
                {"items": [backend_item_from_spec(spec)], "run_id": self.run.run_id, "label": self.label},
            )
            values = values_from_backend_payload(payload, spec)
        else:
            values = self.read_plant_model_compat(spec)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        self.run.event(
            "read_ok",
            label=self.label,
            adapter=self.name,
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

    def read_plant_model_compat(self, spec: RegisterSpec) -> list[int]:
        values = []
        for index in range(spec.count):
            address = table_address_from_offset(spec.table, spec.offset + index)
            payload = backend_request_json(
                "GET",
                backend_url(self.base_url, "/api/registers", {"q": address, "limit": 10}),
                self.request_timeout,
            )
            registers = payload.get("registers") if isinstance(payload.get("registers"), list) else []
            values.extend(values_from_register_rows([row for row in registers if isinstance(row, dict)], make_spec(
                {
                    "name": f"{spec.name} {address}",
                    "table": spec.table,
                    "address": address,
                    "count": 1,
                    "data_type": spec.data_type,
                },
                spec.unit_id,
                "auto",
            )))
        return values[: spec.count]

    def write_single_register(self, spec: RegisterSpec, value: int) -> None:
        if self.mode != "v1":
            raise ValueError("backend write requires POST /api/v1/registers/write")
        started = time.perf_counter()
        payload = {
            "items": [{**backend_item_from_spec(spec), "value": value & 0xFFFF}],
            "run_id": self.run.run_id,
            "label": self.label,
            "reason": "bms-interface-e2e",
        }
        backend_request_json("POST", backend_url(self.base_url, "/api/v1/registers/write"), self.request_timeout, payload)
        self.run.event(
            "write_ok",
            label=self.label,
            adapter=self.name,
            name=spec.name,
            address=spec.address,
            offset=spec.offset,
            value=value & 0xFFFF,
            elapsed_ms=int((time.perf_counter() - started) * 1000),
        )


def create_hardware_adapter(
    adapter_name: str,
    host: str,
    port: int,
    connect_timeout: float,
    request_timeout: float,
    run: RunState,
    label: str,
) -> HardwareAdapter:
    adapters = load_adapters()
    if adapter_name not in adapters:
        raise ValueError(f"unknown adapter: {adapter_name}")
    if adapter_name == "modbus_tcp":
        return ModbusTcpHardwareAdapter(host, port, connect_timeout, request_timeout, run, label)
    if adapter_name == "backend_polling_api":
        return BackendPollingApiAdapter(backend_base_url(host, port), request_timeout, run, label)
    raise ValueError(f"adapter '{adapter_name}' is a planned integration point; live execution is not implemented")


def read_request_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if not length:
        return {}
    return json.loads(handler.rfile.read(length).decode("utf-8"))


def json_response(handler: BaseHTTPRequestHandler, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
    body = json.dumps(payload, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def text_response(handler: BaseHTTPRequestHandler, body: bytes, content_type: str) -> None:
    handler.send_response(HTTPStatus.OK)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def no_content_response(handler: BaseHTTPRequestHandler) -> None:
    handler.send_response(HTTPStatus.NO_CONTENT)
    handler.send_header("Content-Length", "0")
    handler.end_headers()


def run_scenario(run: RunState, request: dict[str, Any]) -> None:
    scenario_id = run.scenario_id
    profiles = load_profiles()
    cases = {case["id"]: case for case in parse_markdown_table(profiles=profiles)}
    case = cases[scenario_id]
    profile = profiles[scenario_id]
    defaults = load_defaults()
    run.status = "running"
    failures = 0

    adapter_name = str(request.get("adapter") or defaults.get("adapter") or "modbus_tcp")
    host = str(request.get("host") or "").strip()
    port = int(request.get("port") or defaults.get("port") or 502)
    unit_id = int(request.get("unit_id") or defaults.get("unit_id") or 1)
    address_base = str(request.get("address_base") or defaults.get("address_base") or "auto")
    dry_run = bool(request.get("dry_run", True))
    allow_writes = bool(request.get("allow_writes", False))
    connect_timeout = float(request.get("connect_timeout") or defaults.get("connect_timeout") or 3.0)
    request_timeout = float(request.get("request_timeout") or defaults.get("request_timeout") or 2.0)
    write_value = int(request.get("write_value") or defaults.get("write_value") or 1)
    cycles = max(1, int(request.get("cycles") or defaults.get("cycles") or 1))
    interval = max(0.0, float(request.get("interval") or defaults.get("interval") or 0.0))
    read_mode = str(request.get("read_mode") or "profile")

    try:
        run.event(
            "scenario_start",
            title=case["title"],
            kind=profile["kind"],
            adapter=adapter_name,
            dry_run=dry_run,
            allow_writes=allow_writes,
            host=host or None,
            port=port,
            unit_id=unit_id,
        )

        read_items = profile.get("reads", [])
        if scenario_id == "1" and read_mode == "custom":
            custom_registers = str(request.get("custom_registers") or "").strip()
            if not custom_registers:
                raise ValueError("custom register text is required when read mode is custom")
            read_items = parse_custom_read_items(custom_registers)
            run.event("custom_read_plan_selected", custom_registers=custom_registers, items=len(read_items))
        else:
            run.event("profile_read_plan_selected", items=len(read_items))

        reads = [make_spec(item, unit_id, address_base) for item in read_items]
        writes = [
            make_spec({"name": item["name"], "table": "holding", "address": item["address"], "count": 1}, unit_id, address_base)
            for item in profile.get("writes", [])
        ]

        for spec in reads:
            run.event(
                "planned_read",
                name=spec.name,
                address=spec.address,
                offset=spec.offset,
                count=spec.count,
                unit_id=spec.unit_id,
            )
        for index, spec in enumerate(writes):
            default = int(profile["writes"][index].get("default", write_value))
            run.event(
                "planned_write",
                name=spec.name,
                address=spec.address,
                offset=spec.offset,
                default_value=default,
                live_enabled=allow_writes and not dry_run,
            )

        if profile["kind"] == "manual":
            run.event("manual_gate", message="Manual or non-Modbus action requires external procedure/equipment.")

        if dry_run:
            run.event(
                "dry_run_complete",
                planned_reads=len(reads),
                planned_writes=len(writes),
                cycles=cycles,
            )
            run.status = "completed"
            run.exit_code = 0
            return

        if not host:
            raise ValueError("host is required for live execution")

        if profile["kind"] == "connection":
            failures += run_connection_profile(run, request, reads, writes, allow_writes, adapter_name)
        else:
            adapter = create_hardware_adapter(
                adapter_name,
                host,
                port,
                connect_timeout,
                request_timeout,
                run,
                "gui",
            )
            try:
                adapter.connect()
                for cycle in range(cycles):
                    if run.cancel_requested:
                        run.event("cancelled")
                        break
                    run.event("cycle_start", cycle=cycle, reads=len(reads))
                    for spec in reads:
                        adapter.read(spec)
                    if writes and cycle == 0:
                        if not allow_writes:
                            run.event("writes_skipped", reason="allow_writes toggle is off")
                        else:
                            for index, spec in enumerate(writes):
                                value = int(request.get("write_value") or profile["writes"][index].get("default", 1))
                                adapter.write_single_register(spec, value)
                            run.event("post_write_verify_start", reads=len(reads))
                            for spec in reads:
                                adapter.read(spec)
                    run.event("cycle_end", cycle=cycle)
                    if cycle < cycles - 1:
                        time.sleep(interval)
            except Exception as exc:
                failures += 1
                run.event("scenario_error", error=str(exc))
            finally:
                adapter.close()

        run.status = "cancelled" if run.cancel_requested else "completed"
        run.exit_code = 1 if failures else 0
        run.event("scenario_complete", failures=failures)
    except Exception as exc:
        run.status = "failed"
        run.exit_code = 1
        run.event("scenario_failed", error=str(exc))
    finally:
        run.finished_at = time.time()
        write_run_result(run)


def read_with_event_decode(client: GuiModbusClient, spec: RegisterSpec) -> list[int]:
    values = client.read(spec)
    decoded = decode_registers(values, spec)
    client.log.event(
        "read_summary",
        label=client.label,
        name=spec.name,
        address=spec.address,
        count=spec.count,
        sample=values[:8],
        decoded=decoded,
    )
    return values


def run_connection_profile(
    run: RunState,
    request: dict[str, Any],
    reads: list[RegisterSpec],
    writes: list[RegisterSpec],
    allow_writes: bool,
    adapter_name: str,
) -> int:
    defaults = load_defaults()
    host = str(request.get("host") or "").strip()
    port = int(request.get("port") or defaults.get("port") or 502)
    connect_timeout = float(request.get("connect_timeout") or defaults.get("connect_timeout") or 3.0)
    request_timeout = float(request.get("request_timeout") or defaults.get("request_timeout") or 2.0)
    sessions = int(request.get("sessions") or defaults.get("sessions") or 4)
    hold_seconds = float(request.get("hold_seconds") or defaults.get("hold_seconds") or 5.0)
    clients: list[HardwareAdapter] = []
    failures = 0

    for index in range(sessions):
        label = f"session_{index + 1}"
        client = create_hardware_adapter(adapter_name, host, port, connect_timeout, request_timeout, run, label)
        try:
            client.connect()
            clients.append(client)
            if reads:
                client.read(reads[0])
        except Exception as exc:
            failures += 1
            run.event("connection_session_error", label=label, error=str(exc))

    if allow_writes and writes and clients:
        try:
            value = int(request.get("write_value") or defaults.get("write_value") or 1)
            clients[0].write_single_register(writes[0], value)
        except Exception as exc:
            failures += 1
            run.event("heartbeat_write_error", error=str(exc))
    elif writes:
        run.event("writes_skipped", reason="allow_writes toggle is off")

    run.event("connection_hold_start", open_sessions=len(clients), hold_seconds=hold_seconds)
    end = time.time() + hold_seconds
    while time.time() < end and not run.cancel_requested:
        time.sleep(min(0.25, end - time.time()))

    extra = create_hardware_adapter(adapter_name, host, port, connect_timeout, request_timeout, run, "extra_session")
    try:
        extra.connect()
        if reads:
            extra.read(reads[0])
    except Exception as exc:
        failures += 1
        run.event("extra_session_error", error=str(exc))
    finally:
        extra.close()

    for client in clients:
        client.close()
    run.event("connection_profile_complete", failures=failures)
    return failures


def test_connection(payload: dict[str, Any]) -> dict[str, Any]:
    defaults = load_defaults()
    adapter_name = str(payload.get("adapter") or defaults.get("adapter") or "modbus_tcp")
    host_value = payload.get("backend_url") if adapter_name == "backend_polling_api" else payload.get("host")
    host = str(host_value or payload.get("host") or "").strip()
    port = int(payload.get("port") or defaults.get("port") or 502)
    connect_timeout = float(payload.get("connect_timeout") or defaults.get("connect_timeout") or 3.0)
    dry_run = bool(payload.get("dry_run", False))

    if adapter_name not in load_adapters():
        raise ValueError(f"unknown adapter: {adapter_name}")
    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "adapter": adapter_name,
            "host": host or None,
            "port": port,
        }
    if not host:
        raise ValueError("host is required for connection test")
    if adapter_name == "backend_polling_api":
        base_url = backend_base_url(host, port)
        started = time.perf_counter()
        try:
            backend_payload = backend_request_json("GET", backend_url(base_url, "/api/v1/health"), connect_timeout)
            endpoint = "/api/v1/health"
            mode = "v1"
        except Exception:
            backend_payload = backend_request_json("GET", backend_url(base_url, "/api/status"), connect_timeout)
            endpoint = "/api/status"
            mode = "plant_model_compat"
        return {
            "ok": True,
            "dry_run": False,
            "adapter": adapter_name,
            "backend_url": base_url,
            "endpoint": endpoint,
            "mode": mode,
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "backend_ok": backend_payload.get("ok", True),
        }
    if adapter_name != "modbus_tcp":
        raise ValueError(f"adapter '{adapter_name}' is a planned integration point; connection test is not implemented")

    started = time.perf_counter()
    sock = socket.create_connection((host, port), timeout=connect_timeout)
    try:
        local = sock.getsockname()
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            "ok": True,
            "dry_run": False,
            "adapter": adapter_name,
            "host": host,
            "port": port,
            "local": f"{local[0]}:{local[1]}",
            "elapsed_ms": elapsed_ms,
        }
    finally:
        sock.close()


class BackendProbeRun:
    def __init__(self) -> None:
        self.run_id = f"probe-{uuid.uuid4().hex[:8]}"
        self.events: list[dict[str, Any]] = []

    def event(self, event: str, **fields: object) -> None:
        self.events.append({"ts": round(time.time(), 3), "event": event, **fields})


def backend_read_probe(payload: dict[str, Any]) -> dict[str, Any]:
    defaults = load_defaults()
    host = str(payload.get("backend_url") or payload.get("host") or "").strip()
    port = int(payload.get("port") or defaults.get("port") or 502)
    unit_id = int(payload.get("unit_id") or defaults.get("unit_id") or 1)
    address_base = str(payload.get("address_base") or defaults.get("address_base") or "auto")
    request_timeout = float(payload.get("request_timeout") or defaults.get("request_timeout") or 2.0)
    raw_items = payload.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise ValueError("items must be a non-empty list of register read requests")

    run = BackendProbeRun()
    adapter = BackendPollingApiAdapter(backend_base_url(host, port), request_timeout, run, "api_probe")
    adapter.connect()
    results = []
    try:
        for item in raw_items:
            if not isinstance(item, dict):
                raise ValueError("each read item must be an object")
            spec = make_spec(item, unit_id, address_base)
            values = adapter.read(spec)
            results.append({**backend_item_from_spec(spec), "values": values, "decoded": decode_registers(values, spec)})
    finally:
        adapter.close()
    return {
        "ok": True,
        "backend_url": adapter.base_url,
        "mode": adapter.mode,
        "items": results,
        "events": run.events,
    }


def transition_action(payload: dict[str, Any]) -> tuple[dict[str, Any], HTTPStatus]:
    scenario_id = str(payload.get("scenario_id") or "")
    action_id = str(payload.get("action_id") or "")
    profiles = load_profiles()
    cases = {case["id"]: case for case in parse_markdown_table(profiles=profiles)}
    if scenario_id not in cases:
        return {"error": "unknown scenario"}, HTTPStatus.BAD_REQUEST

    flow = cases[scenario_id].get("action_flow", {})
    state = str(payload.get("state") or flow.get("initial_state") or "ready")
    actions = flow.get("actions", [])
    action = next((item for item in actions if item["id"] == action_id), None)
    if not action:
        return {"error": "unknown action"}, HTTPStatus.BAD_REQUEST
    if action["from_state"] != state:
        return {
            "error": "transition not available",
            "state": state,
            "expected_state": action["from_state"],
            "action": action,
        }, HTTPStatus.CONFLICT

    next_state = action["to_state"]
    available = [item for item in actions if item["from_state"] == next_state]
    return {
        "ok": True,
        "scenario_id": scenario_id,
        "previous_state": state,
        "state": next_state,
        "action": action,
        "available_actions": available,
        "complete": next_state == flow.get("terminal_state"),
    }, HTTPStatus.OK


class Handler(BaseHTTPRequestHandler):
    server_version = "BmsInterfaceGUI/0.2"

    def log_message(self, format: str, *args: object) -> None:
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), format % args))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/":
                return self.serve_static("index.html", "text/html; charset=utf-8")
            if path == "/favicon.ico":
                return no_content_response(self)
            if path == "/app.js":
                return self.serve_static("app.js", "application/javascript; charset=utf-8")
            if path == "/styles.css":
                return self.serve_static("styles.css", "text/css; charset=utf-8")
            if path == "/api/health":
                return json_response(
                    self,
                    {
                        "ok": True,
                        "version": self.server_version,
                        "uptime_seconds": round(time.time() - STARTED_AT, 3),
                        "profile_file": display_path(PROFILE_FILE),
                    },
                )
            if path == "/api/files":
                return json_response(self, build_file_inventory())
            if path == "/api/adapters":
                return json_response(
                    self,
                    {"default": load_defaults().get("adapter"), "adapters": load_adapters()},
                )
            if path == "/api/scenarios":
                model = build_model()
                return json_response(
                    self,
                    {
                        "profile_file": model["profile_file"],
                        "defaults": model["defaults"],
                        "use_cases": model["use_cases"],
                    },
                )
            if path == "/api/test-plan":
                return json_response(self, build_model())
            if path == "/api/evidence/search":
                query = parse_qs(parsed.query).get("q", [""])[0]
                limit_text = parse_qs(parsed.query).get("limit", ["25"])[0]
                limit = int(limit_text or "25")
                return json_response(self, {"query": query, "results": search_evidence(query, limit)})
            if path == "/api/model":
                return json_response(self, build_model())
            if path == "/api/backend/contract":
                return json_response(self, backend_api_contract())
            if path.startswith("/api/run/"):
                run_id = path.rsplit("/", 1)[-1]
                with RUNS_LOCK:
                    run = RUNS.get(run_id)
                if not run:
                    return json_response(self, {"error": "run not found"}, HTTPStatus.NOT_FOUND)
                return json_response(self, run.snapshot())
            if path == "/api/runs":
                with RUNS_LOCK:
                    runs = [run.snapshot() for run in RUNS.values()]
                runs.sort(key=lambda item: item["started_at"], reverse=True)
                return json_response(self, {"runs": runs[:25]})
            return json_response(self, {"error": "not found"}, HTTPStatus.NOT_FOUND)
        except Exception as exc:
            return json_response(self, {"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/run":
                payload = read_request_json(self)
                scenario_id = str(payload.get("scenario_id") or "")
                profiles = load_profiles()
                cases = {case["id"]: case for case in parse_markdown_table(profiles=profiles)}
                if scenario_id not in cases or scenario_id not in profiles:
                    return json_response(self, {"error": "unknown scenario"}, HTTPStatus.BAD_REQUEST)
                run_id = uuid.uuid4().hex[:12]
                run = RunState(
                    run_id=run_id,
                    scenario_id=scenario_id,
                    title=cases[scenario_id]["title"],
                    jsonl_path=make_run_jsonl_path(scenario_id, run_id),
                )
                write_run_request(run, payload)
                with RUNS_LOCK:
                    RUNS[run_id] = run
                thread = threading.Thread(target=run_scenario, args=(run, payload), daemon=True)
                thread.start()
                return json_response(self, {"run_id": run_id, "run": run.snapshot()}, HTTPStatus.ACCEPTED)
            if parsed.path == "/api/connection/test":
                payload = read_request_json(self)
                return json_response(self, test_connection(payload))
            if parsed.path == "/api/action/transition":
                payload = read_request_json(self)
                result, status = transition_action(payload)
                return json_response(self, result, status)
            if parsed.path == "/api/backend/status":
                payload = read_request_json(self)
                payload["adapter"] = "backend_polling_api"
                payload["dry_run"] = False
                return json_response(self, test_connection(payload))
            if parsed.path == "/api/backend/read":
                payload = read_request_json(self)
                return json_response(self, backend_read_probe(payload))
            if parsed.path.startswith("/api/run/") and parsed.path.endswith("/cancel"):
                parts = parsed.path.strip("/").split("/")
                run_id = parts[2]
                with RUNS_LOCK:
                    run = RUNS.get(run_id)
                if not run:
                    return json_response(self, {"error": "run not found"}, HTTPStatus.NOT_FOUND)
                run.cancel_requested = True
                run.event("cancel_requested")
                return json_response(self, run.snapshot())
            return json_response(self, {"error": "not found"}, HTTPStatus.NOT_FOUND)
        except Exception as exc:
            return json_response(self, {"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def serve_static(self, name: str, content_type: str) -> None:
        path = STATIC_DIR / name
        if not path.exists():
            json_response(self, {"error": f"static file missing: {name}"}, HTTPStatus.NOT_FOUND)
            return
        text_response(self, path.read_bytes(), content_type)


def self_test() -> int:
    config = load_profile_config()
    model = build_model()
    if len(model["use_cases"]) != 13:
        raise SystemExit(f"expected 13 use cases, got {len(model['use_cases'])}")
    if len(config["profiles"]) != 13:
        raise SystemExit(f"expected 13 profiles, got {len(config['profiles'])}")
    if "modbus_tcp" not in model["adapters"]:
        raise SystemExit("profile file must define modbus_tcp adapter")
    if "backend_polling_api" not in model["adapters"]:
        raise SystemExit("profile file must define backend_polling_api adapter")
    contract = backend_api_contract()
    if contract["required_endpoints"]["read_registers"]["path"] != "/api/v1/registers/read":
        raise SystemExit("backend API contract is missing the v1 read endpoint")
    case_1 = next(case for case in model["use_cases"] if case["id"] == "1")
    if len(case_1.get("reads", [])) <= 5:
        raise SystemExit("use case 1 must expand to all available register ranges")
    if any(int(item.get("count", 1)) > MAX_REGISTERS_PER_READ for item in case_1.get("reads", [])):
        raise SystemExit("use case 1 contains an oversized Modbus read range")
    custom_reads = [make_spec(item, 1, "auto") for item in parse_custom_read_items("40071:2, input:30001:4")]
    if len(custom_reads) != 2:
        raise SystemExit("custom register parser did not create expected reads")
    try:
        parse_custom_read_items("not-a-register")
    except ValueError as exc:
        if "custom register address must be an integer" not in str(exc):
            raise SystemExit(f"custom register parser returned unclear error: {exc}") from exc
    else:
        raise SystemExit("custom register parser accepted invalid input")
    values = values_from_backend_payload({"items": [{"values": [1, 2]}]}, custom_reads[0])
    if values != [1, 2]:
        raise SystemExit("backend register read response parser failed")
    action_count = 0
    for case in model["use_cases"]:
        actions = case.get("action_flow", {}).get("actions", [])
        action_count += len(actions)
        if not actions:
            raise SystemExit(f"expected at least one action for use case {case['id']}")
        for item in case.get("reads", []):
            make_spec(item, 1, "auto")
        for item in case.get("writes", []):
            make_spec({"name": item["name"], "table": "holding", "address": item["address"], "count": 1}, 1, "auto")
    print(
        json.dumps(
            {
                "use_cases": len(model["use_cases"]),
                "profiles": len(config["profiles"]),
                "adapters": sorted(model["adapters"].keys()),
                "actions": action_count,
                "sheets": len(model["sheet_summary"]),
            },
            indent=2,
        )
    )
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BMS interface E2E GUI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        return self_test()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"BMS interface GUI running at http://{args.host}:{args.port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
