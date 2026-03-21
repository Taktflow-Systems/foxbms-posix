/**
 * @file    posix_overrides.h
 * @brief   Force-included header to override ARM-specific constructs for POSIX build
 */

#ifndef FOXBMS_POSIX_OVERRIDES_H_
#define FOXBMS_POSIX_OVERRIDES_H_

/* Stub out ARM inline assembly */
#define __asm(x) ((void)0)

/* Stub TI compiler pragmas */
#define __curpc() ((unsigned long)0)

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

/* Override FAS_ASSERT to no-op instead of infinite loop */
#undef FAS_ASSERT_LEVEL
#define FAS_ASSERT_LEVEL (2u)  /* FAS_ASSERT_LEVEL_NO_OPERATION */

/* DIAG_Handler stubbed in hal_stubs_posix.c — diag.c excluded */

/* Override ALL hardware register pointer macros to RAM buffers.
 * These are defined AFTER HL_reg_*.h is included, so we can't
 * override them here. Instead, we patch HL_reg_can.h on the laptop. */

#endif /* FOXBMS_POSIX_OVERRIDES_H_ */
