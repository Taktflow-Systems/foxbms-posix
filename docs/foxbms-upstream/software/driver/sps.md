# SPS Module (Smart Power Switch — Contactor Control)

**Source**: [docs.foxbms.org — SPS](https://iisb-foxbms.iisb.fraunhofer.de/foxbms/docs/latest/software/modules/driver/sps/sps.html)
**Files**: `src/app/driver/sps/sps.c`, `sps.h`, `sps_cfg.c`, `sps_cfg.h`
**Status**: Upstream documentation marked "not yet complete"

---

## Function

Controls high-voltage contactors via SPI-connected power switches. Each SPS channel maps to a contactor:

| Channel | Contactor | Function |
|---------|-----------|----------|
| 0 | String+ contactor | Main positive |
| 1 | String- contactor | Main negative |
| 2 | Precharge contactor | Precharge resistor path |

(Channel mapping is project-specific, configured in `sps_cfg.c`)

## How It Works (Production)

1. BMS state machine requests contactor close → `SPS_RequestContactorState(channel, CLOSE)`
2. SPS builds SPI command → sends via DMA to smart power switch IC
3. SPS reads feedback via SPI → verifies contactor actually closed
4. Feedback mismatch → DIAG fault

## POSIX Port Implementation

SPS simulation in `hal_stubs_posix.c`:
- Per-channel state tracking (requested vs actual)
- Configurable delay (`SPS_CONTACTOR_DELAY_CYCLES`, default 10 = ~10ms)
- State transition logged to stderr: `[SPS] RequestContactor ch=0 state=1`
- No SPI (stubbed), no real feedback (GA-05)
