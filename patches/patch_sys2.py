with open("src/app/engine/sys/sys.c") as f:
    code = f.read()

# Remove old trace if present
code = code.replace('#ifdef FOXBMS_POSIX\n        { static uint32_t sys_trace_cnt', '/* old trace removed */')

# Add trace at the TOP of SYS_Trigger, before any early exit
old = '''extern STD_RETURN_TYPE_e SYS_Trigger(SYS_STATE_s *pSystemState) {
    FAS_ASSERT(pSystemState != NULL_PTR);
    bool earlyExit                = false;'''
new = '''extern STD_RETURN_TYPE_e SYS_Trigger(SYS_STATE_s *pSystemState) {
    FAS_ASSERT(pSystemState != NULL_PTR);
#ifdef FOXBMS_POSIX
    { static uint32_t sys_cnt = 0; sys_cnt++;
      if (sys_cnt <= 5 || sys_cnt % 500 == 0)
        fprintf(stderr, "[SYS] Trigger #%u state=%d sub=%d timer=%u trig=%u" "\\n",
          sys_cnt, pSystemState->currentState, pSystemState->currentSubstate,
          pSystemState->timer, pSystemState->triggerEntry);
      fflush(stderr);
    }
#endif
    bool earlyExit                = false;'''

if old in code:
    code = code.replace(old, new, 1)
    with open("src/app/engine/sys/sys.c", "w") as f:
        f.write(code)
    print("patched SYS_Trigger with top-level trace")
else:
    print("pattern not found")
