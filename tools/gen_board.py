#!/usr/bin/env python3
"""Generate the AZIO Cascade Slim board definition for SonixQMK.

Writes, under qmk/keyboards/azio/cascade_slim/:
  keyboard.json                 LAYOUT (84 keys), RGB Matrix layout, enabled animations
  keymaps/default/keymap.c      base layer + Fn layer
and app/qmk_info.json for the web app (keys, Fn layer, effects, effect id order).

The key matrix below was verified on hardware (see docs/PINOUT.md). The set of
effects compiled in comes from app/effects.json ({"enabled": [ids]}); without
that file a sensible default pack is used.
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB = os.path.join(ROOT, "qmk", "keyboards", "azio", "cascade_slim")
ROWS, COLS = 6, 16

# Physical layout, row by row: (label, width in key units). Rows are 1u tall.
LAYOUT = [
    [("Esc", 1), ("F1", 1), ("F2", 1), ("F3", 1), ("F4", 1), ("F5", 1), ("F6", 1), ("F7", 1), ("F8", 1), ("F9", 1), ("F10", 1), ("F11", 1), ("F12", 1), ("PrtSc", 1), ("Ins", 1), ("Del", 1)],
    [("`", 1), ("1", 1), ("2", 1), ("3", 1), ("4", 1), ("5", 1), ("6", 1), ("7", 1), ("8", 1), ("9", 1), ("0", 1), ("-", 1), ("=", 1), ("Bksp", 2), ("Home", 1)],
    [("Tab", 1.5), ("Q", 1), ("W", 1), ("E", 1), ("R", 1), ("T", 1), ("Y", 1), ("U", 1), ("I", 1), ("O", 1), ("P", 1), ("[", 1), ("]", 1), ("\\", 1.5), ("End", 1)],
    [("Caps", 1.75), ("A", 1), ("S", 1), ("D", 1), ("F", 1), ("G", 1), ("H", 1), ("J", 1), ("K", 1), ("L", 1), (";", 1), ("'", 1), ("Enter", 2.25), ("PgUp", 1)],
    [("LShift", 2.25), ("Z", 1), ("X", 1), ("C", 1), ("V", 1), ("B", 1), ("N", 1), ("M", 1), (",", 1), (".", 1), ("/", 1), ("RShift", 1.75), ("Up", 1), ("PgDn", 1)],
    [("LCtrl", 1.25), ("Opt", 1.25), ("LCmd", 1.25), ("Space", 6.25), ("RCmd", 1), ("Fn", 1), ("RCtrl", 1), ("Left", 1), ("Down", 1), ("Right", 1)],
]

# Electrical matrix position (row, col) of every key, verified on the board.
# Columns 0..15 are B7..B0, A15..A8; rows 0..5 are C15, D11, D10, D9, D8, D7 (COL2ROW).
MATRIX = {
    "Esc": (0, 0), "F1": (0, 1), "F2": (0, 2), "F3": (0, 3), "F4": (0, 4), "F5": (0, 5), "F6": (0, 6), "F7": (0, 7), "F8": (0, 8),
    "F9": (0, 9), "F10": (0, 10), "F11": (0, 11), "F12": (0, 12), "PrtSc": (0, 13), "Ins": (0, 14), "Del": (0, 15),
    "`": (1, 0), "1": (1, 1), "2": (1, 2), "3": (1, 3), "4": (1, 4), "5": (1, 5), "6": (1, 6), "7": (1, 7), "8": (1, 8), "9": (1, 9),
    "0": (1, 10), "-": (1, 11), "=": (1, 12), "Bksp": (1, 13), "Home": (1, 14),
    "Tab": (2, 0), "Q": (2, 1), "W": (2, 2), "E": (2, 3), "R": (2, 4), "T": (2, 5), "Y": (2, 6), "U": (2, 7), "I": (2, 8), "O": (2, 9),
    "P": (2, 10), "[": (2, 11), "]": (2, 12), "\\": (2, 13), "End": (2, 14),
    "Caps": (3, 0), "A": (3, 1), "S": (3, 2), "D": (3, 3), "F": (3, 4), "G": (3, 5), "H": (3, 6), "J": (3, 7), "K": (3, 8), "L": (3, 9),
    ";": (3, 10), "'": (3, 11), "Enter": (3, 13), "PgUp": (3, 14),
    "LShift": (4, 0), "Z": (4, 2), "X": (4, 3), "C": (4, 4), "V": (4, 5), "B": (4, 6), "N": (4, 7), "M": (4, 8), ",": (4, 9), ".": (4, 10),
    "/": (4, 11), "RShift": (4, 12), "Up": (4, 13), "PgDn": (4, 14),
    "LCtrl": (5, 0), "Opt": (5, 1), "LCmd": (5, 2), "Space": (5, 6), "RCmd": (5, 9), "Fn": (5, 10), "RCtrl": (5, 11), "Left": (5, 12),
    "Down": (5, 13), "Right": (5, 14),
}
MODS = {"LShift", "RShift", "LCtrl", "RCtrl", "Opt", "LCmd", "RCmd", "Fn"}  # LED_FLAG_MODIFIER

KC = {"Esc": "KC_ESC", "PrtSc": "KC_PSCR", "Ins": "KC_INS", "Del": "KC_DEL", "`": "KC_GRV", "-": "KC_MINS", "=": "KC_EQL", "Bksp": "KC_BSPC", "Home": "KC_HOME",
      "Tab": "KC_TAB", "[": "KC_LBRC", "]": "KC_RBRC", "\\": "KC_BSLS", "End": "KC_END", "Caps": "KC_CAPS", ";": "KC_SCLN", "'": "KC_QUOT", "Enter": "KC_ENT", "PgUp": "KC_PGUP",
      "LShift": "KC_LSFT", ",": "KC_COMM", ".": "KC_DOT", "/": "KC_SLSH", "RShift": "KC_RSFT", "Up": "KC_UP", "PgDn": "KC_PGDN", "LCtrl": "KC_LCTL", "Opt": "KC_LALT", "LCmd": "KC_LGUI",
      "Space": "KC_SPC", "RCmd": "KC_RGUI", "Fn": "MO(1)", "RCtrl": "KC_RCTL", "Left": "KC_LEFT", "Down": "KC_DOWN", "Right": "KC_RGHT"}
for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789":
    KC[ch] = "KC_" + ch
for i in range(1, 13):
    KC[f"F{i}"] = f"KC_F{i}"

# Fn layer: the stock keyboard's lighting hotkeys, media on the F row, bootloader on Esc.
FN = {"Esc": "QK_BOOT", "End": "RM_NEXT", "Del": "RM_PREV", "Home": "RM_TOGG", "Up": "RM_VALU", "Down": "RM_VALD", "Left": "RM_HUED", "Right": "RM_HUEU",
      "PgUp": "RM_SPDU", "PgDn": "RM_SPDD", "F1": "KC_BRID", "F2": "KC_BRIU", "F7": "KC_MPRV", "F8": "KC_MPLY", "F9": "KC_MNXT", "F10": "KC_MUTE",
      "F11": "KC_VOLD", "F12": "KC_VOLU"}
FN_DESC = {"QK_BOOT": "Enter bootloader: board goes dark and waits for a flash. Only press after arming a flash; replug the cable to get out",
           "RM_NEXT": "Next lighting effect", "RM_PREV": "Previous lighting effect", "RM_TOGG": "Lighting on/off", "RM_VALU": "Brightness up",
           "RM_VALD": "Brightness down", "RM_HUEU": "Hue +", "RM_HUED": "Hue -", "RM_SPDU": "Effect speed up", "RM_SPDD": "Effect speed down",
           "KC_BRID": "Screen brightness down", "KC_BRIU": "Screen brightness up", "KC_MPRV": "Previous track", "KC_MPLY": "Play/pause",
           "KC_MNXT": "Next track", "KC_MUTE": "Mute", "KC_VOLD": "Volume down", "KC_VOLU": "Volume up"}

# Every RGB Matrix effect in SonixQMK, plus the two custom ones in keymaps/default/rgb_matrix_user.inc.
EFFECTS = [
    ("solid_color", "Solid", "One colour everywhere. Fn+Left/Right hue, Fn+Up/Down brightness."),
    ("alphas_mods", "Alphas / mods", "Modifier keys in a second colour (base hue + speed), everything else in the base colour."),
    ("gradient_up_down", "Gradient (vertical)", "A static hue gradient from top to bottom."),
    ("gradient_left_right", "Gradient (horizontal)", "A static hue gradient from left to right."),
    ("breathing", "Breathing", "The whole board fades in and out together."),
    ("band_sat", "Band (saturation)", "A band of colour sweeps across; saturation varies."),
    ("band_val", "Band (brightness)", "A band of brightness sweeps across the board."),
    ("band_pinwheel_sat", "Pinwheel band (sat)", "A saturation band rotating around the centre."),
    ("band_pinwheel_val", "Pinwheel band (bright)", "A brightness band rotating around the centre."),
    ("band_spiral_sat", "Spiral band (sat)", "A spiral of saturation turning around the centre."),
    ("band_spiral_val", "Spiral band (bright)", "A spiral of brightness turning around the centre."),
    ("cycle_all", "Rainbow cycle", "Every key the same hue, cycling through the rainbow."),
    ("cycle_left_right", "Rainbow sweep", "A rainbow travels across the board, left to right."),
    ("cycle_up_down", "Rainbow fall", "A rainbow travels from top to bottom."),
    ("cycle_out_in", "Rainbow ripple in", "Rainbow rings contracting toward the centre."),
    ("cycle_out_in_dual", "Rainbow ripple in (dual)", "Rings contracting toward two centres, left and right."),
    ("rainbow_moving_chevron", "Chevron", "A rainbow chevron sweeps across the board."),
    ("cycle_pinwheel", "Pinwheel", "A rainbow rotating around the centre like a pinwheel."),
    ("cycle_spiral", "Spiral", "A rainbow spiral turning around the centre."),
    ("dual_beacon", "Dual beacon", "Two rainbow beams rotating around the centre."),
    ("rainbow_beacon", "Rainbow beacon", "One thick rainbow beam rotating around the centre."),
    ("rainbow_pinwheels", "Pinwheels", "Two rainbow pinwheels, one each side."),
    ("flower_blooming", "Flower blooming", "Hues bloom outward from the centre like petals."),
    ("raindrops", "Raindrops", "Random keys change to random colours, slowly."),
    ("jellybean_raindrops", "Jellybeans", "Random keys pop to saturated random colours."),
    ("hue_breathing", "Hue breathe", "Breathing where the colour shifts slightly each cycle."),
    ("hue_pendulum", "Hue pendulum", "Hue swings back and forth across the board."),
    ("hue_wave", "Hue wave", "A gentle wave of hue variation moving across the keys."),
    ("pixel_fractal", "Pixel fractal", "A symmetric random pattern grows from the centre."),
    ("pixel_flow", "Pixel flow", "Random colours flow across the board like a conveyor."),
    ("pixel_rain", "Pixel rain", "Keys flash on and off at random like static."),
    ("typing_heatmap", "Typing heatmap", "Keys you hit glow hotter and cool down over time."),
    ("digital_rain", "Digital rain", "Green streaks fall down the board."),
    ("solid_reactive_simple", "Reactive", "Dark until pressed; the pressed key lights and fades."),
    ("solid_reactive", "Reactive hue", "Pressed keys light with a shifted hue and fade."),
    ("solid_reactive_wide", "Reactive wide", "A press lights the key and its neighbours."),
    ("solid_reactive_multiwide", "Reactive wide (multi)", "Like Reactive wide, every press at once."),
    ("solid_reactive_cross", "Reactive cross", "A press lights a cross through the key."),
    ("solid_reactive_multicross", "Reactive cross (multi)", "Crosses from every press at once."),
    ("solid_reactive_nexus", "Reactive nexus", "A press lights lines out to the board edges."),
    ("solid_reactive_multinexus", "Reactive nexus (multi)", "Nexus lines from every press at once."),
    ("splash", "Splash", "A ring of colour spreads out from each press."),
    ("multisplash", "Multi splash", "Rings from every press, overlapping."),
    ("solid_splash", "Solid splash", "A ring of the current colour from each press."),
    ("solid_multisplash", "Solid multi splash", "Rings of the current colour from every press."),
    ("starlight", "Starlight", "Keys twinkle like stars in the current colour."),
    ("starlight_dual_hue", "Starlight (dual hue)", "Twinkling in two hues."),
    ("starlight_dual_sat", "Starlight (dual sat)", "Twinkling in two saturations."),
    ("riverflow", "River flow", "Brightness flows along the key order like a river."),
    ("drift", "Drift (custom)", "Every key random-walks its own hue, nudged toward its neighbours; slow colour weather."),
    ("fireflies", "Fireflies (custom)", "Dark board; random keys fade in with a random colour and fade out."),
]
CUSTOM = {"drift", "fireflies"}
DEFAULT_ENABLED = ["solid_color", "breathing", "cycle_left_right", "cycle_all", "rainbow_moving_chevron", "jellybean_raindrops", "pixel_rain",
                   "pixel_fractal", "typing_heatmap", "digital_rain", "solid_reactive_simple", "solid_reactive", "splash", "multisplash",
                   "solid_multisplash", "hue_breathing", "hue_wave", "raindrops", "drift", "fireflies"]

# QMK numbers effects in the order rgb_matrix_effects.inc includes them (enabled ones only),
# then the custom ones. Read the real file from a SonixQMK checkout when present.
CANONICAL = ["solid_color", "alphas_mods", "gradient_up_down", "gradient_left_right", "breathing", "band_sat", "band_val", "band_pinwheel_sat",
             "band_pinwheel_val", "band_spiral_sat", "band_spiral_val", "cycle_all", "cycle_left_right", "cycle_up_down", "rainbow_moving_chevron",
             "cycle_out_in", "cycle_out_in_dual", "cycle_pinwheel", "cycle_spiral", "dual_beacon", "rainbow_beacon", "rainbow_pinwheels",
             "flower_blooming", "raindrops", "jellybean_raindrops", "hue_breathing", "hue_pendulum", "hue_wave", "pixel_rain", "pixel_flow",
             "pixel_fractal", "typing_heatmap", "digital_rain", "solid_reactive_simple", "solid_reactive", "solid_reactive_wide",
             "solid_reactive_multiwide", "solid_reactive_cross", "solid_reactive_multicross", "solid_reactive_nexus", "solid_reactive_multinexus",
             "splash", "multisplash", "solid_splash", "solid_multisplash", "starlight", "starlight_dual_sat", "starlight_dual_hue", "riverflow"]
ALIAS = {"solid_reactive_cross": ["solid_reactive_cross", "solid_reactive_multicross"], "solid_reactive_nexus": ["solid_reactive_nexus", "solid_reactive_multinexus"],
         "solid_reactive_wide": ["solid_reactive_wide", "solid_reactive_multiwide"], "splash": ["splash", "multisplash"], "solid_splash": ["solid_splash", "solid_multisplash"],
         "colorband_sat": ["band_sat"], "colorband_val": ["band_val"], "colorband_pinwheel_sat": ["band_pinwheel_sat"], "colorband_pinwheel_val": ["band_pinwheel_val"],
         "colorband_spiral_sat": ["band_spiral_sat"], "colorband_spiral_val": ["band_spiral_val"], "alpha_mods": ["alphas_mods"]}


def canonical_order():
    inc = os.path.join(ROOT, "qmk_firmware", "quantum", "rgb_matrix", "animations", "rgb_matrix_effects.inc")
    if os.path.exists(inc):
        out = []
        for name in re.findall(r'#include "([a-z0-9_]+?)(?:_anim)?\.h"', open(inc).read()):
            out += ALIAS.get(name, [name])
        return out
    return CANONICAL


def main():
    labels = [lab for row in LAYOUT for lab, _ in row]
    assert len(labels) == 84 and all(lab in MATRIX for lab in labels)
    assert len(set(MATRIX.values())) == 84, "duplicate matrix positions"

    valid = {e[0] for e in EFFECTS}
    try:
        enabled = {e for e in json.load(open(os.path.join(ROOT, "app", "effects.json")))["enabled"] if e in valid}
    except Exception:
        enabled = set()
    enabled = (enabled or set(DEFAULT_ENABLED)) | CUSTOM

    total_w = max(sum(w for _, w in row) for row in LAYOUT)
    layout_json, rgb_layout = [], []
    for r, row in enumerate(LAYOUT):
        x = 0.0
        for lab, w in row:
            pr, pc = MATRIX[lab]
            k = {"matrix": [pr, pc], "x": round(x, 2), "y": r, "label": lab}
            if w != 1:
                k["w"] = w
            layout_json.append(k)
            rgb_layout.append({"matrix": [pr, pc], "x": round((x + w / 2) / total_w * 224), "y": round((r + 0.5) / 6 * 64), "flags": 1 if lab in MODS else 4})
            x += w

    kb = {
        "keyboard_name": "Cascade Slim", "manufacturer": "AZIO", "maintainer": "riley",
        "url": "https://github.com/rileyr/cascade-qmk",
        "processor": "SN32F248BF", "bootloader": "sn32-dfu", "board": "SN_SN32F240B_PWM",
        "usb": {"vid": "0xFEED", "pid": "0xCA5C", "device_version": "0.0.1"},  # not Apple's IDs: the stock firmware spoofs them, this build does not
        "matrix_pins": {"rows": ["C15", "D11", "D10", "D9", "D8", "D7"],
                        "cols": ["B7", "B6", "B5", "B4", "B3", "B2", "B1", "B0", "A15", "A14", "A13", "A12", "A11", "A10", "A9", "A8"]},
        "diode_direction": "COL2ROW",
        "features": {"bootmagic": True, "extrakey": True, "nkro": True, "mousekey": False, "rgb_matrix": True},
        "rgb_matrix": {"driver": "sn32f2xx", "sleep": True, "default": {"val": 160},
                       "animations": {e[0]: True for e in EFFECTS if e[0] in enabled and e[0] not in CUSTOM},
                       "layout": rgb_layout},
        "layouts": {"LAYOUT": {"layout": layout_json}},
    }
    os.makedirs(os.path.join(KB, "keymaps", "default"), exist_ok=True)
    json.dump(kb, open(os.path.join(KB, "keyboard.json"), "w"), indent=4)

    def rows(fn):
        return ",\n        ".join(", ".join(fn(lab) for lab, _ in row) for row in LAYOUT)
    keymap = f'''// Copyright 2025 riley
// SPDX-License-Identifier: GPL-2.0-or-later
// Generated by tools/gen_board.py. Fn = MO(1). Fn+Esc enters the bootloader.
#include QMK_KEYBOARD_H

const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {{
    [0] = LAYOUT(
        {rows(lambda lab: KC[lab])}
    ),
    [1] = LAYOUT(
        {rows(lambda lab: FN.get(lab, "_______"))}
    ),
}};
'''
    open(os.path.join(KB, "keymaps", "default", "keymap.c"), "w").write(keymap)

    order = [e for e in canonical_order() if e in enabled and e not in CUSTOM] + [e[0] for e in EFFECTS if e[0] in CUSTOM and e[0] in enabled]
    info = {"effect_order": ["none"] + order, "default_enabled": DEFAULT_ENABLED,
            "keys": [{"label": lab, "row": MATRIX[lab][0], "col": MATRIX[lab][1]} for lab in labels],
            "fn": {lab: {"code": FN[lab], "does": FN_DESC.get(FN[lab], FN[lab])} for lab in FN},
            "effects": [{"id": i, "name": n, "desc": d, "enabled": i in enabled, "custom": i in CUSTOM} for i, n, d in EFFECTS],
            "known_issues": ["Bluetooth is off under QMK (the module protocol is not implemented yet); wired only."]}
    json.dump(info, open(os.path.join(ROOT, "app", "qmk_info.json"), "w"), indent=1)
    print(f"board written to {os.path.relpath(KB, ROOT)}: 84 keys, {len(order)} effects in the pack")


if __name__ == "__main__":
    main()
