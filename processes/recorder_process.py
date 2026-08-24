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

Architecture
------------

Fast path:
    - read XR18 audio
    - meter audio
    - write audio

Slow path:
    - check XR18 connection/reconnection
    - check USB storage
    - detect XR18 audio timeout
    - build filesystem-based recording information
    - send status to the UI

The slow path runs independently of whether audio is currently flowing.
This is important because the UI must be told when the XR18 disconnects,
even if there is no longer any successful audio read.
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

# How often to attempt XR18 reconnection.
XR18_RECONNECT_INTERVAL = 2.0

# How often to perform USB/filesystem checks.
USB_CHECK_INTERVAL = 1.0

# How often to build and send a complete UI status snapshot.
STATUS_UPDATE_INTERVAL = 1.0

# Maximum time allowed without receiving actual XR18 audio.
#
# Occasional empty non-blocking ALSA reads are normal.
#
# However, if no successful audio block arrives for this long, treat the
# XR18 audio stream as lost.
XR18_AUDIO_TIMEOUT = 1.0


# ---------------------------------------------------------------------------
# Audio configuration
# ---------------------------------------------------------------------------

CHANNELS = 18
BYTES_PER_SAMPLE = 4
SAMPLE_RATE = 48000


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
# Audio diagnostics
# ---------------------------------------------------------------------------

def print_audio_diagnostics(
    xr18_frames,
    recorder,
):
    """
    Print a comparison between XR18 frames received and frames written.
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
        xr18_frames
        / SAMPLE_RATE
    )


    recorder_duration = (
        recorder_frames
        / SAMPLE_RATE
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
# Stop current recording
# ---------------------------------------------------------------------------

def stop_current_recording(
    recorder,
    session_xr18_frames,
):
    """
    Print diagnostics and cleanly stop the current recording.
    """

    if recorder is None:
        return


    print_audio_diagnostics(
        session_xr18_frames,
        recorder,
    )


    print(
        "Closing recording session...",
        flush=True,
    )


    recorder.stop()


# ---------------------------------------------------------------------------
# Build UI status
# ---------------------------------------------------------------------------

def build_status(
    xr18,
    usb_mount_point,
    usb_name,
    recorder,
    levels,
):
    """
    Build the complete status snapshot required by the UI.

    Only small serialisable values are returned.

    Hardware objects are never sent through the multiprocessing queue.
    """

    if (
        recorder is not None
        and recorder.recording
    ):

        elapsed_seconds = (
            recorder.get_elapsed_seconds()
        )

        recording_size_gb = (
            recorder.get_recording_size_gb()
        )

        remaining_seconds = (
            recorder.get_remaining_seconds()
        )

        folder_path = (
            recorder.get_folder_path()
        )

        free_space_gb = (
            recorder.get_free_space_gb()
        )

        part_number = (
            recorder.part_number
        )

    else:

        elapsed_seconds = 0
        recording_size_gb = 0.0
        remaining_seconds = 0
        folder_path = ""
        free_space_gb = 0.0
        part_number = 0


    return {
        # ---------------------------------------------------------------
        # Connection state
        # ---------------------------------------------------------------

        "xr18_connected": (
            xr18.connected
        ),

        "usb_available": (
            usb_mount_point is not None
        ),

        "usb_name": usb_name,


        # ---------------------------------------------------------------
        # Recording state
        # ---------------------------------------------------------------

        "recording": (
            recorder is not None
            and recorder.recording
        ),

        "elapsed_seconds": elapsed_seconds,

        "recording_size_gb": recording_size_gb,

        "remaining_seconds": remaining_seconds,

        "folder_path": folder_path,

        "free_space_gb": free_space_gb,

        "part_number": part_number,


        # ---------------------------------------------------------------
        # Meter
        # ---------------------------------------------------------------

        "levels": levels,
    }


# ---------------------------------------------------------------------------
# Send UI status
# ---------------------------------------------------------------------------

def send_status(
    status_queue,
    status,
):
    """
    Send a status snapshot to the UI.

    Recording must never stop because the UI is unavailable.
    """

    try:

        status_queue.put_nowait(
            status
        )

    except Exception:

        pass


# ---------------------------------------------------------------------------
# Recorder process
# ---------------------------------------------------------------------------

def run_recorder(
    status_queue,
    shutdown_event,
):
    """
    Main entry point for the recorder process.

    The fast audio path and slow status/filesystem path are deliberately
    independent.

    This means the UI continues receiving connection updates even when
    the XR18 is disconnected and no audio blocks are arriving.
    """

    print(
        "RECORDER PROCESS STARTED",
        flush=True,
    )


    # -----------------------------------------------------------------------
    # Create components
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

    now = time.monotonic()

    last_xr18_reconnect = (
        now
        - XR18_RECONNECT_INTERVAL
    )

    last_usb_check = (
        now
        - USB_CHECK_INTERVAL
    )

    last_status_update = (
        now
        - STATUS_UPDATE_INTERVAL
    )

    last_audio_time = now


    # -----------------------------------------------------------------------
    # Audio diagnostics
    # -----------------------------------------------------------------------

    session_xr18_frames = 0


    # -----------------------------------------------------------------------
    # Last known meter values
    # -----------------------------------------------------------------------

    levels = meter.levels


    try:

        while not shutdown_event.is_set():

            # Current monotonic time is used for all scheduling.
            now = time.monotonic()


            # ===============================================================
            # SLOW PATH: XR18 CONNECTION / RECONNECTION
            # ===============================================================
            #
            # This runs whether or not audio is currently flowing.
            #

            if (
                not xr18.connected
                and
                now - last_xr18_reconnect
                >= XR18_RECONNECT_INTERVAL
            ):

                last_xr18_reconnect = now


                if xr18.connect():

                    last_audio_time = (
                        time.monotonic()
                    )


                    print(
                        f"XR18 connected: "
                        f"{xr18.device_name}",
                        flush=True,
                    )


                    # Start recording immediately if USB is already present.
                    if (
                        usb_mount_point is not None
                        and recorder is None
                    ):

                        recorder = start_recorder(
                            usb_mount_point
                        )


                        if recorder is not None:

                            session_xr18_frames = 0


            # ===============================================================
            # SLOW PATH: USB CHECKS
            # ===============================================================

            if (
                now - last_usb_check
                >= USB_CHECK_INTERVAL
            ):

                last_usb_check = now


                # -----------------------------------------------------------
                # Look for USB storage
                # -----------------------------------------------------------

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


                        # Start recording only if the XR18 is available.
                        if (
                            xr18.connected
                            and recorder is None
                        ):

                            recorder = start_recorder(
                                usb_mount_point
                            )


                            if recorder is not None:

                                session_xr18_frames = 0


                # -----------------------------------------------------------
                # Check existing USB storage
                # -----------------------------------------------------------

                else:

                    if not usb_is_available(
                        usb_mount_point
                    ):

                        print(
                            "USB storage disappeared",
                            flush=True,
                        )


                        if recorder is not None:

                            stop_current_recording(
                                recorder,
                                session_xr18_frames,
                            )

                            recorder = None


                        usb_mount_point = None

                        usb_name = ""


            # ===============================================================
            # FAST PATH: READ AUDIO
            # ===============================================================
            #
            # Only attempt an audio read when the XR18 is currently open.
            #

            if xr18.connected:

                length, data = xr18.read()


                # -----------------------------------------------------------
                # Successful audio
                # -----------------------------------------------------------

                if (
                    length > 0
                    and data
                ):

                    # Successful audio proves the stream is alive.
                    last_audio_time = (
                        time.monotonic()
                    )


                    # -------------------------------------------------------
                    # Count frames
                    # -------------------------------------------------------

                    if (
                        recorder is not None
                        and recorder.recording
                    ):

                        frames_received = (
                            len(data)
                            //
                            (
                                CHANNELS
                                * BYTES_PER_SAMPLE
                            )
                        )


                        session_xr18_frames += (
                            frames_received
                        )


                    # -------------------------------------------------------
                    # Meter
                    # -------------------------------------------------------

                    levels = meter.process(
                        data
                    )


                    # -------------------------------------------------------
                    # Write audio
                    # -------------------------------------------------------

                    if recorder is not None:

                        recording_ok = (
                            recorder.write(
                                data
                            )
                        )


                        if not recording_ok:

                            print(
                                "Recorder stopped or failed",
                                flush=True,
                            )

                            recorder = None


                # -----------------------------------------------------------
                # Genuine ALSA error
                # -----------------------------------------------------------

                elif data is None:

                    print(
                        "XR18 audio stream lost",
                        flush=True,
                    )


                    if recorder is not None:

                        stop_current_recording(
                            recorder,
                            session_xr18_frames,
                        )

                        recorder = None


                    xr18.disconnect()


                # -----------------------------------------------------------
                # Empty non-blocking read
                # -----------------------------------------------------------

                else:

                    # Do nothing immediately.
                    #
                    # The audio watchdog below decides whether the absence
                    # of audio has lasted too long.


                    pass


            # ===============================================================
            # SLOW PATH: XR18 AUDIO WATCHDOG
            # ===============================================================
            #
            # IMPORTANT:
            #
            # This is outside the successful-audio branch.
            #
            # Therefore it continues running even if ALSA repeatedly
            # returns empty reads.
            #

            now = time.monotonic()


            if (
                xr18.connected
                and
                now - last_audio_time
                >= XR18_AUDIO_TIMEOUT
            ):

                print(
                    "XR18 audio timeout - "
                    "no audio received",
                    flush=True,
                )


                if recorder is not None:

                    stop_current_recording(
                        recorder,
                        session_xr18_frames,
                    )

                    recorder = None


                xr18.disconnect()


            # ===============================================================
            # SLOW PATH: UI STATUS
            # ===============================================================
            #
            # IMPORTANT:
            #
            # This is outside every audio branch.
            #
            # The UI therefore receives status whether:
            #
            #   - audio is flowing
            #   - ALSA returns empty reads
            #   - the XR18 times out
            #   - the XR18 is disconnected
            #   - the XR18 is reconnecting
            #

            now = time.monotonic()


            if (
                now - last_status_update
                >= STATUS_UPDATE_INTERVAL
            ):

                last_status_update = now


                status = build_status(
                    xr18=xr18,
                    usb_mount_point=usb_mount_point,
                    usb_name=usb_name,
                    recorder=recorder,
                    levels=levels,
                )


                send_status(
                    status_queue,
                    status,
                )


            # ===============================================================
            # Idle protection
            # ===============================================================
            #
            # When no audio is available, avoid a full-speed CPU loop.
            #
            # This does not run during successful audio because that would
            # unnecessarily delay the recording path.
            #

            if (
                not xr18.connected
            ):

                time.sleep(
                    0.01
                )


    finally:

        print(
            "RECORDER PROCESS SHUTDOWN",
            flush=True,
        )


        # -------------------------------------------------------------------
        # Stop current recording
        # -------------------------------------------------------------------

        if recorder is not None:

            stop_current_recording(
                recorder,
                session_xr18_frames,
            )

            recorder = None


        # -------------------------------------------------------------------
        # Disconnect XR18
        # -------------------------------------------------------------------

        if xr18.connected:

            xr18.disconnect()


        # -------------------------------------------------------------------
        # Prevent multiprocessing.Queue shutdown delays
        # -------------------------------------------------------------------

        try:

            status_queue.cancel_join_thread()

        except Exception:

            pass


        print(
            "RECORDER PROCESS STOPPED",
            flush=True,
        )
