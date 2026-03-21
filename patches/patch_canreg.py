with open("build/app_host_unit_test/include/HL_reg_can.h") as f:
    code = f.read()

code = code.replace(
    '#define canREG1 ((canBASE_t *)0xFFF7DC00U)',
    '#ifdef FOXBMS_POSIX\nextern char posix_canreg1[];\n#define canREG1 ((canBASE_t *)posix_canreg1)\n#else\n#define canREG1 ((canBASE_t *)0xFFF7DC00U)\n#endif'
)
code = code.replace(
    '#define canREG2 ((canBASE_t *)0xFFF7DE00U)',
    '#ifdef FOXBMS_POSIX\nextern char posix_canreg2[];\n#define canREG2 ((canBASE_t *)posix_canreg2)\n#else\n#define canREG2 ((canBASE_t *)0xFFF7DE00U)\n#endif'
)
code = code.replace(
    '#define canREG3 ((canBASE_t *)0xFFF7E000U)',
    '#ifdef FOXBMS_POSIX\nextern char posix_canreg3[];\n#define canREG3 ((canBASE_t *)posix_canreg3)\n#else\n#define canREG3 ((canBASE_t *)0xFFF7E000U)\n#endif'
)

with open("build/app_host_unit_test/include/HL_reg_can.h", "w") as f:
    f.write(code)
print("patched HL_reg_can.h")
