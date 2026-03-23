from __future__ import annotations

import os
import subprocess
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

import pystray
from PIL import Image, ImageDraw

from .capture import capture_fullscreen, capture_region_interactive
from .config import AppConfig
from .storage import build_target_path, save_jpeg_atomic
from .ui.dialogs import close_settings_window, show_about, show_error, show_settings


def _make_icon(assets_dir: Path, size: int = 64) -> Image.Image:
    icon_path = assets_dir / "dmtlogo.ico"
    if icon_path.exists():
        try:
            return Image.open(str(icon_path))
        except Exception:
            pass
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((6, 10, size - 6, size - 10), radius=10, fill=(30, 41, 59, 255))
    d.rectangle((16, 22, size - 16, size - 22), fill=(226, 232, 240, 255))
    d.rectangle((20, 26, size - 20, size - 26), fill=(148, 163, 184, 255))
    d.ellipse((size - 26, size - 26, size - 14, size - 14), fill=(34, 197, 94, 255))
    return img


def _notify(icon: pystray.Icon, title: str, message: str) -> None:
    try:
        icon.notify(message, title)
    except Exception:
        # Notifications can fail on some Windows configurations; don't crash.
        pass


def _open_in_explorer(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    try:
        os.startfile(str(path))  # type: ignore[attr-defined]
    except Exception:
        try:
            subprocess.Popen(["explorer", str(path)], close_fds=True)
        except Exception:
            pass


@dataclass
class RuntimeContext:
    cfg: AppConfig
    app_dir: Path
    assets_dir: Path
    stop_event: threading.Event
    on_config_change: Callable[[AppConfig], None]
    on_show_toolbar: Callable[[], None] | None = None


def make_tray_icon(ctx: RuntimeContext) -> pystray.Icon:
    icon = pystray.Icon("DMTSnapSync", _make_icon(ctx.assets_dir), "DMTSnapSync")

    def _save_image(img: Image.Image, action_label: str) -> None:
        when = datetime.now()
        target = build_target_path(ctx.cfg.share_path, ctx.cfg.resolved_pc_alias, when=when)

        def _save_bg() -> None:
            res = save_jpeg_atomic(img, target, quality=ctx.cfg.quality)
            if res.ok and res.path:
                _notify(icon, "Saved", f"{action_label}: {res.path}")
            else:
                _notify(icon, "Save failed", res.error or "Unknown error")

        threading.Thread(target=_save_bg, daemon=True).start()

    def _capture_full() -> None:
        cap = capture_fullscreen()
        if not cap.ok or not cap.image:
            _notify(icon, "Capture failed", cap.error or "Unknown error")
            return
        _save_image(cap.image, "Fullscreen")

    def _capture_drag() -> None:
        cap = capture_region_interactive()
        if not cap.ok or not cap.image:
            _notify(icon, "Capture failed", cap.error or "Unknown error")
            return
        _save_image(cap.image, "Region")

    def _open_folder() -> None:
        target = build_target_path(ctx.cfg.share_path, ctx.cfg.resolved_pc_alias, when=datetime.now()).parent
        _open_in_explorer(target)

    def _settings() -> None:
        def _on_save(new_cfg: AppConfig) -> None:
            ctx.on_config_change(new_cfg)
            _notify(icon, "Settings", "Saved settings.")

        try:
            show_settings(ctx.cfg, on_save=_on_save)
        except Exception as e:
            show_error("Settings error", str(e))

    def _about() -> None:
        show_about(
            app_name="DMTSnapSync",
            director_name="정태훈",
            director_email="th_jeong@asdmt.com",
            developer_name="강성우",
            developer_email="sw_kang@asdmt.com",
            support_contact="sw_kang@asdmt.com",
        )

    def _quit() -> None:
        ctx.stop_event.set()
        close_settings_window()
        icon.stop()

    icon.menu = pystray.Menu(
        pystray.MenuItem("Capture Fullscreen", lambda: threading.Thread(target=_capture_full, daemon=True).start()),
        pystray.MenuItem("Capture Region (Drag)", lambda: threading.Thread(target=_capture_drag, daemon=True).start()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Show Toolbar", lambda: ctx.on_show_toolbar() if ctx.on_show_toolbar else None),
        pystray.MenuItem("Open Folder", _open_folder),
        pystray.MenuItem("Settings", _settings),
        pystray.MenuItem("About", _about),
        pystray.MenuItem("Quit", _quit),
    )
    return icon
