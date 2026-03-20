from __future__ import annotations

from dataclasses import replace
import re
import threading
from typing import Callable

from ..config import AppConfig

try:
    import customtkinter as ctk
except Exception:  # pragma: no cover
    ctk = None  # type: ignore[assignment]

import tkinter as tk
from tkinter import filedialog, messagebox

_save_dialog_lock = threading.Lock()
_save_dialog_open = False


_INVALID_FILENAME_CHARS = r'<>:"/\\|?*'
_INVALID_FILENAME_RE = re.compile(f"[{re.escape(_INVALID_FILENAME_CHARS)}]")


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
    root.withdraw()
    try:
        messagebox.showerror(title, message)
    finally:
        if is_root:
            root.destroy()


def show_info(title: str, message: str) -> None:
    root, is_root = _create_tk_root(title)
    root.withdraw()
    try:
        messagebox.showinfo(title, message)
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
    if ctk is None:
        msg = (
            f"{app_name}\n\n"
            f"Director: {director_name} ({director_email})\n"
            f"Developer: {developer_name} ({developer_email})\n"
            f"Support/Inquiry: {support_contact}\n"
        )
        show_info("About", msg)
        return

    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")

    win = ctk.CTk()
    win.title("About")
    win.resizable(False, False)
    win.geometry("420x220")

    frame = ctk.CTkFrame(win, corner_radius=12)
    frame.pack(fill="both", expand=True, padx=16, pady=16)

    ctk.CTkLabel(frame, text=app_name, font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w", padx=14, pady=(14, 6))

    info = (
        f"Director: {director_name} ({director_email})\n"
        f"Developer: {developer_name} ({developer_email})\n"
        f"Support/Inquiry: {support_contact}"
    )
    ctk.CTkLabel(frame, text=info, justify="left").pack(anchor="w", padx=14, pady=(0, 10))

    btn_row = ctk.CTkFrame(frame, fg_color="transparent")
    btn_row.pack(fill="x", padx=14, pady=(8, 12))
    ctk.CTkButton(btn_row, text="Close", width=120, command=win.destroy).pack(side="right")

    win.mainloop()


def show_settings(
    cfg: AppConfig,
    on_save: Callable[[AppConfig], None],
    parent: tk.Tk | tk.Toplevel | None = None,
) -> None:
    if ctk is None:
        if parent is None:
            root, is_root = _create_tk_root("DMTSnapSync Settings", geometry="640x380")
        else:
            root, is_root = tk.Toplevel(parent), False
            root.title("DMTSnapSync Settings")
            root.geometry("640x380")
        root.resizable(False, False)

        fields = [
            ("PC Alias", "pc_alias", cfg.pc_alias),
            ("Share Path", "share_path", cfg.share_path),
            ("JPEG Quality (1-100)", "quality", str(cfg.quality)),
            ("Hotkey (Full)", "hotkey_full", cfg.hotkey_full),
            ("Hotkey (Drag)", "hotkey_drag", cfg.hotkey_drag),
        ]

        entries: dict[str, tk.Entry] = {}

        for row, (label, key, initial) in enumerate(fields):
            tk.Label(root, text=label, anchor="w", width=18).grid(row=row, column=0, padx=10, pady=6, sticky="w")
            ent = tk.Entry(root, width=45)
            ent.insert(0, initial)
            ent.grid(row=row, column=1, padx=10, pady=6)
            entries[key] = ent

            if key == "share_path":
                def _browse_path() -> None:
                    initial_dir = entries["share_path"].get().strip() or None
                    path = filedialog.askdirectory(initialdir=initial_dir)
                    if path:
                        entries["share_path"].delete(0, tk.END)
                        entries["share_path"].insert(0, path)

                tk.Button(root, text="Browse...", width=10, command=_browse_path).grid(
                    row=row, column=2, padx=(0, 10), pady=6
                )

        def _save() -> None:
            try:
                q = int(entries["quality"].get().strip())
            except Exception:
                messagebox.showerror("Invalid setting", "Quality must be an integer (1-100).")
                return
            if q < 1 or q > 100:
                messagebox.showerror("Invalid setting", "Quality must be between 1 and 100.")
                return

            new_cfg = replace(
                cfg,
                pc_alias=entries["pc_alias"].get(),
                share_path=entries["share_path"].get(),
                quality=q,
                hotkey_full=entries["hotkey_full"].get(),
                hotkey_drag=entries["hotkey_drag"].get(),
            )
            on_save(new_cfg)
            root.destroy()

        btns = tk.Frame(root)
        btns.grid(row=len(fields), column=0, columnspan=2, pady=10)
        tk.Button(btns, text="Save", width=12, command=_save).pack(side="left", padx=8)
        tk.Button(btns, text="Cancel", width=12, command=root.destroy).pack(side="left", padx=8)

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
    win.geometry("720x440")

    outer = ctk.CTkFrame(win, corner_radius=14)
    outer.pack(fill="both", expand=True, padx=16, pady=16)

    ctk.CTkLabel(outer, text="Settings", font=ctk.CTkFont(size=18, weight="bold")).grid(
        row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(14, 10)
    )

    fields = [
        ("PC Alias", "pc_alias", cfg.pc_alias),
        ("Share Path", "share_path", cfg.share_path),
        ("JPEG Quality (1-100)", "quality", str(cfg.quality)),
        ("Hotkey (Full)", "hotkey_full", cfg.hotkey_full),
        ("Hotkey (Drag)", "hotkey_drag", cfg.hotkey_drag),
    ]

    entries: dict[str, ctk.CTkEntry] = {}

    for i, (label, key, initial) in enumerate(fields, start=1):
        ctk.CTkLabel(outer, text=label).grid(row=i, column=0, sticky="w", padx=14, pady=8)
        ent = ctk.CTkEntry(outer, width=360)
        ent.insert(0, initial)
        ent.grid(row=i, column=1, sticky="w", padx=14, pady=8)
        entries[key] = ent

        if key == "share_path":
            def _browse_path_ctk() -> None:
                initial_dir = entries["share_path"].get().strip() or None
                path = filedialog.askdirectory(initialdir=initial_dir)
                if path:
                    entries["share_path"].delete(0, tk.END)
                    entries["share_path"].insert(0, path)

            ctk.CTkButton(outer, text="Browse...", width=110, command=_browse_path_ctk).grid(
                row=i, column=2, sticky="w", padx=(0, 14), pady=8
            )

    err_var = tk.StringVar(value="")
    err_lbl = ctk.CTkLabel(outer, textvariable=err_var, text_color="#ef4444")
    err_lbl.grid(row=len(fields) + 1, column=0, columnspan=2, sticky="w", padx=14, pady=(2, 0))

    def _save() -> None:
        err_var.set("")
        try:
            q = int(entries["quality"].get().strip())
        except Exception:
            err_var.set("Quality must be an integer (1-100).")
            return
        if q < 1 or q > 100:
            err_var.set("Quality must be between 1 and 100.")
            return

        new_cfg = replace(
            cfg,
            pc_alias=entries["pc_alias"].get(),
            share_path=entries["share_path"].get(),
            quality=q,
            hotkey_full=entries["hotkey_full"].get(),
            hotkey_drag=entries["hotkey_drag"].get(),
        )
        on_save(new_cfg)
        win.destroy()

    btn_row = ctk.CTkFrame(outer, fg_color="transparent")
    btn_row.grid(row=len(fields) + 2, column=0, columnspan=2, sticky="e", padx=14, pady=(14, 14))
    ctk.CTkButton(
        btn_row,
        text="Cancel",
        width=120,
        fg_color="#fecaca",
        hover_color="#fca5a5",
        text_color="#7f1d1d",
        border_width=0,
        command=win.destroy,
    ).pack(side="right", padx=(8, 0))
    ctk.CTkButton(
        btn_row,
        text="Save",
        width=120,
        fg_color="#7dd3fc",
        hover_color="#38bdf8",
        text_color="#0c4a6e",
        command=_save,
    ).pack(side="right")

    outer.grid_columnconfigure(0, weight=0)
    outer.grid_columnconfigure(1, weight=1)
    outer.grid_columnconfigure(2, weight=0)

    if parent is None:
        win.mainloop()
    else:
        win.transient(parent)
        win.grab_set()
        win.wait_window()

