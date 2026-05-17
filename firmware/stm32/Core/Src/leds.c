/**
 * @file    leds.c
 * @brief   LED subsystem orchestrator.
 *
 * This file is intentionally thin.  All implementation is split into:
 *   leds_core.c   – SPI/DMA driver, LED buffer, LED_Init, LED_Show, LED_Clear
 *   leds_config.c – configuration state, LED_Set* public setters
 *   leds_anim.c   – animation engines (Surf/Solid/Pulse/VUBar/Starlight)
 *                   and rebuild_leds()
 *
 * LED_Process() is the only function defined here.  It is called every
 * main-loop iteration (non-blocking) and drives the full animation pipeline.
 */

#include "leds.h"
#include "leds_anim.h"
#include "main.h"

/* LED_Show() is defined in leds_core.c */
extern void LED_Show(void);

void LED_Process(void)
{
    static uint32_t last_tick = 0;
    uint32_t now = HAL_GetTick();

    /* Throttle to ~60 FPS to ensure consistent interpolation speed
       and save CPU cycles for USB CDC and ADC tasks. */
    if ((now - last_tick) < 16u) {
        return;
    }
    last_tick = now;

    anim_process();   /* advance active animation state machine              */
    rebuild_leds();   /* write animation output to s_leds[] with fill masks  */
    LED_Show();       /* push s_leds[] → SPI DMA → SK6812MINI strip          */
}
