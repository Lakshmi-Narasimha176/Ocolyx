from __future__ import annotations

import logging
import threading

from src.ocolyx import blink_detector as blink_module
from src.ocolyx.blink_detector import BlinkDetector


class FakeWebcamManager(threading.Thread):
    instances: list["FakeWebcamManager"] = []

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(daemon=True)
        self.stop_event = threading.Event()
        self.fps = 0.0
        FakeWebcamManager.instances.append(self)

    def run(self) -> None:
        self.stop_event.wait(timeout=2.0)

    def stop(self) -> None:
        self.stop_event.set()

    def get_latest_frame(self):
        return None

    def is_connected(self) -> bool:
        return self.is_alive() and not self.stop_event.is_set()


def _build_detector(monkeypatch) -> BlinkDetector:
    FakeWebcamManager.instances.clear()
    monkeypatch.setattr(BlinkDetector, "_load_detector", lambda self: None)
    monkeypatch.setattr(blink_module, "WebcamManager", FakeWebcamManager)
    return BlinkDetector(logger=logging.getLogger("test.blink.lifecycle"))


def test_blink_detector_recreates_webcam_thread_after_stop(monkeypatch) -> None:
    detector = _build_detector(monkeypatch)

    assert detector.validate_monitoring_state()
    assert detector.start() is True
    first_manager = detector.webcam_manager
    assert detector.validate_monitoring_state()

    assert detector.stop() is True
    assert detector.validate_monitoring_state()

    assert detector.start() is True
    second_manager = detector.webcam_manager

    try:
        assert second_manager is not first_manager
        assert len(FakeWebcamManager.instances) == 2
        assert detector.validate_monitoring_state()
    finally:
        detector.stop()


def test_blink_detector_ignores_duplicate_start(monkeypatch) -> None:
    detector = _build_detector(monkeypatch)

    assert detector.start() is True
    first_manager = detector.webcam_manager
    assert detector.start() is False

    try:
        assert detector.webcam_manager is first_manager
        assert len(FakeWebcamManager.instances) == 1
        assert detector.monitoring_state == "running"
    finally:
        detector.stop()
