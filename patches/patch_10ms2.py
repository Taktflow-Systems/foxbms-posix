with open("src/app/task/config/ftask_cfg.c") as f:
    lines = f.readlines()

out = []
for line in lines:
    out.append(line)
    if line.strip() == 'extern void FTSK_RunUserCodeCyclic10ms(void) {':
        out.append('#ifdef FOXBMS_POSIX\n')
        out.append('    { static uint32_t c10=0; c10++;\n')
        out.append('      if(c10<=3||c10%100==0)\n')
        out.append('        fprintf(stderr,"[10ms] c=%u" "\\n",c10);\n')
        out.append('      fflush(stderr); }\n')
        out.append('#endif\n')

with open("src/app/task/config/ftask_cfg.c", "w") as f:
    f.writelines(out)
print("patched 10ms")
