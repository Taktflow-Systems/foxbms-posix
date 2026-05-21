# Modbus Interface Lab

Self-contained browser tools for exercising a Modbus/TCP BMS interface against
a local plant model.

Start the plant model:

```powershell
python .\tools\modbus_interface_lab\plant_model.py --http-port 8766 --modbus-port 1502
```

Start the interface console:

```powershell
python .\tools\modbus_interface_lab\interface_console.py --port 8768
```

Open:

```text
http://127.0.0.1:8768/
```

The full operator guide is in [HANDBOOK.md](HANDBOOK.md).
