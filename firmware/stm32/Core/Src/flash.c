/**
 * @file    flash.c
 * @brief   SPI Flash driver stub (JEDEC 25-series compatible).
 *
 * SPI1:  PA5=SCK  PA6=MISO  PA7=MOSI  (Full-duplex, ~12 Mbps)
 * CS  :  PB0  (FLASH_CS_Pin / FLASH_CS_GPIO_Port  from main.h)
 *
 * All functions use HAL blocking SPI calls.  Timeout = 100 ms unless
 * stated otherwise.  The SPI1 handle must be initialised by HAL before
 * calling FLASH_Init().
 */

#include "flash.h"
#include "main.h"   /* FLASH_CS_Pin, FLASH_CS_GPIO_Port, Error_Handler */
#include <string.h>

/* ── External handle ─────────────────────────────────────────────────────── */
extern SPI_HandleTypeDef hspi1;

/* ── CS pin helpers ──────────────────────────────────────────────────────── */
#define CS_LOW()  HAL_GPIO_WritePin(FLASH_CS_GPIO_Port, FLASH_CS_Pin, GPIO_PIN_RESET)
#define CS_HIGH() HAL_GPIO_WritePin(FLASH_CS_GPIO_Port, FLASH_CS_Pin, GPIO_PIN_SET)

/* ── Internal helpers ────────────────────────────────────────────────────── */

/**
 * @brief Send a single command byte (no data phase).
 */
static void flash_cmd(uint8_t cmd)
{
    CS_LOW();
    HAL_SPI_Transmit(&hspi1, &cmd, 1, 100);
    CS_HIGH();
}

/**
 * @brief Send a 3-byte address (MSB first) over SPI (CS must already be low).
 */
static void send_addr(uint32_t addr)
{
    uint8_t buf[3] = {
        (uint8_t)((addr >> 16) & 0xFF),
        (uint8_t)((addr >>  8) & 0xFF),
        (uint8_t)( addr        & 0xFF),
    };
    HAL_SPI_Transmit(&hspi1, buf, 3, 100);
}

/* ── Public functions ────────────────────────────────────────────────────── */

int FLASH_Init(void)
{
    CS_HIGH(); /* Ensure CS is de-asserted */
    HAL_Delay(1);

    /* Quick sanity-check: read JEDEC ID – all 0xFF means no device */
    uint8_t id[3] = {0};
    FLASH_ReadID(id);

    if (id[0] == 0xFF && id[1] == 0xFF && id[2] == 0xFF)
        return -1; /* No flash device detected */

    return 0;
}

void FLASH_ReadID(uint8_t id[3])
{
    uint8_t cmd = FLASH_CMD_RDID;
    CS_LOW();
    HAL_SPI_Transmit(&hspi1, &cmd, 1, 100);
    HAL_SPI_Receive(&hspi1, id, 3, 100);
    CS_HIGH();
}

uint8_t FLASH_IsBusy(void)
{
    uint8_t cmd = FLASH_CMD_RDSR;
    uint8_t sr  = 0;
    CS_LOW();
    HAL_SPI_Transmit(&hspi1, &cmd, 1, 100);
    HAL_SPI_Receive(&hspi1, &sr, 1, 100);
    CS_HIGH();
    return (sr & FLASH_SR_BUSY) ? 1u : 0u;
}

void FLASH_WaitReady(void)
{
    while (FLASH_IsBusy()) {
        HAL_Delay(1);
    }
}

void FLASH_Read(uint32_t address, uint8_t *buf, uint16_t length)
{
    uint8_t cmd = FLASH_CMD_READ;
    CS_LOW();
    HAL_SPI_Transmit(&hspi1, &cmd, 1, 100);
    send_addr(address);
    HAL_SPI_Receive(&hspi1, buf, length, 500);
    CS_HIGH();
}

void FLASH_PageProgram(uint32_t address, const uint8_t *buf, uint16_t length)
{
    /* Write Enable must precede every program/erase operation */
    flash_cmd(FLASH_CMD_WREN);

    CS_LOW();
    uint8_t cmd = FLASH_CMD_PP;
    HAL_SPI_Transmit(&hspi1, &cmd, 1, 100);
    send_addr(address);
    /* Cast away const – HAL Transmit takes uint8_t* but does not modify */
    HAL_SPI_Transmit(&hspi1, (uint8_t *)buf, length, 500);
    CS_HIGH();

    FLASH_WaitReady();
}

void FLASH_EraseSector(uint32_t address)
{
    flash_cmd(FLASH_CMD_WREN);  /* Write Enable */

    CS_LOW();
    uint8_t cmd = FLASH_CMD_SE;
    HAL_SPI_Transmit(&hspi1, &cmd, 1, 100);
    send_addr(address);
    CS_HIGH();

    FLASH_WaitReady();          /* Sector erase ~400 ms max */
}
