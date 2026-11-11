// Custom RGB Matrix effects for the Cascade Slim.
// Enabled by RGB_MATRIX_CUSTOM_USER = yes in rules.mk; effects appear in the
// Fn+End cycle after the built-in ones.

RGB_MATRIX_EFFECT(DRIFT)
RGB_MATRIX_EFFECT(FIREFLIES)

#ifdef RGB_MATRIX_CUSTOM_EFFECT_IMPLS

// ---- DRIFT: every key holds its own hue and random-walks it at its own pace.
// Neighbouring keys are nudged toward each other so the board reads as slow,
// lava-lamp-like colour weather rather than static. Speed knob = Fn+PgUp/PgDn.
// One scratch buffer shared by the custom effects (only one runs at a time; RAM is 8 KB).
static union {
    struct { uint8_t hue[RGB_MATRIX_LED_COUNT]; uint8_t rate[RGB_MATRIX_LED_COUNT]; } drift;
    struct { uint8_t level[RGB_MATRIX_LED_COUNT]; uint8_t hue[RGB_MATRIX_LED_COUNT]; } ff;   // level bit7 = rising
} fxmem;
#define drift_hue  fxmem.drift.hue
#define drift_rate fxmem.drift.rate
static uint16_t drift_last = 0;
static bool     drift_seeded = false;

static void drift_seed(void) {
    for (uint8_t i = 0; i < RGB_MATRIX_LED_COUNT; i++) {
        drift_hue[i]  = random8();
        drift_rate[i] = 1 + (random8() & 3);
    }
    drift_seeded = true;
}

static bool DRIFT(effect_params_t* params) {
    RGB_MATRIX_USE_LIMITS(led_min, led_max);
    if (params->init || !drift_seeded) drift_seed();
    // advance the walk at a rate set by the speed setting (every ~20..120 ms).
    // QMK calls the effect once per chunk of LEDs per frame; decide once per frame (iter 0)
    // so every row steps together.
    static bool advance = false;
    if (params->iter == 0) {
        uint16_t now  = g_rgb_timer;
        uint16_t step = 130 - (rgb_matrix_get_speed() / 2);
        advance = (uint16_t)(now - drift_last) > step;
        if (advance) drift_last = now;
    }
    for (uint8_t i = led_min; i < led_max; i++) {
        RGB_MATRIX_TEST_LED_FLAGS();
        if (advance) {
            int8_t r = (int8_t)(random8() & 7) - 3;              // -3..4, slight upward bias so hues circulate
            drift_hue[i] += r * drift_rate[i];
            // pull toward the average of the key's horizontal neighbours (by LED index order,
            // which follows the physical layout row by row)
            uint8_t l = (i > 0) ? drift_hue[i - 1] : drift_hue[i];
            uint8_t rr = (i + 1 < RGB_MATRIX_LED_COUNT) ? drift_hue[i + 1] : drift_hue[i];
            int16_t avg = ((int16_t)l + rr) / 2;
            int16_t d   = (int16_t)(int8_t)(avg - drift_hue[i]);   // shortest way around the hue circle
            drift_hue[i] += d / 8;
            if ((random8() & 0x7f) == 0) drift_hue[i] += 64;       // rare jump so it never settles
        }
        HSV hsv = {drift_hue[i], rgb_matrix_config.hsv.s, rgb_matrix_config.hsv.v};
        RGB rgb = rgb_matrix_hsv_to_rgb(hsv);
        rgb_matrix_set_color(i, rgb.r, rgb.g, rgb.b);
    }
    return rgb_matrix_check_finished_leds(led_max);
}

// ---- FIREFLIES: dark board, random keys fade in with a random hue and fade out.
#define ff_hue fxmem.ff.hue
static uint16_t ff_last = 0;

static bool FIREFLIES(effect_params_t* params) {
    RGB_MATRIX_USE_LIMITS(led_min, led_max);
    if (params->init) {
        for (uint8_t i = 0; i < RGB_MATRIX_LED_COUNT; i++) fxmem.ff.level[i] = 0;
        drift_seeded = false;  // the shared buffer is now ours; Drift must reseed when it returns
    }
    static bool advance = false;
    if (params->iter == 0) {
        uint16_t now  = g_rgb_timer;
        uint16_t step = 40 - (rgb_matrix_get_speed() / 8);
        advance = (uint16_t)(now - ff_last) > step;
        if (advance) ff_last = now;
    }
    for (uint8_t i = led_min; i < led_max; i++) {
        RGB_MATRIX_TEST_LED_FLAGS();
        // level: bit7 = rising, bits 0..6 = brightness 0..127
        uint8_t lv = fxmem.ff.level[i] & 0x7f;
        bool rising = fxmem.ff.level[i] & 0x80;
        if (advance) {
            if (lv == 0 && !rising) {
                if ((random8() & 0x3f) == 0) { lv = 1; rising = true; ff_hue[i] = random8(); }
            } else if (rising) {
                lv = (lv > 124) ? 127 : lv + 3;
                if (lv == 127) rising = false;
            } else {
                lv = (lv < 2) ? 0 : lv - 2;
            }
            fxmem.ff.level[i] = (rising ? 0x80 : 0) | lv;
        }
        uint8_t v = scale8(lv * 2, rgb_matrix_config.hsv.v);
        HSV hsv = {ff_hue[i], rgb_matrix_config.hsv.s, v};
        RGB rgb = rgb_matrix_hsv_to_rgb(hsv);
        rgb_matrix_set_color(i, rgb.r, rgb.g, rgb.b);
    }
    return rgb_matrix_check_finished_leds(led_max);
}

#endif // RGB_MATRIX_CUSTOM_EFFECT_IMPLS
