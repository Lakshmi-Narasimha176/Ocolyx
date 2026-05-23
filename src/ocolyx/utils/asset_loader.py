"""Asset loading helpers for Ocolyx."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple, Union

from PIL import Image, ImageTk


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
    ico_path = _resolve_existing_asset(base_dir, ["ocolyx.ico", "Ocolyx.ico"])
    jpeg_path = _resolve_existing_asset(base_dir, ["ocolyx.jpeg", "Ocolyx.jpeg", "ocolyx.jpg", "Ocolyx.jpg"])
    return ico_path, jpeg_path


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
