from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from unittest.mock import MagicMock, patch

from ocolyx.utils.asset_loader import (
    apply_tk_window_icon,
    apply_windows_app_user_model_id,
    load_image,
    load_tray_icon,
    resolve_icon_paths,
)


class AssetLoaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.icons_dir = self.root / "assets" / "icons"
        self.icons_dir.mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _create_jpeg(self, name: str = "Ocolyx.jpeg") -> Path:
        path = self.icons_dir / name
        image = Image.new("RGB", (200, 100), color="blue")
        image.save(path, format="JPEG")
        return path

    def test_resolve_icon_paths_prefers_ico_when_present(self) -> None:
        ico_path = self.icons_dir / "ocolyx.ico"
        ico_path.write_bytes(b"fake-ico")
        jpeg_path = self._create_jpeg()

        resolved_ico, resolved_jpeg = resolve_icon_paths(self.root)

        self.assertEqual(resolved_ico, ico_path)
        self.assertEqual(resolved_jpeg, jpeg_path)

    def test_resolve_icon_paths_falls_back_to_jpeg_when_ico_missing(self) -> None:
        jpeg_path = self._create_jpeg()

        resolved_ico, resolved_jpeg = resolve_icon_paths(self.root)

        self.assertIsNone(resolved_ico)
        self.assertEqual(resolved_jpeg, jpeg_path)

    def test_load_image_resizes_using_pillow(self) -> None:
        jpeg_path = self._create_jpeg()

        image = load_image(jpeg_path, size=(64, 64))

        self.assertIsNotNone(image)
        self.assertEqual(image.size, (64, 64))

    def test_load_tray_icon_returns_resized_image_for_jpeg(self) -> None:
        jpeg_path = self._create_jpeg()

        image = load_tray_icon(jpeg_path, size=(64, 64))

        self.assertIsNotNone(image)
        self.assertEqual(image.size, (64, 64))

    def test_apply_tk_window_icon_returns_false_when_assets_missing(self) -> None:
        window = MagicMock()

        applied, photo = apply_tk_window_icon(window, None, None)

        self.assertFalse(applied)
        self.assertIsNone(photo)
        window.iconbitmap.assert_not_called()
        window.iconphoto.assert_not_called()

    @patch("ocolyx.utils.asset_loader.load_tk_icon")
    def test_apply_tk_window_icon_uses_ico_when_present(self, mock_load_tk_icon) -> None:
        ico_path = self.icons_dir / "ocolyx.ico"
        image = Image.new("RGBA", (32, 32), color=(12, 34, 56, 255))
        image.save(ico_path, format="ICO", sizes=[(32, 32)])
        mock_photo = MagicMock()
        mock_load_tk_icon.return_value = mock_photo
        window = MagicMock()

        applied, photo = apply_tk_window_icon(window, ico_path, None, windows_shell=False)

        self.assertTrue(applied)
        self.assertIs(mock_photo, photo)
        window.iconbitmap.assert_called_once_with(str(ico_path.resolve()))
        window.iconphoto.assert_called_once_with(True, mock_photo)

    @patch("ocolyx.utils.asset_loader.load_tk_icon")
    def test_apply_tk_window_icon_falls_back_to_logo(self, mock_load_tk_icon) -> None:
        jpeg_path = self._create_jpeg()
        mock_photo = MagicMock()
        mock_load_tk_icon.return_value = mock_photo
        window = MagicMock()

        applied, photo = apply_tk_window_icon(window, None, jpeg_path, windows_shell=False)

        self.assertTrue(applied)
        self.assertIs(mock_photo, photo)
        window.iconbitmap.assert_not_called()
        window.iconphoto.assert_called_once_with(True, mock_photo)

    @patch("ocolyx.utils.asset_loader.sys.platform", "win32")
    @patch("ocolyx.utils.asset_loader._apply_windows_shell_icons", return_value=True)
    def test_apply_tk_window_icon_applies_windows_shell_icons_for_ico(
        self,
        mock_shell_icons,
    ) -> None:
        ico_path = self.icons_dir / "ocolyx.ico"
        image = Image.new("RGBA", (32, 32), color=(12, 34, 56, 255))
        image.save(ico_path, format="ICO", sizes=[(32, 32)])
        window = MagicMock()

        apply_tk_window_icon(window, ico_path, None)

        mock_shell_icons.assert_called_once()

    @patch("ocolyx.utils.asset_loader.sys.platform", "win32")
    @patch("ocolyx.utils.asset_loader.ctypes")
    def test_apply_windows_app_user_model_id_sets_process_id(self, mock_ctypes) -> None:
        apply_windows_app_user_model_id()

        mock_ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID.assert_called_once_with(
            "Ocolyx.Desktop.App"
        )


if __name__ == "__main__":
    unittest.main()
