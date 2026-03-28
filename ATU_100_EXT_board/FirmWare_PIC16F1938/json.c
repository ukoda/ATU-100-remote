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


void json_name(char *name)
{
    if (have_var)
        uart_str(",\n");
    uart_str("  \"");
    uart_str(name);
    uart_str("\": ");
    have_var = true;
}


void json_str(char *name, char *value)
{
    json_name(name);
    uart_str("\"");
    uart_str(value);
    uart_str("\"");
}


void json_bool(char *name, bool value)
{
    json_name(name);
    if (value)
        uart_str("true");
    else
        uart_str("false");
}


void json_int(char *name, int value, uint8_t dp)
{
#define NUMLEN 8
    char str[NUMLEN];
    uint8_t pos;

    json_name(name);

    str[NUMLEN-1] = 0;
    for (pos = 0; pos < (NUMLEN-2); pos++) {
        if (pos == (NUMLEN-2 -dp))
            str[pos] = '.';
        else
            str[pos] = '0';
    }

    pos = NUMLEN-2;
    do
    {
        if (str[pos] == '.')
            pos--;
        str[pos] = '0' + (char)(value % 10);
        pos--;
        value /= 10;
    } while (value != 0);

//    pos++;
    if (pos > (NUMLEN-3 -dp))
      pos = NUMLEN-3 -dp;
    if (str[pos+1] == '.')
        pos--;
    uart_str(&str[pos+1]);
}
