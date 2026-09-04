"""Vendored from SeedSigner (MIT License, Copyright (c) 2021 SeedSigner),
src/seedsigner/hardware/displays/ST7789.py at dev branch, 2026-08-17.
Modified: standalone (no BaseDisplayDriver), fixed 240x240 width/height.
Driver for the WaveShare 1.3" LCD hat (ST7789, SPI0 CE0 at 40MHz;
BOARD pins DC=22, RST=13, BL=18)."""

import spidev
import RPi.GPIO as GPIO
import time
import array
import numpy as _np          # CORKY: RGB565 packing, see show_image
from dataclasses import dataclass




class ST7789:
    """
    The original SeedSigner display driver.

    class for ST7789  240*240 1.3inch OLED displays.
    """
    def __init__(self, width=240, height=240):
        self._width = width
        self._height = height
        #Initialize DC RST pin
        self._dc = 22
        self._rst = 13
        self._bl = 18

        GPIO.setmode(GPIO.BOARD)
        GPIO.setwarnings(False)
        GPIO.setup(self._dc,GPIO.OUT)
        GPIO.setup(self._rst,GPIO.OUT)
        GPIO.setup(self._bl,GPIO.OUT)
        GPIO.output(self._bl, GPIO.HIGH)

        #Initialize SPI
        self._spi = spidev.SpiDev(0, 0)
        self._spi.max_speed_hz = 40000000

        self.init()


    @property
    def width(self):
        return self._width

    @property
    def height(self):
        return self._height

    """    Write register address and data     """
    def command(self, cmd):
        GPIO.output(self._dc, GPIO.LOW)
        self._spi.writebytes([cmd])

    def data(self, val):
        GPIO.output(self._dc, GPIO.HIGH)
        self._spi.writebytes([val])

    def init(self):
        """Initialize display"""    
        self.reset()

        self.command(0x36)
        self.data(0x70)                 #self.data(0x00)

        self.command(0x3A) 
        self.data(0x05)

        self.command(0xB2)
        self.data(0x0C)
        self.data(0x0C)
        self.data(0x00)
        self.data(0x33)
        self.data(0x33)

        self.command(0xB7)
        self.data(0x35) 

        self.command(0xBB)
        self.data(0x19)

        self.command(0xC0)
        self.data(0x2C)

        self.command(0xC2)
        self.data(0x01)

        self.command(0xC3)
        self.data(0x12)   

        self.command(0xC4)
        self.data(0x20)

        self.command(0xC6)
        self.data(0x0F) 

        self.command(0xD0)
        self.data(0xA4)
        self.data(0xA1)

        self.command(0xE0)
        self.data(0xD0)
        self.data(0x04)
        self.data(0x0D)
        self.data(0x11)
        self.data(0x13)
        self.data(0x2B)
        self.data(0x3F)
        self.data(0x54)
        self.data(0x4C)
        self.data(0x18)
        self.data(0x0D)
        self.data(0x0B)
        self.data(0x1F)
        self.data(0x23)

        self.command(0xE1)
        self.data(0xD0)
        self.data(0x04)
        self.data(0x0C)
        self.data(0x11)
        self.data(0x13)
        self.data(0x2C)
        self.data(0x3F)
        self.data(0x44)
        self.data(0x51)
        self.data(0x2F)
        self.data(0x1F)
        self.data(0x1F)
        self.data(0x20)
        self.data(0x23)
        
        self.command(0x21)  # inversion ON; 0x20 = inversion OFF

        self.command(0x11)

        self.command(0x29)

    def reset(self):
        """Reset the display"""
        GPIO.output(self._rst,GPIO.HIGH)
        time.sleep(0.01)
        GPIO.output(self._rst,GPIO.LOW)
        time.sleep(0.01)
        GPIO.output(self._rst,GPIO.HIGH)
        time.sleep(0.01)
        
    def SetWindows(self, Xstart, Ystart, Xend, Yend):
        # CORKY MODIFICATION. Upstream hardcodes both high octets to 0x00,
        # which is correct only while every coordinate is below 256. Corky's
        # primary panel is the SeedSigner+ 2.8" at 320x240 (HARDWARE.md), and
        # there (320 - 1) & 0xff is 63: the driver would send 320x240 pixels
        # into a 64-column window. Send the real 16-bit coordinates. For a
        # 240x240 panel every high octet is still 0x00, so this is identical
        # to upstream on the pocket build.
        #set the X coordinates
        self.command(0x2A)
        self.data((Xstart >> 8) & 0xff)
        self.data(Xstart & 0xff)
        self.data(((Xend - 1) >> 8) & 0xff)
        self.data((Xend - 1) & 0xff)

        #set the Y coordinates
        self.command(0x2B)
        self.data((Ystart >> 8) & 0xff)
        self.data(Ystart & 0xff)
        self.data(((Yend - 1) >> 8) & 0xff)
        self.data((Yend - 1) & 0xff)

        self.command(0x2C)    
    
    def show_image(self,Image,Xstart,Ystart):
        """Set buffer to value of Python Imaging Library image."""
        """Write display buffer to physical display"""
        imwidth, imheight = Image.size
        if imwidth != self.width or imheight != self.height:
            raise ValueError('Image must be same dimensions as display \
                ({0}x{1}).' .format(self.width, self.height))
        # CORKY MODIFICATION. Upstream did:
        #     arr = array.array("H", Image.convert("BGR;16").tobytes())
        #     arr.byteswap()
        # Pillow 11 warns "BGR;16 is deprecated and will be removed in Pillow
        # 12", and Pillow 12 has removed it: the call raises "image has wrong
        # mode". The Pi is on 11.1.0 so it still works there today and breaks
        # on the next bump, and it already cannot run on a current dev machine,
        # so the conversion could not be tested off the device at all.
        #
        # Same output, computed directly: RGB-8:8:8 to big-endian RGB-5:6:5.
        # tests/test_display_driver.py pins the bytes; equivalence with the
        # old path was checked on the board on 2026-09-03, all 65536 values.
        rgb = _np.asarray(Image.convert("RGB"), dtype=_np.uint16)
        pix = ((((rgb[:, :, 0] & 0xF8) << 8)
                | ((rgb[:, :, 1] & 0xFC) << 3)
                | (rgb[:, :, 2] >> 3)).astype(">u2").tobytes())
        self.SetWindows ( 0, 0, self.width, self.height)
        GPIO.output(self._dc,GPIO.HIGH)
        self._spi.writebytes2(pix)	
        
    def clear(self):
        """Clear contents of image buffer"""
        _buffer = [0xff]*(self.width * self.height * 2)
        self.SetWindows ( 0, 0, self.width, self.height)
        GPIO.output(self._dc,GPIO.HIGH)
        self._spi.writebytes2(_buffer)

    def invert(self, enabled: bool = True):
        """Invert how the display interprets colors"""
        self.command(0x21 if enabled else 0x20)
