from __future__ import annotations

import json
import os
import re
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AppConfig:
    pc_alias: str
    share_path: str
    quality: int
    max_image_size_kb: int | None
    owner_name: str
    owner_email: str
    developer_name: str
    developer_email: str
    support_contact: str
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
    share_path="C:\\DMTSnapSync",
    quality=85,
    max_image_size_kb=None,
    owner_name="",
    owner_email="",
    developer_name="",
    developer_email="",
    support_contact="",
    hotkey_full="ctrl+f9",
    hotkey_drag="ctrl+f10",
)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def get_config_path(app_dir: Path) -> Path:
    return app_dir / "config.json"


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _coerce_optional_positive_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        n = int(value)
    except Exception:
        return None
    if n < 1:
        return None
    return n


def _is_valid_email(value: str) -> bool:
    return bool(_EMAIL_RE.match(value.strip()))


def validate_about_metadata(cfg: AppConfig, require_all: bool = True) -> str | None:
    owner_name = cfg.owner_name.strip()
    owner_email = cfg.owner_email.strip()
    developer_name = cfg.developer_name.strip()
    developer_email = cfg.developer_email.strip()
    support_contact = cfg.support_contact.strip()

    if require_all:
        if not owner_name:
            return "Owner/Director name is required."
        if not owner_email:
            return "Owner/Director email is required."
        if not developer_name:
            return "Developer name is required."
        if not developer_email:
            return "Developer email is required."
        if not support_contact:
            return "Support contact is required."
    else:
        if bool(owner_name) != bool(owner_email):
            return "Owner/Director name and email must be entered together."
        if bool(developer_name) != bool(developer_email):
            return "Developer name and email must be entered together."

    if owner_email and not _is_valid_email(owner_email):
        return "Owner/Director email format is invalid."
    if developer_email and not _is_valid_email(developer_email):
        return "Developer email format is invalid."

    return None


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
    share_path = str(raw.get("share_path", DEFAULT_CONFIG.share_path) or "").strip()
    if not share_path:
        share_path = DEFAULT_CONFIG.share_path
    if share_path in ("./shared_folder", ".\\shared_folder", "%USERPROFILE%\\Desktop"):
        share_path = DEFAULT_CONFIG.share_path
    quality = _coerce_int(raw.get("quality", DEFAULT_CONFIG.quality), DEFAULT_CONFIG.quality)
    quality = max(1, min(100, quality))
    max_image_size_kb = _coerce_optional_positive_int(
        raw.get("max_image_size_kb", DEFAULT_CONFIG.max_image_size_kb)
    )
    owner_name = str(raw.get("owner_name", DEFAULT_CONFIG.owner_name) or "").strip()
    owner_email = str(raw.get("owner_email", DEFAULT_CONFIG.owner_email) or "").strip()
    developer_name = str(raw.get("developer_name", DEFAULT_CONFIG.developer_name) or "").strip()
    developer_email = str(raw.get("developer_email", DEFAULT_CONFIG.developer_email) or "").strip()
    support_contact = str(raw.get("support_contact", DEFAULT_CONFIG.support_contact) or "").strip()
    hotkey_full = str(raw.get("hotkey_full", DEFAULT_CONFIG.hotkey_full) or DEFAULT_CONFIG.hotkey_full)
    hotkey_drag = str(raw.get("hotkey_drag", DEFAULT_CONFIG.hotkey_drag) or DEFAULT_CONFIG.hotkey_drag)

    # Expand %VAR% and ~
    share_path = os.path.expandvars(share_path)
    share_path = os.path.expanduser(share_path)

    return AppConfig(
        pc_alias=pc_alias,
        share_path=share_path,
        quality=quality,
        max_image_size_kb=max_image_size_kb,
        owner_name=owner_name,
        owner_email=owner_email,
        developer_name=developer_name,
        developer_email=developer_email,
        support_contact=support_contact,
        hotkey_full=hotkey_full,
        hotkey_drag=hotkey_drag,
    )


def save_config(app_dir: Path, cfg: AppConfig) -> None:
    path = get_config_path(app_dir)
    data = {
        "pc_alias": cfg.pc_alias,
        "share_path": cfg.share_path,
        "quality": cfg.quality,
        "max_image_size_kb": cfg.max_image_size_kb,
        "owner_name": cfg.owner_name,
        "owner_email": cfg.owner_email,
        "developer_name": cfg.developer_name,
        "developer_email": cfg.developer_email,
        "support_contact": cfg.support_contact,
        "hotkey_full": cfg.hotkey_full,
        "hotkey_drag": cfg.hotkey_drag,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

