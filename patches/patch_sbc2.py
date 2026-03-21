with open("src/app/driver/sbc/sbc.c") as f:
    code = f.read()

# Also patch SBC_SetStateRequest to always return SBC_OK on POSIX
old = '''extern SBC_RETURN_TYPE_e SBC_SetStateRequest(SBC_STATE_s *pInstance, SBC_STATE_REQUEST_e stateRequest) {
    FAS_ASSERT(pInstance != NULL_PTR);'''
new = '''extern SBC_RETURN_TYPE_e SBC_SetStateRequest(SBC_STATE_s *pInstance, SBC_STATE_REQUEST_e stateRequest) {
    FAS_ASSERT(pInstance != NULL_PTR);
#ifdef FOXBMS_POSIX
    (void)stateRequest;
    return SBC_OK;  /* POSIX: no SPI, always OK */
#endif'''

if old in code:
    code = code.replace(old, new, 1)
    with open("src/app/driver/sbc/sbc.c", "w") as f:
        f.write(code)
    print("patched SBC_SetStateRequest")
else:
    print("pattern not found")
