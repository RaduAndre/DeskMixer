/**
 * @file    deskmixer.c
 * @brief   Top-level DeskMixer application.
 *
 * Exact functional port of the ESP32/Arduino firmware:
 *   - Reads 5 analog sliders via ADC1 and sends them at SEND_INTERVAL_MS
 *     only when at least one value has changed (delta-filter in comm.c).
 *   - Reads 6 debounced buttons and sends a press event on each 0→1 edge.
 *   - Handles handshake and GET_CONFIG via USB CDC (via comm.c).
 *   - Drives the SK6812 LED surf animation and peripheral LED effects
 *     (slider VU bars + button LEDs) via leds.c.
 *
 * ── Loop structure ───────────────────────────────────────────────────────
 *
 *  Every loop iteration (~100-200 µs):
 *    1. Poll buttons  (GPIO reads, debounce, fire press events)
 *    2. Update button LED mask
 *    3. LED animation tick + DMA push (non-blocking)
 *
 *  Every SEND_INTERVAL_MS (10 ms):
 *    4. Read all 5 ADC channels (≈ 20 µs)
 *    5. Update LED VU bar values from fresh ADC data
 *    6. Transmit slider packet (only if any value changed – see comm.c)
 *
 * Rationale: ADC reads used to happen every loop iteration for LED
 * latency.  Since LED_Process() itself runs every loop (~1-2 ms) and
 * human perception of VU bar motion is in the 30-50 ms range, sampling
 * at 100 Hz (every 10 ms) is more than adequate and removes 5 blocking
 * ADC conversions from the tight loop, freeing CPU for button polling
 * and DMA completion.
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
#define SEND_INTERVAL_MS   10   /**< Slider sample + transmit interval (ms) */

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

    /* 6. USB CDC communication.
     *    COMM_Init() blocks ~COMM_ENUM_WAIT_MS (600 ms) waiting for the USB
     *    host to enumerate, then sends the startup handshake.  This must be
     *    the last init step so that all other subsystems are ready before
     *    the host can start sending commands. */
    COMM_Init();

    s_lastSendTime = HAL_GetTick();
}

void DESKMIXER_Run(void)
{
    /* ── Step 1: Poll buttons (every loop for low latency) ─────────────── */
    BUTTONS_Read();

    /* ── Step 2: Update button LED mask (every loop) ──────────────────── */
    {
        uint8_t mask = 0;
        for (uint8_t i = 0; i < NUM_BUTTONS; i++) {
            if (BUTTONS_GetState(i)) {
                mask |= (uint8_t)(1u << i);
            }
        }
        LED_SetButtonMask(mask);
    }

    /* ── Step 3: Send button press events immediately (one-shot) ────────── */
    for (uint8_t i = 0; i < NUM_BUTTONS; i++)
    {
        if (BUTTONS_GetPressEvent(i))
        {
            COMM_SendButtonPress(i);
        }
    }

    /* ── Step 4: Non-blocking LED animation tick ──────────────────────── */
    /*
     * LED_Process() runs every loop iteration so animation stays smooth.
     * It does NOT re-read the ADC; it uses the last cached s_sliderRaw[]
     * updated in the 10 ms window below.
     */
    LED_Process();

    /* ── Step 5: 10 ms window – ADC read + USB TX ─────────────────────── */
    uint32_t now = HAL_GetTick();
    if ((now - s_lastSendTime) >= SEND_INTERVAL_MS)
    {
        s_lastSendTime = now;

        /* Read all 5 ADC channels (~20 µs total) */
        SLIDERS_Read();

        /* Push fresh values to LED VU bars (raw 12-bit for sub-segment PWM) */
        const uint16_t *rawVals = SLIDERS_GetRaw();
        for (uint8_t i = 0; i < NUM_SLIDERS; i++) {
            LED_SetSliderValue(i, rawVals[i]);
        }

        /* Transmit slider packet (comm.c skips if nothing changed) */
        COMM_SendSliders(SLIDERS_GetAll(), NUM_SLIDERS);
    }
}
