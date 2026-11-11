// Copyright 2025 riley
// SPDX-License-Identifier: GPL-2.0-or-later
// Probe keymap: every matrix position types "row.col " so the physical map can
// be read straight off the real scanner. Hold Esc (matrix 0,0) while plugging
// in to enter the bootloader (bootmagic), or use the pad short.
#include QMK_KEYBOARD_H
#include <stdio.h>

const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {[0] = {{0}}};

bool process_record_user(uint16_t keycode, keyrecord_t *record) {
    if (record->event.pressed) {
        char buf[12];
        snprintf(buf, sizeof buf, "%d.%d ", record->event.key.row, record->event.key.col);
        send_string(buf);
    }
    return false;
}
