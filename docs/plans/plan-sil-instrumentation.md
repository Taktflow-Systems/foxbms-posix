# Plan: SIL Instrumentation Layer — Probes + Fault Injection via #ifdef

**Date**: 2026-03-21
**Status**: PROPOSED
**Goal**: Compile-time instrumentation that enables probing and overriding any internal foxBMS variable
**Compile flag**: `-DFOXBMS_SIL_PROBES`

---

## Concept

```c
// In any foxBMS source file (via patch):
cell_voltage = database_read(CELL_VOLTAGE, cell_id);

#ifdef FOXBMS_SIL_PROBES
// Override: test harness can force this value via CAN 0x7E0
if (sil_override_active(SIL_CELL_VOLTAGE, cell_id))
    cell_voltage = sil_override_get(SIL_CELL_VOLTAGE, cell_id);
// Probe: publish current value on CAN 0x7Fx
sil_probe(SIL_CELL_VOLTAGE, cell_id, cell_voltage);
#endif

// foxBMS continues with cell_voltage — real or overridden
if (cell_voltage > OV_THRESHOLD) { ... }
```

Production build: `#ifdef` is not defined → zero code, zero overhead.
SIL build: `-DFOXBMS_SIL_PROBES` → full instrumentation active.

---

## Architecture

```
Test Harness / Plant Model (Python)
    |                           |
    | CAN 0x7E0-0x7EF          | CAN 0x7F0-0x7FF
    | (override commands)       | (probe data)
    v                           ^
+--------------------------------------------------+
|  foxbms-vecu  (C binary, -DFOXBMS_SIL_PROBES)   |
|                                                   |
|  sil_layer.c:                                     |
|    sil_override_table[32]  ← written by 0x7E0 RX |
|    sil_probe_send()        → writes to 0x7Fx TX  |
|                                                   |
|  foxBMS application code (patched):               |
|    #ifdef FOXBMS_SIL_PROBES                       |
|      sil_override_active() → check override table |
|      sil_probe()           → send probe CAN frame |
|    #endif                                         |
+--------------------------------------------------+
```

---

## Override Command Channel (CAN 0x7E0–0x7EF)

### Frame format (0x7E0)

```
Byte 0: override_id (which variable to override)
Byte 1: index (cell index, channel number, etc.)
Byte 2: active (1=override, 0=release)
Byte 3-6: value (int32 or float32, little-endian)
Byte 7: reserved
```

### Override IDs

| ID | Variable | Type | Index | Fault injection scenario |
|----|----------|------|-------|--------------------------|
| 0x01 | Cell voltage | int16 mV | cell 0-17 | OV: set cell 5 to 4500mV |
| 0x02 | Cell temperature | int16 ddegC | sensor 0-17 | OT: set sensor 3 to 800 (80°C) |
| 0x03 | Pack current | int32 mA | 0 | OC: set to 200000 (200A) |
| 0x04 | SOC | float32 % | 0 | Force SOC to 5% (test low-SOC behavior) |
| 0x05 | Contactor feedback | uint8 | channel 0-15 | Welding: force ch0 feedback=CLOSED after open command |
| 0x06 | Interlock state | uint8 | 0 | Interlock break: set to OPEN |
| 0x07 | Pack voltage | int32 mV | 0 | Voltage sensor fault: force wrong value |
| 0x08 | DIAG force fault | uint8 | diag_id | Force a specific DIAG ID to NOT_OK |
| 0x09 | DIAG clear fault | uint8 | diag_id | Clear a specific DIAG ID |
| 0x0A | SPS force state | uint8 | channel 0-15 | Force contactor stuck open/closed |
| 0x0B | Current sensor timeout | uint8 | 0 | Simulate IVT communication loss |
| 0x0C | Cell voltage invalid | uint8 | cell 0-17 | Simulate AFE measurement error |
| 0x0D | Balancing force | uint8 | cell 0-17 | Force balancing on/off for specific cell |

### Example: Inject overvoltage on cell 5

```python
# Python test harness:
# Override cell 5 voltage to 4500mV
can_send(0x7E0, struct.pack("<BBBiB", 0x01, 5, 1, 4500, 0))
time.sleep(2)
# Read probe 0x7F7 — verify DIAG fault count increased
# Read probe 0x7F0 — verify contactors opened
# Release override
can_send(0x7E0, struct.pack("<BBBiB", 0x01, 5, 0, 0, 0))
```

---

## Probe Points (injected via patches)

### Where to inject (patch locations in foxBMS source)

| # | File | Function | What to probe | What to override |
|---|------|----------|---------------|-----------------|
| 1 | `bms.c` | `BMS_Trigger()` | State, substate, transition trigger | — |
| 2 | `bms.c` | `BMS_CheckPrecharge()` | string_V, bus_V, delta, threshold, result | Pack voltage (force precharge fail/pass) |
| 3 | `soc_counting.c` | `SOC_CalculateSoc()` | current, delta_As, soc_before, soc_after | SOC value |
| 4 | `cont.c` | `CONT_SetState()` | channel, requested, actual | Contactor feedback (welding sim) |
| 5 | `database.c` | `DATA_IterateOverDatabaseEntries()` | block_id, access_type, first bytes | Cell voltage, temperature (per-cell override) |
| 6 | `soa.c` | `SOA_CheckVoltages()` | cell_v, limit_ov, limit_uv, result | Cell voltage (force OV/UV) |
| 7 | `soa.c` | `SOA_CheckTemperatures()` | cell_t, limit_ot, limit_ut, result | Cell temperature (force OT/UT) |
| 8 | `soa.c` | `SOA_CheckCurrent()` | current, limit_oc, result | Current (force OC) |
| 9 | `redundancy.c` | `MRC_ValidateCellVoltage()` | base_v, redundant_v, delta | — |
| 10 | `can_cbs_rx.c` | After IVT decode | decoded current, voltage, temp | — |

### Patch template

```python
# patch_probe_soa_voltage.py
# Injects probe + override into SOA_CheckVoltages()

import re

with open("src/app/application/config/soa_cfg.c") as f:
    code = f.read()

probe_code = '''
#ifdef FOXBMS_SIL_PROBES
    extern int sil_override_active(uint8_t id, uint8_t idx);
    extern int32_t sil_override_get(uint8_t id, uint8_t idx);
    extern void sil_probe_voltage(uint8_t cell, int32_t voltage_mV, int32_t limit_mV, uint8_t result);
    if (sil_override_active(0x01, cellIndex)) {
        cellVoltage_mV = sil_override_get(0x01, cellIndex);
    }
    sil_probe_voltage(cellIndex, cellVoltage_mV, upperLimit_mV, violation);
#endif
'''

# Insert after the voltage read, before the comparison
old = '/* check cell voltage against limits */'
new = probe_code + '\n    /* check cell voltage against limits */'
# ... apply patch
```

---

## C Implementation: sil_layer.h + sil_layer.c

### sil_layer.h

```c
#ifndef SIL_LAYER_H_
#define SIL_LAYER_H_

#ifdef FOXBMS_SIL_PROBES

#include <stdint.h>

/* Override IDs (match CAN 0x7E0 command byte 0) */
#define SIL_CELL_VOLTAGE    0x01
#define SIL_CELL_TEMP       0x02
#define SIL_PACK_CURRENT    0x03
#define SIL_SOC             0x04
#define SIL_CONTACTOR_FB    0x05
#define SIL_INTERLOCK       0x06
#define SIL_PACK_VOLTAGE    0x07
#define SIL_DIAG_FORCE      0x08
#define SIL_DIAG_CLEAR      0x09
#define SIL_SPS_FORCE       0x0A
#define SIL_IVT_TIMEOUT     0x0B
#define SIL_CELL_INVALID    0x0C
#define SIL_BAL_FORCE       0x0D
#define SIL_MAX_OVERRIDES   0x10

#define SIL_MAX_INDEX       18  /* max cells / channels */

/* Initialize override table */
void sil_init(void);

/* Process incoming override command (called from CAN RX) */
void sil_process_command(const uint8_t *data, uint8_t dlc);

/* Check if override is active */
int sil_override_active(uint8_t override_id, uint8_t index);

/* Get override value */
int32_t sil_override_get(uint8_t override_id, uint8_t index);

/* Send probe data on CAN 0x7Fx */
void sil_probe(uint16_t probe_id, const void *data, uint8_t len);

/* Convenience: send 2 int32 values on one probe frame */
void sil_probe_2i32(uint16_t probe_id, int32_t v1, int32_t v2);

/* Convenience: send 4 int16 values on one probe frame */
void sil_probe_4i16(uint16_t probe_id, int16_t v1, int16_t v2, int16_t v3, int16_t v4);

#else
/* No-op macros when SIL probes disabled */
#define sil_init()
#define sil_process_command(d, l)
#define sil_override_active(id, idx) (0)
#define sil_override_get(id, idx) (0)
#define sil_probe(id, d, l)
#define sil_probe_2i32(id, v1, v2)
#define sil_probe_4i16(id, v1, v2, v3, v4)
#endif

#endif /* SIL_LAYER_H_ */
```

### sil_layer.c (in src/)

```c
#ifdef FOXBMS_SIL_PROBES

#include "sil_layer.h"
#include <string.h>
#include <stdio.h>

extern int posix_can_send(uint32_t id, const uint8_t *data, uint8_t dlc);

/* Override table */
static struct {
    uint8_t  active;
    int32_t  value;
} sil_overrides[SIL_MAX_OVERRIDES][SIL_MAX_INDEX];

void sil_init(void) {
    memset(sil_overrides, 0, sizeof(sil_overrides));
    fprintf(stderr, "[SIL] Probe + override layer initialized (%d overrides × %d indices)\n",
            SIL_MAX_OVERRIDES, SIL_MAX_INDEX);
}

void sil_process_command(const uint8_t *data, uint8_t dlc) {
    if (dlc < 7) return;
    uint8_t override_id = data[0];
    uint8_t index       = data[1];
    uint8_t active      = data[2];
    int32_t value;
    memcpy(&value, &data[3], 4);  /* little-endian int32 */

    if (override_id >= SIL_MAX_OVERRIDES || index >= SIL_MAX_INDEX) return;

    sil_overrides[override_id][index].active = active;
    sil_overrides[override_id][index].value  = value;

    fprintf(stderr, "[SIL] Override 0x%02X[%u] %s value=%d\n",
            override_id, index, active ? "SET" : "CLEARED", value);
}

int sil_override_active(uint8_t override_id, uint8_t index) {
    if (override_id >= SIL_MAX_OVERRIDES || index >= SIL_MAX_INDEX) return 0;
    return sil_overrides[override_id][index].active;
}

int32_t sil_override_get(uint8_t override_id, uint8_t index) {
    if (override_id >= SIL_MAX_OVERRIDES || index >= SIL_MAX_INDEX) return 0;
    return sil_overrides[override_id][index].value;
}

void sil_probe(uint16_t probe_id, const void *data, uint8_t len) {
    uint8_t buf[8] = {0};
    if (len > 8) len = 8;
    memcpy(buf, data, len);
    posix_can_send(0x7F0 + (probe_id & 0x0F), buf, 8);
}

void sil_probe_2i32(uint16_t probe_id, int32_t v1, int32_t v2) {
    uint8_t buf[8];
    memcpy(&buf[0], &v1, 4);
    memcpy(&buf[4], &v2, 4);
    posix_can_send(0x7F0 + (probe_id & 0x0F), buf, 8);
}

void sil_probe_4i16(uint16_t probe_id, int16_t v1, int16_t v2, int16_t v3, int16_t v4) {
    uint8_t buf[8];
    memcpy(&buf[0], &v1, 2);
    memcpy(&buf[2], &v2, 2);
    memcpy(&buf[4], &v3, 2);
    memcpy(&buf[6], &v4, 2);
    posix_can_send(0x7F0 + (probe_id & 0x0F), buf, 8);
}

#endif /* FOXBMS_SIL_PROBES */
```

---

## Integration in existing code

### foxbms_posix_main.c

```c
// CAN RX loop:
#ifdef FOXBMS_SIL_PROBES
if ((rx_frame.can_id & CAN_SFF_MASK) == 0x7E0) {
    sil_process_command(rx_frame.data, rx_frame.can_dlc);
    continue;  // don't inject into foxBMS RX
}
#endif
posix_can_rx_inject(...);

// Init:
#ifdef FOXBMS_SIL_PROBES
sil_init();
#endif

// 100ms block:
#ifdef FOXBMS_SIL_PROBES
sil_probe_2i32(0x02, soc_from_db, current_from_db);  // SOC + current
sil_probe_4i16(0x04, v_min, v_max, v_avg, v_delta);  // cell voltage summary
#endif
```

### hal_stubs_posix.c — SPS probes

```c
void SPS_Ctrl(void) {
    // existing delay logic...
    #ifdef FOXBMS_SIL_PROBES
    // Pack all 16 channel states into 2 bytes
    uint16_t actual = 0, requested = 0;
    for (uint8_t i = 0; i < 16; i++) {
        if (sps_channel_actual_state[i]) actual |= (1u << i);
        if (sps_channel_requested_state[i]) requested |= (1u << i);
    }
    uint8_t probe[8] = {actual & 0xFF, actual >> 8, requested & 0xFF, requested >> 8, 0, 0, 0, 0};
    sil_probe(0x00, probe, 8);  // 0x7F0
    #endif
}
```

### Patched foxBMS files — override injection points

```c
// In SOA voltage check (via patch):
int32_t cellVoltage_mV = pCellVoltage->cellVoltage_mV[s][c];
#ifdef FOXBMS_SIL_PROBES
if (sil_override_active(SIL_CELL_VOLTAGE, c))
    cellVoltage_mV = sil_override_get(SIL_CELL_VOLTAGE, c);
#endif
```

---

## Makefile change

```makefile
# Add to CFLAGS for SIL builds:
CFLAGS += -DFOXBMS_SIL_PROBES

# Add sil_layer.c to POSIX_SRCS:
POSIX_SRCS = hal_stubs_posix.c sil_layer.c
```

---

## Python helper: sil_client.py

```python
class SILClient:
    """Send override commands and read probes via CAN."""

    def override_cell_voltage(self, cell_id, voltage_mv):
        self.can_send(0x7E0, struct.pack("<BBBiB", 0x01, cell_id, 1, voltage_mv, 0))

    def release_cell_voltage(self, cell_id):
        self.can_send(0x7E0, struct.pack("<BBBiB", 0x01, cell_id, 0, 0, 0))

    def override_current(self, current_ma):
        self.can_send(0x7E0, struct.pack("<BBBiB", 0x03, 0, 1, current_ma, 0))

    def override_temperature(self, sensor_id, temp_ddegc):
        self.can_send(0x7E0, struct.pack("<BBBiB", 0x02, sensor_id, 1, temp_ddegc, 0))

    def force_interlock_open(self):
        self.can_send(0x7E0, struct.pack("<BBBiB", 0x06, 0, 1, 0, 0))

    def force_contactor_welded(self, channel):
        self.can_send(0x7E0, struct.pack("<BBBiB", 0x05, channel, 1, 1, 0))

    def read_probe_soc(self):
        """Read 0x7F2 → float32 SOC"""
        frame = self.can_recv_filter(0x7F2)
        return struct.unpack("<f", frame[0:4])[0]

    def read_probe_contactor(self):
        """Read 0x7F0 → 16-bit actual state"""
        frame = self.can_recv_filter(0x7F0)
        return struct.unpack("<H", frame[0:2])[0]
```

---

## Test example: Overvoltage fault injection

```python
sil = SILClient("vcan1")

# 1. Verify system is NORMAL
assert sil.read_probe_bms_state() == 7

# 2. Inject overvoltage on cell 5
sil.override_cell_voltage(5, 4500)  # 4.5V — above MSL threshold

# 3. Wait for DIAG to detect
time.sleep(2)
diag = sil.read_probe_diag()
assert diag.fault_count > 0
assert diag.last_fault_id == 18  # DIAG_ID_CELL_VOLTAGE_OVERVOLTAGE_MSL

# 4. Verify contactors opened
sps = sil.read_probe_contactor()
assert sps == 0  # all channels open

# 5. Verify BMS state is ERROR
assert sil.read_probe_bms_state() in (9, 10)  # ERROR or OPEN_CONTACTORS

# 6. Release override
sil.release_cell_voltage(5)

# 7. Wait for recovery (if configured)
time.sleep(5)
```

---

## Exit Criteria

| # | Criterion | Test |
|---|-----------|------|
| SIL.01 | `sil_init()` prints on startup when `-DFOXBMS_SIL_PROBES` set | stderr log |
| SIL.02 | Override cell voltage via 0x7E0 → foxBMS sees overridden value | Probe 0x7F4 shows override |
| SIL.03 | Release override → foxBMS returns to real value | Probe 0x7F4 shows plant value |
| SIL.04 | Probe 0x7F0 shows contactor state in real-time | candump grep 7F0 |
| SIL.05 | Probe 0x7F2 shows float SOC with full precision | candump + decode |
| SIL.06 | OV fault injection → DIAG count increases (0x7F7) | test_fault_ov.py |
| SIL.07 | No probe traffic when compiled without -DFOXBMS_SIL_PROBES | candump grep 7F shows nothing |
| SIL.08 | test_asil.py 50/50 with SIL probes enabled | Full regression |
