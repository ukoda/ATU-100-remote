#!/usr/bin/env python3
'''
ATU-100 control program and library

When called as a program provides a simple traditional command line control
of a remote ATU-100.

The AUT-100 needs to be programmed with the hex file from
https://github.com/ukoda/ATU-100-remote and the 3V TTL serial lines to wire to
the board to allow comms with this program.

This allows the excahnage of JSON format messages to control the ATU-100 and
show it's status.  The format of the JSON messages is documented in the file
https://github.com/ukoda/ATU-100-remote/blob/master/README.md
'''

import argparse
import datetime
import json
import logging
import serial.tools.list_ports
import sys

from datetime import datetime
from enum import Enum
from time import sleep, time



class cell:
    EEPROM_DISPLAY_I2C_ADDR         = 0x00
    EEPROM_DISPLAY_TYPE             = 0x01
    EEPROM_AUTOMATIC_MODE           = 0x02
    EEPROM_TIMEOUT_TIME             = 0x03
    EEPROM_SWR_THRESHOLD            = 0x04
    EEPROM_MIN_POWER                = 0x05
    EEPROM_MAX_POWER                = 0x06
    EEPROM_DISPLAY_OFFSET_DOWN      = 0x07
    EEPROM_DISPLAY_OFFSET_LEFT      = 0x08
    EEPROM_MAX_INIT_SWR             = 0x09
    EEPROM_NUMBER_INDS              = 0x0a
    EEPROM_IND_LINEAR_PITCH         = 0x0b
    EEPROM_NUMBER_CAPS              = 0x0c
    EEPROM_CAP_LINEAR_PITCH         = 0x0d
    EEPROM_ENABLE_NONLINEAR_DIODE   = 0x0e
    EEPROM_INVERSE_INDUCTANCE_RELAY = 0x0f

    EEPROM_INDUCTOR_FIRST           = 0x10
    EEPROM_INDUCTOR_LAST            = 0x1D
    
    EEPROM_CAPACITOR_FIRST          = 0x20
    EEPROM_CAPACITOR_LAST           = 0x2D

    EEPROM_POWER_MEASURE_LEVEL      = 0x30
    EEPROM_TANDEM_MATCH             = 0x31
    EEPROM_DISPLAY_OFF_TIMER        = 0x32
    EEPROM_ADDITIONAL_INDICATION    = 0x33
    EEPROM_FEEDER_LOSS              = 0x34
    EEPROM_DISABLE_RELAYS           = 0x35

    EEPROM_LAST_SWR_L               = 0xfb
    EEPROM_LAST_SWR_H               = 0xfc
    EEPROM_LAST_SW                  = 0xfd
    EEPROM_LAST_IND                 = 0xfe
    EEPROM_LAST_CAP                 = 0xff



class atu100(object):
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
        # Tuner settings
        self.eeprom      = []
        for address in range(0x100):
            self.eeprom.append(0xff)


    def connect(self, port):
        # Open the serial port

        try:
            self.ser = serial.Serial(port = port,
                    baudrate = 4800,
                    bytesize=serial.EIGHTBITS,
                    stopbits = serial.STOPBITS_ONE,
                    parity = serial.PARITY_NONE,
                    timeout=0.1) # default timeout for reading in seconds
        # exit if the port is not opened
        except serial.SerialException as e:
            sys.exit(e)

        logging.info('Succefully connected to ATU-100')

        # Load the JSON files

        # try:
        #     with open(self.args.scpidev) as json_file:
        #         self.scpi_devices = json.load(json_file)
        # except:
        #     logging.error(f"Can't read {self.args.scpidev} SCPI devices file")
        #     print(f"Can't read {self.args.scpidev} SCPI devices file.  Use find_devices.py to create it if missing")
        #     exit(10)



    def sendbool(self, name, value):
        if value:
            msg = f'{{"{name}": true}}\n'
        else:
            msg = f'{{"{name}": false}}\n'
        self.ser.write(msg.encode('ascii'))


    def sendstr(self, name, value):
        msg = f'{{"{name}": "{value}"}}\n'
        self.ser.write(msg.encode('ascii'))


    def geteepromdata(self, address):
        msg = f'{{"Get": {address}}}\n'
        self.ser.write(msg.encode('ascii'))


    def seteepromdata(self, address, data):
        msg = f'{{"Set": {address}, "Value": {data}}}\n'
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
        self.auto = not self.auto
        logging.info(f'Auto -> {self.auto}')
        self.sendbool('Auto', self.auto)


    def toggle_bypass(self):
        self.bypass = not self.bypass
        logging.info(f'Bypass -> {self.bypass}')
        self.sendbool('Bypass', self.bypass)


    def start_tune(self):
        logging.info('Requesting tune')
        self.sendbool('Tune', True)


    def main(self):
        # Get the command line args

        epilog_str = ("Commands can be:\n"
                      " 'a' - Disable auto tunning\n"
                      " 'A' - Enable auto tunning\n"
                      " 'b' - Disable bypass\n"
                      " 'B' - Enable bypass\n"
                      " 'd' - Dump EEPROM contents\n"
                      " 'g' - Get EEPROM setting\n"
                      " 'r' - Reset tuner, C and L\n"
                      " 's' - Set EEPROM setting\n"
                      " 't' - Force tuning\n"
                      "If no command supplied will show current status\n"
                      "Address and data are assumed to be hex format\n"
        )
        parser = argparse.ArgumentParser(prog='atu-100',
                                         description='Control program for ATU-100 tuner',
                                         epilog=epilog_str,
                                         formatter_class=argparse.RawTextHelpFormatter)

        parse_general = parser.add_argument_group('General', 'General options')
        parse_general.add_argument('-p', '--port', default='/dev/ttyACM0', help = 'Serial port for ATU-100')
        parse_general.add_argument('-c', '--command', default='', help = 'Command, as listed below')
        parse_general.add_argument('--logfile', default='atu100.log', help = 'Log filename (atu100.log)')
        parse_general.add_argument('--log-level', type=str,
                                    dest='log_level', default='info',
                                    choices=['debug', 'info', 'warn', 'error', 'critical'],
                                    help='Log level: debug|info(default)|warn|error|critical')
        parse_general.add_argument('--newlog', default=False, action='store_true', help = 'Create a new log file')
        parse_config = parser.add_argument_group('Config', 'EEPROM config options')
        parse_general.add_argument('-s', '--savefile', default='', help = 'Optional file to save EEPROM dump data to')
        parse_general.add_argument('-a', '--address', default='', help = 'EEPROM address for get or set commands')
        parse_general.add_argument('-d', '--data', default='', help = 'EEPROM data for set command')

        self.args = parser.parse_args()

        # Set up logging

        FORMAT = '%(asctime)-15s %(levelname)s %(message)s'
        if self.args.newlog:
            filemode = 'w'
        else:
            filemode = 'a'
        logging.basicConfig(level=logging.getLevelName(self.args.log_level.upper()), format=FORMAT, filename=self.args.logfile, filemode=filemode)
        logging.info('=======================')
        logging.info('| Starting atu100.py |')
        logging.info('=======================')

        self.connect(self.args.port)

        # Get information from the tuner

        if self.args.command == 'a':
            print('Disabling auto tuner mode')
            self.sendbool('Auto', False)

        elif self.args.command == 'A':
            print('Enabling auto tuner mode')
            self.sendbool('Auto', True)

        elif self.args.command == 'b':
            print('Disabling bypass')
            self.sendbool('Bypass', True)

        elif self.args.command == 'B':
            print('Enabling bypass')
            self.sendbool('Bypass', True)

        elif self.args.command == 'd':
            print('Dumping EEPROM, this will take about 10 seconds')
            self.sendstr('Dump', 'EEPROM')

        elif self.args.command == 'r':
            print('Reseting settings')
            eventexpected = True
            self.sendbool('Reset', True)

        elif self.args.command == 't':
            print('Stating tuning')
            eventexpected = True
            self.sendbool('Tune', True)

        elif self.args.command == 'g':
            if self.args.address == '':
                print('Use -a option to set address to get from')
                sys.exit(10)
            self.geteepromdata(int(self.args.address, 16))

        elif self.args.command == 's':
            if self.args.address == '':
                print('Use -a option to set address to set data of')
                sys.exit(10)
            if self.args.data == '':
                print('Use -d option to set data value to be set')
                sys.exit(10)
            self.seteepromdata(int(self.args.address, 16), int(self.args.data, 16))

        else:
            self.sendbool('Status', True)

        #
        # Loop processing key presses, send polls and update battery voltage etc
        #

        while True:

            # Check for a new JSON message

            rxmsg = self.getmsg()
            if rxmsg:
                logging.debug(rxmsg)
                print()
                if self.args.command == 'd':
                    print(json.dumps(rxmsg, indent=4))
                    if self.args.savefile != '':
                        with open(self.args.savefile, 'w') as jsonfile:
                            jsonfile.write(json.dumps(rxmsg, indent=4))
                        print(f'Saved to {self.args.savefile}')
                    break
                
                elif self.args.command == 'g':
                    for name in rxmsg:
                        print(f'{name} = {rxmsg[name]}')
                    break

                elif self.args.command == 's':
                    for name in rxmsg:
                        print(f'{name} = {rxmsg[name]}')
                    break

                else:
                    result = False
                    for name in rxmsg:
                        if name == 'Auto':
                            self.auto = rxmsg[name]
                            if rxmsg[name]:
                                print('Auto:        Enabled')
                            else:
                                print('Auto:        Disabled')

                        elif name == 'Bypass':
                            self.bypass = rxmsg[name]
                            if rxmsg[name]:
                                print('Bypass:      Enabled')
                            else:
                                print('Bypass:      Disabled')

                        elif name == 'Power':
                            self.power = rxmsg[name]
                            print(f'Power:       {self.power:.1f}') 
                            result = True

                        elif name == 'SWR':
                            self.swr = rxmsg[name]
                            print(f'SWR:         {self.swr:.1f}') 

                        elif name == 'Reverse':
                            self.reverse = rxmsg[name]
                            print(f'Reverse:     {self.reverse:.1f}') 

                        elif name == 'Event':
                            print(f'{name+":":12} {rxmsg[name]}')

                        elif name == 'Order':
                            self.order = rxmsg[name]
                            print(f'{name+":":12} {rxmsg[name]}') 

                        elif name == 'Capacitance':
                            self.capacitance = rxmsg[name]
                            print(f'Capacitance: {self.capacitance} pF') 

                        elif name == 'Inductance':
                            self.inductance = rxmsg[name]
                            print(f'Inductance:  {self.inductance} nH') 

                        else:
                            print(f'{name+":":12}: {rxmsg[name]}') 
                    
                    if result:
                        break

        # Clean up and exit

        logging.info('Exiting')




if __name__ == "__main__":
    atu = atu100()
    atu.main()
    sys.exit(0)