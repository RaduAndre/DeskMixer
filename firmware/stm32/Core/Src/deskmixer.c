/**
 * @file    deskmixer.c
 * @brief   Top-level DeskMixer application.
 *
 * Exact functional port of the ESP32/Arduino firmware:
 *   - Reads 5 analog sliders via ADC1 and sends them every SEND_INTERVAL_MS
 *   - Reads 6 debounced buttons and sends a press event on each 0→1 edge
 *   - Handles handshake and GET_CONFIG via USB CDC (via comm.c)
 *   - Drives the SK6812 LED surf animation and peripheral LED effects
 *     (slider VU bars + button LEDs) via leds.c
 *
 * Timing is non-blocking: slider transmission is rate-limited with a
 * HAL_GetTick() comparison, buttons are polled every loop iteration.
 */

#include "deskmixer.h"
#include "sliders.h"
#include "buttons.h"
#include "comm.h"
#include "leds.h"
#include "display.h"
#include "flash.h"
#include "main.h"

/* ── Configuration ───────────────────────────────────────────────────── */
#define SEND_INTERVAL_MS   10   /**< Slider data transmit interval (ms)     */

/* ── State ───────────────────────────────────────────────────────────── */
static uint32_t s_lastSendTime = 0;

/* ── Public functions ────────────────────────────────────────────────── */

void DESKMIXER_Init(void)
{
    /* 1. Flash (non-fatal if absent) */
    FLASH_Init();

    /* 2. OLED display */
    if (DISPLAY_Init() == 0)
    {
        DISPLAY_ShowSplash();
    }

    /* 3. SK6812MINI LEDs – start animation from blank */
    LED_Init();
    LED_RedToBlue();   /* no-op, clears strip and starts surf anim */

    /* 4. Slider ADC (runs calibration) */
    SLIDERS_Init();

    /* 5. Button GPIO (reads initial state to suppress boot events) */
    BUTTONS_Init();

    /* 6. USB CDC communication (sends handshake response) */
    COMM_Init();

    s_lastSendTime = HAL_GetTick();
}

void DESKMIXER_Run(void)
{
    /* ── Step 1: Poll buttons (every loop iteration for low latency) ── */
    BUTTONS_Read();

    /* ── Step 2: Update button LED mask (every loop) ─────────────────── */
    {
        uint8_t mask = 0;
        for (uint8_t i = 0; i < NUM_BUTTONS; i++) {
            if (BUTTONS_GetState(i)) {
                mask |= (uint8_t)(1u << i);
            }
        }
        LED_SetButtonMask(mask);
    }

    /* ── Step 3: Send button press events immediately (one-shot) ────── */
    for (uint8_t i = 0; i < NUM_BUTTONS; i++)
    {
        if (BUTTONS_GetPressEvent(i))
        {
            COMM_SendButtonPress(i);
        }
    }

    /* ── Step 4: Read sliders every loop for low-latency LED update ──── */
    /*
     * SLIDERS_Read() takes ~20 µs (5 ch × ~4 µs ADC conversion).
     * We call it unconditionally so LED VU bars track the sliders
     * with sub-millisecond latency rather than being bound to the
     * 10 ms USB send window.
     */
    SLIDERS_Read();
    {
        const uint16_t *rawVals = SLIDERS_GetRaw();
        for (uint8_t i = 0; i < NUM_SLIDERS; i++) {
            LED_SetSliderValue(i, rawVals[i]);
        }
    }

    /* ── Step 5: Rate-limited USB CDC transmission (every 10 ms) ──────── */
    uint32_t now = HAL_GetTick();
    if ((now - s_lastSendTime) >= SEND_INTERVAL_MS)
    {
        s_lastSendTime = now;
        /* Transmit: "Slider 1 VAL|Slider 2 VAL|...\r\n" (0-1000 scale) */
        COMM_SendSliders(SLIDERS_GetAll(), NUM_SLIDERS);
    }

    /* ── Step 6: Non-blocking LED animation tick ─────────────────────── */
    LED_Process();
}
