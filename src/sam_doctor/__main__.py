"""Allow `python -m sam_doctor` as an alias for the console script."""

import sys

from sam_doctor.cli import main

if __name__ == "__main__":
    sys.exit(main())
