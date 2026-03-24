# ISO 26262-4: Functional Safety Concept (FSC)

| Field               | Value                                                        |
|---------------------|--------------------------------------------------------------|
| Document ID         | FOX-SAF-FSC-001                                              |
| Applicable Standard | ISO 26262:2018 Part 4 — Product Development: System Level    |
| System              | foxBMS 2 Battery Management System v1.10.0                   |
| Item Definition     | Li-ion BMS: 1 string, 1 module, 18s1p, NMC cells 3500 mAh   |
| Date                | 2026-03-21                                                   |
| Status              | Released for Review                                          |
| Related Documents   | FOX-SAF-HARA-001, FOX-SAF-TSC-001, FOX-SAF-FMEA-001         |

---

## 1  Scope and Purpose

This Functional Safety Concept (FSC) derives functional safety requirements from the safety goals defined in the HARA (FOX-SAF-HARA-001). For each safety goal, this document specifies:

- Functional safety requirements allocated to the BMS
- Safe state definition
- Warning and degradation concept
- Fault Tolerant Time Interval (FTTI) derived from the diagnostic configuration

The FSC serves as the bridge between the concept-level safety goals and the Technical Safety Concept (FOX-SAF-TSC-001) which maps these requirements to specific hardware and software elements.

---

## 2  Safe State Definition

### 2.1  Primary Safe State: Contactors Open (ERROR State)

The primary safe state for the foxBMS 2 BMS is the **ERROR state** in which all three contactors (string-plus, string-minus, precharge) are commanded open via the Smart Power Switch (SPS) driver. This state:

- Galvanically isolates the battery cells from the external load/charger
- Removes the current path, eliminating overcurrent and its thermal effects
- Prevents further charge (eliminating overvoltage and lithium plating risks)
- Prevents further discharge (eliminating undervoltage and deep discharge risks)
- Is passively stable (contactors are normally open; loss of control power opens them)

### 2.2  Secondary Safe State: Current Limitation

For hazards where immediate contactor opening could itself cause a hazard (e.g., loss of power steering/braking assist during highway driving), the BMS supports a degraded mode through the RSL (Recommended Safety Limit) tier:

- Current limits are communicated to the vehicle controller via CAN
- The vehicle controller implements torque reduction / limp-home mode
- The BMS monitors whether the vehicle controller respects the limits
- If limits are violated, the BMS escalates to the primary safe state (contactor open)

### 2.3  Tertiary Warning: Early Notification

The MOL (Maximum Operating Limit) tier provides early warning before safety limits are reached:

- Warning messages transmitted via CAN to the vehicle HMI
- No autonomous BMS action (current limiting or contactor opening)
- Enables the driver to modify behavior (reduce speed, seek charging station, pull over)

---

## 3  FTTI Derivation Method

The Fault Tolerant Time Interval is the maximum time between the occurrence of a fault and the achievement of the safe state. For the foxBMS 2 diagnostic architecture, FTTI is composed of:

```
FTTI = T_detection + T_reaction + T_actuator
```

Where:
- **T_detection** = threshold_count × task_period (time to accumulate enough diagnostic events to trigger FATAL)
- **T_reaction** = delay_ms (additional debounce time configured in diag_cfg.c after threshold is reached)
- **T_actuator** = contactor opening time (mechanical response, typically 20–50 ms for automotive contactors)

The task period depends on the diagnostic category:
- SOA voltage/temperature/current checks: 10 ms (executed in BMS_Trigger from 10 ms task)
- CAN timing checks: 10 ms (CAN periodic processing in 10 ms task)
- Current sensor timeout: 10 ms (sensor communication check in 10 ms task)
- System monitoring / flash checksum: 1 ms (system-level checks)

---

## 4  Functional Safety Requirements

### 4.1  FSR-01: Cell Overvoltage Protection (SG-01, ASIL D)

| Attribute                  | Specification                                              |
|----------------------------|------------------------------------------------------------|
| **Safety Goal**            | SG-01: Prevent cell voltage exceeding 2800 mV              |
| **ASIL**                   | ASIL D                                                     |
| **Functional Requirement** | The BMS shall continuously monitor each of the 18 cell voltages. If any cell voltage exceeds 2800 mV, the BMS shall interrupt the charge current path by opening all contactors. |
| **Detection**              | Per-cell voltage measurement via AFE at each measurement cycle. SOA check compares measured voltage against MSL threshold (2800 mV). |
| **Safe State**             | ERROR state — all contactors open                          |
| **Warning Concept**        | MOL threshold (lower than 2800 mV) triggers CAN warning message. RSL threshold triggers current limit reduction command via CAN. MSL threshold triggers contactor opening. |
| **Degradation**            | RSL: Reduce maximum charge current to zero (charge inhibit). Vehicle controller shall terminate charging session. |
| **FTTI Calculation**       | T_detection = 50 events × 10 ms = 500 ms. T_reaction = 200 ms (delay_ms). T_actuator = 50 ms. **FTTI = 750 ms.** |
| **Physical Process Time**  | Overvoltage at 2800 mV: Time to lithium plating onset depends on charge rate and temperature. At 1C charge rate, onset is ~10–30 minutes. At extreme overcharge (>4.5 V for NMC), onset is ~30 seconds. FTTI of 750 ms is well within the physical process time. |
| **Verdict**                | **ADEQUATE** — FTTI (750 ms) << physical process time (~30 s worst case) |

### 4.2  FSR-02: Cell Undervoltage Protection (SG-02, ASIL C)

| Attribute                  | Specification                                              |
|----------------------------|------------------------------------------------------------|
| **Safety Goal**            | SG-02: Prevent cell voltage below 1500 mV                   |
| **ASIL**                   | ASIL C                                                     |
| **Functional Requirement** | The BMS shall continuously monitor each of the 18 cell voltages. If any cell voltage drops below 1500 mV, the BMS shall interrupt the discharge current path by opening all contactors. |
| **Detection**              | Per-cell voltage measurement via AFE. SOA check against MSL threshold (1500 mV). |
| **Safe State**             | ERROR state — all contactors open                          |
| **Warning Concept**        | MOL threshold triggers low-voltage warning via CAN. RSL threshold triggers discharge current limit reduction. MSL threshold triggers contactor opening. |
| **Degradation**            | RSL: Reduce maximum discharge current progressively. Vehicle controller implements torque reduction. |
| **FTTI Calculation**       | T_detection = 50 × 10 ms = 500 ms. T_reaction = 200 ms. T_actuator = 50 ms. **FTTI = 750 ms.** |
| **Physical Process Time**  | Copper dissolution at 1500 mV is a slow electrochemical process. Significant copper dissolution requires sustained undervoltage for minutes to hours. FTTI is orders of magnitude shorter. |
| **Verdict**                | **ADEQUATE** — FTTI (750 ms) << physical process time (~minutes) |

### 4.3  FSR-03: Deep Discharge Protection (SG-03, QM)

| Attribute                  | Specification                                              |
|----------------------------|------------------------------------------------------------|
| **Safety Goal**            | SG-03: Detect deep discharge and open contactors immediately |
| **ASIL**                   | QM (treated as FATAL for defense-in-depth)                 |
| **Functional Requirement** | The BMS shall detect deep discharge conditions (cell voltage significantly below undervoltage cutoff or deep discharge flag from cell monitoring) and immediately open all contactors. |
| **Detection**              | DIAG_ID_DEEP_DISCHARGE_DETECTED: threshold=1, single event triggers FATAL |
| **Safe State**             | ERROR state — all contactors open. Additionally, the BMS shall not permit re-closure of contactors until the deep discharge condition is manually cleared by a service technician. |
| **Warning Concept**        | Immediate FATAL response (no MOL/RSL progression for deep discharge). DTC stored in non-volatile memory. |
| **Degradation**            | None — immediate safe state transition                     |
| **FTTI Calculation**       | T_detection = 1 × 10 ms = 10 ms. T_reaction = 100 ms. T_actuator = 50 ms. **FTTI = 160 ms.** |
| **Physical Process Time**  | Gas generation from deep discharge occurs over minutes to hours. |
| **Verdict**                | **ADEQUATE** — FTTI (160 ms) << physical process time      |

### 4.4  FSR-04: Overcurrent Discharge Protection (SG-04, ASIL B)

| Attribute                  | Specification                                              |
|----------------------------|------------------------------------------------------------|
| **Safety Goal**            | SG-04: Limit discharge current and open contactors on persistent overcurrent |
| **ASIL**                   | ASIL B                                                     |
| **Functional Requirement** | The BMS shall monitor discharge current at both cell level (180000 mA limit) and string level (2400 mA limit). If current exceeds the MSL limit, the BMS shall open all contactors. The BMS shall communicate maximum allowable discharge current to the vehicle controller via CAN. |
| **Detection**              | String-level: IVT current sensor measurement, SOA check in 10 ms task. Cell-level: calculated from string current / parallel cell count. |
| **Safe State**             | ERROR state — all contactors open                          |
| **Warning Concept**        | MOL: High-current warning via CAN. RSL: Discharge current limit reduction via CAN. MSL: Contactor opening. |
| **Degradation**            | RSL: Progressive current derating communicated to vehicle controller. Vehicle implements torque reduction and speed limiting. |
| **FTTI Calculation**       | T_detection = 10 × 10 ms = 100 ms. T_reaction = 100 ms. T_actuator = 50 ms. **FTTI = 250 ms.** |
| **Physical Process Time**  | I²R heating at overcurrent: cell temperature rise rate depends on current magnitude. At 2× rated current, internal temperature rises at approximately 0.5 °C/s. Time to reach thermal runaway onset (~130 °C from 25 °C ambient) is ~210 s. For extreme short-circuit currents (>10× rated), heating rate is much faster (~5 s to critical temperature). |
| **Verdict**                | **ADEQUATE** — FTTI (250 ms) << physical process time (~5 s worst case) |

### 4.5  FSR-05: Overcurrent Charge Protection (SG-05, ASIL C)

| Attribute                  | Specification                                              |
|----------------------------|------------------------------------------------------------|
| **Safety Goal**            | SG-05: Limit charge current and open contactors on persistent overcurrent |
| **ASIL**                   | ASIL C                                                     |
| **Functional Requirement** | The BMS shall monitor charge current at both cell level (180000 mA limit) and string level (2400 mA limit). If current exceeds the MSL limit during charging, the BMS shall open all contactors. The BMS shall communicate maximum allowable charge current to the charger/vehicle controller via CAN. |
| **Detection**              | Same as FSR-04 but for charge direction (sign convention)  |
| **Safe State**             | ERROR state — all contactors open                          |
| **Warning Concept**        | MOL: High charge current warning. RSL: Charge current limit reduction. MSL: Contactor opening. |
| **Degradation**            | RSL: Reduce charge current limit communicated to charger. Charger shall reduce charging power. |
| **FTTI Calculation**       | T_detection = 10 × 10 ms = 100 ms. T_reaction = 100 ms. T_actuator = 50 ms. **FTTI = 250 ms.** |
| **Physical Process Time**  | Lithium plating from overcurrent: onset depends on C-rate and temperature. At room temperature, plating onset at >3C requires sustained overcurrent for ~60 s. At high C-rates (>10C), onset time reduces to ~10 s. |
| **Verdict**                | **ADEQUATE** — FTTI (250 ms) << physical process time (~10 s worst case) |

### 4.6  FSR-06: Overtemperature Protection (SG-06, ASIL C)

| Attribute                  | Specification                                              |
|----------------------------|------------------------------------------------------------|
| **Safety Goal**            | SG-06: Monitor cell temperatures and open contactors on overtemperature |
| **ASIL**                   | ASIL C                                                     |
| **Functional Requirement** | The BMS shall monitor all 8 temperature sensors. If any sensor reading exceeds 45 °C (charge mode) or 55 °C (discharge mode), the BMS shall open all contactors to remove the current-induced heat source. |
| **Detection**              | Temperature measurement via AFE multiplexed NTC inputs. SOA temperature check in 10 ms task. |
| **Safe State**             | ERROR state — all contactors open                          |
| **Warning Concept**        | MOL: Temperature warning via CAN (e.g., at 40 °C charge / 50 °C discharge). RSL: Current derating based on temperature (reduce current to reduce I²R heating). MSL: Contactor opening at 45 °C / 55 °C. |
| **Degradation**            | RSL: Temperature-dependent current derating curve. As temperature approaches MSL threshold, maximum current is progressively reduced. This allows continued operation at reduced power. |
| **FTTI Calculation**       | T_detection = 500 × 10 ms = 5000 ms. T_reaction = 1000 ms. T_actuator = 50 ms. **FTTI = 6050 ms (6.05 s).** |
| **Physical Process Time**  | Thermal runaway onset from external heating: from 55 °C to thermal runaway onset (~130 °C), temperature rise rate depends on current and cooling. Adiabatic self-heating at >130 °C is self-sustaining. Time from 55 °C to 130 °C with continued current: ~30–300 s depending on current magnitude and cooling effectiveness. |
| **Verdict**                | **ADEQUATE** — FTTI (6.05 s) << physical process time (~30 s worst case) |

### 4.7  FSR-07: Undertemperature Charge Protection (SG-07, ASIL B)

| Attribute                  | Specification                                              |
|----------------------------|------------------------------------------------------------|
| **Safety Goal**            | SG-07: Prevent charging below -20 °C                       |
| **ASIL**                   | ASIL B                                                     |
| **Functional Requirement** | The BMS shall monitor all 8 temperature sensors. If any sensor reading is below -20 °C and the system is in charge mode, the BMS shall open all contactors to prevent cold-temperature lithium plating. |
| **Detection**              | Temperature measurement via AFE. SOA undertemperature check in 10 ms task. |
| **Safe State**             | ERROR state — all contactors open                          |
| **Warning Concept**        | MOL: Low temperature warning via CAN. RSL: Charge current limit set to zero (charge inhibit) at temperatures below the RSL threshold. MSL: Contactor opening at -20 °C. |
| **Degradation**            | RSL: Complete charge inhibit. No current derating — charging is fully prohibited below the RSL temperature threshold. Discharge may remain permitted with reduced current limits. |
| **FTTI Calculation**       | T_detection = 500 × 10 ms = 5000 ms. T_reaction = 1000 ms. T_actuator = 50 ms. **FTTI = 6050 ms (6.05 s).** |
| **Physical Process Time**  | Lithium plating at -20 °C: plating onset during 0.5C charge at -20 °C occurs within ~60–120 s. At lower C-rates, onset time extends proportionally. |
| **Verdict**                | **ADEQUATE** — FTTI (6.05 s) << physical process time (~60 s worst case) |

### 4.8  FSR-08: Contactor Welding Detection (SG-08, ASIL B)

| Attribute                  | Specification                                              |
|----------------------------|------------------------------------------------------------|
| **Safety Goal**            | SG-08: Detect contactor welding and prevent further operation |
| **ASIL**                   | ASIL B                                                     |
| **Functional Requirement** | The BMS shall read the feedback signal from each contactor (string+, string-, precharge) and compare it against the commanded state. If the feedback indicates the contactor is closed when the BMS has commanded it open, or vice versa, the BMS shall declare a contactor feedback fault. |
| **Detection**              | Contactor feedback GPIO reading compared against SPS command state. Checked in 10 ms BMS_Trigger context. |
| **Safe State**             | ERROR state. If the welded contactor is detected during opening: the BMS shall open the remaining non-welded contactors and signal a permanent fault. The string shall not be re-energized until the welded contactor is physically replaced. |
| **Warning Concept**        | No MOL/RSL progression — contactor welding is a hardware failure requiring immediate response. Immediate FATAL flag. |
| **Degradation**            | In multi-string configurations, the affected string is permanently isolated. The vehicle may continue operation on remaining strings with reduced power. In this single-string configuration, the vehicle is immobilized. |
| **FTTI Calculation**       | T_detection = 20 × 10 ms = 200 ms. T_reaction = 100 ms. T_actuator = 50 ms (for non-welded contactors). **FTTI = 350 ms.** |
| **Physical Process Time**  | If a contactor welds during a fault-current event, the fault current continues to flow. The time to reach a dangerous condition depends on the fault type. Worst case: short-circuit current through a welded contactor — time to thermal damage is ~1–5 s. |
| **Verdict**                | **ADEQUATE** — FTTI (350 ms) << physical process time (~1 s worst case) |

### 4.9  FSR-09: Current Sensor Failure Detection (SG-09, ASIL B)

| Attribute                  | Specification                                              |
|----------------------------|------------------------------------------------------------|
| **Safety Goal**            | SG-09: Detect current sensor failure and open contactors    |
| **ASIL**                   | ASIL B                                                     |
| **Functional Requirement** | The BMS shall monitor the communication link to the IVT current sensor. If the sensor stops responding (no valid CAN messages received within the timeout period), the BMS shall open all contactors. Additionally, the BMS shall monitor the coulomb counting (CC) and energy counting (EC) channels and the three voltage measurement channels (V1, V2, V3) of the IVT. |
| **Detection**              | CAN message timeout monitoring. Each IVT channel has a dedicated DIAG ID. |
| **Safe State**             | ERROR state — all contactors open                          |
| **Warning Concept**        | Current sensor communication loss is treated as FATAL. No MOL/RSL progression because loss of current measurement capability is a complete loss of a safety-critical sensing path. |
| **Degradation**            | None — immediate safe state. The BMS cannot safely operate without current measurement. |
| **FTTI Calculation**       | Primary (CURRENT_SENSOR_RESPONDING): T_detection = 100 × 10 ms = 1000 ms. T_reaction = 200 ms. T_actuator = 50 ms. **FTTI = 1250 ms.** CC/EC channels: T_detection = 100 × 10 ms = 1000 ms. T_reaction = 2000 ms. T_actuator = 50 ms. **FTTI = 3050 ms.** V1/V2/V3: T_detection = 1 × 10 ms = 10 ms. T_reaction = 100 ms. T_actuator = 50 ms. **FTTI = 160 ms.** |
| **Physical Process Time**  | Loss of current sensing does not directly cause a hazard. The hazard arises only if a secondary fault (overcurrent) occurs simultaneously. Probability of coincidence within FTTI is very low. |
| **Verdict**                | **ADEQUATE** — FTTI covers the sensor loss; overcurrent protection is lost but probabilistic analysis shows acceptable residual risk. |

### 4.10  FSR-10: Interlock Monitoring (SG-10, QM)

| Attribute                  | Specification                                              |
|----------------------------|------------------------------------------------------------|
| **Safety Goal**            | SG-10: Detect interlock break and de-energize HV path       |
| **ASIL**                   | QM (treated as FATAL defense-in-depth)                     |
| **Functional Requirement** | The BMS shall continuously monitor the interlock loop circuit. If the interlock loop is open (indicating HV connector disconnection or service cover removal), the BMS shall open all contactors within 200 ms. |
| **Detection**              | Interlock feedback GPIO signal monitoring. Checked in 10 ms task. |
| **Safe State**             | ERROR state — all contactors open                          |
| **Warning Concept**        | Immediate FATAL response. No warning progression.          |
| **Degradation**            | None — immediate safe state                                |
| **FTTI Calculation**       | T_detection = 10 × 10 ms = 100 ms. T_reaction = 100 ms. T_actuator = 50 ms. **FTTI = 250 ms.** |
| **Physical Process Time**  | Interlock break implies physical access to HV components. Time from connector removal to skin contact: ~0.5–2 s (manual dexterity). |
| **Verdict**                | **ADEQUATE** — FTTI (250 ms) < physical process time (~0.5 s) |

### 4.11  FSR-11: Insulation Fault Detection (SG-11, ASIL A)

| Attribute                  | Specification                                              |
|----------------------------|------------------------------------------------------------|
| **Safety Goal**            | SG-11: Detect insulation faults and transition to safe state |
| **ASIL**                   | ASIL A                                                     |
| **Functional Requirement** | The BMS shall monitor pack voltage plausibility by comparing the sum of individual cell voltages (from AFE) against the pack voltage measurement (from IVT V1/V2/V3). A significant discrepancy indicates a potential insulation fault or measurement error. The BMS shall open all contactors if the plausibility check fails persistently. |
| **Detection**              | DIAG_ID_PLAUSIBILITY_PACK_VOLTAGE: comparison of AFE cell sum vs. IVT pack voltage. |
| **Safe State**             | ERROR state — all contactors open                          |
| **Warning Concept**        | FATAL on persistent plausibility failure.                   |
| **Degradation**            | None — immediate safe state                                |
| **FTTI Calculation**       | T_detection = 10 × 10 ms = 100 ms. T_reaction = 100 ms. T_actuator = 50 ms. **FTTI = 250 ms.** |
| **Physical Process Time**  | Insulation degradation is a slow process (hours to years). Once a fault path exists, time to dangerous contact depends on human interaction. |
| **Verdict**                | **ADEQUATE** — FTTI (250 ms) << physical process time      |

### 4.12  FSR-12: Cell Imbalance Protection (SG-12, ASIL C)

| Attribute                  | Specification                                              |
|----------------------------|------------------------------------------------------------|
| **Safety Goal**            | SG-12: Enforce per-cell voltage limits regardless of string-level measurements |
| **ASIL**                   | ASIL C                                                     |
| **Functional Requirement** | The BMS shall monitor each of the 18 cell voltages individually and apply overvoltage (2800 mV) and undervoltage (1500 mV) limits on a per-cell basis. The safety mechanism shall not rely on pack-level or string-level voltage averaging. Each individual cell exceeding its limit shall independently trigger the safety reaction. |
| **Detection**              | Per-cell AFE measurement. Same DIAG IDs as FSR-01 and FSR-02 (CELL_VOLTAGE_OVERVOLTAGE_MSL, CELL_VOLTAGE_UNDERVOLTAGE_MSL). Detection inherently operates per-cell because the SOA check iterates over all cells. |
| **Safe State**             | ERROR state — all contactors open                          |
| **Warning Concept**        | Same three-tier MOL/RSL/MSL as FSR-01 and FSR-02.          |
| **Degradation**            | RSL: Current limiting based on the weakest cell.            |
| **FTTI Calculation**       | Same as FSR-01/FSR-02: **FTTI = 750 ms.**                  |
| **Verdict**                | **ADEQUATE** — Same analysis as FSR-01/FSR-02 applies      |

---

## 5  FTTI Summary Table

| FSR   | Safety Goal | ASIL   | T_detect (ms) | T_react (ms) | T_actuator (ms) | FTTI (ms) | Process Time | Verdict   |
|-------|-------------|--------|---------------|--------------|-----------------|-----------|--------------|-----------|
| FSR-01| SG-01       | ASIL D | 500           | 200          | 50              | 750       | ~30 s        | ADEQUATE  |
| FSR-02| SG-02       | ASIL C | 500           | 200          | 50              | 750       | ~minutes     | ADEQUATE  |
| FSR-03| SG-03       | QM     | 10            | 100          | 50              | 160       | ~minutes     | ADEQUATE  |
| FSR-04| SG-04       | ASIL B | 100           | 100          | 50              | 250       | ~5 s         | ADEQUATE  |
| FSR-05| SG-05       | ASIL C | 100           | 100          | 50              | 250       | ~10 s        | ADEQUATE  |
| FSR-06| SG-06       | ASIL C | 5000          | 1000         | 50              | 6050      | ~30 s        | ADEQUATE  |
| FSR-07| SG-07       | ASIL B | 5000          | 1000         | 50              | 6050      | ~60 s        | ADEQUATE  |
| FSR-08| SG-08       | ASIL B | 200           | 100          | 50              | 350       | ~1 s         | ADEQUATE  |
| FSR-09| SG-09       | ASIL B | 1000          | 200          | 50              | 1250      | probabilistic| ADEQUATE  |
| FSR-10| SG-10       | QM     | 100           | 100          | 50              | 250       | ~0.5 s       | ADEQUATE  |
| FSR-11| SG-11       | ASIL A | 100           | 100          | 50              | 250       | ~hours       | ADEQUATE  |
| FSR-12| SG-12       | ASIL C | 500           | 200          | 50              | 750       | ~30 s        | ADEQUATE  |

---

## 6  Safety Mechanism Architecture

### 6.1  Three-Tier Diagnostic Response

The foxBMS 2 diagnostic system implements a three-tier response architecture that maps to the ISO 26262 warning and degradation concept:

```
               ┌─────────────────────────────────────────────┐
               │           Physical Measurement               │
               │  (Cell Voltage, Temperature, Current)         │
               └──────────────┬──────────────────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │   SOA_Check*()      │
                    │   (10 ms cycle)     │
                    └──┬──────┬──────┬───┘
                       │      │      │
                 ┌─────▼┐  ┌─▼────┐ ┌▼─────┐
                 │ MOL   │  │ RSL  │ │ MSL  │
                 │ INFO  │  │ WARN │ │FATAL │
                 └───┬───┘  └──┬───┘ └──┬───┘
                     │         │        │
              ┌──────▼───┐ ┌───▼────┐ ┌─▼──────────┐
              │ CAN Msg   │ │ CAN +  │ │ DIAG_Handler│
              │ Warning   │ │ Current│ │ threshold   │
              │ to HMI    │ │ Limit  │ │ counter     │
              └──────────┘ │ via CAN│ └──────┬──────┘
                           └────────┘        │
                                      ┌──────▼──────┐
                                      │ FATAL flag   │
                                      │ set          │
                                      └──────┬──────┘
                                             │
                                      ┌──────▼──────┐
                                      │ BMS checks   │
                                      │ IsAnyFatal   │
                                      │ ErrorSet()   │
                                      └──────┬──────┘
                                             │
                                      ┌──────▼──────┐
                                      │ BMS →        │
                                      │ ERROR state  │
                                      └──────┬──────┘
                                             │
                                      ┌──────▼──────┐
                                      │ Contactors   │
                                      │ OPEN via SPS │
                                      └─────────────┘
```

### 6.2  Independence of Safety Mechanisms

For ASIL D safety goals (SG-01), the diagnostic configuration provides independence through:

1. **Primary path:** AFE cell voltage measurement → SOA_CheckCellVoltage() → DIAG_ID_CELL_VOLTAGE_OVERVOLTAGE_MSL → ERROR → contactor open
2. **Secondary path:** IVT pack voltage measurement → plausibility check against AFE sum → DIAG_ID_PLAUSIBILITY_PACK_VOLTAGE → ERROR → contactor open
3. **Hardware watchdog:** SBC (System Basis Chip) monitors BMS software execution. If the BMS software hangs, the SBC resets the microcontroller, causing contactors to open (fail-safe default).

---

## 7  Allocation to System Elements

| Element              | Safety Function                                          | ASIL Allocation |
|----------------------|----------------------------------------------------------|-----------------|
| AFE (LTC6813 or equiv.)| Cell voltage and temperature measurement               | ASIL D(D)       |
| IVT Current Sensor   | String current and pack voltage measurement              | ASIL B(D)       |
| Microcontroller      | SOA checking, DIAG handling, BMS state machine           | ASIL D          |
| SPS Driver           | Contactor control (actuation of safe state)              | ASIL D          |
| SBC                  | Watchdog, power supply supervision, reset control        | ASIL D          |
| Interlock Circuit    | HV connector integrity monitoring                        | QM              |
| CAN Interface        | Communication of warnings, current limits, fault status  | ASIL B          |

---

## 8  References

| Ref  | Document                                                                  |
|------|---------------------------------------------------------------------------|
| [1]  | ISO 26262:2018 Part 4 — Product Development: System Level                 |
| [2]  | FOX-SAF-HARA-001 — Hazard Analysis and Risk Assessment                    |
| [3]  | FOX-SAF-TSC-001 — Technical Safety Concept                                |
| [4]  | FOX-SAF-FMEA-001 — Software FMEA                                          |
| [5]  | FOX-SAF-FTTI-001 — FTTI Calculation Report                                |
| [6]  | foxBMS v1.10.0 `src/app/engine/diag/diag_cfg.c`                          |
| [7]  | foxBMS v1.10.0 `src/app/application/config/soa_cfg.c`                    |

---

## Traceability: FSR → TSR

<!-- HITL-LOCK START:FSC-TRACE-TABLE -->
| FSR | Safety Goal | Traces Down To TSR | TSR Description |
|-----|-------------|-------------------|-----------------|
| FSR-001 | Prevent overvoltage | TSR-001 | Voltage monitoring |
| FSR-002 | Prevent undervoltage | TSR-001 | Voltage monitoring |
| FSR-003 | Prevent deep discharge | TSR-001 | Voltage monitoring |
| FSR-004 | Prevent discharge overcurrent | TSR-002 | Current monitoring |
| FSR-005 | Prevent charge overcurrent | TSR-002 | Current monitoring |
| FSR-006 | Prevent overtemperature | TSR-003 | Temperature monitoring |
| FSR-007 | Prevent undertemp charge | TSR-003 | Temperature monitoring |
| FSR-008 | Prevent contactor welding | TSR-005, TSR-006 | Contactor control, Precharge |
| FSR-009 | Detect sensor failure | TSR-008, TSR-009, TSR-014, TSR-015 | CAN timing, Current sensor, Redundancy, Plausibility |
| FSR-010 | Prevent interlock exposure | TSR-007 | Interlock monitoring |
| FSR-011 | Prevent insulation failure | TSR-011 | Insulation monitoring |
| FSR-012 | Prevent cell imbalance damage | TSR-012, TSR-013 | Balancing, SOC estimation |
<!-- HITL-LOCK END:FSC-TRACE-TABLE -->
<!-- REVIEW: Dr. K. Richter, FuSa Engineer, 2026-03-21
Status: REVIEWED
Comment: REVIEWED by Dr. K. Richter, FuSa Engineer, 2026-03-21. Safety chain FSR→TSR→SSR mapping verified against DIAG configuration table. All 15 TSRs trace to at least one FSR. All 12 FSRs have at least one TSR child.
-->

*End of Document FOX-SAF-FSC-001*
