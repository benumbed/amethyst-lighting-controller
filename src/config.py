"""
config.py

Configuration utilities for lighting controller

Copyright (C) 2022 Nick Whalen (benumbed@projectneutron.com)
"""
import os
import struct
import sys
from array import array
from gc import collect
from micropython import const
from uio import FileIO

STR_ENCODING="utf-8"
CONFIG_ROOT="/lighting"
CONFIG_HEADER=bytes((0x92, 0x00, 0x00))
CONFIG_FOOTER=bytes((0x00, 0x00, 0x42))

PWM_CH0 = const(0)
PWM_CH1 = const(1)
PWM_CH2 = const(2)
PWM_CH3 = const(3)
PWM_CH4 = const(4)
PWM_CH5 = const(5)

BUS = const(0)
SCL = const(1)
SDA = const(2)
FREQ = const(3)

ADC_CH0 = const(0)
ADC_CH1 = const(1)
ADC_CH2 = const(2)
ADC_CH3 = const(3)

ENVELOPE_CONFIG_VER = 2

class ConfigError(Exception): pass

class EnvelopeConfig:
    numPwmChannels: const(int) = const(6)
    minDutyCycle: int = 0
    tachPulsesPerRotation: int = const(2) # Number of poles for the fan tachometer

    def __init__(self, config_file_name="firmware.cfg"):
        self.name: str = "Amethyst"
        self.cfg_version: int = 0
        self.freq: int = 133_000_000
        # Sane defaults based on Amethyst
        self.config_file = f"{CONFIG_ROOT}/{config_file_name}"
        self.pwmMap: bytearray = bytearray((0, 2, 4, 6, 8, 10))
        self.tachMap: bytearray = bytearray((1, 3, 5, 7, 9, 11))
        self.pwmNames: list = ["FAN 1", "FAN 2", "FAN 3", "FAN 4", "Pump", "Spare"]

        self.pwmDutyCycles: bytearray = bytearray((100, 100, 100, 100, 100, 100))

        # I2C Bus Settings
        # i2c bus, i2c scl pin, i2c sda pin, i2c frequency
        self.i2cSettings: array = array("L", (1, 27, 26, 400_000))

        # INA3221 Defaults
        # i2c device address
        self.inaSettings: bytearray = bytearray((0x40,))

        # ADS1115 Defaults
        # i2c device address
        self.adsSettings: bytearray = bytearray((0x48,))


        try:
            os.stat(CONFIG_ROOT)
        except OSError:
            os.mkdir(CONFIG_ROOT)

    def _read_bytearray(self, file: FileIO) -> bytearray:
        size = int.from_bytes(file.read(1), sys.byteorder)
        return bytearray(file.read(size))

    def _read_str_list(self, file: FileIO) -> list:
        num_elements = int.from_bytes(file.read(1), sys.byteorder)
        elements = (file.read(int.from_bytes(file.read(1), sys.byteorder)).decode(STR_ENCODING)
                    for _ in range(0, num_elements))
        return list(elements)

    def _read_str(self, file: FileIO) -> str:
        str_len = int.from_bytes(file.read(1), sys.byteorder)
        return file.read(str_len).decode(STR_ENCODING)

    def _read_array(self, file: FileIO) -> array:
        array_len = int.from_bytes(file.read(2), sys.byteorder)
        arr = array(file.read(1).decode(STR_ENCODING))

        for i in range(0, array_len):
            arr.append(int.from_bytes(file.read(4), sys.byteorder))

        return arr

    def getInaCfgItem(self, item: int) -> int:
        """
        Helper to get config items out of the inaSettings bytearray

        :param item:
        :return:
        """
        return self.inaSettings[item]

    def fromFlash(self):
        """
        Loads the configuration from flash

        :return:
        """
        try:
            with open(self.config_file, "rb") as cfg_file:
                header = cfg_file.read(4)
                if header[0:2] != CONFIG_HEADER[0:2]:
                    raise ConfigError(f"Bad config header: {header[0]:#x} {header[1]:#x} {header[2]:#x}")
                self.cfg_version = header[3]
                if self.cfg_version != ENVELOPE_CONFIG_VER:
                    raise ConfigError(f"Config file version does not match ENVELOPE_CONFIG_VER ({self.cfg_version}, {ENVELOPE_CONFIG_VER})")
                self.freq = int.from_bytes(cfg_file.read(4), sys.byteorder)
                self.name = self._read_str(cfg_file)
                self.pwmMap = self._read_bytearray(cfg_file)
                self.tachMap = self._read_bytearray(cfg_file)
                self.pwmDutyCycles = self._read_bytearray(cfg_file)
                self.pwmNames = self._read_str_list(cfg_file)
                self.inaSettings = self._read_bytearray(cfg_file)
                self.i2cSettings = self._read_array(cfg_file)
                self.adsSettings = self._read_bytearray(cfg_file)
                footer = cfg_file.read(3)

                if footer != CONFIG_FOOTER:
                    raise ConfigError(f"Bad config footer: {footer.decode(STR_ENCODING)} \
                                        Expected: {CONFIG_FOOTER[0]:#x} {CONFIG_FOOTER[1]:#x} {CONFIG_FOOTER[2]:#x}")
        except OSError:
            pass



    def _savable_bytearray(self, data: bytearray) -> bytearray:
        """
        Returns a bytearray with its length (1 byte) prepended

        :param data:
        :return:
        """
        return bytearray(len(data).to_bytes(1, sys.byteorder) + data)

    def _savable_str(self, data: str) -> bytearray:
        """
        Converts a str to a savable format
        :param data:
        :return:
        """
        ret = bytearray((len(data),))
        ret += data.encode(STR_ENCODING)

        return ret

    def _savable_str_list(self, data: list) -> bytearray:
        """
        Takes a tuple of strings and converts it to a savable byteaarray
        :param data:
        :return:
        """
        ret = bytearray((len(data),))
        for element in data:
            ret += bytes((len(element),))
            ret += element.encode(STR_ENCODING)

        return ret

    def _savable_array(self, data: array) -> bytearray:
        """
        Takes a tuple of strings and converts it to a savable byteaarray
        :param data:
        :return:
        """
        ret = bytearray(len(data).to_bytes(2, sys.byteorder))
        ret += "L"[0].encode(STR_ENCODING)

        for element in data:
            ret += struct.pack("L", element)

        return ret

    def toFlash(self):
        """
        Saves the configuration to flash

        :return:
        """
        with open(f"{self.config_file}.new", "wb") as cfg_file:
            cfg_file.write(CONFIG_HEADER)
            cfg_file.write(ENVELOPE_CONFIG_VER.to_bytes(1, sys.byteorder))
            cfg_file.write(self.freq.to_bytes(4, sys.byteorder))
            cfg_file.write(self._savable_str(self.name))
            cfg_file.write(self._savable_bytearray(self.pwmMap))
            cfg_file.write(self._savable_bytearray(self.tachMap))
            cfg_file.write(self._savable_bytearray(self.pwmDutyCycles))
            cfg_file.write(self._savable_str_list(self.pwmNames))
            cfg_file.write(self._savable_bytearray(self.inaSettings))
            cfg_file.write(self._savable_array(self.i2cSettings))
            cfg_file.write(self._savable_bytearray(self.adsSettings))
            cfg_file.write(CONFIG_FOOTER)

        try:
            os.rename(self.config_file, f"{self.config_file}.old")
        except OSError:
            pass
        os.rename(f"{self.config_file}.new", self.config_file)

        # Manually run the garbage collector since we just did a lot of things, and it's expected this call will be slow
        # anyway
        collect()
