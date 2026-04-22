/**
 * @file    buttons.c
 * @brief   Debounced button reader for 6 GPIOB push-buttons.
 *
 * Pin to GPIOB bit mapping (GPIO_PIN_x values):
 *   Button 1 → PB1  (GPIO_PIN_1)   physical pin 19
 *   Button 2 → PB2  (GPIO_PIN_2)   physical pin 20
 *   Button 3 → PB3  (GPIO_PIN_3)   physical pin 39
 *   Button 4 → PB4  (GPIO_PIN_4)   physical pin 40
 *   Button 5 → PB10 (GPIO_PIN_10)  physical pin 21
 *   Button 6 → PB11 (GPIO_PIN_11)  physical pin 22
 *
 * All configured as INPUT with internal PULL-UP (done by MX_GPIO_Init).
 * Logic: pin LOW when pressed → we invert so state = 1 when pressed.
 */

#include "buttons.h"
#include "main.h"

/* ── GPIO pin table ───────────────────────────────────────────────────── */
static const uint16_t s_pins[NUM_BUTTONS] = {
    GPIO_PIN_1,   /* Button 1 – PB1  */
    GPIO_PIN_2,   /* Button 2 – PB2  */
    GPIO_PIN_3,   /* Button 3 – PB3  */
    GPIO_PIN_4,   /* Button 4 – PB4  */
    GPIO_PIN_10,  /* Button 5 – PB10 */
    GPIO_PIN_11,  /* Button 6 – PB11 */
};

/* ── State / debounce variables ──────────────────────────────────────── */
static uint8_t  s_state[NUM_BUTTONS]          = {0};  /* stable state      */
static uint8_t  s_raw[NUM_BUTTONS]            = {0};  /* raw (un-debounced)*/
static uint32_t s_lastChange[NUM_BUTTONS]     = {0};  /* ms timestamp      */
static uint8_t  s_pressEvent[NUM_BUTTONS]     = {0};  /* latch for press   */

/* ── Public functions ────────────────────────────────────────────────── */

void BUTTONS_Init(void)
{
    /* GPIO is configured by MX_GPIO_Init – nothing else needed here. */
    uint32_t now = HAL_GetTick();
    for (uint8_t i = 0; i < NUM_BUTTONS; i++) {
        /* Read initial state so we don't fire spurious events on boot */
        s_raw[i]        = (HAL_GPIO_ReadPin(GPIOB, s_pins[i]) == GPIO_PIN_RESET) ? 1u : 0u;
        s_state[i]      = s_raw[i];
        s_lastChange[i] = now;
        s_pressEvent[i] = 0;
    }
}

void BUTTONS_Read(void)
{
    uint32_t now = HAL_GetTick();

    for (uint8_t i = 0; i < NUM_BUTTONS; i++) {
        /* Read raw: LOW = pressed (pull-up active), invert so 1 = pressed */
        uint8_t raw = (HAL_GPIO_ReadPin(GPIOB, s_pins[i]) == GPIO_PIN_RESET) ? 1u : 0u;

        if (raw != s_raw[i]) {
            /* Raw signal changed – reset debounce timer */
            s_raw[i]        = raw;
            s_lastChange[i] = now;
        }

        /* Accept state change only after DEBOUNCE_MS of stability */
        if ((now - s_lastChange[i]) >= DEBOUNCE_MS) {
            uint8_t prev = s_state[i];
            s_state[i]   = raw;

            /* Detect rising edge (0 → 1 = press event) */
            if (prev == 0 && s_state[i] == 1) {
                s_pressEvent[i] = 1;
            }
        }
    }
}

uint8_t BUTTONS_GetState(uint8_t index)
{
    if (index >= NUM_BUTTONS) return 0;
    return s_state[index];
}

uint8_t BUTTONS_GetPressEvent(uint8_t index)
{
    if (index >= NUM_BUTTONS) return 0;
    uint8_t ev = s_pressEvent[index];
    s_pressEvent[index] = 0;   /* Clear latch on read */
    return ev;
}
