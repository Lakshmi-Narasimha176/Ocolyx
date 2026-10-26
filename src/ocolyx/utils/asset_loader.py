"""Asset loading helpers for Ocolyx."""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path
from typing import Any, Optional, Tuple, Union

from PIL import Image, ImageTk

APP_USER_MODEL_ID = "Ocolyx.Desktop.App"
WINDOW_ICON_NAMES = ("ocolyx.ico", "Ocolyx.ico")

_WM_SETICON = 0x0080
_ICON_SMALL = 0
_ICON_BIG = 1
_IMAGE_ICON = 1
_LR_LOADFROMFILE = 0x00000010
_GA_ROOT = 2


def _normalize_icon_names(names: list[str]) -> set[str]:
    return {name.lower() for name in names}


def _resolve_existing_asset(base_dir: Path, names: list[str]) -> Optional[Path]:
    if not base_dir.exists():
        return None

    for name in names:
        candidate = base_dir / name
        if candidate.exists():
            return candidate

    targets = _normalize_icon_names(names)
    for candidate in base_dir.iterdir():
        if candidate.is_file() and candidate.name.lower() in targets:
            return candidate

    return None


def resolve_icon_paths(root_dir: Union[str, Path]) -> Tuple[Optional[Path], Optional[Path]]:
    """Resolve the preferred ICO and JPEG assets from the repository root."""
    base_dir = Path(root_dir) / "assets" / "icons"
    ico_path = _resolve_existing_asset(base_dir, list(WINDOW_ICON_NAMES))
    jpeg_path = _resolve_existing_asset(base_dir, ["ocolyx.jpeg", "Ocolyx.jpeg", "ocolyx.jpg", "Ocolyx.jpg"])
    return ico_path, jpeg_path


def apply_windows_app_user_model_id(logger: Any | None = None) -> None:
    """Set the process AppUserModelID so Windows uses the window icon in the taskbar."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception as exc:
        if logger is not None:
            logger.debug("Failed to set Windows AppUserModelID: %s", exc)


def _windows_toplevel_hwnd(tk_window: Any) -> int:
    hwnd = int(tk_window.winfo_id())
    root_hwnd = ctypes.windll.user32.GetAncestor(hwnd, _GA_ROOT)
    return int(root_hwnd or hwnd)


def _apply_windows_shell_icons(tk_window: Any, icon_path: Path, logger: Any | None = None) -> bool:
    if sys.platform != "win32":
        return False
    if getattr(tk_window, "_ocolyx_shell_icon_applied", False):
        return True

    try:
        tk_window.update_idletasks()
    except Exception:
        pass

    resolved = icon_path.resolve()
    hwnd = _windows_toplevel_hwnd(tk_window)
    applied = False
    for icon_type, width, height in ((_ICON_SMALL, 16, 16), (_ICON_BIG, 32, 32)):
        icon_handle = ctypes.windll.user32.LoadImageW(
            None,
            str(resolved),
            _IMAGE_ICON,
            width,
            height,
            _LR_LOADFROMFILE,
        )
        if not icon_handle:
            continue
        ctypes.windll.user32.SendMessageW(hwnd, _WM_SETICON, icon_type, icon_handle)
        applied = True

    if applied:
        tk_window._ocolyx_shell_icon_applied = True
        return True

    if logger is not None:
        logger.debug("Failed to set Windows shell icon from %s", resolved)
    return False


def apply_tk_window_icon(
    tk_window: Any,
    window_icon_path: Optional[Path],
    logo_path: Optional[Path] = None,
    logger: Any | None = None,
    *,
    windows_shell: bool = True,
) -> Tuple[bool, Optional[ImageTk.PhotoImage]]:
    """Apply the Ocolyx icon to a Tk/CustomTkinter window.

    Uses assets/icons/ocolyx.ico when available for the title bar, taskbar, and Alt+Tab.
    Falls back to the JPEG logo, then leaves the default Tk icon in place.
    """
    icon_applied = False
    photo_ref: Optional[ImageTk.PhotoImage] = None

    if window_icon_path is not None and window_icon_path.exists() and window_icon_path.suffix.lower() == ".ico":
        ico_path = window_icon_path.resolve()
        try:
            tk_window.iconbitmap(str(ico_path))
            icon_applied = True
        except Exception as exc:
            if logger is not None:
                logger.warning("Failed to set window icon from %s: %s", ico_path, exc)

        photo = load_tk_icon(ico_path, size=(64, 64), logger=logger)
        if photo is not None:
            try:
                tk_window.iconphoto(True, photo)
                photo_ref = photo
                icon_applied = True
            except Exception as exc:
                if logger is not None:
                    logger.warning("Failed to set window icon photo from %s: %s", ico_path, exc)

        if windows_shell and _apply_windows_shell_icons(tk_window, ico_path, logger=logger):
            icon_applied = True

    if not icon_applied and logo_path is not None and logo_path.exists():
        photo = load_tk_icon(logo_path, size=(64, 64), logger=logger)
        if photo is not None:
            try:
                tk_window.iconphoto(True, photo)
                photo_ref = photo
                icon_applied = True
            except Exception as exc:
                if logger is not None:
                    logger.warning("Failed to set window icon photo from %s: %s", logo_path, exc)

    if not icon_applied and logger is not None:
        logger.warning("Ocolyx window icon is unavailable; using the default Tk icon")

    return icon_applied, photo_ref


def _safe_open_image(path: Union[str, Path], logger=None) -> Optional[Image.Image]:
    path = Path(path)
    if not path.exists():
        if logger:
            logger.warning("Asset not found: %s", path)
        return None

    try:
        image = Image.open(path)
        image.load()
        if image.mode != "RGBA":
            image = image.convert("RGBA")
        return image
    except Exception as exc:
        if logger:
            logger.warning("Failed to open image %s: %s", path, exc)
        return None


def load_image(
    path: Union[str, Path],
    size: Optional[Tuple[int, int]] = None,
    logger=None,
) -> Optional[Image.Image]:
    """Load an image asset and optionally resize it using Pillow."""
    image = _safe_open_image(path, logger=logger)
    if image is None:
        return None

    if size is not None:
        try:
            image = image.resize(size, Image.LANCZOS)
        except Exception as exc:
            if logger:
                logger.warning("Failed to resize image %s: %s", path, exc)
            return None

    return image


load_png_image = load_image


def load_tk_icon(
    path: Union[str, Path],
    size: Optional[Tuple[int, int]] = None,
    logger=None,
) -> Optional[ImageTk.PhotoImage]:
    """Load an icon as a Tkinter-compatible PhotoImage."""
    image = load_image(path, size=size, logger=logger)
    if image is None:
        return None

    try:
        return ImageTk.PhotoImage(image)
    except Exception as exc:
        if logger:
            logger.warning("Failed to convert image to Tkinter PhotoImage %s: %s", path, exc)
        return None


def load_tray_icon(
    path: Union[str, Path],
    size: Tuple[int, int] = (64, 64),
    logger=None,
) -> Optional[Image.Image]:
    """Load a tray icon image for pystray."""
    return load_image(path, size=size, logger=logger)
