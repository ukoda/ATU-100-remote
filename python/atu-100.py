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

SCREEN_WIDTH  = 48
SCREEN_HEIGHT =  7

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
        self.reverse     = 0.0
        self.order       = 'LC'
        self.capacitance = 0
        self.inductance  = 0

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
#        self.swin = curses.newwin(curses.LINES - 1, curses.COLS - 1, 0, 0)
        self.swin = curses.newwin(SCREEN_HEIGHT, SCREEN_WIDTH, 0, 0)

        self.swin.border()
        self.swin.addstr(0, 2, ' ATU-100 ')

        # Render the static status text
        self.swin.addstr(1, 1, 'Power:      ---.- W  Order:             --')
        self.swin.addstr(2, 1, 'SWR:         -.--    Capacitance:    ----- pF')
        self.swin.addstr(3, 1, 'Reverse:    ---.- w  Inductance:     ----- nH')
        self.swin.addstr(4, 1, 'Auto:    --------    Bypass:      -------- ')
        self.swin.addstr(5, 1, 'Event:               Tune:')

        self.mwin.noutrefresh()
        self.swin.noutrefresh()
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


    def toggle_auto(self):
        self.update_var('Auto', '--------', C_EMPTY_DATA)
        self.auto = not self.auto
        logging.info(f'Auto -> {self.auto}')
        self.sendbool('Auto', self.auto)


    def toggle_bypass(self):
        self.update_var('Bypass', '--------', C_EMPTY_DATA)
        self.bypass = not self.bypass
        logging.info(f'Bypass -> {self.bypass}')
        self.sendbool('Bypass', self.bypass)


    def start_tune(self):
        logging.info('Requesting tune')
        self.update_var('Tune', 'Started') 
        self.sendbool('Tune', True)


    def main(self, stdscr):
        self.mwin = stdscr
        self.initlayout()

        # Enable mouse events

        curses.mousemask(curses.ALL_MOUSE_EVENTS)
        print('\033[?1003h')

        # Get inital information from the tuner

        self.sendbool('Status', True)

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
                        if event[1] < (SDATA_FIRST + SDATA_FIRST_WIDTH):
                            if event[2] == AUTO_R:
                                self.toggle_auto()
                        else:
                            if event[2] == BYPASS_R:
                                self.toggle_bypass()
                            elif event[2] == TUNE_R:
                                self.start_tune()
                except:
                    pass                                

            elif key == ord('a'):
                self.toggle_auto()

            elif key == ord('b'):
                self.toggle_bypass()

            elif key == ord('r'):
                logging.info('Requesting reset')
                self.sendbool('Reset', True)

            elif key == ord('s'):
                logging.info('Requesting status')
                self.update_var('Auto', '--------', C_EMPTY_DATA)
                self.update_var('Bypass', '--------', C_EMPTY_DATA)
                self.update_var('Event', ' ') 
                self.sendbool('Status', True)

            elif key == ord('t'):
                self.start_tune()

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

                    elif name == 'Power':
                        self.power = rxmsg[name]
                        self.update_var(name, f'{self.power:.1f}') 

                    elif name == 'SWR':
                        self.swr = rxmsg[name]
                        self.update_var(name, f'{self.swr:.1f}') 

                    elif name == 'Reverse':
                        self.reverse = rxmsg[name]
                        self.update_var(name, f'{self.reverse:.1f}') 

                    elif name == 'Event':
                        self.update_var(name, rxmsg[name]) 

                    elif name == 'Order':
                        self.order = rxmsg[name]
                        self.update_var(name, f'{self.order}') 

                    elif name == 'Capacitance':
                        self.capacitance = rxmsg[name]
                        self.update_var(name, f'{self.capacitance}') 

                    elif name == 'Inductance':
                        self.inductance = rxmsg[name]
                        self.update_var(name, f'{self.inductance}') 

                    else:
                        logging.info(f'Ignored {name} = {rxmsg[name]}')

            # Update information on screen

            # self.update_var('Level', f'{self.bat_percent:.1f}') 
            # self.update_var('Voltage', f'{self.bat_volts:.3f}')
            # self.update_var('Current', f'{self.bat_current:.4f}', attr=current_colour) 

            self.mwin.noutrefresh()
            curses.doupdate()


        # Clean up and exit

        logging.info('Exiting')




if __name__ == "__main__":
    atu = atu_100()
    wrapper(atu.main)
    exit(0)