from __future__ import annotations

import os
import tempfile
from io import BytesIO
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


def resolve_unique_path(target: Path) -> Path:
    if not target.exists():
        return target
    stem = target.stem
    suffix = target.suffix
    i = 1
    while True:
        candidate = target.with_name(f"{stem}_{i}{suffix}")
        if not candidate.exists():
            return candidate
        i += 1


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _encode_jpeg_bytes(img_rgb: Image.Image, quality: int) -> bytes:
    buf = BytesIO()
    img_rgb.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def _resample_lanczos() -> int:
    if hasattr(Image, "Resampling"):
        return Image.Resampling.LANCZOS  # type: ignore[attr-defined]
    return Image.LANCZOS


def _fit_jpeg_bytes(img_rgb: Image.Image, quality: int, max_bytes: int) -> bytes | None:
    # Try lowering JPEG quality first, then scale down if still too large.
    current = img_rgb
    min_quality = 1
    max_quality = max(1, min(100, quality))

    while True:
        best: bytes | None = None
        lo = min_quality
        hi = max_quality

        while lo <= hi:
            mid = (lo + hi) // 2
            data = _encode_jpeg_bytes(current, mid)
            if len(data) <= max_bytes:
                best = data
                lo = mid + 1
            else:
                hi = mid - 1

        if best is not None:
            return best

        if current.width <= 1 or current.height <= 1:
            return None

        next_w = max(1, int(current.width * 0.9))
        next_h = max(1, int(current.height * 0.9))
        if next_w == current.width and current.width > 1:
            next_w = current.width - 1
        if next_h == current.height and current.height > 1:
            next_h = current.height - 1

        current = current.resize((next_w, next_h), _resample_lanczos())


def save_jpeg_atomic(
    img: Image.Image,
    target: Path,
    quality: int,
    max_image_size_kb: int | None = None,
) -> SaveResult:
    try:
        # Avoid overwriting existing files by adding a suffix.
        target = resolve_unique_path(target)

        ensure_parent_dir(target)

        # Write temp in same directory so rename is as atomic as possible on same volume/share.
        tmp_fd, tmp_path_str = tempfile.mkstemp(prefix=target.stem + "_", suffix=".tmp", dir=str(target.parent))
        os.close(tmp_fd)
        tmp_path = Path(tmp_path_str)

        try:
            img_rgb = img.convert("RGB")
            if max_image_size_kb and max_image_size_kb > 0:
                max_bytes = max_image_size_kb * 1024
                data = _fit_jpeg_bytes(img_rgb, quality=quality, max_bytes=max_bytes)
                if data is None:
                    return SaveResult(
                        ok=False,
                        path=None,
                        error=f"Could not fit image into {max_image_size_kb}KB",
                    )
                tmp_path.write_bytes(data)
            else:
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

