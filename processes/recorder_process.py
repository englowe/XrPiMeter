"""
XRPimeter recorder process.

This is currently a multiprocessing proof-of-concept.

The real XR18 recorder will be moved here later.
"""


import time


def run_recorder(status_queue):
    """
    Entry point for the recorder process.

    For now this simulates the recorder doing work and periodically
    sends a status message to the UI process.
    """

    print(
        "RECORDER PROCESS STARTED",
        flush=True,
    )

    counter = 0

    try:

        while True:

            counter += 1

            print(
                "RECORDER PROCESS ALIVE",
                flush=True,
            )

            # Send a small status message to the UI process.
            status_queue.put(
                {
                    "counter": counter,
                }
            )

            time.sleep(2)

    except KeyboardInterrupt:

        print(
            "RECORDER PROCESS STOPPED",
            flush=True,
        )
