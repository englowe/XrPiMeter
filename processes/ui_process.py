"""
XRPimeter UI process.

This process owns:

    OLED display
    LEDs

It receives status information from the recorder process.

The UI must never access:

    XR18
    USB storage
    Recorder
    Meter

directly.
"""

import time
import queue


# ---------------------------------------------------------------------------
# XRPimeter modules
# ---------------------------------------------------------------------------

from display import (
    Display,
    DISPLAY_UPDATE_INTERVAL,
)

from led import LEDs


# ---------------------------------------------------------------------------
# UI process
# ---------------------------------------------------------------------------

def run_ui(
    status_queue,
    shutdown_event,
):
    """
    Main entry point for the UI process.

    The UI consumes status snapshots from the recorder process.

    If multiple status messages are waiting, the UI drains the queue and
    keeps only the newest one.
    """

    print(
        "UI PROCESS STARTED",
        flush=True,
    )

    display = Display()

    leds = LEDs()

    latest_status = {
        "xr18_connected": False,
        "usb_available": False,
        "usb_name": "",
        "recording": False,
        "elapsed_seconds": 0,
        "recording_size_gb": 0.0,
        "remaining_seconds": 0,
        "folder_path": "",
        "free_space_gb": 0.0,
        "part_number": 0,
        "levels": [],
    }

    last_display_update = 0.0

    last_led_update = 0.0

    LED_UPDATE_INTERVAL = 1.0 / 90.0

    try:

        while not shutdown_event.is_set():

            # ---------------------------------------------------------------
            # Consume all waiting status messages.
            #
            # We only care about the newest state.
            # ---------------------------------------------------------------

            while True:

                try:

                    latest_status = (
                        status_queue.get_nowait()
                    )

                except queue.Empty:

                    break

                except Exception:

                    break

            # ---------------------------------------------------------------
            # Pull values from the latest snapshot safely.
            #
            # .get() means a missing field cannot crash the UI process.
            # ---------------------------------------------------------------

            levels = latest_status.get(
                "levels",
                [],
            )

            xr18_connected = latest_status.get(
                "xr18_connected",
                False,
            )

            usb_available = latest_status.get(
                "usb_available",
                False,
            )

            usb_name = latest_status.get(
                "usb_name",
                "",
            )

            recording = latest_status.get(
                "recording",
                False,
            )

            elapsed_seconds = latest_status.get(
                "elapsed_seconds",
                0,
            )

            recording_size_gb = latest_status.get(
                "recording_size_gb",
                0.0,
            )

            free_space_gb = latest_status.get(
                "free_space_gb",
                0.0,
            )

            remaining_seconds = latest_status.get(
                "remaining_seconds",
                0,
            )

            folder_path = latest_status.get(
                "folder_path",
                "",
            )

            part_number = latest_status.get(
                "part_number",
                0,
            )

            now = time.monotonic()

            # ---------------------------------------------------------------
            # OLED
            # ---------------------------------------------------------------

            if (
                now - last_display_update
                >= DISPLAY_UPDATE_INTERVAL
            ):

                display.update(

                    levels=levels,

                    xr18_connected=(
                        xr18_connected
                    ),

                    usb_available=(
                        usb_available
                    ),

                    usb_name=usb_name,

                    recording=recording,

                    elapsed_seconds=(
                        elapsed_seconds
                    ),

                    recording_size_gb=(
                        recording_size_gb
                    ),

                    free_space_gb=(
                        free_space_gb
                    ),

                    remaining_seconds=(
                        remaining_seconds
                    ),

                    folder_path=folder_path,

                )

                last_display_update = now

            # ---------------------------------------------------------------
            # LEDs
            # ---------------------------------------------------------------

            if (
                now - last_led_update
                >= LED_UPDATE_INTERVAL
            ):

                if not xr18_connected:

                    leds.xr18_disconnected(
                        usb_available=(
                            usb_available
                        )
                    )

                else:

                    leds.update(

                        levels=levels,

                        recording=recording,

                        usb_available=(
                            usb_available
                        ),

                    )

                last_led_update = now

            # ---------------------------------------------------------------
            # UI timing
            # ---------------------------------------------------------------

            time.sleep(0.01)

    finally:

        print(
            "UI PROCESS SHUTDOWN",
            flush=True,
        )

        # ---------------------------------------------------------------
        # OLED
        # ---------------------------------------------------------------

        try:

            display.close()

        except Exception as error:

            print(
                f"UI display shutdown error: {error}",
                flush=True,
            )

        # ---------------------------------------------------------------
        # LEDs
        # ---------------------------------------------------------------

        try:

            leds.shutdown()

        except Exception as error:

            print(
                f"UI LED shutdown error: {error}",
                flush=True,
            )

        # ---------------------------------------------------------------
        # Don't wait for queued status messages.
        # ---------------------------------------------------------------

        try:

            status_queue.cancel_join_thread()

        except Exception:

            pass

        print(
            "UI PROCESS STOPPED",
            flush=True,
        )