"""Main entry point — orchestrates detectors, threads, and lifecycle."""

from __future__ import annotations

import logging
import signal
import sys
import threading
from threading import Event

from loguru import logger

from ai_cost_observer.config import load_config
from ai_cost_observer.telemetry import TelemetryManager


class _InterceptHandler(logging.Handler):
    """Route stdlib logging messages to loguru."""

    def emit(self, record):
        # Get corresponding Loguru level
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where the logged message originated
        frame, depth = sys._current_frames()[threading.current_thread().ident], 0
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def _setup_logging(debug: bool = False) -> None:
    """Configure loguru as the sole logging backend."""
    # Remove default loguru handler
    logger.remove()

    # Add loguru handler with the desired format
    logger.add(
        sys.stdout,
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}"
        ),
        level="DEBUG" if debug else "INFO",
        colorize=True,
    )

    # Intercept all stdlib logging and route through loguru
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)


def _run_periodic(name: str, fn: callable, interval: float, stop_event: Event) -> None:
    """Run fn() every `interval` seconds in a thread until stop_event is set."""
    while not stop_event.is_set():
        try:
            fn()
        except Exception:
            logger.opt(exception=True).error("Error in periodic task '{}'", name)
        stop_event.wait(interval)


def run_main_loop(stop_event: Event, config, detectors: dict) -> None:
    """The core, testable main loop of the agent for high-frequency scans."""
    logger.debug("Main scan loop started.")
    while not stop_event.is_set():
        try:
            detectors["desktop"].scan()
            detectors["cli"].scan()
            detectors["wsl"].scan()
        except Exception:
            logger.opt(exception=True).error("Error during main scan loop")
        stop_event.wait(config.scan_interval_seconds)
    logger.debug("Main scan loop stopped.")


def run() -> None:
    """Main entry point for the agent."""
    import argparse

    parser = argparse.ArgumentParser(description="AI Cost Observer — personal AI spending tracker")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    _setup_logging(debug=args.debug)
    logger.info("Agent starting...")
    stop_event = Event()

    def _signal_handler(signum: int, _frame: object) -> None:
        sig_name = signal.Signals(signum).name
        logger.info("Received {} — initiating shutdown.", sig_name)
        stop_event.set()

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    prompt_db = None
    background_threads = []

    try:
        config = load_config()
        telemetry = TelemetryManager(config)

        from ai_cost_observer.detectors.browser_history import BrowserHistoryParser
        from ai_cost_observer.detectors.cli import CLIDetector
        from ai_cost_observer.detectors.desktop import DesktopDetector
        from ai_cost_observer.detectors.shell_history import ShellHistoryParser
        from ai_cost_observer.detectors.token_tracker import TokenTracker
        from ai_cost_observer.detectors.wsl import WSLDetector
        from ai_cost_observer.server.http_receiver import set_token_tracker, start_http_receiver

        # Initialize prompt storage if token tracking is enabled
        tt_config = config.token_tracking
        if tt_config.get("enabled", True):
            try:
                from ai_cost_observer.storage.prompt_db import PromptDB

                db_path = tt_config.get("storage_path", "auto")
                prompt_db = PromptDB(
                    db_path=None if db_path == "auto" else db_path,
                    encrypt=tt_config.get("encrypt_prompts", True),
                    retention_days=tt_config.get("retention_days", 90),
                )
                logger.debug("Prompt storage initialized at {}", prompt_db.db_path)
            except Exception:
                logger.opt(exception=True).warning("Failed to initialize prompt storage")

        token_tracker = TokenTracker(config, telemetry, prompt_db=prompt_db)
        set_token_tracker(token_tracker)

        desktop_detector = DesktopDetector(config, telemetry)
        detectors = {
            "desktop": desktop_detector,
            "cli": CLIDetector(config, telemetry, desktop_detector=desktop_detector),
            "wsl": WSLDetector(config, telemetry),
            "browser_history": BrowserHistoryParser(config, telemetry),
            "shell_history": ShellHistoryParser(config, telemetry),
            "token_tracker": token_tracker,
        }

        http_thread = start_http_receiver(config, telemetry)
        token_interval = tt_config.get("api_polling_interval_seconds", 300)

        background_threads = [
            threading.Thread(
                target=_run_periodic,
                args=(
                    "browser_history",
                    detectors["browser_history"].scan,
                    config.browser_history_interval_seconds,
                    stop_event,
                ),
                daemon=True,
                name="browser-history",
            ),
            threading.Thread(
                target=_run_periodic,
                args=(
                    "shell_history",
                    detectors["shell_history"].scan,
                    config.shell_history_interval_seconds,
                    stop_event,
                ),
                daemon=True,
                name="shell-history",
            ),
            threading.Thread(
                target=_run_periodic,
                args=("token_tracker", token_tracker.scan, token_interval, stop_event),
                daemon=True,
                name="token-tracker",
            ),
        ]
        # http_thread is already started by start_http_receiver(), don't re-start it

        for t in background_threads:
            t.start()

        logger.info("Agent running.")
        run_main_loop(stop_event, config, detectors)

    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received, stopping.")
        stop_event.set()
    except Exception:
        logger.opt(exception=True).critical("Unhandled exception in agent execution.")
        stop_event.set()
    finally:
        logger.info("Shutting down...")
        for t in background_threads:
            if t.is_alive():
                t.join(timeout=2)
        if prompt_db:
            try:
                prompt_db.cleanup()
                prompt_db.close()
            except Exception:
                logger.opt(exception=True).debug("Error during prompt DB cleanup")
        if "telemetry" in locals():
            telemetry.shutdown()
        logger.info("Agent stopped.")


if __name__ == "__main__":
    run()
