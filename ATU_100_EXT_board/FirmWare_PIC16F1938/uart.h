#ifndef uart_h
#define uart_h

#include "cross_compiler.h"

void uart_init(void);

void uartProcessInput(void);
void uartProcessOutput(void);

char uartGetChar(void);

void uart_str(char *str);
void uart_wr_str(char, char, char *, char);

#endif
