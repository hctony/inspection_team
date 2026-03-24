from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import re
import sys
import threading
from typing import Callable

import tkinter as tk
from tkinter import filedialog, messagebox

from PIL import Image, ImageTk

from ..config import AppConfig

try:
    import customtkinter as ctk
except Exception:  # pragma: no cover
    ctk = None  # type: ignore[assignment]

_save_dialog_lock = threading.Lock()
_save_dialog_open = False
_about_window: object | None = None
_settings_window: tk.Tk | tk.Toplevel | None = None
_window_icon_refs: dict[int, ImageTk.PhotoImage] = {}

_INVALID_FILENAME_CHARS = r'<>:"/\\|?*'
_INVALID_FILENAME_RE = re.compile(f"[{re.escape(_INVALID_FILENAME_CHARS)}]")

_THEME_WHITE = "#ffffff"
_THEME_DARK = "#111827"
_THEME_DARK_PANEL = "#1f2937"
_THEME_DARK_PANEL_HOVER = "#374151"
_THEME_TEXT_LIGHT = "#e5e7eb"
_THEME_TEXT_DARK = "#111827"
_THEME_ERROR = "#fca5a5"


def _assets_icon_path() -> Path:
    if getattr(sys, "frozen", False):
        mei_base = Path(getattr(sys, "_MEIPASS", Path.cwd()))
        bundled = mei_base / "dmtsnapsync" / "assets" / "dmtlogo.ico"
        if bundled.exists():
            return bundled
    return Path(__file__).resolve().parent.parent / "assets" / "dmtlogo.ico"


def _sanitize_filename(name: str, default_base: str) -> str:
    base = (name or "").strip()
    if base.lower().endswith(".jpg") or base.lower().endswith(".jpeg"):
        base = re.sub(r"\.(jpe?g)$", "", base, flags=re.IGNORECASE)
    base = _INVALID_FILENAME_RE.sub("_", base)
    base = base.strip().strip(".")
    if not base:
        base = default_base
    return base


def _create_tk_root(title: str, geometry: str | None = None) -> tuple[tk.Tk | tk.Toplevel, bool]:
    base = tk._default_root
    if base is not None:
        win = tk.Toplevel(base)
        win.title(title)
        if geometry:
            win.geometry(geometry)
        return win, False
    root = tk.Tk()
    root.title(title)
    if geometry:
        root.geometry(geometry)
    return root, True


def _set_window_icon(win: tk.Tk | tk.Toplevel) -> None:
    icon_path = _assets_icon_path()
    if not icon_path.exists():
        return
    try:
        photo = ImageTk.PhotoImage(Image.open(icon_path))
        win.iconphoto(True, photo)
        _window_icon_refs[id(win)] = photo
    except Exception:
        pass
    try:
        win.iconbitmap(str(icon_path))
    except Exception:
        pass


def _focus_existing_window(win: object | None) -> bool:
    if win is None:
        return False
    try:
        if hasattr(win, "winfo_exists") and not bool(win.winfo_exists()):  # type: ignore[union-attr]
            return False
        if hasattr(win, "deiconify"):
            win.deiconify()  # type: ignore[union-attr]
        if hasattr(win, "lift"):
            win.lift()  # type: ignore[union-attr]
        if hasattr(win, "focus_force"):
            win.focus_force()  # type: ignore[union-attr]
        return True
    except Exception:
        return False


def _tk_logo_label(parent: tk.Widget, size: int = 20, bg: str = _THEME_WHITE) -> tk.Label | None:
    icon_path = _assets_icon_path()
    if not icon_path.exists():
        return None
    try:
        img = Image.open(icon_path).resize((size, size))
        photo = ImageTk.PhotoImage(img)
        lbl = tk.Label(parent, image=photo, bg=bg)
        lbl.image = photo
        return lbl
    except Exception:
        return None


def prompt_save_path(
    default_base: str,
    parent: tk.Tk | tk.Toplevel | None = None,
    initial_dir: str | None = None,
) -> str | None:
    global _save_dialog_open
    if not _save_dialog_lock.acquire(blocking=False):
        return None
    try:
        if _save_dialog_open:
            return None
        _save_dialog_open = True

        initial_file = _sanitize_filename(default_base, default_base) + ".jpg"
        path = filedialog.asksaveasfilename(
            parent=parent,
            title="Save Capture",
            defaultextension=".jpg",
            initialfile=initial_file,
            initialdir=initial_dir,
            filetypes=[("JPEG Image", "*.jpg"), ("All Files", "*.*")],
        )
        return path or None
    finally:
        _save_dialog_open = False
        _save_dialog_lock.release()


def show_error(title: str, message: str) -> None:
    root, is_root = _create_tk_root(title)
    _set_window_icon(root)
    root.withdraw()
    try:
        messagebox.showerror(title, message, parent=root)
    finally:
        if is_root:
            root.destroy()


def show_info(title: str, message: str) -> None:
    root, is_root = _create_tk_root(title)
    _set_window_icon(root)
    root.withdraw()
    try:
        messagebox.showinfo(title, message, parent=root)
    finally:
        if is_root:
            root.destroy()


def show_about(
    app_name: str,
    director_name: str,
    director_email: str,
    developer_name: str,
    developer_email: str,
    support_contact: str,
) -> None:
    global _about_window
    if _focus_existing_window(_about_window):
        return

    info_text = (
        f"Owner / Director: {director_name} ({director_email})\n"
        f"Developer / Bug Contact: {developer_name} ({developer_email})\n"
        f"Support / Inquiry: {support_contact}"
    )

    if ctk is None:
        root, is_root = _create_tk_root(f"{app_name} About", geometry="520x190")
        _set_window_icon(root)
        root.resizable(False, False)
        root.configure(bg=_THEME_DARK)
        _about_window = root

        def _close_about() -> None:
            global _about_window
            if _about_window is root:
                _about_window = None
            try:
                root.destroy()
            except Exception:
                pass

        tk.Label(
            root,
            text=info_text,
            justify="left",
            anchor="w",
            bg=_THEME_DARK,
            fg=_THEME_TEXT_LIGHT,
            font=("Malgun Gothic", 11),
        ).pack(fill="x", padx=16, pady=(14, 6))

        tk.Button(
            root,
            text="Close",
            width=12,
            command=_close_about,
            bg=_THEME_DARK_PANEL,
            fg=_THEME_TEXT_LIGHT,
            activebackground=_THEME_DARK_PANEL_HOVER,
            activeforeground=_THEME_WHITE,
            relief="solid",
            borderwidth=1,
        ).pack(side="right", padx=14, pady=(0, 2))
        root.protocol("WM_DELETE_WINDOW", _close_about)

        root.mainloop()
        if is_root:
            try:
                root.destroy()
            except Exception:
                pass
        return

    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")

    win = ctk.CTk()
    win.title(f"{app_name} About")
    win.resizable(False, False)
    win.geometry("520x190")
    win.configure(fg_color=_THEME_DARK)
    _set_window_icon(win)
    _about_window = win

    def _close_about_ctk() -> None:
        global _about_window
        if _about_window is win:
            _about_window = None
        try:
            win.destroy()
        except Exception:
            pass

    frame = ctk.CTkFrame(win, corner_radius=0, fg_color=_THEME_DARK)
    frame.pack(fill="both", expand=True, padx=0, pady=0)

    ctk.CTkLabel(
        frame,
        text=info_text,
        justify="left",
        font=ctk.CTkFont(family="Malgun Gothic", size=13),
        text_color=_THEME_TEXT_LIGHT,
        fg_color=_THEME_DARK,
    ).pack(anchor="w", padx=16, pady=(14, 6))

    btn_row = ctk.CTkFrame(frame, fg_color="transparent")
    btn_row.pack(fill="x", padx=14, pady=(4, 2))
    ctk.CTkButton(
        btn_row,
        text="Close",
        width=120,
        fg_color=_THEME_DARK_PANEL,
        hover_color=_THEME_DARK_PANEL_HOVER,
        text_color=_THEME_TEXT_LIGHT,
        corner_radius=0,
        command=_close_about_ctk,
    ).pack(side="right")
    win.protocol("WM_DELETE_WINDOW", _close_about_ctk)

    win.mainloop()


def show_settings(
    cfg: AppConfig,
    on_save: Callable[[AppConfig], None],
    parent: tk.Tk | tk.Toplevel | None = None,
) -> None:
    global _settings_window
    if _focus_existing_window(_settings_window):
        return

    if ctk is None:
        if parent is None:
            root, _ = _create_tk_root("DMTSnapSync Settings", geometry="700x335")
        else:
            root = tk.Toplevel(parent)
            root.title("DMTSnapSync Settings")
            root.geometry("700x335")
        root.resizable(False, False)
        root.configure(bg=_THEME_DARK)
        _set_window_icon(root)
        _settings_window = root

        fields = [
            ("PC Alias", "pc_alias", cfg.pc_alias),
            ("Share Path", "share_path", cfg.share_path),
            ("JPEG Quality (1-100)", "quality", str(cfg.quality)),
            ("Max Image Size (KB, optional)", "max_image_size_kb", str(cfg.max_image_size_kb or "")),
            ("Hotkey (Full)", "hotkey_full", cfg.hotkey_full),
            ("Hotkey (Drag)", "hotkey_drag", cfg.hotkey_drag),
        ]

        entries: dict[str, tk.Entry] = {}
        for i, (label, key, initial) in enumerate(fields):
            tk.Label(
                root,
                text=label,
                anchor="w",
                width=20,
                bg=_THEME_DARK,
                fg=_THEME_TEXT_LIGHT,
            ).grid(row=i, column=0, padx=12, pady=7, sticky="w")
            ent = tk.Entry(root, width=45)
            ent.insert(0, initial)
            ent.grid(row=i, column=1, padx=10, pady=7, sticky="we")
            entries[key] = ent

            if key == "share_path":
                def _browse_path() -> None:
                    initial_dir = entries["share_path"].get().strip() or None
                    path = filedialog.askdirectory(initialdir=initial_dir)
                    if path:
                        entries["share_path"].delete(0, tk.END)
                        entries["share_path"].insert(0, path)

                tk.Button(
                    root,
                    text="Browse...",
                    width=10,
                    command=_browse_path,
                    bg=_THEME_DARK_PANEL,
                    fg=_THEME_TEXT_LIGHT,
                    activebackground=_THEME_DARK_PANEL_HOVER,
                    activeforeground=_THEME_WHITE,
                    relief="solid",
                    borderwidth=1,
                ).grid(row=i, column=2, padx=(0, 10), pady=6)

        def _save() -> None:
            global _settings_window
            try:
                q = int(entries["quality"].get().strip())
            except Exception:
                messagebox.showerror("Invalid setting", "Quality must be an integer (1-100).", parent=root)
                return
            if q < 1 or q > 100:
                messagebox.showerror("Invalid setting", "Quality must be between 1 and 100.", parent=root)
                return
            max_size_raw = entries["max_image_size_kb"].get().strip()
            max_size: int | None = None
            if max_size_raw:
                try:
                    max_size = int(max_size_raw)
                except Exception:
                    messagebox.showerror(
                        "Invalid setting",
                        "Max Image Size must be a positive integer or empty.",
                        parent=root,
                    )
                    return
                if max_size < 1:
                    messagebox.showerror(
                        "Invalid setting",
                        "Max Image Size must be a positive integer or empty.",
                        parent=root,
                    )
                    return

            new_cfg = replace(
                cfg,
                pc_alias=entries["pc_alias"].get(),
                share_path=entries["share_path"].get(),
                quality=q,
                max_image_size_kb=max_size,
                hotkey_full=entries["hotkey_full"].get(),
                hotkey_drag=entries["hotkey_drag"].get(),
            )
            on_save(new_cfg)
            _settings_window = None
            root.destroy()

        def _cancel() -> None:
            global _settings_window
            _settings_window = None
            root.destroy()

        btns = tk.Frame(root, bg=_THEME_DARK)
        btns.grid(row=len(fields), column=0, columnspan=3, pady=4)
        tk.Button(
            btns,
            text="Save",
            width=12,
            command=_save,
            bg="#7dd3fc",
            fg="#0c4a6e",
            activebackground="#38bdf8",
            activeforeground="#0c4a6e",
            relief="solid",
            borderwidth=1,
        ).pack(side="left", padx=8)
        tk.Button(
            btns,
            text="Cancel",
            width=12,
            command=_cancel,
            bg="#fecaca",
            fg="#7f1d1d",
            activebackground="#fca5a5",
            activeforeground="#7f1d1d",
            relief="solid",
            borderwidth=1,
        ).pack(side="left", padx=8)

        def _on_close() -> None:
            global _settings_window
            if _settings_window is root:
                _settings_window = None
            root.destroy()

        root.protocol("WM_DELETE_WINDOW", _on_close)
        if parent is None:
            root.mainloop()
        else:
            root.transient(parent)
            root.grab_set()
            root.wait_window()
        return

    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")

    if parent is None:
        win = ctk.CTk()
    else:
        win = ctk.CTkToplevel(parent)
    win.title("DMTSnapSync Settings")
    win.resizable(False, False)
    win.geometry("760x340")
    win.configure(fg_color=_THEME_DARK)
    _set_window_icon(win)
    _settings_window = win

    outer = ctk.CTkFrame(win, corner_radius=0, fg_color=_THEME_DARK)
    outer.pack(fill="both", expand=True, padx=0, pady=0)

    fields = [
        ("PC Alias", "pc_alias", cfg.pc_alias),
        ("Share Path", "share_path", cfg.share_path),
        ("JPEG Quality (1-100)", "quality", str(cfg.quality)),
        ("Max Image Size (KB, optional)", "max_image_size_kb", str(cfg.max_image_size_kb or "")),
        ("Hotkey (Full)", "hotkey_full", cfg.hotkey_full),
        ("Hotkey (Drag)", "hotkey_drag", cfg.hotkey_drag),
    ]

    entries: dict[str, ctk.CTkEntry] = {}
    for i, (label, key, initial) in enumerate(fields):
        ctk.CTkLabel(
            outer,
            text=label,
            text_color=_THEME_TEXT_LIGHT,
            fg_color=_THEME_DARK,
        ).grid(row=i, column=0, sticky="w", padx=14, pady=9)
        ent = ctk.CTkEntry(
            outer,
            width=390,
            fg_color="#0b1220",
            border_color=_THEME_DARK_PANEL_HOVER,
            text_color=_THEME_TEXT_LIGHT,
        )
        ent.insert(0, initial)
        ent.grid(row=i, column=1, sticky="w", padx=14, pady=9)
        entries[key] = ent

        if key == "share_path":
            def _browse_path_ctk() -> None:
                initial_dir = entries["share_path"].get().strip() or None
                path = filedialog.askdirectory(initialdir=initial_dir)
                if path:
                    entries["share_path"].delete(0, tk.END)
                    entries["share_path"].insert(0, path)

            ctk.CTkButton(
                outer,
                text="Browse...",
                width=110,
                fg_color=_THEME_DARK_PANEL,
                hover_color=_THEME_DARK_PANEL_HOVER,
                text_color=_THEME_TEXT_LIGHT,
                corner_radius=0,
                command=_browse_path_ctk,
            ).grid(row=i, column=2, sticky="w", padx=(0, 14), pady=8)

    err_var = tk.StringVar(value="")
    ctk.CTkLabel(
        outer,
        textvariable=err_var,
        text_color=_THEME_ERROR,
        fg_color=_THEME_DARK,
    ).grid(row=len(fields), column=0, columnspan=2, sticky="w", padx=14, pady=(2, 0))

    def _save() -> None:
        global _settings_window
        err_var.set("")
        try:
            q = int(entries["quality"].get().strip())
        except Exception:
            err_var.set("Quality must be an integer (1-100).")
            return
        if q < 1 or q > 100:
            err_var.set("Quality must be between 1 and 100.")
            return
        max_size_raw = entries["max_image_size_kb"].get().strip()
        max_size: int | None = None
        if max_size_raw:
            try:
                max_size = int(max_size_raw)
            except Exception:
                err_var.set("Max Image Size must be a positive integer or empty.")
                return
            if max_size < 1:
                err_var.set("Max Image Size must be a positive integer or empty.")
                return

        new_cfg = replace(
            cfg,
            pc_alias=entries["pc_alias"].get(),
            share_path=entries["share_path"].get(),
            quality=q,
            max_image_size_kb=max_size,
            hotkey_full=entries["hotkey_full"].get(),
            hotkey_drag=entries["hotkey_drag"].get(),
        )
        on_save(new_cfg)
        _settings_window = None
        win.destroy()

    def _cancel() -> None:
        global _settings_window
        _settings_window = None
        win.destroy()

    btn_row = ctk.CTkFrame(outer, fg_color=_THEME_DARK)
    btn_row.grid(row=len(fields) + 1, column=0, columnspan=2, sticky="e", padx=14, pady=(8, 3))
    ctk.CTkButton(
        btn_row,
        text="Cancel",
        width=120,
        fg_color="#fecaca",
        hover_color="#fca5a5",
        text_color="#7f1d1d",
        border_width=0,
        corner_radius=0,
        command=_cancel,
    ).pack(side="right", padx=(8, 0))
    ctk.CTkButton(
        btn_row,
        text="Save",
        width=120,
        fg_color="#7dd3fc",
        hover_color="#38bdf8",
        text_color="#0c4a6e",
        corner_radius=0,
        command=_save,
    ).pack(side="right")

    outer.grid_columnconfigure(0, weight=0)
    outer.grid_columnconfigure(1, weight=1)
    outer.grid_columnconfigure(2, weight=0)

    def _on_close() -> None:
        global _settings_window
        if _settings_window is win:
            _settings_window = None
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", _on_close)
    if parent is None:
        win.mainloop()
    else:
        win.transient(parent)
        win.grab_set()
        win.wait_window()


def close_settings_window() -> None:
    global _settings_window
    if _settings_window is None:
        return
    try:
        _settings_window.destroy()
    except Exception:
        pass
    _settings_window = None

