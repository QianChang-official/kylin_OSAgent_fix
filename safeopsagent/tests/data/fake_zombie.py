#!/usr/bin/env python3
"""Generate a zombie process for testing process monitoring.
Usage: python fake_zombie.py
Parent process exits, child becomes orphan/zombie briefly.
"""
import os
import time

pid = os.fork()
if pid == 0:
    # Child
    time.sleep(60)  # will be reaped by init after parent exits
else:
    # Parent exits immediately, child becomes orphan
    print(f"Child PID: {pid}")
    print(f"Run: ps aux | grep {pid}")
    os._exit(0)
