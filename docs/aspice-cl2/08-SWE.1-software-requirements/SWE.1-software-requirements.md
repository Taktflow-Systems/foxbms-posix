# Software Requirements Specification

| Document ID | Rev | Date | Classification |
|---|---|---|---|
| SWE.1-001 | 1.0 | 2026-03-21 | Confidential |

## Revision History

| Rev | Date | Author | Reviewer | Description |
|---|---|---|---|---|
| 1.0 | 2026-03-21 | An Dao | -- | Initial release |

## 1. Purpose

This document specifies the software-level requirements for the foxBMS 2 POSIX port.
Each requirement is derived from the system requirements in SYS.2-001 and is
traceable forward to detailed design (SWE.3-001) and test cases (SWE.4-001 through
SWE.6-001). This document satisfies ASPICE SWE.1 and ISO 26262 Part 6 Clause 6.

## 2. Scope

All software requirements for the BMS application, engine, and driver layers running
on the POSIX SIL target.

## 3. References

| ID | Title |
|---|---|
| [SYS.2-001] | System Requirements Specification |
| [SWE.2-001] | Software Architecture Description |
| [SWE.3-001] | Software Detailed Design |
| [ISO-SSR-001] | Software Safety Requirements |

## 4. Definitions

| Term | Definition |
|---|---|
| ASIL | Automotive Safety Integrity Level |
| FATAL | Highest DIAG severity; triggers ERROR state |
| DB entry | A typed data structure in the foxBMS database |

## 5. Safety Requirements

### 5.1 Voltage Safety

| ID | Requirement | Derives From | ASIL |
|---|---|---|---|
| SW-REQ-001 | The SOA module shall compare each cell voltage against the overvoltage MSL threshold of 2800 mV. If any cell exceeds this value, SOA shall call DIAG_Handler with the CELL_VOLTAGE_OVERVOLTAGE_MSL event. | SYS-REQ-020 | D |
| SW-REQ-002 | The SOA module shall compare each cell voltage against the undervoltage MSL threshold of 1500 mV. If any cell falls below this value, SOA shall call DIAG_Handler with the CELL_VOLTAGE_UNDERVOLTAGE_MSL event. | SYS-REQ-021 | D |
| SW-REQ-003 | The SOA module shall compare each cell voltage against the overvoltage RSL threshold of 2750 mV and MOL threshold of 2720 mV, reporting the corresponding events. | SYS-REQ-020 | B |
| SW-REQ-004 | The SOA module shall compare each cell voltage against the undervoltage RSL threshold of 1550 mV and MOL threshold of 1580 mV, reporting the corresponding events. | SYS-REQ-021 | B |
| SW-REQ-005 | The SOA module shall detect deep discharge when any cell voltage falls to or below 1500 mV and report DEEP_DISCHARGE_DETECTED. This event shall latch and not auto-clear. | SYS-REQ-022 | D |

### 5.2 Current Safety

| ID | Requirement | Derives From | ASIL |
|---|---|---|---|
| SW-REQ-010 | The SOA module shall compare cell discharge current against MSL threshold of 180000 mA. If exceeded, SOA shall report OVERCURRENT_DISCHARGE_CELL_MSL. | SYS-REQ-030 | D |
| SW-REQ-011 | The SOA module shall compare cell charge current against MSL threshold of 180000 mA. If exceeded, SOA shall report OVERCURRENT_CHARGE_CELL_MSL. | SYS-REQ-031 | D |
| SW-REQ-012 | The SOA module shall compare string current against the string overcurrent discharge and charge thresholds, reporting STRING_OVERCURRENT_DISCHARGE_MSL and STRING_OVERCURRENT_CHARGE_MSL respectively. | SYS-REQ-013 | D |
| SW-REQ-013 | The SOA module shall compare pack current against the pack overcurrent thresholds, reporting PACK_OVERCURRENT_DISCHARGE_MSL and PACK_OVERCURRENT_CHARGE_MSL. | SYS-REQ-014 | D |
| SW-REQ-014 | The SOA module shall detect current flow on an open string and report CURRENT_ON_OPEN_STRING. | SYS-REQ-013 | D |

### 5.3 Temperature Safety

| ID | Requirement | Derives From | ASIL |
|---|---|---|---|
| SW-REQ-020 | The SOA module shall compare each cell temperature against the overtemperature discharge MSL threshold of 55 deg C. If exceeded, SOA shall report TEMP_OVERTEMPERATURE_DISCHARGE_MSL. | SYS-REQ-040 | D |
| SW-REQ-021 | The SOA module shall compare each cell temperature against the undertemperature discharge MSL threshold of -20 deg C. If below, SOA shall report TEMP_UNDERTEMPERATURE_DISCHARGE_MSL. | SYS-REQ-041 | D |
| SW-REQ-022 | The SOA module shall compare each cell temperature against the overtemperature charge MSL threshold of 45 deg C. If exceeded, SOA shall report TEMP_OVERTEMPERATURE_CHARGE_MSL. | SYS-REQ-042 | D |
| SW-REQ-023 | The SOA module shall compare each cell temperature against the undertemperature charge MSL threshold of -20 deg C. If below, SOA shall report TEMP_UNDERTEMPERATURE_CHARGE_MSL. | SYS-REQ-043 | D |

### 5.4 Diagnostic Handling

| ID | Requirement | Derives From | ASIL |
|---|---|---|---|
| SW-REQ-030 | The DIAG module shall maintain a table of at least 85 diagnostic identifiers, each with a configurable threshold counter and evaluation delay. | SYS-REQ-050, SYS-REQ-051, SYS-REQ-052 | D |
| SW-REQ-031 | When DIAG_Handler is called for a diagnostic event, it shall increment the threshold counter for that event. When the counter reaches the configured threshold, the event shall be flagged as FATAL. | SYS-REQ-053 | D |
| SW-REQ-032 | A FATAL diagnostic flag shall cause the BMS state machine to transition to the ERROR state within the next 100ms task cycle. | SYS-REQ-053 | D |
| SW-REQ-033 | The DIAG module shall support a configurable evaluation delay per diagnostic ID. The handler shall not re-evaluate the same event more frequently than this delay. | SYS-REQ-052 | C |
| SW-REQ-034 | The POSIX port shall suppress 24 hardware-absent diagnostic IDs by setting their severity to non-FATAL or disabling evaluation. | SYS-REQ-153 | QM |
| SW-REQ-035 | The POSIX port shall retain 61 software-checkable diagnostic IDs with their original severity and thresholds. | SYS-REQ-154 | D |

### 5.5 BMS State Machine

| ID | Requirement | Derives From | ASIL |
|---|---|---|---|
| SW-REQ-040 | The BMS state machine shall implement the states: STANDBY (5), PRECHARGE (6), NORMAL (7), ERROR (9). | SYS-REQ-090 | D |
| SW-REQ-041 | Transition from STANDBY to PRECHARGE shall occur only upon receipt of a valid state request via CAN ID 0x210. | SYS-REQ-091 | D |
| SW-REQ-042 | Transition from PRECHARGE to NORMAL shall occur when precharge conditions are met (voltage within tolerance). | SYS-REQ-092 | C |
| SW-REQ-043 | Transition from any operational state to ERROR shall occur when any FATAL diagnostic flag is set. | SYS-REQ-093 | D |
| SW-REQ-044 | In ERROR state, the BMS shall command all three contactors (string+, string-, precharge) to open. | SYS-REQ-054, SYS-REQ-114 | D |
| SW-REQ-045 | The BMS shall not exit ERROR state until both conditions are met: (a) the originating fault is cleared, and (b) an explicit STANDBY request is received via CAN. | SYS-REQ-055, SYS-REQ-094 | D |

### 5.6 System State Machine

| ID | Requirement | Derives From | ASIL |
|---|---|---|---|
| SW-REQ-050 | The SYS state machine shall implement states: UNINITIALIZED (0), INITIALIZATION (1), INITIALIZED (2), IDLE (3), RUNNING (5). | SYS-REQ-080, SYS-REQ-081, SYS-REQ-082, SYS-REQ-083 | C |
| SW-REQ-051 | SYS shall transition from UNINITIALIZED to INITIALIZATION on system startup. | SYS-REQ-080 | C |
| SW-REQ-052 | SYS shall transition from INITIALIZATION to INITIALIZED after all module initialization completes successfully. | SYS-REQ-081 | C |
| SW-REQ-053 | SYS shall transition from IDLE to RUNNING when all subsystems report ready. | SYS-REQ-083 | C |

## 6. Functional Requirements

### 6.1 Database

| ID | Requirement | Derives From | ASIL |
|---|---|---|---|
| SW-REQ-060 | The database module shall enforce single-writer-per-entry at architecture level. Each DATA_BLOCK_ID shall have exactly one producer module. If a second producer attempts to write the same entry, the behavior is undefined and shall be prevented by design review. **Acceptance:** static analysis confirms no DATA_BLOCK_ID is written by more than one module. **DIAG on failure:** N/A (design-time constraint). | SYS-REQ-060 | C |
| SW-REQ-061 | Database read operations (DATA_READ_DATA) shall return the most recent complete snapshot. Partial writes shall not be visible to readers. The database engine shall use double-buffering or equivalent to guarantee atomicity. **Acceptance:** concurrent write + read test shows no torn data over 10,000 iterations. **DIAG on failure:** N/A (structural guarantee). | SYS-REQ-060 | C |
| SW-REQ-062 | The database shall provide DATA_BLOCK_ID_CELL_VOLTAGE containing 18 cell voltages as uint16_t in millivolts (mV), one per cell index [0..17]. **Acceptance:** writing 3700 mV to cell index 5, then reading back, returns exactly 3700. **DIAG on failure:** N/A. | SYS-REQ-001, SYS-REQ-002, SYS-REQ-003, SYS-REQ-004, SYS-REQ-005, SYS-REQ-006, SYS-REQ-007, SYS-REQ-010, SYS-REQ-011, SYS-REQ-012, SYS-REQ-013, SYS-REQ-014, SYS-REQ-015, SYS-REQ-016 | B |
| SW-REQ-063 | The database shall provide DATA_BLOCK_ID_CELL_TEMPERATURE containing 8 temperature sensor readings as int16_t in deci-degrees Celsius (ddegC). **Acceptance:** writing 250 ddegC (25.0 C) to sensor index 3, then reading back, returns exactly 250. **DIAG on failure:** N/A. | SYS-REQ-003, SYS-REQ-004 | B |
| SW-REQ-064 | The database shall provide DATA_BLOCK_ID_CURRENT_SENSOR containing: current (int32_t, mA), voltage1/voltage2/voltage3 (int32_t, mV), power (int32_t, mW), and temperature (int16_t, ddegC). **Acceptance:** writing current=5000 mA, reading back returns 5000. **DIAG on failure:** N/A. | SYS-REQ-005, SYS-REQ-006, SYS-REQ-007 | B |
| SW-REQ-065 | The database shall provide DATA_BLOCK_ID_SOC containing SOC percentage, SOE percentage, and min/max/avg values per string. **Acceptance:** after SOC algorithm writes 50.0%, read returns 50.0%. **DIAG on failure:** N/A. | SYS-REQ-010, SYS-REQ-011 | B |
| SW-REQ-066 | The database shall provide DATA_BLOCK_ID_BALANCING_CONTROL containing a per-cell balancing flag (one bit per cell, 18 cells). **Acceptance:** setting flag for cell 7 and reading back shows cell 7 active, all others inactive. **DIAG on failure:** N/A. | SYS-REQ-003 | QM |
| SW-REQ-067 | The database shall provide DATA_BLOCK_ID_CONTACTOR_FEEDBACK containing per-contactor state for string-plus, string-minus, and precharge contactors. **Acceptance:** writing CLOSED for string-plus, reading back returns CLOSED. **DIAG on failure:** N/A. | SYS-REQ-054 | C |
| SW-REQ-068 | A producer shall write data by calling DATA_WRITE_DATA(), which enqueues the data block. The database engine task (FTSK_RunUserCodeEngine) shall dequeue and apply writes via DATA_IterateOverDatabaseEntries(). **Acceptance:** data written in CAN RX callback is readable by SOA within the same 10 ms cycle. **DIAG on failure:** N/A. | SYS-REQ-060 | C |
| SW-REQ-069 | A consumer shall read data by calling DATA_READ_DATA(), which copies the latest complete snapshot into the caller's buffer. The caller receives a consistent view even if the producer writes concurrently. **Acceptance:** reader never observes a mixture of old and new field values across a single read. **DIAG on failure:** N/A. | SYS-REQ-060 | C |
| SW-REQ-06A | On the POSIX port, DATA_WRITE_DATA() and DATA_READ_DATA() shall execute as direct synchronous calls (no FreeRTOS queue). DATA_IterateOverDatabaseEntries() shall be called synchronously within the engine task slot. **Acceptance:** database functional without FreeRTOS queue primitives on POSIX build. **DIAG on failure:** N/A. | SYS-REQ-151 | QM |

### 6.2 SOC Estimation

| ID | Requirement | Derives From | ASIL |
|---|---|---|---|
| SW-REQ-070 | The SOC algorithm module shall compute state of charge using coulomb counting: SOC(t) = SOC(t-1) - (I_mA x dt_ms) / (Capacity_mAh x 3600000). The current (I_mA) shall be read from DATA_BLOCK_ID_CURRENT_SENSOR. **Acceptance:** at 1000 mA discharge for 3600 s with 1000 mAh capacity, SOC decreases from 100% to 0%. **DIAG on failure:** N/A. | SYS-REQ-130 | B |
| SW-REQ-071 | The SOC module shall initialize SOC to 50% at startup. **Acceptance:** on first algorithm cycle, SOC_avg reads 50.0%. **DIAG on failure:** N/A. | SYS-REQ-131 | B |
| SW-REQ-072 | The SOC module shall execute in the algorithm 100 ms task (FTSK_RunUserCodeCyclicAlgorithm100ms), updating SOC every 100 ms. **Acceptance:** SOC timestamp increments by ~100 ms between consecutive updates. **DIAG on failure:** N/A. | SYS-REQ-134 | B |
| SW-REQ-073 | The SOC module shall clamp the computed SOC to the range [0, 100] percent. Values below 0 shall be set to 0; values above 100 shall be set to 100. **Acceptance:** injecting a large negative current that would drive SOC below 0 results in SOC = 0.0%, not a negative value. **DIAG on failure:** N/A. | SYS-REQ-133 | B |
| SW-REQ-074 | The CAN TX callback for CAN ID 0x235 shall encode SOC_avg as byte 5 with factor 0.5 (raw = SOC% x 2). A SOC of 50% shall produce raw value 0xC8 (100 decimal). A SOC of 0% shall produce 0x00. A computed SOC of 101% (before clamping) shall be clamped to 100% and encoded as 0xC8. **Acceptance:** decode(encode(50.0)) == 50.0. **DIAG on failure:** N/A. | SYS-REQ-132, SYS-REQ-066 | B |
| SW-REQ-075 | The SOE algorithm shall compute state of energy as: SOE = SOC x cell_energy x n_cells, where cell_energy is derived from the voltage-energy lookup. SOE shall be written to DATA_BLOCK_ID_SOC. **Acceptance:** at SOC=100% with nominal cell energy, SOE equals total pack energy. **DIAG on failure:** N/A. | SYS-REQ-011 | B |
| SW-REQ-076 | The SOF (state of function) algorithm shall compute charge and discharge power limits based on current cell voltage, temperature, and SOC. Limits shall be written to the database for CAN transmission. **Acceptance:** at SOC=5%, discharge power limit is reduced relative to SOC=50%. **DIAG on failure:** N/A. | SYS-REQ-012 | B |

### 6.3 Balancing

| ID | Requirement | Derives From | ASIL |
|---|---|---|---|
| SW-REQ-080 | The balancing module shall support three strategy selections: voltage-based (default), history-based, and none. The active strategy shall be selected at compile time via configuration. **Acceptance:** building with BAL_STRATEGY_VOLTAGE produces voltage-based balancing behavior. **DIAG on failure:** N/A. | SYS-REQ-120 | QM |
| SW-REQ-081 | In voltage-based strategy, the balancing module shall activate balancing for any cell whose voltage exceeds V_min + BAL_GetBalancingThreshold_mV() (default 50 mV). V_min is the minimum cell voltage across the string. **Acceptance:** with cells at [3700, 3700, 3760] mV and threshold=50 mV, cell 2 (3760 mV > 3700+50=3750 mV) is flagged for balancing. **DIAG on failure:** N/A. | SYS-REQ-120 | QM |
| SW-REQ-082 | The balancing module shall implement hysteresis for deactivation: a cell's balancing shall deactivate only when its voltage falls below V_min + BAL_GetBalancingThreshold_mV() - BAL_HYSTERESIS_mV. This prevents oscillation at the threshold boundary. **Acceptance:** a cell at exactly threshold activates; it does not deactivate until it drops below (threshold - hysteresis). **DIAG on failure:** N/A. | SYS-REQ-121 | QM |
| SW-REQ-083 | The balancing module shall activate balancing only when: (a) the BMS state machine is in NORMAL state, and (b) the absolute string current is below BS_REST_CURRENT_mA (200 mA). **Acceptance:** with BMS in STANDBY, no balancing flags are set regardless of voltage spread. With BMS in NORMAL and |I|=500 mA, no balancing flags are set. **DIAG on failure:** N/A. | SYS-REQ-122, SYS-REQ-123 | QM |
| SW-REQ-084 | When the balancing module activates balancing for a cell, it shall set the corresponding per-cell flag in DATA_BLOCK_ID_BALANCING_CONTROL and write the block via DATA_WRITE_DATA(). **Acceptance:** after balancing decision, reading DATA_BLOCK_ID_BALANCING_CONTROL shows the correct cell flags. **DIAG on failure:** N/A. | SYS-REQ-120 | QM |
| SW-REQ-085 | When balancing strategy is set to "none", the balancing module shall clear all per-cell flags in DATA_BLOCK_ID_BALANCING_CONTROL on every cycle. **Acceptance:** with strategy=none, no cell ever has its balancing flag set. **DIAG on failure:** N/A. | SYS-REQ-120 | QM |

## 7. Interface Requirements

### 7.1 CAN Transmit

| ID | Requirement | Derives From | ASIL |
|---|---|---|---|
| SW-REQ-090 | The CAN module shall transmit CAN ID 0x220 (DLC 8) every 100 ms via CAN_PeriodicTransmit() in the 10 ms task. Byte 0 lower nibble bits[3:0] = BmsState (STANDBY=5, PRECHARGE=6, NORMAL=7, ERROR=9). Byte 0 upper nibble bits[7:4] = ConnectedStrings count. Remaining bytes encode EmergencyShutoff flag and error flags. **Acceptance:** when BMS is in NORMAL with 1 string connected, byte 0 = 0x17 (upper nibble=1, lower nibble=7). **DIAG on failure:** N/A. | SYS-REQ-060 | B |
| SW-REQ-091 | The CAN module shall transmit CAN ID 0x221 (DLC 8) every 100 ms. This frame shall contain pack voltage (mV), pack current (mA), and pack power (mW) encoded per the DBC specification. **Acceptance:** at 0 A and 66.6 V pack voltage, the decoded pack voltage matches 66600 mV within rounding tolerance. **DIAG on failure:** N/A. | SYS-REQ-061 | B |
| SW-REQ-092 | The CAN module shall transmit CAN IDs 0x240 through 0x245 (DLC 8 each) every 100 ms. Each frame carries 3 cell voltages as uint16_t big-endian (6 frames x 3 = 18 cells). **Acceptance:** cell voltage index 0 appears in 0x240 bytes 0-1, index 1 in bytes 2-3, index 2 in bytes 4-5. **DIAG on failure:** N/A. | SYS-REQ-067 | B |
| SW-REQ-093 | The CAN module shall transmit CAN ID 0x250 (DLC 8) every 100 ms using multiplexing. Byte 0 = mux index (0 through 49). Each frame carries 4 cell voltages encoded as 13-bit values in big-endian format per CAN_BIG_ENDIAN_TABLE. **Acceptance:** encode(3700 mV) then decode yields exactly 3700 mV for each of the 4 voltage slots. **DIAG on failure:** N/A. | SYS-REQ-067 | B |
| SW-REQ-094 | The CAN module shall transmit CAN ID 0x260 (DLC 8) every 100 ms using multiplexing. Byte 0 = mux index (0 through 29). Each frame carries 6 temperature values as 8-bit signed integers (degC). **Acceptance:** a temperature of 25 degC encodes as 0x19 in the corresponding byte position. **DIAG on failure:** N/A. | SYS-REQ-068 | B |
| SW-REQ-095 | The CAN module shall transmit CAN ID 0x235 (DLC 8) every 100 ms. Byte 4 = SOC_min x 2, byte 5 = SOC_avg x 2, byte 6 = SOC_max x 2 (factor 0.5, offset 0). **Acceptance:** at SOC_avg=50%, byte 5 = 0x64 (100 decimal, since 50/0.5=100). SOC_avg decreases monotonically under constant discharge. **DIAG on failure:** N/A. | SYS-REQ-066 | B |
| SW-REQ-096 | All CAN TX messages shall be transmitted by CAN_PeriodicTransmit(), which is called from the 10 ms task (FTSK_RunUserCodeCyclic10ms). Each message shall maintain its own 100 ms period counter, decrementing every 10 ms call and transmitting when the counter reaches zero. **Acceptance:** CAN bus trace shows each TX ID appearing at 100 ms +/- 10 ms intervals. **DIAG on failure:** N/A. | SYS-REQ-060 | B |
| SW-REQ-097 | The CAN TX module shall read all signal data from the database (DATA_READ_DATA) at the time of transmission. It shall not cache stale data between transmit cycles. **Acceptance:** a voltage change written to the database at time T appears in the next CAN TX frame at time T + [0, 100] ms. **DIAG on failure:** N/A. | SYS-REQ-060 | B |
| SW-REQ-098 | Each CAN TX callback function shall construct the 8-byte CAN data payload and call CAN_DataSend() with the correct CAN node, message ID, data length, and data pointer. CAN_DataSend() shall write the frame to the SocketCAN interface. **Acceptance:** the frame appears on the vcan0 interface as captured by candump. **DIAG on failure:** N/A. | SYS-REQ-060 | B |
| SW-REQ-099 | The CAN TX module shall transmit string-specific messages (contactor state, string voltage, string current) for each configured string. The string index shall be embedded in the message encoding. **Acceptance:** with 1 string configured, string 0 messages appear on the bus; no string 1 messages appear. **DIAG on failure:** N/A. | SYS-REQ-060 | B |
| SW-REQ-09A | The CAN TX module shall transmit SOF (state of function) data including recommended charge/discharge current limits and power limits. **Acceptance:** SOF limits decrease when cell voltage approaches overvoltage threshold. **DIAG on failure:** N/A. | SYS-REQ-060, SYS-REQ-012 | B |
| SW-REQ-09B | The CAN TX module shall transmit minimum, maximum, and average cell voltage and temperature values. **Acceptance:** with cells at [3680, 3700, 3720] mV, min=3680, max=3720, avg=3700 in the transmitted frame. **DIAG on failure:** N/A. | SYS-REQ-062, SYS-REQ-063 | B |
| SW-REQ-09C | The CAN TX module shall transmit the insulation monitoring result (if available) or a default safe value when the hardware monitor is absent (POSIX port). **Acceptance:** on POSIX, no spurious insulation fault is reported. **DIAG on failure:** N/A. | SYS-REQ-060 | QM |
| SW-REQ-09D | The CAN TX module shall transmit open-wire detection results for each cell tap. On the POSIX port, all taps shall report no open wire. **Acceptance:** open-wire byte fields are all zero on POSIX. **DIAG on failure:** N/A. | SYS-REQ-060 | QM |
| SW-REQ-09E | The CAN TX module shall transmit balancing status per cell. The frame shall indicate which cells are currently being balanced. **Acceptance:** when cell 5 is flagged for balancing, the corresponding bit/byte in the TX frame is set. **DIAG on failure:** N/A. | SYS-REQ-120 | QM |

### 7.2 CAN Receive

| ID | Requirement | Derives From | ASIL |
|---|---|---|---|
| SW-REQ-100 | The CAN RX module shall receive CAN ID 0x210 (DLC 8). Byte 0 encodes the state request: 0x00 = STANDBY, 0x02 = NORMAL. The decoded request shall be written to the database. The BMS state machine shall read the request from the database in the 10 ms task and act on it. **Acceptance:** sending 0x210 with byte0=0x02 causes BMS to initiate STANDBY->PRECHARGE->NORMAL transition. **DIAG on failure:** CAN_TIMING (if no frames received for timeout period). | SYS-REQ-070 | D |
| SW-REQ-101 | The CAN RX module shall receive CAN ID 0x521 (DLC 8) for IVT current measurement. Bytes 2-5 encode a signed 32-bit big-endian integer representing current in milliamperes (mA). Bytes 0-1 encode the measurement status. The decoded current shall be written to DATA_BLOCK_ID_CURRENT_SENSOR.current. **Acceptance:** at rest (0 A physical), decoded current = 0 +/- 1 mA. **DIAG on failure:** CURRENT_SENSOR_RESPONDING. | SYS-REQ-073 | C |
| SW-REQ-102 | The CAN RX module shall receive CAN ID 0x522 (DLC 8) for IVT voltage 1 measurement. Bytes 2-5 encode voltage in mV as signed 32-bit big-endian. The decoded value shall be written to DATA_BLOCK_ID_CURRENT_SENSOR.highVoltage_mV[string][0]. **Acceptance:** at 66600 mV pack voltage, decoded value = 66600 +/- 10 mV. **DIAG on failure:** CURRENT_SENSOR_RESPONDING. | SYS-REQ-074 | C |
| SW-REQ-103 | The CAN RX module shall receive CAN ID 0x523 (DLC 8) for IVT voltage 2. Decoded value written to highVoltage_mV[string][1]. **Acceptance:** value matches physical measurement within IVT tolerance. **DIAG on failure:** CURRENT_SENSOR_RESPONDING. | SYS-REQ-075 | C |
| SW-REQ-104 | The CAN RX module shall receive CAN ID 0x524 (DLC 8) for IVT voltage 3. Decoded value written to highVoltage_mV[string][2]. This voltage is used by the redundancy module for precharge voltage comparison and MUST match the string voltage within the configured tolerance. **Acceptance:** |highVoltage_mV[s][2] - sum(cellVoltages)| < precharge_tolerance_mV. **DIAG on failure:** CURRENT_SENSOR_RESPONDING. | SYS-REQ-076 | C |
| SW-REQ-105 | The CAN RX module shall receive CAN ID 0x525 (DLC 8) for IVT power measurement. Decoded value (mW, signed 32-bit big-endian) written to DATA_BLOCK_ID_CURRENT_SENSOR.power. **Acceptance:** power = voltage x current within rounding tolerance. **DIAG on failure:** CURRENT_SENSOR_RESPONDING. | SYS-REQ-073 | C |
| SW-REQ-106 | The CAN RX module shall receive CAN ID 0x526 (DLC 8) for IVT coulomb counting. The decoded value shall update the coulomb counter in the current sensor data block. **Acceptance:** accumulated charge matches integral of current over time. **DIAG on failure:** CURRENT_SENSOR_CC_RESPONDING. | SYS-REQ-073 | C |
| SW-REQ-107 | The CAN RX module shall receive CAN ID 0x527 (DLC 8) for IVT energy counting. The decoded value shall update the energy counter in the current sensor data block. **Acceptance:** accumulated energy matches integral of power over time. **DIAG on failure:** CURRENT_SENSOR_CC_RESPONDING. | SYS-REQ-077 | C |
| SW-REQ-108 | The CAN RX module shall receive CAN ID 0x270 (DLC 8) for AFE cell voltages. Byte 0 = mux index (0-49). Each frame carries 4 cell voltages encoded as 13-bit big-endian values per CAN_BIG_ENDIAN_TABLE. Each voltage slot includes a 1-bit invalid flag (1 = VALID, 0 = INVALID). Only voltages with invalid_flag = 1 shall be stored. **Acceptance:** after receiving mux frames 0-4, all 18 cell voltages are populated in the database. **DIAG on failure:** CAN_TIMING. | SYS-REQ-071 | C |
| SW-REQ-109 | The CAN RX module shall receive CAN ID 0x280 (DLC 8) for AFE cell temperatures. Byte 0 = mux index (0-29). Each frame carries 6 temperature values as 8-bit signed integers. **Acceptance:** after receiving mux frames 0-1, all 8 temperature sensors are populated. **DIAG on failure:** CAN_TIMING. | SYS-REQ-072 | C |

### 7.3 CAN Timing Supervision

| ID | Requirement | Derives From | ASIL |
|---|---|---|---|
| SW-REQ-110 | The CAN module shall monitor overall CAN message reception. If no valid CAN frame is received for 100 consecutive 10 ms checks (= 1000 ms), the DIAG module shall evaluate CAN_TIMING. After the configured 200 ms evaluation delay, CAN_TIMING shall be flagged as FATAL. Total fault-tolerant time interval (FTTI) = 1200 ms. **Acceptance:** stopping all CAN traffic for >1200 ms causes BMS to enter ERROR state. **DIAG on failure:** DIAG_ID_CAN_TIMING. | SYS-REQ-05A | D |
| SW-REQ-111 | The CAN module shall monitor IVT current sensor frames (0x521-0x527). If IVT frames stop arriving for 100 consecutive checks, the DIAG module shall evaluate CURRENT_SENSOR_RESPONDING. After 200 ms evaluation delay, it shall be flagged as FATAL. FTTI = 1200 ms. **Acceptance:** stopping IVT frames for >1200 ms causes ERROR state. **DIAG on failure:** DIAG_ID_CURRENT_SENSOR_RESPONDING. | SYS-REQ-073 | D |
| SW-REQ-112 | The CAN module shall monitor IVT coulomb counting frames (0x526). If coulomb counting frames stop arriving for 100 consecutive checks, the DIAG module shall evaluate CURRENT_SENSOR_CC_RESPONDING with a 2000 ms evaluation delay. FTTI = 3000 ms. **Acceptance:** stopping 0x526 for >3000 ms triggers the diagnostic event. **DIAG on failure:** DIAG_ID_CURRENT_SENSOR_CC_RESPONDING. | SYS-REQ-073 | D |
| SW-REQ-113 | The CAN module shall monitor IVT energy counting frames (0x527). If energy counting frames stop arriving for 100 consecutive checks, the DIAG module shall evaluate CURRENT_SENSOR_EC_RESPONDING with a 2000 ms evaluation delay. FTTI = 3000 ms. **Acceptance:** stopping 0x527 for >3000 ms triggers the diagnostic event. **DIAG on failure:** DIAG_ID_CURRENT_SENSOR_EC_RESPONDING. | SYS-REQ-077 | D |

## 8. POSIX Port-Specific Requirements

### 8.1 Cooperative Loop

| ID | Requirement | Derives From | ASIL |
|---|---|---|---|
| SW-REQ-120 | The POSIX cooperative main loop shall iterate at approximately 2 kHz by calling usleep(500) (500 microseconds) per iteration. **Acceptance:** measured iteration rate is 1800-2200 Hz over a 10-second window. **DIAG on failure:** N/A. | SYS-REQ-151 | QM |
| SW-REQ-121 | The 1 ms task slot shall fire every 1000 microseconds of elapsed time. It shall execute: FTSK_RunUserCodeCyclic1ms(), FTSK_RunUserCodeEngine() (database processing), and MEAS_Control(). **Acceptance:** task fires at 1.0 ms +/- 0.5 ms intervals measured by gettimeofday(). **DIAG on failure:** N/A (deadline violation counted). | SYS-REQ-151 | QM |
| SW-REQ-122 | The 10 ms task slot shall fire every 10000 microseconds of elapsed time. It shall execute: FTSK_RunUserCodeCyclic10ms() which contains SYS_Trigger(), BMS_Trigger(), and CAN_PeriodicTransmit(). **Acceptance:** BMS state machine advances within 10 ms of a state request. **DIAG on failure:** N/A (deadline violation counted). | SYS-REQ-151 | QM |
| SW-REQ-123 | The 100 ms task slot shall fire every 100000 microseconds of elapsed time. It shall execute: FTSK_RunUserCodeCyclic100ms() and FTSK_RunUserCodeCyclicAlgorithm100ms() (SOC/SOE/SOF algorithms). **Acceptance:** SOC updates appear at 100 ms intervals. **DIAG on failure:** N/A (deadline violation counted). | SYS-REQ-151 | QM |
| SW-REQ-124 | The cooperative loop shall call task functions in priority order within each iteration: Engine, 1 ms, AFE, 10 ms, 100 ms, I2C, 100 ms-Algorithm. Higher-priority tasks are checked first. **Acceptance:** instrumenting task entry shows Engine always runs before 10 ms in any iteration where both fire. **DIAG on failure:** N/A. | SYS-REQ-151 | QM |
| SW-REQ-125 | The cooperative loop shall implement deadline monitoring. If any task slot takes longer to execute than its period (e.g., 1 ms task takes >1 ms), the loop shall log the violation and increment a per-slot violation counter. **Acceptance:** injecting a 2 ms delay in the 1 ms task increments the 1 ms violation counter. **DIAG on failure:** N/A (logged, not FATAL). | SYS-REQ-151 | QM |
| SW-REQ-126 | The cooperative loop shall perform a non-blocking CAN read from the SocketCAN interface on every iteration. Received frames shall be injected into the foxBMS CAN RX path via posix_can_rx_inject(). **Acceptance:** a frame sent by the plant model is received and processed within 1 ms (2 loop iterations). **DIAG on failure:** N/A. | SYS-REQ-152 | QM |
| SW-REQ-127 | Upon receiving SIGINT, the cooperative loop shall set running=0, command all contactors to open, print a timing summary (task counts, deadline violations), and exit with code 0. **Acceptance:** sending SIGINT during NORMAL operation results in contactors opening and a clean exit. **DIAG on failure:** N/A. | SYS-REQ-151 | QM |

### 8.2 SocketCAN and HAL

| ID | Requirement | Derives From | ASIL |
|---|---|---|---|
| SW-REQ-128 | The SocketCAN interface shall provide send and receive operations compatible with the foxBMS CAN driver API (CAN_DataSend, CAN receive callback). The interface shall bind to vcan0 (or a configurable interface name). **Acceptance:** CAN frames sent via CAN_DataSend() appear on the vcan0 interface. **DIAG on failure:** N/A. | SYS-REQ-152 | QM |
| SW-REQ-129 | HAL stubs shall implement all function signatures of the TMS570 HAL with no-op or RAM-mapped behavior. Functions that return status shall return success. **Acceptance:** the POSIX build links without undefined symbol errors for any HAL function. **DIAG on failure:** N/A. | SYS-REQ-155, SYS-REQ-156 | QM |
| SW-REQ-12A | The POSIX build shall compile 170+ source files with GCC 13 for x86-64 without errors or warnings treated as errors. **Acceptance:** `make` completes with exit code 0. **DIAG on failure:** N/A. | SYS-REQ-150 | QM |

## 9. Negative Requirements

| ID | Requirement | Derives From | ASIL |
|---|---|---|---|
| SW-REQ-200 | The BMS state machine shall NOT transition directly from ERROR to NORMAL. Recovery from ERROR shall always pass through STANDBY first (ERROR -> STANDBY -> PRECHARGE -> NORMAL). **Acceptance:** sending state request NORMAL (0x02) while in ERROR does not cause transition to NORMAL; BMS remains in ERROR. Only after fault clears and STANDBY request (0x00) moves BMS to STANDBY can NORMAL be requested. **DIAG on failure:** N/A (state machine design constraint). | SYS-REQ-055, SYS-REQ-094 | D |
| SW-REQ-201 | The BMS shall NOT close any contactor (string+, string-, precharge) while in ERROR state. Any contactor close command shall be suppressed. **Acceptance:** injecting a contactor-close command while in ERROR results in all contactors remaining open. **DIAG on failure:** N/A (state machine design constraint). | SYS-REQ-054, SYS-REQ-114 | D |
| SW-REQ-202 | The cooperative main loop shall NOT block on CAN read operations. The SocketCAN socket shall be configured as non-blocking (O_NONBLOCK or equivalent). If no frame is available, the read shall return immediately with EAGAIN/EWOULDBLOCK. **Acceptance:** with no CAN traffic, the loop iteration rate remains at ~2 kHz (not degraded by blocking). **DIAG on failure:** N/A. | SYS-REQ-152 | QM |
| SW-REQ-203 | The plant model shall NOT send cell voltage frames (0x270) with invalid_flag = 0 for valid data. The invalid_flag encoding is counterintuitive: 1 = VALID, 0 = INVALID. All valid cell voltages shall have invalid_flag = 1. **Acceptance:** all cell voltage frames from the plant model have invalid_flag = 1 for populated cells, and the BMS stores all 18 cell voltages. **DIAG on failure:** N/A (plant model constraint). | SYS-REQ-071, SYS-REQ-142 | C |
| SW-REQ-204 | The database shall NOT allow two producer modules to write the same DATA_BLOCK_ID. This is a design-time invariant enforced by code review and static analysis, not a runtime check. **Acceptance:** grep of all DATA_WRITE_DATA() call sites confirms each DATA_BLOCK_ID has exactly one writer. **DIAG on failure:** N/A (design-time constraint). | SYS-REQ-060 | C |
| SW-REQ-205 | FAS_ASSERT shall NOT silently continue execution on assertion failure. On the POSIX port, FAS_ASSERT shall log the file, line, and expression to stderr and call exit(1) to terminate the process. **Acceptance:** triggering FAS_ASSERT produces a log message on stderr and non-zero exit code. **DIAG on failure:** N/A (assertion = immediate termination). | SYS-REQ-151 | D |

## 10. Acceptance Criteria

Each software requirement is accepted when:

1. It is traced backward to at least one system requirement in SYS.2-001.
2. It is traced forward to detailed design in SWE.3-001.
3. It is covered by at least one test case in SWE.4-001, SWE.5-001, or SWE.6-001.
4. The covering test case passes on the POSIX SIL target.

---
*End of Document*
