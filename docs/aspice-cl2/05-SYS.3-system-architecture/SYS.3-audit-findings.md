# SYS.3 System Architecture — Audit Findings Register

| Audit Date | 2026-03-23 |
|---|---|
| Auditors | ASPICE SYS.3 Researcher (web research) + Fault Finder (document analysis) |
| Document | SYS.3-system-architecture.md Rev 1.1 |
| Status | **31 findings** — 8 errors, 5 inconsistencies, 8 missing, 6 style, 4 dangling refs |

---

## Category 1: Factual Errors

| ID | Severity | Finding | Location | Action |
|---|---|---|---|---|
| E-01 | LOW | "DECAN decode" is a misnomer — should be "AFE decode" or "LTC6813 decode" | §11.5.1 signal path | Clarify terminology |
| E-02 | **HIGH** | MCU ball D8 dual-assigned to CAN1_EN AND SPS_CS. D8 = N2HET2[01] = SPS_CS (pin 1). CAN1_EN is HET2 pin 18 on a different ball. | §11.1.1 CAN table line "CAN1_EN" | Fix CAN1_EN ball assignment |
| E-03 | MEDIUM | CAN1_EN listed as "N2HET2_01" in §11.1.1 but Section 12 says "CAN1 EN pin 18". N2HET2_01 is channel 01 (pin 1), not pin 18. | §11.1.1 vs §12 | Fix to match data-flow-checker: CAN1_EN = hetREG2 pin 18 |
| E-04 | LOW | CAN1_STB: SYS.3 says N2HET2_19, TSR-DA says "hetREG2 pin 23". HET channel index vs pin number convention inconsistent. | §11.1.1 vs TSR-DA | Standardize to HET channel index |
| E-05 | **HIGH** | MCU ball A13 dual-assigned to INTERLOCK_L AND IMD_OK. A13 = N2HET1[17] = interlock IL_STATE. IMD_OK is on a different HET channel/ball. | §11.1.1 IMD table | Fix IMD_OK ball assignment |
| E-06 | MEDIUM | LTC6813 ADC error stated as "±1.5mV" in one signal path but "±2.2mV" everywhere else. ±2.2mV is correct (7kHz, 25°C). | §11.5.1 signal path (if still present) | Grep and fix all remaining ±1.5mV |
| E-07 | LOW | Section 11.2 header says "Master Board Connectors (v1.2.2)" but source schematic file referenced is v1.2.3. | §11.2 header vs §11 source table | Standardize version reference |
| E-08 | MEDIUM | Gotcha L-018/L-027 says "spread > 0.4V" but code-verified value is `PL_CELL_VOLTAGE_SPREAD_TOLERANCE_mV = 300` (0.3V, 300 mV). | §11.8 gotcha #4 | Fix to 300 mV / 0.3V |

---

## Category 2: Internal Inconsistencies

| ID | Severity | Finding | Location | Action |
|---|---|---|---|---|
| I-01 | **CRITICAL** | TSR numbering mismatch: TSC traceability tables (HITL-LOCKED) use TSR-001="Voltage monitoring" but TSR-DA/SYS.3 use TSR-01="Cell Overvoltage". Completely different decompositions. Breaks safety traceability. | TSC §Traceability vs TSR-DA §3 | Cannot modify HITL-locked. Document discrepancy. |
| I-03 | MEDIUM | TSC says contactor feedback is "<1ms, direct GPIO" but actual path is I2C PEX (~5ms). TSC has wrong hardware path. | TSC §3.8.2 vs SYS.3 §11.2.4 | Cannot modify HITL-locked TSC. Note in TSR-DA. |
| I-04 | LOW | SPS connector numbering "J2004-J2010: Channels 3-7" implies contiguous range but J2005/J2009 are not SPS. | §11.2.4 | Clarify: list individual connectors |
| I-05 | MEDIUM | Temperature sensor MUX group assignment: SYS.3 says T-SENSOR_0-3 in group 0 (4 sensors), TSR-DA says T-SENSOR_0-4 in group 0 (5 sensors). Conflict on T-SENSOR_4. | §11.3.2 vs TSR-DA §3.6 | Verify against LTC6813 driver code |

---

## Category 3: Missing Information

| ID | Severity | Finding | Location | Action |
|---|---|---|---|---|
| M-01 | MEDIUM | SBC SPI chip select pin not documented. SPS_CS is hetREG2 pin 1, but SBC_CS is undefined. | §11.1.1 SPI2 table | Add SBC CS pin from spi_cfg.c |
| M-02 | LOW | GIO register (gioREG 0xFFF7BC00) not in Section 12 cross-reference table. | §12 | Add gioREG entry |
| M-03 | LOW | ADC channels (ch2-5 for interlock) not mapped to physical ADC input pins on J9002. | §11.1.1 Interlock | Add ADC pin mapping if available |
| M-04 | MEDIUM | J9002 (120-pin extension) has no complete pinout table. Only scattered pin references (pin 79, 80, 58-65). | §11.2 | Add at least safety-relevant J9002 pins |
| M-05 | LOW | SPI5 usage not documented beyond "spare". | §12 | Add note: unused in default config |
| M-06 | LOW | SBC communication details missing (register addresses, watchdog window timing). | §11.2.4 | Add basic SBC specs |
| M-07 | LOW | No probe points for RS485, FRAM, Ethernet. | §11.6 | Add note: not in safety path |
| M-08 | MEDIUM | No CAN signal-level encoding (byte position, bit offset, scaling, unit). Only message-level. | §9 | Add DBC reference or signal table for safety messages |

---

## Category 4: ASPICE SYS.3 Structural Gaps

| ID | Severity | Finding | ASPICE BP | Action |
|---|---|---|---|---|
| A-01 | **BLOCKING** | No formal system element decomposition (SE-xxx IDs). Document mixes system architecture with software architecture. | BP.1 | Add system element table |
| A-02 | **BLOCKING** | No requirements allocation matrix. Cannot verify SYS-REQ-xxx → SE-xxx coverage. | BP.2 | Add allocation matrix |
| A-03 | **BLOCKING** | No alternatives analysis. Most frequently downgraded BP in SYS.3 assessments. | BP.5 | Add 1-page alternatives section |
| A-04 | MAJOR | No BMS state machine diagram. States referenced (STANDBY, PRECHARGE, NORMAL, ERROR) but not formally diagrammed. | BP.4 | Add state machine (text or HTML) |
| A-05 | MAJOR | No sequence diagrams (startup, fault reaction, shutdown). | BP.4 | Add at least fault reaction sequence |
| A-06 | MAJOR | No timing/scheduling analysis (WCET, CPU load, deadline guarantees). | BP.4 | Add task timing table |
| A-07 | MEDIUM | Sections 5-10 are SWE.2 content (software decomposition), not SYS.3 (system decomposition). Mixed abstraction levels. | BP.1 | Label sections or split documents |
| A-08 | MEDIUM | No formal interface definitions between software layers (API signatures, data structures). | BP.3 | Add or reference SWE.2 document |
| A-09 | LOW | "AI-simulated" reviewer in revision history — assessor will reject as CL2 review evidence. | GP 2.2.1 | Note: requires real engineering review |
| A-10 | LOW | Open items (IR155 TODO) in a "released" document. Should reference issue tracker. | GP 2.1.1 | Move to issue tracker, reference ID |

---

## Category 5: Style / Formatting

| ID | Finding | Action |
|---|---|---|
| S-01 | Broken markdown table in Section 12 — bus sharing note paragraph splits the table. | Move note outside table |
| S-02 | Register address format inconsistent: short form `(DC00)` vs full `(0xFFF7DC00)`. | Standardize |
| S-03 | Very deep section nesting (§11.2.1 through §11.2.10). | Consider flattening |
| S-04 | Header says Rev 1.0 but revision history includes Rev 1.1. | Update header |
| S-05 | TSR numbering format inconsistent: TSR-01 vs TSR-1 vs TSR-001. | Standardize to TSR-01 |
| S-06 | Temperature sensor notation "GPIO5+1-3 (MUX grp 1)" hard to parse. | Rewrite clearly |

---

## Category 6: Dangling References

| ID | Finding | Action |
|---|---|---|
| D-01 | References `foxbms-posix/docs/lessons-learned/embedded/foxbms-integration.md` — may not exist. | Verify |
| D-02 | References `docs/lessons-learned/embedded/foxbms-hil-signal-path-analysis.md` — created by agent. | Verify |
| D-03 | References `SYS.3-ecu-pin-mapping.html` and `SYS.3-wiring-diagram.html` as sibling files. | Verify exist |
| D-04 | Pinout CSV paths reference local machine `D:/workspace_ccstheia/foxbms-2/`. Not portable. | Note as local-only paths |

---

## Category 7: Cross-Document Inconsistencies

| ID | Severity | Finding | Action |
|---|---|---|---|
| X-01 | MEDIUM | TSC says contactor feedback is "direct GPIO <1ms" but SYS.3/TSR-DA say "I2C PEX ~5ms". TSC is wrong but HITL-locked. | Document discrepancy |
| X-02 | **CRITICAL** | TSR numbering completely mismatched between TSC traceability (HITL-locked) and TSR-DA. TSC TSR-001="Voltage monitoring" vs TSR-DA TSR-01="Cell Overvoltage". | Document mapping table |
| X-03 | LOW | TSR-DA references FM-18 for both "cell imbalance" (TSR-01) and "interlock noise" (TSR-13). FM-18 is overloaded. | Fix FM reference in TSR-DA |
| X-04 | MEDIUM | CAN1_STB pin: SYS.3 says N2HET2_19, TSR-DA says hetREG2 pin 23. Different numbering conventions. | Standardize |

---

## Priority Summary

| Priority | Count | Items |
|---|---|---|
| **Fix immediately** (factual errors) | 4 | E-02, E-05, E-06, E-08 |
| **Fix before assessment** (ASPICE blocking) | 3 | A-01, A-02, A-03 |
| **Fix soon** (structural/consistency) | 8 | E-03, I-05, M-01, M-04, M-08, A-04, A-05, S-01/S-04 |
| **Fix eventually** (polish) | 16 | Everything else |
| **Cannot fix** (HITL-locked) | 2 | I-01/X-02, I-03/X-01 |

---

*Generated 2026-03-23 by ASPICE SYS.3 Researcher + Fault Finder agents.*
