# 30-Day Delivery Plan v2 — ML Validation Platform for BMS Companies

**Date**: 2026-03-27 (end of day)
**Customer**: BMS companies selling BMS hardware + firmware to pack integrators / OEMs
**Goal**: In 30 days, we can walk into a BMS company and say "give us your DBC + one CAN log, we'll validate your SOC across all your customer pack variants"
**Total**: 160h (20 working days × 8h)

---

## Updated Starting State (after today's session)

| Asset | Status | Verified |
|---|---|---|
| ml_sidecar.py | **LIVE on VPS** with 3 ONNX models + anomaly | ML_SOC=70.2%, anomaly=0.36, imbalance=14mV |
| plant_model.py | **LIVE** with thermal model + NMC OCV S-curve | Temp rising 25.0→25.4°C under discharge |
| web dashboard | **LIVE** with ML Intelligence panel (6 gauges) | sil.taktflow-systems.com/bms/ |
| soc_lstm.onnx | **Deployed to VPS**, producing predictions | Window=60, features=5, per-cell normalized |
| thermal_cnn.onnx | **Deployed**, reads 4 features | Risk=0.000 on normal (correct) |
| soh_transformer.onnx | **Deployed**, expects 12 features | Producing predictions (accuracy unknown) |
| anomaly_model.pkl | Trained on **synthetic** data | Score=0.36 (needs retraining on real CAN) |
| soc_norm_mean/std.npy | **Estimated** from BMW i3 specs, not actual data | ML_SOC=70% vs BMS=50% (domain gap) |
| pipeline/ directory | **NOT built** | No run_audit.py, no reports |
| BMW i3 raw data | **NOT downloaded** | Need Kaggle download |
| FOBSS validation | **NOT done** | Need KIT Radar download |

**What's DONE**: Live demo works end-to-end. All ONNX models producing predictions. Dashboard shows ML gauges. CAN 0x700-0x705 publishing.

**What's NOT DONE**: Offline pipeline (run_audit.py), report generation, bench sidecar, FOBSS validation, proper normalization, demo packaging.

---

## Day-by-Day Plan (160 hours)

### Day 1 (8h): Retrain anomaly on real data + fix normalization

Already-done work from today's session means Day 1 of the original plan is mostly complete. Start with what's still broken.

| Hour | Task | Detail | Output | Sells after? |
|---|---|---|---|---|
| 1 | Download BMW i3 data | Run `python scripts/bms/download_datasets.py` or manual Kaggle download. Need 72 trip CSVs to `data/bms-raw/bmw-i3-driving/`. ~37MB total. | 72 CSV files | No |
| 2 | Compute real normalization stats | Run `python scripts/bms/prepare_soc_dataset.py`. This loads all 72 trips, creates sliding windows, fits StandardScaler, saves `soc_norm_mean.npy` + `soc_norm_std.npy` with exact training statistics. | Correct .npy files (not estimates) | No |
| 3 | Deploy real norm stats to VPS | `scp soc_norm_mean.npy soc_norm_std.npy root@VPS:/opt/foxbms-sil/models/bms/`. Restart sidecar. Wait 60s for SOC LSTM warmup. Check: ML_SOC should be closer to BMS_SOC (gap should shrink from 20% to <10%). | ML_SOC closer to truth | No |
| 4-5 | Capture + retrain anomaly baseline | SSH VPS: `timeout 1800 candump vcan1 -L > baseline.log`. Write `train_from_candump.py` (80 lines): parse candump → extract features per second → train IsolationForest on real foxBMS CAN. Deploy retrained model. Anomaly score should drop from 0.36 → <0.10. | Retrained anomaly model | No |
| 6-7 | Validate anomaly on fault injection | Inject OV, OT, OC via dashboard. Record: normal_score, fault_score, separation for each. Write validation table. Take screenshots. This is demo-quality proof: "inject fault → score spikes → clear → score drops." | Anomaly validation table + screenshots | Yes: live demo now shows real anomaly detection |
| 8 | Update VPS systemd services | Create systemd services for plant, vecu, sidecar, web server. Enable auto-restart. Test: `reboot` → all services come back. | VPS survives reboot | No |

**After Day 1**: Live demo is polished. Anomaly detection is real (not synthetic). SOC LSTM uses proper normalization. VPS auto-restarts.

---

### Day 2-3 (16h): FOBSS validation — get citable accuracy numbers

| Hour | Task | Detail | Output |
|---|---|---|---|
| D2.1-2 | Download FOBSS dataset | Manual download from `radar.kit.edu`. 128MB TAR. Extract. Explore format: what columns, what sample rate, how many cells (44). Write `explore_fobss.py` (50 lines). | FOBSS data on disk, format documented |
| D2.3-4 | Create FOBSS config | Map FOBSS signal names to model features. Create `customers/fobss/pack_config.json`. FOBSS is real foxBMS data → near-zero domain gap for validation. | pack_config.json for FOBSS |
| D2.5-6 | Run SOC LSTM on FOBSS | Write `validate_fobss.py` (~100 lines). Load FOBSS features → normalize → sliding window → soc_lstm.onnx inference. Compare with FOBSS ground truth SOC. Compute RMSE. **This is the decision gate**: <3% = strong claim. 3-5% = usable. >5% = retrain. | SOC LSTM RMSE on foxBMS hardware data |
| D2.7-8 | Run Thermal CNN + Imbalance on FOBSS | Thermal: score all windows, count false positives on normal data. Imbalance: compute cell spread, compare with CNN if available. Document results. | Thermal FPR + Imbalance accuracy |
| D3.1-3 | Write validation-results.md | Formal document: SOC RMSE, Thermal FPR, Imbalance accuracy, all on FOBSS foxBMS data. Include: training data source, validation data source, caveats. **This is what we cite to BMS customers.** | Citable validation document |
| D3.4-5 | If SOC RMSE > 5%: retrain | Fine-tune SOC LSTM last 2 layers on FOBSS data (transfer learning). Re-export to ONNX. Re-validate. Literature says <3% after fine-tuning with 200 cycles of target data. | Improved ONNX model (if needed) |
| D3.6-8 | Test with BMW i3 as "customer pack" | Create BMW i3 config (96S/94Ah). Run pipeline manually: load trip CSV → extract features → infer → compare ML SOC vs CSV ground truth SOC. This simulates "BMS company gives us CAN log, we validate their SOC." Record RMSE. Should match published 1.83%. | BMW i3 RMSE confirmed |

**After Day 3**: We have citable numbers: "SOC LSTM: X.X% RMSE on foxBMS monitoring data from KIT Radar." This is the credibility we need for BMS customer conversations.

---

### Day 4-6 (24h): Build offline pipeline (run_audit.py)

This is the core deliverable — the tool that processes customer CAN logs.

| Hour | Task | Detail | Output |
|---|---|---|---|
| D4.1-2 | Create pipeline/ directory + decode_can.py | CAN log decoder using cantools. Support: .blf (Vector BLF), .asc (ASC), .csv (generic), .log (candump). Output: time-aligned CSV with all decoded signals. `pip install cantools python-can`. ~80 lines. | decode_can.py working on candump log |
| D4.3-4 | Test decode on multiple formats | Test with: foxBMS candump log, BMW i3 CSV. Verify signal extraction. Handle edge cases: missing signals, different delimiters, encoding issues. | Decoder handles 3+ formats |
| D4.5-6 | Write extract_features.py | Config-driven feature extraction. Input: decoded CSV + pack_config.json. Output: numpy array (N, 5). Key: per-cell normalization `V_cell = pack_V / cells_in_series`. This is what makes it work across 18S, 96S, 108S, 216S packs. ~60 lines. | extract_features.py working |
| D4.7-8 | Write ml_inference.py | ONNX model wrapper. Load available models from directory. Run sliding-window inference on feature array. Return dict with per-model predictions. Handle missing models gracefully. ~100 lines. | ml_inference.py working |
| D5.1-2 | Write run_audit.py orchestrator | Single command: `python run_audit.py --config pack.json --log test.blf --models models/ --output reports/`. Stages: decode → extract → infer → save predictions.csv. Print progress. ~80 lines. | run_audit.py end-to-end |
| D5.3-4 | Test: foxBMS SIL data through pipeline | Dump 60s of VPS CAN → run through pipeline offline → verify predictions match live sidecar within 1%. This cross-validates offline vs real-time. | Offline matches live |
| D5.5-6 | Test: BMW i3 data through pipeline | `python run_audit.py --config customers/bmw-i3/pack_config.json --log trip_001.csv --output reports/bmw/`. SOC predictions should track ground truth. RMSE should be ~1.83%. | BMW i3 audit successful |
| D5.7-8 | Create pack_config template + 3 sample configs | Template with comments. Configs for: foxBMS 18S, BMW i3 96S, FOBSS 44S. Document: "how to create a config from a DBC file in 15 minutes." | Template + 3 working configs |
| D6.1-3 | Simulate BMS customer variant validation | Create 4 synthetic configs from the same pipeline to prove the variant story: 48S/LFP, 96S/NMC, 108S/NMC, 216S/NMC. Run pipeline on BMW i3 data with per-cell normalization for each. Show that SOC predictions are similar across all 4 (proving series-count agnostic). | 4 variant reports, similar RMSE |
| D6.4-5 | Write test_pipeline.py | pytest tests: decode produces CSV, extract produces (N,5), inference produces predictions, short log doesn't crash, missing signal handled. ~100 lines. Run: `pytest pipeline/test_pipeline.py -v`. | 8+ tests passing |
| D6.6-8 | Pipeline README + edge case hardening | Document: install deps, create config, run audit. Fix any bugs from testing. Handle: empty CAN log, DBC with no matching signals, log shorter than model window. | Robust pipeline |

**After Day 6**: `run_audit.py` works end-to-end. We can process any BMS company's CAN log and produce predictions. The variant validation story (4 pack configs, similar RMSE) is proven.

---

### Day 7-9 (24h): Report generation — what BMS companies actually receive

| Hour | Task | Detail | Output |
|---|---|---|---|
| D7.1-3 | SOC Validation Report generator | `generate_report.py` function: takes ML SOC predictions + BMS SOC + config → produces markdown + matplotlib plot. Two-panel chart: SOC comparison (ML vs BMS) + delta over time. Metrics: RMSE, max drift, end-of-test error. Interpretation text (auto-generated based on RMSE thresholds). ~120 lines for SOC report. | soc_validation.md + soc_comparison.png |
| D7.4-6 | Thermal + Cell Health reports | Thermal: risk timeline plot (0-1 scale, color-coded), peak risk, high-risk duration, affected cell group. Cell Health: per-cell voltage bar chart at rest, weakest cell identification, spread trend. ~80 lines each. | thermal_risk.md + cell_health.md + plots |
| D7.7-8 | Variant Summary Report | **NEW — specific to BMS companies**: One report that compares SOC accuracy across multiple pack variants. Table: variant name, cell count, chemistry, RMSE, max drift, verdict (PASS/FAIL). This is what they show their ISO 26262 assessor. ~60 lines. | variant_summary.md |
| D8.1-2 | Integrate reports into run_audit.py | Stage 4: `generate_all_reports()`. Auto-generates 3-4 reports from predictions. Output to reports/ directory. | run_audit.py produces reports |
| D8.3-4 | Test: full pipeline → reports on BMW i3 | Run full pipeline on trip_001.csv. Open all reports. Verify: plots render, numbers match, interpretation text is correct. Take screenshots. | 4 reports from BMW i3, visually reviewed |
| D8.5-6 | Test: variant comparison report | Run pipeline on 4 configs (48S/96S/108S/216S). Generate variant_summary.md. Verify: all 4 appear in table, RMSE values reasonable, chemistry noted. | Variant summary with 4 configs |
| D8.7-8 | PDF conversion | `pip install weasyprint` or `pandoc`. Convert markdown → PDF. If fails: ship as markdown + PNG (still professional for first customer). | PDF or markdown+PNG decided |
| D9.1-3 | Report polish | Review all reports critically. Fix: axis labels, unit conversions, font sizes, color scheme matching dashboard (dark theme). Add Taktflow logo and "Generated by Taktflow ML Pipeline" footer. Make them look professional, not like a script output. | Professional-quality reports |
| D9.4-5 | ISO 26262 compliance framing | Add section to SOC report: "Independent Validation per ISO 26262 Part 6". Explain: ML model is independently trained (different algorithm, different data, different implementation). Cite: model architecture, training data source, validation dataset. This is what the safety engineer needs. | ISO 26262-ready SOC validation section |
| D9.6-8 | Create "BMS customer sample package" | Bundle: sample SOC validation report (from BMW i3), sample variant summary (4 configs), sample thermal report. Anonymize file paths. This is the "here's what you'll get" package for the first sales meeting. | sample_reports.zip |

**After Day 9**: We can hand a BMS company a professional validation report from their CAN log. The variant summary shows SOC accuracy across pack configs. The ISO 26262 framing gives their safety engineer what they need.

---

### Day 10-12 (24h): Bench sidecar — runs on their hardware

| Hour | Task | Detail | Output |
|---|---|---|---|
| D10.1-4 | Write ml_sidecar_bench.py (150 lines) | DBC-driven sidecar using cantools + python-can. Unlike foxBMS-specific sidecar (hardcoded CAN IDs), this reads ANY DBC, decodes ANY signal names, maps via pack_config.json. `--dbc customer.dbc --config pack.json --can can0 --models models/`. Main loop: `bus.recv()` → `db.decode_message()` → per-cell normalize → infer → `bus.send(0x700-0x705)`. | ml_sidecar_bench.py |
| D10.5-6 | Test with python-can virtual bus | Create virtual bus in Python: `can.interface.Bus("test", bustype="virtual")`. Send foxBMS-format frames. Verify sidecar decodes + infers. No real hardware needed. | Virtual bus test passing |
| D10.7-8 | Create ML_Predictions.dbc | CANape/Vector DBC file for CAN 0x700-0x705. 6 messages with signal definitions. Customer imports into CANape → ML signals appear as recordable measurements alongside their BMS signals. | ML_Predictions.dbc |
| D11.1-3 | Test with real CAN (if PCAN available) | Plug PCAN USB adapter. `ip link show can0`. Run sidecar on can0. Send test frames with `cansend`. Verify with `candump`. If no PCAN: test with vcan + cansend to simulate. | Real or simulated CAN test |
| D11.4-6 | Anomaly baseline training from customer CAN | Write `pipeline/train_baseline.py` (~80 lines). Input: DBC + CAN log (normal operation). Decode → extract features → train IsolationForest → save .pkl. This is the "personalized anomaly model" for the BMS company's specific pack. | train_baseline.py working |
| D11.7-8 | Customer instruction document | 1-page: "How to record your anomaly baseline." Step 1: connect adapter. Step 2: start logging normal operation. Step 3: 30 min. Step 4: send us the file. | Instruction doc (1 page) |
| D12.1-4 | Auto-DBC config generator | `auto_config.py` (~100 lines). Parses DBC with cantools, auto-detects BMS signals by naming patterns (voltage, current, SOC, temperature). Outputs draft pack_config.json. Reduces 15 min manual config → 2 min review. | auto_config.py |
| D12.5-6 | Test auto-config on 3 DBCs | Test with: foxBMS DBC, mebms-classic DBC, and one other if available. Verify signal detection accuracy. Handle: different naming conventions, missing signals. | Auto-config works on 3 DBCs |
| D12.7-8 | Bench sidecar README | Deploy instructions for customer bench: hardware requirements (USB-CAN, laptop), software setup (`pip install`), config creation, sidecar start, CANape integration (import DBC). | Bench deployment guide |

**After Day 12**: We can deploy a sidecar on any BMS company's bench. Auto-DBC parsing reduces onboarding to 2 minutes. CANape DBC lets them see ML predictions in their existing tooling.

---

### Day 13-15 (24h): SIL variant testing — the BMS company's main use case

| Hour | Task | Detail | Output |
|---|---|---|---|
| D13.1-3 | Parameterized plant model | Refactor plant_model.py to accept pack config via CLI: `--cells 96 --capacity 60 --chemistry NMC --ocv-table nmc811.json`. Same physics engine, different parameters. A BMS company tests their firmware against 4 pack variants without changing any code. ~80 lines of config loading added. | Plant model accepts pack params |
| D13.4-5 | Plant calibration from CAN log | Write `pipeline/calibrate_plant.py` (~100 lines). Input: customer CAN log + pack_config. Extracts: OCV curve (voltage at rest periods), internal resistance (dV/dI at load steps), cell spread (std of cell voltages), thermal mass (dT from known power). Output: `plant_calibration.json`. | calibrate_plant.py |
| D13.6-8 | Test: calibrate from BMW i3 data | Run calibrate on BMW i3 trip → extract OCV curve, R_internal. Compare extracted OCV with real NMC curve. Verify: R_internal ~50-100 mΩ (reasonable for 96S). Run plant with extracted params → voltage should match BMW i3 data within ±5%. | Calibrated plant model from real data |
| D14.1-3 | SIL variant test runner | Write `pipeline/run_sil_variants.py` (~120 lines). Input: BMS firmware binary + list of pack configs. For each variant: start plant with those params → start vECU → start sidecar → run for 60s → collect predictions → generate variant summary report. Automated, no human intervention. | run_sil_variants.py |
| D14.4-6 | Test: 4 variant SIL run | Run on foxBMS with 4 configs: 18S/3Ah (original), 48S/30Ah, 96S/60Ah, 108S/94Ah. Each: plant calibrated, vECU runs, sidecar collects. Generate: variant_summary.md with SOC RMSE per variant. This is the demo that sells Tier 2. | 4-variant SIL report |
| D14.7-8 | Docker compose for SIL variants | Update docker-compose.yml: parameterized plant config via environment variables. `PACK_CONFIG=/configs/customer_A.json docker compose up`. Each variant = different env var, same containers. | Docker variant support |
| D15.1-3 | SIL fault injection across variants | For each of the 4 variants: inject OV, OT, OC. Measure BMS response time (contactor open latency). Generate: `fault_detection_matrix.md` — table showing response time per variant per fault type. BMS company uses this to prove their fault detection works on all customer packs. | Fault detection matrix (4 variants × 3 faults) |
| D15.4-5 | ISO 26262 traceability | Link each test to a requirement: "SWR-SOC-001: SOC accuracy < 5% → PASS (2.1% on variant A)". Format matches ASPICE SWE.6 test evidence. BMS company can include in their safety case. | Traceable test evidence |
| D15.6-8 | Buffer + integration testing | Run full pipeline end-to-end: decode BMW i3 log → extract → infer → report → variant summary. Fix any bugs. Performance test: target <5 min for 1-hour CAN log. | Robust pipeline |

**After Day 15**: The BMS company value prop is proven. We can: (1) validate their SOC across N pack variants, (2) test their fault detection across variants, (3) generate ISO 26262-ready evidence. All automated, all from one SIL build.

---

### Day 16-18 (24h): Package + demo + Docker

| Hour | Task | Detail | Output |
|---|---|---|---|
| D16.1-3 | Pipeline Docker image | `pipeline/Dockerfile`: Python 3.11 + onnxruntime + cantools + matplotlib. Copy models + pipeline scripts. Entrypoint: `run_audit.py`. `docker run pipeline --config ... --log ... --output ...`. | Pipeline Docker image |
| D16.4-6 | Full SIL Docker compose | All services: vECU + plant (parameterized) + sidecar + web dashboard. `PACK_CONFIG=x.json docker compose up`. Test: clean Ubuntu VM → clone → compose up → dashboard loads in <10 min. | One-command SIL |
| D16.7-8 | Health endpoint + monitoring | Add `/health` to web server: JSON with ml_active, bms_state, uptime, anomaly_score, model versions. Add `/api/predictions` for programmatic access to latest ML predictions. | REST API for ML predictions |
| D17.1-3 | Write 10-minute demo script | Minute-by-minute: intro (1.5min) → live dashboard (2.5min) → fault injection → anomaly spike (2min) → run_audit on BMW i3 → show report (2min) → variant summary → pricing (2min). Include exact commands, what to say, what to show. | demo-script.md |
| D17.4-6 | Rehearse demo 3 times | Time each. Fix flow. Pre-stage terminal commands. Prepare FAQ: "Does it work with LFP?" "How accurate is it on our pack?" "What do you need from us?" | Demo < 10 min, FAQ ready |
| D17.7-8 | Record terminal session | asciinema: pipeline run on BMW i3 → reports → variant summary. Keep < 5 min. Export for async sharing. | demo.cast |
| D18.1-3 | BMS customer pitch deck | 6 slides: (1) Problem: N variants, limited bench time. (2) Solution: SIL + ML validation. (3) Live demo screenshot. (4) Sample reports. (5) Pricing tiers. (6) Next steps: "Give us DBC + 1 log." Not PowerPoint — markdown rendered to PDF or HTML. | Pitch deck (6 slides) |
| D18.4-6 | Customer-facing README | 1 page: what this is, what we need from them (DBC + CAN log), what they get (3 reports in 48h), how to evaluate (Docker demo). | Customer README |
| D18.7-8 | Leave-behind package | ZIP: sample reports (3 PDFs), variant summary, pack_config template, ML_Predictions.dbc, customer README, pitch deck. < 5 MB. | leave-behind.zip |

**After Day 18**: Complete sales package. Demo rehearsed. Docker works. Leave-behind ready.

---

### Day 19-20 (16h): Dry run + retrospective

| Hour | Task | Detail | Output |
|---|---|---|---|
| D19.1-3 | Dry run: full customer simulation | Pretend BMW i3 data is from "Customer A" (96S NMC pack). Create config (15 min). Run pipeline (5 min). Review 4 reports (2 hours). Rate each report: "Would a BMS company's safety engineer accept this?" | 4 reports, critically reviewed |
| D19.4-6 | Dry run: variant validation | Same "Customer A" firmware against 4 pack configs. Generate variant summary. Rate: "Does this prove SOC works across variants?" If any report fails quality check: fix report generator. | Variant summary, quality-checked |
| D19.7-8 | Fix quality issues | Axis labels, interpretation text, missing units, plot readability. Final polish on all report templates. | Reports are professional |
| D20.1-2 | Update live VPS demo | Deploy latest code. Ensure all services running with systemd. Verify dashboard loads cleanly with all ML gauges. Final screenshot. | sil.taktflow-systems.com/bms/ stable |
| D20.3-4 | Metrics + documentation | Count: lines written, models validated, pipeline runtime, reports generated, data sources tested. Update PLAN.md with Phase 6 (AI Integration) status. Update ml-changelog.md. | Metrics documented |
| D20.5-6 | Retrospective | What worked: live demo approach (fix → deploy → verify → repeat). What took longer: ONNX shape mismatch debugging, normalization domain gap. What to cut next time: SOH without cycling data (shows 0, confuses users). Lessons learned. | lessons-learned entry |
| D20.7-8 | Plan next 30 days | Day 21-50 priorities: (1) First real BMS customer engagement with ME bench data. (2) LSTM-Autoencoder for temporal anomaly detection. (3) Plant calibration from real bench CAN. (4) LFP chemistry support. | next-30-days-plan.md |

---

## What You Can Sell After Each Milestone

| After Day | Capability | Pitch to BMS company | Price |
|---|---|---|---|
| **1** | Live demo + tuned anomaly detection | "Watch: inject fault → ML catches it → clear → back to normal" | Free demo |
| **3** | Citable FOBSS accuracy numbers | "SOC LSTM: X.X% RMSE validated on foxBMS monitoring data" | Credibility |
| **6** | Offline pipeline + variant configs | "Give us your DBC + CAN log → SOC accuracy report in 48h" | Tier 0: free proof |
| **9** | Professional reports + ISO 26262 framing | "Here's your SOC validation report with independent ML baseline" | Tier 0.5: €2-5k |
| **12** | Bench sidecar + CANape DBC | "ML predictions live on your bench, visible in CANape" | Tier 1: €5-15k |
| **15** | SIL variant testing + fault matrix | "Your firmware validated across 4 pack variants, automated" | Tier 2: €20-40k |
| **18** | Docker + demo + pitch package | "Full package: SIL + ML + reports + Docker + CI" | Tier 2 ready to sell |
| **20** | Everything polished, dry-run complete | "Walk into first customer meeting" | Ready for revenue |

---

## Hour Budget Summary

| Category | Hours | % | Key files |
|---|---|---|---|
| Data prep + validation (BMW i3, FOBSS) | 20h | 12.5% | download, explore, validate_fobss.py |
| Pipeline code (decode/extract/infer/report) | 32h | 20% | 5 Python files (~400 lines total) |
| Report generator + templates | 20h | 12.5% | generate_report.py, 4 report types |
| Bench sidecar + auto-DBC | 16h | 10% | ml_sidecar_bench.py, auto_config.py |
| SIL variant testing | 20h | 12.5% | parameterized plant, variant runner, fault matrix |
| Docker + packaging | 16h | 10% | Dockerfile, compose, health endpoint |
| Demo + pitch materials | 16h | 10% | demo script, pitch deck, leave-behind |
| VPS ops + hardening | 8h | 5% | systemd, reboot test, monitoring |
| Testing + edge cases | 8h | 5% | test_pipeline.py, 3 data sources |
| Retrospective + planning | 4h | 2.5% | metrics, lessons, next plan |
| **Total** | **160h** | **100%** | |

---

## Risk Register

| Risk | Impact | Mitigation | Day affected |
|---|---|---|---|
| BMW i3 data download fails (Kaggle auth) | No training data validation | Use FOBSS only, or generate synthetic from plant model | Day 1 |
| FOBSS format incompatible | No citable foxBMS accuracy | Validate on BMW i3 only (weaker but still valid) | Day 2-3 |
| SOC LSTM RMSE > 5% on FOBSS | Can't claim accuracy | Fine-tune last 2 layers on FOBSS (3h detour) | Day 3 |
| cantools can't parse customer DBC | Pipeline fails on real DBC | Support manual decode fallback | Day 10 |
| weasyprint PDF fails | No PDF reports | Ship markdown + PNG (still professional) | Day 8 |
| No PCAN adapter for bench test | Can't test real CAN | Use vcan simulation (proven to work) | Day 11 |
| BMS firmware won't compile for x86 | SIL variant testing blocked | Use foxBMS as functional stand-in + calibrated plant | Day 14 |
