#!/usr/bin/env python3
"""Entry point for executing `python3 -m snx_manager`."""

import sys
from snx_manager.cli import main

if __name__ == "__main__":
    sys.exit(main())
