from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path

from .capture import capture_fullscreen, capture_region_interactive
from .config import AppConfig, load_config, save_config, validate_about_metadata
from .hotkeys import HotkeyHandles, register_hotkeys, unregister_hotkeys
from .retry_sync import RetrySyncQueue
from .storage import build_target_path, save_jpeg_atomic
from .tray import RuntimeContext, make_tray_icon
from .ui.dialogs import close_settings_window, show_about, show_error, show_settings
from .ui.toolbar import FloatingToolbar


def _app_dir() -> Path:
    # Running under PyInstaller onefile: config.json should live next to exe (current working directory).
    # In dev: use DMTSnapSync folder as working directory (recommended in README).
    return Path.cwd()


def main() -> int:
    app_dir = _app_dir()
    assets_dir = Path(__file__).resolve().parent / "assets"
    stop_event = threading.Event()
    retry_queue = RetrySyncQueue(app_dir)

    cfg = load_config(app_dir)
    cfg_lock = threading.Lock()

    hotkey_handles: HotkeyHandles | None = None

    def _get_cfg() -> AppConfig:
        with cfg_lock:
            return cfg

    def _set_cfg(new_cfg: AppConfig) -> None:
        nonlocal cfg, hotkey_handles
        with cfg_lock:
            cfg = new_cfg
            save_config(app_dir, cfg)
            if hotkey_handles is not None:
                unregister_hotkeys(hotkey_handles)
                hotkey_handles = None

    def _register_current_hotkeys() -> None:
        nonlocal hotkey_handles
        c = _get_cfg()
        try:
            hotkey_handles = register_hotkeys(c.hotkey_full, c.hotkey_drag, on_full=_on_full, on_drag=_on_drag)
        except Exception:
            hotkey_handles = None

    def _on_config_change(new_cfg: AppConfig) -> None:
        _set_cfg(new_cfg)
        _register_current_hotkeys()

    def _show_toolbar() -> None:
        if toolbar is not None:
            toolbar.show()

    ctx = RuntimeContext(
        cfg=_get_cfg(),
        app_dir=app_dir,
        assets_dir=assets_dir,
        stop_event=stop_event,
        on_config_change=_on_config_change,
        on_show_toolbar=_show_toolbar,
        retry_queue=retry_queue,
    )

    icon = make_tray_icon(ctx)
    toolbar: FloatingToolbar | None = None

    def _notify(title: str, message: str) -> None:
        try:
            icon.notify(message, title)
        except Exception:
            pass

    retry_queue.set_notifier(_notify)
    retry_queue.start()

    def _save_capture(img, label: str) -> None:
        c = _get_cfg()
        when = datetime.now()
        target = build_target_path(c.share_path, c.resolved_pc_alias, when=when)

        def _save_bg() -> None:
            res = save_jpeg_atomic(
                img,
                target,
                quality=c.quality,
                max_image_size_kb=c.max_image_size_kb,
            )
            if res.ok and res.path:
                _notify("Saved", f"{label}: {res.path}")
            elif ctx.retry_queue is not None:
                qres = ctx.retry_queue.enqueue_image(
                    img,
                    target,
                    quality=c.quality,
                    max_image_size_kb=c.max_image_size_kb,
                )
                if qres.ok and qres.path:
                    _notify("Queued", f"{label}: {qres.path.name}")
                else:
                    _notify("Save failed", qres.error or res.error or "Unknown error")
            else:
                _notify("Save failed", res.error or "Unknown error")

        threading.Thread(target=_save_bg, daemon=True).start()

    def _on_full() -> None:
        if toolbar is not None:
            toolbar.hide()
        cap = capture_fullscreen()
        if not cap.ok or not cap.image:
            _notify("Capture failed", cap.error or "Unknown error")
            if toolbar is not None:
                toolbar.show()
            return
        _save_capture(cap.image, "Fullscreen")
        if toolbar is not None:
            toolbar.show()

    def _on_drag() -> None:
        if toolbar is not None:
            toolbar.hide()
        cap = capture_region_interactive()
        if not cap.ok or not cap.image:
            _notify("Capture failed", cap.error or "Unknown error")
            if toolbar is not None:
                toolbar.show()
            return
        _save_capture(cap.image, "Region")
        if toolbar is not None:
            toolbar.show()

    def _open_settings() -> None:
        def _on_save(new_cfg: AppConfig) -> None:
            _on_config_change(new_cfg)
            _notify("Settings", "Saved settings.")

        try:
            # Use the same settings window path as tray menu to keep icon behavior consistent.
            show_settings(_get_cfg(), on_save=_on_save)
        except Exception as e:
            show_error("Settings error", str(e))

    def _open_about() -> None:
        c = _get_cfg()
        about_error = validate_about_metadata(c)
        if about_error:
            show_error("About metadata missing", f"{about_error}\nPlease update Settings.")
            return
        try:
            show_about(
                app_name="DMTSnapSync",
                director_name=c.owner_name,
                director_email=c.owner_email,
                developer_name=c.developer_name,
                developer_email=c.developer_email,
                support_contact=c.support_contact,
            )
        except Exception as e:
            show_error("About error", str(e))

    def _quit_all() -> None:
        stop_event.set()
        retry_queue.stop()
        try:
            icon.stop()
        except Exception:
            pass
        try:
            close_settings_window()
        except Exception:
            pass
        if toolbar is not None:
            toolbar.stop()

    def _run_icon() -> None:
        icon.run()

    t = threading.Thread(target=_run_icon, daemon=True)
    t.start()

    _register_current_hotkeys()

    icon_path = assets_dir / "dmtlogo.ico"
    full_icon_path = assets_dir / "fullscn.png"
    region_icon_path = assets_dir / "areascn.png"
    settings_icon_path = assets_dir / "setting.png"
    about_icon_path = assets_dir / "inquiry.png"
    toolbar = FloatingToolbar(
        on_full=_on_full,
        on_drag=_on_drag,
        on_settings=_open_settings,
        on_about=_open_about,
        on_quit=_quit_all,
        icon_path=str(icon_path) if icon_path.exists() else None,
        full_icon_path=str(full_icon_path) if full_icon_path.exists() else None,
        region_icon_path=str(region_icon_path) if region_icon_path.exists() else None,
        settings_icon_path=str(settings_icon_path) if settings_icon_path.exists() else None,
        about_icon_path=str(about_icon_path) if about_icon_path.exists() else None,
    )
    toolbar.start()

    # Keep cfg on ctx updated (tray callbacks use ctx.cfg snapshot)
    while not stop_event.is_set():
        with cfg_lock:
            ctx.cfg = cfg
        stop_event.wait(0.5)

    try:
        if hotkey_handles is not None:
            unregister_hotkeys(hotkey_handles)
    except Exception:
        pass
    try:
        if toolbar is not None:
            toolbar.stop()
    except Exception:
        pass
    try:
        t.join(timeout=1.0)
    except Exception:
        pass
    try:
        retry_queue.stop()
    except Exception:
        pass

    return 0


