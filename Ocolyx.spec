# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for the Ocolyx Windows executable."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


ROOT = Path(SPECPATH).resolve()
ASSETS_DIR = ROOT / "assets"
CONFIG_DIR = ROOT / "config"
ICON_PATH = ASSETS_DIR / "icons" / "Ocolyx.ico"
DLIB_MODEL_PATH = ASSETS_DIR / "models" / "shape_predictor_68_face_landmarks.dat"

required_paths = (
    ASSETS_DIR,
    CONFIG_DIR / "default_config.json",
    ICON_PATH,
    DLIB_MODEL_PATH,
)
missing = [str(path) for path in required_paths if not path.exists()]
if missing:
    raise FileNotFoundError("Missing required build resources: " + ", ".join(missing))

datas = [
    (str(ASSETS_DIR), "assets"),
    (str(CONFIG_DIR), "config"),
]
datas += collect_data_files("customtkinter")

hiddenimports = [
    "PIL._tkinter_finder",
    "pystray._win32",
    "dlib",
    "cv2",
]
hiddenimports += collect_submodules("customtkinter")

excludes = [
    "pytest",
    "unittest",
    "pydoc",
    "doctest",
    "IPython",
    "matplotlib",
]

a = Analysis(
    ["main.py"],
    pathex=[str(ROOT), str(ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Ocolyx",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON_PATH),
)
