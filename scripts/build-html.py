#!/usr/bin/env python3
"""
Build HTML documentation site from all foxbms-posix markdown files.

Generates a single-page HTML with navigation sidebar and all documents
rendered inline. Pure stdlib + markdown library.

Usage:
    python scripts/build-html.py                    # Default output: docs/site/index.html
    python scripts/build-html.py --output path.html # Custom output
"""

import argparse
import os
import re
from pathlib import Path

import markdown
from markdown.extensions.tables import TableExtension
from markdown.extensions.fenced_code import FencedCodeExtension
from markdown.extensions.toc import TocExtension
from markdown.extensions.codehilite import CodeHiliteExtension

ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "docs"
DEFAULT_OUTPUT = DOCS_DIR / "site" / "index.html"

# Document ordering and grouping
SECTIONS = [
    ("Project Overview", [
        ("README.md", ROOT / "README.md"),
        ("STATUS.md", ROOT / "STATUS.md"),
        ("PLAN.md", ROOT / "PLAN.md"),
    ]),
    ("Project Documentation", [
        ("Gap Analysis", DOCS_DIR / "project" / "gap-analysis.md"),
        ("Coverage Matrix", DOCS_DIR / "project" / "coverage.md"),
        ("Troubleshooting", DOCS_DIR / "project" / "troubleshooting.md"),
        ("Build Guide", DOCS_DIR / "project" / "build-guide.md"),
        ("Integration Notes", DOCS_DIR / "project" / "integration-notes.md"),
        ("10-Role Audit v1", DOCS_DIR / "project" / "audit-10-role.md"),
        ("10-Role Audit v2", DOCS_DIR / "project" / "audit-10-role-v2.md"),
        ("Munich Electrification Mapping", DOCS_DIR / "project" / "munich-electrification-mapping.md"),
        ("Lessons Learned", DOCS_DIR / "project" / "lessons-learned.md"),
    ]),
    ("ASPICE CL2 — Assessment", [
        ("Assessment Scope", DOCS_DIR / "aspice-cl2" / "00-assessment" / "assessment-scope.md"),
        ("CL2 Gap Assessment", DOCS_DIR / "aspice-cl2" / "00-assessment" / "cl2-gap-assessment.md"),
        ("Traceability Guide", DOCS_DIR / "aspice-cl2" / "00-assessment" / "traceability-guide.md"),
        ("Traceability Matrix (auto)", DOCS_DIR / "aspice-cl2" / "00-assessment" / "traceability-matrix-generated.md"),
    ]),
    ("ASPICE CL2 — Management & Support", [
        ("MAN.3 Project Plan", DOCS_DIR / "aspice-cl2" / "01-MAN.3-project-management" / "project-plan.md"),
        ("SUP.1 QA Plan", DOCS_DIR / "aspice-cl2" / "14-SUP.1-quality-assurance" / "qa-plan.md"),
        ("SUP.8 CM Plan", DOCS_DIR / "aspice-cl2" / "15-SUP.8-configuration-management" / "cm-plan.md"),
        ("SUP.9 Problem Resolution", DOCS_DIR / "aspice-cl2" / "16-SUP.9-problem-resolution" / "problem-resolution-process.md"),
        ("SUP.10 Change Request", DOCS_DIR / "aspice-cl2" / "17-SUP.10-change-request" / "change-request-process.md"),
    ]),
    ("ASPICE CL2 — System Engineering", [
        ("SYS.1 Stakeholder Requirements", DOCS_DIR / "aspice-cl2" / "03-SYS.1-stakeholder-requirements" / "stakeholder-requirements.md"),
        ("SYS.2 System Requirements", DOCS_DIR / "aspice-cl2" / "04-SYS.2-system-requirements" / "SYS.2-system-requirements.md"),
        ("SYS.3 System Architecture", DOCS_DIR / "aspice-cl2" / "05-SYS.3-system-architecture" / "SYS.3-system-architecture.md"),
        ("SYS.4 System Integration Test", DOCS_DIR / "aspice-cl2" / "06-SYS.4-system-integration-test" / "system-integration-test-spec.md"),
        ("SYS.5 System Qualification Test", DOCS_DIR / "aspice-cl2" / "07-SYS.5-system-qualification-test" / "system-qualification-test-spec.md"),
    ]),
    ("ASPICE CL2 — Software Engineering", [
        ("SWE.1 Software Requirements", DOCS_DIR / "aspice-cl2" / "08-SWE.1-software-requirements" / "SWE.1-software-requirements.md"),
        ("SWE.2 Software Architecture", DOCS_DIR / "aspice-cl2" / "09-SWE.2-software-architecture" / "SWE.2-software-architecture.md"),
        ("SWE.3 Software Detailed Design", DOCS_DIR / "aspice-cl2" / "10-SWE.3-software-detailed-design" / "SWE.3-software-detailed-design.md"),
        ("SWE.4 Unit Test Spec", DOCS_DIR / "aspice-cl2" / "11-SWE.4-software-unit-verification" / "SWE.4-unit-test-spec.md"),
        ("SWE.5 Integration Test Spec", DOCS_DIR / "aspice-cl2" / "12-SWE.5-software-integration-test" / "SWE.5-integration-test-spec.md"),
        ("SWE.6 Qualification Test Spec", DOCS_DIR / "aspice-cl2" / "13-SWE.6-software-qualification-test" / "SWE.6-qualification-test-spec.md"),
    ]),
    ("ISO 26262 — Safety", [
        ("Part 3: HARA", DOCS_DIR / "aspice-cl2" / "18-safety" / "part3-concept" / "ISO26262-part3-HARA.md"),
        ("Part 4: FSC", DOCS_DIR / "aspice-cl2" / "18-safety" / "part4-system" / "ISO26262-part4-FSC.md"),
        ("Part 4: TSC", DOCS_DIR / "aspice-cl2" / "18-safety" / "part4-system" / "ISO26262-part4-TSC.md"),
        ("Part 5: HSI", DOCS_DIR / "aspice-cl2" / "18-safety" / "part5-hardware" / "ISO26262-part5-hardware-software-interface.md"),
        ("Part 5: FMEA", DOCS_DIR / "aspice-cl2" / "18-safety" / "part5-hardware" / "ISO26262-part5-FMEA.md"),
        ("Part 6: Safety Requirements", DOCS_DIR / "aspice-cl2" / "18-safety" / "part6-software" / "ISO26262-part6-safety-requirements.md"),
        ("Part 6: FTTI Calculations", DOCS_DIR / "aspice-cl2" / "18-safety" / "part6-software" / "ISO26262-part6-FTTI-calculations.md"),
        ("Part 8: Traceability", DOCS_DIR / "aspice-cl2" / "18-safety" / "part8-supporting" / "ISO26262-part8-traceability.md"),
        ("Part 9: ASIL Decomposition", DOCS_DIR / "aspice-cl2" / "18-safety" / "part9-asil" / "ISO26262-part9-ASIL-decomposition.md"),
    ]),
    ("foxBMS Upstream Reference", [
        ("Index", DOCS_DIR / "foxbms-upstream" / "INDEX.md"),
        ("ASPICE Extraction", DOCS_DIR / "foxbms-upstream" / "aspice-extraction.md"),
        ("Modules Index", DOCS_DIR / "foxbms-upstream" / "software" / "modules-index.md"),
        ("BMS State Machine", DOCS_DIR / "foxbms-upstream" / "software" / "application" / "bms.md"),
        ("DIAG Handler", DOCS_DIR / "foxbms-upstream" / "software" / "engine" / "diag.md"),
        ("Database", DOCS_DIR / "foxbms-upstream" / "software" / "engine" / "database.md"),
        ("CAN Module", DOCS_DIR / "foxbms-upstream" / "software" / "driver" / "can.md"),
        ("FTASK (Tasks)", DOCS_DIR / "foxbms-upstream" / "software" / "task" / "ftask.md"),
        ("SOA (Safe Operating Area)", DOCS_DIR / "foxbms-upstream" / "software" / "application" / "soa.md"),
        ("Balancing", DOCS_DIR / "foxbms-upstream" / "software" / "application" / "balancing.md"),
        ("SBC", DOCS_DIR / "foxbms-upstream" / "software" / "driver" / "sbc.md"),
        ("Precharging", DOCS_DIR / "foxbms-upstream" / "system" / "precharging.md"),
        ("Interlock", DOCS_DIR / "foxbms-upstream" / "software" / "driver" / "interlock.md"),
        ("DBC Signals", DOCS_DIR / "foxbms-upstream" / "dbc" / "foxbms-signals-summary.md"),
        ("Safety", DOCS_DIR / "foxbms-upstream" / "general" / "safety.md"),
    ]),
    ("Business & Service", [
        ("Reusable Pipeline", DOCS_DIR / "business" / "pipeline-reusable.md"),
        ("ML Integration Proposal", DOCS_DIR / "business" / "proposal-ml-integration.md"),
        ("ML Feasibility Analysis", DOCS_DIR / "business" / "feasibility-ml-integration.md"),
        ("HIL Data Capture Plan", DOCS_DIR / "business" / "plan-hil-data-capture.md"),
    ]),
    ("Test Documentation", [
        ("Fault Injection Matrix", DOCS_DIR / "test" / "fault-injection-test-matrix.md"),
        ("Fault Injection ASIL-D", DOCS_DIR / "test" / "fault-injection-test-matrix-asild.md"),
    ]),
]

CSS = """
:root {
    --bg: #0d1117;
    --bg-secondary: #161b22;
    --bg-tertiary: #21262d;
    --text: #c9d1d9;
    --text-secondary: #8b949e;
    --text-heading: #f0f6fc;
    --accent: #58a6ff;
    --accent-hover: #79c0ff;
    --border: #30363d;
    --green: #3fb950;
    --red: #f85149;
    --yellow: #d29922;
    --orange: #db6d28;
    --sidebar-width: 300px;
    --font-mono: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'Consolas', monospace;
    --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
    font-family: var(--font-sans);
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
}
/* Sidebar */
nav.sidebar {
    position: fixed;
    left: 0; top: 0; bottom: 0;
    width: var(--sidebar-width);
    background: var(--bg-secondary);
    border-right: 1px solid var(--border);
    overflow-y: auto;
    padding: 16px 0;
    z-index: 100;
    font-size: 13px;
}
nav.sidebar h2 {
    color: var(--accent);
    font-size: 14px;
    padding: 12px 16px 4px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-weight: 600;
}
nav.sidebar a {
    display: block;
    padding: 4px 16px 4px 24px;
    color: var(--text-secondary);
    text-decoration: none;
    border-left: 2px solid transparent;
    transition: all 0.15s;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
nav.sidebar a:hover {
    color: var(--text);
    background: var(--bg-tertiary);
    border-left-color: var(--accent);
}
nav.sidebar .logo {
    padding: 8px 16px 16px;
    font-size: 16px;
    font-weight: 700;
    color: var(--text-heading);
    border-bottom: 1px solid var(--border);
    margin-bottom: 8px;
}
nav.sidebar .stats {
    padding: 8px 16px;
    font-size: 11px;
    color: var(--text-secondary);
    border-top: 1px solid var(--border);
    margin-top: 8px;
}
/* Main content */
main {
    margin-left: var(--sidebar-width);
    max-width: 900px;
    padding: 32px 48px 120px;
}
/* Document sections */
section.doc {
    margin-bottom: 64px;
    padding-top: 24px;
    border-top: 1px solid var(--border);
}
section.doc:first-child { border-top: none; }
.section-group {
    margin-bottom: 16px;
    padding: 8px 16px;
    background: var(--bg-secondary);
    border-radius: 6px;
    border-left: 3px solid var(--accent);
}
.section-group h2 {
    color: var(--accent);
    font-size: 18px;
    margin: 0;
}
/* Markdown content styling */
.content h1 { color: var(--text-heading); font-size: 28px; margin: 24px 0 16px; padding-bottom: 8px; border-bottom: 1px solid var(--border); }
.content h2 { color: var(--text-heading); font-size: 22px; margin: 20px 0 12px; }
.content h3 { color: var(--text-heading); font-size: 18px; margin: 16px 0 8px; }
.content h4 { color: var(--text-heading); font-size: 15px; margin: 12px 0 6px; }
.content p { margin: 8px 0; }
.content a { color: var(--accent); text-decoration: none; }
.content a:hover { color: var(--accent-hover); text-decoration: underline; }
.content strong { color: var(--text-heading); }
.content em { color: var(--text-secondary); }
.content ul, .content ol { padding-left: 24px; margin: 8px 0; }
.content li { margin: 4px 0; }
.content blockquote {
    border-left: 3px solid var(--accent);
    padding: 8px 16px;
    margin: 12px 0;
    background: var(--bg-secondary);
    border-radius: 0 6px 6px 0;
    color: var(--text-secondary);
}
/* Tables */
.content table {
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0;
    font-size: 13px;
}
.content th {
    background: var(--bg-tertiary);
    color: var(--text-heading);
    padding: 8px 12px;
    text-align: left;
    border: 1px solid var(--border);
    font-weight: 600;
}
.content td {
    padding: 6px 12px;
    border: 1px solid var(--border);
    vertical-align: top;
}
.content tr:hover td { background: var(--bg-secondary); }
/* Code */
.content code {
    font-family: var(--font-mono);
    font-size: 13px;
    background: var(--bg-tertiary);
    padding: 2px 6px;
    border-radius: 4px;
    color: var(--accent);
}
.content pre {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 16px;
    overflow-x: auto;
    margin: 12px 0;
    font-size: 13px;
    line-height: 1.5;
}
.content pre code {
    background: none;
    padding: 0;
    color: var(--text);
}
/* HITL lock indicator */
.content .hitl-lock {
    border-left: 3px solid var(--yellow);
    background: rgba(210, 153, 34, 0.05);
    padding: 4px 12px;
    margin: 8px 0;
    font-size: 11px;
    color: var(--yellow);
}
/* Status badges */
.badge-pass { color: var(--green); font-weight: 700; }
.badge-fail { color: var(--red); font-weight: 700; }
.badge-partial { color: var(--yellow); font-weight: 700; }
/* Print */
@media print {
    nav.sidebar { display: none; }
    main { margin-left: 0; max-width: 100%; }
    .content pre { white-space: pre-wrap; }
    section.doc { page-break-inside: avoid; }
}
/* Search */
#search {
    width: calc(100% - 32px);
    margin: 8px 16px;
    padding: 6px 10px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: 4px;
    color: var(--text);
    font-size: 13px;
    outline: none;
}
#search:focus { border-color: var(--accent); }
"""

JS = """
document.getElementById('search').addEventListener('input', function(e) {
    const q = e.target.value.toLowerCase();
    document.querySelectorAll('nav.sidebar a').forEach(a => {
        a.style.display = a.textContent.toLowerCase().includes(q) || q === '' ? '' : 'none';
    });
    document.querySelectorAll('nav.sidebar h2').forEach(h => {
        const links = [];
        let el = h.nextElementSibling;
        while (el && el.tagName === 'A') { links.push(el); el = el.nextElementSibling; }
        const anyVisible = links.some(a => a.style.display !== 'none');
        h.style.display = anyVisible || q === '' ? '' : 'none';
    });
});
"""


def slugify(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def render_md(text):
    # Strip HITL lock markers but mark them visually
    text = re.sub(
        r'<!--\s*HITL-LOCK\s+START:([^>]+)\s*-->',
        r'<div class="hitl-lock">HITL-LOCK: \1 (human-reviewed, do not modify)</div>',
        text
    )
    text = re.sub(r'<!--\s*HITL-LOCK\s+END:[^>]+\s*-->', '', text)
    # C/Python HITL markers — leave as-is in code blocks

    md = markdown.Markdown(extensions=[
        TableExtension(),
        FencedCodeExtension(),
        TocExtension(permalink=False),
    ])
    return md.convert(text)


def build():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Build sidebar + content
    sidebar_html = '<input type="text" id="search" placeholder="Search docs...">\n'
    content_html = ''
    doc_count = 0
    line_count = 0

    for group_name, docs in SECTIONS:
        slug = slugify(group_name)
        sidebar_html += f'<h2>{group_name}</h2>\n'
        content_html += f'<div class="section-group" id="group-{slug}"><h2>{group_name}</h2></div>\n'

        for title, filepath in docs:
            doc_slug = slugify(title)
            if not filepath.exists():
                continue

            text = filepath.read_text(encoding='utf-8', errors='replace')
            lines = len(text.splitlines())
            line_count += lines
            doc_count += 1

            sidebar_html += f'<a href="#{doc_slug}">{title}</a>\n'
            rendered = render_md(text)
            content_html += f'<section class="doc" id="{doc_slug}">\n'
            content_html += f'<div class="content">\n{rendered}\n</div>\n'
            content_html += f'</section>\n'

    sidebar_html += f'<div class="stats">{doc_count} documents | {line_count:,} lines</div>\n'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>foxBMS POSIX vECU — Documentation</title>
    <style>{CSS}</style>
</head>
<body>
    <nav class="sidebar">
        <div class="logo">foxBMS POSIX vECU</div>
        {sidebar_html}
    </nav>
    <main>
        {content_html}
    </main>
    <script>{JS}</script>
</body>
</html>"""

    output_path.write_text(html, encoding='utf-8')
    print(f"Built: {output_path} ({doc_count} docs, {line_count:,} lines)")


if __name__ == '__main__':
    build()
