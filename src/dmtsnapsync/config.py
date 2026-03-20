from __future__ import annotations

import json
import os
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AppConfig:
    pc_alias: str
    share_path: str
    quality: int
    hotkey_full: str
    hotkey_drag: str

    @property
    def resolved_pc_alias(self) -> str:
        alias = (self.pc_alias or "").strip()
        if alias:
            return alias
        return socket.gethostname()


DEFAULT_CONFIG = AppConfig(
    pc_alias="",
    share_path="./shared_folder",
    quality=85,
    hotkey_full="ctrl+f9",
    hotkey_drag="ctrl+f10",
)


def get_config_path(app_dir: Path) -> Path:
    return app_dir / "config.json"


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def load_config(app_dir: Path) -> AppConfig:
    path = get_config_path(app_dir)
    if not path.exists():
        save_config(app_dir, DEFAULT_CONFIG)
        return DEFAULT_CONFIG

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("config.json must be an object")
    except Exception:
        # Do not crash a tray utility; fall back to defaults.
        return DEFAULT_CONFIG

    pc_alias = str(raw.get("pc_alias", DEFAULT_CONFIG.pc_alias) or "")
    share_path = str(raw.get("share_path", DEFAULT_CONFIG.share_path) or DEFAULT_CONFIG.share_path)
    quality = _coerce_int(raw.get("quality", DEFAULT_CONFIG.quality), DEFAULT_CONFIG.quality)
    quality = max(1, min(100, quality))
    hotkey_full = str(raw.get("hotkey_full", DEFAULT_CONFIG.hotkey_full) or DEFAULT_CONFIG.hotkey_full)
    hotkey_drag = str(raw.get("hotkey_drag", DEFAULT_CONFIG.hotkey_drag) or DEFAULT_CONFIG.hotkey_drag)

    # Expand %VAR% and ~
    share_path = os.path.expandvars(share_path)
    share_path = os.path.expanduser(share_path)

    return AppConfig(
        pc_alias=pc_alias,
        share_path=share_path,
        quality=quality,
        hotkey_full=hotkey_full,
        hotkey_drag=hotkey_drag,
    )


def save_config(app_dir: Path, cfg: AppConfig) -> None:
    path = get_config_path(app_dir)
    data = {
        "pc_alias": cfg.pc_alias,
        "share_path": cfg.share_path,
        "quality": cfg.quality,
        "hotkey_full": cfg.hotkey_full,
        "hotkey_drag": cfg.hotkey_drag,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

