# AI-for-BMS Testing — 30-Day Work Packages (Hour-Level Detail)

**Date**: 2026-03-27
**Total estimated hours**: 160h (8h/day × 20 working days)
**Starting state**: ml_sidecar.py (643 lines) running on VPS with anomaly detection only. 3 ONNX models exist but not deployed. No offline pipeline. No reports.

---

## Current State (verified on disk)

| Asset | Status | Location | Size |
|---|---|---|---|
| ml_sidecar.py | Running on VPS, anomaly only | /opt/foxbms-sil/src/ | 643 lines |
| train_anomaly_bms.py | Deployed, model trained | /opt/foxbms-sil/src/ | 215 lines |
| soc_lstm.onnx | On disk, NOT deployed to VPS | taktflow-bms-ml/models/bms/ | 2.2 MB |
| thermal_cnn.onnx | On disk, NOT deployed to VPS | taktflow-bms-ml/models/bms/ | 163 KB |
| soh_transformer.onnx | On disk, NOT deployed to VPS | taktflow-bms-ml/models/bms/ | 328 KB |
| soc_norm_mean.npy | **MISSING** — not generated | — | — |
| soc_norm_std.npy | **MISSING** — not generated | — | — |
| foxbms_constants.py | On VPS | /opt/foxbms-sil/tools/ | 283 lines |
| web/server.py | Running on VPS, ML parsers added | /opt/foxbms-sil/web/ | 426 lines |
| web/index.html | On VPS, ML panel added | /opt/foxbms-sil/web/ | ~500 lines |
| BMW i3 data | **NOT downloaded** | — | 72 trips expected |
| FOBSS data | **NOT downloaded** | Manual from KIT Radar | 128 MB |
| pipeline/ directory | **DOES NOT EXIST** | — | — |
| run_audit.py | **NOT written** | — | — |
| generate_report.py | **NOT written** | — | — |

---

## WP1: Validate + Harden (Day 1–5, 40h)

### Day 1 (8h): Fix live sidecar CAN parsers

**Problem**: BMS_SOC shows 0.0% because 0x235 parser reads raw bytes instead of foxBMS big-endian encoding.

| Hour | Task | What exactly to do | Output |
|---|---|---|---|
| 1 | Diagnose 0x235 parser | SSH to VPS. `candump vcan1,235:7FF -n 1` → get raw bytes. Decode manually using `_fox_decode(d, 7, 16)` vs current `(data[0]<<8)\|data[1]`. Compare. | Confirmed: byte order is wrong |
| 2 | Fix 0x235 in ml_sidecar.py | Replace lines 147-150 with `_fox_decode`. Same for 0x233 (pack V/I) lines 137-145: use `_fox_decode(d, 7, 17)` for voltage, `_fox_decode(d, 20, 24)` for current with sign extension. | Fixed ml_sidecar.py locally |
| 3 | Fix 0x233 pack V/I | The current code at line 141 does `(d >> 40) & 0x1FFFF` — this is wrong for foxBMS big-endian. Replace with `_fox_decode(d, 7, 17)` and `_fox_decode(d, 20, 24)`. Test: pack_voltage should read ~66600 mV (18 cells × 3700 mV). | Pack V/I reading correctly |
| 4 | Deploy fixes to VPS | `scp src/ml_sidecar.py root@152.53.245.209:/opt/foxbms-sil/src/`. Restart sidecar: `pkill -f ml_sidecar; nohup python3 ml_sidecar.py vcan1 --no-onnx &`. Wait 10s. Check log: `tail -5 /var/log/foxbms-ml-sidecar.log`. Expect: `BMS_SOC=50.0% spread=14mV` | VPS sidecar shows correct values |
| 5 | Verify dashboard | Open `sil.taktflow-systems.com/bms/`. Check: ML Intelligence panel shows SOC ~50%, anomaly ~0.1, imbalance ~14mV. Check: CAN monitor shows 0x703/0x705 frames in amber. Screenshot. | Dashboard screenshot with correct ML values |
| 6 | Fix temperature display | Check if 0x280 parser reads temperatures correctly. Current code (lines 172-180) uses `data[2+i]` raw — but foxBMS encodes temp as 8-bit °C values at specific bit positions using big-endian table. Verify with `candump vcan1,280:7FF`. Fix if needed. | Cell temps show ~25.0°C on dashboard |
| 7 | Add SOC to footer bar | Dashboard footer shows `SOC` but uses plant SOC. When ML is active, show ML SOC next to BMS SOC in footer. Edit `web/index.html` update() function around line 437: add `ml_soc` display. | Footer shows: "SOC 50.0% (ML: 50.0%)" |
| 8 | Deploy updated dashboard | `scp web/index.html root@152.53.245.209:/opt/foxbms-sil/web/`. No restart needed (static file). Verify in browser. Final screenshot. | Day 1 complete: all ML gauges correct |

### Day 2 (8h): Tune anomaly model on real foxBMS data

| Hour | Task | What exactly to do | Output |
|---|---|---|---|
| 1-2 | Capture foxBMS normal baseline | SSH to VPS. Record 30 min of normal CAN: `timeout 1800 candump vcan1 -L > /tmp/foxbms_baseline.log`. This captures all CAN frames (~1M lines at 1ms plant rate). Verify: `wc -l /tmp/foxbms_baseline.log` should show >500K lines. Download: `scp root@152.53.245.209:/tmp/foxbms_baseline.log .` | foxbms_baseline.log (~50-100 MB) |
| 3-4 | Write train_from_candump.py | New script (~80 lines). Parse candump log format: `(timestamp) vcan1 ID#DATA`. For each second, extract features from 0x270 (decode 5 mux groups × 4 cells → 18 cell voltages → compute mean, std, max-min spread), 0x521 (current), 0x280 (temperature). Compute 5-feature vector: `[V_mean_mV, V_std_mV, I_mA, T_ddegC, V_spread_mV]`. Output: numpy array ready for IsolationForest. | train_from_candump.py (80 lines) |
| 5 | Train on real data | `python3 train_from_candump.py --log foxbms_baseline.log --output-dir src/`. Compare: synthetic model anomaly score on normal data was 0.34 (too high). Real-data model should score 0.05-0.15 on the same normal data. | anomaly_model.pkl + anomaly_scaler.pkl (retrained) |
| 6 | Deploy retrained model | `scp src/anomaly_model.pkl src/anomaly_scaler.pkl root@152.53.245.209:/opt/foxbms-sil/src/`. Restart sidecar. Check log: anomaly score should drop from ~0.34 to ~0.05-0.15 (model now knows what foxBMS normal looks like). | Anomaly score ~0.10 on dashboard |
| 7 | Validate: inject overvoltage | Open dashboard. Click "Overvoltage → Cell 0 → Inject". Watch CAN 0x705: score should rise from 0.10 to >0.60 within 2 seconds. The retrained model should have BETTER separation (lower normal, higher fault) than synthetic model. Record: normal score, fault score, separation margin. | Validated: normal=0.10, OV fault=0.72, separation=0.62 |
| 8 | Validate: inject overtemperature | Same process with "Overtemperature → Sensor 0 → Inject (80°C)". Record scores. Clear fault. Test overcurrent (200A). Document all three fault types with scores. Write validation table: 3 fault types × {normal_score, fault_score, detection_latency_ms}. | Anomaly validation table (3 rows) |

### Day 3-4 (16h): FOBSS validation + normalization stats

| Hour | Task | What exactly to do | Output |
|---|---|---|---|
| D3.1 | Download FOBSS | Go to `https://radar.kit.edu/radar/en/dataset/uabgQSNJZVAhKHgS`. Manual download (128 MB TAR). Extract to `taktflow-bms-ml/data/fobss/`. List files, understand format (CSV? HDF5? column names?). | FOBSS data extracted, format documented |
| D3.2-3 | Explore FOBSS data | Write `explore_fobss.py` (~50 lines). Load data, print column names, data types, sample rate, duration, cell count (expect 44), voltage range, temperature range, SOC range. Plot 1 minute of cell voltages to verify data makes sense. | FOBSS data profile: N columns, M rows, X seconds, 44 cells |
| D3.4-5 | Create FOBSS pack_config.json | Map FOBSS signal names to model features. Key mapping: FOBSS cell voltage columns → average for per-cell V. FOBSS pack current → I. FOBSS cell temps → T_avg, T_max. 44 cells in series. Create `customers/fobss/pack_config.json`. | pack_config.json for FOBSS |
| D3.6-7 | Generate normalization stats | Run `prepare_soc_dataset.py` from taktflow-bms-ml (148 lines, already exists). This generates `soc_norm_mean.npy` and `soc_norm_std.npy` from BMW i3 training data. If BMW i3 data not downloaded yet: use `download_datasets.py` first (126 lines, Kaggle download). **Fallback**: compute mean/std manually from the training features used in `soc_lstm.py`. | soc_norm_mean.npy (5 values), soc_norm_std.npy (5 values) |
| D3.8 | Verify normalization | Load .npy files: `np.load("soc_norm_mean.npy")` → expect 5 values like `[3.7, 0.5, 30.0, 35.0, 0.0]` (V_cell, I, T_avg, T_max, velocity). Print and sanity check against BMW i3 signal ranges. | Normalization stats verified |
| D4.1-3 | Run SOC LSTM on FOBSS | Write `validate_fobss_soc.py` (~80 lines). Load FOBSS features, normalize with soc_norm_mean/std, run sliding window (200 steps) through soc_lstm.onnx. Compare with FOBSS ground truth SOC (if available). Compute RMSE. **If FOBSS has no SOC ground truth**: compute from coulomb counting (integrate current → SOC). | SOC LSTM RMSE on FOBSS: X.XX% |
| D4.4-5 | Run Thermal CNN on FOBSS | Same pattern. Extract temperature features from FOBSS. Run through thermal_cnn.onnx (50-step window). Count false positives on normal operation (expect risk scores <0.3). If any scores >0.3, investigate: is it a real thermal event in the FOBSS data, or a model false positive? | Thermal CNN: X false positives per Y windows |
| D4.6-7 | Run Imbalance on FOBSS | Compute cell voltage spread (max-min) at each timestep from FOBSS 44-cell data. Compare with Imbalance CNN predictions (if model exists) or just report the spread statistics. This doesn't need an ONNX model — it's a direct computation. | Imbalance: mean spread=X mV, max spread=Y mV |
| D4.8 | Write validation-results.md | Document all results: SOC RMSE, Thermal false positive rate, Imbalance spread stats. Include: training data source, validation data source, window sizes, caveats. This is the document we cite in customer conversations. | validation-results.md (1-2 pages) |

### Day 5 (8h): VPS stability hardening

| Hour | Task | What exactly to do | Output |
|---|---|---|---|
| 1-2 | systemd service: ml_sidecar | SSH to VPS. Create `/etc/systemd/system/foxbms-ml-sidecar.service`: `[Unit] Description=foxBMS ML Sidecar After=network.target Requires=sys-devices-virtual-net-vcan1.device [Service] Type=simple ExecStart=/usr/bin/python3 /opt/foxbms-sil/src/ml_sidecar.py vcan1 --no-onnx --interval 1.0 WorkingDirectory=/opt/foxbms-sil/src Restart=always RestartSec=5 StandardOutput=journal StandardError=journal [Install] WantedBy=multi-user.target`. Enable: `systemctl daemon-reload && systemctl enable --now foxbms-ml-sidecar`. Test: `systemctl status foxbms-ml-sidecar`. Kill it: `pkill -f ml_sidecar`, verify it auto-restarts within 5s. | systemd service active, auto-restarts |
| 3-4 | systemd service: web server | Same pattern for web server. `/etc/systemd/system/foxbms-web.service`. ExecStart: `python3 /opt/foxbms-sil/web/server.py --can vcan1 --port 8081 --host 0.0.0.0`. After: foxbms-ml-sidecar.service. Test: kill server, verify auto-restart. Verify port 8081 responds. | systemd service active |
| 5 | systemd service: plant + vecu | Create `foxbms-sil.service` that starts plant_model.py and foxbms-vecu. Use `ExecStartPre` for vcan1 setup: `modprobe vcan; ip link add vcan1 type vcan; ip link set vcan1 up`. ExecStart: wrapper script that starts plant in background, then foxbms-vecu in foreground. | All 4 services in systemd |
| 6 | Reboot test | `reboot`. Wait 2 minutes. Check: `systemctl status foxbms-sil foxbms-ml-sidecar foxbms-web`. All should be active. Open dashboard in browser — should load with live data. | VPS survives reboot |
| 7 | Log rotation | Create `/etc/logrotate.d/foxbms`: rotate daily, keep 7, max 10M, compress. Since we're using systemd journal now (StandardOutput=journal), also set `journalctl --vacuum-size=100M`. | Logs won't fill disk |
| 8 | Health check endpoint | Add `/health` route to web/server.py (~15 lines): return JSON `{"status": "ok", "ml_active": state["ml_active"], "bms_state": state["bms_state_name"], "uptime_s": state["uptime_ms"]/1000, "anomaly_score": state["ml_anomaly_score"], "frames": ...}`. Deploy. Test: `curl https://sil.taktflow-systems.com/bms/health`. | Health endpoint responds |

**WP1 Total: 40h (5 days)**

---

## WP2: ONNX Models + Offline Pipeline (Day 6–10, 40h)

### Day 6 (8h): Deploy ONNX models to VPS

| Hour | Task | What exactly to do | Output |
|---|---|---|---|
| 1 | Install onnxruntime on VPS | `ssh root@152.53.245.209 "pip3 install --break-system-packages onnxruntime"`. Verify: `python3 -c "import onnxruntime; print(onnxruntime.__version__)"`. Check memory: `free -h` (expect 7+ GB free after install). | onnxruntime installed |
| 2 | Copy models + norm stats | `ssh root@... "mkdir -p /opt/foxbms-sil/models/bms"`. `scp taktflow-bms-ml/models/bms/soc_lstm.onnx taktflow-bms-ml/models/bms/thermal_cnn.onnx taktflow-bms-ml/models/bms/soh_transformer.onnx root@...:/opt/foxbms-sil/models/bms/`. Copy normalization stats (generated in WP1 Day 3): `scp soc_norm_mean.npy soc_norm_std.npy root@...:/opt/foxbms-sil/models/bms/`. | 3 ONNX files + 2 .npy files on VPS |
| 3 | Update sidecar systemd | Change ExecStart from `--no-onnx` to `--models-dir /opt/foxbms-sil/models/bms`. `systemctl daemon-reload && systemctl restart foxbms-ml-sidecar`. Check log: `journalctl -u foxbms-ml-sidecar -n 20`. Expect: "Loaded SOC LSTM", "Loaded normalization stats", "Loaded Thermal CNN", "Loaded SOH Transformer". | All 3 ONNX models loaded |
| 4 | Monitor SOC LSTM warmup | SOC LSTM needs 200 timesteps (200 seconds at 1Hz inference). Watch log: `journalctl -u foxbms-ml-sidecar -f`. After ~200s, expect: log shows `ML_SOC=XX.X%` instead of `SOC=waiting`. Check CAN: `timeout 210 candump vcan1,700:7FF -n 1`. First 0x700 frame should appear at ~200s. | SOC LSTM producing predictions |
| 5 | Verify SOC accuracy | Compare ML SOC (0x700) with plant SOC (0x600). Plant sends SOC on 0x600 as float32. If plant is at 49.5% (discharging from 50%), ML SOC should be within ±5% initially (model was trained on BMW i3, not foxBMS). Record: ML_SOC vs plant_SOC at t=300s. | ML SOC vs plant SOC recorded |
| 6 | Verify thermal CNN | Check CAN 0x702. With plant at 25°C constant, thermal risk should be <0.1 (no anomaly). `candump vcan1,702:7FF -n 5`. Decode: `0x0032` = 50/1000 = 0.050. If >0.3 on normal data, the model may need temperature feature normalization check. | Thermal risk <0.1 on normal |
| 7 | Check VPS memory usage | `ps aux --sort=-rss | head -10`. Check RSS of ml_sidecar.py process. Expected: 150-250 MB (Python + onnxruntime + 3 models + sliding windows). If >500 MB, investigate memory leak (window deque should cap at maxlen). | Memory usage documented |
| 8 | Dashboard final check | Open dashboard. All 6 ML gauges should show live values. SOC LSTM: value after 200s warmup. SOH: value or 0 (needs cycling data). Thermal: <0.1. Imbalance: ~14mV. Anomaly: ~0.1 (retrained model). Take screenshot + save for demo. | Dashboard screenshot: all models live |

### Day 7-8 (16h): Build offline pipeline

| Hour | Task | What exactly to do | Output |
|---|---|---|---|
| D7.1 | Create pipeline/ directory | `mkdir -p foxbms-posix/pipeline`. Create `__init__.py`. | Empty pipeline package |
| D7.2-4 | Write decode_can.py (80 lines) | Decode CAN log files to CSV. Support 3 formats: candump log (parse `(ts) iface ID#DATA`), BLF (`can.BLFReader`), ASC (`can.ASCReader`). If cantools not available, fall back to manual foxBMS decoding from foxbms_constants.py. Output: CSV with columns `[timestamp, signal_name1, signal_name2, ...]`. Time-align to 100ms bins. Test: decode foxBMS candump log from Day 2 baseline capture. | decode_can.py passing on foxBMS log |
| D7.5-7 | Write extract_features.py (60 lines) | Read CSV + pack_config.json. Map signal names to model features. Normalize pack voltage to per-cell: `V_cell = pack_V / cells_in_series`. Compute T_avg, T_max from temperature columns. Output: numpy array `(N, 5)` = `[V_cell, I, T_avg, T_max, velocity=0]`. Also extract BMS SOC if signal exists (for comparison). Test: extract from foxBMS decoded CSV, verify V_cell ≈ 3.7V, I ≈ 1A, T ≈ 25°C. | extract_features.py passing |
| D7.8 | Write ml_inference.py (100 lines) | Wrapper around ONNX models. Load all 3 available models. Run sliding-window inference on feature array. Return dict: `{"ml_soc": array, "ml_thermal_risk": array, "ml_soc_offset": 200, ...}`. Handle missing models gracefully (skip, don't crash). Include IsolationForest anomaly scoring if anomaly_model.pkl exists. | ml_inference.py passing |
| D8.1-2 | Write run_audit.py (80 lines) | Orchestrator: parse args → decode → extract → infer → save predictions.csv. Print progress: `[1/4] Decoding... [2/4] Extracting... [3/4] Inferring... [4/4] Saving...`. Output predictions.csv with columns: `[timestamp, ml_soc, ml_thermal_risk, ml_anomaly_score, cell_v_spread_mv, bms_soc]`. | run_audit.py end-to-end on foxBMS log |
| D8.3-4 | Test on foxBMS SIL data | Run: `python pipeline/run_audit.py --log foxbms_baseline.log --config customers/foxbms-demo/pack_config.json --models taktflow-bms-ml/models/bms/ --output reports/test/`. Verify predictions.csv has correct shape, SOC values in 0-100 range, thermal risk in 0-1 range. Compare SOC predictions with live sidecar values (should match within 1%). | Pipeline produces correct predictions.csv |
| D8.5-6 | Download BMW i3 data | Use `download_datasets.py` or manual Kaggle download. Extract to `taktflow-bms-ml/data/bms-raw/bmw-i3-driving/`. Verify: `ls *.csv | wc -l` → 72 files. Read first file: check columns match expected schema (col 7=voltage, col 8=current, col 9=temp, col 11=SOC). Create `customers/bmw-i3/pack_config.json` (96S, 94Ah, NMC). | BMW i3 data ready + config |
| D8.7-8 | Test pipeline on BMW i3 | `python pipeline/run_audit.py --log data/bmw-i3-driving/trip_001.csv --config customers/bmw-i3/pack_config.json --models models/bms/ --output reports/bmw-i3-test/`. Check: SOC LSTM predictions should track ground truth SOC with ~1.83% RMSE (this is the training data, so accuracy should be high). Plot comparison. | BMW i3 audit produces predictions matching training accuracy |

### Day 9-10 (16h): Customer config + integration testing

| Hour | Task | What exactly to do | Output |
|---|---|---|---|
| D9.1-2 | Create config template | Write `customers/template/pack_config.json` with every field commented. Include: customer name, all signal names with placeholders, cell count, chemistry, capacity, voltage limits. Write `customers/template/README.md` explaining each field (what to put, where to find it in their DBC). | Template + README |
| D9.3-4 | Test on FOBSS data | Create `customers/fobss/pack_config.json`. Run pipeline on FOBSS: `python run_audit.py --log data/fobss/monitoring.csv --config customers/fobss/pack_config.json --output reports/fobss/`. Compare SOC predictions with FOBSS ground truth. This cross-validates the pipeline on foxBMS-native data. | FOBSS predictions.csv + RMSE number |
| D9.5-6 | Edge case: short log | Test with 10-second CAN log (shorter than 200-step SOC window). Pipeline should: produce thermal + anomaly predictions (shorter windows), skip SOC LSTM (not enough data), report "SOC: insufficient data (10s < 200s required)". No crash. | Short log handled gracefully |
| D9.7 | Edge case: missing signals | Test with config pointing to non-existent signal name. Pipeline should: warn "Signal BMS_SOC_Display not found in decoded data", continue with available signals, mark missing fields as NaN in predictions.csv. | Missing signal handled gracefully |
| D9.8 | Edge case: different DBC | If available: test with mebms-classic DBC (different signal names, 96S pack). Create config, run pipeline. Verify per-cell normalization works (96S pack → V_cell ≈ 3.7V, same as 18S). This proves topology independence. | Cross-pack validation |
| D10.1-2 | Pipeline performance | Measure: 60s foxBMS log (1M frames) → decode time, extract time, inference time, total time. Target: <60s total for 60s of CAN data (real-time capable). If slow: profile with cProfile, optimize bottleneck (likely decode loop). | Performance: Xs for 60s log |
| D10.3-4 | Write test_pipeline.py | Automated tests for pipeline (~100 lines). Test: decode produces CSV, extract produces (N,5) array, inference produces dict with expected keys, short log doesn't crash, missing signal doesn't crash. Use pytest. Run: `pytest pipeline/test_pipeline.py -v`. | 8+ tests passing |
| D10.5-6 | Pipeline README | Write `pipeline/README.md` (~50 lines). Usage: install deps, create config, run audit. Include: supported log formats, expected output, troubleshooting (common DBC issues). | Pipeline documented |
| D10.7-8 | Buffer | Fix any bugs found during testing. Update foxbms_constants.py if needed. Clean up code. | Day 10 complete |

**WP2 Total: 40h (5 days)**

---

## WP3: Reports + Bench Sidecar (Day 11–15, 40h)

### Day 11-12 (16h): Report generator

| Hour | Task | What exactly to do | Output |
|---|---|---|---|
| D11.1-2 | Install matplotlib on dev machine | `pip install matplotlib`. Create `pipeline/generate_report.py`. Start with SOC audit report: function that takes predictions + config → markdown + PNG plot. | Skeleton report generator |
| D11.3-5 | SOC audit report (3h) | Implement `generate_soc_report()`. Plot: 2-panel figure (SOC comparison + delta). Top panel: ML SOC line (purple) + BMS SOC line (green) vs time. Bottom panel: difference filled area (yellow). Compute: RMSE, max diff, end drift. Generate markdown table with metrics. Interpretation text: <2% = excellent, 2-5% = moderate, >5% = investigate. | soc_audit.md + soc_comparison.png |
| D11.6-8 | Thermal risk report (3h) | Implement `generate_thermal_report()`. Plot: thermal risk timeline (0-1 scale). Color: green <0.3, yellow 0.3-0.7, red >0.7. Horizontal threshold line at 0.3. Overlay: cell temperature on secondary axis. Compute: peak risk, high-risk duration, cell group with highest risk. | thermal_risk.md + thermal_timeline.png |
| D12.1-3 | Cell health report (3h) | Implement `generate_cell_health_report()`. Plot: bar chart of per-cell mean voltage at rest. Color: weakest cell in red, strongest in blue, others in gray. Compute: spread (max-min), weakest cell index, deviation from mean. Recommendation text. | cell_health.md + cell_voltage_bar.png |
| D12.4 | Integrate into run_audit.py | Add stage 4: `generate_all_reports(config, features, predictions, bms_soc, output_dir)`. Call all 3 report generators. Print: "Reports generated: soc_audit.md, thermal_risk.md, cell_health.md". | run_audit.py produces 3 reports |
| D12.5-6 | Test on BMW i3 data | Run full pipeline on trip_001.csv → 3 reports. Open each: verify plot renders, numbers make sense, interpretation text is appropriate. BMW i3 SOC RMSE should be ~1.83% (training data). Screenshot all 3 reports. | 3 reports from BMW i3, visually reviewed |
| D12.7 | Test on FOBSS data | Same. FOBSS RMSE may differ. Thermal risk should be low (normal operation data). Cell health should show 44-cell spread. | 3 reports from FOBSS |
| D12.8 | PDF conversion (optional) | Try: `pip install weasyprint` → `weasyprint soc_audit.md soc_audit.pdf`. If weasyprint fails (common on Windows): try `pandoc -f markdown -t pdf soc_audit.md`. If both fail: ship as markdown + PNG (still professional). | PDF or markdown+PNG, decision made |

### Day 13-14 (16h): Bench sidecar + CANape DBC

| Hour | Task | What exactly to do | Output |
|---|---|---|---|
| D13.1-4 | Write ml_sidecar_bench.py (150 lines) | DBC-driven sidecar using cantools + python-can. Unlike the foxBMS-specific sidecar (raw SocketCAN + hardcoded IDs), this one: reads any DBC file, decodes any signal name, maps to model features via pack_config.json. `pip install cantools python-can`. Input: `--dbc customer.dbc --config pack_config.json --can can0 --models models/bms/`. Main loop: `bus.recv()` → `db.decode_message()` → update state → infer at 1Hz → `bus.send(0x700-0x705)`. | ml_sidecar_bench.py (150 lines) |
| D13.5-6 | Test with virtual bus | python-can supports virtual bus: `can.interface.Bus("test", bustype="virtual")`. Write test: send foxBMS-format frames on virtual bus → verify sidecar decodes → verify predictions appear on 0x700. This tests without real hardware. | Unit test passing |
| D13.7-8 | Write ML_Predictions.dbc | CANape DBC file for ML output signals. 6 messages: 0x700 (ML_SOC, BMS_SOC, SOC_Diff), 0x701 (ML_SOH), 0x702 (ML_ThermalRisk), 0x703 (ML_CellSpread), 0x704 (ML_RUL), 0x705 (ML_Anomaly). Standard DBC format. Test: load in cantools (`db = cantools.database.load_file("ML_Predictions.dbc")`). | ML_Predictions.dbc |
| D14.1-2 | Write train_anomaly.py (offline) | Adapts train_anomaly_bms.py for customer data. Input: DBC + CAN log (normal operation). Decodes signals → extracts features → trains IsolationForest → saves model. This is the Tier 1 "record 30 min of normal, then we train your baseline" workflow. | pipeline/train_anomaly.py (80 lines) |
| D14.3-4 | Customer instruction doc | 1-page document: "How to record your anomaly baseline". Step 1: connect CAN adapter. Step 2: start recording (`python -m can.logger -i can0 -f normal_baseline.blf`). Step 3: run pack through normal cycle (charge, discharge, idle). Step 4: stop after 30 min. Step 5: send us the .blf file. | customer_baseline_instructions.md |
| D14.5-6 | Test PCAN integration (if available) | If PCAN USB adapter available: plug in, `ip link show can0`, `candump can0`. Run ml_sidecar_bench.py on real CAN. If no PCAN: test with vcan + cansend to simulate. | Real or simulated CAN test |
| D14.7-8 | Buffer | Fix bugs. Clean up code. Update pipeline/README.md with bench sidecar instructions. | Day 14 complete |

### Day 15 (8h): Integration testing + buffer

| Hour | Task | What exactly to do | Output |
|---|---|---|---|
| 1-3 | Full pipeline end-to-end | Test the complete chain: CAN log → decode → extract → infer → report → 3 PDFs/MDs. Test on 3 data sources: foxBMS SIL dump, BMW i3 trip, FOBSS (if available). All 3 should produce reports without errors. | 9 reports total (3 sources × 3 reports) |
| 4-5 | Benchmark pipeline speed | Measure wall-clock time for each stage on each data source. Target: <5 min for 1-hour CAN log. If slow, identify bottleneck (usually decode loop or ONNX inference). | Performance table: 3 sources × 4 stages |
| 6-8 | Fix issues, clean code | Address any test failures, improve error messages, add docstrings, remove debug prints. | Clean pipeline code |

**WP3 Total: 40h (5 days)**

---

## WP4: Package + Demo + Dry Run (Day 16–20, 40h)

### Day 16-17 (16h): Docker packaging

| Hour | Task | What exactly to do | Output |
|---|---|---|---|
| D16.1-3 | Pipeline Dockerfile | Write `pipeline/Dockerfile`. Base: python:3.11-slim. Install: onnxruntime, numpy, scikit-learn, matplotlib, cantools, python-can. Copy: pipeline/*.py, models/bms/*.onnx, models/bms/*.npy. Entrypoint: `python run_audit.py`. Build: `docker build -t foxbms-pipeline pipeline/`. Test: `docker run --rm -v $(pwd)/data:/data foxbms-pipeline --log /data/test.csv --config /data/config.json --output /data/reports/`. | Pipeline Docker image works |
| D16.4-6 | Full SIL docker-compose | Update foxbms-posix/docker-compose.yml. Services: vecu (vECU + plant), ml-sidecar (anomaly + ONNX), web (dashboard + ML panel). Network: shared canbus bridge. Health checks on each service. Test: `docker compose up -d && sleep 20 && curl localhost:8080/health && docker compose down`. | docker-compose works from scratch |
| D16.7-8 | Clean machine test | On a fresh Ubuntu 24.04 VM (or Docker-in-Docker): `git clone foxbms-posix && cd foxbms-posix && docker compose up -d`. Wait 30s. Open browser → dashboard loads → ML panel shows data. If fails: fix Dockerfile, rebuild. | Reproducible in <10 min |
| D17.1-3 | Compose with models | Ensure docker-compose copies ONNX models into ml-sidecar container. Two options: (a) bake into Dockerfile, or (b) mount as volume. Option (a) is simpler for demos but larger image. Option (b) needs models on host. Decide and implement. | ONNX models available in container |
| D17.4-6 | CI pipeline update | Update `.github/workflows/ci.yml`. Add job: "Pipeline test" — install deps, run pipeline on test data, verify reports generated. Add job: "Docker build" — build all images, verify compose starts. Non-blocking (continue-on-error for now). | CI runs pipeline tests |
| D17.7-8 | Buffer | Fix Docker issues (vcan permissions, CAN module loading, etc.). | Docker works reliably |

### Day 18-19 (16h): Demo script + recording

| Hour | Task | What exactly to do | Output |
|---|---|---|---|
| D18.1-3 | Write demo script document | 10-minute scripted demo. Minute-by-minute: intro (1.5min) → live dashboard (2.5min) → fault injection (2min) → offline pipeline (2min) → pricing (1.5min) → Q&A (0.5min). Include: exact URLs to click, exact terminal commands to type, what to say at each step, what the audience should see. | demo-script.md (2 pages) |
| D18.4-6 | Rehearse 3 times | Time each rehearsal. First: identify flow problems, awkward transitions, too-long pauses. Second: optimize command order, pre-type commands in terminal. Third: smooth, under 10 minutes, confident transitions. Notes: what questions might they ask? Prepare 5 FAQ answers. | Demo smooth, <10 min, FAQ prepared |
| D18.7-8 | Record terminal session | Install asciinema: `pip install asciinema`. Record: `asciinema rec demo.cast`. Inside recording: run pipeline on BMW i3 data, show reports, show dashboard. Keep under 5 min (the terminal portion of the demo). Export as GIF or SVG for embedding in pitch deck. | demo.cast recording |
| D19.1-2 | Customer-facing README | Write `README-customer.md`. How to evaluate: (1) clone repo, (2) docker compose up, (3) open browser, (4) try fault injection, (5) give us your DBC + CAN log for free Tier 0 audit. Keep under 1 page. | Customer README |
| D19.3-4 | Sample reports | Take the best BMW i3 or FOBSS reports from WP3 testing. Anonymize if needed (remove file paths, rename to "Sample BMS"). These become the "sample output" we show customers. Package as ZIP: 3 PDFs + predictions.csv + pack_config template. | sample_reports.zip |
| D19.5-8 | Dry run on real-world data | Pick the best data source: BMW i3 (72 trips available), FOBSS (foxBMS native), or ME bench data (if available). Run full pipeline on 3 different logs from the same source. Review all 9 reports critically. For each report: Is the finding actionable? Is the number believable? Would a customer pay €5k for this? If any answer is "no", fix the report generator. | 9 critically-reviewed reports |

### Day 20 (8h): Pitch package + retrospective

| Hour | Task | What exactly to do | Output |
|---|---|---|---|
| 1-2 | One-page service description | Tier 0-3 summary. What we deliver, what we need from them, timeline, price range. No more than 1 page A4. Print-ready PDF. Include: live demo URL, sample report screenshot, contact info. | service-description.pdf |
| 3-4 | Leave-behind package | ZIP file or USB stick contents: sample reports (3 PDFs), pack_config template, ML_Predictions.dbc (for CANape), customer README, service description. Total: <5 MB. | leave-behind.zip |
| 5 | Update VPS demo | Ensure sil.taktflow-systems.com/bms/ is stable. All models running. Health endpoint responds. Take final screenshot for pitch deck. | VPS demo stable |
| 6 | Metrics | Count: lines of code written (pipeline + sidecar + tools), models validated, pipeline runtime, reports generated, data sources tested. | Metrics document |
| 7 | Retrospective | What worked (fastest tasks), what took longer (data format issues?), what to cut (SOH without cycle data?), what to add (Grafana?). Write in lessons-learned format. | lessons-learned.md entry |
| 8 | Plan next 30 days | Day 21-50: Tier 2 SIL for customer firmware, Tier 3 anomaly mining, first customer engagement. Prioritize based on which customer is closest to signing. | next-30-days-plan.md |

**WP4 Total: 40h (5 days)**

---

## Grand Total

| WP | Days | Hours | Key Deliverable |
|---|---|---|---|
| WP1: Validate + Harden | Day 1-5 | 40h | Correct dashboard, retrained anomaly model, FOBSS validation numbers, systemd auto-restart |
| WP2: ONNX + Pipeline | Day 6-10 | 40h | All 5 models live on VPS, run_audit.py produces predictions from any CAN log |
| WP3: Reports + Bench | Day 11-15 | 40h | 3 PDF reports with plots, DBC-driven bench sidecar, CANape DBC |
| WP4: Package + Demo | Day 16-20 | 40h | Docker, 10-min demo, dry run reports, pitch package |
| **Total** | **20 days** | **160h** | **Customer-ready Tier 0 + Tier 1** |

---

## Hour Budget by Category

| Category | Hours | % | Files |
|---|---|---|---|
| CAN parser fixes + debugging | 12h | 7.5% | ml_sidecar.py |
| Anomaly model retraining | 8h | 5% | train_from_candump.py |
| FOBSS validation | 16h | 10% | validate_fobss_soc.py, validation-results.md |
| VPS ops (systemd, deploy, reboot) | 8h | 5% | systemd services |
| ONNX deployment + testing | 8h | 5% | scp + restart + verify |
| Pipeline code (decode/extract/infer) | 24h | 15% | 4 Python files (~320 lines) |
| Report generator | 16h | 10% | generate_report.py (~200 lines) |
| Bench sidecar + DBC | 16h | 10% | ml_sidecar_bench.py, ML_Predictions.dbc |
| Docker packaging | 16h | 10% | Dockerfile, docker-compose.yml |
| Demo + recording | 16h | 10% | demo-script.md, demo.cast |
| Testing + edge cases | 12h | 7.5% | test_pipeline.py, 3 data sources |
| Documentation | 8h | 5% | READMEs, templates, service description |
| **Total** | **160h** | **100%** | |

---

## Critical Path

```
Day 1: Fix parsers ──→ Day 2: Retrain anomaly ──→ Day 3-4: FOBSS validation
                                                           │
Day 5: systemd ────────────────────────────────────────────┤
                                                           │
Day 6: Deploy ONNX ──→ Day 7-8: Build pipeline ──→ Day 9: Test on 3 sources
                                                           │
Day 11-12: Reports ──→ Day 13-14: Bench sidecar ──→ Day 16: Docker
                                                           │
Day 18: Demo script ──→ Day 19: Dry run ──→ Day 20: Pitch package
```

**Bottleneck**: FOBSS download (Day 3) — manual, depends on KIT Radar availability. If blocked: skip FOBSS, validate on BMW i3 data only (weaker claim but still valid).

**Risk buffer**: 0h explicitly allocated. Each day has natural slack in "buffer" hours. If a task runs over, borrow from the next day's buffer.
