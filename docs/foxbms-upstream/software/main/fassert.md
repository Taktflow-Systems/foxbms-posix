# Assertion Module (fassert)

**Source**: [docs.foxbms.org — fassert](https://iisb-foxbms.iisb.fraunhofer.de/foxbms/docs/latest/software/modules/main/fassert.html)
**Files**: `src/app/main/include/fassert.h`
**Status**: Upstream documentation marked "not yet complete"

---

## Assert Levels (from source code)

| Level | Value | Behavior |
|-------|-------|----------|
| `FAS_ASSERT_LEVEL_GENERAL_ASSERT` | 0 | Standard assert → `FAS_InfiniteLoop()` (infinite loop, waits for watchdog reset) |
| `FAS_ASSERT_LEVEL_TRAP` | 1 | Hardware trap instruction |
| `FAS_ASSERT_LEVEL_NO_OPERATION` | 2 | No-op — assertion failure is silently ignored |

## Key Functions

- `FAS_ASSERT(condition)` — macro, evaluates condition, acts based on level
- `FAS_InfiniteLoop()` — infinite while(1) loop (default failure handler)
- `FAS_StoreAssertLocation(pc, line)` — records where assertion failed (for post-mortem)

## POSIX Port Override (GA-07)

```c
// posix_overrides.h
#undef FAS_ASSERT_LEVEL
#define FAS_ASSERT_LEVEL (2u)  // NO_OPERATION — prevents infinite loop

// hal_stubs_posix.c — override FAS_StoreAssertLocation
void FAS_StoreAssertLocation(uint32_t *pc, uint32_t line) {
    fprintf(stderr, "[FAS] ASSERT FAILED at pc=%p line=%u\n", (void*)pc, line);
    exit(1);  // Crash visibly instead of silently continuing
}
```

Level 2 makes `FAS_InfiniteLoop()` a no-op. Our override of `FAS_StoreAssertLocation()` logs the location and exits. This catches real bugs while avoiding infinite loops on a POSIX system (no watchdog to recover).
