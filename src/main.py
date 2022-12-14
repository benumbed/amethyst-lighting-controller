"""
main.py

Entry-point for the Amethyst LED controller

Copyright (C) 2022 Nick Whalen (purplxed@projectneutron.com)
"""
from gc import collect
from machine import I2C, Pin, SPI
from micropython import const, alloc_emergency_exception_buf

from peripherals import picoled
pico_led = picoled.PicoLed()
pico_led.blink(20)

from leds import LedControl
from peripherals import ina3221, ads1115, dht20


# TODO:
# Create a concept of groupings, so you can apply color values to the groups instead of individual channels


# Allocates an exception buffer for ISRs
alloc_emergency_exception_buf(256)

DeviceName = "Amethyst LED Controller"
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
dht: dht20.Dht20


def initializeController():
    """
    Start the controller

    :return:
    """
    global leds, i2c, current, adc, Initialized, dht

    pico_led.blink(50)
    i2c = I2C(1, scl=Pin(7), sda=Pin(6))

    pico_led.blink(100)
    current = ina3221.INA3221(i2c)
    current.addDevice(0x40, "Channels 0-2", shunt_value=SHUNT_RESISTOR_VALUE)
    current.addDevice(0x41, "Channels 3-5", shunt_value=SHUNT_RESISTOR_VALUE)
    current.addDevice(0x42, "Channels 6-8", shunt_value=SHUNT_RESISTOR_VALUE)
    current.addDevice(0x43, "Channels 9-11", shunt_value=SHUNT_RESISTOR_VALUE)

    pico_led.blink(300)
    adc = ads1115.ADS1115(i2c)
    adc.addDevice(0x48, "Temperature ADC 1")
    adc.addDevice(0x49, "Temperature ADC 2")

    pico_led.blink(500)
    dht = dht20.Dht20(i2c)

    pico_led.blink(800)
    leds = LedControl(
        current,
        pin_names=CHANNEL_NAMES,
        initialize_to_on=True)

    Initialized = True
    pico_led.on()
    collect()



if __name__ == "__main__":
    initializeController()
