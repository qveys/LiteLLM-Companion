"""Tests for main module logging setup and periodic runner."""

import logging
import threading

from ai_cost_observer.main import _InterceptHandler, _run_periodic, _setup_logging


class TestSetupLogging:
    """Test _setup_logging configures loguru correctly."""

    def test_setup_logging_default(self):
        from loguru import logger

        old_handlers = dict(logger._core.handlers)
        try:
            _setup_logging(debug=False)
            # _setup_logging should have added a loguru handler to stdout
            assert len(logger._core.handlers) >= 1
        finally:
            logger.remove()
            for hid, handler in old_handlers.items():
                logger._core.handlers[hid] = handler

    def test_setup_logging_debug(self):
        from loguru import logger

        old_handlers = dict(logger._core.handlers)
        try:
            _setup_logging(debug=True)
            assert len(logger._core.handlers) >= 1
        finally:
            logger.remove()
            for hid, handler in old_handlers.items():
                logger._core.handlers[hid] = handler


class TestInterceptHandler:
    """Test _InterceptHandler routes stdlib logging to loguru."""

    def test_emit_routes_to_loguru(self):
        handler = _InterceptHandler()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None,
        )
        handler.emit(record)


class TestRunPeriodic:
    """Test _run_periodic handles errors and stops on event."""

    def test_stops_on_event(self):
        stop = threading.Event()
        call_count = 0

        def fn():
            nonlocal call_count
            call_count += 1
            stop.set()

        _run_periodic("test", fn, 1.0, stop)
        assert call_count == 1

    def test_handles_exception(self):
        stop = threading.Event()
        call_count = 0

        def failing_fn():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("boom")
            stop.set()

        _run_periodic("test", failing_fn, 0.01, stop)
        assert call_count >= 2
