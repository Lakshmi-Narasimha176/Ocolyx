# Windows Executable Build

Ocolyx uses PyInstaller to create a single Windows executable at `dist/Ocolyx.exe`.

## Build

From the repository root:

```powershell
.\tools\build_windows.ps1
```

For a packaging-only build after tests have already passed:

```powershell
.\tools\build_windows.ps1 -SkipTests
```

## Packaged Resources

The reusable `Ocolyx.spec` bundles:

- `assets/`
- `assets/icons/Ocolyx.ico`
- `assets/icons/Ocolyx.jpeg`
- `assets/models/shape_predictor_68_face_landmarks.dat`
- `config/default_config.json`
- CustomTkinter data files

The executable is built with `console=False`, so no terminal window is shown. Runtime code resolves bundled resources through PyInstaller's `_MEIPASS` directory and writes user-editable config/log files under `%APPDATA%\Ocolyx` in packaged builds.

## Notes

- Keep `assets/models/shape_predictor_68_face_landmarks.dat` in place before building.
- Keep `assets/icons/Ocolyx.ico` in place; it is used as the executable icon.
- The build target is compatible with Windows 10 and newer.
- One-file executables extract bundled resources at startup, so first launch can be slower than subsequent launches.
