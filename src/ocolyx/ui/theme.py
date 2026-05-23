"""Reusable theme manager for Ocolyx UI.

Provides a futuristic cyber-blue theme with neon accents, dark navy backgrounds,
rounded panels, and reusable widget styling helpers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import customtkinter as ctk


NAMED_COLORS = {
    "blue": "#6EE3FF",
    "cyan": "#7DF9FF",
    "neon": "#7DF9FF",
    "electric": "#54E5FF",
    "teal": "#61E8FF",
    "turquoise": "#60E5FF",
}


@dataclass
class ThemeConfig:
    mode: str = "dark"
    accent_color: str = "#6EE3FF"
    bg_sidebar: str = "#030917"
    bg_main: str = "#030B18"
    header_bg: str = "#081423"
    card_bg: str = "#0C1830"
    panel_bg: str = "#0F1E37"
    panel_hover: str = "#142545"
    border_color: str = "#1E5D8D"
    glow_color: str = "#8BF7FF"
    text_primary: str = "#F3FCFF"
    text_secondary: str = "#A5C7EA"
    text_muted: str = "#7C9FCA"
    success: str = "#63FBD0"
    warning: str = "#FFE47A"
    danger: str = "#FF6D95"
    card_radius: int = 24
    border_radius: int = 16
    font_family: str = "Segoe UI"
    font_display_size: int = 22
    font_heading_size: int = 18
    font_body_size: int = 13
    font_caption_size: int = 11


class ThemeManager:
    def __init__(self, cfg: Dict[str, Any] | None = None, logger: Any | None = None) -> None:
        self.logger = logger
        self._cfg = ThemeConfig()
        if isinstance(cfg, dict):
            for key, value in cfg.items():
                if hasattr(self._cfg, key):
                    setattr(self._cfg, key, value)
        self._cfg.accent_color = self._normalize_color(self._cfg.accent_color)
        self._heading_font = None
        self._display_font = None
        self._body_font = None
        self._caption_font = None

    @staticmethod
    def _normalize_color(color: str) -> str:
        if not isinstance(color, str):
            return ThemeConfig().accent_color

        normalized = color.strip()
        if not normalized:
            return ThemeConfig().accent_color

        if normalized.startswith("#"):
            return normalized.upper()

        return NAMED_COLORS.get(normalized.lower(), ThemeConfig().accent_color)

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, value))

    @staticmethod
    def _blend_hex(start: str, end: str, ratio: float) -> str:
        start_rgb = tuple(int(start[i : i + 2], 16) for i in (1, 3, 5))
        end_rgb = tuple(int(end[i : i + 2], 16) for i in (1, 3, 5))
        ratio = ThemeManager._clamp(ratio)
        blended = tuple(
            int(start_component + (end_component - start_component) * ratio)
            for start_component, end_component in zip(start_rgb, end_rgb)
        )
        return "#" + "".join(f"{channel:02X}" for channel in blended)

    @classmethod
    def lighten(cls, color: str, amount: float = 0.18) -> str:
        return cls._blend_hex(color, "#FFFFFF", cls._clamp(amount))

    @classmethod
    def darken(cls, color: str, amount: float = 0.18) -> str:
        return cls._blend_hex(color, "#000000", cls._clamp(amount))

    @property
    def mode(self) -> str:
        return self._cfg.mode

    @property
    def accent(self) -> str:
        return self._cfg.accent_color

    @property
    def accent_soft(self) -> str:
        return self.lighten(self.accent, 0.12)

    @property
    def accent_glow(self) -> str:
        return self.lighten(self.accent, 0.24)

    @property
    def bg_sidebar(self) -> str:
        return self._cfg.bg_sidebar

    @property
    def bg_main(self) -> str:
        return self._cfg.bg_main

    @property
    def header_bg(self) -> str:
        return self._cfg.header_bg

    @property
    def card_bg(self) -> str:
        return self._cfg.card_bg

    @property
    def card_hover(self) -> str:
        return self.lighten(self.card_bg, 0.08)

    @property
    def panel_bg(self) -> str:
        return self._cfg.panel_bg

    @property
    def panel_hover(self) -> str:
        return self._cfg.panel_hover

    @property
    def border_color(self) -> str:
        return self._cfg.border_color

    @property
    def glow_color(self) -> str:
        return self._cfg.glow_color

    @property
    def text_primary(self) -> str:
        return self._cfg.text_primary

    @property
    def text_secondary(self) -> str:
        return self._cfg.text_secondary

    @property
    def text_muted(self) -> str:
        return self._cfg.text_muted

    @property
    def success(self) -> str:
        return self._cfg.success

    @property
    def warning(self) -> str:
        return self._cfg.warning

    @property
    def danger(self) -> str:
        return self._cfg.danger

    @property
    def button_bg(self) -> str:
        return self.accent

    @property
    def button_hover(self) -> str:
        return self.accent_glow

    @property
    def button_text(self) -> str:
        return self._cfg.bg_main

    @property
    def secondary_button_bg(self) -> str:
        return self.panel_bg

    @property
    def secondary_button_hover(self) -> str:
        return self.panel_hover

    @property
    def card_radius(self) -> int:
        return int(self._cfg.card_radius)

    @property
    def border_radius(self) -> int:
        return int(self._cfg.border_radius)

    @property
    def display_font(self):
        if self._display_font is None:
            self._display_font = ctk.CTkFont(family=self._cfg.font_family, size=self._cfg.font_display_size, weight="bold")
        return self._display_font

    @property
    def heading_font(self):
        if self._heading_font is None:
            self._heading_font = ctk.CTkFont(family=self._cfg.font_family, size=self._cfg.font_heading_size, weight="bold")
        return self._heading_font

    @property
    def body_font(self):
        if self._body_font is None:
            self._body_font = ctk.CTkFont(family=self._cfg.font_family, size=self._cfg.font_body_size)
        return self._body_font

    @property
    def caption_font(self):
        if self._caption_font is None:
            self._caption_font = ctk.CTkFont(family=self._cfg.font_family, size=self._cfg.font_caption_size)
        return self._caption_font

    def apply(self) -> None:
        """Apply global appearance mode to CustomTkinter."""
        try:
            ctk.set_appearance_mode(self.mode)
        except Exception:
            if self.logger:
                self.logger.exception("Failed to set appearance mode on CustomTkinter")

    def style_surface(self, widget: ctk.CTkBaseClass, *, corner_radius: int | None = None, border_width: int = 1, border_color: str | None = None) -> None:
        widget.configure(
            fg_color=self.bg_main,
            corner_radius=corner_radius if corner_radius is not None else self.card_radius,
            border_width=border_width,
            border_color=border_color or self.border_color,
        )

    def style_panel(self, widget: ctk.CTkBaseClass, *, corner_radius: int | None = None) -> None:
        widget.configure(
            fg_color=self.panel_bg,
            corner_radius=corner_radius if corner_radius is not None else self.border_radius,
            border_width=1,
            border_color=self.border_color,
        )
        self._bind_surface_hover(widget, self.panel_bg, self.panel_hover)

    def style_card(self, widget: ctk.CTkBaseClass, *, corner_radius: int | None = None) -> None:
        widget.configure(
            fg_color=self.card_bg,
            corner_radius=corner_radius if corner_radius is not None else self.card_radius,
            border_width=1,
            border_color=self.border_color,
        )
        self._bind_surface_hover(widget, self.card_bg, self.card_hover)

    def style_primary_button(self, widget: ctk.CTkBaseClass, *, text: str | None = None) -> None:
        widget.configure(
            text=text or widget.cget("text"),
            fg_color=self.button_bg,
            hover_color=self.button_hover,
            text_color=self.button_text,
            corner_radius=self.border_radius,
            border_width=1,
            border_color=self.glow_color,
            font=self.body_font,
        )

    def style_secondary_button(self, widget: ctk.CTkBaseClass, *, text: str | None = None) -> None:
        widget.configure(
            text=text or widget.cget("text"),
            fg_color=self.secondary_button_bg,
            hover_color=self.secondary_button_hover,
            text_color=self.text_primary,
            corner_radius=self.border_radius,
            border_width=1,
            border_color=self.border_color,
            font=self.body_font,
        )

    def style_title_label(self, widget: ctk.CTkBaseClass, *, text: str | None = None) -> None:
        widget.configure(
            text=text or widget.cget("text"),
            font=self.display_font,
            text_color=self.text_primary,
        )

    def style_heading_label(self, widget: ctk.CTkBaseClass, *, text: str | None = None) -> None:
        widget.configure(
            text=text or widget.cget("text"),
            font=self.heading_font,
            text_color=self.text_primary,
        )

    def style_body_label(self, widget: ctk.CTkBaseClass, *, text: str | None = None, color: str | None = None) -> None:
        widget.configure(
            text=text or widget.cget("text"),
            font=self.body_font,
            text_color=color or self.text_primary,
        )

    def style_muted_label(self, widget: ctk.CTkBaseClass, *, text: str | None = None, color: str | None = None) -> None:
        widget.configure(
            text=text or widget.cget("text"),
            font=self.body_font,
            text_color=color or self.text_muted,
        )

    def _bind_surface_hover(self, widget: ctk.CTkBaseClass, normal_bg: str, hover_bg: str) -> None:
        def on_enter(_: Any) -> None:
            if widget.winfo_exists():
                widget.configure(fg_color=hover_bg, border_color=self.accent)

        def on_leave(_: Any) -> None:
            if widget.winfo_exists():
                widget.configure(fg_color=normal_bg, border_color=self.border_color)

        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)

    def as_dict(self) -> Dict[str, Any]:
        return self._cfg.__dict__.copy()
