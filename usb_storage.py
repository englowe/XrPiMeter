"""
XRPimeter USB storage management.

This module finds and prepares the removable USB storage used by XRPimeter.

Important:
    Linux and UDisks2 are responsible for actually mounting the USB drive.

    XRPimeter does NOT:
        - use sudo
        - run the mount command directly
        - assume the USB is /dev/sda1
        - assume a particular USB port
        - assume a particular volume name

The Polkit rule installed on the Pi allows the 'pi' user to ask UDisks2
to mount removable storage without an authentication prompt.

The rest of XRPimeter does not need to know how Linux mounted the drive.
This module simply finds a suitable USB drive and returns its mount point.
"""


import json
import subprocess
from pathlib import Path

from xrp_log import get_logger


# ---------------------------------------------------------------------------
# Central logger
# ---------------------------------------------------------------------------

# USB events are recorded in the same monthly XRPimeter log as the rest of
# the application.
logger = get_logger()


# ---------------------------------------------------------------------------
# Recording directory
# ---------------------------------------------------------------------------

# Keep XRPimeter recordings inside their own directory on the USB drive.
#
# This means that if the USB drive contains other files, XRPimeter won't
# clutter the root of the drive.
RECORDINGS_FOLDER = "XRPiMeter Recordings"


# ---------------------------------------------------------------------------
# Find USB storage devices
# ---------------------------------------------------------------------------

def find_usb_devices():
    """
    Ask Linux for a list of block devices and find removable USB
    filesystems.

    Returns:
        A list of dictionaries describing USB partitions.

    We use lsblk because it gives us information about:
        - device name
        - filesystem type
        - whether it is removable
        - how it is connected
        - mount point
        - volume label

    The important part is TRAN=usb.

    This prevents the Pi's own SD card from accidentally being treated
    as recording storage.
    """

    try:

        result = subprocess.run(
            [
                "lsblk",
                "-J",
                "-o",
                "NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS,RM,TRAN,LABEL",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

    except (
        subprocess.SubprocessError,
        OSError,
    ) as error:

        logger.error(
            f"Unable to query USB storage with lsblk: {error}"
        )

        return []


    # lsblk's JSON output is converted into normal Python data.
    data = json.loads(
        result.stdout
    )


    usb_devices = []


    # Go through every physical block device reported by Linux.
    for device in data.get(
        "blockdevices",
        []
    ):

        # We only want devices connected via USB.
        #
        # This is the key protection against accidentally selecting the
        # Raspberry Pi's own microSD card.
        if device.get("tran") != "usb":
            continue


        # USB drives normally contain one or more partitions.
        for partition in device.get(
            "children",
            []
        ):

            # We need an actual partition.
            if partition.get("type") != "part":
                continue


            # A partition without a filesystem isn't useful for recording.
            if not partition.get("fstype"):
                continue


            usb_devices.append(
                partition
            )


    return usb_devices


# ---------------------------------------------------------------------------
# Find current mount point
# ---------------------------------------------------------------------------

def get_mount_point(device):
    """
    Find where Linux has currently mounted a device.

    Example:

        /dev/sda1

    might be mounted at:

        /media/pi/LOD

    We deliberately discover this rather than hard-coding the path.
    """

    result = subprocess.run(
        [
            "findmnt",
            "-n",
            "-o",
            "TARGET",
            device,
        ],
        capture_output=True,
        text=True,
    )


    # Remove the newline returned by the command.
    mount_point = (
        result.stdout.strip()
    )


    if mount_point:
        return Path(
            mount_point
        )


    return None


# ---------------------------------------------------------------------------
# Ask UDisks2 to mount a device
# ---------------------------------------------------------------------------

def mount_device(device):
    """
    Ask UDisks2 to mount a USB filesystem.

    UDisks2 performs the actual Linux mount operation.

    Our Polkit rule allows the pi user to perform this operation without
    requiring a password.

    Returns:
        Path to the mount point, or None if mounting failed.
    """

    print(
        f"Mounting USB device: {device}"
    )


    result = subprocess.run(
        [
            "udisksctl",
            "mount",
            "-b",
            device,
        ],
        capture_output=True,
        text=True,
    )


    if result.returncode != 0:

        print(
            "USB mount failed."
        )

        print(
            result.stderr.strip()
        )


        logger.warning(
            f"USB mount failed for {device}: "
            f"{result.stderr.strip()}"
        )


        return None


    # UDisks normally prints something similar to:
    #
    #     Mounted /dev/sda1 at /media/pi/LOD.
    #
    print(
        result.stdout.strip()
    )


    logger.info(
        f"USB mounted: {device}"
    )


    # Ask Linux where it actually mounted the filesystem.
    return get_mount_point(
        device
    )


# ---------------------------------------------------------------------------
# Check that a USB is writable
# ---------------------------------------------------------------------------

def is_writable(mount_point):
    """
    Check that XRPimeter can write to the USB.

    We create a temporary test file and immediately delete it.

    This is preferable to simply checking filesystem permissions because
    a filesystem can appear writable while actually being read-only.
    """

    test_file = (
        mount_point
        / ".xrpimeter_write_test"
    )


    try:

        test_file.touch()
        test_file.unlink()

        return True


    except OSError:

        return False


# ---------------------------------------------------------------------------
# Find and prepare USB storage
# ---------------------------------------------------------------------------

def find_usb():
    """
    Find a suitable USB storage device.

    The function:

        1. Finds removable USB filesystems.
        2. Checks whether each one is already mounted.
        3. Asks UDisks2 to mount it if necessary.
        4. Finds the resulting mount point.
        5. Checks that XRPimeter can write to it.

    Returns:
        Path to the usable USB storage.

    Returns None if no suitable USB storage is available.
    """

    devices = find_usb_devices()


    # No USB storage was detected.
    if not devices:

        print(
            "No USB storage found."
        )

        return None


    # Try each USB filesystem found by Linux.
    for device_info in devices:

        device = (
            f"/dev/{device_info['name']}"
        )


        print(
            f"USB storage detected: {device}"
        )


        # ---------------------------------------------------------------
        # Is it already mounted?
        # ---------------------------------------------------------------

        mount_point = get_mount_point(
            device
        )


        # ---------------------------------------------------------------
        # If not mounted, ask UDisks2 to mount it.
        # ---------------------------------------------------------------

        if mount_point is None:

            mount_point = mount_device(
                device
            )


        # Mount failed.
        if mount_point is None:

            continue


        # ---------------------------------------------------------------
        # Verify that the mount point exists.
        # ---------------------------------------------------------------

        if not mount_point.is_dir():

            print(
                f"Invalid USB mount point: {mount_point}"
            )

            continue


        # ---------------------------------------------------------------
        # Verify that we can write to it.
        # ---------------------------------------------------------------

        if not is_writable(
            mount_point
        ):

            print(
                f"USB is not writable: {mount_point}"
            )

            logger.warning(
                f"USB is not writable: {mount_point}"
            )

            continue


        # Everything succeeded.
        #print(
        #    f"USB storage ready: {mount_point}"
       # )


        logger.info(
            f"USB storage ready: {mount_point}"
        )


        return mount_point


    # We found USB devices, but none were suitable.
    print(
        "No usable USB storage found."
    )


    return None


# ---------------------------------------------------------------------------
# Get XRPimeter recording directory
# ---------------------------------------------------------------------------

def recordings_directory(mount_point):
    """
    Return the directory where XRPimeter recordings should be stored.

    The directory is created if it does not already exist.

    Example:

        /media/pi/LOD

    becomes:

        /media/pi/LOD/XRPimeter

    Keeping this decision here means recorder.py doesn't need to know
    anything about USB mount points.
    """

    if mount_point is None:
        return None


    recordings_path = (
        Path(mount_point)
        / RECORDINGS_FOLDER
    )


    try:

        recordings_path.mkdir(
            parents=True,
            exist_ok=True
        )


    except OSError as error:

        logger.error(
            f"Unable to create XRPimeter recording "
            f"directory {recordings_path}: {error}"
        )


        return None


    return recordings_path


# ---------------------------------------------------------------------------
# Check USB is still available
# ---------------------------------------------------------------------------

def usb_is_available(mount_point):
    """
    Check whether the USB storage is still available.

    This is useful while recording.

    If somebody physically removes the USB drive, the recorder can detect
    the change instead of blindly continuing to write to a missing drive.
    """

    if mount_point is None:
        return False


    return mount_point.is_dir()



def get_usb_name(mount_point):
    """
    Return the filesystem label for the mounted USB storage.

    Returns an empty string if the label cannot be determined.
    """

    if mount_point is None:
        return ""

    try:

        result = subprocess.run(
            [
                "lsblk",
                "-J",
                "-o",
                "NAME,LABEL,MOUNTPOINTS",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        data = json.loads(
            result.stdout
        )

    except (
        subprocess.SubprocessError,
        OSError,
        json.JSONDecodeError,
    ):

        return ""

    target = str(
        mount_point
    )

    for device in data.get(
        "blockdevices",
        []
    ):

        for partition in device.get(
            "children",
            []
        ):

            mount_points = (
                partition.get(
                    "mountpoints",
                    []
                )
                or []
            )

            if target in mount_points:

                return (
                    partition.get(
                        "label"
                    )
                    or ""
                )

    return ""