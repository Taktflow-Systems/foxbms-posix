#!/usr/bin/env python3
"""
Build multi-page HTML documentation site from foxbms-posix markdown files.

Generates one HTML per document + an index page with navigation.
All pages share a common sidebar and dark theme.

Usage:
    python scripts/build-html.py                    # Default: docs/site/
    python scripts/build-html.py --output path/     # Custom output dir
"""

import argparse
import re
from pathlib import Path
from collections import defaultdict

import markdown
from markdown.extensions.tables import TableExtension
from markdown.extensions.fenced_code import FencedCodeExtension
from markdown.extensions.toc import TocExtension

ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "docs"
DEFAULT_OUTPUT = DOCS_DIR / "site"

# ---------------------------------------------------------------------------
# Traceability graph (built once, used to annotate every page)
# ---------------------------------------------------------------------------

TRACE_DOCS_DIR = ROOT / "docs" / "aspice-cl2"
TRACE_SRC_DIR = ROOT / "src"

ALL_ID_RE = re.compile(
    r"\b(STKH-REQ-\d+[A-Za-z]?|SYS-REQ-\d+[A-Za-z]?|SW-REQ-\d+[A-Za-z]?|"
    r"SSR-\d+|SG-\d+|HZ-\d+|FSR-\d+|TSR-\d+|FM-\d+|UT-\d+|IT-\d+|QT-\d+)\b"
)

LEVEL_ORDER = ["STKH-REQ","SYS-REQ","SG","HZ","FSR","TSR","SW-REQ","SSR","FM","UT","IT","QT"]

LEVEL_COLORS = {
    "STKH-REQ":"#9b59b6","SYS-REQ":"#3498db","SG":"#e74c3c","HZ":"#e74c3c",
    "FSR":"#e67e22","TSR":"#e67e22","SW-REQ":"#2ecc71","SSR":"#f39c12",
    "FM":"#95a5a6","UT":"#1abc9c","IT":"#1abc9c","QT":"#1abc9c",
}

def classify_id(rid):
    for prefix in LEVEL_ORDER:
        if rid.startswith(prefix + "-"):
            return prefix
    return "UNKNOWN"

def build_trace_graph():
    """Scan ASPICE docs and build {id: {up:set, down:set}} graph."""
    nodes = defaultdict(lambda: {"up": set(), "down": set()})

    for md_file in sorted(TRACE_DOCS_DIR.rglob("*.md")):
        text = md_file.read_text(encoding="utf-8", errors="replace")
        for line in text.split("\n"):
            if "|" not in line:
                continue
            ids_in_row = [m.group(1) for m in ALL_ID_RE.finditer(line)]
            if len(ids_in_row) >= 2:
                primary = ids_in_row[0]
                p_level = classify_id(primary)
                p_idx = LEVEL_ORDER.index(p_level) if p_level in LEVEL_ORDER else -1
                for other in ids_in_row[1:]:
                    if other == primary:
                        continue
                    o_level = classify_id(other)
                    o_idx = LEVEL_ORDER.index(o_level) if o_level in LEVEL_ORDER else -1
                    # Ensure both exist in graph
                    _ = nodes[primary]
                    _ = nodes[other]
                    if p_idx > o_idx:
                        nodes[primary]["up"].add(other)
                        nodes[other]["down"].add(primary)
                    elif p_idx < o_idx:
                        nodes[primary]["down"].add(other)
                        nodes[other]["up"].add(primary)

    return dict(nodes)

# Build once at import time
TRACE_GRAPH = None

SECTIONS = [
    ("Project Overview", [
        ("README", ROOT / "README.md"),
        ("STATUS", ROOT / "STATUS.md"),
        ("PLAN", ROOT / "PLAN.md"),
    ]),
    ("Project Documentation", [
        ("Gap Analysis", DOCS_DIR / "project" / "gap-analysis.md"),
        ("Coverage Matrix", DOCS_DIR / "project" / "coverage.md"),
        ("Troubleshooting", DOCS_DIR / "project" / "troubleshooting.md"),
        ("Build Guide", DOCS_DIR / "project" / "build-guide.md"),
        ("Integration Notes", DOCS_DIR / "project" / "integration-notes.md"),
        ("10-Role Audit v1", DOCS_DIR / "project" / "audit-10-role.md"),
        ("10-Role Audit v2", DOCS_DIR / "project" / "audit-10-role-v2.md"),

        ("Lessons Learned", DOCS_DIR / "project" / "lessons-learned.md"),
    ]),
    ("ASPICE CL2 — Assessment", [
        ("Assessment Scope", DOCS_DIR / "aspice-cl2" / "00-assessment" / "assessment-scope.md"),
        ("CL2 Gap Assessment", DOCS_DIR / "aspice-cl2" / "00-assessment" / "cl2-gap-assessment.md"),
        ("Traceability Guide", DOCS_DIR / "aspice-cl2" / "00-assessment" / "traceability-guide.md"),
        ("Traceability Matrix", DOCS_DIR / "aspice-cl2" / "00-assessment" / "traceability-matrix-generated.md"),
    ]),
    ("ASPICE CL2 — Management", [
        ("MAN.3 Project Plan", DOCS_DIR / "aspice-cl2" / "01-MAN.3-project-management" / "project-plan.md"),
        ("SUP.1 QA Plan", DOCS_DIR / "aspice-cl2" / "14-SUP.1-quality-assurance" / "qa-plan.md"),
        ("SUP.8 CM Plan", DOCS_DIR / "aspice-cl2" / "15-SUP.8-configuration-management" / "cm-plan.md"),
        ("SUP.9 Problem Resolution", DOCS_DIR / "aspice-cl2" / "16-SUP.9-problem-resolution" / "problem-resolution-process.md"),
        ("SUP.10 Change Request", DOCS_DIR / "aspice-cl2" / "17-SUP.10-change-request" / "change-request-process.md"),
    ]),
    ("ASPICE CL2 — System", [
        ("SYS.1 Stakeholder Reqs", DOCS_DIR / "aspice-cl2" / "03-SYS.1-stakeholder-requirements" / "stakeholder-requirements.md"),
        ("SYS.2 System Reqs", DOCS_DIR / "aspice-cl2" / "04-SYS.2-system-requirements" / "SYS.2-system-requirements.md"),
        ("SYS.3 System Architecture", DOCS_DIR / "aspice-cl2" / "05-SYS.3-system-architecture" / "SYS.3-system-architecture.md"),
        ("SYS.4 System Integration Test", DOCS_DIR / "aspice-cl2" / "06-SYS.4-system-integration-test" / "system-integration-test-spec.md"),
        ("SYS.5 System Qualification", DOCS_DIR / "aspice-cl2" / "07-SYS.5-system-qualification-test" / "system-qualification-test-spec.md"),
    ]),
    ("ASPICE CL2 — Software", [
        ("SWE.1 Software Reqs", DOCS_DIR / "aspice-cl2" / "08-SWE.1-software-requirements" / "SWE.1-software-requirements.md"),
        ("SWE.2 SW Architecture", DOCS_DIR / "aspice-cl2" / "09-SWE.2-software-architecture" / "SWE.2-software-architecture.md"),
        ("SWE.3 Detailed Design", DOCS_DIR / "aspice-cl2" / "10-SWE.3-software-detailed-design" / "SWE.3-software-detailed-design.md"),
        ("SWE.4 Unit Tests", DOCS_DIR / "aspice-cl2" / "11-SWE.4-software-unit-verification" / "SWE.4-unit-test-spec.md"),
        ("SWE.5 Integration Tests", DOCS_DIR / "aspice-cl2" / "12-SWE.5-software-integration-test" / "SWE.5-integration-test-spec.md"),
        ("SWE.6 Qualification Tests", DOCS_DIR / "aspice-cl2" / "13-SWE.6-software-qualification-test" / "SWE.6-qualification-test-spec.md"),
    ]),
    ("ISO 26262 — Safety", [
        ("Part 3: HARA", DOCS_DIR / "aspice-cl2" / "18-safety" / "part3-concept" / "ISO26262-part3-HARA.md"),
        ("Part 4: FSC", DOCS_DIR / "aspice-cl2" / "18-safety" / "part4-system" / "ISO26262-part4-FSC.md"),
        ("Part 4: TSC", DOCS_DIR / "aspice-cl2" / "18-safety" / "part4-system" / "ISO26262-part4-TSC.md"),
        ("Part 5: HSI", DOCS_DIR / "aspice-cl2" / "18-safety" / "part5-hardware" / "ISO26262-part5-hardware-software-interface.md"),
        ("Part 5: FMEA", DOCS_DIR / "aspice-cl2" / "18-safety" / "part5-hardware" / "ISO26262-part5-FMEA.md"),
        ("Part 6: Safety Reqs", DOCS_DIR / "aspice-cl2" / "18-safety" / "part6-software" / "ISO26262-part6-safety-requirements.md"),
        ("Part 6: FTTI", DOCS_DIR / "aspice-cl2" / "18-safety" / "part6-software" / "ISO26262-part6-FTTI-calculations.md"),
        ("Part 8: Traceability", DOCS_DIR / "aspice-cl2" / "18-safety" / "part8-supporting" / "ISO26262-part8-traceability.md"),
        ("Part 9: ASIL Decomp", DOCS_DIR / "aspice-cl2" / "18-safety" / "part9-asil" / "ISO26262-part9-ASIL-decomposition.md"),
    ]),
    ("foxBMS Reference", [
        ("Index", DOCS_DIR / "foxbms-upstream" / "INDEX.md"),
        ("ASPICE Extraction", DOCS_DIR / "foxbms-upstream" / "aspice-extraction.md"),
        ("Modules Index", DOCS_DIR / "foxbms-upstream" / "software" / "modules-index.md"),
        ("BMS State Machine", DOCS_DIR / "foxbms-upstream" / "software" / "application" / "bms.md"),
        ("DIAG Handler", DOCS_DIR / "foxbms-upstream" / "software" / "engine" / "diag.md"),
        ("Database", DOCS_DIR / "foxbms-upstream" / "software" / "engine" / "database.md"),
        ("CAN Module", DOCS_DIR / "foxbms-upstream" / "software" / "driver" / "can.md"),
        ("FTASK", DOCS_DIR / "foxbms-upstream" / "software" / "task" / "ftask.md"),
        ("SOA", DOCS_DIR / "foxbms-upstream" / "software" / "application" / "soa.md"),
        ("Balancing", DOCS_DIR / "foxbms-upstream" / "software" / "application" / "balancing.md"),
        ("SBC", DOCS_DIR / "foxbms-upstream" / "software" / "driver" / "sbc.md"),
        ("Precharging", DOCS_DIR / "foxbms-upstream" / "system" / "precharging.md"),
        ("Interlock", DOCS_DIR / "foxbms-upstream" / "software" / "driver" / "interlock.md"),
        ("DBC Signals", DOCS_DIR / "foxbms-upstream" / "dbc" / "foxbms-signals-summary.md"),
    ]),
    ("Business & Service", [
        ("Reusable Pipeline", DOCS_DIR / "business" / "pipeline-reusable.md"),
        ("ML Integration", DOCS_DIR / "business" / "proposal-ml-integration.md"),
        ("ML Feasibility", DOCS_DIR / "business" / "feasibility-ml-integration.md"),
        ("HIL Data Plan", DOCS_DIR / "business" / "plan-hil-data-capture.md"),
    ]),
]

CSS = """
:root {
    --bg: #0d1117; --bg2: #161b22; --bg3: #21262d;
    --text: #c9d1d9; --text2: #8b949e; --heading: #f0f6fc;
    --accent: #58a6ff; --accent2: #79c0ff; --border: #30363d;
    --green: #3fb950; --red: #f85149; --yellow: #d29922;
    --sidebar-w: 280px;
    --font: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    --mono: 'Consolas', 'Fira Code', monospace;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
html { scroll-behavior: smooth; }
body { font-family: var(--font); background: var(--bg); color: var(--text); line-height: 1.6; display: flex; min-height: 100vh; }

/* Sidebar */
nav.sidebar {
    position: fixed; left: 0; top: 0; bottom: 0; width: var(--sidebar-w);
    background: var(--bg2); border-right: 1px solid var(--border);
    overflow-y: auto; padding: 0; z-index: 100; font-size: 13px;
}
.logo { padding: 16px; font-size: 15px; font-weight: 700; color: var(--heading); border-bottom: 1px solid var(--border); }
.logo small { display: block; font-size: 11px; color: var(--text2); font-weight: 400; margin-top: 2px; }
nav.sidebar h3 {
    color: var(--accent); font-size: 11px; padding: 12px 14px 4px;
    text-transform: uppercase; letter-spacing: 0.8px; font-weight: 600;
}
nav.sidebar a {
    display: block; padding: 3px 14px 3px 22px; color: var(--text2);
    text-decoration: none; border-left: 2px solid transparent;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
nav.sidebar a:hover { color: var(--text); background: var(--bg3); border-left-color: var(--accent); }
nav.sidebar a.active { color: var(--accent); border-left-color: var(--accent); background: var(--bg3); }
#search {
    width: calc(100% - 24px); margin: 10px 12px; padding: 6px 10px;
    background: var(--bg3); border: 1px solid var(--border); border-radius: 4px;
    color: var(--text); font-size: 12px; outline: none;
}
#search:focus { border-color: var(--accent); }
.stats { padding: 8px 14px; font-size: 10px; color: var(--text2); border-top: 1px solid var(--border); }

/* Main */
main { margin-left: var(--sidebar-w); flex: 1; max-width: 920px; padding: 32px 48px 80px; }

/* Breadcrumb */
.breadcrumb { font-size: 12px; color: var(--text2); margin-bottom: 16px; }
.breadcrumb a { color: var(--accent); text-decoration: none; }
.breadcrumb a:hover { text-decoration: underline; }

/* Content */
.content h1 { color: var(--heading); font-size: 26px; margin: 20px 0 12px; padding-bottom: 6px; border-bottom: 1px solid var(--border); }
.content h2 { color: var(--heading); font-size: 20px; margin: 18px 0 10px; }
.content h3 { color: var(--heading); font-size: 16px; margin: 14px 0 8px; }
.content h4 { color: var(--heading); font-size: 14px; margin: 10px 0 6px; }
.content p { margin: 8px 0; }
.content a { color: var(--accent); text-decoration: none; }
.content a:hover { text-decoration: underline; }
.content strong { color: var(--heading); }
.content ul, .content ol { padding-left: 24px; margin: 8px 0; }
.content li { margin: 3px 0; }
.content blockquote { border-left: 3px solid var(--accent); padding: 8px 16px; margin: 12px 0; background: var(--bg2); border-radius: 0 6px 6px 0; color: var(--text2); }
.content table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 13px; }
.content th { background: var(--bg3); color: var(--heading); padding: 7px 10px; text-align: left; border: 1px solid var(--border); font-weight: 600; }
.content td { padding: 5px 10px; border: 1px solid var(--border); vertical-align: top; }
.content tr:hover td { background: var(--bg2); }
.content code { font-family: var(--mono); font-size: 13px; background: var(--bg3); padding: 1px 5px; border-radius: 3px; color: var(--accent); }
.content pre { background: var(--bg2); border: 1px solid var(--border); border-radius: 6px; padding: 14px; overflow-x: auto; margin: 12px 0; font-size: 13px; }
.content pre code { background: none; padding: 0; color: var(--text); }
.hitl-lock { border-left: 3px solid var(--yellow); background: rgba(210,153,34,0.05); padding: 3px 10px; margin: 6px 0; font-size: 11px; color: var(--yellow); }

/* Trace badges */
.trace-id { position: relative; display: inline; }
.trace-badges {
    display: none; position: absolute; left: 0; top: 100%; z-index: 50;
    background: var(--bg2); border: 1px solid var(--border); border-radius: 6px;
    padding: 8px 10px; min-width: 200px; max-width: 400px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.4); font-size: 12px; line-height: 1.8;
}
.trace-id:hover .trace-badges, .trace-badges:hover { display: block; }
.trace-badges .tb-section { margin-bottom: 4px; }
.trace-badges .tb-label { color: var(--text2); font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px; }
.trace-badges a.tb-link {
    display: inline-block; padding: 1px 6px; margin: 1px 2px; border-radius: 3px;
    font-family: var(--mono); font-size: 11px; text-decoration: none;
    border: 1px solid var(--border); transition: all 0.15s;
}
.trace-badges a.tb-link:hover { border-color: var(--accent); color: var(--accent); }
.trace-badges a.tb-up { border-left: 2px solid #3498db; color: #79c0ff; }
.trace-badges a.tb-down { border-left: 2px solid #2ecc71; color: #7ee8a8; }

/* Index page cards */
.card-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin: 16px 0; }
.card {
    background: var(--bg2); border: 1px solid var(--border); border-radius: 8px;
    padding: 16px; transition: border-color 0.15s;
}
.card:hover { border-color: var(--accent); }
.card h3 { color: var(--accent); font-size: 14px; margin-bottom: 8px; }
.card a { color: var(--text); text-decoration: none; display: block; padding: 2px 0; font-size: 13px; }
.card a:hover { color: var(--accent); }
.card .count { font-size: 11px; color: var(--text2); margin-top: 6px; }

/* Nav buttons */
.nav-buttons { display: flex; justify-content: space-between; margin-top: 48px; padding-top: 16px; border-top: 1px solid var(--border); }
.nav-buttons a {
    color: var(--accent); text-decoration: none; font-size: 13px;
    padding: 8px 16px; border: 1px solid var(--border); border-radius: 6px;
    background: var(--bg2);
}
.nav-buttons a:hover { background: var(--bg3); border-color: var(--accent); }

@media print { nav.sidebar { display: none; } main { margin-left: 0; max-width: 100%; } }
"""

JS_SEARCH = """
document.getElementById('search')?.addEventListener('input', function(e) {
    const q = e.target.value.toLowerCase();
    document.querySelectorAll('nav.sidebar a[href]').forEach(a => {
        a.style.display = a.textContent.toLowerCase().includes(q) || q === '' ? '' : 'none';
    });
    document.querySelectorAll('nav.sidebar h3').forEach(h => {
        let el = h.nextElementSibling, any = false;
        while (el && el.tagName === 'A') { if (el.style.display !== 'none') any = true; el = el.nextElementSibling; }
        h.style.display = any || q === '' ? '' : 'none';
    });
});
"""


def slugify(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def _make_trace_popup(req_id, page_lookup):
    """Build HTML for a trace badge popup showing up/down links."""
    global TRACE_GRAPH
    if TRACE_GRAPH is None or req_id not in TRACE_GRAPH:
        return req_id  # No trace data, return plain text

    node = TRACE_GRAPH[req_id]
    up_ids = sorted(node["up"])
    down_ids = sorted(node["down"])

    if not up_ids and not down_ids:
        return req_id  # Orphan, no popup needed

    color = LEVEL_COLORS.get(classify_id(req_id), "#666")

    popup = '<span class="trace-badges">'
    if up_ids:
        popup += '<div class="tb-section"><span class="tb-label">&#x2191; Traces Up</span><br>'
        for uid in up_ids[:8]:  # limit to 8 to avoid huge popups
            href = page_lookup.get(uid, "traceability.html")
            popup += f'<a class="tb-link tb-up" href="{href}">{uid}</a>'
        if len(up_ids) > 8:
            popup += f'<span style="color:var(--text2)"> +{len(up_ids)-8} more</span>'
        popup += '</div>'
    if down_ids:
        popup += '<div class="tb-section"><span class="tb-label">&#x2193; Traces Down</span><br>'
        for did in down_ids[:8]:
            href = page_lookup.get(did, "traceability.html")
            popup += f'<a class="tb-link tb-down" href="{href}">{did}</a>'
        if len(down_ids) > 8:
            popup += f'<span style="color:var(--text2)"> +{len(down_ids)-8} more</span>'
        popup += '</div>'
    popup += '</span>'

    return (f'<span class="trace-id" style="border-bottom:1px dashed {color};cursor:help">'
            f'<a href="traceability.html" style="color:{color};text-decoration:none">{req_id}</a>'
            f'{popup}</span>')


def _annotate_trace_links(html, page_lookup):
    """Post-process rendered HTML to add trace popups to requirement IDs."""
    # Only annotate IDs that are NOT inside <a> tags or <code> blocks
    def replacer(m):
        req_id = m.group(1)
        return _make_trace_popup(req_id, page_lookup)

    # Split by HTML tags to avoid replacing inside href="" or <code>
    parts = re.split(r'(<[^>]+>)', html)
    in_code = False
    in_a = False
    result = []
    for part in parts:
        if part.startswith('<'):
            lower = part.lower()
            if lower.startswith('<code') or lower.startswith('<pre'):
                in_code = True
            elif lower.startswith('</code') or lower.startswith('</pre'):
                in_code = False
            elif lower.startswith('<a '):
                in_a = True
            elif lower.startswith('</a'):
                in_a = False
            result.append(part)
        else:
            if in_code or in_a:
                result.append(part)
            else:
                result.append(ALL_ID_RE.sub(replacer, part))
    return ''.join(result)


def render_md(text, page_lookup=None):
    text = re.sub(r'<!--\s*HITL-LOCK\s+START:([^>]+)\s*-->', r'<div class="hitl-lock">🔒 HITL-LOCK: \1</div>', text)
    text = re.sub(r'<!--\s*HITL-LOCK\s+END:[^>]+\s*-->', '', text)
    md = markdown.Markdown(extensions=[TableExtension(), FencedCodeExtension(), TocExtension(permalink=False)])
    html = md.convert(text)
    if page_lookup is not None and TRACE_GRAPH:
        html = _annotate_trace_links(html, page_lookup)
    return html


def build_sidebar(sections, all_pages, current_slug=None):
    html = '<div class="logo">foxBMS POSIX vECU<small>Documentation Site</small></div>\n'
    html += '<input type="text" id="search" placeholder="Search...">\n'
    html += f'<a href="index.html" {"class=active" if current_slug is None else ""}>Home</a>\n'
    for group_name, docs in sections:
        html += f'<h3>{group_name}</h3>\n'
        for title, filepath in docs:
            slug = slugify(title)
            if not filepath.exists():
                continue
            active = 'class="active"' if slug == current_slug else ''
            html += f'<a href="{slug}.html" {active}>{title}</a>\n'
    html += f'<div class="stats">{len(all_pages)} documents</div>\n'
    return html


def page_html(title, sidebar, body, breadcrumb="", prev_link="", next_link=""):
    nav_buttons = ""
    if prev_link or next_link:
        nav_buttons = '<div class="nav-buttons">'
        nav_buttons += f'<a href="{prev_link[1]}">&larr; {prev_link[0]}</a>' if prev_link else '<span></span>'
        nav_buttons += f'<a href="{next_link[1]}">{next_link[0]} &rarr;</a>' if next_link else '<span></span>'
        nav_buttons += '</div>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — foxBMS POSIX vECU</title>
<style>{CSS}</style>
</head>
<body>
<nav class="sidebar">{sidebar}</nav>
<main>
{breadcrumb}
<div class="content">{body}</div>
{nav_buttons}
</main>
<script>{JS_SEARCH}</script>
</body>
</html>"""


def build():
    global TRACE_GRAPH

    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    # Build traceability graph
    print("Building traceability graph...")
    TRACE_GRAPH = build_trace_graph()
    print(f"  {len(TRACE_GRAPH)} requirement IDs, {sum(len(v['up'])+len(v['down']) for v in TRACE_GRAPH.values())//2} links")

    # Collect all pages in order
    all_pages = []
    for group_name, docs in SECTIONS:
        for title, filepath in docs:
            if filepath.exists():
                all_pages.append((title, filepath, slugify(title), group_name))

    # Build page lookup: requirement ID → which HTML page contains it
    # Scan each page's markdown for IDs defined in it (first column of tables)
    page_lookup = {}
    for title, filepath, slug, group in all_pages:
        text = filepath.read_text(encoding='utf-8', errors='replace')
        for line in text.split("\n"):
            if "|" not in line:
                continue
            cells = [c.strip() for c in line.split("|")]
            if len(cells) >= 3:
                # Check first non-empty cell for a requirement ID
                for cell in cells[1:3]:
                    m = ALL_ID_RE.match(cell.strip())
                    if m:
                        page_lookup[m.group(1)] = f"{slug}.html#{slugify(m.group(1))}"
                        break
    # Fallback: any ID not found gets linked to traceability.html
    print(f"  {len(page_lookup)} IDs mapped to pages")

    # Build index page
    sidebar = build_sidebar(SECTIONS, all_pages, current_slug=None)
    index_body = '<h1>foxBMS POSIX vECU — Documentation</h1>\n'
    index_body += '<p>foxBMS 2 v1.10.0 Battery Management System running as Linux x86-64 process. '
    index_body += f'{len(all_pages)} documents covering ASPICE CL2, ISO 26262 ASIL-D, and project documentation.</p>\n'
    index_body += '<div class="card-grid">\n'
    for group_name, docs in SECTIONS:
        valid = [(t, p) for t, p in docs if p.exists()]
        if not valid:
            continue
        index_body += f'<div class="card"><h3>{group_name}</h3>\n'
        for title, filepath in valid:
            slug = slugify(title)
            index_body += f'<a href="{slug}.html">{title}</a>\n'
        index_body += f'<div class="count">{len(valid)} documents</div></div>\n'
    index_body += '</div>\n'

    (out / "index.html").write_text(page_html("Home", sidebar, index_body), encoding='utf-8')

    # Build each document page
    for i, (title, filepath, slug, group) in enumerate(all_pages):
        sidebar = build_sidebar(SECTIONS, all_pages, current_slug=slug)
        text = filepath.read_text(encoding='utf-8', errors='replace')
        body = render_md(text, page_lookup=page_lookup)
        bc = f'<div class="breadcrumb"><a href="index.html">Home</a> / {group} / {title}</div>'

        prev_link = (all_pages[i - 1][0], f"{all_pages[i - 1][2]}.html") if i > 0 else ""
        next_link = (all_pages[i + 1][0], f"{all_pages[i + 1][2]}.html") if i < len(all_pages) - 1 else ""

        html = page_html(title, sidebar, body, breadcrumb=bc, prev_link=prev_link, next_link=next_link)
        (out / f"{slug}.html").write_text(html, encoding='utf-8')

    print(f"Built {len(all_pages) + 1} HTML pages in {out}/")


if __name__ == '__main__':
    build()
