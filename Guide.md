# ATU-100 remote usage guide

This guide is intended to help step you through the process of modifying, setting up and using an ATU-100 for remote operation.  The LCD display will be disconnected as this software can not drive both the LCD and UART.

It should be noted the instructions here assume you are using a Linux PC.  If you are not using Linux you will need to work out the equivelent steps for your OS.  I only have Linux PCs now as they are so much easier to use for this kind of development work.

## Considerations

As you will be controlling the ATU via a serial port to a PC you need to decide on where the PC will be and how it will be commected.  Some options are:

### In shack remote operation

If the ATU-100 is in the shack near your computer and you are using remote for easier operation and the more advanced fuctionality a PC offers then all you need is a USB to TTL serial adaptor between the PC and the ATU-100.

### Remote control via a long serial cable

In this case controlling computer is your shack and the ATU-100 is remote, such as on the mast head near the antenna.  In this case you can not use the TTL serial connection as it is only intended for short distances.  The use of RS-422 to TLL  at the ATU-100 and RS422 to USB at the PC and connected via shelided CAT 5 cable with common chokes on it should work well.  I have not personally tried this.  NB: RS-485 will not work with my software as there is no direction pin set up on the ATU-100.

### Remote control via TCPIP

This is my target mode of use.  A small computer, such as the Raspberry Pi (RPi), is located adjacent to the ATU-100.  With the RPi you can use a simple direct TTL serial connection.  You then can then connect to the RPi via Ethernet.  As Ethernet has electrical isolation sheild CAT 5, or better, with common mode chokes should work.  I have not personally tried this.

In my case I have a POE Ethernet switch with a fibre interface as I also have a Hermes Lite at the remote location.  I power the RPi via POE and remote boot it using PXE.  I also have a remote antenna switch modifed for RPi control.  This set up allow the remote site to only need a power feed and a single fibre cable, so mitigates many RF issues and allow long distances with no losses.

This is the reason much of the supporting client software is Ncurses terminal based is it runs well remotely over a SSH connection to the RPi.

## Preperation

You will need:
* A tested and working ATU-100.
* A PC for control.
* Serial cable for between the ATH-100 and the PC
	- For a normal PC this will be a normal TTL to USB adaptor.
	- For a Raspberry Pi a direct connection can be made.
* PIC16 programmer and related software.
	- For the programmer I am using a PICkit 2.
	- For software I use `pk2cmd` which can be installed using:
		1. Change to a directory to build the software.
		2. `git clone git@github.com:jaka-fi/pk2cmd.git`
		3. `cd pk2cmd/pk2cmd`
		4. `make linux`
		5. `sudo make install`

## Converting for remote operation

1. Backup the existing software and setting.
	1. Disconnect the LCD and store in case you want to convert back in future.
	2. Connect the programmer to the header the LCD was using.
	3. Check your PC sees the programmer using: `pk2cmd -S`
	4. Check your PC sees the PIC16 processor using: `	pk2cmd -PPIC16F1938 -I`
	5. Download the full content of the PIC15 using: `pk2cmd -PPIC16F1938 -J -GFFull.hex`
	6. You should now have a hex format file called `Full.hex`, save it somewhere so you can restore it later if you want.
	7. Extract the EEPROM settings from the hex file so you can restore the after the firmware has been updated.
		1. `./atu100hextojson.py ../../ATU-100-backups/sma/backup/Full.txt saved.json`
2. Flash the new firmware into the ATU-100.  The firmware is in the same directory as this guide and has the name `ATU-100_remote_PIC16F1938_XXXXXXXX_YYYY.hex` where XXXXXXXX is that date and YYYY the time when the hex file was created.
	1. Flash the new firmware using: `pk2cmd -B/your/path/to/pk2cmd/pk2cmd -PPIC16F1938 -FATU-100_remote_PIC16F1938_XXXXXXXX_YYYY.hex -E -M -J -R`
3. Test the software is running:
	1. Disconnect the programmer and power off.
	2. Wire the TTL serial TXD data line from the PC to the pad on the rear of the PCBA named ... TODO: Check the label on the PCBA.
	3. Wire the TTL serial RXD data line to the PC to the pad on the rear of the PCBA named ... TODO: Check the label on the PCBA.
	4. Connect the serial adaptor or cable.  In this example we are assuming it is `/dev/ttyUSB0`
	4. Power on the ATU-100.
	5. Goto the `python` directory in this project.
	6. `./atu100.py -p /dev/ttyUSB0`
	7. You should now see the basic status report from the ATU-100.
4. Restore the EEPROM settings you saved earlier:
	1. `./atu100.py -p /dev/ttyACM1 -c u -e saved.json`
