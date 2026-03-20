from __future__ import annotations

import threading
from typing import Callable

try:
    import customtkinter as ctk
except Exception:  # pragma: no cover
    ctk = None  # type: ignore[assignment]

import tkinter as tk
from PIL import Image, ImageTk


class FloatingToolbar:
    def __init__(
        self,
        on_full: Callable[[], None],
        on_drag: Callable[[], None],
        on_settings: Callable[[], None],
        on_quit: Callable[[], None],
        icon_path: str | None = None,
        full_icon_path: str | None = None,
        region_icon_path: str | None = None,
        settings_icon_path: str | None = None,
    ) -> None:
        self._on_full = on_full
        self._on_drag = on_drag
        self._on_settings = on_settings
        self._on_quit = on_quit
        self._icon_path = icon_path
        self._full_icon_path = full_icon_path
        self._region_icon_path = region_icon_path
        self._settings_icon_path = settings_icon_path
        self._thread: threading.Thread | None = None
        self._root: tk.Tk | None = None
        self._ui_thread_id: int | None = None
        self._images: list[object] = []

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def run_on_ui_thread(self, fn):
        if self._root is None:
            return None
        if self._ui_thread_id is not None and threading.get_ident() == self._ui_thread_id:
            return fn()
        done = threading.Event()
        result = {"value": None}

        def _wrap() -> None:
            try:
                result["value"] = fn()
            finally:
                done.set()

        try:
            self._root.after(0, _wrap)
        except Exception:
            return None
        done.wait()
        return result["value"]

    def get_root(self) -> tk.Tk | None:
        return self._root

    def hide(self) -> None:
        if self._root is None:
            return
        try:
            self._root.after(0, self._root.withdraw)
        except Exception:
            pass

    def show(self) -> None:
        if self._root is None:
            return
        try:
            self._root.after(0, self._root.deiconify)
        except Exception:
            pass

    def stop(self) -> None:
        if self._root is None:
            return
        try:
            self._root.after(0, self._root.destroy)
        except Exception:
            pass

    def _run(self) -> None:
        if ctk is not None:
            ctk.set_appearance_mode("System")
            ctk.set_default_color_theme("blue")
            root = ctk.CTk()
        else:
            root = tk.Tk()
        self._root = root
        self._ui_thread_id = threading.get_ident()
        root.title("DMTSnapSync Toolbar")
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.geometry("540x96+40+40")
        if self._icon_path:
            try:
                root.iconbitmap(self._icon_path)
            except Exception:
                pass

        if ctk is not None:
            frame = ctk.CTkFrame(root, corner_radius=0)
            frame.configure(fg_color="#111827")
        else:
            frame = tk.Frame(root, bg="#111827")
        frame.pack(fill="both", expand=True)

        if ctk is not None:
            topbar = ctk.CTkFrame(frame, fg_color="#ffffff", corner_radius=0)
            topbar_content = ctk.CTkFrame(topbar, fg_color="#ffffff", corner_radius=0)
        else:
            topbar = tk.Frame(frame, bg="#ffffff")
            topbar_content = tk.Frame(topbar, bg="#ffffff")
        topbar.pack(fill="x", padx=0, pady=0)
        topbar_content.pack(fill="x", padx=10, pady=6)

        if self._icon_path:
            try:
                icon_img = Image.open(self._icon_path)
                icon_img = icon_img.resize((18, 18))
                if ctk is not None:
                    icon_photo = ctk.CTkImage(icon_img, size=(18, 18))
                    logo = ctk.CTkLabel(topbar_content, image=icon_photo, text="", fg_color="#ffffff")
                else:
                    icon_photo = ImageTk.PhotoImage(icon_img)
                    logo = tk.Label(topbar_content, image=icon_photo, bg="#ffffff")
                logo.image = icon_photo
                logo.pack(side="left", padx=(6, 6))
                if ctk is not None:
                    title = ctk.CTkLabel(topbar_content, text="DMTSnapSync", fg_color="#ffffff", text_color="#000000")
                else:
                    title = tk.Label(topbar_content, text="DMTSnapSync", bg="#ffffff", fg="#000000")
                title.pack(side="left", padx=(0, 8))
            except Exception:
                pass

        def _top_btn(text: str, cmd: Callable[[], None]):
            if ctk is not None:
                return ctk.CTkButton(
                    topbar_content,
                    text=text,
                    command=cmd,
                    fg_color="#ffffff",
                    hover_color="#f3f4f6",
                    text_color="#000000",
                    corner_radius=0,
                    height=22,
                    width=28,
                )
            return tk.Button(
                topbar_content,
                text=text,
                command=cmd,
                bg="#ffffff",
                fg="#000000",
                activebackground="#f3f4f6",
                activeforeground="#000000",
                relief="solid",
                borderwidth=1,
                padx=6,
                pady=2,
            )

        def _btn(text: str, cmd: Callable[[], None], small: bool = False):
            if ctk is not None:
                return ctk.CTkButton(
                    frame,
                    text=text,
                    command=cmd,
                    fg_color="#1f2937",
                    hover_color="#374151",
                    text_color="#e5e7eb",
                    corner_radius=0,
                    height=22 if small else 30,
                    width=28 if small else 80,
                )
            return tk.Button(
                frame,
                text=text,
                command=cmd,
                bg="#1f2937",
                fg="#e5e7eb",
                activebackground="#374151",
                activeforeground="#ffffff",
                relief="solid",
                borderwidth=1,
                padx=6 if small else 10,
                pady=2 if small else 6,
            )

        drag_x = 0
        drag_y = 0

        def _start_drag(event) -> None:
            nonlocal drag_x, drag_y
            drag_x = event.x
            drag_y = event.y

        def _on_drag(event) -> None:
            x = root.winfo_x() + event.x - drag_x
            y = root.winfo_y() + event.y - drag_y
            root.geometry(f"+{x}+{y}")

        def _bind_drag(widget) -> None:
            try:
                widget.bind("<ButtonPress-1>", _start_drag)
                widget.bind("<B1-Motion>", _on_drag)
            except Exception:
                pass

        _bind_drag(frame)
        _bind_drag(topbar)
        _bind_drag(topbar_content)

        _top_btn("X", self._on_quit).pack(side="right", padx=(4, 2))
        _top_btn("—", self.hide).pack(side="right", padx=(2, 2))

        full_img = None
        region_img = None
        settings_img = None
        if self._full_icon_path:
            try:
                img = Image.open(self._full_icon_path)
                img = img.resize((18, 18))
                if ctk is not None:
                    full_img = ctk.CTkImage(img, size=(18, 18))
                else:
                    full_img = ImageTk.PhotoImage(img)
            except Exception:
                full_img = None
        if self._region_icon_path:
            try:
                img = Image.open(self._region_icon_path)
                img = img.resize((18, 18))
                if ctk is not None:
                    region_img = ctk.CTkImage(img, size=(18, 18))
                else:
                    region_img = ImageTk.PhotoImage(img)
            except Exception:
                region_img = None
        if self._settings_icon_path:
            try:
                img = Image.open(self._settings_icon_path)
                img = img.resize((18, 18))
                if ctk is not None:
                    settings_img = ctk.CTkImage(img, size=(18, 18))
                else:
                    settings_img = ImageTk.PhotoImage(img)
            except Exception:
                settings_img = None
        if full_img is not None:
            self._images.append(full_img)
        if region_img is not None:
            self._images.append(region_img)
        if settings_img is not None:
            self._images.append(settings_img)

        full_btn = _btn("Full (F9)", self._on_full)
        if full_img:
            try:
                full_btn.configure(image=full_img, compound="left")
            except Exception:
                pass
        full_btn.pack(side="left", padx=(10, 8), pady=(8, 10))

        region_btn = _btn("Region (F10)", self._on_drag)
        if region_img:
            try:
                region_btn.configure(image=region_img, compound="left")
            except Exception:
                pass
        region_btn.pack(side="left", padx=8, pady=(8, 10))
        settings_btn = _btn("Settings", self._on_settings)
        if settings_img:
            try:
                settings_btn.configure(image=settings_img, compound="left")
            except Exception:
                pass
        settings_btn.pack(side="left", padx=8, pady=(8, 10))

        root.mainloop()
