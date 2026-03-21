# ISO 26262-5: Software Failure Mode and Effects Analysis (FMEA)

| Field               | Value                                                        |
|---------------------|--------------------------------------------------------------|
| Document ID         | FOX-SAF-FMEA-001                                             |
| Applicable Standard | ISO 26262:2018 Part 5 — Product Development: Hardware Level  |
| Method              | FMEA per IEC 60812 adapted for software-intensive systems    |
| System              | foxBMS 2 Battery Management System v1.10.0                   |
| Item Definition     | Li-ion BMS: 1 string, 1 module, 18s1p, NMC cells 3500 mAh   |
| Date                | 2026-03-21                                                   |
| Status              | Released for Review                                          |
| Related Documents   | FOX-SAF-HARA-001, FOX-SAF-FSC-001, FOX-SAF-TSC-001          |

---

## 1  Scope

This Software FMEA analyzes failure modes of the foxBMS 2 diagnostic subsystem and its monitored elements. Each failure mode is assessed for its local effect, system-level effect, and end effect on vehicle occupants or persons. The Risk Priority Number (RPN) is calculated using:

```
RPN = Severity (S) × Occurrence (O) × Detection (D)
```

Where:
- **Severity (S):** 1–10 scale (1 = no effect, 10 = hazard without warning)
- **Occurrence (O):** 1–10 scale (1 = extremely unlikely, 10 = almost certain)
- **Detection (D):** 1–10 scale (1 = almost certain detection, 10 = no detection)

RPN threshold for action: **RPN > 100** requires risk reduction measures.

---

## 2  Severity Rating Scale

| Rating | Description                                                          |
|--------|----------------------------------------------------------------------|
| 1      | No effect                                                            |
| 2      | Very minor effect — cosmetic defect, no functional impact            |
| 3      | Minor effect — reduced comfort, no safety impact                     |
| 4      | Moderate effect — degraded performance, customer dissatisfaction     |
| 5      | Significant effect — partial loss of function, customer complaint    |
| 6      | Major effect — loss of primary function, regulatory non-compliance   |
| 7      | High severity — potential for injury (non-life-threatening)          |
| 8      | Very high severity — potential for serious injury                    |
| 9      | Hazardous with warning — potential for life-threatening injury       |
| 10     | Hazardous without warning — potential for fatal injury               |

## 3  Occurrence Rating Scale

| Rating | Description                                    | Approximate Failure Rate  |
|--------|------------------------------------------------|---------------------------|
| 1      | Extremely unlikely                             | < 1 in 1,500,000          |
| 2      | Remote                                         | 1 in 150,000              |
| 3      | Very low                                       | 1 in 15,000               |
| 4      | Low                                            | 1 in 2,000                |
| 5      | Moderate                                       | 1 in 400                  |
| 6      | Moderately high                                | 1 in 80                   |
| 7      | High                                           | 1 in 20                   |
| 8      | Very high                                      | 1 in 8                    |
| 9      | Extremely high                                 | 1 in 3                    |
| 10     | Almost certain                                 | > 1 in 2                  |

## 4  Detection Rating Scale

| Rating | Description                                                          |
|--------|----------------------------------------------------------------------|
| 1      | Almost certain detection — continuous automated monitoring with proven mechanism |
| 2      | Very high — automated detection with redundant check                 |
| 3      | High — automated detection with single mechanism                     |
| 4      | Moderately high — automated detection with time delay                |
| 5      | Moderate — automated detection but with significant latency          |
| 6      | Low — detection relies on indirect measurement                       |
| 7      | Very low — detection relies on manual inspection or external report  |
| 8      | Remote — detection only during specific test conditions              |
| 9      | Very remote — no systematic detection, found by chance               |
| 10     | Absolute uncertainty — no detection mechanism exists                 |

---

## 5  FMEA Worksheets

### 5.1  Battery Cell Voltage Monitoring

#### FM-01: Cell Overvoltage — Undetected

| Field                    | Value                                                      |
|--------------------------|------------------------------------------------------------|
| **Component/Function**   | SOA_CheckCellVoltage() — overvoltage monitoring            |
| **Failure Mode**         | AFE reports cell voltage below actual value (offset error), causing overvoltage to go undetected |
| **Local Effect**         | SOA check passes despite cell being above 2800 mV          |
| **System Effect**        | BMS remains in NORMAL state, charging continues             |
| **End Effect**           | Lithium plating → dendrite → internal short → thermal runaway → fire |
| **Severity (S)**         | **9** — Life-threatening with warning (other cells may trigger) |
| **Occurrence (O)**       | **3** — AFE ADC drift beyond 100 mV is very low probability with periodic calibration |
| **Current Controls**     | DIAG_ID_AFE_COMMUNICATION_INTEGRITY (PEC check), DIAG_ID_PLAUSIBILITY_PACK_VOLTAGE (cross-check AFE sum vs IVT), DIAG_ID_AFE_CONFIG (register readback) |
| **Detection (D)**        | **2** — Redundant detection via IVT pack voltage plausibility check |
| **RPN**                  | **9 × 3 × 2 = 54**                                        |
| **Action Required**      | No (RPN < 100). Current controls adequate.                 |

#### FM-02: Cell Overvoltage — Detected but Reaction Fails

| Field                    | Value                                                      |
|--------------------------|------------------------------------------------------------|
| **Component/Function**   | DIAG_Handler() → BMS_ERROR → contactor open                |
| **Failure Mode**         | DIAG correctly sets FATAL flag but contactor fails to open (welded contactor) |
| **Local Effect**         | BMS in ERROR state but current path remains closed          |
| **System Effect**        | Overvoltage condition continues despite BMS detecting it    |
| **End Effect**           | Thermal runaway — fire, potential injury                    |
| **Severity (S)**         | **10** — Hazardous without further warning (BMS has exhausted its reaction) |
| **Occurrence (O)**       | **2** — Contactor welding during normal operation is remote; requires prior high-current event |
| **Current Controls**     | DIAG_ID_STRING_PLUS_CONTACTOR_FEEDBACK (20 events, 100 ms), DIAG_ID_STRING_MINUS_CONTACTOR_FEEDBACK, DIAG_ID_PRECHARGE_CONTACTOR_FEEDBACK |
| **Detection (D)**        | **2** — Contactor feedback monitoring detects welding within 350 ms |
| **RPN**                  | **10 × 2 × 2 = 40**                                       |
| **Action Required**      | No (RPN < 100). Contactor feedback provides adequate detection. Recommendation: Add pyro-fuse as secondary disconnection device for ASIL D systems. |

#### FM-03: Cell Undervoltage — False Positive

| Field                    | Value                                                      |
|--------------------------|------------------------------------------------------------|
| **Component/Function**   | SOA_CheckCellVoltage() — undervoltage monitoring           |
| **Failure Mode**         | AFE reports cell voltage below actual value (noise, EMC, loose connector), triggering spurious undervoltage fault |
| **Local Effect**         | DIAG threshold counter increments on valid cells            |
| **System Effect**        | BMS transitions to ERROR, contactors open unnecessarily     |
| **End Effect**           | Loss of vehicle propulsion (availability impact). No safety hazard — safe state is achieved. |
| **Severity (S)**         | **5** — Significant nuisance (stranded vehicle), no safety impact |
| **Occurrence (O)**       | **4** — Low probability with 50-event threshold providing noise filtering |
| **Current Controls**     | 50-event threshold + 200 ms delay filters transient measurement errors. AFE open-wire detection identifies loose connections. |
| **Detection (D)**        | **3** — High detection of false positive via threshold filter |
| **RPN**                  | **5 × 4 × 3 = 60**                                        |
| **Action Required**      | No (RPN < 100). Threshold provides adequate filtering.     |

---

### 5.2  Temperature Monitoring

#### FM-04: Overtemperature — Sensor Open Circuit

| Field                    | Value                                                      |
|--------------------------|------------------------------------------------------------|
| **Component/Function**   | NTC temperature sensor (1 of 8)                            |
| **Failure Mode**         | NTC open circuit — AFE reads maximum ADC value, interpreted as extremely low temperature (NTC has negative coefficient) or as out-of-range value |
| **Local Effect**         | If interpreted as low temperature: undertemperature fault triggered (charge inhibit). If out-of-range: AFE MUX fault triggered. |
| **System Effect**        | BMS enters ERROR state. False positive (no actual temperature hazard). |
| **End Effect**           | Loss of propulsion. No safety impact — system fails to safe state. |
| **Severity (S)**         | **5** — Availability impact only                           |
| **Occurrence (O)**       | **5** — Moderate probability over vehicle life. NTC wire connectors subject to vibration, corrosion. |
| **Current Controls**     | DIAG_ID_AFE_MUX detects out-of-range measurements. 500-event threshold filters intermittent connections. Multiple sensors (8) provide spatial redundancy. |
| **Detection (D)**        | **2** — Multiple detection paths (MUX check, range check)  |
| **RPN**                  | **5 × 5 × 2 = 50**                                        |
| **Action Required**      | No (RPN < 100).                                            |

#### FM-05: Overtemperature — Sensor Short Circuit

| Field                    | Value                                                      |
|--------------------------|------------------------------------------------------------|
| **Component/Function**   | NTC temperature sensor (1 of 8)                            |
| **Failure Mode**         | NTC short circuit — AFE reads minimum ADC value, interpreted as extremely high temperature |
| **Local Effect**         | Overtemperature fault triggered on one sensor               |
| **System Effect**        | BMS enters ERROR state. If actual temperature is normal: false positive. |
| **End Effect**           | Loss of propulsion. No safety impact.                       |
| **Severity (S)**         | **5** — Availability impact only                           |
| **Occurrence (O)**       | **4** — Lower probability than open circuit (NTC short requires insulation failure) |
| **Current Controls**     | 500-event threshold filters transient shorts. Range check on ADC value. |
| **Detection (D)**        | **2** — Immediate detection via range check                 |
| **RPN**                  | **5 × 4 × 2 = 40**                                        |
| **Action Required**      | No (RPN < 100).                                            |

#### FM-06: Overtemperature — All Sensors Fail Low (Dangerous)

| Field                    | Value                                                      |
|--------------------------|------------------------------------------------------------|
| **Component/Function**   | All 8 NTC temperature sensors simultaneously               |
| **Failure Mode**         | Common-cause failure: all 8 sensors report lower-than-actual temperature (e.g., due to systematic placement error, thermal coupling degradation, or AFE MUX stuck on a cold reference channel) |
| **Local Effect**         | SOA temperature check passes despite actual temperature exceeding limits |
| **System Effect**        | BMS remains in NORMAL state during overtemperature condition |
| **End Effect**           | Thermal runaway — fire, injury                             |
| **Severity (S)**         | **9** — Life-threatening                                   |
| **Occurrence (O)**       | **1** — Common-cause failure of all 8 independent sensors is extremely unlikely |
| **Current Controls**     | DIAG_ID_AFE_MUX checks MUX channel switching. Spatial distribution of 8 sensors reduces common-cause. No independent temperature measurement path (only AFE-based). |
| **Detection (D)**        | **6** — Low detection capability for systematic sensor underreading. No independent temperature measurement. |
| **RPN**                  | **9 × 1 × 6 = 54**                                        |
| **Action Required**      | No (RPN < 100). Recommendation: Consider adding an independent temperature sensor on a separate ADC channel for ASIL C/D applications. |

---

### 5.3  Current Monitoring

#### FM-07: Overcurrent — Current Sensor Offset Drift

| Field                    | Value                                                      |
|--------------------------|------------------------------------------------------------|
| **Component/Function**   | IVT current sensor — current measurement                   |
| **Failure Mode**         | Current sensor develops positive offset, causing measured current to appear lower than actual. Overcurrent condition goes undetected or is detected late. |
| **Local Effect**         | SOA current check threshold effectively shifted higher      |
| **System Effect**        | Overcurrent detection delayed or missed                     |
| **End Effect**           | I²R heating → potential thermal runaway at extreme currents |
| **Severity (S)**         | **8** — Very high severity (thermal runaway possible)       |
| **Occurrence (O)**       | **2** — IVT shunt-based sensors have excellent long-term stability (<0.1% drift per year) |
| **Current Controls**     | IVT internal self-calibration. DIAG_ID_CURRENT_ON_OPEN_STRING detects non-zero current when contactors are open (reveals offset). Pack voltage plausibility provides indirect current detection via voltage drop. |
| **Detection (D)**        | **4** — Moderately high detection via open-string current check and IVT self-cal |
| **RPN**                  | **8 × 2 × 4 = 64**                                        |
| **Action Required**      | No (RPN < 100). IVT shunt sensor stability is adequate.    |

#### FM-08: Overcurrent — Current Sensor Total Loss

| Field                    | Value                                                      |
|--------------------------|------------------------------------------------------------|
| **Component/Function**   | IVT current sensor — communication                         |
| **Failure Mode**         | IVT stops transmitting CAN messages (hardware failure, CAN bus fault, power supply loss) |
| **Local Effect**         | No current measurement updates received by BMS              |
| **System Effect**        | DIAG_ID_CURRENT_SENSOR_RESPONDING triggers after 100 × 10 ms + 200 ms = 1200 ms. BMS transitions to ERROR. |
| **End Effect**           | Loss of propulsion (safe state). If a concurrent overcurrent event occurs during the 1200 ms detection window, it goes undetected. |
| **Severity (S)**         | **7** — High severity (overcurrent exposure during detection window) |
| **Occurrence (O)**       | **3** — IVT hardware failure rate is very low, but CAN bus faults are possible (connector, wiring) |
| **Current Controls**     | DIAG_ID_CURRENT_SENSOR_RESPONDING (100 events, 200 ms). DIAG_ID_CURRENT_SENSOR_V1/V2/V3_MEASUREMENT_TIMEOUT (1 event, 100 ms — faster detection for voltage channels). Cell voltage monitoring provides indirect overcurrent detection (voltage sag under load). |
| **Detection (D)**        | **2** — Very high detection via CAN timeout monitoring       |
| **RPN**                  | **7 × 3 × 2 = 42**                                        |
| **Action Required**      | No (RPN < 100).                                            |

---

### 5.4  Communication Failures

#### FM-09: AFE SPI Communication Loss

| Field                    | Value                                                      |
|--------------------------|------------------------------------------------------------|
| **Component/Function**   | AFE SPI interface — cell voltage/temperature data transport |
| **Failure Mode**         | SPI bus failure (open, short, EMC-induced errors). No valid cell data received. |
| **Local Effect**         | AFE driver reports SPI error                                |
| **System Effect**        | DIAG_ID_AFE_SPI triggers after 5 × 10 ms + 100 ms = 150 ms. FATAL → ERROR. |
| **End Effect**           | Loss of propulsion. During 150 ms detection window: BMS operates on stale cell voltage data. If a cell was trending toward overvoltage, the stale data will not reflect the continued rise. |
| **Severity (S)**         | **8** — Very high (loss of primary ASIL D sensing path)     |
| **Occurrence (O)**       | **3** — SPI is a board-level bus (short physical distance, no connectors in typical design), making failures very low |
| **Current Controls**     | DIAG_ID_AFE_SPI (5 events, 100 ms — fast detection). AFE PEC (Packet Error Code) provides per-transaction error detection. IVT pack voltage provides independent voltage measurement. |
| **Detection (D)**        | **1** — Almost certain detection via SPI error flag + PEC   |
| **RPN**                  | **8 × 3 × 1 = 24**                                        |
| **Action Required**      | No (RPN < 100).                                            |

#### FM-10: AFE Data Corruption (Undetected)

| Field                    | Value                                                      |
|--------------------------|------------------------------------------------------------|
| **Component/Function**   | AFE SPI data — cell voltage values                         |
| **Failure Mode**         | SPI data corrupted in transit but PEC check passes (PEC collision — extremely rare). Corrupted data interpreted as valid cell voltage. |
| **Local Effect**         | Incorrect cell voltage value used by SOA check              |
| **System Effect**        | Potential missed overvoltage or false undervoltage           |
| **End Effect**           | Depends on direction of corruption. If voltage appears lower: missed overvoltage → thermal runaway risk. If voltage appears higher: false undervoltage → availability loss. |
| **Severity (S)**         | **9** — Life-threatening if overvoltage missed               |
| **Occurrence (O)**       | **1** — PEC collision probability for 8-bit PEC is 1/256 per transaction. Multi-bit errors required. With CRC-based PEC, Hamming distance provides robust detection. Undetected corruption is extremely unlikely. |
| **Current Controls**     | AFE PEC (CRC-8) on every SPI transaction. DIAG_ID_AFE_COMMUNICATION_INTEGRITY. Pack voltage plausibility cross-check. |
| **Detection (D)**        | **3** — High detection via PEC + plausibility               |
| **RPN**                  | **9 × 1 × 3 = 27**                                        |
| **Action Required**      | No (RPN < 100).                                            |

#### FM-11: CAN Bus Loss

| Field                    | Value                                                      |
|--------------------------|------------------------------------------------------------|
| **Component/Function**   | CAN bus — vehicle communication                            |
| **Failure Mode**         | CAN bus failure (bus-off, wiring fault, termination resistor failure). BMS cannot send warnings or receive vehicle commands. |
| **Local Effect**         | CAN TX/RX timeout detected                                  |
| **System Effect**        | DIAG_ID_CAN_TIMING triggers after 100 × 10 ms + 200 ms = 1200 ms. FATAL → ERROR. Vehicle controller loses BMS current limits. |
| **End Effect**           | Loss of propulsion. Vehicle may request currents beyond BMS limits during the 1200 ms detection window, but cell-level SOA checks (voltage, temperature, current) remain active and provide independent protection. |
| **Severity (S)**         | **6** — Major (loss of communication, but independent protection active) |
| **Occurrence (O)**       | **4** — CAN bus faults are low probability but higher than board-level SPI (connectors, harness routing, EMC susceptibility) |
| **Current Controls**     | DIAG_ID_CAN_TIMING (100 events, 200 ms). BMS cell-level monitoring is independent of CAN bus health. |
| **Detection (D)**        | **2** — Very high detection via CAN timeout                  |
| **RPN**                  | **6 × 4 × 2 = 48**                                        |
| **Action Required**      | No (RPN < 100).                                            |

---

### 5.5  Contactor and Power Path Failures

#### FM-12: Contactor Welding — String Plus

| Field                    | Value                                                      |
|--------------------------|------------------------------------------------------------|
| **Component/Function**   | String-plus contactor                                      |
| **Failure Mode**         | Contactor contacts weld closed due to inrush current or arc erosion. BMS cannot open the positive current path. |
| **Local Effect**         | String-plus contactor remains closed when BMS commands open  |
| **System Effect**        | Safe state (contactor open) cannot be fully achieved for the positive side. String-minus or precharge contactor opening may still interrupt current if they are not also welded. |
| **End Effect**           | If only one contactor welds: remaining contactors can still interrupt current (reduced safety margin). If multiple contactors weld: complete loss of disconnection capability. |
| **Severity (S)**         | **9** — Life-threatening (loss of primary safety mechanism)  |
| **Occurrence (O)**       | **2** — Contactor welding requires high-energy arcing events. Proper precharge sequencing reduces inrush. |
| **Current Controls**     | DIAG_ID_STRING_PLUS_CONTACTOR_FEEDBACK (20 events, 100 ms). Precharge sequence limits inrush current. Three independent contactors provide N-1 redundancy for current interruption. |
| **Detection (D)**        | **2** — Very high detection via feedback GPIO comparison     |
| **RPN**                  | **9 × 2 × 2 = 36**                                        |
| **Action Required**      | No (RPN < 100). N-1 contactor redundancy is adequate.       |

#### FM-13: Contactor Stuck Open — String Minus

| Field                    | Value                                                      |
|--------------------------|------------------------------------------------------------|
| **Component/Function**   | String-minus contactor                                     |
| **Failure Mode**         | Contactor fails to close when commanded (coil failure, mechanical jam, SPS driver fault) |
| **Local Effect**         | String-minus contactor remains open. BMS cannot complete the current path. |
| **System Effect**        | BMS cannot transition from STANDBY to PRECHARGE/NORMAL. Battery pack is non-functional. |
| **End Effect**           | Loss of vehicle propulsion (availability). No safety hazard — system is in open-circuit state. |
| **Severity (S)**         | **5** — Significant nuisance (stranded vehicle)             |
| **Occurrence (O)**       | **3** — Very low probability (contactor coil failure, SPS MOSFET failure) |
| **Current Controls**     | DIAG_ID_STRING_MINUS_CONTACTOR_FEEDBACK detects mismatch. BMS state machine times out if precharge does not complete within expected duration. |
| **Detection (D)**        | **2** — Very high detection via feedback                     |
| **RPN**                  | **5 × 3 × 2 = 30**                                        |
| **Action Required**      | No (RPN < 100).                                            |

#### FM-14: Current on Open String

| Field                    | Value                                                      |
|--------------------------|------------------------------------------------------------|
| **Component/Function**   | Current measurement during STANDBY (contactors open)       |
| **Failure Mode**         | IVT detects non-zero current flow when all contactors are commanded open |
| **Local Effect**         | Indicates either: (a) welded contactor allowing current through external load, (b) current sensor offset error, or (c) external fault path bypassing contactors |
| **System Effect**        | DIAG_ID_CURRENT_ON_OPEN_STRING triggers after 10 × 10 ms + 100 ms = 200 ms. FATAL → ERROR (already in safe state if contactors are truly open). |
| **End Effect**           | If caused by welded contactor: escalation to permanent fault, service required. If sensor offset: nuisance fault. |
| **Severity (S)**         | **8** — Very high (may indicate welded contactor — loss of disconnection) |
| **Occurrence (O)**       | **2** — Remote (requires preceding high-current fault event or sensor failure) |
| **Current Controls**     | DIAG_ID_CURRENT_ON_OPEN_STRING (10 events, 100 ms). Cross-referenced with contactor feedback for root cause identification. |
| **Detection (D)**        | **1** — Almost certain (direct current measurement)          |
| **RPN**                  | **8 × 2 × 1 = 16**                                        |
| **Action Required**      | No (RPN < 100).                                            |

---

### 5.6  Safety Infrastructure Failures

#### FM-15: SBC Watchdog Failure

| Field                    | Value                                                      |
|--------------------------|------------------------------------------------------------|
| **Component/Function**   | SBC (FS8x) — watchdog supervision                         |
| **Failure Mode**         | SBC watchdog does not trigger reset on BMS software hang (SBC internal failure or watchdog window misconfiguration) |
| **Local Effect**         | BMS software hangs; no watchdog reset occurs                |
| **System Effect**        | BMS stops executing SOA checks, DIAG processing, and contactor control. Contactors remain in last commanded state (potentially closed). |
| **End Effect**           | All safety monitoring lost. Any subsequent battery fault goes undetected. |
| **Severity (S)**         | **10** — Hazardous without warning                          |
| **Occurrence (O)**       | **1** — SBC is a safety-qualified component (ASIL D). Internal watchdog failure rate is extremely low (< 1 FIT). |
| **Current Controls**     | DIAG_ID_SBC_RSTB_ERROR (1 event, 100 ms). DIAG_ID_ALERT_MODE monitors SBC alert state. SBC has independent internal monitoring. TMS570 lockstep provides secondary hang detection. |
| **Detection (D)**        | **3** — High detection via SBC self-monitoring and ALERT_MODE |
| **RPN**                  | **10 × 1 × 3 = 30**                                       |
| **Action Required**      | No (RPN < 100). SBC is designed to ASIL D safety standards. |

#### FM-16: Flash Memory Corruption

| Field                    | Value                                                      |
|--------------------------|------------------------------------------------------------|
| **Component/Function**   | TMS570 MCU — program flash memory                         |
| **Failure Mode**         | Single Event Upset (SEU) or retention failure corrupts program code. SOA threshold values, DIAG configuration, or BMS state machine logic altered. |
| **Local Effect**         | Incorrect program execution                                 |
| **System Effect**        | DIAG_ID_FLASHCHECKSUM triggers immediately (threshold=1, no delay). BMS → ERROR. If corruption affects FLASHCHECKSUM logic itself: lockstep CPU detects divergent execution. |
| **End Effect**           | Loss of propulsion (safe state). If both detection mechanisms fail: unpredictable BMS behavior. |
| **Severity (S)**         | **9** — Life-threatening (if undetected, arbitrary code execution) |
| **Occurrence (O)**       | **2** — SEU rate for automotive flash at ground level is ~1 bit/Mbit/1000 hours. TMS570 ECC provides single-bit correction. |
| **Current Controls**     | DIAG_ID_FLASHCHECKSUM (CRC over program area). TMS570 ECC on flash (SECDED — Single Error Correction, Double Error Detection). Lockstep CPU compares execution cycle-by-cycle. |
| **Detection (D)**        | **1** — Almost certain (ECC + CRC + lockstep = three independent mechanisms) |
| **RPN**                  | **9 × 2 × 1 = 18**                                        |
| **Action Required**      | No (RPN < 100). Triple detection mechanism is comprehensive. |

#### FM-17: System Monitoring — Task Overrun

| Field                    | Value                                                      |
|--------------------------|------------------------------------------------------------|
| **Component/Function**   | RTOS task scheduling — 1 ms and 10 ms tasks                |
| **Failure Mode**         | A task exceeds its execution deadline. SOA checks, DIAG processing, or contactor control delayed beyond worst-case execution time. |
| **Local Effect**         | DIAG_ID_SYSTEM_MONITORING triggers (threshold=1, no delay)  |
| **System Effect**        | Immediate FATAL → ERROR → contactors open                   |
| **End Effect**           | Loss of propulsion. If the overrun prevented a critical SOA check from executing, the brief gap is covered by the FTTI margin. |
| **Severity (S)**         | **7** — High (loss of function, safety margin reduced during overrun) |
| **Occurrence (O)**       | **2** — RTOS task timing is verified by static analysis (WCET) and tested. Overruns indicate a software defect or excessive interrupt load. |
| **Current Controls**     | DIAG_ID_SYSTEM_MONITORING (immediate detection). RTOS deadline monitoring. TMS570 RTI (Real Time Interrupt) hardware timer. |
| **Detection (D)**        | **1** — Almost certain (hardware timer + RTOS kernel check)  |
| **RPN**                  | **7 × 2 × 1 = 14**                                        |
| **Action Required**      | No (RPN < 100).                                            |

---

### 5.7  Interlock and Isolation Failures

#### FM-18: Interlock Loop — False Open Detection

| Field                    | Value                                                      |
|--------------------------|------------------------------------------------------------|
| **Component/Function**   | Interlock feedback circuit                                 |
| **Failure Mode**         | Interlock feedback signal intermittently drops due to connector vibration, EMC, or wire chafing. Loop is physically intact but electrical signal is noisy. |
| **Local Effect**         | DIAG_ID_INTERLOCK_FEEDBACK counter increments on noise spikes |
| **System Effect**        | If 10 consecutive events occur: FATAL → ERROR → contactors open. False positive shutdown. |
| **End Effect**           | Loss of propulsion. No safety hazard.                       |
| **Severity (S)**         | **5** — Significant nuisance                               |
| **Occurrence (O)**       | **5** — Moderate (interlock connectors on battery packs are subject to vibration and thermal cycling) |
| **Current Controls**     | 10-event threshold provides debounce filtering. Shielded interlock wiring reduces EMC susceptibility. |
| **Detection (D)**        | **3** — High detection of false positive via threshold filter |
| **RPN**                  | **5 × 5 × 3 = 75**                                        |
| **Action Required**      | No (RPN < 100). Monitor field return data for interlock connector reliability. |

#### FM-19: Pack Voltage Plausibility — False Failure

| Field                    | Value                                                      |
|--------------------------|------------------------------------------------------------|
| **Component/Function**   | DIAG_ID_PLAUSIBILITY_PACK_VOLTAGE — AFE sum vs IVT comparison |
| **Failure Mode**         | AFE and IVT voltage measurements drift in opposite directions due to independent calibration errors, producing a plausibility error despite both measurements being individually within specification. |
| **Local Effect**         | Plausibility check fails                                    |
| **System Effect**        | DIAG_ID_PLAUSIBILITY_PACK_VOLTAGE triggers after 10 × 10 ms + 100 ms = 200 ms. FATAL → ERROR. |
| **End Effect**           | Loss of propulsion. No safety hazard — both sensors are actually functional. |
| **Severity (S)**         | **5** — Significant nuisance                               |
| **Occurrence (O)**       | **3** — Very low probability (requires opposite drift in two independent sensors) |
| **Current Controls**     | 10-event threshold filters transient disagreements. Plausibility tolerance band accounts for measurement uncertainty. |
| **Detection (D)**        | **4** — Moderately high (root cause analysis after shutdown can identify drift direction) |
| **RPN**                  | **5 × 3 × 4 = 60**                                        |
| **Action Required**      | No (RPN < 100).                                            |

---

## 6  FMEA Summary and RPN Ranking

| FM ID  | Failure Mode                           | S  | O  | D  | RPN | Action Required |
|--------|----------------------------------------|----|----|----|-----|-----------------|
| FM-01  | Cell OV undetected (AFE offset)        | 9  | 3  | 2  | 54  | No              |
| FM-02  | Cell OV detected, contactor welded     | 10 | 2  | 2  | 40  | No              |
| FM-03  | Cell UV false positive                 | 5  | 4  | 3  | 60  | No              |
| FM-04  | NTC open circuit                       | 5  | 5  | 2  | 50  | No              |
| FM-05  | NTC short circuit                      | 5  | 4  | 2  | 40  | No              |
| FM-06  | All NTCs fail low (common cause)       | 9  | 1  | 6  | 54  | No              |
| FM-07  | Current sensor offset drift            | 8  | 2  | 4  | 64  | No              |
| FM-08  | Current sensor total loss              | 7  | 3  | 2  | 42  | No              |
| FM-09  | AFE SPI communication loss             | 8  | 3  | 1  | 24  | No              |
| FM-10  | AFE data corruption (undetected PEC)   | 9  | 1  | 3  | 27  | No              |
| FM-11  | CAN bus loss                           | 6  | 4  | 2  | 48  | No              |
| FM-12  | Contactor welding (string+)            | 9  | 2  | 2  | 36  | No              |
| FM-13  | Contactor stuck open (string-)         | 5  | 3  | 2  | 30  | No              |
| FM-14  | Current on open string                 | 8  | 2  | 1  | 16  | No              |
| FM-15  | SBC watchdog failure                   | 10 | 1  | 3  | 30  | No              |
| FM-16  | Flash memory corruption                | 9  | 2  | 1  | 18  | No              |
| FM-17  | Task overrun                           | 7  | 2  | 1  | 14  | No              |
| FM-18  | Interlock false open                   | 5  | 5  | 3  | 75  | No              |
| FM-19  | Pack voltage plausibility false fail   | 5  | 3  | 4  | 60  | No              |

**Maximum RPN: 75** (FM-18: Interlock false open). All failure modes are below the RPN action threshold of 100.

---

## 7  Recommendations

Although no failure modes exceed the RPN action threshold, the following recommendations are made for ASIL D deployments:

1. **R-01:** Add a pyro-fuse (pyrotechnic disconnect) as a secondary current interruption device independent of the contactors. This addresses FM-02 (contactor welding during overvoltage) and reduces the severity of FM-12.

2. **R-02:** Add an independent temperature sensor (not routed through the AFE MUX) on a separate MCU ADC channel. This addresses FM-06 (common-cause NTC failure through AFE MUX).

3. **R-03:** Implement IVT current plausibility cross-check using the relationship between voltage drop (V_pack - V_sum_cells) and measured current (V = I × R_total). This improves detection of FM-07 (current sensor offset drift).

4. **R-04:** Consider reducing the CURRENT_SENSOR_RESPONDING threshold from 100 to 50 events to reduce the detection window for FM-08 from 1200 ms to 700 ms.

---

## 8  References

| Ref  | Document                                                                  |
|------|---------------------------------------------------------------------------|
| [1]  | ISO 26262:2018 Part 5 — Product Development: Hardware Level               |
| [2]  | IEC 60812:2018 — Failure modes and effects analysis (FMEA and FMECA)      |
| [3]  | FOX-SAF-HARA-001 — Hazard Analysis and Risk Assessment                    |
| [4]  | FOX-SAF-TSC-001 — Technical Safety Concept                                |
| [5]  | FOX-SAF-FTTI-001 — FTTI Calculation Report                                |
| [6]  | foxBMS v1.10.0 `src/app/engine/diag/diag_cfg.c`                          |

---

## Traceability

| FM ID | Failure Mode | Hazard | Safety Requirement | DIAG ID |
|-------|-------------|--------|-------------------|---------|
| FM-001 | Cell overvoltage | HZ-001 | SSR-001 | DIAG_ID_CELLVOLTAGE_OVERVOLTAGE_MSL |
| FM-002 | Cell undervoltage | HZ-002 | SSR-002 | DIAG_ID_CELLVOLTAGE_UNDERVOLTAGE_MSL |
| FM-003 | Overcurrent discharge | HZ-004 | SSR-005 | DIAG_ID_OVERCURRENT_DISCHARGE_CELL_MSL |
| FM-004 | Overcurrent charge | HZ-005 | SSR-006 | DIAG_ID_OVERCURRENT_CHARGE_CELL_MSL |
| FM-005 | Overtemperature discharge | HZ-006 | SSR-007 | DIAG_ID_TEMP_OVERTEMPERATURE_DISCHARGE_MSL |
| FM-006 | Overtemperature charge | HZ-006 | SSR-008 | DIAG_ID_TEMP_OVERTEMPERATURE_CHARGE_MSL |
| FM-007 | Undertemperature charge | HZ-007 | SSR-009 | DIAG_ID_TEMP_UNDERTEMPERATURE_CHARGE_MSL |
| FM-008 | Sensor failure - voltage | HZ-001 | SSR-003 | DIAG_ID_AFE_CELL_VOLTAGE_MEAS_ERROR |
| FM-009 | Sensor failure - current | HZ-009 | SSR-010 | DIAG_ID_CURRENT_SENSOR_RESPONDING |
| FM-010 | Sensor failure - temperature | HZ-006 | SSR-010 | DIAG_ID_AFE_CELL_TEMPERATURE_MEAS_ERROR |
| FM-011 | CAN timeout | HZ-009 | SSR-010 | DIAG_ID_CAN_TIMING |
| FM-012 | Contactor weld | HZ-008 | SSR-004 | DIAG_ID_CONTACTOR_FEEDBACK |
| FM-013 | Contactor fail open | HZ-008 | SSR-004 | DIAG_ID_CONTACTOR_FEEDBACK |
| FM-014 | Precharge fail | HZ-008 | SSR-004 | DIAG_ID_PRECHARGE_ABORT |
| FM-015 | Interlock break | HZ-010 | SSR-010 | DIAG_ID_INTERLOCK_FEEDBACK |
| FM-016 | SBC failure | HZ-009 | SSR-010 | DIAG_ID_SBC_FIN_STATE |
| FM-017 | Insulation fault | HZ-011 | SSR-010 | DIAG_ID_INSULATION_MEASUREMENT |
| FM-018 | Cell imbalance | HZ-012 | SSR-003 | DIAG_ID_CELL_VOLTAGE_SPREAD |
| FM-019 | Deep discharge | HZ-003 | SSR-002 | DIAG_ID_DEEP_DISCHARGE_DETECTED |

---

*End of Document FOX-SAF-FMEA-001*
