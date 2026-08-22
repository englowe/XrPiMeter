"""
XRPimeter process supervisor.

The supervisor starts and monitors the independent XRPimeter
processes.

Current proof-of-concept architecture:

    Supervisor
        |
        +---- Recorder process
        |
        +---- UI process

The recorder sends small status messages to the UI through a
multiprocessing.Queue.

Audio data is NOT sent through the queue.
"""


import multiprocessing
import time

from processes.recorder_process import run_recorder
from processes.ui_process import run_ui


def main():
    """
    Start and monitor the XRPimeter processes.
    """

    print(
        "XRPimeter supervisor starting...",
        flush=True,
    )


    # -----------------------------------------------------------------------
    # Recorder → UI status queue
    # -----------------------------------------------------------------------
    #
    # This queue is only for small status messages.
    #
    # The recorder will eventually send things such as:
    #
    #     XR18 connection state
    #     USB state
    #     recording state
    #     audio levels
    #     elapsed recording time
    #     remaining recording time
    #
    # We NEVER send the actual 18-channel audio through this queue.
    #

    status_queue = multiprocessing.Queue()


    # -----------------------------------------------------------------------
    # Create recorder process
    # -----------------------------------------------------------------------

    recorder_process = multiprocessing.Process(
        target=run_recorder,
        args=(status_queue,),
        name="xrpimeter-recorder",
    )


    # -----------------------------------------------------------------------
    # Create UI process
    # -----------------------------------------------------------------------

    ui_process = multiprocessing.Process(
        target=run_ui,
        args=(status_queue,),
        name="xrpimeter-ui",
    )


    # -----------------------------------------------------------------------
    # Start both processes
    # -----------------------------------------------------------------------

    recorder_process.start()

    ui_process.start()


    print(
        "Both processes started.",
        flush=True,
    )

    print(
        f"Supervisor PID: "
        f"{multiprocessing.current_process().pid}",
        flush=True,
    )

    print(
        f"Recorder PID: "
        f"{recorder_process.pid}",
        flush=True,
    )

    print(
        f"UI PID: "
        f"{ui_process.pid}",
        flush=True,
    )


    # -----------------------------------------------------------------------
    # Monitor processes
    # -----------------------------------------------------------------------

    try:

        while True:


            # ---------------------------------------------------------------
            # Check recorder
            # ---------------------------------------------------------------

            if not recorder_process.is_alive():

                print(
                    "CRITICAL: recorder process has stopped.",
                    flush=True,
                )

                # The recorder is the primary function of XRPimeter.
                #
                # For now we simply stop the supervisor as well.
                # Later we will implement proper critical-failure handling.

                break


            # ---------------------------------------------------------------
            # Check UI
            # ---------------------------------------------------------------

            if not ui_process.is_alive():

                print(
                    "WARNING: UI process has stopped.",
                    flush=True,
                )

                print(
                    "Restarting UI process...",
                    flush=True,
                )


                # -----------------------------------------------------------
                # Create a completely new UI process.
                # -----------------------------------------------------------
                #
                # A multiprocessing.Process object cannot be started again
                # once it has stopped, so a new object must be created.
                #

                ui_process = multiprocessing.Process(
                    target=run_ui,
                    args=(status_queue,),
                    name="xrpimeter-ui",
                )


                # Start the replacement UI process.

                ui_process.start()


                print(
                    f"UI process restarted. "
                    f"PID: {ui_process.pid}",
                    flush=True,
                )


            # ---------------------------------------------------------------
            # Give the supervisor a short pause.
            # ---------------------------------------------------------------

            time.sleep(1)


    except KeyboardInterrupt:

        print(
            "Supervisor stopping...",
            flush=True,
        )


    finally:

        # -------------------------------------------------------------------
        # Stop recorder
        # -------------------------------------------------------------------

        if recorder_process.is_alive():

            print(
                "Stopping recorder process...",
                flush=True,
            )

            recorder_process.terminate()

            recorder_process.join()


        # -------------------------------------------------------------------
        # Stop UI
        # -------------------------------------------------------------------

        if ui_process.is_alive():

            print(
                "Stopping UI process...",
                flush=True,
            )

            ui_process.terminate()

            ui_process.join()


        # -------------------------------------------------------------------
        # Close status queue
        # -------------------------------------------------------------------

        status_queue.close()

        status_queue.join_thread()


        print(
            "Supervisor stopped.",
            flush=True,
        )


# ---------------------------------------------------------------------------
# Program entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    main()