/**
 * @file    sil_layer.c
 * @brief   SIL Instrumentation Layer — probes + overrides
 *
 * Only compiled when -DFOXBMS_SIL_PROBES is set.
 */

#ifdef FOXBMS_SIL_PROBES

#include "sil_layer.h"
#include <string.h>
#include <stdio.h>

/* CAN send function from foxbms_posix_main.c */
extern int posix_can_send(uint32_t id, const uint8_t *data, uint8_t dlc);

/* ================================================================
 * Override table
 * ================================================================ */
typedef struct {
    uint8_t  active;
    int32_t  value;  /* int32 or float32 reinterpreted via memcpy */
} sil_override_entry_t;

static sil_override_entry_t sil_overrides[SIL_MAX_OVERRIDES][SIL_MAX_INDEX];

void sil_init(void) {
    memset(sil_overrides, 0, sizeof(sil_overrides));
    fprintf(stderr, "[SIL] Instrumentation layer initialized "
            "(%u overrides × %u indices, probes on 0x7F0–0x7FF, "
            "commands on 0x7E0)\n",
            (unsigned)SIL_MAX_OVERRIDES, (unsigned)SIL_MAX_INDEX);
    fflush(stderr);
}

void sil_process_command(const uint8_t *data, uint8_t dlc) {
    if (dlc < 7u) return;

    uint8_t override_id = data[0];
    uint8_t index       = data[1];
    uint8_t active      = data[2];
    int32_t value;
    memcpy(&value, &data[3], 4);  /* little-endian */

    if (override_id >= SIL_MAX_OVERRIDES || index >= SIL_MAX_INDEX) {
        return;  /* silently ignore invalid — NEG tests verify no crash */
    }

    sil_overrides[override_id][index].active = active;
    sil_overrides[override_id][index].value  = value;

    if (active) {
        fprintf(stderr, "[SIL] Override 0x%02X[%u] SET value=%d\n",
                override_id, index, value);
    } else {
        fprintf(stderr, "[SIL] Override 0x%02X[%u] CLEARED\n",
                override_id, index);
    }
    fflush(stderr);
}

int sil_override_active(uint8_t override_id, uint8_t index) {
    if (override_id >= SIL_MAX_OVERRIDES || index >= SIL_MAX_INDEX) return 0;
    return sil_overrides[override_id][index].active;
}

int32_t sil_override_get_i32(uint8_t override_id, uint8_t index) {
    if (override_id >= SIL_MAX_OVERRIDES || index >= SIL_MAX_INDEX) return 0;
    return sil_overrides[override_id][index].value;
}

float sil_override_get_f32(uint8_t override_id, uint8_t index) {
    int32_t raw = sil_override_get_i32(override_id, index);
    float f;
    memcpy(&f, &raw, sizeof(f));
    return f;
}

/* ================================================================
 * Probe send
 * ================================================================ */
void sil_probe_raw(uint8_t probe_id, const uint8_t *data, uint8_t len) {
    uint8_t buf[8] = {0};
    if (len > 8u) len = 8u;
    memcpy(buf, data, len);
    posix_can_send(0x7F0u + (uint32_t)(probe_id & 0x0Fu), buf, 8u);
}

void sil_probe_2i32(uint8_t probe_id, int32_t v1, int32_t v2) {
    uint8_t buf[8];
    memcpy(&buf[0], &v1, 4);
    memcpy(&buf[4], &v2, 4);
    posix_can_send(0x7F0u + (uint32_t)(probe_id & 0x0Fu), buf, 8u);
}

void sil_probe_4i16(uint8_t probe_id, int16_t v1, int16_t v2, int16_t v3, int16_t v4) {
    uint8_t buf[8];
    memcpy(&buf[0], &v1, 2);
    memcpy(&buf[2], &v2, 2);
    memcpy(&buf[4], &v3, 2);
    memcpy(&buf[6], &v4, 2);
    posix_can_send(0x7F0u + (uint32_t)(probe_id & 0x0Fu), buf, 8u);
}

void sil_probe_4u16(uint8_t probe_id, uint16_t v1, uint16_t v2, uint16_t v3, uint16_t v4) {
    uint8_t buf[8];
    memcpy(&buf[0], &v1, 2);
    memcpy(&buf[2], &v2, 2);
    memcpy(&buf[4], &v3, 2);
    memcpy(&buf[6], &v4, 2);
    posix_can_send(0x7F0u + (uint32_t)(probe_id & 0x0Fu), buf, 8u);
}

void sil_probe_heartbeat(uint32_t tick, uint32_t uptime_ms) {
    uint8_t buf[8];
    memcpy(&buf[0], &tick, 4);
    memcpy(&buf[4], &uptime_ms, 4);
    posix_can_send(0x7FFu, buf, 8u);
}

#endif /* FOXBMS_SIL_PROBES */
