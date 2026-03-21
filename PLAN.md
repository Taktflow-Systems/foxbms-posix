# foxBMS POSIX vECU — Consolidated Roadmap

**Last updated**: 2026-03-21
**Status**: BMS in NORMAL state — all critical milestones achieved

---

## Completed Work

- [x] Compile foxBMS 170+ sources for x86-64 with GCC 13
- [x] Stub 60+ TMS570 register bases to RAM buffers
- [x] Replace FreeRTOS scheduler with cooperative main loop
- [x] Stub 80+ HAL functions (SPI, I2C, DMA, GIO, ADC, etc.)
- [x] Bypass SBC, RTC, DIAG, current sensor presence checks
- [x] CAN TX via SocketCAN (15+ message types periodic)
- [x] CAN RX via SocketCAN ring buffer → foxBMS callbacks
- [x] Database passthrough (direct call instead of FreeRTOS queue)
- [x] SPS contactor simulation (track requested/actual state per channel)
- [x] AFE queue routing: CAN → ftsk_canToAfeCellVoltagesQueue → DECAN
- [x] MEAS_Control() in cooperative main loop
- [x] Plant model: IVT current (0A), IVT voltage (66600mV)
- [x] Plant model: cell voltages (18 cells × 3700mV) — foxBMS big-endian encoding verified
- [x] Plant model: cell temperatures (25.0°C)
- [x] Plant model: BMS state requests (STANDBY → NORMAL)
- [x] Plant model: IVT voltage 3 (0x524) for redundancy module HV bus voltage
- [x] Cell voltage invalid flag = 1 (DECAN_DATA_IS_VALID = 1, not 0)
- [x] String voltage calculation: 18 × 3700 = 66600mV
- [x] Precharge voltage check passes (string voltage ≈ HV bus voltage)
- [x] SYS state machine reaches RUNNING
- [x] BMS state machine: IDLE → STANDBY → PRECHARGE → **NORMAL**
- [x] Contactors: 3 channels close during precharge, verified via SPS trace
- [x] SOC: 50% initial (counting method)
- [x] Windows unit tests: 183+ passing (Ceedling + GCC 15)

## Phase 2: Realistic Simulation (Priority: P2)

### 2.1 Dynamic current model
- [ ] Plant model: vary current based on contactor state (10A discharge when NORMAL)
- [ ] SOC should decrease over time
- [ ] Verify 0x235 SOC changes

### 2.2 Cell voltage variation
- [ ] Add small noise (±10mV) per cell
- [ ] Vary voltage based on SOC (3.4V at 0%, 4.2V at 100%)
- [ ] Verify plausibility checks don't trigger

### 2.3 Dynamic pack voltage (IR drop)
- [ ] V_pack = N_cells × V_cell - I × R_internal
- [ ] R_internal = ~50mΩ per cell

## Phase 3: Fault Injection (Priority: P3)

### 3.1 Overvoltage
- [ ] Set one cell to 4.5V → foxBMS opens contactors
- [ ] Verify 0x220 shows ERROR state

### 3.2 Undervoltage
- [ ] Set one cell to 2.5V → foxBMS opens contactors

### 3.3 Overtemperature
- [ ] Set one sensor to 60°C → warning, 80°C → contactors open

### 3.4 Overcurrent
- [ ] Set IVT current to 200A → foxBMS opens contactors

### 3.5 Cell imbalance
- [ ] Set cells to 3.5V, 3.7V, 3.9V → balancing activates

### 3.6 Sensor failure
- [ ] Send invalid flag for one cell → foxBMS detects missing cell

## Phase 4: Integration (Priority: P4)

### 4.1 Dockerize
- [ ] Dockerfile for foxbms-vecu
- [ ] docker-compose alongside taktflow SIL ECUs

### 4.2 Connect to real CAN bus (HIL)
- [ ] FOXBMS_CAN_IF=can0 → canable on HIL bench
- [ ] Run alongside physical STM32/TMS570 ECUs

### 4.3 XCP integration
- [ ] Add XCP on TCP/UDP for real-time monitoring
- [ ] Connect with CANape for visualization

### 4.4 Selective DIAG_Handler
- [ ] Allow real error detection for software checks
- [ ] Suppress only hardware-absent errors
