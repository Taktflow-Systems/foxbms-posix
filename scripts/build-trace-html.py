#!/usr/bin/env python3
"""
Build interactive traceability visualization HTML from trace-gen.py JSON output.

Generates a single HTML page with:
- V-model diagram showing requirement layers
- Clickable nodes for each requirement ID
- Visible up/down/test links on click
- Color coding: green=fully traced, yellow=partial, red=orphan
- Search/filter by ID or level
- Summary stats dashboard

Usage:
    python scripts/build-trace-html.py
"""

import json
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
DOCS_DIR = ROOT / "docs" / "aspice-cl2"
SRC_DIR = ROOT / "src"
OUTPUT = ROOT / "docs" / "site" / "traceability.html"

# ---------------------------------------------------------------------------
# Re-use trace-gen scanning logic (import or inline)
# ---------------------------------------------------------------------------

ID_PATTERNS = [
    ("STKH-REQ", r"STKH-REQ-0*(\d+)"),
    ("SYS-REQ",  r"SYS-REQ-0*(\d+)"),
    ("SW-REQ",   r"SW-REQ-0*(\d+[A-Za-z]?)"),
    ("SSR",      r"SSR-0*(\d+)"),
    ("SG",       r"SG-0*(\d+)"),
    ("HZ",       r"HZ-0*(\d+)"),
    ("FSR",      r"FSR-0*(\d+)"),
    ("TSR",      r"TSR-0*(\d+)"),
    ("FM",       r"FM-0*(\d+)"),
    ("UT",       r"UT-0*(\d+)"),
    ("IT",       r"IT-0*(\d+)"),
    ("QT",       r"QT-0*(\d+)"),
]

ALL_ID_RE = re.compile(
    r"(STKH-REQ-\d+[A-Za-z]?|SYS-REQ-\d+[A-Za-z]?|SW-REQ-\d+[A-Za-z]?|"
    r"SSR-\d+|SG-\d+|HZ-\d+|FSR-\d+|TSR-\d+|FM-\d+|UT-\d+|IT-\d+|QT-\d+)"
)

LEVEL_ORDER = ["STKH-REQ", "SYS-REQ", "SG", "HZ", "FSR", "TSR", "SW-REQ", "SSR", "FM", "UT", "IT", "QT"]

LEVEL_COLORS = {
    "STKH-REQ": "#9b59b6",
    "SYS-REQ": "#3498db",
    "SG": "#e74c3c",
    "HZ": "#e74c3c",
    "FSR": "#e67e22",
    "TSR": "#e67e22",
    "SW-REQ": "#2ecc71",
    "SSR": "#f39c12",
    "FM": "#95a5a6",
    "UT": "#1abc9c",
    "IT": "#1abc9c",
    "QT": "#1abc9c",
}

LEVEL_LABELS = {
    "STKH-REQ": "Stakeholder",
    "SYS-REQ": "System",
    "SG": "Safety Goals",
    "HZ": "Hazards",
    "FSR": "Func Safety",
    "TSR": "Tech Safety",
    "SW-REQ": "Software",
    "SSR": "SW Safety",
    "FM": "Failure Modes",
    "UT": "Unit Tests",
    "IT": "Integration Tests",
    "QT": "Qualification Tests",
}


def classify_id(req_id):
    for prefix, _ in ID_PATTERNS:
        if req_id.startswith(prefix + "-"):
            return prefix
    return "UNKNOWN"


def normalize_id(req_id):
    for prefix, pattern in ID_PATTERNS:
        m = re.match(pattern.replace(r"0*(\d+)", r"0*(\d+[A-Za-z]?)"), req_id)
        if m:
            num = m.group(1)
            if num[-1].isalpha():
                return f"{prefix}-{int(num[:-1]):03d}{num[-1].upper()}"
            return f"{prefix}-{int(num):03d}"
    return req_id


def scan_docs():
    """Scan all markdown docs and build requirement graph."""
    nodes = {}  # id -> {level, file, up:set, down:set, tested_by:set}

    for md_file in sorted(DOCS_DIR.rglob("*.md")):
        text = md_file.read_text(encoding="utf-8", errors="replace")
        rel_path = str(md_file.relative_to(ROOT))

        # Find all IDs mentioned in this file
        ids_in_file = set()
        for m in ALL_ID_RE.finditer(text):
            nid = normalize_id(m.group(1))
            ids_in_file.add(nid)
            if nid not in nodes:
                nodes[nid] = {"level": classify_id(nid), "file": rel_path,
                              "up": set(), "down": set(), "tested_by": set()}

        # Parse table rows for trace links
        for line in text.split("\n"):
            if "|" not in line:
                continue
            cells = [c.strip() for c in line.split("|")]
            ids_in_row = []
            for cell in cells:
                for m in ALL_ID_RE.finditer(cell):
                    ids_in_row.append(normalize_id(m.group(1)))

            if len(ids_in_row) >= 2:
                # First ID in row is the requirement being defined
                # Other IDs are traces (up or down depending on level)
                primary = ids_in_row[0]
                primary_level = classify_id(primary)
                for other in ids_in_row[1:]:
                    other_level = classify_id(other)
                    if other == primary:
                        continue
                    p_idx = LEVEL_ORDER.index(primary_level) if primary_level in LEVEL_ORDER else -1
                    o_idx = LEVEL_ORDER.index(other_level) if other_level in LEVEL_ORDER else -1

                    if primary in nodes and other in nodes:
                        if p_idx > o_idx:  # primary is lower level -> other is parent
                            nodes[primary]["up"].add(other)
                            nodes[other]["down"].add(primary)
                        elif p_idx < o_idx:  # primary is higher level -> other is child
                            nodes[primary]["down"].add(other)
                            nodes[other]["up"].add(primary)
                        else:  # same level -> cross reference
                            nodes[primary]["down"].add(other)

    # Scan source for @verifies / @safety_req
    if SRC_DIR.exists():
        for src_file in SRC_DIR.glob("*.py"):
            text = src_file.read_text(encoding="utf-8", errors="replace")
            for m in re.finditer(r"@verifies\s+([\w-]+)", text):
                nid = normalize_id(m.group(1))
                if nid in nodes:
                    nodes[nid]["tested_by"].add(str(src_file.name))
        for src_file in SRC_DIR.glob("*.c"):
            text = src_file.read_text(encoding="utf-8", errors="replace")
            for m in re.finditer(r"@safety_req\s+([\w-]+)", text):
                nid = normalize_id(m.group(1))
                if nid in nodes:
                    nodes[nid]["tested_by"].add(str(src_file.name))

    return nodes


def build_html(nodes):
    """Build interactive traceability HTML."""

    # Group by level
    by_level = defaultdict(list)
    for nid, data in sorted(nodes.items()):
        by_level[data["level"]].append(nid)

    # Compute stats
    total = len(nodes)
    orphans = [nid for nid, d in nodes.items() if not d["up"] and not d["down"]]
    fully_traced = [nid for nid, d in nodes.items() if d["up"] or d["down"]]

    # Build nodes JSON for the JS
    nodes_json = {}
    edges = []
    for nid, data in nodes.items():
        nodes_json[nid] = {
            "level": data["level"],
            "file": data["file"],
            "up": sorted(data["up"]),
            "down": sorted(data["down"]),
            "tested_by": sorted(data["tested_by"]),
        }
        for child in data["down"]:
            edges.append({"from": nid, "to": child})

    nodes_js = json.dumps(nodes_json, indent=None)

    # Level stats for dashboard
    level_stats = []
    for level in LEVEL_ORDER:
        ids = by_level.get(level, [])
        if not ids:
            continue
        traced = sum(1 for i in ids if nodes[i]["up"] or nodes[i]["down"])
        level_stats.append({
            "level": level,
            "label": LEVEL_LABELS.get(level, level),
            "count": len(ids),
            "traced": traced,
            "color": LEVEL_COLORS.get(level, "#666"),
        })

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Traceability Explorer — foxBMS POSIX</title>
<style>
:root {{
    --bg: #0d1117; --bg2: #161b22; --bg3: #21262d;
    --text: #c9d1d9; --text2: #8b949e; --heading: #f0f6fc;
    --accent: #58a6ff; --border: #30363d;
    --green: #3fb950; --red: #f85149; --yellow: #d29922;
    --font: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    --mono: 'Consolas', monospace;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: var(--font); background: var(--bg); color: var(--text); }}

/* Header */
.header {{
    background: var(--bg2); border-bottom: 1px solid var(--border);
    padding: 16px 24px; display: flex; align-items: center; gap: 24px;
}}
.header h1 {{ color: var(--heading); font-size: 18px; }}
.header a {{ color: var(--accent); text-decoration: none; font-size: 13px; }}
#search {{
    padding: 6px 12px; background: var(--bg3); border: 1px solid var(--border);
    border-radius: 4px; color: var(--text); font-size: 13px; width: 250px; outline: none;
}}
#search:focus {{ border-color: var(--accent); }}

/* Dashboard */
.dashboard {{
    display: flex; gap: 12px; padding: 16px 24px; flex-wrap: wrap;
    border-bottom: 1px solid var(--border); background: var(--bg2);
}}
.stat-card {{
    background: var(--bg3); border: 1px solid var(--border); border-radius: 6px;
    padding: 10px 14px; min-width: 100px; cursor: pointer; transition: border-color 0.15s;
}}
.stat-card:hover {{ border-color: var(--accent); }}
.stat-card.active {{ border-color: var(--accent); background: rgba(88,166,255,0.1); }}
.stat-card .label {{ font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px; }}
.stat-card .count {{ font-size: 22px; font-weight: 700; color: var(--heading); }}
.stat-card .bar {{ height: 3px; border-radius: 2px; margin-top: 4px; background: var(--bg); }}
.stat-card .bar-fill {{ height: 100%; border-radius: 2px; }}

/* Main layout */
.main {{ display: flex; height: calc(100vh - 140px); }}

/* Left: requirement list */
.req-list {{
    width: 320px; overflow-y: auto; border-right: 1px solid var(--border);
    padding: 8px 0; flex-shrink: 0;
}}
.level-group h3 {{
    font-size: 11px; text-transform: uppercase; letter-spacing: 0.8px;
    padding: 10px 14px 4px; position: sticky; top: 0; background: var(--bg); z-index: 1;
}}
.req-item {{
    padding: 4px 14px 4px 22px; font-size: 13px; font-family: var(--mono);
    cursor: pointer; border-left: 3px solid transparent;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}}
.req-item:hover {{ background: var(--bg2); }}
.req-item.selected {{ background: var(--bg3); border-left-color: var(--accent); color: var(--accent); }}
.req-item.orphan {{ color: var(--red); }}
.req-item.partial {{ color: var(--yellow); }}
.req-item.full {{ color: var(--green); }}
.req-item.hidden {{ display: none; }}

/* Right: detail panel */
.detail {{
    flex: 1; padding: 24px; overflow-y: auto;
}}
.detail h2 {{ color: var(--heading); font-size: 20px; margin-bottom: 16px; }}
.detail .meta {{ font-size: 13px; color: var(--text2); margin-bottom: 16px; }}
.trace-section {{ margin-bottom: 20px; }}
.trace-section h3 {{ font-size: 13px; text-transform: uppercase; color: var(--text2); margin-bottom: 8px; letter-spacing: 0.5px; }}
.trace-link {{
    display: inline-block; padding: 4px 10px; margin: 3px; border-radius: 4px;
    font-family: var(--mono); font-size: 13px; cursor: pointer;
    border: 1px solid var(--border); background: var(--bg2); color: var(--text);
    text-decoration: none; transition: all 0.15s;
}}
.trace-link:hover {{ border-color: var(--accent); color: var(--accent); }}
.trace-link.up {{ border-left: 3px solid #3498db; }}
.trace-link.down {{ border-left: 3px solid #2ecc71; }}
.trace-link.test {{ border-left: 3px solid #1abc9c; }}
.empty-state {{
    color: var(--text2); font-size: 14px; margin-top: 120px; text-align: center;
}}
.empty-state .big {{ font-size: 48px; margin-bottom: 16px; }}

/* Chain visualization */
.chain {{ margin: 16px 0; padding: 16px; background: var(--bg2); border-radius: 6px; border: 1px solid var(--border); }}
.chain-row {{ display: flex; align-items: center; gap: 8px; margin: 4px 0; flex-wrap: wrap; }}
.chain-arrow {{ color: var(--text2); font-size: 16px; }}
.chain-node {{
    padding: 3px 8px; border-radius: 3px; font-family: var(--mono); font-size: 12px;
    cursor: pointer; border: 1px solid var(--border);
}}
.chain-node:hover {{ border-color: var(--accent); }}
.chain-node.current {{ font-weight: 700; box-shadow: 0 0 0 2px var(--accent); }}
</style>
</head>
<body>

<div class="header">
    <h1>Traceability Explorer</h1>
    <input type="text" id="search" placeholder="Search requirement ID...">
    <a href="index.html">Back to Docs</a>
    <span style="color:var(--text2);font-size:12px;margin-left:auto">{total} requirements | {len(orphans)} orphans | {len(edges)} links</span>
</div>

<div class="dashboard" id="dashboard">
    {"".join(f'''
    <div class="stat-card" data-level="{s['level']}" onclick="filterLevel('{s['level']}')">
        <div class="label" style="color:{s['color']}">{s['label']}</div>
        <div class="count">{s['count']}</div>
        <div class="bar"><div class="bar-fill" style="width:{s['traced']*100//max(s['count'],1)}%;background:{s['color']}"></div></div>
    </div>''' for s in level_stats)}
</div>

<div class="main">
    <div class="req-list" id="reqList">
        {"".join(_build_level_html(level, by_level.get(level, []), nodes) for level in LEVEL_ORDER if by_level.get(level))}
    </div>
    <div class="detail" id="detail">
        <div class="empty-state">
            <div class="big">Click a requirement</div>
            Select any requirement ID on the left to see its full traceability chain — parents, children, and test coverage.
        </div>
    </div>
</div>

<script>
const NODES = {nodes_js};
const LEVEL_COLORS = {json.dumps(LEVEL_COLORS)};

let activeLevel = null;

function filterLevel(level) {{
    const cards = document.querySelectorAll('.stat-card');
    cards.forEach(c => c.classList.toggle('active', c.dataset.level === level && activeLevel !== level));
    activeLevel = activeLevel === level ? null : level;

    document.querySelectorAll('.req-item').forEach(el => {{
        if (!activeLevel) {{ el.classList.remove('hidden'); return; }}
        const node = NODES[el.dataset.id];
        el.classList.toggle('hidden', node && node.level !== activeLevel);
    }});
    document.querySelectorAll('.level-group').forEach(g => {{
        const items = g.querySelectorAll('.req-item:not(.hidden)');
        g.style.display = items.length ? '' : 'none';
    }});
}}

function selectReq(id) {{
    document.querySelectorAll('.req-item').forEach(el => el.classList.remove('selected'));
    const el = document.querySelector(`.req-item[data-id="${{id}}"]`);
    if (el) {{ el.classList.add('selected'); el.scrollIntoView({{block:'nearest'}}); }}

    const node = NODES[id];
    if (!node) return;

    const detail = document.getElementById('detail');
    let html = `<h2>${{id}}</h2>`;
    html += `<div class="meta">Level: <strong style="color:${{LEVEL_COLORS[node.level] || '#666'}}">${{node.level}}</strong> | File: ${{node.file}}</div>`;

    // Build full chain (walk up to roots, walk down to leaves)
    const chain = buildChain(id);
    if (chain.length > 0) {{
        html += `<div class="chain"><strong>Trace Chain</strong>`;
        chain.forEach(path => {{
            html += `<div class="chain-row">`;
            path.forEach((nid, i) => {{
                if (i > 0) html += `<span class="chain-arrow">→</span>`;
                const color = LEVEL_COLORS[NODES[nid]?.level] || '#666';
                const isCurrent = nid === id ? 'current' : '';
                html += `<span class="chain-node ${{isCurrent}}" style="color:${{color}};border-color:${{color}}" onclick="selectReq('${{nid}}')">${{nid}}</span>`;
            }});
            html += `</div>`;
        }});
        html += `</div>`;
    }}

    // Traces up
    if (node.up.length) {{
        html += `<div class="trace-section"><h3>Traces Up (derives from)</h3>`;
        node.up.forEach(uid => {{
            html += `<span class="trace-link up" onclick="selectReq('${{uid}}')">${{uid}}</span>`;
        }});
        html += `</div>`;
    }}

    // Traces down
    if (node.down.length) {{
        html += `<div class="trace-section"><h3>Traces Down (derived by)</h3>`;
        node.down.forEach(did => {{
            html += `<span class="trace-link down" onclick="selectReq('${{did}}')">${{did}}</span>`;
        }});
        html += `</div>`;
    }}

    // Tested by
    if (node.tested_by.length) {{
        html += `<div class="trace-section"><h3>Tested By</h3>`;
        node.tested_by.forEach(t => {{
            html += `<span class="trace-link test">${{t}}</span>`;
        }});
        html += `</div>`;
    }}

    if (!node.up.length && !node.down.length && !node.tested_by.length) {{
        html += `<div style="color:var(--red);margin-top:16px">Orphan — no upstream or downstream links found.</div>`;
    }}

    detail.innerHTML = html;
}}

function buildChain(id) {{
    // Find all paths from root ancestors to leaf descendants through this node
    const paths = [];

    // Walk up to find roots
    function findRoots(nid, visited) {{
        const node = NODES[nid];
        if (!node || visited.has(nid)) return [nid];
        visited.add(nid);
        if (!node.up.length) return [nid];
        const roots = [];
        node.up.forEach(p => roots.push(...findRoots(p, visited)));
        return [...new Set(roots)];
    }}

    // Walk down from a node collecting one path
    function walkDown(nid, path, visited, maxDepth) {{
        if (maxDepth <= 0 || visited.has(nid)) return;
        visited.add(nid);
        path.push(nid);
        const node = NODES[nid];
        if (!node || !node.down.length) {{
            paths.push([...path]);
        }} else {{
            // Only follow first 3 children to avoid explosion
            node.down.slice(0, 3).forEach(child => walkDown(child, path, new Set(visited), maxDepth - 1));
        }}
        path.pop();
    }}

    // Walk up from id to find roots, then walk down through id
    const roots = findRoots(id, new Set());
    const uniqueRoots = [...new Set(roots)].slice(0, 3);

    uniqueRoots.forEach(root => {{
        walkDown(root, [], new Set(), 8);
    }});

    // Filter to only paths that contain our target id
    const relevant = paths.filter(p => p.includes(id)).slice(0, 5);
    return relevant;
}}

// Search
document.getElementById('search').addEventListener('input', function(e) {{
    const q = e.target.value.toUpperCase();
    document.querySelectorAll('.req-item').forEach(el => {{
        el.classList.toggle('hidden', q && !el.dataset.id.includes(q));
    }});
    document.querySelectorAll('.level-group').forEach(g => {{
        const items = g.querySelectorAll('.req-item:not(.hidden)');
        g.style.display = items.length ? '' : 'none';
    }});
}});

// Keyboard navigation
document.addEventListener('keydown', function(e) {{
    if (e.target.id === 'search') return;
    const selected = document.querySelector('.req-item.selected');
    if (!selected) return;
    let next;
    if (e.key === 'ArrowDown') next = selected.nextElementSibling || selected.parentElement.nextElementSibling?.querySelector('.req-item');
    if (e.key === 'ArrowUp') next = selected.previousElementSibling || selected.parentElement.previousElementSibling?.querySelector('.req-item:last-child');
    if (next && next.classList.contains('req-item')) {{ e.preventDefault(); selectReq(next.dataset.id); }}
}});
</script>
</body>
</html>"""
    return html


def _build_level_html(level, ids, nodes):
    color = LEVEL_COLORS.get(level, "#666")
    label = LEVEL_LABELS.get(level, level)
    html = f'<div class="level-group"><h3 style="color:{color}">{label} ({len(ids)})</h3>\n'
    for nid in sorted(ids):
        d = nodes[nid]
        status = "full" if d["up"] and d["down"] else "partial" if d["up"] or d["down"] else "orphan"
        html += f'<div class="req-item {status}" data-id="{nid}" onclick="selectReq(\'{nid}\')">{nid}</div>\n'
    html += '</div>\n'
    return html


def main():
    print("Scanning documents...")
    nodes = scan_docs()
    print(f"Found {len(nodes)} requirement IDs")

    # Group by level for HTML
    by_level = defaultdict(list)
    for nid, data in sorted(nodes.items()):
        by_level[data["level"]].append(nid)

    edges = []
    for nid, data in nodes.items():
        for child in data["down"]:
            edges.append({"from": nid, "to": child})

    print(f"Building HTML ({len(edges)} links)...")
    html = build_html(nodes)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"Built: {OUTPUT}")


if __name__ == "__main__":
    main()
