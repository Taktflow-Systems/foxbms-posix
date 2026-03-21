# ASPICE Work Product Index

| Document ID | Rev | Date |
|---|---|---|
| WP-INDEX-001 | 1.0 | 2026-03-21 |

## Revision History

| Rev | Date | Author | Description |
|---|---|---|---|
| 1.0 | 2026-03-21 | An Dao | Initial release |

## 1. Purpose

This document provides a master index of all ASPICE v3.1 and ISO 26262 work products
for the foxBMS 2 POSIX port project. It maps each deliverable to its governing ASPICE
process area and the corresponding ISO 26262 part, enabling auditors and reviewers to
locate any artifact by process context.

## 2. Scope

The index covers all work products produced for the software-in-the-loop (SIL)
adaptation of foxBMS 2 v1.10.0, compiled for x86-64 under GCC 13, with POSIX HAL
stubs replacing TMS570 hardware.

## 3. References

- Automotive SPICE v3.1 Process Assessment Model, VDA, 2017
- ISO 26262:2018, Road vehicles -- Functional safety, Parts 1-12
- foxBMS 2 v1.10.0, Fraunhofer IISB

## 4. Document Map

### 4.1 ASPICE System Engineering (SYS)

| ID | Title | File | ASPICE Area | ISO 26262 Part |
|---|---|---|---|---|
| SYS.2-001 | System Requirements Specification | [SYS.2-system-requirements.md](SYS.2-system-requirements.md) | SYS.2 | Part 3 -- System-level requirements |
| SYS.3-001 | System Architecture Description | [SYS.3-system-architecture.md](SYS.3-system-architecture.md) | SYS.3 | Part 4 -- System design |

### 4.2 ASPICE Software Engineering (SWE)

| ID | Title | File | ASPICE Area | ISO 26262 Part |
|---|---|---|---|---|
| SWE.1-001 | Software Requirements Specification | [SWE.1-software-requirements.md](SWE.1-software-requirements.md) | SWE.1 | Part 6 -- Software requirements |
| SWE.2-001 | Software Architecture Description | [SWE.2-software-architecture.md](SWE.2-software-architecture.md) | SWE.2 | Part 6 -- Software architecture |
| SWE.3-001 | Software Detailed Design | [SWE.3-software-detailed-design.md](SWE.3-software-detailed-design.md) | SWE.3 | Part 6 -- Software unit design |
| SWE.4-001 | Unit Test Specification | [SWE.4-unit-test-spec.md](SWE.4-unit-test-spec.md) | SWE.4 | Part 6 -- Software unit verification |
| SWE.5-001 | Integration Test Specification | [SWE.5-integration-test-spec.md](SWE.5-integration-test-spec.md) | SWE.5 | Part 6 -- Software integration verification |
| SWE.6-001 | Qualification Test Specification | [SWE.6-qualification-test-spec.md](SWE.6-qualification-test-spec.md) | SWE.6 | Part 6 -- Software qualification |

### 4.3 ISO 26262 Specific Work Products

| ID | Title | File | ISO 26262 Part | ASPICE Mapping |
|---|---|---|---|---|
| ISO-HSI-001 | Hardware-Software Interface Specification | [ISO26262-part5-hardware-software-interface.md](ISO26262-part5-hardware-software-interface.md) | Part 5, Clause 7 | SYS.3, SWE.2 |
| ISO-SSR-001 | Software Safety Requirements | [ISO26262-part6-safety-requirements.md](ISO26262-part6-safety-requirements.md) | Part 6, Clause 6 | SWE.1 (safety subset) |
| ISO-TRC-001 | Bidirectional Traceability Matrix | [ISO26262-part8-traceability.md](ISO26262-part8-traceability.md) | Part 8, Clause 6 | All SWE/SYS areas |

### 4.4 ISO 26262 Safety Analysis Work Products

| ID | Title | File | ISO 26262 Part | ASPICE Mapping |
|---|---|---|---|---|
| FOX-SAF-HARA-001 | Hazard Analysis and Risk Assessment | [ISO26262-part3-HARA.md](ISO26262-part3-HARA.md) | Part 3, Clause 7 | SYS.2 (safety input) |
| FOX-SAF-FSC-001 | Functional Safety Concept | [ISO26262-part4-FSC.md](ISO26262-part4-FSC.md) | Part 4, Clause 6 | SYS.2, SYS.3 |
| FOX-SAF-TSC-001 | Technical Safety Concept | [ISO26262-part4-TSC.md](ISO26262-part4-TSC.md) | Part 4, Clause 7 | SYS.3, SWE.2 |
| FOX-SAF-FMEA-001 | Software FMEA | [ISO26262-part5-FMEA.md](ISO26262-part5-FMEA.md) | Part 5, Clause 7 | SWE.2, SWE.3 |
| FOX-SAF-FTTI-001 | FTTI Calculation Report | [ISO26262-part6-FTTI-calculations.md](ISO26262-part6-FTTI-calculations.md) | Part 6, Clause 7 | SWE.3 (timing) |
| FOX-SAF-ASIL-DEC-001 | ASIL Decomposition Analysis | [ISO26262-part9-ASIL-decomposition.md](ISO26262-part9-ASIL-decomposition.md) | Part 9, Clause 5 | SYS.3, SWE.2 |

## 5. Completeness Status

| Process Area | Base Practices Addressed | Status |
|---|---|---|
| SYS.2 | BP1-BP6 | Complete |
| SYS.3 | BP1-BP5 | Complete |
| SWE.1 | BP1-BP7 | Complete |
| SWE.2 | BP1-BP6 | Complete |
| SWE.3 | BP1-BP5 | Complete |
| SWE.4 | BP1-BP4 | Complete |
| SWE.5 | BP1-BP4 | Complete |
| SWE.6 | BP1-BP4 | Complete |
| ISO 26262 Part 5 HSI | Clause 7 | Complete |
| ISO 26262 Part 6 Safety | Clauses 6-10 | Complete |
| ISO 26262 Part 8 Traceability | Clause 6 | Complete |
| ISO 26262 Part 3 HARA | Clause 7 | Complete |
| ISO 26262 Part 4 FSC | Clause 6 | Complete |
| ISO 26262 Part 4 TSC | Clause 7 | Complete |
| ISO 26262 Part 5 FMEA | Clause 7 | Complete |
| ISO 26262 Part 6 FTTI | Clause 7 | Complete |
| ISO 26262 Part 9 ASIL Decomposition | Clause 5 | Complete |

## 6. Cross-Reference to ASPICE Generic Practices

Each document in this index supports the following ASPICE generic practices at
Capability Level 2:

- **GP 2.1.1** -- Identification of work products: This index provides unique IDs.
- **GP 2.1.6** -- Resources allocated: Each document names its author and review authority.
- **GP 2.2.1** -- Quality criteria defined: Each document includes acceptance criteria.
- **GP 2.2.4** -- Traceability maintained: ISO-TRC-001 provides full bidirectional trace.

---
*End of Document*
