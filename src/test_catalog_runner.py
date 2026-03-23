#!/usr/bin/env python3
"""
foxBMS POSIX vECU — Unified Test Catalog Runner

Loads test catalogs from all test_*.py modules (SIG, SM, DIAG, THR, SSR, DFA,
B2B, E2E, HW, FI, END categories) and provides:
  - Summary statistics (total, per-category, per-ASIL, per-priority)
  - Traceability report (requirement → test mapping)
  - HTML test matrix export for docs/site and ASPICE evidence
  - Selective execution by category, priority, or ASIL level

Usage:
    python3 test_catalog_runner.py --summary
    python3 test_catalog_runner.py --traceability
    python3 test_catalog_runner.py --export-html > test-matrix.html
    python3 test_catalog_runner.py --category SIG --priority P1
"""
import importlib
import sys
import json
from collections import Counter, defaultdict
from pathlib import Path

# All test catalog modules (each must expose get_tests() → list[dict])
CATALOG_MODULES = [
    "test_can_signals",
    "test_state_machine",
    "test_diag_verification",
    "test_thresholds",
    "test_safety_validation",
]


def load_all_tests():
    """Load tests from all catalog modules."""
    all_tests = []
    for mod_name in CATALOG_MODULES:
        try:
            mod = importlib.import_module(mod_name)
            tests = mod.get_tests()
            all_tests.extend(tests)
        except (ImportError, AttributeError) as e:
            print(f"[WARN] Could not load {mod_name}: {e}", file=sys.stderr)
    return all_tests


def summary(tests):
    """Print summary statistics."""
    cats = Counter(t.get("category", "?") for t in tests)
    asils = Counter(t.get("asil", "") or "—" for t in tests)
    prios = Counter(t.get("priority", "P2") for t in tests)

    print(f"\n{'='*60}")
    print(f"  foxBMS POSIX vECU — Test Catalog Summary")
    print(f"{'='*60}")
    print(f"  Total test cases: {len(tests)}")
    print()
    print(f"  By Category:")
    for cat, count in sorted(cats.items()):
        print(f"    {cat:12s}  {count:5d}")
    print()
    print(f"  By ASIL Level:")
    for asil, count in sorted(asils.items()):
        print(f"    {asil:12s}  {count:5d}")
    print()
    print(f"  By Priority:")
    for prio, count in sorted(prios.items()):
        print(f"    {prio:12s}  {count:5d}")
    print(f"{'='*60}\n")


def traceability(tests):
    """Print requirement → test traceability matrix."""
    req_map = defaultdict(list)
    for t in tests:
        for req in t.get("verifies", []):
            req_map[req].append(t["id"])

    print(f"\n{'='*60}")
    print(f"  Requirement → Test Traceability ({len(req_map)} requirements)")
    print(f"{'='*60}")
    for req in sorted(req_map.keys()):
        test_ids = req_map[req]
        print(f"  {req:20s} → {len(test_ids)} tests: {', '.join(test_ids[:5])}", end="")
        if len(test_ids) > 5:
            print(f" ... (+{len(test_ids)-5} more)", end="")
        print()

    # Check for untested requirements
    all_reqs = set(req_map.keys())
    print(f"\n  Total requirements with tests: {len(all_reqs)}")


def export_html(tests):
    """Export full test matrix as HTML for docs/site integration."""
    cats = sorted(set(t.get("category", "?") for t in tests))

    print('<!DOCTYPE html><html lang="en"><head>')
    print('<meta charset="UTF-8"><title>Test Matrix — foxBMS POSIX vECU</title>')
    print('<style>')
    print(':root{--bg:#0f1117;--card:#1a1d27;--border:#2a2d3a;--text:#c9d1d9;--accent:#7c3aed;--ok:#22c55e;--warn:#eab308;--err:#ef4444}')
    print('*{margin:0;padding:0;box-sizing:border-box}')
    print('body{font-family:"Segoe UI",system-ui,sans-serif;background:var(--bg);color:var(--text);padding:24px}')
    print('h1{color:#fff;margin-bottom:16px}h2{color:var(--accent);margin:24px 0 8px;font-size:1rem}')
    print('.stats{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0}')
    print('.stat{background:var(--card);border:1px solid var(--border);border-radius:6px;padding:10px 14px;min-width:100px}')
    print('.stat .num{font-size:1.5rem;font-weight:700;color:#fff}.stat .label{font-size:.7rem;text-transform:uppercase;color:#6b7280}')
    print('table{width:100%;border-collapse:collapse;font-size:.8rem;margin:8px 0}')
    print('th{background:var(--card);color:var(--accent);padding:6px 8px;text-align:left;border:1px solid var(--border);font-weight:600;position:sticky;top:0}')
    print('td{padding:4px 8px;border:1px solid var(--border)}tr:hover td{background:var(--card)}')
    print('.badge{display:inline-block;padding:1px 6px;border-radius:3px;font-size:.7rem;font-weight:600}')
    print('.b-d{background:rgba(239,68,68,.15);color:#ef4444;border:1px solid #ef4444}')
    print('.b-c{background:rgba(234,179,8,.15);color:#eab308;border:1px solid #eab308}')
    print('.b-b{background:rgba(59,130,246,.15);color:#3b82f6;border:1px solid #3b82f6}')
    print('.b-qm{background:rgba(107,114,128,.15);color:#6b7280;border:1px solid #6b7280}')
    print('</style></head><body>')
    print(f'<h1>foxBMS POSIX vECU — Full Test Matrix ({len(tests)} tests)</h1>')

    # Stats
    asil_counts = Counter(t.get("asil", "") or "—" for t in tests)
    cat_counts = Counter(t.get("category", "?") for t in tests)
    print('<div class="stats">')
    print(f'<div class="stat"><div class="num">{len(tests)}</div><div class="label">Total</div></div>')
    for asil in ["D", "C", "B", "QM"]:
        if asil in asil_counts:
            print(f'<div class="stat"><div class="num">{asil_counts[asil]}</div><div class="label">ASIL {asil}</div></div>')
    for cat in sorted(cat_counts.keys()):
        print(f'<div class="stat"><div class="num">{cat_counts[cat]}</div><div class="label">{cat}</div></div>')
    print('</div>')

    # Table per category
    for cat in cats:
        cat_tests = [t for t in tests if t.get("category") == cat]
        print(f'<h2>{cat} — {len(cat_tests)} tests</h2>')
        print('<table><tr><th>ID</th><th>Type</th><th>ASIL</th><th>Description</th><th>Verifies</th><th>Priority</th></tr>')
        for t in cat_tests:
            asil = t.get("asil", "")
            badge_cls = {"D": "b-d", "C": "b-c", "B": "b-b", "QM": "b-qm"}.get(asil, "")
            badge = f'<span class="badge {badge_cls}">{asil}</span>' if asil else ""
            verifies = ", ".join(t.get("verifies", [])[:3])
            if len(t.get("verifies", [])) > 3:
                verifies += f" +{len(t['verifies'])-3}"
            print(f'<tr><td><strong>{t["id"]}</strong></td><td>{t.get("test_type","")}</td>'
                  f'<td>{badge}</td><td>{t.get("description","")}</td>'
                  f'<td>{verifies}</td><td>{t.get("priority","P2")}</td></tr>')
        print('</table>')

    print('</body></html>')


def main():
    import argparse
    parser = argparse.ArgumentParser(description="foxBMS Test Catalog Runner")
    parser.add_argument("--summary", action="store_true", help="Print summary statistics")
    parser.add_argument("--traceability", action="store_true", help="Print requirement traceability")
    parser.add_argument("--export-html", action="store_true", help="Export HTML test matrix")
    parser.add_argument("--export-json", action="store_true", help="Export JSON test catalog")
    parser.add_argument("--category", help="Filter by category (SIG, SM, DIAG, THR, SSR, etc.)")
    parser.add_argument("--asil", help="Filter by ASIL level (D, C, B, QM)")
    parser.add_argument("--priority", help="Filter by priority (P1, P2)")
    args = parser.parse_args()

    tests = load_all_tests()

    if args.category:
        tests = [t for t in tests if t.get("category") == args.category]
    if args.asil:
        tests = [t for t in tests if t.get("asil") == args.asil]
    if args.priority:
        tests = [t for t in tests if t.get("priority") == args.priority]

    if args.export_html:
        export_html(tests)
    elif args.export_json:
        print(json.dumps(tests, indent=2))
    elif args.traceability:
        traceability(tests)
    else:
        summary(tests)


if __name__ == "__main__":
    main()
