#!/usr/bin/env python3
"""
foxBMS POSIX — Bidirectional Traceability Matrix Generator

Scans docs/aspice-cl2/ for requirement IDs and trace links, scans src/ for
@safety_req and @verifies tags, builds a bidirectional graph, validates
completeness, and generates the traceability matrix markdown.

Pure stdlib — no pip dependencies.

Usage:
    python scripts/trace-gen.py                    # Generate matrix (default)
    python scripts/trace-gen.py --check            # CI mode: exit 1 on gaps
    python scripts/trace-gen.py --stats            # Print summary stats only
    python scripts/trace-gen.py --json             # Output as JSON
    python scripts/trace-gen.py --output FILE      # Custom output path

Scanned tags:
    Markdown tables:  | STKH-REQ-001 | ... | SYS-REQ-001 |
    Markdown fields:  **Traces up**: SYS-REQ-001  /  **Traces down**: SW-REQ-010
    Markdown headings: ### TSR-01: ... (FSR-01, ...)
    Source code:       @safety_req SSR-001  /  @verifies SW-REQ-001
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
DOCS_DIR = ROOT_DIR / "docs" / "aspice-cl2"
SRC_DIR = ROOT_DIR / "src"
DEFAULT_OUTPUT = DOCS_DIR / "00-assessment" / "traceability-matrix-generated.md"

# All requirement ID patterns that can appear in documents.
# The order matters for classification (first match wins for ambiguous IDs).
ID_PATTERNS = [
    ("STKH-REQ", r"STKH-REQ-0*(\d+)"),
    ("SYS-REQ",  r"SYS-REQ-0*(\d+)"),
    ("SW-REQ",   r"SW-REQ-0*(\d+)"),
    ("SSR",      r"SSR-0*(\d+)"),
    ("SG",       r"SG-0*(\d+)"),
    ("FSR",      r"FSR-0*(\d+)"),
    ("TSR",      r"TSR-0*(\d+)"),
    ("HZ",       r"HZ-0*(\d+)"),
    ("UT",       r"UT-0*(\d+)"),
    ("IT",       r"IT-0*(\d+)"),
    ("QT",       r"QT-0*(\d+)"),
    ("FM",       r"FM-0*(\d+)"),
]

# Composite regex that matches any requirement ID in text.
# Captures the full ID string (e.g., "SYS-REQ-001" or "SG-01").
ALL_ID_RE = re.compile(
    r"\b("
    r"STKH-REQ-\d+"
    r"|SYS-REQ-\d+"
    r"|SW-REQ-\d+"
    r"|SSR-\d+"
    r"|SG-\d+"
    r"|FSR-\d+"
    r"|TSR-\d+"
    r"|HZ-\d+"
    r"|UT-\d+"
    r"|IT-\d+"
    r"|QT-\d+"
    r"|FM-\d+"
    r")\b"
)

# Source code tag patterns
SAFETY_REQ_RE = re.compile(r"@safety_req\s+((?:SSR|SW-REQ|SYS-REQ|STKH-REQ|FSR|TSR)-\d+)")
VERIFIES_RE = re.compile(r"@verifies\s+((?:SW-REQ|SYS-REQ|SSR|STKH-REQ|UT|IT|QT)-\d+)")

# Level hierarchy (top to bottom in the V-model)
LEVEL_ORDER = [
    "STKH-REQ", "SYS-REQ", "SG", "HZ", "FSR", "TSR",
    "SW-REQ", "SSR", "FM", "UT", "IT", "QT",
]

# Leaf requirement levels (must have test coverage)
LEAF_LEVELS = {"SW-REQ", "SSR"}

# Test levels
TEST_LEVELS = {"UT", "IT", "QT"}

# ASIL values
ASIL_ORDER = {"QM": 0, "A": 1, "B": 2, "C": 3, "D": 4}


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

def normalize_id(raw_id):
    """Normalize a requirement ID to canonical form with zero-padded numbers.

    Examples:
        SYS-REQ-1   -> SYS-REQ-001
        SG-01        -> SG-001
        SSR-42       -> SSR-042
        STKH-REQ-020 -> STKH-REQ-020
        UT-1         -> UT-001
    """
    for prefix, pattern in ID_PATTERNS:
        m = re.match(r"^" + prefix + r"-0*(\d+)$", raw_id)
        if m:
            num = int(m.group(1))
            return f"{prefix}-{num:03d}"
    return raw_id


def classify_level(req_id):
    """Return the level prefix for a given normalized ID."""
    for prefix, _ in ID_PATTERNS:
        if req_id.startswith(prefix + "-"):
            return prefix
    return "UNKNOWN"


def extract_ids(text):
    """Extract all requirement IDs from text and return normalized list."""
    raw_ids = ALL_ID_RE.findall(text)
    return [normalize_id(rid) for rid in raw_ids]


# ---------------------------------------------------------------------------
# Requirement node
# ---------------------------------------------------------------------------

class Requirement:
    """A single requirement in the traceability graph."""

    __slots__ = (
        "req_id", "level", "title", "source_file", "asil",
        "traces_up", "traces_down", "verified_by", "implemented_by",
    )

    def __init__(self, req_id, level=None, title="", source_file="", asil=""):
        self.req_id = req_id
        self.level = level or classify_level(req_id)
        self.title = title
        self.source_file = source_file
        self.asil = asil
        self.traces_up = set()      # IDs this derives from
        self.traces_down = set()    # IDs derived from this
        self.verified_by = set()    # Test IDs or code files that verify this
        self.implemented_by = set() # Source files with @safety_req for this

    def to_dict(self):
        return {
            "id": self.req_id,
            "level": self.level,
            "title": self.title,
            "source_file": self.source_file,
            "asil": self.asil,
            "traces_up": sorted(self.traces_up),
            "traces_down": sorted(self.traces_down),
            "verified_by": sorted(self.verified_by),
            "implemented_by": sorted(self.implemented_by),
        }


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------

class TraceGraph:
    """Bidirectional traceability graph."""

    def __init__(self):
        self.reqs = {}           # req_id -> Requirement
        self.broken_links = []   # (source_file, referencing_id, missing_id)
        self.asymmetric = []     # (id_a, id_b, direction)
        self.code_tags = []      # (file, tag_type, req_id)

    def get_or_create(self, req_id, **kwargs):
        nid = normalize_id(req_id)
        if nid not in self.reqs:
            self.reqs[nid] = Requirement(nid, **kwargs)
        else:
            # Update fields if provided and currently empty
            r = self.reqs[nid]
            for k, v in kwargs.items():
                if v and not getattr(r, k, None):
                    setattr(r, k, v)
        return self.reqs[nid]

    def add_trace(self, from_id, to_id, source_file=""):
        """Add a directional trace: from_id traces up to to_id."""
        fid = normalize_id(from_id)
        tid = normalize_id(to_id)
        f = self.get_or_create(fid, source_file=source_file)
        t = self.get_or_create(tid, source_file=source_file)
        f.traces_up.add(tid)
        t.traces_down.add(fid)

    def add_verification(self, test_id, req_id, source_file=""):
        """Record that test_id verifies req_id."""
        tid = normalize_id(test_id)
        rid = normalize_id(req_id)
        self.get_or_create(tid, source_file=source_file)
        r = self.get_or_create(rid)
        r.verified_by.add(tid)

    def add_code_impl(self, code_file, req_id):
        """Record that code_file implements req_id via @safety_req."""
        rid = normalize_id(req_id)
        r = self.get_or_create(rid)
        r.implemented_by.add(code_file)


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def parse_markdown_tables(graph, filepath):
    """Parse markdown tables to extract requirement definitions and trace links.

    Handles table formats found in the foxBMS ASPICE documents:
      | ID | Requirement | ... | Derives From | ... |
      | ID | Requirement | ... | Traces To | ... |
      | ID | Test Case | ... | Traces To | ... |
    Also handles heading-based IDs like: ### TSR-01: Description (FSR-01, ...)
    And safety goal tables: | SG-001 | ... |
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except (OSError, UnicodeDecodeError) as e:
        print(f"  WARNING: Cannot read {filepath}: {e}", file=sys.stderr)
        return

    rel_path = str(filepath)
    lines = content.split("\n")

    # --- Pass 1: Extract heading-based IDs with inline refs ---
    # e.g., "### TSR-01: Cell Overvoltage Detection and Reaction (FSR-01, ASIL D)"
    # e.g., "### HZ-01: Cell Overvoltage"
    # e.g., "### 4.1  FSR-01: Cell Overvoltage Protection (SG-01, ASIL D)"
    heading_re = re.compile(
        r"^#{2,4}\s+(?:\d+(?:\.\d+)*\s+)?"
        r"((?:TSR|FSR|HZ|SG|SSR|FM)-\d+):\s*(.+)"
    )

    for line in lines:
        m = heading_re.match(line)
        if m:
            raw_id = m.group(1)
            title_rest = m.group(2)
            nid = normalize_id(raw_id)
            graph.get_or_create(nid, title=title_rest.strip(), source_file=rel_path)

            # Extract parenthetical refs like (FSR-01, ASIL D) or (SG-01)
            paren = re.search(r"\(([^)]+)\)", title_rest)
            if paren:
                refs = extract_ids(paren.group(1))
                for ref in refs:
                    ref_level = classify_level(ref)
                    my_level = classify_level(nid)
                    # Determine direction: if the ref is "higher", trace up
                    try:
                        ref_idx = LEVEL_ORDER.index(ref_level)
                        my_idx = LEVEL_ORDER.index(my_level)
                    except ValueError:
                        continue
                    if ref_idx < my_idx:
                        graph.add_trace(nid, ref, source_file=rel_path)
                    else:
                        graph.add_trace(ref, nid, source_file=rel_path)

                # Extract ASIL from parenthetical
                asil_m = re.search(r"ASIL\s+([A-D])", paren.group(1))
                if asil_m:
                    graph.reqs[nid].asil = asil_m.group(1)
                elif "QM" in paren.group(1):
                    graph.reqs[nid].asil = "QM"

    # --- Pass 2: Extract **Traces up/down** fields ---
    traces_up_re = re.compile(r"\*\*Traces?\s*up\*?\*?:?\s*(.+)", re.IGNORECASE)
    traces_down_re = re.compile(r"\*\*Traces?\s*down\*?\*?:?\s*(.+)", re.IGNORECASE)

    current_id = None
    for line in lines:
        # Track the most recent heading-defined ID
        hm = heading_re.match(line)
        if hm:
            current_id = normalize_id(hm.group(1))
            continue

        # Check for Traces up
        tum = traces_up_re.search(line)
        if tum and current_id:
            refs = extract_ids(tum.group(1))
            for ref in refs:
                graph.add_trace(current_id, ref, source_file=rel_path)
            continue

        # Check for Traces down
        tdm = traces_down_re.search(line)
        if tdm and current_id:
            refs = extract_ids(tdm.group(1))
            for ref in refs:
                graph.add_trace(ref, current_id, source_file=rel_path)
            continue

    # --- Pass 3: Parse table rows ---
    # Strategy: a table header is a pipe row FOLLOWED by a separator row
    # (|---|---|...). We detect header+separator pairs first, then parse
    # subsequent data rows using the column layout from the header.
    table_state = None  # None or dict with column info

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Detect separator row — the previous non-blank pipe row is the header
        if stripped.startswith("|") and "---" in stripped:
            # Look back for the header row
            header_line = None
            for back in range(i - 1, max(i - 3, -1), -1):
                prev = lines[back].strip()
                if prev.startswith("|") and "---" not in prev and prev:
                    header_line = prev
                    break
            if header_line:
                cells = [c.strip() for c in header_line.split("|")]
                if cells and cells[0] == "":
                    cells = cells[1:]
                if cells and cells[-1] == "":
                    cells = cells[:-1]
                lower_cells = [c.lower() for c in cells]
                table_state = {
                    "id_col": None,
                    "derives_col": None,
                    "traces_col": None,
                    "asil_col": None,
                    "safety_goal_col": None,
                }
                for j, c in enumerate(lower_cells):
                    if c in ("id", "hazard id", "safety goal id"):
                        table_state["id_col"] = j
                    elif "derives from" in c or "derives" in c:
                        table_state["derives_col"] = j
                    elif "traces to" in c or "traces" in c:
                        table_state["traces_col"] = j
                    elif c == "asil":
                        table_state["asil_col"] = j
                    elif "safety goal" in c and c != "safety goal id":
                        table_state["safety_goal_col"] = j
            continue

        # Non-table line resets table state
        if not stripped.startswith("|"):
            if stripped:  # Non-blank, non-table line
                table_state = None
            continue

        # Data row (pipe row that is not a separator, with active table_state)
        if stripped.startswith("|") and table_state:
            cells = [c.strip() for c in stripped.split("|")]
            if cells and cells[0] == "":
                cells = cells[1:]
            if cells and cells[-1] == "":
                cells = cells[:-1]

            if len(cells) < 2:
                continue

            # Extract the row's primary ID
            row_id = None
            id_col = table_state.get("id_col")
            if id_col is not None and id_col < len(cells):
                ids_in_cell = extract_ids(cells[id_col])
                if ids_in_cell:
                    row_id = ids_in_cell[0]
            # Fallback: check first cell for an ID
            if not row_id:
                ids_in_first = extract_ids(cells[0])
                if ids_in_first:
                    row_id = ids_in_first[0]

            if not row_id:
                continue

            # Register the requirement
            title = ""
            if len(cells) > 1:
                # Take the second cell as title/description (truncated)
                raw_title = cells[1]
                # Remove markdown formatting
                raw_title = re.sub(r"\*\*([^*]+)\*\*", r"\1", raw_title)
                title = raw_title[:120]

            asil = ""
            if table_state.get("asil_col") is not None:
                ac = table_state["asil_col"]
                if ac < len(cells):
                    asil_text = cells[ac].strip()
                    if asil_text in ("A", "B", "C", "D", "QM"):
                        asil = asil_text
                    else:
                        am = re.search(r"ASIL\s+([A-D])", asil_text)
                        if am:
                            asil = am.group(1)

            graph.get_or_create(
                row_id, title=title, source_file=rel_path, asil=asil
            )

            # Process "Derives From" column
            dc = table_state.get("derives_col")
            if dc is not None and dc < len(cells):
                refs = extract_ids(cells[dc])
                for ref in refs:
                    graph.add_trace(row_id, ref, source_file=rel_path)

            # Process "Traces To" column
            tc = table_state.get("traces_col")
            if tc is not None and tc < len(cells):
                refs = extract_ids(cells[tc])
                for ref in refs:
                    ref_level = classify_level(ref)
                    row_level = classify_level(row_id)
                    try:
                        ref_idx = LEVEL_ORDER.index(ref_level)
                        row_idx = LEVEL_ORDER.index(row_level)
                    except ValueError:
                        graph.add_trace(ref, row_id, source_file=rel_path)
                        continue

                    if ref_idx > row_idx:
                        # Traces forward (down the V)
                        graph.add_trace(ref, row_id, source_file=rel_path)
                    elif ref_idx < row_idx:
                        # Traces backward (up the V)
                        graph.add_trace(row_id, ref, source_file=rel_path)
                    else:
                        # Same level — treat as peer link, add both directions
                        graph.add_trace(row_id, ref, source_file=rel_path)

            # Process "Safety Goal" column (for SSR-like docs)
            sgc = table_state.get("safety_goal_col")
            if sgc is not None and sgc < len(cells):
                refs = extract_ids(cells[sgc])
                for ref in refs:
                    if classify_level(ref) in ("SG", "HZ"):
                        graph.add_trace(row_id, ref, source_file=rel_path)

            # Also: scan ALL cells for cross-references (catch "Traces To" in
            # non-header-detected columns and inline refs)
            for j, cell in enumerate(cells):
                if j == (id_col if id_col is not None else 0):
                    continue  # Skip the ID cell itself
                if j == dc or j == tc or j == sgc:
                    continue  # Already processed
                refs = extract_ids(cell)
                for ref in refs:
                    if ref == row_id:
                        continue
                    ref_level = classify_level(ref)
                    row_level = classify_level(row_id)

                    # Test refs verify requirements
                    if row_level in TEST_LEVELS and ref_level not in TEST_LEVELS:
                        graph.add_verification(row_id, ref, source_file=rel_path)
                    elif ref_level in TEST_LEVELS and row_level not in TEST_LEVELS:
                        graph.add_verification(ref, row_id, source_file=rel_path)
                    else:
                        # Determine trace direction
                        try:
                            ref_idx = LEVEL_ORDER.index(ref_level)
                            row_idx = LEVEL_ORDER.index(row_level)
                        except ValueError:
                            continue
                        if ref_idx < row_idx:
                            graph.add_trace(row_id, ref, source_file=rel_path)
                        elif ref_idx > row_idx:
                            graph.add_trace(ref, row_id, source_file=rel_path)



def parse_safety_goal_table(graph, filepath):
    """Parse the HARA safety goal summary table.

    Handles lines like:
        | SG-01 | HZ-01 | ASIL D | Description... |
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except (OSError, UnicodeDecodeError):
        return

    rel_path = str(filepath)
    sg_row_re = re.compile(
        r"\|\s*(SG-\d+)\s*\|\s*(HZ-\d+)\s*\|\s*(ASIL\s+[A-D]|QM)\s*\|\s*(.+?)\s*\|"
    )
    for m in sg_row_re.finditer(content):
        sg_id = normalize_id(m.group(1))
        hz_id = normalize_id(m.group(2))
        asil = m.group(3).replace("ASIL ", "").strip()
        title = m.group(4).strip()[:120]
        graph.get_or_create(sg_id, title=title, source_file=rel_path, asil=asil)
        graph.get_or_create(hz_id, source_file=rel_path)
        graph.add_trace(sg_id, hz_id, source_file=rel_path)


def parse_source_files(graph, src_dir):
    """Scan source files for @safety_req and @verifies tags."""
    if not src_dir.is_dir():
        print(f"  WARNING: Source directory not found: {src_dir}", file=sys.stderr)
        return

    for fpath in sorted(src_dir.iterdir()):
        if not fpath.is_file():
            continue
        if fpath.suffix not in (".c", ".h", ".py"):
            continue

        try:
            content = fpath.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            print(f"  WARNING: Cannot read {fpath}: {e}", file=sys.stderr)
            continue

        rel_path = fpath.name

        for m in SAFETY_REQ_RE.finditer(content):
            rid = normalize_id(m.group(1))
            graph.add_code_impl(rel_path, rid)
            graph.code_tags.append((rel_path, "@safety_req", rid))

        for m in VERIFIES_RE.finditer(content):
            rid = normalize_id(m.group(1))
            graph.add_verification(f"code:{rel_path}", rid, source_file=rel_path)
            graph.code_tags.append((rel_path, "@verifies", rid))


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate(graph):
    """Validate the traceability graph for completeness and consistency."""
    broken_links = []
    orphans = []
    untested = []
    asymmetric = []

    defined_ids = set(graph.reqs.keys())

    for req_id, req in sorted(graph.reqs.items()):
        level = req.level

        # Check for broken links (references to undefined IDs)
        for ref in req.traces_up:
            if ref not in defined_ids:
                broken_links.append((req.source_file, req_id, ref))
        for ref in req.traces_down:
            if ref not in defined_ids:
                broken_links.append((req.source_file, req_id, ref))

        # Orphan detection: no parent AND no child (excluding top-level and tests)
        if level not in ("STKH-REQ", "HZ") and level not in TEST_LEVELS:
            has_parent = len(req.traces_up) > 0
            has_child = len(req.traces_down) > 0 or len(req.verified_by) > 0
            if not has_parent and not has_child:
                orphans.append((req_id, level))

        # Untested leaf requirements
        if level in LEAF_LEVELS:
            has_test = len(req.verified_by) > 0
            # Also check if any UT/IT/QT traces down to this via the table
            for rid, r in graph.reqs.items():
                if classify_level(rid) in TEST_LEVELS:
                    if req_id in r.traces_up:
                        has_test = True
                        break
            if not has_test:
                untested.append((req_id, level))

    # Asymmetric link detection
    for req_id, req in graph.reqs.items():
        for ref in req.traces_up:
            if ref in graph.reqs:
                peer = graph.reqs[ref]
                if req_id not in peer.traces_down:
                    asymmetric.append((req_id, ref, "up"))
        for ref in req.traces_down:
            if ref in graph.reqs:
                peer = graph.reqs[ref]
                if req_id not in peer.traces_up:
                    asymmetric.append((req_id, ref, "down"))

    return broken_links, orphans, untested, asymmetric


# ---------------------------------------------------------------------------
# Output generation
# ---------------------------------------------------------------------------

def level_stats(graph):
    """Compute per-level statistics."""
    stats = {}
    for level in LEVEL_ORDER:
        ids = [r for r in graph.reqs.values() if r.level == level]
        if not ids:
            continue
        defined = len(ids)
        traced_up = sum(1 for r in ids if r.traces_up)
        traced_down = sum(1 for r in ids if r.traces_down or r.verified_by)
        tested = sum(1 for r in ids if r.verified_by)
        coverage = (tested / defined * 100) if defined > 0 else 0
        stats[level] = {
            "defined": defined,
            "traced_up": traced_up,
            "traced_down": traced_down,
            "tested": tested,
            "coverage": coverage,
        }
    return stats


def generate_markdown(graph, broken_links, orphans, untested, asymmetric):
    """Generate the traceability matrix markdown."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    stats = level_stats(graph)
    total_reqs = len(graph.reqs)

    lines = []
    lines.append("# Auto-Generated Traceability Matrix")
    lines.append("")
    lines.append(f"Generated: {now}")
    lines.append("")
    lines.append(f"Total requirement IDs tracked: **{total_reqs}**")
    lines.append("")

    # --- Summary table ---
    lines.append("## Summary")
    lines.append("")
    lines.append("| Level | Defined | Traced Up | Traced Down | Tested | Coverage |")
    lines.append("|---|---|---|---|---|---|")
    for level in LEVEL_ORDER:
        if level in stats:
            s = stats[level]
            lines.append(
                f"| {level} | {s['defined']} | {s['traced_up']} "
                f"| {s['traced_down']} | {s['tested']} "
                f"| {s['coverage']:.0f}% |"
            )
    lines.append("")

    # --- Forward trace: STKH -> SYS -> SW-REQ -> Test ---
    lines.append("## Forward Trace: Stakeholder -> System -> Software -> Test")
    lines.append("")
    lines.append("| STKH-REQ | -> SYS-REQ | -> SW-REQ | -> SSR | -> Code | -> Test |")
    lines.append("|---|---|---|---|---|---|")

    stkh_reqs = sorted(
        [r for r in graph.reqs.values() if r.level == "STKH-REQ"],
        key=lambda r: r.req_id
    )
    for stkh in stkh_reqs:
        sys_ids = sorted(stkh.traces_down & {
            r.req_id for r in graph.reqs.values() if r.level == "SYS-REQ"
        })
        for sys_id in (sys_ids or [""]):
            sw_ids = []
            if sys_id and sys_id in graph.reqs:
                sw_ids = sorted(graph.reqs[sys_id].traces_down & {
                    r.req_id for r in graph.reqs.values() if r.level == "SW-REQ"
                })
            for sw_id in (sw_ids or [""]):
                ssr_ids = []
                code_files = set()
                test_ids = set()
                if sw_id and sw_id in graph.reqs:
                    sw_req = graph.reqs[sw_id]
                    code_files.update(sw_req.implemented_by)
                    test_ids.update(sw_req.verified_by)
                    # Find SSRs that trace up to the same SYS-REQ or safety goals
                    for rid, r in graph.reqs.items():
                        if r.level == "SSR" and sw_id in r.traces_up:
                            ssr_ids.append(rid)

                ssr_str = ", ".join(sorted(ssr_ids)) if ssr_ids else "--"
                code_str = ", ".join(sorted(code_files)) if code_files else "--"
                test_str = ", ".join(sorted(test_ids)) if test_ids else "--"

                lines.append(
                    f"| {stkh.req_id} | {sys_id or '--'} "
                    f"| {sw_id or '--'} | {ssr_str} | {code_str} | {test_str} |"
                )

    lines.append("")

    # --- Safety trace: HZ -> SG -> FSR -> TSR -> SSR -> Test ---
    lines.append("## Safety Trace: Hazard -> Safety Goal -> FSR -> TSR -> SSR -> Test")
    lines.append("")
    lines.append("| HZ | -> SG | -> FSR | -> TSR | -> SSR | -> Test |")
    lines.append("|---|---|---|---|---|---|")

    hz_reqs = sorted(
        [r for r in graph.reqs.values() if r.level == "HZ"],
        key=lambda r: r.req_id
    )
    for hz in hz_reqs:
        sg_ids = sorted(hz.traces_down & {
            r.req_id for r in graph.reqs.values() if r.level == "SG"
        })
        for sg_id in (sg_ids or [""]):
            fsr_ids = []
            if sg_id and sg_id in graph.reqs:
                fsr_ids = sorted(graph.reqs[sg_id].traces_down & {
                    r.req_id for r in graph.reqs.values() if r.level == "FSR"
                })
            for fsr_id in (fsr_ids or [""]):
                tsr_ids = []
                if fsr_id and fsr_id in graph.reqs:
                    tsr_ids = sorted(graph.reqs[fsr_id].traces_down & {
                        r.req_id for r in graph.reqs.values() if r.level == "TSR"
                    })
                for tsr_id in (tsr_ids or [""]):
                    ssr_ids = []
                    test_ids = set()
                    if tsr_id and tsr_id in graph.reqs:
                        for rid, r in graph.reqs.items():
                            if r.level == "SSR":
                                ssr_ids.append(rid)
                    for ssr_id in (ssr_ids or [""]):
                        if ssr_id and ssr_id in graph.reqs:
                            test_ids.update(graph.reqs[ssr_id].verified_by)
                        test_str = ", ".join(sorted(test_ids)) if test_ids else "--"
                        lines.append(
                            f"| {hz.req_id} | {sg_id or '--'} "
                            f"| {fsr_id or '--'} | {tsr_id or '--'} "
                            f"| {ssr_id or '--'} | {test_str} |"
                        )

    lines.append("")

    # --- Broken links ---
    lines.append("## Broken Links")
    lines.append("")
    if broken_links:
        lines.append("| Source Doc | Referencing ID | Missing ID |")
        lines.append("|---|---|---|")
        for src, ref_id, missing_id in sorted(set(broken_links)):
            lines.append(f"| {src} | {ref_id} | {missing_id} |")
    else:
        lines.append("No broken links found.")
    lines.append("")

    # --- Untested requirements ---
    lines.append("## Untested Requirements")
    lines.append("")
    if untested:
        lines.append("| Requirement | Level | Status |")
        lines.append("|---|---|---|")
        for rid, level in sorted(untested):
            lines.append(f"| {rid} | {level} | No test found |")
    else:
        lines.append("All leaf requirements have test coverage.")
    lines.append("")

    # --- Orphan requirements ---
    lines.append("## Orphan Requirements")
    lines.append("")
    if orphans:
        lines.append("| Requirement | Level | Status |")
        lines.append("|---|---|---|")
        for rid, level in sorted(orphans):
            lines.append(f"| {rid} | {level} | No parent, no child |")
    else:
        lines.append("No orphan requirements found.")
    lines.append("")

    # --- Asymmetric links ---
    lines.append("## Asymmetric Links")
    lines.append("")
    if asymmetric:
        lines.append("| ID A | ID B | Direction | Issue |")
        lines.append("|---|---|---|---|")
        seen = set()
        for id_a, id_b, direction in sorted(asymmetric):
            key = (min(id_a, id_b), max(id_a, id_b))
            if key in seen:
                continue
            seen.add(key)
            lines.append(
                f"| {id_a} | {id_b} | {direction} "
                f"| A references B but B does not reference A |"
            )
    else:
        lines.append("All links are bidirectional.")
    lines.append("")

    # --- Code tags ---
    if graph.code_tags:
        lines.append("## Source Code Tags")
        lines.append("")
        lines.append("| File | Tag | Requirement |")
        lines.append("|---|---|---|")
        for fpath, tag, rid in sorted(graph.code_tags):
            lines.append(f"| {fpath} | `{tag}` | {rid} |")
        lines.append("")

    lines.append("---")
    lines.append("*Auto-generated by trace-gen.py — do not edit manually.*")
    lines.append("")

    return "\n".join(lines)


def generate_json(graph, broken_links, orphans, untested, asymmetric):
    """Generate JSON output."""
    return json.dumps({
        "generated": datetime.now(timezone.utc).isoformat(),
        "total_requirements": len(graph.reqs),
        "stats": level_stats(graph),
        "requirements": {
            rid: req.to_dict() for rid, req in sorted(graph.reqs.items())
        },
        "broken_links": [
            {"source": s, "referencing": r, "missing": m}
            for s, r, m in broken_links
        ],
        "untested": [
            {"requirement": r, "level": l} for r, l in untested
        ],
        "orphans": [
            {"requirement": r, "level": l} for r, l in orphans
        ],
        "asymmetric_links": [
            {"id_a": a, "id_b": b, "direction": d}
            for a, b, d in asymmetric
        ],
        "code_tags": [
            {"file": f, "tag": t, "requirement": r}
            for f, t, r in graph.code_tags
        ],
    }, indent=2)


def print_stats(graph, broken_links, orphans, untested, asymmetric):
    """Print summary statistics."""
    stats = level_stats(graph)
    total = len(graph.reqs)

    print(f"\nfoxBMS POSIX — Traceability Summary")
    print(f"{'=' * 55}")
    print(f"Total requirement IDs: {total}")
    print()
    print(f"{'Level':<12} {'Defined':>8} {'Up':>6} {'Down':>6} "
          f"{'Tested':>7} {'Coverage':>9}")
    print(f"{'-' * 55}")
    for level in LEVEL_ORDER:
        if level in stats:
            s = stats[level]
            print(f"{level:<12} {s['defined']:>8} {s['traced_up']:>6} "
                  f"{s['traced_down']:>6} {s['tested']:>7} "
                  f"{s['coverage']:>8.0f}%")

    print(f"\n{'Validation':<30} {'Count':>6}")
    print(f"{'-' * 38}")
    print(f"{'Broken links':<30} {len(broken_links):>6}")
    print(f"{'Orphan requirements':<30} {len(orphans):>6}")
    print(f"{'Untested leaf requirements':<30} {len(untested):>6}")
    print(f"{'Asymmetric links':<30} {len(asymmetric):>6}")

    has_errors = len(broken_links) > 0 or len(untested) > 0
    print()
    if has_errors:
        print("STATUS: ISSUES FOUND")
    else:
        print("STATUS: PASS")

    return has_errors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="foxBMS POSIX — Bidirectional Traceability Matrix Generator"
    )
    parser.add_argument(
        "--check", action="store_true",
        help="CI mode: exit 1 if broken links or untested leaf requirements"
    )
    parser.add_argument(
        "--stats", action="store_true",
        help="Print summary statistics only (no file output)"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON instead of markdown"
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Custom output file path"
    )
    args = parser.parse_args()

    graph = TraceGraph()

    # --- Scan all markdown files in docs/aspice-cl2/ ---
    print("Scanning ASPICE documents...")
    if DOCS_DIR.is_dir():
        md_files = sorted(DOCS_DIR.rglob("*.md"))
        for md_file in md_files:
            rel = md_file.relative_to(ROOT_DIR)
            print(f"  {rel}")
            parse_markdown_tables(graph, md_file)
            # Also parse safety goal summary tables
            if "HARA" in md_file.name or "part3" in md_file.name:
                parse_safety_goal_table(graph, md_file)
    else:
        print(f"  WARNING: Docs directory not found: {DOCS_DIR}", file=sys.stderr)

    # --- Scan source files ---
    print("Scanning source code...")
    parse_source_files(graph, SRC_DIR)

    # --- Validate ---
    print("Validating traceability...")
    broken_links, orphans, untested, asymmetric = validate(graph)

    # --- Output ---
    if args.stats:
        has_errors = print_stats(graph, broken_links, orphans, untested, asymmetric)
        if args.check and has_errors:
            sys.exit(1)
        return

    if args.json:
        output_text = generate_json(
            graph, broken_links, orphans, untested, asymmetric
        )
        ext = ".json"
    else:
        output_text = generate_markdown(
            graph, broken_links, orphans, untested, asymmetric
        )
        ext = ".md"

    # Determine output path
    if args.output:
        out_path = Path(args.output)
    elif args.json:
        out_path = DEFAULT_OUTPUT.with_suffix(".json")
    else:
        out_path = DEFAULT_OUTPUT

    # Write output
    if not args.check or True:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output_text, encoding="utf-8")
        print(f"\nOutput written to: {out_path}")

    # Print summary
    has_errors = print_stats(graph, broken_links, orphans, untested, asymmetric)

    if args.check and has_errors:
        print("\nCI CHECK FAILED: broken links or untested requirements found.")
        sys.exit(1)
    elif args.check:
        print("\nCI CHECK PASSED.")


if __name__ == "__main__":
    main()
