"""
XRPimeter UI process.

This process will eventually contain:

    OLED display
    LEDs

For now it receives test status information from the recorder.
"""


import time


def run_ui(status_queue):
    """
    Entry point for the UI process.

    The UI waits for status messages from the recorder and displays
    the most recently received value.
    """

    print(
        "UI PROCESS STARTED",
        flush=True,
    )

    try:

        while True:

            # Check whether the recorder has sent a status message.
            #
            # get_nowait() means the UI never waits indefinitely for
            # the recorder.
            try:

                status = status_queue.get_nowait()

              #  print(
              #      f"UI RECEIVED STATUS: {status}",
              #      flush=True,
              #  )

            except Exception:

                # Nothing waiting in the queue.
                pass


            time.sleep(0.1)

    except KeyboardInterrupt:

        print(
            "UI PROCESS STOPPED",
            flush=True,
        )