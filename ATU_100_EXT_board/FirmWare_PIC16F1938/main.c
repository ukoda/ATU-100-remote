//   ATU-100 project
//   David Fainitski
//   2016

#include "cross_compiler.h"
#include "uart.h"
#include "json.h"
#include "main.h"
#include <stdbool.h>
#include <string.h>

/*  a few constants */

#define DEFAULT_INITIAL_OLD_VALUE  10000

#define DYSP_CNT_MULT 2.3

#define MAX_EVENT_STR  20

// Variables
int g_i_SWR_fixed_old = 0;
char g_work_str[7], g_work_str_2[7];
int g_i_Power = 0, g_i_Power_old = DEFAULT_INITIAL_OLD_VALUE, g_i_Power_report = 0;
int g_i_SWR_old = DEFAULT_INITIAL_OLD_VALUE;
int g_i_SWR_fixed;
int g_i_Efficency = 0;
char g_b_Soft_tune = 0;
char g_b_Auto_mode = 0;

char g_b_Bypas_mode = 0;
char g_c_cap_mem = 0, g_c_ind_mem = 0, g_c_SW_mem = 0, g_c_Auto_mem = 0;

char g_b_Restart = 0;
char g_b_Test_mode = 0;
char g_b_lcd_prep_short = 0;
char g_b_L = 1;

char g_b_Loss_mode = 0;

char event_str[MAX_EVENT_STR];
bool new_event = false;
bool new_state = false;

/*  initial eeprom values*/
// PP5OO - Cell 31 changed from 0x10 to 0x11 because of error on transformer winding.
__eeprom unsigned char initial_eeprom[256] = {
    0x78, 0x01, 0x01, 0x15, 0x13, 0x01, 0x00, 0x00, 0x02, 0x00, 0x07, 0x00, 0x07, 0x00, 0x01, 0x00,
    0x00, 0x50, 0x01, 0x10, 0x02, 0x20, 0x04, 0x50, 0x10, 0x00, 0x22, 0x00, 0x45, 0x00, 0xff, 0xff,
    0x00, 0x10, 0x00, 0x22, 0x00, 0x47, 0x01, 0x00, 0x02, 0x20, 0x04, 0x70, 0x10, 0x00, 0xff, 0xff,
    0x00, 0x11, 0x00, 0x01, 0x00, 0x00, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0x00, 0x00, 0x01, 0x00, 0x00,
};

//***************** Forward declares *****************

void send_event(char *event);
void send_state(void);




void __interrupt() isr(void) {
    if (TMR0IE && TMR0IF) {
        // Actually 19200 sample rate, which is 4 x over samples to give actual 4800 baud
        TMR0 = 256 - (4000000 / 9600 / 2) + 7;
        TMR0IF = 0;
        uartProcessInput();
        uartProcessOutput();
    }
}

void interrupt_init(void) {
    OPTION_REGbits.PS = 0b000; // 1:2 Prescaller
//    OPTION_REGbits.PSA = 0; // Prescaller assigned to Timer0
    OPTION_REGbits.PSA = 1; // Prescaller assigned to Timer0
    OPTION_REGbits.T0CS = 0; // Timer increments on instruction clock
    INTCONbits.T0IE = 1; // Enable interrupt on TMR0 overflow
    INTCONbits.PEIE = 1; // Enable peripheral interrupt
    INTCONbits.GIE = 1; // Enable global interrupt
}

void main() {

    if (STATUSbits.nTO == 0)
        g_b_Restart = 1;

    pic_init();
    uart_init();

    interrupt_init();

    //
    Delay_ms(300);
    CLRWDT();
    cells_init();

    //
    Delay_ms(300);
    CLRWDT();

    if (e_c_num_L_q == 5)
        g_c_L_mult = 1;
    else if (e_c_num_L_q == 6)
        g_c_L_mult = 2;
    else if (e_c_num_L_q == 7)
        g_c_L_mult = 4;
    if (e_c_num_C_q == 5)
        g_c_C_mult = 1;
    else if (e_c_num_C_q == 6)
        g_c_C_mult = 2;
    else if (e_c_num_C_q == 7)
        g_c_C_mult = 4;

    Delay_ms(300);
    CLRWDT();
    Delay_ms(300);
    CLRWDT();
    Delay_ms(300);
    CLRWDT();
    Delay_ms(300);
    CLRWDT();
    Delay_ms(300);
    CLRWDT();

    //
    if (g_b_Test_mode == 0) {
        g_c_cap = eeprom_read(EEPROM_LAST_CAP);
        g_c_ind = eeprom_read(EEPROM_LAST_IND);
        g_c_SW = eeprom_read(EEPROM_LAST_SW);
        g_i_swr_a = eeprom_read(EEPROM_LAST_SWR_H) * 256;
        g_i_swr_a += eeprom_read(EEPROM_LAST_SWR_L);
        set_ind(g_c_ind);
        set_cap(g_c_cap);
        set_sw(g_c_SW);
        if (g_b_Restart == 1)
            g_b_lcd_prep_short = 1;
        lcd_prep();
    } else
        Test_init();

    lcd_ind();

    //*******************************

    while (1) {
        CLRWDT();
        lcd_pwr();
        //
        if (g_b_Test_mode == 0)
            button_proc();
        else
            button_proc_test();

        send_state();

        //
//        if (g_b_Test_mode == 0 & g_b_display_onoff == 1) {
//            if (e_c_b_Relay_off) {
//                set_ind(0);
//                set_cap(0);
//                set_sw(0);
//            }
//            g_b_display_onoff = 0;
//        }

        // next While code
    }
}

//***************** Routines *****************

void send_event(char *event)
{
    strncpy(event_str, event, MAX_EVENT_STR);
    new_event = true;
}


void send_error(void)
{
    send_event("Error");
}


void send_state(void)
{
    uint8_t sft;
    if (json_rx_busy)
        return;

    if (new_event) {
        new_event = false;
        json_event(event_str);
    }

    if (!new_state)
        return;
    
    new_state = false;
    json_start();
    json_bool("Auto", g_b_Auto_mode);
    json_bool("Bypass", g_b_Bypas_mode);
    if (g_i_Efficency > 0)
        json_int("efficency", g_i_Efficency, 0);
    if (e_c_b_P_High == 0)
        sft = 1;
    else
        sft = 0;
    json_int("Power", g_i_Power_report, sft);
    json_int("SWR", g_i_SWR_fixed, 2);
    json_str("Order", (g_c_SW == 1) ? "LC" : "CL");
    json_int("Capacitance", g_i_cap, 0);
    json_int("Inductance", g_i_ind, 0);
    json_end();
}


void button_proc_test(void) {
    if (Button(&PORTB, TUNE_BUTTON, 50, BUTTON_PRESSED)) { // Tune btn
        Delay_ms(250);
        CLRWDT();
        if (PORTB_TUNE_BUTTON == BUTTON_RELEASED) { // short press button
            if (g_c_SW == 0)
                g_c_SW = 1;
            else
                g_c_SW = 0;
            set_sw(g_c_SW);
            lcd_ind();
        } else { // long press button
            if (g_b_L == 1)
                g_b_L = 0;
            else
                g_b_L = 1;
            if (g_b_L == 1) {
                send_event("Inductor");
            } else {
                send_event("Capacitor");
            }
        }
        while (Button(&PORTB, TUNE_BUTTON, 50, BUTTON_PRESSED)) {
            lcd_pwr();
            CLRWDT();
        }
    } // END Tune btn
    //
    if (Button(&PORTB, BYPASS_BUTTON, 50, BUTTON_PRESSED)) { // BYP button
        CLRWDT();
        while (PORTB_BYPASS_BUTTON == BUTTON_PRESSED) {
            if (g_b_L & (g_c_ind < 32 * g_c_L_mult - 1)) {
                g_c_ind++;
                set_ind(g_c_ind);
            } else if (!g_b_L & (g_c_cap < 32 * g_c_L_mult - 1)) {
                g_c_cap++;
                set_cap(g_c_cap);
            }
            lcd_ind();
            lcd_pwr();
            Delay_ms(30);
            CLRWDT();
        }
    } // end of BYP button
    //
    if (Button(&PORTB, AUTO_BUTTON, 50, BUTTON_PRESSED) & (g_b_Bypas_mode == 0)) { // g_b_Auto_mode button
        CLRWDT();
        while (PORTB_AUTO_BUTTON == BUTTON_PRESSED) {
            if (g_b_L & (g_c_ind > 0)) {
                g_c_ind--;
                set_ind(g_c_ind);
            } else if (!g_b_L & (g_c_cap > 0)) {
                g_c_cap--;
                set_cap(g_c_cap);
            }
            lcd_ind();
            lcd_pwr();
            Delay_ms(30);
            CLRWDT();
        }
    }
    return;
}


void toggle_auto_mode(void)
{
    CLRWDT();
    if (g_b_Auto_mode == 0)
        g_b_Auto_mode = 1;
    else
        g_b_Auto_mode = 0;
    eeprom_write(EEPROM_AUTOMATIC_MODE, g_b_Auto_mode);
    CLRWDT();
    new_state = true;
}


void toggle_bypass_mode(void)
{
    CLRWDT();
    if (g_b_Bypas_mode == 0) {
        g_b_Bypas_mode = 1;
        g_c_cap_mem = g_c_cap;
        g_c_ind_mem = g_c_ind;
        g_c_SW_mem = g_c_SW;
        g_c_cap = 0;
        if (e_c_b_L_invert)
            g_c_ind = 255;
        else
            g_c_ind = 0;
        g_c_SW = 1;
        set_ind(g_c_ind);
        set_cap(g_c_cap);
        set_sw(g_c_SW);
        if (g_b_Loss_mode == 0)
            lcd_ind();
        g_c_Auto_mem = g_b_Auto_mode;
        g_b_Auto_mode = 0;
    } else {
        g_b_Bypas_mode = 0;
        g_c_cap = g_c_cap_mem;
        g_c_ind = g_c_ind_mem;
        g_c_SW = g_c_SW_mem;
        set_cap(g_c_cap);
        set_ind(g_c_ind);
        set_sw(g_c_SW);
        if (g_b_Loss_mode == 0)
            lcd_ind();
        g_b_Auto_mode = g_c_Auto_mem;
    }
    CLRWDT();
    new_state = true;
}


void start_reset(void)
{
    CLRWDT();
    show_reset();
    g_b_Bypas_mode = 0;
    new_state = true;
}


void start_tune(void)
{
    CLRWDT();
    p_Tx = 1; //
    n_Tx = 0; // TX request
    Delay_ms(250); //
    tune_btn_push();
    g_b_Bypas_mode = 0;
    g_b_Soft_tune = 0;
    new_state = true;
}


void button_proc_rx(char uartChar) {

    // RESET
    if (uartChar == 'r') {
        Delay_ms(250);
        start_reset();
    }

    // TUNE
    if (uartChar == 't' || g_b_Soft_tune) {
        Delay_ms(250);
        start_tune();
    }


    // BYPASS
    if (uartChar == 'b') {
        toggle_bypass_mode();
    }

    // AUTO
    if (uartChar == 'a' && g_b_Bypas_mode == 0)
        toggle_auto_mode();
    return;
}


char nibbletochar(uint8_t nibble)
{
    nibble &= 0xf;
    if (nibble < 10)
        return nibble + '0';
    else
        return nibble - 10 + 'a';
}


void bytetostr(uint8_t byte, char *str)
{
    str[0] = nibbletochar(byte >> 4);
    str[1] = nibbletochar(byte);
    str[2] = 0;
}


void dump_eeprom()
{
    uint16_t address;
    char addstr[3];
    char datastr[3];

    CLRWDT();
    json_start();
    for (address = 0; address <= 0xff; address++) {
        bytetostr((uint8_t)address, addstr);
        bytetostr(eeprom_read((uint8_t)address), datastr);
        CLRWDT();
        json_str(addstr, datastr);
    }
    json_end();
}


void button_proc(void) {
    char uartChar = uartGetChar();

    while (uartChar && (uartChar < 0x80)) {
        CLRWDT();
        switch (json_rx_process(uartChar))
        {
        case JRR_NOT_JSON:
            button_proc_rx(uartChar);
            break;
        
        case JRR_BOOL:
            if (strcmp(json_rx_name, "Auto") == 0) {
                if (g_b_Bypas_mode == 0) {
                    if (json_rx_bool != (g_b_Auto_mode == 1))
                        toggle_auto_mode();
                    new_state = true;
                } else {
                    send_error();
                }

            } else if (strcmp(json_rx_name, "Bypass") == 0) {
                if (json_rx_bool != (g_b_Bypas_mode == 1))
                    toggle_bypass_mode();
                new_state = true;
                
            } else if (strcmp(json_rx_name, "Reset") == 0) {
                start_reset();
                
            } else if (strcmp(json_rx_name, "Status") == 0) {
                CLRWDT();
                new_state = true;
                
            } else if (strcmp(json_rx_name, "Tune") == 0) {
                start_tune();
                new_state = true;

            } else {
                send_error();
            }
            break;

        case JRR_INT:
            send_error();
            break;

        case JRR_STR:
            if (strcmp(json_rx_name, "Dump") == 0) {
                dump_eeprom();
            } else {
                send_error();
            }
            break;

        default:
            break;
        }

    uartChar = uartGetChar();
    }
}


void show_reset() {
    atu_reset();
    g_c_SW = 1;
    set_sw(g_c_SW);
    eeprom_write(EEPROM_LAST_CAP, 0);
    eeprom_write(EEPROM_LAST_IND, 0);
    eeprom_write(EEPROM_LAST_SW, 1);
    eeprom_write(EEPROM_LAST_SWR_H, 0);
    eeprom_write(EEPROM_LAST_SWR_L, 0);
    lcd_ind();
    g_b_Loss_mode = 0;
    p_Tx = 0;
    n_Tx = 1;
    g_i_SWR = 0;
    g_i_PWR = 0;
    g_i_SWR_fixed_old = 0;
    send_event("Reset");
    CLRWDT();
    g_i_SWR_old = DEFAULT_INITIAL_OLD_VALUE;
    g_i_Power_old = DEFAULT_INITIAL_OLD_VALUE;
    lcd_pwr();
    return;
}

void tune_btn_push() {
    CLRWDT();
    send_event("Tune");
    tune();
    if (g_b_Loss_mode == 0 | e_c_b_Loss_ind == 0)
        lcd_ind();
    eeprom_write(EEPROM_LAST_CAP, g_c_cap);
    eeprom_write(EEPROM_LAST_IND, g_c_ind);
    eeprom_write(EEPROM_LAST_SW, g_c_SW);
    eeprom_write(EEPROM_LAST_SWR_H, (char) (g_i_swr_a / 256));
    eeprom_write(EEPROM_LAST_SWR_L, (char) (g_i_swr_a % 256));
    g_i_SWR_old = DEFAULT_INITIAL_OLD_VALUE;
    g_i_Power_old = DEFAULT_INITIAL_OLD_VALUE;
    lcd_pwr();
    g_i_SWR_fixed_old = g_i_SWR;
    p_Tx = 0;
    n_Tx = 1;
    CLRWDT();
    return;
}

void lcd_prep() {
    CLRWDT();
    if (g_b_lcd_prep_short == 0) {
        uart_str("\n");
        send_event("Startup");
        json_start();
        json_str("Board", "ATU-100_EXT");
        json_str("Credit", "N7DDC");
        json_str("FW", "3.2");
        json_str("Build", "ukoda");
        json_end();
    }
    CLRWDT();
    lcd_ind();
    new_state = true;
    return;
}

void lcd_swr(int swr) {
    if (swr != g_i_SWR_old) {
        g_i_SWR_old = swr;
        new_state = true;
    }
    CLRWDT();
    return;
}

void show_pwr(int parm_Power, int parm_SWR) {
    int p_ant;
    double a, b;
    a = 100;
    CLRWDT();
    //
    if (g_b_Test_mode == 0 & e_c_b_Loss_ind == 1 & parm_Power >= 10) {
        g_b_Loss_mode = 1;
    } else {
        if (g_b_Loss_mode == 1)
            lcd_ind();
        g_b_Loss_mode = 0;
    }
    CLRWDT();
    if (parm_Power != g_i_Power_old) {
        g_i_Power_old = parm_Power;
        g_i_Power_report = parm_Power;
        //  Loss indication
        if (g_b_Loss_mode == 1) {
            if (g_c_ind == 0 & g_c_cap == 0)
                g_i_swr_a = parm_SWR;
            a = 1.0 / ((g_i_swr_a / 100.0 + 100.0 / g_i_swr_a) * e_c_tenths_Fid_loss / 10.0 * 0.115 + 1.0); // Fider loss
            b = 4.0 / (2.0 + parm_SWR / 100.0 + 100.0 / parm_SWR); // parm_SWR loss
            if (a >= 1.0)
                a = 1.0;
            if (b >= 1.0)
                b = 1.0;
            p_ant = (int) (parm_Power * a * b);
            g_i_Efficency = (int) (a * b * 100);
            if (g_i_Efficency >= 100)
                g_i_Efficency = 99;
            //
            g_i_Power_report = p_ant;
            //
        }
        new_state = true;
    }
    CLRWDT();
    return;
}

void lcd_pwr() {
    int p = 0;
    char peak_cnt;
    int delta = e_i_tenths_SWR_Auto_delta - 100;
    char cnt;
    g_i_PWR = 0;
    CLRWDT();

    // peak detector
    cnt = 120;
    for (peak_cnt = 0; peak_cnt < cnt; peak_cnt++) {
        get_pwr();
        if (g_i_PWR > p) {
            p = g_i_PWR;
            g_i_SWR_fixed = g_i_SWR;
        }
        Delay_ms(3);
    }
    CLRWDT();
    if (p >= 100) {
        p = (p + 5) / 10;
        p *= 10;
    } // round to 1 W if more then 100 W
    g_i_Power = p;
    if (g_i_Power < 10)
        g_i_SWR_fixed = 0;
    lcd_swr(g_i_SWR_fixed);
    //
    if (g_b_Auto_mode & (g_i_SWR_fixed >= e_i_tenths_SWR_Auto_delta) & ((g_i_SWR_fixed > g_i_SWR_fixed_old & (g_i_SWR_fixed - g_i_SWR_fixed_old) > delta) | (g_i_SWR_fixed < g_i_SWR_fixed_old & (g_i_SWR_fixed_old - g_i_SWR_fixed) > delta) | g_i_SWR_fixed_old == 999))
        g_b_Soft_tune = 1;

    show_pwr(g_i_Power, g_i_SWR_fixed);

    CLRWDT();
    if (g_b_Overload == 1) {
        send_event("Overload");
        CLRWDT();
        g_i_SWR_old = DEFAULT_INITIAL_OLD_VALUE;
        lcd_swr(g_i_SWR_fixed);
    }
    return;
}

void lcd_ind() {
    char l_line;
    int l_work_int;
    CLRWDT();
    charbits indbits;
    indbits.bytes = g_c_ind;
    l_work_int = 0;
    if (indbits.bits.B0)
        l_work_int += e_i_Ind1;
    if (indbits.bits.B1)
        l_work_int += e_i_Ind2;
    if (indbits.bits.B2)
        l_work_int += e_i_Ind3;
    if (indbits.bits.B3)
        l_work_int += e_i_Ind4;
    if (indbits.bits.B4)
        l_work_int += e_i_Ind5;
    if (indbits.bits.B5)
        l_work_int += e_i_Ind6;
    if (indbits.bits.B6)
        l_work_int += e_i_Ind7;
    g_i_ind = l_work_int;
    CLRWDT();
    l_work_int = 0;
    charbits capbits;
    capbits.bytes = g_c_cap;
    if (capbits.bits.B0)
        l_work_int += e_i_Cap1;
    if (capbits.bits.B1)
        l_work_int += e_i_Cap2;
    if (capbits.bits.B2)
        l_work_int += e_i_Cap3;
    if (capbits.bits.B3)
        l_work_int += e_i_Cap4;
    if (capbits.bits.B4)
        l_work_int += e_i_Cap5;
    if (capbits.bits.B5)
        l_work_int += e_i_Cap6;
    if (capbits.bits.B6)
        l_work_int += e_i_Cap7;
    g_i_cap = l_work_int;
    CLRWDT();
    return;
}

void Test_init(void) { // g_b_Test_mode mode
    send_event("Test mode inductor");
    atu_reset();
    g_c_SW = 1; // C to OUT
    set_sw(g_c_SW);
    eeprom_write(EEPROM_LAST_CAP, g_c_cap);
    eeprom_write(EEPROM_LAST_IND, g_c_ind);
    eeprom_write(EEPROM_LAST_SW, g_c_SW);
    g_b_lcd_prep_short = 1;
    lcd_prep();
    return;
}

void cells_init(void) {
    // Cells init
    CLRWDT();
    if (eeprom_read(EEPROM_AUTOMATIC_MODE) == 1)
        g_b_Auto_mode = 1;
    e_i_ms_Rel_Del = Bcd2Dec(eeprom_read(EEPROM_TIMEOUT_TIME)); // Relay's Delay
    e_i_tenths_SWR_Auto_delta = Bcd2Dec(eeprom_read(EEPROM_SWR_THRESHOLD)) * 10; // e_i_tenths_SWR_Auto_delta
    e_i_watts_min_for_start = Bcd2Dec(eeprom_read(EEPROM_MIN_POWER)) * 10; // P_min_for_start
    e_i_watts_max_for_start = Bcd2Dec(eeprom_read(EEPROM_MAX_POWER)) * 10; // P_max_for_start
    // 7  - shift down
    // 8 - shift left
    e_i_tenths_init_max_swr = Bcd2Dec(eeprom_read(EEPROM_MAX_INIT_SWR)) * 10; // Max g_i_SWR
    e_c_num_L_q = eeprom_read(EEPROM_NUMBER_INDS);
    e_c_b_L_linear = eeprom_read(EEPROM_IND_LINEAR_PITCH);
    e_c_num_C_q = eeprom_read(EEPROM_NUMBER_CAPS);
    e_c_b_C_linear = eeprom_read(EEPROM_CAP_LINEAR_PITCH);
    e_c_b_D_correction = eeprom_read(EEPROM_ENABLE_NONLINEAR_DIODE);
    e_c_b_L_invert = eeprom_read(EEPROM_INVERSE_INDUCTANCE_RELAY);
    //
    CLRWDT();
    e_i_Ind1 = Bcd2Dec(eeprom_read(16)) * 100 + Bcd2Dec(eeprom_read(17)); // e_i_Ind1
    e_i_Ind2 = Bcd2Dec(eeprom_read(18)) * 100 + Bcd2Dec(eeprom_read(19)); // e_i_Ind2
    e_i_Ind3 = Bcd2Dec(eeprom_read(20)) * 100 + Bcd2Dec(eeprom_read(21)); // e_i_Ind3
    e_i_Ind4 = Bcd2Dec(eeprom_read(22)) * 100 + Bcd2Dec(eeprom_read(23)); // e_i_Ind4
    e_i_Ind5 = Bcd2Dec(eeprom_read(24)) * 100 + Bcd2Dec(eeprom_read(25)); // e_i_Ind5
    e_i_Ind6 = Bcd2Dec(eeprom_read(26)) * 100 + Bcd2Dec(eeprom_read(27)); // e_i_Ind6
    e_i_Ind7 = Bcd2Dec(eeprom_read(28)) * 100 + Bcd2Dec(eeprom_read(29)); // e_i_Ind7
    //
    e_i_Cap1 = Bcd2Dec(eeprom_read(32)) * 100 + Bcd2Dec(eeprom_read(33)); // e_i_Cap1
    e_i_Cap2 = Bcd2Dec(eeprom_read(34)) * 100 + Bcd2Dec(eeprom_read(35)); // e_i_Cap2
    e_i_Cap3 = Bcd2Dec(eeprom_read(36)) * 100 + Bcd2Dec(eeprom_read(37)); // e_i_Cap3
    e_i_Cap4 = Bcd2Dec(eeprom_read(38)) * 100 + Bcd2Dec(eeprom_read(39)); // e_i_Cap4
    e_i_Cap5 = Bcd2Dec(eeprom_read(40)) * 100 + Bcd2Dec(eeprom_read(41)); // e_i_Cap5
    e_i_Cap6 = Bcd2Dec(eeprom_read(42)) * 100 + Bcd2Dec(eeprom_read(43)); // e_i_Cap6
    e_i_Cap7 = Bcd2Dec(eeprom_read(44)) * 100 + Bcd2Dec(eeprom_read(45)); // e_i_Cap7
    //
    e_c_b_P_High = eeprom_read(EEPROM_POWER_MEASURE_LEVEL); // High power
    e_c_K_Mult = Bcd2Dec(eeprom_read(EEPROM_TANDEM_MATCH)); // Tandem Match rate

    e_c_b_Loss_ind = eeprom_read(EEPROM_ADDITIONAL_INDICATION);
    e_c_tenths_Fid_loss = Bcd2Dec(eeprom_read(EEPROM_FEEDER_LOSS));
    e_c_b_Relay_off = Bcd2Dec(eeprom_read(EEPROM_DISABLE_RELAYS));
    CLRWDT();
    return;
}

void show_loss(void) {
    json_start();
    json_int("Loss", e_c_tenths_Fid_loss, 1);
    json_end();
    return;
}
