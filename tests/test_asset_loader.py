from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from ocolyx.utils.asset_loader import load_image, load_tray_icon, resolve_icon_paths


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


if __name__ == "__main__":
    unittest.main()
