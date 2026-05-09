/**
 * @file    leds.h
 * @brief   SK6812MINI LED driver for DeskMixer STM32 port.
 *
 * Layout:
 *   - 5 strips of 8 LEDs next to each slider  → 40 LEDs  (indices 0–39)
 *   - 2 strips of 3 LEDs next to buttons       →  6 LEDs  (indices 40–45)
 *   Total: 46 LEDs on a single data line (PB15 / SPI2_MOSI)
 *
 * Protocol:  SK6812 uses a 800 kHz NZR-like protocol, encoded here
 *            via SPI at 3.2 MHz (STM32 APB1 = 24 MHz, prescaler = 8).
 *            Each bit is sent as a 4-bit SPI word:
 *              '0' → 1000   (high ~312 ns, low ~937 ns)
 *              '1' → 1110   (high ~937 ns, low ~312 ns)
 *            Reset: ≥80 µs of low → sent as 0x00 bytes.
 *
 * Color order: GRB  (SK6812 standard)
 *
 * ── Behaviour overview ──────────────────────────────────────────────────────
 *   Max brightness: 20% (51/255).
 *
 *   1. Color-surf animation (driven by LED_Process):
 *      All 7 rows cycle through a rainbow palette.  The board stays uniform
 *      for 600 ms, then a sweep wave rolls left→right (one row per 60 ms)
 *      assigning the next color until every row matches – then repeats.
 *
 *   2. Slider VU bars (set via LED_SetSliderValue):
 *      Each slider (0–4) controls 8 LEDs using the raw 12-bit ADC value
 *      [0..4095].  Every 512 counts lights one additional LED (j-th LED
 *      lights when raw > j×512).  Lit LEDs use the current row surf color;
 *      unlit LEDs are always off.
 *
 *   3. Button LEDs (set via LED_SetButtonMask):
 *      6 button LEDs (one per button), arranged as 2 rows of 3.
 *      A button's LED is lit only while the button is held down.
 */

#ifndef LEDS_H
#define LEDS_H

#include <stdint.h>

/* ---- Configuration ----------------------------------------------------- */

#define LED_SLIDER_COUNT   5   /**< Number of slider LED strips              */
#define LED_PER_SLIDER     8   /**< LEDs per slider strip                    */
#define LED_BUTTON_COUNT   2   /**< Number of button LED strips              */
#define LED_PER_BUTTON     3   /**< LEDs per button strip                    */

#define LED_TOTAL          (LED_SLIDER_COUNT * LED_PER_SLIDER + \
                            LED_BUTTON_COUNT * LED_PER_BUTTON)  /**< = 46   */

/* ---- Public API -------------------------------------------------------- */

/**
 * @brief  Initialise the LED subsystem.
 *         Must be called after MX_SPI2_Init() and MX_DMA_Init().
 */
void LED_Init(void);

/**
 * @brief  Set the colour of a single LED (0-indexed).
 * @param  index  LED index [0 .. LED_TOTAL-1]
 * @param  r      Red   component [0-255]
 * @param  g      Green component [0-255]
 * @param  b      Blue  component [0-255]
 */
void LED_SetColor(uint8_t index, uint8_t r, uint8_t g, uint8_t b);

/**
 * @brief  Fill all LEDs with the same colour.
 */
void LED_Fill(uint8_t r, uint8_t g, uint8_t b);

/**
 * @brief  Legacy no-op (animation is now driven by LED_Process).
 */
void LED_RedToBlue(void);

/**
 * @brief  Update the slider VU-bar state for one slider.
 * @param  sliderIndex  Slider index [0..LED_SLIDER_COUNT-1]
 * @param  rawValue     Raw 12-bit ADC value [0..4095]
 *                      512 counts → 1 LED lit; all 8 LEDs lit at 4096.
 *                      (j-th LED lights when rawValue > j × 512)
 */
void LED_SetSliderValue(uint8_t sliderIndex, uint16_t rawValue);

/**
 * @brief  Update which button LEDs are lit.
 * @param  mask  Bit-mask of pressed buttons; bit i = 1 → button i pressed.
 *               Bits 0-5 correspond to buttons 0-5.
 */
void LED_SetButtonMask(uint8_t mask);

/**
 * @brief  Non-blocking LED animation tick.  Call every main-loop iteration.
 *         Advances the surf animation (80 ms ticks), rebuilds the LED
 *         buffer from slider/button state, and calls LED_Show().
 */
void LED_Process(void);

/**
 * @brief  Push the current colour buffer to the LED strip via SPI2 DMA.
 *         Non-blocking – uses DMA TX.
 */
void LED_Show(void);

/**
 * @brief  Clear (turn off) all LEDs and show immediately.
 */
void LED_Clear(void);

/* ---- Dynamic configuration setters ------------------------------------ */

/**
 * @brief  Set LED brightness as a percentage of the hardware maximum.
 * @param  pct  0-100 (0 = off, 100 = full 20% hardware cap)
 */
void LED_SetBrightnessPct(uint8_t pct);

/**
 * @brief  Set animation speed level.
 * @param  speed  1 (slowest) … 10 (fastest). Default 5.
 */
void LED_SetAnimSpeedLevel(uint8_t speed);

/**
 * @brief  Set slider LED fill mode.
 * @param  fill  0=off  1=volume-bar  2=always-on
 */
void LED_SetSliderFillMode(uint8_t fill);

/**
 * @brief  Set button LED fill mode.
 * @param  fill  0=off  1=on-press  2=always-on
 */
void LED_SetButtonFillMode(uint8_t fill);

/**
 * @brief  Set slider animation style (stored; future style switching).
 * @param  style  0 = surf (default)
 */
void LED_SetSliderStyleMode(uint8_t style);

/**
 * @brief  Set button animation style (stored; future style switching).
 * @param  style  0 = surf (default)
 */
void LED_SetButtonStyleMode(uint8_t style);

/**
 * @brief  Set a custom RGB colour for one slider strip.
 *         (0,0,0) = revert to animated palette colour.
 * @param  idx   Slider index [0..LED_SLIDER_COUNT-1]
 * @param  r,g,b RGB components [0-255]
 */
void LED_SetSliderColor(uint8_t idx, uint8_t r, uint8_t g, uint8_t b);

/**
 * @brief  Set a custom RGB colour for one button LED.
 *         (0,0,0) = revert to animated palette colour.
 * @param  idx   Button index [0..5]
 * @param  r,g,b RGB components [0-255]
 */
void LED_SetButtonColor(uint8_t idx, uint8_t r, uint8_t g, uint8_t b);

#endif /* LEDS_H */
