"""Tests for Bug H2: _free_port() removal — no arbitrary process killing."""

import importlib

from werkzeug.serving import BaseWSGIServer


def test_free_port_function_removed():
    """Verify _free_port() no longer exists in main module.

    The old _free_port() sent SIGKILL to arbitrary processes listening on
    port 8080 without checking process ownership. It has been removed entirely.
    """
    import ai_cost_observer.main as main_mod

    # Reload to pick up latest source
    importlib.reload(main_mod)
    assert not hasattr(main_mod, "_free_port"), (
        "_free_port should be removed — it kills arbitrary processes"
    )


def test_werkzeug_sets_so_reuseaddr():
    """Verify Werkzeug enables SO_REUSEADDR, making _free_port() unnecessary.

    With SO_REUSEADDR the agent can rebind to its port immediately after a
    restart, without needing to kill whatever held the port before.
    """
    assert BaseWSGIServer.allow_reuse_address is True, (
        "Werkzeug should set allow_reuse_address=True (SO_REUSEADDR)"
    )


def test_run_function_does_not_reference_free_port():
    """Verify the run() function source code has no reference to _free_port."""
    import inspect

    import ai_cost_observer.main as main_mod

    source = inspect.getsource(main_mod.run)
    assert "_free_port" not in source, (
        "run() should not call _free_port — the function was removed"
    )
