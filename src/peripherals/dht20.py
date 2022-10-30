"""
dht20.py

Management for DHT20 temp/humidity sensor.

Copyright (C) 2022 Nick Whalen (purplxed@projectneutron.com)
"""
from gc import collect

import gc
from machine import I2C
from micropython import const
from time import sleep_ms

DEV_ADDR = const(0x38)

class Dht20Error(Exception): pass

class Dht20:
    def __init__(self, i2c: I2C):
        """

        """
        self._i2c = i2c
        self._address = 0x38
        self._recv_buffer = bytearray(6)
        self._humid = 0.0
        self._temp = 0.0

        self._checkStatus()

        gc.collect()

    @property
    def humidity(self) -> float:
        self._readDevice()
        return self._humid

    @property
    def temperature(self) -> float:
        self._readDevice()
        return self._temp

    def _write(self, data: bytearray or bytes):
        """
        Writes the send buffer to the device

        :return:
        """
        self._i2c.writeto(DEV_ADDR, bytes(data))

    def _read(self, num_bytes: int):
        """
        Reads the requested number of bytes from the device

        """
        self._recv_buffer = bytearray(num_bytes)
        self._recv_buffer = self._i2c.readfrom(DEV_ADDR, num_bytes)

    def _checkStatus(self):
        """
        Soft-resets the device
        """
        self._write((0x71,))
        sleep_ms(10)
        self._read(1)
        if (self._recv_buffer[0] & 0x18) != 0x18:
            raise Dht20Error(f"Soft reset response was not 0x18 ({self._recv_buffer[0]:#2x})")

    def _readDevice(self):
        """
        Reads temperature and humidity data from the device

        """
        self._write((0xAC, 0x33, 0x00))
        sleep_ms(80)    # Per datasheet
        self._read(7)

        self._humid = ((
            (self._recv_buffer[1] << 12) | (self._recv_buffer[2] << 4) | (self._recv_buffer[3] >> 4)) / 0x100000
                      ) * 100

        self._temp = ((
            (((self._recv_buffer[3] & 0xF) << 16) | (self._recv_buffer[4] << 8) | self._recv_buffer[5]) / 0x100000
                      ) * 200.0) - 50
