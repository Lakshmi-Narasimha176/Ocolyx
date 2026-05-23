"""Ocolyx UI package."""

from .dashboard import DashboardView


def __getattr__(name):
    if name == "OcolyxDashboard":
        from .controller import DashboardController

        return DashboardController
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["DashboardView", "OcolyxDashboard"]
