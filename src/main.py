import micropython

from peripherals import picoled
pico_led = picoled.PicoLed()
pico_led.blink(20)
from leds import LedControl



# Allocates an exception buffer for ISRs
micropython.alloc_emergency_exception_buf(256)

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
    "Top Left",
    "Top Fans",
    "Top Right",
    "Back Left",
    "Front Left",
    "Front Right",
    "Panel Strip"
    "Side Fans",
    "Bottom Fans",
    "Bottom Back and Right",
    "Bottom Left",
    "Bottom Front"
)
CHANNEL_PIN_MAP = (2, 17, 21, 1, 20, 0, 19, 18, 16, 3, 4, 5)
CHANNEL_RGBW_LEDS = (True, False, True, True, True, True, False, False, False, True, True, True)
CHANNEL_LED_COUNTS = (59, 60, 58, 65, 65, 65, 28, 60, 60, 93, 62, 25)
RGB_DEFAULT_COLOR = (255, 0, 255)
RGBW_DEFAULT_COLOR = (0, 0, 112, 255)

leds: LedControl

def initializeController():
    """
    Start the controller

    :return:
    """
    global leds
    leds = LedControl(
        CHANNEL_PIN_MAP,
        CHANNEL_RGBW_LEDS,
        CHANNEL_LED_COUNTS,
        CHANNEL_NAMES,
        RGB_DEFAULT_COLOR,
        RGBW_DEFAULT_COLOR)

pico_led.blink(100)
initializeController()

pico_led.on()