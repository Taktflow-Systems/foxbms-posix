"""
Phase 3: Deep fault injection at database READ path.

After DATA_IterateOverDatabaseEntries copies data from the internal
database to the caller's struct (READ operation), this patch checks
for active SIL overrides and modifies the returned data in-place.

This means every foxBMS module that reads from the database
(SOA, BMS, algorithm, redundancy) sees the overridden value.

Injection points:
- DATA_BLOCK_ID_MIN_MAX: override min/max cell voltage and temperature
- DATA_BLOCK_ID_PACK_VALUES: override string/pack current
- DATA_BLOCK_ID_CELL_VOLTAGE: override individual cell voltages
- DATA_BLOCK_ID_CELL_TEMPERATURE: override individual cell temperatures

Idempotent: checks for sentinel before patching.
"""

import sys

TARGET = "src/app/engine/database/database.c"
SENTINEL = "/* SIL: deep fault injection at DB read */"

# Code to insert after DATA_CopyData on READ path
INJECT_CODE = '''
#ifdef FOXBMS_SIL_PROBES
            ''' + SENTINEL + '''
            if (accessType == DATA_READ_ACCESS) {
                extern int sil_override_active(uint8_t type, uint8_t index);
                extern int32_t sil_override_get_i32(uint8_t type, uint8_t index);

                /* Override cell voltages in MIN_MAX block */
                if (uniqueId == (uint8_t)DATA_BLOCK_ID_MIN_MAX) {
                    DATA_BLOCK_MIN_MAX_s *pMM = (DATA_BLOCK_MIN_MAX_s *)pPassedDataStruct;
                    for (uint8_t s = 0u; s < BS_NR_OF_STRINGS; s++) {
                        /* Cell voltage override: find min/max from overrides */
                        int16_t ov_min = 32767;
                        int16_t ov_max = -32768;
                        uint8_t any_v_override = 0u;
                        for (uint8_t c = 0u; c < BS_NR_OF_CELL_BLOCKS_PER_MODULE; c++) {
                            if (sil_override_active(0x01u, c)) {
                                int16_t v = (int16_t)sil_override_get_i32(0x01u, c);
                                if (v < ov_min) ov_min = v;
                                if (v > ov_max) ov_max = v;
                                any_v_override = 1u;
                            }
                        }
                        if (any_v_override != 0u) {
                            /* If override min is lower than DB min, use override */
                            if (ov_min < pMM->minimumCellVoltage_mV[s]) {
                                pMM->minimumCellVoltage_mV[s] = ov_min;
                            }
                            /* If override max is higher than DB max, use override */
                            if (ov_max > pMM->maximumCellVoltage_mV[s]) {
                                pMM->maximumCellVoltage_mV[s] = ov_max;
                            }
                        }

                        /* Temperature override */
                        int16_t ot_min = 32767;
                        int16_t ot_max = -32768;
                        uint8_t any_t_override = 0u;
                        for (uint8_t t = 0u; t < BS_NR_OF_TEMP_SENSORS_PER_MODULE; t++) {
                            if (sil_override_active(0x02u, t)) {
                                int16_t tv = (int16_t)sil_override_get_i32(0x02u, t);
                                if (tv < ot_min) ot_min = tv;
                                if (tv > ot_max) ot_max = tv;
                                any_t_override = 1u;
                            }
                        }
                        if (any_t_override != 0u) {
                            if (ot_min < pMM->minimumTemperature_ddegC[s]) {
                                pMM->minimumTemperature_ddegC[s] = ot_min;
                            }
                            if (ot_max > pMM->maximumTemperature_ddegC[s]) {
                                pMM->maximumTemperature_ddegC[s] = ot_max;
                            }
                        }
                    }
                }

                /* Override current in PACK_VALUES block */
                if (uniqueId == (uint8_t)DATA_BLOCK_ID_PACK_VALUES) {
                    DATA_BLOCK_PACK_VALUES_s *pPV = (DATA_BLOCK_PACK_VALUES_s *)pPassedDataStruct;
                    if (sil_override_active(0x03u, 0u)) {
                        int32_t i_override = sil_override_get_i32(0x03u, 0u);
                        for (uint8_t s = 0u; s < BS_NR_OF_STRINGS; s++) {
                            pPV->stringCurrent_mA[s] = i_override;
                        }
                        pPV->packCurrent_mA = i_override;
                    }
                }

                /* Override individual cell voltages in CELL_VOLTAGE block
                   Array: cellVoltage_mV[BS_NR_OF_STRINGS][BS_NR_OF_MODULES_PER_STRING][BS_NR_OF_CELL_BLOCKS_PER_MODULE] */
                if (uniqueId == (uint8_t)DATA_BLOCK_ID_CELL_VOLTAGE) {
                    DATA_BLOCK_CELL_VOLTAGE_s *pCV = (DATA_BLOCK_CELL_VOLTAGE_s *)pPassedDataStruct;
                    for (uint8_t c = 0u; c < BS_NR_OF_CELL_BLOCKS_PER_MODULE; c++) {
                        if (sil_override_active(0x01u, c)) {
                            int16_t v = (int16_t)sil_override_get_i32(0x01u, c);
                            for (uint8_t s = 0u; s < BS_NR_OF_STRINGS; s++) {
                                for (uint8_t m = 0u; m < BS_NR_OF_MODULES_PER_STRING; m++) {
                                    pCV->cellVoltage_mV[s][m][c] = v;
                                }
                            }
                        }
                    }
                }

                /* Override individual cell temperatures in CELL_TEMPERATURE block
                   Array: cellTemperature_ddegC[BS_NR_OF_STRINGS][BS_NR_OF_MODULES_PER_STRING][BS_NR_OF_TEMP_SENSORS_PER_MODULE] */
                if (uniqueId == (uint8_t)DATA_BLOCK_ID_CELL_TEMPERATURE) {
                    DATA_BLOCK_CELL_TEMPERATURE_s *pCT = (DATA_BLOCK_CELL_TEMPERATURE_s *)pPassedDataStruct;
                    for (uint8_t t = 0u; t < BS_NR_OF_TEMP_SENSORS_PER_MODULE; t++) {
                        if (sil_override_active(0x02u, t)) {
                            int16_t tv = (int16_t)sil_override_get_i32(0x02u, t);
                            for (uint8_t s = 0u; s < BS_NR_OF_STRINGS; s++) {
                                for (uint8_t m = 0u; m < BS_NR_OF_MODULES_PER_STRING; m++) {
                                    pCT->cellTemperature_ddegC[s][m][t] = tv;
                                }
                            }
                        }
                    }
                }
            }
#endif
'''

try:
    with open(TARGET) as f:
        code = f.read()
except FileNotFoundError:
    print(f"ERROR: {TARGET} not found")
    sys.exit(1)

if SENTINEL in code:
    print("already patched")
    sys.exit(0)

# Find the DATA_CopyData call inside the iterate function
# Pattern: "DATA_CopyData(accessType, dataLength, pDatabaseStruct, pPassedDataStruct);"
anchor = "DATA_CopyData(accessType, dataLength, pDatabaseStruct, pPassedDataStruct);"
pos = code.find(anchor)
if pos < 0:
    print("ERROR: DATA_CopyData call not found")
    sys.exit(1)

# Insert after the DATA_CopyData line
insert_pos = pos + len(anchor)
new_code = code[:insert_pos] + INJECT_CODE + code[insert_pos:]

# Add includes for database_cfg types if not present
if '#include "database_cfg.h"' not in new_code:
    # It should already be included via database.h → database_cfg.h
    pass

with open(TARGET, "w") as f:
    f.write(new_code)

print("patched DATA_IterateOverDatabaseEntries with deep fault injection")
