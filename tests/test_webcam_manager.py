import logging

import cv2
import numpy as np

from src.ocolyx.blink_detector import WebcamManager


class FakeCapture:
    def __init__(self, opened: bool = True) -> None:
        self._opened = opened
        self.set_calls = []
        self.release_calls = 0

    def isOpened(self) -> bool:
        return self._opened

    def set(self, prop, value) -> bool:
        self.set_calls.append((prop, value))
        return True

    def get(self, prop):
        if prop == cv2.CAP_PROP_FRAME_WIDTH:
            return 640.0
        if prop == cv2.CAP_PROP_FRAME_HEIGHT:
            return 480.0
        if prop == cv2.CAP_PROP_FPS:
            return 12.0
        return 0.0

    def release(self) -> None:
        self.release_calls += 1

    def grab(self) -> bool:
        return True

    def retrieve(self):
        return True, np.zeros((480, 640, 3), dtype=np.uint8)


def test_webcam_manager_tries_dshow_and_falls_back_to_default(monkeypatch) -> None:
    created = []

    def fake_video_capture(source, backend=None):
        created.append((source, backend))
        if backend == cv2.CAP_DSHOW:
            return FakeCapture(opened=False)
        return FakeCapture(opened=True)

    monkeypatch.setattr(cv2, "VideoCapture", fake_video_capture)

    manager = WebcamManager(logger=logging.getLogger("test.webcam_manager"))

    assert manager._ensure_capture() is True
    assert created == [(0, cv2.CAP_DSHOW), (0, None)]
    assert manager._selected_backend_name == "default"


def test_webcam_manager_caps_retry_interval() -> None:
    manager = WebcamManager(reconnect_delay=0.1, max_retry_interval=0.3, logger=logging.getLogger("test.webcam_manager"))

    manager._schedule_reconnect()
    assert manager._current_retry_delay == 0.2

    manager._schedule_reconnect()
    assert manager._current_retry_delay == 0.3

    manager._schedule_reconnect()
    assert manager._current_retry_delay == 0.3
