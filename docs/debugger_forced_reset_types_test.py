"""
FW-Check Debugger-Forced Reset Types (Warm PORST / System / Application)

Type: Integration

Requirements: <sysreq-warm>, <swreq-warm>, <sysreq-system>, <swreq-system>,
    <sysreq-application>, <swreq-application>

Labels: <project-a>, <project-b>

Procedure: One parameterized harness for the remaining MCU FW-check reset
types. Run each type separately: --type warm|system|application [--dry-run].
- warm (<sysreq-warm>):        debugger PORST pulse (SYStem.Mode Down + NoDebug)
- system (<sysreq-system>):      SW system reset (RSTCON.SW=01b, SWRSTREQ=1)
- application (<sysreq-application>): SW application reset (RSTCON.SW=10b, SWRSTREQ=1)
After the forced reset the test reads the STORED reset-cause copy
(FwCheckHandle.rstStat - the value the FW-check module actually decodes, see
the cold-POR sibling test), asserts the decode matches the injected type,
applies the same clearing-clause assertions as the cold-POR test, and
verifies the DUT boots back to normal operation. Cold POR and standby exit
are covered by sibling tests.
SETUP: SYMBOL_ELF_PATH must match the running image (symbols only, /NoCode,
never flashed) - same rule and same variable as the sibling tests.
RUN THE WARM VARIANT LAST IN A SLOT, on a rig where losing the debugger is
acceptable, and use --dry-run before live. A warm PORST resets the TC3xx DAP
module. On the TriCore DAP/JTAG probe, SYStem.Mode Down also actively drives
RESET-/PORST- low; it must never be used as a generic attach/detach command.
The non-resetting inactive mode is NoDebug. An attach-retry storm on a dead
debug port can wedge the PowerDebug probe firmware itself ("fatal error
#FF"), which only a mains power cycle of the Lauterbach box recovers.
An independent HIL-controlled open-drain PORST pulse while TRACE32 is in
NoDebug remains the preferred warm-reset actuator. The debugger-owned pulse
below is a fallback and must be qualified on the exact probe/cable/rig.
1. Ensure the TRACE32 RCL connection, configure it once, then release its
   reset output with NoDebug before bringing HIL and DUT to normal operation.
2. Load symbols (/NoCode); baseline the stored rstStat/wStat. With --dry-run
   the test stops here (no reset) and returns to Standby.
3. Inject the selected reset via TRACE32 (intrusive - the target resets):
   warm = NoDebug + Down + NoDebug (assert PORST, then release it without
   reconnecting DAP during startup); system/application = RSTCON.SW
   preselect/readback + SWRSTCON.SWRSTREQ, with no subsequent Down command.
4. Wait for the reboot; reconnect with NoDebug + Attach (no reset); read the
   stored copy plus the SFR set.
5. Decode per the FW-check priority chain; assert it matches the injected
   type.
6. Clearing clause: live SCU_RSTSTAT == 0, SMU_AG0..11 == 0.
7. Verify the DUT answers normally (UDS); write a dated snapshot CSV; recover
   to Standby.
8. Probe-health epilogue: VERSION.HARDWARE must answer without a fatal error;
   the session is left non-intrusively detached (SYStem.Mode NoDebug). A
   wedged probe fails THIS test loudly instead of silently poisoning every
   test after it.

Applicable to projects : <project-a>, <project-b>
"""

import csv
import sys
import time
from datetime import datetime
from pathlib import Path

import hil_utilities.testcase as tc

from defines import defines
from tc_lib import T32Python, generic
from tc_lib.evidence import upload_evidence_csv

# --- TC377 (TC37xA) addresses, verified against IfxScu_reg.h / IfxPms_reg.h ---
SCU_RSTSTAT = 0xF0036050
SCU_RSTCON = 0xF0036058  # SW field bits [9:8]: 01b=system reset, 10b=application reset
SCU_SWRSTCON = 0xF0036060  # SWRSTREQ = bit 1
SCU_STMEM3 = 0xF00361C0
SCU_LCLCON0 = 0xF0036134
SCU_LCLCON1 = 0xF0036138
PMS_PMSWSTAT = 0xF02480D4
PMS_PMSWSTAT2 = 0xF02480D8
SMU_AG_BASE = 0xF00369C0

# Decode masks - same set as the cold-POR test (reset_cause_decode_table.md)
RSTSTAT_PORST_MASK = 1 << 16
RSTSTAT_COLD_QUALIFIER_MASK = (1 << 23) | (1 << 24) | (1 << 25) | (1 << 28)
RSTSTAT_LOWER_WORD_MASK = 0x0000FFFF
RSTSTAT_HSMA_MASK = 1 << 27
RSTSTAT_HSMS_MASK = 1 << 26
RSTSTAT_LBTERM_MASK = 1 << 30
RSTSTAT_SW_MASK = 1 << 4  # SW reset request bit in the lower word

STORED_RSTSTAT_VAR = "FwCheckHandle.rstStat"
STORED_WSTAT_VAR = "FwCheckHandle.wStat"
# Resolved relative to this file, not a per-rig absolute path: drop the build-
# matching ELF as "current_build.elf" next to this test before running (any
# rig, no path edit needed) - same convention as the sibling tests. Must match
# the running image, fails loudly on a build mismatch.
SYMBOL_ELF_PATH = str(Path(__file__).parent / "current_build.elf")
# Long enough for a deliberate bench PORST pulse; validate against the board's
# reset supervisor and capture PORST/VTREF during first use on each rig type.
WARM_PORST_ASSERT_TIME_S = 0.1

# type -> (RSTCON.SW value to pre-select, expected decode after reboot)
RESET_TYPES = {
    "warm": (None, "WARM_PORST"),  # NoDebug + Down + NoDebug; no RSTCON change
    "system": (0x1, "SYSTEM_RESET"),  # RSTCON.SW = 01b
    "application": (0x2, "APPLICATION_RESET"),  # RSTCON.SW = 10b
}


def read_u32(address: int) -> int:
    # REVIEW (added): fixed sleep + get_message() can return a STALE message
    # left over from an earlier PRINT on a slow rig; a stale reply parses as a
    # plausible hex value and silently reports the WRONG register content.
    # Remedy: drain/clear the message line before each PRINT, or tag every
    # PRINT with a nonce and require the tag in the reply before parsing.
    T32Python.run_command(f"PRINT FORMAT.HEX(8.,Data.Long(D:{address:#010x}))")
    time.sleep(0.2)
    msg = T32Python.get_message()
    try:
        return int(msg.strip(), 16)
    except (AttributeError, ValueError):
        raise RuntimeError(f"T32 SFR read {address:#010x} failed - message: {msg!r}")


def write_u32(address: int, value: int):
    """Debugger write (intrusive path is acceptable here - we are about to reset)."""
    T32Python.run_command(f"Data.Set D:{address:#010x} %Long {value:#010x}")
    time.sleep(0.2)


def read_var_u32(varname: str) -> int:
    T32Python.run_command(f"PRINT FORMAT.HEX(8.,Var.VALUE({varname}))")
    time.sleep(0.25)
    msg = T32Python.get_message()
    try:
        return int(msg.strip(), 16)
    except (AttributeError, ValueError):
        raise RuntimeError(
            f"T32 var read {varname} failed (symbols loaded? build match?) - message: {msg!r}"
        )


def load_symbols_no_flash():
    T32Python.run_command(f'Data.LOAD.Elf "{SYMBOL_ELF_PATH}" /NoCode /NoClear')
    time.sleep(4.0)


def t32_rcl_connected() -> bool:
    try:
        return T32Python.get_state() is not None
    except Exception:
        return False


def t32_configure():
    """Configure TRACE32 once, then release PORST without opening DAP.

    On the TriCore DAP/JTAG cable, Mode Down drives RESET-/PORST- low. It is
    required while changing CPU/core configuration, but must be followed by
    NoDebug so the target is not left in reset.
    """
    # REVIEW (added): per the current Lauterbach TriCore manual, Down asserts
    # reset only when SYStem.Option.DOWNMODE ReSeT is configured - the DEFAULT
    # DOWNMODE is TriState, where Down releases the debug port just like
    # NoDebug. This file's "Down holds PORST low" premise was evidently true
    # on the original rig but is a per-config behavior, not a TRACE32
    # invariant. Remedy: read/set SYStem.Option.DOWNMODE explicitly here and
    # record it in the evidence.
    try:
        T32Python.run_command("SYStem.Mode Down")
        T32Python.run_command("SYStem.CPU TC377TP")
        T32Python.run_command("CORE.ASSIGN 1. 2.")
        T32Python.run_command("SYStem.Option.DUALPORT ON")
        T32Python.run_command("SYStem.Option.RESetBehavior RunRestore")
    finally:
        # Mode Down actively holds the TriCore PORST line low. Always release
        # it, including when CPU/core configuration fails part-way through.
        T32Python.run_command("SYStem.Mode NoDebug")
    time.sleep(0.5)


def t32_attach_no_reset():
    """Reconnect to the running target without asserting RESET-/PORST-."""
    T32Python.run_command("SYStem.Mode NoDebug")
    T32Python.run_command("SYStem.Mode Attach")
    time.sleep(1.0)


def t32_detach():
    """Tri-state the probe outputs without asserting RESET-/PORST-."""
    try:
        T32Python.run_command("SYStem.Mode NoDebug")
        time.sleep(0.5)
    except Exception:
        pass


def probe_health_ok() -> tuple[bool, str]:
    """Ask the PowerDebug probe itself (no target involved) whether it still answers.

    A wedged probe ('fatal error #FF', 2026-07-17 incident) fails every probe
    command including this one - that must fail THIS test's verdict, not the
    next test's setup.
    """
    # REVIEW (added): VERSION.HARDWARE renders into its own WINDOW (ide_ref
    # manual), and the remote API's T32_GetMessage reads only the MESSAGE
    # LINE - so get_message() here returns empty or a stale line, the "fatal"
    # check passes vacuously, and a wedged probe can be declared healthy on
    # zero evidence. Remedy: use the documented RCL pattern instead - PRINT a
    # PRACTICE function that targets the probe, e.g.
    # PRINT VERSION.SERIAL.CABLE() or PRINT VERSION.FirmWare.DEBUG() - and
    # treat an empty/unparseable reply as NOT healthy.
    try:
        T32Python.run_command("VERSION.HARDWARE")
        time.sleep(0.5)
        msg = T32Python.get_message() or ""
    except Exception as e:
        return False, repr(e)
    if "fatal" in msg.lower():
        return False, msg
    return True, msg


def decode_reset_type(rststat: int, pmswstat2: int = 0) -> str:
    """FW-check reset-reason priority chain on the STORED copy.
    Same chain as the cold-POR sibling test, extended: the priority-5
    module-reset group is split system/application via the SW-request bit +
    the RSTCON.SW class that was pre-selected before injection (the FW-check
    module reads SCU_RSTCON for the same distinction)."""
    if rststat & RSTSTAT_PORST_MASK:
        return "COLD_PORST" if (rststat & RSTSTAT_COLD_QUALIFIER_MASK) else "WARM_PORST"
    if rststat & RSTSTAT_HSMA_MASK:
        return "APPLICATION_RESET"  # HSM-initiated application reset
    if rststat & RSTSTAT_HSMS_MASK:
        return "SYSTEM_RESET"
    if rststat & RSTSTAT_LOWER_WORD_MASK:
        # REVIEW (added): this reads SCU_RSTCON *live at decode time*, i.e.
        # after the reboot. If the startup SW or a later test rewrites
        # RSTCON.SW between the reset and this read, a stored SW reset is
        # misclassified. It mirrors the FW-check module's own logic (so it
        # agrees with the DUT), but it is not evidence of what was latched at
        # reset time. Remedy: also read RSTCON.SW immediately before injection
        # and assert the post-reboot class against that captured value.
        rstcon = read_u32(SCU_RSTCON)
        sw_class = (rstcon >> 8) & 0x3
        if rststat & RSTSTAT_SW_MASK:
            return {0x1: "SYSTEM_RESET", 0x2: "APPLICATION_RESET"}.get(
                sw_class, "SW_RESET_UNKNOWN_CLASS"
            )
        return "APP_OR_SYSTEM_RESET (non-SW lower-word source)"
    if (pmswstat2 & 0xFF) & ((pmswstat2 >> 24) & 0xFF):
        return "STANDBY_EXIT"
    if rststat & RSTSTAT_LBTERM_MASK:
        return "COLD_PORST"
    return "UNKNOWN"


def inject_reset(reset_type: str):
    """Force the selected reset from the debugger. Intrusive by design.

    Mode Down is used only as the intentional assertion phase of warm PORST.
    NoDebug releases the open-drain reset output without reconnecting DAP
    during startup. System/application resets remain on the configured reset-
    recovery path and must not be followed by Mode Down.
    """
    sw_class, _ = RESET_TYPES[reset_type]
    if reset_type == "warm":
        # Disconnect DAP first. Down then drives RESET-/PORST- low; NoDebug
        # tri-states the output so the board pull-up releases PORST and the SSW
        # runs without TRACE32 reconnecting during the reset transition.
        T32Python.run_command("SYStem.Mode NoDebug")
        # REVIEW (added): this only asserts PORST if SYStem.Option.DOWNMODE is
        # ReSeT; with the factory default (TriState) the Down below is a no-op
        # on the reset line and NO RESET HAPPENS - which, combined with the
        # rerun false-pass noted in Step 3, can green-light the test without
        # any injection. Remedy: set SYStem.Option.DOWNMODE ReSeT immediately
        # before this sequence (restore afterwards), and keep the header's
        # scope qualification of PORST/VTREF on first use per rig.
        try:
            T32Python.run_command("SYStem.Mode Down")
            time.sleep(WARM_PORST_ASSERT_TIME_S)
        finally:
            # Releasing PORST is mandatory even when the host-side wait or
            # the Down command itself reports an exception after transmission.
            T32Python.run_command("SYStem.Mode NoDebug")
    else:
        # Halt, pre-select the SW reset class in RSTCON.SW ([9:8], Safety-ENDINIT
        # protected), read it back, then request via SWRSTCON.SWRSTREQ. Do not
        # enter Mode Down after the request: on TriCore that would append a
        # warm PORST and invalidate the system/application reset evidence.
        T32Python.run_command("Break")
        time.sleep(0.5)
        try:
            # REVIEW (added): RSTCON is Safety-ENDINIT protected and this is a
            # plain Data.Set; it works only because
            # SYStem.Option.EndInitProtectionOverride defaults to AUTO (TRACE32
            # auto-overrides ENDINIT for segment-0xF long writes). The readback
            # below already fails loudly, but the evidence never records which
            # override mode was active. Remedy: query and log
            # SYStem.Option.EndInitProtectionOverride next to the readback so
            # a rejected write is attributable instead of just "readback
            # mismatch".
            rstcon = read_u32(SCU_RSTCON)
            requested_rstcon = (rstcon & ~(0x3 << 8)) | (sw_class << 8)
            write_u32(SCU_RSTCON, requested_rstcon)
            rstcon_readback = read_u32(SCU_RSTCON)
            if ((rstcon_readback >> 8) & 0x3) != sw_class:
                raise RuntimeError(
                    f"RSTCON.SW readback failed: requested {sw_class:#x}, "
                    f"read {((rstcon_readback >> 8) & 0x3):#x} "
                    f"(RSTCON={rstcon_readback:#010x})"
                )
        except Exception:
            # No reset request has been issued yet. Resume the CPU stopped by
            # Break so a failed setup/readback cannot strand the live DUT.
            try:
                T32Python.run_command("Go")
            finally:
                raise
        write_u32(SCU_SWRSTCON, 0x2)  # SWRSTREQ
    time.sleep(2.0)


def run_reset_type_test(reset_type: str, htf_test=None, dry_run: bool = False):
    myTest = tc.Testcase("<testcase-id>", htf_test=htf_test)

    myTest.test_step_start(comment=f"Configuration check (reset type '{reset_type}')")
    if reset_type not in RESET_TYPES:
        myTest.test_step_fail(f"Unknown reset type {reset_type!r} - use warm|system|application")
        return myTest.test_finish()
    _, expected_decode = RESET_TYPES[reset_type]
    myTest.test_step_pass(f"Injection: {reset_type} -> expected decode {expected_decode}")

    # Step 1 - configure TRACE32 before establishing the DUT baseline. TriCore
    # requires Mode Down while changing CPU/core settings, and Mode Down asserts
    # PORST. Release it with NoDebug first; only then bring the DUT to normal
    # operation so this setup pulse cannot contaminate the measured reset.
    myTest.test_step_start(
        comment="Configure TRACE32 safely, release PORST, then bring DUT to normal operation"
    )
    if not t32_rcl_connected():
        T32Python.connect_t32()
        T32Python.wait_for_cmd(10)
    if not t32_rcl_connected():
        myTest.test_step_fail("Could not connect to TRACE32")
        return myTest.test_finish()
    try:
        t32_configure()
    except Exception as e:
        myTest.test_step_fail(f"Could not configure TRACE32 and release PORST: {e!r}")
        return myTest.test_finish()

    generic.normal_operation()
    (swVer, swRev) = generic.get_swver_swrev()
    if swVer is None or swRev is None:
        myTest.test_step_fail("Could not get SW version after TRACE32 configuration")
        return myTest.test_finish()
    myTest.setSwVersion(swVer, swRev)
    myTest.test_step_pass("TRACE32 configured in NoDebug; DUT reached normal operation")

    # Step 2 - baseline + symbols
    myTest.test_step_start(comment="Load symbols (/NoCode), read stored reset-cause baseline")
    t32_attach_no_reset()
    load_symbols_no_flash()
    stored_before = read_var_u32(STORED_RSTSTAT_VAR)
    wstat_before = read_var_u32(STORED_WSTAT_VAR)
    myTest.test_step_pass(
        f"Baseline: stored rstStat={stored_before:#010x} "
        f"({decode_reset_type(stored_before, wstat_before)})"
    )

    if dry_run:
        myTest.test_step_start(comment="DRY RUN - no reset injected, return to Standby")
        myTest.test_step_pass("Dry run complete: attach, symbols, baseline decode all OK")
        t32_detach()
        generic.go_to_standby()
        return myTest.test_finish()

    # Step 3 - inject
    myTest.test_step_start(comment=f"Inject {reset_type} reset via TRACE32")
    # REVIEW (added): on a RERUN of the same type, the stored baseline already
    # decodes to the expected value - if the injection silently does nothing
    # (dropped RCL command, probe glitch), step 5 still sees the leftover
    # stored cause and FALSE-PASSES. Nothing here proves a reboot actually
    # happened. Remedy: capture a reboot witness that must change across the
    # reset (boot counter / uptime via UDS, or a RAM sentinel cleared by the
    # SSW) and assert it changed before trusting the decode.
    try:
        inject_reset(reset_type)
    except Exception as e:
        t32_detach()
        myTest.test_step_fail(f"Reset injection failed before completion: {e!r}")
        return myTest.test_finish()
    myTest.test_step_pass("Reset command issued")

    # Step 4 - wait for reboot, attach fresh, read
    myTest.test_step_start(comment="Wait for reboot, attach fresh, read stored copy + FW-check register set")
    time.sleep(defines.wake_up_time_s)
    # One non-resetting reconnect attempt, then STOP. Retrying a fatal probe is
    # unsafe, and escalating to SYStem.Up/Go or Down would reset the chip and
    # destroy the stored reset-cause evidence this test exists to read.
    rststat_live = None
    try:
        t32_attach_no_reset()
        rststat_live = read_u32(SCU_RSTSTAT)
    except Exception as e:
        myTest.test_step_add_note(f"Non-resetting attach failed ({e!r})")
    if rststat_live is None:
        t32_detach()
        healthy, hmsg = probe_health_ok()
        if healthy:
            myTest.test_step_fail(
                "Target not accessible after reset (one non-resetting attach). Probe itself healthy - "
                "debug port on the target side did not come back."
            )
        else:
            myTest.test_step_fail(
                f"PROBE WEDGED after reset injection - probe command failed ({hmsg}). "
                "Power-cycle the Lauterbach PowerDebug (mains) before ANY further TRACE32 use. "
                "Do not run more TRACE32-dependent tests this slot."
            )
        return myTest.test_finish()

    stored_rststat = read_var_u32(STORED_RSTSTAT_VAR)
    stored_wstat = read_var_u32(STORED_WSTAT_VAR)
    regs = {
        "SCU_RSTSTAT_live": rststat_live,
        "stored_rstStat": stored_rststat,
        "stored_wStat": stored_wstat,
        "SCU_RSTCON": read_u32(SCU_RSTCON),
        "PMS_PMSWSTAT": read_u32(PMS_PMSWSTAT),
        "PMS_PMSWSTAT2": read_u32(PMS_PMSWSTAT2),
        "SCU_LCLCON0": read_u32(SCU_LCLCON0),
        "SCU_LCLCON1": read_u32(SCU_LCLCON1),
    }
    for n in range(4):
        regs[f"SCU_STMEM{3 + n}"] = read_u32(SCU_STMEM3 + n * 4)
    myTest.test_step_add_note(" ".join(f"{k}={v:#010x}" for k, v in regs.items()))
    myTest.test_step_pass(
        f"Register set captured (judged in the next steps): live SCU_RSTSTAT="
        f"{rststat_live:#010x}, stored rstStat={stored_rststat:#010x}, "
        f"stored wStat={stored_wstat:#010x}"
    )

    # Step 5 - decode assertion
    myTest.test_step_start(comment=f"Decode STORED reset cause; expect {expected_decode}")
    decoded = decode_reset_type(stored_rststat, stored_wstat)
    if decoded == expected_decode:
        myTest.test_step_pass(
            f"Decoded {decoded} (stored rstStat={stored_rststat:#010x}) - matches injection"
        )
    else:
        myTest.test_step_fail(
            f"Decoded {decoded}, expected {expected_decode} "
            f"(stored rstStat={stored_rststat:#010x}, wStat={stored_wstat:#010x})"
        )

    # Step 6 - clearing clause (same assertions as the cold-POR test)
    myTest.test_step_start(comment="Clearing clause: live RSTSTAT cleared, SMU alarm groups clear")
    clear_fails = []
    if rststat_live != 0:
        clear_fails.append(f"live SCU_RSTSTAT={rststat_live:#010x} not cleared after evaluation")
    ag_words = [read_u32(SMU_AG_BASE + n * 4) for n in range(12)]
    for n, ag in enumerate(ag_words):
        if ag != 0:
            clear_fails.append(f"SMU_AG{n}={ag:#010x} latched after boot")
    if clear_fails:
        myTest.test_step_fail("Clearing clause violated: " + "; ".join(clear_fails))
    else:
        myTest.test_step_pass(
            f"Clearing clause OK: live SCU_RSTSTAT={rststat_live:#010x} (expected "
            f"0x00000000 - evaluated and cleared by the startup SW) and SMU_AG0..AG11 "
            f"all 0x00000000 (expected clear): "
            + " ".join(f"AG{n}={v:#010x}" for n, v in enumerate(ag_words))
        )

    # Step 7 - normal boot + evidence + recover
    myTest.test_step_start(comment="Verify normal boot after reset (DUT responsive)")
    (swVer2, _) = generic.get_swver_swrev()
    if swVer2 is not None:
        myTest.test_step_pass("DUT booted normally after forced reset")
    else:
        myTest.test_step_fail("DUT not responsive after forced reset")

    date_tag = datetime.now().strftime("%Y%m%d")
    csv_path = Path(__file__).parent / f"fwcheck_{reset_type}_reset__{date_tag}.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["register", "value", "note"])
        w.writerow(["injection_type", reset_type, f"expected decode {expected_decode}"])
        w.writerow(["stored_rstStat_before", f"{stored_before:#010x}", "baseline"])
        for k, v in regs.items():
            w.writerow([k, f"{v:#010x}", decoded if k == "stored_rstStat" else ""])
    myTest.test_step_add_note(f"Register snapshot written: {csv_path}")
    if upload_evidence_csv(myTest, csv_path):
        myTest.test_step_add_note(
            f"Register snapshot uploaded to S3 next to {myTest.default_log_path}"
        )

    # Step 8 - probe-health epilogue: leave the port cleanly detached and prove
    # the PowerDebug still answers. A wedged probe must fail HERE, loudly, not
    # surface as mystery failures in whatever test runs next.
    myTest.test_step_start(comment="Probe-health epilogue: detach cleanly, verify PowerDebug answers")
    t32_detach()
    healthy, hmsg = probe_health_ok()
    if healthy:
        myTest.test_step_pass("Probe healthy, session detached (SYStem.Mode NoDebug)")
    else:
        myTest.test_step_fail(
            f"PROBE WEDGED at test end ({hmsg}). Power-cycle the Lauterbach PowerDebug (mains) "
            "before ANY further TRACE32 use. Do not run more TRACE32-dependent tests this slot."
        )

    generic.go_to_standby()
    return myTest.test_finish()


if __name__ == "__main__":
    # REVIEW (added): hand-rolled argument parsing - "--type" as the LAST
    # argument raises IndexError on the index()+1 lookup, and giving both a
    # positional type and "--type" silently lets "--type" win. Remedy: use
    # argparse with choices=RESET_TYPES and store_true for --dry-run.
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    rtype = args[0] if args else ("warm" if "--type" not in sys.argv else None)
    if "--type" in sys.argv:
        rtype = sys.argv[sys.argv.index("--type") + 1]
    run_reset_type_test(rtype or "warm", dry_run="--dry-run" in sys.argv)


# ---- Transcription note (not part of the original file) --------------------
# Consolidated from 17 phone photos of the original test file, 2026-08-06.
# Coverage is continuous from line 1 to the end of the file (~413 lines in
# the original). Content is faithful; exact line wrapping, blank-line
# placement, and comment wrapping are best-effort from angled/blurry photos.
# Individually uncertain tokens (photo blur):
#   - 'CORE.ASSIGN 1. 2.' argument formatting in t32_configure()
#   - the photographed bit-26 name was corrected to the TC37x manual's HSMS
#     (HSM System Reset); bit 27 is HSMA (HSM Application Reset)
#   - 'msg = T32Python.get_message() or ""' in probe_health_ok()
# Sanitization note: requirement IDs, project codenames, internal test-case
# IDs, and firmware symbol prefixes were replaced with generic placeholders
# (<sysreq-*>, <project-a/b>, <testcase-id>, FwCheckHandle/FwCheck), and the
# internal test-framework import was renamed to hil_utilities. "REVIEW
# (added)" comments are review annotations, not part of the original file.
# ----------------------------------------------------------------------------
