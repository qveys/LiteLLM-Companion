"""HTTP receiver — Flask endpoint for Chrome extension browser metrics and token intercepts."""

from __future__ import annotations

import logging
import threading

from flask import Flask, jsonify, request
from loguru import logger

from ai_cost_observer.config import AppConfig
from ai_cost_observer.telemetry import TelemetryManager

# Token tracker reference (set after initialization in main.py)
_token_tracker = None


def set_token_tracker(tracker) -> None:
    """Set the token tracker instance for API intercept handling."""
    global _token_tracker
    _token_tracker = tracker


def create_app(config: AppConfig, telemetry: TelemetryManager) -> Flask:
    """Create the Flask app for receiving browser extension metrics."""
    app = Flask(__name__)
    app.config["TESTING"] = False

    domain_lookup = {d["domain"]: d for d in config.ai_domains}
    _extension_connected = False

    @app.before_request
    def log_request():
        logger.debug("{} {} from {}", request.method, request.path, request.remote_addr)

    @app.route("/", methods=["GET"])
    def root():
        logger.debug("Browser visited root endpoint")
        return jsonify({
            "service": "ai-cost-observer",
            "status": "running",
            "endpoints": ["/health", "/metrics/browser", "/api/tokens", "/api/extension-config"],
        })

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "healthy"})

    @app.route("/api/extension-config", methods=["GET"])
    def extension_config():
        """Serve config for the Chrome extension (domains + API patterns)."""
        domains = [d["domain"] for d in config.ai_domains]
        api_patterns = config.api_intercept_patterns
        cost_rates = {d["domain"]: d.get("cost_per_hour", 0) for d in config.ai_domains}
        return jsonify({
            "domains": domains,
            "api_patterns": api_patterns,
            "cost_rates": cost_rates,
        })

    @app.route("/metrics/browser", methods=["POST"])
    def receive_browser_metrics():
        nonlocal _extension_connected
        if not _extension_connected:
            _extension_connected = True
            logger.info("Chrome extension connected.")

        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400

        events = data.get("events", [])
        if not isinstance(events, list):
            return jsonify({"error": "events must be a list"}), 400

        for event in events:
            domain = event.get("domain", "")
            duration_seconds = event.get("duration_seconds", 0)
            visit_count = event.get("visit_count", 0)

            if not domain or not isinstance(duration_seconds, (int, float)):
                continue

            domain_cfg = domain_lookup.get(domain)
            if not domain_cfg:
                # Not a tracked AI domain — ignore
                continue

            labels = {
                "ai.domain": domain,
                "ai.category": domain_cfg.get("category", "unknown"),
                "browser.name": event.get("browser", "chrome"),
                "usage.source": "extension",
            }

            if duration_seconds > 0:
                telemetry.browser_domain_active_duration.add(duration_seconds, labels)

            if visit_count > 0:
                telemetry.browser_domain_visit_count.add(visit_count, labels)

            cost_per_hour = domain_cfg.get("cost_per_hour", 0)
            if cost_per_hour > 0 and duration_seconds > 0:
                cost_labels = {
                    "ai.domain": domain,
                    "ai.category": domain_cfg.get("category", "unknown"),
                }
                cost = cost_per_hour * (duration_seconds / 3600)
                telemetry.browser_domain_estimated_cost.add(cost, cost_labels)

            logger.debug(
                "Extension: {} — {:.0f}s, {} visits",
                domain, duration_seconds, visit_count,
            )

        return jsonify({"status": "ok", "processed": len(events)})

    @app.route("/api/tokens", methods=["POST"])
    def receive_token_events():
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400

        events = data.get("events", [])
        if not isinstance(events, list):
            return jsonify({"error": "events must be a list"}), 400

        processed = 0
        for event in events:
            event_type = event.get("type", "")
            tool = event.get("tool", "unknown")
            model = event.get("model", "unknown")
            input_tokens = event.get("input_tokens", 0)
            output_tokens = event.get("output_tokens", 0)
            prompt_text = event.get("prompt_text")
            response_text = event.get("response_text")

            if event_type == "api_intercept":
                if _token_tracker:
                    _token_tracker.record_api_intercept(
                        tool_name=tool,
                        model=model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        prompt_text=prompt_text,
                        response_text=response_text,
                    )
                else:
                    # No token tracker — just record the OTel metrics directly
                    labels = {"tool.name": tool, "model.name": model}
                    if input_tokens > 0:
                        telemetry.tokens_input_total.add(input_tokens, labels)
                    if output_tokens > 0:
                        telemetry.tokens_output_total.add(output_tokens, labels)
                    telemetry.prompt_count_total.add(
                        1, {"tool.name": tool, "source": "browser"}
                    )

                processed += 1
                logger.debug(
                    "Token intercept: {} model={} in={} out={}",
                    tool, model, input_tokens, output_tokens,
                )

        return jsonify({"status": "ok", "processed": processed})

    return app


def start_http_receiver(config: AppConfig, telemetry: TelemetryManager) -> threading.Thread | None:
    """Start the Flask HTTP receiver in a daemon thread. Returns the thread, or None on failure."""
    try:
        # Suppress noisy werkzeug request logs and Flask startup banner
        # ("* Serving Flask app ..." / "* Debug mode: off" use click.echo, not logging)
        logging.getLogger("werkzeug").setLevel(logging.WARNING)
        import flask.cli
        flask.cli.show_server_banner = lambda *_a, **_kw: None

        app = create_app(config, telemetry)

        thread = threading.Thread(
            target=lambda: app.run(
                host="127.0.0.1",
                port=config.http_receiver_port,
                use_reloader=False,
                threaded=True,
            ),
            daemon=True,
            name="http-receiver",
        )
        thread.start()
        logger.debug("HTTP receiver started on 127.0.0.1:{}", config.http_receiver_port)
        return thread
    except Exception:
        logger.opt(exception=True).error("Failed to start HTTP receiver")
        return None
