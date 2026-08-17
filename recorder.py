"""
XRPimeter audio recorder.

This module receives the 18-channel audio stream from the XR18 and writes
it to separate synchronised mono WAV files.

The recorder is deliberately responsible ONLY for recording.

It does NOT:
    - detect the XR18
    - mount or unmount USB storage
    - decide whether the USB is available
    - calculate audio meter levels
    - control the LEDs

Those jobs belong to other modules.

Recording structure
-------------------

A recording session contains one or more 20-minute parts.

Example with a valid system clock:

    12_08_2026_19-42-16/
    |
    +-- README.txt
    |
    +-- Part 1 - 12_08_2026_19-42-16/
    |   +-- Part 1 CH 1.wav
    |   +-- Part 1 CH 2.wav
    |   +-- ...
    |   +-- Part 1 CH 18.wav
    |
    +-- Part 2 - 12_08_2026_20-02-16/
        +-- Part 2 CH 1.wav
        +-- ...
        +-- Part 2 CH 18.wav

If the system clock is not trustworthy:

    Session 1/
    |
    +-- README.txt
    |
    +-- Part 1/
    |   +-- Part 1 CH 1.wav
    |   +-- ...
    |
    +-- Part 2/
        +-- Part 2 CH 1.wav
        +-- ...

The session README deliberately does not state how many parts the session
contains, because the number of parts is not known when the session starts.

Each part is closed cleanly before the next part begins. This limits the
amount of audio that could be affected by a failure.
"""

import shutil
import wave
from pathlib import Path

import numpy as np

# XRPimeter's central logging system.
#
# Every module writes through the same logger so that all events end up in
# the monthly XRPimeter system log.
from xrp_log import get_logger

# XRPimeter's time-status system.
#
# We use this rather than blindly trusting datetime.now(), because a Pi
# without an RTC and without NTP can have an invalid system clock.
from time_status import (
    get_time_status,
    format_filename_time,
)


# Get the central XRPimeter logger.
logger = get_logger()


# ---------------------------------------------------------------------------
# Recording configuration
# ---------------------------------------------------------------------------

# The XR18 provides 18 audio channels.
CHANNELS = 18

# XR18 sample rate.
SAMPLE_RATE = 48000

# The actual audio resolution is 24 bits.
#
# 24 bits = 3 bytes per sample.
OUTPUT_BYTES_PER_SAMPLE = 3

# Maximum length of one recording part.
#
# The recorder uses the number of audio frames written rather than the
# computer's wall clock to determine when a part has reached 20 minutes.
#
# This is preferable because the audio stream itself is the thing we are
# measuring.
PART_LENGTH_SECONDS = 20 * 60

PART_LENGTH_FRAMES = (
    SAMPLE_RATE * PART_LENGTH_SECONDS
)


# ---------------------------------------------------------------------------
# Recorder class
# ---------------------------------------------------------------------------

class Recorder:
    """
    Records the 18 XR18 channels as separate synchronised mono WAV files.

    One Recorder object represents one recording session.

    The session may contain multiple 20-minute parts.
    """

    def __init__(self, recordings_root):

        # Convert the supplied recording location to a Path object.
        #
        # For example:
        #
        #     /mnt/xrpimeter-usb/Recordings
        #
        self.recordings_root = Path(
            recordings_root
        )

        # Directory containing the entire recording session.
        self.session_dir = None

        # Directory containing the currently active part.
        self.part_dir = None

        # List of currently open WAV files.
        #
        # There is one WAV file per XR18 channel.
        self.wav_files = []

        # True while the recorder is actively accepting audio.
        self.recording = False

        # Current part number.
        #
        # This starts at zero and is incremented when Part 1 is created.
        self.part_number = 0

        # Number of audio frames written to the current part.
        #
        # This allows us to determine exactly when 20 minutes of audio
        # have been written.
        self.part_frames_written = 0

        # Whether the system clock was considered valid when the session
        # began.
        self.time_valid = False

        # Whether the time came from NTP, an RTC, or neither.
        self.time_source = "NONE"

        # The time at which the recording session started.
        self.session_start_time = None


    # -----------------------------------------------------------------------
    # Start a recording session
    # -----------------------------------------------------------------------

    def start(self):
        """
        Start a new recording session.

        Creates:

            session directory
            README.txt
            Part 1 directory
            18 WAV files

        Returns:

            True  = recording session successfully started
            False = recording session could not be started
        """

        # Ask the time-status module for one complete snapshot.
        #
        # This tells us whether it is safe to use the system date/time.
        time_status = get_time_status()

        self.session_start_time = (
            time_status["current_time"]
        )

        self.time_valid = (
            time_status["valid"]
        )

        self.time_source = (
            time_status["source"]
        )


        # -------------------------------------------------------------------
        # Determine the session directory name
        # -------------------------------------------------------------------

        if self.time_valid:

            # The system clock is trustworthy.
            #
            # Example:
            #
            #     12_08_2026_19-42-16
            #
            session_name = format_filename_time(
                self.session_start_time
            )

        else:

            # The clock cannot be trusted.
            #
            # We deliberately do NOT create something like:
            #
            #     01_01_1970_00-00-00
            #
            # because that would look like a genuine recording date.
            #
            # Instead use:
            #
            #     Session 1
            #     Session 2
            #     Session 3
            #
            session_number = (
                self._find_next_session_number()
            )

            session_name = (
                f"Session {session_number}"
            )


        self.session_dir = (
            self.recordings_root / session_name
        )


        # -------------------------------------------------------------------
        # Create the session directory
        # -------------------------------------------------------------------

        try:

            self.session_dir.mkdir(
                parents=True,
                exist_ok=False
            )

        except OSError as error:

            logger.error(
                f"Unable to create recording session "
                f"{self.session_dir}: {error}"
            )

            print(
                f"ERROR: Unable to create recording session: {error}"
            )

            self.session_dir = None

            return False


        # -------------------------------------------------------------------
        # Create the session README
        # -------------------------------------------------------------------

        try:

            self._write_session_readme()

        except OSError as error:

            logger.error(
                f"Unable to create session README in "
                f"{self.session_dir}: {error}"
            )

            print(
                f"ERROR: Unable to create session README: {error}"
            )

            # Remove the session directory if it is still empty.
            try:
                self.session_dir.rmdir()
            except OSError:
                pass

            self.session_dir = None

            return False


        # -------------------------------------------------------------------
        # Start Part 1
        # -------------------------------------------------------------------

        self.part_number = 0

        if not self._start_part():

            logger.error(
                f"Unable to start Part 1 of session "
                f"{self.session_dir}"
            )

            print(
                "ERROR: Unable to start recording Part 1."
            )

            self.session_dir = None

            return False


        # Everything required for recording now exists.
        self.recording = True


        # Record the successful start in the system log.
        logger.info(
            f"Recording session started: {self.session_dir} "
            f"time_source={self.time_source} "
            f"time_valid={self.time_valid}"
        )


        print()
        print(
            f"Recording session: {self.session_dir}"
        )
        print(
            f"Recording Part:    {self.part_number}"
        )
        print()


        return True


    # -----------------------------------------------------------------------
    # Find the next available session number
    # -----------------------------------------------------------------------

    def _find_next_session_number(self):
        """
        Find the next available Session X number.

        Used when the system clock is invalid.

        Example:

            Session 1
            Session 2
            Session 3

        If those all exist, the function returns 4.
        """

        number = 1

        while (
            self.recordings_root
            / f"Session {number}"
        ).exists():

            number += 1

        return number


    # -----------------------------------------------------------------------
    # Start a recording part
    # -----------------------------------------------------------------------

    def _start_part(self):
        """
        Create the directory and WAV files for the next recording part.

        Returns:

            True  = part successfully created
            False = part could not be created
        """

        # Increase the part number.
        self.part_number += 1


        # Get the current time.

        # We only use this timestamp if the clock was already considered
        # valid when the session began.
        #
        # If the session started with an invalid clock, we continue using
        # simple Part 1 / Part 2 naming for the entire session.
        part_time_status = get_time_status()

        part_time = (
            part_time_status["current_time"]
        )


        # -------------------------------------------------------------------
        # Determine the part directory name
        # -------------------------------------------------------------------

        if self.time_valid:

            # Example:
            #
            #     Part 1 - 12_08_2026_19-42-16
            #
            timestamp = format_filename_time(
                part_time
            )

            part_name = (
                f"Part {self.part_number} - {timestamp}"
            )

        else:

            # No trustworthy clock, so use a simple part number.
            part_name = (
                f"Part {self.part_number}"
            )


        self.part_dir = (
            self.session_dir / part_name
        )


        # -------------------------------------------------------------------
        # Create the part directory
        # -------------------------------------------------------------------

        try:

            self.part_dir.mkdir(
                parents=True,
                exist_ok=False
            )

        except OSError as error:

            logger.error(
                f"Unable to create recording part "
                f"{self.part_dir}: {error}"
            )

            print(
                f"ERROR: Unable to create recording part: {error}"
            )

            return False


        # Start with no open WAV files.
        self.wav_files = []


        # -------------------------------------------------------------------
        # Create the 18 channel WAV files
        # -------------------------------------------------------------------

        try:

            for channel in range(
                1,
                CHANNELS + 1
            ):

                # WAV filenames deliberately do not contain the timestamp.
                #
                # The timestamp is already represented by the session and
                # part directories.
                #
                # Example:
                #
                #     Part 1 CH 1.wav
                #     Part 1 CH 2.wav
                #     ...
                #     Part 1 CH 18.wav
                filename = (
                    f"Part {self.part_number} "
                    f"CH {channel}.wav"
                )


                path = (
                    self.part_dir / filename
                )


                # Open the WAV file for writing.
                wav = wave.open(
                    str(path),
                    "wb"
                )


                # One channel per file.
                wav.setnchannels(1)


                # 24-bit audio = 3 bytes per sample.
                wav.setsampwidth(
                    OUTPUT_BYTES_PER_SAMPLE
                )


                # 48 kHz sample rate.
                wav.setframerate(
                    SAMPLE_RATE
                )


                # Keep the open file for write().
                self.wav_files.append(
                    wav
                )


        except (OSError, wave.Error) as error:

            logger.error(
                f"Unable to create WAV files for "
                f"Part {self.part_number}: {error}"
            )


            # Close anything that was successfully opened before the error.
            self._close_wav_files()


            print(
                f"ERROR: Unable to create WAV files: {error}"
            )

            return False


        # Reset the number of frames written for this part.
        self.part_frames_written = 0


        logger.info(
            f"Recording Part {self.part_number} started: "
            f"{self.part_dir}"
        )


        print(
            f"Recording Part {self.part_number} started."
        )


        return True


    # -----------------------------------------------------------------------
    # Write one block of audio
    # -----------------------------------------------------------------------

    def write(self, data):
        """
        Convert an interleaved XR18 S32_LE block into 18 separate 24-bit
        mono WAV streams.

        Returns:

            True
                Audio was written successfully.

            False
                Recording is not active or a recording error occurred.
        """

        # It is perfectly normal for the XR18 to be running while the
        # recorder is not.
        #
        # For example, the user may be using XRPimeter purely as a meter
        # with no USB storage attached.
        if not self.recording:
            return False


        try:

            # ---------------------------------------------------------------
            # Convert raw ALSA bytes into signed 32-bit integers
            # ---------------------------------------------------------------

            samples = np.frombuffer(
                data,
                dtype="<i4"
            )


            # ---------------------------------------------------------------
            # Separate the interleaved 18-channel audio
            # ---------------------------------------------------------------
            #
            # The XR18 sends:
            #
            #     CH1 CH2 CH3 ... CH18
            #     CH1 CH2 CH3 ... CH18
            #
            # Each row therefore represents one complete audio frame.

            samples = samples.reshape(
                (-1, CHANNELS)
            )


            # ---------------------------------------------------------------
            # Convert the XR18's S32 container to 24-bit audio
            # ---------------------------------------------------------------
            #
            # The useful 24 audio bits are stored in the upper 24 bits of
            # the 32-bit ALSA container.
            #
            # Shifting right by 8 removes the unused byte.

            samples_24 = (
                samples >> 8
            )


            # ---------------------------------------------------------------
            # Process each channel
            # ---------------------------------------------------------------

            for channel in range(CHANNELS):

                # Extract this channel from the interleaved audio.
                channel_samples = (
                    samples_24[:, channel]
                )


                # -----------------------------------------------------------
                # Convert signed values to 24-bit two's-complement form
                # -----------------------------------------------------------

                unsigned = (
                    channel_samples.astype(
                        np.int32
                    )
                    & 0xFFFFFF
                )


                # -----------------------------------------------------------
                # Split each 24-bit sample into three bytes
                # -----------------------------------------------------------
                #
                # WAV uses little-endian byte ordering:
                #
                #     byte 0 = least significant
                #     byte 1 = middle
                #     byte 2 = most significant

                bytes_24 = np.empty(
                    (len(unsigned), 3),
                    dtype=np.uint8
                )


                bytes_24[:, 0] = (
                    unsigned & 0xFF
                )

                bytes_24[:, 1] = (
                    (unsigned >> 8)
                    & 0xFF
                )

                bytes_24[:, 2] = (
                    (unsigned >> 16)
                    & 0xFF
                )


                # Write this channel's samples to its WAV file.
                self.wav_files[channel].writeframes(
                    bytes_24.tobytes()
                )


            # ---------------------------------------------------------------
            # Update our frame counter
            # ---------------------------------------------------------------

            frames_written = len(samples)

            self.part_frames_written += (
                frames_written
            )


        except (
            ValueError,
            OSError,
            wave.Error
        ) as error:

            # An error writing the audio is serious enough to record.
            logger.error(
                f"Audio write error in Part "
                f"{self.part_number}: {error}"
            )

            print(
                f"ERROR: Audio write failed: {error}"
            )

            # Stop the recorder rather than continuing as though everything
            # were healthy.
            self.stop()

            return False


        # -------------------------------------------------------------------
        # Check whether the part has reached 20 minutes
        # -------------------------------------------------------------------

        if (
            self.part_frames_written
            >= PART_LENGTH_FRAMES
        ):

            # Close this part and immediately begin the next one.
            return self._finish_part()


        return True


    # -----------------------------------------------------------------------
    # Finish one part and begin the next
    # -----------------------------------------------------------------------

    def _finish_part(self):
        """
        Close the current 20-minute part and start the next part.

        The overall recording session continues.
        """

        completed_part = (
            self.part_number
        )


        # Close all 18 WAV files.
        self._close_wav_files()


        logger.info(
            f"Recording Part {completed_part} completed"
        )


        print()
        print(
            f"Recording Part {completed_part} completed."
        )


        # Start the next part.
        if not self._start_part():

            logger.error(
                f"Unable to start Part "
                f"{completed_part + 1}"
            )

            print(
                "ERROR: Unable to start the next recording part."
            )


            # We can no longer safely continue recording.
            self.recording = False

            return False


        return True


    # -----------------------------------------------------------------------
    # Close WAV files
    # -----------------------------------------------------------------------

    def _close_wav_files(self):
        """
        Close all currently open WAV files.

        Closing the files is important because the WAV header contains
        information such as the final data size.

        The wave module updates that information when the file is closed.
        """

        for wav in self.wav_files:

            try:

                wav.close()

            except Exception as error:

                logger.error(
                    f"Error closing WAV file: {error}"
                )


        # Clear the list once all files have been closed.
        self.wav_files = []


    # -----------------------------------------------------------------------
    # Calculate available recording time
    # -----------------------------------------------------------------------

    def _get_free_recording_hours(self):
        """
        Estimate how many hours of 18-channel recording can fit in the
        currently available filesystem space.

        This is an estimate based on uncompressed 24-bit 48 kHz audio.

        Calculation:

            18 channels
            × 48,000 samples/sec
            × 3 bytes/sample

        = 2,592,000 bytes/sec

        This does not account for filesystem overhead, WAV headers or other
        files, so the result is deliberately only an estimate.
        """

        try:

            usage = shutil.disk_usage(
                self.recordings_root
            )

        except OSError:

            return None


        # Bytes of audio generated every second.
        bytes_per_second = (
            CHANNELS
            * SAMPLE_RATE
            * OUTPUT_BYTES_PER_SAMPLE
        )


        if bytes_per_second <= 0:
            return None


        # Convert available bytes into seconds of recording.
        seconds = (
            usage.free
            / bytes_per_second
        )


        # Convert seconds to hours.
        hours = (
            seconds / 3600
        )


        return hours


    # -----------------------------------------------------------------------
    # Create session README
    # -----------------------------------------------------------------------

    def _write_session_readme(self):
        """
        Create the README for the recording session.

        This records information known at the beginning of the session.

        It intentionally does NOT say how many parts will be created.
        """

        readme_path = (
            self.session_dir / "README.txt"
        )


        # ---------------------------------------------------------------
        # Format the starting time
        # ---------------------------------------------------------------

        start_time = (
            self.session_start_time.strftime(
                "%d/%m/%Y %H:%M:%S"
            )
        )


        # ---------------------------------------------------------------
        # Get initial free space and recording-time estimate
        # ---------------------------------------------------------------

        try:

            usage = shutil.disk_usage(
                self.recordings_root
            )

            free_bytes = usage.free

        except OSError:

            free_bytes = None


        free_hours = (
            self._get_free_recording_hours()
        )


        # ---------------------------------------------------------------
        # Build the README
        # ---------------------------------------------------------------

        lines = [
            "XRPimeter Recording Session",
            "===========================",
            "",
            f"Session start: {start_time}",
            f"Time source: {self.time_source}",
            f"Time valid: {'YES' if self.time_valid else 'NO'}",
            "",
            f"Sample rate: {SAMPLE_RATE} Hz",
            f"Channels: {CHANNELS}",
            "Bit depth: 24-bit",
            "Recording format: PCM WAV",
            "Maximum part length: 20 minutes",
            "",
        ]


        # Add storage information if it could be obtained.
        if free_bytes is not None:

            free_gb = (
                free_bytes
                / 1_000_000_000
            )

            lines.append(
                f"Free space at session start: "
                f"{free_gb:.2f} GB"
            )


        if free_hours is not None:

            lines.append(
                f"Estimated recording time available "
                f"at session start: {free_hours:.1f} hours"
            )

        else:

            lines.append(
                "Estimated recording time available "
                "at session start: unavailable"
            )


        lines.append("")


        # Write the README using UTF-8.
        readme_path.write_text(
            "\n".join(lines),
            encoding="utf-8"
        )


   
    # -----------------------------------------------------------------------
    # Stop the entire recording session
    # -----------------------------------------------------------------------

    def stop(self):
        """
        Stop the current recording session.

        The current part is closed cleanly.

        No new part is created.

        Returns:

            True
                Recording files were closed.

            False
                Recorder was not active.
        """

        if not self.recording:
            return False


        completed_part = (
            self.part_number
        )


        # ---------------------------------------------------------------
        # Tell the system log that file closure has begun.
        # ---------------------------------------------------------------

        logger.info(
            f"Closing WAV files for Part "
            f"{completed_part}"
        )


        print(
            "Closing WAV files..."
        )


        # ---------------------------------------------------------------
        # Close all currently open WAV files.
        # ---------------------------------------------------------------
        #
        # This is important because the WAV headers contain the final
        # data size. wave.close() writes the completed header.

        self._close_wav_files()


        # ---------------------------------------------------------------
        # Mark recording as stopped.
        # ---------------------------------------------------------------

        self.recording = False


        # ---------------------------------------------------------------
        # Log successful closure.
        # ---------------------------------------------------------------

        logger.info(
            f"WAV files closed for Part "
            f"{completed_part}"
        )


        print(
            "WAV files closed."
        )


        # ---------------------------------------------------------------
        # Reset active-part information.
        # ---------------------------------------------------------------

        self.part_dir = None
        self.part_frames_written = 0


        # ---------------------------------------------------------------
        # Log the completed recording session.
        # ---------------------------------------------------------------

        logger.info(
            f"Recording session stopped: "
            f"{self.session_dir} "
            f"last_part={completed_part}"
        )


        print(
            "Recording stopped."
        )


        return True

    # -----------------------------------------------------------------------
    # Safety cleanup
    # -----------------------------------------------------------------------

    def __del__(self):
        """
        Safety net for closing WAV files if the Recorder object is destroyed.

        main.py should normally call stop() explicitly.

        This exists as a final precaution against leaving files open if the
        Python object is destroyed unexpectedly.
        """

        try:

            self._close_wav_files()

        except Exception:

            # Never allow destructor errors during Python shutdown.
            pass