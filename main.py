"""
XRPimeter application launcher.

The supervisor owns the recorder and UI processes.
"""

from processes.supervisor import main


if __name__ == "__main__":
    main()