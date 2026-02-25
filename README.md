# ATU-100 firmware for serial communication

This is a firmware for using the popular open source ATU-100 Antenna Tuner in remote operations.

This is very useful, for example, to have the tuner right at the feedpoint of the antenna.

## Build instructions

Build docker image from https://github.com/zsteva/mplab-pic-xc8-builder

then start docker.sh and run make

## How to program

The compiled hex file is on dist\default\production folder.

Just load it on PICkit or any other tool you use for writing the microcontroller.


## How to interface

The serial routine runs at a baud-rate of 9600 bps.

To control the tuner you just need to send a character as if you were pressing a button on the original firmware. The firmware is case insensitive and the commands are:

**A** - toggles auto (automatic tuning)

**B** - toggles bypass

**R** - resets the tuner (makes C = 0 and L=0)

**T** - forces tuning

The tuner sends almost the same text that is send to the display on the original firmware whenever there's a change in status.


## Acknowledgements

This code is derived from:

https://github.com/edsonbrusque/ATU-100

Which is derived from:

https://github.com/WA1RCT/N7DDC-ATU-100-mini-and-extended-boards

Which is derived from:

https://github.com/Dfinitski/N7DDC-ATU-100-mini-and-extended-boards

