# Ocolyx Architecture Summary

Ocolyx is organized as a desktop monitoring application with clear separation between computer vision, analytics, alerts, UI, tray behavior, settings, and packaging support.

## High-Level Flow

```text
Webcam
  -> OpenCV frame capture
  -> dlib face and landmark detection
  -> Eye Aspect Ratio calculation
  -> blink event
  -> rolling blink-rate analyzer
  -> alert evaluation
  -> dashboard/tray/screen dim updates
```

## Runtime Components

- `ApplicationController` coordinates startup, shutdown, tray, UI, detection, alerts, and screen dimming.
- `WebcamManager` owns the OpenCV capture loop and reconnect behavior.
- `BlinkDetector` processes frames, computes EAR, and emits blink events.
- `BlinkRateAnalyzer` converts blink timestamps into rolling blinks-per-minute metrics.
- `SmartAlertManager` evaluates thresholds and records alert history.
- `ScreenDimmer` creates a click-through overlay when low blink rate persists.
- `DashboardController` bridges application state into the CustomTkinter view.
- `DashboardView` owns Tk widgets and safe main-thread UI update dispatch.
- `TrayManager` exposes restore/start/stop/exit operations from the system tray.
- `ConfigManager` validates and persists JSON settings.

## Threading Model

Ocolyx keeps blocking and periodic work away from the Tk main thread:

- OpenCV capture runs in `WebcamManager`, a daemon thread.
- Blink processing runs in a detector thread.
- Background service work runs outside direct UI callbacks.
- Tray icon work runs in a separate thread.
- Tk updates are marshalled through `DashboardView.safe_update`.
- Periodic Tk callbacks are scheduled through guarded `.after()` wrappers and cancelled during shutdown.

## Shutdown Model

Shutdown is ordered to avoid Tk callbacks running after widget destruction:

1. Mark application/controller/view as shutting down.
2. Cancel app health ticks, dashboard status ticks, session ticks, UI queue dispatch, feedback timers, and overlay timers.
3. Stop tray integration.
4. Stop blink detection and webcam capture.
5. Stop background services.
6. Destroy dashboard widgets after pending UI work is drained.

## Resource Resolution

`src/ocolyx/utils/runtime_paths.py` centralizes path behavior:

- Source runs resolve resources from the repository root.
- PyInstaller runs resolve bundled read-only resources from `_MEIPASS`.
- Packaged builds write user settings and logs under `%APPDATA%\Ocolyx`.

This prevents missing-file errors for icons, JSON defaults, and the dlib model after packaging.

## Packaging

`Ocolyx.spec` builds a single-file Windows executable with:

- `assets/`
- `config/default_config.json`
- CustomTkinter data files
- dlib model files
- Ocolyx application icon
- hidden console window

`tools/build_windows.ps1` validates required resources, runs tests by default, builds the executable, and creates an installer-ready distribution folder and zip.
