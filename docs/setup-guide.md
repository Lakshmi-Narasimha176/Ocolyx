# Ocolyx Setup Guide

This guide covers local development, testing, and Windows executable builds.

## Prerequisites

- Windows 10 or newer
- Python 3.10 or newer
- Webcam
- Git
- `assets/models/shape_predictor_68_face_landmarks.dat`

For best Tkinter compatibility, prefer the Python.org Windows installer over the Microsoft Store Python package.

## Local Development Setup

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Run Ocolyx:

```powershell
python main.py
```

## Test Setup

Run the test suite:

```powershell
pytest
```

If Windows temp directory permissions block pytest setup, use a repository-local temp folder:

```powershell
pytest --basetemp .\test-tmp
```

## Required Assets

Ocolyx expects:

```text
assets/icons/ocolyx.ico
assets/icons/Ocolyx.jpeg
assets/models/shape_predictor_68_face_landmarks.dat
config/default_config.json
```

The dlib model is required for real blink detection. Without it, the app can start in fallback mode but cannot perform facial landmark detection.

## Configuration

Default settings live in:

```text
config/default_config.json
```

Important settings:

- `ear_threshold`
- `consecutive_frame_count`
- `blink_rate_threshold_bpm`
- `alert_delay_minutes`
- `dim_delay_minutes`
- `overlay_enabled`
- `overlay_opacity`
- `process_fps`

Packaged builds write runtime config under `%APPDATA%\Ocolyx`.

## Build A Windows Executable

Install production/build dependencies:

```powershell
python -m pip install -r requirements.txt -r requirements-prod.txt
```

Build:

```powershell
.\tools\build_windows.ps1
```

Skip tests only when they already passed:

```powershell
.\tools\build_windows.ps1 -SkipTests
```

Output:

```text
dist/Ocolyx.exe
dist/Ocolyx-Windows/
dist/Ocolyx-Windows.zip
```

## Clean Demo Preparation

Before a demo:

1. Confirm the webcam is available.
2. Confirm no other application is using the webcam.
3. Confirm the dlib model exists.
4. Run `pytest --basetemp .\test-tmp`.
5. Build with `.\tools\build_windows.ps1`.
6. Launch `dist/Ocolyx.exe`.
7. Verify dashboard, tray icon, blink-rate updates, settings, and screen dim behavior.
