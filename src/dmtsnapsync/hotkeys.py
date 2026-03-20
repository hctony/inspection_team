from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable

import keyboard


@dataclass(frozen=True)
class HotkeyHandles:
    full_id: int | None
    drag_id: int | None


def register_hotkeys(
    hotkey_full: str,
    hotkey_drag: str,
    on_full: Callable[[], None],
    on_drag: Callable[[], None],
) -> HotkeyHandles:
    # Run callbacks in separate threads to avoid blocking keyboard hook.
    def _wrap(fn: Callable[[], None]) -> Callable[[], None]:
        return lambda: threading.Thread(target=fn, daemon=True).start()

    full_id: int | None = None
    drag_id: int | None = None
    if hotkey_full:
        full_id = keyboard.add_hotkey(hotkey_full, _wrap(on_full))
    if hotkey_drag:
        drag_id = keyboard.add_hotkey(hotkey_drag, _wrap(on_drag))
    return HotkeyHandles(full_id=full_id, drag_id=drag_id)


def unregister_hotkeys(handles: HotkeyHandles) -> None:
    try:
        if handles.full_id is not None:
            keyboard.remove_hotkey(handles.full_id)
    except Exception:
        pass
    try:
        if handles.drag_id is not None:
            keyboard.remove_hotkey(handles.drag_id)
    except Exception:
        pass

