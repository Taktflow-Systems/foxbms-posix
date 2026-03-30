/**
 * @file    posix_can.h
 * @brief   POSIX SocketCAN function declarations for the foxBMS SIL harness.
 * @date    2026-03-27
 *
 * Satisfies MISRA C:2012 Rule 8.4: a compatible declaration shall be visible
 * when an object or function with external linkage is defined.
 *
 * Satisfies MISRA C:2012 Rule 8.5: each external function is declared in
 * exactly one header file (this file), not scattered across translation units.
 *
 * Function definitions:
 *   posix_can_open()     — foxbms_posix_main.c
 *   posix_can_send()     — foxbms_posix_main.c
 *   posix_can_rx_inject()— hal_stubs_posix.c
 */

#ifndef POSIX_CAN_H_
#define POSIX_CAN_H_

#include <stdint.h>

/**
 * @brief  Open a SocketCAN interface and bind it for CAN RAW communication.
 * @param  ifname  Interface name, e.g. "vcan1".
 * @return 0 on success, -1 on error (errno set by failing syscall).
 */
int posix_can_open(const char *ifname);

/**
 * @brief  Transmit a CAN frame via the open SocketCAN socket.
 * @param  id    Standard (11-bit) CAN frame identifier.
 * @param  data  Pointer to payload bytes.
 * @param  dlc   Data length code; clamped to 8 internally.
 * @return 0 on success, -1 if the socket is not open or the write fails.
 */
int posix_can_send(uint32_t id, const uint8_t *data, uint8_t dlc);

/**
 * @brief  Inject a received CAN frame into the foxBMS software CAN RX ring buffer.
 *         Called by foxbms_posix_main.c after reading a frame from SocketCAN.
 *         Defined in hal_stubs_posix.c.
 * @param  id    Standard (11-bit) CAN frame identifier.
 * @param  data  Pointer to payload bytes.
 * @param  dlc   Data length code (0–8).
 */
void posix_can_rx_inject(uint32_t id, uint8_t *data, uint8_t dlc);

#endif /* POSIX_CAN_H_ */
