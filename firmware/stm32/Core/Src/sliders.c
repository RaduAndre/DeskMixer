/**
 * @file    sliders.c
 * @brief   Analog slider reader – software-sequential ADC1 scan.
 *
 * The STM32F103 ADC1 is 12-bit (0-4095). We map the raw reading to the
 * range 0-1024 using a power-of-two right-shift:
 *
 *   value = raw_12bit >> 2   (equivalent to raw / 4 ≈ raw * 1024 / 4096)
 *
 * This gives exactly 0-1023 for raw 0-4095, with 1024 reserved for a
 * physically-pegged maximum.  Any raw reading >= 4060 (~99.1% of ADC
 * range) is clamped to 1024 so real-world potentiometers that cannot
 * mechanically reach the absolute ADC ceiling still report 100%.
 * The Python host divides by 1024.0 to get a float [0.0-1.0].
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
static uint16_t s_values[NUM_SLIDERS] = {0};  /* 0-1024 (USB/comms scale) */
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
    sConfig.SamplingTime   = ADC_SAMPLETIME_71CYCLES_5;  /* 71.5 cyc @ 12 MHz ≈ 6 µs/ch;
                                                           * 5 ch × 6 µs ≈ 30 µs total.
                                                           * Adequate for ≤10 kΩ source impedance
                                                           * (STM32F1 spec requires ≈0.4 µs min). */

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
            /* Map raw 12-bit [0-4095] → [0-1024] via power-of-two shift.   */
            /* raw >> 2 = raw / 4 → range [0-1023].  Clamp anything >= 3900 */
            /* (~95.2% of ADC range) to 1024 so real-world potentiometers   */
            /* that cannot reach the absolute ADC ceiling still report 100%. */
            uint16_t mapped = (uint16_t)(s_raw12[i] >> 2u);
            if (s_raw12[i] >= 3900u) mapped = 1024u;
            s_values[i] = mapped;
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
