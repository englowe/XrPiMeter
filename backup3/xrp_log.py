"""
XRPimeter central logging system.

All XRPimeter modules use this module for logging important events.

Log files are separated by month:

    /var/log/xrpimeter/
        2026-08.log
        2026-09.log
        2026-10.log
        ...

The logger automatically changes to the new month's file when the first
log message of a new month is written.

This means XRPimeter does NOT need to be restarted at the end of a month.

The log is intended to help diagnose problems after the fact, including:

    - Pi boot and shutdown
    - XR18 detection/disconnection
    - USB detection/disconnection
    - recording start/stop
    - recording errors
    - temperature warnings
    - CPU throttling
    - other important system events

This file is deliberately called xrp_log.py rather than logging.py.

Python already has a standard module called "logging", so naming this file
logging.py could cause Python import conflicts.
"""

import logging
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Directory in which XRPimeter's logs are stored.
#
# /var/log is the conventional Linux location for system/service logs.
LOG_DIRECTORY = Path("/var/log/xrpimeter")


# Internal name used by Python's logging system.
LOGGER_NAME = "xrpimeter"


# ---------------------------------------------------------------------------
# Monthly rotating file handler
# ---------------------------------------------------------------------------

class MonthlyFileHandler(logging.Handler):
    """
    Logging handler which automatically creates one log file per month.

    Example:

        2026-08.log
        2026-09.log
        2026-10.log

    The handler checks the current month whenever a message is written.

    Therefore, if XRPimeter remains running across midnight on the last day
    of a month, the next message automatically goes into the new month's
    file.
    """

    def __init__(self, directory):
        """
        Create the monthly log handler.

        directory:
            Directory in which the monthly log files will be stored.
        """

        super().__init__()

        # Store the log directory as a Path object.
        self.directory = Path(directory)

        # The file currently being written to.
        self.current_file = None

        # The Python FileHandler currently responsible for writing the file.
        self.file_handler = None

        # Remember which month the current handler represents.
        #
        # Example:
        #
        #     "2026-08"
        #
        self.current_month = None

        # Make sure the initial file exists.
        self._switch_month_if_required()


    # -----------------------------------------------------------------------
    # Determine the current month
    # -----------------------------------------------------------------------

    @staticmethod
    def _get_current_month():
        """
        Return the current year/month as a string.

        Example:

            2026-08
        """

        return datetime.now().strftime(
            "%Y-%m"
        )


    # -----------------------------------------------------------------------
    # Change log file if the month has changed
    # -----------------------------------------------------------------------

    def _switch_month_if_required(self):
        """
        Switch to a new log file if the current month has changed.
        """

        month = self._get_current_month()


        # If we're already using this month's file, there is nothing to do.
        if (
            self.current_month == month
            and self.file_handler is not None
        ):
            return


        # ---------------------------------------------------------------
        # Make sure the log directory exists
        # ---------------------------------------------------------------

        try:

            self.directory.mkdir(
                parents=True,
                exist_ok=True
            )

        except OSError as error:

            # Don't allow a logging failure to crash XRPimeter.
            print(
                f"WARNING: Unable to create log directory: {error}"
            )

            return


        # ---------------------------------------------------------------
        # Close the previous month's file
        # ---------------------------------------------------------------

        if self.file_handler is not None:

            try:
                self.file_handler.close()

            except Exception:
                pass

            self.file_handler = None


        # ---------------------------------------------------------------
        # Create the new month's filename
        # ---------------------------------------------------------------

        self.current_file = (
            self.directory
            / f"{month}.log"
        )


        # ---------------------------------------------------------------
        # Open the new log file
        # ---------------------------------------------------------------

        try:

            self.file_handler = logging.FileHandler(
                self.current_file,
                encoding="utf-8"
            )

        except OSError as error:

            print(
                f"WARNING: Unable to open log file "
                f"{self.current_file}: {error}"
            )

            self.file_handler = None

            return


        # Remember which month this handler represents.
        self.current_month = month


        # ---------------------------------------------------------------
        # Give the underlying file handler the same formatter
        # ---------------------------------------------------------------

        formatter = logging.Formatter(
            "%(asctime)s %(levelname)-8s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        self.file_handler.setFormatter(
            formatter
        )


    # -----------------------------------------------------------------------
    # Write a log record
    # -----------------------------------------------------------------------

    def emit(self, record):
        """
        Write one logging record.

        This is called automatically by Python's logging system.
        """

        try:

            # Check whether we have crossed into a new month.
            self._switch_month_if_required()


            # If the file could not be opened, there is nowhere to write.
            if self.file_handler is None:
                return


            # Write the record to the current month's file.
            self.file_handler.emit(record)


        except Exception:

            # Logging must never be allowed to crash the main application.
            #
            # Python's logging system provides handleError() for this.
            self.handleError(record)


    # -----------------------------------------------------------------------
    # Close handler
    # -----------------------------------------------------------------------

    def close(self):
        """
        Close the current month's file.
        """

        if self.file_handler is not None:

            try:
                self.file_handler.close()

            except Exception:
                pass

            self.file_handler = None


        # Call the base Handler.close() as well.
        super().close()


# ---------------------------------------------------------------------------
# Create/configure the XRPimeter logger
# ---------------------------------------------------------------------------

def get_logger():
    """
    Return the XRPimeter logger.

    The logger is configured the first time this function is called.

    Subsequent calls return the same logger.

    This is important because many different XRPimeter modules will use
    the same logger.
    """

    logger = logging.getLogger(
        LOGGER_NAME
    )


    # ---------------------------------------------------------------
    # Don't configure the logger more than once
    # ---------------------------------------------------------------

    if logger.handlers:

        return logger


    # ---------------------------------------------------------------
    # Set the minimum logging level
    # ---------------------------------------------------------------

    # INFO and anything more serious will be recorded.
    #
    # This means:
    #
    #     DEBUG    -> ignored
    #     INFO     -> recorded
    #     WARNING  -> recorded
    #     ERROR    -> recorded
    #     CRITICAL -> recorded
    #
    logger.setLevel(
        logging.INFO
    )


    # ---------------------------------------------------------------
    # Create the monthly file handler
    # ---------------------------------------------------------------

    handler = MonthlyFileHandler(
        LOG_DIRECTORY
    )


    # Add the handler to the XRPimeter logger.
    logger.addHandler(
        handler
    )


    return logger


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

def log_info(message):
    """
    Write an informational message.

    Example:

        log_info("XR18 connected")
    """

    get_logger().info(
        message
    )


def log_warning(message):
    """
    Write a warning message.

    Example:

        log_warning("CPU temperature above 60 C")
    """

    get_logger().warning(
        message
    )


def log_error(message):
    """
    Write an error message.

    Example:

        log_error("XR18 audio read failed")
    """

    get_logger().error(
        message
    )