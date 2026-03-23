# SYS.4 Regression Test Strategy

| Document ID | Rev | Date | Classification |
|---|---|---|---|
| FOX-SIT-REG-001 | 1.0 | 2026-03-23 | Confidential |

## 1. Purpose

This document defines which tests must be re-run when changes are made to the foxBMS POSIX vECU. It satisfies ASPICE CL2 SYS.4-BP.2 (regression test selection) and PA 2.1 (performance management).

## 2. Change Categories and Required Regression

### 2.1 Change Impact Matrix

| Change Type | Example | Regression Scope | Est. Time |
|---|---|---|---|
| **Safety parameter change** | SOA threshold, DIAG config | Full ASIL D suite + affected THR | ~3h |
| **State machine change** | New transition, guard condition | SM + SSR + DFA + E2E | ~2h |
| **CAN message change** | New signal, encoding change | SIG (affected msg) + B2B | ~1h |
| **DIAG ID change** | New ID, threshold change | DIAG (affected ID) + THR + FTTI | ~1h |
| **Contactor logic change** | Sequence, timing | SM-CSEQ + SSR-050/051/052 | ~30min |
| **Plant model change** | New override, encoding fix | Smoke + SIG (affected signals) | ~30min |
| **Documentation only** | Comment, README | None (no code change) | 0 |

### 2.2 Minimum Regression Per Release

Every release candidate MUST pass:
1. **Smoke test** (`test_smoke.py`) — BMS starts, reaches STANDBY, CAN TX active
2. **Integration test** (`test_integration.py`) — 21 criteria, 30s run
3. **ASIL test** (`test_asil.py`) — 50+ criteria, 60s run with trip replay
4. **GAP-03 mandatory** (HIL-SIT-070) — single-cell OV plausibility test (per audit FuSa-P3-01)

### 2.3 Full Regression

Run before major releases or after safety-critical changes:
- All ~1,272 test catalog entries via `test_catalog_runner.py --summary`
- Fault injection suite (`test_fault_injection.py`)
- 1-hour endurance soak (END-SOAK-001)

## 3. Test Suite Tiers

| Tier | Name | Tests | Runtime | When |
|---|---|---|---|---|
| **T0** | Smoke | ~10 | 30s | Every commit |
| **T1** | Fast integration | ~80 | 5min | Every PR |
| **T2** | Full integration + ASIL | ~200 | 30min | Daily CI |
| **T3** | Full catalog | ~1,272 | ~3h | Release candidate |
| **T4** | Full + endurance | ~1,280 | ~4h | Major release |

## 4. Regression Trigger Rules

1. If a DIAG threshold changes → re-run all DIAG-xxx and THR-xxx tests for that parameter
2. If a CAN signal encoding changes → re-run SIG-TX/RX tests for that message + B2B
3. If the state machine changes → re-run SM-xxx + SSR-020 through SSR-024
4. If any file in `src/app/task/` changes → re-run E2E-xxx + timing tests
5. If `plant_model.py` changes → re-run smoke + affected signal tests
6. If `sil_layer.c` changes → full T3 regression (SIL override paths affected)

## 5. Traceability

This document satisfies:
- **ASPICE CL2 SYS.4-BP.2**: Regression test strategy documented
- **ASPICE CL2 PA 2.1**: Test activities planned and managed
- **ISO 26262-4 §8.4.2**: Regression test method defined
