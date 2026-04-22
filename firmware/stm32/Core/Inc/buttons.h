/**
 * @file    buttons.h
 * @brief   Debounced button reader for DeskMixer STM32.
 *
 * Reads 6 push-buttons wired with internal pull-ups (active LOW).
 * Pin mapping (physical pin → MCU pin):
 *   Button 1 → pin 19 = PB1
 *   Button 2 → pin 20 = PB2
 *   Button 3 → pin 39 = PB3
 *   Button 4 → pin 40 = PB4
 *   Button 5 → pin 21 = PB10
 *   Button 6 → pin 22 = PB11
 *
 * Debounce: a state change is only accepted after the pin has been stable
 * for DEBOUNCE_MS milliseconds. The pressed state is reported as 1, released
 * as 0 – matching the ESP32 firmware convention.
 *
 * Press events (0→1 edge) are latched via BUTTONS_GetPressEvent() so that
 * fast single presses are never missed even if the loop is slow.
 */

#ifndef BUTTONS_H
#define BUTTONS_H

#include <stdint.h>

/* ---- Configuration ----------------------------------------------------- */
#define NUM_BUTTONS     6
#define DEBOUNCE_MS     5    /**< 5 ms covers physical bounce for tactile switches */

/* ---- Public API -------------------------------------------------------- */

/**
 * @brief  Initialise the button subsystem.
 *         GPIO must already be configured (done by MX_GPIO_Init).
 */
void BUTTONS_Init(void);

/**
 * @brief  Poll all buttons. Call once per main loop iteration.
 *         Internally timestamps via HAL_GetTick().
 */
void BUTTONS_Read(void);

/**
 * @brief  Get the debounced current state of a button (0-indexed).
 * @retval 1 = pressed, 0 = released.
 */
uint8_t BUTTONS_GetState(uint8_t index);

/**
 * @brief  Check if a debounced press event (0→1 edge) occurred since the
 *         last call to this function for the given button.
 *         The latch is cleared on read.
 * @param  index  Button index [0..NUM_BUTTONS-1]
 * @retval 1 if a new press was detected, 0 otherwise.
 */
uint8_t BUTTONS_GetPressEvent(uint8_t index);

#endif /* BUTTONS_H */
