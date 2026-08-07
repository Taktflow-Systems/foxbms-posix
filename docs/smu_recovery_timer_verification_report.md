
`SMU_RecoveryTimer_Alarm_AutoStop.py` (`<hil-test-repo>`)

---

## 1. What the ticket is about

**`<ticket-id>`** — "AURIX SMs: Investigate in SMU recovery timer usage [and close safety gaps] related to SM[HW]:SMU:RT" — is a **Feature** ticket (not a bug), reported by the safety lead, assigned to the implementer, currently in ticket status **"Under Review"**.

### The safety gap

AURIX TC377's SMU (System Monitoring Unit) has two hardware **Recovery Timers**, RT0 and RT1. These are a distinct safety mechanism from the SMU's ordinary alarm-to-FSP (Fail Safe Pattern) chain that this project's other Aurix SM tests already cover (four existing tests, evidence folder `p02_smu_alarm_mapping`). The label `SM[HW]:SMU:RT` is a formally tracked safety-mechanism entry in this project's requirement label set.

The mechanism, per the implementer's own explanation in the ticket (comment, 2026-07-16):

> An alarm (preconfigured for the Recovery Timer) triggers the RT and the timer starts. The SW needs to stop it or reset it, otherwise the timer expires and causes a shutdown (as long as FSP has been set). So: enable RT, map it to alarm events *other than the timers themselves*, configure it to fire on interrupt, stop/reset the timer when the alarm is handled, and enable FSP so an unstopped timer forces a reset.

In other words: **RT0/RT1 are a watchdog on the software's own fault-handling.** It's not enough for the SW to detect a fault — the RT proves the SW actually *reacted* to it in time. If the reaction path breaks (interrupt handler bug, task starvation, etc.), the RT itself becomes the backstop that forces a safe shutdown.

**The gap:** before this ticket, RT0 and RT1 existed in configuration but were **disabled** (`SmuCoreEnableRT0/RT1 = SMU_RT_DISABLE`) and had **no alarms mapped to them** (`SmuCoreRT0Alarm`/`SmuCoreRT1Alarm` were empty). A real hardware safety mechanism was sitting inert.

### Discussion thread (chronological)

1. **2026-07-16, the implementer** — lays out the concept above, flags the open question of *which* alarm events should map to which timer, and asks the systems team to weigh in.
2. **2026-07-17, the safety lead** — proposes linking RTs to the project's existing `SW:SUPER_VISION` concept: since every alarm already routes to `SMU_INT0/1/2`, servicing the RTs from the SBC driver's notification handlers (where those interrupts already land) should be sufficient. Raises a follow-up: if the RT reaction itself becomes "unserviced," does the system need a `SYSTEMRESET` reaction rather than just another interrupt?
3. **2026-07-17, the implementer** — notes a hardware constraint: **only 4 alarms can be mapped per RT**. Recommends mapping alarms that *don't already have their own FSP reaction* — the RT's job is specifically to catch faults that would otherwise go unhandled silently.
4. **2026-07-31, the implementer** — reports the implementation is done and manually verified with a debugger: alarms mapped, RT-stop path wired into the SBC driver's alarm-handling, confirmed with the debugger that the mapped alarms are set and that the diagnostic event traces back to the underlying trigger. Explicitly asks the report author whether that manual verification "makes sense" and is "enough to prove that we actually trigger the recovery timer reactions appropriately" — i.e., asking whether an automated HIL test is warranted. This is the origin of today's work.

## 2. What the fix (PR `<pr-id>`) actually does

**PR `<pr-id>`**, title *"`<ticket-id>` feat: Recovery timer setup and check"*, branch `feature/<ticket-id>-aurix-SM-recovery-timers`, author/merger the implementer, six reviewers (two approvals recorded). **State: MERGED**, merge commit `<merge-commit>` into `master`.

Two files change the actual behavior:

### `src/mcal/tresosprojectHigh/config/Smu.xdm` (MCAL configuration)

- `SmuCoreEnableRT0` / `SmuCoreEnableRT1`: `SMU_RT_DISABLE` → **`SMU_RT_ENABLE`**.
- `SmuCoreRTDuration`: `16383` → **`1000000`** (timer ticks; confirmed live on hardware today as `RTD=0xf4240` = 1,000,000).

> **REVIEW (added):** `RTD = 1,000,000` ticks is only meaningful next to the RT clock, which this report never pins down. Per the TC3xx Part1 UM (SMU ch. 15), the recovery timers count `FSMU_FS = fBACK / 2^(PRE1+1)` (`FSP.PRE1`, fBACK ≈ 100 MHz, minimum divider 2) — so at the default prescaler `RTD = 1,000,000` is **20 ms**, only a 2× margin over the 10 ms `SbcDriver_Task()` service cycle below: an alarm landing just after a task tick is stopped up to one full cycle plus ISR latency later. Remedy: live-read `FSP.PRE1`, compute the actual expiry time, and check the worst-case stop latency (one service period + interrupt latency + any task jitter) against it; if the margin is thin, the *configuration value* — not the test — is the finding to raise.

- **RT0 alarm map** (`SmuCoreRT0Alarm`): `GROUP6_ALARM18`, `GROUP7_ALARM30`, `GROUP8_ALARM22` (plus a duplicate `GROUP6_ALARM18` entry — 4 slots used, one redundant).
- **RT1 alarm map** (`SmuCoreRT1Alarm`): `GROUP10_ALARM18`, `GROUP10_ALARM22` (listed twice), `GROUP11_ALARM12`.

> **REVIEW (added):** the duplicate entries (`GROUP6_ALARM18` twice on RT0, `GROUP10_ALARM22` twice on RT1) waste two of the hard-limited 4 slots per RT that the discussion itself flagged as the scarce resource. Remedy: ask the implementer whether the duplicates are intentional; if not, two more distinct not-otherwise-FSP-covered alarms could take those slots.

- A few pre-existing `SmuCoreAlarmBehavior` entries change their interrupt routing (`SMU_IGCS1_INT_ACTION` → `SMU_IGCS0_INT_ACTION` / `SMU_NA_INT_ACTION`) and two entries flip `SmuCoreAlarmFSP` from `DISABLED` to `ENABLED` — these look like the concrete outcome of the implementer's "only alarms without their own FSP reaction" rule, redirecting some alarms' behavior now that they're covered by a Recovery Timer instead.
- Generated files (`Smu_PBcfg.c`, `Smu_Cfg.h`) reflect the same changes at the register-config level (`RTC`, `RTAC00/01/10/11` fields now populated; previously all zero).

### `src/bsw/src/middleware/SBC/SbcDriver.c` (application driver)

- New constants: bitmasks for each of the six mapped alarms (`SMU_GROUP6_ALARM18_MASK`, etc.) and `SMU_RECOVERY_TIMER_0/1` IDs.
- New static flags `areRT0relatedAlarmsHandled` / `areRT1relatedAlarmsHandled`, cleared at boot.
- New function `SbcDriverLocal_SMU_checkRTStatus()`, called **every `SbcDriver_Task()` cycle (10 ms)**: if either flag is set, it calls `SbcDriverLocal_SMU_stopRT(rtID)` — which invokes the MCAL's `Smu_RTStop()` — and clears the flag.
- `SbcDriverLocal_SMU_Interrupt_1_Notification()` (SMU interrupt line 1, where the RT-mapped alarms are routed) now checks the live alarm-status bits for Groups 6/7/8 (→ sets the RT0 flag) and Groups 10/11 (→ sets the RT1 flag) in addition to its pre-existing behavior of setting `isTransitionProhibitFaultPresent = true` unconditionally.
- `SbcDriverLocal_SMU_Interrupt_2_Notification()` additionally checks `GROUP10_ALARM18` to set the RT1 flag.

> **REVIEW (added):** `areRT0/1relatedAlarmsHandled` are plain flags set in interrupt context and consumed (checked, then cleared) in 10 ms task context. A second mapped alarm arriving between the task's `Smu_RTStop()` call and its flag-clear is absorbed by the clear while its restarted RT keeps counting — the next cycle sees no flag and never stops that RT, so it expires into the FSP shutdown even though the SW *did* service the alarm. That is a safe-side failure (spurious shutdown, not a missed fault) but still an availability defect. Remedy: verify the check-and-clear is atomic against the notifications (interrupt lock or clear-before-stop ordering plus a re-check), or document why a lost set cannot occur.

**End-to-end intent:** a mapped alarm fires → its interrupt notification runs, sets the "handled" flag → within one 10 ms task cycle, `SbcDriverLocal_SMU_checkRTStatus()` calls `Smu_RTStop()` → the RT is stopped before it can expire. If any link in that chain breaks, the RT keeps counting, expires, and (since FSP is enabled on the RT's own escalation alarm, Group10 ALM16/17 per the implementer's later ticket comment) forces a shutdown via the unsafe-supply diagnostic event (`<de-unsafe-shutdown>`).

## 3. What today's session did and found

### Test authored: `SMU_RecoveryTimer_Alarm_AutoStop.py`

New HIL test in `<hil-test-repo>`'s manual Aurix safety-measures area, modeled on the existing SMU register-test pattern (TRACE32 RCL, non-intrusive attach, register read/poll, evidence CSV). It checks two things:

1. **Config live-check** (no fault injection): reads live `SMU_RTC` and confirms `RT0E=1`, `RT1E=1`, and the configured duration — proving the enable/config half of the fix actually landed in a running build.
2. **Fault-path check** (original design): writes an RT-mapped alarm bit directly via TRACE32 debug-port access, then polls `SMU_STS`'s RT-missed-event bits. Post-session technical review found two problems with this design: an `SMU_AGx` write must satisfy the register's access conditions and must be performed while the SMU is in START, and the `RTME0/1` bits do not prove that a recovery timer started or was stopped. The corrected test oracle is defined in Section 4.

### What was verified live on hardware (`<project-b>` rig, 2026-08-06)

- Rig had drifted to a stale, config-mismatched firmware (config-mismatch diagnostic event `<de-config-invalid>`) before this session started — unrelated pre-existing issue, not caused by this work.
- Confirmed the PR is merged into `master` (merge commit `<merge-commit>`) and is an ancestor of all three currently-retained master CI builds on S3.
- Flashed the newest retained build (`<build-id>`) + its exactly-hash-matched base config (firmware `.elf`, config `.bin`/`.dat`/`.hex`, all verified against the CI job's `SHA256SUMS`) via JTAG. This resolved the pre-existing `<de-config-invalid>`.
- **Config live-check PASSED on real hardware**: `SMU_RTC = 0x0f424003` → RT0E=1, RT1E=1, RTD=1,000,000 — an exact match to the PR's configured values. This is solid, hardware-confirmed proof that the enable/config half of the ticket is live in this build.
- **Fault-injection step FAILED — a real hardware finding, not a script bug**: writing directly to `SMU_AG8` (the raw alarm-status register for the group RT0's test alarm lives in) via TRACE32 `Data.Set` produced a genuine **bus error** (`bus error at address ED:0xF00369E0`). `SMU_AG8` is at the expected address (`SMU` base `0xF0036800` + offset `0x1E0`), but the bus error alone does not identify which access condition failed. The leading hypothesis is that `SMU_ACCEN0` did not authorize the Cerberus/DAP master TAG (TAG ID 28). The exact `Data.Set` width, supervisor access, Safety-ENDINIT handling, and `SMU_ACCEN0.EN28` were not captured and remain alternative or contributing explanations. A permitted write in SMU RUN state would be ignored rather than bus-errored, so RUN-state semantics are a separate blocker, not the cause of this bus acknowledgement.
- DUT was left in a fully safe, coherent state after the failed injection (SMU still RUN, no alarm latched, no hang) and was returned to Standby with TRACE32 cleanly disconnected at end of session.

### Open question / next step

The implementer's 2026-07-31 ticket comment shows they *did* successfully observe an alarm being set and the diagnostic event tracing to the trigger using a debugger — meaning some injection method does work. Today's session ruled out the attempted raw `Data.Set` path with concrete hardware evidence; independent of the bus error, a direct AG write while the SMU is in RUN cannot perform the desired injection. **The exact mechanism the implementer used (screenshots, commands, SMU state, access width, and whether target CPU code executed the write) needs to be pulled before the fault-injection half of the new test is finalized.**

## 4. Technical verification and corrected test strategy

This section records the post-session verification of the working hypotheses against the TC37x register manual, Infineon's SMU test guidance, the official TC3xx iLLD, the TRACE32 TriCore debugger manual, and the TC37x errata sheet.

### 4.1 Why the `Data.Set` access failed

The observed bus error is consistent with an access-protection failure, but the current evidence does not prove that the debugger's master TAG was the rejected condition:

- `SMU_AG8` is correctly addressed at `0xF00369E0` and requires a 32-bit supervisor/access-protected, Safety-ENDINIT-protected write.
- Cerberus/DAP uses bus-master TAG ID 28. If `SMU_ACCEN0.EN28 == 0`, its write is terminated with an error acknowledgement. This is the leading explanation and is directly testable by reading `SMU_ACCEN0`.
- The exact `Data.Set` command and transfer width must be retained in the evidence. A non-32-bit access is not valid for this register.
- Capture the TRACE32 ENDINIT-override option state. TRACE32 can automatically override ENDINIT protection for eligible segment-F writes, so an ENDINIT failure must not be assumed without recording this setting and the resulting target state.
- Capture `SMU_DBG.SSM`. If access protection is satisfied but the SMU is in RUN, the AG write is ignored. RUN state does not explain the bus error; it explains why an otherwise accepted write would still fail to inject the alarm.

The immediate discriminator for the next session is therefore: read `SMU_ACCEN0`, check bit 28, record the exact 32-bit command and ENDINIT-override setting, and record `SMU_DBG.SSM` before writing anything.

### 4.2 SMU state and injection semantics

Infineon's documented hardware-alarm test method is to leave the SMU in START, set the desired `SMU_AGx` bit, and then execute the intended alarm-reaction sequence. Direct AG writes in RUN are ignored.

The CPU-context and command paths are not interchangeable:

- In START, `IfxSmu_setAlarmStatus()` clears Safety ENDINIT and writes the selected `AG[group]` bit. A TRACE32 `Var.Call` or a small CPU-executed RAM stub can use this path, provided the test controls the SMU START state and all normal startup consequences.
- In RUN/FAULT, `IfxSmu_setAlarmStatus()` uses the SMU command mechanism. That mechanism can trigger only software alarms `GROUP10_ALARM0..15`; it cannot set an arbitrary hardware alarm group.
- None of the RT mappings can be correctly injected through that RUN command path. Alarm positions 18, 22, and 30 are outside the software-alarm range. `GROUP11_ALARM12` would address software-alarm position 12 in Group 10 rather than the requested Group 11 alarm.
- A firmware test hook that merely calls `IfxSmu_setAlarmStatus()` while the production firmware is in RUN has the same limitation. Such a hook must instead invoke a genuine module-specific fault mechanism or be part of a controlled START-state test sequence.

### 4.3 Identities of the mapped alarms

The mapped alarms are not generic software alarms:

| Recovery timer | Mapping | TC37x monitored condition |
|---|---|---|
| RT0 | `GROUP6_ALARM18` | CAN SRAM miscellaneous/latent-error monitor |
| RT0 | `GROUP7_ALARM30` | PFlash `FLASHCON` configuration monitor |
| RT0 | `GROUP8_ALARM22` | Interrupt monitor configuration/data-path error |
| RT1 | `GROUP10_ALARM18` | FSP error-pin fault-state activation |
| RT1 | `GROUP10_ALARM22` | Access-enable protection error |
| RT1 | `GROUP11_ALARM12` | Converter phase-synchronizer error |

`GROUP6_ALARM18` is SRAM-related but is not the ordinary CAN SRAM correctable- or uncorrectable-ECC alarm; those use Group 6 alarm positions 16 and 17. Generic ECC injection would therefore prove the wrong alarm path. A genuine-fault test remains the strongest safety-case evidence, but each selected alarm requires a safe, module-specific injection mechanism.

The candidate routes, in evidence order, are:

1. **Provoke the genuine monitored condition.** This best represents the production path. First identify a safe module-specific test or error-injection mechanism for one RT0 alarm and one RT1 alarm.
2. **Controlled START-state AG injection executed by a CPU.** Use `Var.Call`, a CPU-executed RAM stub, or equivalent target code so that the access carries a CPU TAG and performs the required protection sequence. This route is valid only while the SMU is genuinely in START; CPU context alone does not make an AG write valid in RUN.
3. **Purpose-built firmware test hook.** Use only if the hook invokes the genuine monitor or participates in a controlled START-state injection. A RUN-state wrapper around `IfxSmu_setAlarmStatus()` is insufficient for these mappings.
4. **Direct debug-port AG write.** Use only as a fallback, in START, with a 32-bit access and with the debugger TAG, access protection, and ENDINIT behavior explicitly verified. This is the weakest safety-case evidence because the injection path bypasses the real fault source.

### 4.4 Correct oracle for the auto-stop path

`SMU_STS.RTME0/1` is a missed-*event* indication: it reports that another alarm requiring that recovery timer occurred while the timer was already running. It does not indicate RT expiry, and it does not prove that the timer started or stopped. `RTME=0` is also compatible with the timer never starting.

The automated test must instead prove this sequence for each timer:

1. Record the target alarm as inactive and `SMU_STS.RTSx == 0`.
2. Inject the correct mapped alarm and prove that its AG bit becomes active.
3. Prove that `SMU_STS.RTSx` transitions from 0 to 1.
4. Prove that the expected SMU interrupt/diagnostic handler runs.
5. Prove that `Smu_RTStop()` is issued and `RTSx` returns to 0 before expiry.
6. Prove that the RT timeout alarm (`GROUP10_ALARM16` for RT0 or `GROUP10_ALARM17` for RT1), its FSP reaction, and the shutdown/reset chain do not occur during this serviced-path test.

Because the application may stop the RT within one 10 ms task cycle, debugger polling alone can miss the `RTSx == 1` interval. Use target trace, a breakpoint/tracepoint at `SbcDriverLocal_SMU_checkRTStatus()` or immediately before `Smu_RTStop()`, or another timestamped observation that does not alter the behavior being claimed.

### 4.5 No-code-change expiry-path test

The earlier conclusion that expiry cannot be tested without a firmware change is too strong. A debugger can prevent the software stop while leaving the SMU running, subject to the module's debug-suspend configuration:

1. Read and retain `SMU_OCS.SUS` and `SMU_OCS.SUSSTA`.
2. Ensure halting the CPU does not suspend the SMU. In TRACE32 this normally requires `SYStem.Option.PERSTOP OFF`, unless the live OCS configuration already proves that the SMU ignores the peripheral-suspend signal.
3. Inject a mapped alarm and prove `SMU_STS.RTSx == 1`.
4. Break immediately before `Smu_RTStop()` and halt every CPU that could service the path.
5. Wait longer than the configured RT duration while observing that the SMU continues running.
6. Prove the corresponding timeout alarm (`GROUP10_ALARM16/17`), configured alarm reaction, FSP assertion, external PMIC/shutdown behavior, diagnostic event, and reset source.

> **REVIEW (added):** halting every CPU for longer than the RT duration also stops servicing of every *other* watchdog in the system (external SBC window watchdog, internal WDTs). If one of them bites first, the observed shutdown/reset is not attributable to RT expiry. Remedy: before running this, enumerate the live watchdog timeouts in that configuration and either confirm they exceed the RT duration with margin, or capture their trip evidence separately (the checklist's `SCU_RSTSTAT` capture helps; pin the external FSP/PMIC observation to a timestamp) so the reset source can be discriminated.

Before this test, live-read the configured `RTAC00/01/10/11` mappings and the Group 10 alarm-reaction/FSP fields for alarms 16 and 17. `SMU_RTC` alone proves enablement and duration, not the live mappings or expiry reaction chain.

Erratum `OCDS_TC.H015` must be considered if expiry causes a system/application reset while a lockstep-enabled CPU is halted with debugging enabled: that combination can create a spurious lockstep alarm. It does not apply if the resulting external safety reaction asserts PORST. Record `SCU_RSTSTAT` and the alarm state so that the reset source and any secondary lockstep alarm can be classified. `OCDS_TC.H018` is also relevant if CPU0 is halted across a system/application reset because startup software can stop again on the retained debug state.

### 4.6 Register-level evidence checklist

Capture these values before and after each attempt:

- `SMU_DBG.SSM`
- `SMU_ACCEN0`, especially `EN28` for Cerberus/DAP
- SMU key/protection state and the TRACE32 ENDINIT-override setting
- `SMU_RTC`
- `SMU_RTAC00`, `SMU_RTAC01`, `SMU_RTAC10`, `SMU_RTAC11`
- `SMU_STS.RTS0/1` and `RTME0/1`
- The selected target `SMU_AGx` bit
- Group 10 alarm-reaction and FSP configuration for alarms 16 and 17
- `SMU_OCS.SUS` and `SUSSTA`
- `SCU_RSTSTAT` and external FSP/PMIC observations for an expiry test
- Exact TRACE32 commands, access class, transfer width, breakpoints, and CPU run/halt state

Primary references:

- [AURIX TC37x User's Manual Appendix](https://www.infineon.com/assets/row/public/documents/10/44/infineon-aurix-tc37x-usermanual-en.pdf)
- [Infineon SMU alarm-test guidance](https://documentation.infineon.com/aurixtc3xx/docs/owq1745576218449)
- [Infineon TC3xx iLLD `IfxSmu_setAlarmStatus()` implementation](https://github.com/Infineon/illd_release_tc3x/blob/ac8fb805633894b89819b953516b4e94387056fd/src/BaseSw/iLLD/TC3xx/Tricore/Smu/Std/IfxSmu.c#L297)
- [Infineon TC3xx iLLD recovery-timer API documentation](https://github.com/Infineon/illd_release_tc3x/blob/ac8fb805633894b89819b953516b4e94387056fd/src/BaseSw/iLLD/TC3xx/Tricore/Smu/Std/IfxSmu.h#L504)
- [TRACE32 TriCore Debugger manual](https://repo.lauterbach.com/pdf/debugger_tricore.pdf)
- [AURIX TC37x errata sheet](https://www.infineon.com/dgdl/Infineon-AURIX_TC37x_AA-Step-ErrataSheet-v02_04-EN.pdf?fileId=5546d4627506bb320175229e8e3c68ad)

## 5. Summary table

| Item | Status |
|---|---|
| RT0/RT1 enabled in config | ✅ Confirmed live on hardware (2026-08-06) |
| RT0/RT1 alarm mapping present in config | ✅ Confirmed via source/diff review |
| RT duration matches spec | ✅ Confirmed live (`RTD=1,000,000`) |
| SW auto-stop logic exists (`SbcDriverLocal_SMU_checkRTStatus`) | ✅ Confirmed via code review |
| Live `RTAC00/01/10/11` mappings | ⚠️ Not yet captured; source/diff review is not a live-register check |
| Original `RTME`-based auto-stop oracle | ❌ Invalid — `RTME` reports a second mapped event while the timer is running, not timer start/stop |
| SW auto-stop logic proven live via automated fault injection | ❌ Not yet — attempted debugger write bus-errored, and direct AG injection in RUN is invalid even if access succeeds |
| Exact cause of the debugger bus error | ⚠️ Leading hypothesis is `SMU_ACCEN0.EN28 == 0`; access width, ENDINIT handling, and live access state still need capture |
| RT *expiry* path (unserviced → FSP → shutdown) | ⚠️ Not attempted; potentially testable without a firmware change by halting before `Smu_RTStop()` while ensuring the SMU is not debug-suspended |
| Requirements traceability (`<sysreq>` ID for `SM[HW]:SMU:RT`) | ❌ Not found in anything reviewed — needs confirming [row cut off at bottom of last photo] |

<!--
Transcription note: consolidated from 8 photos of the original recovery-timer
verification report, 2026-08-06. Overlapping scroll regions were merged. The
final summary-table row was cut off at the bottom edge of the last photo and
ends mid-sentence at "needs confirming"; anything after that row (if it
exists) is not captured.
Sanitization note: personal names were replaced with roles (the implementer,
the safety lead, the report author), and ticket/PR/build/commit identifiers,
project codenames, diagnostic-event IDs, and internal repo names were
replaced with <angle-bracket> placeholders. "REVIEW (added)" blockquotes are
review annotations, not part of the original report.
-->
