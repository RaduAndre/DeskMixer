/**
 * @file    sliders.h
 * @brief   Analog slider reader for DeskMixer STM32.
 *
 * Reads 5 potentiometer sliders connected to ADC1 channels 0-4
 * (physical pins 10-14 = PA0-PA4).
 *
 * The CubeMX-generated MX_ADC1_Init() only configures a single channel.
 * This driver overrides the channel selection per-read so that all 5
 * channels can be sampled sequentially without needing DMA scan mode.
 * Values are returned in the range 0-1023 (10-bit, matching the ESP32
 * analogReadResolution(10) setting used in the original firmware).
 */

#ifndef SLIDERS_H
#define SLIDERS_H

#include <stdint.h>

/* ---- Configuration ----------------------------------------------------- */
#define NUM_SLIDERS     5       /**< Number of analog sliders                */
#define SLIDER_MAX_VAL  1000    /**< Volume scale max (sent as volume × 1000)*/
#define SLIDER_RAW_MAX  4095    /**< Raw 12-bit ADC maximum value             */

/* ---- Public API -------------------------------------------------------- */

/**
 * @brief  Initialise the slider subsystem.
 *         Must be called after MX_ADC1_Init().
 *         Runs ADC calibration (required on STM32F1 for accuracy).
 */
void SLIDERS_Init(void);

/**
 * @brief  Read all 5 slider values and store internally.
 *         Call this once per main loop iteration.
 */
void SLIDERS_Read(void);

/**
 * @brief  Get the last-read value for a specific slider (0-indexed).
 * @param  index  Slider index [0..NUM_SLIDERS-1]
 * @retval 10-bit value [0..1023], or 0 on invalid index.
 */
uint16_t SLIDERS_GetValue(uint8_t index);

/**
 * @brief  Pointer to the internal values array for bulk access.
 * @retval Const pointer to array of NUM_SLIDERS uint16_t values.
 */
const uint16_t *SLIDERS_GetAll(void);

/**
 * @brief  Pointer to the raw 12-bit ADC values array [0..4095].
 *         Updated by the last SLIDERS_Read() call.
 * @retval Const pointer to array of NUM_SLIDERS uint16_t values.
 */
const uint16_t *SLIDERS_GetRaw(void);

#endif /* SLIDERS_H */
