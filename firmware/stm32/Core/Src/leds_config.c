/**
 * @file    leds_config.c
 * @brief   LED configuration state variables and public setter/getter functions.
 *          Owns all mutable LED parameters written by params.c via the public
 *          LED_Set*() API and read by leds_anim.c through leds_anim.h externs.
 */

#include "leds.h"
#include "leds_anim.h"
#include <string.h>

/* ── Timing globals (defined in leds_anim.c, updated here) ─────────────── */

extern uint32_t s_surfTickMs;
extern uint32_t s_rowStepMs;
extern uint32_t s_pulseStepMs;
extern uint32_t s_starIntervalMs;

/* ── Configuration state ────────────────────────────────────────────────── */

uint8_t  s_slider_fill   = 1u;  /* 0=off  1=volume-based  2=full           */
uint8_t  s_button_fill   = 1u;  /* 0=off  1=on-press      2=always-on      */
uint8_t  s_slider_style  = 0u;  /* 0=Surf 1=Solid 2=Pulse 3=VUBar 4=Star  */
uint8_t  s_button_style  = 0u;  /* 0=Surf 1=Solid 2=Pulse 3=Starlight      */
uint8_t  s_slider_mode   = 0u;  /* 0=All/Rand 1=Per/CustomPalette          */
uint8_t  s_button_mode   = 0u;  /* 0=All/Rand 1=Per/CustomPalette          */
uint8_t  s_brightness_pct = 80u;

uint16_t s_sliderScaled[LED_SLIDER_COUNT];
uint8_t  s_buttonMask = 0u;

uint8_t  s_slider_custom_r[LED_SLIDER_COUNT];
uint8_t  s_slider_custom_g[LED_SLIDER_COUNT];
uint8_t  s_slider_custom_b[LED_SLIDER_COUNT];

uint8_t  s_button_custom_r[6];
uint8_t  s_button_custom_g[6];
uint8_t  s_button_custom_b[6];

/* ── Brightness helper ──────────────────────────────────────────────────── */

uint8_t led_brite(uint8_t c)
{
    return (uint8_t)((uint16_t)c * s_brightness_pct / 100u);
}

/* ── Public setters ─────────────────────────────────────────────────────── */

void LED_SetBrightnessPct(uint8_t pct)
{
    if (pct > 100u) pct = 100u;
    s_brightness_pct = pct;
}

void LED_SetAnimSpeedLevel(uint8_t speed)
{
    if (speed < 1u)  speed = 1u;
    if (speed > 10u) speed = 10u;

    s_surfTickMs    = 3000u / speed;
    s_rowStepMs     = 250u  / speed;
    if (s_rowStepMs < 10u) s_rowStepMs = 10u;

    s_pulseStepMs   = 50u   / speed;
    if (s_pulseStepMs < 5u) s_pulseStepMs = 5u;

    s_starIntervalMs = 300u / speed;
    if (s_starIntervalMs < 30u) s_starIntervalMs = 30u;
}

void LED_SetSliderFillMode(uint8_t fill)  { s_slider_fill  = fill;  }
void LED_SetButtonFillMode(uint8_t fill)  { s_button_fill  = fill;  }
void LED_SetSliderStyleMode(uint8_t style){ s_slider_style = style; }
void LED_SetButtonStyleMode(uint8_t style){ s_button_style = style; }
void LED_SetSliderColorMode(uint8_t mode) { s_slider_mode  = mode;  }
void LED_SetButtonColorMode(uint8_t mode) { s_button_mode  = mode;  }

void LED_SetButtonMask(uint8_t mask)      { s_buttonMask   = mask;  }

void LED_SetSliderValue(uint8_t sliderIndex, uint16_t scaledValue)
{
#define SLIDER_DEADZONE 3u
    if (sliderIndex >= LED_SLIDER_COUNT) return;
    if (scaledValue > 1024u) scaledValue = 1024u;

    uint16_t prev  = s_sliderScaled[sliderIndex];
    int16_t  delta = (int16_t)scaledValue - (int16_t)prev;
    if (delta < 0) delta = -delta;
    if ((uint16_t)delta <= SLIDER_DEADZONE) return;

    s_sliderScaled[sliderIndex] = scaledValue;
}

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
