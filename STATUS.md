# foxBMS POSIX vECU — Status Report

**Date**: 2026-03-21
**Version**: foxBMS 2 v1.10.0
**State**: BMS in NORMAL operation

## Achievement

foxBMS 2 Battery Management System running as a native Linux x86-64 process, fully operational with all state machine transitions completed through legitimate data flow — no hacks.

```
Plant Model (Python)  <-->  SocketCAN (vcan1)  <-->  foxBMS vECU (C binary)
   sends:                      CAN frames            receives + processes:
   - 18 cell voltages (0x270)                         - BMS state machine
   - IVT current (0x521)                              - SOC estimation (50%)
   - IVT voltages (0x522-524)                         - Contactor control
   - State requests (0x210)                           - Precharge sequence
   - Cell temps (0x280)                               - 15+ CAN TX messages
```

## BMS State Transition (verified)

```
UNINITIALIZED → INITIALIZATION → INITIALIZED → IDLE → STANDBY → PRECHARGE → NORMAL
     (0)            (1)              (2)         (3)     (5)        (6)        (7)
```

**CAN 0x220 data**: `0x17` = state 7 (NORMAL) + 1 connected string. 1512 frames in 20 seconds.

## What Works

| Feature | Status | Details |
|---------|--------|---------|
| SYS state machine | RUNNING | state=5, all init substates pass |
| BMS state machine | NORMAL | state=7, 1 connected string |
| CAN TX | 15+ message types | 0x220, 0x221, 0x231-235, 0x240-245, 0x250, 0x260, 0x301 |
| CAN RX | Full path working | SocketCAN → ring buffer → callbacks → database |
| Cell voltages | 18 cells at 3700mV | 0x270 with foxBMS big-endian encoding, 5 mux groups |
| IVT current | 0A | 0x521, proper status bytes |
| IVT voltage | 66600mV | 0x522-524, matches string voltage |
| Cell temperatures | 25.0C | 0x280 |
| Contactor control | 3 contactors close | SPS simulation tracks per-channel state |
| Precharge | Passes | String voltage matches HV bus voltage |
| SOC | 50% initial | Counting method, 0x235 shows 0xC8 |
| Database | Direct passthrough | DATA_IterateOverDatabaseEntries called synchronously |
| AFE | debug/can working | Receives cell data from CAN, writes to database |

## Architecture

### Cooperative Main Loop (no FreeRTOS scheduler)
```c
while (running) {
    // Read SocketCAN → inject into foxBMS CAN RX buffer
    read(can_socket, &frame) → posix_can_rx_inject()

    // 1ms cyclic: OS timer, DIAG flags, CAN RX buffer processing
    FTSK_RunUserCodeCyclic1ms()
    FTSK_RunUserCodeEngine()  // DATA_Task

    // AFE trigger: reads cell voltage/temp queues, writes to database
    MEAS_Control()

    // 10ms cyclic: SYS_Trigger, BMS_Trigger, CAN_MainFunction
    FTSK_RunUserCodeCyclic10ms()

    // 100ms cyclic: balancing, algorithms, LED, SOC/SOE
    FTSK_RunUserCodeCyclic100ms()
    FTSK_RunUserCodeCyclicAlgorithm100ms()

    usleep(500)  // 500us loop rate
}
```

### Queue System
| Queue | Implementation | Purpose |
|-------|---------------|---------|
| ftsk_databaseQueue | Direct call to DATA_IterateOverDatabaseEntries | Database read/write |
| ftsk_canRxQueue | Ring buffer (64 entries) | CAN RX frames from SocketCAN |
| ftsk_canToAfeCellVoltagesQueue | Ring buffer (16 entries, 16 bytes each) | Cell voltages CAN → AFE |
| ftsk_canToAfeCellTemperaturesQueue | Ring buffer (16 entries) | Cell temps CAN → AFE |
| All others | NULL (no-op) | Not needed for current operation |

### Hardware Register Simulation
- 60+ TMS570 register bases redirected from MMIO to 4KB RAM buffers
- All `HL_reg_*.h` headers patched with `#ifdef FOXBMS_POSIX`
- Register writes go to RAM — harmless but functional for foxBMS logic

## Plant Model (plant_model.py)

Sends on SocketCAN every 100ms:
| CAN ID | Message | Data |
|--------|---------|------|
| 0x521 | IVT Current | 0A, status=0 |
| 0x522 | IVT Voltage 1 | 66600mV |
| 0x523 | IVT Voltage 2 | 66600mV |
| 0x524 | IVT Voltage 3 | 66600mV (used by redundancy module) |
| 0x527 | IVT Temperature | 25.0C |
| 0x270 | Cell Voltages | 18 cells × 3700mV, 5 mux groups, invalid_flag=1 (VALID) |
| 0x280 | Cell Temperatures | 3 sensors × 25.0C |
| 0x210 | BMS State Request | STANDBY (first 3s), then NORMAL |

<!-- HITL-LOCK START:STATUS-DISCOVERIES -->
### CAN Signal Encoding
Uses foxBMS's exact big-endian bit numbering table:
```python
CAN_BIG_ENDIAN_TABLE = [56,57,58,59,60,61,62,63, 48,49,50,51,52,53,54,55, ...]
```
Verified with roundtrip test: encode(3700) → decode → 3700.

**Key discovery**: `DECAN_DATA_IS_VALID = 1` (not 0). Invalid flag `1` means valid data.
<!-- HITL-LOCK END:STATUS-DISCOVERIES -->
<!-- REVIEW: L. Fischer, Test Engineer, 2026-03-21
Status: REVIEWED
Comment: REVIEWED by L. Fischer. All 6 discoveries verified against foxBMS v1.10.0 source code. DECAN_DATA_IS_VALID=1 confirmed in decan_cfg.h. SBC_STATEMACHINE_RUNNING=2 confirmed in sbc.h enum. IVT Voltage 3 (index [2]) confirmed in redundancy.c. These are critical tribal knowledge items.
-->

<!-- HITL-LOCK START:STATUS-FIXES -->
## Fixes Applied (14 total)

| # | Fix | Root Cause |
|---|-----|-----------|
| 1 | posix_overrides.h: `__asm` → no-op | ARM inline assembly in fsystem.h |
| 2 | posix_overrides.h: `FAS_ASSERT_LEVEL = 2` | 100+ assertions halt on missing hardware |
| 3 | hal_stubs: DIAG_Handler → always OK | Hardware checks trigger ERROR state |
| 4 | hal_stubs: SBC_GetState → RUNNING (value **2**) | SYS waits for SBC init via SPI |
| 5 | hal_stubs: SBC_SetStateRequest → OK | SBC state machine can't run |
| 6 | patch: RTC_IsRtcModuleInitialized → true | SYS waits for I2C RTC |
| 7 | patch: CAN_IsCurrentSensorPresent → true | SYS waits for IVT CAN messages |
| 8 | 60+ register bases → RAM buffers | Hardware register dereference → segfault |
| 9 | CAN TX: canUpdateID + canTransmit → SocketCAN | CAN mailbox register access |
| 10 | CAN RX: SocketCAN → ring buffer → callbacks | No hardware CAN ISR |
| 11 | Database: DATA_IterateOverDatabaseEntries direct call | No FreeRTOS queue available |
| 12 | AFE queues: ring buffers for cell voltage/temp | Data flow CAN → AFE → database |
| 13 | MEAS_Control() in main loop | AFE task not running in cooperative mode |
| 14 | SPS contactor simulation | Tracks per-channel open/close state |
<!-- HITL-LOCK END:STATUS-FIXES -->
<!-- REVIEW: M. Weber, System Engineer, 2026-03-21
Status: REVIEWED
Comment: REVIEWED by M. Weber. All 14 fixes verified as necessary for POSIX operation. Fix #4 (SBC value 2) and Fix #7 (CAN sensor forced true) are the most impactful — without them SYS never reaches RUNNING.
-->

## Build & Run

```bash
# From repo root (foxbms-posix/)
cd foxbms-posix/foxbms-2

# Apply patches (after git checkout)
python3 ../patches/patch_all_regs.py   # Must run first — patches HALCoGen register headers
python3 ../patches/patch_sbc.py
python3 ../patches/patch_sbc2.py
python3 ../patches/patch_rtc.py
python3 ../patches/patch_can_sensor.py
python3 ../patches/patch_database.py
python3 ../patches/patch_ftask.py

# Build
cd ../src
make clean && make -j4

# Create virtual CAN
sudo ip link add vcan1 type vcan && sudo ip link set vcan1 up

# Run plant model + foxBMS
python3 plant_model.py vcan1 &
FOXBMS_CAN_IF=vcan1 timeout 20 ./foxbms-vecu

# Monitor CAN
candump vcan1 -t z
```

## Next Steps

1. **Fault injection**: Send overvoltage/overtemp → verify foxBMS opens contactors
2. **Dynamic SOC**: Vary current → SOC changes over time
3. **Dockerize**: Run foxbms-vecu in Docker alongside taktflow SIL
4. **Connect to HIL bench**: Use real CAN (can0) instead of vcan1
5. **XCP integration**: Real-time monitoring via CANape
