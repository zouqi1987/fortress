"""Centralised logging configuration for Fortress.

All logs go to stderr — stdout is reserved for MCP JSON-RPC.
engine/ layer must NOT use logging (zero-I/O constraint).
"""
import logging
import sys


def setup(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s [%(levelname)-5s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    ))
    # Avoid adding duplicate handlers if called more than once
    root = logging.root
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
