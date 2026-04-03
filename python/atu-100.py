#!/usr/bin/env python3
'''
ATU-100 control program

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
import sys

from curses import wrapper
from datetime import datetime
from enum import Enum
from time import sleep, time



# ncurses related

# Colours

C_GOOD_DATA  = 1
C_BAD_DATA   = 2
C_WARN_DATA  = 3
C_NOTE_DATA  = 4
C_COMPLETE   = 5
C_EMPTY_DATA = 6

# Screen locations

SCREEN_WIDTH  = 41
SCREEN_HEIGHT =  7

SDATA_FIRST        = 10
SDATA_FIRST_WIDTH  =  7
SDATA_SECOND       = 35
SDATA_SECOND_WIDTH = 10

AUTO_R    = 4
AUTO_C    = SDATA_FIRST
AUTO_W    = 8

BYPASS_R  = 4
BYPASS_C  = SDATA_SECOND
BYPASS_W  =8

STATE_R     = 2
STATE_C     = SDATA_FIRST
STATE_W     = SDATA_FIRST_WIDTH + 2

LEVEL_R     = 3
LEVEL_C     = SDATA_FIRST
LEVEL_W     = SDATA_FIRST_WIDTH

VOLTAGE_R   = 4
VOLTAGE_C   = SDATA_FIRST
VOLTAGE_W   = SDATA_FIRST_WIDTH

CURRENT_R   = 5
CURRENT_C   = SDATA_FIRST
CURRENT_W   = SDATA_FIRST_WIDTH

MAX_V_R     = 3
MAX_V_C     = SDATA_SECOND
MAX_V_W     = SDATA_SECOND_WIDTH

MIN_V_R     = 4
MIN_V_C     = SDATA_SECOND
MIN_V_W     = SDATA_SECOND_WIDTH

CAPACITY_R  = 5
CAPACITY_C  = SDATA_SECOND
CAPACITY_W  = SDATA_SECOND_WIDTH



class atu_100(object):
    def __init__(self):
        # JSON messages
        self.ser         = None
        self.json_active = False
        self.json_buffer = ''
        # Tuner state
        self.auto        = True
        self.bypass      = False
        self.power       = 0.0
        self.swr         = 0.0
        self.order       = 'LC'
        self.capacitance = 0
        self.inductance  = 0

        # Stuff in battery defintion file
        self.bat_percent  = 0.0 # Battery charge percentage NB: Use set_bat_percentage() to set to keep bat_volts in sync
        self.bat_min_v    = 0.0 # Battery minimum voltage
        self.bat_max_v    = 0.0 # Battery maximum charge
        self.bat_capacity = 0.0 # Battery capacity in Ah
        # Stuff not in battery defintion file
        self.bat_volts    = 0.0 # Battery voltage NB: Use set_bat_voltage() to set to keep bat_percent in sync
        self.bat_current  = 0.0 # Battery current, positive is charing, negative is discharging
        self.scpi_volts   = 0.0 # Last voltage sent to SCPI devices
        self.psu = None         # SCPI Power Supply
        self.dcl = None         # SCPI DC Load
        self.current_psu  = 0.0 # Current bing pulled from PSU
        self.current_dcl  = 0.0 # Current bing sunk into DCL
        self.state = 'Startup'  # Operating state of the battery
        self.state_start = datetime.now()

        # Get the command line args

        epilog_str = ("Keys to control program:\n"
                      " 'q' or ESC - exit\n"
                      " 'a'        - Toggle auto tunning\n"
                      " 'b'        - Toggle bypass\n"
                      " 'r'        - Reset tuner, C and L\n"
                      " 't'        - Force tuning\n"
        )
        parser = argparse.ArgumentParser(prog='atu-100',
                                         description='Control program for ATU-100 tuner',
                                         epilog=epilog_str,
                                         formatter_class=argparse.RawTextHelpFormatter)

        parse_general = parser.add_argument_group('General', 'General options')
        parse_general.add_argument('-p', '--port', default='/dev/ttyACM0', help = 'Serial port for ATU-100')
        parse_general.add_argument('--logfile', default='atu-100.log', help = 'Log filename (atu-100.log)')
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
        logging.info('=======================')
        logging.info('| Starting atu-100.py |')
        logging.info('=======================')

        # Open the serial port

        try:
            self.ser = serial.Serial(port = self.args.port,
                    baudrate = 4800,
                    bytesize=serial.EIGHTBITS,
                    stopbits = serial.STOPBITS_ONE,
                    parity = serial.PARITY_NONE,
                    timeout=0.1) # default timeout for reading in seconds
        # exit if the port is not opened
        except serial.SerialException as e:
            sys.exit(e)

        logging.info('Succefully to connect to ATU-100')

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
        curses.init_pair(C_NOTE_DATA,  curses.COLOR_BLUE,    curses.COLOR_BLACK)
        curses.init_pair(C_COMPLETE,   curses.COLOR_WHITE,   curses.COLOR_GREEN)
        curses.init_pair(C_EMPTY_DATA, curses.COLOR_WHITE,   curses.COLOR_BLACK)
        self.mwin.clear()
        self.mwin.nodelay(True)

        #  Create windows         Lines, Columns, Down, Across
        self.swin = curses.newwin(curses.LINES - 1, curses.COLS - 1, 0, 0)
#        self.swin = curses.newwin(SCREEN_HEIGHT, SCREEN_WIDTH, 0, 0)

        self.swin.border()
        self.swin.addstr(0, 2, ' ATU-100 ')

        # Render the static status text
        self.swin.addstr(1, 1, 'Power:      ---.- W  Order:             --')
        self.swin.addstr(2, 1, 'SWR:        -.---    Capacitance:    ----- pF')
        self.swin.addstr(3, 1, 'Reverse:    ---.- w  Inductance:     ----- nH')
        self.swin.addstr(4, 1, 'Auto:    --------    Bypass:      -------- ')

        self.mwin.noutrefresh()
        self.swin.noutrefresh()
        curses.doupdate()



    def update_var(self, var, value, attr = C_GOOD_DATA):
        width = SDATA_FIRST_WIDTH
        rjust = True
        if var == 'Auto':
            r = AUTO_R
            c = AUTO_C
            width = AUTO_W
            rjust = True

        elif var == 'Bypass':
            r = BYPASS_R
            c = BYPASS_C
            width = BYPASS_W
            rjust = True

        elif var == 'State':
            r = STATE_R
            c = STATE_C
            width = STATE_W
            rjust = False

        elif var == 'Level':
            r = LEVEL_R
            c = LEVEL_C
            width = LEVEL_W

        elif var == 'Voltage':
            r = VOLTAGE_R
            c = VOLTAGE_C
            width = VOLTAGE_W

        elif var == 'Current':
            r = CURRENT_R
            c = CURRENT_C
            width = CURRENT_W

        elif var == 'Max_V':
            r = MAX_V_R
            c = MAX_V_C
            width = MAX_V_W

        elif var == 'Min_V':
            r = MIN_V_R
            c = MIN_V_C
            width = MIN_V_W

        elif var == 'Capacity':
            r = CAPACITY_R
            c = CAPACITY_C
            width = CAPACITY_W

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


    def sendbool(self, name, value):
        if value:
            msg = f'{{"{name}": true}}\n'
        else:
            msg = f'{{"{name}": false}}\n'
        self.ser.write(msg.encode('ascii'))


    def getmsg(self):
        result = None
        rxd = self.ser.read()
        if not rxd:
            return None

        if self.json_active:
            while (rxd):
                ch = rxd.decode("utf-8")
                logging.debug(f'Got {ch}')
                self.json_buffer += ch
                if ch == '}':
                    logging.debug('JSON ended')
                    self.json_active = False
                    try:
                        result = json.loads( self.json_buffer)
                    except:
                        logging.warning(f'Invalid JSON reveived: [{self.json_buffer}]')
                    return result
                rxd = self.ser.read()
        else:
            while (rxd):
                ch = rxd.decode("utf-8")
                logging.debug(f'Wait {ch}')
                if ch == '{':
                    logging.debug('JSON started')
                    self.json_active = True
                    self.json_buffer = ch
                    return None
                rxd = self.ser.read()

        return None



    def main(self, stdscr):
        self.mwin = stdscr
        self.initlayout()

        # Get inital information from the tuner


        #
        # Loop processing key presses, send polls and update battery voltage etc
        #

        while True:
            loopstart = time()

            # Show how long we have been in current battery state

            # lapsed = datetime.now() - self.state_start
            # self.update_var('Lapsed', "%02d:%02d:%02d" % (lapsed.seconds // 3600, lapsed.seconds // 60 % 60, lapsed.seconds % 60))

            # Process key presses

            key = self.mwin.getch()
            if key == ord('q') or key == 27:   # 'q' or ESC - Quit program
                break

            elif key == ord('a'):
                self.update_var('Auto', '--------', C_EMPTY_DATA)
                self.auto = not self.auto
                logging.info(f'Auto -> {self.auto}')
                self.sendbool('Auto', self.auto)

            elif key == ord('b'):
                self.update_var('Bypass', '--------', C_EMPTY_DATA)
                self.bypass = not self.bypass
                logging.info(f'Bypass -> {self.bypass}')
                self.sendbool('Bypass', self.bypass)

            elif key != -1:                    # Not 'no key' - Show key usage
                 logging.warning(f'Unknown key: {key}')

            # Check for a new JSON message

            rxmsg = self.getmsg()
            if rxmsg:
                logging.debug(rxmsg)
                for name in rxmsg:
                    if name == 'Auto':
                        self.auto = rxmsg[name]
                        if rxmsg[name]:
                            self.update_var(name, 'Enabled')
                        else:
                            self.update_var(name, 'Disabled')
                    elif name == 'Bypass':
                        self.bypass = rxmsg[name]
                        if rxmsg[name]:
                            self.update_var(name, 'Enabled')
                        else:
                            self.update_var(name, 'Disabled')
                    else:
                        logging.info(f'Ignored {name} = {rxmsg[name]}')

            # Update information on screen

            # self.update_var('Level', f'{self.bat_percent:.1f}') 
            # self.update_var('Voltage', f'{self.bat_volts:.3f}')
            # self.update_var('Current', f'{self.bat_current:.4f}', attr=current_colour) 

            self.mwin.noutrefresh()
            curses.doupdate()

            # Wait for short time to not waste CPU

#            sleep(0.1)

        # Clean up and exit

        logging.info('Exiting')




if __name__ == "__main__":
    atu = atu_100()
    wrapper(atu.main)
    exit(0)