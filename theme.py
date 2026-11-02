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
    "banner": "#fff6db", "banner_text": "#7a4d00", "nav": "#e6e8ec",
    # Chart marks; validated with the dataviz palette checks against this theme's surface
    "chart": "#1aa34a", "chart_hover": "#13843b", "grid": "#eceef1",
}
DARK = {
    "bg": "#16181d", "surface": "#1f2228", "border": "#30343c", "text": "#e6e8eb", "muted": "#9aa1ab",
    "hover": "#2a2e36", "selected": "#263a5c", "stripe": "#23262d", "focus": "#4c8dff", "focus_active": "#3a78e6",
    "disabled": "#343841", "disabled_text": "#6b717b", "button_disabled_text": "#5f6570",
    "scrollbar": "#3a3f48", "scrollbar_active": "#4b515b",
    "added": "#3fb950", "removed": "#f85149", "unplayable": "#d29922", "playable": "#58a6ff", "initial": "#8b949e",
    "spotify_tint": "#1b2c22", "youtube_tint": "#30201f",
    "banner": "#3a2f15", "banner_text": "#e3b341", "nav": "#262a31",
    "chart": "#2ea043", "chart_hover": "#3fb950", "grid": "#2a2e35",
}

# One type scale for the whole interface (sizes in points, which follow the screen scale)
TYPE = {
    "caption": ("Segoe UI Semibold", 9),   # small capitals over a title, table headings
    "small": ("Segoe UI", 9),              # chart labels, changes since the previous period
    "body": ("Segoe UI", 10),
    "body_bold": ("Segoe UI Semibold", 10),
    "lead": ("Segoe UI", 12),              # the line under a title
    "heading": ("Segoe UI Semibold", 12),  # section titles
    "title": ("Segoe UI Semibold", 15),    # the window title
    "display": ("Segoe UI Semibold", 18),  # the name on a top card, the numbers in the tiles
    "name": ("Segoe UI Semibold", 24),     # names in the monthly summary
    "big": ("Segoe UI Semibold", 44),      # the large numbers of the monthly summary
}
FONT = TYPE["body"]
FONT_BOLD = TYPE["body_bold"]
# Spacing between and inside parts of a page uses only these steps (design pixels, through px());
# controls such as buttons keep their own inner padding
SPACING = (4, 8, 12, 16, 24)
# Windows' own icon fonts, newest first; ICON_GLYPHS are their code points, TEXT_GLYPHS stand in without them
ICON_FONTS = ("Segoe Fluent Icons", "Segoe MDL2 Assets")
ICON_GLYPHS = {"back": "\ue76b", "forward": "\ue76c", "close": "\ue711",
               # Section headings of the statistics
               "tracks": "\ue8d6", "artists": "\ue77b", "calendar": "\ue787", "clock": "\ue823",
               "star": "\ue734", "tag": "\ue8ec", "history": "\ue81c", "disc": "\ue93c"}
TEXT_GLYPHS = {"back": "‹", "forward": "›", "close": "✕"}
_icon_font: str | None = None

P = SimpleNamespace(**LIGHT, dark=False)

# The layout is designed for a 1920x1080 screen; on other screens fonts, pictures and spacing are
# multiplied by SCALE so the window covers the same part of the screen and looks the same
DESIGN_SCREEN = (1920, 1080)
MIN_SCALE, MAX_SCALE = 0.8, 3.0
SCALE = 1.0


def make_dpi_aware() -> None:
    """Draw at the real screen resolution, so Windows does not stretch (and blur) the window.

    Call before the first Tk window is created."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # PROCESS_SYSTEM_DPI_AWARE
    except (AttributeError, OSError):
        pass


def set_scale(root: tk.Tk) -> None:
    """Pick SCALE from the screen size; font sizes in points follow it through Tk's own scaling."""
    global SCALE
    width, height = root.winfo_screenwidth(), root.winfo_screenheight()
    SCALE = min(MAX_SCALE, max(MIN_SCALE, min(width / DESIGN_SCREEN[0], height / DESIGN_SCREEN[1])))
    # Tk's scaling is pixels per point; 96 / 72 is a 100% (96 DPI) screen
    root.tk.call("tk", "scaling", SCALE * 96 / 72)


def px(value: float) -> int:
    """A size in pixels of the 1920x1080 design, on this screen."""
    return round(value * SCALE)


def place_window(window: tk.Misc, width: int, height: int) -> None:
    """Size a window in design pixels and center it on the screen."""
    width, height = px(width), px(height)
    left = max(0, (window.winfo_screenwidth() - width) // 2)
    # A little above the middle, leaving room for the taskbar
    top = max(0, (window.winfo_screenheight() - height) // 2 - px(20))
    window.geometry(f"{width}x{height}+{left}+{top}")


def mix(color: str, other: str, amount: float) -> str:
    """The color amount of the way from color to other (both #rrggbb)."""
    a = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(other[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * amount):02x}" for x, y in zip(a, b))


def _luminance(color: str) -> float:
    channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(color: str, other: str) -> float:
    """The WCAG contrast ratio of two colors, from 1 to 21."""
    light, dark = sorted((_luminance(color), _luminance(other)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


# Contrast small text needs to stay readable (WCAG AA)
READABLE = 4.5


def readable(color: str, backgrounds: list[str], target: float = READABLE) -> str:
    """color, moved toward the text color just as far as it takes to read well on every background."""
    for step in range(11):
        candidate = mix(color, P.text, step / 10)
        if all(contrast(candidate, background) >= target for background in backgrounds):
            return candidate
    return P.text


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


def icon(name: str) -> str:
    """The character of an icon in icon_font(); "" for an icon without a stand-in when that font is missing."""
    return (ICON_GLYPHS if _icon_font else TEXT_GLYPHS).get(name, "")


def icon_font() -> str | None:
    return _icon_font


def _button_style(style, name, background, foreground, border, active, disabled, disabled_text):
    style.configure(name, background=background, foreground=foreground, bordercolor=border,
                    lightcolor=background, darkcolor=background, padding=(px(14), px(6)), focusthickness=0)
    states = [("disabled", disabled), ("pressed", active), ("active", active)]
    style.map(name, background=states, lightcolor=states, darkcolor=states,
              bordercolor=[("disabled", P.border)], foreground=[("disabled", disabled_text)])


def apply_theme(root: tk.Tk, setting: str | None, accents: dict[str, tuple[str, str]]) -> None:
    """Activate the palette and style all ttk widgets; accents maps a style prefix to (color, pressed color)."""
    P.__dict__.update(DARK if is_dark(setting) else LIGHT, dark=is_dark(setting))

    set_scale(root)
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
    style.configure("Title.TLabel", font=TYPE["title"])
    style.configure("Tile.TFrame", background=P.surface, bordercolor=P.border, relief="solid", borderwidth=1)
    style.configure("TileValue.TLabel", background=P.surface, font=TYPE["display"])
    style.configure("Period.TLabel", background=P.surface, font=TYPE["heading"])
    style.configure("Caption.TLabel", background=P.surface, foreground=P.muted, font=TYPE["caption"])
    style.configure("Banner.TFrame", background=P.banner)
    style.configure("Banner.TLabel", background=P.banner, foreground=P.banner_text)
    style.configure("Nav.TFrame", background=P.nav)
    style.configure("Card.TCheckbutton", background=P.surface, foreground=P.text, indicatorbackground=P.surface,
                    indicatorforeground=P.text, upperbordercolor=P.border, lowerbordercolor=P.border,
                    focusthickness=0, padding=(0, px(4)))
    style.map("Card.TCheckbutton", background=[("active", P.surface)],
              indicatorbackground=[("selected", P.focus), ("active", P.hover)],
              indicatorforeground=[("selected", "#ffffff")])

    _button_style(style, "TButton", P.surface, P.text, P.border, P.hover, P.bg, P.button_disabled_text)
    _button_style(style, "Accent.TButton", P.focus, "#ffffff", P.focus, P.focus_active, P.disabled,
                  P.disabled_text)
    # Section switcher: the selected section looks like a raised tab on a recessed track
    for name, background, foreground in (("Nav.TButton", P.nav, P.muted),
                                         ("NavSelected.TButton", P.surface, P.text)):
        style.configure(name, background=background, foreground=foreground, bordercolor=background,
                        lightcolor=background, darkcolor=background, padding=(px(16), px(5)), focusthickness=0,
                        font=FONT_BOLD)
        style.map(name, background=[("active", P.surface)], lightcolor=[("active", P.surface)],
                  darkcolor=[("active", P.surface)], foreground=[("active", P.text)])
    # Square buttons with an icon: back, forward and close
    global _icon_font
    families = set(tkfont.families(root))
    _icon_font = next((family for family in ICON_FONTS if family in families), None)
    _button_style(style, "Icon.TButton", P.surface, P.text, P.border, P.hover, P.bg, P.button_disabled_text)
    style.configure("Icon.TButton", font=(_icon_font, 11) if _icon_font else ("Segoe UI Semibold", 14),
                    padding=(px(12), px(7)) if _icon_font else (px(10), px(1)), width=0)
    style.map("Icon.TButton", bordercolor=[("disabled", P.border), ("active", P.muted)],
              foreground=[("disabled", P.button_disabled_text), ("active", P.text)])
    for prefix, (color, active) in accents.items():
        _button_style(style, f"{prefix}.Accent.TButton", color, "#ffffff", color, active, P.disabled,
                      P.disabled_text)

    for widget in ("TEntry", "TCombobox"):
        style.configure(widget, fieldbackground=P.surface, background=P.surface, foreground=P.text,
                        bordercolor=P.border, lightcolor=P.surface, darkcolor=P.surface, arrowcolor=P.muted,
                        insertcolor=P.text, padding=px(5))
        style.map(widget, bordercolor=[("focus", P.focus)], lightcolor=[("focus", P.focus)],
                  fieldbackground=[("readonly", P.surface)], background=[("active", P.hover)],
                  foreground=[("readonly", P.text)],
                  selectbackground=[("readonly", P.surface)], selectforeground=[("readonly", P.text)])

    style.configure("TNotebook", background=P.bg, bordercolor=P.border, lightcolor=P.surface,
                    darkcolor=P.surface, tabmargins=(0, 0, 0, 0))
    style.configure("TNotebook.Tab", background=P.bg, foreground=P.muted, bordercolor=P.bg, lightcolor=P.bg,
                    darkcolor=P.bg, padding=(px(18), px(7)), font=FONT_BOLD)
    style.map("TNotebook.Tab",
              background=[("selected", P.surface), ("active", P.hover)],
              foreground=[("selected", P.text)],
              bordercolor=[("selected", P.border)],
              lightcolor=[("selected", P.surface), ("active", P.hover)],
              darkcolor=[("selected", P.surface), ("active", P.hover)],
              expand=[("selected", (0, 0, 0, 0))])

    style.configure("Treeview", background=P.surface, fieldbackground=P.surface, foreground=P.text,
                    bordercolor=P.border, lightcolor=P.surface, darkcolor=P.surface, rowheight=px(30))
    style.map("Treeview", background=[("selected", P.selected)], foreground=[("selected", P.text)])
    style.configure("Treeview.Heading", background=P.stripe, foreground=P.muted, bordercolor=P.border,
                    lightcolor=P.stripe, darkcolor=P.stripe, relief="flat", padding=(px(8), px(6)),
                    font=TYPE["caption"])
    style.map("Treeview.Heading", background=[("active", P.hover)], lightcolor=[("active", P.hover)],
              darkcolor=[("active", P.hover)])

    style.configure("Vertical.TScrollbar", background=P.scrollbar, troughcolor=P.surface, bordercolor=P.surface,
                    lightcolor=P.scrollbar, darkcolor=P.scrollbar, arrowcolor=P.muted, gripcount=0, arrowsize=px(12))
    style.map("Vertical.TScrollbar", background=[("active", P.scrollbar_active)],
              lightcolor=[("active", P.scrollbar_active)], darkcolor=[("active", P.scrollbar_active)])

    dark_title_bar(root)


def text_box(parent, height: int) -> tk.Text:
    return tk.Text(parent, height=height, wrap="word", font=FONT, background=P.surface, foreground=P.text,
                   insertbackground=P.text, relief="flat", highlightthickness=1, highlightbackground=P.border,
                   highlightcolor=P.border, padx=px(10), pady=px(8), state="disabled")
