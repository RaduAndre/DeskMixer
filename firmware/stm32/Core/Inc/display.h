/**
 * @file    display.h
 * @brief   SSD1306 128×64 OLED display driver for DeskMixer STM32 port.
 *
 * Interface: I2C1 (PB6 = SCL, PB7 = SDA, 100 kHz)
 * Address  : 0x3C (SA0 tied LOW) – change to 0x3D if SA0 is HIGH.
 *
 * Provides minimal functions to initialise the display and render text.
 * A built-in 6×8 ASCII font (printable chars 0x20-0x7E) is included in
 * the .c file – no external font dependency required.
 */

#ifndef DISPLAY_H
#define DISPLAY_H

#include <stdint.h>

/* ---- Configuration ----------------------------------------------------- */

#define DISPLAY_I2C_ADDR   (0x3C << 1)   /**< 7-bit addr shifted for HAL   */
#define DISPLAY_WIDTH      128
#define DISPLAY_HEIGHT     64
#define DISPLAY_PAGES      (DISPLAY_HEIGHT / 8)   /**< 8 pages              */

/* ---- Public API -------------------------------------------------------- */

/**
 * @brief  Initialise the SSD1306 display.
 *         Must be called after MX_I2C1_Init().
 * @retval 0 on success, non-zero on I2C error.
 */
int DISPLAY_Init(void);

/**
 * @brief  Clear the frame-buffer (RAM only – call DISPLAY_Flush to update).
 */
void DISPLAY_Clear(void);

/**
 * @brief  Send the full frame-buffer to the display via I2C.
 */
void DISPLAY_Flush(void);

/**
 * @brief  Draw a single ASCII character at the given column/page position.
 * @param  col   Pixel column [0-127] (snapped to 6-pixel boundary internally)
 * @param  page  Page [0-7]
 * @param  c     ASCII character
 */
void DISPLAY_DrawChar(uint8_t col, uint8_t page, char c);

/**
 * @brief  Draw a null-terminated string starting at col/page.
 */
void DISPLAY_DrawString(uint8_t col, uint8_t page, const char *str);

/**
 * @brief  Show a centred "DeskMixer" splash on the display.
 *         Clears the buffer, writes text, and flushes in one call.
 */
void DISPLAY_ShowSplash(void);

/**
 * @brief  Update the display's awareness of the USB connection state.
 * @param  connected  1 if connected, 0 if disconnected.
 */
void DISPLAY_SetConnectionState(uint8_t connected);

/**
 * @brief  Temporarily override the display to show a string (e.g. parameter name).
 * @param  text  Null-terminated string to show.
 */
void DISPLAY_ShowOverride(const char* text);

/**
 * @brief  Periodic tick for display state transitions. Call from main loop.
 */
void DISPLAY_Process(void);

#endif /* DISPLAY_H */
