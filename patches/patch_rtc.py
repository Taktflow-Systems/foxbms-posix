with open("src/app/driver/rtc/rtc.c") as f:
    code = f.read()

# Patch RTC_IsRtcModuleInitialized to return true on POSIX
old = 'extern bool RTC_IsRtcModuleInitialized(void) {'
new = '''extern bool RTC_IsRtcModuleInitialized(void) {
#ifdef FOXBMS_POSIX
    return true;  /* POSIX: no I2C RTC */
#endif'''

if old in code:
    code = code.replace(old, new, 1)
    with open("src/app/driver/rtc/rtc.c", "w") as f:
        f.write(code)
    print("patched RTC")
else:
    print("pattern not found")
