#!/usr/bin/env python3
'''
ATU-100 hex to JSON extractor

This program takes an ATU-100. hex program file and extracts the EEPROM areas
and saves as JSON file that can be later to apply the EEPROM settings to
another ATU-100/

The format of the JSON messages is documented in the file
https://github.com/ukoda/ATU-100-remote/blob/master/README.md
'''

import json
import sys

# Show usage if now supplied two file names

if len(sys.argv) != 3:
    print('ATU-100 hex to JSON extractor')
    print('  This program extracts the EEPROM data from a hex ATU-100 firmware file')
    print('  and saves it as a JSON format file.')
    print()
    print('Usage:')
    print(f'  {sys.argv[0]} firmware.hex eeprom.json')
    sys.exit(10)

# Open the hex file and loop thru it line by line

try:
    with open(sys.argv[1], 'r') as hexfile:
        base = 0
        eeprom = []
        for celladdress in range(0x100):
            eeprom.append(0xff)

        for line in hexfile:

            # Check line starts ':' and is long enough

            if line[:1] != ':' or len(line) < 12:
                print(f'Invalid line {line}')
                sys.exit(20)

            size    = int(line[1:3], 16)        # Get the size
            address = int(line[3:7], 16) + base # Get address
            rectype = int(line[7:9], 16)        # Get record type, we only expect type 0, 1 and 4 

            # Process based on record type

            if rectype == 0:
                if (address >= 0x1e000) and (address < 0x1e200):
                    for datapos in range(size // 2):
                        strpos = datapos*4
                        celladdress = (address - 0x1e000) // 2 + datapos
                        celldata = int(line[9+strpos:11+strpos], 16)
                        eeprom[celladdress] = celldata

            elif rectype == 1:

                # Write the EEPROM data to the JSON file

                with open(sys.argv[2], 'w') as jsonfile:
                    jsonfile.write('{\n')
                    for celladdress in range(0x100):
                        if celladdress != 0xff:
                            jsonfile.write(f'    "{celladdress:02x}": "{eeprom[celladdress]:02x}",\n')
                        else:
                            jsonfile.write(f'    "{celladdress:02x}": "{eeprom[celladdress]:02x}"\n')
                    jsonfile.write('}\n')
                print(f'Created {sys.argv[2]}')

            elif rectype == 4:
                base = int(line[9:13], 16) * 0x10000

            else:
                print(f'Unexpected record type {rectype} in line {line}')
                sys.exit(30)

except Exception as e:
    print(f'Error: {e}')
    sys.exit(10)

print('Extraction complete')
