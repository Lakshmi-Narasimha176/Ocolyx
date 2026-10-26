# Ocolyx Demo Workflow

Use this workflow for a product demo, engineering review, or release validation walkthrough.

## Pre-Demo Checklist

- Confirm `assets/models/shape_predictor_68_face_landmarks.dat` exists.
- Confirm `assets/icons/ocolyx.ico` exists.
- Confirm the webcam works in Windows Camera or another known-good app.
- Close other apps using the webcam.
- Run tests:

```powershell
pytest --basetemp .\test-tmp
```

- Build the executable:

```powershell
.\tools\build_windows.ps1 -SkipTests
```

## Demo Script

1. Launch Ocolyx from source or executable.

```powershell
python main.py
```

or:

```powershell
.\dist\Ocolyx.exe
```

2. Show the dashboard.

Highlight:

- Blink rate
- Webcam status
- Monitoring status
- Alert status
- Session timer

3. Explain local-only webcam processing.

State that frames are processed on the local machine using OpenCV and dlib. Ocolyx does not upload webcam frames or face data.

4. Demonstrate blink detection.

Sit centered in the webcam frame, blink naturally, and watch the blink/session status update. Explain that the app computes Eye Aspect Ratio from eye landmarks and counts sustained eye closures as blinks.

5. Demonstrate settings.

Open the settings view and show:

- Screen dimming toggle
- Blink-rate threshold
- Alert delay
- Screen dim delay
- Screen dim cooldown

6. Demonstrate tray behavior.

Close or minimize the dashboard to tray, then restore it from the tray menu. Show start/stop monitoring if appropriate.

7. Demonstrate alert and screen dim workflow.

For a short demo, temporarily lower timing thresholds in settings so the effect is visible. Show that Ocolyx records alert status and can pulse the screen dim overlay when blink rate remains below threshold.

8. Show packaged deployment.

Open:

```text
dist/Ocolyx-Windows/
```

Highlight:

- `Ocolyx.exe`
- `README_DEPLOYMENT.txt`
- `SHA256SUMS.txt`

## Discussion Points

- Ocolyx is behavior-aware rather than timer-only.
- EAR detection is computationally lightweight.
- Processing is local-only for privacy.
- The architecture separates capture, detection, analytics, UI, tray, and shutdown cleanup.
- PyInstaller packaging includes assets, configs, CustomTkinter data, and dlib models.

## Known Demo Risks

- Low light can reduce landmark quality.
- Reflective glasses may affect EAR stability.
- Multiple faces can make face selection less predictable.
- One-file PyInstaller startup can be slower because resources are extracted at launch.
- Windows camera permissions or another app using the webcam can block capture.
