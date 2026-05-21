#!/usr/bin/env python3
"""BMS plant model with Modbus/TCP and browser import GUI."""

from __future__ import annotations

import argparse
import csv
import html
import io
import json
import re
import socket
import struct
import sys
import threading
import time
import zipfile
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse
from xml.etree import ElementTree

try:
    from modbus_client_sim import FUNCTION_CODES, address_to_offset, normalize_table
except ModuleNotFoundError:
    from .modbus_client_sim import FUNCTION_CODES, address_to_offset, normalize_table


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "plant_gui"
DATA_DIR = ROOT / "data"
PROFILE_FILE = DATA_DIR / "interface_profiles.json"
USE_CASE_MD = DATA_DIR / "use_cases.md"

TABLE_BY_FUNCTION = {
    1: "coil",
    2: "discrete",
    3: "holding",
    4: "input",
}
NOT_AVAILABLE_REGISTER = 0xFFFF
OCR_LINE_HEADERS = {"source_image", "ocr_input", "line_index", "x", "y", "width", "height", "text"}


@dataclass
class PlantRegister:
    table: str
    address: int
    offset: int
    value: int
    name: str = ""
    unit_id: int = 1
    data_type: str = "uint16"
    source: str = "generated"
    writable: bool = False
    available: bool = True
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "table": self.table,
            "address": self.address,
            "offset": self.offset,
            "value": self.value,
            "name": self.name,
            "unit_id": self.unit_id,
            "data_type": self.data_type,
            "source": self.source,
            "writable": self.writable,
            "available": self.available,
            "notes": self.notes,
        }


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def clean_text(value: object) -> str:
    return str(value or "").strip()


def parse_int(value: object, default: int | None = None) -> int:
    text = clean_text(value)
    if not text:
        if default is None:
            raise ValueError("missing integer value")
        return default
    if re.fullmatch(r"-?\d+\.0+", text):
        text = text.split(".", 1)[0]
    return int(text.replace("_", ""), 0)


def parse_register_value(value: object, default: int = 0) -> int:
    text = clean_text(value).lower()
    if text in ("n/a", "na", "not available", "not applicable", "not_available"):
        return NOT_AVAILABLE_REGISTER
    return parse_int(value, default)


def parse_bool(value: object, default: bool = False) -> bool:
    text = clean_text(value).lower()
    if not text:
        return default
    return text not in ("0", "false", "no", "n", "off")


def parse_available(row: dict[str, Any]) -> bool:
    applicable = first_value(row, "available", "applicable")
    if applicable is not None:
        return parse_bool(applicable, True)
    not_applicable = first_value(row, "not_applicable", "not_available", "na")
    if not_applicable is not None:
        return not parse_bool(not_applicable, False)
    explicit_value = first_value(row, "value", "default", "initial", "initial_value")
    return clean_text(explicit_value).lower() not in (
        "n/a",
        "na",
        "not available",
        "not applicable",
        "not_available",
    )


def normalize_header(value: object) -> str:
    text = clean_text(value).lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def first_value(row: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in row and clean_text(row[name]):
            return row[name]
    return None


def infer_table(row: dict[str, Any]) -> str:
    table = first_value(row, "table", "register_table", "modbus_table")
    if table:
        return normalize_table(str(table))
    function = first_value(row, "function", "function_code", "fc")
    if function:
        function_code = parse_int(function)
        if function_code in TABLE_BY_FUNCTION:
            return TABLE_BY_FUNCTION[function_code]
    address = parse_int(first_value(row, "address", "register", "modbus_address", "addr"))
    if 10001 <= address <= 19999:
        return "discrete"
    if 30001 <= address <= 39999:
        return "input"
    return "holding"


def import_address_value(row: dict[str, Any]) -> Any:
    return first_value(
        row,
        "address",
        "register",
        "modbus_address",
        "modbus",
        "g_modbus",
        "addr",
    )


def import_data_type(row: dict[str, Any]) -> str:
    return clean_text(
        first_value(
            row,
            "reviewed_data_type",
            "data_type",
            "datatype",
            "type",
            "type_hint",
        )
    )


def import_name(row: dict[str, Any]) -> str:
    return clean_text(
        first_value(
            row,
            "reviewed_name",
            "name",
            "symbol",
            "field",
            "signal",
            "label",
            "reviewed_label",
            "description",
            "reviewed_description",
        )
    )


def import_count(row: dict[str, Any]) -> int:
    count_value = first_value(row, "count", "words", "length")
    if count_value is not None:
        try:
            return max(1, parse_int(count_value, 1))
        except ValueError:
            pass
    data_type = import_data_type(row).lower()
    size_value = first_value(row, "reviewed_size", "size")
    if data_type == "string" and size_value is not None:
        try:
            return max(1, parse_int(size_value, 1))
        except ValueError:
            return 1
    if data_type in ("uint32", "int32", "acc32", "float32"):
        return 2
    if data_type in ("uint64", "int64", "acc64", "float64"):
        return 4
    if size_value is not None:
        try:
            return max(1, parse_int(size_value, 1))
        except ValueError:
            return 1
    return 1


def import_explicit_value(row: dict[str, Any]) -> Any:
    value = first_value(row, "reviewed_value", "value", "default", "initial", "initial_value", "default_value")
    if value is None:
        return None
    text = clean_text(value)
    if re.fullmatch(r"-?\d+(?:\.0+)?", text):
        return text
    if text.lower() in ("n/a", "na", "not available", "not applicable", "not_available"):
        return text
    return None


def import_writable(row: dict[str, Any]) -> bool:
    access = clean_text(first_value(row, "reviewed_rw_access", "rw_access", "access", "rw")).lower()
    if access:
        return "w" in access or "write" in access
    return parse_bool(first_value(row, "writable", "write", "enabled"), False)


def canonical_import_row(row: dict[str, Any]) -> dict[str, Any]:
    canonical = dict(row)
    canonical["address"] = import_address_value(row)
    canonical["count"] = str(import_count(row))
    canonical["name"] = import_name(row)
    canonical["data_type"] = import_data_type(row) or "uint16"
    canonical["writable"] = "true" if import_writable(row) else "false"
    value = import_explicit_value(row)
    if value is not None:
        canonical["value"] = value
    else:
        canonical.pop("value", None)
    notes = clean_text(first_value(row, "notes", "comment"))
    description = clean_text(first_value(row, "reviewed_description", "description"))
    confidence = clean_text(first_value(row, "review_confidence"))
    note_parts = [part for part in (notes, description, f"review_confidence={confidence}" if confidence else "") if part]
    if note_parts:
        canonical["notes"] = "; ".join(note_parts)
    return canonical


def stable_seed(address: int, index: int, name: str = "") -> int:
    lower = name.lower()
    if "soc" in lower:
        return 72
    if "soh" in lower:
        return 96
    if "cellv" in lower or "cell_v" in lower:
        return 3600 + (index % 18) * 3
    if "celltmp" in lower or "cell_tmp" in lower:
        return 250 + (index % 8)
    if "isomon" in lower:
        return 1 if "status" in lower else 50000
    return (address * 17 + index * 29) & 0xFFFF


def table_address_from_offset(table: str, offset: int) -> int:
    if table == "coil":
        return offset + 1
    if table == "discrete":
        return offset + 10001
    if table == "input":
        return offset + 30001
    return offset + 40001


def parse_use_case_markdown(path: Path = USE_CASE_MD) -> list[dict[str, str]]:
    if not path.exists():
        return []
    cases: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        parts = [part.strip() for part in line.strip().strip("|").split("|")]
        if len(parts) < 5 or not parts[0].isdigit():
            continue
        scenario = parts[1].replace("**", "").replace("`", "")
        title, _, detail = scenario.partition(" - ")
        cases.append(
            {
                "id": parts[0],
                "title": title,
                "detail": detail or scenario,
                "available_test": parts[2],
                "status": parts[3],
            }
        )
    return cases


class PlantModel:
    def __init__(self, profile_file: Path = PROFILE_FILE) -> None:
        self.profile_file = profile_file
        self.lock = threading.RLock()
        self.registers: dict[tuple[str, int], PlantRegister] = {}
        self.events: list[dict[str, Any]] = []
        self.imports: list[dict[str, Any]] = []
        self.device_address = 1
        self.state = {
            "preset": "nominal",
            "contactors_closed": False,
            "isolation_enabled": True,
            "power_saving": False,
            "sw_flashing": False,
            "fault_level": 0,
            "heartbeat_seen_at": 0.0,
            "started_at": time.time(),
        }
        self.reset_defaults()

    def reset_defaults(self) -> None:
        with self.lock:
            self.registers.clear()
            self.imports.clear()
            self.device_address = 1
            self.state.update(
                {
                    "preset": "nominal",
                    "contactors_closed": False,
                    "isolation_enabled": True,
                    "power_saving": False,
                    "sw_flashing": False,
                    "fault_level": 0,
                    "heartbeat_seen_at": 0.0,
                }
            )
            self._load_profile_registers()
            self._seed_behavior_registers()
            self._apply_state_registers()
            self.event("model_reset", registers=len(self.registers))

    def _load_profile_registers(self) -> None:
        config = load_json(self.profile_file)
        profiles = config.get("profiles", {})
        for scenario_id, profile in profiles.items():
            for item in profile.get("reads", []):
                self.add_range(item, source=f"use_case_{scenario_id}:read", writable=False)
            for item in profile.get("writes", []):
                row = {
                    "name": item.get("name"),
                    "table": item.get("table", "holding"),
                    "address": item.get("address"),
                    "count": 1,
                    "value": item.get("default", 0),
                    "data_type": "uint16",
                    "writable": True,
                }
                self.add_range(row, source=f"use_case_{scenario_id}:write", writable=True)

    def _seed_behavior_registers(self) -> None:
        anchors = [
            ("holding", 40002, 1, "SunSpec common model ID"),
            ("holding", 40003, 66, "SunSpec common model length"),
            ("holding", 40068, self.device_address, "DA"),
            ("holding", 40088, 0, "Controller heartbeat status"),
            ("holding", 40089, 0, "CtrlHb"),
            ("holding", 40090, 0, "AlmRst"),
            ("holding", 40097, 0, "M802 Evt1"),
            ("holding", 40157, 804, "M804 model ID"),
            ("holding", 40169, 0, "M804 Evt1"),
            ("holding", 40170, 0, "SetEna"),
            ("holding", 40171, 0, "SetCon"),
            ("holding", 40173, 0, "ConSt"),
            ("holding", 40176, 0, "ConFail"),
            ("holding", 42282, 64093, "M64093 custom model ID"),
            ("holding", 42288, 0, "EnterPowerSaving"),
            ("holding", 42289, 0, "PowerSavingStatus"),
            ("holding", 42292, 1, "IsoMonEnable"),
            ("holding", 42293, 1, "IsoMonStatus"),
            ("holding", 42294, 50000, "IsoMonResMea"),
            ("holding", 42330, 0, "SwFlashActive"),
            ("holding", 42356, 0, "CusEvt1"),
        ]
        writable = {"DA", "CtrlHb", "AlmRst", "SetEna", "SetCon", "EnterPowerSaving", "IsoMonEnable"}
        for table, address, value, name in anchors:
            self.upsert_register(
                table=table,
                address=address,
                value=value,
                name=name,
                unit_id=1,
                source="plant_behavior",
                writable=name in writable,
            )

    def add_range(self, item: dict[str, Any], source: str, writable: bool | None = None) -> int:
        table = infer_table(item)
        address = parse_int(import_address_value(item))
        count = import_count(item)
        address_base = clean_text(first_value(item, "address_base", "base")) or "auto"
        unit_id = parse_int(first_value(item, "unit_id", "unit"), self.device_address)
        name = import_name(item)
        data_type = import_data_type(item) or "uint16"
        notes = clean_text(first_value(item, "notes", "comment", "description", "reviewed_description"))
        row_writable = import_writable(item)
        row_available = parse_available(item)
        if writable is None:
            writable = row_writable
        explicit_value = import_explicit_value(item)
        offset = address_to_offset(table, address, address_base)
        for index in range(count):
            value = (
                parse_register_value(explicit_value, 0)
                if explicit_value is not None and count == 1
                else stable_seed(address + index, index, name)
            )
            if not row_available:
                value = NOT_AVAILABLE_REGISTER
            self.registers[(table, offset + index)] = PlantRegister(
                table=table,
                address=address + index,
                offset=offset + index,
                value=value & 0xFFFF,
                name=name if count == 1 else f"{name}[{index}]" if name else "",
                unit_id=unit_id,
                data_type=data_type,
                source=source,
                writable=bool(writable),
                available=row_available,
                notes=notes,
            )
        return count

    def upsert_register(
        self,
        table: str,
        address: int,
        value: int,
        name: str = "",
        unit_id: int = 1,
        source: str = "plant_behavior",
        writable: bool = False,
        available: bool = True,
        notes: str = "",
    ) -> None:
        table = normalize_table(table)
        offset = address_to_offset(table, address, "auto")
        existing = self.registers.get((table, offset))
        self.registers[(table, offset)] = PlantRegister(
            table=table,
            address=address,
            offset=offset,
            value=value & 0xFFFF,
            name=name or (existing.name if existing else ""),
            unit_id=unit_id,
            data_type=existing.data_type if existing else "uint16",
            source=source,
            writable=writable or (existing.writable if existing else False),
            available=available if existing is None else existing.available and available,
            notes=notes or (existing.notes if existing else ""),
        )

    def event(self, event: str, **fields: Any) -> None:
        payload = {"ts": round(time.time(), 3), "event": event, **fields}
        self.events.append(payload)
        del self.events[:-300]

    def read(self, table: str, offset: int, count: int, unit_id: int) -> list[int]:
        with self.lock:
            self.tick()
            values = []
            not_available = 0
            for index in range(count):
                register = self.registers.get((table, offset + index))
                if not register or not register.available:
                    values.append(NOT_AVAILABLE_REGISTER)
                    not_available += 1
                else:
                    values.append(register.value)
            self.event("read", table=table, offset=offset, count=count, unit_id=unit_id, not_available=not_available)
            return values

    def read_bits(self, table: str, offset: int, count: int, unit_id: int) -> list[int]:
        with self.lock:
            self.tick()
            values = []
            not_available = 0
            for index in range(count):
                register = self.registers.get((table, offset + index))
                if not register or not register.available:
                    values.append(0)
                    not_available += 1
                else:
                    values.append(1 if register.value else 0)
            self.event("read_bits", table=table, offset=offset, count=count, unit_id=unit_id, not_available=not_available)
            return values

    def write_register(self, offset: int, value: int, unit_id: int) -> None:
        with self.lock:
            address = table_address_from_offset("holding", offset)
            register = self.registers.get(("holding", offset))
            name = register.name if register else ""
            if not register:
                self.registers[("holding", offset)] = PlantRegister(
                    table="holding",
                    address=address,
                    offset=offset,
                    value=value & 0xFFFF,
                    name=f"holding_{address}",
                    unit_id=unit_id,
                    source="modbus_write",
                    writable=True,
                    available=True,
                )
            else:
                register.value = value & 0xFFFF
                register.writable = True
            self._apply_write_effects(address, value & 0xFFFF)
            self.event(
                "write_single",
                address=address,
                offset=offset,
                value=value & 0xFFFF,
                unit_id=unit_id,
                name=name,
            )

    def write_many(self, offset: int, values: list[int], unit_id: int) -> None:
        for index, value in enumerate(values):
            self.write_register(offset + index, value, unit_id)

    def _apply_write_effects(self, address: int, value: int) -> None:
        if address == 40068:
            self.device_address = max(1, min(value, 247))
            self.upsert_register("holding", 40068, self.device_address, "DA", writable=True)
        elif address == 40089:
            self.state["heartbeat_seen_at"] = time.time()
            self.upsert_register("holding", 40088, 1, "Controller heartbeat status")
        elif address == 40090 and value:
            self.state["fault_level"] = 0
            for event_address in (40097, 40098, 40169, 40176, 42356, 42357, 42358):
                self.upsert_register("holding", event_address, 0, source="plant_behavior")
        elif address in (40170, 40171):
            self._update_contactors()
        elif address == 42288:
            self.state["power_saving"] = bool(value)
            self._apply_state_registers()
        elif address == 42292:
            self.state["isolation_enabled"] = bool(value)
            self._apply_state_registers()

    def _update_contactors(self) -> None:
        enabled = self.value_at("holding", 40170) != 0
        requested = self.value_at("holding", 40171) != 0
        if requested and enabled and self.state["sw_flashing"]:
            self.state["contactors_closed"] = False
            self.state["fault_level"] = max(int(self.state["fault_level"]), 2)
            self.upsert_register("holding", 40173, 0, "ConSt")
            self.upsert_register("holding", 40176, 1, "ConFail")
            self.upsert_register("holding", 42356, 1, "CusEvt1")
            self.event("contactor_blocked", reason="sw_flashing")
        else:
            self.state["contactors_closed"] = bool(enabled and requested)
            self.upsert_register("holding", 40173, 1 if self.state["contactors_closed"] else 0, "ConSt")
            self.upsert_register("holding", 40176, 0, "ConFail")

    def _apply_state_registers(self) -> None:
        self.upsert_register("holding", 42289, 1 if self.state["power_saving"] else 0, "PowerSavingStatus")
        self.upsert_register("holding", 42293, 1 if self.state["isolation_enabled"] else 0, "IsoMonStatus")
        self.upsert_register("holding", 42294, 50000 if self.state["isolation_enabled"] else 0, "IsoMonResMea")
        self.upsert_register("holding", 42330, 1 if self.state["sw_flashing"] else 0, "SwFlashActive")
        if self.state["fault_level"]:
            self.upsert_register("holding", 40097, int(self.state["fault_level"]), "M802 Evt1")
            self.upsert_register("holding", 42356, int(self.state["fault_level"]), "CusEvt1")
        else:
            for event_address in (40097, 40098, 40169, 40176, 42356, 42357, 42358):
                self.upsert_register("holding", event_address, 0, source="plant_behavior")
        if self.state["preset"] == "thermal_limit":
            self._set_repeated_range(
                40339,
                120,
                lambda index: 0 if index % 3 == 2 else stable_seed(40339 + index, index, "CellTmp"),
            )

    def _set_repeated_range(self, start_address: int, count: int, value_fn: Any) -> None:
        for index in range(count):
            address = start_address + index
            offset = address_to_offset("holding", address, "auto")
            register = self.registers.get(("holding", offset))
            if register:
                register.value = int(value_fn(index)) & 0xFFFF

    def value_at(self, table: str, address: int) -> int:
        offset = address_to_offset(table, address, "auto")
        register = self.registers.get((table, offset))
        return register.value if register else 0

    def set_preset(self, preset: str) -> None:
        with self.lock:
            presets = {"nominal", "fault_l2", "fault_l3", "sw_flashing", "power_saving", "thermal_limit"}
            if preset not in presets:
                raise ValueError(f"unknown preset: {preset}")
            self.state["preset"] = preset
            self.state["sw_flashing"] = preset == "sw_flashing"
            self.state["power_saving"] = preset == "power_saving"
            self.state["fault_level"] = 2 if preset == "fault_l2" else 3 if preset == "fault_l3" else 0
            if preset == "thermal_limit":
                self.state["contactors_closed"] = False
            self._apply_state_registers()
            self._update_contactors()
            self.event("preset_applied", preset=preset)

    def tick(self) -> None:
        now = time.time()
        if self.state["heartbeat_seen_at"] and now - float(self.state["heartbeat_seen_at"]) > 8:
            self.upsert_register("holding", 40088, 0, "Controller heartbeat status")
        if not self.state["power_saving"]:
            uptime = int(now - float(self.state["started_at"]))
            self.upsert_register("holding", 40071, 70 + (uptime % 5), "SoC")
            self.upsert_register("holding", 40072, 96, "SoH")
            self.upsert_register("holding", 40073, 5000 if self.state["contactors_closed"] else 0, "WChaRteMax")
        self._apply_state_registers()

    def import_rows(self, rows: list[dict[str, Any]], filename: str, workbook_sheet: str = "") -> dict[str, Any]:
        imported = 0
        skipped = 0
        errors: list[str] = []
        source_name = f"{filename}#{workbook_sheet}" if workbook_sheet else filename
        if rows and any(
            clean_text({normalize_header(key): value for key, value in row.items()}.get("review_status")).lower()
            == "ocr_unreviewed"
            for row in rows
        ):
            raise ValueError(
                "Reconstructed OCR table is still marked ocr_unreviewed. Review/correct the sheet first, "
                "then change review_status before importing it into the plant model."
            )
        with self.lock:
            for row_index, row in enumerate(rows, start=2):
                normalized = {normalize_header(key): value for key, value in row.items()}
                canonical = canonical_import_row(normalized)
                if not import_address_value(canonical):
                    skipped += 1
                    continue
                try:
                    imported += self.add_range(canonical, source=f"import:{source_name}", writable=None)
                except Exception as exc:
                    skipped += 1
                    if len(errors) < 8:
                        errors.append(f"row {row_index}: {exc}")
            summary = {
                "filename": filename,
                "workbook_sheet": workbook_sheet,
                "imported_registers": imported,
                "skipped_rows": skipped,
                "errors": errors,
                "loaded_at": round(time.time(), 3),
            }
            self.imports.append(summary)
            del self.imports[:-20]
            self.event("file_imported", **summary)
            return summary

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            self.tick()
            tables: dict[str, int] = {}
            for table, _offset in self.registers:
                tables[table] = tables.get(table, 0) + 1
            return {
                "registers": len(self.registers),
                "not_available_register": NOT_AVAILABLE_REGISTER,
                "tables": tables,
                "device_address": self.device_address,
                "state": dict(self.state),
                "profile_file": "data/interface_profiles.json",
                "use_case_file": "data/use_cases.md",
                "imports": list(self.imports),
                "events": list(self.events[-100:]),
                "use_cases": parse_use_case_markdown(),
            }

    def register_rows(self, limit: int = 300, query: str = "") -> list[dict[str, Any]]:
        with self.lock:
            query_l = query.lower().strip()
            rows = sorted(
                (register.as_dict() for register in self.registers.values()),
                key=lambda item: (item["table"], item["address"], item["name"]),
            )
            if query_l:
                rows = [row for row in rows if query_l in json.dumps(row, sort_keys=True).lower()]
            return rows[: max(1, min(limit, 2000))]


def parse_csv_rows(content: bytes) -> list[dict[str, Any]]:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = content.decode("utf-8", errors="replace")
    sample = text[:4096]
    first_line = sample.splitlines()[0] if sample.splitlines() else ""
    if first_line.count(",") >= 1 and first_line.count(",") >= first_line.count("\t"):
        dialect = csv.excel
    elif first_line.count("\t") >= 1:
        dialect = csv.excel_tab
    else:
        try:
            dialect = csv.Sniffer().sniff(sample)
        except csv.Error:
            dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    rows = [dict(row) for row in reader]
    if looks_like_ocr_line_rows(rows):
        raise ValueError(
            "OCR evidence CSV cannot be loaded as the plant-model register database. "
            "Use a structured CSV/XLSX with columns such as name, table, address, count, value, data_type, and writable."
        )
    return rows


def looks_like_ocr_line_rows(rows: list[dict[str, Any]]) -> bool:
    if not rows:
        return False
    headers = {normalize_header(header) for header in rows[0].keys()}
    return OCR_LINE_HEADERS.issubset(headers)


def parse_xlsx_rows(content: bytes, sheet_name: str = "") -> list[dict[str, Any]]:
    matrix = xlsx_sheet_matrix(content, sheet_name=sheet_name)
    while matrix and not any(clean_text(value) for value in matrix[0]):
        matrix.pop(0)
    if not matrix:
        return []
    headers = [normalize_header(value) or f"column_{index + 1}" for index, value in enumerate(matrix[0])]
    rows = []
    for cells in matrix[1:]:
        if not any(clean_text(value) for value in cells):
            continue
        row = {}
        for index, header in enumerate(headers):
            row[header] = cells[index] if index < len(cells) else ""
        rows.append(row)
    return rows


def xlsx_sheet_entries(content: bytes) -> list[dict[str, Any]]:
    namespaces = {
        "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        "pkgrel": "http://schemas.openxmlformats.org/package/2006/relationships",
    }
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        rels = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    relation_targets = {
        rel.attrib.get("Id"): xlsx_target_path(rel.attrib.get("Target", ""))
        for rel in rels.findall("pkgrel:Relationship", namespaces)
    }
    entries: list[dict[str, Any]] = []
    for index, sheet in enumerate(workbook.findall("main:sheets/main:sheet", namespaces), start=1):
        relation_id = sheet.attrib.get(f"{{{namespaces['rel']}}}id")
        entries.append(
            {
                "index": index,
                "name": sheet.attrib.get("name", f"Sheet{index}"),
                "path": relation_targets.get(relation_id, f"xl/worksheets/sheet{index}.xml"),
            }
        )
    return entries


def xlsx_target_path(target: str) -> str:
    target = target.replace("\\", "/").lstrip("/")
    if target.startswith("xl/"):
        return target
    return "xl/" + target


def xlsx_sheet_names(content: bytes) -> list[dict[str, Any]]:
    return [{"index": entry["index"], "name": entry["name"]} for entry in xlsx_sheet_entries(content)]


def xlsx_sheet_matrix(content: bytes, sheet_name: str = "") -> list[list[Any]]:
    namespaces = {
        "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        "pkgrel": "http://schemas.openxmlformats.org/package/2006/relationships",
    }
    entries = xlsx_sheet_entries(content)
    if not entries:
        return []
    selected = entries[0]
    if sheet_name:
        for entry in entries:
            if entry["name"] == sheet_name:
                selected = entry
                break
        else:
            raise ValueError(f"sheet not found: {sheet_name}")
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        shared_strings = read_shared_strings(archive, namespaces)
        sheet = ElementTree.fromstring(archive.read(selected["path"]))
    rows: dict[int, dict[int, Any]] = {}
    for row in sheet.findall(".//main:sheetData/main:row", namespaces):
        row_index = int(row.attrib.get("r", len(rows) + 1))
        cells: dict[int, Any] = {}
        for cell in row.findall("main:c", namespaces):
            ref = cell.attrib.get("r", "")
            col_index = column_index_from_ref(ref)
            cells[col_index] = read_cell_value(cell, shared_strings, namespaces)
        rows[row_index] = cells
    matrix = []
    for row_index in sorted(rows):
        cells = rows[row_index]
        width = max(cells.keys(), default=-1) + 1
        matrix.append([cells.get(index, "") for index in range(width)])
    return matrix


def read_shared_strings(archive: zipfile.ZipFile, namespaces: dict[str, str]) -> list[str]:
    try:
        root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    values = []
    for item in root.findall("main:si", namespaces):
        values.append("".join(node.text or "" for node in item.findall(".//main:t", namespaces)))
    return values


def column_index_from_ref(ref: str) -> int:
    letters = "".join(ch for ch in ref if ch.isalpha()).upper()
    total = 0
    for char in letters:
        total = total * 26 + (ord(char) - ord("A") + 1)
    return max(0, total - 1)


def read_cell_value(cell: ElementTree.Element, shared_strings: list[str], namespaces: dict[str, str]) -> Any:
    cell_type = cell.attrib.get("t", "")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//main:t", namespaces))
    value_node = cell.find("main:v", namespaces)
    if value_node is None or value_node.text is None:
        return ""
    value = value_node.text
    if cell_type == "s":
        index = int(value)
        return shared_strings[index] if 0 <= index < len(shared_strings) else ""
    if cell_type == "b":
        return "1" if value == "1" else "0"
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    try:
        number = float(value)
    except ValueError:
        return value
    return int(number) if number.is_integer() else number


def build_test_workbook() -> bytes:
    def sheet_xml(rows: list[list[Any]]) -> str:
        row_xml = []
        for row_index, row in enumerate(rows, start=1):
            cells = []
            for col_index, value in enumerate(row):
                ref = f"{chr(ord('A') + col_index)}{row_index}"
                if isinstance(value, (int, float)):
                    cells.append(f'<c r="{ref}"><v>{value}</v></c>')
                else:
                    cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{html.escape(str(value))}</t></is></c>')
            row_xml.append(f'<row r="{row_index}">{"".join(cells)}</row>')
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<sheetData>{"".join(row_xml)}</sheetData>'
            '</worksheet>'
        )

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>",
        )
        archive.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="1" sheetId="1" r:id="rId1"/><sheet name="802" sheetId="2" r:id="rId2"/></sheets>'
            "</workbook>",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>'
            "</Relationships>",
        )
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml([["name", "table", "address", "count", "value"], ["A", "holding", 41000, 1, 11]]))
        archive.writestr("xl/worksheets/sheet2.xml", sheet_xml([["name", "table", "address", "count", "value"], ["B", "holding", 42000, 2, 22]]))
    return output.getvalue()


def parse_uploaded_rows(filename: str, content: bytes, sheet_name: str = "") -> list[dict[str, Any]]:
    lower = filename.lower()
    if lower.endswith(".csv") or lower.endswith(".tsv"):
        return parse_csv_rows(content)
    if lower.endswith(".xlsx"):
        return parse_xlsx_rows(content, sheet_name=sheet_name)
    raise ValueError("upload must be .csv, .tsv, or .xlsx")


class ModbusPlantServer:
    def __init__(self, model: PlantModel, host: str, port: int) -> None:
        self.model = model
        self.host = host
        self.port = port
        self._stop = threading.Event()
        self._socket: socket.socket | None = None

    def serve_forever(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        sock.listen(16)
        sock.settimeout(0.5)
        self._socket = sock
        self.model.event("modbus_listening", host=self.host, port=self.port)
        try:
            while not self._stop.is_set():
                try:
                    conn, address = sock.accept()
                except socket.timeout:
                    continue
                thread = threading.Thread(target=self.handle_client, args=(conn, address), daemon=True)
                thread.start()
        finally:
            sock.close()

    def shutdown(self) -> None:
        self._stop.set()
        if self._socket:
            try:
                self._socket.close()
            except OSError:
                pass

    def handle_client(self, conn: socket.socket, address: tuple[str, int]) -> None:
        with conn:
            conn.settimeout(10.0)
            self.model.event("client_connected", remote=f"{address[0]}:{address[1]}")
            while not self._stop.is_set():
                try:
                    header = recv_exact(conn, 7)
                    tid, protocol_id, length, unit_id = struct.unpack(">HHHB", header)
                    if protocol_id != 0 or length <= 1:
                        return
                    body = recv_exact(conn, length - 1)
                    if not body:
                        return
                    response_pdu = self.handle_pdu(body, unit_id)
                    response = struct.pack(">HHHB", tid, 0, len(response_pdu) + 1, unit_id) + response_pdu
                    conn.sendall(response)
                except (TimeoutError, ConnectionError, OSError, ValueError):
                    return

    def handle_pdu(self, body: bytes, unit_id: int) -> bytes:
        function_code = body[0]
        try:
            if function_code in (1, 2):
                if len(body) < 5:
                    return exception_pdu(function_code, 3)
                offset, count = struct.unpack(">HH", body[1:5])
                if count <= 0 or count > 2000:
                    return exception_pdu(function_code, 3)
                bits = self.model.read_bits(TABLE_BY_FUNCTION[function_code], offset, count, unit_id)
                return bytes([function_code, (count + 7) // 8]) + pack_bits(bits)
            if function_code in (3, 4):
                if len(body) < 5:
                    return exception_pdu(function_code, 3)
                offset, count = struct.unpack(">HH", body[1:5])
                if count <= 0 or count > 125:
                    return exception_pdu(function_code, 3)
                values = self.model.read(TABLE_BY_FUNCTION[function_code], offset, count, unit_id)
                data = b"".join(struct.pack(">H", value & 0xFFFF) for value in values)
                return bytes([function_code, len(data)]) + data
            if function_code == 6:
                if len(body) < 5:
                    return exception_pdu(function_code, 3)
                offset, value = struct.unpack(">HH", body[1:5])
                self.model.write_register(offset, value, unit_id)
                return body[:5]
            if function_code == 16:
                if len(body) < 6:
                    return exception_pdu(function_code, 3)
                offset, count, byte_count = struct.unpack(">HHB", body[1:6])
                data = body[6:]
                if count <= 0 or count > 123 or byte_count != len(data) or byte_count != count * 2:
                    return exception_pdu(function_code, 3)
                values = [struct.unpack(">H", data[index : index + 2])[0] for index in range(0, len(data), 2)]
                self.model.write_many(offset, values, unit_id)
                return bytes([function_code]) + struct.pack(">HH", offset, count)
        except Exception:
            return exception_pdu(function_code, 4)
        return exception_pdu(function_code, 1)


def recv_exact(conn: socket.socket, count: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < count:
        chunk = conn.recv(count - len(chunks))
        if not chunk:
            raise ConnectionError("connection closed")
        chunks.extend(chunk)
    return bytes(chunks)


def exception_pdu(function_code: int, exception_code: int) -> bytes:
    return bytes([function_code | 0x80, exception_code])


def pack_bits(bits: list[int]) -> bytes:
    output = bytearray()
    for start in range(0, len(bits), 8):
        byte = 0
        for bit_index, bit in enumerate(bits[start : start + 8]):
            if bit:
                byte |= 1 << bit_index
        output.append(byte)
    return bytes(output)


class PlantHttpHandler(BaseHTTPRequestHandler):
    server_version = "BmsPlantModel/0.1"

    def log_message(self, format: str, *args: object) -> None:
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), format % args))

    @property
    def model(self) -> PlantModel:
        return self.server.model  # type: ignore[attr-defined]

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/":
                return self.serve_static("index.html", "text/html; charset=utf-8")
            if parsed.path == "/app.js":
                return self.serve_static("app.js", "application/javascript; charset=utf-8")
            if parsed.path == "/styles.css":
                return self.serve_static("styles.css", "text/css; charset=utf-8")
            if parsed.path == "/api/status":
                payload = self.model.snapshot()
                payload["http"] = {"host": self.server.server_address[0], "port": self.server.server_address[1]}  # type: ignore[attr-defined]
                payload["modbus"] = {"host": self.server.modbus_host, "port": self.server.modbus_port}  # type: ignore[attr-defined]
                return json_response(self, payload)
            if parsed.path == "/api/registers":
                query = parse_qs(parsed.query)
                limit = int(query.get("limit", ["300"])[0] or "300")
                search = query.get("q", [""])[0]
                return json_response(self, {"registers": self.model.register_rows(limit=limit, query=search)})
            return json_response(self, {"error": "not found"}, HTTPStatus.NOT_FOUND)
        except Exception as exc:
            return json_response(self, {"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/workbook/sheets":
                fields, files = read_multipart(self)
                filename, content = uploaded_file(files)
                if not filename.lower().endswith(".xlsx"):
                    return json_response(self, {"filename": filename, "sheets": []})
                return json_response(self, {"filename": filename, "sheets": xlsx_sheet_names(content)})
            if parsed.path == "/api/import":
                fields, files = read_multipart(self)
                filename, content = uploaded_file(files)
                sheet_name = clean_text(fields.get("sheet_name"))
                rows = parse_uploaded_rows(filename, content, sheet_name=sheet_name)
                return json_response(self, self.model.import_rows(rows, filename, workbook_sheet=sheet_name))
            if parsed.path == "/api/reset":
                self.model.reset_defaults()
                return json_response(self, self.model.snapshot())
            if parsed.path == "/api/preset":
                payload = read_json(self)
                self.model.set_preset(clean_text(payload.get("preset")) or "nominal")
                return json_response(self, self.model.snapshot())
            return json_response(self, {"error": "not found"}, HTTPStatus.NOT_FOUND)
        except Exception as exc:
            return json_response(self, {"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def serve_static(self, name: str, content_type: str) -> None:
        path = STATIC_DIR / name
        if not path.exists():
            return json_response(self, {"error": f"missing static file: {name}"}, HTTPStatus.NOT_FOUND)
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def json_response(handler: BaseHTTPRequestHandler, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
    body = json.dumps(payload, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if not length:
        return {}
    return json.loads(handler.rfile.read(length).decode("utf-8"))


def read_multipart(handler: BaseHTTPRequestHandler) -> tuple[dict[str, str], dict[str, tuple[str, bytes]]]:
    content_type = handler.headers.get("Content-Type", "")
    length = int(handler.headers.get("Content-Length", "0") or "0")
    body = handler.rfile.read(length)
    if "multipart/form-data" not in content_type:
        raise ValueError("expected multipart/form-data upload")
    match = re.search(r"boundary=(.+)", content_type)
    if not match:
        raise ValueError("multipart boundary missing")
    boundary = match.group(1).strip('"').encode("utf-8")
    fields: dict[str, str] = {}
    files: dict[str, tuple[str, bytes]] = {}
    for part in body.split(b"--" + boundary):
        header_blob, _, payload = part.partition(b"\r\n\r\n")
        if not payload:
            continue
        headers = header_blob.decode("utf-8", errors="replace")
        name_match = re.search(r'name="?([^";\r\n]+)"?', headers)
        field_name = name_match.group(1).strip() if name_match else "file"
        payload = payload.rstrip(b"\r\n")
        if b"filename=" not in header_blob:
            fields[field_name] = payload.decode("utf-8", errors="replace")
            continue
        filename_match = re.search(r'filename\*=[^\'"]*\'\'([^;\r\n]+)', headers)
        if filename_match:
            filename = Path(unquote(filename_match.group(1).strip().strip('"'))).name
        else:
            filename_match = re.search(r'filename="?([^";\r\n]+)"?', headers)
            filename = Path(filename_match.group(1).strip()).name if filename_match else "upload"
        files[field_name] = (filename, payload)
    return fields, files


def uploaded_file(files: dict[str, tuple[str, bytes]]) -> tuple[str, bytes]:
    if "file" in files:
        return files["file"]
    if files:
        return next(iter(files.values()))
    raise ValueError("no uploaded file found")


def read_upload(handler: BaseHTTPRequestHandler) -> tuple[str, bytes]:
    _fields, files = read_multipart(handler)
    return uploaded_file(files)


class PlantHttpServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        handler: type[BaseHTTPRequestHandler],
        model: PlantModel,
        modbus_host: str,
        modbus_port: int,
    ) -> None:
        super().__init__(server_address, handler)
        self.model = model
        self.modbus_host = modbus_host
        self.modbus_port = modbus_port


def self_test() -> int:
    model = PlantModel()
    snapshot = model.snapshot()
    if snapshot["registers"] < 100:
        raise SystemExit(f"expected seeded register map, got {snapshot['registers']}")
    values = model.read("holding", address_to_offset("holding", 40002, "auto"), 4, 1)
    if len(values) != 4:
        raise SystemExit("read failed")
    model.write_register(address_to_offset("holding", 40170, "auto"), 1, 1)
    model.write_register(address_to_offset("holding", 40171, "auto"), 1, 1)
    if model.value_at("holding", 40173) != 1:
        raise SystemExit("contactor state did not follow SetEna/SetCon")
    rows = parse_csv_rows(b"name,table,address,count,value,writable\nImported,holding,41000,2,7,true\n")
    summary = model.import_rows(rows, "sample.csv")
    if summary["imported_registers"] != 2:
        raise SystemExit("CSV import failed")
    real_style_rows = parse_csv_rows(
        b"Modbus,Name,Value,Type,Size,RW Access,Label,Description\n"
        b"41030,ID,805,uint16,1,RO,Model ID,Model identifier\n"
        b"41031,L,,uint16,1,RO,Model Length,Model length\n"
    )
    summary = model.import_rows(real_style_rows, "real-style.csv")
    if summary["imported_registers"] != 2 or model.value_at("holding", 41030) != 805:
        raise SystemExit(f"real-style table import failed: {summary}")
    missing = model.read("holding", address_to_offset("holding", 49999, "auto"), 1, 1)
    if missing != [NOT_AVAILABLE_REGISTER]:
        raise SystemExit("missing register did not return not-available value")
    rows = parse_csv_rows(b"name,table,address,count,not_applicable\nNotApplicable,holding,41020,1,1\n")
    model.import_rows(rows, "not-applicable.csv")
    not_applicable = model.read("holding", address_to_offset("holding", 41020, "auto"), 1, 1)
    if not_applicable != [NOT_AVAILABLE_REGISTER]:
        raise SystemExit("not-applicable register did not return not-available value")
    try:
        parse_csv_rows(
            b"source_image,ocr_input,line_index,x,y,width,height,text\n"
            b"IMG_TEST.HEIC,IMG_TEST_table.png,1,180,100,52,15,40310\n"
        )
    except ValueError as exc:
        if "OCR evidence CSV" not in str(exc):
            raise
    else:
        raise SystemExit("OCR evidence CSV should not be accepted as a register database")
    workbook = build_test_workbook()
    sheets = xlsx_sheet_names(workbook)
    if [sheet["name"] for sheet in sheets] != ["1", "802"]:
        raise SystemExit(f"XLSX sheet discovery failed: {sheets}")
    model_802_rows = parse_uploaded_rows("modbus.xlsx", workbook, sheet_name="802")
    if model_802_rows[0].get("name") != "B":
        raise SystemExit("XLSX selected-sheet parsing failed")
    summary = model.import_rows(model_802_rows, "modbus.xlsx", workbook_sheet="802")
    if summary["workbook_sheet"] != "802" or summary["imported_registers"] != 2:
        raise SystemExit("workbook-sheet import failed")
    print(json.dumps({"ok": True, "registers": snapshot["registers"], "sample": values}, indent=2))
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BMS plant model with Modbus/TCP and Excel/CSV GUI")
    parser.add_argument("--http-host", default="127.0.0.1")
    parser.add_argument("--http-port", type=int, default=8766)
    parser.add_argument("--modbus-host", default="127.0.0.1")
    parser.add_argument("--modbus-port", type=int, default=1502)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        return self_test()

    model = PlantModel()
    modbus_server = ModbusPlantServer(model, args.modbus_host, args.modbus_port)
    modbus_thread = threading.Thread(target=modbus_server.serve_forever, daemon=True)
    modbus_thread.start()

    http_server = PlantHttpServer(
        (args.http_host, args.http_port),
        PlantHttpHandler,
        model,
        args.modbus_host,
        args.modbus_port,
    )
    print(
        f"BMS plant model GUI running at http://{args.http_host}:{args.http_port}/ "
        f"with Modbus/TCP at {args.modbus_host}:{args.modbus_port}",
        flush=True,
    )
    try:
        http_server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        http_server.server_close()
        modbus_server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
