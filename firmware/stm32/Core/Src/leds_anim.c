/**
 * @file    leds_anim.c
 * @brief   LED animation engines and rebuild_leds().
 *
 * Styles (slider):  0=Surf  1=Solid  2=Pulse  3=VU Bar  4=Starlight
 * Styles (button):  0=Surf  1=Solid  2=Pulse  3=Starlight
 *
 * All animations produce a "full-brightness target color" per LED group.
 * rebuild_leds() then applies fill-mode masking before writing to s_leds[].
 */

#include "leds.h"
#include "leds_anim.h"
#include "main.h"
#include <string.h>

/* ══════════════════════════════════════════════════════════════════════════
 *  CONSTANTS
 * ══════════════════════════════════════════════════════════════════════════ */

#define LED_MAX_BRIGHT   51u    /* 20 % of 255                               */
#define ANIM_ROWS        (LED_SLIDER_COUNT + LED_BUTTON_COUNT)  /* 7         */
#define INTERP_STEPS     16u   /* Surf: lerp steps per row transition        */
#define PULSE_STEP_VAL   4u    /* Pulse: brightness delta per tick           */

/* Rainbow palette – 8 hues, pre-scaled to LED_MAX_BRIGHT. */
static const uint8_t k_palette[8][3] = {
    {LED_MAX_BRIGHT, 0,               0             },  /* Red     */
    {LED_MAX_BRIGHT, LED_MAX_BRIGHT,  0             },  /* Yellow  */
    {0,              LED_MAX_BRIGHT,  0             },  /* Green   */
    {0,              LED_MAX_BRIGHT,  LED_MAX_BRIGHT},  /* Cyan    */
    {0,              0,               LED_MAX_BRIGHT},  /* Blue    */
    {LED_MAX_BRIGHT, 0,               LED_MAX_BRIGHT},  /* Magenta */
    {LED_MAX_BRIGHT, LED_MAX_BRIGHT/3u, 0           },  /* Amber   */
    {LED_MAX_BRIGHT/2u, 0,           LED_MAX_BRIGHT },  /* Violet  */
};
#define PALETTE_SIZE  8u

/* ══════════════════════════════════════════════════════════════════════════
 *  TIMING GLOBALS  (extern-declared in leds_anim.h, set by leds_config.c)
 * ══════════════════════════════════════════════════════════════════════════ */

uint32_t s_surfTickMs    = 600u;
uint32_t s_rowStepMs     =  50u;
uint32_t s_pulseStepMs   =  10u;
uint32_t s_starIntervalMs=  60u;

/* ══════════════════════════════════════════════════════════════════════════
 *  LCG PSEUDO-RANDOM (palette index picker)
 * ══════════════════════════════════════════════════════════════════════════ */

static uint32_t s_seed = 0u;

static uint8_t rand_palette(void)
{
    if (s_seed == 0u) s_seed = HAL_GetTick() | 1u;
    s_seed = s_seed * 1664525u + 1013904223u;           /* Numerical Recipes LCG */
    return (uint8_t)((s_seed >> 16u) % PALETTE_SIZE);
}

/* ══════════════════════════════════════════════════════════════════════════
 *  BRIGHTNESS HELPER (defined in leds_config.c, exposed in leds_anim.h)
 * ══════════════════════════════════════════════════════════════════════════ */


/* Helper: resolve a slider's base color (custom > palette). */
static void resolve_slider_color(uint8_t s, uint8_t pal_rand, uint8_t pal_seq,
                                  uint8_t *r, uint8_t *g, uint8_t *b)
{
    if (s_slider_style == 1u) {
        /* Solid style: always use the specific slider's color (the UI clones them for 'All' mode) */
        *r = s_slider_custom_r[s];
        *g = s_slider_custom_g[s];
        *b = s_slider_custom_b[s];
        if (*r == 0 && *g == 0 && *b == 0) {
            *r = k_palette[0][0]; *g = k_palette[0][1]; *b = k_palette[0][2];
        }
    } else {
        /* Animation styles */
        if (s_slider_mode == 1u) {
            /* Custom palette: cycle through the active custom colors */
            uint8_t psize = 0;
            for(uint8_t i=0; i<LED_SLIDER_COUNT; i++) {
                if (s_slider_custom_r[i]==0 && s_slider_custom_g[i]==0 && s_slider_custom_b[i]==0) break;
                psize++;
            }
            if (psize == 0) psize = 1;
            uint8_t idx = pal_seq % psize;
            *r = s_slider_custom_r[idx];
            *g = s_slider_custom_g[idx];
            *b = s_slider_custom_b[idx];
        } else {
            /* Random/Default palette */
            *r = k_palette[pal_rand % PALETTE_SIZE][0];
            *g = k_palette[pal_rand % PALETTE_SIZE][1];
            *b = k_palette[pal_rand % PALETTE_SIZE][2];
        }
    }
}

/* Helper: resolve a button's base color. */
static void resolve_button_color(uint8_t btn, uint8_t pal_rand, uint8_t pal_seq,
                                  uint8_t *r, uint8_t *g, uint8_t *b)
{
    if (s_button_style == 1u) {
        *r = s_button_custom_r[btn];
        *g = s_button_custom_g[btn];
        *b = s_button_custom_b[btn];
        if (*r == 0 && *g == 0 && *b == 0) {
            *r = k_palette[0][0]; *g = k_palette[0][1]; *b = k_palette[0][2];
        }
    } else {
        if (s_button_mode == 1u) {
            uint8_t psize = 0;
            for(uint8_t i=0; i<6; i++) {
                if (s_button_custom_r[i]==0 && s_button_custom_g[i]==0 && s_button_custom_b[i]==0) break;
                psize++;
            }
            if (psize == 0) psize = 1;
            uint8_t idx = pal_seq % psize;
            *r = s_button_custom_r[idx];
            *g = s_button_custom_g[idx];
            *b = s_button_custom_b[idx];
        } else {
            *r = k_palette[pal_rand % PALETTE_SIZE][0];
            *g = k_palette[pal_rand % PALETTE_SIZE][1];
            *b = k_palette[pal_rand % PALETTE_SIZE][2];
        }
    }
}

/* ══════════════════════════════════════════════════════════════════════════
 *  STYLE 0 – SURF  (smooth left-to-right color drift)
 * ══════════════════════════════════════════════════════════════════════════ */

typedef enum { SURF_UNIFORM, SURF_SWEEPING } SurfState;

static SurfState s_surfState  = SURF_UNIFORM;
static uint8_t   s_surfCur    = 0u;
static uint8_t   s_surfNext   = 1u;
static uint8_t   s_sweepRow   = 0u;
static uint32_t  s_surfTime   = 0u;

/*
 * Per-row interpolated color (0-255 range, not pre-scaled).
 * Lerp from current palette entry to target.
 */
static uint8_t s_rowInterp[ANIM_ROWS][3];
static uint8_t s_rowTarget[ANIM_ROWS];   /* target palette index per row   */

static void surf_init(void)
{
    for (uint8_t r = 0; r < ANIM_ROWS; r++) {
        s_rowTarget[r] = s_surfCur;
        s_rowInterp[r][0] = k_palette[s_surfCur][0];
        s_rowInterp[r][1] = k_palette[s_surfCur][1];
        s_rowInterp[r][2] = k_palette[s_surfCur][2];
    }
}

/* Nudge one channel one step toward its target. */
static uint8_t lerp_step(uint8_t cur, uint8_t tgt)
{
    if (cur == tgt) return cur;
    int16_t diff = (int16_t)tgt - (int16_t)cur;
    int16_t step = diff / (int16_t)INTERP_STEPS;
    if (step == 0) step = (diff > 0) ? 1 : -1;
    int16_t next = (int16_t)cur + step;
    if (next < 0) next = 0;
    if (next > 255) next = 255;
    return (uint8_t)next;
}

static void anim_surf(void)
{
    uint32_t now = HAL_GetTick();

    switch (s_surfState) {
    case SURF_UNIFORM:
        if ((now - s_surfTime) >= s_surfTickMs) {
            s_surfState = SURF_SWEEPING;
            s_sweepRow  = 0u;
            s_surfTime  = now;
        }
        break;

    case SURF_SWEEPING:
        if ((now - s_surfTime) >= s_rowStepMs) {
            s_surfTime += s_rowStepMs;
            /* Assign new target color to the next row in the sweep */
            s_rowTarget[s_sweepRow] = s_surfNext;
            s_sweepRow++;
            if (s_sweepRow >= ANIM_ROWS) {
                s_surfCur   = s_surfNext;
                s_surfNext  = (uint8_t)((s_surfNext + 1u) % PALETTE_SIZE);
                s_surfState = SURF_UNIFORM;
                s_surfTime  = now;
            }
        }
        break;

    default:
        s_surfState = SURF_UNIFORM;
        break;
    }

    /* Interpolate every row toward its target (runs every LED_Process call) */
    for (uint8_t row = 0; row < ANIM_ROWS; row++) {
        uint8_t tgt_r, tgt_g, tgt_b;
        if (row < LED_SLIDER_COUNT) {
            resolve_slider_color(row, s_rowTarget[row], s_rowTarget[row], &tgt_r, &tgt_g, &tgt_b);
        } else {
            resolve_button_color(row - LED_SLIDER_COUNT, s_rowTarget[row], s_rowTarget[row], &tgt_r, &tgt_g, &tgt_b);
        }
        s_rowInterp[row][0] = lerp_step(s_rowInterp[row][0], tgt_r);
        s_rowInterp[row][1] = lerp_step(s_rowInterp[row][1], tgt_g);
        s_rowInterp[row][2] = lerp_step(s_rowInterp[row][2], tgt_b);
    }
}

/* ══════════════════════════════════════════════════════════════════════════
 *  STYLE 2 – PULSE  (uniform brightness triangle wave, random color peaks)
 * ══════════════════════════════════════════════════════════════════════════ */

static uint32_t s_pulseTime       = 0u;
static uint8_t  s_pulseBrightness = 0u;   /* 0-100 scale                  */
static int8_t   s_pulseDir        = 1;    /* +1 rising, -1 falling         */
static uint8_t  s_pulseColorRand  = 0u;   
static uint8_t  s_pulseColorSeq   = 0u;   

static void anim_pulse(void)
{
    uint32_t now = HAL_GetTick();
    if ((now - s_pulseTime) < s_pulseStepMs) return;
    s_pulseTime = now;

    s_pulseBrightness = (uint8_t)((int16_t)s_pulseBrightness + s_pulseDir * (int16_t)PULSE_STEP_VAL);

    if (s_pulseDir > 0 && s_pulseBrightness >= 100u) {
        s_pulseBrightness = 100u;
        s_pulseDir        = -1;
    } else if (s_pulseDir < 0 && s_pulseBrightness <= 4u) {
        s_pulseBrightness = 0u;
        s_pulseDir        = 1;
        s_pulseColorRand  = rand_palette();   /* new random color at trough */
        s_pulseColorSeq++;                    /* cycle custom palette at trough */
    }
}

/* ══════════════════════════════════════════════════════════════════════════
 *  STYLE 3 – VU BAR  (sliders only; random color per rise-from-zero)
 * ══════════════════════════════════════════════════════════════════════════ */

static uint16_t s_vuPrev[LED_SLIDER_COUNT];
static uint8_t  s_vuColorRand[LED_SLIDER_COUNT];
static uint8_t  s_vuColorSeq[LED_SLIDER_COUNT];

static void anim_vu(void)
{
    for (uint8_t s = 0; s < LED_SLIDER_COUNT; s++) {
        uint16_t cur = s_sliderScaled[s];
        if (cur > 0u && s_vuPrev[s] == 0u) {
            /* Rising from zero: assign a fresh random/seq palette color */
            s_vuColorRand[s] = rand_palette();
            s_vuColorSeq[s]++;
        }
        s_vuPrev[s] = cur;
    }
}

/* ══════════════════════════════════════════════════════════════════════════
 *  STYLE 4/3 – STARLIGHT  (random LED sparks that fade)
 * ══════════════════════════════════════════════════════════════════════════ */

#define STAR_FADE_STEP  6u   /* channel subtracted per tick                  */

static uint32_t s_starTime = 0u;
/* Per-LED fade buffer [0-LED_MAX_BRIGHT range] */
static uint8_t  s_starBuf[LED_TOTAL][3];
static uint8_t  s_starSeq = 0u;

static void anim_starlight(void)
{
    uint32_t now = HAL_GetTick();

    static uint32_t s_fadeTime = 0u;
    if ((now - s_fadeTime) >= 10u) {
        s_fadeTime = now;
        for (uint8_t i = 0; i < LED_TOTAL; i++) {
            for (uint8_t ch = 0; ch < 3u; ch++) {
                if (s_starBuf[i][ch] > STAR_FADE_STEP)
                    s_starBuf[i][ch] -= STAR_FADE_STEP;
                else
                    s_starBuf[i][ch] = 0u;
            }
        }
    }

    /* ── Spawn new stars ─────────────────────────────────────────────── */
    if ((now - s_starTime) >= s_starIntervalMs) {
        s_starTime = now;

        /* Spawn 3 stars at a time to have multiple lit up */
        for (uint8_t k = 0; k < 3u; k++) {
            /* Pick a random LED in the slider region (0-39) */
            if (s_seed == 0u) s_seed = HAL_GetTick() | 1u;
            s_seed = s_seed * 1664525u + 1013904223u;
            uint8_t led_idx = (uint8_t)((s_seed >> 8u) % (LED_SLIDER_COUNT * LED_PER_SLIDER));

            /* If fill=1 (volume-based), restrict to lit range of that slider */
            uint8_t slider_idx = led_idx / LED_PER_SLIDER;
            uint8_t slot       = led_idx % LED_PER_SLIDER;
            if (s_slider_fill == 1u) {
                uint8_t max_slot = (uint8_t)(s_sliderScaled[slider_idx] / 128u);
                if (max_slot == 0u) goto spawn_button_star;  /* slider off – skip */
                if (max_slot > LED_PER_SLIDER) max_slot = LED_PER_SLIDER;
                if (slot >= max_slot) slot = max_slot - 1u;
                led_idx = slider_idx * LED_PER_SLIDER + slot;
            }

            uint8_t col = rand_palette();
            s_starSeq++;
            uint8_t tgt_r, tgt_g, tgt_b;
            resolve_slider_color(slider_idx, col, s_starSeq, &tgt_r, &tgt_g, &tgt_b);
            s_starBuf[led_idx][0] = tgt_r;
            s_starBuf[led_idx][1] = tgt_g;
            s_starBuf[led_idx][2] = tgt_b;

            spawn_button_star:;
            /* Also spawn a star in the button region if button style == Starlight */
            if (s_button_style == 3u) {
                uint8_t total_btn = LED_BUTTON_COUNT * LED_PER_BUTTON;
                s_seed = s_seed * 1664525u + 1013904223u;
                uint8_t b_rel = (uint8_t)((s_seed >> 8u) % total_btn);
                uint8_t b_abs = (uint8_t)(LED_SLIDER_COUNT * LED_PER_SLIDER + b_rel);
                uint8_t b_idx = b_rel / LED_PER_BUTTON;
                uint8_t bcol  = rand_palette();
                s_starSeq++;
                resolve_button_color(b_idx, bcol, s_starSeq, &tgt_r, &tgt_g, &tgt_b);
                s_starBuf[b_abs][0] = tgt_r;
                s_starBuf[b_abs][1] = tgt_g;
                s_starBuf[b_abs][2] = tgt_b;
            }
        }
    }
}

/* ══════════════════════════════════════════════════════════════════════════
 *  anim_process() — dispatcher
 * ══════════════════════════════════════════════════════════════════════════ */

void anim_process(void)
{
    switch (s_slider_style) {
    case 0:  anim_surf();      break;
    case 1:  /* Solid: no animation tick needed */  break;
    case 2:  anim_pulse();     break;
    case 3:  anim_vu();        break;
    case 4:  anim_starlight(); break;
    default: anim_surf();      break;
    }

    /* Buttons may need their own Surf/Pulse/Starlight tick
       when slider and button styles differ */
    if (s_button_style != s_slider_style) {
        switch (s_button_style) {
        case 0:  anim_surf();      break;   /* shares surf state — intentional */
        case 2:  anim_pulse();     break;   /* shares pulse state */
        case 3:  anim_starlight(); break;
        default: break;
        }
    }
}

/* ══════════════════════════════════════════════════════════════════════════
 *  rebuild_leds() — apply animation output to s_leds[] with fill masks
 * ══════════════════════════════════════════════════════════════════════════ */

/* Write a color into a slider LED slot, respecting fill mode.
   Returns 1 if LED was lit, 0 if masked off. */
static void write_slider_led(uint8_t abs_idx, uint8_t r, uint8_t g, uint8_t b,
                              uint8_t slot, uint8_t slider_idx)
{
    uint8_t lit = 0u;

    if (s_slider_fill == 1u) {
        /* Full: always on */
        lit = 1u;
    } else if (s_slider_fill == 2u) {
        /* Volume-based */
        uint8_t  full_leds = (uint8_t)(s_sliderScaled[slider_idx] / 128u);
        uint16_t remainder = s_sliderScaled[slider_idx] % 128u;
        if (full_leds > LED_PER_SLIDER) full_leds = LED_PER_SLIDER;

        if (slot < full_leds) {
            lit = 1u;
        } else if (slot == full_leds && full_leds < LED_PER_SLIDER) {
            /* Partial tip LED */
            s_leds[abs_idx].r = (uint8_t)((r * remainder) / 128u);
            s_leds[abs_idx].g = (uint8_t)((g * remainder) / 128u);
            s_leds[abs_idx].b = (uint8_t)((b * remainder) / 128u);
            return;
        }
    }

    if (lit) {
        s_leds[abs_idx].r = r;
        s_leds[abs_idx].g = g;
        s_leds[abs_idx].b = b;
    } else {
        s_leds[abs_idx].r = 0u;
        s_leds[abs_idx].g = 0u;
        s_leds[abs_idx].b = 0u;
    }
}

static void write_button_led(uint8_t abs_idx, uint8_t r, uint8_t g, uint8_t b,
                              uint8_t btn_index)
{
    uint8_t pressed = (uint8_t)((s_buttonMask >> btn_index) & 1u);
    uint8_t show = 0u;

    if      (s_button_fill == 0u) show = 0u;
    else if (s_button_fill == 2u) show = 1u;
    else                          show = pressed;   /* on-press */

    s_leds[abs_idx].r = show ? r : 0u;
    s_leds[abs_idx].g = show ? g : 0u;
    s_leds[abs_idx].b = show ? b : 0u;
}

void rebuild_leds(void)
{
    /* ── Slider fill off: blackout ───────────────────────────────────── */
    if (s_slider_fill == 0u) {
        for (uint8_t i = 0; i < LED_SLIDER_COUNT * LED_PER_SLIDER; i++) {
            s_leds[i].r = 0u; s_leds[i].g = 0u; s_leds[i].b = 0u;
        }
        goto rebuild_buttons;
    }

    /* ── Sliders ─────────────────────────────────────────────────────── */
    for (uint8_t s = 0; s < LED_SLIDER_COUNT; s++) {
        uint8_t base = s * LED_PER_SLIDER;
        uint8_t pr, pg, pb;

        switch (s_slider_style) {

        case 0: /* Surf */
            pr = led_brite(s_rowInterp[s][0]);
            pg = led_brite(s_rowInterp[s][1]);
            pb = led_brite(s_rowInterp[s][2]);
            for (uint8_t j = 0; j < LED_PER_SLIDER; j++)
                write_slider_led(base+j, pr, pg, pb, j, s);
            break;

        case 1: /* Solid */
            resolve_slider_color(s, 0u, 0u, &pr, &pg, &pb);
            pr = led_brite(pr); pg = led_brite(pg); pb = led_brite(pb);
            for (uint8_t j = 0; j < LED_PER_SLIDER; j++)
                write_slider_led(base+j, pr, pg, pb, j, s);
            break;

        case 2: /* Pulse */
            resolve_slider_color(s, s_pulseColorRand, s_pulseColorSeq, &pr, &pg, &pb);
            pr = (uint8_t)((uint16_t)pr * s_pulseBrightness / 100u);
            pg = (uint8_t)((uint16_t)pg * s_pulseBrightness / 100u);
            pb = (uint8_t)((uint16_t)pb * s_pulseBrightness / 100u);
            pr = led_brite(pr); pg = led_brite(pg); pb = led_brite(pb);
            for (uint8_t j = 0; j < LED_PER_SLIDER; j++)
                write_slider_led(base+j, pr, pg, pb, j, s);
            break;

        case 3: /* VU Bar */
            resolve_slider_color(s, s_vuColorRand[s], s_vuColorSeq[s], &pr, &pg, &pb);
            pr = led_brite(pr); pg = led_brite(pg); pb = led_brite(pb);
            for (uint8_t j = 0; j < LED_PER_SLIDER; j++)
                write_slider_led(base+j, pr, pg, pb, j, s);
            break;

        case 4: /* Starlight */
            for (uint8_t j = 0; j < LED_PER_SLIDER; j++) {
                uint8_t abs = base + j;
                /* Check fill eligibility */
                uint8_t eligible = 1u;
                if (s_slider_fill == 2u) {
                    uint8_t max_slot = (uint8_t)(s_sliderScaled[s] / 128u);
                    if (max_slot > LED_PER_SLIDER) max_slot = LED_PER_SLIDER;
                    eligible = (j < max_slot) ? 1u : 0u;
                }
                if (eligible) {
                    s_leds[abs].r = led_brite(s_starBuf[abs][0]);
                    s_leds[abs].g = led_brite(s_starBuf[abs][1]);
                    s_leds[abs].b = led_brite(s_starBuf[abs][2]);
                } else {
                    s_leds[abs].r = 0u;
                    s_leds[abs].g = 0u;
                    s_leds[abs].b = 0u;
                }
            }
            break;

        default:
            break;
        }
    }

rebuild_buttons:
    /* ── Buttons ─────────────────────────────────────────────────────── */
    if (s_button_fill == 0u) {
        uint8_t btn_start = LED_SLIDER_COUNT * LED_PER_SLIDER;
        for (uint8_t i = 0; i < LED_BUTTON_COUNT * LED_PER_BUTTON; i++) {
            s_leds[btn_start+i].r = 0u;
            s_leds[btn_start+i].g = 0u;
            s_leds[btn_start+i].b = 0u;
        }
        return;
    }

    for (uint8_t g = 0; g < LED_BUTTON_COUNT; g++) {
        uint8_t base = LED_SLIDER_COUNT * LED_PER_SLIDER + g * LED_PER_BUTTON;

        for (uint8_t j = 0; j < LED_PER_BUTTON; j++) {
            uint8_t btn = (uint8_t)(g * LED_PER_BUTTON + j);
            uint8_t abs = base + j;
            uint8_t pr, pg, pb;

            switch (s_button_style) {

            case 0: /* Surf – button rows are rows 5 and 6 */
                pr = led_brite(s_rowInterp[LED_SLIDER_COUNT + g][0]);
                pg = led_brite(s_rowInterp[LED_SLIDER_COUNT + g][1]);
                pb = led_brite(s_rowInterp[LED_SLIDER_COUNT + g][2]);
                write_button_led(abs, pr, pg, pb, btn);
                break;

            case 1: /* Solid */
                resolve_button_color(btn, 0u, 0u, &pr, &pg, &pb);
                pr = led_brite(pr); pg = led_brite(pg); pb = led_brite(pb);
                write_button_led(abs, pr, pg, pb, btn);
                break;

            case 2: /* Pulse */
                resolve_button_color(btn, s_pulseColorRand, s_pulseColorSeq, &pr, &pg, &pb);
                pr = (uint8_t)((uint16_t)pr * s_pulseBrightness / 100u);
                pg = (uint8_t)((uint16_t)pg * s_pulseBrightness / 100u);
                pb = (uint8_t)((uint16_t)pb * s_pulseBrightness / 100u);
                pr = led_brite(pr); pg = led_brite(pg); pb = led_brite(pb);
                write_button_led(abs, pr, pg, pb, btn);
                break;

            case 3: /* Starlight */
                s_leds[abs].r = led_brite(s_starBuf[abs][0]);
                s_leds[abs].g = led_brite(s_starBuf[abs][1]);
                s_leds[abs].b = led_brite(s_starBuf[abs][2]);
                /* Apply button fill manually */
                {
                    uint8_t pressed = (uint8_t)((s_buttonMask >> btn) & 1u);
                    uint8_t show = (s_button_fill == 2u) ? 1u : pressed;
                    if (!show) {
                        s_leds[abs].r = 0u;
                        s_leds[abs].g = 0u;
                        s_leds[abs].b = 0u;
                    }
                }
                break;

            default:
                break;
            }
        }
    }
}

/* ══════════════════════════════════════════════════════════════════════════
 *  LED_Init companion: initialise surf row interpolation buffers
 * ══════════════════════════════════════════════════════════════════════════ */

/* Called once from LED_Init (leds_core.c) before the first anim_process() */
void anim_surf_init(void)
{
    surf_init();
}
