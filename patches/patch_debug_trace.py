"""Debug trace: add probes to DATA_CopyData and MRC to trace voltage data flow."""
import sys

# Patch 1: database.c — trace WRITE timestamp
db_path = "src/app/engine/database/database.c"
with open(db_path) as f:
    code = f.read()

if "[DB-W]" not in code:
    old = "pHeader->timestamp         = OS_GetTickCount();"
    trace = old + '\n        { static int dw=0; dw++; if(dw<=5||dw%1000==0) { fprintf(stderr, "[DB-W] uid=%u ts=%u #%d\\n", (unsigned)pHeader->uniqueId, pHeader->timestamp, dw); fflush(stderr); } }'
    code = code.replace(old, trace, 1)
    if '#include <stdio.h>' not in code:
        code = code.replace('#include <stdint.h>', '#include <stdint.h>\n#include <stdio.h>')
    with open(db_path, "w") as f:
        f.write(code)
    print("Patched database.c with WRITE trace")

# Patch 2: redundancy.c — trace MRC timestamp check
mrc_path = "src/app/application/redundancy/redundancy.c"
with open(mrc_path) as f:
    code = f.read()

if "[MRC]" not in code:
    old = "    if (mrc_state.lastBaseCellVoltageTimestamp != pCellVoltageBase->header.timestamp) {"
    trace = '    { static int mc=0; mc++; if(mc<=5||mc%500==0) { fprintf(stderr, "[MRC] #%d base_ts=%u last=%u timeout=%d\\n", mc, pCellVoltageBase->header.timestamp, mrc_state.lastBaseCellVoltageTimestamp, baseCellVoltageMeasurementTimeoutReached); fflush(stderr); } }\n' + old
    code = code.replace(old, trace, 1)
    if '#include <stdio.h>' not in code:
        code = code.replace('#include <stdint.h>', '#include <stdint.h>\n#include <stdio.h>')
    with open(mrc_path, "w") as f:
        f.write(code)
    print("Patched redundancy.c with MRC trace")
