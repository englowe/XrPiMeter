"""
XRPimeter time and clock status.

This module determines whether the Raspberry Pi's system clock can be
trusted for recording timestamps.

Why this matters
----------------

XRPimeter uses the system date and time for:

    - Recording session folder names
    - WAV filenames
    - Session README files
    - System logs

A Raspberry Pi may not have an RTC fitted. If it is also offline and
there is no network time synchronisation, Linux may start with an
incorrect date/time.

We therefore NEVER assume that datetime.now() is automatically reliable.

This module reports:

    - Current system time
    - Whether an RTC device exists
    - Whether the system clock is synchronised
    - Whether the current time appears plausible
    - A simple overall validity status

The recorder can then decide whether it is safe to use the current
date/time in filenames.
"""

from datetime import datetime
from pathlib import Path
import subprocess


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# A normal XRPimeter will obviously be operating after this date.
#
# This catches the classic Raspberry Pi situation where the clock starts
# somewhere around 1970 because there was no valid clock source at boot.
#
# This isn't intended to prove the exact date is correct. It simply prevents
# obviously invalid timestamps from being treated as valid.
MIN_VALID_YEAR = 2020


# Path used by Linux for the first RTC device.
#
# On a normal Raspberry Pi this is usually:
#
#     /sys/class/rtc/rtc0
#
# We don't assume that the RTC actually exists, however.
RTC_PATH = Path("/sys/class/rtc/rtc0")


# ---------------------------------------------------------------------------
# Check for RTC hardware
# ---------------------------------------------------------------------------

def rtc_present():
    """
    Check whether Linux has an RTC device available.

    Returns:

        True
            An RTC device exists.

        False
            No RTC device was detected.

    Important:
        This only tells us that RTC hardware exists.

        It does NOT tell us that the RTC contains the correct time.
    """

    return RTC_PATH.exists()


# ---------------------------------------------------------------------------
# Check whether Linux considers the clock synchronised
# ---------------------------------------------------------------------------

def clock_synchronised():
    """
    Ask systemd whether the system clock is synchronised.

    Raspberry Pi OS uses systemd, so timedatectl provides a convenient
    way of asking Linux about the current clock state.

    Returns:

        True
            Linux reports that the clock is synchronised.

        False
            Linux reports that the clock is not synchronised, or the
            status could not be determined.
    """

    try:

        result = subprocess.run(
            [
                "timedatectl",
                "show",
                "--property=NTPSynchronized",
                "--value",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

    except (subprocess.SubprocessError, OSError):

        # If timedatectl isn't available or fails, we cannot claim that
        # the clock is synchronised.
        return False


    # systemd normally returns:
    #
    #     yes
    #
    # or:
    #
    #     no
    #
    return result.stdout.strip().lower() == "yes"


# ---------------------------------------------------------------------------
# Get current system time
# ---------------------------------------------------------------------------

def get_current_time():
    """
    Return the Raspberry Pi's current system time.

    The datetime returned here is the local system time, including the
    timezone configured on the Pi.

    This function deliberately does NOT decide whether the time is valid.
    That is handled separately by get_time_status().
    """

    return datetime.now()


# ---------------------------------------------------------------------------
# Check whether the date looks plausible
# ---------------------------------------------------------------------------

def time_looks_valid(current_time):
    """
    Check whether the system date is at least plausible.

    This is deliberately a simple sanity check.

    We are mainly trying to detect an uninitialised Raspberry Pi clock,
    which commonly results in a date around 1970.

    Returns:

        True
            The date is plausible.

        False
            The date is clearly invalid.
    """

    return current_time.year >= MIN_VALID_YEAR


# ---------------------------------------------------------------------------
# Get complete time status
# ---------------------------------------------------------------------------

def get_time_status():
    """
    Get a complete snapshot of the Pi's clock status.

    Returns a dictionary containing:

        current_time
            The current system time.

        rtc_present
            Whether an RTC device exists.

        ntp_synchronised
            Whether systemd reports the clock as synchronised.

        time_plausible
            Whether the date passes our basic sanity check.

        valid
            Whether XRPimeter considers the timestamp safe to use.

        source
            Best available indication of where the time is coming from.

    The recorder can use this information when deciding whether to use
    date/time based recording names.
    """

    current_time = get_current_time()

    has_rtc = rtc_present()
    ntp_sync = clock_synchronised()
    plausible = time_looks_valid(current_time)


    # -----------------------------------------------------------------------
    # Decide whether the time can be trusted
    # -----------------------------------------------------------------------
    #
    # We consider the time valid if:
    #
    #     1. Linux has synchronised it using NTP
    #
    # OR:
    #
    #     2. A hardware RTC exists AND the resulting date looks plausible
    #
    # The second case is important for an offline XRPimeter.
    #
    # If there is no RTC and no NTP synchronisation, we cannot confidently
    # say that the date is correct.
    valid = (
        plausible
        and (
            ntp_sync
            or has_rtc
        )
    )


    # -----------------------------------------------------------------------
    # Determine the most likely time source
    # -----------------------------------------------------------------------

    if ntp_sync:

        source = "NTP"

    elif has_rtc:

        source = "RTC"

    else:

        source = "NONE"


    return {
        "current_time": current_time,
        "rtc_present": has_rtc,
        "ntp_synchronised": ntp_sync,
        "time_plausible": plausible,
        "valid": valid,
        "source": source,
    }


# ---------------------------------------------------------------------------
# Format a timestamp for filenames
# ---------------------------------------------------------------------------

def format_filename_time(current_time):
    """
    Convert a datetime into the XRPimeter filename format.

    Example:

        12 August 2026 at 19:42:16

    becomes:

        12_08_2026_19-42-16

    This keeps filenames sortable and avoids characters such as ':'
    which are awkward on some filesystems.
    """

    return current_time.strftime("%d_%m_%Y_%H-%M-%S")

