#include "params.h"
#include "leds.h"
#include "flash.h"
#include "comm.h"
#include <string.h>
#include <stdio.h>

#define PARAMS_FLASH_ADDR 0x000000   /* sector 0 of SPI flash */

/*
 * Magic bumped from 0xA55A to 0xA55B so boards with the old
 * (names-only) struct automatically re-initialise to safe defaults
 * the first time they boot with this firmware.
 */
#define PARAMS_MAGIC  0xA55C

/* ── Flash layout ──────────────────────────────────────────────────────── */

typedef struct {
    /* Slider / button display names */
    char s1[MAX_PARAM_NAME_LEN];
    char s2[MAX_PARAM_NAME_LEN];
    char s3[MAX_PARAM_NAME_LEN];
    char s4[MAX_PARAM_NAME_LEN];
    char s5[MAX_PARAM_NAME_LEN];
    char b1[MAX_PARAM_NAME_LEN];
    char b2[MAX_PARAM_NAME_LEN];
    char b3[MAX_PARAM_NAME_LEN];
    char b4[MAX_PARAM_NAME_LEN];
    char b5[MAX_PARAM_NAME_LEN];
    char b6[MAX_PARAM_NAME_LEN];

    /* LED configuration */
    uint8_t brightness;    /* 0-100 %                          */
    uint8_t slider_style;  /* 0-N animation style              */
    uint8_t slider_mode;   /* 0=All/Rand 1=Per/Custom          */
    uint8_t button_style;  /* 0-N animation style              */
    uint8_t button_mode;   /* 0=All/Rand 1=Per/Custom          */
    uint8_t slider_fill;   /* 0=off  1=volume  2=always-on     */
    uint8_t button_fill;   /* 0=off  1=on-press  2=always-on   */
    uint8_t anim_speed;    /* 1-10 (5 = default speed)         */

    /* Per-slider RGB colours (0,0,0 = use palette/default) */
    uint8_t slider_colors[PARAMS_NUM_SLIDERS][3];

    /* Per-button RGB colours (0,0,0 = use palette/default) */
    uint8_t button_colors[PARAMS_NUM_BUTTONS][3];

    uint16_t magic;
} Params_t;

static Params_t s_params;
static uint8_t  s_save_pending = 0;

/* ── Defaults ──────────────────────────────────────────────────────────── */

static void set_default(void)
{
    memset(&s_params, 0, sizeof(s_params));

    /* Names */
    strcpy(s_params.s1, "Slider 1");
    strcpy(s_params.s2, "Slider 2");
    strcpy(s_params.s3, "Slider 3");
    strcpy(s_params.s4, "Slider 4");
    strcpy(s_params.s5, "Slider 5");
    strcpy(s_params.b1, "Button 1");
    strcpy(s_params.b2, "Button 2");
    strcpy(s_params.b3, "Button 3");
    strcpy(s_params.b4, "Button 4");
    strcpy(s_params.b5, "Button 5");
    strcpy(s_params.b6, "Button 6");

    /* LED defaults (match Python host defaults) */
    s_params.brightness   = 80;
    s_params.slider_style = 0;
    s_params.slider_mode  = 0;
    s_params.button_style = 0;
    s_params.button_mode  = 0;
    s_params.slider_fill  = 1;
    s_params.button_fill  = 1;
    s_params.anim_speed   = 5;

    /* Default slider colours: 0,61,61 (teal) */
    for (uint8_t i = 0; i < PARAMS_NUM_SLIDERS; i++) {
        s_params.slider_colors[i][0] = 0;
        s_params.slider_colors[i][1] = 61;
        s_params.slider_colors[i][2] = 61;
    }
    /* Default button colours: 61,20,0 (amber) */
    for (uint8_t i = 0; i < PARAMS_NUM_BUTTONS; i++) {
        s_params.button_colors[i][0] = 61;
        s_params.button_colors[i][1] = 20;
        s_params.button_colors[i][2] = 0;
    }

    s_params.magic = PARAMS_MAGIC;
}

/* ── Init / Load / Save ────────────────────────────────────────────────── */

void PARAMS_Init(void)
{
    PARAMS_Load();
}

void PARAMS_Load(void)
{
    FLASH_Read(PARAMS_FLASH_ADDR, (uint8_t *)&s_params, sizeof(s_params));
    if (s_params.magic != PARAMS_MAGIC) {
        set_default();
        PARAMS_Save();
    }
}

void PARAMS_Save(void)
{
    FLASH_EraseSector(PARAMS_FLASH_ADDR);
    FLASH_PageProgram(PARAMS_FLASH_ADDR, (const uint8_t *)&s_params, sizeof(s_params));
}

void PARAMS_Process(void)
{
    if (s_save_pending) {
        s_save_pending = 0;
        PARAMS_Save();
    }
}

/* ── Name update (sent by host as Parameter_update: "Slider X" "val") ── */

void PARAMS_Update(const char *param_name, const char *param_value)
{
    uint8_t changed = 0;
    char val[MAX_PARAM_NAME_LEN];
    strncpy(val, param_value, MAX_PARAM_NAME_LEN - 1);
    val[MAX_PARAM_NAME_LEN - 1] = '\0';

    if      (strcmp(param_name, "Slider 1") == 0) { strcpy(s_params.s1, val); changed = 1; }
    else if (strcmp(param_name, "Slider 2") == 0) { strcpy(s_params.s2, val); changed = 1; }
    else if (strcmp(param_name, "Slider 3") == 0) { strcpy(s_params.s3, val); changed = 1; }
    else if (strcmp(param_name, "Slider 4") == 0) { strcpy(s_params.s4, val); changed = 1; }
    else if (strcmp(param_name, "Slider 5") == 0) { strcpy(s_params.s5, val); changed = 1; }
    else if (strcmp(param_name, "Button 1") == 0) { strcpy(s_params.b1, val); changed = 1; }
    else if (strcmp(param_name, "Button 2") == 0) { strcpy(s_params.b2, val); changed = 1; }
    else if (strcmp(param_name, "Button 3") == 0) { strcpy(s_params.b3, val); changed = 1; }
    else if (strcmp(param_name, "Button 4") == 0) { strcpy(s_params.b4, val); changed = 1; }
    else if (strcmp(param_name, "Button 5") == 0) { strcpy(s_params.b5, val); changed = 1; }
    else if (strcmp(param_name, "Button 6") == 0) { strcpy(s_params.b6, val); changed = 1; }

    if (changed) s_save_pending = 1;
}

/* ── PARAMS_LIST transmit ─────────────────────────────────────────────── */

void PARAMS_SendList(void)
{
    char buf[768];
    snprintf(buf, sizeof(buf),
        "PARAMS:S1:%s|S2:%s|S3:%s|S4:%s|S5:%s"
        "|B1:%s|B2:%s|B3:%s|B4:%s|B5:%s|B6:%s"
        "|BR:%d|SF:%d|SS:%d|SM:%d|BF:%d|BS:%d|BM:%d|AS:%d"
        "|SC1:%d,%d,%d|SC2:%d,%d,%d|SC3:%d,%d,%d|SC4:%d,%d,%d|SC5:%d,%d,%d"
        "|BC1:%d,%d,%d|BC2:%d,%d,%d|BC3:%d,%d,%d|BC4:%d,%d,%d|BC5:%d,%d,%d|BC6:%d,%d,%d\r\n",
        s_params.s1, s_params.s2, s_params.s3, s_params.s4, s_params.s5,
        s_params.b1, s_params.b2, s_params.b3, s_params.b4, s_params.b5, s_params.b6,
        s_params.brightness, s_params.slider_fill, s_params.slider_style, s_params.slider_mode,
        s_params.button_fill, s_params.button_style, s_params.button_mode, s_params.anim_speed,
        s_params.slider_colors[0][0], s_params.slider_colors[0][1], s_params.slider_colors[0][2],
        s_params.slider_colors[1][0], s_params.slider_colors[1][1], s_params.slider_colors[1][2],
        s_params.slider_colors[2][0], s_params.slider_colors[2][1], s_params.slider_colors[2][2],
        s_params.slider_colors[3][0], s_params.slider_colors[3][1], s_params.slider_colors[3][2],
        s_params.slider_colors[4][0], s_params.slider_colors[4][1], s_params.slider_colors[4][2],
        s_params.button_colors[0][0], s_params.button_colors[0][1], s_params.button_colors[0][2],
        s_params.button_colors[1][0], s_params.button_colors[1][1], s_params.button_colors[1][2],
        s_params.button_colors[2][0], s_params.button_colors[2][1], s_params.button_colors[2][2],
        s_params.button_colors[3][0], s_params.button_colors[3][1], s_params.button_colors[3][2],
        s_params.button_colors[4][0], s_params.button_colors[4][1], s_params.button_colors[4][2],
        s_params.button_colors[5][0], s_params.button_colors[5][1], s_params.button_colors[5][2]);
    COMM_Send(buf);
}

/* ── Name getters ─────────────────────────────────────────────────────── */

const char *PARAMS_GetSliderName(uint8_t index)
{
    switch (index) {
        case 0: return s_params.s1;
        case 1: return s_params.s2;
        case 2: return s_params.s3;
        case 3: return s_params.s4;
        case 4: return s_params.s5;
        default: return "";
    }
}

const char *PARAMS_GetButtonName(uint8_t index)
{
    switch (index) {
        case 0: return s_params.b1;
        case 1: return s_params.b2;
        case 2: return s_params.b3;
        case 3: return s_params.b4;
        case 4: return s_params.b5;
        case 5: return s_params.b6;
        default: return "";
    }
}

/* ── LED setters ──────────────────────────────────────────────────────── */

void PARAMS_SetBrightness(uint8_t pct)
{
    if (pct > 100) pct = 100;
    if (s_params.brightness == pct) return;
    s_params.brightness = pct;
    s_save_pending = 1;
}

void PARAMS_SetSliderStyle(uint8_t style)
{
    if (s_params.slider_style == style) return;
    s_params.slider_style = style;
    s_save_pending = 1;
}

void PARAMS_SetSliderMode(uint8_t mode)
{
    if (s_params.slider_mode == mode) return;
    s_params.slider_mode = mode;
    s_save_pending = 1;
}

void PARAMS_SetButtonStyle(uint8_t style)
{
    if (s_params.button_style == style) return;
    s_params.button_style = style;
    s_save_pending = 1;
}

void PARAMS_SetButtonMode(uint8_t mode)
{
    if (s_params.button_mode == mode) return;
    s_params.button_mode = mode;
    s_save_pending = 1;
}

void PARAMS_SetSliderFill(uint8_t fill)
{
    if (s_params.slider_fill == fill) return;
    s_params.slider_fill = fill;
    s_save_pending = 1;
}

void PARAMS_SetButtonFill(uint8_t fill)
{
    if (s_params.button_fill == fill) return;
    s_params.button_fill = fill;
    s_save_pending = 1;
}

void PARAMS_SetAnimSpeed(uint8_t speed)
{
    if (speed < 1)  speed = 1;
    if (speed > 10) speed = 10;
    if (s_params.anim_speed == speed) return;
    s_params.anim_speed = speed;
    s_save_pending = 1;
}

void PARAMS_SetSliderColor(uint8_t idx, uint8_t r, uint8_t g, uint8_t b)
{
    if (idx >= PARAMS_NUM_SLIDERS) return;
    s_params.slider_colors[idx][0] = r;
    s_params.slider_colors[idx][1] = g;
    s_params.slider_colors[idx][2] = b;
    s_save_pending = 1;
}

void PARAMS_SetButtonColor(uint8_t idx, uint8_t r, uint8_t g, uint8_t b)
{
    if (idx >= PARAMS_NUM_BUTTONS) return;
    s_params.button_colors[idx][0] = r;
    s_params.button_colors[idx][1] = g;
    s_params.button_colors[idx][2] = b;
    s_save_pending = 1;
}

/* ── LED getters ──────────────────────────────────────────────────────── */

uint8_t PARAMS_GetBrightness(void)   { return s_params.brightness;   }
uint8_t PARAMS_GetSliderStyle(void)  { return s_params.slider_style;  }
uint8_t PARAMS_GetSliderMode(void)   { return s_params.slider_mode;   }
uint8_t PARAMS_GetButtonStyle(void)  { return s_params.button_style;  }
uint8_t PARAMS_GetButtonMode(void)   { return s_params.button_mode;   }
uint8_t PARAMS_GetSliderFill(void)   { return s_params.slider_fill;   }
uint8_t PARAMS_GetButtonFill(void)   { return s_params.button_fill;   }
uint8_t PARAMS_GetAnimSpeed(void)    { return s_params.anim_speed;    }

const uint8_t *PARAMS_GetSliderColor(uint8_t idx)
{
    if (idx >= PARAMS_NUM_SLIDERS) return s_params.slider_colors[0];
    return s_params.slider_colors[idx];
}

const uint8_t *PARAMS_GetButtonColor(uint8_t idx)
{
    if (idx >= PARAMS_NUM_BUTTONS) return s_params.button_colors[0];
    return s_params.button_colors[idx];
}

/* ── Apply stored LED params to LED driver ────────────────────────────── */

void PARAMS_ApplyToLeds(void)
{
    LED_SetBrightnessPct(s_params.brightness);
    LED_SetAnimSpeedLevel(s_params.anim_speed);
    LED_SetSliderFillMode(s_params.slider_fill);
    LED_SetButtonFillMode(s_params.button_fill);
    LED_SetSliderStyleMode(s_params.slider_style);
    LED_SetSliderColorMode(s_params.slider_mode);
    LED_SetButtonStyleMode(s_params.button_style);
    LED_SetButtonColorMode(s_params.button_mode);

    for (uint8_t i = 0; i < PARAMS_NUM_SLIDERS; i++) {
        LED_SetSliderColor(i,
            s_params.slider_colors[i][0],
            s_params.slider_colors[i][1],
            s_params.slider_colors[i][2]);
    }
    for (uint8_t i = 0; i < PARAMS_NUM_BUTTONS; i++) {
        LED_SetButtonColor(i,
            s_params.button_colors[i][0],
            s_params.button_colors[i][1],
            s_params.button_colors[i][2]);
    }
}
