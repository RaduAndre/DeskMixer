/**
 * @file    flash.h
 * @brief   SPI Flash memory driver stub for DeskMixer STM32 port.
 *
 * Interface: SPI1  (PA5 = SCK, PA6 = MISO, PA7 = MOSI)
 * CS pin   : PB0  (FLASH_CS – defined in main.h)
 *
 * Implements minimal JEDEC-compatible operations using the STM32 HAL
 * blocking SPI API.  Designed for any 25-series flash chip.
 *
 * NOTE: This is a placeholder/stub implementation.  Only the functions
 * required to validate SPI communication are filled in.  Full read/write
 * support, wear-levelling etc. will be added in future iterations.
 */

#ifndef FLASH_H
#define FLASH_H

#include <stdint.h>

/* ---- JEDEC common commands --------------------------------------------- */
#define FLASH_CMD_RDID    0x9F   /**< Read JEDEC ID (3 bytes)                */
#define FLASH_CMD_RDSR    0x05   /**< Read Status Register                   */
#define FLASH_CMD_WREN    0x06   /**< Write Enable                           */
#define FLASH_CMD_READ    0x03   /**< Read Data (max speed depends on chip)  */
#define FLASH_CMD_PP      0x02   /**< Page Program (256 bytes)               */
#define FLASH_CMD_SE      0x20   /**< Sector Erase (4 kB)                    */
#define FLASH_CMD_CE      0x60   /**< Chip Erase                             */

#define FLASH_SR_BUSY     0x01   /**< Status Register WIP (busy) bit         */

/* ---- Public API -------------------------------------------------------- */

/**
 * @brief  Initialise the flash driver and assert CS high.
 *         Must be called after MX_SPI1_Init().
 * @retval 0 on success, non-zero if JEDEC ID read fails.
 */
int FLASH_Init(void);

/**
 * @brief  Read the 3-byte JEDEC ID (Manufacturer, Memory Type, Capacity).
 * @param  id  Output buffer – must be at least 3 bytes.
 */
void FLASH_ReadID(uint8_t id[3]);

/**
 * @brief  Poll the BUSY bit in the Status Register.
 * @retval 1 if busy, 0 if ready.
 */
uint8_t FLASH_IsBusy(void);

/**
 * @brief  Wait until the flash is not busy (blocking, polls with HAL_Delay).
 */
void FLASH_WaitReady(void);

/**
 * @brief  Read @p length bytes from flash starting at @p address.
 * @param  address  24-bit byte address.
 * @param  buf      Output buffer.
 * @param  length   Number of bytes to read.
 */
void FLASH_Read(uint32_t address, uint8_t *buf, uint16_t length);

/**
 * @brief  Write up to 256 bytes to a flash page.
 *         The target sector must have been erased first.
 * @param  address  24-bit byte address (must be page-aligned).
 * @param  buf      Data to write.
 * @param  length   Number of bytes (1-256).
 */
void FLASH_PageProgram(uint32_t address, const uint8_t *buf, uint16_t length);

/**
 * @brief  Erase a 4 kB sector containing @p address.
 */
void FLASH_EraseSector(uint32_t address);

#endif /* FLASH_H */
