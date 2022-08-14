from machine import Pin, I2C
from neopixel import NeoPixel
from array import array

# Lian Li AF120
# These are in sequence order, edges start at the power connector and move clockwise when looking at the side of the
# fan with the hub supports
# Hub - 8 LEDs
# Top Right - 3
# Top Left - 3
# Bottom Left - 3
# Bottom Right - 3
# 20 Total LEDs

LED_PINS = (0, 1, 2, 3, 4, 5, 16, 17, 18, 19, 20, 21)

SHUNT_RESISTOR_VALUE = 0.03

SHUNT_VOLTAGE = 1
BUS_VOLTAGE = 2

# 0 - Top 3 tri-terminals
# 1 - Mid 3 tri-terminals
# 2 - Bottom 3 tri-terminals
CURMON_INA3221_ADDRS = (0x40, 0x41, 0x42, 0x43)
# Shunt, Bus
INA3221_LSB = (0.00004, 0.008)

# 0 - Top (2 top fan LED terminals)
# 1 - Bottom (2 bottom fan LED terminals)
CURMON_INA219_ADDRS = (0x45, 0x44)
# Shunt, Bus
INA219_LSB = (0.00001, 0.004)

# LED channels 0-12 to the current monitor that handles them
CHANNEL_CURMON_DEVICE_MAP = (
    0x40, 0x40, 0x40,
    0x41, 0x41, 0x41,
    0x42, 0x42, 0x42,
    0x42, 0x42, 0x42,
)
# Maps LED channels 0-12 to their channel on the current monitor
CHANNEL_CURMON_CHAN_MAP = (
    0x1, 0x3, 0x5,
    0x1, 0x3, 0x5,
    0x1, 0x3, 0x5,
    0x1, 0x3, 0x5,
)

CHANNEL_CURMON_BUSV_MAP = (
    0x2, 0x4, 0x6,
    0x2, 0x4, 0x6,
    0x2, 0x4, 0x6,
    0x2, 0x4, 0x6,
)

i2c = I2C(1, scl=Pin(7, pull=Pin.PULL_UP), sda=Pin(6, Pin.PULL_UP), freq=400_000)
np: NeoPixel


def _resetDevice(device_num: int) -> bool:
    """
    Sends a reset signal to the selected current monitor

    :param device_num:
    :return:
    """
    # Fetch existing config
    i2c.writeto(device_num, bytes((0x0,)))
    existingCfg = i2c.readfrom(device_num, 2)

    # Set reset bit and send
    i2c.writeto(device_num, bytes((0x0, (existingCfg[0] | 0x80), existingCfg[1])))
    if i2c.readfrom(device_num, 2) == existingCfg:
        return True

    return False

def _readChipInfo(device_num: int) -> tuple:
    i2c.writeto(device_num, bytes((0xFE,)))
    manuId = i2c.readfrom(device_num, 2)
    i2c.writeto(device_num, bytes((0xFF,)))
    dieId = i2c.readfrom(device_num, 2)

    return manuId, dieId


def _readConfiguration(device_num: int) -> bytes:
    """
    Reads the configuration register of the provided device
    :param device_num:
    :return:
    """
    i2c.writeto(device_num, bytes((0x0,)))
    return i2c.readfrom(device_num, 2)

def _writeConfiguration(device_num: int, config: bytes) -> bool:
    """
    Writes the provided configuration to the device's config register

    :param device_num:
    :param config:
    :return:
    """

def _channelToDeviceRegister(channel: int) -> bytes:
    """
    Converts a LED channel number into the i2c address+channel on the appropriate current monitor board
    :param channel:
    :return:
    """
    return bytes((CHANNEL_CURMON_DEVICE_MAP[channel], CHANNEL_CURMON_CHAN_MAP[channel]))

def _getLsb(channel: int, voltageType = SHUNT_VOLTAGE) -> float:
    """
    Looks up the LSB for the given channel and voltage type

    :param channel: LED Channel
    :param voltageType: SHUNT_VOLTAGE for shunt, BUS_VOLTAGE for bus
    :return: Least significant bit value for the provided voltage type on the monitor for the given channel
    """
    return INA3221_LSB[voltageType-1] if CHANNEL_CURMON_DEVICE_MAP[channel] in CURMON_INA3221_ADDRS \
        else INA219_LSB[voltageType-1]

def _readVoltage(channel: int, voltageType = SHUNT_VOLTAGE) -> float:
    """

    :param channel: LED Channel
    :return: Actual voltage value
    """
    i2c.writeto(CHANNEL_CURMON_DEVICE_MAP[channel],
                bytes((CHANNEL_CURMON_CHAN_MAP[channel] if voltageType == SHUNT_VOLTAGE
                       else CHANNEL_CURMON_BUSV_MAP[channel],)
                      )
                )
    res = i2c.readfrom(CHANNEL_CURMON_DEVICE_MAP[channel], 2)

    # Shift first byte 8 bits to the left to create a word
    # OR new word (16b) with second byte (8b) to get word
    # Shift word 3b to the right to remove unused 0s (per datasheet)
    # Correct value for sign, if needed (MSB of first byte is set)
    # Multiply by LSB voltage value (provided via lookup tables)
    val = (((res[0] << 8) | res[1]) >> 3)
    return (val if val < 32768 else val - 65535) * _getLsb(channel, voltageType)


def readShuntVoltage(channel: int) -> float:
    """

    :param channel:
    :return:
    """
    return _readVoltage(channel, SHUNT_VOLTAGE)

def readChannelCurrent(channel: int) -> float:
    """
    Reads the current value for a channel

    :param channel:
    :return:
    """
    return readShuntVoltage(channel) / SHUNT_RESISTOR_VALUE



def readBusVoltage(channel: int) -> float:
    """

    :param channel:
    :return:
    """
    return _readVoltage(channel, BUS_VOLTAGE)


def initAllStrips(r, g, b, w):
    for pin in LED_PINS:
        initRGBStrip(pin, 144)
        applyRGBW(r,g,b,w)

def initRGBStrip(pin: int, num_leds: int = 63, rgbw = True):
    global np
    np = NeoPixel(Pin(pin, mode=Pin.OUT), num_leds, bpp=4 if rgbw else 3)

def applyRGBW(r, g, b, w):
    np.fill((r,g,b,w))
    np.write()

def applyRGB(r, g, b):
    np.fill((r,g,b))
    np.write()