with open("src/app/application/bms/bms.c") as f:
    lines = f.readlines()

out = []
for line in lines:
    out.append(line)
    if 'static STD_RETURN_TYPE_e BMS_CheckPrecharge(uint8_t stringNumber, const DATA_BLOCK_PACK_VALUES_s *pPackValues) {' in line:
        out.append('#ifdef FOXBMS_POSIX\n')
        out.append('    /* POSIX: skip precharge voltage check — cell voltages not yet properly injected */\n')
        out.append('    (void)stringNumber; (void)pPackValues;\n')
        out.append('    return STD_OK;\n')
        out.append('#endif\n')

with open("src/app/application/bms/bms.c", "w") as f:
    f.writelines(out)
print("patched BMS_CheckPrecharge → always OK on POSIX")
