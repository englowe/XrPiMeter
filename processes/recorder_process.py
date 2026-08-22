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

IMPORTANT ARCHITECTURE:

The recorder loop is split into two paths.

FAST AUDIO PATH
    XR18 read
    Meter processing
    Recorder write

This path runs as quickly as audio arrives and must contain no
filesystem statistics, directory scanning, or UI queue work.

SLOW STATUS PATH
    USB availability check
    Recording statistics
    Filesystem statistics
    UI status message

This path runs approximately once per second.

This prevents filesystem operations from being performed once for
every 1024-frame audio block.
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

# Filesystem and USB status checks are deliberately slow.
USB_CHECK_INTERVAL = 1.0

# UI status is also deliberately limited to approximately once per second.
STATUS_UPDATE_INTERVAL = 1.0


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
        xr18_frames / SAMPLE_RATE
    )

    recorder_duration = (
        recorder_frames / SAMPLE_RATE
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

    IMPORTANT:

    This function intentionally performs filesystem-related operations
    such as recording-size and free-space queries.

    It MUST therefore only be called from the slow status path.

    It must NEVER be called for every audio block.
    """

    if recorder is not None and recorder.recording:

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

        "xr18_connected": xr18.connected,

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
# Recorder process
# ---------------------------------------------------------------------------

def run_recorder(
    status_queue,
    shutdown_event,
):
    """
    Main entry point for the recorder process.

    The recorder checks shutdown_event once per loop.

    The loop is deliberately divided into:

        FAST AUDIO PATH
            XR18 read
            meter processing
            recorder write

        SLOW STATUS PATH
            USB checks
            filesystem statistics
            UI status queue

    The slow path must never interfere unnecessarily with the audio path.
    """

    print(
        "RECORDER PROCESS STARTED",
        flush=True,
    )

    # -----------------------------------------------------------------------
    # Hardware/software components
    # -----------------------------------------------------------------------

    xr18 = XR18()

    meter = Meter()

    usb_mount_point = None

    usb_name = ""

    recorder = None

    # -----------------------------------------------------------------------
    # Timing state
    # -----------------------------------------------------------------------

    last_xr18_reconnect = 0.0

    last_usb_check = 0.0

    last_status_update = 0.0

    # -----------------------------------------------------------------------
    # Audio diagnostics
    # -----------------------------------------------------------------------

    session_xr18_frames = 0

    # -----------------------------------------------------------------------
    # Last known meter values
    # -----------------------------------------------------------------------
    #
    # These are retained between status updates.
    #
    # Meter processing itself remains on the fast audio path.
    #

    levels = meter.levels

    # -----------------------------------------------------------------------
    # Main process
    # -----------------------------------------------------------------------

    try:

        while not shutdown_event.is_set():

            # ===============================================================
            # FAST AUDIO PATH
            # ===============================================================
            #
            # Everything below this point should be kept as lightweight
            # as possible.
            #
            # In particular:
            #
            #   NO filesystem statistics
            #   NO directory scans
            #   NO free-space queries
            #   NO recording-size queries
            #   NO status_queue calls
            #
            # ===============================================================


            # ---------------------------------------------------------------
            # XR18 disconnected
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

                        # If USB is already available, start recording.

                        if (
                            usb_mount_point is not None
                            and recorder is None
                        ):

                            recorder = start_recorder(
                                usb_mount_point
                            )

                            if recorder is not None:

                                session_xr18_frames = 0

                # Avoid unnecessary CPU usage while disconnected.

                time.sleep(0.01)

                continue


            # ===============================================================
            # SLOW PATH
            # ===============================================================
            #
            # USB discovery is only required when we currently have no
            # known USB mount point.
            #
            # This is deliberately outside the normal audio processing
            # path.
            #
            # ===============================================================

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

                    if recorder is None:

                        recorder = start_recorder(
                            usb_mount_point
                        )

                        if recorder is not None:

                            session_xr18_frames = 0


            # ===============================================================
            # FAST AUDIO PATH
            # ===============================================================
            #
            # Read the next XR18 block.
            #
            # This should be the dominant operation in the loop.
            #
            # ===============================================================

            length, data = xr18.read()


            # ---------------------------------------------------------------
            # Temporary empty read
            # ---------------------------------------------------------------

            if (
                length <= 0
                and data == b""
            ):

                # We deliberately do not sleep here.
                #
                # The XR18 is operating in non-blocking mode.
                # The loop should return immediately and try again.

                continue


            # ---------------------------------------------------------------
            # Genuine XR18 failure
            # ---------------------------------------------------------------

            if data is None:

                print(
                    "XR18 audio stream lost",
                    flush=True,
                )

                if recorder is not None:

                    print_audio_diagnostics(
                        session_xr18_frames,
                        recorder,
                    )

                    recorder.stop()

                    recorder = None

                xr18.disconnect()

                continue


            # ---------------------------------------------------------------
            # Count received frames
            # ---------------------------------------------------------------

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


            # ---------------------------------------------------------------
            # Meter
            # ---------------------------------------------------------------
            #
            # This stays on the fast path because metering requires the
            # actual audio data.
            #

            levels = meter.process(
                data
            )


            # ---------------------------------------------------------------
            # Recorder
            # ---------------------------------------------------------------
            #
            # This is the critical disk-write path.
            #
            # Recorder.write() is deliberately called immediately after
            # receiving and processing the audio block.
            #
            # No filesystem statistics or UI work happens between the
            # audio read and this write.
            #

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


            # ===============================================================
            # SLOW STATUS PATH
            # ===============================================================
            #
            # This section executes approximately once per second.
            #
            # Previously build_status() was being called for EVERY audio
            # block.
            #
            # At 48 kHz with 1024-frame blocks, that is approximately:
            #
            #     48000 / 1024 = 46.875 calls per second
            #
            # Each call could perform:
            #
            #     statfs()
            #     stat()
            #     directory scans
            #     file-size queries
            #
            # This was visible in strace and was unnecessary.
            #
            # Now these operations happen approximately once per second.
            #
            # ===============================================================

            now = time.monotonic()

            if (
                now - last_usb_check
                >= USB_CHECK_INTERVAL
            ):

                last_usb_check = now

                # -----------------------------------------------------------
                # Check existing USB storage
                # -----------------------------------------------------------

                if usb_mount_point is not None:

                    if not usb_is_available(
                        usb_mount_point
                    ):

                        print(
                            "USB storage disappeared",
                            flush=True,
                        )

                        # Print diagnostics before stopping the recorder.

                        if recorder is not None:

                            print_audio_diagnostics(
                                session_xr18_frames,
                                recorder,
                            )

                            recorder.stop()

                            recorder = None

                        usb_mount_point = None
                        usb_name = ""


            # ---------------------------------------------------------------
            # UI status update
            # ---------------------------------------------------------------
            #
            # Filesystem-heavy status functions are only called here.
            #

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

                try:

                    status_queue.put_nowait(
                        status
                    )

                except Exception:

                    # UI may be restarting or unavailable.
                    #
                    # Recording must continue regardless.

                    pass


    finally:

        print(
            "RECORDER PROCESS SHUTDOWN",
            flush=True,
        )

        # -------------------------------------------------------------------
        # Diagnostics
        # -------------------------------------------------------------------

        if recorder is not None:

            print_audio_diagnostics(
                session_xr18_frames,
                recorder,
            )

        # -------------------------------------------------------------------
        # Stop recorder
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

        # -------------------------------------------------------------------
        # Queue shutdown
        # -------------------------------------------------------------------
        #
        # We don't need the recorder process to wait for a multiprocessing
        # queue feeder thread to flush an obsolete final UI status message.
        #

        try:

            status_queue.cancel_join_thread()

        except Exception:

            pass

        print(
            "RECORDER PROCESS STOPPED",
            flush=True,
        )