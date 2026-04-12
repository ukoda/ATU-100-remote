#!/usr/bin/env python3
'''
ATU-100 diagnostic program

This program is intended for diagnostics and setup of a remote ATU-100.

The AUT-100 needs to be programmed with the hex file from
https://github.com/ukoda/ATU-100-remote and the 3V TTL serial lines to wire to
the board to allow comms with this program.

This allows the excahnage of JSON format messages to control the ATU-100 and
show it's status.  The format of the JSON messages is documented in the file
https://github.com/ukoda/ATU-100-remote/blob/master/README.md
'''

import argparse
import curses
import datetime
import json
import logging
import serial.tools.list_ports
import string
import sys
import atu100

from atu100 import cell
from curses import wrapper
from datetime import datetime
from enum import Enum
from time import sleep, time


# Process state

class ProcessState:
    PS_IDLE        = 0
    PS_NEED_STATUS = 1
    PS_WAIT_STATUS = 2
    PS_GOT_STATUS  = 3
    PS_NEED_EEPROM = 4
    PS_WAIT_EEPROM = 5
    PS_GOT_EEPROM  = 6

# ncurses related

# Colours

C_GOOD_DATA  = 1
C_BAD_DATA   = 2
C_WARN_DATA  = 3
C_NOTE_DATA  = 4
C_EDIT_DATA  = 5
C_EMPTY_DATA = 6


# Screen locations

# Status window

STAT_WIN_WIDTH  = 48
STAT_WIN_HEIGHT =  7
STAT_WIN_DOWN   =  0
STAT_WIN_ACROSS =  0

SDATA_FIRST        = 10
SDATA_FIRST_WIDTH  =  8
SDATA_SECOND       = 35
SDATA_SECOND_WIDTH =  8

POWER_R     = 1
POWER_C     = SDATA_FIRST

SWR_R       = 2
SWR_C       = SDATA_FIRST

REVERSE_R   = 3
REVERSE_C   = SDATA_FIRST

AUTO_R      = 4
AUTO_C      = SDATA_FIRST

EVENT_R     = 5
EVENT_C     = SDATA_FIRST

ORDER_R     = 1
ORDER_C     = SDATA_SECOND

CAP_R       = 2
CAP_C       = SDATA_SECOND

IND_R       = 3
IND_C       = SDATA_SECOND

BYPASS_R    = 4
BYPASS_C    = SDATA_SECOND

TUNE_R      = 5
TUNE_C      = SDATA_SECOND

# EEPROM window

EEPROM_WIN_WIDTH  = 53
EEPROM_WIN_HEIGHT = 20
EEPROM_WIN_DOWN   =  0
EEPROM_WIN_ACROSS = STAT_WIN_WIDTH

# Config window

CONFIG_WIN_WIDTH  = STAT_WIN_WIDTH
CONFIG_WIN_HEIGHT = EEPROM_WIN_HEIGHT - STAT_WIN_HEIGHT
CONFIG_WIN_DOWN   = STAT_WIN_HEIGHT
CONFIG_WIN_ACROSS = 0
CONFIG_FIRST      = 1
CONFIG_FIRSTD     = CONFIG_FIRST + 4
CONFIG_SECOND     = 24
CONFIG_SECONDD    = CONFIG_SECOND + 4

class atu100diag(object):
    def __init__(self):
        self.atu = atu100.atu100()
        self.process_state = ProcessState.PS_IDLE
        self.edit_mode = False
        self.edit_address = 3
        self.edit_value = 0xff
        self.control_capacitor = False
        self.control_inductor = False

        # Get the command line args

        epilog_str = ("Keys to control program:\n"
                      " 'q' or ESC - exit\n"
                      " 'a'        - Toggle auto tunning\n"
                      " 'b'        - Toggle bypass\n"
                      " 'c'        - Toggle capacitor relay\n"
                      " 'l'        - Toggle inductor relay\n"
                      " 'o'        - Toggle capacitior order\n"
                      " 'r'        - Reset tuner, C and L\n"
                      " 'T'        - Force tuning\n"
                      " 'X'        - Force board restart\n"
                      " '0' to '6' - Relay to toggle\n"
        )
        parser = argparse.ArgumentParser(prog='atu-100 diagnostics',
                                         description='Diagnostics program for ATU-100 tuner',
                                         epilog=epilog_str,
                                         formatter_class=argparse.RawTextHelpFormatter)

        parse_general = parser.add_argument_group('General', 'General options')
        parse_general.add_argument('-p', '--port', default='/dev/ttyACM0', help = 'Serial port for ATU-100')
        parse_general.add_argument('--logfile', default='atu100.log', help = 'Log filename (atu100.log)')
        parse_general.add_argument('--log-level', type=str,
                                    dest='log_level', default='info',
                                    choices=['debug', 'info', 'warn', 'error', 'critical'],
                                    help='Log level: debug|info(default)|warn|error|critical')
        parse_general.add_argument('--newlog', default=False, action='store_true', help = 'Create a new log file')

        self.args = parser.parse_args()

        # Set up logging

        FORMAT = '%(asctime)-15s %(levelname)s %(message)s'
        if self.args.newlog:
            filemode = 'w'
        else:
            filemode = 'a'
        logging.basicConfig(level=logging.getLevelName(self.args.log_level.upper()), format=FORMAT, filename=self.args.logfile, filemode=filemode)
        logging.info('=================================')
        logging.info('| Starting atu100diagnostics.py |')
        logging.info('=================================')

        # Open the serial port

        try:
            self.atu.connect(self.args.port)
        # exit if the port is not opened
        except serial.SerialException as e:
            sys.exit(e)

        # Load the JSON files

        # try:
        #     with open(self.args.scpidev) as json_file:
        #         self.scpi_devices = json.load(json_file)
        # except:
        #     logging.error(f"Can't read {self.args.scpidev} SCPI devices file")
        #     print(f"Can't read {self.args.scpidev} SCPI devices file.  Use find_devices.py to create it if missing")
        #     exit(10)





    def initlayout(self):
        # Set up the ncurses style window

        curses.curs_set(False)
        curses.init_color(curses.COLOR_BLACK, 0, 0, 0)
        curses.init_pair(C_GOOD_DATA,  curses.COLOR_GREEN,   curses.COLOR_BLACK)
        curses.init_pair(C_BAD_DATA,   curses.COLOR_WHITE,   curses.COLOR_RED)
        curses.init_pair(C_WARN_DATA,  curses.COLOR_MAGENTA, curses.COLOR_BLACK)
        curses.init_pair(C_NOTE_DATA,  curses.COLOR_BLACK,   curses.COLOR_GREEN)
        curses.init_pair(C_EDIT_DATA,  curses.COLOR_WHITE,   curses.COLOR_BLUE)
        curses.init_pair(C_EMPTY_DATA, curses.COLOR_WHITE,   curses.COLOR_BLACK)
        self.mwin.clear()
        self.mwin.nodelay(True)

        # Create windows

        # Status window

        #          Lines, Columns, Down, Across
        self.swin = curses.newwin(STAT_WIN_HEIGHT, STAT_WIN_WIDTH, STAT_WIN_DOWN, STAT_WIN_ACROSS)

        self.swin.border()
        self.swin.addstr(0, 2, ' ATU-100 Status ')

        # Render the static status text
        self.swin.addstr(1, 1, 'Power:      ---.- W  Order:             --')
        self.swin.addstr(2, 1, 'SWR:         -.--    Capacitance:    ----- pF')
        self.swin.addstr(3, 1, 'Reverse:    ---.- w  Inductance:     ----- nH')
        self.swin.addstr(4, 1, 'Auto:    --------    Bypass:      -------- ')
        self.swin.addstr(5, 1, 'Event:               Tune:')

        # EEPROM window

        self.ewin = curses.newwin(EEPROM_WIN_HEIGHT, EEPROM_WIN_WIDTH, EEPROM_WIN_DOWN, EEPROM_WIN_ACROSS)
        self.ewin.border()
        self.ewin.addstr(0, 2, ' EEPROM data ')
        # Render the static status text
        self.ewin.addstr(1, 1, 'Add -0 -1 -2 -3 -4 -5 -6 -7 -8 -9 -a -b -c -d -e -f')
        self.ewin.addstr(2, 1, '---------------------------------------------------')
        for line in range(16):
           self.ewin.addstr(3 + line, 1, f'{line:x}-  -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --')

        # Config window

        self.cwin = curses.newwin(CONFIG_WIN_HEIGHT, CONFIG_WIN_WIDTH, CONFIG_WIN_DOWN, CONFIG_WIN_ACROSS)
        self.cwin.border()
        self.cwin.addstr(0, 2, ' Configuration ')

        # Final screen set up

        self.mwin.noutrefresh()
        self.swin.noutrefresh()
        self.ewin.noutrefresh()
        self.cwin.noutrefresh()
        curses.doupdate()


    def update_var(self, var, value, attr = C_GOOD_DATA):
        width = SDATA_FIRST_WIDTH
        rjust = True
        if var == 'Power':
            r = POWER_R
            c = POWER_C

        elif var == 'SWR':
            r = SWR_R
            c = SWR_C

        elif var == 'Reverse':
            r = REVERSE_R
            c = REVERSE_C

        elif var == 'Auto':
            r = AUTO_R
            c = AUTO_C

        elif var == 'Event':
            r = EVENT_R
            c = EVENT_C

        elif var == 'Order':
            r = ORDER_R
            c = ORDER_C

        elif var == 'Capacitance':
            r = CAP_R
            c = CAP_C

        elif var == 'Inductance':
            r = IND_R
            c = IND_C

        elif var == 'Bypass':
            r = BYPASS_R
            c = BYPASS_C

        elif var == 'Tune':
            r = TUNE_R
            c = TUNE_C

        else:
            self.show_error(f'Uknown var {var} with value {value}')
            return

        try:
            if rjust:
                self.swin.addnstr(r, c, value.rjust(width), width, curses.color_pair(attr))
            else:
                self.swin.addnstr(r, c, value.ljust(width), width, curses.color_pair(attr))
        except:
            pass
        self.swin.noutrefresh()


    def toggle_auto(self):
        self.update_var('Auto', '--------', C_EMPTY_DATA)
        self.atu.toggle_auto()


    def toggle_bypass(self):
        self.update_var('Bypass', '--------', C_EMPTY_DATA)
        self.atu.toggle_bypass()


    def start_tune(self):
        self.update_var('Tune', 'Started') 
        self.atu.start_tune()


    def process_status_msg(self, rxmsg):
        for name in rxmsg:
            if name == 'Auto':
                self.atu.auto = rxmsg[name]
                if rxmsg[name]:
                    self.update_var(name, 'Enabled')
                else:
                    self.update_var(name, 'Disabled')

            elif name == 'Bypass':
                self.atu.bypass = rxmsg[name]
                if rxmsg[name]:
                    self.update_var(name, 'Enabled')
                else:
                    self.update_var(name, 'Disabled')

            elif name == 'Power':
                self.atu.power = rxmsg[name]
                self.update_var(name, f'{self.atu.power:.1f}') 

            elif name == 'SWR':
                self.atu.swr = rxmsg[name]
                self.update_var(name, f'{self.atu.swr:.1f}') 

            elif name == 'Reverse':
                self.atu.reverse = rxmsg[name]
                self.update_var(name, f'{self.atu.reverse:.1f}') 

            elif name == 'Event':
                self.update_var(name, rxmsg[name]) 

            elif name == 'Order':
                self.atu.order = rxmsg[name]
                self.update_var(name, f'{self.atu.order}') 

            elif name == 'Capacitance':
                self.atu.capacitance = rxmsg[name]
                self.update_var(name, f'{self.atu.capacitance}') 

            elif name == 'Inductance':
                self.atu.inductance = rxmsg[name]
                self.update_var(name, f'{self.atu.inductance}') 

            else:
                logging.info(f'Ignored {name} = {rxmsg[name]}')

        self.mwin.noutrefresh()
        curses.doupdate()
        if self.process_state == ProcessState.PS_WAIT_STATUS:
            self.process_state = ProcessState.PS_GOT_STATUS


    def show_eeprom(self):
        for address in range(0x100):
            value = self.atu.eeprom[address]
            row = 3 + int(address // 16)
            col = 5 + (address % 16) * 3
            if self.edit_mode and (address == self.edit_address):
                attr = C_EDIT_DATA
            elif address <= cell.EEPROM_DISPLAY_TYPE:
                attr = C_WARN_DATA
            elif address <= cell.EEPROM_MAX_POWER:
                attr = C_GOOD_DATA
            elif address < cell.EEPROM_MAX_INIT_SWR:
                attr = C_WARN_DATA
            elif address <= cell.EEPROM_INDUCTOR_LAST:
                attr = C_GOOD_DATA
            elif address < cell.EEPROM_CAPACITOR_FIRST:
                attr = C_EMPTY_DATA
            elif address <= cell.EEPROM_CAPACITOR_LAST:
                attr = C_GOOD_DATA
            elif address < cell.EEPROM_POWER_MEASURE_LEVEL:
                attr = C_EMPTY_DATA
            elif address <= cell.EEPROM_TANDEM_MATCH:
                attr = C_GOOD_DATA
            elif address < cell.EEPROM_ADDITIONAL_INDICATION:
                attr = C_WARN_DATA
            elif address <= cell.EEPROM_DISABLE_RELAYS:
                attr = C_GOOD_DATA
            elif address >= cell.EEPROM_LAST_SWR_L:
                attr = C_GOOD_DATA
            elif value == 0xff:
                attr = C_EMPTY_DATA
            else:
                attr = C_BAD_DATA
            self.ewin.addnstr(row, col, f'{value:02x}', 2, curses.color_pair(attr))
        self.ewin.noutrefresh()
        self.mwin.noutrefresh()
        curses.doupdate()


    def check_bcd(self, bcd):
        tens = bcd // 16
        units = bcd & 0xf
        return (tens <= 9) and (units <= 9)


    def show_configuration(self, log):
        address = cell.EEPROM_TIMEOUT_TIME
        value = self.atu.eeprom[address]
        attr = C_GOOD_DATA
        if self.check_bcd(value):
            bcd = self.atu.get_bcd(value)
            valstr = f'Timeout {bcd} mS  '
        else:
            attr = C_BAD_DATA
            valstr = 'Invalid timeout'
        if log:
            logging.info(valstr)
        row = 3
        self.cwin.addstr(row, CONFIG_FIRST, f'{address:02x}:')
        self.cwin.addstr(row, CONFIG_FIRSTD, valstr, curses.color_pair(attr))

        address = cell.EEPROM_SWR_THRESHOLD
        value = self.atu.eeprom[address]
        attr = C_GOOD_DATA
        if self.check_bcd(value):
            dec = value // 16
            frac = value & 0xf
            valstr = f'Auto SWR thres {dec}.{frac}'
        else:
            attr = C_BAD_DATA
            valstr = 'Invalid SWR       '
        if log:
            logging.info(valstr)
        self.cwin.addstr(row, CONFIG_SECOND, f'{address:02x}:')
        self.cwin.addstr(row, CONFIG_SECONDD, valstr, curses.color_pair(attr))

        address = cell.EEPROM_MIN_POWER
        value = self.atu.eeprom[address]
        attr = C_GOOD_DATA
        if self.check_bcd(value):
            bcd = self.atu.get_bcd(value)
            if self.atu.eeprom[cell.EEPROM_POWER_MEASURE_LEVEL] == 1:
                bcd *= 10
            valstr = f'Minimum power {bcd:>2} W'
        else:
            attr = C_BAD_DATA
            valstr = 'Invalid min power '
        if log:
            logging.info(valstr)
        row += 1
        self.cwin.addstr(row, CONFIG_FIRST, f'{address:02x}:')
        self.cwin.addstr(row, CONFIG_FIRSTD, valstr, curses.color_pair(attr))

        address = cell.EEPROM_MAX_POWER
        value = self.atu.eeprom[address]
        attr = C_GOOD_DATA
        if value == 0:
            valstr = 'No maximum power'
        else:
            if self.check_bcd(value):
                bcd = self.atu.get_bcd(value)
                if self.atu.eeprom[cell.EEPROM_POWER_MEASURE_LEVEL] == 1:
                    bcd *= 10
                valstr = f'Maximum power {bcd:>2} W'
            else:
                attr = C_BAD_DATA
                valstr = 'Invalid min power'
        if log:
            logging.info(valstr)
        self.cwin.addstr(row, CONFIG_SECOND, f'{address:02x}:')
        self.cwin.addstr(row, CONFIG_SECONDD, valstr, curses.color_pair(attr))

        address = cell.EEPROM_MAX_INIT_SWR
        value = self.atu.eeprom[address]
        attr = C_GOOD_DATA
        if value == 0:
            valstr = 'No max initial SWR'
        else:
            if self.check_bcd(value):
                dec = value // 16
                frac = value & 0xf
                valstr = f'Max init SWR {dec}.{frac}  '
            else:
                attr = C_BAD_DATA
                valstr = 'Invalid SWR       '
        if log:
            logging.info(valstr)
        row += 1
        self.cwin.addstr(row, CONFIG_FIRST, f'{address:02x}:')
        self.cwin.addstr(row, CONFIG_FIRSTD, valstr, curses.color_pair(attr))

        address = cell.EEPROM_NUMBER_INDS
        value = self.atu.eeprom[address]
        iattr = C_GOOD_DATA
        if (value < 5) or (value > 7):
            iattr = C_BAD_DATA
            num_inductors = 0
            if log:
                logging.warning(f'{address:02x}: Number of inductors invalid')
        else:
            num_inductors = value
            if log:
                logging.info(f'{address:02x}: Number of inductors {value}')

        address = cell.EEPROM_IND_LINEAR_PITCH
        value = self.atu.eeprom[address]
        linear_inds = False
        if value == 0:
            if log:
                logging.info(f'{address:02x}: Inductors not linear pitch')
        elif value == 1:
            linear_inds = True
            num_inductors = 0
            if log:
                logging.info(f'{address:02x}: Inductors linear pitch')
        else:
            iattr = C_BAD_DATA
            num_inductors = 0
            if log:
                logging.warning(f'{address:02x}: Inductors pitch invalid')

        address = cell.EEPROM_NUMBER_CAPS
        value = self.atu.eeprom[address]
        cattr = C_GOOD_DATA
        if (value < 5) or (value > 7):
            cattr = C_BAD_DATA
            num_capacitors = 0
            if log:
                logging.warning(f'{address:02x}: Number of capacitors invalid')
        else:
            num_capacitors = value
            if log:
                logging.info(f'{address:02x}: Number of capacitors {value}')

        address = cell.EEPROM_CAP_LINEAR_PITCH
        value = self.atu.eeprom[address]
        linear_caps = False
        if value == 0:
            if log:
                logging.info(f'{address:02x}: Capacitors not linear pitch')
        elif value == 1:
            linear_caps = True
            num_capacitors = 0
            if log:
                logging.info(f'{address:02x}: Capacitors linear pitch')
        else:
            cattr = C_BAD_DATA
            num_capacitors = 0
            if log:
                logging.warning(f'{address:02x}: Capacitors pitch invalid')

        address = cell.EEPROM_ENABLE_NONLINEAR_DIODE
        value = self.atu.eeprom[address]
        attr = C_GOOD_DATA
        if value == 0:
            valstr = 'No linear correct'
        elif value == 1:
            valstr = 'Linearity correct'
        else:
            attr =C_BAD_DATA
            valstr = 'Invalid linear   '
        if log:
            logging.info(valstr)
        self.cwin.addstr(row, CONFIG_SECOND, f'{address:02x}:')
        self.cwin.addstr(row, CONFIG_SECONDD, valstr, curses.color_pair(attr))

        address = cell.EEPROM_INVERSE_INDUCTANCE_RELAY
        value = self.atu.eeprom[address]
        attr = C_GOOD_DATA
        if value == 0:
            valstr = 'Normal ind relays '
        elif value == 1:
            valstr = 'Inverse ind relays'
        else:
            attr =C_BAD_DATA
            valstr = 'Invalid ind relays'
        if log:
            logging.info(valstr)
        row += 1
        self.cwin.addstr(row, CONFIG_FIRST, f'{address:02x}:')
        self.cwin.addstr(row, CONFIG_FIRSTD, valstr, curses.color_pair(attr))

        if num_inductors > 0:
            if self.control_inductor:
                attr = C_WARN_DATA
            else:
                attr = C_EMPTY_DATA
            self.cwin.addstr(1, 1, 'Inds (nH): ', curses.color_pair(attr))
            for relay in range(num_inductors):
                valstr = f'{self.atu.value_ind[relay]:>4}'
                attr = iattr
                if (iattr == C_GOOD_DATA) and self.atu.relay_ind[relay]:
                    attr = C_NOTE_DATA
                self.cwin.addstr(1, 12 + relay * 5, valstr, curses.color_pair(attr))
                if log:
                    logging.info(f'Inductor {relay} is {valstr} nH')

        elif linear_inds:
            self.cwin.addstr(1, 1, 'Linear spacing of inductors                  ', curses.color_pair(C_GOOD_DATA))
        else:
            self.cwin.addstr(1, 1, 'Invalid number of inductors or spacing       ', curses.color_pair(C_BAD_DATA))

        if num_capacitors > 0:
            if self.control_capacitor:
                attr = C_WARN_DATA
            else:
                attr = C_EMPTY_DATA
            self.cwin.addstr(2, 1, 'Caps (pf): ', curses.color_pair(attr))
            for relay in range(num_inductors):
                valstr = f'{self.atu.value_cap[relay]:>4}'
                attr = iattr
                if (iattr == C_GOOD_DATA) and self.atu.relay_cap[relay]:
                    attr = C_NOTE_DATA
                self.cwin.addstr(2, 12 + relay * 5, valstr, curses.color_pair(attr))
                if log:
                    logging.info(f'Capacitor {relay} is {valstr} pF')

        elif linear_caps:
            self.cwin.addstr(2, 1, 'Linear spacing of capacitors                 ', curses.color_pair(C_GOOD_DATA))
        else:
            self.cwin.addstr(2, 1, 'Invalid number of capacitors or spacing      ', curses.color_pair(C_BAD_DATA))

        address = cell.EEPROM_POWER_MEASURE_LEVEL
        value = self.atu.eeprom[address]
        attr = C_GOOD_DATA
        if value == 0:
            valstr = 'Measure to 999 W '
        elif value == 1:
            valstr = 'Measure to 9999 W'
        else:
            attr = C_BAD_DATA
            valstr = 'Invalid range    '
        if log:
            logging.info(valstr)
        self.cwin.addstr(row, CONFIG_SECOND, f'{address:02x}:')
        self.cwin.addstr(row, CONFIG_SECONDD, valstr, curses.color_pair(attr))

        address = cell.EEPROM_TANDEM_MATCH
        value = self.atu.eeprom[address]
        attr = C_GOOD_DATA
        if self.check_bcd(value):
            bcd = self.atu.get_bcd(value)
            valstr = f'Tandum match 1:{bcd}  '
        else:
            attr = C_BAD_DATA
            valstr = 'Invalid tandum match'
        if log:
            logging.info(valstr)
        row += 1
        self.cwin.addstr(row, CONFIG_FIRST, f'{address:02x}:')
        self.cwin.addstr(row, CONFIG_FIRSTD, valstr, curses.color_pair(attr))

        address = cell.EEPROM_ADDITIONAL_INDICATION
        value = self.atu.eeprom[address]
        attr = C_GOOD_DATA
        if value == 0:
            valstr = 'LC indication only '
        elif value == 1:
            valstr = 'Efficeny indication'
        else:
            attr = C_BAD_DATA
            valstr = 'Invalid indication '
        if log:
            logging.info(valstr)
        self.cwin.addstr(row, CONFIG_SECOND, f'{address:02x}:')
        self.cwin.addstr(row, CONFIG_SECONDD, valstr, curses.color_pair(attr))

        address = cell.EEPROM_FEEDER_LOSS
        value = self.atu.eeprom[address]
        attr = C_GOOD_DATA
        if value == 0:
            valstr = 'Feed loss ignored'
        else:
            if self.check_bcd(value):
                dec = value // 16
                frac = value & 0xf
                valstr = f'Feed loss 1:{dec}.{frac}  '
            else:
                attr = C_BAD_DATA
                valstr = 'Invalid feed loss'
        if log:
            logging.info(valstr)
        row += 1
        self.cwin.addstr(row, CONFIG_FIRST, f'{address:02x}:')
        self.cwin.addstr(row, CONFIG_FIRSTD, valstr, curses.color_pair(attr))

        address = cell.EEPROM_DISABLE_RELAYS
        value = self.atu.eeprom[address]
        valstr = f'Disable relays {value}'
        if log:
            logging.info(valstr)
        self.cwin.addstr(row, CONFIG_SECOND, f'{address:02x}:')
        self.cwin.addstr(row, CONFIG_SECONDD, valstr, curses.color_pair(C_GOOD_DATA))


        address = cell.EEPROM_LAST_SWR_L
        valuelow = self.atu.eeprom[address]
        valuehi = self.atu.eeprom[address+1]
        valstr = f'Last SWR {valuehi}:{valuelow}'
        if log:
            logging.info(valstr)
        row += 2
        self.cwin.addstr(row, CONFIG_FIRST, f'{address:02x}:')
        self.cwin.addstr(row, CONFIG_FIRSTD, valstr, curses.color_pair(C_GOOD_DATA))

        address = cell.EEPROM_LAST_SW
        value = self.atu.eeprom[address]
        valstr = f'Last SW {value}'
        if log:
            logging.info(valstr)
        self.cwin.addstr(row, CONFIG_SECOND, f'{address:02x}:')
        self.cwin.addstr(row, CONFIG_SECONDD, valstr, curses.color_pair(C_GOOD_DATA))

        address = cell.EEPROM_LAST_IND
        value = self.atu.eeprom[address]
        valstr = f'Last inductor {value}'
        if log:
            logging.info(valstr)
        row += 1
        self.cwin.addstr(row, CONFIG_FIRST, f'{address:02x}:')
        self.cwin.addstr(row, CONFIG_FIRSTD, valstr, curses.color_pair(C_GOOD_DATA))

        address = cell.EEPROM_LAST_CAP
        value = self.atu.eeprom[address]
        valstr = f'Last capacitor {value}'
        if log:
            logging.info(valstr)
        self.cwin.addstr(row, CONFIG_SECOND, f'{address:02x}:')
        self.cwin.addstr(row, CONFIG_SECONDD, valstr, curses.color_pair(C_GOOD_DATA))

        self.cwin.noutrefresh()
        self.mwin.noutrefresh()
        curses.doupdate()


    def process_eeprom_msg(self, rxmsg):
        # for name in rxmsg:
        #     address = int(name, 16)
        #     self.atu.eeprom[address] = int(rxmsg[name], 16)
        self.show_eeprom()
        self.show_configuration(True)
        self.process_state = ProcessState.PS_GOT_EEPROM


    def process_normal_key(self, key):
        if key == ord('a'):
            self.toggle_auto()

        elif key == ord('b'):
            self.toggle_bypass()

        elif key == ord('r'):
            logging.info('Requesting reset')
            self.atu.sendbool('Reset', True)

        elif key == ord('s'):
            logging.info('Requesting status')
            self.update_var('Auto', '--------', C_EMPTY_DATA)
            self.update_var('Bypass', '--------', C_EMPTY_DATA)
            self.update_var('Event', ' ') 
            self.atu.sendbool('Status', True)
            self.process_state = ProcessState.PS_WAIT_STATUS

        elif key == ord('T'):
            self.start_tune()

        elif key == ord('X'):
            self.atu.send_restart()

        elif key == ord('e'):
            self.edit_mode = True
            self.edit_value = self.atu.eeprom[self.edit_address]
            self.show_eeprom()

        elif key == ord('c'):
            self.control_capacitor = not self.control_capacitor
            self.control_inductor = False
            self.show_configuration(False)

        elif key == ord('l'):
            self.control_inductor = not self.control_inductor
            self.control_capacitor = False
            self.show_configuration(False)

        elif key == ord('o'):
            self.atu.relay_order = not self.atu.relay_order
            self.atu.send_relay_capacitors()

        elif key >= ord('0') and key <= ord('6'):
            relay = key - ord('0')
            if self.control_capacitor:
                self.atu.relay_cap[relay] = not self.atu.relay_cap[relay] 
                logging.info(f'Capacitor relay {relay} now {self.atu.relay_cap[relay]}')
                self.atu.send_relay_capacitors()
                self.show_configuration(False)

            elif self.control_inductor:
                self.atu.relay_ind[relay] = not self.atu.relay_ind[relay]
                logging.info(f'Inductor relay {relay} now {self.atu.relay_ind[relay]}')
                self.atu.send_relay_inductors()
                self.show_configuration(False)

        elif key != -1:                    # Not 'no key' - Show key usage
            logging.warning(f'Unknown normal key: {key}')


    def update_cell(self):
        if self.edit_value != self.atu.eeprom[self.edit_address]:
            logging.info(f'Cell {self.edit_address:02x}: {self.edit_value:02x} -> {self.atu.eeprom[self.edit_address]:02x}')
            self.atu.seteepromdata(self.edit_address, self.atu.eeprom[self.edit_address])
        else:
            logging.info(f'Cell {self.edit_address:02x}: unchanged as {self.edit_value:02x}')


    def process_edit_key(self, key):
        current_address = self.edit_address

        if key == 10:
            self.update_cell()
            self.edit_mode = False

        elif key == 260:    # Left arrow
            self.update_cell()
            self.edit_address -= 1
            if self.edit_address < 0:
                self.edit_address = 255

        elif key == 261:    # Right arrow
            self.update_cell()
            self.edit_address += 1
            if self.edit_address > 255:
                self.edit_address = 0

        elif key == 259:    # Up arrow
            self.update_cell()
            self.edit_address -= 16
            if self.edit_address < 0:
                self.edit_address += 256

        elif key == 258:    # Down arrow
            self.update_cell()
            self.edit_address += 16
            if self.edit_address > 255:
                self.edit_address -= 256

        elif key == 262:    # Home
            self.update_cell()
            self.edit_address &= 0xf0

        elif key == 360:    # End
            self.update_cell()
            self.edit_address &= 0xf0
            self.edit_address += 0x0f

        elif key == 339:    # Page up
            self.update_cell()
            self.edit_address &= 0x0f

        elif key == 338:    # Page down
            self.update_cell()
            self.edit_address &= 0x0f
            self.edit_address += 0xf0

        elif (key >= ord('0')) and (key <= ord('9')):
            nibble = key - ord('0')
            cell = self.atu.eeprom[self.edit_address]
            cell = (cell << 4) & 0xf0   # Move low nibble to high nibble
            cell += nibble
            self.atu.eeprom[self.edit_address] = cell

        elif (key >= ord('a')) and (key <= ord('f')):
            nibble = key - ord('a') + 10
            cell = self.atu.eeprom[self.edit_address]
            cell = (cell << 4) & 0xf0   # Move low nibble to high nibble
            cell += nibble
            self.atu.eeprom[self.edit_address] = cell

        elif (key >= ord('A')) and (key <= ord('F')):
            nibble = key - ord('A') + 10
            cell = self.atu.eeprom[self.edit_address]
            cell = (cell << 4) & 0xf0   # Move low nibble to high nibble
            cell += nibble
            self.atu.eeprom[self.edit_address] = cell

        elif key != -1:                    # Not 'no key' - Show key usage
            logging.warning(f'Unknown edit key: {key}')

        if key != -1:                      # Not 'no key' - Refesh
            if self.edit_address < 0:
                self.edit_address = 0
            if self.edit_address > 255:
                self.edit_address = 255
            self.show_eeprom()
            self.show_configuration(False)
            if current_address != self.edit_address:
                self.edit_value = self.atu.eeprom[self.edit_address]


    def process_double_click(self, x, y):

        # Auto tune toggle

        if x > 0 and x < 21 and y == AUTO_R:
            self.toggle_auto()

        # Bypass toggle

        elif x > 21 and x < 47 and y == BYPASS_R:
            self.toggle_bypass()

        # Start tune

        # elif x > 21 and x < 47 and y == TUNE_R:
        #     logging.info(f'Tuning started by double click at {x}, {y}')
        #     self.start_tune()

        # Toggle capacitor order

        elif x > 40 and x <43 and y == ORDER_R:
            self.atu.relay_order = not self.atu.relay_order
            self.atu.send_relay_capacitors()

        # Toggle inductor

        elif x > 10 and x < 46 and y == 8:
            relay = (x - 11) // 5
            self.atu.relay_ind[relay] = not self.atu.relay_ind[relay]
            logging.info(f'Inductor relay {relay} now {self.atu.relay_ind[relay]}')
            self.atu.send_relay_inductors()
            self.show_configuration(False)

        # Toggle capacitor

        elif x > 10 and x < 46 and y == 9:
            relay = (x - 11) // 5
            self.atu.relay_cap[relay] = not self.atu.relay_cap[relay] 
            logging.info(f'Capacitor relay {relay} now {self.atu.relay_cap[relay]}')
            self.atu.send_relay_capacitors()
            self.show_configuration(False)

        # Not a valid place to double click

        else:
            logging.info(f'Ignoring double click at {x}, {y}')


    def main(self, stdscr):
        self.mwin = stdscr
        self.initlayout()

        # Enable mouse events

        curses.mousemask(curses.ALL_MOUSE_EVENTS)
        print('\033[?1003h')

        # Get inital information from the tuner

        self.process_state = ProcessState.PS_NEED_STATUS

        #
        # Loop processing key presses, send polls and update battery voltage etc
        #

        while True:

            # Process key presses

            key = self.mwin.getch()
            if key == ord('q') or key == 27:   # 'q' or ESC - Quit program
                # Stop mouse events
                print('\033[?1003l')
                break

            elif key == curses.KEY_MOUSE:
                try:
                    event = curses.getmouse()
                    if event[4] == curses.BUTTON1_DOUBLE_CLICKED:
                        logging.debug(f'id {event[0]}, x {event[1]}, y {event[2]}, z {event[3]}')
                        self.process_double_click(event[1], event[2])
                except Exception as e:
                    logging.warning(f'Mouse error {e}')

            else:
                if self.edit_mode:
                    self.process_edit_key(key)
                else:
                    self.process_normal_key(key)

            # Check for a new JSON message

            rxmsg = self.atu.getmsg()
            if rxmsg:
                logging.debug(rxmsg)

                # Get the name and value of the first dictonary entry

                for name in rxmsg:
                    if name != '':
                        value = rxmsg[name]
                        break

                # Handle based on message type

                if 'Board' in rxmsg:
                    logging.info('Received info message')

                elif 'Power' in rxmsg:
                    logging.info('Received status message')
                    self.process_status_msg(rxmsg)

                elif '00' in rxmsg:
                    logging.info('Received eeprom dump message')
                    self.process_eeprom_msg(rxmsg)
                
                elif 'Event' in rxmsg:
                    logging.info(f'Received event message: {rxmsg["Event"]}')

                elif all(char in string.hexdigits for char in name):
                    cell_address = int(name, 16)
                    cell_data = int(value, 16)
                    if (cell_address < 0x100) and (cell_data < 0x100):
                        logging.info(f'Received cell update {cell_address:02x}: = {cell_data:02x}')
#                        self.atu.eeprom[cell_address] = cell_data

                else:
                    logging.warning(f'Received unknown message: {rxmsg}')

            # Process state

            match self.process_state:
                case ProcessState.PS_IDLE:
                    pass

                case ProcessState.PS_NEED_STATUS:
                    self.atu.sendbool('Status', True)
                    self.process_state = ProcessState.PS_WAIT_STATUS

                case ProcessState.PS_WAIT_STATUS:
                    pass

                case ProcessState.PS_GOT_STATUS:
                    self.process_state = ProcessState.PS_NEED_EEPROM

                case ProcessState.PS_NEED_EEPROM:
                    self.atu.sendstr('Dump', 'EEPROM')
                    self.ewin.border()
                    self.ewin.addstr(0, 2, ' EEPROM data - Fetching ')
                    self.ewin.noutrefresh()
                    curses.doupdate()
                    self.process_state = ProcessState.PS_WAIT_EEPROM

                case ProcessState.PS_WAIT_EEPROM:
                    pass

                case ProcessState.PS_GOT_EEPROM:
                    self.ewin.border()
                    self.ewin.addstr(0, 2, ' EEPROM data ')
                    self.ewin.noutrefresh()
                    curses.doupdate()
                    self.process_state = ProcessState.PS_IDLE

        # Clean up and exit

        logging.info('Exiting')




if __name__ == "__main__":
    atu = atu100diag()
    wrapper(atu.main)
    exit(0)