# Precharging

**Source**: [docs.foxbms.org — Precharging](https://iisb-foxbms.iisb.fraunhofer.de/foxbms/docs/latest/system/precharging.html)

---

## Purpose

Precharging limits potentially high inrush current during startup of high voltage DC applications. Without precharge, the DC-link capacitor in the inverter would draw destructive current through the contactors.

## Circuit

- Precharge resistor in series with precharge contactor
- Current limited by R until capacitor charges to near-pack-voltage
- Once V_bus ≈ V_string, main contactors close and precharge opens

## Three States

| State | Contactors | Description |
|-------|-----------|-------------|
| Off | All open | No power delivery |
| Precharge | Precharge + one main closed | Current limited by resistor |
| On | Both main closed, precharge open | Full power delivery |

## Success Criteria

```
|V_string - V_bus| < threshold
```

Where:
- `V_string` = sum of all cell voltages (from AFE via database)
- `V_bus` = HV bus voltage (from IVT Voltage 3, CAN ID 0x524, `highVoltage_mV[s][2]`)

## Failure Detection

BMS monitors voltage and current during precharge:
- If conditions not met within timeout → precharge failure → ERROR state
- Timeout configurable in `bms_cfg.h`

## Dimensioning Tool

`tools/precharge/precharge_dimensioning.ipynb` — Jupyter notebook for RC calculations.

## Key Discovery (POSIX Port)

foxBMS uses `highVoltage_mV[s][2]` (index 2 = IVT Voltage 3 = CAN 0x524) for HV bus voltage, NOT index 0 (0x522). The plant model must send matching voltage on all three IVT voltage channels (0x522, 0x523, 0x524).
