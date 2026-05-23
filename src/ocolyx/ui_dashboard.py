"""Tkinter dashboard for Ocolyx."""

import customtkinter as ctk
from typing import Any


class OcolyxDashboard:
    def __init__(self, config_manager, background_service, logger) -> None:
        self.config_manager = config_manager
        self.background_service = background_service
        self.logger = logger
        self.app = ctk.CTk()
        self.app.title("Ocolyx")
        self.app.geometry(
            f"{config_manager.get('window', {}).get('width', 960)}x{config_manager.get('window', {}).get('height', 620)}"
        )

        self._build_ui()

    def _build_ui(self) -> None:
        label = ctk.CTkLabel(self.app, text="Ocolyx Eye-Strain Prevention")
        label.pack(padx=24, pady=24)

    def run(self) -> None:
        self.logger.info("Launching dashboard")
        self.app.mainloop()
