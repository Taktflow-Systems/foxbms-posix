# MISRA C:2012 Compliance Report — foxBMS POSIX SIL Port

**Original analysis date:** 2026-03-27
**Rescan date:** 2026-03-27 (after remediation of `foxbms_posix_main.c`)
**Standard:** MISRA C:2012 (ISO/IEC 9899:2011 baseline)
**Analyst:** AI-assisted static analysis (Claude)
**Review status:** Draft — requires human engineer sign-off before regulatory submission

---

## Scope

**Note on file path:** The task referenced `src/posix.c`, which does not exist in this repository. The actual POSIX C source files analyzed are:

| File | Lines | Purpose |
|---|---|---|
| `src/foxbms_posix_main.c` | 437 | POSIX vECU main loop, SocketCAN, cooperative scheduler |
| `src/hal_stubs_posix.c` | 955 | HAL stubs, OS wrappers, SPS simulation, CAN RX ring buffer |
| `src/sil_layer.c` | 123 | SIL instrumentation layer (probes + overrides) |

All three files collectively constitute the "posix" implementation layer. The analysis is performed manually (no tool-generated output) against MISRA C:2012 Mandatory, Required, and Advisory guidelines.

---

## Deviation Policy for POSIX SIL Port

This codebase is a **Software-in-the-Loop (SIL) test harness**, not production firmware. Several rule violations are inherent to the POSIX/Linux target platform and are acceptable with documented deviations. Such violations are marked **[DEV-ELIGIBLE]** below.

---

## Summary Table

| ID | Rule | Category | File | Count | Severity |
|---|---|---|---|---|---|
| V-001 | 7.2 | Required | main, stubs | 8 | Medium |
| V-002 | 8.5 | Required | main, stubs | 15 | Medium |
| V-003 | 10.3 | Required | main, stubs, sil | 8 | High |
| V-004 | 10.4 | Required | main, stubs, sil | 7 | High |
| V-005 | 11.3 | Required | main | 2 | High |
| V-006 | 14.4 | Required | main, stubs, sil | 5 | High |
| V-007 | 17.7 | Required | main, stubs, sil | 9 | High |
| V-008 | 21.1 | Required | main | 1 | Medium |
| V-009 | 21.5 | Required | main | 1 | High [DEV-ELIGIBLE] |
| V-010 | 21.6 | Required | main, stubs | 30+ | Medium [DEV-ELIGIBLE] |
| V-011 | 21.7 | Required | main | 1 | High |
| V-012 | 21.8 | Required | main, stubs | 3 | High [DEV-ELIGIBLE] |
| V-013 | 1.2 | Advisory | stubs | 2 | Low [DEV-ELIGIBLE] |
| V-014 | 2.3 | Advisory | stubs | 7 | Low |
| V-015 | 8.3 | Required | main | 1 | High |
| V-016 | 15.5 | Advisory | main | 2 | Low |
| V-017 | 8.4 | Required | main | 2 | High |

**Total unique violations: 17 categories, ~107 individual instances**

---

## Detailed Findings

---

### V-001 — Rule 7.2 [Required]: Integer constants of unsigned type without `u`/`U` suffix

**Rule text:** "A u or U suffix shall be applied to all integer constants of unsigned type."

#### `foxbms_posix_main.c`

| Line | Code | Issue |
|---|---|---|
| 404 | `tick % 100 == 0` | `tick` is `uint32_t`; literals `100` and `0` lack `u` suffix |
| 404 | `tick > 0` | `0` lacks `u` suffix in unsigned comparison |
| 411 | `tick & 0xFFFF` | `0xFFFF` lacks `u` suffix |
| 415 | `tick % 5000 == 0` | `5000` and `0` lack `u` suffix |
| 416 | `tick / 1000` | `1000` lacks `u` suffix |

#### `src/hal_stubs_posix.c`

| Line | Code | Issue |
|---|---|---|
| 370 | `#define POSIX_CAN_RX_BUF_SIZE 64` | `64` lacks `u` suffix; used in modulo with `uint32_t` |
| 397 | `if (dlc > 8) dlc = 8;` | `8` lacks `u` suffix; `dlc` is `uint8_t` |
| 442 | `if (rx_cnt <= 20 \|\| ...)` | `20` lacks `u` suffix; `rx_cnt` is `uint32_t` |

**Recommended fix:** Append `u` suffix: `100u`, `0u`, `0xFFFFu`, `5000u`, `1000u`, `64u`, `8u`, `20u`.

---

### V-002 — Rule 8.5 [Required]: External objects/functions declared outside header files

**Rule text:** "An external object or function shall be declared once in one and only one file."

The rule requires external declarations to appear in a header file, not in `.c` translation units.

#### `foxbms_posix_main.c` — `extern` declarations inside function bodies

| Lines | Symbol |
|---|---|
| 255 | `extern void MEAS_Control(void);` (inside `HITL-LOCK START:MAIN-LOOP-TIMING` — **cannot be modified**) |
| 314 | `extern volatile uint8_t os_boot;` (inside `main()`, in `#ifdef FOXBMS_SIL_PROBES` block) |
| 315 | `extern uint8_t BMS_GetState(void);` |
| 316 | `extern uint8_t BMS_GetNumberOfConnectedStrings(void);` |
| 326 | `extern float posix_sil_soc_pct;` |
| 339 | `extern uint16_t posix_sil_cell_v_min, posix_sil_cell_v_max;` |
| 347 | `extern int32_t posix_sil_string_voltage_mv;` |
| 348 | `extern int32_t posix_sil_bus_voltage_mv;` |
| 353 | `extern int16_t posix_sil_cell_t_min, posix_sil_cell_t_max;` |
| 367 | `extern int32_t posix_sil_current_ma;` |
| 376 | `extern uint32_t posix_diag_fault_count;` |
| 377 | `extern uint8_t posix_diag_last_id;` |
| 378 | `extern uint8_t posix_diag_last_event;` |
| 388 | `extern uint64_t posix_diag_bitmap;` |
| 392 | `extern uint32_t posix_sil_db_write_count;` |
| 393 | `extern uint32_t posix_sil_db_read_count;` |
| 426 | `extern void SPS_SwitchOffAllGeneralIoChannels(void);` (inside `main()` shutdown block) |

#### `src/hal_stubs_posix.c` — `extern` declarations inside function bodies

| Lines | Symbol |
|---|---|
| 416–419 | `ftsk_canRxQueue`, `ftsk_canToAfeCellVoltagesQueue`, `ftsk_canToAfeCellTemperaturesQueue` |
| 452 | `extern void *ftsk_databaseQueue;` |
| 460 | `extern void *ftsk_canToAfeCellVoltagesQueue;` |
| 461 | `extern void *ftsk_canToAfeCellTemperaturesQueue;` |

**Recommended fix:** Move all `extern` declarations to a corresponding header file (e.g., `posix_sil_probes.h`, `posix_hal_externs.h`).

---

### V-003 — Rule 10.3 [Required]: Narrowing implicit type conversions

**Rule text:** "The value of an expression shall not be assigned to an object with a narrower essential type or of a different essential type category."

#### `foxbms_posix_main.c`

| Line | Expression | From type | To type | Notes |
|---|---|---|---|---|
| 342 | `(v_min + v_max) / 2u` assigned to `uint16_t v_avg` | `unsigned int` (promoted) | `uint16_t` | Sum can overflow 16 bits |
| 343 | `v_max - v_min` assigned to `uint16_t v_delta` | `int` (promoted) | `uint16_t` | Signed result assigned to unsigned |
| 363 | `(tmin + tmax) / 2` assigned to `int16_t tavg` | `int` (promoted) | `int16_t` | Signed narrowing |
| 398 | `(int32_t)(dt)` where `dt` is `uint64_t` | `uint64_t` | `int32_t` | Explicit narrowing cast; Rule 10.5 also applies |

#### `src/hal_stubs_posix.c`

| Line | Expression | From type | To type | Notes |
|---|---|---|---|---|
| 86 (`sil_layer.c`) | `len = 8u` | `unsigned int` | `uint8_t` | Value fits but essential type is narrower |
| 887 | `actual \|= (1u << i)` | `unsigned int` | `uint16_t` | `1u << i` is 32-bit result; stored to 16-bit |
| 888 | `requested \|= (1u << i)` | `unsigned int` | `uint16_t` | Same |
| 889 | `pending \|= (1u << i)` | `unsigned int` | `uint16_t` | Same |

#### `src/sil_layer.c`

| Line | Expression | From type | To type | Notes |
|---|---|---|---|---|
| 86 | `len = 8u` | `unsigned int` | `uint8_t` | `len` parameter is `uint8_t` |

**Recommended fixes:**
- Line 342: `uint16_t v_avg = (uint16_t)(((uint32_t)v_min + v_max) / 2u);`
- Line 343: `uint16_t v_delta = (uint16_t)(v_max - v_min);` (add explicit cast)
- Lines 887–889: `actual |= (uint16_t)(1u << i);` (add explicit cast)

---

### V-004 — Rule 10.4 [Required]: Mixed essential type categories in arithmetic/comparison

**Rule text:** "Both operands of an operator in which the usual arithmetic conversions are performed shall have the same essential type category."

#### `foxbms_posix_main.c`

| Line | Expression | Left type | Right type | Notes |
|---|---|---|---|---|
| 115 | `n == sizeof(frame)` | `ssize_t` (signed) | `size_t` (unsigned) | Signed vs unsigned comparison |
| 229 | `read(...) == sizeof(rx_frame)` | `ssize_t` (signed) | `size_t` (unsigned) | Same pattern in loop condition |
| 404 | `tick % 100` | `uint32_t` (unsigned) | `int` (signed) | Unsigned % signed |
| 415 | `tick % 5000` | `uint32_t` | `int` | Same |

#### `src/hal_stubs_posix.c`

| Line | Expression | Left type | Right type | Notes |
|---|---|---|---|---|
| 331 | `ts.tv_sec * 1000u` | `time_t` (signed long) | `unsigned int` | Signed × unsigned |
| 331 | `ts.tv_nsec / 1000000u` | `long` (signed) | `unsigned int` | Signed ÷ unsigned |
| 382 | `posix_can_rx_head + 1` | `uint32_t` | `int` | Unsigned + signed |

**Recommended fixes:** Add explicit casts to the unsigned type, e.g., `(uint32_t)ts.tv_sec * 1000u`, `(uint32_t)ts.tv_nsec / 1000000u`, `posix_can_rx_head + 1u`.

---

### V-005 — Rule 11.3 [Required]: Cast between pointer to incompatible object types

**Rule text:** "A cast shall not be performed between a pointer to a complete object type and a pointer to a different complete object type."

#### `foxbms_posix_main.c`

| Line | Code | Issue |
|---|---|---|
| 101 | `bind(can_socket, (struct sockaddr *)&addr, sizeof(addr))` | Cast from `struct sockaddr_can *` to `struct sockaddr *` |
| 389 | `(const uint8_t *)&posix_diag_bitmap` | Cast from `uint64_t *` to `const uint8_t *` for byte-level serialization |

**Notes:**
- Line 101 is required by the POSIX socket API and cannot be avoided on Linux. Eligible for a documented deviation.
- Line 389 uses type-punning to serialize a `uint64_t` to bytes. The same effect can be achieved with a union or via `memcpy` to avoid the pointer cast.

---

### V-006 — Rule 14.4 [Required]: Controlling expression not essentially Boolean

**Rule text:** "The controlling expression of an if statement and the controlling expression of an iteration statement shall have essentially Boolean type."

| File | Line | Code | Actual type | Issue |
|---|---|---|---|---|
| `foxbms_posix_main.c` | 216 | `while (running)` | `volatile int` | Not essentially Boolean; should be `running != 0` |
| `foxbms_posix_main.c` | 229 | `while (read(...) == sizeof(...))` | OK — relational result is essentially Boolean | *(not a violation)* |
| `hal_stubs_posix.c` | 737 | `if (crc & 1ULL)` | `uint64_t` (bitwise AND) | Not essentially Boolean; should be `(crc & 1ULL) != 0u` |
| `hal_stubs_posix.c` | 887 | `if (sps_channel_actual_state[i])` | `uint8_t` | Not essentially Boolean |
| `hal_stubs_posix.c` | 888 | `if (sps_channel_requested_state[i])` | `uint8_t` | Not essentially Boolean |
| `hal_stubs_posix.c` | 889 | `if (sps_channel_pending[i])` | `uint8_t` | Not essentially Boolean |
| `sil_layer.c` | 54 | `if (active)` | `uint8_t` | Not essentially Boolean |

**Recommended fixes:**
- `while (running)` → `while (running != 0)`
- `if (crc & 1ULL)` → `if ((crc & 1ULL) != 0ULL)`
- `if (sps_channel_actual_state[i])` → `if (sps_channel_actual_state[i] != 0u)`
- `if (active)` → `if (active != 0u)`

---

### V-007 — Rule 17.7 [Required]: Return value of non-void function not used

**Rule text:** "The value returned by a function having non-void return type shall be used."

#### `foxbms_posix_main.c`

| Line | Call | Return type | Notes |
|---|---|---|---|
| 94 | `fcntl(can_socket, F_SETFL, O_NONBLOCK)` | `int` | Error not checked; socket may remain blocking |
| 134 | `signal(SIGINT, sigint_handler)` | `sig_t` (previous handler) | Previous handler discarded |
| 154 | `posix_can_open(can_if)` | `int` | Error return ignored |
| 177 | `DIAG_Initialize(&diag_device)` | `uint32_t` | Initialization error silently ignored |
| 179 | `OS_CheckTimeHasPassedSelfTest()` | `uint32_t` | Self-test result ignored |

#### `src/sil_layer.c`

| Line | Call | Return type | Notes |
|---|---|---|---|
| 88 | `posix_can_send(...)` in `sil_probe_raw` | `int` | Probe TX errors silently ignored |
| 95 | `posix_can_send(...)` in `sil_probe_2i32` | `int` | Same |
| 104 | `posix_can_send(...)` in `sil_probe_4i16` | `int` | Same |
| 113 | `posix_can_send(...)` in `sil_probe_4u16` | `int` | Same |
| 120 | `posix_can_send(...)` in `sil_probe_heartbeat` | `int` | Same |

**Notes for SIL context:** Probe TX failures are non-critical (probes are observability tools), so ignoring the return is defensible for `sil_layer.c`. For `DIAG_Initialize` (V-007 line 177), the return value should be checked in production firmware.

---

### V-008 — Rule 21.1 [Required]: Use of reserved identifier

**Rule text:** "#define and #undef shall not be used on a reserved identifier or reserved macro name."

#### `foxbms_posix_main.c`

| Line | Code | Issue |
|---|---|---|
| 15 | `#define _GNU_SOURCE` | `_GNU_SOURCE` begins with underscore — reserved identifier per C11 §7.1.3. Defining it is a violation of Rule 21.1. |

**Note [DEV-ELIGIBLE]:** `_GNU_SOURCE` is required on Linux to expose POSIX/GNU socket extensions. The POSIX SIL port cannot run without it. A project-level deviation is appropriate.

---

### V-009 — Rule 21.5 [Required]: Use of `<signal.h>` **[DEV-ELIGIBLE]**

**Rule text:** "The standard header file <signal.h> shall not be used."

#### `foxbms_posix_main.c`

| Line | Code | Issue |
|---|---|---|
| 23 | `#include <signal.h>` | Prohibited header included |
| 134 | `signal(SIGINT, sigint_handler)` | Use of `signal()` from prohibited header |

**Deviation rationale:** The POSIX SIL vECU requires `SIGINT` handling for graceful shutdown when run interactively or under timeout. `signal()` is the standard POSIX mechanism for this. A documented deviation is required.

---

### V-010 — Rule 21.6 [Required]: Standard library I/O functions used **[DEV-ELIGIBLE]**

**Rule text:** "The Standard Library input/output functions shall not be used in production code."

Both `foxbms_posix_main.c` and `hal_stubs_posix.c` use `fprintf`, `fflush`, `perror`, and `setbuf` extensively (30+ call sites). These functions are from `<stdio.h>`.

Representative call sites in `foxbms_posix_main.c`:

| Lines | Functions |
|---|---|
| 93, 97, 102 | `perror()`, `fprintf(stderr, ...)` |
| 135–136 | `setbuf(stdout, NULL)`, `setbuf(stderr, NULL)` |
| 150–221 | `fprintf(stderr, ...)` in init and main loop |
| 263, 287, 302 | `fprintf(stderr, ...)` for deadline violation logging |

**Deviation rationale:** The `<stdio.h>` functions are used exclusively for diagnostic output in a Linux SIL harness, not in production embedded firmware. The POSIX build target (`foxbms-posix`) is never flashed to hardware. A blanket deviation for the SIL port is appropriate.

---

### V-011 — Rule 21.7 [Required]: Use of `atoi()`

**Rule text:** "The atof, atoi, atol and atoll functions of <stdlib.h> shall not be used."

#### `foxbms_posix_main.c`

| Line | Code | Issue |
|---|---|---|
| 142 | `timeout_s = atoi(argv[i + 1])` | `atoi` has no error indication; returns `0` for invalid input silently |

**Recommended fix:** Replace with `strtol` and check `errno` and `endptr`:
```c
char *endptr;
long v = strtol(argv[i + 1], &endptr, 10);
if (endptr != argv[i + 1] && *endptr == '\0' && v > 0) { timeout_s = (int)v; }
```

---

### V-012 — Rule 21.8 [Required]: Use of `exit()`, `getenv()` from `<stdlib.h>` **[DEV-ELIGIBLE]**

**Rule text:** "The library functions abort, exit, getenv and system of <stdlib.h> shall not be used."

| File | Line | Function | Notes |
|---|---|---|---|
| `foxbms_posix_main.c` | 148 | `getenv("FOXBMS_CAN_IF")` | Reads CAN interface name from environment |
| `hal_stubs_posix.c` | 70 | `getenv("FOXBMS_CAN_IF")` | Same in constructor |
| `hal_stubs_posix.c` | 98–99 | `getenv("FOXBMS_CAN_IF")` | Same in `canInit()` |
| `hal_stubs_posix.c` | 656 | `exit(1)` | Called in `FAS_StoreAssertLocation()` on assertion failure |

**Deviation rationale:**
- `getenv` is the only practical mechanism for passing the CAN interface name to the vECU binary in a containerized/CI environment. A deviation is appropriate for the SIL port.
- `exit(1)` in `FAS_StoreAssertLocation` is intentional: it converts a TMS570 infinite loop into a process abort that test harnesses can detect. This behaviour is safety-correct for the SIL context.

---

### V-013 — Rule 1.2 [Advisory]: Use of GCC language extensions **[DEV-ELIGIBLE]**

**Rule text:** "Language extensions should not be used."

| File | Line | Extension | Notes |
|---|---|---|---|
| `hal_stubs_posix.c` | 66 | `__attribute__((constructor))` | GCC constructor attribute (inside `HITL-LOCK` — **cannot be modified**) |
| `hal_stubs_posix.c` | 671 | `__attribute__((aligned(4)))` in `REG_BUF` macro | GCC alignment attribute |

**Deviation rationale:** `__attribute__((constructor))` is required for pre-`main()` SocketCAN setup. `__attribute__((aligned(4)))` ensures register-buffer arrays are aligned to 4-byte boundaries as TMS570 peripheral registers expect. Both are GCC extensions unavoidable on the Linux target.

---

### V-014 — Rule 2.3 [Advisory]: Unused type declarations

**Rule text:** "A project should not contain unused type declarations."

#### `hal_stubs_posix.c` — lines 42–51

The following typedefs are declared to prevent type conflicts with HALCoGen headers, but may not be used within the translation unit itself:

| Line | Declaration |
|---|---|
| 42 | `typedef uint32_t uint32;` |
| 43 | `typedef uint16_t uint16;` |
| 44 | `typedef uint8_t uint8;` |
| 45 | `typedef int32_t sint32;` |
| 46 | `typedef int16_t sint16;` |
| 47 | `typedef int8_t sint8;` |
| 48 | `typedef _Bool boolean;` |
| 51 | `#define NULL_PTR ((void *)0)` |

**Note:** These definitions exist to satisfy HALCoGen-generated code that is not compiled in the POSIX build. They have functional purpose but the declaration-in-same-TU is advisory only.

---

### V-015 — Rule 8.3 [Required]: Inconsistent declaration and definition types

**Rule text:** "All declarations of an object or function shall use the same names and type qualifiers."

#### `foxbms_posix_main.c`

| Line | Code | Issue |
|---|---|---|
| 66 | `extern char diag_device[];` | The actual definition in `diag_cfg.c` is `DIAG_DEV_s diag_device`. Declaring it as `char[]` (a different type) violates Rule 8.3. This is explicitly documented in a comment: *"actually DIAG_DEV_s, but we just pass the address"*. |

**Recommended fix:** Include the appropriate foxBMS header to get `DIAG_DEV_s` or use a proper opaque-handle pattern with `void *`. The current approach causes undefined behaviour under strict aliasing rules.

---

### V-017 — Rule 8.4 [Required]: No compatible declaration visible when external function is defined

**Rule text:** "A compatible declaration shall be visible when an object or function with external linkage is defined."

When a function with external linkage is defined (i.e., without `static`), a matching prototype must be in scope at the definition point. The standard mechanism is to include a header containing the prototype before the definition.

#### `foxbms_posix_main.c`

| Line (pre-fix) | Symbol | Issue |
|---|---|---|
| 121 | `int posix_can_open(const char *ifname)` | Defined with external linkage; no prior declaration visible in TU |
| 148 | `int posix_can_send(uint32_t id, const uint8_t *data, uint8_t dlc)` | Defined with external linkage; no prior declaration visible in TU |

**Root cause:** `posix_can_open` and `posix_can_send` were defined directly below the `#include` block with no preceding prototype in a header file. Their `extern` re-declarations in `hal_stubs_posix.c` (lines 62, 92–93, 115) and `sil_layer.c` (line 17) demonstrate external linkage but do not satisfy Rule 8.4 for the definition TU.

**Fix applied (2026-03-27):**

1. Created `src/posix_can.h` containing prototypes for:
   - `int posix_can_open(const char *ifname);`
   - `int posix_can_send(uint32_t id, const uint8_t *data, uint8_t dlc);`
   - `void posix_can_rx_inject(uint32_t id, uint8_t *data, uint8_t dlc);`

2. Added `#include "posix_can.h"` to `foxbms_posix_main.c` immediately after `#include "sil_layer.h"` (line 38), before the first function definition.

3. Removed the redundant inline `extern void posix_can_rx_inject(...)` declaration (previously line 170), which is now provided by the header — fixing the co-located Rule 8.5 violation for that symbol.

**Status: FIXED**

**Scope note:** The same `extern` re-declarations in `hal_stubs_posix.c` (lines 62, 92–93, 115) and `sil_layer.c` (line 17) are now candidates for replacement with `#include "posix_can.h"`. Those files were not modified in this pass; their Rule 8.5 violations remain open (see V-002).

---

### V-016 — Rule 15.5 [Advisory]: Functions with multiple exit points

**Rule text:** "A function should have a single point of exit at the end of the function."

#### `foxbms_posix_main.c`

| Function | Multiple-return lines | Notes |
|---|---|---|
| `posix_can_open()` | 88 (early return), 93 (on error), 97 (on ioctl fail), 101 (on bind fail), 103 (success) | 5 exit points |
| `main()` | `break` at 223, 274 (running=0+break), `return 0` at 435 | Multiple forced exits |

**Note:** Multiple returns in `posix_can_open()` are common error-handling pattern for POSIX socket setup. Advisory only; no safety impact in the SIL context.

---

## HITL-LOCK Regions: Violations Not Actionable

The following violations fall inside `HITL-LOCK` regions. Per the project HITL lock policy, these **cannot be modified** without explicit human approval. They are documented here for traceability only.

| File | Lock ID | Line | Rule | Violation |
|---|---|---|---|---|
| `foxbms_posix_main.c` | `MAIN-LOOP-TIMING` | 255 | 8.5 | `extern void MEAS_Control(void)` inside block |
| `hal_stubs_posix.c` | `HAL-EARLY-INIT` | 66 | 1.2 | `__attribute__((constructor))` GCC extension |
| `hal_stubs_posix.c` | `HAL-SBC-STATE` | 704–710 | — | Within locked region; no new violations added |

---

## Prioritised Remediation Plan

### P1 — High-priority (Required rules, production-relevant)

1. **V-015 (Rule 8.3):** Fix `diag_device` type mismatch (line 66, `foxbms_posix_main.c`).
2. **V-007 (Rule 17.7):** Check return values of `DIAG_Initialize` and `fcntl` (lines 94, 177).
3. **V-006 (Rule 14.4):** Replace non-Boolean controlling expressions with explicit comparisons (`!= 0`).
4. **V-003 / V-004 (Rules 10.3/10.4):** Add explicit casts at arithmetic narrowing points (lines 342–343, 363, 887–889).

### P2 — Medium-priority (Required rules, deviation-eligible)

5. **V-011 (Rule 21.7):** Replace `atoi` with `strtol` (1 occurrence).
6. **V-001 (Rule 7.2):** Add `u` suffix to all unsigned integer literals (8 occurrences).
7. **V-002 (Rule 8.5):** Move `extern` declarations to a new header file.
8. **V-005 (Rule 11.3):** Add `/* MISRA deviation: POSIX socket API requires sockaddr cast */` comments.

### P3 — Deviation-document (DEV-ELIGIBLE violations)

9. **V-008 (Rule 21.1):** Document `_GNU_SOURCE` deviation.
10. **V-009 (Rule 21.5):** Document `<signal.h>` deviation for SIL graceful shutdown.
11. **V-010 (Rule 21.6):** Document blanket `<stdio.h>` deviation for SIL diagnostic output.
12. **V-012 (Rule 21.8):** Document `getenv` and `exit` deviations for POSIX SIL context.

---

## ASPICE / Traceability Note

This report partially satisfies the software quality criterion for ASPICE SWE.1 software requirements by providing evidence of static analysis coverage of the POSIX SIL port. It does not replace a tool-generated MISRA compliance report from a certified static analyser (e.g., PC-lint Plus, Polyspace, Helix QAC).

---

---

## Rescan Results — `foxbms_posix_main.c` (2026-03-27)

Remediation was applied to `foxbms_posix_main.c` only. `hal_stubs_posix.c` and `sil_layer.c` are unchanged.
HITL-LOCK region `MAIN-LOOP-TIMING` (lines 308–369 of the revised file) was not modified per lock policy.

### Status per violation category (foxbms_posix_main.c)

| ID | Rule | Previous count | Status after fix | Notes |
|---|---|---|---|---|
| V-001 | 7.2 | 5 | **FIXED** | `u` suffix added: `0u`, `100u`, `5000u`, `0xFFFFu`, `1000u` |
| V-002 | 8.5 | 16 | **MOSTLY FIXED** | 15 externs moved to file scope; 1 (`MEAS_Control`, line 318) in HITL-LOCK — untouchable |
| V-003 | 10.3 | 4 | **FIXED** | Explicit casts: `(uint16_t)(…)`, `(int16_t)(…)`; `dt` cast has documented deviation |
| V-004 | 10.4 | 4 | **FIXED** | `(size_t)n`, `(ssize_t)sizeof(…)` casts applied |
| V-005 | 11.3 | 2 | **FIXED** | sockaddr cast has deviation comment; bitmap uses `memcpy` instead of pointer cast |
| V-006 | 14.4 | 1 | **FIXED** | `while (running != 0)` |
| V-007 | 17.7 | 5 | **FIXED** | `fcntl` return checked; `signal`/`OS_CheckTimeHasPassedSelfTest` cast to void; `posix_can_open`/`DIAG_Initialize` return checked |
| V-008 | 21.1 | 1 | **DOCUMENTED** | Deviation comment DEV-SIL-21.1 added |
| V-009 | 21.5 | 1 | **DOCUMENTED** | Deviation comment DEV-SIL-21.5 added |
| V-010 | 21.6 | 30+ | **DOCUMENTED** | Blanket deviation comment DEV-SIL-21.6 added |
| V-011 | 21.7 | 1 | **FIXED** | `atoi` replaced with `strtol` + `errno` check |
| V-012 | 21.8 | 1 | **DOCUMENTED** | Deviation comment DEV-SIL-21.8 added |
| V-015 | 8.3 | 1 | **PARTIALLY FIXED** | `char[]` → `uint8_t[]` with deviation comment DEV-SIL-8.3; full fix requires including `DIAG_DEV_s` header |
| V-016 | 15.5 | 2 | **OPEN (Advisory)** | Multiple exit points in `posix_can_open` and `main` — acceptable pattern for POSIX SIL |
| V-017 | 8.4 | 2 | **FIXED** | `posix_can.h` created; included before definitions of `posix_can_open` and `posix_can_send` |

### Remaining open items in `foxbms_posix_main.c`

| Location | Rule | Reason unfixed |
|---|---|---|
| Line 318 (HITL-LOCK) | 8.5 | `extern void MEAS_Control(void)` inside locked region — HITL policy prohibits modification |
| Lines 21.1 / 21.5 / 21.6 / 21.8 | DEV-ELIGIBLE | Platform-required; deviation documented inline |
| Line 78 | 8.3 | Opaque declaration pattern; full fix requires production header inclusion |
| Multiple | 15.5 (Advisory) | Acceptable error-handling pattern; no safety impact |

**V-017 (Rule 8.4) is FIXED** — `posix_can.h` added in second remediation pass (2026-03-27).

### Violations remaining in `hal_stubs_posix.c` and `sil_layer.c`

These files were not modified in this remediation pass. Their violations (V-001 through V-014 where applicable) remain open. A separate remediation pass is recommended.

---

*Original report generated by manual analysis against commit `9030bab`. Rescan performed after remediation commit (see git log). Re-run full analysis after any modification to `src/*.c`.*
