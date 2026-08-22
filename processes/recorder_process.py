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
# Audio configuration
# ---------------------------------------------------------------------------

CHANNELS = 18

BYTES_PER_SAMPLE = 4


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
# Print audio diagnostics
# ---------------------------------------------------------------------------

def print_audio_diagnostics(
    xr18_frames,
    recorder,
):
    """
    Print a comparison between the number of audio frames received from
    the XR18 and the number of frames written by Recorder.

    Both values represent one complete 18-channel audio frame.
    """

    if recorder is None:
        return


    recorder_frames = (
        recorder.total_frames_written
    )


    difference = (
        xr18_frames
        - recorder_frames
    )


    xr18_duration = (
        xr18_frames / 48000
    )


    recorder_duration = (
        recorder_frames / 48000
    )


    print(
        "",
        flush=True,
    )

    print(
        "========================================",
        flush=True,
    )

    print(
        "RECORDER AUDIO DIAGNOSTICS",
        flush=True,
    )

    print(
        "========================================",
        flush=True,
    )

    print(
        f"XR18 frames received:     "
        f"{xr18_frames:,}",
        flush=True,
    )

    print(
        f"Recorder frames written:  "
        f"{recorder_frames:,}",
        flush=True,
    )

    print(
        f"Difference:               "
        f"{difference:,}",
        flush=True,
    )

    print(
        f"XR18 duration:            "
        f"{xr18_duration:.3f} seconds",
        flush=True,
    )

    print(
        f"Recorded duration:        "
        f"{recorder_duration:.3f} seconds",
        flush=True,
    )

    print(
        "========================================",
        flush=True,
    )

    print(
        "",
        flush=True,
    )


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
    # This counts complete 18-channel audio frames received from the XR18
    # during the CURRENT recording session.
    #
    # It is deliberately separate from Recorder's own frame counter.
    #
    # This lets us compare:
    #
    #     XR18 frames received
    #
    # against:
    #
    #     Recorder frames written
    #
    # A difference indicates that frames were lost between those two points.
    #

    session_xr18_frames = 0


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


                                if recorder is not None:

                                    # Start counting frames for this
                                    # recording session from zero.

                                    session_xr18_frames = 0


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


                        if recorder is not None:

                            # Start counting frames for this recording
                            # session from zero.

                            session_xr18_frames = 0


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


                    # -------------------------------------------------------
                    # Print diagnostics BEFORE stopping the recorder.
                    # -------------------------------------------------------

                    if recorder is not None:

                        print_audio_diagnostics(
                            session_xr18_frames,
                            recorder,
                        )


                        # Stop recording before forgetting the USB.

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


                # -----------------------------------------------------------
                # Print diagnostics BEFORE stopping the recorder.
                # -----------------------------------------------------------

                if recorder is not None:

                    print_audio_diagnostics(
                        session_xr18_frames,
                        recorder,
                    )


                    # Stop the current recording cleanly.

                    recorder.stop()

                    recorder = None


                # Release ALSA.

                xr18.disconnect()

                continue


            # ---------------------------------------------------------------
            # Count XR18 audio frames
            # ---------------------------------------------------------------
            #
            # The XR18 provides:
            #
            #     18 channels
            #     4 bytes per sample
            #
            # Therefore one complete audio frame is:
            #
            #     18 × 4 = 72 bytes
            #
            # len(data) / 72 therefore gives the number of complete
            # 18-channel frames in this block.
            #
            # Only count frames while a recording session is active.

            if (
                recorder is not None
                and recorder.recording
            ):

                frames_received = (
                    len(data)
                    // (
                        CHANNELS
                        * BYTES_PER_SAMPLE
                    )
                )


                session_xr18_frames += (
                    frames_received
                )


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


                    # The recorder has already stopped itself if write()
                    # encountered an error.

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
        # Print diagnostics BEFORE stopping the recorder
        # -------------------------------------------------------------------

        if recorder is not None:

            print_audio_diagnostics(
                session_xr18_frames,
                recorder,
            )


            # ---------------------------------------------------------------
            # Stop recording
            # ---------------------------------------------------------------

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