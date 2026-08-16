"""
Minimal raw I2C OLED test.

Attempts to initialise a 128x64 SSD1306 at address 0x3C
and fills the entire display white.
"""

import time
from smbus2 import SMBus


I2C_BUS = 1
OLED_ADDRESS = 0x3C


def command(bus, value):
    """
    Send one command byte to the OLED.
    """
    bus.write_i2c_block_data(
        OLED_ADDRESS,
        0x00,
        [value],
    )


def data(bus, values):
    """
    Send display data to the OLED in small I2C chunks.
    """

    for start in range(0, len(values), 16):

        chunk = values[start:start + 16]

        bus.write_i2c_block_data(
            OLED_ADDRESS,
            0x40,
            chunk,
        )


with SMBus(I2C_BUS) as bus:

    # Give the display time to power up.
    time.sleep(0.1)

    # Display OFF.
    command(bus, 0xAE)

    # Set display clock.
    command(bus, 0xD5)
    command(bus, 0x80)

    # Multiplex ratio: 64 rows.
    command(bus, 0xA8)
    command(bus, 0x3F)

    # Display offset.
    command(bus, 0xD3)
    command(bus, 0x00)

    # Start line.
    command(bus, 0x40)

    # Charge pump.
    command(bus, 0x8D)
    command(bus, 0x14)

    # Memory addressing mode.
    command(bus, 0x20)
    command(bus, 0x00)

    # Segment remap.
    command(bus, 0xA1)

    # COM scan direction.
    command(bus, 0xC8)

    # COM pins.
    command(bus, 0xDA)
    command(bus, 0x12)

    # Contrast.
    command(bus, 0x81)
    command(bus, 0xCF)

    # Pre-charge.
    command(bus, 0xD9)
    command(bus, 0xF1)

    # VCOM detect.
    command(bus, 0xDB)
    command(bus, 0x40)

    # Entire display follows RAM.
    command(bus, 0xA4)

    # Normal display.
    command(bus, 0xA6)

    # Display ON.
    command(bus, 0xAF)

    # Set column range.
    command(bus, 0x21)
    command(bus, 0x00)
    command(bus, 0x7F)

    # Set page range.
    command(bus, 0x22)
    command(bus, 0x00)
    command(bus, 0x07)

    # Fill all 1024 display bytes with 0xFF.
    for _ in range(8):

        # 128 bytes per page.
        data(
            bus,
            [0xFF] * 128,
        )

print("OLED raw test complete.")
