import logging
import threading
import time
from pathlib import Path

from src.ocolyx.config_manager import ConfigManager
from src.ocolyx.services.background_service import BackgroundService
from src.ocolyx.ui.controller import DashboardController


def _build_controller() -> DashboardController:
    logger = logging.getLogger("test.dashboard.window")
    config_path = Path(__file__).resolve().parents[1] / "config" / "default_config.json"
    config_manager = ConfigManager(config_path, logger=logger)
    background_service = BackgroundService(config_manager, logger)
    return DashboardController(config_manager, background_service, logger)


def test_show_window_restores_withdrawn_window() -> None:
    controller = _build_controller()
    try:
        controller.view.withdraw()
        assert controller.view.state() == "withdrawn"

        controller.show_window()

        assert controller.view.state() == "normal"
    finally:
        controller.view.destroy()


def test_show_window_restores_iconified_window() -> None:
    controller = _build_controller()
    try:
        controller.view.iconify()
        assert controller.view.state() == "iconic"

        controller.show_window()

        assert controller.view.state() == "normal"
    finally:
        controller.view.deiconify()
        controller.view.destroy()


def test_safe_update_queues_worker_callbacks_to_main_thread() -> None:
    controller = _build_controller()
    main_thread_id = threading.get_ident()
    completed = threading.Event()
    callback_thread_ids: list[int] = []

    def callback() -> None:
        callback_thread_ids.append(threading.get_ident())
        completed.set()

    try:
        def worker() -> None:
            controller.view.safe_update(callback)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        thread.join()

        deadline = time.time() + 2.0
        while not completed.is_set() and time.time() < deadline:
            controller.view.update()
            time.sleep(0.01)

        assert completed.is_set()
        assert callback_thread_ids == [main_thread_id]
    finally:
        controller.view.destroy()


def test_settings_apply_rejects_zero_timing_values() -> None:
    controller = _build_controller()
    applied_updates: list[dict[str, object]] = []
    controller.view.on_settings_change = applied_updates.append

    try:
        controller.view.show_settings_view()
        controller.view._setting_vars["alert_delay_minutes"].set("0")

        controller.view._apply_numeric_settings()

        assert applied_updates == []
        assert "First notification delay must be greater than 0 minutes." == controller.view._settings_error_var.get()
    finally:
        controller.view.destroy()


def test_settings_success_message_auto_hides() -> None:
    controller = _build_controller()

    try:
        controller.view.show_settings_view()
        controller.view.show_settings_success()
        controller.view.update_idletasks()

        assert controller.view._settings_feedback_var.get() == "Settings applied successfully"
        assert controller.view._settings_feedback_frame.winfo_ismapped()

        deadline = time.time() + 3.0
        while controller.view._settings_feedback_frame.winfo_ismapped() and time.time() < deadline:
            controller.view.update()
            time.sleep(0.01)

        assert not controller.view._settings_feedback_frame.winfo_ismapped()
    finally:
        controller.view.destroy()
