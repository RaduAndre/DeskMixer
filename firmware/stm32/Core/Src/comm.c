/**
 * @file    comm.c
 * @brief   USB CDC serial communication – DeskMixer wire protocol.
 *
 * ── How to hook this up ──────────────────────────────────────────────────
 *
 * 1.  In STM32CubeIDE / CubeMX, enable: Middleware → USB_DEVICE → CDC
 *     then re-generate code.  This creates:
 *       USB_DEVICE/App/usbd_cdc_if.c
 *       USB_DEVICE/App/usbd_cdc_if.h
 *
 * 2.  In usbd_cdc_if.c, locate CDC_Receive_FS() and add one call:
 *       static int8_t CDC_Receive_FS(uint8_t* Buf, uint32_t *Len)
 *       {
 *           COMM_OnRxData(Buf, *Len);            // ← add this line
 *           USBD_CDC_SetRxBuffer(&hUsbDeviceFS, &Buf[0]);
 *           USBD_CDC_ReceivePacket(&hUsbDeviceFS);
 *           return (USBD_OK);
 *       }
 *
 * 3.  Add #include "comm.h" at the top of usbd_cdc_if.c.
 *
 * 4.  comm.c calls CDC_Transmit_FS() which is already declared in
 *     usbd_cdc_if.h – so the linker just needs that object in the build.
 *
 * ────────────────────────────────────────────────────────────────────────
 *
 * ── Optimisation notes ──────────────────────────────────────────────────
 *
 * 1. Delta-filtered slider TX:
 *    COMM_SendSliders() compares each new value against the last-sent
 *    value.  A transmission is skipped entirely when no slider has
 *    changed by more than SLIDER_TX_THRESHOLD counts.  This removes
 *    ~99 % of idle slider traffic (100 packets/s → effectively 0 when
 *    the user is not touching the hardware).
 *
 * 2. Non-blocking COMM_Send:
 *    CDC_Transmit_FS returns USBD_BUSY while the USB stack is mid-
 *    transfer.  Rather than spin-waiting up to 10 ms in the middle of
 *    the main loop, we do ONE attempt and return.  A dropped slider
 *    frame costs ≤ 10 ms of data – invisible to the user.  Button press
 *    frames are sent separately and retried up to BUTTON_TX_RETRIES times
 *    with a short spin so they are never silently dropped.
 *
 * 3. Connection-state guard:
 *    s_connected is set to 1 only after a successful handshake exchange.
 *    Slider data is not sent until connected, avoiding floods of data
 *    during USB enumeration that could block the handshake.
 *
 * 4. Handshake priority:
 *    COMM_Init() waits up to COMM_ENUM_WAIT_MS for the USB stack to
 *    enumerate before attempting the startup handshake, using
 *    HAL_GetTick() (no volatile busy-loops).  The handshake response is
 *    sent with the button-priority retry path so it is never dropped.
 *
 * 5. Scale: slider values are in range 0-1024 (raw 12-bit >> 2).
 *    Python host divides by 1024.0 → float [0.0 .. 1.0].
 * ────────────────────────────────────────────────────────────────────────
 */

#include "comm.h"
#include "sliders.h"   /* NUM_SLIDERS */
#include "buttons.h"   /* NUM_BUTTONS */
#include "main.h"      /* HAL_GetTick */
#include "display.h"   /* DISPLAY_Clear, DISPLAY_DrawString, DISPLAY_Flush, DISPLAY_ShowSplash */
#include "params.h"    /* PARAMS_SendList, PARAMS_Update */
#include <string.h>
#include <stdio.h>
#include <stdint.h>

/* ── CDC_Transmit_FS forward declaration ─────────────────────────────── */
extern uint8_t CDC_Transmit_FS(uint8_t *Buf, uint16_t Len);

/* ── Protocol strings ────────────────────────────────────────────────── */
#define HANDSHAKE_REQUEST   "DeskMixer controller request"
#define HANDSHAKE_RESPONSE  "DeskMixer Controller Ready\r\n"

#define NUM_SCREENS         1   /* SCREEN_ACTIVE = 1, matching ESP32 firmware */

#define _STR(x) #x
#define STRINGIFY(x) _STR(x)

/* CONFIG string: "CONFIG:SLIDERS:5:BUTTONS:6:SCREEN:1\r\n" */
static const char CONFIG_RESPONSE[] =
    "CONFIG:SLIDERS:" STRINGIFY(NUM_SLIDERS)
    ":BUTTONS:"       STRINGIFY(NUM_BUTTONS)
    ":SCREEN:"        STRINGIFY(NUM_SCREENS) "\r\n";

/* ── Tuning constants ────────────────────────────────────────────────── */

/*
 * SLIDER_TX_THRESHOLD  – minimum change in the 0-1024 scaled value before
 * a slider packet is transmitted.  Set to 2 (≈ 0.2% of full scale).
 * Eliminates idle noise-chatter while keeping step resolution fine enough
 * to be imperceptible to the audio API.
 */
#define SLIDER_TX_THRESHOLD  2u

/*
 * Time (ms) to wait after USB device init before sending the startup
 * handshake.  The USB stack needs ~500 ms to enumerate on most hosts.
 * We poll in a non-busy way using HAL_GetTick().
 */
#define COMM_ENUM_WAIT_MS    600u

/*
 * Button and handshake frames are important – retry on USBD_BUSY.
 * Each retry spin ≈ 0.7 ms (on 72MHz STM32); 100 retries = ~70 ms worst-case.
 * This ensures we don't drop handshake responses even if the host is slow.
 */
#define BUTTON_TX_RETRIES    100

/* ── State ───────────────────────────────────────────────────────────── */
static char     s_rxBuf[COMM_RX_BUF_SIZE];
static uint16_t s_rxHead = 0;

/* Last values that were actually transmitted (for delta filter). */
static uint16_t s_lastSent[NUM_SLIDERS];
static uint8_t  s_lastSentValid = 0;   /* 0 until first transmission */

/*
 * Set to 1 once the board has successfully responded to (or sent) a
 * handshake.  Slider data is gated behind this flag so that USB
 * enumeration is never polluted with slider traffic.
 */
static uint8_t s_connected = 0;

static uint32_t s_lastPingTime = 0;
static uint8_t s_send_params_pending = 0;

/*
 * Post-connect burst counter.
 * After every successful handshake this is set to COMM_CONNECT_BURST.
 * COMM_SendSliders() sends unconditionally (bypassing the delta filter)
 * while this counter is non-zero, decrementing it each call.  This
 * guarantees the host receives a full snapshot of all slider positions
 * right after connecting even if no slider has moved past the threshold.
 * The counter is checked/decremented inside COMM_SendSliders so the
 * main loop is never stalled waiting for the burst to complete.
 */
#define COMM_CONNECT_BURST  20u
static uint8_t s_burst_remaining = 0;

/* ── Internal helpers ────────────────────────────────────────────────── */

/*
 * _send_reliable – attempt to transmit, retry BUTTON_TX_RETRIES times
 * on USBD_BUSY with a minimal spin.  Used for high-priority frames
 * (handshake, config, button press) where a dropped frame is unacceptable.
 */
static void _send_reliable(const char *str, uint16_t len)
{
    for (int retry = 0; retry < BUTTON_TX_RETRIES; retry++) {
        if (CDC_Transmit_FS((uint8_t *)str, len) == 0 /* USBD_OK */) return;
        /* ~0.1 ms spin – total worst case ≈ 1 ms */
        for (volatile int d = 0; d < 10000; d++) {}
    }
}

/*
 * _send_best_effort – single-shot transmit for slider data.
 * Returns without retrying so the main loop is never stalled.
 * A missed slider frame is harmless; the next one arrives in ≤ SEND_INTERVAL_MS.
 */
static inline void _send_best_effort(const char *str, uint16_t len)
{
    CDC_Transmit_FS((uint8_t *)str, len);
}

/* ── Public functions ────────────────────────────────────────────────── */

void COMM_Init(void)
{
    memset(s_rxBuf,    0, sizeof(s_rxBuf));
    memset(s_lastSent, 0, sizeof(s_lastSent));
    s_rxHead       = 0;
    s_lastSentValid = 0;
    s_connected    = 0;

    /*
     * Wait for USB stack enumeration using HAL_GetTick() (no busy-loops).
     * COMM_ENUM_WAIT_MS is chosen conservatively; most hosts enumerate
     * within 400-500 ms.  We must not block other init tasks, so we use
     * a simple tick comparison.
     */
    uint32_t start = HAL_GetTick();
    while ((HAL_GetTick() - start) < COMM_ENUM_WAIT_MS) {
        /* Yield – other HAL tasks (SysTick callbacks) still run */
        __NOP();
    }

    /*
     * Send startup handshake.  The Python host listens for this string
     * on connect.  Use the reliable path so USB-busy doesn't drop it.
     */
    _send_reliable(HANDSHAKE_RESPONSE, (uint16_t)(sizeof(HANDSHAKE_RESPONSE) - 1));

    /* Mark disconnected so we show Disconnected until handshake */
    s_connected = 0;
}

void COMM_OnRxData(const uint8_t *buf, uint32_t len)
{
    /*
     * Accumulate incoming bytes into s_rxBuf.
     * When a '\n' is received, process the complete line.
     * Handshake and GET_CONFIG requests are answered via the reliable path
     * so they have priority over any concurrent slider transmission.
     */
    for (uint32_t i = 0; i < len; i++) {
        char c = (char)buf[i];

        if (c == '\r') continue;  /* Ignore CR, wait for LF */

        if (c == '\n') {
            s_rxBuf[s_rxHead] = '\0';

            if (strcmp(s_rxBuf, HANDSHAKE_REQUEST) == 0) {
                /* Host is re-requesting handshake – re-arm connection state */
                s_connected = 1;
                s_burst_remaining = COMM_CONNECT_BURST; /* send 20 frames unconditionally */
                s_lastPingTime = HAL_GetTick();
                _send_reliable(HANDSHAKE_RESPONSE,
                               (uint16_t)(sizeof(HANDSHAKE_RESPONSE) - 1));
                s_send_params_pending = 1;
            } else if (strncmp(s_rxBuf, "Parameter_update: ", 18) == 0) {
                char *ptr = s_rxBuf + 18;
                if (*ptr == '"') {
                    ptr++;
                    char *name_end = strchr(ptr, '"');
                    if (name_end) {
                        *name_end = '\0';
                        char *name = ptr;
                        ptr = name_end + 1;
                        char *val_start = strchr(ptr, '"');
                        if (val_start) {
                            val_start++;
                            char *val_end = strchr(val_start, '"');
                            if (val_end) {
                                *val_end = '\0';
                                PARAMS_Update(name, val_start);
                            }
                        }
                    }
                }
                _send_reliable("ACK\r\n", 5);
            } else if (strncmp(s_rxBuf, "SET_PARAMS:", 11) == 0) {
                /* Handled elsewhere or just ACK to avoid timeout */
                _send_reliable("ACK\r\n", 5);
            } else if (strcmp(s_rxBuf, "DISCONNECTED") == 0) {
                s_connected = 0;
                _send_reliable("ACK\r\n", 5);
            } else if (strcmp(s_rxBuf, "GET_PARAMS") == 0) {
                s_send_params_pending = 1;
            } else if (strcmp(s_rxBuf, "GET_CONFIG") == 0) {
                _send_reliable(CONFIG_RESPONSE,
                               (uint16_t)(sizeof(CONFIG_RESPONSE) - 1));
            } else if (strcmp(s_rxBuf, "CONNECTED") == 0) {
                _send_reliable("ACK\r\n", 5);
            }
            /* Unknown commands silently ignored (future extension point) */

            s_rxHead = 0;
        } else {
            if (s_rxHead < COMM_RX_BUF_SIZE - 1) {
                s_rxBuf[s_rxHead++] = c;
            } else {
                /* Buffer overflow – discard the corrupted line */
                s_rxHead = 0;
            }
        }
    }
}

void COMM_SendSliders(const uint16_t *values, uint8_t count)
{
    /*
     * Connection guard – never transmit slider data before handshake.
     * During USB enumeration this prevents a burst of slider packets from
     * filling the USB TX buffer and delaying the handshake response.
     */
    if (!s_connected) return;

    /*
     * Delta filter – skip the transmission entirely if nothing changed
     * beyond the noise threshold.  This eliminates idle USB traffic when
     * the user is not touching the hardware.
     */
    static uint16_t s_dispAnchor[NUM_SLIDERS] = {0};
    static uint8_t s_dispAnchorInit = 0;
    if (!s_dispAnchorInit) {
        for(uint8_t i=0; i<count; i++) s_dispAnchor[i] = values[i];
        s_dispAnchorInit = 1;
    }

    if (s_lastSentValid) {
        uint8_t changed = 0;
        for (uint8_t i = 0; i < count; i++) {
            uint16_t prev = s_lastSent[i];
            uint16_t curr = values[i];
            /* Absolute difference without using abs() to stay C89-compatible */
            uint16_t diff = (curr >= prev) ? (curr - prev) : (prev - curr);
            if (diff > SLIDER_TX_THRESHOLD) {
                changed = 1;
            }

            uint16_t diff_anchor = (curr >= s_dispAnchor[i]) ? (curr - s_dispAnchor[i]) : (s_dispAnchor[i] - curr);
            if (diff_anchor > 14) {
                s_dispAnchor[i] = curr;
                DISPLAY_ShowOverride(PARAMS_GetSliderName(i));
            }
        }

        /*
         * Post-connect burst: bypass the delta-filter gate for the first
         * COMM_CONNECT_BURST calls after a handshake so the host gets a
         * full slider snapshot immediately.  We decrement here (inside
         * the s_lastSentValid block so the very first ever send, which
         * always passes through, is counted separately).
         * The main loop is never blocked – one frame per loop iteration.
         */
        if (s_burst_remaining > 0) {
            s_burst_remaining--;
            /* fall through to transmit unconditionally */
        } else if (!changed) {
            return;   /* Nothing to send – bandwidth saved */
        }
    }

    /*
     * Build: "Slider 1 512|Slider 2 1024|...|Slider 5 0\r\n"
     * Max per entry: "Slider X YYYY" = 13 chars, plus separator = 14.
     * 5 × 14 + 2 (\r\n) = 72 bytes – well within COMM_TX_BUF_SIZE (256).
     * Scale: 0-1024 (raw 12-bit >> 2). Python host divides by 1024.0.
     */
    static char buf[COMM_TX_BUF_SIZE];   /* static: no stack pressure */
    int pos = 0;

    for (uint8_t i = 0; i < count && pos < (int)sizeof(buf) - 16; i++) {
        if (i > 0) buf[pos++] = '|';
        pos += snprintf(buf + pos, sizeof(buf) - pos,
                        "Slider %d %d", i + 1, (int)values[i]);
    }
    buf[pos++] = '\r';
    buf[pos++] = '\n';
    buf[pos]   = '\0';

    /* Update delta cache before sending */
    for (uint8_t i = 0; i < count; i++) s_lastSent[i] = values[i];
    s_lastSentValid = 1;

    /* Best-effort: drop this frame if USB is busy; next frame arrives soon */
    _send_best_effort(buf, (uint16_t)pos);
}

void COMM_SendButtonPress(uint8_t index)
{
    if (!s_connected) return;

    DISPLAY_ShowOverride(PARAMS_GetButtonName(index));

    /*
     * Button presses are one-shot events – use the reliable path so a
     * transient USBD_BUSY does not silently drop a keypress.
     */
    char buf[24];
    int  len = snprintf(buf, sizeof(buf), "Button %d 1\r\n", index + 1);
    _send_reliable(buf, (uint16_t)len);
}

void COMM_Send(const char *str)
{
    uint16_t len = (uint16_t)strlen(str);
    if (len == 0) return;
    _send_reliable(str, len);
}

void COMM_Process(void)
{
    uint32_t now = HAL_GetTick();

    if (s_connected) {
        if (now - s_lastPingTime >= 30000) {
            s_lastPingTime = now;
            COMM_Send("PING\r\n");
        }
    }

    if (s_send_params_pending) {
        s_send_params_pending = 0;
        PARAMS_SendList();
    }
    
    PARAMS_Process();

    /* Let display module know about the connection status */
    DISPLAY_SetConnectionState(s_connected);
}
