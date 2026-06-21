"""Unit tests for logging_config — verify format and stderr output."""
import logging
import sys

from src.logging_config import setup


class TestLoggingSetup:
    def test_outputs_to_stderr(self):
        setup(logging.WARNING)
        handler = logging.root.handlers[0]
        assert isinstance(handler, logging.StreamHandler)
        assert handler.stream is sys.stderr

    def test_formatter_has_correct_format(self):
        setup(logging.INFO)
        handler = logging.root.handlers[0]
        fmt = handler.formatter._fmt
        assert "%(asctime)s" in fmt
        assert "%(levelname)" in fmt
        assert "%(name)s" in fmt
        assert "%(message)s" in fmt

    def test_does_not_duplicate_handlers(self):
        setup(logging.INFO)
        count_before = len(logging.root.handlers)
        setup(logging.INFO)
        assert len(logging.root.handlers) == count_before
