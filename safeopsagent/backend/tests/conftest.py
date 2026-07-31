"""Explicitly select the localhost-only unauthenticated mode for legacy tests."""
import os

os.environ["CONSOLE_AUTH_ENABLED"] = "0"
os.environ["CONSOLE_AUTH_ALLOW_INSECURE_NON_LOOPBACK"] = "1"
