"""Screen dimming overlay for Ocolyx."""

from __future__ import annotations

import ctypes
import platform
import threading
from ctypes import wintypes
from dataclasses import dataclass
from threading import RLock
from tkinter import Toplevel
from typing import List, Optional


@dataclass
class MonitorRect:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def geometry(self) -> str:
        return f"{self.width}x{self.height}+{self.left}+{self.top}"


class ScreenDimmer:
    def __init__(
        self,
        root,
        opacity: float = 0.35,
        fade_duration_ms: int = 400,
        fade_steps: int = 20,
        logger=None,
    ) -> None:
        self.root = root
        self.opacity = opacity
        self.fade_duration_ms = fade_duration_ms
        self.fade_steps = fade_steps
        self.logger = logger
        self._lock = RLock()
        self._overlays: List[Toplevel] = []
        self._active = False
        self._pulse_after_id: str | None = None
        self._after_ids: set[str] = set()
        self._is_shutting_down = False
        self._monitor_rects = self._discover_monitors()

    def _root_exists(self) -> bool:
        try:
            return bool(self.root.winfo_exists())
        except Exception:
            return False

    def _schedule_after(self, delay_ms: int, callback) -> str | None:
        if self._is_shutting_down or not self._root_exists():
            return None

        after_id: str | None = None

        def guarded_callback() -> None:
            if after_id is not None:
                self._after_ids.discard(after_id)
            if self._is_shutting_down or not self._root_exists():
                return
            callback()

        try:
            if hasattr(self.root, "schedule_after"):
                after_id = self.root.schedule_after(delay_ms, guarded_callback)
            else:
                after_id = self.root.after(delay_ms, guarded_callback)
            if after_id is not None:
                self._after_ids.add(after_id)
            return after_id
        except Exception:
            return None

    def _cancel_after(self, after_id: str | None) -> None:
        if after_id is None:
            return
        self._after_ids.discard(after_id)
        try:
            if hasattr(self.root, "cancel_after"):
                self.root.cancel_after(after_id)
            elif self._root_exists():
                self.root.after_cancel(after_id)
        except Exception:
            pass

    def _discover_monitors(self) -> List[MonitorRect]:
        if platform.system() != "Windows":
            width = self.root.winfo_screenwidth()
            height = self.root.winfo_screenheight()
            return [MonitorRect(0, 0, width, height)]

        monitors: List[MonitorRect] = []
        user32 = ctypes.windll.user32

        def _monitor_enum_proc(hMonitor, hdcMonitor, lprcMonitor, dwData):
            rect = lprcMonitor.contents
            monitors.append(MonitorRect(rect.left, rect.top, rect.right, rect.bottom))
            return 1

        MonitorEnumProc = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HMONITOR,
            wintypes.HDC,
            ctypes.POINTER(wintypes.RECT),
            wintypes.LPARAM,
        )

        callback = MonitorEnumProc(_monitor_enum_proc)
        if not user32.EnumDisplayMonitors(0, 0, callback, 0):
            width = self.root.winfo_screenwidth()
            height = self.root.winfo_screenheight()
            return [MonitorRect(0, 0, width, height)]

        if not monitors:
            width = self.root.winfo_screenwidth()
            height = self.root.winfo_screenheight()
            return [MonitorRect(0, 0, width, height)]

        return monitors

    def show(self, fade_duration_ms: Optional[int] = None, opacity: Optional[float] = None) -> None:
        if self._is_shutting_down or not self._root_exists():
            return
        if threading.current_thread() is not threading.main_thread():
            self._schedule_after(0, lambda: self.show(fade_duration_ms=fade_duration_ms, opacity=opacity))
            return

        with self._lock:
            if self._active:
                return
            self._active = True
            if opacity is not None:
                self.opacity = opacity
            if fade_duration_ms is None:
                fade_duration_ms = self.fade_duration_ms
            self._create_overlays()
            self._fade_in(fade_duration_ms)

    def pulse(
        self,
        duration_ms: int = 2500,
        fade_duration_ms: Optional[int] = None,
        opacity: Optional[float] = None,
    ) -> None:
        if self._is_shutting_down or not self._root_exists():
            return
        if threading.current_thread() is not threading.main_thread():
            self._schedule_after(0, lambda: self.pulse(duration_ms=duration_ms, fade_duration_ms=fade_duration_ms, opacity=opacity))
            return

        with self._lock:
            if self._active:
                return
            self._active = True
            if opacity is not None:
                self.opacity = opacity
            fade_ms = fade_duration_ms if fade_duration_ms is not None else self.fade_duration_ms
            hold_ms = max(1, int(duration_ms) - (fade_ms * 2))
            self._create_overlays()
            self._fade_in(fade_ms, on_complete=lambda: self._schedule_pulse_hide(hold_ms, fade_ms))

    def hide(self, fade_duration_ms: Optional[int] = None) -> None:
        if self._is_shutting_down or not self._root_exists():
            return
        if threading.current_thread() is not threading.main_thread():
            self._schedule_after(0, lambda: self.hide(fade_duration_ms=fade_duration_ms))
            return

        with self._lock:
            if not self._active:
                return
            if fade_duration_ms is None:
                fade_duration_ms = self.fade_duration_ms
            self._fade_out(fade_duration_ms)

    def _schedule_pulse_hide(self, hold_ms: int, fade_duration_ms: int) -> None:
        self._pulse_after_id = self._schedule_after(hold_ms, lambda: self.hide(fade_duration_ms=fade_duration_ms))

    def _create_overlays(self) -> None:
        if self._is_shutting_down or not self._root_exists():
            return
        self._destroy_overlays(reset_active=False)
        for monitor in self._monitor_rects:
            overlay = Toplevel(self.root)
            overlay.overrideredirect(True)
            overlay.attributes("-topmost", True)
            overlay.attributes("-alpha", 0.0)
            overlay.configure(bg="#000000")
            overlay.geometry(monitor.geometry)
            self._make_click_through(overlay)
            overlay.bind("<Escape>", lambda event: self.hide())
            overlay.lift()
            self._overlays.append(overlay)

    def _make_click_through(self, overlay: Toplevel) -> None:
        if platform.system() != "Windows":
            return

        try:
            overlay.update_idletasks()
            hwnd = overlay.winfo_id()
            user32 = ctypes.windll.user32
            get_window_long = user32.GetWindowLongW
            set_window_long = user32.SetWindowLongW
            gwl_exstyle = -20
            ws_ex_layered = 0x00080000
            ws_ex_transparent = 0x00000020
            ws_ex_noactivate = 0x08000000
            styles = get_window_long(hwnd, gwl_exstyle)
            set_window_long(hwnd, gwl_exstyle, styles | ws_ex_layered | ws_ex_transparent | ws_ex_noactivate)
        except Exception as exc:
            if self.logger:
                self.logger.warning("Failed to make dimming overlay click-through: %s", exc)

    def _destroy_overlays(self, reset_active: bool = True) -> None:
        if self._pulse_after_id is not None:
            self._cancel_after(self._pulse_after_id)
            self._pulse_after_id = None
        for after_id in list(self._after_ids):
            self._cancel_after(after_id)
        for overlay in self._overlays:
            try:
                if overlay.winfo_exists():
                    overlay.destroy()
            except Exception:
                pass
        self._overlays.clear()
        if reset_active:
            self._active = False

    def _fade_in(self, fade_duration_ms: int, on_complete=None) -> None:
        if self._is_shutting_down or not self._overlays:
            return

        step_ms = max(1, fade_duration_ms // self.fade_steps)
        alpha_step = self.opacity / self.fade_steps
        current_alpha = 0.0

        def step() -> None:
            nonlocal current_alpha
            if self._is_shutting_down or not self._root_exists():
                return
            current_alpha += alpha_step
            alpha = min(current_alpha, self.opacity)
            for overlay in self._overlays:
                try:
                    overlay.attributes("-alpha", alpha)
                except Exception:
                    pass
            if alpha < self.opacity and self._active:
                self._schedule_after(step_ms, step)
            elif on_complete:
                on_complete()

        step()

    def _fade_out(self, fade_duration_ms: int) -> None:
        if self._is_shutting_down:
            self._destroy_overlays()
            return
        if not self._overlays:
            self._destroy_overlays()
            return

        step_ms = max(1, fade_duration_ms // self.fade_steps)
        alpha_step = self.opacity / self.fade_steps
        current_alpha = self.opacity

        def step() -> None:
            nonlocal current_alpha
            if self._is_shutting_down or not self._root_exists():
                return
            current_alpha -= alpha_step
            alpha = max(current_alpha, 0.0)
            for overlay in self._overlays:
                try:
                    overlay.attributes("-alpha", alpha)
                except Exception:
                    pass
            if alpha > 0.0:
                self._schedule_after(step_ms, step)
            else:
                self._destroy_overlays()

        step()

    def is_active(self) -> bool:
        with self._lock:
            return self._active

    def toggle(self, fade_duration_ms: Optional[int] = None, opacity: Optional[float] = None) -> None:
        if self.is_active():
            self.hide(fade_duration_ms=fade_duration_ms)
        else:
            self.show(fade_duration_ms=fade_duration_ms, opacity=opacity)

    def shutdown(self) -> None:
        with self._lock:
            self._is_shutting_down = True
            self._destroy_overlays()
