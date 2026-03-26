with open("src/app/driver/sbc/sbc.c") as f:
    code = f.read()

# After the initial state declaration, add a POSIX override
# Find the SBC_GetState function and make it always return RUNNING on POSIX
old = 'extern SBC_STATEMACHINE_e SBC_GetState(SBC_STATE_s *pInstance) {\n    FAS_ASSERT(pInstance != NULL_PTR);\n\n    return pInstance->state;\n}'
new = '''extern SBC_STATEMACHINE_e SBC_GetState(SBC_STATE_s *pInstance) {
    FAS_ASSERT(pInstance != NULL_PTR);
#ifdef FOXBMS_POSIX
    return SBC_STATEMACHINE_RUNNING;  /* POSIX: no SPI, skip SBC init */
#else
    return pInstance->state;
#endif
}'''

if old in code:
    code = code.replace(old, new, 1)
    with open("src/app/driver/sbc/sbc.c", "w") as f:
        f.write(code)
    print("patched SBC_GetState")
else:
    print("pattern not found")
