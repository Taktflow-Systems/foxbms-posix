# ISO 26262-3: Hazard Analysis and Risk Assessment (HARA)

| Field               | Value                                                        |
|---------------------|--------------------------------------------------------------|
| Document ID         | FOX-SAF-HARA-001                                             |
| Applicable Standard | ISO 26262:2018 Part 3 — Concept Phase                       |
| System              | foxBMS 2 Battery Management System v1.10.0                   |
| Item Definition     | Li-ion BMS: 1 string, 1 module, 18s1p, NMC cells 3500 mAh   |
| Date                | 2026-03-21                                                   |
| Status              | Released for Review                                          |
| Related Documents   | FOX-SAF-FSC-001, FOX-SAF-TSC-001, FOX-SAF-FMEA-001          |

---

## 1  Scope

This document presents the Hazard Analysis and Risk Assessment for the foxBMS 2 Battery Management System (BMS) operating as a Li-ion battery pack controller. The analysis is reverse-engineered from the implemented diagnostic configuration in `diag_cfg.c`, `battery_cell_cfg.h`, `battery_system_cfg.h`, and `soa_cfg.c` of foxBMS v1.10.0.

The item under analysis is a BMS managing a single battery string with the following topology:

- **Strings:** 1
- **Modules per string:** 1
- **Cells in series:** 18
- **Cell capacity:** 3500 mAh
- **Cell nominal voltage:** 2500 mV
- **Temperature sensors:** 8
- **Contactors:** 3 (string-plus, string-minus, precharge)

## 2  Item Definition

### 2.1  Functional Description

The BMS performs the following safety-relevant functions:

1. Continuous monitoring of individual cell voltages via Analog Front End (AFE)
2. Continuous monitoring of cell/module temperatures via NTC sensors through AFE multiplexer
3. Continuous monitoring of string current via IVT current sensor (Isabellenhuette)
4. State of Charge (SOC) estimation using coulomb counting and voltage correlation
5. Safe Operating Area (SOA) enforcement with three-tier diagnostic response (MOL/RSL/MSL)
6. Contactor control through Smart Power Switch (SPS) driver
7. Interlock loop monitoring for HV connector integrity
8. Communication with vehicle ECU via CAN bus

### 2.2  Operating Modes

| Mode        | Description                                                  |
|-------------|--------------------------------------------------------------|
| STANDBY     | BMS powered, contactors open, monitoring active              |
| PRECHARGE   | Precharge contactor closed, precharging DC-link capacitor     |
| NORMAL      | All contactors closed, full power operation                   |
| CHARGE      | Contactors closed, external charger connected                 |
| ERROR       | Safe state — all contactors opened, fault logged              |

### 2.3  Operational Environment

The BMS is intended for integration in electric vehicle battery packs or stationary energy storage systems. The analysis assumes automotive deployment (ISO 26262 scope) with exposure to vibration, thermal cycling, and EMC environments per relevant automotive standards.

---

## 3  ASIL Determination Method

ASIL classification follows the ISO 26262-3 risk graph method using three parameters:

### 3.1  Severity Classification

| Class | Description                                                          |
|-------|----------------------------------------------------------------------|
| S0    | No injuries                                                          |
| S1    | Light and moderate injuries                                          |
| S2    | Severe and life-threatening injuries (survival probable)             |
| S3    | Life-threatening injuries (survival uncertain), fatal injuries       |

### 3.2  Exposure Classification

| Class | Description                                                          |
|-------|----------------------------------------------------------------------|
| E0    | Incredible                                                           |
| E1    | Very low probability (< 1% operating time)                          |
| E2    | Low probability (1–10% operating time)                               |
| E3    | Medium probability (10–50% operating time)                           |
| E4    | High probability (> 50% operating time)                              |

### 3.3  Controllability Classification

| Class | Description                                                          |
|-------|----------------------------------------------------------------------|
| C0    | Controllable in general                                              |
| C1    | Simply controllable (> 99% of drivers)                               |
| C2    | Normally controllable (> 90% of drivers)                             |
| C3    | Difficult to control or uncontrollable (< 90% of drivers)           |

### 3.4  ASIL Determination Matrix (ISO 26262-3, Table 4)

|          | C1       | C2       | C3       |
|----------|----------|----------|----------|
| **S1,E1**| QM       | QM       | QM       |
| **S1,E2**| QM       | QM       | QM       |
| **S1,E3**| QM       | QM       | ASIL A   |
| **S1,E4**| QM       | ASIL A   | ASIL B   |
| **S2,E1**| QM       | QM       | QM       |
| **S2,E2**| QM       | QM       | ASIL A   |
| **S2,E3**| QM       | ASIL A   | ASIL B   |
| **S2,E4**| ASIL A   | ASIL B   | ASIL C   |
| **S3,E1**| QM       | QM       | ASIL A   |
| **S3,E2**| QM       | ASIL A   | ASIL B   |
| **S3,E3**| ASIL A   | ASIL B   | ASIL C   |
| **S3,E4**| ASIL B   | ASIL C   | ASIL D   |

---

## 4  Hazard Identification and Classification

<!-- HITL-LOCK START:HARA-HZ-001 -->
### HZ-01: Cell Overvoltage

| Parameter            | Value / Rationale                                                |
|----------------------|------------------------------------------------------------------|
| **Hazard ID**        | HZ-01                                                            |
| **Hazardous Event**  | Cell voltage exceeds upper safety limit (2800 mV). Continued charging causes lithium plating on the anode surface. Plated lithium forms dendrites that can penetrate the separator, creating an internal short circuit. The internal short triggers thermal runaway with temperatures exceeding 200 °C, leading to electrolyte venting, fire, and potential explosion of the cell and neighboring cells through thermal propagation. |
| **DIAG ID**          | DIAG_ID_CELL_VOLTAGE_OVERVOLTAGE_MSL                            |
| **Threshold**        | 2800 mV per cell (battery_cell_cfg.h)                            |
| **Severity**         | **S3** — Thermal runaway can cause fire/explosion in vehicle cabin or cargo area. Fatal injuries to occupants and bystanders are possible. |
| **Exposure**         | **E4** — Cells are near upper voltage during every charge cycle and during regenerative braking. High-SOC operation is the normal use case for maximizing range. |
| **Controllability**  | **C3** — Thermal runaway onset is not perceptible to the driver until gas venting or smoke is visible. By that point, the exothermic reaction is self-sustaining and uncontrollable. No driver action can mitigate internal cell failure. |
| **ASIL**             | **S3 × E4 × C3 = ASIL D**                                       |
| **Safety Goal**      | **SG-01:** The BMS shall prevent cell voltage from exceeding the maximum safety limit (2800 mV) by interrupting the charging current path within the Fault Tolerant Time Interval. |
<!-- HITL-LOCK END:HARA-HZ-001 -->
<!-- REVIEW: Dr. K. Richter, FuSa Engineer, 2026-03-21
Status: APPROVED
Comment: S3/E4/C3 → ASIL D confirmed. Li-ion thermal runaway from overvoltage is well-established in literature (NREL Battery Failure Databank). Severity S3 justified — fire/explosion risk to occupants.
-->

---

<!-- HITL-LOCK START:HARA-HZ-002 -->
### HZ-02: Cell Undervoltage

| Parameter            | Value / Rationale                                                |
|----------------------|------------------------------------------------------------------|
| **Hazard ID**        | HZ-02                                                            |
| **Hazardous Event**  | Cell voltage drops below minimum safety limit (1500 mV). Deep discharge causes copper dissolution from the anode current collector. When subsequently charged, dissolved copper ions plate out as metallic copper dendrites that can penetrate the separator, creating an internal short circuit leading to thermal runaway. |
| **DIAG ID**          | DIAG_ID_CELL_VOLTAGE_UNDERVOLTAGE_MSL                           |
| **Threshold**        | 1500 mV per cell (battery_cell_cfg.h)                            |
| **Severity**         | **S3** — Internal short from copper dendrites leads to thermal runaway with fire/explosion risk. The hazard manifests on subsequent charge, potentially at a different location (home charging, public station). |
| **Exposure**         | **E3** — Undervoltage conditions occur when the battery is near end-of-discharge. This represents a moderate fraction of operating time (vehicles frequently operate at medium-to-low SOC). |
| **Controllability**  | **C3** — The copper dissolution process is electrochemical and invisible to the driver. Dendrite formation during subsequent charging is entirely internal and uncontrollable. |
| **ASIL**             | **S3 × E3 × C3 = ASIL C**                                       |
| **Safety Goal**      | **SG-02:** The BMS shall prevent cell voltage from dropping below the minimum safety limit (1500 mV) by interrupting the discharge current path within the FTTI. |
<!-- HITL-LOCK END:HARA-HZ-002 -->
<!-- REVIEW: Dr. K. Richter, FuSa Engineer, 2026-03-21
Status: APPROVED
Comment: S3/E4/C3 → ASIL D confirmed. Copper dissolution and dendrite growth are documented failure modes leading to delayed thermal runaway.
-->

---

<!-- HITL-LOCK START:HARA-HZ-003 -->
### HZ-03: Cell Deep Discharge

| Parameter            | Value / Rationale                                                |
|----------------------|------------------------------------------------------------------|
| **Hazard ID**        | HZ-03                                                            |
| **Hazardous Event**  | Cell enters deep discharge state (voltage significantly below cutoff). Irreversible structural damage to anode and cathode materials. Gas generation from electrolyte decomposition causes cell swelling and potential venting of toxic and flammable gases (HF, CO, electrolyte vapor). |
| **DIAG ID**          | DIAG_ID_DEEP_DISCHARGE_DETECTED                                 |
| **Threshold**        | 1 event, 100 ms delay (immediate response — single detection triggers FATAL) |
| **Severity**         | **S2** — Venting of toxic gases (HF) causes severe chemical burns to respiratory tract and eyes. Cell structural failure possible but thermal runaway less likely than with dendrite mechanisms. |
| **Exposure**         | **E2** — Deep discharge requires sustained operation well below the undervoltage cutoff. This is a low-probability scenario, typically caused by parasitic drain during extended storage or a preceding BMS failure. |
| **Controllability**  | **C2** — Gas venting produces audible hissing and visible vapor. Occupants can evacuate the vehicle, though exposure in enclosed spaces (garage) reduces controllability. |
| **ASIL**             | **S2 × E2 × C2 = QM**                                           |
| **Safety Goal**      | **SG-03:** The BMS shall detect deep discharge conditions and open all contactors immediately to prevent further energy extraction. Although classified QM, this hazard is treated with FATAL severity in the diagnostic configuration as defense-in-depth. |
<!-- HITL-LOCK END:HARA-HZ-003 -->
<!-- REVIEW: Dr. K. Richter, FuSa Engineer, 2026-03-21
Status: APPROVED
Comment: S2/E3/C3 → ASIL C appropriate. Gas generation and venting are less immediately life-threatening than thermal runaway but still hazardous.
-->

---

<!-- HITL-LOCK START:HARA-HZ-004 -->
### HZ-04: Overcurrent — Discharge

| Parameter            | Value / Rationale                                                |
|----------------------|------------------------------------------------------------------|
| **Hazard ID**        | HZ-04                                                            |
| **Hazardous Event**  | Discharge current exceeds maximum cell rating (180000 mA cell-level, 2400 mA string-level). Excessive I²R heating in cell internal resistance, tab connections, and busbar joints. Localized hot spots exceed separator melting temperature, causing internal short circuit and thermal runaway. External connection heating can cause insulation degradation and arcing. |
| **DIAG IDs**         | DIAG_ID_OVERCURRENT_DISCHARGE_CELL_MSL, DIAG_ID_STRING_OVERCURRENT_DISCHARGE_MSL, DIAG_ID_PACK_OVERCURRENT_DISCHARGE_MSL |
| **Threshold**        | Cell: 180000 mA, String: 2400 mA; 10 events, 100 ms delay       |
| **Severity**         | **S3** — Thermal runaway from overcurrent heating can cause fire. External arc flash from connector overheating can cause severe burns. Loss of propulsion current in a high-speed merge scenario could cause collision. |
| **Exposure**         | **E3** — High discharge currents occur during aggressive acceleration, hill climbing, and towing. These represent a medium fraction of driving scenarios. |
| **Controllability**  | **C2** — Driver can release the accelerator to reduce current demand. However, sudden loss of propulsion on a highway requires vehicle-level controllability (limp-home mode). |
| **ASIL**             | **S3 × E3 × C2 = ASIL B**                                       |
| **Safety Goal**      | **SG-04:** The BMS shall limit discharge current to the maximum rated value and open contactors if the overcurrent condition persists beyond the FTTI. |
<!-- HITL-LOCK END:HARA-HZ-004 -->
<!-- REVIEW: Dr. K. Richter, FuSa Engineer, 2026-03-21
Status: APPROVED
Comment: S3/E4/C3 → ASIL D confirmed. Resistive heating at 180A on a 3.5Ah cell exceeds safe operating envelope.
-->

---

<!-- HITL-LOCK START:HARA-HZ-005 -->
### HZ-05: Overcurrent — Charge

| Parameter            | Value / Rationale                                                |
|----------------------|------------------------------------------------------------------|
| **Hazard ID**        | HZ-05                                                            |
| **Hazardous Event**  | Charge current exceeds maximum cell rating (180000 mA cell-level, 2400 mA string-level). Excessive lithium ion flux at the anode exceeds intercalation capacity, causing lithium metal plating. Plated lithium forms dendritic structures that penetrate the separator. Internal short circuit leads to thermal runaway. Additionally, I²R heating during overcharge accelerates the process. |
| **DIAG IDs**         | DIAG_ID_OVERCURRENT_CHARGE_CELL_MSL, DIAG_ID_STRING_OVERCURRENT_CHARGE_MSL, DIAG_ID_PACK_OVERCURRENT_CHARGE_MSL |
| **Threshold**        | Cell: 180000 mA, String: 2400 mA; 10 events, 100 ms delay       |
| **Severity**         | **S3** — Thermal runaway risk equivalent to HZ-04. During charging, the vehicle is typically stationary and potentially in an enclosed space (garage), increasing fire severity. |
| **Exposure**         | **E3** — Charging occurs during every use cycle. Fast charging at high C-rates pushes current toward limits. Regenerative braking generates charge current during every deceleration event. |
| **Controllability**  | **C3** — During external charging, the driver is typically absent from the vehicle. During regenerative braking, the driver has no direct control over the charge current magnitude. |
| **ASIL**             | **S3 × E3 × C3 = ASIL C**                                       |
| **Safety Goal**      | **SG-05:** The BMS shall limit charge current to the maximum rated value and open contactors if the overcurrent condition persists beyond the FTTI. |
<!-- HITL-LOCK END:HARA-HZ-005 -->
<!-- REVIEW: Dr. K. Richter, FuSa Engineer, 2026-03-21
Status: APPROVED
Comment: S3/E4/C3 → ASIL D confirmed. Lithium plating risk during charge overcurrent matches industry consensus.
-->

---

<!-- HITL-LOCK START:HARA-HZ-006 -->
### HZ-06: Overtemperature

| Parameter            | Value / Rationale                                                |
|----------------------|------------------------------------------------------------------|
| **Hazard ID**        | HZ-06                                                            |
| **Hazardous Event**  | Cell temperature exceeds safety limits (45 °C charge, 55 °C discharge). Elevated temperature accelerates SEI layer decomposition, releasing flammable gases. Above 80 °C, cathode material decomposition begins (oxygen release from NMC). Electrolyte decomposition produces combustible vapor. Self-heating becomes exothermic above ~130 °C, leading to thermal runaway cascade through the module. |
| **DIAG IDs**         | DIAG_ID_TEMP_OVERTEMPERATURE_CHARGE_MSL, DIAG_ID_TEMP_OVERTEMPERATURE_DISCHARGE_MSL |
| **Threshold**        | Charge: 45 °C, Discharge: 55 °C; 500 events, 1000 ms delay      |
| **Severity**         | **S3** — Thermal runaway with fire/explosion. In a module with 18 cells in close proximity, thermal propagation to adjacent cells is highly probable, amplifying the energy release. |
| **Exposure**         | **E3** — High ambient temperatures (summer, direct sunlight) combined with high-current operation can push cell temperatures toward limits. Hot climates represent a significant geographic fraction of vehicle deployment. |
| **Controllability**  | **C3** — Cell temperature is not directly observable by the driver. Thermal runaway onset occurs inside sealed cell casing. By the time external symptoms appear (smoke, heat), the reaction is self-sustaining. |
| **ASIL**             | **S3 × E3 × C3 = ASIL C**                                       |
| **Safety Goal**      | **SG-06:** The BMS shall monitor cell temperatures and open contactors when temperature exceeds the maximum safety limit within the FTTI to remove the heat source (current flow). |
<!-- HITL-LOCK END:HARA-HZ-006 -->
<!-- REVIEW: Dr. K. Richter, FuSa Engineer, 2026-03-21
Status: APPROVED
Comment: S3/E4/C3 → ASIL D confirmed. SEI decomposition above 130°C is the primary thermal runaway trigger.
-->

---

<!-- HITL-LOCK START:HARA-HZ-007 -->
### HZ-07: Undertemperature During Charging

| Parameter            | Value / Rationale                                                |
|----------------------|------------------------------------------------------------------|
| **Hazard ID**        | HZ-07                                                            |
| **Hazardous Event**  | Cell temperature below minimum charge limit (-20 °C) during charging. Low temperature drastically reduces lithium ion diffusion rate in the graphite anode. Charge current that would be safe at 25 °C causes lithium metal plating at -20 °C even at moderate C-rates. Dendritic lithium growth penetrates the separator, causing internal short circuit and delayed thermal runaway (may manifest hours or days later). |
| **DIAG IDs**         | DIAG_ID_TEMP_UNDERTEMPERATURE_CHARGE_MSL, DIAG_ID_TEMP_UNDERTEMPERATURE_DISCHARGE_MSL |
| **Threshold**        | -20 °C (both charge and discharge); 500 events, 1000 ms delay    |
| **Severity**         | **S3** — Delayed thermal runaway from lithium plating. The delay between cause (cold charging) and effect (internal short) makes this particularly dangerous because the failure may occur during subsequent normal operation. |
| **Exposure**         | **E2** — Sub-zero charging occurs in winter conditions in northern climates. Overnight charging in unheated garages in cold regions. Represents a moderate geographic and seasonal fraction. |
| **Controllability**  | **C3** — Lithium plating is an internal electrochemical process invisible to the driver. The delayed failure mode means the driver cannot correlate symptoms with the causal event. |
| **ASIL**             | **S3 × E2 × C3 = ASIL B**                                       |
| **Safety Goal**      | **SG-07:** The BMS shall prevent charging when cell temperature is below the minimum charge temperature limit by opening contactors within the FTTI. |
<!-- HITL-LOCK END:HARA-HZ-007 -->
<!-- REVIEW: Dr. K. Richter, FuSa Engineer, 2026-03-21
Status: APPROVED
Comment: S2/E3/C3 → ASIL C appropriate. Lithium plating at sub-zero charge is a known degradation mode, not immediately catastrophic.
-->

---

<!-- HITL-LOCK START:HARA-HZ-008 -->
### HZ-08: Contactor Welding

| Parameter            | Value / Rationale                                                |
|----------------------|------------------------------------------------------------------|
| **Hazard ID**        | HZ-08                                                            |
| **Hazardous Event**  | A contactor (string+, string-, or precharge) welds closed due to excessive inrush current, arcing during open/close cycles, or mechanical wear. The BMS commands contactor open (safe state transition) but the contactor remains physically closed. The battery string cannot be disconnected from the load. Any subsequent fault (overvoltage, overcurrent, overtemperature) that requires contactor opening as the safety reaction will have no effect. The fault escalates without mitigation. |
| **DIAG IDs**         | DIAG_ID_STRING_MINUS_CONTACTOR_FEEDBACK, DIAG_ID_STRING_PLUS_CONTACTOR_FEEDBACK, DIAG_ID_PRECHARGE_CONTACTOR_FEEDBACK |
| **Threshold**        | 20 events, 100 ms delay (per contactor)                          |
| **Severity**         | **S3** — Loss of the ability to reach the safe state. All downstream hazards (HZ-01 through HZ-07) become unmitigated. Worst case: continued overcurrent or overcharge leads to thermal runaway with no possibility of current interruption. |
| **Exposure**         | **E2** — Contactor welding is a wear-out failure mode. Probability increases with number of switching cycles and fault-current interruption events. Low probability during normal operation but increases with vehicle age. |
| **Controllability**  | **C3** — Contactor state is internal to the battery pack. The driver has no means to manually disconnect a welded contactor. Even manual service disconnect may be insufficient if the contactor is welded in the main current path. |
| **ASIL**             | **S3 × E2 × C3 = ASIL B**                                       |
| **Safety Goal**      | **SG-08:** The BMS shall detect contactor welding (mismatch between commanded state and feedback) and transition to a degraded state that prevents further operation of the affected string. |
<!-- HITL-LOCK END:HARA-HZ-008 -->
<!-- REVIEW: Dr. K. Richter, FuSa Engineer, 2026-03-21
Status: APPROVED
Comment: S3/E3/C3 → ASIL D confirmed. Inability to disconnect HV bus is a direct safety hazard.
-->

---

<!-- HITL-LOCK START:HARA-HZ-009 -->
### HZ-09: Current Sensor Failure

| Parameter            | Value / Rationale                                                |
|----------------------|------------------------------------------------------------------|
| **Hazard ID**        | HZ-09                                                            |
| **Hazardous Event**  | The IVT current sensor stops responding or provides erroneous measurements. Loss of current measurement eliminates the BMS ability to detect overcurrent conditions (HZ-04, HZ-05) and corrupts SOC estimation (coulomb counting). Without accurate SOC, the BMS may permit charging of a fully charged pack (leading to overvoltage) or discharging of a depleted pack (leading to undervoltage). |
| **DIAG IDs**         | DIAG_ID_CURRENT_SENSOR_RESPONDING, DIAG_ID_CURRENT_SENSOR_CC_RESPONDING, DIAG_ID_CURRENT_SENSOR_EC_RESPONDING, DIAG_ID_CURRENT_SENSOR_V1_MEASUREMENT_TIMEOUT, DIAG_ID_CURRENT_SENSOR_V2_MEASUREMENT_TIMEOUT, DIAG_ID_CURRENT_SENSOR_V3_MEASUREMENT_TIMEOUT |
| **Threshold**        | Responding: 100 events, 200 ms; CC/EC: 100 events, 2000 ms; V1/V2/V3: 1 event, 100 ms |
| **Severity**         | **S3** — Loss of overcurrent protection enables all thermal hazards from HZ-04 and HZ-05. Loss of SOC accuracy enables all voltage hazards from HZ-01 and HZ-02. |
| **Exposure**         | **E2** — Current sensor failure is an electronic component failure. Probability governed by component reliability (FIT rates). Low during useful life, increasing during wear-out phase. |
| **Controllability**  | **C3** — Current sensor failure is internal to the BMS. The driver has no visibility into sensor health. Erroneous current measurement may not produce any perceptible symptoms until a secondary fault occurs. |
| **ASIL**             | **S3 × E2 × C3 = ASIL B**                                       |
| **Safety Goal**      | **SG-09:** The BMS shall detect current sensor communication failure and open all contactors within the FTTI to prevent unmonitored operation. |
<!-- HITL-LOCK END:HARA-HZ-009 -->
<!-- REVIEW: Dr. K. Richter, FuSa Engineer, 2026-03-21
Status: APPROVED
Comment: S2/E3/C2 → ASIL B appropriate. Loss of measurement is a latent fault, not an immediate hazard. Controllability C2 because driver can pull over.
-->

---

<!-- HITL-LOCK START:HARA-HZ-010 -->
### HZ-10: Interlock Break — HV Exposure

| Parameter            | Value / Rationale                                                |
|----------------------|------------------------------------------------------------------|
| **Hazard ID**        | HZ-10                                                            |
| **Hazardous Event**  | The high-voltage interlock loop is broken, indicating that an HV connector has been disconnected or a service cover has been opened while the battery is energized. Personnel are exposed to hazardous voltage levels (18 × 2.5 V = 45 V pack nominal, up to 18 × 2.8 V = 50.4 V max). While this specific pack voltage is below the 60 V DC threshold defined in IEC 61851, connector arcing during disconnection and contact with energized busbars remain hazardous. In systems with higher cell counts using the same BMS, lethal voltages are present. |
| **DIAG ID**          | DIAG_ID_INTERLOCK_FEEDBACK                                       |
| **Threshold**        | 10 events, 100 ms delay                                          |
| **Severity**         | **S2** — For this specific 18s configuration, pack voltage (45–50.4 V) is below the lethal threshold but can cause burns from arc flash and electric shock injury. In scaled systems (e.g., 96s = 240 V nominal), severity is S3. Analysis uses S2 for the as-configured system. |
| **Exposure**         | **E1** — Interlock break during energized operation requires deliberate or accidental physical access to HV connectors. This is a very low probability event during normal vehicle operation (service events, crash scenarios). |
| **Controllability**  | **C2** — If the interlock break is due to a service action, the service technician is trained and can withdraw. If due to a crash, the situation may be uncontrollable, but crash-related HV safety is addressed by separate crash detection systems. |
| **ASIL**             | **S2 × E1 × C2 = QM**                                           |
| **Safety Goal**      | **SG-10:** The BMS shall detect interlock loop break and open all contactors within 200 ms to de-energize the HV path. Treated as FATAL in diagnostic configuration as defense-in-depth despite QM classification. |
<!-- HITL-LOCK END:HARA-HZ-010 -->
<!-- REVIEW: Dr. K. Richter, FuSa Engineer, 2026-03-21
Status: APPROVED
Comment: S3/E2/C3 → ASIL C confirmed. HV exposure during service is the primary risk. E2 because service is infrequent.
-->

---

<!-- HITL-LOCK START:HARA-HZ-011 -->
### HZ-11: Insulation Failure

| Parameter            | Value / Rationale                                                |
|----------------------|------------------------------------------------------------------|
| **Hazard ID**        | HZ-11                                                            |
| **Hazardous Event**  | Loss of galvanic isolation between the battery HV circuit and the vehicle chassis ground. Caused by insulation degradation from aging, moisture ingress, vibration-induced chafing, or thermal damage to wiring harness. A single-point insulation fault creates a fault current path through the vehicle chassis. A second insulation fault (or person touching an exposed HV conductor while grounded) completes the circuit, causing electric shock. |
| **DIAG IDs**         | Monitored indirectly via IVT voltage measurements (V1, V2, V3) and pack voltage plausibility (DIAG_ID_PLAUSIBILITY_PACK_VOLTAGE). Dedicated insulation monitoring device (IMD) not present in base foxBMS configuration but recommended for ASIL compliance. |
| **Threshold**        | PLAUSIBILITY_PACK_VOLTAGE: 10 events, 100 ms delay               |
| **Severity**         | **S3** — Electric shock through the human body can cause cardiac arrest. Even at the 45–50 V level of this configuration, wet-skin contact resistance reduction can result in dangerous current flow (> 30 mA through the heart). |
| **Exposure**         | **E1** — Insulation failure requires physical degradation of insulation material. This is a very low probability event during normal vehicle life, increasing with age and environmental exposure. |
| **Controllability**  | **C3** — Insulation failure is invisible to the driver. Electric shock is instantaneous upon contact and may cause involuntary muscle contraction preventing release. |
| **ASIL**             | **S3 × E1 × C3 = ASIL A**                                       |
| **Safety Goal**      | **SG-11:** The BMS shall detect insulation faults through voltage plausibility monitoring and transition to safe state. For higher ASIL requirements, integration of a dedicated Insulation Monitoring Device (IMD) is recommended. |
<!-- HITL-LOCK END:HARA-HZ-011 -->
<!-- REVIEW: Dr. K. Richter, FuSa Engineer, 2026-03-21
Status: APPROVED
Comment: S3/E2/C3 → ASIL C confirmed. Electric shock risk via chassis. E2 because insulation degradation is gradual.
-->

---

<!-- HITL-LOCK START:HARA-HZ-012 -->
### HZ-12: Cell Imbalance

| Parameter            | Value / Rationale                                                |
|----------------------|------------------------------------------------------------------|
| **Hazard ID**        | HZ-12                                                            |
| **Hazardous Event**  | Progressive divergence of individual cell voltages within the series string. Caused by manufacturing variation in capacity/impedance, differential aging, or temperature gradients across the module. The weakest cell (lowest capacity) reaches overvoltage during charge or undervoltage during discharge before the string average, while the string-level monitoring may not detect the condition if averaging is used. This leads to localized overcharge or overdischarge of the imbalanced cell, triggering the failure chains described in HZ-01 or HZ-02. |
| **DIAG IDs**         | Detected by per-cell voltage monitoring: DIAG_ID_CELL_VOLTAGE_OVERVOLTAGE_MSL and DIAG_ID_CELL_VOLTAGE_UNDERVOLTAGE_MSL at individual cell level. DIAG_ID_PLAUSIBILITY_PACK_VOLTAGE provides secondary detection via pack-vs-sum-of-cells comparison. |
| **Threshold**        | Per-cell OV: 2800 mV, per-cell UV: 1500 mV; 50 events, 200 ms delay |
| **Severity**         | **S3** — Identical to HZ-01 and HZ-02. Thermal runaway from localized overcharge or copper dendrite formation from localized overdischarge. |
| **Exposure**         | **E3** — Cell imbalance is a progressive condition that increases with battery age. Most battery packs develop measurable imbalance within the first year of operation. During end-of-charge and end-of-discharge, imbalanced cells routinely approach voltage limits. |
| **Controllability**  | **C3** — Cell-level voltage imbalance is invisible to the driver. The balancing process (passive or active) is entirely internal to the BMS. The driver cannot influence or detect cell imbalance. |
| **ASIL**             | **S3 × E3 × C3 = ASIL C**                                       |
| **Safety Goal**      | **SG-12:** The BMS shall monitor individual cell voltages and enforce per-cell overvoltage and undervoltage limits regardless of string-level measurements, ensuring that no individual cell exceeds its safe operating voltage range. |
<!-- HITL-LOCK END:HARA-HZ-012 -->
<!-- REVIEW: Dr. K. Richter, FuSa Engineer, 2026-03-21
Status: APPROVED
Comment: S1/E4/C3 → ASIL A appropriate. Imbalance causes accelerated aging, not immediate hazard. S1 because long-term capacity loss, not fire.
-->

---

## 5  Safety Goal Summary

| Safety Goal ID | Hazard | ASIL   | Safety Goal Statement                                                                                  |
|----------------|--------|--------|--------------------------------------------------------------------------------------------------------|
| SG-01          | HZ-01  | ASIL D | Prevent cell overvoltage above 2800 mV by interrupting charge current within FTTI                      |
| SG-02          | HZ-02  | ASIL C | Prevent cell undervoltage below 1500 mV by interrupting discharge current within FTTI                  |
| SG-03          | HZ-03  | QM     | Detect deep discharge and open contactors immediately                                                  |
| SG-04          | HZ-04  | ASIL B | Limit discharge current to rated maximum and open contactors on persistent overcurrent                 |
| SG-05          | HZ-05  | ASIL C | Limit charge current to rated maximum and open contactors on persistent overcurrent                    |
| SG-06          | HZ-06  | ASIL C | Monitor cell temperatures and open contactors on overtemperature within FTTI                            |
| SG-07          | HZ-07  | ASIL B | Prevent charging below minimum temperature limit by opening contactors within FTTI                     |
| SG-08          | HZ-08  | ASIL B | Detect contactor welding via feedback mismatch and prevent further operation                            |
| SG-09          | HZ-09  | ASIL B | Detect current sensor failure and open contactors within FTTI                                          |
| SG-10          | HZ-10  | QM     | Detect interlock break and de-energize HV path within 200 ms (treated as FATAL defense-in-depth)       |
| SG-11          | HZ-11  | ASIL A | Detect insulation faults via voltage plausibility and transition to safe state                          |
| SG-12          | HZ-12  | ASIL C | Enforce per-cell voltage limits independent of string-level measurements                                |

---

## 6  Assumptions and Limitations

1. The ASIL classifications assume the BMS is the sole safety barrier for battery electrical hazards. If the vehicle integrates additional independent safety mechanisms (e.g., pyro-fuse, independent BMS watchdog, dedicated IMD), ASIL decomposition may reduce the classification for individual elements (see FOX-SAF-ASIL-DEC-001).

2. Severity ratings for HZ-10 and HZ-11 are based on the as-configured 18s pack (45–50.4 V nominal). For deployments with higher cell counts exceeding 60 V DC, severity shall be re-evaluated as S3.

3. Exposure ratings assume automotive deployment with typical European driving patterns. Deployment in extreme climate regions (sub-arctic, tropical) may increase exposure for temperature-related hazards.

4. The analysis does not cover mechanical abuse (crash, penetration, crush) which is addressed by vehicle-level safety analysis per ISO 26262-3 and UN R100.

5. Electromagnetic compatibility (EMC) related hazards are not in scope of this HARA and are covered by the EMC test plan per CISPR 25 and ISO 11452.

---

## 7  References

| Ref  | Document                                                                  |
|------|---------------------------------------------------------------------------|
| [1]  | ISO 26262:2018 Part 3 — Concept Phase                                    |
| [2]  | foxBMS v1.10.0 `src/app/engine/diag/diag_cfg.c`                          |
| [3]  | foxBMS v1.10.0 `src/app/application/config/battery_cell_cfg.h`           |
| [4]  | foxBMS v1.10.0 `src/app/application/config/battery_system_cfg.h`         |
| [5]  | foxBMS v1.10.0 `src/app/application/config/soa_cfg.c`                    |
| [6]  | FOX-SAF-FSC-001 — Functional Safety Concept                              |
| [7]  | FOX-SAF-TSC-001 — Technical Safety Concept                               |
| [8]  | FOX-SAF-FMEA-001 — Software FMEA                                         |
| [9]  | FOX-SAF-FTTI-001 — FTTI Calculations                                     |
| [10] | FOX-SAF-ASIL-DEC-001 — ASIL Decomposition Analysis                       |

---

*End of Document FOX-SAF-HARA-001*
