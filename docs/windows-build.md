# Windows Executable Build

Ocolyx uses PyInstaller to create a single Windows executable at `dist/Ocolyx.exe` and an installer-ready package at `dist/Ocolyx-Windows`.

## Build

From the repository root:

```powershell
.\tools\build_windows.ps1
```

For a packaging-only build after tests have already passed:

```powershell
.\tools\build_windows.ps1 -SkipTests
```

To build only the executable without the deployment folder and zip:

```powershell
.\tools\build_windows.ps1 -SkipTests -NoPackage
```

## Packaged Resources

The reusable `Ocolyx.spec` bundles:

- `assets/`
- `assets/icons/ocolyx.ico`
- `assets/icons/Ocolyx.jpeg`
- `assets/models/shape_predictor_68_face_landmarks.dat`
- `config/default_config.json`
- CustomTkinter data files

The executable is built with `console=False`, so no terminal window is shown. `assets/icons/ocolyx.ico` is embedded in `Ocolyx.exe` through PyInstaller's `EXE(icon=...)` setting (and the build script's `--icon` flag). A runtime hook sets the Windows AppUserModelID before the UI starts so the taskbar uses the packaged icon instead of a generic Python icon.

Runtime code resolves bundled resources through PyInstaller's `_MEIPASS` directory and writes user-editable config/log files under `%APPDATA%\Ocolyx` in packaged builds.

## Deployment Output

After a successful build, `dist/` contains:

- `Ocolyx.exe` - single-file application executable
- `Ocolyx-Windows/` - installer-ready folder
- `Ocolyx-Windows.zip` - compressed deployment package

The installer-ready folder includes:

- `Ocolyx.exe`
- `Ocolyx.lnk` (sample shortcut that uses the embedded executable icon)
- `ocolyx.ico` (for installer tools that require a separate icon file)
- `SHA256SUMS.txt`
- `README_DEPLOYMENT.txt`

Use `dist/Ocolyx-Windows/Ocolyx.exe` as the binary input for installer tools such as Inno Setup, WiX, NSIS, Advanced Installer, or MSIX packaging. Point Start Menu and desktop shortcuts at `Ocolyx.exe`, or ship `Ocolyx.lnk`, so shortcuts inherit the embedded icon.

## Notes

- Keep `assets/models/shape_predictor_68_face_landmarks.dat` in place before building.
- Keep `assets/icons/ocolyx.ico` in place; it is used as the executable icon.
- The build target is compatible with Windows 10 and newer.
- One-file executables extract bundled resources at startup, so first launch can be slower than subsequent launches.
