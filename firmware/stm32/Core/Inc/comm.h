/**
 * @file    comm.h
 * @brief   USB CDC serial communication for DeskMixer STM32.
 *
 * Implements the same wire protocol as the original ESP32/Arduino firmware
 * so the Python host application requires zero changes.
 *
 * Protocol (newline-terminated ASCII lines):
 *
 *  Host → Device:
 *    "DeskMixer controller request"   → device replies with HANDSHAKE_RESPONSE
 *    "GET_CONFIG"                     → device replies with CONFIG line
 *
 *  Device → Host:
 *    Handshake : "DeskMixer Controller Ready\r\n"
 *    Config    : "CONFIG:SLIDERS:5:BUTTONS:6:SCREEN:1\r\n"
 *    Sliders   : "Slider 1 512|Slider 2 1024|Slider 3 0|...\r\n"  (delta-gated, max 100 Hz)
 *    Button    : "Button X 1\r\n"                                  (on press edge, reliable)
 *
 * Slider values are in the range 0-1024 (raw 12-bit ADC >> 2).
 * Python host divides by 1024.0 to obtain a float in [0.0 .. 1.0].
 * Packets are skipped when no slider changes by more than the threshold,
 * so idle USB bandwidth consumption is near zero.
 *
 * ── USB CDC dependency ───────────────────────────────────────────────────
 * This file requires the STM32 USB Device CDC middleware.
 * In STM32CubeIDE / CubeMX:
 *   1. Open deskmixer.ioc → Middleware → USB_DEVICE → Class: CDC
 *   2. Re-generate code – this creates USB_DEVICE/ with usbd_cdc_if.c
 *   3. usbd_cdc_if.c exposes:
 *        extern uint8_t CDC_Transmit_FS(uint8_t *Buf, uint16_t Len);
 *        extern void    usbd_cdc_if_RxCallback(uint8_t *buf, uint32_t len);
 *   4. In usbd_cdc_if.c, inside CDC_Receive_FS(), call COMM_OnRxData().
 * ────────────────────────────────────────────────────────────────────────
 */

#ifndef COMM_H
#define COMM_H

#include <stdint.h>

/* ---- Configuration ----------------------------------------------------- */
#define COMM_TX_BUF_SIZE   256
#define COMM_RX_BUF_SIZE   128

/* ---- Public API -------------------------------------------------------- */

/**
 * @brief  Initialise the communication layer.
 *         Call after USB device stack has started.
 *         Sends the handshake response on startup.
 */
void COMM_Init(void);

/**
 * @brief  Called by the USB CDC receive callback (CDC_Receive_FS).
 *         Buffers incoming bytes and processes complete lines.
 * @param  buf  Pointer to received data
 * @param  len  Number of bytes received
 */
void COMM_OnRxData(const uint8_t *buf, uint32_t len);

/**
 * @brief  Send slider data line.
 *         Format: "Slider 1 VAL|Slider 2 VAL|...|Slider 5 VAL\r\n"
 *         VAL is in range 0-1000 (= volume * 1000, e.g. 750 = 75.0% volume).
 *         Python host divides by 1000.0 to get the float it passes to the
 *         Windows audio API.
 * @param  values  Array of NUM_SLIDERS (5) slider values [0-1000]
 */
void COMM_SendSliders(const uint16_t *values, uint8_t count);

/**
 * @brief  Send a button press event.
 *         Format: "Button N 1\r\n"  (1-indexed, N = index+1)
 */
void COMM_SendButtonPress(uint8_t index);

/**
 * @brief  Low-level transmit.  Wraps CDC_Transmit_FS with a short
 *         busy-wait retry so callers do not need to handle USBD_BUSY.
 * @param  str  Null-terminated string to send (max COMM_TX_BUF_SIZE-1 bytes)
 */
void COMM_Send(const char *str);

#endif /* COMM_H */
