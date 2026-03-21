# Interlock Module

**Source**: [docs.foxbms.org — Interlock](https://iisb-foxbms.iisb.fraunhofer.de/foxbms/docs/latest/software/modules/driver/interlock/interlock.html)
**Files**: `src/app/driver/interlock/interlock.c`, `interlock.h`

---

## How It Works

External safety circuit with monitor current:
- BMS-Master supplies low-power current through interlock connector
- External loop passes through emergency stop switches
- Low-side current sense: 0-100mA → 0-4V (linear)
- Threshold comparator: pin goes low when current > 10mA

## Feedback Checking

- Pin LOW = interlock **closed** (normal)
- Pin HIGH = interlock **open** (fault condition)
- State machine monitors feedback, reports to DIAG on unexpected open

## Configuration

`BS_IGNORE_INTERLOCK_FEEDBACK` — disables feedback checking (removes safety detection).

## POSIX Port Status

Interlock hardcoded always-closed (GA-23). Cannot simulate interlock-break → safe-state transition. Phase 3 work: add interlock override via SIL command (0x7E0).
