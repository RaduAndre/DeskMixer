#ifndef PARAMS_H
#define PARAMS_H

#include <stdint.h>

#define MAX_PARAM_NAME_LEN 16

void PARAMS_Init(void);
void PARAMS_Load(void);
void PARAMS_Save(void);
void PARAMS_Update(const char* param_name, const char* param_value);
void PARAMS_SendList(void);
void PARAMS_Process(void);

const char* PARAMS_GetSliderName(uint8_t index);
const char* PARAMS_GetButtonName(uint8_t index);

#endif /* PARAMS_H */
