#include "params.h"
#include "flash.h"
#include "comm.h"
#include <string.h>
#include <stdio.h>

#define PARAMS_FLASH_ADDR 0x000000 // sector 0 of SPI flash
#define PARAMS_MAGIC      0xA55A

typedef struct {
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
    uint16_t magic;
} Params_t;

static Params_t s_params;
static uint8_t s_save_pending = 0;

static void set_default(void) {
    memset(&s_params, 0, sizeof(s_params));
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
    s_params.magic = PARAMS_MAGIC;
}

void PARAMS_Init(void) {
    PARAMS_Load();
}

void PARAMS_Load(void) {
    FLASH_Read(PARAMS_FLASH_ADDR, (uint8_t*)&s_params, sizeof(s_params));
    if (s_params.magic != PARAMS_MAGIC) {
        set_default();
        PARAMS_Save();
    }
}

void PARAMS_Save(void) {
    FLASH_EraseSector(PARAMS_FLASH_ADDR);
    FLASH_PageProgram(PARAMS_FLASH_ADDR, (const uint8_t*)&s_params, sizeof(s_params));
}

void PARAMS_Update(const char* param_name, const char* param_value) {
    uint8_t changed = 0;
    char val[MAX_PARAM_NAME_LEN];
    strncpy(val, param_value, MAX_PARAM_NAME_LEN - 1);
    val[MAX_PARAM_NAME_LEN - 1] = '\0';

    if (strcmp(param_name, "Slider 1") == 0) { strcpy(s_params.s1, val); changed = 1; }
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

    if (changed) {
        s_save_pending = 1;
    }
}

void PARAMS_Process(void) {
    if (s_save_pending) {
        s_save_pending = 0;
        PARAMS_Save();
    }
}

void PARAMS_SendList(void) {
    char buf[512];
    snprintf(buf, sizeof(buf), "PARAMS_LIST: \"Slider 1\":\"%s\"|\"Slider 2\":\"%s\"|\"Slider 3\":\"%s\"|\"Slider 4\":\"%s\"|\"Slider 5\":\"%s\"|\"Button 1\":\"%s\"|\"Button 2\":\"%s\"|\"Button 3\":\"%s\"|\"Button 4\":\"%s\"|\"Button 5\":\"%s\"|\"Button 6\":\"%s\"\r\n",
        s_params.s1, s_params.s2, s_params.s3, s_params.s4, s_params.s5,
        s_params.b1, s_params.b2, s_params.b3, s_params.b4, s_params.b5, s_params.b6);
    COMM_Send(buf);
}

const char* PARAMS_GetSliderName(uint8_t index) {
    switch(index) {
        case 0: return s_params.s1;
        case 1: return s_params.s2;
        case 2: return s_params.s3;
        case 3: return s_params.s4;
        case 4: return s_params.s5;
        default: return "";
    }
}

const char* PARAMS_GetButtonName(uint8_t index) {
    switch(index) {
        case 0: return s_params.b1;
        case 1: return s_params.b2;
        case 2: return s_params.b3;
        case 3: return s_params.b4;
        case 4: return s_params.b5;
        case 5: return s_params.b6;
        default: return "";
    }
}
