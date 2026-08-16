import time

from xr18 import XR18
from led import LEDs, GREEN


xr18 = XR18()
leds = LEDs()


print("Connecting to XR18...")

if not xr18.connect():

    print("XR18 not found.")
    raise SystemExit


print(
    f"XR18 connected: {xr18.device_name}"
)


try:

    while True:

        # Read an audio block from the XR18.
        #
        # We deliberately do nothing with the audio data.
       # length, data = xr18.read()


        # Keep the entire LED strip permanently green.
        #
        # This deliberately bypasses all meter calculations,
        # channel mapping and normal LED state logic.
        leds.strip.set_all_pixels(
            GREEN
        )

        leds.strip.show()


        # Slow the test down deliberately.
        time.sleep(0.1)


except KeyboardInterrupt:

    print()
    print("Stopping test...")


finally:

    leds.shutdown()

    xr18.disconnect()
