"""
XRPimeter main application.

This file coordinates the XRPimeter modules.

The individual jobs are handled by separate modules:

    xr18.py
        Finds the XR18 and receives the 18-channel audio stream.

    usb_storage.py
        Finds and checks the USB recording storage.

    meter.py
        Calculates the audio level for each channel.

    recorder.py
        Writes the audio stream to 18 separate WAV files.
        Handles recording sessions and 20-minute part rollover.

    led.py
        Controls the 20 WS2812 status and channel LEDs.

    xrp_log.py
        Records important XRPimeter events in the system log.

    time_status.py
        Determines whether the Raspberry Pi's system clock can be trusted.

main.py coordinates these jobs rather than implementing their internal
behaviour.

The basic operating principle is:

    XR18 connected
        |
        +----> Metering
        |
        +----> USB available?
                  |
                  +---- YES ---> Recording
                  |
                  +---- NO ----> Metering continues

Therefore XRPimeter can operate as a meter without a USB drive.
"""


import time


# ---------------------------------------------------------------------------
# XRPimeter modules
# ---------------------------------------------------------------------------

# XR18 handles discovery and capture of the audio interface.
from xr18 import XR18

# USB storage handles finding and preparing removable recording storage.
from usb_storage import (
    find_usb,
    recordings_directory,
    usb_is_available,
)

# Meter calculates the audio levels.
from meter import Meter

# Recorder writes the incoming audio to WAV files.
#
# Recorder also handles:
#
#     - session naming
#     - time-validity naming
#     - Part 1 / Part 2 naming
#     - 20-minute rollover
#     - WAV file creation and closing
from recorder import Recorder

# LED controller handles:
#
#     - REC LED
#     - USB status LED
#     - CH1-CH18 level LEDs
#     - boot animation
#     - shutdown animation
from led import LEDs

# Central XRPimeter system logger.
from xrp_log import get_logger


# ---------------------------------------------------------------------------
# Create application components
# ---------------------------------------------------------------------------

# Create the XR18 interface.
#
# This does not mean that the XR18 is currently connected.
xr18 = XR18()


# Create the audio meter.
#
# Metering does not require USB storage.
meter = Meter()


# Create the LED controller.
#
# The LED controller handles all WS2812 hardware and presentation logic.
leds = LEDs()

# LED display update rate.
#
# Audio metering continues at the full XR18 sample rate, but the physical
# LEDs only need to be refreshed around 24 times per second.
LED_UPDATE_INTERVAL = 1.0 / 90.0

last_led_update = 0.0


# No USB storage has been found yet.
usb_mount_point = None


# No recorder exists until usable USB storage is found.
recorder = None


# Get the central system logger.
logger = get_logger()


# ---------------------------------------------------------------------------
# Application startup
# ---------------------------------------------------------------------------

print("XRPimeter starting...")
print()

logger.info(
    "XRPimeter application starting"
)


# ---------------------------------------------------------------------------
# Main application loop
# ---------------------------------------------------------------------------
#
# The loop continuously:
#
#     1. Finds the XR18.
#     2. Looks for USB storage.
#     3. Checks existing USB storage.
#     4. Reads one block of audio.
#     5. Sends that block to the meter.
#     6. Updates the LEDs.
#     7. Sends that same block to the recorder.
#
# Recorder handles the 20-minute rollover internally.
#
# When Part 1 reaches 20 minutes, recorder.write() closes Part 1 and
# immediately starts Part 2. main.py does not need to know the exact
# rollover point.

try:

    while True:

        # -------------------------------------------------------------------
        # Find XR18
        # -------------------------------------------------------------------

        if not xr18.connected:

            print("Searching for XR18...")
            print()


            # Search ALSA dynamically.
            #
            # We do not assume that the XR18 will always be hw:2,0.
            if xr18.connect():

                print(
                    f"XR18 connected: "
                    f"{xr18.device_name}"
                )

                print()


                logger.info(
                    f"XR18 connected: "
                    f"{xr18.device_name}"
                )

            else:

                print("XR18 not found.")
                print("Waiting...")
                print()


                # No audio can be processed yet.
                time.sleep(2)

                continue


        # -------------------------------------------------------------------
        # Find USB storage
        # -------------------------------------------------------------------
        #
        # USB recording is optional.
        #
        # If no USB has been found, search for one.
        #
        # Failure to find USB does NOT stop metering.

        if usb_mount_point is None:

            print(
                "Searching for USB storage..."
            )


            usb_mount_point = find_usb()


            if usb_mount_point is not None:

                print(
                    f"USB storage ready: "
                    f"{usb_mount_point}"
                )

                print()


                logger.info(
                    f"USB storage ready: "
                    f"{usb_mount_point}"
                )


                # -----------------------------------------------------------
                # Create the XRPimeter recording directory
                # -----------------------------------------------------------

                recording_root = recordings_directory(
                    usb_mount_point
                )


                if recording_root is None:

                    print(
                        "Unable to create recording directory."
                    )

                    print(
                        "Meter will continue without recording."
                    )

                    print()


                    logger.error(
                        "Unable to create XRPimeter recording directory"
                    )


                    usb_mount_point = None


                else:

                    # -------------------------------------------------------
                    # Create recorder
                    # -------------------------------------------------------

                    recorder = Recorder(
                        recording_root
                    )


                    # Start a new recording session.
                    #
                    # Recorder determines whether the system clock is valid
                    # and chooses the appropriate session naming scheme.
                    #
                    # It also creates Part 1 and the 18 WAV files.
                    if recorder.start():

                        logger.info(
                            "Recorder started"
                        )

                    else:

                        logger.error(
                            "Recorder failed to start"
                        )

                        recorder = None


            else:

                # USB is optional, so this is not an application failure.
                print(
                    "USB storage not found."
                )

                print(
                    "Meter will continue without recording."
                )

                print()


        # -------------------------------------------------------------------
        # Check existing USB storage
        # -------------------------------------------------------------------
        #
        # If the USB drive disappears during recording, stop the recorder
        # cleanly and return to metering-only operation.

        if usb_mount_point is not None:

            if not usb_is_available(
                usb_mount_point
            ):

                print()
                print(
                    "USB storage has disappeared."
                )

                print(
                    "Stopping recording."
                )

                print(
                    "Meter will continue."
                )

                print()


                logger.warning(
                    "USB storage disappeared"
                )


                # Close the current WAV files cleanly.
                if recorder is not None:

                    recorder.stop()

                    recorder = None


                # Forget the old USB mount.
                usb_mount_point = None

                leds.update(
                    levels=meter.levels,
                    recording=False,
                    usb_available=False,
                )


                # Give Linux a moment to settle.
                time.sleep(1)

                continue


        # -------------------------------------------------------------------
        # Read audio from XR18
        # -------------------------------------------------------------------
        #
        # XR18.read() returns:
        #
        #     length
        #         Number of audio frames received.
        #
        #     data
        #         Raw interleaved S32_LE audio bytes.
        #
        # A valid block contains all 18 channels.

        length, data = xr18.read()


        # -------------------------------------------------------------------
        # Handle an empty XR18 read
        # -------------------------------------------------------------------
        #
        # ALSA can occasionally return an empty read without the XR18
        # actually disconnecting.
        #
        # xr18.py represents this as:
        #
        #     length = 0
        #     data = b""
        #
        # There are no samples to process, so simply wait for the next read.
        #
        # IMPORTANT:
        #
        # We must NOT pass an empty buffer to Meter or Recorder because
        # NumPy would attempt to calculate an RMS value from an empty array
        # and produce "Mean of empty slice" warnings.

        if length <= 0 and data == b"":

            continue


        # -------------------------------------------------------------------
        # Handle an actual XR18 failure
        # -------------------------------------------------------------------
        #
        # xr18.py returns data=None when an actual ALSA audio error occurs.
        #
        # Unlike an empty read, this means the audio device should be
        # released and rediscovered.

        if data is None:

            print()
            print(
                "XR18 audio stream lost."
            )

            print()


            logger.warning(
                "XR18 audio stream lost"
            )


            # Stop recording cleanly if necessary.
            if recorder is not None:

                recorder.stop()

                recorder = None


            # Release the ALSA device.
            
            xr18.disconnect()

            # Clear stale LED information immediately.
            #
            # The XR18 is no longer supplying audio, so the previous
            # channel levels must not remain displayed.
            leds.xr18_disconnected(
                usb_available=(
                    usb_mount_point is not None
                )
            )

            
            # On the next loop the XR18 will be discovered again.
            continue


        # -------------------------------------------------------------------
        # Process audio with the meter
        # -------------------------------------------------------------------
        #
        # Metering is independent of USB recording.
        #
        # Keep the returned levels because they are also used by led.py.

        levels = meter.process(
            data
        )


        # Display the current levels.
        meter.display()


        # -------------------------------------------------------------------
        # Update the physical LEDs
        # -------------------------------------------------------------------
        #
        # LED order:
        #
        #     LED 1  = REC
        #     LED 2  = USB
        #     LED 3  = CH1
        #     ...
        #     LED 20 = CH18
        #
        # The LED controller handles all colour and animation decisions.

        now = time.monotonic()

        if (
            now - last_led_update
            >= LED_UPDATE_INTERVAL
        ):

            leds.update(
                levels=levels,
                recording=(
                    recorder is not None
                    and recorder.recording
                ),
                usb_available=(
                    usb_mount_point is not None
                ),
            )

            last_led_update = now


        # -------------------------------------------------------------------
        # Send audio to recorder
        # -------------------------------------------------------------------
        #
        # Recorder receives exactly the same valid audio block as the meter.
        #
        # Recorder handles:
        #
        #     - S32_LE to 24-bit WAV conversion
        #     - all 18 channels
        #     - frame counting
        #     - 20-minute rollover
        #     - starting the next part
        #
        # main.py therefore does NOT need to monitor the 20-minute timer.

        if recorder is not None:

            recording_ok = recorder.write(
                data
            )


            # If Recorder reports a failure, stop using it.
            if not recording_ok:

                logger.error(
                    "Recorder stopped or failed"
                )

                recorder = None


# ---------------------------------------------------------------------------
# Application shutdown
# ---------------------------------------------------------------------------
#
# This currently handles a normal Ctrl+C / KeyboardInterrupt.
#
# The proper Raspberry Pi shutdown animation will eventually be handled
# through the operating system shutdown sequence rather than relying on
# main.py to remain running.

except KeyboardInterrupt:

    print()
    print(
        "XRPimeter stopping..."
    )
    print()


    logger.info(
        "XRPimeter application stopping"
    )


    # Close the current WAV files cleanly.
    if recorder is not None:

        recorder.stop()

        recorder = None


    # Turn the LEDs off.
    leds.shutdown()


    # Release the XR18 audio device.
    xr18.disconnect()


    logger.info(
        "XRPimeter application stopped"
    )


    print(
        "XRPimeter stopped."
    )
