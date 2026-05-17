/**
 * @file    leds_core.c
 * @brief   SK6812MINI SPI/DMA low-level driver.
 *          Owns the LED shadow buffer, SPI encode table, LED_Init, LED_Show,
 *          LED_Clear, LED_Fill, LED_SetColor, LED_RedToBlue.
 *
 * Protocol encoding (SPI at 3.0 MHz, APB1=24 MHz, prescaler /8):
 *   SK6812 '0' bit → 0b1000 (high ~333 ns, low ~1000 ns)
 *   SK6812 '1' bit → 0b1110 (high ~1000 ns, low ~333 ns)
 *   Each GRB byte → 8 SK6812 bits → 32 SPI bits → 4 SPI bytes.
 *   46 LEDs × 3 bytes × 4 SPI bytes = 552 payload bytes + 10 reset bytes.
 */

#include "leds.h"
#include "leds_anim.h"
#include "main.h"
#include <string.h>

/* ── External SPI/DMA handles (from MX-generated code) ─────────────────── */

extern SPI_HandleTypeDef  hspi2;
extern DMA_HandleTypeDef  hdma_spi2_tx;

/* ── SPI buffer constants ───────────────────────────────────────────────── */

#define SPI_BYTES_PER_LED_BYTE   4u
#define SPI_LED_PAYLOAD          (LED_TOTAL * 3u * SPI_BYTES_PER_LED_BYTE)  /* 552 */
#define SPI_RESET_BYTES          10u
#define SPI_BUF_SIZE             (SPI_LED_PAYLOAD + SPI_RESET_BYTES)        /* 562 */

/* ── LED shadow buffer and SPI transmit buffer ──────────────────────────── */

Led_t   s_leds[LED_TOTAL];                  /* exported via leds_anim.h     */
static uint8_t s_spiBuf[SPI_BUF_SIZE];

/* ── Encode lookup: raw byte → 4 SPI bytes ──────────────────────────────── */

static uint8_t s_encode[256][4];

static void build_lookup(void)
{
    for (int v = 0; v < 256; v++) {
        for (int b = 0; b < 4; b++) {
            uint8_t hi = (uint8_t)((v >> (7 - b * 2))     & 1u);
            uint8_t lo = (uint8_t)((v >> (7 - b * 2 - 1)) & 1u);
            s_encode[v][b] = (uint8_t)((hi ? 0xE0u : 0x80u) |
                                       (lo ? 0x0Eu : 0x08u));
        }
    }
}

/* ── Public functions ───────────────────────────────────────────────────── */

void LED_Init(void)
{
    build_lookup();
    memset(s_leds,   0, sizeof(s_leds));
    memset(s_spiBuf, 0, sizeof(s_spiBuf));

    /* Zero all config arrays (owned by leds_config.c) */
    memset(s_sliderScaled,    0, sizeof(s_sliderScaled));
    memset(s_slider_custom_r, 0, LED_SLIDER_COUNT);
    memset(s_slider_custom_g, 0, LED_SLIDER_COUNT);
    memset(s_slider_custom_b, 0, LED_SLIDER_COUNT);
    memset(s_button_custom_r, 0, 6u);
    memset(s_button_custom_g, 0, 6u);
    memset(s_button_custom_b, 0, 6u);
    s_buttonMask = 0u;

    /* Set default speed (speed=5) so timing globals are initialised */
    LED_SetAnimSpeedLevel(5u);

    /* Initialise surf row interpolation buffers */
    anim_surf_init();

    /* First frame: run animation once then push */
    anim_process();
    rebuild_leds();
    LED_Show();
    HAL_Delay(1);
}

void LED_SetColor(uint8_t index, uint8_t r, uint8_t g, uint8_t b)
{
    if (index >= LED_TOTAL) return;
    s_leds[index].r = r;
    s_leds[index].g = g;
    s_leds[index].b = b;
}

void LED_Fill(uint8_t r, uint8_t g, uint8_t b)
{
    for (uint8_t i = 0; i < LED_TOTAL; i++) {
        s_leds[i].r = r;
        s_leds[i].g = g;
        s_leds[i].b = b;
    }
}

void LED_RedToBlue(void)
{
    /* Legacy no-op: animation is now driven by LED_Process. */
    LED_Fill(0, 0, 0);
    LED_Show();
}

void LED_Show(void)
{
    /* Return immediately if DMA transfer is in progress */
    if (HAL_SPI_GetState(&hspi2) != HAL_SPI_STATE_READY) {
        return;
    }

    /* Encode LED buffer into SPI buffer (SK6812 colour order: G, R, B) */
    uint8_t *p = s_spiBuf;
    for (uint8_t i = 0; i < LED_TOTAL; i++) {
        memcpy(p, s_encode[s_leds[i].g], 4u); p += 4u;
        memcpy(p, s_encode[s_leds[i].r], 4u); p += 4u;
        memcpy(p, s_encode[s_leds[i].b], 4u); p += 4u;
    }
    /* Reset bytes remain 0x00 from initialisation */
    HAL_SPI_Transmit_DMA(&hspi2, s_spiBuf, SPI_BUF_SIZE);
}

void LED_Clear(void)
{
    LED_Fill(0, 0, 0);
    LED_Show();
}
