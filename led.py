"""
XRPimeter LED controller. Connect WS2812 LED strip to GPIO10 (MOSI) which is pin 19 on the Raspberry Pi 5.

Physical LED order
------------------

    LED 1  = REC
    LED 2  = USB
    LED 3  = CH01
    LED 4  = CH02
    ...
    LED 20 = CH18


Normal operation
----------------

REC LED:

    Not recording = OFF
    Recording     = breathing green

    Although a normal recording LED (say, on a camera) blinks red when recording, we want a more confident glance
    over to the whole panel and see no red LEDs if everything is OK.

    A 'breathing' green LED for recording gives positive feedback it is recording.
    When not recording the LED is off.

    As the XrPiMeter automatically starts recording on USB insertion,
    there is no start/stop record button, so no action needed, hence why no red LED.

    Also red could be mistaken as recording (like some phones/cameras show a solid red indication when recording).


USB LED:

    USB present   = green
    USB absent    = red

    The USB LED is a little different to the REC LED, in that action may be needed.
    For example, a USB stick has been inserted and is not writable, or not detected, or is just simply broken.

    The user needs to see it is OK or not OK, hence the green/red LED status for the USB.


Channel LEDs:

    Not recording      = OFF
    Recording, quiet   = dim green
    Increasing level   = progressively brighter green
    -20 dBFS and up   = bright green
    -10 dBFS           = green / amber transition
    -6 dBFS            = amber / red transition
    > -6 dBFS          = red
    >= -0.1 dBFS      = flashing red


System status
-------------

If the pi is used with no OLED display, only the faint glow of the Pi's internal LED shows what state it is in.
Which is usually a mistery - has it booted OK? Is it working? What does pale green mean?

So lets use our LEDs to give some actual feedback. Boot status, shutdown status etc.


Boot:

    Green sweep from LED 1 to LED 20.


Shutdown:

    Green sweep from LED 20 back to LED 1.


These animations are deliberately contained within this module so that
the rest of XRPimeter does not need to know anything about the WS2812
hardware or its animation timing.
"""


import math
import time


from rpi5_ws2812.ws2812 import (
    Color,
    WS2812SpiDriver,
)


# ---------------------------------------------------------------------------
# Hardware configuration
# ---------------------------------------------------------------------------

LED_COUNT = 20

# Raspberry Pi 5 SPI0.
#
# GPIO10 is SPI0 MOSI and is connected to the SN74AHCT125 level shifter.
SPI_BUS = 0
SPI_DEVICE = 0


# Maximum overall LED brightness.
#
# This limits the brightness applied by the WS2812 driver.
#
# Eg. BRIGHTNESS = 0.2 = 20%
#
# Be careful drawing too much current if using the 5V header of the pi.
# At full brightness of 1 (100%), 20 WS2812 LEDs displaying white draws
# up to 1.2A at 5V!
#
# At 0.2 (20%) in theory 20 LEDs at full white draws 240mA at 5V.
#
# Using the XrPiMeter at gigs, I find 0.005 (0.5%) is a good low brightness
# indication level for the LEDs.
#
# There is no official pi doc that states max draw from the 5V header.
#
BRIGHTNESS = 0.04


# ---------------------------------------------------------------------------
# LED positions
# ---------------------------------------------------------------------------

# Zero-based LED indexes.
#
# By starting the LED string with REC and USB status, a minimum build can
# be built using just two WS2812 LEDs and no channel meter LEDs connected.
#
# The two LEDs will work fine; the pi will still send data for all 20 LEDs
# but it won't affect the operation of the first two LEDs if the rest are
# missing.

REC_LED = 0
USB_LED = 1

CHANNEL_LED_START = 2


# ---------------------------------------------------------------------------
# Meter thresholds
# ---------------------------------------------------------------------------

# The useful green metering range.
#
# Anything below GREEN_FLOOR is treated as very quiet.
GREEN_FLOOR = -60.0

# At this level the green channel LED reaches maximum green brightness.
GREEN_MAX_LEVEL = -20.0

# Amber begins at this level.
GREEN_LEVEL = -10.0

# Red begins above this level.
AMBER_LEVEL = -6.0
RED_LEVEL = -6.0

# Treat levels approaching 0 dBFS as clipping.
CLIP_LEVEL = -0.1


# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------

GREEN = Color(
    0,
    255,
    0,
)
DIM_GREEN = Color(
    0,
    70,
    0,
)

AMBER = Color(
    255,
    100,
    0,
)

RED = Color(
    255,
    0,
    0,
)

DIM_RED = Color(
    70,
    0,
    0,
)

OFF = Color(
    0,
    0,
    0,
)


# ---------------------------------------------------------------------------
# LEDs class
# ---------------------------------------------------------------------------

class LEDs:
    """
    Controls the XRPimeter WS2812 LED strip.

    The class is responsible for:

        - WS2812 hardware
        - REC indicator
        - USB indicator
        - 18 channel level indicators
        - boot animation
        - shutdown animation
        - system status indication

    It deliberately knows nothing about:

        - XR18
        - ALSA
        - USB mounting
        - recording files
        - audio measurement
    """


    def __init__(self):

        # ---------------------------------------------------------------
        # Initialise the Raspberry Pi 5 WS2812 driver.
        # ---------------------------------------------------------------

        self.driver = WS2812SpiDriver(
            spi_bus=SPI_BUS,
            spi_device=SPI_DEVICE,
            led_count=LED_COUNT,
        )

        self.strip = self.driver.get_strip()

        self.strip.set_brightness(
            BRIGHTNESS
        )


        # ---------------------------------------------------------------
        # Animation timing
        # ---------------------------------------------------------------

        # REC breathing animation.
        self.breath_start = time.monotonic()

        # Channel clipping flash.
        self.clip_flash_start = time.monotonic()


        # ---------------------------------------------------------------
        # Initial state
        # ---------------------------------------------------------------

        self.clear()


    # -----------------------------------------------------------------------
    # Basic control
    # -----------------------------------------------------------------------

    def clear(self):
        """
        Turn all LEDs off immediately.
        """

        self.strip.clear()
        self.strip.show()


    def _set_pixel(self, index, colour):
        """
        Set one LED without transmitting the strip yet.
        """

        self.strip.set_pixel_color(
            index,
            colour,
        )


    def _show(self):
        """
        Send the current LED buffer to the strip.
        """

        self.strip.show()


    # -----------------------------------------------------------------------
    # Boot animation
    # -----------------------------------------------------------------------

    def boot_animation(self):
        """
        Show the XRPimeter boot animation.

        LEDs illuminate green from LED 1 through LED 20.

        The animation is deliberately simple and deterministic so it can
        also be used by a system service before main.py starts.
        """

        print("LED boot animation...")

        self.clear()

        for index in range(
            LED_COUNT
        ):

            self._set_pixel(
                index,
                GREEN,
            )

            self._show()

            time.sleep(
                0.05
            )


        # Hold the completed green bar briefly.
        time.sleep(
            0.25
        )


        # Clear ready for normal operation.
        self.clear()


    # -----------------------------------------------------------------------
    # Shutdown animation
    # -----------------------------------------------------------------------

    def shutdown_animation(self):
        """
        Show the XRPimeter shutdown animation.

        LEDs illuminate green from LED 20 back towards LED 1.
        """

        print("LED shutdown animation...")

        self.clear()

        for index in reversed(
            range(LED_COUNT)
        ):

            self._set_pixel(
                index,
                GREEN,
            )

            self._show()

            time.sleep(
                0.05
            )


        time.sleep(
            0.25
        )

        self.clear()


    # -----------------------------------------------------------------------
    # Generic system status
    # -----------------------------------------------------------------------

    def status(self, colour=GREEN, duration=0.5):
        """
        Display a temporary system-status indication.

        All LEDs are illuminated with the supplied colour for the requested
        duration, then turned off.

        This gives us a simple mechanism for future system states without
        changing the normal meter display.

        Example:

            leds.status(RED)

        """

        self.strip.set_all_pixels(
            colour
        )

        self._show()

        time.sleep(
            duration
        )

        self.clear()




def xr18_disconnected(self, usb_available=False):
    """
    Display the safe idle state when the XR18 is disconnected.

    Channel LEDs are cleared because their previous audio levels
    are no longer meaningful. Recording is also stopped.
    """

    self._update_rec_led(False)
    self._update_usb_led(usb_available)

    for channel in range(18):

        self._set_pixel(
            CHANNEL_LED_START + channel,
            OFF,
        )

    self._show()


    # -----------------------------------------------------------------------
    # REC LED
    # -----------------------------------------------------------------------

    def _update_rec_led(self, recording):
        """
        Update the recording indicator.

        Not recording:
            LED OFF

        Recording:
            Smooth breathing green pulse.
        """

        if not recording:

            self._set_pixel(
                REC_LED,
                OFF,
            )
            self.breath_start = time.monotonic()
            return


        # ---------------------------------------------------------------
        # Generate a smooth breathing waveform.
        # ---------------------------------------------------------------

        elapsed = (
            time.monotonic()
            - self.breath_start
        )

        # Complete breathing cycle in seconds.
        period = 2.5

        phase = (
            elapsed
            / period
            * 2.0
            * math.pi
        )

        brightness = (
            math.sin(
                phase
            )
            + 1.0
        ) / 2.0


        # Keep a small minimum level so the LED doesn't completely vanish.
        brightness = (
            0.3
            + (
                brightness
                * 0.95
            )
        )


        colour = Color(
            0,
            int(
                255
                
                * brightness
            ),
            0,
        )


        self._set_pixel(
            REC_LED,
            colour,
        )


    # -----------------------------------------------------------------------
    # USB LED
    # -----------------------------------------------------------------------

    def _update_usb_led(self, usb_available):
        """
        Update the USB status indicator.

        USB present:
            Green

        USB absent:
            Red
        """

        if usb_available:
         
            self._set_pixel(
                USB_LED,
                DIM_GREEN,
            )

        else:
         
            self._set_pixel(
                USB_LED,
                DIM_RED,
            )


    # -----------------------------------------------------------------------
    # Channel colour calculation
    # -----------------------------------------------------------------------

    def _channel_colour(
        self,
        level,
    ):
        """
        Convert a channel dBFS level into an LED colour.

         

            <= -60 dBFS
                Very dim green.

            -60 to -20 dBFS
                Progressively brighter green.

            -20 to -10 dBFS
                Bright green.

            -10 to -6 dBFS
                Green to amber transition.

            -6 to -0.1 dBFS
                Red.

            >= -0.1 dBFS
                Flashing red.

        The overall LED brightness remains limited by BRIGHTNESS.
        """



        # ---------------------------------------------------------------
        # Clipping
        # ---------------------------------------------------------------
        #
        # Check clipping BEFORE the normal red region.
        # Otherwise the flashing state would never be reached.

        if level >= CLIP_LEVEL:

            elapsed = (
                time.monotonic()
                - self.clip_flash_start
            )


            # 2 Hz flash:
            #
            # 250 ms ON
            # 250 ms OFF

            if (
                elapsed % 0.5
            ) < 0.25:

                return RED

            return OFF


        # ---------------------------------------------------------------
        # Red
        # ---------------------------------------------------------------

        if level > RED_LEVEL:

            return RED


        # ---------------------------------------------------------------
        # Green to amber transition
        # ---------------------------------------------------------------

        if level > GREEN_LEVEL:

            # Map -10 dBFS to -6 dBFS onto:
            #
            #     green -> amber
            #
            # At -10:
            #
            #     (0, 255, 0)
            #
            # At -6:
            #
            #     (255, 100, 0)

            position = (
                level
                - GREEN_LEVEL
            ) / (
                AMBER_LEVEL
                - GREEN_LEVEL
            )


            position = max(
                0.0,
                min(
                    1.0,
                    position,
                ),
            )


            red = int(
                255
                * position
            )

            green = int(
                255
                - (
                    155
                    * position
                )
            )


            return Color(
                red,
                green,
                0,
            )


        # ---------------------------------------------------------------
        # Green metering
        # ---------------------------------------------------------------
        #
        # Minimum green brightness while recording.
        #
        # This is deliberately not zero: it gives visual confirmation
        # that the channel is part of the active recording even when it
        # contains no useful audio.

        minimum = 25

        maximum = 255


        # ---------------------------------------------------------------
        # Below the useful metering floor.
        # ---------------------------------------------------------------

        if level <= GREEN_FLOOR:

            brightness = minimum


        # ---------------------------------------------------------------
        # Progressive green metering.
        #
        # -60 dBFS -> minimum
        # -20 dBFS -> maximum
        # ---------------------------------------------------------------

        elif level < GREEN_MAX_LEVEL:

            position = (
                level
                - GREEN_FLOOR
            ) / (
                GREEN_MAX_LEVEL
                - GREEN_FLOOR
            )


            position = max(
                0.0,
                min(
                    1.0,
                    position,
                ),
            )


            brightness = (
                minimum
                + (
                    (
                        maximum
                        - minimum
                    )
                    * position
                )
            )


        # ---------------------------------------------------------------
        # -20 dBFS and above.
        # ---------------------------------------------------------------

        else:

            brightness = maximum


        brightness = int(
            max(
                minimum,
                min(
                    maximum,
                    brightness,
                ),
            )
        )


        return Color(
            0,
            brightness,
            0,
        )


    # -----------------------------------------------------------------------
    # Channel LEDs
    # -----------------------------------------------------------------------

    def _update_channel_leds(
        self,
        levels,
    ):
        """
        Update the 18 channel LEDs.

        levels is expected to contain one dBFS value for each channel.

        recording determines whether the channel LEDs should show their
        recording baseline.
        """

        # Defensive fallback.

        if levels is None:

            levels = [
                -120.0
            ] * 18


        for channel in range(18):

            # Missing values are treated as silence.
            if channel < len(levels):

                level = levels[channel]

            else:

                level = -120.0


            colour = self._channel_colour(
                level,
            )


            # Channel 1 -> LED 3
            #
            # Channel 18 -> LED 20

            led_index = (
                CHANNEL_LED_START
                + channel
            )


            self._set_pixel(
                led_index,
                colour,
            )


    # -----------------------------------------------------------------------
    # Normal operating display
    # -----------------------------------------------------------------------

    def update(
        self,
        levels,
        recording,
        usb_available,
    ):
        """
        Update the complete normal XRPimeter display.

        Parameters
        ----------

        levels:
            List containing 18 dBFS values from meter.py.

        recording:
            True when Recorder is actively recording.

        usb_available:
            True when the recording USB storage is available.
        
        """

        # Status LEDs.
        self._update_rec_led(
            recording
        )

        self._update_usb_led(
            usb_available
        )


        # Channel meters.
        self._update_channel_leds(
            levels,
        )


        # Send the complete 20 LED frame.
        self._show()


    # -----------------------------------------------------------------------
    # Shutdown
    # -----------------------------------------------------------------------

    def shutdown(self):
        """
        Turn all LEDs off.

        This should be called during normal XRPimeter shutdown.
        """

        self.clear()


    # -----------------------------------------------------------------------
    # Destructor safety
    # -----------------------------------------------------------------------

    def __del__(self):
        """
        Final safety cleanup.

        Python normally calls shutdown() explicitly, but this prevents the
        strip being left illuminated if the object is destroyed.
        """

        try:

            self.clear()

        except Exception:

            # Never allow destructor errors during Python shutdown.
            pass
