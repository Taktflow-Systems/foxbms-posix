# foxBMS POSIX vECU — Consolidated Roadmap

**Last updated**: 2026-03-21
**Consolidates**: plan-foxbms-posix-incremental.md, plan-foxbms-posix-realistic.md, plan-foxbms-posix-vecu.md

---

## Completed Work

- [x] Compile foxBMS 170+ sources for x86-64 with GCC 13
- [x] Stub 60+ TMS570 register bases to RAM buffers
- [x] Replace FreeRTOS scheduler with cooperative main loop
- [x] Stub 80+ HAL functions (SPI, I2C, DMA, GIO, ADC, etc.)
- [x] Bypass SBC, RTC, DIAG, current sensor presence checks
- [x] CAN TX via SocketCAN (15 message types periodic)
- [x] CAN RX via SocketCAN ring buffer -> foxBMS callbacks
- [x] Database passthrough (direct call instead of FreeRTOS queue)
- [x] SPS contactor simulation (track requested/actual state per channel)
- [x] Plant model: IVT current (0A), IVT voltage (22.2V), state requests
- [x] Plant model: cell voltage messages (0x270) — encoding unverified
- [x] Plant model: cell temperature messages (0x280) — encoding approximate
- [x] SYS state machine reaches RUNNING
- [x] BMS transitions IDLE -> STANDBY -> PRECHARGE
- [x] Windows unit tests: 183+ passing (Ceedling + GCC 15)

## Phase 1: Reach BMS NORMAL State (Priority: P1)

### 1.1 Fix cell voltage CAN encoding
- **Status**: BLOCKED — this is the #1 blocker
- **Problem**: `plant_model.py` manual bit-banging for 0x270 produces wrong data. foxBMS reads string voltage = 0mV.
- **Fix**: Use `cantools` library to encode from foxBMS DBC file
- **Location**: DBC file is in `foxbms-2/tools/dbc/` or `foxbms-2/src/app/driver/config/`
- **Verify**: foxBMS database shows cell voltages, string voltage > 0

### 1.2 Fix cell temperature CAN encoding
- **Status**: NOT VERIFIED
- **Problem**: `encode_cell_temp_msg()` uses same layout as voltages (comment says "approximate")
- **Fix**: Check DBC for 0x280 signal definitions, use `cantools`
- **Verify**: foxBMS temperature data populated, no plausibility errors

### 1.3 Verify precharge voltage check passes
- **Status**: BLOCKED by 1.1
- **Condition**: |string_voltage - pack_voltage| < threshold
- **Verify**: BMS transitions PRECHARGE -> NORMAL, CAN 0x220 shows NORMAL state

## Phase 2: Dynamic Plant Model (Priority: P3)

### 2.1 Track contactor state from foxBMS CAN TX
- Read foxBMS 0x240 (String State) to know when contactors are closed
- Plant model adjusts current output based on contactor state

### 2.2 Dynamic current model
- Contactors closed: simulate 10A discharge
- Contactors open: 0A
- Update IVT current (0x521) accordingly
- **Verify**: SOC decreases during discharge (CAN 0x235 changes)

### 2.3 Dynamic pack voltage with IR drop
- V_pack = N_cells x V_cell - I x R_internal
- Update IVT voltage (0x522) accordingly
- **Verify**: Pack voltage in CAN 0x233 matches model

### 2.4 Cell voltage noise and variation
- Add +/-10mV random noise to cell voltages for realism
- Vary individual cells slightly to test imbalance detection

## Phase 3: Fault Injection (Priority: P4)

### 3.1 Implement selective DIAG_Handler
- Classify DIAG IDs: software checks (keep) vs hardware-absent checks (suppress)
- `DIAG_Handler` stub checks ID range, returns real result for software IDs
- **Prerequisite**: Must reach NORMAL state first

### 3.2 Fault injection scenarios
| Scenario | Input | Expected Response |
|----------|-------|-------------------|
| Overvoltage | One cell at 4.5V (0x270) | foxBMS opens contactors |
| Undervoltage | One cell at 2.5V (0x270) | foxBMS opens contactors |
| Overtemperature | One sensor at 80C (0x280) | foxBMS opens contactors |
| Overcurrent | 200A via 0x521 | foxBMS opens contactors |
| Cell imbalance | Cells at 3.5/3.7/3.9V | Balancing activates |
| Sensor failure | Invalid flag in 0x270 | foxBMS detects missing cell |

## Phase 4: Docker & HIL Integration (Priority: P5)

### 4.1 Dockerfile for foxBMS vECU
- Ubuntu base, copy binary + stubs
- Entrypoint: run foxbms-vecu on shared vcan

### 4.2 docker-compose integration
- Add foxbms-vecu service alongside taktflow SIL ECUs (CVC, FZC, RZC)
- Shared virtual CAN network
- Plant model as separate container or sidecar

### 4.3 Real CAN bus (HIL bench)
- `FOXBMS_CAN_IF=can0` for real CAN via canable USB adapter
- foxBMS sends 0x220/0x235 alongside taktflow ECU messages on physical bus
- **Verify**: `candump can0` shows foxBMS + taktflow messages together

### 4.4 Full vehicle + battery simulation
- foxBMS monitors virtual battery, sends SOC/limits
- CVC reads foxBMS limits, adjusts torque request
- SC monitors foxBMS state for safety
- Plant model provides closed-loop simulation

## Dependencies

```
Phase 1 (1.1 -> 1.2 -> 1.3) -> Phase 2 -> Phase 3
                                              |
Phase 4.1 -> 4.2 -> 4.3 -> 4.4 -------------+
```

## Stubs That Should Stay As Stubs

These components are hardware-only and have no BMS behavior impact:

| Component | Why Stub Is OK |
|-----------|---------------|
| SPI/I2C/DMA drivers | No physical peripherals on POSIX |
| LED | Printf debug output instead |
| FRAM | RAM buffer (data lost on restart, acceptable) |
| PEX (port expander) | Contactor feedback handled by SPS stub |
| HT sensor | Temperature from CAN instead |
| RTC | System clock via `clock_gettime` |
| CRC | Software CRC implemented |
| Hardware registers | 60+ RAM buffers (4KB each) |
| FAS_ASSERT | NO_OPERATION level (hardware checks always fail) |

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| DBC encoding mismatch | Cell data rejected, NORMAL unreachable | Use `cantools` library, not manual encoding |
| foxBMS version update breaks patches | Build fails | Pin to v1.10.0, document patch targets |
| DIAG suppression masks real bugs | Incorrect BMS behavior | Implement selective DIAG (Phase 3.1) |
| Ring buffer overflow | CAN frames dropped silently | Monitor with trace, increase buffer if needed |
| Docker vcan networking | Container CAN isolation | Use `--network host` or vxcan pairs |
