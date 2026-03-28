#include "json.h"
#include "uart.h"

static bool have_var;

void json_start(void)
{
    have_var = false;
    uart_str("{\n");
}


void json_end(void)
{
    uart_str("\n}\n");
}


void json_str(char *name, char *value)
{
    if (have_var)
        uart_str(",\n");
    uart_str("  \"");
    uart_str(name);
    uart_str("\": \"");
    uart_str(value);
    uart_str("\"");
    have_var = true;
}
