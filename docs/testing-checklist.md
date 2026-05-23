# Ocolyx Testing Checklist

Use this checklist before a release, after camera/detection changes, and after UI/tray/overlay changes. Record the OS, device model, camera model, lighting condition, glasses condition, CPU, RAM, and Ocolyx commit hash for each full pass.

## Test Environment

- [ ] Test on Windows 10 or newer.
- [ ] Test with the built-in laptop camera.
- [ ] Test with at least one external USB webcam.
- [ ] Test with camera permission enabled.
- [ ] Test with camera permission denied.
- [ ] Test with another app already using the webcam.
- [ ] Test with `assets/models/shape_predictor_68_face_landmarks.dat` present.
- [ ] Test startup behavior when the landmark model is missing.
- [ ] Test with default configuration from `config/default_config.json`.
- [ ] Test with a saved user configuration.
- [ ] Confirm logs are written without repeated noisy errors during normal use.

## Automated Regression Tests

- [ ] Run the full test suite with `pytest`.
- [ ] Run webcam lifecycle tests.
- [ ] Run blink detector lifecycle tests.
- [ ] Run background service tests.
- [ ] Run dashboard lifecycle tests.
- [ ] Run tray manager tests.
- [ ] Run settings persistence tests.
- [ ] Run asset loader tests.
- [ ] Run theme manager tests.
- [ ] Confirm tests pass from a clean checkout.
- [ ] Confirm tests pass after deleting transient cache/log files.

## Webcam Tests

- [ ] App starts when the default webcam is available.
- [ ] Webcam opens using the preferred backend on Windows.
- [ ] Webcam falls back to the default OpenCV backend if the preferred backend fails.
- [ ] Camera frames are captured continuously for at least 10 minutes.
- [ ] Captured frames are valid, non-empty, finite arrays.
- [ ] Frame size is stable during monitoring.
- [ ] Processing FPS is close to the configured processing rate.
- [ ] The app does not freeze if the webcam is unplugged during monitoring.
- [ ] The app shows or logs a disconnect state when the webcam is unplugged.
- [ ] The app reconnects automatically when the webcam is plugged back in.
- [ ] Reconnect attempts use backoff instead of tight retry loops.
- [ ] Starting monitoring twice does not create duplicate camera threads.
- [ ] Stopping monitoring releases the camera.
- [ ] After stopping Ocolyx, another camera app can use the webcam.
- [ ] Switching from internal to external camera works if camera source selection is supported.
- [ ] Webcam failure does not crash the dashboard.
- [ ] Webcam failure does not crash the tray process.
- [ ] Camera access is released on normal exit.
- [ ] Camera access is released when exiting from the tray menu.

## Blink Detection Accuracy Tests

- [ ] Detection starts with zero blink count.
- [ ] Normal open eyes do not count as blinks.
- [ ] A deliberate full blink increments the blink count once.
- [ ] A long eye closure increments the blink count once, not repeatedly.
- [ ] Rapid double blinks are counted as two blinks when visibly distinct.
- [ ] Partial squints are not counted as blinks.
- [ ] Looking left/right briefly does not create false blinks.
- [ ] Looking down briefly does not create repeated false blinks.
- [ ] Natural blinking for 5 minutes produces a reasonable blink-per-minute value.
- [ ] Blink-per-minute value updates as old blinks leave the rolling window.
- [ ] Blink rate returns toward zero after no blinks occur for the configured window.
- [ ] EAR value decreases during closed eyes and recovers when eyes reopen.
- [ ] EAR threshold works for at least three different face distances.
- [ ] Consecutive-frame setting prevents single-frame false positives.
- [ ] Blink callbacks fire once per detected blink.
- [ ] Blink count resets when monitoring is stopped and restarted if that is intended behavior.
- [ ] Detection remains stable when the user moves slightly in the chair.
- [ ] Detection remains stable with mild head tilt.
- [ ] Detection remains stable with common facial expressions.
- [ ] Detection does not count mouth movement or speaking as blinks.

## Low-Light Tests

- [ ] Detection works in bright office lighting.
- [ ] Detection works in moderate indoor lighting.
- [ ] Detection behavior is acceptable in dim room lighting.
- [ ] Low light does not cause excessive false positives.
- [ ] Low light does not cause repeated detector crashes.
- [ ] Low light with monitor-only illumination is tested.
- [ ] Low light with warm lighting is tested.
- [ ] Low light with cool lighting is tested.
- [ ] Backlit face near a window is tested.
- [ ] Side-lit face is tested.
- [ ] Face-not-found state is handled gracefully in very poor lighting.
- [ ] Blink rate does not spike when face landmarks are temporarily lost.
- [ ] UI status reflects degraded/no-face conditions if supported.
- [ ] Logs identify camera or detection issues clearly enough for debugging.

## Glasses Detection And Glasses Compatibility Tests

- [ ] Blink detection works without glasses.
- [ ] Blink detection works with clear prescription glasses.
- [ ] Blink detection works with thin frames.
- [ ] Blink detection works with thick frames.
- [ ] Blink detection works with reflective lenses under room lighting.
- [ ] Blink detection works with anti-glare lenses.
- [ ] Blink detection works with mild screen glare reflected in lenses.
- [ ] Blink detection is tested with sunglasses or tinted lenses.
- [ ] Glasses glare does not create repeated false positives.
- [ ] Glasses frames do not prevent landmark detection at normal distance.
- [ ] Detection remains stable when the user adjusts glasses.
- [ ] Detection remains stable when the user looks through the top/bottom of lenses.
- [ ] If explicit glasses detection is implemented, verify glasses/no-glasses classification accuracy.
- [ ] If explicit glasses detection is not implemented, document this as compatibility testing rather than a feature pass/fail.

## Multi-Face Handling

- [ ] Single face is detected and monitored normally.
- [ ] No face in frame does not crash detection.
- [ ] Two faces in frame does not crash detection.
- [ ] Three or more faces in frame does not crash detection.
- [ ] Detection behavior is documented when multiple faces are present.
- [ ] The selected face remains stable when a second person enters the frame.
- [ ] Blink count does not rapidly jump because another person blinks.
- [ ] Blink rate is not counted from background faces unless that is intended.
- [ ] Face selection remains stable when the main user is closer than background faces.
- [ ] Face selection behavior is tested when the background face is larger or more centered.
- [ ] Detection recovers when the extra face leaves the frame.
- [ ] No unhandled exception occurs when face ordering changes between frames.

## CPU Usage Benchmarks

- [ ] Measure idle CPU with Ocolyx closed.
- [ ] Measure CPU with Ocolyx open but monitoring stopped.
- [ ] Measure CPU with monitoring active for 5 minutes.
- [ ] Measure CPU with monitoring active for 30 minutes.
- [ ] Measure CPU during webcam disconnect/reconnect loops.
- [ ] Measure CPU while dashboard is visible.
- [ ] Measure CPU while dashboard is minimized to tray.
- [ ] Measure CPU while screen dim overlay is active.
- [ ] Measure CPU on battery power.
- [ ] Measure CPU while another video app is running.
- [ ] Confirm average CPU stays within the release target.
- [ ] Confirm CPU spikes settle within a few seconds after startup.
- [ ] Confirm CPU does not climb continuously during long runs.
- [ ] Confirm process FPS throttling prevents busy-wait behavior.
- [ ] Record benchmark method, sample interval, and hardware.

## Memory Leak Testing

- [ ] Record baseline memory after app startup.
- [ ] Record memory after monitoring starts.
- [ ] Run monitoring for 30 minutes and record memory.
- [ ] Run monitoring for 2 hours and record memory.
- [ ] Run monitoring for 8 hours for release-candidate validation.
- [ ] Start and stop monitoring 25 times and check memory recovery.
- [ ] Disconnect and reconnect webcam 10 times and check memory recovery.
- [ ] Open and close dashboard repeatedly and check memory recovery.
- [ ] Minimize and restore from tray repeatedly and check memory recovery.
- [ ] Show and hide screen dim overlay repeatedly and check memory recovery.
- [ ] Confirm old frames are not retained unbounded.
- [ ] Confirm blink timestamp history is pruned by the rolling window.
- [ ] Confirm camera handles are released after stop.
- [ ] Confirm tray icon resources are released after exit.
- [ ] Confirm no thread count growth after repeated start/stop cycles.
- [ ] Investigate any steady memory growth after warm-up.

## UI Responsiveness Tests

- [ ] Dashboard opens within the release target time.
- [ ] Dashboard remains responsive while monitoring is active.
- [ ] Start monitoring button responds immediately.
- [ ] Stop monitoring button responds immediately.
- [ ] Settings controls remain usable while frames are being processed.
- [ ] Blink count display updates without visible stutter.
- [ ] Blink rate display updates without blocking input.
- [ ] Window can be moved while monitoring is active.
- [ ] Window can be resized without layout breakage.
- [ ] Closing the window follows the intended behavior.
- [ ] App handles rapid start/stop clicks without duplicate threads or crashes.
- [ ] App handles rapid minimize/restore actions.
- [ ] UI remains usable during webcam disconnect.
- [ ] UI remains usable during webcam reconnect.
- [ ] UI remains usable while screen dim overlay fades in/out.
- [ ] UI text does not overlap at minimum supported window size.
- [ ] UI is readable at common Windows display scaling values.
- [ ] UI remains responsive after running for at least 2 hours.

## Tray Behavior Tests

- [ ] Tray icon appears after app startup if tray support is enabled.
- [ ] Tray icon uses the correct Ocolyx asset.
- [ ] Tray tooltip shows the app name.
- [ ] Tray tooltip shows blink rate when available.
- [ ] Tooltip updates after blink rate changes.
- [ ] Restore menu item opens or focuses the dashboard.
- [ ] Start Monitoring menu item starts monitoring.
- [ ] Stop Monitoring menu item stops monitoring.
- [ ] Exit menu item shuts down the app.
- [ ] Exiting from tray stops monitoring cleanly.
- [ ] Exiting from tray releases the webcam.
- [ ] Starting tray twice does not create duplicate tray icons.
- [ ] Stopping tray removes the tray icon.
- [ ] Tray remains stable if icon asset loading fails.
- [ ] Tray callbacks do not crash the tray loop when they raise errors.
- [ ] Tray behavior is correct after minimizing the dashboard.
- [ ] Tray behavior is correct after restoring the dashboard multiple times.
- [ ] Tray behavior is correct after sleep/wake if supported by the OS test plan.

## Screen Dim Reliability Tests

- [ ] Screen dim overlay appears when triggered.
- [ ] Screen dim overlay fades in smoothly.
- [ ] Screen dim overlay fades out smoothly.
- [ ] Overlay opacity matches configured opacity.
- [ ] Overlay pulse duration matches configured duration.
- [ ] Overlay covers the full primary monitor.
- [ ] Overlay covers all monitors in a multi-monitor setup.
- [ ] Overlay geometry is correct with monitors arranged side-by-side.
- [ ] Overlay geometry is correct with monitors stacked vertically.
- [ ] Overlay geometry is correct with mixed DPI scaling.
- [ ] Overlay remains topmost during the dim period.
- [ ] Overlay is click-through on Windows.
- [ ] Overlay does not steal keyboard focus.
- [ ] Pressing Escape hides the overlay if that behavior is intended.
- [ ] Calling show repeatedly while active does not create duplicate overlays.
- [ ] Calling hide repeatedly while inactive is safe.
- [ ] Calling pulse repeatedly does not leave orphan overlays.
- [ ] Overlay is destroyed when the app exits.
- [ ] Overlay does not block tray menu usage.
- [ ] Overlay does not permanently dim the screen after errors.
- [ ] Overlay thread handoff works when triggered outside the Tk main thread.

## Alert And Dim Trigger Reliability

- [ ] Low blink rate triggers the expected alert.
- [ ] Normal blink rate does not trigger repeated alerts.
- [ ] Alert cooldown prevents alert spam.
- [ ] Screen dim trigger fires at the configured condition.
- [ ] Screen dim trigger does not fire when monitoring is stopped.
- [ ] Alert state resets correctly after monitoring restarts.
- [ ] Alert behavior is correct when face is temporarily lost.
- [ ] Alert behavior is correct immediately after webcam reconnect.
- [ ] Settings changes affect subsequent alert decisions.
- [ ] Alert logs contain enough context to debug false positives.

## Long-Run Stability

- [ ] Run active monitoring for 2 hours with dashboard visible.
- [ ] Run active monitoring for 2 hours minimized to tray.
- [ ] Run active monitoring for 8 hours for release-candidate validation.
- [ ] Confirm no unhandled exceptions in logs.
- [ ] Confirm no stalled detection thread.
- [ ] Confirm no stalled webcam thread.
- [ ] Confirm no duplicate tray icons.
- [ ] Confirm no orphan overlays.
- [ ] Confirm CPU remains near benchmark target after warm-up.
- [ ] Confirm memory remains near benchmark target after warm-up.
- [ ] Confirm app exits cleanly after the long run.

## Release Sign-Off

- [ ] All automated tests pass.
- [ ] Webcam tests pass on internal and external cameras.
- [ ] Blink accuracy is acceptable across tested users and lighting conditions.
- [ ] Low-light limitations are documented.
- [ ] Glasses compatibility results are documented.
- [ ] Multi-face behavior is documented.
- [ ] CPU benchmark results meet release target.
- [ ] Memory leak testing meets release target.
- [ ] UI responsiveness meets release target.
- [ ] Tray behavior passes.
- [ ] Screen dim reliability passes.
- [ ] Known issues are documented with severity and reproduction steps.
- [ ] Logs from the final test pass are archived.
