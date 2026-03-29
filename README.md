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

**System information:**
```
{
    "Board": "ATU-100_EXT",
    "Credit": "N7DDC",
    "FW": "3.2",
    "Build": "ukoda"
}
```


**System state:**
```
{
    "Efficency": 100,
    "Power": 85,
    "SWR": 1.2,
    "Order": "LC",
    "Inductance": 100,
    "Capacitance": 47
}
```
Where:
* Efficency is a percentage, will not be reported is not calculated.
* Power is in Watts.
* Order will be "CL" of the capacitor is before the inductor and "LC" if after it.
* Inductance is in uH.
* Capacitance is in pF.


**Settings:**
```
{
    "timeout: 21
}
```
Only setting that are actually used in the code are sent.


**EEPROM data:**
```
{
    "00": "78",
    "01": "01",
    "02": "00",
    "03": "15",
...
    "fe": "00",
    "ff": "00"
}
```
All fields are hex and are address and data pairs

## To do

I would love to clean up all the `char` types being used as `bool` and usually testing for `== 0` as false and `== 1` as true.  However it is high risk because a lot of the compound tests are using the `&` bitwise operator instead of the `&&` boolean operator.  There is a risk if a char is set to a value other that 1 anywhere.

If done we could change stuff like:
```
if (g_c_SW == 0)
    g_c_SW = 1;
else
    g_c_SW = 0;
```
to easier to read code like:
```
g_c_SW = !g_c_SW;
```

Some header files do not have protection from multiple inclusion and some, such as `main.h` have `static` type declaration that given the intended scope should be defined in the related c file.  Likewise the regular code in the header files too.

## Acknowledgements

This code is derived from:

https://github.com/zsteva/ATU-100-uart

Which is derived from:

https://github.com/edsonbrusque/ATU-100

Which is derived from:

https://github.com/WA1RCT/N7DDC-ATU-100-mini-and-extended-boards

Which is derived from:

https://github.com/Dfinitski/N7DDC-ATU-100-mini-and-extended-boards

