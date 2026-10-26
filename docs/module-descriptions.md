# Module Descriptions

This document summarizes the main Ocolyx modules and their responsibilities.

## Entry Point

- `main.py` creates `OcolyxApp` and starts the application.

## Core Application

- `src/ocolyx/app.py` contains `ApplicationController`, the main orchestrator for UI, tray, blink detection, alerts, screen dimming, logging, and shutdown.
- `src/ocolyx/event_bus.py` provides thread-safe event publish/subscribe behavior.
- `src/ocolyx/logger.py` configures rotating application logs.
- `src/ocolyx/config_manager.py` loads, validates, migrates, and saves JSON settings.

## Computer Vision

- `src/ocolyx/blink_detector.py` contains `WebcamManager`, `BlinkDetector`, `BlinkEvent`, and EAR calculation helpers.
- `WebcamManager` handles OpenCV camera capture, frame validation, FPS throttling, and reconnect backoff.
- `BlinkDetector` runs dlib face detection and landmark prediction, computes eye aspect ratio, and registers blink events.
- `NoOpBlinkDetector` keeps the app stable when the dlib model or detector dependencies are unavailable.

## Blink Analytics

- `src/ocolyx/blink_rate_analysis.py` tracks blink timestamps in a rolling window and exposes blink-rate metrics and health state.

## Alerts And Overlay

- `src/ocolyx/alerts.py` evaluates blink-rate thresholds, cooldowns, escalation, alert history, and alert popup behavior.
- `src/ocolyx/overlay.py` creates the screen dimming overlay and manages fade/pulse timers safely.

## UI

- `src/ocolyx/ui/controller.py` controls dashboard state, periodic status refresh, session timer, tray lifecycle hooks, and settings updates.
- `src/ocolyx/ui/dashboard.py` defines the CustomTkinter dashboard widgets and safe UI update queue.
- `src/ocolyx/ui/theme.py` centralizes colors, fonts, and component styling.
- `src/ocolyx/ui_dashboard.py` is a simpler legacy dashboard module retained for compatibility.

## Tray

- `src/ocolyx/tray.py` implements the primary `pystray` integration used by `ApplicationController`.
- The tray exposes restore, start monitoring, stop monitoring, and exit actions.

## Services

- `src/ocolyx/services/background_service.py` manages recurring background service lifecycle.
- `src/ocolyx/services/blink_service.py` provides a blink-service facade.
- `src/ocolyx/services/settings_service.py` provides a settings-service facade.

## Models

- `src/ocolyx/models/alert_model.py` defines alert data structures.
- `src/ocolyx/models/settings_model.py` defines settings data structures.

## Utilities

- `src/ocolyx/utils/asset_loader.py` loads window and tray icon assets.
- `src/ocolyx/utils/runtime_paths.py` resolves source and PyInstaller resource paths.
- `src/ocolyx/utils/file_utils.py` contains file helpers.
- `src/ocolyx/utils/thread_safe.py` contains thread-safety helpers.
- `src/ocolyx/utils/time_utils.py` contains time helpers.
- `src/ocolyx/utils/validation.py` contains validation helpers.

## Tests

The `tests/` directory covers webcam lifecycle, blink detector lifecycle, dashboard lifecycle, tray behavior, settings persistence, asset loading, background service behavior, and theme management.
