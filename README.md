# ATU-100 firmware for serial communication

This is a firmware for using the popular open source ATU-100 Antenna Tuner in remote operations.

This is very useful, for example, to have the tuner right at the feedpoint of the antenna.

It assumes there is no local display so the eeprom cell settings related to the displays are ignored.

Serial messages are JSON format with the assumption there will be external control software.  Line endings are Linux style.

## Build instructions

Build docker image from https://github.com/zsteva/mplab-pic-xc8-builder

then start docker.sh and run make

## How to program

The compiled hex file is on dist\default\production folder.

Just load it on PICkit or any other tool you use for writing the microcontroller, e.g:
`pk2cmd -B/your/path/to/pk2cmd -PPIC16F1938 -FATU_100_EXT_board/FirmWare_PIC16F1938/dist/default/production/FirmWare_PIC16F1938.production.hex -E -M -J -R`

## How to interface

The serial routine runs at a baud-rate of 9600 bps.

TODO: Redfine this as JSON mesages.

To control the tuner you just need to send a character as if you were pressing a button on the original firmware. The firmware is case insensitive and the commands are:

**A** - toggles auto (automatic tuning)

**B** - toggles bypass

**R** - resets the tuner (makes C = 0 and L=0)

**T** - forces tuning

The tuner sends almost the same text that is send to the display on the original firmware whenever there's a change in status.

## JSON messages

From ATU, any field may be omitted if unchanged:
```
{
    "Board": "ATU-100_EXT",
    "Credit": "N7DDC",
    "FW": "3.2",
    "Build": "ukoda",
    "Power": 85,
    "SWR": 1.2,
    "Order": "LC",
    "Inductance": 100,
    "Capacitance": 47
}
```

## To do

Change number in JSON from string type to number with decimal point scaling

## Acknowledgements

This code is derived from:

https://github.com/zsteva/ATU-100-uart

Which is derived from:

https://github.com/edsonbrusque/ATU-100

Which is derived from:

https://github.com/WA1RCT/N7DDC-ATU-100-mini-and-extended-boards

Which is derived from:

https://github.com/Dfinitski/N7DDC-ATU-100-mini-and-extended-boards

