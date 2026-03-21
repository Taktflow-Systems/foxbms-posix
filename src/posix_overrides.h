/**
 * @file    posix_overrides.h
 * @brief   Force-included header to override ARM-specific constructs for POSIX build
 */

#ifndef FOXBMS_POSIX_OVERRIDES_H_
#define FOXBMS_POSIX_OVERRIDES_H_

/* Stub out ARM inline assembly */
#define __asm(x) ((void)0)

/* Stub TI compiler pragmas */
#define __curpc() ((unsigned long)__builtin_return_address(0))

/* Stub TI-specific keywords */
#ifndef __attribute__
/* GCC has __attribute__, no need to redefine */
#endif

/* Override FAS_ASSERT record macro to avoid ARM-specific __curpc */
/* This is handled by the __curpc stub above */

/* FreeRTOS port-optimized task selection macros for x86 POSIX.
 * The TMS570 port uses ARM CLZ instruction. On x86, use __builtin_clz. */
#undef portGET_HIGHEST_PRIORITY
#define portGET_HIGHEST_PRIORITY(uxTopPriority, uxReadyPriorities) \
    (uxTopPriority) = (31UL - (uint32_t)__builtin_clz((uxReadyPriorities)))

#undef portRECORD_READY_PRIORITY
#define portRECORD_READY_PRIORITY(uxPriority, uxReadyPriorities) \
    (uxReadyPriorities) |= (1UL << (uxPriority))

#undef portRESET_READY_PRIORITY
#define portRESET_READY_PRIORITY(uxPriority, uxReadyPriorities) \
    (uxReadyPriorities) &= ~(1UL << (uxPriority))

/* GA-07: Override FAS_ASSERT to log location and exit instead of silently
 * continuing (level 2 NO_OP) or spinning forever (level 0/1).
 * This captures __FILE__ and __LINE__ which the original macro does not. */
#undef FAS_ASSERT_LEVEL
#define FAS_ASSERT_LEVEL (2u)  /* FAS_ASSERT_LEVEL_NO_OPERATION — keeps FAS_InfiniteLoop as no-op */

#include <stdio.h>
#include <stdlib.h>

/* Override the entire FAS_ASSERT macro after fassert.h defines it.
 * Since posix_overrides.h is force-included (-include), and fassert.h is
 * included later by source files, we redefine in hal_stubs_posix.c instead.
 * The FAS_ASSERT_LEVEL=2 makes FAS_InfiniteLoop() a no-op, and we override
 * FAS_StoreAssertLocation() in hal_stubs_posix.c to log + exit. */

/* DIAG_Handler: selective implementation in hal_stubs_posix.c (GA-06) */

/* Override ALL hardware register pointer macros to RAM buffers.
 * These are defined AFTER HL_reg_*.h is included, so we can't
 * override them here. Instead, we patch HL_reg_can.h on the laptop. */

#endif /* FOXBMS_POSIX_OVERRIDES_H_ */
