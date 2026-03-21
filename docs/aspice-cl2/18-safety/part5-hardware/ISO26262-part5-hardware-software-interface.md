# Hardware-Software Interface Specification

| Document ID | Rev | Date | Classification |
|---|---|---|---|
| ISO-HSI-001 | 1.0 | 2026-03-21 | Confidential |

## Revision History

| Rev | Date | Author | Reviewer | Description |
|---|---|---|---|---|
| 1.0 | 2026-03-21 | An Dao | Dr. K. Richter (AI-simulated) | Initial release |

## 1. Purpose

This document specifies the Hardware-Software Interface (HSI) for the foxBMS 2 POSIX
port, as required by ISO 26262 Part 5 Clause 7. It maps every hardware dependency in
the foxBMS software to its POSIX stub implementation, providing the technical
justification for executing the BMS software in a SIL environment without physical
hardware.

## 2. Scope

The HSI covers all hardware interfaces used by the foxBMS 2 v1.10.0 software when
running on the TMS570LC4357 MCU, and their corresponding POSIX replacements.

## 3. References

| ID | Title |
|---|---|
| [SYS.3-001] | System Architecture Description |
| [SWE.2-001] | Software Architecture Description |
| [SWE.1-001] | Software Requirements Specification |
| TMS570-DS | TI TMS570LC4357 Data Sheet |
| foxBMS-HAL | foxBMS 2 HAL documentation |

## 4. Definitions

| Term | Definition |
|---|---|
| HSI | Hardware-Software Interface |
| Stub | A minimal implementation that satisfies the API contract without real hardware |
| RAM-mapped register | A software variable that occupies the same memory layout as a hardware register, enabling register access code to execute on a host CPU |

## 5. HSI Mapping Overview

The foxBMS 2 software accesses hardware through the following interface categories.
Each is mapped to a POSIX equivalent.

| Category | TMS570 (Production) | POSIX (SIL) | Stub Count | Validation |
|---|---|---|---|---|
| MCU Registers | Memory-mapped I/O at fixed addresses | RAM buffers at allocated addresses | 60+ register bases | Register read/write executes without fault |
| CAN | TMS570 DCAN peripheral | Linux SocketCAN (vcan0) | 1 module | Full CAN frame TX/RX functional |
| SPI | TMS570 MibSPI peripheral | No-op stub returning configurable data | 5+ modules | AFE data path tested via CAN injection |
| I2C | TMS570 I2C peripheral | No-op stub | 3+ modules | I2C-dependent features not exercised |
| GPIO | TMS570 GIO peripheral | RAM-mapped register | 10+ modules | Pin state readable/writable in software |
| ADC | TMS570 ADC peripheral | RAM-mapped register with static values | 5+ modules | ADC values configurable for test |
| DMA | TMS570 DMA peripheral | No-op stub | 3+ modules | DMA transfers replaced by direct copy |
| Timer | TMS570 RTI/Timer peripheral | POSIX clock_gettime / gettimeofday | 2+ modules | Timing functional on host |
| Watchdog | TMS570 RTI Watchdog | No-op stub (always satisfied) | 1 module | Watchdog disabled for SIL |
| Interrupt Controller | TMS570 VIM | No-op (cooperative loop, no interrupts) | 2+ modules | All processing synchronous |
| Flash | TMS570 Flash/ECC | No-op stub | 2+ modules | Flash checksum DIAG suppressed |
| Power Supply | TMS570 voltage regulators | No-op stub | 1 module | Power monitoring DIAG suppressed |
| SBC | NXP SBC chip via SPI | No-op stub returning OK status | 3+ modules | SBC state machine stubs |

## 6. Detailed HSI Mapping

### 6.1 MCU Register Bases

The TMS570LC4357 uses memory-mapped registers. In the POSIX port, each register base
is replaced by a `malloc`-allocated RAM buffer of the same structure size.

| Register Base | TMS570 Address | POSIX Replacement | Size (bytes) | Used By |
|---|---|---|---|---|
| systemREG1 | 0xFFFFFF00 | RAM buffer | 256 | System module |
| systemREG2 | 0xFFFFE100 | RAM buffer | 256 | System module |
| gioREG | 0xFFF7BC00 | RAM buffer | 128 | GPIO driver |
| gioPORTA | 0xFFF7BC34 | RAM buffer | 64 | Interlock, SPS |
| gioPORTB | 0xFFF7BC54 | RAM buffer | 64 | Contactor feedback |
| spiREG1 | 0xFFF7F400 | RAM buffer | 256 | AFE SPI |
| spiREG2 | 0xFFF7F600 | RAM buffer | 256 | SBC SPI |
| spiREG3 | 0xFFF7F800 | RAM buffer | 256 | SPS SPI |
| spiREG4 | 0xFFF7FA00 | RAM buffer | 256 | Spare SPI |
| spiREG5 | 0xFFF7FC00 | RAM buffer | 256 | Spare SPI |
| canREG1 | 0xFFF7DC00 | SocketCAN fd | 512 | CAN driver |
| canREG2 | 0xFFF7DE00 | SocketCAN fd | 512 | CAN driver |
| i2cREG1 | 0xFFF7D400 | RAM buffer | 128 | I2C driver |
| i2cREG2 | 0xFFF7D500 | RAM buffer | 128 | I2C driver |
| adcREG1 | 0xFFF7C000 | RAM buffer | 256 | ADC driver |
| adcREG2 | 0xFFF7C200 | RAM buffer | 256 | ADC driver |
| hetREG1 | 0xFFF7B800 | RAM buffer | 512 | HET timer |
| hetREG2 | 0xFFF7B900 | RAM buffer | 512 | HET timer |
| rtiREG1 | 0xFFFFFC00 | RAM buffer + clock_gettime | 256 | RTI timer, OS tick |
| dmaREG | 0xFFFFF000 | RAM buffer (no-op) | 512 | DMA controller |
| vimREG | 0xFFFFFE00 | RAM buffer (no-op) | 256 | Interrupt controller |
| esmREG | 0xFFFFF500 | RAM buffer | 256 | Error signaling |
| pmmREG | 0xFFFF0000 | RAM buffer | 128 | Power management |
| pcr1REG | 0xFFFFE000 | RAM buffer | 128 | Peripheral clock |
| pcr2REG | 0xFCFF1000 | RAM buffer | 128 | Peripheral clock |
| pcr3REG | 0xFFF78000 | RAM buffer | 128 | Peripheral clock |

Note: The full set of 60+ register bases follows the same pattern. The above table
shows the primary bases. Each is allocated via `malloc(sizeof(struct))` during
initialization.

### 6.2 CAN Interface

| Aspect | TMS570 | POSIX | Rationale |
|---|---|---|---|
| Physical layer | DCAN peripheral + CAN transceiver | Linux SocketCAN | Standard Linux CAN API |
| Initialization | DCAN register configuration | `socket(PF_CAN, SOCK_RAW, CAN_RAW)` + `bind()` | Direct API mapping |
| Transmit | Write to DCAN TX message object | `write(sockfd, &frame, sizeof(frame))` | Equivalent semantics |
| Receive | DCAN RX interrupt + message object | `read(sockfd, &frame, sizeof(frame))` non-blocking | Polled in cooperative loop |
| Filtering | DCAN acceptance mask registers | `setsockopt()` CAN filters | Equivalent functionality |
| Bus speed | 500 kbit/s on physical bus | Unlimited (virtual CAN) | No bus load limitation in SIL |
| Error handling | DCAN error and status register | `ioctl()` for error frames | Partial equivalence |

### 6.3 SPI Interface (AFE Communication)

| Aspect | TMS570 | POSIX | Impact |
|---|---|---|---|
| Physical layer | MibSPI with DMA | No-op stub | No actual SPI communication |
| Data path | SPI to LTC6813 AFE IC | CAN injection via 0x270/0x280 | Cell data injected externally |
| Transfer initiation | SPI register write | Function returns immediately | No latency modeling |
| Response data | SPI RXRAM | Pre-configured return values | Test controllable |
| Validation | AFE data validated by plausibility module | Same plausibility code executes | Safety logic preserved |

### 6.4 I2C Interface

| Aspect | TMS570 | POSIX | Impact |
|---|---|---|---|
| Physical layer | I2C peripheral | No-op stub | No actual I2C communication |
| Connected devices | EEPROM, port expanders | Not emulated | I2C features not exercised |
| Transfer | I2C register write/read | Returns STD_OK immediately | No functional testing |

### 6.5 GPIO Interface

| Aspect | TMS570 | POSIX | Impact |
|---|---|---|---|
| Pin read | GIO register read | RAM buffer read | Pin state software-controllable |
| Pin write | GIO register write | RAM buffer write | Output state stored in RAM |
| Interlock | GIO pin input | RAM buffer (default: interlock OK) | Interlock testable via buffer |
| Contactor feedback | GIO pin input | RAM buffer (configurable) | Feedback testable via buffer |

### 6.6 Timer / OS Tick

| Aspect | TMS570 | POSIX | Impact |
|---|---|---|---|
| RTI counter | Hardware counter at MCU clock | clock_gettime(CLOCK_MONOTONIC) | Millisecond resolution sufficient |
| OS tick | FreeRTOS tick interrupt | usleep(1000) in cooperative loop | ~1 ms tick approximation |
| Timestamp | RTI free-running counter | gettimeofday() | Real-time timestamps |

## 7. POSIX Port Justification

### 7.1 What Is Preserved

The POSIX port preserves the following safety-relevant software behaviors:

1. **SOA threshold checking logic**: All comparison operations against MOL/RSL/MSL values execute identically.
2. **DIAG threshold counting**: Counter increment/decrement logic, threshold comparison, and FATAL flagging are unchanged.
3. **BMS state machine**: All state transitions and guard conditions are identical.
4. **Contactor command logic**: Open/close commands are issued through the same API.
5. **Database producer/consumer pattern**: Single-writer discipline is maintained.
6. **CAN message encoding/decoding**: Frame packing and unpacking code is unchanged.

### 7.2 What Is Not Preserved

| Aspect | Reason | Mitigation |
|---|---|---|
| Real-time guarantees | POSIX host is not real-time | Timing tests verify approximate behavior |
| Interrupt latency | No interrupts in cooperative model | All processing is sequential |
| Hardware fault injection | No physical AFE, SBC, IMD | 24 DIAG IDs suppressed; hardware faults planned for Phase 3 |
| EMC/ESD behavior | No physical environment | Out of scope for SIL |
| Flash integrity | No physical flash | FLASHCHECKSUM DIAG suppressed |

### 7.3 Diagnostic Coverage Impact

| Category | Total DIAG IDs | Retained | Suppressed | Coverage |
|---|---|---|---|---|
| Cell voltage | 6 | 6 | 0 | 100% |
| Temperature | 12 | 12 | 0 | 100% |
| Current | 8 | 8 | 0 | 100% |
| Contactor | 3 | 3 | 0 | 100% |
| CAN/sensor | 4 | 4 | 0 | 100% |
| Plausibility | 2 | 2 | 0 | 100% |
| AFE communication | 4 | 4 | 0 | 100% |
| System critical | 3 | 3 | 0 | 100% |
| Hardware-specific | 24 | 0 | 24 | 0% (by design) |
| Other SW-checkable | 19 | 19 | 0 | 100% |
| **Total** | **85** | **61** | **24** | **72% overall; 100% of SW-checkable** |

## 8. Acceptance Criteria

This HSI specification is accepted when:

1. All 80+ HAL stub modules compile without errors.
2. All 60+ register bases are allocated and accessible.
3. The SIL binary starts and reaches SYS RUNNING state.
4. All 61 retained DIAG IDs can be triggered through their software paths.
5. No segfaults or undefined behavior occur during test execution.

---
*End of Document*
