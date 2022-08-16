"""
leds.py

LED control (SK6812 and WS2812) for the Pico.

Copyright (C) 2022 Nick Whalen (benumbed@projectneutron.com)
"""
from gc import collect
from machine import Pin
from micropython import const
from neopixel import NeoPixel

DEFAULT_CHANNEL_LED_COUNT = const(100)
DEFAULT_RGB_COLOR = (255, 0, 255)
DEFAULT_RGBW_COLOR = (0, 0, 112, 255)
RGB_BPP = const(3)
RGBW_BPP = const(4)

class LedControl:
    def __init__(self,
                 pins: tuple,
                 pin_rgbw_truth: tuple,
                 pin_led_counts: tuple,
                 pin_names: tuple = None,
                 rgb_color: tuple = DEFAULT_RGB_COLOR,
                 rgbw_color: tuple = DEFAULT_RGBW_COLOR):
        """

        :param pins: Tuple of GPIO pins to use for RGB(W) control
        :param pin_rgbw_truth: Truth table for RGBW, `True` if the corresponding slot in `pins` has RGBW LEDs, `False`
                               otherwise
        :param pin_led_counts: Number of LEDs for each `pins` slot
        :param pin_names: The names to use for each pin (will end up as the channel names)
        """
        self._rgb_color_default = rgb_color
        self._rgbw_color_default = rgbw_color
        self.rgb_pixel_strings: tuple = self._initAllPins(pins, pin_rgbw_truth, pin_led_counts)
        self._chan_names: tuple = pin_names

        collect()

    @property
    def channelNames(self):
        return self._chan_names

    def printChannelNameMap(self):
        for idx in range(0, len(self.rgb_pixel_strings)-1):
            print(f"{idx}: {self._chan_names[idx]}")

    def chanIsRgbw(self, chan_num: int):
        return True if self.rgb_pixel_strings[chan_num].bpp == RGBW_BPP else False

    def _initAllPins(self, pins: tuple, pin_rgbw_truth: tuple, pin_led_counts: tuple) -> tuple:
        """
        Initializes all RGB(w) pins with the provided pin numbers and LED counts

        :param pins:
        :param pin_rgbw_truth:
        :param pin_led_counts:
        :return: Tuples of all initialized RGB pins (NeoPixel)
        """
        rgb_pins = []
        for idx in range(0, len(pins)):
            rgb_pins.append(self.initPin(
                pins[idx],
                pin_led_counts[idx],
                has_white=pin_rgbw_truth[idx],
                default_color=self._rgbw_color_default if pin_rgbw_truth[idx] else self._rgb_color_default)
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
