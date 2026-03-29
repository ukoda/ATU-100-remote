#ifndef json_h
#define json_h

#include <stdbool.h>
#include <stdint.h>


void json_start(void);
void json_end(void);
void json_str(char *name, char *value);
void json_bool(char *name, bool value);
void json_int(char *name, int value, uint8_t dp);
void json_event(char *event);

#endif
