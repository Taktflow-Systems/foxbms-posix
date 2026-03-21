with open("src/app/driver/can/can.c") as f:
    lines = f.readlines()

out = []
for line in lines:
    out.append(line)
    if 'extern bool CAN_IsCurrentSensorPresent(uint8_t stringNumber) {' in line:
        out.append('#ifdef FOXBMS_POSIX\n')
        out.append('    (void)stringNumber; return true;\n')
        out.append('#endif\n')
    if 'extern bool CAN_IsCurrentSensorCcPresent(uint8_t stringNumber) {' in line:
        out.append('#ifdef FOXBMS_POSIX\n')
        out.append('    (void)stringNumber; return true;\n')
        out.append('#endif\n')
    if 'extern bool CAN_IsCurrentSensorEcPresent(uint8_t stringNumber) {' in line:
        out.append('#ifdef FOXBMS_POSIX\n')
        out.append('    (void)stringNumber; return true;\n')
        out.append('#endif\n')

with open("src/app/driver/can/can.c", "w") as f:
    f.writelines(out)
print("patched CAN sensor presence")
