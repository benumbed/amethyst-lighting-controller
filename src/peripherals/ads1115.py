"""
ads1115.py

Copyright (C) 2022 Nick Whalen (purplxed@projectneutron.com)

MicroPython-based management of ADS1115 I2C 4-channel (muxed) 16-bit Delta-Sigma ADC chips
Written from Rev. D of datasheet: https://www.ti.com/lit/ds/symlink/ads1115.pdf
"""
import micropython
from gc import collect

import time
from machine import I2C
from micropython import const
from struct import unpack, pack

CTXT_NONE = 0
CTXT_ENTER = 1
CTXT_EXIT = 2

# Address Pointer Register Values
ADDR_CONVERSION_REG = const(0x00)
ADDR_CONFIG_REG = const(0x01)
ADDR_LO_THRESH_REG = const(0x02)
ADDR_HI_THRESH_REG = const(0x03)

# Config Register Values
CFG_OS_STAT_WRITE_NE = const(0x0000)
CFG_OS_STAT_WRITE_SINGLE = const(0x8000)
CFG_OS_STAT_READ_CONV = const(0x0000)
CFG_OS_STAT_READ_NOCONV = const(0x8000)

CFG_MUX_AIN0_AIN1 = const(0x0000)   # Default
CFG_MUX_AIN0_AIN3 = const(0x1000)
CFG_MUX_AIN1_AIN3 = const(0x2000)
CFG_MUX_AIN2_AIN3 = const(0x3000)
CFG_MUX_AIN0_GND = const(0x4000)
CFG_MUX_AIN1_GND = const(0x5000)
CFG_MUX_AIN2_GND = const(0x6000)
CFG_MUX_AIN3_GND = const(0x7000)

CFG_PGA_FSR_6_144 = const(0x000)
CFG_PGA_FSR_4_096 = const(0x200)
CFG_PGA_FSR_2_048 = const(0x400)    # Default
CFG_PGA_FSR_1_024 = const(0x600)
CFG_PGA_FSR_0_512 = const(0x800)
CFG_PGA_FSR_0_256 = const(0xA00)
CFG_PGA_FSR_0_256_6 = const(0xC00)
CFG_PGA_FSR_0_256_7 = const(0xE00)

CFG_OP_MODE_CONT = const(0x000)
CFG_OP_MODE_SNGL = const(0x100)     # Default

CFG_DATA_RT_8SPS = const(0x00)
CFG_DATA_RT_16SPS = const(0x20)
CFG_DATA_RT_32SPS = const(0x40)
CFG_DATA_RT_64SPS = const(0x60)
CFG_DATA_RT_128SPS = const(0x80)    # Default
CFG_DATA_RT_250SPS = const(0xA0)
CFG_DATA_RT_475SPS = const(0xC0)
CFG_DATA_RT_860SPS = const(0xE0)

CFG_COMP_MODE_TRAD = const(0x00)    # Default
CFG_COMP_MODE_WINDOW = const(0x10)

CFG_COMP_POL_LOW = const(0x0)       # Default
CFG_COMP_POL_HIGH = const(0x8)

CFG_COMP_LAT_NON = const(0x0)       # Default
CFG_COMP_LAT_LATCH = const(0x4)

CFG_COMP_QUE_1 = const(0x0)
CFG_COMP_QUE_2 = const(0x1)
CFG_COMP_QUE_4 = const(0x2)
CFG_COMP_QUE_DISABLE = const(0x3)   # Default

LSB_6_144 = const(0.0001875)
LSB_4_096 = const(0.000125)
LSB_2_048 = const(0.0000625)        # Default
LSB_1_024 = const(0.00003125)
LSB_0_512 = const(0.000015625)
LSB_0_256 = const(0.0000078125)

# FSR config values after bitwise and-ing with 0xE on top config byte
FSR_LSB_IDX_MAP = (0, 2, 4, 6, 8, 10, 12, 14)
LSB_MAP = (LSB_6_144, LSB_4_096, LSB_2_048, LSB_1_024, LSB_0_512, LSB_0_256, LSB_0_256, LSB_0_256)

# These only map (AIp=>GND) not (AIp=>AIn),
CHAN_MAP = (CFG_MUX_AIN0_GND, CFG_MUX_AIN1_GND, CFG_MUX_AIN2_GND, CFG_MUX_AIN3_GND)


class ADS1115Error(Exception): pass
class ADSDoesNotExistError(ADS1115Error): pass
class ADSConfigError(ADS1115Error): pass

class _ADS1115Device:
    """
    Encapsulates information about an ADS1115 device

    """
    def __init__(self, addr: int, name: str, i2c: I2C, config: bytearray[2] = bytearray((0x85, 0x83)), writeCfg=False):
        """
        Initialize a ASD1115 device

        :param addr: i2c address of the device
        :param name: Display name for the device
        :param i2c: Initialized i2c object
        :param config: Configuration for the device (defaults to 0x8583, which is the actual device default)
        :param writeCfg: Write provided config to the device
        """
        self._i2c: I2C = i2c
        self.address: int = addr
        self.name: str = name
        self.config: bytearray[2] = config
        self._config_packet: bytearray[3] = bytearray((ADDR_CONFIG_REG, 0x0, 0x0))
        self._config_addr: bytes[1] = bytes((ADDR_CONFIG_REG,))
        self._i2c_packet: bytearray[3] = bytearray(3)
        self._reg_address: bytearray[1] = bytearray(1)
        self._last_read_value: int = 0

        if writeCfg:
            self.writeConfig()

        self.readConfiguration()

    @micropython.native
    def writeConfig(self):
        """
        Writes the config bytes out to the device

        :return: `True` on successful write, `False` otherwise
        """
        self._config_packet[1:] = self.config[0:]
        self._i2c.writeto(self.address, self._config_packet)

        if self._i2c.readfrom(self.address, 2) == self.config:
            # The ADS returns before it has finished saving the config, and without this, _weird_ shit happens if you
            # cycle through channels (thus changing the config). Happened after I optimized the code.
            time.sleep_ms(30)
            return

        raise ADSConfigError("Returned configuration from device did not match local configuration")

    @micropython.native
    def readConfiguration(self) -> bytearray:
        """
        Reads the configuration register of the active device

        :return: The 2 bytes of configuration for the active device
        """
        self._i2c.writeto(self.address, self._config_packet[:1])
        self.config = bytearray(self._i2c.readfrom(self.address, 2))

        return self.config

    def printConfiguration(self, int_format_code="010b"):
        """
        Prints the configuration

        :return:
        """
        print(f"High Byte: {self.config[0]:#{int_format_code}}\nLow Byte:  {self.config[1]:#{int_format_code}}")

    @micropython.native
    def setActiveChannel(self, chan_num: int) -> int:
        """
        Sets the active ADC channel in the device's mux

        :param chan_num: Channel number (0-3)
        """
        # If the channel's already set to the appropriate one, don't do anything
        if (self.config[0] & 0x70) != CHAN_MAP[chan_num]:
            self.config[0] = (self.config[0] & 0x8F) | (CHAN_MAP[chan_num] >> 8)
            self.writeConfig()

        return chan_num

    @micropython.native
    def getActiveChannel(self, use_cache=True) -> int:
        """
        Returns the active channel number on the ASD1115

        :return: Channel number
        """
        if not use_cache:
            self.readConfiguration()
        return CHAN_MAP.index((self.config[0] & 0x70) << 8)

    def setSamplesPerSec(self, sps: int):
        """
        Sets the ADC samples per second

        :param sps: Samples per second bits (see the consts at the top of this module)
        """
        self.config |= sps
        self.writeConfig()

    def _getLsbValue(self) -> float:
        """
        Uses the static lookup tuples defined above to determine which LSB value maps to what FSR (Full-Scale Range)

        :return: Least significant bit value for the current FSR setting in the config
        """
        return LSB_MAP[FSR_LSB_IDX_MAP.index(self.config[0] & 0xE)]

    @micropython.native
    def readValue(self) -> int:
        """
        Reads the value of the last ADC conversion

        :return: Converted ADC value
        """
        self._reg_address[0] = ADDR_CONVERSION_REG
        self._i2c.writeto(self.address, self._reg_address)
        self._last_read_value = unpack(">h",  self._i2c.readfrom(self.address, 2))[0]
        return self._last_read_value

    @micropython.native
    def readVoltage(self) ->float:
        """
        Return the last ADC conversion value with the appropriate conversions applied to turn it into a usable voltage
        number.

        :return: Last ADC conversion in Volts
        """
        return self._getLsbValue() * self.readValue()

    def _setThresh(self, thresh_reg: int, thresh_val: int):
        """

        :param thresh_reg:
        :param thresh_val:
        :return:
        """
        self._i2c_packet[0] = thresh_reg
        self._i2c_packet[1:] = pack(">h", thresh_val)
        self._i2c.writeto(self.address, self._i2c_packet)

    def setHiThreshold(self, thresh_val: int):
        """
        Sets the comparator's high threshold

        :param thresh_val:
        :return:
        """
        self._setThresh(ADDR_HI_THRESH_REG, thresh_val)

    def setLoThreshold(self, thresh_val: int):
        """
        Sets the comparator's low threshold

        :param thresh_val:
        :return:
        """
        self._setThresh(ADDR_LO_THRESH_REG, thresh_val)


class ADS1115:

    def __init__(self,
                 i2c: I2C,
                 device_defaults: int = 0x0000|
                                        CFG_MUX_AIN0_GND|CFG_PGA_FSR_4_096|
                                        CFG_OP_MODE_CONT|CFG_DATA_RT_128SPS|
                                        CFG_COMP_MODE_WINDOW|CFG_COMP_POL_HIGH|
                                        CFG_COMP_LAT_NON|CFG_COMP_QUE_4):
        """
        Initialize the ADS1115 management library

        :param i2c: Initialized I2C class
        :param device_defaults: Config to apply to the ADS1115 at initialization
        """
        self._i2c = i2c
        self._device_defaults: bytearray = bytearray(device_defaults.to_bytes(2, "big"))
        self._devices: list[_ADS1115Device] = list()
        self._current_device_idx = 0
        self.device: _ADS1115Device or None = None

        ## Everything below is designed to prevent allocations for the operations of this class
        self._two_byte_value = bytearray(2)
        self._config_register_cache = bytearray((ADDR_CONFIG_REG, 0x0, 0x0))

        collect()  # Take any GC hits at init time

    def _read(self, num_bytes: int, address: int or None = None) -> bytes:
        """
        Sugar for reading from the current INA3221

        :param num_bytes: Number of bytes to expect/read
        :param address: (Optional) Override the address being read from

        :return: The returned bytes from the i2c bus
        """
        return self._i2c.readfrom(self.device.address if address is None else address, num_bytes)


    def _write(self, value: bytearray or bytes, valueHasAddress: int = False):
        """
        Sugar for writing to the current INA3221

        :param value: Value to write to the i2c bus
        :param valueHasAddress: Allow overriding of the current device addr stored on the class
                                (address must be first byte of `value`)
        """
        self._i2c.writeto(self.device.address if not valueHasAddress else value[0],
                          value if not valueHasAddress else value[1:])

    def addDevice(self, device_addr: int, device_name: str, config: int = None) -> int:
        """
        Adds a device to the list of ADS1115 devices under management.

        :param device_addr: Address of the ADS1115 device to be managed
        :param device_name: Nice name for the device
        :param config: Configuration to apply to the device

        :return: Internal device number
        """
        self._devices.append(
            _ADS1115Device(
                device_addr,
                device_name,
                self._i2c,
                config=config if config is not None else self._device_defaults,
                writeCfg=True
            ),
        )
        self._current_device_idx = len(self._devices)-1
        self.device = self._devices[self._current_device_idx]

        return self._current_device_idx

    def setCurrentDevice(self, device_num: int):
        """
        Sets the current device being managed

        :param device_num: Internal device number
        """
        self.device = self._devices[device_num]
