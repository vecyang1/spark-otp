#!/usr/bin/env -S python3 -B
import sys

sys.dont_write_bytecode = True

from spark_otp.cli import main

if __name__ == "__main__":
    main()
