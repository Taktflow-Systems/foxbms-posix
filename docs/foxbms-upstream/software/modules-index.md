# foxBMS 2 Software Modules (v1.10.0)

**Source**: [docs.foxbms.org/software/modules](https://docs.foxbms.org/software/modules/modules.html)

---

## Application Modules

| # | Module | Source | Description |
|---|--------|--------|-------------|
| 4.1 | **Algorithm** | `src/app/application/algorithm/` | SOC/SOE/SOF state estimation framework |
| 4.2 | **Balancing** | `src/app/application/bal/` | Voltage-based + history-based cell balancing |
| 4.3 | **BMS** | `src/app/application/bms/` | BMS state machine (STANDBY→NORMAL→ERROR) |
| 4.4 | **Plausibility** | `src/app/application/plausibility/` | Sensor data consistency validation |
| 4.5 | **Redundancy** | `src/app/application/redundancy/` | IVT cross-checking, AFE validation |
| 4.6 | **SOA** | `src/app/application/soa/` | Safe Operating Area checks (MOL/RSL/MSL) |

## Engine Modules

| # | Module | Source | Description |
|---|--------|--------|-------------|
| 4.7 | **Database** | `src/app/engine/database/` | Producer/consumer data exchange |
| 4.8 | **Diagnosis** | `src/app/engine/diag/` | Fault detection, threshold counters, callbacks |
| 4.9 | **HW Info** | `src/app/engine/hw_info/` | Hardware configuration info |
| 4.10 | **SYS** | `src/app/engine/sys/` | System state machine (init → RUNNING) |
| 4.11 | **SYS_MON** | `src/app/engine/sys_mon/` | Task timing compliance monitoring |

## Task Modules

| # | Module | Source | Description |
|---|--------|--------|-------------|
| 4.12 | **FTASK** | `src/app/task/ftask/` | 7 FreeRTOS tasks, creation, scheduling |
| 4.13 | **OS** | `src/app/task/os/` | OS abstraction layer |

## Driver Modules

| # | Module | Source | Description |
|---|--------|--------|-------------|
| 4.14 | ADC | `src/app/driver/adc/` | Analog-to-digital conversion |
| 4.15 | **CAN** | `src/app/driver/can/` | CAN bus TX/RX, callbacks, mailbox config |
| 4.16 | CRC | `src/app/driver/crc/` | CRC calculations |
| 4.17 | **Contactor** | `src/app/driver/contactor/` | Contactor open/close, feedback |
| 4.18 | DMA | `src/app/driver/dma/` | Direct memory access |
| 4.19 | foxmath | `src/app/driver/foxmath/` | Math utilities |
| 4.20 | utils | `src/app/driver/foxmath/` | General utilities |
| 4.21 | FRAM | `src/app/driver/fram/` | Ferroelectric RAM |
| 4.22 | HTSEN | `src/app/driver/htsen/` | Humidity/temperature sensor |
| 4.23 | I2C | `src/app/driver/i2c/` | I2C communication |
| 4.24 | **IMD** | `src/app/driver/imd/` | Insulation monitoring (Bender IR155/iso165c) |
| 4.25 | **Interlock** | `src/app/driver/interlock/` | Safety interlock circuit |
| 4.26 | IO | `src/app/driver/io/` | GPIO pin management |
| 4.27 | MEAS | `src/app/driver/meas/` | Measurement acquisition |
| 4.28 | MCU | `src/app/driver/mcu/` | MCU interface |
| 4.29 | **AFE API** | `src/app/driver/afe/` | Analog Front-End interface |
| 4.30 | AFE Impls | `src/app/driver/afe/` | ADI ADES1830, LTC, Maxim, NXP MC33775A, Debug |
| 4.31 | PEX | `src/app/driver/pex/` | Port expander |
| 4.32 | PWM | `src/app/driver/pwm/` | Pulse-width modulation |
| 4.33 | RTC | `src/app/driver/rtc/` | Real-time clock |
| 4.34 | **SBC** | `src/app/driver/sbc/` | System Basis Chip (NXP FS8x) |
| 4.35 | SPI | `src/app/driver/spi/` | SPI communication |
| 4.36 | **SPS** | `src/app/driver/sps/` | Smart Power Switch (contactors) |
| 4.37 | TS API | `src/app/driver/ts/` | Temperature sensor interface |
| 4.38 | TS Impls | `src/app/driver/ts/` | Thermistor implementations |

## Startup / Misc

| # | Module | Source | Description |
|---|--------|--------|-------------|
| 4.39 | Startup | `src/app/main/` | System initialization sequence |
| 4.40 | Version | `src/app/main/` | Version information |
| 4.41 | **fassert** | `src/app/main/include/fassert.h` | Runtime assertions |

**Bold** = modules critical to the POSIX port.
