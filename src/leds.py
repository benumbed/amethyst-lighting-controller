"""
leds.py

LED control (SK6812 and WS2812) for the Pico.

Copyright (C) 2022 Nick Whalen (benumbed@projectneutron.com)
"""
from gc import collect
from machine import Pin, Timer
from micropython import const, schedule
from neopixel import NeoPixel
from peripherals.ina3221 import INA3221

DEFAULT_CHANNEL_LED_COUNT = const(100)
DEFAULT_RGB_COLOR = (128, 0, 128)
DEFAULT_RGBW_COLOR = (0, 0, 64, 96)
RGB_BPP = const(3)
RGBW_BPP = const(4)
POWER_TRIGGER_VOLTAGE = const(3)    # If the LED bus voltage is above this value, the main PSU is on
POWER_TRIGGER_CHANNEL = const(0)
CHANNEL_PIN_MAP = (2, 17, 21, 1, 20, 0, 19, 18, 16, 3, 4, 5)
CHANNEL_RGBW_LEDS = (True, False, True, True, True, True, False, False, False, True, True, True)
CHANNEL_LED_COUNTS = (59, 60, 58, 65, 65, 65, 28, 60, 60, 62, 93, 25)

class LedControl:
    def __init__(self,
                 current_monitor: INA3221,
                 pins: tuple = CHANNEL_PIN_MAP,
                 pin_rgbw_truth: tuple = CHANNEL_RGBW_LEDS,
                 pin_led_counts: tuple = CHANNEL_LED_COUNTS,
                 pin_names: tuple = None,
                 rgb_color: tuple = DEFAULT_RGB_COLOR,
                 rgbw_color: tuple = DEFAULT_RGBW_COLOR,
                 initialize_to_on: bool = False,
                 restore_state_on_main_power: bool = True):
        """
        :param current_monitor: Reference to an initialized instance of the current monitor library
        :param pins: Tuple of GPIO pins to use for RGB(W) control
        :param pin_rgbw_truth: Truth table for RGBW, `True` if the corresponding slot in `pins` has RGBW LEDs, `False`
                               otherwise
        :param pin_led_counts: Number of LEDs for each `pins` slot
        :param pin_names: The names to use for each pin (will end up as the channel names)
        :param rgb_color: The default color to initialize RGB strings to
        :param rgbw_color: The default color to initialize RGBW strings to
        :param initialize_to_on: If `True` then the LEDs will be set to their default values during initialization
        :param restore_state_on_main_power: Monitors the main power by means of the LED current monitor bus voltage and
                                            if it switches from off to on, restore the last state of the LEDs
        """
        self._rgb_pin_map = pins
        self._rgb_color_default = rgb_color
        self._rgbw_color_default = rgbw_color
        self._rgbw_truth_table = pin_rgbw_truth
        self._led_count_by_pin = pin_led_counts
        self._chan_names: tuple = pin_names

        self._current_monitor = current_monitor
        self._main_power: bool = False
        self._main_power_restore_state: bool = restore_state_on_main_power
        self._CBK_scanForPower(None)    # Make sure we set _main_power from actual hardware status
        self._power_scan_timer: Timer = Timer(-1)
        # This does an actual scan of the current sensor, so it can't be run too frequently
        self._power_scan_timer.init(period=1000, callback=self._CBK_scanForPower)

        self.rgb_pixel_strings: tuple = self._initAllPins(init_to_on=initialize_to_on)

        collect()

    @property
    def channelNames(self):
        return self._chan_names

    def printChannelNameMap(self):
        for idx in range(0, len(self.rgb_pixel_strings)-1):
            print(f"{idx}: {self._chan_names[idx]}")

    def chanIsRgbw(self, chan_num: int):
        return True if self.rgb_pixel_strings[chan_num].bpp == RGBW_BPP else False

    def _CBK_scanForPower(self, _):
        """
        This is currently just a hack that will re-run the pin init to turn the LEDs on. Will need to be changed in
        the future if/when animations and such are added.

        """
        if self._current_monitor.readChannelBusVoltage(0) >= POWER_TRIGGER_VOLTAGE:
            if not self._main_power:
                self._main_power = True
                if self._main_power_restore_state:
                    self._initAllPins(init_to_on=True)
        else:
            if self._main_power:
                self._main_power = False


    def _initAllPins(self, init_to_on = False) -> tuple:
        """
        Initializes all RGB(w) pins with the provided pin numbers and LED counts

        :param pins:
        :return: Tuples of all initialized RGB pins (NeoPixel)
        """
        rgb_pins = []
        for idx in range(0, len(self._rgb_pin_map)):
            rgb_pins.append(self.initPin(
                self._rgb_pin_map[idx],
                self._led_count_by_pin[idx],
                has_white=self._rgbw_truth_table[idx],
                default_color=None if not init_to_on
                              else (self._rgbw_color_default if self._rgbw_truth_table[idx] else self._rgb_color_default))
            )

        return tuple(rgb_pins)


    def initPin(self,
                pin: int,
                led_count: int = DEFAULT_CHANNEL_LED_COUNT,
                has_white=False,
                default_color = None,
                ) -> NeoPixel:
        """
        Sets up a RP2040 pin for RGB LED control and will flood fill the default color if set

        :param pin: Pin number
        :param led_count: Number of LEDs attached to this pin
        :param has_white: LED modules have a discrete white LED
        :param default_color: If set, will flood fill the LEDs on the provided pin with the provided color tuple
        """
        px = NeoPixel(Pin(pin, mode=Pin.OUT), led_count, bpp=4 if has_white else 3)

        if default_color is not None:
            px.fill(default_color)
            px.write()

        return px

    def setAll(self, r, g, b, w = None):
        """
        Sets all RGB LEDs to the provided color, or, when `w` is also set, will set the RGBW LEDs (not the RGB).

        :param r: Red  color value
        :param g: Green color value
        :param b: Blue color value
        :param w: White color value
        :return:
        """
        for chan_num in range(0, len(self.rgb_pixel_strings)):
            self.setChannelColor(chan_num, r, g, b, w)

    def clearAll(self):
        """
        Clears all the LEDs (sets them to 0,0,0 (,0))

        """
        self.setAll(0, 0, 0, 0)

    def setChannelColor(self, chan_num: int,  r: int, g: int, b: int, w: int = None):
        """
        Sets the color for all LEDs in a channel

        :param chan_num: Channel number to set the flood fill color for
        :param r: Red value (0-255)
        :param g: Green value (0-255)
        :param b: Blue value (0-255)
        :param w: (optional) White parameter for RGBW LEDs (0-255)
        """
        self.rgb_pixel_strings[chan_num].fill((r,g,b,w) if self.chanIsRgbw(chan_num) is not None else (r,g,b))
        self.rgb_pixel_strings[chan_num].write()

    def getChannelByName(self, name: str) -> int or None:
        """
        WARNING: This is slow by nature of doing a search in the channel name tuple
        :param name:
        :return:
        """
        if self._chan_names is None:
            return None

        return self._chan_names.index(name)
