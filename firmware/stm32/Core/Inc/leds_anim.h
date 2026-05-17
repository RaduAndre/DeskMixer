/**
 * @file    leds_anim.h
 * @brief   Internal shared state between leds_config.c, leds_core.c, and leds_anim.c.
 *          NOT a public header — do not include from outside the leds_*.c modules.
 */

#ifndef LEDS_ANIM_H
#define LEDS_ANIM_H

#include "leds.h"   /* LED_SLIDER_COUNT, LED_BUTTON_COUNT, LED_TOTAL, LED_PER_SLIDER, LED_PER_BUTTON */
#include "main.h"   /* HAL_GetTick, uint8_t, uint16_t, uint32_t */

/* ── Shared LED shadow buffer (owned by leds_core.c) ───────────────────── */

typedef struct { uint8_t r, g, b; } Led_t;
extern Led_t s_leds[LED_TOTAL];

/* ── Configuration state (owned by leds_config.c) ──────────────────────── */

extern uint8_t  s_slider_fill;          /* 0=off  1=volume-based  2=full    */
extern uint8_t  s_button_fill;          /* 0=off  1=on-press      2=always  */
extern uint8_t  s_slider_style;         /* 0=Surf 1=Solid 2=Pulse 3=VUBar 4=Starlight */
extern uint8_t  s_button_style;         /* 0=Surf 1=Solid 2=Pulse 3=Starlight        */
extern uint8_t  s_slider_mode;          /* 0=All/Rand 1=Per/CustomPalette            */
extern uint8_t  s_button_mode;          /* 0=All/Rand 1=Per/CustomPalette            */
extern uint8_t  s_brightness_pct;       /* 0-100 %                          */

extern uint16_t s_sliderScaled[LED_SLIDER_COUNT]; /* 0-1024 per slider      */
extern uint8_t  s_buttonMask;           /* bit i = button i held            */

extern uint8_t  s_slider_custom_r[LED_SLIDER_COUNT];
extern uint8_t  s_slider_custom_g[LED_SLIDER_COUNT];
extern uint8_t  s_slider_custom_b[LED_SLIDER_COUNT];

extern uint8_t  s_button_custom_r[6];
extern uint8_t  s_button_custom_g[6];
extern uint8_t  s_button_custom_b[6];

/* ── Animation timing globals (owned by leds_anim.c) ───────────────────── */

extern uint32_t s_surfTickMs;       /* ms between surf color changes        */
extern uint32_t s_rowStepMs;        /* ms between surf row advances         */
extern uint32_t s_pulseStepMs;      /* ms between pulse brightness steps    */
extern uint32_t s_starIntervalMs;   /* ms between starlight spawns          */

/* ── Internal function prototypes ───────────────────────────────────────── */

/**
 * @brief  Run the active animation state machine (non-blocking).
 *         Called every main loop from LED_Process().
 */
void anim_process(void);

/**
 * @brief  Write animation output into s_leds[], applying fill-mode masks.
 *         Called immediately after anim_process() from LED_Process().
 */
void rebuild_leds(void);

/**
 * @brief  Apply brightness scale to a raw colour channel byte.
 * @param  c  Raw channel value [0-255]
 * @return Scaled value
 */
uint8_t led_brite(uint8_t c);

/**
 * @brief  Initialise surf interpolation buffers. Call once from LED_Init().
 */
void anim_surf_init(void);

#endif /* LEDS_ANIM_H */
