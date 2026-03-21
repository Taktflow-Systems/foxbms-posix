# Safety Documentation

**Source**: [docs.foxbms.org — Safety](https://iisb-foxbms.iisb.fraunhofer.de/foxbms/docs/latest/general/safety/safety.html)

---

## Key Statement

> "Since the target country and use of foxBMS 2 is unknown, the users of the system need to do a risk assessment on their own according to their concerns."

foxBMS 2 does NOT claim a specific ASIL level. It provides a BMS development platform that users must integrate into their own safety framework.

## Referenced Standards

- IEC 61508 — Functional Safety of E/E Systems
- ISO 26262 — Road Vehicles Functional Safety
- EN 13849 — Safety of Machinery

## Safety Hazards

- Electrical shock (HV battery system)
- Fire and explosion (Li-ion cells)
- Chemical exposure (electrolyte)
- Short-circuit risk
- Overvoltage / overcurrent

## Slave Voltage Limit

BMS slaves: max 12 cells, voltage sum between 11V and 55V.

## Implication for POSIX Port

foxBMS is not ASIL-certified. The POSIX port inherits this — it's a development/validation tool, not a safety-certified component. Safety claims must come from the user's application-specific analysis, not from foxBMS or our port.
