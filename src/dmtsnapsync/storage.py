from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image


@dataclass(frozen=True)
class SaveResult:
    ok: bool
    path: Path | None
    error: str | None


def build_target_path(share_path: str, pc_alias: str, when: datetime | None = None) -> Path:
    when = when or datetime.now()
    date_part = when.strftime("%Y-%m-%d")
    time_part = when.strftime("%H%M%S")
    filename = f"cap_{time_part}.jpg"
    return Path(share_path) / pc_alias / date_part / filename


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def save_jpeg_atomic(img: Image.Image, target: Path, quality: int) -> SaveResult:
    try:
        # Avoid overwriting existing files by adding a suffix.
        if target.exists():
            stem = target.stem
            suffix = target.suffix
            i = 1
            while True:
                candidate = target.with_name(f"{stem}_{i}{suffix}")
                if not candidate.exists():
                    target = candidate
                    break
                i += 1

        ensure_parent_dir(target)

        # Write temp in same directory so rename is as atomic as possible on same volume/share.
        tmp_fd, tmp_path_str = tempfile.mkstemp(prefix=target.stem + "_", suffix=".tmp", dir=str(target.parent))
        os.close(tmp_fd)
        tmp_path = Path(tmp_path_str)

        try:
            img_rgb = img.convert("RGB")
            img_rgb.save(str(tmp_path), format="JPEG", quality=quality, optimize=True)
            os.replace(str(tmp_path), str(target))
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass

        return SaveResult(ok=True, path=target, error=None)
    except Exception as e:
        return SaveResult(ok=False, path=None, error=str(e))

