"""
XRPimeter recorder process.

This process owns the critical recording path:

    XR18
      ↓
    Meter
      ↓
    Recorder
      ↓
    USB storage

The UI process is completely separate.

The recorder process must never depend on the OLED or LEDs.
"""

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


# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------

XR18_RECONNECT_INTERVAL = 2.0
USB_CHECK_INTERVAL = 1.0


# ---------------------------------------------------------------------------
# Start recorder
# ---------------------------------------------------------------------------

def start_recorder(usb_mount_point):
    """
    Create and start a new recording session.

    Returns:

        Recorder
            Recorder instance if successfully started.

        None
            Recorder could not be started.
    """

    recording_root = recordings_directory(
        usb_mount_point
    )


    if recording_root is None:

        print(
            "Unable to create XRPimeter recording directory",
            flush=True,
        )

        return None


    recorder = Recorder(
        recording_root
    )


    if not recorder.start():

        print(
            "Recorder failed to start",
            flush=True,
        )

        return None


    print(
        "Recorder started",
        flush=True,
    )


    return recorder


# ---------------------------------------------------------------------------
# Recorder process
# ---------------------------------------------------------------------------

def run_recorder(status_queue):
    """
    Main entry point for the recorder process.

    This function owns:

        XR18
        USB storage
        Meter
        Recorder

    No OLED or LED code is used here.
    """

    print(
        "RECORDER PROCESS STARTED",
        flush=True,
    )


    # -----------------------------------------------------------------------
    # Create hardware/software components
    # -----------------------------------------------------------------------

    xr18 = XR18()

    meter = Meter()


    # -----------------------------------------------------------------------
    # Application state
    # -----------------------------------------------------------------------

    usb_mount_point = None

    usb_name = ""

    recorder = None


    # -----------------------------------------------------------------------
    # Timing state
    # -----------------------------------------------------------------------

    last_xr18_reconnect = 0.0

    last_usb_check = 0.0


    # -----------------------------------------------------------------------
    # Audio diagnostics
    # -----------------------------------------------------------------------
    #
    # These counters measure the amount of audio arriving from the XR18.
    #
    # They are deliberately independent of the recorder.
    #
    # This will help us determine whether audio is being lost before
    # Recorder.write() receives it.
    #

    total_audio_bytes = 0

    total_audio_reads = 0

    last_diagnostic_time = time.monotonic()


    try:

        while True:

            # ---------------------------------------------------------------
            # Find XR18
            # ---------------------------------------------------------------

            if not xr18.connected:

                now = time.monotonic()


                if (
                    now - last_xr18_reconnect
                    >= XR18_RECONNECT_INTERVAL
                ):

                    last_xr18_reconnect = now


                    if xr18.connect():

                        print(
                            f"XR18 connected: "
                            f"{xr18.device_name}",
                            flush=True,
                        )


                        # ---------------------------------------------------
                        # If USB is already available, start recording.
                        # ---------------------------------------------------

                        if usb_mount_point is not None:

                            if recorder is None:

                                recorder = start_recorder(
                                    usb_mount_point
                                )


                time.sleep(0.01)

                continue


            # ---------------------------------------------------------------
            # Find USB storage
            # ---------------------------------------------------------------

            if usb_mount_point is None:

                usb_mount_point = find_usb()


                if usb_mount_point is not None:

                    usb_name = get_usb_name(
                        usb_mount_point
                    )


                    print(
                        f"USB storage ready: "
                        f"{usb_mount_point} "
                        f"label={usb_name}",
                        flush=True,
                    )


                    # -------------------------------------------------------
                    # XR18 is already connected.
                    #
                    # Start a recording session.
                    # -------------------------------------------------------

                    if recorder is None:

                        recorder = start_recorder(
                            usb_mount_point
                        )


            # ---------------------------------------------------------------
            # Check existing USB storage
            # ---------------------------------------------------------------

            now = time.monotonic()


            if (
                usb_mount_point is not None
                and now - last_usb_check
                >= USB_CHECK_INTERVAL
            ):

                last_usb_check = now


                if not usb_is_available(
                    usb_mount_point
                ):

                    print(
                        "USB storage disappeared",
                        flush=True,
                    )


                    # Stop recording before forgetting the USB.

                    if recorder is not None:

                        recorder.stop()

                        recorder = None


                    usb_mount_point = None

                    usb_name = ""


                    time.sleep(1)

                    continue


            # ---------------------------------------------------------------
            # Read audio from XR18
            # ---------------------------------------------------------------

            length, data = xr18.read()


            # ---------------------------------------------------------------
            # Empty read
            # ---------------------------------------------------------------

            if length <= 0 and data == b"":

                continue


            # ---------------------------------------------------------------
            # XR18 audio failure
            # ---------------------------------------------------------------

            if data is None:

                print(
                    "XR18 audio stream lost",
                    flush=True,
                )


                # Stop the current recording cleanly.

                if recorder is not None:

                    recorder.stop()

                    recorder = None


                # Release ALSA.

                xr18.disconnect()

                continue


            # ---------------------------------------------------------------
            # Audio diagnostics
            # ---------------------------------------------------------------
            #
            # Count every successful block returned by the XR18.
            #
            # We count bytes for now. Later we can make this more precise
            # by counting audio frames directly.
            #

            total_audio_reads += 1

            total_audio_bytes += len(data)


            # ---------------------------------------------------------------
            # Periodic diagnostic output
            # ---------------------------------------------------------------

            now = time.monotonic()


            if (
                now - last_diagnostic_time
                >= 10.0
            ):

                elapsed = (
                    now - last_diagnostic_time
                )


                rate_kb_per_second = (
                    total_audio_bytes
                    / elapsed
                    / 1024
                )


                print(
                    f"AUDIO DIAGNOSTIC: "
                    f"reads={total_audio_reads} "
                    f"bytes={total_audio_bytes} "
                    f"rate={rate_kb_per_second:.1f} KB/s",
                    flush=True,
                )


                # Reset the counters for the next interval.

                total_audio_reads = 0

                total_audio_bytes = 0

                last_diagnostic_time = now


            # ---------------------------------------------------------------
            # Meter audio
            # ---------------------------------------------------------------

            levels = meter.process(
                data
            )


            # ---------------------------------------------------------------
            # Write audio
            # ---------------------------------------------------------------

            if recorder is not None:

                recording_ok = recorder.write(
                    data
                )


                if not recording_ok:

                    print(
                        "Recorder stopped or failed",
                        flush=True,
                    )

                    recorder = None


            # ---------------------------------------------------------------
            # Send status to UI
            # ---------------------------------------------------------------
            #
            # Only small metadata is sent.
            #
            # The audio buffer itself is NEVER sent through the queue.
            #
            # If the UI process is dead or unavailable, recording continues.
            #

            try:

                status_queue.put_nowait(
                    {
                        "xr18_connected": xr18.connected,

                        "usb_available": (
                            usb_mount_point is not None
                        ),

                        "usb_name": usb_name,

                        "recording": (
                            recorder is not None
                            and recorder.recording
                        ),

                        "levels": levels,
                    }
                )

            except Exception:

                # UI communication must never interfere with recording.

                pass


    finally:

        # -------------------------------------------------------------------
        # Stop recording
        # -------------------------------------------------------------------

        if recorder is not None:

            print(
                "Closing recording session...",
                flush=True,
            )

            recorder.stop()

            recorder = None


        # -------------------------------------------------------------------
        # Disconnect XR18
        # -------------------------------------------------------------------

        if xr18.connected:

            xr18.disconnect()


        print(
            "RECORDER PROCESS STOPPED",
            flush=True,
        )