"""
Phase 3: Add SIL probe instrumentation to the real diag.c.

Inserts code at the end of DIAG_Handler() (just before the final return)
that updates the SIL probe variables (posix_diag_fault_count, etc.) and
logs fatal threshold exceedances.

Idempotent: checks for sentinel comment before patching.
"""

import sys

TARGET = "src/app/engine/diag/diag.c"
SENTINEL = "/* SIL probe: update DIAG state for probe bus */"

PROBE_CODE = '''
#ifdef FOXBMS_SIL_PROBES
    ''' + SENTINEL + '''
    extern uint32_t posix_diag_fault_count;
    extern uint8_t posix_diag_last_id;
    extern uint8_t posix_diag_last_event;
    extern uint64_t posix_diag_bitmap;
    if (event == DIAG_EVENT_NOT_OK && ret_val == DIAG_HANDLER_RETURN_ERR_OCCURRED) {
        posix_diag_fault_count++;
        posix_diag_last_id = (uint8_t)(diagId & 0xFFu);
        posix_diag_last_event = 1u;
        if ((uint16_t)diagId < 64u) posix_diag_bitmap |= (1ULL << (uint16_t)diagId);
        fprintf(stderr, "[DIAG] FATAL: diagId=%u threshold exceeded -> contactor open\\n", (unsigned)diagId);
        fflush(stderr);
    } else if (event == DIAG_EVENT_OK) {
        if ((uint16_t)diagId < 64u) posix_diag_bitmap &= ~(1ULL << (uint16_t)diagId);
    }
#endif
'''

try:
    with open(TARGET) as f:
        code = f.read()
except FileNotFoundError:
    print(f"ERROR: {TARGET} not found")
    sys.exit(1)

if SENTINEL in code:
    print("already patched")
    sys.exit(0)

# We also need stdio.h for fprintf — add it after the existing includes if not present
if '#include <stdio.h>' not in code:
    # Insert after the last #include in the includes section
    code = code.replace(
        '#include <stdint.h>',
        '#include <stdint.h>\n#include <stdio.h>  /* POSIX: for SIL probe fprintf */',
        1
    )

# The DIAG_Handler function ends with:
#     return ret_val;
# }
#
# We want to insert our probe code just before "    return ret_val;" at the END
# of the DIAG_Handler function. The function signature is on line ~341.
#
# Strategy: find the pattern "    return ret_val;\n}\n" that ends DIAG_Handler.
# DIAG_Handler is the only function that returns ret_val and has that exact pattern
# before DIAG_CheckEvent.

# Find the insertion point: the final "return ret_val;" in DIAG_Handler
# We look for the pattern between DIAG_Handler and DIAG_CheckEvent
handler_start = code.find('DIAG_RETURNTYPE_e DIAG_Handler(')
if handler_start < 0:
    print("ERROR: DIAG_Handler function not found")
    sys.exit(1)

checkevent_start = code.find('STD_RETURN_TYPE_e DIAG_CheckEvent(')
if checkevent_start < 0:
    print("ERROR: DIAG_CheckEvent function not found")
    sys.exit(1)

# Within the DIAG_Handler body, find the last "return ret_val;"
handler_body = code[handler_start:checkevent_start]
last_return_offset = handler_body.rfind('    return ret_val;')
if last_return_offset < 0:
    print("ERROR: 'return ret_val;' not found in DIAG_Handler")
    sys.exit(1)

# Absolute position in the file
insert_pos = handler_start + last_return_offset

# Insert probe code before the return
new_code = code[:insert_pos] + PROBE_CODE + '\n' + code[insert_pos:]

with open(TARGET, "w") as f:
    f.write(new_code)

print("patched DIAG_Handler with SIL probe instrumentation")
