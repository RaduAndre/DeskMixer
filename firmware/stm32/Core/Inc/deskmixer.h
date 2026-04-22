/**
 * @file    deskmixer.h
 * @brief   Top-level DeskMixer application logic.
 *
 * Replaces the Arduino setup() / loop() pattern.
 * DESKMIXER_Init()  → call once after all peripheral inits
 * DESKMIXER_Run()   → call in the infinite while(1) loop
 */

#ifndef DESKMIXER_H
#define DESKMIXER_H

/**
 * @brief  One-time application initialisation.
 *         Initialises sliders, buttons, communication, LEDs, and display.
 */
void DESKMIXER_Init(void);

/**
 * @brief  Main application tick. Call continuously in while(1).
 *         Handles:
 *           - Slider ADC reads (every SEND_INTERVAL_MS)
 *           - Button debounce and press-event reporting
 *           - USB CDC packet transmission
 */
void DESKMIXER_Run(void);

#endif /* DESKMIXER_H */
