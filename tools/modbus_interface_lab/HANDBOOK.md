# Modbus Interface Lab Handbook

## Purpose

This folder contains a small local lab for BMS interface testing:

- `plant_model.py`: a local Modbus/TCP target plus browser plant-model GUI.
- `interface_console.py`: a browser test console that runs BMS interface use cases.
- `interface_gui/`: static assets for the test console.
- `plant_gui/`: static assets for the plant-model GUI.
- `data/interface_profiles.json`: executable read/write profiles.
- `data/use_cases.md`: use-case catalog loaded by both tools.
- `data/loadable_sheets/all_loadable_sheets.csv`: optional structured register data for plant-model import.

The tools use only Python standard-library modules. No external Python package
is required for normal CSV use. XLSX import uses a lightweight built-in parser
for simple workbook sheets.

## Safety Model

The interface console defaults to `Dry Run`. In dry-run mode it builds the read
or write plan and writes run evidence, but it does not open a live connection.

Live reads require `Dry Run` to be unchecked. Live writes require both:

- `Dry Run` unchecked.
- `Arm Writes` checked.

Keep `Arm Writes` off when using the plant model unless the selected use case
explicitly needs write behavior.

## Start The Plant Model

From the repository root:

```powershell
python .\tools\modbus_interface_lab\plant_model.py --http-port 8766 --modbus-port 1502
```

Open the plant GUI:

```text
http://127.0.0.1:8766/
```

The plant exposes:

- HTTP status and register lookup at `http://127.0.0.1:8766/api/status`.
- Modbus/TCP at `127.0.0.1:1502`.

Optional register-data import:

1. Open the plant GUI.
2. Use `Load Register File`.
3. Select `tools/modbus_interface_lab/data/loadable_sheets/all_loadable_sheets.csv`.
4. Confirm the import count in the page summary.

## Start The Interface Console

From the repository root:

```powershell
python .\tools\modbus_interface_lab\interface_console.py --port 8768
```

Open:

```text
http://127.0.0.1:8768/
```

## Run Use Case 1 Against The Plant

Use these controls in the interface console:

- `Target`: `Plant API`
- `Probe`: confirms the HTTP link before the run
- Use case: `1`

The preset sets:

- `Adapter`: `Backend Polling API`
- `Host`: `http://127.0.0.1:8766`
- `Port`: `8766`
- `Dry Run`: unchecked
- `Arm Writes`: unchecked
- `Read Source`: `Custom`
- `Register Text`: `40071:1`

Click `Run`.

Expected evidence in `Run Log`:

- `connect_ok`
- `endpoint="/api/status"`
- `mode="plant_model_compat"`
- `read_ok`
- `address=40071`
- `raw=[...]`
- `scenario_complete failures=0`

The Signal Board should show one captured signal and render a plot for register
`40071`.

## Plot, Pin, And Monitor

After a successful run:

1. In `Filter`, enter `40071`.
2. Click `Pin Visible`.
3. Change `Plot` to `Pinned`.
4. Confirm the row changes from `Pin` to `Unpin`.
5. Confirm `Dry Run` is unchecked.
6. Click `Start 1s` or `Monitor 1s` to start live polling.
7. Watch the sample count increase and the plot update.
8. Click `Stop` to cancel the monitor.

`Start 1s` and `Monitor 1s` intentionally start a long live-read polling run
(`cycles=3600`). If `Dry Run` is still checked, the console blocks monitor
startup and leaves the safety setting unchanged. Treat monitor mode as a
long-running live read that should be stopped manually.

## Direct Modbus Mode

To bypass the HTTP compatibility path:

- `Target`: `Plant Modbus`
- `Probe`: confirms the TCP socket before the run

The preset sets:

- `Adapter`: `Modbus TCP`
- `Host`: `127.0.0.1`
- `Port`: `1502`
- `Dry Run`: unchecked
- `Read Source`: `Custom`
- `Register Text`: `40071:1`

Use the same use-case and register controls. This opens Modbus/TCP sessions
directly against the local plant model.

## Evidence Files

Each interface-console run writes evidence under:

```text
tools/modbus_interface_lab/runs/
```

For each run, the tool writes:

- `request.json`
- `events.jsonl`
- `run.log`
- `result.json`

The `runs/` folder is intentionally ignored by git.

## HTTP API Summary

Interface console:

- `GET /api/health`
- `GET /api/model`
- `GET /api/adapters`
- `GET /api/scenarios`
- `POST /api/run`
- `GET /api/run/<run_id>`
- `POST /api/run/<run_id>/cancel`
- `POST /api/backend/status`
- `POST /api/backend/read`

Plant model:

- `GET /api/status`
- `GET /api/registers?q=<address>`
- `POST /api/import`
- `POST /api/reset`
- `POST /api/preset`

## Self Tests

Run the script-level self tests:

```powershell
python .\tools\modbus_interface_lab\plant_model.py --self-test
python .\tools\modbus_interface_lab\interface_console.py --self-test
```

## Privacy And Naming

The package uses repository-relative paths in the UI and API model responses.
Local run artifacts stay under the ignored `runs/` folder. Do not commit run
artifacts, imported private workbooks, bench logs, network addresses, hardware
serials, or local absolute paths.
