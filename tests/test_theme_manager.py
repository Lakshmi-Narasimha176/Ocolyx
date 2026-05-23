from __future__ import annotations

import importlib.util
import pathlib
import sys
import unittest


class ThemeManagerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        path = pathlib.Path(__file__).resolve().parents[1] / "src" / "ocolyx" / "ui" / "theme.py"
        spec = importlib.util.spec_from_file_location("theme_module", path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Unable to load theme module")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        cls.ThemeManager = module.ThemeManager

    def test_theme_manager_resolves_named_accent_to_hex(self) -> None:
        theme = self.ThemeManager({"accent_color": "blue"})

        self.assertTrue(theme.accent.startswith("#"))
        self.assertNotEqual(theme.accent, "blue")

    def test_theme_manager_produces_hover_variant(self) -> None:
        theme = self.ThemeManager({"accent_color": "blue"})

        self.assertTrue(theme.button_hover.startswith("#"))
        self.assertNotEqual(theme.button_hover, theme.accent)


if __name__ == "__main__":
    unittest.main()
