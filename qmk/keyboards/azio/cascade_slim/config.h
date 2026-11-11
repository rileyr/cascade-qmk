// Copyright 2025 riley
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

/* LED matrix, recovered from the stock V1.5 firmware (see ../../out/PINOUT-NOTES.md).
 * Row pins per LED row in the order the sn32f2xx hardware-PWM driver consumes them: B, G, R.
 *   row0 R=B12 G=C0  B=C1     row1 R=C6  G=C4  B=C5     row2 R=C9  G=C7  B=C8
 *   row3 R=C12 G=C10 B=C11    row4 R=B13 G=C13 B=C14    row5 R=B14 G=D3  B=B15
 * Rows are driven high to light. Columns are CT16B1 PWM channels 23..8.
 */
#define SN32F2XX_RGB_MATRIX_ROW_PINS { C1, C0, B12, C5, C4, C6, C8, C7, C9, C11, C10, C12, C14, C13, B13, B15, D3, B14 }
/* LED columns share the key column pins (shared-matrix mode: the driver scans keys between PWM
 * frames). Column 15 is A8 (PWM channel 8), the same column set as the Keychron K2. */
#define SN32F2XX_RGB_OUTPUT_ACTIVE_LEVEL SN32F2XX_RGB_OUTPUT_ACTIVE_HIGH
#define SN32F2XX_PWM_OUTPUT_ACTIVE_LEVEL SN32F2XX_PWM_OUTPUT_ACTIVE_LOW

/* RAM is 8 KB. Keep the settings-storage cache small: 2 keymap layers (384 B) + eeconfig fit
 * in a 768 B logical EEPROM (default 1024), trimming the wear-leveling RAM cache. */
#define WEAR_LEVELING_LOGICAL_SIZE 768
#define WEAR_LEVELING_BACKING_SIZE 3072
#define DYNAMIC_KEYMAP_LAYER_COUNT 2
