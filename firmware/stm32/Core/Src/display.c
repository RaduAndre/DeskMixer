/**
 * @file    display.c
 * @brief   SSD1306 128×64 OLED driver (I2C1, PB6=SCL, PB7=SDA, 100 kHz).
 *
 * A full 128×64 frame-buffer is maintained in RAM (~1 kB).
 * DISPLAY_Flush() writes the entire buffer to the SSD1306 in one I2C
 * transaction using the "continuation" data byte (0x40 | 0x80... no –
 * the STM32 HAL I2C memory-write will do it as repeated bytes after address).
 *
 * Built-in font: 6×8 pixels per character (5×7 glyph + 1 column padding).
 */

#include "display.h"
#include "main.h"
#include <string.h>

/* ── External handle ─────────────────────────────────────────────────────── */
extern I2C_HandleTypeDef hi2c1;

/* ── SSD1306 command bytes ───────────────────────────────────────────────── */
#define SSD_CMD          0x00   /* Co=0, D/C=0 → command stream      */
#define SSD_DATA         0x40   /* Co=0, D/C=1 → data stream         */

/* ── Frame buffer (1 bit per pixel, page-organised) ─────────────────────── */
static uint8_t s_fb[DISPLAY_PAGES][DISPLAY_WIDTH];

/* ── 6×8 ASCII font (printable chars 0x20-0x7E) ─────────────────────────── */
/* Each character is 5 columns of 8-bit column data (LSB = top pixel).
 * A 6th column of 0x00 is added automatically as spacing.              */
static const uint8_t FONT_6x8[][5] = {
    {0x00,0x00,0x00,0x00,0x00}, /* ' ' 0x20 */
    {0x00,0x00,0x5F,0x00,0x00}, /* '!' */
    {0x00,0x07,0x00,0x07,0x00}, /* '"' */
    {0x14,0x7F,0x14,0x7F,0x14}, /* '#' */
    {0x24,0x2A,0x7F,0x2A,0x12}, /* '$' */
    {0x23,0x13,0x08,0x64,0x62}, /* '%' */
    {0x36,0x49,0x55,0x22,0x50}, /* '&' */
    {0x00,0x05,0x03,0x00,0x00}, /* '\'' */
    {0x00,0x1C,0x22,0x41,0x00}, /* '(' */
    {0x00,0x41,0x22,0x1C,0x00}, /* ')' */
    {0x08,0x2A,0x1C,0x2A,0x08}, /* '*' */
    {0x08,0x08,0x3E,0x08,0x08}, /* '+' */
    {0x00,0x50,0x30,0x00,0x00}, /* ',' */
    {0x08,0x08,0x08,0x08,0x08}, /* '-' */
    {0x00,0x60,0x60,0x00,0x00}, /* '.' */
    {0x20,0x10,0x08,0x04,0x02}, /* '/' */
    {0x3E,0x51,0x49,0x45,0x3E}, /* '0' */
    {0x00,0x42,0x7F,0x40,0x00}, /* '1' */
    {0x42,0x61,0x51,0x49,0x46}, /* '2' */
    {0x21,0x41,0x45,0x4B,0x31}, /* '3' */
    {0x18,0x14,0x12,0x7F,0x10}, /* '4' */
    {0x27,0x45,0x45,0x45,0x39}, /* '5' */
    {0x3C,0x4A,0x49,0x49,0x30}, /* '6' */
    {0x01,0x71,0x09,0x05,0x03}, /* '7' */
    {0x36,0x49,0x49,0x49,0x36}, /* '8' */
    {0x06,0x49,0x49,0x29,0x1E}, /* '9' */
    {0x00,0x36,0x36,0x00,0x00}, /* ':' */
    {0x00,0x56,0x36,0x00,0x00}, /* ';' */
    {0x00,0x08,0x14,0x22,0x41}, /* '<' */
    {0x14,0x14,0x14,0x14,0x14}, /* '=' */
    {0x41,0x22,0x14,0x08,0x00}, /* '>' */
    {0x02,0x01,0x51,0x09,0x06}, /* '?' */
    {0x32,0x49,0x79,0x41,0x3E}, /* '@' */
    {0x7E,0x11,0x11,0x11,0x7E}, /* 'A' */
    {0x7F,0x49,0x49,0x49,0x36}, /* 'B' */
    {0x3E,0x41,0x41,0x41,0x22}, /* 'C' */
    {0x7F,0x41,0x41,0x22,0x1C}, /* 'D' */
    {0x7F,0x49,0x49,0x49,0x41}, /* 'E' */
    {0x7F,0x09,0x09,0x09,0x01}, /* 'F' */
    {0x3E,0x41,0x41,0x49,0x7A}, /* 'G' */
    {0x7F,0x08,0x08,0x08,0x7F}, /* 'H' */
    {0x00,0x41,0x7F,0x41,0x00}, /* 'I' */
    {0x20,0x40,0x41,0x3F,0x01}, /* 'J' */
    {0x7F,0x08,0x14,0x22,0x41}, /* 'K' */
    {0x7F,0x40,0x40,0x40,0x40}, /* 'L' */
    {0x7F,0x02,0x04,0x02,0x7F}, /* 'M' */
    {0x7F,0x04,0x08,0x10,0x7F}, /* 'N' */
    {0x3E,0x41,0x41,0x41,0x3E}, /* 'O' */
    {0x7F,0x09,0x09,0x09,0x06}, /* 'P' */
    {0x3E,0x41,0x51,0x21,0x5E}, /* 'Q' */
    {0x7F,0x09,0x19,0x29,0x46}, /* 'R' */
    {0x46,0x49,0x49,0x49,0x31}, /* 'S' */
    {0x01,0x01,0x7F,0x01,0x01}, /* 'T' */
    {0x3F,0x40,0x40,0x40,0x3F}, /* 'U' */
    {0x1F,0x20,0x40,0x20,0x1F}, /* 'V' */
    {0x3F,0x40,0x38,0x40,0x3F}, /* 'W' */
    {0x63,0x14,0x08,0x14,0x63}, /* 'X' */
    {0x07,0x08,0x70,0x08,0x07}, /* 'Y' */
    {0x61,0x51,0x49,0x45,0x43}, /* 'Z' */
    {0x00,0x7F,0x41,0x41,0x00}, /* '[' */
    {0x02,0x04,0x08,0x10,0x20}, /* '\\' */
    {0x00,0x41,0x41,0x7F,0x00}, /* ']' */
    {0x04,0x02,0x01,0x02,0x04}, /* '^' */
    {0x40,0x40,0x40,0x40,0x40}, /* '_' */
    {0x00,0x01,0x02,0x04,0x00}, /* '`' */
    {0x20,0x54,0x54,0x54,0x78}, /* 'a' */
    {0x7F,0x48,0x44,0x44,0x38}, /* 'b' */
    {0x38,0x44,0x44,0x44,0x20}, /* 'c' */
    {0x38,0x44,0x44,0x48,0x7F}, /* 'd' */
    {0x38,0x54,0x54,0x54,0x18}, /* 'e' */
    {0x08,0x7E,0x09,0x01,0x02}, /* 'f' */
    {0x08,0x14,0x54,0x54,0x3C}, /* 'g' */
    {0x7F,0x08,0x04,0x04,0x78}, /* 'h' */
    {0x00,0x44,0x7D,0x40,0x00}, /* 'i' */
    {0x20,0x40,0x44,0x3D,0x00}, /* 'j' */
    {0x7F,0x10,0x28,0x44,0x00}, /* 'k' */
    {0x00,0x41,0x7F,0x40,0x00}, /* 'l' */
    {0x7C,0x04,0x18,0x04,0x78}, /* 'm' */
    {0x7C,0x08,0x04,0x04,0x78}, /* 'n' */
    {0x38,0x44,0x44,0x44,0x38}, /* 'o' */
    {0x7C,0x14,0x14,0x14,0x08}, /* 'p' */
    {0x08,0x14,0x14,0x18,0x7C}, /* 'q' */
    {0x7C,0x08,0x04,0x04,0x08}, /* 'r' */
    {0x48,0x54,0x54,0x54,0x20}, /* 's' */
    {0x04,0x3F,0x44,0x40,0x20}, /* 't' */
    {0x3C,0x40,0x40,0x20,0x7C}, /* 'u' */
    {0x1C,0x20,0x40,0x20,0x1C}, /* 'v' */
    {0x3C,0x40,0x30,0x40,0x3C}, /* 'w' */
    {0x44,0x28,0x10,0x28,0x44}, /* 'x' */
    {0x0C,0x50,0x50,0x50,0x3C}, /* 'y' */
    {0x44,0x64,0x54,0x4C,0x44}, /* 'z' */
    {0x00,0x08,0x36,0x41,0x00}, /* '{' */
    {0x00,0x00,0x77,0x00,0x00}, /* '|' */
    {0x00,0x41,0x36,0x08,0x00}, /* '}' */
    {0x08,0x08,0x2A,0x1C,0x08}, /* '~' */
};

/* ── SSD1306 init sequence ───────────────────────────────────────────────── */
static const uint8_t s_initSeq[] = {
    0xAE,       /* Display OFF                    */
    0xD5, 0x80, /* Clock divide / oscillator freq */
    0xA8, 0x3F, /* MUX ratio 64                   */
    0xD3, 0x00, /* Display offset 0               */
    0x40,       /* Start line 0                   */
    0x8D, 0x14, /* Charge pump ON                 */
    0x20, 0x00, /* Memory addressing: horizontal  */
    0xA1,       /* Segment remap (col 127→SEG0)   */
    0xC8,       /* COM scan: remapped (top→bottom)*/
    0xDA, 0x12, /* COM pins config                */
    0x81, 0xCF, /* Contrast                       */
    0xD9, 0xF1, /* Pre-charge period              */
    0xDB, 0x40, /* VCOM deselect level            */
    0xA4,       /* Entire display ON (follow RAM) */
    0xA6,       /* Normal display (not inverted)  */
    0xAF,       /* Display ON                     */
};

/* ── Internal helpers ────────────────────────────────────────────────────── */

static int write_cmd(uint8_t cmd)
{
    uint8_t buf[2] = { SSD_CMD, cmd };
    return (int)HAL_I2C_Master_Transmit(&hi2c1,
                                        DISPLAY_I2C_ADDR,
                                        buf, 2,
                                        50);
}

static int write_cmd2(uint8_t cmd, uint8_t arg)
{
    uint8_t buf[3] = { SSD_CMD, cmd, arg };
    return (int)HAL_I2C_Master_Transmit(&hi2c1,
                                        DISPLAY_I2C_ADDR,
                                        buf, 3,
                                        50);
}

/* ── Public functions ────────────────────────────────────────────────────── */

int DISPLAY_Init(void)
{
    HAL_Delay(10); /* Wait for display power-on */

    /* Send init sequence byte by byte */
    const uint8_t *p   = s_initSeq;
    const uint8_t *end = s_initSeq + sizeof(s_initSeq);
    while (p < end) {
        uint8_t buf[2] = { SSD_CMD, *p++ };
        if (HAL_I2C_Master_Transmit(&hi2c1, DISPLAY_I2C_ADDR, buf, 2, 50) != HAL_OK)
            return -1;
    }

    DISPLAY_Clear();
    DISPLAY_Flush();
    return 0;
}

void DISPLAY_Clear(void)
{
    memset(s_fb, 0, sizeof(s_fb));
}

void DISPLAY_Flush(void)
{
    /* Set column and page address windows to full display */
    write_cmd2(0x21, 0x00); write_cmd(0x7F); /* column 0-127  */
    write_cmd2(0x22, 0x00); write_cmd(0x07); /* page   0-7    */

    /*
     * Send the frame buffer page by page.
     * Each I2C transaction: [SSD_DATA, 128 bytes of column data]
     */
    for (uint8_t page = 0; page < DISPLAY_PAGES; page++) {
        /* Build a 129-byte packet: 1 control byte + 128 data bytes */
        uint8_t pkt[129];
        pkt[0] = SSD_DATA;
        memcpy(&pkt[1], s_fb[page], DISPLAY_WIDTH);
        HAL_I2C_Master_Transmit(&hi2c1,
                                DISPLAY_I2C_ADDR,
                                pkt, sizeof(pkt),
                                100);
    }
}

void DISPLAY_DrawChar(uint8_t col, uint8_t page, char c)
{
    if (c < 0x20 || c > 0x7E) c = '?';
    if (page >= DISPLAY_PAGES) return;

    const uint8_t *glyph = FONT_6x8[(uint8_t)(c - 0x20)];
    for (uint8_t x = 0; x < 5; x++) {
        if (col + x < DISPLAY_WIDTH)
            s_fb[page][col + x] = glyph[x];
    }
    /* 6th column spacing */
    if (col + 5 < DISPLAY_WIDTH)
        s_fb[page][col + 5] = 0x00;
}

void DISPLAY_DrawString(uint8_t col, uint8_t page, const char *str)
{
    while (*str && col < DISPLAY_WIDTH) {
        DISPLAY_DrawChar(col, page, *str++);
        col += 6;
    }
}

void DISPLAY_ShowSplash(void)
{
    DISPLAY_Clear();

    /* ── Line 1: "DeskMixer" centred (9 chars × 6 px = 54 px wide) ── */
    const char *title    = "DeskMixer";
    uint8_t title_len    = 9u;
    uint8_t title_px     = title_len * 6u;                /* 54 */
    uint8_t title_col    = (DISPLAY_WIDTH - title_px) / 2u; /* 37 */
    DISPLAY_DrawString(title_col, 3, title);              /* centre vertically */

    /* ── Line 2: divider dashes ── */
    const char *sub = "-  Volume Mixer  -";
    uint8_t sub_len  = 15u;
    uint8_t sub_px   = sub_len * 6u;                      /* 90 */
    uint8_t sub_col  = (DISPLAY_WIDTH - sub_px) / 2u;     /* 19 */
    DISPLAY_DrawString(sub_col, 5, sub);

    DISPLAY_Flush();
}

/* ── State Management ────────────────────────────────────────────────── */

typedef enum {
    DISP_STATE_DISCONNECTED = 0,
    DISP_STATE_CONNECTED_MSG = 1,
    DISP_STATE_IDLE = 2,
    DISP_STATE_OVERRIDE = 3
} DisplayState_t;

static DisplayState_t s_disp_state = DISP_STATE_DISCONNECTED;
static uint32_t s_connected_msg_time = 0;
static uint32_t s_override_time = 0;
static char s_override_text[32] = {0};
static uint8_t s_force_redraw = 1;

void DISPLAY_SetConnectionState(uint8_t connected) {
    if (!connected) {
        if (s_disp_state != DISP_STATE_DISCONNECTED) {
            s_disp_state = DISP_STATE_DISCONNECTED;
            s_force_redraw = 1;
        }
    } else {
        if (s_disp_state == DISP_STATE_DISCONNECTED) {
            s_disp_state = DISP_STATE_CONNECTED_MSG;
            s_connected_msg_time = HAL_GetTick();
            s_force_redraw = 1;
        }
    }
}

void DISPLAY_ShowOverride(const char* text) {
    strncpy(s_override_text, text, sizeof(s_override_text)-1);
    s_override_time = HAL_GetTick();
    if (s_disp_state != DISP_STATE_OVERRIDE) {
        s_disp_state = DISP_STATE_OVERRIDE;
    }
    s_force_redraw = 1;
}

void DISPLAY_Process(void) {
    uint32_t now = HAL_GetTick();

    if (s_disp_state == DISP_STATE_CONNECTED_MSG) {
        if (now - s_connected_msg_time >= 5000) {
            s_disp_state = DISP_STATE_IDLE;
            s_force_redraw = 1;
        }
    } else if (s_disp_state == DISP_STATE_OVERRIDE) {
        if (now - s_override_time >= 2000) {
            s_disp_state = DISP_STATE_IDLE;
            s_force_redraw = 1;
        }
    }

    if (s_force_redraw) {
        s_force_redraw = 0;
        if (s_disp_state == DISP_STATE_DISCONNECTED) {
            DISPLAY_Clear();
            DISPLAY_DrawString(28, 3, "Disconnected");
            DISPLAY_Flush();
        } else if (s_disp_state == DISP_STATE_CONNECTED_MSG) {
            DISPLAY_Clear();
            DISPLAY_DrawString(37, 3, "Connected");
            DISPLAY_Flush();
        } else if (s_disp_state == DISP_STATE_IDLE) {
            DISPLAY_ShowSplash();
        } else if (s_disp_state == DISP_STATE_OVERRIDE) {
            DISPLAY_Clear();
            int len = strlen(s_override_text);
            int x = 64 - (len * 3);
            if (x < 0) x = 0;
            DISPLAY_DrawString(x, 3, s_override_text);
            DISPLAY_Flush();
        }
    }
}
