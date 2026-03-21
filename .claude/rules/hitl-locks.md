# HITL Lock Policy — foxbms-posix

## Purpose

HITL (Human-In-The-Loop) locks mark safety-critical content that has been reviewed and verified by a human engineer. AI assistants (including Claude) MUST NOT modify content between HITL-LOCK markers without explicit human approval.

## Lock Format

- **Markdown files**: `<!-- HITL-LOCK START:<id> -->` ... `<!-- HITL-LOCK END:<id> -->`
- **C/H source files**: `// HITL-LOCK START:<id>` ... `// HITL-LOCK END:<id>`
- **Python files**: `# HITL-LOCK START:<id>` ... `# HITL-LOCK END:<id>`

## Rules

1. **DO NOT modify** any content between HITL-LOCK START and HITL-LOCK END markers.
2. **DO NOT move, rename, or delete** HITL-LOCK markers.
3. **DO NOT add new content** inside a locked region.
4. If a task requires changing locked content, **stop and ask the human** for approval. Explain what needs to change and why.
5. You MAY add new content **outside** locked regions in the same file.
6. You MAY reference locked content (read it, quote it) without modification.

## Locked Categories in foxbms-posix

| ID Pattern | File(s) | What Is Locked |
|---|---|---|
| `HARA-HZ-001` .. `HARA-HZ-012` | ISO26262-part3-HARA.md | Hazard entries with S/E/C ratings and ASIL determinations |
| `SAFETY-GOALS` | ISO26262-part6-safety-requirements.md | Safety goals table (SG-001 through SG-005) |
| `SSR-FAULT-DETECT` | ISO26262-part6-safety-requirements.md | Fault detection requirements (SSR-001 through SSR-010) |
| `SSR-FAULT-REACT` | ISO26262-part6-safety-requirements.md | Fault reaction requirements (SSR-020 through SSR-024) |
| `SSR-DIAG-COV` | ISO26262-part6-safety-requirements.md | Diagnostic coverage requirements (SSR-030 through SSR-033) |
| `SSR-COMM-SAFETY` | ISO26262-part6-safety-requirements.md | Communication safety requirements (SSR-040 through SSR-042) |
| `SSR-CONTACTOR` | ISO26262-part6-safety-requirements.md | Contactor safety requirements (SSR-050 through SSR-052) |
| `FTTI-SUMMARY` | ISO26262-part6-FTTI-calculations.md | Summary table with all 34 FTTI verdicts |
| `FTTI-CONCLUSION` | ISO26262-part6-FTTI-calculations.md | FTTI adequacy conclusion |
| `GAP-ACCEPT-GA02` | gap-analysis.md | GA-02 acceptance rationale |
| `GAP-ACCEPT-GA08` | gap-analysis.md | GA-08 acceptance rationale |
| `GAP-ACCEPT-GA17` | gap-analysis.md | GA-17 acceptance rationale |
| `STATUS-DISCOVERIES` | STATUS.md | Key discoveries from debugging (6 findings) |
| `STATUS-FIXES` | STATUS.md | Fixes applied table (14 fixes) |
| `POSIX-FAS-ASSERT` | posix_overrides.h | FAS_ASSERT_LEVEL override |
| `POSIX-HIGHEST-PRIO` | posix_overrides.h | portGET_HIGHEST_PRIORITY macro |
| `HAL-SBC-STATE` | hal_stubs_posix.c | SBC_STATEMACHINE_RUNNING value and SBC stubs |
| `HAL-EARLY-INIT` | hal_stubs_posix.c | posix_early_init constructor (SocketCAN setup) |
| `HAL-CAN-INIT` | hal_stubs_posix.c | canInit function (SocketCAN setup) |
| `MAIN-LOOP-TIMING` | foxbms_posix_main.c | 1ms/10ms/100ms cooperative scheduler if-blocks |
| `PLANT-BE-TABLE` | plant_model.py | CAN_BIG_ENDIAN_TABLE (verified by roundtrip test) |
| `PLANT-DECAN-VALID` | plant_model.py | DECAN_DATA_IS_VALID constant |

## Rationale

These sections contain:
- ISO 26262 ASIL-rated safety determinations reviewed by a functional safety engineer
- FTTI calculations with ADEQUATE verdicts based on physical process time analysis
- Debugged initialization sequences that took significant effort to get correct
- Timing structures whose modification breaks the cooperative scheduler
- CAN encoding tables verified by roundtrip testing
- Accepted gap rationale that represents deliberate engineering decisions

Modifying any of these without human review could introduce safety violations or break the POSIX vECU.
