"""
Light and dark themes for the tkinter interface, built on ttk's "clam" engine so no extra packages are needed.

THEME in config.json is "system", "light" or "dark". Widgets read colors from P, which
apply_theme() fills with the active palette before the window is built.
"""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk
from types import SimpleNamespace

THEMES = ("system", "light", "dark")

LIGHT = {
    "bg": "#f3f4f6", "surface": "#ffffff", "border": "#e3e6ea", "text": "#1f2328", "muted": "#6b7280",
    "hover": "#f0f2f5", "selected": "#e3ecfd", "stripe": "#fafbfc", "focus": "#3b82f6", "focus_active": "#2f6fdb",
    "disabled": "#c9cdd3", "disabled_text": "#f5f6f8", "button_disabled_text": "#a0a6b0",
    "scrollbar": "#d5d9df", "scrollbar_active": "#bfc5cd",
    "added": "#1a7f37", "removed": "#c62828", "unplayable": "#b26a00", "playable": "#1565c0", "initial": "#666666",
    "spotify_tint": "#ecf8f0", "youtube_tint": "#fdf0ef",
}
DARK = {
    "bg": "#16181d", "surface": "#1f2228", "border": "#30343c", "text": "#e6e8eb", "muted": "#9aa1ab",
    "hover": "#2a2e36", "selected": "#263a5c", "stripe": "#23262d", "focus": "#4c8dff", "focus_active": "#3a78e6",
    "disabled": "#343841", "disabled_text": "#6b717b", "button_disabled_text": "#5f6570",
    "scrollbar": "#3a3f48", "scrollbar_active": "#4b515b",
    "added": "#3fb950", "removed": "#f85149", "unplayable": "#d29922", "playable": "#58a6ff", "initial": "#8b949e",
    "spotify_tint": "#1b2c22", "youtube_tint": "#30201f",
}

FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI Semibold", 10)

P = SimpleNamespace(**LIGHT, dark=False)


def system_prefers_dark() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
            return winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False


def is_dark(setting: str | None) -> bool:
    if setting == "dark":
        return True
    if setting == "light":
        return False
    return system_prefers_dark()


def dark_title_bar(window: tk.Misc) -> None:
    """Ask Windows 10/11 to draw the title bar of a window in dark mode."""
    if sys.platform != "win32" or not P.dark:
        return
    try:
        import ctypes
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        value = ctypes.c_int(1)
        for attribute in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE, older Windows 10 builds use 19
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(value),
                                                          ctypes.sizeof(value)) == 0:
                break
    except (AttributeError, OSError):
        pass


def _button_style(style, name, background, foreground, border, active, disabled, disabled_text):
    style.configure(name, background=background, foreground=foreground, bordercolor=border,
                    lightcolor=background, darkcolor=background, padding=(14, 6), focusthickness=0)
    states = [("disabled", disabled), ("pressed", active), ("active", active)]
    style.map(name, background=states, lightcolor=states, darkcolor=states,
              bordercolor=[("disabled", P.border)], foreground=[("disabled", disabled_text)])


def apply_theme(root: tk.Tk, setting: str | None, accents: dict[str, tuple[str, str]]) -> None:
    """Activate the palette and style all ttk widgets; accents maps a style prefix to (color, pressed color)."""
    P.__dict__.update(DARK if is_dark(setting) else LIGHT, dark=is_dark(setting))

    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        tkfont.nametofont(name).configure(family=FONT[0], size=FONT[1])
    root.configure(background=P.bg)
    root.option_add("*TCombobox*Listbox.background", P.surface)
    root.option_add("*TCombobox*Listbox.foreground", P.text)
    root.option_add("*TCombobox*Listbox.selectBackground", P.selected)
    root.option_add("*TCombobox*Listbox.selectForeground", P.text)
    root.option_add("*TCombobox*Listbox.font", FONT)

    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background=P.bg, foreground=P.text, bordercolor=P.border, lightcolor=P.bg,
                    darkcolor=P.bg, troughcolor=P.bg, selectbackground=P.selected, selectforeground=P.text,
                    font=FONT)
    style.configure("Card.TFrame", background=P.surface)
    style.configure("Card.TLabel", background=P.surface)
    style.configure("Muted.TLabel", foreground=P.muted)
    style.configure("CardMuted.TLabel", background=P.surface, foreground=P.muted)
    style.configure("Section.TLabel", background=P.surface, font=FONT_BOLD)
    style.configure("Title.TLabel", font=("Segoe UI Semibold", 15))

    _button_style(style, "TButton", P.surface, P.text, P.border, P.hover, P.bg, P.button_disabled_text)
    _button_style(style, "Accent.TButton", P.focus, "#ffffff", P.focus, P.focus_active, P.disabled,
                  P.disabled_text)
    for prefix, (color, active) in accents.items():
        _button_style(style, f"{prefix}.Accent.TButton", color, "#ffffff", color, active, P.disabled,
                      P.disabled_text)

    for widget in ("TEntry", "TCombobox"):
        style.configure(widget, fieldbackground=P.surface, background=P.surface, foreground=P.text,
                        bordercolor=P.border, lightcolor=P.surface, darkcolor=P.surface, arrowcolor=P.muted,
                        insertcolor=P.text, padding=5)
        style.map(widget, bordercolor=[("focus", P.focus)], lightcolor=[("focus", P.focus)],
                  fieldbackground=[("readonly", P.surface)], background=[("active", P.hover)],
                  foreground=[("readonly", P.text)],
                  selectbackground=[("readonly", P.surface)], selectforeground=[("readonly", P.text)])

    style.configure("TNotebook", background=P.bg, bordercolor=P.border, lightcolor=P.surface,
                    darkcolor=P.surface, tabmargins=(0, 0, 0, 0))
    style.configure("TNotebook.Tab", background=P.bg, foreground=P.muted, bordercolor=P.bg, lightcolor=P.bg,
                    darkcolor=P.bg, padding=(18, 7), font=FONT_BOLD)
    style.map("TNotebook.Tab",
              background=[("selected", P.surface), ("active", P.hover)],
              foreground=[("selected", P.text)],
              bordercolor=[("selected", P.border)],
              lightcolor=[("selected", P.surface), ("active", P.hover)],
              darkcolor=[("selected", P.surface), ("active", P.hover)],
              expand=[("selected", (0, 0, 0, 0))])

    style.configure("Treeview", background=P.surface, fieldbackground=P.surface, foreground=P.text,
                    bordercolor=P.border, lightcolor=P.surface, darkcolor=P.surface, rowheight=30)
    style.map("Treeview", background=[("selected", P.selected)], foreground=[("selected", P.text)])
    style.configure("Treeview.Heading", background=P.stripe, foreground=P.muted, bordercolor=P.border,
                    lightcolor=P.stripe, darkcolor=P.stripe, relief="flat", padding=(8, 6),
                    font=("Segoe UI Semibold", 9))
    style.map("Treeview.Heading", background=[("active", P.hover)], lightcolor=[("active", P.hover)],
              darkcolor=[("active", P.hover)])

    style.configure("Vertical.TScrollbar", background=P.scrollbar, troughcolor=P.surface, bordercolor=P.surface,
                    lightcolor=P.scrollbar, darkcolor=P.scrollbar, arrowcolor=P.muted, gripcount=0, arrowsize=12)
    style.map("Vertical.TScrollbar", background=[("active", P.scrollbar_active)],
              lightcolor=[("active", P.scrollbar_active)], darkcolor=[("active", P.scrollbar_active)])

    dark_title_bar(root)


def text_box(parent, height: int) -> tk.Text:
    return tk.Text(parent, height=height, wrap="word", font=FONT, background=P.surface, foreground=P.text,
                   insertbackground=P.text, relief="flat", highlightthickness=1, highlightbackground=P.border,
                   highlightcolor=P.border, padx=10, pady=8, state="disabled")
