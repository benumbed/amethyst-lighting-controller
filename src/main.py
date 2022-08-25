from gc import collect
from machine import I2C, Pin, SPI
from micropython import const, alloc_emergency_exception_buf

from peripherals import picoled
pico_led = picoled.PicoLed()
pico_led.blink(20)

from leds import LedControl
from peripherals import ina3221, ads1115


# TODO:
# Create a concept of groupings, so you can apply color values to the groups instead of individual channels


# Allocates an exception buffer for ISRs
alloc_emergency_exception_buf(256)

Initialized = False

# Lian Li AF120/Infinity
# These are in sequence order, edges start at the power connector and move clockwise when looking at the side of the
# fan with the hub supports
# Hub - 8 LEDs
# Top Right - 3
# Top Left - 3
# Bottom Left - 3
# Bottom Right - 3
# 20 Total LEDs

CHANNEL_NAMES = (
    "Top Left",                 # 0
    "Top Fans",                 # 1
    "Top Right",                # 2
    "Back Left",                # 3
    "Front Left",               # 4
    "Front Right",              # 5
    "Panel Strip",              # 6
    "Side Fans",                # 7
    "Bottom Fans",              # 8
    "Bottom Left",              # 9
    "Bottom Back and Right",    # 10
    "Bottom Front"              # 11
)
CHANNEL_PIN_MAP = (2, 17, 21, 1, 20, 0, 19, 18, 16, 3, 4, 5)
CHANNEL_RGBW_LEDS = (True, False, True, True, True, True, False, False, False, True, True, True)
CHANNEL_LED_COUNTS = (59, 60, 58, 65, 65, 65, 28, 60, 60, 62, 93, 25)
RGB_DEFAULT_COLOR = (128, 0, 128)
RGBW_DEFAULT_COLOR = (0, 0, 64, 96)

SHUNT_RESISTOR_VALUE = 0.03  # All 4 current monitor boards use 0.03 Ohm shunts
CURRENT_MON_CRIT_PINS = (11, 10, 26, 22)
ADC_ALERT_PINS = (9, 8)

                    # SCL, SDA
EXTERNAL_I2C_PINS = (15, 14)
                    # SCK, MOSI, MISO, CS
EXTERNAL_SPI_PINS = (14, 15, 12, 13)

leds: LedControl
current: ina3221.INA3221
adc: ads1115.ADS1115
i2c: I2C



def initializeController():
    """
    Start the controller

    :return:
    """
    global leds, i2c, current, adc, Initialized

    pico_led.blink(50)
    i2c = I2C(1, scl=Pin(7), sda=Pin(6))

    pico_led.blink(100)
    current = ina3221.INA3221(i2c)
    current.addDevice(0x40, "Channels 0-2", shunt_value=SHUNT_RESISTOR_VALUE)
    current.addDevice(0x41, "Channels 3-5", shunt_value=SHUNT_RESISTOR_VALUE)
    current.addDevice(0x42, "Channels 6-8", shunt_value=SHUNT_RESISTOR_VALUE)
    current.addDevice(0x43, "Channels 9-11", shunt_value=SHUNT_RESISTOR_VALUE)

    # pico_led.blink(300)
    # adc = ads1115.ADS1115(i2c)
    # adc.addDevice(0x48)


    pico_led.blink(800)
    leds = LedControl(
        CHANNEL_PIN_MAP,
        CHANNEL_RGBW_LEDS,
        CHANNEL_LED_COUNTS,
        CHANNEL_NAMES,
        RGB_DEFAULT_COLOR,
        RGBW_DEFAULT_COLOR,
        initialize_to_on=True)

    Initialized = True
    pico_led.on()
    collect()



if __name__ == "__main__":
    initializeController()
