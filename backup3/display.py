"""
XRPimeter OLED display driver.

Hardware
--------
0.96" 128x64 SSD1306 OLED
I2C bus 1
I2C address 0x3C

The top of this file contains the user-editable configuration.
The rest of the file should normally not need changing.
"""

import time
from smbus2 import SMBus


# ===========================================================================
# USER CONFIGURATION
# ===========================================================================

# ---------------------------------------------------------------------------
# OLED hardware
# ---------------------------------------------------------------------------

I2C_BUS = 1
OLED_ADDRESS = 0x3C

OLED_WIDTH = 128
OLED_HEIGHT = 64


# ---------------------------------------------------------------------------
# XRPimeter information
# ---------------------------------------------------------------------------

DISPLAY_VERSION = "v1.0"


# ---------------------------------------------------------------------------
# Display labels
# ---------------------------------------------------------------------------

LABEL_TITLE = "XRPIMETER"

LABEL_XR18 = "XR18"
LABEL_USB = "USB"
LABEL_REC = "Rec"

LABEL_XR18_OK = "OK"
LABEL_XR18_WAIT = "WAIT"

LABEL_USB_OK = "OK"
LABEL_USB_NONE = "NONE"

LABEL_REC_IDLE = "IDLE"


# ---------------------------------------------------------------------------
# Main display layout
#
# Line 1 = title/time
# Line 2 = XR18/USB status
# Line 3 = scrolling path
# Line 4 = recording time
# Line 5 = recording size
# Bottom = 18 channel meter
# ---------------------------------------------------------------------------

TITLE_Y = 0
STATUS_Y = 9
SCROLL_Y = 18
REC_TIME_Y = 27
FILE_SIZE_Y = 36

# Horizontal position of the file-size line.
FILE_SIZE_INDENT = 30


# ---------------------------------------------------------------------------
# Top-right information alternation
# ---------------------------------------------------------------------------

# How long each item remains displayed.
TOP_INFO_INTERVAL = 3.0

# CPU temperature format.
CPU_TEMP_FORMAT = "{:.1f}C"


# ---------------------------------------------------------------------------
# Title positions
# ---------------------------------------------------------------------------

TITLE_X = 0
CLOCK_X = 96


# ---------------------------------------------------------------------------
# Status positions
# ---------------------------------------------------------------------------

XR18_X = 0
USB_X = 66


# ---------------------------------------------------------------------------
# Recording positions
# ---------------------------------------------------------------------------

# Recording line starts at the left edge.
#
# The elapsed and remaining time are now drawn as one string so that
# there is always a space before the remaining-time bracket.
REC_TIME_X = 0


# ---------------------------------------------------------------------------
# Marquee / scrolling path
# ---------------------------------------------------------------------------

# Pixels moved during each scroll step.
#
# Larger = faster.
SCROLL_SPEED = 1.0


# Time between scroll steps.
#
# Smaller = faster.
SCROLL_INTERVAL = 0.035


# Pause when the path first appears.
SCROLL_START_HOLD = 2.5

# Pause when the path reaches the end.
SCROLL_END_HOLD = 3.0

# Number of pixels available for the scrolling path.
SCROLL_WIDTH = OLED_WIDTH


# ---------------------------------------------------------------------------
# Time limits
# ---------------------------------------------------------------------------

# Once elapsed or remaining time exceeds this number of hours,
# display a compact >99h indication rather than allowing text to grow.
MAX_DISPLAY_HOURS = 99


# ---------------------------------------------------------------------------
# Channel meter
# ---------------------------------------------------------------------------

METER_Y = 50

METER_HEIGHT = 13
METER_BOTTOM = 63

# 18 channels × 7 pixels = 126 pixels.
#
#     5 pixels = bar
#     2 pixels = gap
#
METER_BAR_WIDTH = 5
METER_CHANNEL_SPACING = 2

METER_MIN_DB = -60.0
METER_MAX_DB = 0.0

# Reference line.
METER_REFERENCE_DB = -6.0


# ---------------------------------------------------------------------------
# Main display refresh
# ---------------------------------------------------------------------------

DISPLAY_UPDATE_INTERVAL = 0.05


# ===========================================================================
# SSD1306 COMMANDS
# ===========================================================================

DISPLAY_OFF = 0xAE
DISPLAY_ON = 0xAF

SET_DISPLAY_CLOCK = 0xD5
SET_MULTIPLEX = 0xA8
SET_DISPLAY_OFFSET = 0xD3
SET_START_LINE = 0x40

SET_CHARGE_PUMP = 0x8D
SET_MEMORY_MODE = 0x20

SET_SEGMENT_REMAP = 0xA1
SET_COM_SCAN_DIRECTION = 0xC8

SET_COM_PINS = 0xDA
SET_CONTRAST = 0x81
SET_PRECHARGE = 0xD9
SET_VCOM_DETECT = 0xDB

DISPLAY_ALL_ON_RESUME = 0xA4
NORMAL_DISPLAY = 0xA6

SET_COLUMN_ADDRESS = 0x21
SET_PAGE_ADDRESS = 0x22

OLED_PAGES = 8


# ===========================================================================
# 5x7 FONT
# ===========================================================================

FONT = {

    " ": [0x00, 0x00, 0x00, 0x00, 0x00],

    "0": [0x3E, 0x51, 0x49, 0x45, 0x3E],
    "1": [0x00, 0x42, 0x7F, 0x40, 0x00],
    "2": [0x42, 0x61, 0x51, 0x49, 0x46],
    "3": [0x21, 0x41, 0x45, 0x4B, 0x31],
    "4": [0x18, 0x14, 0x12, 0x7F, 0x10],
    "5": [0x27, 0x45, 0x45, 0x45, 0x39],
    "6": [0x3C, 0x4A, 0x49, 0x49, 0x30],
    "7": [0x01, 0x71, 0x09, 0x05, 0x03],
    "8": [0x36, 0x49, 0x49, 0x49, 0x36],
    "9": [0x06, 0x49, 0x49, 0x29, 0x1E],

    "A": [0x7E, 0x11, 0x11, 0x11, 0x7E],
    "B": [0x7F, 0x49, 0x49, 0x49, 0x36],
    "C": [0x3E, 0x41, 0x41, 0x41, 0x22],
    "D": [0x7F, 0x41, 0x41, 0x22, 0x1C],
    "E": [0x7F, 0x49, 0x49, 0x49, 0x41],
    "F": [0x7F, 0x09, 0x09, 0x09, 0x01],
    "G": [0x3E, 0x41, 0x49, 0x49, 0x7A],
    "H": [0x7F, 0x08, 0x08, 0x08, 0x7F],
    "I": [0x00, 0x41, 0x7F, 0x41, 0x00],
    "J": [0x20, 0x40, 0x41, 0x3F, 0x01],
    "K": [0x7F, 0x08, 0x14, 0x22, 0x41],
    "L": [0x7F, 0x40, 0x40, 0x40, 0x40],
    "M": [0x7F, 0x02, 0x0C, 0x02, 0x7F],
    "N": [0x7F, 0x04, 0x08, 0x10, 0x7F],
    "O": [0x3E, 0x41, 0x41, 0x41, 0x3E],
    "P": [0x7F, 0x09, 0x09, 0x09, 0x06],
    "Q": [0x3E, 0x41, 0x51, 0x21, 0x5E],
    "R": [0x7F, 0x09, 0x19, 0x29, 0x46],
    "S": [0x46, 0x49, 0x49, 0x49, 0x31],
    "T": [0x01, 0x01, 0x7F, 0x01, 0x01],
    "U": [0x3F, 0x40, 0x40, 0x40, 0x3F],
    "V": [0x1F, 0x20, 0x40, 0x20, 0x1F],
    "W": [0x7F, 0x20, 0x18, 0x20, 0x7F],
    "X": [0x63, 0x14, 0x08, 0x14, 0x63],
    "Y": [0x07, 0x08, 0x70, 0x08, 0x07],
    "Z": [0x61, 0x51, 0x49, 0x45, 0x43],

    ".": [0x00, 0x60, 0x60, 0x00, 0x00],
    ":": [0x00, 0x36, 0x36, 0x00, 0x00],
    "-": [0x08, 0x08, 0x08, 0x08, 0x08],
    "/": [0x20, 0x10, 0x08, 0x04, 0x02],
    "\\": [0x02, 0x04, 0x08, 0x10, 0x20],
    "_": [0x40, 0x40, 0x40, 0x40, 0x40],
    "%": [0x63, 0x13, 0x08, 0x64, 0x63],
    "(": [0x00, 0x1C, 0x22, 0x41, 0x00],
    ")": [0x00, 0x41, 0x22, 0x1C, 0x00],
}


# ===========================================================================
# DISPLAY CLASS
# ===========================================================================

class Display:

    def __init__(self):

        self.bus = SMBus(I2C_BUS)

        self.buffer = bytearray(
            OLED_WIDTH * OLED_PAGES
        )


        # -------------------------------------------------------------------
        # Top-right information state.
        # -------------------------------------------------------------------

        self.top_info_last_change = (
            time.monotonic()
        )

        self.top_info_show_temperature = False

        # Temperature is deliberately cached.
        #
        # It is only read when switching from the clock to temperature. 
        # Otherwise you get temp up and down whilst showing temp. Better to show a steady number.
        self.cached_cpu_temperature = None


        # -------------------------------------------------------------------
        # Marquee state.
        # -------------------------------------------------------------------

        self.scroll_text = ""
        self.scroll_offset = 0.0

        # True while waiting to reset after reaching the end.
        self.scroll_at_end = False

        self.scroll_last_update = (
            time.monotonic()
        )

        self.scroll_hold_until = (
            time.monotonic()
            + SCROLL_START_HOLD
        )


        self._initialise()

        self.clear()


    # =======================================================================
    # LOW-LEVEL I2C
    # =======================================================================

    def _command(self, value):

        self.bus.write_i2c_block_data(
            OLED_ADDRESS,
            0x00,
            [value],
        )


    def _data(self, values):

        # SMBus transfers cannot exceed 32 bytes.
        # Use 16-byte chunks for safety.

        for start in range(
            0,
            len(values),
            32,
        ):

            chunk = values[
                start:start + 16
            ]

            self.bus.write_i2c_block_data(
                OLED_ADDRESS,
                0x40,
                list(chunk),
            )


    # =======================================================================
    # SSD1306 INITIALISATION
    # =======================================================================

    def _initialise(self):

        self._command(DISPLAY_OFF)

        self._command(SET_DISPLAY_CLOCK)
        self._command(0x80)

        self._command(SET_MULTIPLEX)
        self._command(0x3F)

        self._command(SET_DISPLAY_OFFSET)
        self._command(0x00)

        self._command(SET_START_LINE)

        self._command(SET_CHARGE_PUMP)
        self._command(0x14)

        self._command(SET_MEMORY_MODE)
        self._command(0x00)

        self._command(SET_SEGMENT_REMAP)

        self._command(SET_COM_SCAN_DIRECTION)

        self._command(SET_COM_PINS)
        self._command(0x12)

        self._command(SET_CONTRAST)
        self._command(0xCF)

        self._command(SET_PRECHARGE)
        self._command(0xF1)

        self._command(SET_VCOM_DETECT)
        self._command(0x40)

        self._command(DISPLAY_ALL_ON_RESUME)

        self._command(NORMAL_DISPLAY)

        self._command(DISPLAY_ON)


    # =======================================================================
    # FRAMEBUFFER
    # =======================================================================

    def clear(self):

        self.buffer[:] = (
            b"\x00"
            * len(self.buffer)
        )

        self.show()


    def show(self):

        self._command(SET_COLUMN_ADDRESS)
        self._command(0)
        self._command(OLED_WIDTH - 1)

        self._command(SET_PAGE_ADDRESS)
        self._command(0)
        self._command(OLED_PAGES - 1)

        self._data(self.buffer)


    # =======================================================================
    # PIXELS
    # =======================================================================

    def pixel(
        self,
        x,
        y,
        on=True,
    ):

        if (
            x < 0
            or x >= OLED_WIDTH
            or y < 0
            or y >= OLED_HEIGHT
        ):
            return

        page = y // 8
        bit = y % 8

        index = (
            page * OLED_WIDTH
            + x
        )

        if on:

            self.buffer[index] |= (
                1 << bit
            )

        else:

            self.buffer[index] &= ~(
                1 << bit
            )


    # =======================================================================
    # TEXT
    # =======================================================================

    def text(
        self,
        text,
        x,
        y,
    ):
        """
        Draw 5x7 text.

        Text is clipped automatically at the right-hand edge.
        """

        cursor_x = int(x)

        for character in str(text):

            glyph = FONT.get(
                character.upper(),
                FONT[" "],
            )

            for column, bits in enumerate(
                glyph
            ):

                pixel_x = (
                    cursor_x
                    + column
                )

                if (
                    pixel_x < 0
                    or pixel_x >= OLED_WIDTH
                ):
                    continue

                for row in range(7):

                    if bits & (
                        1 << row
                    ):

                        self.pixel(
                            pixel_x,
                            y + row,
                            True,
                        )

            cursor_x += 6

            if cursor_x >= OLED_WIDTH:
                break


    # =======================================================================
    # TOP-RIGHT INFORMATION
    # =======================================================================

    def _get_cpu_temperature(self):
        """
        Read the Raspberry Pi CPU temperature once.

        Returns:
            Temperature in degrees Celsius, or None if unavailable.
        """

        try:

            with open(
                "/sys/class/thermal/thermal_zone0/temp",
                "r",
            ) as file:

                millidegrees = int(
                    file.read().strip()
                )

            return millidegrees / 1000.0

        except (
            OSError,
            ValueError,
        ):

            return None


    def _top_right_info(self):
        """
        Return either the current time or the cached CPU temperature.

        The CPU temperature is only read when switching from clock mode
        to temperature mode. This prevents the displayed temperature
        changing during the three-second temperature period.
        """

        now = time.monotonic()

        if (
            now - self.top_info_last_change
            >= TOP_INFO_INTERVAL
        ):

            self.top_info_show_temperature = (
                not self.top_info_show_temperature
            )

            self.top_info_last_change = now

            # Read temperature exactly once when entering temperature mode.
            if self.top_info_show_temperature:

                self.cached_cpu_temperature = (
                    self._get_cpu_temperature()
                )


        if self.top_info_show_temperature:

            if (
                self.cached_cpu_temperature
                is not None
            ):

                return CPU_TEMP_FORMAT.format(
                    self.cached_cpu_temperature
                )

            return "--.-C"


        return time.strftime("%H:%M")


    # =======================================================================
    # MARQUEE
    # =======================================================================

    def _set_scroll_text(
        self,
        text,
    ):

        text = str(text)

        if text != self.scroll_text:

            self.scroll_text = text

            # Always start at the beginning when the path changes.
            self.scroll_offset = 0.0

            self.scroll_at_end = False

            now = time.monotonic()

            self.scroll_last_update = now

            self.scroll_hold_until = (
                now
                + SCROLL_START_HOLD
            )


    def _update_scroll(self):

        now = time.monotonic()


        # -------------------------------------------------------------------
        # Short strings don't need scrolling.
        # -------------------------------------------------------------------

        if len(self.scroll_text) <= 21:

            self.scroll_offset = 0.0

            self.scroll_at_end = False

            return


        # -------------------------------------------------------------------
        # Wait during the pause at the beginning or end.
        # -------------------------------------------------------------------

        if now < self.scroll_hold_until:

            return


        # -------------------------------------------------------------------
        # If we have reached the end and the end pause has finished,
        # jump immediately back to the beginning.
        #
        # There is deliberately NO reverse scrolling.
        # -------------------------------------------------------------------

        if self.scroll_at_end:

            self.scroll_offset = 0.0

            self.scroll_at_end = False

            self.scroll_hold_until = (
                now
                + SCROLL_START_HOLD
            )

            self.scroll_last_update = now

            return


        # -------------------------------------------------------------------
        # Wait until the next scroll step.
        # -------------------------------------------------------------------

        if (
            now - self.scroll_last_update
            < SCROLL_INTERVAL
        ):

            return

        self.scroll_last_update = now


        text_width = (
            len(self.scroll_text)
            * 6
        )

        max_offset = max(
            0,
            text_width
            - SCROLL_WIDTH,
        )


        # -------------------------------------------------------------------
        # Scroll forwards.
        # -------------------------------------------------------------------

        self.scroll_offset += (
            SCROLL_SPEED
        )


        # -------------------------------------------------------------------
        # Reached the end.
        #
        # Stop there, hold for SCROLL_END_HOLD, then reset directly
        # to the beginning.
        # -------------------------------------------------------------------

        if (
            self.scroll_offset
            >= max_offset
        ):

            self.scroll_offset = (
                max_offset
            )

            self.scroll_at_end = True

            self.scroll_hold_until = (
                now
                + SCROLL_END_HOLD
            )


    def _draw_scrolling_text(
        self,
        text,
        y,
    ):

        self._set_scroll_text(text)

        self._update_scroll()

        offset = int(
            self.scroll_offset
        )

        cursor_x = -offset

        for character in self.scroll_text:

            glyph = FONT.get(
                character.upper(),
                FONT[" "],
            )

            for column, bits in enumerate(
                glyph
            ):

                x = (
                    cursor_x
                    + column
                )

                if (
                    x < 0
                    or x >= OLED_WIDTH
                ):
                    continue

                for row in range(7):

                    if bits & (
                        1 << row
                    ):

                        self.pixel(
                            x,
                            y + row,
                            True,
                        )

            cursor_x += 6

            if cursor_x >= OLED_WIDTH:
                break


    # =======================================================================
    # TIME FORMATTING
    # =======================================================================

    def _format_elapsed_time(
        self,
        seconds,
    ):

        seconds = max(
            0,
            int(seconds),
        )

        hours = seconds // 3600

        if hours > MAX_DISPLAY_HOURS:

            return ">99h"

        minutes = (
            seconds % 3600
        ) // 60

        secs = (
            seconds % 60
        )

        return (
            f"{hours:02d}:"
            f"{minutes:02d}:"
            f"{secs:02d}"
        )


    def _format_remaining_time(
        self,
        seconds,
    ):

        seconds = max(
            0,
            int(seconds),
        )

        hours = seconds // 3600

        if hours > MAX_DISPLAY_HOURS:

            return ">99h"

        minutes = (
            seconds % 3600
        ) // 60

        if hours > 0:

            return (
                f"{hours}h"
                f"{minutes:02d}m"
            )

        return f"{minutes}m"


    # =======================================================================
    # CHANNEL METER
    # =======================================================================

    def channel_meter(
        self,
        levels,
    ):
        """
        Draw the 18-channel OLED meter.

        At or below -6 dBFS:
            Solid bar.

        Above -6 dBFS:
            Entire bar becomes a hollow outline.

        This makes even a small excursion above -6 dBFS immediately obvious.
        """

        if levels is None:

            levels = [
                -120.0
            ] * 18


        for channel in range(18):

            if channel < len(levels):

                level = float(
                    levels[channel]
                )

            else:

                level = -120.0


            # Clamp level to the display range.

            level = max(
                METER_MIN_DB,
                min(
                    METER_MAX_DB,
                    level,
                ),
            )


            # Convert dBFS into a vertical bar height.

            fraction = (
                level
                - METER_MIN_DB
            ) / (
                METER_MAX_DB
                - METER_MIN_DB
            )

            height = int(
                fraction
                * METER_HEIGHT
            )


            # Calculate horizontal position.

            x_start = (
                channel
                * (
                    METER_BAR_WIDTH
                    + METER_CHANNEL_SPACING
                )
            )


            # Determine whether the level has crossed -6 dBFS.

            over_reference = (
                level
                > METER_REFERENCE_DB
            )


            # Draw the bar.

            for x in range(
                x_start,
                x_start
                + METER_BAR_WIDTH,
            ):

                for y in range(
                    METER_BOTTOM
                    - height
                    + 1,
                    METER_BOTTOM
                    + 1,
                ):

                    if not over_reference:

                        # Normal level: solid bar.

                        self.pixel(
                            x,
                            y,
                            True,
                        )

                    else:

                        # Above -6 dBFS:
                        # entire bar becomes a hollow outline.

                        is_left_edge = (
                            x == x_start
                        )

                        is_right_edge = (
                            x
                            == (
                                x_start
                                + METER_BAR_WIDTH
                                - 1
                            )
                        )

                        is_bottom_edge = (
                            y == METER_BOTTOM
                        )

                        if (
                            is_left_edge
                            or is_right_edge
                            or is_bottom_edge
                        ):

                            self.pixel(
                                x,
                                y,
                                True,
                            )


        # Draw the -6 dBFS reference line.

        fraction = (
            METER_REFERENCE_DB
            - METER_MIN_DB
        ) / (
            METER_MAX_DB
            - METER_MIN_DB
        )

        reference_y = (
            METER_BOTTOM
            - int(
                fraction
                * METER_HEIGHT
            )
        )


        for x in range(OLED_WIDTH):

            if x % 2 == 0:

                self.pixel(
                    x,
                    reference_y,
                    True,
                )


    # =======================================================================
    # MAIN DASHBOARD
    # =======================================================================

    def update(
        self,
        levels=None,
        xr18_connected=False,
        usb_available=False,
        usb_name="",
        recording=False,
        elapsed_seconds=0,
        recording_size_gb=0.0,
        free_space_gb=0.0,
        remaining_seconds=0,
        folder_path="",
    ):
        """
        Draw one complete dashboard frame.

        All values are optional so this can also be used during development.
        """

        self.buffer[:] = (
            b"\x00"
            * len(self.buffer)
        )


        # -------------------------------------------------------------------
        # Line 1: title and alternating clock/temperature
        # -------------------------------------------------------------------

        self.text(
            f"{LABEL_TITLE} "
            f"{DISPLAY_VERSION}",
            TITLE_X,
            TITLE_Y,
        )

        top_info = self._top_right_info()

        # Right-align the time/temperature display.

        top_info_x = (
            OLED_WIDTH
            - (
                len(top_info)
                * 6
            )
        )

        self.text(
            top_info,
            top_info_x,
            TITLE_Y,
        )


        # -------------------------------------------------------------------
        # Line 2: XR18 / USB status
        # -------------------------------------------------------------------

        xr_status = (
            LABEL_XR18_OK
            if xr18_connected
            else LABEL_XR18_WAIT
        )

        usb_status = (
            LABEL_USB_OK
            if usb_available
            else LABEL_USB_NONE
        )

        self.text(
            f"{LABEL_XR18}:{xr_status}",
            XR18_X,
            STATUS_Y,
        )

        self.text(
            f"{LABEL_USB}:{usb_status}",
            USB_X,
            STATUS_Y,
        )


        # -------------------------------------------------------------------
        # Line 3: scrolling path
        # -------------------------------------------------------------------

        self._draw_scrolling_text(
            folder_path,
            SCROLL_Y,
        )


        # -------------------------------------------------------------------
        # Line 4: recording time
        #
        # The elapsed and remaining times are now one string.
        #
        # Example:
        #
        # Rec: 01:01:12 (5h42m)
        #
        # This guarantees a space before the bracket and keeps the entire
        # recording information together.
        # -------------------------------------------------------------------

        if recording:

            elapsed_text = (
                self._format_elapsed_time(
                    elapsed_seconds
                )
            )

            remaining_text = (
                self._format_remaining_time(
                    remaining_seconds
                )
            )

            recording_time_text = (
                f"{LABEL_REC}: "
                f"{elapsed_text} "
                f"{remaining_text}"
            )

            self.text(
                recording_time_text,
                REC_TIME_X,
                REC_TIME_Y,
            )

        else:

            self.text(
                f"{LABEL_REC}: "
                f"{LABEL_REC_IDLE}",
                REC_TIME_X,
                REC_TIME_Y,
            )


        # -------------------------------------------------------------------
        # Line 5: recording size
        #
        # This is deliberately indented so it visually belongs to REC.
        # -------------------------------------------------------------------

        size_text = (
            f"{recording_size_gb:.2f}GB "
            f"({free_space_gb:.1f}GB)"
        )

        self.text(
            size_text,
            FILE_SIZE_INDENT,
            FILE_SIZE_Y,
        )


        # -------------------------------------------------------------------
        # Bottom: 18-channel miniature meter
        # -------------------------------------------------------------------

        self.channel_meter(
            levels
        )


        # -------------------------------------------------------------------
        # Send frame to OLED
        # -------------------------------------------------------------------

        self.show()

# =======================================================================
    # DIAGNOSTIC / MESSAGE SCREEN
    # =======================================================================

    def diagnostic(
        self,
        lines,
        x=0,
        y=0,
        line_spacing=8,
    ):
        """
        Display multiple diagnostic messages.

        Args:
            lines:
                List of strings to display.

            x:
                Horizontal starting position in pixels.

            y:
                Vertical starting position in pixels.

            line_spacing:
                Vertical distance between lines.

        Example:

            display.diagnostic([
                "XRPimeter v1.0",
                "BOOTING...",
                "RTC: OK",
                "RTC: NTP",
                "USB: OK",
                "XR18: OK",
                "SERVICE START",
            ])
        """

        # Clear the framebuffer.
        self.buffer[:] = (
            b"\x00"
            * len(self.buffer)
        )

        # Work out how many lines can physically fit.
        max_lines = (
            (OLED_HEIGHT - y)
            // line_spacing
        )

        # Draw each diagnostic line.
        for line_number, line in enumerate(
            lines[:max_lines]
        ):

            self.text(
                str(line),
                x,
                y + (
                    line_number
                    * line_spacing
                ),
            )

        # Send the completed frame to the OLED.
        self.show()


    # =======================================================================
    # BOOT SCREEN
    # =======================================================================

    def booting(self):

        self.buffer[:] = (
            b"\x00"
            * len(self.buffer)
        )

        self.text(
            LABEL_TITLE,
            40,
            20,
        )

        self.text(
            "BOOTING",
            40,
            35,
        )

        self.show()


    # =======================================================================
    # SHUTDOWN SCREEN
    # =======================================================================

    def shutting_down(self):

        self.buffer[:] = (
            b"\x00"
            * len(self.buffer)
        )

        self.text(
            LABEL_TITLE,
            25,
            20,
        )

        self.text(
            "SHUTTING DOWN",
            25,
            35,
        )

        self.show()


    # =======================================================================
    # CLOSE
    # =======================================================================

    def close(self):

        try:

            self._command(
                DISPLAY_OFF
            )

        finally:

            self.bus.close()


    # =======================================================================
    # SAFETY DESTRUCTOR
    # =======================================================================

    def __del__(self):

        try:

            self.bus.close()

        except Exception:

            pass