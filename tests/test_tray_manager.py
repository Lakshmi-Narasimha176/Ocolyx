from __future__ import annotations

import logging
import threading

from src.ocolyx.tray import TrayManager


class BlockingIcon:
    def __init__(self) -> None:
        self.title = "Ocolyx"
        self.run_started = threading.Event()
        self.release_run = threading.Event()

    def run(self) -> None:
        self.run_started.set()
        self.release_run.wait(timeout=2.0)


def test_tray_icon_run_does_not_block_tooltip_updates() -> None:
    logger = logging.getLogger("test.tray")
    manager = TrayManager(None, logger=logger)
    icon = BlockingIcon()
    manager._icon = icon  # type: ignore[assignment]

    tray_thread = threading.Thread(target=manager._run_icon, daemon=True)
    tray_thread.start()
    assert icon.run_started.wait(timeout=1.0)

    update_completed = threading.Event()

    def update_tooltip() -> None:
        manager.update_tooltip(12.5)
        update_completed.set()

    update_thread = threading.Thread(target=update_tooltip, daemon=True)
    update_thread.start()

    try:
        assert update_completed.wait(timeout=0.5)
        assert icon.title == "Ocolyx - Blink rate: 12.5 BPM"
    finally:
        icon.release_run.set()
        tray_thread.join(timeout=1.0)
        update_thread.join(timeout=1.0)
