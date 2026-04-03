/*  oled_control.c */
#include "uart.h"

#define MYONE 1
#define MYZERO 0

#define CHAR_LF 10
#define CHAR_CR 13


#define BUFFER_LEN (32+5)
static char txbuffer[BUFFER_LEN] = "                                    \n";
static char rxbuffer[BUFFER_LEN];
static uint8_t rxin = 0;
static uint8_t rxout = 0;
static uint8_t phase = 2;  // This is used to support the 4 times over sample on receive

volatile bool refresh = false;
uint8_t       txlen   = BUFFER_LEN;

void uart_init(void) {
    UART_OUT_PIN = MYONE; // Set line to idle state
}


void uartProcessOutput(void) {
    if (phase)
        return;
    static uint8_t strPosition = 0;     // Charcter location in string
    static uint8_t chrPosition = 0;     // Bit in character

    static uint8_t buf = 0x00;

    if (chrPosition == 0) {
        if (refresh) {
            if (strPosition < txlen) {
                UART_OUT_PIN = MYZERO; // Start bit
                buf = txbuffer[strPosition];
            }
            chrPosition++;
        }
    } else if (chrPosition <= 8) {
        if (buf & 0x01) {
            UART_OUT_PIN = MYONE;
        } else {
            UART_OUT_PIN = MYZERO;
        }
        buf >>= 1;
        chrPosition++;
    } else if (chrPosition <= 10) {
        UART_OUT_PIN = MYONE; // Stop bit
        chrPosition++;
    } else {
        chrPosition = 0;
        strPosition++;
        if (strPosition == txlen) {
            refresh = false;
            strPosition = 0;
        }
    }
}



void uart_str(char *str) {
    uint8_t len = 0;

    // Wait for any active send to finish

    while(refresh)
        CLRWDT();

    // Copy string to txbuffer

    while (str[len]) {
        txbuffer[len] = str[len];
        len++;
    }

    // Kick off send

    txlen = len;
    refresh = true;
}


////////////////////////////////////////

enum state_e {
    START_BIT,
    DATA_BIT,
    STOP_BIT,
};

void uartProcessInput(void) {
    static uint8_t state;
    static uint8_t buf;
    static uint8_t bitCounter = 0;

    bool inbit = UART_IN_PIN;

    if (state == START_BIT) {
        if (inbit == MYZERO) {
            bitCounter = 0;
            state = DATA_BIT;
            phase = 5;  // This shifts use to the center of the first data bit +/- 25%
        }
    }

    if (phase) {
        phase--;
        return;
    }
    phase = 3;    

    switch (state) {
        case DATA_BIT:
            buf >>= 1;
            buf |= inbit << 7;

            if (++bitCounter == 8) {
                state = STOP_BIT;
            }
            break;

        case STOP_BIT:
            if (inbit == MYONE) {
                rxbuffer[rxin++] = buf;
                if (rxin >= BUFFER_LEN)
                    rxin = 0;
            }
            state = START_BIT;
            break;

        default:
            break;
    }
}

char uartGetChar(void) {
    if (rxout == rxin)
        return 0;

    char ret = rxbuffer[rxout++];
    if (rxout >= BUFFER_LEN)
        rxout = 0;
    return ret;
}
