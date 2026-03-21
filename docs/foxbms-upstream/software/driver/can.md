# CAN Module

**Source**: [docs.foxbms.org — CAN](https://iisb-foxbms.iisb.fraunhofer.de/foxbms/docs/latest/software/modules/driver/can/can.html)
**Files**: `src/app/driver/can/can.c`, `can.h`, `can_cfg.c`, `can_cfg.h`, `can_helper.c`, `can_cbs.h`
**Callbacks**: `src/app/driver/can/cbs/` (tx_cyclic, tx_async, rx)

---

## TX Configuration

`can_txMessages[]` table defines each TX message:

| Field | Description |
|-------|-------------|
| CAN ID | Message identifier (11-bit standard) |
| DLC | Data length code (max 8 bytes) |
| Repetition time | Period in ms (multiples of 10) |
| Repetition phase | Initial delay before first TX |
| Byte order | Endianness (big-endian for foxBMS) |
| Callback | Function pointer that builds the CAN data |
| Multiplexer | Optional pointer for mux-based messages |

### TX Flow

1. `CAN_PeriodicTransmit()` called every 10ms (from 10ms task)
2. Checks each message: has its period elapsed?
3. If yes → calls callback → callback encodes signals → calls `canTransmit()`
4. If TX fails → queued in `ftsk_canTxUnsentMessagesQueue` for retry

### TX Helper Functions

```c
CAN_TxSetMessageDataWithSignalData()  // Encode signal into 64-bit message variable
CAN_TxSetCanDataWithMessageData()     // Transfer to low-level driver
```

## RX Configuration

`can_rxMessages[]` table defines each RX message:

| Field | Description |
|-------|-------------|
| CAN ID | Message identifier |
| DLC | Expected data length |
| Byte order | Endianness |
| Callback | Function pointer that decodes the CAN data |

### RX Flow

1. CAN hardware ISR fires → `CAN_RxInterrupt()` called
2. Message placed in `ftsk_canRxQueue`
3. `CAN_ReadRxBuffer()` called every 1ms (from 1ms task)
4. Dequeues frames → dispatches to matching RX callback
5. Callbacks decode signals → write to database

### RX Helper Functions

```c
CAN_RxGetMessageDataFromCanData()     // Copy CAN frame to 64-bit variable
CAN_RxGetSignalDataFromMessageData()  // Extract individual signal
```

## Hardware Configuration

- 64 mailboxes per CAN interface: 32 TX + 32 RX (TI HALCoGen)
- Mailboxes 61-64: extended 29-bit identifiers
- E2E protection via AUTOSAR (counter + CRC per message)

## POSIX Port Differences

| Feature | Production | POSIX |
|---------|-----------|-------|
| TX | HW mailbox → CAN bus | `posix_can_send()` → SocketCAN |
| RX | HW ISR → queue | `read(can_socket)` → ring buffer |
| Mailbox | 64 HW mailboxes | Tracked in `can_mailbox_id[]` array |
| TX arbitration | HW bus arbitration | None (GA-11) |
| TX failure/retry | HW mailbox full → queue | Always succeeds on SocketCAN |
| E2E protection | AUTOSAR counter + CRC | Bypassed (GA-27) |
| TX period | Timer ISR enforced | Fires when loop reaches it (GA-26) |
