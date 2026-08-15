"""
XRPimeter WS2812 hardware test.

Raspberry Pi 5
GPIO10 / SPI0 MOSI
        |
        v
SN74AHCT125
        |
        v
WS2812 strip

20 LEDs total.
"""

import time

from rpi5_ws2812.ws2812 import (
    Color,
    WS2812SpiDriver,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

LED_COUNT = 20

SPI_BUS = 0
SPI_DEVICE = 0

BRIGHTNESS = 0.005


# ---------------------------------------------------------------------------
# Initialise the LED strip
# ---------------------------------------------------------------------------

driver = WS2812SpiDriver(
    spi_bus=SPI_BUS,
    spi_device=SPI_DEVICE,
    led_count=LED_COUNT,
)

strip = driver.get_strip()

strip.set_brightness(
    BRIGHTNESS
)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def clear():
    """Turn every LED off."""

    strip.clear()
    strip.show()


def set_all(red, green, blue):
    """Set every LED to the same colour."""

    strip.set_all_pixels(
        Color(red, green, blue)
    )

    strip.show()


def set_one(index, red, green, blue):
    """Set one LED to a colour."""

    strip.set_pixel_color(
        index,
        Color(red, green, blue)
    )

    strip.show()


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

try:

    print()
    print("============================")
    print("XRPimeter WS2812 test")
    print("============================")
    print()

    print(
        f"LED count: {LED_COUNT}"
    )

    print(
        f"Brightness: {BRIGHTNESS:.0%}"
    )

    print()


    # ---------------------------------------------------------------
    # Start from a known state
    # ---------------------------------------------------------------

    print("Clearing LEDs...")

    clear()

    time.sleep(1)


    # ---------------------------------------------------------------
    # All green
    # ---------------------------------------------------------------

    print("All LEDs green...")

    set_all(
        0,
        255,
        0
    )

    time.sleep(2)


    # ---------------------------------------------------------------
    # Individual LED test
    # ---------------------------------------------------------------

    print()
    print("Testing individual LEDs...")
    print()

    for index in range(LED_COUNT):

        clear()

        set_one(
            index,
            0,
            255,
            0
        )

        print(
            f"LED {index + 1:02d} / {LED_COUNT}"
        )

        time.sleep(0.25)


    # ---------------------------------------------------------------
    # Progressive fill
    # ---------------------------------------------------------------

    print()
    print("Progressive fill...")
    print()

    clear()

    for index in range(LED_COUNT):

        set_one(
            index,
            0,
            255,
            0
        )

        time.sleep(0.1)


    # ---------------------------------------------------------------
    # Colour tests
    # ---------------------------------------------------------------

    print()
    print("Red...")

    set_all(
        255,
        0,
        0
    )

    time.sleep(1)


    print("Green...")

    set_all(
        0,
        255,
        0
    )

    time.sleep(1)


    print("Blue...")

    set_all(
        0,
        0,
        255
    )

    time.sleep(1)


    print("White...")

    set_all(
        255,
        255,
        255
    )

    time.sleep(1)


    # ---------------------------------------------------------------
    # Final clear
    # ---------------------------------------------------------------

    print()
    print("Clearing LEDs...")

    clear()

    print()
    print("Test complete.")
    print()


except KeyboardInterrupt:

    print()
    print("Test interrupted.")


finally:

    # Always leave the strip off.
    clear()
