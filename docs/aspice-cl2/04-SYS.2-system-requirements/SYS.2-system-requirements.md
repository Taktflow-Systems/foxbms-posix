# System Requirements Specification

| Document ID | Rev | Date | Classification |
|---|---|---|---|
| SYS.2-001 | 1.0 | 2026-03-21 | Confidential |

## Revision History

| Rev | Date | Author | Reviewer | Description |
|---|---|---|---|---|
| 1.0 | 2026-03-21 | An Dao | M. Weber (AI-simulated) | Initial release |

## 1. Purpose

This document specifies the system-level requirements for the foxBMS 2 POSIX port
battery management system. It serves as the primary input to the system architecture
(SYS.3-001) and is the root of the bidirectional traceability chain mandated by
ASPICE SYS.2 and ISO 26262 Part 3.

## 2. Scope

The requirements herein cover the BMS functionality as configured for one battery
string with the cell chemistry and safety parameters defined below. The POSIX port
preserves all software-checkable safety logic while replacing hardware-dependent
interfaces with validated stubs.

## 3. References

| ID | Title |
|---|---|
| [SYS.3-001] | System Architecture Description |
| [SWE.1-001] | Software Requirements Specification |
| [ISO-SSR-001] | Software Safety Requirements |
| foxBMS-DS | foxBMS 2 v1.10.0 Data Sheet |

## 4. Definitions

| Term | Definition |
|---|---|
| MOL | Maximum Operating Limit -- first warning threshold |
| RSL | Recommended Safety Limit -- elevated warning threshold |
| MSL | Maximum Safety Limit -- violation triggers FATAL diagnostic |
| FTTI | Fault Tolerant Time Interval |
| SOA | Safe Operating Area |
| DIAG | Diagnostic module |

## 5. System Requirements

### 5.1 Battery Pack Configuration

| ID | Requirement | Value | Rationale |
|---|---|---|---|
| SYS-REQ-001 | The BMS shall support the configured number of battery strings. | 1 | Single-string topology for SIL validation |
| SYS-REQ-002 | Each string shall contain the configured number of modules. | 1 | Minimum viable pack structure |
| SYS-REQ-003 | Each module shall contain the configured number of cells in series. | 18 | Matches reference cell chemistry voltage range |
| SYS-REQ-004 | Each cell block shall contain the configured number of parallel cells. | 1 | Single parallel cell per block |
| SYS-REQ-005 | Each module shall support the configured number of temperature sensors. | 8 | Sufficient thermal coverage per module |
| SYS-REQ-006 | The system shall manage the configured number of contactors. | 3 (string+, string-, precharge) | Minimum contactor set for safe operation |
| SYS-REQ-007 | The system shall accept HV voltage inputs from current sensor. | 3 inputs | Pack voltage, string voltage, and reference |

### 5.2 Cell Electrical Parameters

| ID | Requirement | Value | Rationale |
|---|---|---|---|
| SYS-REQ-010 | The BMS shall record cell nominal capacity. | 3500 mAh | Cell data sheet parameter |
| SYS-REQ-011 | The BMS shall record cell energy rating. | 10.0 Wh | Cell data sheet parameter |
| SYS-REQ-012 | The BMS shall record cell nominal voltage. | 2500 mV | Cell data sheet parameter |
| SYS-REQ-013 | The BMS shall enforce maximum string current limit. | 2400 mA | Derived from cell current rating and parallel count |
| SYS-REQ-014 | The BMS shall enforce maximum pack current limit. | 2400 mA | Single-string configuration; equals string limit |
| SYS-REQ-015 | Contactor maximum break current shall not be exceeded. | 3500 mA | Contactor derating specification |
| SYS-REQ-016 | The BMS shall detect rest current condition. | 200 mA | Threshold below which pack is considered at rest |

### 5.3 Voltage Safety Thresholds

| ID | Requirement | MOL (mV) | RSL (mV) | MSL (mV) | Action at MSL |
|---|---|---|---|---|---|
| SYS-REQ-020 | Cell overvoltage detection | 2720 | 2750 | 2800 | FATAL: open contactors |
| SYS-REQ-021 | Cell undervoltage detection | 1580 | 1550 | 1500 | FATAL: open contactors |
| SYS-REQ-022 | Deep discharge detection | -- | -- | 1500 | FATAL: open contactors, latch |

### 5.4 Current Safety Thresholds

| ID | Requirement | MOL (mA) | RSL (mA) | MSL (mA) | Action at MSL |
|---|---|---|---|---|---|
| SYS-REQ-030 | Cell discharge overcurrent | 170000 | 175000 | 180000 | FATAL: open contactors |
| SYS-REQ-031 | Cell charge overcurrent | 170000 | 175000 | 180000 | FATAL: open contactors |

### 5.5 Temperature Safety Thresholds

| ID | Requirement | MOL | RSL | MSL | Action at MSL |
|---|---|---|---|---|---|
| SYS-REQ-040 | Overtemperature during discharge | 45 deg C | 50 deg C | 55 deg C | FATAL: open contactors |
| SYS-REQ-041 | Undertemperature during discharge | -10 deg C | -15 deg C | -20 deg C | FATAL: open contactors |
| SYS-REQ-042 | Overtemperature during charge | 35 deg C | 40 deg C | 45 deg C | FATAL: open contactors |
| SYS-REQ-043 | Undertemperature during charge | -10 deg C | -15 deg C | -20 deg C | FATAL: open contactors |

### 5.6 Diagnostic System Requirements

| ID | Requirement | Acceptance Criteria | Rationale |
|---|---|---|---|
| SYS-REQ-050 | The BMS shall maintain a diagnostic module with at least 85 diagnostic identifiers. | Count of entries in `diag_cfg.c` DIAG_ID table >= 85. | Coverage of all monitored parameters |
| SYS-REQ-051 | Each diagnostic identifier shall have a configurable threshold counter (number of events before triggering). | Every DIAG_ID entry has a non-zero `threshold` field; value is independently settable per ID. | Debounce transient faults |
| SYS-REQ-052 | Each diagnostic identifier shall have a configurable evaluation delay (period between consecutive checks). | Every DIAG_ID entry has a `delay_ms` field; value is independently settable per ID. | Allow periodic re-evaluation |
| SYS-REQ-053 | A diagnostic reaching FATAL severity shall cause the BMS to transition to ERROR state within the configured FTTI. | Inject fault → verify BMS state == ERROR within FTTI. | Primary safety mechanism |
| SYS-REQ-054 | In ERROR state the BMS shall open all three contactors (string+, string-, precharge). | Observe SPS channels 0, 1, 2 all OFF within one control cycle after ERROR entry. | Disconnect battery from load |
| SYS-REQ-055 | The BMS shall not exit ERROR state until the fault is cleared AND an explicit STANDBY request (0x210 byte 0 = 0x00) is received. | Clear fault + send STANDBY → BMS leaves ERROR. Clear fault alone → BMS remains in ERROR. Send STANDBY alone → BMS remains in ERROR. | Prevent unintended re-energization |
| SYS-REQ-056 | Voltage fault FTTI shall be <= 700 ms (threshold=50 events x 10 ms period = 500 ms detection + 200 ms delay). | Inject overvoltage at t=0; verify contactors open by t <= 700 ms. | Derived from diag_cfg.c timing |
| SYS-REQ-057 | Current fault FTTI shall be <= 200 ms (threshold=10 x 10 ms = 100 ms detection + 100 ms delay). | Inject overcurrent at t=0; verify contactors open by t <= 200 ms. | Fastest safety-critical fault path |
| SYS-REQ-058 | Temperature fault FTTI shall be <= 6000 ms (threshold=500 x 10 ms = 5000 ms detection + 1000 ms delay). | Inject overtemperature at t=0; verify contactors open by t <= 6000 ms. | Thermal time constant is slow |
| SYS-REQ-059 | Contactor feedback fault FTTI shall be <= 300 ms (threshold=20 x 10 ms = 200 ms + 100 ms delay). | Inject feedback mismatch at t=0; verify ERROR by t <= 300 ms. | Contactor weld detection |
| SYS-REQ-05A | CAN timing fault FTTI shall be <= 1200 ms (threshold=100 x 10 ms = 1000 ms + 200 ms delay). | Stop CAN TX at t=0; verify ERROR by t <= 1200 ms. | Communication loss detection |

### 5.7 CAN TX Communication Requirements

| ID | Requirement | CAN ID | Period | Content / Encoding | Acceptance Criteria |
|---|---|---|---|---|---|
| SYS-REQ-060 | The BMS shall transmit the BMS state message. | 0x220 | 100 ms | Byte 0 lower nibble = BMS state enum; byte 0 upper nibble = number of connected strings. | Receive 0x220 at 100 ms +/- 10 ms; decode state matches internal BMS state. |
| SYS-REQ-061 | The BMS shall transmit the BMS state details message. | 0x221 | 100 ms | BMS sub-state and error flags. | Receive 0x221 at 100 ms +/- 10 ms; content changes on state transitions. |
| SYS-REQ-062 | The BMS shall transmit cell voltage summary. | 0x231 | 100 ms | Minimum, maximum, and average cell voltage (mV). | Values match independently computed min/max/avg from cell voltage database within 1 mV. |
| SYS-REQ-063 | The BMS shall transmit cell temperature summary. | 0x232 | 100 ms | Minimum, maximum, and average cell temperature (deg C). | Values match independently computed min/max/avg from temperature database within 1 deg C. |
| SYS-REQ-064 | The BMS shall transmit pack values P0 (voltage and current). | 0x233 | 100 ms | Pack voltage in mV, pack current in mA. | Decoded voltage == sum of cell voltages +/- 10 mV; current matches IVT reading +/- 1 mA. |
| SYS-REQ-065 | The BMS shall transmit pack values P1 (power). | 0x234 | 100 ms | Pack power in W. | Power == voltage x current / 1e6 +/- 1 W. |
| SYS-REQ-066 | The BMS shall transmit SOC. | 0x235 | 100 ms | Byte 5 = SOC percentage x 2 (e.g., 0xC8 = 100%, 0x64 = 50%). | Decode byte 5, divide by 2 → SOC in 0-100% range; value matches internal SOC +/- 0.5%. |
| SYS-REQ-067 | The BMS shall transmit multiplexed cell voltages. | 0x250 | 100 ms | 50 mux groups x 4 cells per frame; each voltage 13-bit unsigned, big-endian. | All 18 cell voltages recoverable from mux groups 0-4; values match AFE input within 1 mV. |
| SYS-REQ-068 | The BMS shall transmit multiplexed cell temperatures. | 0x260 | 100 ms | 30 mux groups x 6 sensors per frame; each temperature 8-bit signed (deg C). | All 8 temperature sensor values recoverable from mux groups 0-1; values match AFE input within 1 deg C. |
| SYS-REQ-069 | The BMS shall transmit slave info. | 0x301 | 1000 ms | Slave status and version information. | Receive 0x301 at 1000 ms +/- 100 ms. |

### 5.8 CAN RX Communication Requirements

| ID | Requirement | CAN ID | Content / Decoding | Validity Check | Acceptance Criteria |
|---|---|---|---|---|---|
| SYS-REQ-070 | The BMS shall accept state request messages. | 0x210 | Byte 0: 0x00 = STANDBY, 0x02 = NORMAL. | Frame received within CAN timing window. | Send 0x210 with byte 0 = 0x02 → BMS initiates PRECHARGE within 1 s. |
| SYS-REQ-071 | The BMS shall accept AFE cell voltage messages. | 0x270 | 50 mux groups x 4 voltages; each 13-bit unsigned, big-endian; invalid_flag = 1 means VALID. | Discard frame if invalid_flag != 1. | Inject 0x270 with 18 known voltages → internal cell voltage database matches within 1 mV. |
| SYS-REQ-072 | The BMS shall accept AFE cell temperature messages. | 0x280 | 30 mux groups x 6 temps; each 8-bit signed (deg C); invalid_flag = 1 means VALID. | Discard frame if invalid_flag != 1. | Inject 0x280 with 8 known temperatures → internal temperature database matches within 1 deg C. |
| SYS-REQ-073 | The BMS shall accept IVT current measurement. | 0x521 | 32-bit signed big-endian at byte offset 2; status in bytes 0-1. | Status bytes indicate valid measurement. | Inject 0x521 with known current → internal pack current matches within 1 mA. |
| SYS-REQ-074 | The BMS shall accept IVT voltage 1 measurement. | 0x522 | 32-bit signed big-endian at byte offset 2; status in bytes 0-1. | Status bytes indicate valid measurement. | Inject 0x522 with known voltage → internal IVT voltage 1 matches within 1 mV. |
| SYS-REQ-075 | The BMS shall accept IVT voltage 2 measurement. | 0x523 | 32-bit signed big-endian at byte offset 2; status in bytes 0-1. | Status bytes indicate valid measurement. | Inject 0x523 with known voltage → internal IVT voltage 2 matches within 1 mV. |
| SYS-REQ-076 | The BMS shall accept IVT voltage 3 (HV bus voltage) for precharge and redundancy checks. | 0x524 | 32-bit signed big-endian at byte offset 2; stored as highVoltage_mV[s][2]. | Status bytes indicate valid measurement. | Inject 0x524 with known voltage → verify highVoltage_mV[0][2] matches; precharge uses this value for V_bus comparison. |
| SYS-REQ-077 | The BMS shall accept IVT temperature measurement. | 0x527 | 32-bit signed big-endian at byte offset 2; status in bytes 0-1. | Status bytes indicate valid measurement. | Inject 0x527 with known temperature → internal IVT temperature matches within 1 deg C. |

### 5.9 SYS State Machine Requirements

| ID | Requirement | From State | To State | Trigger / Guard | Timing | Acceptance Criteria |
|---|---|---|---|---|---|---|
| SYS-REQ-080 | SYS shall transition from UNINITIALIZED to INITIALIZATION on startup. | UNINIT (0) | INIT (1) | System reset / power-on. | Immediate on first scheduler tick. | After reset, SYS state == INIT within 10 ms. |
| SYS-REQ-081 | SYS shall transition from INIT to INITIALIZED when all init conditions are met. | INIT (1) | INITIALIZED (2) | SBC state == RUNNING (value 2) AND RTC initialized AND current sensor present. | Within 500 ms of startup. | Verify SBC stub returns RUNNING; SYS state == INITIALIZED within 500 ms. |
| SYS-REQ-082 | SYS shall transition from INITIALIZED to IDLE automatically. | INITIALIZED (2) | IDLE (3) | Automatic (no external trigger). | Within one control cycle (10 ms) of INITIALIZED entry. | SYS state == IDLE within 510 ms of startup. |
| SYS-REQ-083 | SYS shall transition from IDLE to RUNNING when all subsystems are ready. | IDLE (3) | RUNNING (5) | All subsystem init complete. | Within 1 s of IDLE entry. | SYS state == RUNNING within 1.5 s of startup. |
| SYS-REQ-084 | SYS shall remain in RUNNING for the entire operational lifetime unless a system-level fault occurs. | RUNNING (5) | -- | -- | -- | SYS state == RUNNING continuously while BMS operates. |

### 5.10 BMS State Machine Requirements

| ID | Requirement | From State | To State | Trigger / Guard | Contactor Action | Acceptance Criteria |
|---|---|---|---|---|---|---|
| SYS-REQ-090 | BMS shall not activate until SYS state == RUNNING. | -- | STANDBY (5) | SYS reaches RUNNING (5). | All contactors open. | BMS state remains inactive while SYS < RUNNING. |
| SYS-REQ-091 | BMS shall transition from STANDBY to PRECHARGE on NORMAL request. | STANDBY (5) | PRECHARGE (6) | CAN 0x210 byte 0 == 0x02 (NORMAL). | Close precharge contactor (ch2) + string- contactor (ch1). | Send 0x210=0x02 → BMS enters PRECHARGE within 100 ms; ch1 and ch2 close. |
| SYS-REQ-092 | BMS shall transition from PRECHARGE to NORMAL when precharge voltage converges. | PRECHARGE (6) | NORMAL (7) | \|V_string - V_bus\| < threshold, where V_bus = IVT Voltage 3 (0x524). | Close string+ contactor (ch0); open precharge contactor (ch2). | Precharge completes → ch0 closes, ch2 opens; BMS state == NORMAL. |
| SYS-REQ-093 | BMS shall transition from any operational state to ERROR on FATAL diagnostic. | STANDBY/PRECHARGE/NORMAL | ERROR (9) | Any DIAG ID reaches FATAL severity. | Open all contactors (ch0, ch1, ch2). | Inject FATAL fault → BMS == ERROR; all contactors open within one control cycle. |
| SYS-REQ-094 | BMS shall transition from ERROR to STANDBY only when fault cleared AND STANDBY requested. | ERROR (9) | STANDBY (5) | Fault condition cleared AND CAN 0x210 byte 0 == 0x00 (STANDBY). | All contactors remain open. | Clear fault + send STANDBY → BMS == STANDBY. Either condition alone → BMS remains ERROR. |
| SYS-REQ-095 | BMS shall abort precharge on timeout. | PRECHARGE (6) | ERROR (9) | Precharge timer expires before voltage convergence. | Open all contactors (ch0, ch1, ch2). | Block V_bus convergence → BMS == ERROR after precharge timeout. |

### 5.11 Precharge Sequence Requirements

| ID | Requirement | Acceptance Criteria | Rationale |
|---|---|---|---|
| SYS-REQ-100 | On PRECHARGE entry, the BMS shall close the precharge contactor (SPS ch2) and string- contactor (SPS ch1). | ch2 and ch1 transition to ON within one control cycle of PRECHARGE entry; ch0 remains OFF. | Precharge resistor limits inrush current |
| SYS-REQ-101 | The BMS shall compute V_string as the sum of all 18 cell voltages received from the AFE (CAN 0x270). | V_string == sum of 18 decoded voltages from 0x270 mux groups 0-4, within 1 mV of independent calculation. | String voltage reference for precharge check |
| SYS-REQ-102 | The BMS shall use IVT Voltage 3 (CAN 0x524, stored as highVoltage_mV[s][2]) as V_bus for the precharge comparison. | V_bus value read from highVoltage_mV[0][2], NOT highVoltage_mV[0][0]. | Bus-side voltage measurement via current sensor |
| SYS-REQ-103 | The BMS shall evaluate \|V_string - V_bus\| < precharge threshold on each 100 ms control cycle during PRECHARGE. | Threshold comparison executes every 100 ms; log shows evaluation at each cycle. | Continuous monitoring during precharge |
| SYS-REQ-104 | On successful precharge (voltage convergence), the BMS shall close string+ contactor (SPS ch0) and then open precharge contactor (SPS ch2). | ch0 transitions to ON; ch2 transitions to OFF; final state: ch0=ON, ch1=ON, ch2=OFF. | Complete main path, remove precharge resistor |
| SYS-REQ-105 | On precharge timeout (voltage does not converge within configured time), the BMS shall abort by opening all contactors and entering ERROR state. | All contactors OFF; BMS state == ERROR. | Prevent indefinite precharge with potential fault |

### 5.12 Contactor Control Requirements

| ID | Requirement | Acceptance Criteria | Rationale |
|---|---|---|---|
| SYS-REQ-110 | The BMS shall control three contactors via the SPS driver: ch0 = string+ contactor, ch1 = string- contactor, ch2 = precharge contactor. | SPS channel mapping verified in configuration; each channel independently controllable. | Hardware interface definition |
| SYS-REQ-111 | During STANDBY, all three SPS channels shall be OFF (all contactors open). | In STANDBY: ch0=OFF, ch1=OFF, ch2=OFF. | No current path in standby |
| SYS-REQ-112 | During PRECHARGE, SPS ch1 (string-) and ch2 (precharge) shall be ON; ch0 (string+) shall be OFF. | In PRECHARGE: ch0=OFF, ch1=ON, ch2=ON. | Precharge current path through precharge resistor |
| SYS-REQ-113 | During NORMAL, SPS ch0 (string+) and ch1 (string-) shall be ON; ch2 (precharge) shall be OFF. | In NORMAL: ch0=ON, ch1=ON, ch2=OFF. | Main current path, precharge resistor bypassed |
| SYS-REQ-114 | On ERROR entry, the BMS shall open all three contactors within one control cycle (10 ms). | ch0=OFF, ch1=OFF, ch2=OFF within 10 ms of ERROR transition. | Fastest possible disconnection |
| SYS-REQ-115 | The SPS driver shall verify contactor feedback (actual state matches requested state) within 20 evaluation events. | Inject feedback mismatch → contactor feedback DIAG triggers within 20 x 10 ms = 200 ms. | Contactor weld / stuck detection |

### 5.13 Balancing Requirements

| ID | Requirement | Acceptance Criteria | Rationale |
|---|---|---|---|
| SYS-REQ-120 | The BMS shall use voltage-based balancing: any cell where V_cell > V_min + BAL_threshold shall be balanced (discharged). | Inject cell voltages with one cell 50 mV above minimum → that cell's balancing flag is set; others are not. | Equalize cell voltages to maximize usable capacity |
| SYS-REQ-121 | Balancing shall employ hysteresis: stop balancing a cell when V_cell <= V_min + BAL_threshold + hysteresis. | Start balancing at threshold; verify balancing stops at threshold + hysteresis (not at threshold). | Prevent rapid on/off cycling |
| SYS-REQ-122 | Balancing shall only be active when BMS state == NORMAL. | In STANDBY or PRECHARGE, no balancing flags are set regardless of cell voltage spread. | Balancing requires stable pack connection |
| SYS-REQ-123 | Balancing shall only be active when \|I_pack\| < rest current threshold (200 mA). | Set pack current to 500 mA → no balancing. Set to 100 mA → balancing activates per voltage criteria. | Accurate voltage comparison requires near-zero current |

### 5.14 SOC Estimation Requirements

| ID | Requirement | Acceptance Criteria | Rationale |
|---|---|---|---|
| SYS-REQ-130 | The BMS shall estimate SOC using Coulomb counting: SOC(t) = SOC(t-1) - (I x dt) / (Capacity x 3600). | Apply known constant current for known duration → SOC change matches I x dt / (Capacity x 3600) within 0.1%. | Standard SOC estimation method |
| SYS-REQ-131 | The initial SOC at startup shall be 50%. | On fresh startup with no prior data, SOC == 50.0%. | Conservative default when no SOC persistence is available |
| SYS-REQ-132 | The BMS shall report SOC on CAN message 0x235 byte 5, encoded as SOC percentage x 2 (e.g., 50% = 0x64, 100% = 0xC8). | Read 0x235 byte 5; divide by 2 → value matches internal SOC within 0.5%. | CAN encoding per DBC specification |
| SYS-REQ-133 | SOC shall be clamped to the range 0-100%. | Drive SOC calculation below 0% or above 100% → reported value remains within [0, 100]. | Prevent nonsensical SOC values |
| SYS-REQ-134 | SOC shall be updated and transmitted every 100 ms. | Measure 0x235 inter-frame timing == 100 ms +/- 10 ms. | Matches CAN TX schedule |

### 5.15 Plant Model Requirements (POSIX-Specific)

| ID | Requirement | Acceptance Criteria | Rationale |
|---|---|---|---|
| SYS-REQ-140 | The plant model shall send all CAN RX messages (0x210, 0x270, 0x280, 0x521-0x524, 0x527) at 100 ms period on SocketCAN. | Capture CAN traffic → all listed IDs present at 100 ms +/- 10 ms. | Provide realistic stimulus to BMS under test |
| SYS-REQ-141 | The plant model shall simulate 18 cell voltages derived from OCV(SOC) curve in the range 3400-4200 mV, with IR drop of 50 mOhm/cell x I_pack. | At SOC=50%, I=0A → V_cell approx midpoint of OCV curve. At I=10A → V_cell drops by 500 mV (10A x 50 mOhm). | Physically plausible cell behavior |
| SYS-REQ-142 | The plant model shall encode cell voltages into CAN 0x270 using 50 mux groups x 4 voltages, 13-bit unsigned big-endian, with invalid_flag = 1 (VALID). | BMS decodes 0x270 → internal cell voltages match plant model values within 1 mV. | Match foxBMS DBC encoding |
| SYS-REQ-143 | The plant model shall simulate IVT current: 0 A in STANDBY, 10 A discharge in NORMAL (closed-loop from contactor state). | In STANDBY: 0x521 current field == 0. After contactors close: 0x521 current field == 10000 mA. | Closed-loop behavior based on contactor feedback |
| SYS-REQ-144 | The plant model shall simulate IVT voltages: V_pack = 18 x V_cell - I x R_internal. | Decode 0x522/0x523/0x524 → pack voltage matches 18 x V_cell - I x R within 10 mV. | Consistent electrical model |
| SYS-REQ-145 | The plant model shall simulate cell temperatures at 25 deg C (static). | Decode 0x280 → all temperature values == 25 deg C. | Simplified thermal model for SIL |
| SYS-REQ-146 | The plant model shall send state request: STANDBY (0x00) for the first 3 s, then NORMAL (0x02). | CAN 0x210 byte 0 == 0x00 for t < 3 s; == 0x02 for t >= 3 s. | Allow BMS initialization before energization |
| SYS-REQ-147 | The plant model IVT Voltage 3 (0x524) shall reflect the HV bus voltage for precharge verification: 0 V when contactors open, rising toward V_string when precharge contactor is closed. | During precharge: 0x524 voltage ramps from 0 toward V_string; BMS precharge check uses this value. | Enable closed-loop precharge in SIL |

### 5.16 POSIX Port Requirements

| ID | Requirement | Acceptance Criteria | Rationale |
|---|---|---|---|
| SYS-REQ-150 | The POSIX port shall compile foxBMS 2 v1.10.0 for x86-64 using GCC 13. | `make` completes with zero errors on GCC 13.x; binary executes on x86-64 Linux. | SIL execution target |
| SYS-REQ-151 | The POSIX port shall replace FreeRTOS with a cooperative main loop. | No FreeRTOS symbols linked; main loop calls 1 ms / 10 ms / 100 ms task groups. | No RTOS on POSIX host |
| SYS-REQ-152 | The POSIX port shall replace hardware CAN with SocketCAN. | CAN frames sent/received via `vcan0` interface; `candump vcan0` shows traffic. | Linux-native CAN interface |
| SYS-REQ-153 | The POSIX port shall suppress 24 hardware-absent diagnostic IDs. | Exactly 24 DIAG IDs configured with DIAG_EVALUATION_DISABLED; none trigger FATAL in headless operation. | Avoid false FATAL on missing hardware |
| SYS-REQ-154 | The POSIX port shall retain 61 software-checkable diagnostic IDs. | Exactly 61 DIAG IDs remain active; each can be triggered by injecting the corresponding fault condition. | Preserve safety logic validation |
| SYS-REQ-155 | The POSIX port shall provide at least 80 HAL stub modules. | Count of `*_posix.c` or stub files >= 80. | Cover all hardware abstraction points |
| SYS-REQ-156 | The POSIX port shall map 60+ TMS570 register bases to RAM buffers. | Count of register base addresses in `posix_register_map.c` >= 60; all reads/writes execute without segfault. | Enable register-level code to execute without hardware |

### 5.17 Traceability: SYS-REQ → SW-REQ

| SYS-REQ | Traces Down To |
|---|---|
| SYS-REQ-001 | SW-REQ-062 |
| SYS-REQ-002 | SW-REQ-062 |
| SYS-REQ-003 | SW-REQ-062, SW-REQ-080 |
| SYS-REQ-004 | SW-REQ-062 |
| SYS-REQ-005 | SW-REQ-062 |
| SYS-REQ-006 | SW-REQ-044 |
| SYS-REQ-007 | SW-REQ-101 |
| SYS-REQ-010 | SW-REQ-070 |
| SYS-REQ-011 | SW-REQ-071 |
| SYS-REQ-012 | SW-REQ-062 |
| SYS-REQ-013 | SW-REQ-012 |
| SYS-REQ-014 | SW-REQ-013 |
| SYS-REQ-015 | SW-REQ-044 |
| SYS-REQ-016 | SW-REQ-081, SW-REQ-083 |
| SYS-REQ-020 | SW-REQ-001, SW-REQ-003 |
| SYS-REQ-021 | SW-REQ-002, SW-REQ-004 |
| SYS-REQ-022 | SW-REQ-005 |
| SYS-REQ-030 | SW-REQ-010 |
| SYS-REQ-031 | SW-REQ-011 |
| SYS-REQ-040 | SW-REQ-020 |
| SYS-REQ-041 | SW-REQ-021 |
| SYS-REQ-042 | SW-REQ-022 |
| SYS-REQ-043 | SW-REQ-023 |
| SYS-REQ-050 | SW-REQ-030 |
| SYS-REQ-051 | SW-REQ-031 |
| SYS-REQ-052 | SW-REQ-033 |
| SYS-REQ-053 | SW-REQ-031, SW-REQ-032 |
| SYS-REQ-054 | SW-REQ-044 |
| SYS-REQ-055 | SW-REQ-045, SW-REQ-200 |
| SYS-REQ-056 | SW-REQ-031 |
| SYS-REQ-057 | SW-REQ-031 |
| SYS-REQ-058 | SW-REQ-031 |
| SYS-REQ-059 | SW-REQ-031 |
| SYS-REQ-05A | SW-REQ-110 |
| SYS-REQ-060 | SW-REQ-090 |
| SYS-REQ-061 | SW-REQ-091 |
| SYS-REQ-062 | SW-REQ-095 |
| SYS-REQ-063 | SW-REQ-095 |
| SYS-REQ-064 | SW-REQ-095 |
| SYS-REQ-065 | SW-REQ-095 |
| SYS-REQ-066 | SW-REQ-095, SW-REQ-074 |
| SYS-REQ-067 | SW-REQ-092, SW-REQ-093 |
| SYS-REQ-068 | SW-REQ-094 |
| SYS-REQ-069 | SW-REQ-090 |
| SYS-REQ-070 | SW-REQ-100 |
| SYS-REQ-071 | SW-REQ-108 |
| SYS-REQ-072 | SW-REQ-109 |
| SYS-REQ-073 | SW-REQ-101, SW-REQ-111 |
| SYS-REQ-074 | SW-REQ-102 |
| SYS-REQ-075 | SW-REQ-103 |
| SYS-REQ-076 | SW-REQ-104 |
| SYS-REQ-077 | SW-REQ-107 |
| SYS-REQ-080 | SW-REQ-050 |
| SYS-REQ-081 | SW-REQ-051 |
| SYS-REQ-082 | SW-REQ-052 |
| SYS-REQ-083 | SW-REQ-053 |
| SYS-REQ-084 | SW-REQ-044 |
| SYS-REQ-085 | SW-REQ-045 |
| SYS-REQ-086 | SW-REQ-090 |
| SYS-REQ-090 | SW-REQ-040 |
| SYS-REQ-091 | SW-REQ-041 |
| SYS-REQ-092 | SW-REQ-042 |
| SYS-REQ-093 | SW-REQ-043 |
| SYS-REQ-094 | SW-REQ-045 |
| SYS-REQ-095 | SW-REQ-044 |
| SYS-REQ-100 | SW-REQ-042 |
| SYS-REQ-101 | SW-REQ-042 |
| SYS-REQ-102 | SW-REQ-042 |
| SYS-REQ-103 | SW-REQ-044 |
| SYS-REQ-104 | SW-REQ-044 |
| SYS-REQ-105 | SW-REQ-044 |
| SYS-REQ-110 | SW-REQ-044 |
| SYS-REQ-111 | SW-REQ-044 |
| SYS-REQ-112 | SW-REQ-044 |
| SYS-REQ-113 | SW-REQ-044 |
| SYS-REQ-114 | SW-REQ-044 |
| SYS-REQ-115 | SW-REQ-044 |
| SYS-REQ-120 | SW-REQ-080, SW-REQ-081 |
| SYS-REQ-121 | SW-REQ-082 |
| SYS-REQ-122 | SW-REQ-083 |
| SYS-REQ-123 | SW-REQ-083 |
| SYS-REQ-130 | SW-REQ-070 |
| SYS-REQ-131 | SW-REQ-071 |
| SYS-REQ-132 | SW-REQ-074 |
| SYS-REQ-133 | SW-REQ-073 |
| SYS-REQ-134 | SW-REQ-072 |
| SYS-REQ-140 | SW-REQ-108 |
| SYS-REQ-141 | SW-REQ-108 |
| SYS-REQ-142 | SW-REQ-108 |
| SYS-REQ-143 | SW-REQ-108 |
| SYS-REQ-144 | SW-REQ-108 |
| SYS-REQ-145 | SW-REQ-108 |
| SYS-REQ-146 | SW-REQ-108, SW-REQ-109 |
| SYS-REQ-147 | SW-REQ-108 |
| SYS-REQ-150 | SW-REQ-129 |
| SYS-REQ-151 | SW-REQ-120, SW-REQ-121, SW-REQ-122, SW-REQ-123, SW-REQ-124, SW-REQ-125 |
| SYS-REQ-152 | SW-REQ-126, SW-REQ-128 |
| SYS-REQ-153 | SW-REQ-034 |
| SYS-REQ-154 | SW-REQ-035 |
| SYS-REQ-155 | SW-REQ-129 |
| SYS-REQ-156 | SW-REQ-129 |

## 6. Acceptance Criteria

Each requirement in Section 5 is accepted when all three general criteria AND the section-specific verification method are satisfied.

### 6.1 General Criteria

1. The requirement is traced forward to at least one software requirement in SWE.1-001.
2. The requirement is traced forward to at least one test case in SWE.5-001 or SWE.6-001.
3. The corresponding test case passes in the POSIX SIL environment.

### 6.2 Section-Specific Verification Methods

| Section | Verification Method |
|---|---|
| 5.1 Battery Pack Configuration | Inspection: verify `bms_cfg.h` constants match requirement values. |
| 5.2 Cell Electrical Parameters | Inspection: verify `battery_cell_cfg.h` constants match requirement values. |
| 5.3 Voltage Safety Thresholds | Test: inject cell voltages at MOL, RSL, MSL boundaries; verify correct DIAG severity at each level. |
| 5.4 Current Safety Thresholds | Test: inject pack current at MOL, RSL, MSL boundaries; verify correct DIAG severity at each level. |
| 5.5 Temperature Safety Thresholds | Test: inject temperatures at MOL, RSL, MSL boundaries per charge/discharge direction; verify correct DIAG severity. |
| 5.6 Diagnostic System | Test: for each fault type, inject fault and measure time to ERROR state; verify FTTI per SYS-REQ-056 through SYS-REQ-05A. |
| 5.7 CAN TX Communication | Test: run BMS with plant model; capture all TX messages on `vcan0`; verify IDs, periods, and decoded content match requirements. |
| 5.8 CAN RX Communication | Test: send each RX message with known payloads; read BMS internal database; verify decoded values match within stated tolerances. |
| 5.9 SYS State Machine | Test: start BMS from reset; log state transitions with timestamps; verify sequence UNINIT->INIT->INITIALIZED->IDLE->RUNNING and timing per requirements. |
| 5.10 BMS State Machine | Test: exercise full cycle STANDBY->PRECHARGE->NORMAL->ERROR->STANDBY; verify each transition trigger, guard, and contactor action per requirements. |
| 5.11 Precharge Sequence | Test: start precharge; monitor V_bus ramp on 0x524; verify contactor sequence ch2+ch1 ON -> voltage convergence -> ch0 ON, ch2 OFF. Test timeout by blocking V_bus. |
| 5.12 Contactor Control | Test: verify SPS channel state in each BMS state; inject feedback mismatch and verify detection within 200 ms. |
| 5.13 Balancing | Test: set cell voltages with known spread; verify balancing flags set only for cells above V_min + threshold; verify hysteresis; verify no balancing when I > 200 mA or state != NORMAL. |
| 5.14 SOC Estimation | Test: apply known current for known time; verify SOC change matches Coulomb counting formula; verify 0x235 encoding; verify clamping at 0% and 100%. |
| 5.15 Plant Model | Test: run plant model standalone; capture CAN traffic; verify all message IDs, periods, encoding, and closed-loop response to contactor state changes. |
| 5.16 POSIX Port | Test: compile and run; verify no FreeRTOS symbols; verify SocketCAN operation; count suppressed/active DIAG IDs; count HAL stubs and register mappings. |

## 7. Open Issues

None at initial release.

---
*End of Document*
