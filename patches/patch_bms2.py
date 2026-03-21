with open("src/app/application/bms/bms.c") as f:
    lines = f.readlines()

out = []
added_stdio = False
for line in lines:
    if not added_stdio and '#include' in line:
        out.append('#include <stdio.h>\n')
        added_stdio = True
    out.append(line)
    if line.strip() == 'void BMS_Trigger(void) {':
        out.append('#ifdef FOXBMS_POSIX\n')
        out.append('    { static uint32_t bms_cnt = 0; bms_cnt++;\n')
        out.append('      if (bms_cnt <= 20 || bms_cnt % 500 == 0)\n')
        out.append('        fprintf(stderr, "[BMS] #%u state=%d sub=%d" "\\n",\n')
        out.append('          bms_cnt, bms_state.state, bms_state.substate);\n')
        out.append('      fflush(stderr); }\n')
        out.append('#endif\n')

with open("src/app/application/bms/bms.c", "w") as f:
    f.writelines(out)
print("patched bms.c")
