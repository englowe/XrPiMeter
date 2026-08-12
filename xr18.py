"""
XRPimeter XR18 interface.

This module is responsible for:

    1. Finding the Behringer XR18 in ALSA.
    2. Determining which ALSA card/device number it has been assigned.
    3. Opening the XR18 with the correct audio settings.
    4. Verifying that 18-channel audio can actually be read.
    5. Providing blocks of audio data to the meter and recorder.
    6. Detecting genuine XR18/ALSA failures.

Important:

Linux assigns ALSA card numbers dynamically.

The XR18 might therefore appear as:

    hw:0,0
    hw:1,0
    hw:2,0
    hw:3,0

etc.

We therefore NEVER hard-code the XR18 as hw:2,0.

Instead, we ask ALSA which capture devices currently exist and find
the device whose description contains X18 or XR18.
"""


# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

import re
import subprocess

import alsaaudio


# ---------------------------------------------------------------------------
# XR18 audio configuration
# ---------------------------------------------------------------------------

# The XR18 provides 18 USB audio channels.
#
# Channels 1-16 are the main mixer inputs.
# Channels 17-18 provide the additional stereo pair.
#
# XRPimeter currently captures all 18 channels.
CHANNELS = 18


# The XR18 operates at 48 kHz.
#
# 48,000 samples are provided every second for EACH channel.
SAMPLE_RATE = 48000


# Number of audio frames requested from ALSA at a time.
#
# A frame contains one sample from every channel.
#
# Therefore:
#
#     1 frame = 18 samples
#
# Each sample is stored by ALSA in a 32-bit container:
#
#     1 sample = 4 bytes
#
# Therefore:
#
#     1 frame = 18 × 4 = 72 bytes
#
# A 1024-frame block therefore contains:
#
#     1024 × 72 = 73,728 bytes
#
PERIOD_SIZE = 1024


# The XR18 audio interface is exposed to ALSA as S32_LE.
#
# S32_LE means:
#
#     S32 = signed 32-bit container
#     LE  = little-endian byte order
#
# The actual audio resolution is 24-bit, but the samples are transported
# inside 32-bit containers.
AUDIO_FORMAT = alsaaudio.PCM_FORMAT_S32_LE


# ---------------------------------------------------------------------------
# XR18 class
# ---------------------------------------------------------------------------

class XR18:
    """
    Handles discovery and capture of the Behringer XR18.

    The class deliberately does not assume a particular ALSA card number.

    For example, if Linux currently assigns the XR18:

        hw:2,0

    this class will discover that automatically.

    If the Pi is rebooted and Linux assigns it:

        hw:1,0

    the class will discover that instead.
    """

    def __init__(self):

        # ALSA device name.

        # Example:
        #
        #     hw:2,0
        #
        # This is discovered when find_device() is called.
        self.device_name = None


        # Once the XR18 has been successfully opened, this contains the
        # Python ALSA PCM object used to receive audio.
        self.audio = None


        # Simple state flag used by main.py.
        #
        # True  = XR18 is currently open and usable.
        # False = XR18 isn't currently available.
        self.connected = False


    # -----------------------------------------------------------------------
    # Discover the XR18
    # -----------------------------------------------------------------------

    def find_device(self):
        """
        Search ALSA for an X18/XR18 capture device.

        Returns:

            True
                An XR18 was found and self.device_name was populated.

            False
                No XR18 was found.

        We use:

            arecord -l

        because this asks ALSA for its current list of capture devices.
        """

        # Ask ALSA for its current capture-device list.
        result = subprocess.run(
            ["arecord", "-l"],
            capture_output=True,
            text=True
        )


        # If arecord itself failed, there is no useful output to search.
        if result.returncode != 0:

            self.device_name = None

            return False


        # ALSA produces lines similar to:
        #
        #     card 2: x18 [x18], device 0: USB Audio [USB Audio]
        #
        # We need the card number and device number.
        pattern = re.compile(
            r"card\s+(\d+):\s+([^\s\[]+).*?,\s+device\s+(\d+):",
            re.IGNORECASE
        )


        # Examine each line returned by ALSA.
        for line in result.stdout.splitlines():

            # Try to extract the ALSA card/device numbers.
            match = pattern.search(line)

            if not match:
                continue


            # Convert the numbers from strings to integers.
            card = int(match.group(1))
            device = int(match.group(3))


            # Look for the XR18/X18 in the device description.
            #
            # lower() makes this comparison case-insensitive.
            if (
                "x18" in line.lower()
                or "xr18" in line.lower()
            ):

                # Build the ALSA hardware-device name.
                #
                # For example:
                #
                #     card  = 2
                #     device = 0
                #
                # becomes:
                #
                #     hw:2,0
                self.device_name = f"hw:{card},{device}"

                return True


        # Nothing matching X18/XR18 was found.
        self.device_name = None

        return False


    # -----------------------------------------------------------------------
    # Open and verify the XR18
    # -----------------------------------------------------------------------

    def connect(self):
        """
        Find and open the XR18.

        Opening the ALSA device isn't sufficient to prove that it works,
        so we also perform an actual audio read.

        Returns:

            True
                The XR18 was found, opened and supplied valid audio.

            False
                The XR18 could not be found or opened.
        """

        # Find the XR18 dynamically.
        if not self.find_device():

            self.connected = False

            return False


        try:

            # Open the ALSA capture device using the configuration required
            # by XRPimeter.
            self.audio = alsaaudio.PCM(
                type=alsaaudio.PCM_CAPTURE,
                mode=alsaaudio.PCM_NORMAL,
                device=self.device_name,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                format=AUDIO_FORMAT,
                periodsize=PERIOD_SIZE
            )


            # ---------------------------------------------------------------
            # Verify that actual audio can be read
            # ---------------------------------------------------------------
            #
            # An ALSA device can appear in the device list even when it
            # isn't currently capable of supplying audio.
            #
            # Therefore we perform one real read before declaring the
            # connection successful.

            length, data = self.audio.read()


            # A zero-length result during initial connection isn't useful
            # enough to declare the device working.
            #
            # This is different from the normal read() method below,
            # where a temporary zero-frame read is simply ignored.
            if length <= 0 or not data:

                self.disconnect()

                return False


            # ---------------------------------------------------------------
            # Verify the amount of received data
            # ---------------------------------------------------------------
            #
            # Each frame should contain:
            #
            #     18 channels × 4 bytes = 72 bytes
            #
            # Therefore the total data size should be:
            #
            #     frames × 18 × 4

            expected_bytes = (
                length
                * CHANNELS
                * 4
            )

            actual_bytes = len(data)


            # If the amount of data doesn't match the requested format,
            # something is wrong with the capture configuration.
            if actual_bytes != expected_bytes:

                self.disconnect()

                return False


            # Everything passed.
            self.connected = True

            return True


        except alsaaudio.ALSAAudioError as error:

            print(
                f"XR18 ALSA error while connecting: {error}"
            )

            self.disconnect()

            return False


    # -----------------------------------------------------------------------
    # Read an audio block
    # -----------------------------------------------------------------------

    def read(self):
        """
        Read one block of interleaved XR18 audio.

        Returns:

            (length, data)

                when audio was successfully received.

            (0, b"")

                when ALSA temporarily returns zero frames.

                This is NOT treated as a disconnection.

            (0, None)

                when an actual ALSA error occurs.

        This distinction is important.

        During testing we discovered that the XR18 can occasionally return:

            length = 0
            data   = None

        without producing an ALSA error.

        That does not necessarily mean the XR18 has disconnected.

        Therefore main.py must not restart the XR18 merely because one
        read contains zero frames.
        """

        # If there is no open ALSA device, there is nothing to read.
        if self.audio is None:

            return 0, None


        try:

            # Ask ALSA for the next block of audio.
            length, data = self.audio.read()


            # A zero-frame read is treated as a temporary empty read.
            #
            # We deliberately DO NOT set connected = False here.
            #
            # The XR18 may immediately provide audio on the next read,
            # which is exactly what we observed during testing.
            if length <= 0:

                return 0, b""


            # Normal successful audio block.
            return length, data


        except alsaaudio.ALSAAudioError as error:

            # This is different from a zero-frame read.
            #
            # ALSA has actually reported a capture error, so the XR18
            # should be considered unavailable.
            print(
                f"XR18 ALSA read error: {error}"
            )

            self.connected = False

            return 0, None


    # -----------------------------------------------------------------------
    # Disconnect
    # -----------------------------------------------------------------------

    def disconnect(self):
        """
        Release the ALSA device and return to the disconnected state.
        """

        # Delete the PCM object so ALSA releases the underlying device.
        if self.audio is not None:

            del self.audio


        # Reset the object to its initial state.
        self.audio = None
        self.connected = False