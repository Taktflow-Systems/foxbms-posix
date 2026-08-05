# S-CH-07 pilot: Eclipse OpenBSW referenceApp as PC-hosted SIL

## Codebase choice (decision + rationale)

**Chosen pilot: Eclipse OpenBSW** (`eclipse-openbsw/openbsw`,
Apache-2.0), pinned at commit `bc8d49b58b26050bef8d3d79575b404c36750324`
(shallow clone, 2026-08-02).

Rationale:

- The plan (S-CH-07) allows an open-source embedded codebase with a
  plausible POSIX build path. OpenBSW is automotive embedded base
  software (CAN, UDS diagnostics, lifecycle manager, Ethernet/DoIP)
  whose primary target is the NXP S32K148 evaluation board — real
  firmware, not a demo repo.
- It has a **textbook hardware boundary**: `platforms/s32k1xx/bsp/`
  holds the real peripheral drivers (bspAdc, bspClock, bspFlexCan,
  bspFtmPwm, bspIo, bspTja1101 CAN-PHY…) while `platforms/posix/bsp/`
  is the host-side replacement layer (bspStdio, bspSystemTime, bspUart,
  socketCanTransceiver, tapEthernetDriver). The platform is switched by
  one cmake cache variable (`BUILD_TARGET_PLATFORM`), which makes it an
  ideal worked example for the skill's "identify the hardware boundary"
  step.
- Domain match: the owner's real workflow is BMS/automotive embedded
  work, so the skill is exercised on representative material.
- Toolchain match: cmake ≥3.22 + GCC + ninja, all present on the
  laptop (cmake 3.28.3, gcc 13.3.0, ninja 1.11.1).

Alternatives considered: foxBMS 2 (waf build, no upstream POSIX
target — would require inventing the whole host layer, too large for a
pilot), Betaflight SITL (POSIX target exists but domain is
flight-control hobbyist, weaker match).

## Files

- `build.sh` — idempotent clone + configure + build
  (`cmake --preset posix-freertos`). Product:
  `openbsw/build/posix-freertos/executables/referenceApp/application/Release/app.referenceApp.elf`.
- `smoke.sh` — smoke scenario with hard pass criteria; writes
  `smoke-run.log`.
- `openbsw/` — pinned upstream source (not authored here; upstream
  authors/SPDX headers retained).

## Smoke scenario (what "runs on the laptop" means)

1. Start `app.referenceApp.elf` (no hardware, no root, no CAN device —
   CAN demo traffic goes through the POSIX transceiver stub).
2. The lifecycle manager must boot through all run levels to
   `Run level 9`.
3. Send `stats cpu` on the console (stdin); the command must be
   received and answered (`Console command succeeded`).
4. Send `lc poweroff`; the app must walk shutdown levels 9→1, log
   `Lifecycle shutdown complete`, and exit with code 0.

## Validated result (2026-08-02, this laptop)

- Build: 381 ninja targets, zero errors, binary ~960 KB.
- Smoke: `SMOKE PASS: exit 0, all 4 markers present` — lifecycle
  reached level 9, `stats cpu` succeeded, clean shutdown. Evidence:
  `smoke-run.log` (kept in this folder), summarized in
  `logs/iteration-11.md`.
