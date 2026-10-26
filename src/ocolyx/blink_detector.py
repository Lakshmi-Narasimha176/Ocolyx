"""Blink detection engine for Ocolyx."""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Deque, List, Optional, Tuple

import cv2
import dlib
import imutils
import numpy as np

from .utils.runtime_paths import dlib_shape_predictor_path


BlinkEventCallback = Callable[["BlinkEvent"], None]
StatusCallback = Callable[[str], None]
ErrorCallback = Callable[[Exception], None]
FrameCallback = Callable[[np.ndarray], None]


@dataclass
class BlinkEvent:
    timestamp: float
    ear: float
    blink_count: int
    blinks_per_minute: float


LEFT_EYE_INDICES = list(range(42, 48))
RIGHT_EYE_INDICES = list(range(36, 42))


def _euclidean_distance(point_a: np.ndarray, point_b: np.ndarray) -> float:
    """Euclidean distance between two 2D landmark points."""
    return float(np.linalg.norm(point_a - point_b))


def eye_aspect_ratio(eye_points: np.ndarray) -> float:
    vertical_1 = _euclidean_distance(eye_points[1], eye_points[5])
    vertical_2 = _euclidean_distance(eye_points[2], eye_points[4])
    horizontal = _euclidean_distance(eye_points[0], eye_points[3])
    if horizontal == 0:
        return 0.0
    return (vertical_1 + vertical_2) / (2.0 * horizontal)


def _estimate_brightness(frame: np.ndarray) -> float:
    """Estimate frame brightness (0-1, where 1 is brightest)."""
    if frame is None or frame.size == 0:
        return 0.5
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
    return float(np.mean(gray) / 255.0)


def _preprocess_frame_for_detection(frame: np.ndarray, brightness: float) -> np.ndarray:
    """Apply adaptive preprocessing for robust detection in varying light conditions.
    
    Args:
        frame: Input BGR frame
        brightness: Estimated brightness (0-1 scale)
    
    Returns:
        Preprocessed grayscale frame optimized for face/eye detection
    """
    # Convert to grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization) for low-light enhancement
    # CLAHE is superior to regular histogram equalization as it prevents over-amplification
    # of noise in uniform regions
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    
    # For very dark frames, apply additional contrast enhancement
    if brightness < 0.25:
        # Apply bilateral filtering to reduce noise while preserving edges
        enhanced = cv2.bilateralFilter(enhanced, 9, 75, 75)
        # Apply morphological opening to clean up noise
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        enhanced = cv2.morphologyEx(enhanced, cv2.MORPH_OPEN, kernel)
        # Increase contrast further
        enhanced = cv2.convertScaleAbs(enhanced, alpha=1.2, beta=10)
    elif brightness < 0.4:
        # For moderately dark frames, apply light bilateral filtering
        enhanced = cv2.bilateralFilter(enhanced, 5, 50, 50)
    
    return enhanced


class WebcamManager(threading.Thread):
    """Threaded webcam capture manager with Windows-friendly backend selection.

    The capture path prefers DirectShow on Windows because it is typically more
    stable than the default MSMF backend for USB webcams. If DirectShow cannot
    open the device, the manager falls back to the default OpenCV backend and
    schedules reconnects with exponential backoff so the app does not spam the
    logs or continuously thrash the camera.
    """

    def __init__(
        self,
        source: int = 0,
        frame_width: int = 640,
        reconnect_delay: float = 2.0,
        max_retry_interval: float = 30.0,
        process_fps: float = 6.0,
        logger: Optional[logging.Logger] = None,
        on_frame: Optional[FrameCallback] = None,
        on_disconnect: Optional[StatusCallback] = None,
        on_reconnect: Optional[StatusCallback] = None,
        on_error: Optional[ErrorCallback] = None,
    ) -> None:
        super().__init__(daemon=True)
        self.source = source
        self.target_frame_width = max(320, min(640, int(frame_width)))
        self.reconnect_delay = max(0.1, float(reconnect_delay))
        self.max_retry_interval = max(self.reconnect_delay, float(max_retry_interval))
        self.process_fps = max(1.0, float(process_fps))
        self.process_interval = 1.0 / self.process_fps

        # Capture settings are intentionally fixed for stability on Windows 10.
        # The processing thread can still downsample frames independently.
        self.capture_width = 640
        self.capture_height = 480
        self.capture_fps = 30.0

        self.logger = logger or logging.getLogger("ocolyx.blink_detector.webcam")
        self.on_frame = on_frame
        self.on_disconnect = on_disconnect
        self.on_reconnect = on_reconnect
        self.on_error = on_error

        self._capture_lock = threading.RLock()
        self._reconnect_lock = threading.Lock()
        self._capture: Optional[cv2.VideoCapture] = None
        self._stop_event = threading.Event()
        self._frame_lock = threading.Lock()
        self._latest_frame: Optional[np.ndarray] = None
        self._connected = False
        self._last_read_time = time.time()
        self.fps = 0.0
        self._last_process_time = 0.0
        self._current_retry_delay = self.reconnect_delay
        self._next_retry_time = 0.0
        self._selected_backend_name = "uninitialized"
        self._reconnect_attempts = 0
        self._reconnect_in_progress = False
        self._last_reconnect_log_delay = 0.0
        self._last_reconnect_log_time = 0.0

    def run(self) -> None:
        self.logger.info("Webcam manager thread started")
        try:
            while not self._stop_event.is_set():
                if not self._ensure_capture():
                    time.sleep(max(0.05, self._retry_sleep_interval()))
                    continue

                now = time.time()
                with self._capture_lock:
                    capture = self._capture
                    if capture is None or not capture.isOpened():
                        self._handle_disconnect()
                        continue

                    try:
                        grabbed = capture.grab()
                    except Exception:
                        grabbed = False

                if not grabbed:
                    self.logger.warning("Frame capture failed using %s; reconnecting", self._selected_backend_name)
                    self._handle_disconnect()
                    time.sleep(max(0.05, self._retry_sleep_interval()))
                    continue

                if now - self._last_process_time >= self.process_interval:
                    with self._capture_lock:
                        capture = self._capture
                        if capture is None or not capture.isOpened():
                            self._handle_disconnect()
                            continue

                        try:
                            ret, frame = capture.retrieve()
                        except Exception:
                            ret, frame = False, None

                    if not ret or not self._is_valid_frame(frame):
                        self.logger.warning("Frame capture failed using %s; reconnecting", self._selected_backend_name)
                        self._handle_disconnect()
                        time.sleep(max(0.05, self._retry_sleep_interval()))
                        continue

                    self.logger.debug("Frame read succeeded using %s", self._selected_backend_name)

                    try:
                        frame = imutils.resize(frame, width=self.target_frame_width)
                    except Exception:
                        self.logger.warning("Frame resize failed using %s; reconnecting", self._selected_backend_name)
                        self._handle_disconnect()
                        time.sleep(max(0.05, self._retry_sleep_interval()))
                        continue

                    self._update_fps()

                    with self._frame_lock:
                        self._latest_frame = frame.copy() if isinstance(frame, np.ndarray) else frame

                    if self.on_frame:
                        try:
                            self.on_frame(self._latest_frame)
                        except Exception:
                            self.logger.exception("on_frame callback raised an exception")

                    self._last_process_time = now
                    time.sleep(0.001)
                else:
                    time.sleep(min(0.005, self.process_interval / 4.0))
        except Exception as exc:
            self.logger.exception("Unexpected exception in WebcamManager run loop")
            if self.on_error:
                try:
                    self.on_error(exc)
                except Exception:
                    self.logger.exception("on_error callback raised during error handling")
        finally:
            self._release_capture()
            self.logger.info("Webcam manager thread stopped")

    def stop(self) -> None:
        self._stop_event.set()
        self._release_capture()

    def get_latest_frame(self) -> Optional[np.ndarray]:
        with self._frame_lock:
            return None if self._latest_frame is None else self._latest_frame.copy()

    def is_connected(self) -> bool:
        return self._connected

    def _ensure_capture(self) -> bool:
        with self._capture_lock:
            if self._capture is not None and self._capture.isOpened():
                return True

        with self._reconnect_lock:
            if self._reconnect_in_progress:
                return False
            if time.time() < self._next_retry_time:
                return False
            self._reconnect_in_progress = True
            self._reconnect_attempts += 1

        try:
            self._release_capture()
            self.logger.info(
                "Webcam reconnect attempt %d scheduled in %.1fs",
                self._reconnect_attempts,
                self._current_retry_delay,
            )

            backends = self._backend_preference()
            self.logger.info("Webcam backend selection: trying %s", ", ".join(label for _, label in backends))

            for backend, label in backends:
                try:
                    if backend is None:
                        capture = cv2.VideoCapture(self.source)
                    else:
                        capture = cv2.VideoCapture(self.source, backend)
                except Exception:
                    self.logger.warning("Failed to create VideoCapture with backend %s", label)
                    continue

                if not capture.isOpened():
                    capture.release()
                    self.logger.warning(
                        "Webcam unavailable or busy: failed to open source %s using %s",
                        self.source,
                        label,
                    )
                    continue

                self._selected_backend_name = label
                if not self._apply_capture_settings(capture):
                    capture.release()
                    self.logger.warning("Webcam settings failed for backend %s", label)
                    continue

                with self._capture_lock:
                    self._capture = capture
                    self._connected = True
                    self._last_read_time = time.time()
                self._current_retry_delay = self.reconnect_delay
                self._next_retry_time = 0.0
                self._reconnect_attempts = 0
                self.logger.info("Webcam opened successfully using backend %s", label)
                if self.on_reconnect:
                    self.on_reconnect(f"Webcam connected using {label}")
                return True

            self._schedule_reconnect()
            return False
        finally:
            with self._reconnect_lock:
                self._reconnect_in_progress = False

    def _backend_preference(self) -> list[tuple[Optional[int], str]]:
        # Windows 10 is more reliable with DirectShow than MSMF for USB webcams.
        backends: list[tuple[Optional[int], str]] = []
        dshow_backend = getattr(cv2, "CAP_DSHOW", None)
        if dshow_backend is not None:
            backends.append((int(dshow_backend), "DirectShow"))
        backends.append((None, "default"))
        return backends

    def _apply_capture_settings(self, capture: cv2.VideoCapture) -> bool:
        # Reduce camera buffer latency on Windows where stale frames can cause
        # delayed or repeated detections.
        try:
            buffer_prop = getattr(cv2, "CAP_PROP_BUFFERSIZE", None)
            if buffer_prop is not None:
                capture.set(buffer_prop, 1)
        except Exception:
            self.logger.debug("CAP_PROP_BUFFERSIZE is unavailable for this backend")

        # Explicitly request a stable frame size and frame rate for OpenCV capture.
        for prop, value in (
            (cv2.CAP_PROP_FRAME_WIDTH, float(self.capture_width)),
            (cv2.CAP_PROP_FRAME_HEIGHT, float(self.capture_height)),
            (cv2.CAP_PROP_FPS, float(self.capture_fps)),
        ):
            try:
                success = capture.set(prop, value)
            except Exception:
                success = False
            if not success:
                self.logger.warning("Failed to set webcam property %s to %s", prop, value)

        current_width = capture.get(cv2.CAP_PROP_FRAME_WIDTH)
        current_height = capture.get(cv2.CAP_PROP_FRAME_HEIGHT)
        current_fps = capture.get(cv2.CAP_PROP_FPS)

        self.logger.info(
            "Webcam settings applied: backend=%s width=%.1f height=%.1f fps=%.1f",
            self._selected_backend_name,
            current_width,
            current_height,
            current_fps,
        )
        return bool(current_width > 0 and current_height > 0)

    def _is_valid_frame(self, frame: Any) -> bool:
        # Frame validation protects downstream MediaPipe and dlib code from
        # receiving corrupt or empty frames after a camera hiccup.
        if frame is None or not isinstance(frame, np.ndarray):
            return False
        if frame.size == 0:
            return False
        if frame.ndim != 3 or frame.shape[2] not in (1, 3):
            return False
        if frame.shape[0] <= 0 or frame.shape[1] <= 0:
            return False
        return bool(np.isfinite(frame).all())

    def _handle_disconnect(self) -> None:
        with self._capture_lock:
            was_connected = self._connected
            self._connected = False
            capture = self._capture
            self._capture = None

        if capture is not None:
            try:
                capture.release()
            except Exception:
                pass

        if was_connected:
            if self.on_disconnect:
                self.on_disconnect("Webcam unavailable")
            self.logger.warning("Webcam disconnected during capture")

        self._schedule_reconnect()

    def _release_capture(self) -> None:
        with self._capture_lock:
            capture = self._capture
            self._capture = None
            self._connected = False

        if capture is not None:
            try:
                capture.release()
            except Exception:
                pass

    def _schedule_reconnect(self) -> None:
        with self._reconnect_lock:
            self._current_retry_delay = min(self.max_retry_interval, max(self.reconnect_delay, self._current_retry_delay * 2.0))
            self._next_retry_time = time.time() + self._current_retry_delay
            self._last_reconnect_log_delay = self._current_retry_delay
            self._last_reconnect_log_time = time.time()
            self.logger.info(
                "Webcam reconnect cooldown: %.1fs (max %.1fs)",
                self._current_retry_delay,
                self.max_retry_interval,
            )

    def _retry_sleep_interval(self) -> float:
        if self._next_retry_time <= 0:
            return self.reconnect_delay

        remaining = max(0.0, self._next_retry_time - time.time())
        if remaining <= 0:
            return 0.05
        return min(self._current_retry_delay, remaining)

    def _update_fps(self) -> None:
        now = time.time()
        elapsed = now - self._last_read_time
        if elapsed > 0:
            self.fps = min(60.0, 1.0 / elapsed)
        self._last_read_time = now


class BlinkDetector:
    def __init__(
        self,
        predictor_path: Optional[Path] = None,
        source: int = 0,
        ear_threshold: float = 0.23,
        consecutive_frames: int = 3,
        window_seconds: int = 60,
        logger: Optional[logging.Logger] = None,
        on_blink: Optional[BlinkEventCallback] = None,
        on_disconnect: Optional[StatusCallback] = None,
        on_reconnect: Optional[StatusCallback] = None,
        on_error: Optional[ErrorCallback] = None,
        process_fps: float = 6.0,
    ) -> None:
        self.logger = logger or logging.getLogger("ocolyx.blink_detector")
        self.predictor_path = predictor_path or dlib_shape_predictor_path()
        self.ear_threshold = ear_threshold
        self.consecutive_frames = consecutive_frames
        self.window_seconds = window_seconds
        self.on_blink = on_blink
        self.on_disconnect = on_disconnect
        self.on_reconnect = on_reconnect
        self.on_error = on_error
        self.process_fps = float(process_fps) if process_fps and process_fps > 0 else 6.0
        self.source = source

        # Attempt to load the dlib predictor; allow callers to catch FileNotFoundError
        self._load_detector()

        self.webcam_manager: Optional[WebcamManager] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._stop_event.set()
        self._state_lock = threading.Lock()
        self._lifecycle_lock = threading.Lock()
        self._monitoring_state = "stopped"
        self.current_ear = 0.0
        self.blink_count = 0
        self._eye_closed_frames = 0
        self._last_blink_time = 0.0
        self._blink_timestamps: Deque[float] = deque()
        self._current_fps = 0.0
        
        # Low-light detection and adaptation
        self._current_brightness = 0.5
        self._brightness_history: Deque[float] = deque(maxlen=10)
        self._current_ear_threshold = self.ear_threshold

    def _load_detector(self) -> None:
        if not self.predictor_path.exists():
            raise FileNotFoundError(
                f"Facial landmark predictor not found: {self.predictor_path}"
            )

        try:
            self.face_detector = dlib.get_frontal_face_detector()
            self.shape_predictor = dlib.shape_predictor(str(self.predictor_path))
            self.logger.info("Loaded dlib 68-point facial landmark predictor")
        except Exception as exc:
            self.logger.exception("Failed to initialize dlib predictor")
            raise

    def _create_webcam_manager(self) -> WebcamManager:
        return WebcamManager(
            source=self.source,
            on_frame=self._no_op_frame_callback,
            on_disconnect=self._handle_disconnect,
            on_reconnect=self._handle_reconnect,
            logger=self.logger,
            process_fps=self.process_fps,
            on_error=self.on_error,
        )

    def start(self) -> bool:
        with self._lifecycle_lock:
            if self._monitoring_state in {"starting", "running"}:
                self.logger.debug("Blink detector already %s", self._monitoring_state)
                return False

            self._monitoring_state = "starting"
            self.logger.info("Starting blink detector")
            self._stop_event = threading.Event()
            self._reset_runtime_state()
            self.webcam_manager = self._create_webcam_manager()
            self._thread = threading.Thread(target=self._run, daemon=True)

            try:
                self.webcam_manager.start()
                self._thread.start()
            except RuntimeError:
                self._monitoring_state = "stopped"
                self._stop_event.set()
                self.webcam_manager.stop()
                raise

            self._monitoring_state = "running"
            return True

    def stop(self) -> bool:
        with self._lifecycle_lock:
            if self._monitoring_state in {"stopping", "stopped"}:
                self.logger.debug("Blink detector already %s", self._monitoring_state)
                return False

            self.logger.info("Stopping blink detector")
            self._monitoring_state = "stopping"
            self._stop_event.set()
            webcam_manager = self.webcam_manager
            processing_thread = self._thread

        if webcam_manager is not None:
            webcam_manager.stop()
            if webcam_manager.is_alive() and threading.current_thread() is not webcam_manager:
                webcam_manager.join(timeout=2.0)

        if processing_thread is not None and processing_thread.is_alive() and threading.current_thread() is not processing_thread:
            processing_thread.join(timeout=2.0)

        with self._lifecycle_lock:
            if self.webcam_manager is webcam_manager:
                self.webcam_manager = None
            if self._thread is processing_thread:
                self._thread = None
            self._monitoring_state = "stopped"
            self._reset_runtime_state()
            return True

    def _reset_runtime_state(self) -> None:
        with self._state_lock:
            self.current_ear = 0.0
            self._current_fps = 0.0
            self._eye_closed_frames = 0
            self.blink_count = 0
            self._blink_timestamps.clear()
            self._current_brightness = 0.5
            self._brightness_history.clear()
            self._current_ear_threshold = self.ear_threshold

    def validate_monitoring_state(self) -> bool:
        with self._lifecycle_lock:
            if self._monitoring_state == "running":
                return (
                    self._thread is not None
                    and self._thread.is_alive()
                    and self.webcam_manager is not None
                    and self.webcam_manager.is_alive()
                    and not self._stop_event.is_set()
                )
            if self._monitoring_state == "stopped":
                return (
                    (self._thread is None or not self._thread.is_alive())
                    and (self.webcam_manager is None or not self.webcam_manager.is_alive())
                    and self._stop_event.is_set()
                )
            return False

    @property
    def monitoring_state(self) -> str:
        with self._lifecycle_lock:
            return self._monitoring_state

    @property
    def is_running(self) -> bool:
        return self.monitoring_state == "running"

    def _run(self) -> None:
        while not self._stop_event.is_set():
            webcam_manager = self.webcam_manager
            if webcam_manager is None:
                time.sleep(0.02)
                continue

            frame = webcam_manager.get_latest_frame()
            if frame is None:
                time.sleep(0.02)
                continue

            try:
                self._process_frame(frame)
            except Exception as exc:
                self.logger.exception("Error during blink detection")
                if self.on_error:
                    self.on_error(exc)
            time.sleep(0.015)

    def _process_frame(self, frame: np.ndarray) -> None:
        # Estimate frame brightness for adaptive processing
        brightness = _estimate_brightness(frame)
        
        with self._state_lock:
            self._brightness_history.append(brightness)
            avg_brightness = float(np.mean(list(self._brightness_history)))
            self._current_brightness = avg_brightness
            
            # Dynamically adjust EAR threshold based on lighting conditions
            # In dark conditions, lower the threshold to be more sensitive to blinks
            if avg_brightness < 0.25:
                self._current_ear_threshold = self.ear_threshold * 0.85  # 15% more sensitive
            elif avg_brightness < 0.4:
                self._current_ear_threshold = self.ear_threshold * 0.92  # 8% more sensitive
            else:
                self._current_ear_threshold = self.ear_threshold
        
        # Apply adaptive preprocessing for robust detection in varying light
        gray = _preprocess_frame_for_detection(frame, brightness)
        
        # Detect faces in preprocessed frame
        faces = self.face_detector(gray, 0)
        if not faces:
            with self._state_lock:
                self.current_ear = 0.0
            return

        face = faces[0]
        shape = self.shape_predictor(gray, face)
        landmarks = self._landmarks_to_np(shape)
        left_eye = landmarks[LEFT_EYE_INDICES]
        right_eye = landmarks[RIGHT_EYE_INDICES]

        left_ear = eye_aspect_ratio(left_eye)
        right_ear = eye_aspect_ratio(right_eye)
        ear = (left_ear + right_ear) / 2.0

        with self._state_lock:
            self.current_ear = ear
            webcam_manager = self.webcam_manager
            self._current_fps = webcam_manager.fps if webcam_manager is not None else 0.0
            current_threshold = self._current_ear_threshold

        if ear < current_threshold:
            self._eye_closed_frames += 1
            return

        if self._eye_closed_frames >= self.consecutive_frames:
            self._register_blink(ear)

        self._eye_closed_frames = 0

    def _register_blink(self, ear: float) -> None:
        timestamp = time.time()
        with self._state_lock:
            self.blink_count += 1
            self._blink_timestamps.append(timestamp)
            self._prune_old_timestamps(timestamp)

        event = BlinkEvent(
            timestamp=timestamp,
            ear=ear,
            blink_count=self.blink_count,
            blinks_per_minute=self.blinks_per_minute,
        )
        self.logger.info("Blink detected: count=%d ear=%.3f bpm=%.2f", event.blink_count, event.ear, event.blinks_per_minute)
        if self.on_blink:
            self.on_blink(event)

    def _prune_old_timestamps(self, current_time: float) -> None:
        while self._blink_timestamps and self._blink_timestamps[0] < current_time - self.window_seconds:
            self._blink_timestamps.popleft()

    def _landmarks_to_np(self, shape: dlib.full_object_detection) -> np.ndarray:
        coords = np.zeros((68, 2), dtype=int)
        for i in range(68):
            coords[i] = (shape.part(i).x, shape.part(i).y)
        return coords

    def _handle_disconnect(self, status: str) -> None:
        self.logger.warning(status)
        if self.on_disconnect:
            self.on_disconnect(status)

    def _handle_reconnect(self, status: str) -> None:
        self.logger.info(status)
        if self.on_reconnect:
            self.on_reconnect(status)

    def _no_op_frame_callback(self, frame: np.ndarray) -> None:
        pass

    @property
    def blinks_per_minute(self) -> float:
        with self._state_lock:
            now = time.time()
            self._prune_old_timestamps(now)
            return float(len(self._blink_timestamps)) * (60.0 / max(self.window_seconds, 1))

    @property
    def latest_ear(self) -> float:
        with self._state_lock:
            return self.current_ear

    @property
    def total_blinks(self) -> int:
        with self._state_lock:
            return self.blink_count

    @property
    def camera_fps(self) -> float:
        return self._current_fps

    @property
    def current_brightness(self) -> float:
        """Return average brightness of recent frames (0-1 scale)."""
        with self._state_lock:
            return self._current_brightness

    @property
    def adaptive_ear_threshold(self) -> float:
        """Return current adaptive EAR threshold based on lighting."""
        with self._state_lock:
            return self._current_ear_threshold


class NoOpBlinkDetector:
    """Fallback detector used when dependencies or models are missing.

    This keeps the app stable while providing no-op implementations for the
    methods the rest of the application expects.
    """
    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self.logger = logger or logging.getLogger("ocolyx.noop_detector")

    def start(self) -> bool:
        self.logger.warning("NoOpBlinkDetector.start() called - detector unavailable")
        return False

    def stop(self) -> bool:
        self.logger.warning("NoOpBlinkDetector.stop() called - detector unavailable")
        return False

    def validate_monitoring_state(self) -> bool:
        return True

    @property
    def monitoring_state(self) -> str:
        return "stopped"

    @property
    def is_running(self) -> bool:
        return False

    @property
    def blinks_per_minute(self) -> float:
        return 0.0

    @property
    def latest_ear(self) -> float:
        return 0.0

    @property
    def total_blinks(self) -> int:
        return 0

    @property
    def camera_fps(self) -> float:
        return 0.0
