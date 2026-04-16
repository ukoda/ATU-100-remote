#!/usr/bin/env python3
'''
ATU-100 control program and library

When called as a program provides a simple traditional command line control
of a remote ATU-100.

The AUT-100 needs to be programmed with the hex file from
https://github.com/ukoda/ATU-100-remote and the 3V TTL serial lines to wire to
the board to allow comms with this program.

This allows the exchanage of JSON format messages to control the ATU-100 and
show it's status.  The format of the JSON messages is documented in the file
https://github.com/ukoda/ATU-100-remote/blob/master/README.md
'''

import argparse
import datetime
import json
import logging
import serial.tools.list_ports
import string
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
        self.relay_order = False
        self.relay_cap   = [False, False, False, False, False, False, False]
        self.relay_ind   = [False, False, False, False, False, False, False]
        # Tuner settings
        self.eeprom      = []
        for address in range(0x100):
            self.eeprom.append(0xff)
        self.value_cap   = [0, 0, 0, 0, 0, 0, 0]
        self.value_ind   = [0, 0, 0, 0, 0, 0, 0]


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
            print(f'Serial port fail: {e}')
            sys.exit(10)

        logging.info('Succefully connected to ATU-100')


    def wait_name(self, name):
        timeout = 0
        while True:
            rxmsg = self.getmsg()
            if rxmsg and name in rxmsg:
                return rxmsg
            timeout += 1
            if timeout > 30:    # 3 Seconds
                logging.warning(f'Timeout waiting for {name}')
                return None


    def sendbool(self, name, value):
        if value:
            msg = f'{{"{name}": true}}\n'
        else:
            msg = f'{{"{name}": false}}\n'
        self.ser.write(msg.encode('ascii'))


    def sendint(self, name, value):
        msg = f'{{"{name}": {value}}}\n'
        self.ser.write(msg.encode('ascii'))


    def sendstr(self, name, value):
        msg = f'{{"{name}": "{value}"}}\n'
        self.ser.write(msg.encode('ascii'))


    def send_restart(self):
        self.sendbool('x', True)

    def geteepromdata(self, address):
        msg = f'{{"Get": {address}}}\n'
        self.ser.write(msg.encode('ascii'))


    def seteepromdata(self, address, data):
        msg = f'{{"Set": {address}, "Value": {data}}}\n'
        self.ser.write(msg.encode('ascii'))


    def send_relay_capacitors(self):
        bit = 0x1
        relaybits = 0
        for relay in range(7):
            if self.relay_cap[relay]:
                relaybits += bit
            bit *= 2
        if self.relay_order:
            relaybits += 128
        self.sendint('RelayC', relaybits)
        self.sendbool('Status', True)


    def send_relay_inductors(self):
        bit = 0x1
        relaybits = 0
        for relay in range(7):
            if self.relay_ind[relay]:
                relaybits += bit
            bit *= 2
        self.sendint('RelayI', relaybits)
        self.sendbool('Status', True)


    def get_relay_capacitors(self):
        self.geteepromdata(cell.EEPROM_LAST_SW)
        self.wait_name('fd')
        self.geteepromdata(cell.EEPROM_LAST_CAP)
        self.wait_name('ff')


    def get_relay_inductors(self):
        self.geteepromdata(cell.EEPROM_LAST_IND)
        self.wait_name('fe')


    def get_bcd(self, bcd):
        tens = bcd // 16
        units = bcd & 0xf
        return tens * 10 + units


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

                    if result:

                        # We have a valid JSON message from the tuner, check the info in it

                        for name in result:
                            value = result[name]
                            if all(char in string.hexdigits for char in name):
                                cell_address = int(name, 16)
                                cell_data = int(value, 16)
                                if (cell_address < 0x100) and (cell_data < 0x100):

                                    # We have a EEPROM cell value, save it and use to get setting info

                                    self.eeprom[cell_address] = cell_data
                                    if (cell_address >= cell.EEPROM_INDUCTOR_FIRST) and (cell_address <= cell.EEPROM_INDUCTOR_LAST):
                                        offset = cell_address - cell.EEPROM_INDUCTOR_FIRST
                                        highbyte = (offset % 2) == 0
                                        offset //= 2
                                        if highbyte:
                                            self.value_ind[offset] = self.get_bcd(cell_data) * 100
                                        else:
                                            self.value_ind[offset] += self.get_bcd(cell_data)
                                            logging.info(f'Inductor {offset} is {self.value_ind[offset]}')

                                    elif (cell_address >= cell.EEPROM_CAPACITOR_FIRST) and (cell_address <= cell.EEPROM_CAPACITOR_LAST):
                                        offset = cell_address - cell.EEPROM_CAPACITOR_FIRST
                                        highbyte = (offset % 2) == 0
                                        offset //= 2
                                        if highbyte:
                                            self.value_cap[offset] = self.get_bcd(cell_data) * 100
                                        else:
                                            self.value_cap[offset] += self.get_bcd(cell_data)
                                            logging.info(f'Capacitor {offset} is {self.value_cap[offset]}')

                                    elif cell_address == cell.EEPROM_LAST_SW:
                                        self.relay_order = cell_data == '01'
                                            
                                    elif cell_address == cell.EEPROM_LAST_IND:
                                        bit = 0x1
                                        for relay in range(7):
                                            self.relay_ind[relay] = bool(bit & cell_data)
                                            bit *= 2

                                    elif cell_address == cell.EEPROM_LAST_CAP:
                                        bit = 0x1
                                        for relay in range(7):
                                            self.relay_cap[relay] = bool(bit & cell_data)
                                            bit *= 2

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


    def _print_msg(self, rxmsg):
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


    def main(self):
        # Get the command line args

        epilog_str = ("Commands can be:\n"
                      " 'a' - Disable auto tunning\n"
                      " 'A' - Enable auto tunning\n"
                      " 'b' - Disable bypass\n"
                      " 'B' - Enable bypass\n"
                      " 'c' - Capacitor relay on\n"
                      " 'C' - Capacitor relay off\n"
                      " 'd' - Download EEPROM contents from ATU-100\n"
                      " 'f' - Capacitor first\n"
                      " 'g' - Get an EEPROM cell\n"
                      " 'i' - Inductor relay off\n"
                      " 'I' - Inductor relay on\n"
                      " 'l' - Capacitor last\n"
                      " 'r' - Reset tuner, C and L\n"
                      " 's' - Set an EEPROM cell\n"
                      " 't' - Force tuning\n"
                      " 'u' - Upload EEPROM contents to ATU-100\n"
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
        parse_config.add_argument('-e', '--eepromfile', default='', help = 'EEPROM file anme for EEPROM dump or upload')
        parse_config.add_argument('-a', '--address', default='', help = 'EEPROM address for get or set commands')
        parse_config.add_argument('-d', '--data', default='', help = 'EEPROM data for set command')
        parse_config.add_argument('-r', '--relay', default=0, help = 'Relay number, 0 to 6')

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
            print('Downloading EEPROM, this will take about 10 seconds')
            self.sendstr('Dump', 'EEPROM')

        elif self.args.command == 'u':
            if self.args.eepromfile == '':
                print('Use the -e to specifiy the EEPROM JSON file to upload')
                sys.exit(20)
            try:
                with open(self.args.eepromfile, 'r') as jsonfile:
                    jsondata = jsonfile.read()
                    upload = json.loads(jsondata)
            except Exception as e:
                print(f'EEPROM JSON file read error: {e}')
                sys.exit(22)
            print('Checking EEPROM, this will take about 10 seconds')
            self.sendstr('Dump', 'EEPROM')
            rxmsg = self.wait_name('ff')
            if not 'ff' in rxmsg:
                print('Failed to check existing EEPROM contents')
                sys.exit(25)
            print('Uploading changes')
            for address in upload:
                eepromaddress = int(address, 16)
                if self.eeprom[eepromaddress] != int(upload[address], 16):
                    print(f'  Cell {address}: {self.eeprom[eepromaddress]:02x} replaced with {upload[address]}')
                    self.seteepromdata(eepromaddress, int(upload[address], 16))
                    self.wait_name(address)
            print('Upload complete')
            return
            
        elif self.args.command == 'f':
            print('Turn on capacitor first relay i.e CL')
            self.get_relay_capacitors()
            self.relay_order = False
            self.send_relay_capacitors()

        elif self.args.command == 'l':
            print('Turn off capacitor first relay i.e LC')
            self.get_relay_capacitors()
            self.relay_order = True
            self.send_relay_capacitors()

        elif self.args.command == 'c':
            print(f'Turn off capacitor relay {self.args.relay}')
            self.get_relay_capacitors()
            self.relay_cap[int(self.args.relay)] = False
            self.send_relay_capacitors()

        elif self.args.command == 'C':
            print(f'Turn on capacitor relay {self.args.relay}')
            self.get_relay_capacitors()
            self.relay_cap[int(self.args.relay)] = True
            self.send_relay_capacitors()

        elif self.args.command == 'i':
            print(f'Turn off inductor relay {self.args.relay}')
            self.get_relay_inductors()
            self.relay_ind[int(self.args.relay)] = False
            self.send_relay_inductors()

        elif self.args.command == 'I':
            print(f'Turn on inductor relay {self.args.relay}')
            self.get_relay_inductors()
            self.relay_ind[int(self.args.relay)] = True
            self.send_relay_inductors()

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
                sys.exit(30)
            self.geteepromdata(int(self.args.address, 16))

        elif self.args.command == 's':
            if self.args.address == '':
                print('Use -a option to set address to set data of')
                sys.exit(40)
            if self.args.data == '':
                print('Use -d option to set data value to be set')
                sys.exit(50)
            self.seteepromdata(int(self.args.address, 16), int(self.args.data, 16))

        else:
            self.sendbool('Status', True)

        #
        # Loop processing waiting for last message
        #

        while True:

            # Check for a new JSON message

            rxmsg = self.getmsg()
            if rxmsg:
                logging.debug(rxmsg)
                print()

                # EEPROM Dump command

                if self.args.command == 'd':
                    print(json.dumps(rxmsg, indent=4))
                    if self.args.eepromfile != '':
                        with open(self.args.eepromfile, 'w') as jsonfile:
                            jsonfile.write(json.dumps(rxmsg, indent=4))
                        print(f'Saved to {self.args.eepromfile}')
                    break

                # Get EEPROM cell
                
                elif self.args.command == 'g':
                    for name in rxmsg:
                        print(f'{name} = {rxmsg[name]}')
                    break

                # Set EEPROM cell

                elif self.args.command == 's':
                    for name in rxmsg:
                        print(f'{name} = {rxmsg[name]}')
                    break

                else:
                    result = 'Power' in rxmsg
                    self._print_msg(rxmsg)
                    if result:
                        break

        # Clean up and exit

        logging.info('Exiting')




if __name__ == "__main__":
    atu = atu100()
    atu.main()
    sys.exit(0)