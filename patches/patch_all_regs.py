import re, os, glob

import pathlib
# Headers are in halcogen-headers/ at repo root, or foxbms-2/build/... as fallback
_repo_root = pathlib.Path(__file__).resolve().parent.parent
_halcogen = _repo_root / "halcogen-headers"
_fallback = pathlib.Path("build/app_host_unit_test/include")
base_dir = str(_halcogen) if _halcogen.is_dir() else str(_fallback)
stubs = []

# Find all #define xxxREG ((type *)0xFFF...) patterns
for hfile in glob.glob(os.path.join(base_dir, "HL_reg_*.h")):
    with open(hfile) as f:
        code = f.read()

    modified = False
    for match in re.finditer(r'#define\s+(\w+REG\d*)\s+\(\((\w+)\s*\*\s*\)\s*(0x[0-9A-Fa-f]+U?)\)', code):
        name = match.group(1)
        typ = match.group(2)
        addr = match.group(3)

        # Create RAM buffer for this register
        buf_name = f"posix_{name.lower()}"
        stubs.append((name, typ, buf_name))

        old = match.group(0)
        new = f'''#ifdef FOXBMS_POSIX
extern char {buf_name}[];
#define {name} (({typ} *){buf_name})
#else
{old}
#endif'''
        code = code.replace(old, new, 1)
        modified = True

    if modified:
        with open(hfile, "w") as f:
            f.write(code)
        print(f"Patched {os.path.basename(hfile)}: {len([s for s in stubs if True])} regs")

# Generate stub declarations
print(f"\n// Add to hal_stubs_posix.c:")
for name, typ, buf_name in stubs:
    print(f'char {buf_name}[4096] __attribute__((aligned(4))) = {{0}};')
