/**
 * @file    sliders.c
 * @brief   Analog slider reader – software-sequential ADC1 scan.
 *
 * The STM32F103 ADC1 is 12-bit (0-4095). We map the raw reading to the
 * range 0-1000 using integer arithmetic:
 *
 *   value = (raw_12bit * 1000) / 4095
 *
 * This means the board sends the volume level directly as a number that
 * represents volume * 1000 (e.g. 750 = 75.0% volume). The Python host
 * simply divides by 1000.0 to get a float [0.0-1.0] ready for the
 * Windows audio API – no magic 1023 divisor needed.
 *
 * Channel mapping:
 *   Slider 1 → ADC1_IN0 (PA0, physical pin 10)
 *   Slider 2 → ADC1_IN1 (PA1, physical pin 11)
 *   Slider 3 → ADC1_IN2 (PA2, physical pin 12)
 *   Slider 4 → ADC1_IN3 (PA3, physical pin 13)
 *   Slider 5 → ADC1_IN4 (PA4, physical pin 14)
 */

#include "sliders.h"
#include "main.h"

/* ── External ADC handle from main.c ──────────────────────────────────── */
extern ADC_HandleTypeDef hadc1;

/* ── ADC channel table ───────────────────────────────────────────────── */
static const uint32_t s_channels[NUM_SLIDERS] = {
    ADC_CHANNEL_0,   /* PA0 – Slider 1 */
    ADC_CHANNEL_1,   /* PA1 – Slider 2 */
    ADC_CHANNEL_2,   /* PA2 – Slider 3 */
    ADC_CHANNEL_3,   /* PA3 – Slider 4 */
    ADC_CHANNEL_4,   /* PA4 – Slider 5 */
};

/* ── Internal value store ─────────────────────────────────────────────── */
static uint16_t s_values[NUM_SLIDERS] = {0};  /* 0-1000 (USB/comms scale) */
static uint16_t s_raw12[NUM_SLIDERS]  = {0};  /* 0-4095 (raw 12-bit ADC)  */

/* ── Public functions ────────────────────────────────────────────────── */

void SLIDERS_Init(void)
{
    /*
     * Run ADC self-calibration.
     * Required on STM32F1 for best accuracy.
     * HAL_ADCEx_Calibration_Start() must be called AFTER HAL_ADC_Init().
     */
    HAL_ADCEx_Calibration_Start(&hadc1);
}

void SLIDERS_Read(void)
{
    static uint8_t first_read = 1;
    ADC_ChannelConfTypeDef sConfig = {0};
    sConfig.Rank           = ADC_REGULAR_RANK_1;
    sConfig.SamplingTime   = ADC_SAMPLETIME_239CYCLES_5; /* max sample time for stability */

    for (uint8_t i = 0; i < NUM_SLIDERS; i++) {
        /* Re-configure ADC to the next channel */
        sConfig.Channel = s_channels[i];
        HAL_ADC_ConfigChannel(&hadc1, &sConfig);

        /* Start single conversion */
        HAL_ADC_Start(&hadc1);

        if (HAL_ADC_PollForConversion(&hadc1, 10) == HAL_OK) {
            uint32_t raw = HAL_ADC_GetValue(&hadc1);   /* 12-bit [0-4095]     */
            
            /* Software Low-Pass Filter (Exponential Moving Average) 
             * Weighs the new reading 1/4 and the old reading 3/4.
             * Eliminates spikes and crosstalk from USB/SPI noise. */
            if (first_read) {
                 s_raw12[i] = (uint16_t)raw;
            } else {
                 s_raw12[i] = (uint16_t)(((s_raw12[i] * 3) + raw) / 4);
            }
            
            /* Use the filtered value for the mapped result */
            /* Map to 0-1000 (volume * 1000) using integer math, no float    */
            s_values[i] = (uint16_t)((s_raw12[i] * 1000u) / 4095u);
        }

        HAL_ADC_Stop(&hadc1);
    }
    
    first_read = 0;
}

uint16_t SLIDERS_GetValue(uint8_t index)
{
    if (index >= NUM_SLIDERS) return 0;
    return s_values[index];
}

const uint16_t *SLIDERS_GetAll(void)
{
    return s_values;
}

const uint16_t *SLIDERS_GetRaw(void)
{
    return s_raw12;
}
