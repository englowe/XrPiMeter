XrPiMeter

Raspberry Pi-based 18-channel audio recorder, real-time meter and monitoring system for the Behringer XR18.

XrPiMeter connects to the XR18 over USB, captures all 18 audio channels, displays real-time channel levels and records synchronised mono WAV files to removable USB storage.

The system is designed to run unattended once the Raspberry Pi has booted.

⸻

Features

* 18-channel XR18 USB audio capture
* Automatic XR18 ALSA device discovery
* No hard-coded ALSA card number
* 48 kHz audio capture
* 24-bit PCM WAV recording
* One synchronised mono WAV file per XR18 channel
* Real-time audio level metering
* 18-channel LED level display
* OLED status display
* Automatic USB storage detection
* Automatic USB mounting through UDisks2
* USB removal detection
* Automatic recording start when USB storage is available
* Automatic recording stop when USB storage is removed
* 20-minute recording parts
* Automatic recording-part rollover
* Recording session README files
* System clock validity checking
* Safe recording names when the system clock is unavailable
* Central application logging
* Automatic startup through systemd
* Graceful shutdown through the Raspberry Pi power button

⸻

Hardware

XrPiMeter is currently designed around:

* Raspberry Pi 5
* Behringer XR18
* Removable USB recording storage
* OLED display
* 18-channel LED level display

The XR18 provides 18 USB audio channels to the Raspberry Pi.

The Raspberry Pi handles:

* USB audio capture
* recording
* storage management
* level metering
* LEDs
* OLED status information
* system monitoring

The XR18 remains responsible for the audio hardware and mixing.

⸻

Architecture

The application is split into separate modules so that each part has a clearly defined responsibility.

                         Behringer XR18
                              │
                              │ USB audio
                              ▼
                         ┌──────────┐
                         │  xr18.py │
                         └────┬─────┘
                              │
                     18-channel audio
                              │
                 ┌────────────┴────────────┐
                 │                         │
                 ▼                         ▼
            ┌─────────┐              ┌───────────┐
            │ meter.py│              │recorder.py│
            └────┬────┘              └─────┬─────┘
                 │                         │
                 ▼                         ▼
            ┌─────────┐              USB storage
            │  led.py │
            └─────────┘
                 ┌────────────┐
                 │ display.py │
                 └─────┬──────┘
                       │
                       ▼
                  OLED display
                 ┌───────────────┐
                 │usb_storage.py │
                 └───────────────┘
                 ┌────────────────┐
                 │ time_status.py │
                 └────────────────┘
                 ┌────────────┐
                 │ xrp_log.py │
                 └────────────┘

main.py coordinates the modules but does not contain the implementation of each individual subsystem.

⸻

Audio

The XR18 USB interface provides:

* 18 channels
* 48,000 samples/second
* S32_LE USB audio containers

The XR18’s actual audio resolution is 24-bit.

XrPiMeter therefore converts the incoming 32-bit ALSA containers into 24-bit PCM WAV data.

Recording data rate

18-channel 24-bit/48 kHz audio produces:

18 × 48,000 × 3
= 2,592,000 bytes/second

Approximately:

2.59 MB/s

or:

9.33 GB/hour

before filesystem overhead and WAV headers.

⸻

Recording

Recording is performed by recorder.py.

A recording session consists of one or more 20-minute parts.

Each part contains one mono WAV file for each XR18 channel.

Example:

Part 1/
├── Part 1 CH 1.wav
├── Part 1 CH 2.wav
├── Part 1 CH 3.wav
├── ...
└── Part 1 CH 18.wav

When 20 minutes of audio frames have been written:

1. The current 18 WAV files are closed.
2. The completed part is logged.
3. A new part directory is created.
4. 18 new WAV files are opened.
5. Recording continues.

The recorder uses the number of audio frames written to determine the part length rather than relying on the system wall clock.

⸻

Recording Directory

Recordings are stored on the USB drive inside:

XRPiMeter Recordings/

For example, a USB drive labelled LOD may contain:

LOD/
└── XRPiMeter Recordings/
    └── 21_08_2026_19-42-16/
        ├── README.txt
        ├── Part 1/
        │   ├── Part 1 CH 1.wav
        │   ├── Part 1 CH 2.wav
        │   ├── ...
        │   └── Part 1 CH 18.wav
        └── Part 2/
            ├── Part 2 CH 1.wav
            ├── Part 2 CH 2.wav
            ├── ...
            └── Part 2 CH 18.wav

The timestamp is used only for the recording session directory.

Individual parts are simply named:

Part 1
Part 2
Part 3

There is therefore no duplicated timestamp in every part directory.

⸻

System Time

The Raspberry Pi may start without a trustworthy system clock if an RTC is unavailable and network time synchronisation has not yet occurred.

XrPiMeter checks the system time before creating a recording session.

If the clock is valid, the session is timestamped.

If the clock is not valid, XrPiMeter deliberately avoids creating a misleading date such as 01_01_1970.

Instead it uses:

XRPiMeter Recordings/
├── Session 1/
├── Session 2/
└── Session 3/

The session README records:

* session start time
* time source
* whether the time was considered valid
* sample rate
* channel count
* bit depth
* recording format
* available storage
* estimated recording time

⸻

USB Storage

XrPiMeter does not assume:

* /dev/sda1
* a particular USB port
* a particular volume name
* a particular Linux mount point

USB storage is discovered dynamically through Linux and UDisks2.

The application:

1. Finds USB block devices using lsblk.
2. Finds suitable filesystems.
3. Checks whether they are already mounted.
4. Requests mounting through UDisks2 if necessary.
5. Discovers the resulting mount point.
6. Checks that the filesystem is writable.
7. Creates the XRPiMeter Recordings directory.
8. Starts recording.

XrPiMeter does not directly run mount and does not require sudo for normal USB mounting.

A Polkit rule is used to allow the pi user to request the required UDisks2 mount operation.

USB removal

USB storage is monitored while recording.

If the USB drive is removed:

* the current recording session is stopped
* open WAV files are closed
* recording is stopped
* the USB state is updated
* the OLED reports the USB as unavailable
* the application continues running

When another suitable USB drive becomes available, XrPiMeter can initialise it and start a new recording session.

⸻

XR18 Detection

ALSA assigns sound-card numbers dynamically.

The XR18 may therefore appear as:

hw:0,0
hw:1,0
hw:2,0
hw:3,0

depending on the devices present when Linux starts.

XrPiMeter never assumes a fixed card number.

xr18.py queries ALSA using:

arecord -l

and searches for the XR18/X18 device.

The discovered ALSA device is then opened using the required 18-channel configuration.

XrPiMeter also performs an actual audio read before declaring the XR18 connected.

⸻

XR18 Removal

If the XR18 is physically disconnected or ALSA reports an actual capture failure:

1. The XR18 is marked disconnected.
2. The current recording is stopped cleanly.
3. The ALSA device is released.
4. Stale meter information is cleared.
5. The application continues running.
6. XrPiMeter searches for the XR18 again.

A temporary zero-frame read is not automatically treated as a disconnection.

This prevents transient empty ALSA reads from unnecessarily restarting the connection.

⸻

Metering

meter.py processes the incoming 18-channel audio stream independently of the recorder.

This allows XrPiMeter to continue functioning as a real-time meter even when recording storage is unavailable.

The resulting channel levels are used by:

* led.py
* display.py

⸻

LED Display

The LED system provides visual feedback for all 18 audio channels.

The current design uses:

* 18 channel LEDs
* USB status LED
* recording status LED

The channel LEDs provide progressive level indication and clipping indication.

The LED system also provides status states for:

* startup
* normal operation
* high signal level
* clipping
* XR18 disconnection
* USB availability
* recording
* shutdown

LED updates are handled independently of the audio-processing path.

⸻

OLED Display

The OLED provides the main status dashboard.

It displays information including:

* XR18 connection status
* USB connection status
* USB volume name
* recording status
* elapsed recording time
* estimated remaining recording time
* recording size
* available USB capacity
* current recording folder
* channel levels

The displayed recording path is intentionally simplified so that Linux mount-point details do not clutter the user interface.

The top-right status alternates between the current time and Raspberry Pi CPU temperature.

⸻

Logging

XrPiMeter uses a central logging system implemented in xrp_log.py.

Important events include:

* application startup
* XR18 connection
* XR18 disconnection
* ALSA errors
* USB detection
* USB mounting
* USB removal
* recording start
* recording part creation
* recording part completion
* recording errors
* WAV closure
* application shutdown

Logs are written to the system’s XrPiMeter log location and are intended to assist with diagnosing unattended operation.

⸻

Automatic Startup

XrPiMeter runs as a systemd service.

The service starts automatically when Raspberry Pi OS boots.

The Python virtual environment is used by the service, so the application does not need to be started manually from SSH.

After startup, XrPiMeter:

1. Initialises the hardware interfaces.
2. Searches for the XR18.
3. Waits if the XR18 is unavailable.
4. Starts metering when the XR18 becomes available.
5. Searches for USB storage.
6. Starts recording when suitable USB storage is available.
7. Continues operating if no USB storage is present.
8. Recovers from USB removal.
9. Recovers from XR18 removal.

⸻

Shutdown

The Raspberry Pi power button is used to initiate a normal operating-system shutdown.

systemd-logind detects the physical power button and requests system shutdown.

XrPiMeter receives the shutdown signal and performs its own cleanup.

The shutdown process includes:

1. Stop the recording session.
2. Close the active WAV files.
3. Finalise WAV headers.
4. Disconnect the XR18.
5. Run the LED shutdown sequence.
6. Close the OLED.
7. Allow Raspberry Pi OS to complete shutdown.

The physical power button should therefore be used instead of simply removing power from the Raspberry Pi.

⸻

Installation

The following procedure installs XrPiMeter onto a fresh Raspberry Pi.

1. Install Raspberry Pi OS

Install a current Raspberry Pi OS release using Raspberry Pi Imager.

Recommended:

* Raspberry Pi 5
* Raspberry Pi OS Lite 64-bit
* hostname: XRPimeter
* username: pi
* SSH enabled
* network configured

A desktop environment is not required.

After booting the Pi, connect over SSH:

ssh pi@XRPimeter.local

If hostname resolution is unavailable, use the Pi’s IP address:

ssh pi@192.168.x.x

⸻

2. Update Raspberry Pi OS

Run:

sudo apt update
sudo apt full-upgrade -y

Reboot:

sudo reboot

Reconnect over SSH after the reboot.

⸻

3. Install Git

Install Git:

sudo apt install -y git

Check it:

git --version

⸻

4. Install the system dependencies

XrPiMeter requires Linux audio, storage and system-management components.

Install the required packages:

sudo apt install -y \
    alsa-utils \
    udisks2 \
    polkitd \
    python3 \
    python3-venv \
    python3-pip

Check that ALSA is available:

arecord --version

Check UDisks2:

udisksctl --version

⸻

5. Clone XrPiMeter

Clone the repository into /home/pi:

cd /home/pi
git clone https://github.com/englowe/XrPiMeter.git xrpimeter

Enter the project directory:

cd /home/pi/xrpimeter

Check the repository:

ls

⸻

6. Create the Python virtual environment

Create the virtual environment:

python3 -m venv .venv

Activate it:

source .venv/bin/activate

The shell prompt should now show:

(.venv) pi@XRPimeter:~/xrpimeter $

⸻

7. Install Python dependencies

With the virtual environment active:

pip install --upgrade pip

Then install the project dependencies:

pip install -r requirements.txt

Check that Python is using the virtual environment:

which python

It should return:

/home/pi/xrpimeter/.venv/bin/python

⸻

8. Configure USB mounting

XrPiMeter uses UDisks2 rather than directly mounting USB devices.

The repository contains the required system configuration for allowing the pi user to request removable-storage mounts.

Install the relevant Polkit configuration from the repository according to the files included with the current release.

After changing Polkit configuration, restart the relevant service or reboot the Raspberry Pi.

Verify that the Pi can see a connected USB drive:

lsblk

Then verify that UDisks2 can see it:

udisksctl status

⸻

9. Test the XR18

Connect the XR18 to the Raspberry Pi using USB.

Check that ALSA detects it:

arecord -l

You should see an entry containing the XR18/X18.

Do not assume that it will be card 2.

The card number is assigned dynamically by Linux.

⸻

10. Test XrPiMeter manually

Before enabling automatic startup, run XrPiMeter manually.

Activate the virtual environment:

cd /home/pi/xrpimeter
source .venv/bin/activate

Run:

python main.py

Check that:

* the OLED starts
* the LEDs initialise
* the XR18 is detected
* channel levels respond to audio
* USB storage is detected
* a recording session is created
* WAV files are written
* removing the USB stops recording cleanly
* reconnecting the USB allows recording again
* removing the XR18 is detected
* reconnecting the XR18 restores operation

Stop the application with:

Ctrl+C

⸻

11. Install automatic startup

XrPiMeter is designed to run as a systemd service.

Install the supplied service configuration from the repository.

The service should execute:

/home/pi/xrpimeter/.venv/bin/python

with:

/home/pi/xrpimeter/main.py

as the application.

After installing the service:

sudo systemctl daemon-reload

Enable it:

sudo systemctl enable xrpimeter

Start it:

sudo systemctl start xrpimeter

Check its status:

systemctl status xrpimeter --no-pager

If everything is working, reboot:

sudo reboot

After the Pi has restarted, XrPiMeter should start automatically without an SSH session.

⸻

12. Verify automatic startup

After rebooting, wait for the Raspberry Pi to finish booting.

Check:

systemctl status xrpimeter --no-pager

The service should report:

active (running)

If troubleshooting is required:

journalctl -u xrpimeter --no-pager

The application log can also be inspected using the XrPiMeter logging system.

⸻

Updating XrPiMeter

If XrPiMeter is already installed and the repository has been updated:

cd /home/pi/xrpimeter
git pull

Activate the virtual environment:

source .venv/bin/activate

Update Python dependencies:

pip install -r requirements.txt

If system configuration files have changed, reinstall those configuration files as required.

Then restart XrPiMeter:

sudo systemctl restart xrpimeter

Check:

systemctl status xrpimeter --no-pager

⸻

Useful Commands

Check XrPiMeter service

systemctl status xrpimeter --no-pager

Start XrPiMeter

sudo systemctl start xrpimeter

Stop XrPiMeter

sudo systemctl stop xrpimeter

Restart XrPiMeter

sudo systemctl restart xrpimeter

View XrPiMeter logs

journalctl -u xrpimeter --no-pager

Follow logs live

journalctl -u xrpimeter -f

Check ALSA devices

arecord -l

Check USB storage

lsblk

Check UDisks2

udisksctl status

Check system time

timedatectl

⸻

Project Structure

XrPiMeter/
│
├── main.py
│   Main application coordinator.
│
├── xr18.py
│   XR18 discovery, ALSA connection and audio capture.
│
├── meter.py
│   Real-time 18-channel audio metering.
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
│   LED level and status control.
│
├── time_status.py
│   System clock validity and timestamp handling.
│
├── xrp_log.py
│   Central application logging.
│
├── requirements.txt
│   Python dependencies.
│
├── tests/
│   Test and diagnostic programs.
│
└── .gitignore
    Files excluded from version control.

⸻

Testing

Development and diagnostic programs are stored in:

tests/

These are not required for normal operation.

The main application should be run through the systemd service once installation and testing are complete.

⸻

Current Status

The core XrPiMeter system is operational.

Implemented:

* XR18 USB audio discovery
* Dynamic ALSA card detection
* 18-channel audio capture
* 48 kHz audio
* 24-bit WAV recording
* Separate synchronised channel WAV files
* 20-minute recording parts
* Automatic recording rollover
* USB storage detection
* Automatic USB mounting
* USB removal handling
* Automatic recording start/stop
* System time validation
* Session naming
* Session README generation
* Central logging
* Real-time channel metering
* LED level/status display
* OLED dashboard
* Automatic application startup
* XR18 disconnection/reconnection handling
* Graceful shutdown
* Raspberry Pi power-button shutdown

The project remains under active development.

⸻

Why?

The project started from a simple requirement:

Record all 18 USB channels from an XR18 without needing a full computer.

The goal is a small, dedicated recorder and meter that can be connected to an XR18 and left running without a monitor, keyboard or desktop computer.

The Raspberry Pi handles audio capture, storage, metering and status information while the XR18 remains responsible for the audio hardware.

⸻

Licence

No licence has currently been selected for this repository.

Until a licence is added, normal copyright restrictions apply.