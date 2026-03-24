from __future__ import annotations

import json
import os
import shutil
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from PIL import Image

from .storage import SaveResult, ensure_parent_dir, resolve_unique_path, save_jpeg_atomic


@dataclass
class RetryQueueItem:
    item_id: str
    local_path: str
    target_path: str
    attempts: int
    created_ts: float
    next_retry_ts: float


class RetrySyncQueue:
    def __init__(self, app_dir: Path, notifier: Callable[[str, str], None] | None = None) -> None:
        self.app_dir = app_dir
        self.spool_dir = app_dir / "_retry_spool"
        self.queue_path = app_dir / "retry_queue.json"
        self._notifier = notifier
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._items: list[RetryQueueItem] = []
        self._load_state()

    def set_notifier(self, notifier: Callable[[str, str], None] | None) -> None:
        self._notifier = notifier

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        t = self._thread
        if t is not None and t.is_alive():
            t.join(timeout=1.5)

    def pending_count(self) -> int:
        with self._lock:
            return len(self._items)

    def enqueue_image(
        self,
        img: Image.Image,
        target: Path,
        quality: int,
        max_image_size_kb: int | None = None,
    ) -> SaveResult:
        try:
            self.spool_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return SaveResult(ok=False, path=None, error=f"Retry spool dir create failed: {e}")

        item_id = uuid.uuid4().hex
        local_target = self.spool_dir / f"{item_id}.jpg"
        local_res = save_jpeg_atomic(
            img,
            local_target,
            quality=quality,
            max_image_size_kb=max_image_size_kb,
        )
        if not local_res.ok or local_res.path is None:
            return SaveResult(ok=False, path=None, error=local_res.error or "Local queue save failed")

        now = time.time()
        item = RetryQueueItem(
            item_id=item_id,
            local_path=str(local_res.path),
            target_path=str(target),
            attempts=0,
            created_ts=now,
            next_retry_ts=now,
        )
        with self._lock:
            self._items.append(item)
            self._save_state_locked()

        self._notify("Queued", f"Saved locally and queued for retry ({self.pending_count()})")
        return SaveResult(ok=True, path=local_res.path, error=None)

    def retry_now(self) -> None:
        self._retry_due_items(force=True)

    def _run_loop(self) -> None:
        while not self._stop_event.wait(5.0):
            self._retry_due_items(force=False)

    def _retry_due_items(self, force: bool) -> None:
        with self._lock:
            now = time.time()
            due_ids = [
                i.item_id
                for i in self._items
                if force or i.next_retry_ts <= now
            ]
        for item_id in due_ids:
            self._retry_one(item_id)

    def _retry_one(self, item_id: str) -> None:
        with self._lock:
            item = next((x for x in self._items if x.item_id == item_id), None)
        if item is None:
            return

        local_path = Path(item.local_path)
        target_path = Path(item.target_path)

        if not local_path.exists():
            with self._lock:
                self._items = [x for x in self._items if x.item_id != item_id]
                self._save_state_locked()
            return

        try:
            target_path = resolve_unique_path(target_path)
            ensure_parent_dir(target_path)
            try:
                os.replace(str(local_path), str(target_path))
            except OSError:
                shutil.copy2(str(local_path), str(target_path))
                local_path.unlink(missing_ok=True)
        except Exception:
            with self._lock:
                cur = next((x for x in self._items if x.item_id == item_id), None)
                if cur is None:
                    return
                cur.attempts += 1
                delay_sec = min(300, 5 * (2 ** min(cur.attempts, 6)))
                cur.next_retry_ts = time.time() + delay_sec
                self._save_state_locked()
            return

        with self._lock:
            self._items = [x for x in self._items if x.item_id != item_id]
            self._save_state_locked()

        self._notify("Synced", f"Queued capture synced ({self.pending_count()} pending)")

    def _notify(self, title: str, message: str) -> None:
        fn = self._notifier
        if fn is None:
            return
        try:
            fn(title, message)
        except Exception:
            pass

    def _save_state_locked(self) -> None:
        data = [asdict(i) for i in self._items]
        tmp = self.queue_path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            os.replace(str(tmp), str(self.queue_path))
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except Exception:
                    pass

    def _load_state(self) -> None:
        if not self.queue_path.exists():
            return
        try:
            raw = json.loads(self.queue_path.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                return
            items: list[RetryQueueItem] = []
            for r in raw:
                if not isinstance(r, dict):
                    continue
                try:
                    items.append(
                        RetryQueueItem(
                            item_id=str(r.get("item_id") or ""),
                            local_path=str(r.get("local_path") or ""),
                            target_path=str(r.get("target_path") or ""),
                            attempts=int(r.get("attempts", 0)),
                            created_ts=float(r.get("created_ts", time.time())),
                            next_retry_ts=float(r.get("next_retry_ts", time.time())),
                        )
                    )
                except Exception:
                    continue
            with self._lock:
                self._items = [i for i in items if i.item_id and i.local_path and i.target_path]
        except Exception:
            with self._lock:
                self._items = []
