#ifndef PARAMS_H
#define PARAMS_H

#include <stdint.h>

#define MAX_PARAM_NAME_LEN 16
#define PARAMS_NUM_SLIDERS  5
#define PARAMS_NUM_BUTTONS  6

/* ── Name params ──────────────────────────────────────────────────── */
void PARAMS_Init(void);
void PARAMS_Load(void);
void PARAMS_Save(void);
void PARAMS_Update(const char* param_name, const char* param_value);
void PARAMS_SendList(void);
void PARAMS_Process(void);

const char* PARAMS_GetSliderName(uint8_t index);
const char* PARAMS_GetButtonName(uint8_t index);

/* ── LED params – setters (mark save pending) ─────────────────────── */
void PARAMS_SetBrightness(uint8_t pct);          /* 0-100              */
void PARAMS_SetSliderStyle(uint8_t style);       /* 0-N                */
void PARAMS_SetSliderMode(uint8_t mode);         /* 0=All/Rand 1=Per/Custom */
void PARAMS_SetButtonStyle(uint8_t style);       /* 0-N                */
void PARAMS_SetButtonMode(uint8_t mode);         /* 0=All/Rand 1=Per/Custom */
void PARAMS_SetSliderFill(uint8_t fill);         /* 0=off 1=vol 2=full */
void PARAMS_SetButtonFill(uint8_t fill);         /* 0=off 1=press 2=on */
void PARAMS_SetAnimSpeed(uint8_t speed);         /* 1-10               */
void PARAMS_SetSliderColor(uint8_t idx, uint8_t r, uint8_t g, uint8_t b);
void PARAMS_SetButtonColor(uint8_t idx, uint8_t r, uint8_t g, uint8_t b);

/* ── LED params – getters ─────────────────────────────────────────── */
uint8_t PARAMS_GetBrightness(void);
uint8_t PARAMS_GetSliderStyle(void);
uint8_t PARAMS_GetSliderMode(void);
uint8_t PARAMS_GetButtonStyle(void);
uint8_t PARAMS_GetButtonMode(void);
uint8_t PARAMS_GetSliderFill(void);
uint8_t PARAMS_GetButtonFill(void);
uint8_t PARAMS_GetAnimSpeed(void);
const uint8_t* PARAMS_GetSliderColor(uint8_t idx); /* returns [R,G,B] */
const uint8_t* PARAMS_GetButtonColor(uint8_t idx); /* returns [R,G,B] */

/* ── Apply stored LED params to the LED driver ────────────────────── */
void PARAMS_ApplyToLeds(void);

#endif /* PARAMS_H */
