/**
 * @file    sil_layer.h
 * @brief   SIL Instrumentation Layer — probes (read) + overrides (write)
 *
 * Compile with -DFOXBMS_SIL_PROBES to enable.
 * Without the flag, all functions become no-op macros (zero overhead).
 *
 * Probes:    CAN 0x7F0–0x7FF — internal state broadcast
 * Overrides: CAN 0x7E0       — intercept pipeline stages
 */

#ifndef SIL_LAYER_H_
#define SIL_LAYER_H_

#ifdef FOXBMS_SIL_PROBES

#include <stdint.h>

/* Override IDs (byte 0 of 0x7E0 command frame) */
#define SIL_CELL_VOLTAGE    0x01u
#define SIL_CELL_TEMP       0x02u
#define SIL_PACK_CURRENT    0x03u
#define SIL_SOC             0x04u
#define SIL_CONTACTOR_FB    0x05u
#define SIL_INTERLOCK       0x06u
#define SIL_PACK_VOLTAGE    0x07u
#define SIL_DIAG_FORCE      0x08u
#define SIL_DIAG_CLEAR      0x09u
#define SIL_SPS_FORCE       0x0Au
#define SIL_IVT_TIMEOUT     0x0Bu
#define SIL_CELL_INVALID    0x0Cu
#define SIL_BAL_FORCE       0x0Du
#define SIL_MAX_OVERRIDES   0x10u
#define SIL_MAX_INDEX       18u

/* Probe IDs (offset from 0x7F0) */
#define SIL_PROBE_SPS_STATE       0x00u  /* 0x7F0 */
#define SIL_PROBE_SPS_PENDING     0x01u  /* 0x7F1 */
#define SIL_PROBE_SOC             0x02u  /* 0x7F2 */
#define SIL_PROBE_SOC_INTEGRATOR  0x03u  /* 0x7F3 */
#define SIL_PROBE_CELL_V_SUMMARY  0x04u  /* 0x7F4 */
#define SIL_PROBE_PACK_V          0x05u  /* 0x7F5 */
#define SIL_PROBE_CELL_T_SUMMARY  0x06u  /* 0x7F6 */
#define SIL_PROBE_DIAG            0x07u  /* 0x7F7 */
#define SIL_PROBE_DIAG_BITMAP     0x08u  /* 0x7F8 */
#define SIL_PROBE_STATE_MACHINE   0x09u  /* 0x7F9 */
#define SIL_PROBE_CURRENT         0x0Au  /* 0x7FA */
#define SIL_PROBE_TIMING          0x0Bu  /* 0x7FB */
#define SIL_PROBE_DB_COUNTERS     0x0Cu  /* 0x7FC */
#define SIL_PROBE_HEARTBEAT       0x0Fu  /* 0x7FF */

void sil_init(void);
void sil_process_command(const uint8_t *data, uint8_t dlc);
int  sil_override_active(uint8_t override_id, uint8_t index);
int32_t sil_override_get_i32(uint8_t override_id, uint8_t index);
float   sil_override_get_f32(uint8_t override_id, uint8_t index);
void sil_probe_raw(uint8_t probe_id, const uint8_t *data, uint8_t len);
void sil_probe_2i32(uint8_t probe_id, int32_t v1, int32_t v2);
void sil_probe_4i16(uint8_t probe_id, int16_t v1, int16_t v2, int16_t v3, int16_t v4);
void sil_probe_4u16(uint8_t probe_id, uint16_t v1, uint16_t v2, uint16_t v3, uint16_t v4);
void sil_probe_heartbeat(uint32_t tick, uint32_t uptime_ms);

#else /* FOXBMS_SIL_PROBES not defined */

#define sil_init()                              ((void)0)
#define sil_process_command(d, l)               ((void)0)
#define sil_override_active(id, idx)            (0)
#define sil_override_get_i32(id, idx)           (0)
#define sil_override_get_f32(id, idx)           (0.0f)
#define sil_probe_raw(id, d, l)                 ((void)0)
#define sil_probe_2i32(id, v1, v2)              ((void)0)
#define sil_probe_4i16(id, v1, v2, v3, v4)      ((void)0)
#define sil_probe_4u16(id, v1, v2, v3, v4)      ((void)0)
#define sil_probe_heartbeat(t, u)               ((void)0)

#endif /* FOXBMS_SIL_PROBES */
#endif /* SIL_LAYER_H_ */
