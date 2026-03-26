with open("src/app/task/config/ftask_cfg.c") as f:
    lines = f.readlines()

out = []
for line in lines:
    out.append(line)
    if '#include "ftask_cfg.h"' in line:
        out.append('#include <stdio.h>\n')
    if 'STD_RETURN_TYPE_e retval = DATA_Initialize();' in line:
        out.insert(-1, '    fprintf(stderr, "[POSIX] InitEngine enter" "\\n"); fflush(stderr);\n')
        out.append('    fprintf(stderr, "[POSIX] DATA_Init done" "\\n"); fflush(stderr);\n')
    if line.strip() == 'FRAM_Initialize();':
        out.append('    fprintf(stderr, "[POSIX] FRAM done" "\\n"); fflush(stderr);\n')
    if 'retval = SYSM_Initialize();' in line:
        out.append('    fprintf(stderr, "[POSIX] SYSM done" "\\n"); fflush(stderr);\n')

with open("src/app/task/config/ftask_cfg.c", "w") as f:
    f.writelines(out)
print("patched")
