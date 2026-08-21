XrPiMeter

Raspberry Pi-based 18-channel audio meter and recorder for the Behringer XR18.

XrPiMeter receives the XR18’s USB audio stream, displays real-time levels for all 18 channels, and can record the same audio stream to removable USB storage as 18 synchronised mono WAV files.

It is designed to operate as a standalone, headless recording appliance.


Features

    18-channel XR18 USB audio capture
    Automatic XR18 ALSA device discovery
    No hard-coded ALSA card number
    48 kHz audio capture
    24-bit PCM WAV recording
    One synchronised mono WAV file per XR18 channel
    Real-time 18-channel audio metering
    USB storage is optional
    Automatic USB storage detection
    Automatic USB mounting through UDisks2
    Detection of USB removal while recording
    Automatic XR18 disconnect/reconnect handling
    Recordings divided into 20-minute parts
    Automatic rollover between recording parts
    Timestamped recording sessions when the system clock is trusted
    Safe fallback session numbering when the system clock is not trusted
    OLED status display
    18-channel LED level meter
    Recording and USB status indication
    Graceful shutdown through the Raspberry Pi power button
    WAV files closed cleanly before shutdown
    Central application logging
    Persistent system journalling
    Recording-session README files containing recording and storage information


Hardware

XrPiMeter is currently designed around:

    Raspberry Pi
    Behringer XR18 digital mixer
    USB storage device
    OLED display
    18-channel LED level display

The Raspberry Pi does not need the XR18 to be assigned a particular ALSA card number.

Linux can assign the XR18 different card numbers after reboot or when other USB audio devices are connected. XrPiMeter searches the available ALSA capture devices and identifies the XR18 dynamically.


System architecture

XrPiMeter is split into separate modules, with main.py acting as the application coordinator.

                         ┌──────────────┐

                         │   Behringer  │

                         │     XR18     │

                         └──────┬───────┘

                                │

                         18-channel USB

                                │

                                ▼

                         ┌──────────────┐

                         │    xr18.py  │

                         │ ALSA capture │

                         └──────┬───────┘

                                │

                                ▼

                         ┌──────────────┐

                         │   main.py    │

                         │  coordinator │

                         └──────┬───────┘

                                │

             ┌──────────────────┼──────────────────┐

             │                  │                  │

             ▼                  ▼                  ▼

        ┌─────────┐       ┌───────────┐      ┌─────────┐

        │ meter.py│       │recorder.py│      │  led.py │

        └─────────┘       └─────┬─────┘      └─────────┘

                                │

                                ▼

                         ┌──────────────┐

                         │usb_storage.py│

                         └──────┬───────┘

                                │

                                ▼

                          USB recording

                            storage


                         ┌──────────────┐

                         │ display.py   │

                         │ OLED display │

                         └──────────────┘

The modules deliberately have separate responsibilities:

main.py

Coordinates the application and manages the overall state.

It handles:

    XR18 connection state
    USB storage state
    metering
    recording
    LED updates
    OLED updates
    shutdown
    reconnection and recovery

xr18.py

Handles the XR18 USB audio interface.

It:

    discovers the XR18 through ALSA
    determines its current card/device number
    opens the capture device
    verifies that audio can actually be read
    provides audio blocks to the rest of the application
    detects ALSA capture failures
    releases the device during disconnection

The XR18 ALSA card number is never hard-coded.

meter.py

Processes the incoming 18-channel audio stream and calculates channel levels for the real-time meter.

recorder.py

Handles recording only.

It:

    creates recording sessions
    creates recording parts
    creates the 18 WAV files
    converts the XR18’s audio format to 24-bit PCM WAV
    counts audio frames
    performs 20-minute part rollover
    calculates available recording time
    creates the session README
    closes WAV files cleanly

usb_storage.py

Handles removable USB storage.

It:

    discovers USB filesystems
    identifies USB devices through lsblk
    checks whether storage is already mounted
    requests mounting through UDisks2 when required
    discovers the resulting mount point
    verifies that the filesystem is writable
    detects when the USB storage disappears

XrPiMeter does not assume /dev/sda1, a particular USB port, or a particular mount point.

display.py

Controls the OLED dashboard.

The display provides information including:

    XR18 status
    USB status
    USB volume name
    recording status
    elapsed recording time
    estimated remaining recording time
    current recording size
    available USB space
    recording folder/path
    channel levels
    system information

led.py

Controls the physical LED indicators and 18-channel level display.

time_status.py

Determines whether the Raspberry Pi’s system clock can be trusted.

This is important because a Raspberry Pi may boot without an RTC or network time synchronisation.

xrp_log.py

Provides the central XrPiMeter logging system.


Audio

The XR18 provides 18 USB audio channels at 48 kHz.

ALSA exposes the audio as an S32_LE stream:

S32 = signed 32-bit container

LE  = little-endian

The XR18’s actual audio resolution is 24-bit.

XrPiMeter therefore converts the incoming S32_LE samples into 24-bit PCM WAV data.

Recording data rate

Uncompressed recording requires approximately:

18 channels

× 48,000 samples/sec

× 3 bytes/sample


= 2,592,000 bytes/sec

Approximately:

2.59 MB/sec

of storage is required while recording.

This means approximately:

155.5 MB/min

9.33 GB/hour

of raw audio storage is required.

Actual filesystem usage will vary slightly because of filesystem and WAV-file overhead.


Recording

USB recording is optional.

If the XR18 is connected without a suitable USB recording drive, XrPiMeter continues to operate as a real-time meter.

When suitable USB storage becomes available, XrPiMeter prepares the storage and starts a recording session.

Recording sessions

Each time recording starts, XrPiMeter creates a new session directory.

With a trusted system clock:

XRPiMeter Recordings/

└── 21_08_2026_19-42-16/

    ├── README.txt

    │

    ├── Part 1/

    │   ├── Part 1 CH 1.wav

    │   ├── Part 1 CH 2.wav

    │   ├── ...

    │   └── Part 1 CH 18.wav

    │

    └── Part 2/

        ├── Part 2 CH 1.wav

        ├── Part 2 CH 2.wav

        ├── ...

        └── Part 2 CH 18.wav

The session directory contains the recording date and time.

Individual part directories are simply:

Part 1

Part 2

Part 3

...

The timestamp does not need to be repeated because it is already represented by the session directory.


20-minute recording parts

A recording session is divided into 20-minute parts.

When a part reaches 20 minutes:

    All 18 WAV files are closed.
    Their WAV headers are finalised.
    The completed part is logged.
    The next part directory is created.
    18 new WAV files are opened.
    Recording continues.

The part length is determined from the number of audio frames written rather than the system wall clock.

This means changes to the system clock cannot affect the 20-minute recording boundary.


Untrusted system time

A Raspberry Pi without a working RTC or network time synchronisation may start with an incorrect system clock.

XrPiMeter checks the clock before creating a recording session.

If the clock cannot be trusted, it deliberately avoids creating misleading date-based filenames.

Instead:

XRPiMeter Recordings/

└── Session 1/

    ├── README.txt

    │

    ├── Part 1/

    │   ├── Part 1 CH 1.wav

    │   ├── ...

    │   └── Part 1 CH 18.wav

    │

    └── Part 2/

        ├── Part 2 CH 1.wav

        ├── ...

        └── Part 2 CH 18.wav

Subsequent sessions become:

Session 2

Session 3

Session 4

...

The session README records whether the system time was considered valid and what time source was available.


Session README

Every recording session contains a README.txt.

It records information such as:

    session start time
    time source
    whether the system time was trusted
    sample rate
    number of channels
    bit depth
    recording format
    maximum part length
    free USB storage at session start
    estimated recording time available at session start

The README intentionally does not state how many parts the session contains because that number is not known when recording starts.


USB storage

XrPiMeter does not directly mount a hard-coded device such as:

/dev/sda1

USB storage is discovered dynamically through Linux and UDisks2.

The application:

    Finds removable USB filesystems.
    Identifies USB devices using lsblk.
    Checks whether the filesystem is already mounted.
    Requests mounting through udisksctl when necessary.
    Finds the resulting mount point.
    Verifies that the filesystem is writable.
    Uses the mounted filesystem for recording.

The USB volume label is also detected and displayed by the OLED dashboard.

USB removal

USB storage can be removed while XrPiMeter is running.

If the recording USB disappears:

USB removed

     ↓

Recording stopped

     ↓

WAV files closed

     ↓

USB state cleared

     ↓

OLED/LED status updated

     ↓

XrPiMeter continues running

     ↓

USB storage searched for again

The application does not require a reboot after USB removal.


XR18 removal and reconnection

The XR18 can also be disconnected while XrPiMeter is running.

If ALSA reports a genuine capture failure:

XR18 removed

     ↓

Audio stream failure detected

     ↓

Recording stopped cleanly

     ↓

WAV files closed

     ↓

ALSA device released

     ↓

Meter/LED state cleared

     ↓

OLED continues updating

     ↓

XR18 discovery continues

When the XR18 is connected again, XrPiMeter dynamically discovers its new ALSA card number and reconnects.

The recorder then starts a new recording session when suitable USB storage is available.

A temporary zero-frame ALSA read is not automatically treated as an XR18 disconnection.


OLED display

The OLED provides a live dashboard rather than requiring an SSH connection to determine the system state.

The dashboard displays:

    XR18 connection status
    USB connection status
    USB volume name
    recording status
    elapsed recording time
    estimated remaining recording time
    recording size
    available USB space
    current recording path
    18-channel audio levels

The display is updated independently of the recording process.

This means that an audio or storage fault should not cause the user interface to freeze.


LED meter

The physical LED display provides a visual indication of the 18 audio channels.

The LEDs are used for:

    channel level indication
    recording status
    USB status
    XR18 status
    startup/shutdown indication

The LEDs are deliberately driven independently from the OLED display.


Shutdown

XrPiMeter is designed to run as a standalone Raspberry Pi appliance.

The Raspberry Pi’s physical power button is handled by the Linux/systemd shutdown mechanism.

A normal shutdown follows this general sequence:

Power button

     ↓

systemd/logind

     ↓

XrPiMeter receives shutdown request

     ↓

Recording session stopped

     ↓

WAV files closed

     ↓

XR18 disconnected

     ↓

LED shutdown

     ↓

OLED closed

     ↓

Raspberry Pi powers off

The recorder closes the active WAV files before the application exits so that their headers are finalised correctly.

The application should therefore not be terminated by simply removing power while recording.


Automatic startup

XrPiMeter is configured to run automatically as a systemd service on the Raspberry Pi.

The intended appliance workflow is:

Power on

   ↓

Raspberry Pi boots

   ↓

systemd starts XrPiMeter

   ↓

OLED dashboard starts

   ↓

XR18 is discovered

   ↓

USB storage is discovered

   ↓

Recording begins when suitable storage is available

The system does not require an SSH session or manually running python main.py during normal operation.


Logging

XrPiMeter uses a central logging system.

Important application events are logged, including:

    application startup
    XR18 connection
    XR18 disconnection
    ALSA errors
    USB storage detection
    USB storage removal
    recording session start
    recording part start
    recording part completion
    recording errors
    shutdown

System-level logs are also retained using systemd-journald.

This is particularly useful for investigating problems that occurred before a reboot.


Linux dependencies

In addition to the Python dependencies, XrPiMeter relies on Linux system components including:

    ALSA
    arecord
    UDisks2
    udisksctl
    lsblk
    findmnt
    systemd
    timedatectl

These components are normally available on Raspberry Pi OS, although exact package requirements may vary between Raspberry Pi OS releases.


Python dependencies

Python dependencies are listed in:

requirements.txt

Install them with:

pip install -r requirements.txt

A Python virtual environment is recommended.

For development:

python -m venv .venv

source .venv/bin/activate

pip install -r requirements.txt


Development and testing

Development and diagnostic scripts are kept separately in:

tests/

These scripts are intended for hardware and module testing and are not required for normal XrPiMeter operation.

The repository excludes local development environments, generated Python files and local test artefacts through .gitignore.


Project structure

XrPiMeter/

│

├── main.py

│   Main application coordinator.

│

├── xr18.py

│   XR18 discovery and ALSA audio capture.

│

├── meter.py

│   Real-time audio level metering.

│

├── recorder.py

│   18-channel WAV recording and 20-minute part rollover.

│

├── usb_storage.py

│   USB discovery, mounting and availability checking.

│

├── display.py

│   OLED dashboard.

│

├── led.py

│   Physical LED meter and status indicators.

│

├── time_status.py

│   System clock validation and timestamp handling.

│

├── xrp_log.py

│   Central application logging.

│

├── tests/

│   Development and diagnostic scripts.

│

├── requirements.txt

│   Python dependencies.

│

├── .gitignore

│   Files excluded from version control.

│

└── README.md

    Project documentation.


Current status

XrPiMeter currently provides a working:

    XR18 USB audio interface
    dynamic XR18 ALSA discovery
    18-channel real-time meter
    18-channel LED meter
    OLED status dashboard
    USB storage detection and mounting
    USB removal handling
    18-channel WAV recorder
    24-bit PCM recording
    20-minute recording rollover
    recording session structure
    system time validation
    recording metadata
    XR18 disconnect/reconnect handling
    central application logging
    graceful system shutdown
    automatic application startup

The project is currently being developed and tested on Raspberry Pi hardware with a Behringer XR18.


Licence

Licence to be decided.