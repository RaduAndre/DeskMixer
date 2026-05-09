/**
 * @file    leds.c
 * @brief   SK6812MINI LED driver – SPI2 bit-stuffing implementation.
 *
 * ── Protocol Background ─────────────────────────────────────────────────────
 * SK6812MINI uses a single-wire 800 kHz NZR protocol:
 *   T0H ≈ 300 ns  T0L ≈ 900 ns   → bit 0
 *   T1H ≈ 600 ns  T1L ≈ 600 ns   → bit 1
 *   Reset: low ≥ 80 µs
 *
 * Encoding via SPI (3.0 MHz, period ≈ 333 ns):
 *   One SK6812 bit → 4 SPI bits:
 *     '0' → 0b1000  (high 333 ns, low 1000 ns)  ✓ inside SK6812 tolerances
 *     '1' → 0b1110  (high 1000 ns, low 333 ns)  ✓ inside SK6812 tolerances
 *
 *   Each LED GRB byte = 8 SK6812 bits = 32 SPI bits = 4 SPI bytes.
 *   Each LED (3 bytes GRB) → 12 SPI bytes.
 *   46 LEDs → 46 × 12 = 552 SPI bytes payload.
 *   Reset  → 10 × 0x00 bytes (≈ 250 µs at 3.0 MHz).
 *
 * ── SPI2 config ─────────────────────────────────────────────────────────────
 *   APB1 = 24 MHz, prescaler /8 → 3.0 MHz
 *
 * ── LED Layout ──────────────────────────────────────────────────────────────
 *   Indices  0–39 : 5 slider strips, 8 LEDs each
 *                   slider 0 → LEDs  0–7
 *                   slider 1 → LEDs  8–15
 *                   slider 2 → LEDs 16–23
 *                   slider 3 → LEDs 24–31
 *                   slider 4 → LEDs 32–39
 *   Indices 40–45 : 2 button strips, 3 LEDs each
 *                   button group 0 → LEDs 40–42  (buttons 0,1,2)
 *                   button group 1 → LEDs 43–45  (buttons 3,4,5)
 *
 * ── Behaviour ───────────────────────────────────────────────────────────────
 *   1. Structured color-surf animation (max 20% ≈ 51/255 brightness):
 *      - All 7 rows share ONE current color.
 *      - Every SURF_TICK_MS a new target color is chosen from the palette.
 *      - The transition sweeps LEFT→RIGHT, one row per ROW_STEP_MS:
 *          row 0 gets the new color first, then row 1, … , row 6 last.
 *      - Once all rows reach the new color the board is uniform again,
 *        then a new palette step begins.
 *
 *   2. Slider VU bars (LEDs 0–39) – raw 12-bit ADC [0..4095]:
 *      - 8 LEDs per slider, 512 counts per LED segment.
 *      - LEDs below the tip segment are fully lit at 20% brightness.
 *      - The tip LED (the one partially within its segment) scales
 *        linearly 0→20% across its 512-count window.
 *        Example: raw=256 → LED 0 at 50% of 20% (≈ 10% abs brightness).
 *      - LEDs above the tip are off.
 *
 *   3. Button LEDs (LEDs 40–45):
 *      - One LED per button (6 buttons × 1 LED).
 *      - LED on while button is held, using current surf color of its row.
 *      - LED off when button released.
 */

#include "leds.h"
#include "main.h"
#include <string.h>

/* ── External handles ───────────────────────────────────────────────────── */
extern SPI_HandleTypeDef hspi2;
extern DMA_HandleTypeDef hdma_spi2_tx;

/* ── SPI buffer constants ───────────────────────────────────────────────── */
#define SPI_BYTES_PER_LED_BYTE  4u
#define SPI_LED_PAYLOAD         (LED_TOTAL * 3u * SPI_BYTES_PER_LED_BYTE)  /* 552 */
#define SPI_RESET_BYTES         10u
#define SPI_BUF_SIZE            (SPI_LED_PAYLOAD + SPI_RESET_BYTES)

/* ── Internal LED shadow buffer ─────────────────────────────────────────── */
static struct { uint8_t r, g, b; } s_leds[LED_TOTAL];
static uint8_t s_spiBuf[SPI_BUF_SIZE];

/* ── SPI encode lookup table: byte → 4 SPI bytes ───────────────────────── */
static uint8_t s_encode[256][4];

static void build_lookup(void)
{
    for (int v = 0; v < 256; v++) {
        for (int b = 0; b < 4; b++) {
            uint8_t hi = (v >> (7 - b * 2))     & 1u;
            uint8_t lo = (v >> (7 - b * 2 - 1)) & 1u;
            s_encode[v][b] = (uint8_t)((hi ? 0xE0u : 0x80u) |
                                       (lo ? 0x0Eu : 0x08u));
        }
    }
}

/* ── Color surf animation ───────────────────────────────────────────────── */

/*
 * 20% of 255 = 51.
 * All palette entries are pre-scaled to this ceiling.
 */
#define LED_MAX_BRIGHT  51u

/* Rainbow palette – 8 evenly-spaced hues, pre-scaled to 20% brightness. */
static const uint8_t k_palette[][3] = {
    {LED_MAX_BRIGHT, 0,              0             },  /* Red     */
    {LED_MAX_BRIGHT, LED_MAX_BRIGHT, 0             },  /* Yellow  */
    {0,              LED_MAX_BRIGHT, 0             },  /* Green   */
    {0,              LED_MAX_BRIGHT, LED_MAX_BRIGHT},  /* Cyan    */
    {0,              0,              LED_MAX_BRIGHT},  /* Blue    */
    {LED_MAX_BRIGHT, 0,              LED_MAX_BRIGHT},  /* Magenta */
    {LED_MAX_BRIGHT, LED_MAX_BRIGHT/3u, 0          },  /* Amber   */
    {LED_MAX_BRIGHT/2u, 0,          LED_MAX_BRIGHT},  /* Violet  */
};
#define PALETTE_SIZE  (sizeof(k_palette) / sizeof(k_palette[0]))

/*
 * Total rows:   5 slider rows (8 LEDs each) + 2 button rows (3 LEDs each)
 * Sweep order:  row 0 → 1 → 2 → 3 → 4 → 5 → 6 (left slider to right button)
 */
#define ANIM_ROWS  (LED_SLIDER_COUNT + LED_BUTTON_COUNT)  /* 7 */

/*
 * Animation timing – updated dynamically via LED_SetAnimSpeedLevel().
 * speed=5 is the default (original hardcoded values).
 *   SURF_TICK_MS = 3000 / speed
 *   ROW_STEP_MS  = max(10, 250 / speed)
 */
static uint32_t s_surfTickMs = 600u;
static uint32_t s_rowStepMs  =  50u;

typedef enum {
    SURF_UNIFORM,   /* all rows show current color; waiting for next tick     */
    SURF_SWEEPING,  /* wave is rolling through rows one at a time             */
} SurfState;

static SurfState s_surfState;
static uint8_t   s_curColor;
static uint8_t   s_nextColor;
static uint8_t   s_sweepRow;
static uint32_t  s_stateTime;

/* Per-row current palette index (tracks sweep progress). */
static uint8_t s_rowColor[ANIM_ROWS];

/* ── Dynamic LED configuration ──────────────────────────────────────────── */

/*
 * Brightness percentage 0-100.  Applied as a multiplier against
 * LED_MAX_BRIGHT (51 = 20% of 255).  Default 80.
 */
static uint8_t s_brightness_pct = 80u;

/* Helper: scale a raw [0-255] colour byte by the brightness percentage. */
static inline uint8_t _brite(uint8_t c)
{
    return (uint8_t)((uint16_t)c * s_brightness_pct / 100u);
}

/*
 * Per-slider/button custom colours.
 * (0,0,0) means "use the animated palette colour" (default).
 */
static uint8_t s_slider_custom_r[LED_SLIDER_COUNT];
static uint8_t s_slider_custom_g[LED_SLIDER_COUNT];
static uint8_t s_slider_custom_b[LED_SLIDER_COUNT];

static uint8_t s_button_custom_r[6];   /* one per physical button */
static uint8_t s_button_custom_g[6];
static uint8_t s_button_custom_b[6];

/* Fill / style modes */
static uint8_t s_slider_fill  = 1u;  /* 0=off  1=volume-bar  2=always-on  */
static uint8_t s_button_fill  = 1u;  /* 0=off  1=on-press    2=always-on  */
static uint8_t s_slider_style = 0u;  /* 0=surf (future styles reserved)   */
static uint8_t s_button_style = 0u;

/* ── Peripheral state (set from deskmixer.c) ────────────────────────────── */
static uint16_t s_sliderRaw[LED_SLIDER_COUNT];  /* raw 12-bit [0..4095]  */
static uint8_t  s_buttonMask;                   /* bit i = button i held */

/* ── Internal rebuild ───────────────────────────────────────────────────── */

static void rebuild_leds(void)
{
    /* ── Slider VU bars ──────────────────────────────────────────────── */
    for (uint8_t s = 0; s < LED_SLIDER_COUNT; s++) {
        uint8_t base = s * LED_PER_SLIDER;

        if (s_slider_fill == 0u) {
            /* Fill OFF – all slider LEDs dark */
            for (uint8_t j = 0; j < LED_PER_SLIDER; j++) {
                s_leds[base+j].r = 0; s_leds[base+j].g = 0; s_leds[base+j].b = 0;
            }
            continue;
        }

        /* Resolve this slider's colour: custom or animated palette */
        uint8_t pr, pg, pb;
        if (s_slider_custom_r[s] || s_slider_custom_g[s] || s_slider_custom_b[s]) {
            pr = s_slider_custom_r[s];
            pg = s_slider_custom_g[s];
            pb = s_slider_custom_b[s];
        } else {
            const uint8_t *c = k_palette[s_rowColor[s]];
            pr = c[0]; pg = c[1]; pb = c[2];
        }
        pr = _brite(pr); pg = _brite(pg); pb = _brite(pb);

        if (s_slider_fill == 2u) {
            /* Always-on: all 8 LEDs fully lit */
            for (uint8_t j = 0; j < LED_PER_SLIDER; j++) {
                s_leds[base+j].r = pr; s_leds[base+j].g = pg; s_leds[base+j].b = pb;
            }
        } else {
            /* Volume-bar (fill=1): proportional to ADC value */
            uint8_t  full_leds = (uint8_t)(s_sliderRaw[s] / 512u);
            uint16_t remainder = s_sliderRaw[s] % 512u;
            if (full_leds > LED_PER_SLIDER) full_leds = LED_PER_SLIDER;

            for (uint8_t j = 0; j < LED_PER_SLIDER; j++) {
                if (j < full_leds) {
                    s_leds[base+j].r = pr; s_leds[base+j].g = pg; s_leds[base+j].b = pb;
                } else if (j == full_leds && full_leds < LED_PER_SLIDER) {
                    s_leds[base+j].r = (uint8_t)((pr * remainder) / 512u);
                    s_leds[base+j].g = (uint8_t)((pg * remainder) / 512u);
                    s_leds[base+j].b = (uint8_t)((pb * remainder) / 512u);
                } else {
                    s_leds[base+j].r = 0; s_leds[base+j].g = 0; s_leds[base+j].b = 0;
                }
            }
        }
    }

    /* ── Button LEDs ─────────────────────────────────────────────────── */
    for (uint8_t g = 0; g < LED_BUTTON_COUNT; g++) {
        uint8_t base = LED_SLIDER_COUNT * LED_PER_SLIDER + g * LED_PER_BUTTON;

        for (uint8_t j = 0; j < LED_PER_BUTTON; j++) {
            uint8_t btn = (uint8_t)(g * LED_PER_BUTTON + j);

            /* Resolve this button's colour: custom or animated palette */
            uint8_t pr, pg, pb;
            if (btn < 6u &&
                (s_button_custom_r[btn] || s_button_custom_g[btn] || s_button_custom_b[btn])) {
                pr = s_button_custom_r[btn];
                pg = s_button_custom_g[btn];
                pb = s_button_custom_b[btn];
            } else {
                const uint8_t *c = k_palette[s_rowColor[LED_SLIDER_COUNT + g]];
                pr = c[0]; pg = c[1]; pb = c[2];
            }
            pr = _brite(pr); pg = _brite(pg); pb = _brite(pb);

            uint8_t pressed = (uint8_t)((s_buttonMask >> btn) & 1u);

            if (s_button_fill == 0u) {
                /* Always off */
                s_leds[base+j].r = 0; s_leds[base+j].g = 0; s_leds[base+j].b = 0;
            } else if (s_button_fill == 2u) {
                /* Always on */
                s_leds[base+j].r = pr; s_leds[base+j].g = pg; s_leds[base+j].b = pb;
            } else {
                /* On-press (fill=1, default) */
                if (pressed) {
                    s_leds[base+j].r = pr; s_leds[base+j].g = pg; s_leds[base+j].b = pb;
                } else {
                    s_leds[base+j].r = 0; s_leds[base+j].g = 0; s_leds[base+j].b = 0;
                }
            }
        }
    }
}

/* ── Public functions ────────────────────────────────────────────────────── */

void LED_Init(void)
{
    build_lookup();
    memset(s_leds,              0, sizeof(s_leds));
    memset(s_spiBuf,            0, sizeof(s_spiBuf));
    memset(s_sliderRaw,         0, sizeof(s_sliderRaw));
    memset(s_slider_custom_r,   0, sizeof(s_slider_custom_r));
    memset(s_slider_custom_g,   0, sizeof(s_slider_custom_g));
    memset(s_slider_custom_b,   0, sizeof(s_slider_custom_b));
    memset(s_button_custom_r,   0, sizeof(s_button_custom_r));
    memset(s_button_custom_g,   0, sizeof(s_button_custom_g));
    memset(s_button_custom_b,   0, sizeof(s_button_custom_b));
    s_buttonMask = 0;

    /* Start with the first palette color on all rows */
    s_curColor  = 0;
    s_nextColor = 1;
    for (uint8_t r = 0; r < ANIM_ROWS; r++) {
        s_rowColor[r] = s_curColor;
    }
    s_surfState = SURF_UNIFORM;
    s_stateTime = 0;
    s_sweepRow  = 0;

    LED_Show();
    HAL_Delay(1);
}

void LED_SetColor(uint8_t index, uint8_t r, uint8_t g, uint8_t b)
{
    if (index >= LED_TOTAL) return;
    s_leds[index].r = r;
    s_leds[index].g = g;
    s_leds[index].b = b;
}

void LED_Fill(uint8_t r, uint8_t g, uint8_t b)
{
    for (uint8_t i = 0; i < LED_TOTAL; i++) {
        s_leds[i].r = r;
        s_leds[i].g = g;
        s_leds[i].b = b;
    }
}

void LED_RedToBlue(void)
{
    /* Legacy no-op: animation is driven by LED_Process. */
    LED_Fill(0, 0, 0);
    LED_Show();
}

/*
 * Deadzone applied in LED_SetSliderValue to prevent ADC noise from flickering
 * the tip LED.  Any change smaller than this (in raw 12-bit counts) is
 * silently ignored.  12 counts ≈ 0.3% of full scale.
 */
#define SLIDER_DEADZONE  12u

void LED_SetSliderValue(uint8_t sliderIndex, uint16_t rawValue)
{
    if (sliderIndex >= LED_SLIDER_COUNT) return;
    if (rawValue > 4095u) rawValue = 4095u;

    /* Deadzone: ignore tiny changes caused by ADC noise */
    uint16_t prev  = s_sliderRaw[sliderIndex];
    int16_t  delta = (int16_t)rawValue - (int16_t)prev;
    if (delta < 0) delta = -delta;
    if ((uint16_t)delta <= SLIDER_DEADZONE) return;

    s_sliderRaw[sliderIndex] = rawValue;
}

void LED_SetButtonMask(uint8_t mask)
{
    s_buttonMask = mask;
}

void LED_Process(void)
{
    uint32_t now = HAL_GetTick();

    /* ── Structured surf state machine ─────────────────────────────── */
    switch (s_surfState) {

    case SURF_UNIFORM:
        if ((now - s_stateTime) >= s_surfTickMs) {
            s_surfState = SURF_SWEEPING;
            s_sweepRow  = 0;
            s_stateTime = now;
        }
        break;

    case SURF_SWEEPING:
        /*
         * Strict one-row-per-tick advance.
         *
         * s_stateTime is bumped by exactly ROW_STEP_MS each time a row
         * is committed, so the timer never drifts and can never skip rows
         * even if LED_Process() is called late.
         *
         * Sequence for 7 rows with ROW_STEP_MS = 50 ms:
         *   t =  0 ms  (sweep start): s_stateTime set, waiting
         *   t = 50 ms : row 0 → new color
         *   t = 100 ms: row 1 → new color
         *   ⋮
         *   t = 350 ms: row 6 → new color, board uniform, back to SURF_UNIFORM
         */
        if ((now - s_stateTime) >= s_rowStepMs) {
            s_stateTime += s_rowStepMs;
            s_rowColor[s_sweepRow] = s_nextColor;
            s_sweepRow++;
            if (s_sweepRow >= ANIM_ROWS) {
                s_curColor  = s_nextColor;
                s_nextColor = (uint8_t)((s_nextColor + 1u) % PALETTE_SIZE);
                s_surfState = SURF_UNIFORM;
                s_stateTime = now;
            }
        }
        break;

    default:
        s_surfState = SURF_UNIFORM;
        break;
    }

    /* ── Rebuild LED buffer and push ────────────────────────────────── */
    rebuild_leds();
    LED_Show();
}

void LED_Show(void)
{
    /* Wait for previous DMA transmission to complete before touching the buffer */
    while (HAL_SPI_GetState(&hspi2) != HAL_SPI_STATE_READY) { /* spin */ }

    /* Encode GRB bytes into SPI buffer (SK6812 colour order: G,R,B) */
    uint8_t *p = s_spiBuf;
    for (uint8_t i = 0; i < LED_TOTAL; i++) {
        memcpy(p, s_encode[s_leds[i].g], 4); p += 4;
        memcpy(p, s_encode[s_leds[i].r], 4); p += 4;
        memcpy(p, s_encode[s_leds[i].b], 4); p += 4;
    }
    /* Reset bytes stay 0x00 from init */

    HAL_SPI_Transmit_DMA(&hspi2, s_spiBuf, SPI_BUF_SIZE);
}

void LED_Clear(void)
{
    LED_Fill(0, 0, 0);
    LED_Show();
}

/* ── Dynamic configuration setters ────────────────────────────────────────── */

void LED_SetBrightnessPct(uint8_t pct)
{
    if (pct > 100u) pct = 100u;
    s_brightness_pct = pct;
}

void LED_SetAnimSpeedLevel(uint8_t speed)
{
    if (speed < 1u)  speed = 1u;
    if (speed > 10u) speed = 10u;
    /* SURF_TICK_MS = 3000/speed, ROW_STEP_MS = max(10, 250/speed) */
    s_surfTickMs = 3000u / speed;
    s_rowStepMs  = 250u  / speed;
    if (s_rowStepMs < 10u) s_rowStepMs = 10u;
}

void LED_SetSliderFillMode(uint8_t fill)  { s_slider_fill  = fill;  }
void LED_SetButtonFillMode(uint8_t fill)  { s_button_fill  = fill;  }
void LED_SetSliderStyleMode(uint8_t style){ s_slider_style = style; }
void LED_SetButtonStyleMode(uint8_t style){ s_button_style = style; }

void LED_SetSliderColor(uint8_t idx, uint8_t r, uint8_t g, uint8_t b)
{
    if (idx >= LED_SLIDER_COUNT) return;
    s_slider_custom_r[idx] = r;
    s_slider_custom_g[idx] = g;
    s_slider_custom_b[idx] = b;
}

void LED_SetButtonColor(uint8_t idx, uint8_t r, uint8_t g, uint8_t b)
{
    if (idx >= 6u) return;
    s_button_custom_r[idx] = r;
    s_button_custom_g[idx] = g;
    s_button_custom_b[idx] = b;
}
