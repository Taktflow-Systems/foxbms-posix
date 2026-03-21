# DBC File

**Source**: [docs.foxbms.org — DBC](https://iisb-foxbms.iisb.fraunhofer.de/foxbms/gen2/docs/html/v1.4.1/tools/dbc.html)
**Location**: `foxbms-2/tools/dbc/foxbms.dbc` and `foxbms.sym`
**Tool**: PCAN Symbol Editor v6.5.2

---

## Files

| File | Format | Use |
|------|--------|-----|
| `foxbms.dbc` | Vector DBC | Standard CAN signal database (cantools, CANape, CANoe, PCAN) |
| `foxbms.sym` | PCAN Symbol | PCAN-specific signal format |

## Notes

- All signals big-endian (Motorola byte order)
- Endianness is configurable in the CAN module code
- Error flags added as enum in later versions
- See [foxbms-signals-summary.md](../dbc/foxbms-signals-summary.md) for decoded signal reference
