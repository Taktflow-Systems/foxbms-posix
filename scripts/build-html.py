#!/usr/bin/env python3
"""
Build multi-page HTML documentation site from foxbms-posix markdown files.

Generates one HTML per document + an index page with navigation.
Reference pages share a sidebar and stylesheet.

Usage:
    python scripts/build-html.py                    # Default: docs/site/
    python scripts/build-html.py --output path/     # Custom output dir
    python scripts/build-html.py --refresh-layout   # Keep published document bodies
"""

import argparse
from html import escape
import re
from pathlib import Path
from collections import defaultdict
from shutil import copyfile

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
    r"SSR-\d+|SG-\d+|HZ-\d+|FSR-\d+|TSR-\d+|FM-\d+|"
    r"FI-(?:VOLT|CURR|TEMP|TIMING|PLAUS|RECOV|STATE|COMBO|IMBAL|SENSOR)-\d+|"
    r"UT-\d+|IT-\d+|QT-\d+)\b"
)

LEVEL_ORDER = ["STKH-REQ","SYS-REQ","SG","HZ","FSR","TSR","SW-REQ","SSR","FM","FI","UT","IT","QT"]

LEVEL_COLORS = {
    "STKH-REQ":"#9b59b6","SYS-REQ":"#3498db","SG":"#e74c3c","HZ":"#e74c3c",
    "FSR":"#e67e22","TSR":"#e67e22","SW-REQ":"#2ecc71","SSR":"#f39c12",
    "FM":"#95a5a6","FI":"#e056a0","UT":"#1abc9c","IT":"#1abc9c","QT":"#1abc9c",
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
        ("README", ROOT / "README-foxbms-posix.md"),
        ("STATUS", ROOT / "STATUS.md"),
        ("PLAN", ROOT / "PLAN.md"),
        ("SIL Demo Guide", DOCS_DIR / "SIL-DEMO-GUIDE.md"),
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
        ("Traceability Explorer", DEFAULT_OUTPUT / "traceability.html"),
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
        ("SYS.3 Architecture Views", DEFAULT_OUTPUT / "sys3-portfolio.html"),
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
        ("foxBMS Index", DOCS_DIR / "foxbms-upstream" / "INDEX.md"),
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


def page_slug(title, path):
    return path.stem if path.suffix == '.html' else slugify(title)


def doc_link(title, slug, current_slug=None):
    active = ' aria-current="page"' if slug == current_slug else ''
    return f'<a href="{slug}.html"{active}>{escape(title)}</a>'


def build_sidebar(groups, current_slug):
    html = '<span class="logo">foxBMS POSIX vECU</span>\n'
    html += '<label for="search">Filter documents</label>\n<input type="search" id="search">\n'
    html += doc_link('Documentation index', 'index', current_slug) + '\n'
    for group_name, docs in groups:
        html += f'<div class="sidebar-group"><h2>{escape(group_name)}</h2>\n'
        html += '\n'.join(doc_link(title, slug, current_slug) for title, _, slug, _ in docs)
        html += '\n</div>\n'
    html += '<p class="search-status" id="search-status" role="status"></p>\n'
    return html


def build_index(groups):
    html = '''<h1>foxBMS POSIX documentation</h1>
<p>The POSIX port runs foxBMS 2 v1.10.0 as a virtual ECU on Linux. A battery model sends simulated measurements over SocketCAN. Use the SIL environment to exercise BMS states, CAN interfaces and fault responses.</p>
<p>The engineering records include Automotive SPICE work products, ISO 26262 safety analyses and test specifications. The SIL evidence covers simulated behavior; target hardware and production safety validation are outside its scope.</p>
<nav class="start-links" aria-label="Start here">
<a href="build-guide.html">Build and run locally</a>
<a href="sil-demo-guide.html">SIL demo guide</a>
<a href="https://sil.taktflow-systems.com/bms/">Open SIL demo</a>
<a href="https://github.com/Taktflow-Systems/foxbms-posix">Source repository</a>
</nav>
<h2>Document index</h2>
'''
    for group_name, docs in groups:
        html += f'<section class="doc-group"><h3>{escape(group_name)}</h3><ul>\n'
        html += '\n'.join(f'<li>{doc_link(title, slug)}</li>' for title, _, slug, _ in docs)
        html += '\n</ul></section>\n'
    return html


def page_html(title, sidebar, body, breadcrumb="", prev_link="", next_link=""):
    nav_buttons = ""
    if prev_link or next_link:
        nav_buttons = '<nav class="nav-buttons" aria-label="Adjacent documents">'
        nav_buttons += f'<a href="{prev_link[1]}">&larr; {prev_link[0]}</a>' if prev_link else '<span></span>'
        nav_buttons += f'<a href="{next_link[1]}">{next_link[0]} &rarr;</a>' if next_link else '<span></span>'
        nav_buttons += '</nav>'

    body = re.sub(r'<table(?=[\s>])', '<div class="table-scroll"><table', body)
    body = body.replace('</table>', '</table></div>')

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escape(title)} — foxBMS POSIX vECU</title>
<link rel="stylesheet" href="docs.css">
</head>
<body>
<a class="skip-link" href="#main">Skip to content</a>
<div class="docs-layout">
<details class="sidebar" open>
<summary>Browse documentation</summary>
<nav aria-label="Documentation">{sidebar}</nav>
</details>
<main class="docs-main" id="main" tabindex="-1">
{breadcrumb}
<div class="content">{body}</div>
{nav_buttons}
</main>
</div>
<script src="docs.js"></script>
</body>
</html>"""


def build():
    global TRACE_GRAPH

    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default=str(DEFAULT_OUTPUT))
    parser.add_argument('--refresh-layout', action='store_true',
                        help='Rebuild the index and page layout while retaining published document bodies')
    args = parser.parse_args()

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    if out.resolve() != DEFAULT_OUTPUT.resolve():
        for asset in ('docs.css', 'docs.js', 'sys3-portfolio.html', 'traceability.html'):
            copyfile(DEFAULT_OUTPUT / asset, out / asset)

    # Collect all pages in order
    groups = []
    for group_name, docs in SECTIONS:
        pages = [(title, path, page_slug(title, path), group_name) for title, path in docs if path.exists()]
        if pages:
            groups.append((group_name, pages))
    all_pages = [page for _, pages in groups for page in pages]

    # Build page lookup: requirement ID → which HTML page contains it
    # Scan each page's markdown for IDs defined in it (first column of tables)
    page_lookup = {}
    if not args.refresh_layout:
        TRACE_GRAPH = build_trace_graph()
        print(f"  {len(TRACE_GRAPH)} requirement IDs, {sum(len(v['up'])+len(v['down']) for v in TRACE_GRAPH.values())//2} links")
        for _, filepath, slug, _ in all_pages:
            if filepath.suffix == '.html':
                continue
            for line in filepath.read_text(encoding='utf-8').splitlines():
                if "|" not in line:
                    continue
                cells = line.split("|")
                if len(cells) >= 3:
                    for cell in cells[1:3]:
                        m = ALL_ID_RE.match(cell.strip())
                        if m:
                            page_lookup[m.group(1)] = f"{slug}.html#{slugify(m.group(1))}"
                            break
        print(f"  {len(page_lookup)} IDs mapped to pages")

    # Build index page
    sidebar = build_sidebar(groups, 'index')
    (out / "index.html").write_text(page_html("Documentation index", sidebar, build_index(groups)), encoding='utf-8')

    # Build each document page
    for i, (title, filepath, slug, group) in enumerate(all_pages):
        if filepath.suffix == '.html':
            continue
        sidebar = build_sidebar(groups, slug)
        if args.refresh_layout:
            existing = (out / f"{slug}.html").read_text(encoding='utf-8')
            content = re.search(r'<div class="content">(.*?)</div>\s*(?:<(?:div|nav) class="nav-buttons"|</main>)', existing, re.S)
            if not content:
                parser.error(f'Could not find the published document body in {slug}.html')
            body = re.sub(r'<div class="table-scroll">(<table[\s\S]*?</table>)</div>', r'\1', content[1])
        else:
            body = render_md(filepath.read_text(encoding='utf-8'), page_lookup=page_lookup)
        bc = f'<nav class="breadcrumb" aria-label="Breadcrumb"><a href="index.html">Docs</a> / {escape(group)} / <span aria-current="page">{escape(title)}</span></nav>'

        prev_link = (all_pages[i - 1][0], f"{all_pages[i - 1][2]}.html") if i > 0 else ""
        next_link = (all_pages[i + 1][0], f"{all_pages[i + 1][2]}.html") if i < len(all_pages) - 1 else ""

        html = page_html(title, sidebar, body, breadcrumb=bc, prev_link=prev_link, next_link=next_link)
        (out / f"{slug}.html").write_text(html, encoding='utf-8')

    print(f"Built {len(all_pages) + 1} HTML pages in {out}/")


if __name__ == '__main__':
    build()
