"""Add @satisfies/@verifies tags to fill forward trace blanks."""
import os

SATISFIES = {
    "src/hal_stubs_posix.c": [
        "SW-REQ-042", "SW-REQ-051", "SW-REQ-052", "SW-REQ-053",
        "SW-REQ-061", "SW-REQ-062", "SW-REQ-063", "SW-REQ-065",
        "SW-REQ-066", "SW-REQ-067", "SW-REQ-068", "SW-REQ-069",
        "SW-REQ-071", "SW-REQ-072", "SW-REQ-073", "SW-REQ-074",
        "SW-REQ-075", "SW-REQ-095", "SW-REQ-096", "SW-REQ-097",
        "SW-REQ-098", "SW-REQ-099", "SW-REQ-108", "SW-REQ-109",
        "SW-REQ-120", "SW-REQ-123", "SW-REQ-129",
    ],
    "src/foxbms_posix_main.c": [
        "SW-REQ-080", "SW-REQ-200", "SW-REQ-201",
    ],
    "src/sil_layer.c": [
        "SW-REQ-203", "SW-REQ-204",
    ],
    "src/plant_model.py": [
        "SW-REQ-003",
    ],
}

VERIFIES = {
    "src/test_integration.py": [
        "SW-REQ-062", "SW-REQ-063", "SW-REQ-065", "SW-REQ-066",
        "SW-REQ-067", "SW-REQ-068", "SW-REQ-069",
        "SW-REQ-095", "SW-REQ-096", "SW-REQ-097", "SW-REQ-098",
        "SW-REQ-099", "SW-REQ-108", "SW-REQ-109",
    ],
    "src/test_smoke.py": [
        "SW-REQ-061", "SW-REQ-062", "SW-REQ-080",
        "SW-REQ-095", "SW-REQ-120", "SW-REQ-200",
    ],
}

def add_tags(filepath, reqs, tag_type):
    is_c = filepath.endswith(".c") or filepath.endswith(".h")
    prefix = "/* @{} ".format(tag_type) if is_c else "# @{} ".format(tag_type)
    suffix = " */" if is_c else ""

    with open(filepath, encoding="utf-8") as f:
        lines = f.readlines()

    content = "".join(lines)
    added = []
    insert_idx = 0

    # Find last existing tag line
    for i, line in enumerate(lines):
        if "@satisfies" in line or "@verifies" in line:
            insert_idx = i + 1

    if insert_idx == 0:
        # Find first code line
        for i, line in enumerate(lines):
            if is_c and ("#include" in line or "#define" in line):
                insert_idx = i
                break
            elif not is_c and (line.startswith("import ") or line.startswith("from ")):
                insert_idx = i
                break

    for req in reversed(reqs):
        if req not in content:
            tag_line = prefix + req + suffix + "\n"
            lines.insert(insert_idx, tag_line)
            added.append(req)

    if added:
        with open(filepath, "w", encoding="utf-8") as f:
            f.writelines(lines)
        print("  %s: +%d %s tags" % (filepath, len(added), tag_type))

for fp, reqs in SATISFIES.items():
    if os.path.isfile(fp):
        add_tags(fp, reqs, "satisfies")

for fp, reqs in VERIFIES.items():
    if os.path.isfile(fp):
        add_tags(fp, reqs, "verifies")

print("Done")
