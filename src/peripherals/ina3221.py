"""
ina3221.py

Provides a class to manage INA3221 current monitors from TI. NOTE: This class is built around the 3-channel INA3221
boards commonly available on Amazon and Aliexpress. Chances are any INA3221 implementation will work, but the above
boards were what were tested against.

Copyright (C) 2022 Nick Whalen (benumbed@projectneutron.com)
"""
import micropython
from array import array
from machine import I2C
from math import floor
from micropython import const
from gc import collect
from struct import unpack

DEVICE_SHUNT_LSB = 0.00004
DEVICE_BUS_LSB = 0.008

SHUNT_VOLTAGE = const(1)
BUS_VOLTAGE = const(2)

ADDR_CONFIG_REG = const(0x0)
CFG_REG_DATA_BEGIN = const(1)
MANUFACTURER_REGISTER = bytes((0xFE,))
MANUFACTURER_VALUE = const(0x5449)
DIE_ID_REGISTER = bytes((0xFF,))
DIE_ID_VALUE = const(0x3220)

VOLT_READ_CFG_DEVICE = const(0)
VOLT_READ_CFG_DEV_CHANNEL = const(1)
VOLT_READ_CFG_I2C_DATA = const(2)

# Device Reset
CONFIG_RESET = const(0x8000)
# Channel Enable/Disable
CH1_ENABLE = const(0x4000)
CH2_ENABLE = const(0x2000)
CH3_ENABLE = const(0x1000)
# Averaging Mode
AVERAGING_1_SAMPLES = const(0x0)
AVERAGING_4_SAMPLES = const(0x200)
AVERAGING_16_SAMPLES = const(0x400)
AVERAGING_64_SAMPLES = const(0x600)
AVERAGING_128_SAMPLES = const(0x800)
AVERAGING_256_SAMPLES = const(0xA00)
AVERAGING_512_SAMPLES = const(0xC00)
AVERAGING_1024_SAMPLES = const(0xE00)
# Bus Voltage Conversion Time
BUS_CONVERSION_TIME_140us = const(0x0000)
BUS_CONVERSION_TIME_204us = const(0x40)
BUS_CONVERSION_TIME_332us = const(0x80)
BUS_CONVERSION_TIME_588us = const(0xC0)
BUS_CONVERSION_TIME_1_1ms = const(0x100)
BUS_CONVERSION_TIME_2_116ms = const(0x140)
BUS_CONVERSION_TIME_4_156ms = const(0x180)
BUS_CONVERSION_TIME_8_244ms = const(0x1C0)
# Shunt Voltage Conversion Time
SHUNT_CONVERSION_TIME_140us = const(0x0000)
SHUNT_CONVERSION_TIME_204us = const(0x8)
SHUNT_CONVERSION_TIME_332us = const(0x10)
SHUNT_CONVERSION_TIME_588us = const(0x18)
SHUNT_CONVERSION_TIME_1_1ms = const(0x20)
SHUNT_CONVERSION_TIME_2_116ms = const(0x28)
SHUNT_CONVERSION_TIME_4_156ms = const(0x30)
SHUNT_CONVERSION_TIME_8_244ms = const(0x38)

# Operating Modes
OPMODE_SS_SHUNT = const(0x1)
OPMODE_SS_BUS = const(0x2)
OPMODE_SS_SHUNT_BUS = const(0x3)
OPMODE_POWER_DOWN = const(0x4)
OPMODE_CONT_SHUNT = const(0x5)
OPMODE_CONT_BUS = const(0x6)
OPMODE_CONT_SHUNT_BUS = const(0x7)



class INACommonError(Exception): pass
class INADoesNotExistError(INACommonError): pass

class _INADevice:
    """
    Encapsulates information about an INA3221 device

    """
    def __init__(self, addr: int, name: str, shunt_resistor_value: float):
        self.address: int = addr
        self.name: str = name
        self.channel_voltages = array("f", (0.0, 0.0, 0.0))
        self.shunt_resistor_values = array("f", (shunt_resistor_value, shunt_resistor_value, shunt_resistor_value))

    def setShuntResistorValue(self, channel: int, value: float):
        """
        Sets the shunt resistor value for a voltage channel. Note `channel` is the zero-indexed channel number local
        to this device (not the register address).

        :param channel: Local channel id
        :param value: The shunt resistor's value in ohms
        """
        self.shunt_resistor_values[channel] = value

class INA3221:
    def __init__(self,
                 i2c: I2C,
                 device_defaults: int = 0x0000|
                                        CH1_ENABLE|CH2_ENABLE|CH3_ENABLE|
                                        AVERAGING_128_SAMPLES|
                                        BUS_CONVERSION_TIME_1_1ms|SHUNT_CONVERSION_TIME_1_1ms|
                                        OPMODE_CONT_SHUNT_BUS):
        """
        Initialize the INA3221 management library

        :param i2c: Initialized I2C class
        :param device_defaults: Config to apply to the INA3221 at initialization
        """
        self._i2c = i2c
        self._device_defaults: int = device_defaults
        self._devices: list[_INADevice] = list()

        ## Everything below is designed to prevent allocations for the operations of this class
        self._channel_id_cache = bytearray(1)   # Helps prevent allocations when talking to INA channels
        self._two_byte_value = bytearray(2)
        self._shifted_voltage = bytearray(2)
        self._config_register_cache = bytearray((ADDR_CONFIG_REG, 0x0, 0x0))
        self._active_device_addr = 0x40
        self._volt_read_cfg = bytearray(4)

        collect()   # Take any GC hits at init time

    def _configure(self, device_addr: int, options: int):
        """
        Configures the device

        :param options:
        :return:
        """
        i2c_packet = bytearray((device_addr, ADDR_CONFIG_REG))
        i2c_packet += options.to_bytes(2, "big")
        self._write(i2c_packet, valueHasAddress=True)

    @micropython.native
    @property
    def _voltageStorage(self) -> array:
        return self._devices[
            self._volt_read_cfg[VOLT_READ_CFG_DEVICE]
        ].channel_voltages[
            self._volt_read_cfg[VOLT_READ_CFG_DEV_CHANNEL]
        ]

    @micropython.native
    @_voltageStorage.setter
    def _voltageStorage(self, voltage):
        self._devices[
            self._volt_read_cfg[VOLT_READ_CFG_DEVICE]
        ].channel_voltages[
            self._volt_read_cfg[VOLT_READ_CFG_DEV_CHANNEL]
        ] = voltage

    @micropython.native
    @property
    def _voltageShuntValues(self) -> array:
        return self._devices[self._volt_read_cfg[0]].shunt_resistor_values

    def _getDeviceIdxFromChannel(self, channel_id: int) -> int:
        """
        Determines which device a channel belongs to

        :param channel_id: Global channel id

        :return: The global device id (not the device's i2c address)
        """
        return floor(channel_id / 3) # All INA3221s have 3 channels

    def _getDeviceLocalChannelIdx(self, device_id: int, channel_id: int) -> int:
        """
        Figures out what the channel index for the provided device is based on the global index

        :param device_id: The device the channel is located on
        :param channel_id: The global channel id to use for conversion

        :return: The local channel ID on the device object (not the register on the device)
        """
        return channel_id - (((device_id + 1) * 3) - 3)

    def addDevice(self, device_addr: int, device_name: str, shunt_value: float = 0.1, config: int = None) -> int:
        """
        Adds a device to the list of INA3221 devices under management. If your channels have differing shunt resistor
        values, you will need to call `setChannelShuntResistor()` on the appropriate channel

        :param device_addr: Address of the new INA3221 device to be managed
        :param device_name: Nice name for the device
        :param shunt_value: Default shunt resistor value, in ohms
        :param config: Configuration to apply to the device

        :return: Internal device number
        """
        self._devices.append(_INADevice(device_addr, device_name, shunt_value))
        device_id = len(self._devices)-1
        try:
            self._configure(device_addr, config if config is not None else self._device_defaults)
        except OSError as e:
            if e.errno == 5:
                raise INADoesNotExistError(f"Device {device_addr:#x} does not exist on the i2c bus")
            raise

        return device_id

    def setChannelShuntResistor(self, channel_id: int, shunt_resistor_value: float):
        """
        Sets the shut resistor value (in ohms) for the specified channel

        :param channel_id: Channel id to set the shunt resistor value for
        :param shunt_resistor_value: Shunt resistor value in ohms
        """
        device_id = self._getDeviceIdxFromChannel(channel_id)
        self._devices[device_id]. \
            shunt_resistor_values[self._getDeviceLocalChannelIdx(device_id, channel_id)] = shunt_resistor_value

    def getDeviceAddr(self, device_id: int) -> int:
        """
        Translates an internal device ID to that device's I2C address

        :param device_id: ID of the device to fetch the i2c address of

        :return: i2c address of the device
        """
        return self._devices[device_id].address

    def setActiveDevice(self, device_id: int):
        """
        Sets the active device that is being operated against

        :param device_id: ID of device to switch operations to
        """
        addr = self.getDeviceAddr(device_id)
        if addr == self._active_device_addr:
            return
        self._active_device_addr = addr

    @micropython.native
    def _read(self, num_bytes: int, address: int or None = None) -> bytes:
        """
        Sugar for reading from the current INA3221

        :param num_bytes: Number of bytes to expect/read
        :param address: (Optional) Override the address being read from

        :return: The returned bytes from the i2c bus
        """
        return self._i2c.readfrom(self._active_device_addr if address is None else address, num_bytes)

    @micropython.native
    def _write(self, value: bytearray or bytes, valueHasAddress: int = False):
        """
        Sugar for writing to the current INA3221

        :param value: Value to write to the i2c bus
        :param valueHasAddress: Allow overriding of the current device addr stored on the class
                                (address must be first byte of `value`)
        """
        self._i2c.writeto(self._active_device_addr if not valueHasAddress else value[0],
                          value if not valueHasAddress else value[1:])

    @micropython.native
    def _setVoltReadCfgFromChan(self, channel_id: int, voltage_type: int):
        """
        Translates an internal channel ID to the device ID and channel number for that device

        :param channel_id: Channel ID to rest the read config for voltages on
        :param voltage_type: SHUNT_VOLTAGE or BUS_VOLTAGE -- Adjusts the device register addresses
        """
        # The math below gives us the internal index of the device (0-based) based on the channel id
        self._volt_read_cfg[VOLT_READ_CFG_DEVICE] = self._getDeviceIdxFromChannel(channel_id)
        # The zero-indexed channel, local to the device struct
        self._volt_read_cfg[VOLT_READ_CFG_DEV_CHANNEL] = self._getDeviceLocalChannelIdx(
            self._volt_read_cfg[VOLT_READ_CFG_DEVICE], channel_id)
        # I2C address of the device
        self._volt_read_cfg[VOLT_READ_CFG_I2C_DATA] = self._devices[self._volt_read_cfg[VOLT_READ_CFG_DEVICE]].address


        # The following is an explanation of the fuckery at the end of the return statement. The computation is packed
        # to avoid allocs.

        # Gives us 0-indexed channel ID on the device (the shunt register without the offset adjustment)
        # zero_indexed_channel_id = channel_id - (((device_idx+1) * 3) - 3)

        # Creates the offset to net the actual register address we need
        # (zero_indexed_channel_id * 2) + 1 # gives us the actual register ID on the device

        # Voltage register address on the target device
        self._volt_read_cfg[VOLT_READ_CFG_I2C_DATA+1] = int((self._volt_read_cfg[1] * 2) + voltage_type)

    @micropython.native
    def _resetDevice(self):
        """
        Sends a reset signal to the selected current monitor

        """
        self._config_register_cache[CFG_REG_DATA_BEGIN:] = self._readConfiguration()

        self._config_register_cache[CFG_REG_DATA_BEGIN] |= 0x80  # Set the reset bit in the first byte

        self._writeConfiguration(self._config_register_cache) # Device resets as soon as this is written

    def _validateChipInfo(self) -> bool:
        """
        Validate that the chip info matches the information from TI in the INA3221 datasheet (8.6.2.[19,20])

        :return: True if the chip validated successfully, False otherwise
        """
        self._write(MANUFACTURER_REGISTER)
        if self._read(2) != MANUFACTURER_VALUE:
            return False

        self._write(DIE_ID_REGISTER)
        if self._read(2) != DIE_ID_VALUE:
            return False

        return True

    @micropython.native
    def _readConfiguration(self) -> bytes:
        """
        Reads the configuration register of the active device

        :return: The 2 bytes of configuration for the active device
        """
        self._write(bytes(ADDR_CONFIG_REG, ))
        self._config_register_cache[1:] = self._read(2)

        return self._config_register_cache[1:]

    @micropython.native
    def _writeConfiguration(self, config: bytes):
        """
        Writes the provided configuration to the active device's config register.

        :param config: 2 bytes of configuration bits
        """
        self._config_register_cache = config
        self._write(self._config_register_cache)

    @micropython.native
    def _readVoltage(self, channel: int, voltageType = SHUNT_VOLTAGE) -> float:
        """
        Reads a channel's voltage. NOTE: this method computes the appropriate device and voltage registers on the fly
        and will read those instead of using `self._current_device_addr`. This is because this method has no concept
        of devices, merely internal channel IDs.

        To anyone reading this other than me... I am sorry. This is designed to be run in a tight loop and, as a result,
        it avoids allocations wherever possible. This has led to the fuckery you now behold below.

        :param channel: Internal channel number

        :return: Actual voltage value (in Volts, not milliVolts)
        """
        self._setVoltReadCfgFromChan(channel, voltageType)

        self._write(self._volt_read_cfg[VOLT_READ_CFG_I2C_DATA:], valueHasAddress=True)
        self._two_byte_value = self._read(2, address=self._volt_read_cfg[VOLT_READ_CFG_I2C_DATA])

        # Unpacks the 2-byte value into a signed short, then removes the 3 useless LSB (per datasheet)
        self._shifted_voltage = unpack(">h", self._two_byte_value)[0] >> 3

        self._voltageStorage = self._shifted_voltage * \
                               (DEVICE_SHUNT_LSB if voltageType == SHUNT_VOLTAGE else DEVICE_BUS_LSB)

        return self._devices[self._volt_read_cfg[VOLT_READ_CFG_DEVICE]] \
            .channel_voltages[self._volt_read_cfg[VOLT_READ_CFG_DEV_CHANNEL]]

    @micropython.native
    def readChannelShuntVoltage(self, channel: int) -> float:
        """
        Reads the shunt voltage for the given channel

        :param channel: Global channel ID

        :return: The voltage for the given channel, in Volts
        """
        return self._readVoltage(channel, SHUNT_VOLTAGE)

    @micropython.native
    def readChannelCurrent(self, channel: int) -> float:
        """
        Reads the shunt voltage for a channel and converts it to current in Amperes

        :param channel: Global channel ID

        :return: The current for the channel, in Amperes
        """
        return self.readChannelShuntVoltage(channel) \
               / self._voltageShuntValues[self._volt_read_cfg[VOLT_READ_CFG_DEV_CHANNEL]]

    @micropython.native
    def readChannelBusVoltage(self, channel: int) -> float:
        """
        Reads the bus voltage from the given channel

        :param channel: Global channel ID

        :return: The bus voltage for a channel, in Volts
        """
        return self._readVoltage(channel, BUS_VOLTAGE)
