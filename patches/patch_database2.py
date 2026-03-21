with open("src/app/engine/database/database.c") as f:
    lines = f.readlines()

out = []
added_stdio = False
for line in lines:
    if not added_stdio and '#include "database.h"' in line:
        out.append(line)
        out.append('#include <stdio.h>\n')
        added_stdio = True
        continue
    out.append(line)
    if 'void DATA_IterateOverDatabaseEntries(const DATA_QUEUE_MESSAGE_s *kpReceiveMessage) {' in line:
        out.append('#ifdef FOXBMS_POSIX\n')
        out.append('    { static uint32_t db_cnt = 0; db_cnt++;\n')
        out.append('      if (db_cnt <= 10 || db_cnt % 1000 == 0)\n')
        out.append('        fprintf(stderr, "[DB] Iterate #%u access=%d ptr0=%p" "\\n",\n')
        out.append('          db_cnt, kpReceiveMessage->accessType, (void*)kpReceiveMessage->pDatabaseEntry[0]);\n')
        out.append('      fflush(stderr); }\n')
        out.append('#endif\n')

with open("src/app/engine/database/database.c", "w") as f:
    f.writelines(out)
print("patched database.c with iterate trace")
