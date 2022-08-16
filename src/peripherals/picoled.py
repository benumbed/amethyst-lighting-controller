"""
picoled.py

Helper methods for the Pico's on-board LED

Copyright (C) 2022 Nick Whalen (benumbed@projectneutron.com)
"""
from machine import Pin, Timer

class PicoLed:
    def __init__(self, on_by_default = False):
        self._led = Pin(25, mode=Pin.OUT, value=on_by_default)
        self._blink_timer = Timer(mode=Timer.PERIODIC)

    def _INTHNDLR_boardLedCycle(self, _):
        self._led.value(not self._led.value())

    def on(self):
        """
        Turns the LED on (disables any existing blinking)

        """
        self._blink_timer.deinit()
        self._led.on()

    def off(self):
        """
        Turns the LED off (disables existing blinking)

        """
        self._blink_timer.deinit()
        self._led.on()


    def blink(self, period: int):
        """
        Sets up timer to blink the led with the provided period

        :param period: Period in milliseconds
        """
        self._blink_timer.init(period=period, callback=self._INTHNDLR_boardLedCycle)
