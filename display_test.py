"""
XRPimeter OLED display test.

This does NOT connect to:
    - XR18
    - ALSA
    - USB storage
    - recorder
    - meter

It simply feeds simulated data into display.py.

Press Ctrl+C to stop.
"""

import time

from display import (
    Display,
    DISPLAY_UPDATE_INTERVAL,
)


# ===========================================================================
# TEST CONFIGURATION
# ===========================================================================

# Simulated USB volume name.
USB_NAME = "LOD"

# Simulated recording path.
FOLDER_PATH = (
    r"LOD\Recordings\2026-08-16-06-09\Part 1"
)

# Simulated recording state.
RECORDING = True

# Simulated elapsed recording time.
ELAPSED_SECONDS = (
    1 * 3600
    + 1 * 60
    + 12
)

# Simulated remaining recording time.
REMAINING_SECONDS = (
    5 * 3600
    + 42 * 60
)

# Simulated current recording size.
RECORDING_SIZE_GB = 1.25

# Simulated free USB capacity.
FREE_SPACE_GB = 18.7


# ===========================================================================
# SIMULATED CHANNEL LEVELS
# ===========================================================================

LEVELS = [

    -30,   # CH1
    -18,   # CH2
    -12,   # CH3
    -8,    # CH4
    -5,    # CH5
    -3,    # CH6
    -10,   # CH7
    -20,   # CH8
    -40,   # CH9
    -15,   # CH10
    -7,    # CH11
    -2,    # CH12
    -25,   # CH13
    -50,   # CH14
    -10,   # CH15
    -6,    # CH16
    -30,   # CH17
    -1,    # CH18

]


# ===========================================================================
# START DISPLAY
# ===========================================================================

display = Display()


try:

    print()
    print("XRPimeter OLED display test")
    print("----------------------------")
    print()
    print("Simulated XR18: connected")
    print("Simulated USB: connected")
    print("Simulated recording: active")
    print()
    print("The USB/folder path should scroll.")
    print("The top-right display alternates time and CPU temperature.")
    print("The temperature is sampled once per temperature display.")
    print()
    print("Press Ctrl+C to stop.")
    print()


    while True:




        display.update(



            levels=LEVELS,

            xr18_connected=True,

            usb_available=True,

            usb_name=USB_NAME,

            recording=RECORDING,

            elapsed_seconds=ELAPSED_SECONDS,

            recording_size_gb=RECORDING_SIZE_GB,

            free_space_gb=FREE_SPACE_GB,

            remaining_seconds=REMAINING_SECONDS,

            folder_path=FOLDER_PATH,

        )



        time.sleep(
            DISPLAY_UPDATE_INTERVAL
        )


except KeyboardInterrupt:

    print()
    print("Stopping OLED test...")


finally:

    display.close()

    print("OLED test stopped.")
