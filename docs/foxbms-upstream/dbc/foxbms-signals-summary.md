# foxBMS CAN Signal Summary

**Source**: `foxbms-2/tools/dbc/foxbms.dbc` (fetched from GitHub)
**Tool**: PCAN Symbol Editor v6.5.2

---

## Key TX Messages (foxBMS → CAN bus)

| CAN ID | Hex | Name | Period | Key Signals |
|--------|-----|------|--------|-------------|
| 544 | 0x220 | `f_BmsState` | 100ms | BmsState (4-bit), InsulationResistance, error/warning flags (30+ signals) |
| 545 | 0x221 | `f_BmsStateDetails` | 100ms | Substates, connected strings |
| 561 | 0x231 | `f_CellVoltages` | 100ms | Min/max/avg cell voltage, string voltage |
| 562 | 0x232 | `f_CellTemperatures` | 100ms | Min/max/avg cell temperature |
| 563 | 0x233 | `f_PackValues_P0` | 100ms | Pack voltage, pack current |
| 564 | 0x234 | `f_PackValues_P1` | 100ms | Pack power |
| 565 | 0x235 | `f_SOC` | 100ms | SOC (min, max, avg) |
| 566 | 0x236 | `f_SOE` | 100ms | State of energy |
| 576 | 0x240-0x245 | `f_CellVoltage_*` | 100ms | Individual cell voltages (multiplexed) |
| 592 | 0x250 | `f_CellVoltages_Mux` | 100ms | Cell voltages with mux (50 groups × 4 voltages) |
| 608 | 0x260 | `f_CellTemperatures_Mux` | 100ms | Cell temps with mux (30 groups × 6 temps) |
| 769 | 0x301 | `f_SlaveInfo` | 1000ms | Slave status |

## Key RX Messages (CAN bus → foxBMS)

| CAN ID | Hex | Name | Key Signals |
|--------|-----|------|-------------|
| 528 | 0x210 | `f_BmsStateRequest` | Mode request (STANDBY/NORMAL), balancing control |
| 624 | 0x270 | `AFE_CellVoltages` | 50 mux groups × 4 voltages (13-bit, 0-8191mV) + 4 invalid flags |
| 640 | 0x280 | `AFE_CellTemperatures` | 30 mux groups × 6 temps (8-bit signed, -128 to 127°C) + 6 invalid flags |
| 1313 | 0x521 | IVT Current | Current measurement (via Isabellenhuette IVT) |
| 1314 | 0x522 | IVT Voltage 1 | Pack voltage measurement |
| 1315 | 0x523 | IVT Voltage 2 | Pack voltage redundant |
| 1316 | 0x524 | IVT Voltage 3 | **HV bus voltage** (used by redundancy module, index [s][2]) |
| 1319 | 0x527 | IVT Temperature | Pack temperature |

## Signal Encoding

- **Byte order**: Big-endian (Motorola) for all foxBMS messages
- **Encoding**: Uses `CAN_BIG_ENDIAN_TABLE` lookup for DBC start bit → actual bit position
- **Cell voltages**: 13-bit unsigned, 0-8191 mV, factor=1, offset=0
- **Invalid flags**: 1-bit, `DECAN_DATA_IS_VALID = 1` (1 = valid, counterintuitive)
- **Temperatures**: 8-bit signed, -128 to 127°C, factor=1, offset=0

## f_BmsState (0x220) Signal Detail

| Signal | Bit | Size | Description |
|--------|-----|------|-------------|
| BmsState | 3 | 4 bits | 0=UNINIT, 3=IDLE, 5=STANDBY, 6=PRECHARGE, 7=NORMAL, 9=ERROR |
| ConnectedStrings | 7 | 4 bits | Number of connected strings (upper nibble of byte 0) |
| InsulationResistance | 63 | 8 bits | Factor=200, range 0-51000 kOhm |
| ErrorFlags | various | 1 bit each | Overcurrent, overvoltage, overtemp, precharge fail, etc. |

## Aerosol Sensor (0x3C4)

| CAN ID | Hex | Name | Signals |
|--------|-----|------|---------|
| 964 | 0x3C4 | `BAS_AerosolSensor` | PM concentration, threshold, status, faults, counter, CRC |

## POSIX Port Usage

Plant model encodes RX messages (0x210, 0x270, 0x280, 0x521-0x527) using these exact signal definitions. The `foxbms_signals.dbc` in `src/` should match these definitions. SIL probe messages (0x7E0-0x7FF) are NOT in the upstream DBC — they need a separate DBC file (audit finding A2-03).
