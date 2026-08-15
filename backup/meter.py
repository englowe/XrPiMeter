import numpy as np


CHANNELS = 18


class Meter:
    """
    Calculates audio levels for the 18 XR18 channels.
    """

    def __init__(self):
        self.levels = [-120.0] * CHANNELS

    # -----------------------------------------------------------------------
    # Process one audio block
    # -----------------------------------------------------------------------

    def process(self, data):
        """
        Calculate RMS dB levels for all 18 channels.

        The XR18 audio arrives as interleaved little-endian 32-bit samples.
        """

        samples = np.frombuffer(
            data,
            dtype="<i4"
        )

        samples = samples.reshape(
            (-1, CHANNELS)
        )

        # Convert the XR18's 24-bit audio from its S32 container.
        samples = samples >> 8

        # Convert to floating point for level calculation.
        samples = samples.astype(np.float64)

        # Calculate RMS for each channel.
        rms = np.sqrt(
            np.mean(samples ** 2, axis=0)
        )

        # Convert to dBFS.
        #
        # 24-bit signed audio has a maximum positive value of 8388607.
        reference = 8388607.0

        with np.errstate(divide="ignore"):

            db = 20 * np.log10(
                rms / reference
            )

        # Replace zero/invalid values with -120 dB.
        db = np.nan_to_num(
            db,
            nan=-120.0,
            neginf=-120.0,
            posinf=0.0
        )

        self.levels = db.tolist()

        return self.levels

    # -----------------------------------------------------------------------
    # Display levels
    # -----------------------------------------------------------------------

    def display(self):
        """
        Print the current levels.
        """

        output = []

        for channel, level in enumerate(
            self.levels,
            start=1
        ):

            output.append(
                f"CH{channel:02d}: {level:6.1f} dB"
            )

        print(" | ".join(output))