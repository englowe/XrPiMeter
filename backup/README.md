# XrPiMeter

Raspberry Pi-based 18-channel audio recorder and real-time meter for the Behringer XR18.

XrPiMeter receives the XR18's USB audio stream, displays real-time audio levels for all 18 channels, and can optionally record the same audio stream to USB storage as separate synchronised mono WAV files.

## Features

- 18-channel XR18 USB audio capture
- 48 kHz audio
- 24-bit PCM WAV recording
- Separate mono WAV file for each XR18 channel
- Real-time channel metering
- Recording without interfering with metering
- USB storage is optional
- Automatic USB storage detection and mounting
- Automatic detection of the XR18's ALSA card number
- Recording divided into 20-minute parts
- Automatic recording rollover between parts
- Timestamped recording sessions when the system clock is trusted
- Fallback session and part numbering when the system clock is not trusted
- Central monthly system logging
- Recording-session README files containing recording and storage information

## Hardware

XrPiMeter is currently designed around:

- Raspberry Pi
- Behringer XR18 digital mixer
- USB storage device for recording

The Raspberry Pi does not need to have the XR18 assigned to a fixed ALSA card number. XrPiMeter discovers the XR18 dynamically.

## Audio

The XR18 provides:

- 18 channels
- 48,000 samples/second
- S32_LE USB audio container

The XR18's audio converters are 24-bit. XrPiMeter converts the incoming S32_LE samples to 24-bit PCM WAV data.

The recording data rate is approximately:

    18 channels × 48,000 samples/sec × 3 bytes

    = 2,592,000 bytes/sec

This is approximately 2.59 MB/s of uncompressed audio.

## Recording

USB recording is optional.

If the XR18 is connected without a USB recording drive, XrPiMeter continues to operate as a real-time meter.

When a suitable USB storage device becomes available, XrPiMeter creates the recording directory and starts recording.

### Recording structure

With a valid system clock, a recording session looks like:

    XRPiMeter Recordings/
    └── 12_08_2026_19-42-16/
        ├── README.txt
        ├── Part 1 - 12_08_2026_19-42-16/
        │   ├── Part 1 CH 1.wav
        │   ├── Part 1 CH 2.wav
        │   ├── ...
        │   └── Part 1 CH 18.wav
        └── Part 2 - 12_08_2026_20-02-16/
            ├── Part 2 CH 1.wav
            ├── ...
            └── Part 2 CH 18.wav

Each recording part is limited to 20 minutes.

When a part reaches 20 minutes, all 18 WAV files are closed cleanly and the next part is started automatically.

The WAV filenames deliberately use the part and channel number rather than repeating the timestamp because the timestamp is already represented by the directory structure.

### Invalid system time

A Raspberry Pi may start without a reliable date/time if it has no working RTC and no network time synchronisation.

XrPiMeter therefore checks the system clock before creating a recording session.

If the time cannot be trusted, it avoids creating misleading date-based filenames:

    XRPiMeter Recordings/
    └── Session 1/
        ├── README.txt
        ├── Part 1/
        │   ├── Part 1 CH 1.wav
        │   ├── ...
        │   └── Part 1 CH 18.wav
        └── Part 2/
            ├── Part 2 CH 1.wav
            ├── ...
            └── Part 2 CH 18.wav

## USB storage

XrPiMeter does not directly mount `/dev/sda1` or assume a particular USB device.

USB storage is discovered through Linux and UDisks2.

The application:

1. Finds removable USB filesystems.
2. Identifies USB devices using `lsblk`.
3. Checks whether the filesystem is already mounted.
4. Uses `udisksctl` to request mounting when necessary.
5. Finds the resulting mount point.
6. Tests that the filesystem is writable.
7. Uses the mounted filesystem for recording.

The application does not require `sudo` to perform normal USB mounting.

A Polkit rule is used so that the Raspberry Pi user can request the required UDisks2 mount operation without an authentication prompt.

## Linux dependencies

XrPiMeter relies on several Linux/system components in addition to its Python packages.

These include:

- ALSA
- `arecord`
- UDisks2
- `udisksctl`
- `lsblk`
- `findmnt`
- systemd / `timedatectl`

These are normally available on Raspberry Pi OS, but the exact installation requirements may vary between Raspberry Pi OS releases.

## Python dependencies

Python dependencies are listed in:

    requirements.txt

Install them with:

```bash
pip install -r requirements.txt

Running

The application is currently started directly with:

python main.py

The application will:

    Start XrPiMeter.
    Search for the XR18.
    Wait if the XR18 is unavailable.
    Start metering when the XR18 is connected.
    Search for USB recording storage.
    Start recording automatically when suitable storage is available.
    Continue metering if no USB storage is present.
    Stop recording if the USB storage disappears.
    Continue searching for the storage again.

Logging

XrPiMeter uses a central logging module.

System logs are stored under:
/var/log/xrpimeter/

Logs are rotated monthly.

The logging system records important events such as:

    Application startup
    XR18 connection
    XR18 disconnection
    USB storage availability
    Recording session start
    Recording part start
    Recording part completion
    Recording errors
    USB removal

Project structure

The main application currently consists of:
main.py
    Main application coordinator.

xr18.py
    XR18 discovery and ALSA audio capture.

meter.py
    Real-time audio level metering.

recorder.py
    Multi-channel WAV recording and 20-minute part rollover.

usb_storage.py
    USB device discovery, mounting and availability checking.

time_status.py
    System clock validity and timestamp handling.

xrp_log.py
    Central XRPiMeter logging.

Development

Development and diagnostic scripts are kept locally in the Tests/ directory but are currently excluded from Git using .gitignore.

Python virtual environments and generated Python cache files are also excluded from Git.

Current status

XrPiMeter currently has a working:

    XR18 USB audio interface
    18-channel audio meter
    USB storage system
    18-channel WAV recorder
    20-minute recording rollover
    Timestamp validation
    Recording session structure
    System logging

Additional hardware features such as physical LEDs, an OLED display and a dedicated recording/shutdown button are planned but are not currently part of the application.

Licence

Licence to be decided.

