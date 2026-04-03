#include "json.h"
#include "uart.h"


bool json_rx_busy = false;
char json_rx_name[JSON_MAX_STR];
bool json_rx_bool;
int  json_rx_int;
char json_rx_str[JSON_MAX_STR];


typedef enum {
    JRS_START_WAIT,
    JRS_NAME_WAIT,
    JRS_NAME,
    JRS_VALUE_WAIT,
    JRS_INT,
    JRS_STR
} json_rx_state_t;


typedef enum {
    JRT_UNKNOWN,
    JRT_BOOL,
    JRT_INT,
    JRT_STR
} json_rx_type_t;


static bool have_var;

static json_rx_state_t json_rx_state = JRS_START_WAIT;
static json_rx_type_t  json_rx_type  = JRT_UNKNOWN;
static uint8_t         json_rx_pos;

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


void json_event(char *event)
{
    json_start();
    json_str("Event", event);
    json_end();
}


json_rx_result_t json_rx_process(char rx)
{
    switch (json_rx_state) {
    case JRS_START_WAIT:
/*    
        if (rx != 10) {
            json_start();
            json_int("Debug", rx, 0);
            json_end();
        }
*/            
        if (rx == '{') {
            json_rx_busy = true;
            json_rx_state = JRS_NAME_WAIT;
        } else {
            return JRR_NOT_JSON;
        }
        break;
 
    case JRS_NAME_WAIT:
        if (rx == '}') {
            json_rx_busy = false;
            json_rx_state = JRS_START_WAIT;
            return JRR_END;
        } else if (rx == '"') {
            json_rx_pos = 0;
            json_rx_state = JRS_NAME;
        }
        break;

    case JRS_NAME:
        if (rx == '"') {
            json_rx_state = JRS_VALUE_WAIT;
        } else if (json_rx_pos <= (JSON_MAX_STR-2)) {
            json_rx_name[json_rx_pos++] = rx;
            json_rx_name[json_rx_pos] = 0;
        }
        break;

    case JRS_VALUE_WAIT:
        if (rx == '"') {
            json_rx_pos = 0;
            json_rx_state = JRS_STR;
        } else if (rx == 't') {
            json_rx_bool = true;
            json_rx_state = JRS_NAME_WAIT;
            return JRR_BOOL;
        } else if (rx == 'f') {
            json_rx_bool = false;
            json_rx_state = JRS_NAME_WAIT;
            return JRR_BOOL;
        } else if ((rx >= '0') && (rx <= '9')) {
            json_rx_int = rx - '0';
            json_rx_state = JRS_INT;
        }
        break;

    case JRS_INT:
        if ((rx >= '0') && (rx <= '9')) {
            json_rx_int = json_rx_int * 10 + rx - (int)'0';
        } else {
            json_rx_state = JRS_NAME_WAIT;
            return JRR_INT;
        }
        break;

    case JRS_STR:
        if (rx == '"') {
            json_rx_state = JRS_NAME_WAIT;
            return JRR_STR;
        } else if (json_rx_pos <= (JSON_MAX_STR-2)) {
            json_rx_str[json_rx_pos++] = rx;
            json_rx_str[json_rx_pos] = 0;
        }
        break;
    }

    return JRR_NO_DATA;
}
