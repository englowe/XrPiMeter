"""
XRPimeter main application.

Coordinates:
    XR18
    USB storage
    audio metering
    recording
    LEDs
    OLED display
    system logging
"""

import signal
import time


# ---------------------------------------------------------------------------
# XRPimeter modules
# ---------------------------------------------------------------------------

from xr18 import XR18

from usb_storage import (
    find_usb,
    recordings_directory,
    usb_is_available,
    get_usb_name,
)

from meter import Meter

from recorder import Recorder

from led import LEDs

from xrp_log import get_logger

from display import (
    Display,
    DISPLAY_UPDATE_INTERVAL,
)


# ---------------------------------------------------------------------------
# Create application components
# ---------------------------------------------------------------------------

xr18 = XR18()

meter = Meter()

leds = LEDs()

display = Display()

logger = get_logger()


# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------

LED_UPDATE_INTERVAL = 1.0 / 90.0

XR18_RECONNECT_INTERVAL = 2.0

last_led_update = 0.0

last_display_update = 0.0

last_xr18_reconnect = 0.0


# ---------------------------------------------------------------------------
# Application state
# ---------------------------------------------------------------------------

usb_mount_point = None

usb_name = ""

recorder = None


# ---------------------------------------------------------------------------
# Shutdown state
# ---------------------------------------------------------------------------

shutdown_requested = False


# ---------------------------------------------------------------------------
# Shutdown handler
# ---------------------------------------------------------------------------

def request_shutdown(signum=None, frame=None):
    """
    Request an orderly XRPimeter shutdown.

    The signal handler only sets a flag. The main loop performs the actual
    cleanup.
    """

    global shutdown_requested

    if shutdown_requested:
        return

    shutdown_requested = True


# ---------------------------------------------------------------------------
# Register shutdown signals
# ---------------------------------------------------------------------------

signal.signal(
    signal.SIGTERM,
    request_shutdown,
)

signal.signal(
    signal.SIGINT,
    request_shutdown,
)


# ---------------------------------------------------------------------------
# Start recorder if USB is available
# ---------------------------------------------------------------------------

def start_recorder():
    """
    Create and start a new recording session if USB storage is available.

    Returns:

        True
            Recorder successfully started.

        False
            Recorder could not be started.
    """

    global recorder

    if usb_mount_point is None:
        return False

    if recorder is not None:
        return True


    # -----------------------------------------------------------------------
    # Create XRPimeter recording directory
    # -----------------------------------------------------------------------

    recording_root = recordings_directory(
        usb_mount_point
    )


    if recording_root is None:

        logger.error(
            "Unable to create XRPimeter recording directory"
        )

        return False


    # -----------------------------------------------------------------------
    # Create recorder
    # -----------------------------------------------------------------------

    new_recorder = Recorder(
        recording_root
    )


    # -----------------------------------------------------------------------
    # Start recording session
    # -----------------------------------------------------------------------

    if not new_recorder.start():

        logger.error(
            "Recorder failed to start"
        )

        return False


    recorder = new_recorder

    logger.info(
        "Recorder started"
    )

    return True


# ---------------------------------------------------------------------------
# Stop recorder
# ---------------------------------------------------------------------------

def stop_recorder():
    """
    Stop the current recording session cleanly.
    """

    global recorder

    if recorder is None:
        return


    logger.info(
        "Stopping recording session"
    )


    recorder.stop()

    recorder = None


# ---------------------------------------------------------------------------
# Application startup
# ---------------------------------------------------------------------------

print(
    "XRPimeter starting..."
)

print()

logger.info(
    "XRPimeter application starting"
)


# ---------------------------------------------------------------------------
# Main application loop
# ---------------------------------------------------------------------------

try:

    while not shutdown_requested:

        # -------------------------------------------------------------------
        # Find XR18
        # -------------------------------------------------------------------

        if not xr18.connected:

            now = time.monotonic()


            # Avoid hammering ALSA every loop while the XR18 is disconnected.
            if (
                now - last_xr18_reconnect
                >= XR18_RECONNECT_INTERVAL
            ):

                last_xr18_reconnect = now


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


                    # -------------------------------------------------------
                    # If USB is already present, start a new recording.
                    #
                    # This is what allows:
                    #
                    #     XR18 unplugged
                    #         ↓
                    #     recording stops
                    #         ↓
                    #     XR18 plugged back in
                    #         ↓
                    #     new recording session starts
                    #
                    # -------------------------------------------------------

                    if usb_mount_point is not None:

                        if recorder is None:

                            start_recorder()


            # ---------------------------------------------------------------
            # Update display while XR18 is disconnected.
            # ---------------------------------------------------------------

            now = time.monotonic()


            if (
                now - last_display_update
                >= DISPLAY_UPDATE_INTERVAL
            ):

                display.update(

                    levels=meter.levels,

                    xr18_connected=False,

                    usb_available=(
                        usb_mount_point is not None
                    ),

                    usb_name=usb_name,

                    recording=(
                        recorder is not None
                        and recorder.recording
                    ),

                    elapsed_seconds=(
                        recorder.get_elapsed_seconds()
                        if recorder is not None
                        else 0
                    ),

                    recording_size_gb=(
                        recorder.get_recording_size_gb()
                        if recorder is not None
                        else 0.0
                    ),

                    free_space_gb=(
                        recorder.get_free_space_gb()
                        if recorder is not None
                        else 0.0
                    ),

                    remaining_seconds=(
                        recorder.get_remaining_seconds()
                        if recorder is not None
                        else 0
                    ),

                    folder_path=(
                        recorder.get_folder_path()
                        if recorder is not None
                        else ""
                    ),

                )


                last_display_update = now


            # ---------------------------------------------------------------
            # Keep LEDs showing the disconnected state.
            # ---------------------------------------------------------------

            if (
                now - last_led_update
                >= LED_UPDATE_INTERVAL
            ):

                leds.xr18_disconnected(
                    usb_available=(
                        usb_mount_point is not None
                    )
                )

                last_led_update = now


            # Give the CPU a little breathing room.
            time.sleep(0.01)

            continue


        # -------------------------------------------------------------------
        # Find USB storage
        # -------------------------------------------------------------------

        if usb_mount_point is None:

            usb_mount_point = find_usb()


            if usb_mount_point is not None:

                usb_name = get_usb_name(
                    usb_mount_point
                )


                logger.info(
                    f"USB storage ready: "
                    f"{usb_mount_point} "
                    f"label={usb_name}"
                )


                # -----------------------------------------------------------
                # Start recorder if XR18 is already connected.
                # -----------------------------------------------------------

                if recorder is None:

                    start_recorder()


        # -------------------------------------------------------------------
        # Check existing USB storage
        # -------------------------------------------------------------------

        if usb_mount_point is not None:

            if not usb_is_available(
                usb_mount_point
            ):

                logger.warning(
                    "USB storage disappeared"
                )


                # -----------------------------------------------------------
                # Stop recording cleanly.
                # -----------------------------------------------------------

                stop_recorder()


                # -----------------------------------------------------------
                # Forget USB.
                # -----------------------------------------------------------

                usb_mount_point = None

                usb_name = ""


                # -----------------------------------------------------------
                # Update LEDs immediately.
                # -----------------------------------------------------------

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

        length, data = xr18.read()


        # -------------------------------------------------------------------
        # Handle temporary empty XR18 read
        # -------------------------------------------------------------------

        if length <= 0 and data == b"":

            continue


        # -------------------------------------------------------------------
        # Handle genuine XR18 failure
        # -------------------------------------------------------------------

        if data is None:

            logger.warning(
                "XR18 audio stream lost"
            )


            # ---------------------------------------------------------------
            # Stop recording cleanly.
            #
            # The USB remains mounted.
            # ---------------------------------------------------------------

            stop_recorder()


            # ---------------------------------------------------------------
            # Release ALSA.
            # ---------------------------------------------------------------

            xr18.disconnect()


            # ---------------------------------------------------------------
            # Clear stale LED information.
            # ---------------------------------------------------------------

            leds.xr18_disconnected(
                usb_available=(
                    usb_mount_point is not None
                )
            )


            continue


        # -------------------------------------------------------------------
        # Process audio with meter
        # -------------------------------------------------------------------

        levels = meter.process(
            data
        )


        # -------------------------------------------------------------------
        # Update LEDs
        # -------------------------------------------------------------------

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

        if recorder is not None:

            recording_ok = recorder.write(
                data
            )


            # ---------------------------------------------------------------
            # Recorder reports that recording has stopped or failed.
            # ---------------------------------------------------------------

            if not recording_ok:

                logger.error(
                    "Recorder stopped or failed"
                )

                recorder = None


        # -------------------------------------------------------------------
        # Update OLED dashboard
        # -------------------------------------------------------------------

        now = time.monotonic()


        if (
            now - last_display_update
            >= DISPLAY_UPDATE_INTERVAL
        ):

            elapsed_seconds = 0

            recording_size_gb = 0.0

            free_space_gb = 0.0

            remaining_seconds = 0

            folder_path = ""

            recording = False


            if recorder is not None:

                recording = (
                    recorder.recording
                )

                elapsed_seconds = (
                    recorder.get_elapsed_seconds()
                )

                recording_size_gb = (
                    recorder.get_recording_size_gb()
                )

                free_space_gb = (
                    recorder.get_free_space_gb()
                )

                remaining_seconds = (
                    recorder.get_remaining_seconds()
                )

                folder_path = (
                    recorder.get_folder_path()
                )


            display.update(

                levels=levels,

                xr18_connected=xr18.connected,

                usb_available=(
                    usb_mount_point is not None
                ),

                usb_name=usb_name,

                recording=recording,

                elapsed_seconds=elapsed_seconds,

                recording_size_gb=recording_size_gb,

                free_space_gb=free_space_gb,

                remaining_seconds=remaining_seconds,

                folder_path=folder_path,

            )


            last_display_update = now


# ---------------------------------------------------------------------------
# Application shutdown
# ---------------------------------------------------------------------------

finally:

    shutdown_requested = True


    print()

    print(
        "XRPimeter stopping..."
    )

    print()


    logger.info(
        "XRPimeter shutdown requested"
    )


    # -----------------------------------------------------------------------
    # Stop recorder
    # -----------------------------------------------------------------------

    if recorder is not None:

        logger.info(
            "Closing recording session"
        )

        recorder.stop()

        recorder = None


    # -----------------------------------------------------------------------
    # Disconnect XR18
    # -----------------------------------------------------------------------

    if xr18.connected:

        xr18.disconnect()


    logger.info(
        "XR18 disconnected"
    )


    # -----------------------------------------------------------------------
    # Shutdown LEDs
    # -----------------------------------------------------------------------

    print(
        "Running shutdown animation..."
    )


    leds.shutdown()


    logger.info(
        "XRPimeter LED shutdown complete"
    )


    # -----------------------------------------------------------------------
    # Close OLED
    # -----------------------------------------------------------------------

    display.close()


    logger.info(
        "XRPimeter display closed"
    )


    # -----------------------------------------------------------------------
    # Finish
    # -----------------------------------------------------------------------

    print()

    print(
        "XRPimeter stopped."
    )

    print(
        "Safe to power off."
    )