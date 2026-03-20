from __future__ import annotations

from dataclasses import dataclass

import ctypes
import tkinter as tk

from PIL import Image, ImageGrab


@dataclass(frozen=True)
class CaptureResult:
    ok: bool
    image: Image.Image | None
    error: str | None


def capture_fullscreen() -> CaptureResult:
    try:
        img = ImageGrab.grab(all_screens=True)
        return CaptureResult(ok=True, image=img, error=None)
    except Exception as e:
        return CaptureResult(ok=False, image=None, error=str(e))


def capture_region_interactive() -> CaptureResult:
    try:
        user32 = ctypes.windll.user32
        SM_XVIRTUALSCREEN = 76
        SM_YVIRTUALSCREEN = 77
        SM_CXVIRTUALSCREEN = 78
        SM_CYVIRTUALSCREEN = 79

        vx = int(user32.GetSystemMetrics(SM_XVIRTUALSCREEN))
        vy = int(user32.GetSystemMetrics(SM_YVIRTUALSCREEN))
        vw = int(user32.GetSystemMetrics(SM_CXVIRTUALSCREEN))
        vh = int(user32.GetSystemMetrics(SM_CYVIRTUALSCREEN))

        root = tk.Tk()
        root.withdraw()

        sel: dict[str, int | None] = {"x1": None, "y1": None, "x2": None, "y2": None}

        overlay = tk.Toplevel(root)
        overlay.overrideredirect(True)
        overlay.attributes("-topmost", True)
        overlay.attributes("-alpha", 0.25)
        overlay.configure(bg="black")
        overlay.geometry(f"{vw}x{vh}+{vx}+{vy}")

        canvas = tk.Canvas(overlay, bg="black", highlightthickness=0, cursor="cross")
        canvas.pack(fill="both", expand=True)

        rect_id: int | None = None

        def _cancel(_event=None) -> None:
            sel["x1"] = sel["y1"] = sel["x2"] = sel["y2"] = None
            overlay.destroy()
            root.quit()

        def _on_press(event) -> None:
            nonlocal rect_id
            x = int(event.x_root)
            y = int(event.y_root)
            sel["x1"], sel["y1"] = x, y
            sel["x2"], sel["y2"] = x, y
            if rect_id is not None:
                canvas.delete(rect_id)
            # Translate screen coords into overlay-local coords.
            rect_id = canvas.create_rectangle(
                x - vx,
                y - vy,
                x - vx + 1,
                y - vy + 1,
                outline="#84cc16",
                width=3,
            )

        def _on_drag(event) -> None:
            if sel["x1"] is None or sel["y1"] is None:
                return
            x = int(event.x_root)
            y = int(event.y_root)
            sel["x2"], sel["y2"] = x, y
            if rect_id is not None:
                canvas.coords(rect_id, sel["x1"] - vx, sel["y1"] - vy, x - vx, y - vy)

        def _on_release(_event) -> None:
            overlay.destroy()
            root.quit()

        overlay.bind("<Escape>", _cancel)
        canvas.bind("<ButtonPress-1>", _on_press)
        canvas.bind("<B1-Motion>", _on_drag)
        canvas.bind("<ButtonRelease-1>", _on_release)

        root.deiconify()
        root.withdraw()
        root.mainloop()
        root.destroy()

        if sel["x1"] is None or sel["y1"] is None or sel["x2"] is None or sel["y2"] is None:
            return CaptureResult(ok=False, image=None, error="Selection cancelled.")

        x1, y1 = int(sel["x1"]), int(sel["y1"])
        x2, y2 = int(sel["x2"]), int(sel["y2"])
        left, right = (x1, x2) if x1 <= x2 else (x2, x1)
        top, bottom = (y1, y2) if y1 <= y2 else (y2, y1)

        if right - left < 5 or bottom - top < 5:
            return CaptureResult(ok=False, image=None, error="Selection too small.")

        img = ImageGrab.grab(bbox=(left, top, right, bottom), all_screens=True)
        return CaptureResult(ok=True, image=img, error=None)
    except Exception as e:
        return CaptureResult(ok=False, image=None, error=str(e))

