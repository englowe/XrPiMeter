"""
XRPimeter OLED display test.

0.96" 128x64 SSD1306 I2C OLED
I2C address: 0x3C
"""

from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306


# ---------------------------------------------------------------------------
# OLED configuration
# ---------------------------------------------------------------------------

# Raspberry Pi I2C bus 1.
# SSD1306 module responds at 0x3C.
serial = i2c(
    port=1,
    address=0x3C,
)


# Create the 128x64 SSD1306 display object.
device = ssd1306(
    serial,
)


# ---------------------------------------------------------------------------
# Display test
# ---------------------------------------------------------------------------

with canvas(device) as draw:

    # Title
    draw.text(
        (0, 0),
        "XRPimeter",
        fill="white",
    )

    # Separator
    draw.line(
        (0, 15, 127, 15),
        fill="white",
    )

    # Test information
    draw.text(
        (0, 22),
        "OLED TEST",
        fill="white",
    )

    draw.text(
        (0, 36),
        "I2C: OK",
        fill="white",
    )

    draw.text(
        (0, 50),
        "SSD1306 128x64",
        fill="white",
    )
