# ATU-100 remote usage guide

This guide is intended to help step you through the process of modifying, setting up and using an ATU-100 for remote operation.

## Considerations

As you will be controlling the ATU via a serial port to a PC you need to decide on where the PC will be and how it will be commected.  Some options are:

### In shack remote operation

If the ATU-100 is in the shack near your computer and you are using remote for easier operation and the more advanced fuctionality a PC offers then all you need is a USB to TTL serial adaptor between the PC and the ATU-100.

### Remote control via a long serial cable

In this case controlling computer is your shack and the ATU-100 is remote, such as on the mast head near the antenna.  In this case you can not use the TTL serial connection as it is only intended for short distances.  The use of RS-422 to TLL  at the ATU-100 and RS422 to USB at the PC and connected via shelided CAT 5 cable with common chokes on it should work well.  I have not personally tried this.  NB: RS-485 will not work with my software as there is no direction pin set up on the ATU-100.

### Remote control via TCPIP

This is my target mode of use.  A small computer, such as the Raspberry Pi (RPi), is located adjacent to the ATU-100.  With the RPi you can use a simple direct TTL serial connection.  You then can then connect to the RPi via Ethernet.  As Ethernet has electrical isolation sheild CAT 5, or better, with common mode chokes should work.  I have not personally tried this.

In my case I have a POE Ethernet switch with a fibre interface as I also have a Hermes Lite at the remote location.  I power the RPi via POE and remote boot it using PXE.  I also have a remote antenna switch modifed for RPi control.  This set up allow the remote site to only need a power feed and a single fibre cable, so mitigates many RF issues and allow long distances with no losses.

The reason much of the supporting client software is Ncurses terminal based is it runs well remotely over a SSH connection to the RPi.

## Preperation

You will need:
* A tested and working ATU-100.
* A PC for control.

.... Not complete yet ....
