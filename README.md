**XRPimeter**

**A standalone 18-channel recorder and level meter for the Behringer XR18.**

XRPimeter turns a Raspberry Pi and a USB-connected XR18 into a small, self-contained recording appliance.

Plug in the XR18, connect a recording USB drive and XRPimeter can record all 18 USB audio channels directly to the drive while showing the input levels and recording status.

You can run it with the **OLED and LED interface**, or use it without the display hardware. The recording system itself does not depend on the UI.

The aim is simple:

**Connect it, start it, and let it record.**

**Features**

- 18-channel XR18 USB audio recording
- 48 kHz audio capture
- Automatic XR18/ALSA device detection
- Automatic USB recording-storage detection
- Separate WAV file for each channel
- Automatic recording session organisation
- Recording status and diagnostics
- Optional OLED display
- Optional 18-channel LED level meter
- USB and recording-status LEDs
- Battery-backed RTC for accurate timestamps
- Automatic startup after boot
- Independent recorder and UI processes
- UI can restart without stopping recording
- Clean shutdown of recording sessions
- XR18 disconnect/reconnect handling
- USB storage disconnect/reconnect handling
- Low filesystem activity on the critical audio path

**Hardware**

A typical XRPimeter installation consists of:

- Raspberry Pi
- Behringer XR18
- USB connection between the XR18 and Pi
- USB recording drive
- Battery-backed RTC
- Optional OLED display
- Optional WS2812/compatible LED level meter
- Appropriate level-meter/LED driver hardware

The display hardware is optional.

The recorder does **not** require the OLED or LEDs to operate.

**LED Level Meter**

When the LED interface is installed, XRPimeter provides a simple visual indication of the 18 XR18 input levels.

There is one level LED for each audio channel:

CH 1 ●

CH 2 ●

CH 3 ●

...

CH 18 ●

The LEDs provide progressive level indication.

**Normal level**

Audio levels progressively illuminate the LEDs in green.

**Higher level**

As the signal approaches the upper operating range, the indication moves into amber.

**Excessive level**

Signals above the defined red threshold illuminate the corresponding LED red.

**Clipping**

A clipped signal causes the red indication to flash, making it immediately obvious that the channel has exceeded the available digital headroom.

The LED brightness is deliberately limited so that the meter remains visible without being unnecessarily bright.

Additional indicators are used for:

- USB storage status
- recording status

The LED system is therefore intended to work as an **at-a-glance recording meter**, rather than requiring the user to read the OLED continuously.

**OLED Display**

The OLED is an optional user interface.

When fitted, it can display information such as:

- XR18 connection state
- USB storage state
- USB name
- recording state
- elapsed recording time
- recording size
- remaining recording time
- available storage
- current recording part
- audio status

The OLED is deliberately isolated from the recording process.

A slow or failed I²C display operation must not stop the audio recorder.

**RTC**

XRPimeter uses a battery-backed real-time clock so that the Raspberry Pi has a reliable date and time even when it has no network connection.

This is particularly important because recording sessions and files are timestamped.

The RTC allows XRPimeter to retain the correct time across:

- power removal;
- reboot;
- network loss;
- standalone operation.

The installation process configures the Raspberry Pi's I²C support and RTC support appropriate to the RTC hardware fitted to the XRPimeter.

**Installation**

The preferred installation method is the supplied installation script.

The intention is that a freshly installed Raspberry Pi can be turned into an XRPimeter with one installation procedure rather than requiring the user to manually configure every component.

**1\. Install Raspberry Pi OS**

Install Raspberry Pi OS on the Raspberry Pi.

A Lite installation is sufficient; XRPimeter does not require a desktop environment.

Connect the Pi to the network and log in.

**2\. Download XRPimeter**

Clone the repository:

git clone &lt;repository-url&gt;

cd xrpimeter

**3\. Run the installer**

Run:

chmod +x install.sh

sudo ./install.sh

The installer configures the XRPimeter environment.

It installs the required operating-system packages, creates the Python virtual environment, installs Python dependencies, configures required interfaces and creates the startup service.

**4\. Reboot**

After installation:

sudo reboot

XRPimeter should then start automatically.

**5\. Check the service**

After reboot:

sudo systemctl status xrpimeter

Live logs can be viewed with:

journalctl -u xrpimeter -f

The service can be manually restarted with:

sudo systemctl restart xrpimeter

**Starting XRPimeter Manually**

For development and testing, XRPimeter can still be started manually.

Activate the virtual environment:

source .venv/bin/activate

Then:

python -m processes.supervisor

This is useful when developing because the supervisor output appears directly in the terminal.

**Software Architecture**

XRPimeter is divided into three main processes:

&nbsp; ┌─────────────────────┐

&nbsp; │ Supervisor │

&nbsp; └──────────┬──────────┘

&nbsp; │

&nbsp; ┌─────────────┴─────────────┐

&nbsp; │ │

&nbsp; ┌────────▼────────┐ ┌────────▼────────┐

&nbsp; │ Recorder Process │ │ UI Process │

&nbsp; └────────┬────────┘ └────────┬────────┘

&nbsp; │ │

&nbsp; ┌──────┼──────┐ ┌─────┴─────┐

&nbsp; │ │ │ │ │

&nbsp; XR18 Meter USB OLED LEDs

This separation is one of the most important parts of XRPimeter.

**Supervisor**

The supervisor starts and monitors the other processes.

It:

- starts the recorder;
- starts the UI;
- monitors both processes;
- restarts the UI if it stops;
- detects a recorder failure;
- handles shutdown requests;
- gives child processes time to clean themselves up.

The supervisor does not process audio.

**Recorder Process**

The recorder owns the critical recording path:

XR18

&nbsp;↓

ALSA

&nbsp;↓

Meter

&nbsp;↓

Recorder

&nbsp;↓

USB storage

The recorder is deliberately independent of the OLED and LEDs.

It is responsible for:

- XR18 discovery;
- XR18 connection;
- ALSA capture;
- audio metering;
- USB storage detection;
- recording;
- recording-session management;
- recording diagnostics.

**UI Process**

The UI process owns the non-critical user interface.

It receives small status snapshots from the recorder through a multiprocessing queue.

It handles:

- OLED updates;
- LED updates;
- level-meter display;
- recording indicators;
- connection indicators.

**Audio data is never sent through this queue.**

This keeps the queue small and prevents the user interface from becoming part of the audio path.

**Fast and Slow Paths**

The recorder separates operations according to how quickly they need to happen.

**Fast path**

The audio path runs continuously:

XR18 read

&nbsp; ↓

meter

&nbsp; ↓

recorder write

This path must not be interrupted by unnecessary filesystem operations.

**Slow path**

Operations such as:

- checking USB availability;
- checking free space;
- calculating recording size;
- updating elapsed time;
- building UI status;
- sending UI information

are performed approximately once per second.

This substantially reduces unnecessary filesystem activity while recording.

The distinction is important because the audio stream is arriving continuously, whereas the display does not need to know the free-space figure thousands of times per second.

**XR18 Detection**

Linux does not guarantee that the XR18 will always receive the same ALSA card number.

It may appear as:

hw:0,0

or:

hw:1,0

or:

hw:2,0

etc.

XRPimeter therefore searches the ALSA capture-device list for the XR18/X18 rather than hard-coding a card number.

This allows the system to continue working when Linux assigns the XR18 a different card number after reboot or when another USB device is connected.

**Audio Recording**

The XR18 provides 18 USB audio channels.

XRPimeter records them at:

48,000 Hz

18 channels

S32_LE USB transport

The XR18's USB samples are transported in 32-bit containers even though the converter's actual audio resolution is 24-bit.

Each channel is written as its own WAV file.

A recording session therefore looks approximately like:

XRPiMeter Recordings/

└── 22_08_2026_22-20-02/

&nbsp; ├── README.txt

&nbsp; └── Part 1/

&nbsp; ├── Part 1 CH 1.wav

&nbsp; ├── Part 1 CH 2.wav

&nbsp; ├── Part 1 CH 3.wav

&nbsp; ├── ...

&nbsp; └── Part 1 CH 18.wav

This makes the files straightforward to import into a DAW.

**Recording Sessions**

Each recording session receives its own directory.

The session contains the audio files and a README containing information about the recording.

This keeps individual recording sessions separate and makes the USB drive easier to organise.

Long recordings can also be divided into parts so that individual files do not become unnecessarily large.

**Fault Handling**

**XR18 disconnected**

If the XR18 disappears, the recorder detects the loss of the audio stream.

The current recording is closed cleanly and the recorder releases the ALSA device.

XRPimeter then attempts to rediscover the XR18.

**USB disconnected**

If the recording USB drive disappears, the current recording is stopped cleanly.

The recorder then waits for storage to become available again.

**UI failure**

If the UI process stops, the supervisor can restart it.

The recorder does not need to stop simply because the display process has failed.

**Recorder failure**

The recorder is the critical process.

If it stops unexpectedly, the supervisor treats this as a critical failure rather than blindly restarting it indefinitely.

**Clean Shutdown**

XRPimeter uses a coordinated shutdown process.

The supervisor signals the child processes to stop.

The recorder then has an opportunity to:

1. finish its current work;
2. close the WAV files;
3. stop the recording session;
4. disconnect the XR18;
5. release its resources;
6. exit cleanly.

The UI performs its own cleanup separately.

This avoids leaving partially written recording files simply because the application was stopped.

**Automatic Startup**

When installed as a system service, XRPimeter starts automatically when the Raspberry Pi boots.

This means the normal operating procedure does not require a keyboard, monitor or SSH connection.

The intended workflow is:

Power on

&nbsp; ↓

Raspberry Pi boots

&nbsp; ↓

XRPimeter starts

&nbsp; ↓

XR18 detected

&nbsp; ↓

USB storage detected

&nbsp; ↓

Ready to record

The service can still be stopped, started or inspected manually using systemctl.

**Development**

For development, the normal Python environment can be activated with:

source .venv/bin/activate

The supervisor can then be run manually:

python -m processes.supervisor

This allows development output and errors to be observed directly.

The production installation uses systemd so that XRPimeter can run unattended.

**Project Philosophy**

XRPimeter is intended to behave more like a small recording appliance than a conventional desktop application.

The important principles are:

- **Recording comes first.**
- The UI is optional.
- OLED and LED failures must not unnecessarily interrupt recording.
- Audio is never sent through the multiprocessing status queue.
- Filesystem work is kept away from the high-speed audio path.
- Hardware is detected rather than relying on fragile fixed device numbers.
- Recording storage is external to the Pi's operating-system storage.
- Hardware failures are handled explicitly.
- Shutdowns close recordings cleanly.
- The system should be able to boot and operate without a desktop environment.

The ultimate goal is simple:

**Turn it on, connect the XR18 and recording drive, and let XRPimeter get on with it.**