"""
XRPimeter process supervisor.

Architecture:

    Supervisor
        |
        +---- Recorder process
        |
        +---- UI process

The recorder sends small status snapshots to the UI.

Audio data NEVER passes through the queue.

The supervisor:

    - starts the recorder
    - starts the UI
    - monitors both
    - restarts the UI if required
    - detects recorder failure
    - requests orderly shutdown
    - force-kills a process only as a final fallback
"""

import multiprocessing
import signal
import time


from processes.recorder_process import run_recorder
from processes.ui_process import run_ui


# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------

SUPERVISOR_CHECK_INTERVAL = 1.0

PROCESS_SHUTDOWN_TIMEOUT = 10.0

FORCE_TERMINATE_TIMEOUT = 2.0


# ---------------------------------------------------------------------------
# Shutdown state
# ---------------------------------------------------------------------------

shutdown_requested = False


# ---------------------------------------------------------------------------
# Signal handler
# ---------------------------------------------------------------------------

def request_shutdown(
    signum=None,
    frame=None,
):
    """
    Request supervisor shutdown.

    The signal handler deliberately does not touch child processes.
    """

    global shutdown_requested

    shutdown_requested = True


# ---------------------------------------------------------------------------
# Process creation
# ---------------------------------------------------------------------------

def create_recorder_process(
    status_queue,
    shutdown_event,
):
    """
    Create the recorder process.
    """

    return multiprocessing.Process(

        target=run_recorder,

        args=(
            status_queue,
            shutdown_event,
        ),

        name="xrpimeter-recorder",
    )


def create_ui_process(
    status_queue,
    shutdown_event,
):
    """
    Create the UI process.
    """

    return multiprocessing.Process(

        target=run_ui,

        args=(
            status_queue,
            shutdown_event,
        ),

        name="xrpimeter-ui",
    )


# ---------------------------------------------------------------------------
# Process shutdown
# ---------------------------------------------------------------------------

def request_process_shutdown(
    process,
):
    """
    Wait for a process to shut down.

    The process should already have been told to shut down through the
    shared shutdown Event.

    SIGTERM is NOT used as the normal shutdown mechanism.

    If the process refuses to exit, terminate() is used.

    If terminate() somehow fails to stop it, kill() is the final fallback.
    """

    if process is None:
        return

    if process.pid is None:
        return

    if not process.is_alive():

        print(
            f"{process.name} already stopped.",
            flush=True,
        )

        return

    print(
        f"Waiting for "
        f"{process.name} "
        f"(PID {process.pid}) "
        f"to shut down...",
        flush=True,
    )

    # ---------------------------------------------------------------
    # Normal graceful shutdown
    # ---------------------------------------------------------------

    process.join(
        PROCESS_SHUTDOWN_TIMEOUT
    )

    if not process.is_alive():

        print(
            f"{process.name} stopped cleanly.",
            flush=True,
        )

        return

    # ---------------------------------------------------------------
    # First emergency measure
    # ---------------------------------------------------------------

    print(
        f"WARNING: {process.name} did not shut down "
        f"within {PROCESS_SHUTDOWN_TIMEOUT:.0f} seconds.",
        flush=True,
    )

    print(
        f"Force terminating {process.name}...",
        flush=True,
    )

    process.terminate()

    process.join(
        FORCE_TERMINATE_TIMEOUT
    )

    if not process.is_alive():

        print(
            f"{process.name} terminated.",
            flush=True,
        )

        return

    # ---------------------------------------------------------------
    # Absolute final fallback
    # ---------------------------------------------------------------

    print(
        f"ERROR: {process.name} survived terminate().",
        flush=True,
    )

    print(
        f"Force killing {process.name}...",
        flush=True,
    )

    process.kill()

    process.join(
        FORCE_TERMINATE_TIMEOUT
    )

    if process.is_alive():

        print(
            f"ERROR: {process.name} is STILL alive.",
            flush=True,
        )

    else:

        print(
            f"{process.name} killed.",
            flush=True,
        )


# ---------------------------------------------------------------------------
# Supervisor
# ---------------------------------------------------------------------------

def main():
    """
    Start and monitor XRPimeter processes.
    """

    global shutdown_requested

    shutdown_requested = False

    # -----------------------------------------------------------------------
    # Signals
    # -----------------------------------------------------------------------

    signal.signal(
        signal.SIGTERM,
        request_shutdown,
    )

    signal.signal(
        signal.SIGINT,
        request_shutdown,
    )

    print(
        "XRPimeter supervisor starting...",
        flush=True,
    )

    # -----------------------------------------------------------------------
    # IPC
    # -----------------------------------------------------------------------

    status_queue = multiprocessing.Queue()

    shutdown_event = multiprocessing.Event()

    # -----------------------------------------------------------------------
    # Create processes
    # -----------------------------------------------------------------------

    recorder_process = (
        create_recorder_process(
            status_queue,
            shutdown_event,
        )
    )

    ui_process = (
        create_ui_process(
            status_queue,
            shutdown_event,
        )
    )

    # -----------------------------------------------------------------------
    # Start processes
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
    # Monitor
    # -----------------------------------------------------------------------

    try:

        while not shutdown_requested:

            # ---------------------------------------------------------------
            # Recorder
            # ---------------------------------------------------------------

            if not recorder_process.is_alive():

                print(
                    "CRITICAL: recorder process has stopped.",
                    flush=True,
                )

                print(
                    f"Recorder exit code: "
                    f"{recorder_process.exitcode}",
                    flush=True,
                )

                shutdown_requested = True

                break

            # ---------------------------------------------------------------
            # UI
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
                # Create a new UI process.
                #
                # The Event is the SAME Event.
                #
                # It must NOT be set while we want the replacement UI to run.
                # -----------------------------------------------------------

                ui_process = (
                    create_ui_process(
                        status_queue,
                        shutdown_event,
                    )
                )

                ui_process.start()

                print(
                    f"UI process restarted. "
                    f"PID: {ui_process.pid}",
                    flush=True,
                )

            # ---------------------------------------------------------------
            # Supervisor timing
            # ---------------------------------------------------------------

            time.sleep(
                SUPERVISOR_CHECK_INTERVAL
            )

    except KeyboardInterrupt:

        shutdown_requested = True

    finally:

        print(
            "Supervisor shutting down...",
            flush=True,
        )

        # -------------------------------------------------------------------
        # Tell BOTH children to exit.
        # -------------------------------------------------------------------
        #
        # This is the key change.
        #
        # We do not send SIGINT to the recorder.
        #

        shutdown_event.set()

        # -------------------------------------------------------------------
        # Stop recorder
        # -------------------------------------------------------------------

        request_process_shutdown(
            recorder_process
        )

        # -------------------------------------------------------------------
        # Stop UI
        # -------------------------------------------------------------------

        request_process_shutdown(
            ui_process
        )

        # -------------------------------------------------------------------
        # Queue cleanup
        # -------------------------------------------------------------------

        try:

            status_queue.close()

        except Exception:

            pass

        try:

            status_queue.join_thread()

        except Exception:

            pass

        print(
            "Supervisor stopped.",
            flush=True,
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    main()
