#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Shared helpers for the Mod Loader """

from __future__ import annotations

import io, os, sys, math, subprocess, time, weakref, threading, re
from pathlib import Path
from tkinter import messagebox
from typing import Optional, Tuple, Any, Callable, Union
import tkinter as tk
import tkinter.font as tkfont
import tkinter.ttk as ttk
from tkinter import ttk
from weakref import WeakSet
import ctypes as ct
from ctypes import wintypes
from PIL import Image, ImageTk, ImageFilter
import ModLoader

FOLDER_NAME = ModLoader.FOLDER_NAME
HERE = Path(__file__).resolve().parent

ICON_SIZE = 20
ICON_DISABLE_SUFFIX = "_disable"
ICON_INACTIVE_SUFFIX = "_inactive"


# ---------------- Theme ----------------


FONTS = {
    "mono": ("Consolas", 11),
    "base": ("Helvetica", 10),
    "base_bold": ("Helvetica", 10, "bold"),
    "base_mini": ("Helvetica", 9),
    "title_h1": ("Helvetica", 16, "bold"),
    "title_h2": ("Helvetica", 13, "bold"),
    "title_h3": ("Helvetica", 11, "bold"),
}

COLOR_PALETTE = {
    
    # Base areas
    "main_bg":        "#071023",   # main app bg
    "panel":          "#071423",   # default panel bg
    "panel_hover":    "#0e2236",
    "panel_active":   "#14314d",   # panel selected/active

    # Cards (on mod list)
    "card_bg":        "#0a1828",
    "card_bg_hover":  "#0e2236",
    "card_bg_active": "#14314d",
    "card_bg_disabled":"#081421",

    # Badges
    "badge_bg":       "#0f2336",
    "badge_border":   "#1f4a72",
    "badge_fg":       "#cfe8ff",

    # Buttons
    "button_bg":        "#0a1828",
    "button_bg_hover":  "#183a5c",
    "button_bg_active": "#1F4F7C",
    "button_bg_disabled":"#081421",    
    "button_border":   "#2b669c",
    "special_fg":       "#001522",
    
    # Scrollbar
    "scrollbar_bg":        "#0e2236",
    "scrollbar_bg_hover":  "#153350",
    "scrollbar_thumb":   "#1f4a72",
    "scrollbar_thumb_hover":   "#2b669c",
    
    
    # Text & meta
    "text":           "#ffffff",
    "desc":           "#cfe8ff",
    "meta":           "#9fb7d9",
    "text_disabled":  "#7f8da3",
    "desc_disabled":  "#6f7b90",

    # Dividers & borders
    "divider":        "#12344f",
    "border":         "#1f3a5c",   # sheet border default

    # Text input fields
    "input_bg":       "#0b1722",
    "input_bd":       "#18334d",

    # Tooltips
    "tooltip_bg":     "#0b1b2a",

    # Sheet
    "sheet_panel":        "#0e243b",
    "sheet_panel_hover":  "#163455",
    "sheet_panel_active": "#1a355a",
    "sheet_text":         "#eaf3ff",
    "sheet_sub":          "#9fb7d9",
    "sheet_divider":      "#183456",    
    
    # Accents
    "accent_green":       "#39d353",
    "accent_red":         "#ff6b6b",    
    "accent_yellow":      "#ffd166",
    "accent_blue":        "#72c0ff",
    "accent_lightblue":   "#9cd2ff",
    "accent_darkblue":    "#2b84d6",
    
    # Extras    
    "pill_bg":            "#0b1a2a",
    "pill_bg_2":          "#0f243a",
}

# Back-compat single-name constants
CARD_BG           = COLOR_PALETTE["card_bg"]
CARD_BG_HOVER     = COLOR_PALETTE["card_bg_hover"]
CARD_BG_ACTIVE    = COLOR_PALETTE["card_bg_active"]
CARD_BG_DISABLED  = COLOR_PALETTE["card_bg_disabled"]
BADGE_BG          = COLOR_PALETTE["badge_bg"]
BADGE_BORDER      = COLOR_PALETTE["badge_border"]
BADGE_FG          = COLOR_PALETTE["badge_fg"]
DIVIDER           = COLOR_PALETTE["divider"]
DESC_FG           = COLOR_PALETTE["desc"]
TEXT_FG           = COLOR_PALETTE["text"]
META_FG           = COLOR_PALETTE["meta"]
META_FG_DISABLED  = COLOR_PALETTE["desc_disabled"]
TOOLTIP_BG        = COLOR_PALETTE["tooltip_bg"]
INPUT_BG          = COLOR_PALETTE["input_bg"]
INPUT_BORDER      = COLOR_PALETTE["input_bd"]
COLOR             = COLOR_PALETTE

# amount: 0..1 (0 = unchanged, 0.12 = slightly darker)
def _darken_hex(hex_color: str, amount: float = 0.12) -> str:
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return hex_color
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    r = max(0, int(r * (1.0 - amount)))
    g = max(0, int(g * (1.0 - amount)))
    b = max(0, int(b * (1.0 - amount)))
    return f"#{r:02x}{g:02x}{b:02x}"



# Hide the console window on Windows when running the Tk app (we don't like sad black windows, do we?)
def hide_console_on_windows():
    if sys.platform.startswith("win"):
        try:
            import ctypes
            wh = ctypes.windll.kernel32.GetConsoleWindow()
            if wh:
                ctypes.windll.user32.ShowWindow(wh, 0)  # SW_HIDE
        except Exception:
            pass




# ---------------- Titlebar ----------------

class Titlebar:
    _APPLIED: dict[int, tuple[str, str] | str] = {}
    _LAST_APPLY: dict[int, float] = {}
    _WIN_BUILD: int | None = None
    _HAS_COLOR: bool | None = None
    _APPID_SET: bool = False
    _NEEDS_REAPPLY: set[int] = set()

    # Return candidates: [self_hwnd, owner, parent] – no duplicates/zeros.
    @staticmethod
    def _candidate_hwnds(widget: tk.Misc):
        top = widget.winfo_toplevel()
        top.update_idletasks()
        self_hwnd = top.winfo_id()

        user32 = ct.windll.user32
        GW_OWNER = 4
        try:
            owner = user32.GetWindow(wintypes.HWND(self_hwnd), GW_OWNER)
        except Exception:
            owner = 0
        try:
            parent = user32.GetParent(wintypes.HWND(self_hwnd))
        except Exception:
            parent = 0

        seen = set()
        out = []
        for h in (self_hwnd, owner, parent):
            h = int(h) if h else 0
            if h and h not in seen:
                seen.add(h)
                out.append(h)
        return out

    # Set AppUserModelID BEFORE creating windows (fixes taskbar icon grouping).
    @staticmethod
    def ensure_appid(app_id: str = "ModLoaderGUI"):
        if Titlebar._APPID_SET:
            return
        if sys.platform.startswith("win"):
            try:
                ct.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
            except Exception:
                pass
        Titlebar._APPID_SET = True

    @staticmethod
    def _windows_build() -> int:
        if Titlebar._WIN_BUILD is not None:
            return Titlebar._WIN_BUILD

        class RTL_OSVERSIONINFOEXW(ct.Structure):
            _fields_ = [
                ("dwOSVersionInfoSize", wintypes.DWORD),
                ("dwMajorVersion", wintypes.DWORD),
                ("dwMinorVersion", wintypes.DWORD),
                ("dwBuildNumber", wintypes.DWORD),
                ("dwPlatformId", wintypes.DWORD),
                ("szCSDVersion", wintypes.WCHAR * 128),
            ]

        info = RTL_OSVERSIONINFOEXW()
        info.dwOSVersionInfoSize = ct.sizeof(info)
        build = 0
        try:
            ct.windll.ntdll.RtlGetVersion(ct.byref(info))
            build = int(info.dwBuildNumber or 0)
        except Exception:
            build = 0

        Titlebar._WIN_BUILD = build
        Titlebar._HAS_COLOR = (build >= 22621)  # Win11 22H2+
        return build

    @staticmethod
    def _hex_to_bgr(hx: str) -> int:
        hx = hx.lstrip("#")
        r, g, b = int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)
        return (b << 16) | (g << 8) | r  # COLORREF

    @staticmethod
    def _dlls():
        try:
            user32 = ct.WinDLL("user32", use_last_error=True)
        except Exception:
            user32 = ct.windll.user32
        try:
            dwmapi = ct.WinDLL("dwmapi", use_last_error=True)
        except Exception:
            dwmapi = ct.windll.dwmapi

        try:
            user32.IsWindow.restype = wintypes.BOOL
            user32.IsWindow.argtypes = [wintypes.HWND]
            user32.IsWindowVisible.restype = wintypes.BOOL
            user32.IsWindowVisible.argtypes = [wintypes.HWND]
            user32.GetParent.restype = wintypes.HWND
            user32.GetParent.argtypes = [wintypes.HWND]
            user32.SetWindowPos.restype = wintypes.BOOL
            user32.SetWindowPos.argtypes = [
                wintypes.HWND, wintypes.HWND,
                ct.c_int, ct.c_int, ct.c_int, ct.c_int, ct.c_uint,
            ]
            dwmapi.DwmSetWindowAttribute.restype = ct.c_long  # HRESULT
            dwmapi.DwmSetWindowAttribute.argtypes = [
                wintypes.HWND, ct.c_uint, ct.c_void_p, ct.c_uint
            ]
        except Exception:
            pass

        return user32, dwmapi

    # True only when: not finalizing, in main thread, widget (if given) still exists.
    @staticmethod
    def _safe_to_call_native(widget: tk.Misc | None = None) -> bool:
        try:
            if sys.is_finalizing():
                return False
        except Exception:
            pass

        if threading.current_thread() is not threading.main_thread():
            return False

        if widget is not None:
            try:
                if not widget.winfo_exists():
                    return False
            except Exception:
                return False

        return True

    # Enable dark caption buttons/background when possible.
    @staticmethod
    def _force_dark(hwnd: int) -> None:
        if not Titlebar._safe_to_call_native():
            return
        try:
            user32, dwm = Titlebar._dlls()

            if not user32.IsWindow(wintypes.HWND(hwnd)):
                return

            def _try(attr: int, val: int) -> bool:
                try:
                    v = ct.c_int(val)
                    hr = dwm.DwmSetWindowAttribute(
                        wintypes.HWND(hwnd),
                        ct.c_uint(attr),
                        ct.byref(v),
                        ct.sizeof(v),
                    )
                    return hr == 0
                except Exception:
                    return False

            ok = _try(20, 2) or _try(20, 1) or _try(19, 2) or _try(19, 1)

            SWP_NOSIZE = 0x0001
            SWP_NOMOVE = 0x0002
            SWP_NOZORDER = 0x0004
            SWP_FRAMECHANGED = 0x0020
            user32.SetWindowPos(
                wintypes.HWND(hwnd),
                0, 0, 0, 0, 0,
                SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_FRAMECHANGED,
            )
        except Exception:
            pass

    # StackOverflow-style fallback: immersive dark mode flag only.
    @staticmethod
    def _dark_title_bar_SO(widget: tk.Misc) -> bool:
        if not Titlebar._safe_to_call_native(widget):
            return False
        try:
            user32, dwm = Titlebar._dlls()
            widget.update_idletasks()
            hwnd_self = widget.winfo_id()
            parent = user32.GetParent(wintypes.HWND(hwnd_self))
            hwnd = parent if parent else hwnd_self

            if not user32.IsWindow(wintypes.HWND(hwnd)):
                return False

            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            val = ct.c_int(2)
            hr = dwm.DwmSetWindowAttribute(
                wintypes.HWND(hwnd),
                ct.c_uint(DWMWA_USE_IMMERSIVE_DARK_MODE),
                ct.byref(val),
                ct.sizeof(val),
            )

            SWP_NOSIZE = 0x0001
            SWP_NOMOVE = 0x0002
            SWP_NOZORDER = 0x0004
            SWP_FRAMECHANGED = 0x0020
            user32.SetWindowPos(
                wintypes.HWND(hwnd),
                0, 0, 0, 0, 0,
                SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_FRAMECHANGED,
            )
            return (hr == 0)
        except Exception:
            return False

    # Set window + taskbar icon once per toplevel.
    @staticmethod
    def set_icon(widget: tk.Misc):
        try:
            toplevel = widget.winfo_toplevel()
            toplevel.update_idletasks()
            if getattr(toplevel, "_icon_set", False):
                return

            app_dir = Path(__file__).resolve().parent
            icons_dir = app_dir / "assets" / "icons"

            if sys.platform.startswith("win"):
                ico = icons_dir / "icon.ico"
                if ico.exists():
                    try:
                        toplevel.iconbitmap(str(ico))
                    except Exception:
                        pass
            else:
                png = icons_dir / "iconPNG.png"
                if png.exists():
                    try:
                        toplevel.iconphoto(True, tk.PhotoImage(file=str(png)))
                    except Exception:
                        pass

            toplevel._icon_set = True
        except Exception:
            pass

    @staticmethod
    def set_color(widget: tk.Misc,
                  caption_hex: str = "#0e1b29",
                  text_hex: str = "#e6f1ff") -> bool:
        if not Titlebar._safe_to_call_native(widget):
            return False
        if not sys.platform.startswith("win"):
            return False

        Titlebar._windows_build()  # sets _HAS_COLOR
        try:
            hwnds = Titlebar._candidate_hwnds(widget)
        except Exception:
            return False
        if not hwnds:
            return False

        now = time.time()
        first = hwnds[0]
        last = Titlebar._LAST_APPLY.get(first, 0.0)
        if now - last < 0.20:
            return Titlebar._APPLIED.get(first) == (caption_hex, text_hex)

        user32, dwm = Titlebar._dlls()

        def _apply_to(hwnd: int) -> bool:
            if hwnd not in Titlebar._APPLIED or Titlebar._APPLIED.get(hwnd) == "dark":
                Titlebar._force_dark(hwnd)

            if not Titlebar._HAS_COLOR:
                return False

            try:
                if not user32.IsWindow(wintypes.HWND(hwnd)):
                    return False

                DWMWA_CAPTION_COLOR = 35
                DWMWA_TEXT_COLOR = 36
                cap = wintypes.DWORD(Titlebar._hex_to_bgr(caption_hex))
                txt = wintypes.DWORD(Titlebar._hex_to_bgr(text_hex))
                hr1 = dwm.DwmSetWindowAttribute(
                    wintypes.HWND(hwnd), ct.c_uint(DWMWA_CAPTION_COLOR),
                    ct.byref(cap), ct.sizeof(cap),
                )
                hr2 = dwm.DwmSetWindowAttribute(
                    wintypes.HWND(hwnd), ct.c_uint(DWMWA_TEXT_COLOR),
                    ct.byref(txt), ct.sizeof(txt),
                )
                ok = (hr1 == 0 and hr2 == 0)
                if ok:
                    SWP_NOSIZE = 0x0001
                    SWP_NOMOVE = 0x0002
                    SWP_NOZORDER = 0x0004
                    SWP_FRAMECHANGED = 0x0020
                    user32.SetWindowPos(
                        wintypes.HWND(hwnd),
                        0, 0, 0, 0, 0,
                        SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_FRAMECHANGED,
                    )
                return ok
            except Exception:
                return False

        success = False
        if _apply_to(first):
            Titlebar._APPLIED[first] = (caption_hex, text_hex)
            success = True
        else:
            for alt in hwnds[1:]:
                if _apply_to(alt):
                    Titlebar._APPLIED[first] = (caption_hex, text_hex)
                    success = True
                    break

        if not success:
            Titlebar._APPLIED.setdefault(first, "dark")

        Titlebar._LAST_APPLY[first] = now
        return success

    # After Win+D / minimize / display change: reapply titlebar color safely.
    @staticmethod
    def bind_reapply(widget: tk.Misc):
        try:
            top = widget.winfo_toplevel()
            top.update_idletasks()
            hwnd = top.winfo_id()
            after_id = {"id": None}

            def _mark_dirty(_e=None):
                Titlebar._NEEDS_REAPPLY.add(hwnd)

            def _do_reapply():
                if not Titlebar._safe_to_call_native(top):
                    return
                colors = Titlebar._APPLIED.get(hwnd)
                if isinstance(colors, tuple) and len(colors) == 2:
                    cap, txt = colors
                else:
                    cap, txt = "#0e1b29", "#e6f1ff"
                ok = Titlebar.set_color(top, caption_hex=cap, text_hex=txt)
                if not ok:
                    Titlebar._dark_title_bar_SO(top)
                Titlebar._NEEDS_REAPPLY.discard(hwnd)

            def _retry_once():
                if not top.winfo_exists():
                    return
                _do_reapply()
                after_id["id"] = None

            def _reapply_now(e=None):
                if e is not None and e.widget is not top:
                    return
                if not Titlebar._safe_to_call_native(top):
                    return
                _do_reapply()
                if after_id["id"] is None and top.winfo_exists():
                    after_id["id"] = top.after(120, _retry_once)

            def _on_destroy(_e=None):
                aid = after_id["id"]
                if aid is not None:
                    try:
                        top.after_cancel(aid)
                    except Exception:
                        pass
                    after_id["id"] = None
                try:
                    Titlebar._NEEDS_REAPPLY.discard(hwnd)
                except Exception:
                    pass

            top.bind("<Unmap>",      _mark_dirty,  add="+")
            top.bind("<Map>",        _reapply_now, add="+")
            top.bind("<Visibility>", _reapply_now, add="+")
            top.bind("<FocusIn>",    _reapply_now, add="+")
            top.bind("<Destroy>",    _on_destroy,  add="+")
        except Exception:
            pass

    # One call: icon + colored titlebar + safe reapply + fallback.
    @staticmethod
    def install(widget: tk.Misc,
                caption_hex: str = "#0e1b29",
                text_hex: str = "#e6f1ff"):
        try:
            Titlebar.set_icon(widget)
            ok = Titlebar.set_color(widget, caption_hex=caption_hex, text_hex=text_hex)
            if not ok:
                Titlebar._dark_title_bar_SO(widget)
            Titlebar.bind_reapply(widget)
        except Exception:
            pass


# ---------------- Combo box ----------------

def combobox_style(root):
    style = ttk.Style(root)
    style.theme_use("clam")

    style_name = "ModLoader.TCombobox"
    accent_combo = COLOR_PALETTE["desc"]

    style.configure(style_name,
        fieldbackground = COLOR_PALETTE["input_bg"],
        background      = COLOR_PALETTE["input_bg"],
        foreground      = accent_combo,
        bordercolor     = COLOR_PALETTE["input_bg"],
        lightcolor      = COLOR_PALETTE["input_bg"],
        darkcolor       = COLOR_PALETTE["input_bg"],
        arrowcolor      = accent_combo,
        arrowsize       = 16,
        padding         = (4, 6, 6, 4),
        relief          = "flat",
        borderwidth     = 0,
        selectbackground = COLOR_PALETTE["input_bg"],
        selectforeground = accent_combo,
        focuscolor      = "",
    )
    
    

    style.map(style_name,
              
        # Default textfield
        fieldbackground = [
            ("readonly", "pressed", COLOR_PALETTE["panel_active"]),
            ("readonly", "active",  COLOR_PALETTE["panel_hover"]),
            ("readonly", "focus",   COLOR_PALETTE["panel_active"]),
            ("readonly", "hover",   COLOR_PALETTE["panel_hover"]),
            ("",                  COLOR_PALETTE["input_bg"]),
            
        ],
        
        # global background
        background = [ 
            ("readonly", "pressed", COLOR_PALETTE["panel_active"]),
            ("readonly", "active",  COLOR_PALETTE["panel_hover"]),
            ("readonly", "focus",   COLOR_PALETTE["panel_active"]),
            ("readonly", "hover",   COLOR_PALETTE["panel_hover"]),
            ("",                  COLOR_PALETTE["input_bg"]),
        ],
        bordercolor = [
            ("pressed", COLOR_PALETTE["panel_active"]),
            ("active",  COLOR_PALETTE["panel_hover"]),
            ("focus",   COLOR_PALETTE["panel_active"]),
            ("hover",   COLOR_PALETTE["panel_hover"]),
            ("",                  COLOR_PALETTE["input_bg"]),
        ],
        arrowcolor = [
            ("pressed", accent_combo),
            ("active",  accent_combo),
            ("focus",   accent_combo),
            ("hover",   accent_combo),
        ],
    )

    # Style the popdown listbox (tk.Listbox), not ttk style
    root.option_add("*TCombobox*Listbox.font", FONTS["base_bold"])
    root.option_add("*TCombobox*Listbox.background", COLOR_PALETTE["panel"])
    root.option_add("*TCombobox*Listbox.foreground", COLOR_PALETTE["meta"])
    root.option_add("*TCombobox*Listbox.selectBackground", COLOR_PALETTE["panel_hover"])
    root.option_add("*TCombobox*Listbox.selectForeground", COLOR_PALETTE["text"])
    root.option_add("*TCombobox*Listbox.padding", COLOR_PALETTE["text"])
    root.option_add("*TCombobox*Listbox.borderWidth", 0)
    root.option_add("*TCombobox*Listbox.relief", "flat")

    # lista rozwijana
    style.configure(f"{style_name}.Dropdown",
        background = COLOR_PALETTE["panel"],
        foreground = COLOR_PALETTE["text"],
        bordercolor = COLOR_PALETTE["border"],
    )

    style.map(f"{style_name}.Dropdown",
        background = [("hover", COLOR_PALETTE["panel_hover"])]
    )

    style.configure("ComboboxPopdownFrame",
        background = COLOR_PALETTE["border"],
        relief     = "flat",
        borderwidth = 1,
    )

    return style_name

class CustomCombo(ttk.Combobox):

    STYLE_NAME = None
    _global_bound = False
    _instances = set()

    def __init__(self, master, **kwargs):
        if CustomCombo.STYLE_NAME is None:
            CustomCombo.STYLE_NAME = combobox_style(master)

        kwargs.setdefault("style", CustomCombo.STYLE_NAME)
        kwargs.setdefault("font", FONTS["base_bold"])
        kwargs.setdefault("justify", "right")
        kwargs.setdefault("state", "readonly")
        kwargs.setdefault("width", 14)

        super().__init__(master, **kwargs)
        
        self._watch_popdown_job = None
        self._watching_popdown = False

        self._pre_click_value = None

        CustomCombo._instances.add(self)
        self.bind("<Destroy>", self._on_destroy, add="+")
        
        self.bind("<<ComboboxSelected>>", self._on_select, add="+")
        self.bind("<FocusIn>", self._clear_selection, add="+")
        self.bind("<KeyRelease>", self._clear_selection, add="+")

        self.bind("<Button-1>", self._on_mouse_down, add="+")
        self.bind("<ButtonRelease-1>", self._on_mouse_up, add="+")

        self.bind("<FocusOut>", self._force_reset_visual, add="+")
        self.bind("<Leave>", self._force_reset_visual, add="+")

        root = self.winfo_toplevel()
        if not CustomCombo._global_bound:
            root.bind_all("<Button-1>", CustomCombo._global_click_defocus, add="+")
            CustomCombo._global_bound = True

    def _on_destroy(self, event=None):
        try:
            CustomCombo._instances.discard(self)
        except Exception:
            pass

    def _on_mouse_down(self, event=None):
        self._pre_click_value = self.get()
        self._clear_selection()
        self._begin_popdown_watch()

    def _on_mouse_up(self, event=None):
        self.after(120, self._defocus_if_nothing_changed)

    def _defocus_if_nothing_changed(self):
        if self.get() == self._pre_click_value:
            self._force_reset_visual()
            try:
                self.master.focus_set()
            except Exception:
                pass
        self._clear_selection()

    @classmethod
    def _global_click_defocus(cls, event):
        try:
            clicked = event.widget
            clicked_path = str(clicked)

            # If user clicked inside the popdown list -> do nothing here
            # (selection handling happens there; closing popdown will trigger other resets)
            if ".popdown" in clicked_path:
                return

            def do_reset():
                # Reset ALL combos except the one we clicked on (if any)
                for combo in list(cls._instances):
                    try:
                        if not combo.winfo_exists():
                            cls._instances.discard(combo)
                            continue

                        if clicked is combo:
                            continue

                        # If popdown is open, leave it alone (closing popdown will clear states)
                        if combo._is_popdown_open():
                            def delayed_reset(c=combo):
                                try:
                                    if not c.winfo_exists():
                                        return
                                    if c._is_popdown_open():
                                        c.after(60, delayed_reset)
                                        return
                                    c.state(["!active", "!pressed"])
                                    c._clear_selection()
                                except Exception:
                                    pass
                            combo.after(60, delayed_reset)
                            continue

                        combo.state(["!active", "!pressed"])
                        combo._clear_selection()
                    except Exception:
                        pass

            # Run after Tk finishes processing the click (state changes settle)
            clicked.after_idle(do_reset)

        except Exception:
            pass


    def _force_reset_visual(self, event=None):
        if self._is_popdown_open():
            return
        try:
            self.state(["!active", "!pressed"])
        except Exception:
            pass
        self._clear_selection()

    def _clear_selection(self, _=None):
        try:
            self.selection_clear()
            self.icursor("end")
        except Exception:
            pass

    def _is_popdown_open(self):
        try:
            pop = self.tk.call("ttk::combobox::PopdownWindow", self)
            return int(self.tk.call("winfo", "ismapped", pop)) == 1
        except Exception:
            return False

    def _on_select(self, event=None):
        # After selection, dropdown closes; reset visual and optionally defocus
        def finish():
            try:
                self.state(["!active", "!pressed"])
            except Exception:
                pass
            self._clear_selection()
            try:
                self.master.focus_set()
            except Exception:
                pass

        self.after(1, finish)

    def _begin_popdown_watch(self):
        # Cancel previous watcher if any
        try:
            if self._watch_popdown_job is not None:
                self.after_cancel(self._watch_popdown_job)
        except Exception:
            pass

        self._watching_popdown = True
        self._watch_popdown_job = self.after(30, self._poll_popdown_close)

    def _poll_popdown_close(self):
        if not self._watching_popdown:
            return

        if self._is_popdown_open():
            self._watch_popdown_job = self.after(60, self._poll_popdown_close)
            return

        # Popdown closed -> always clear the "open/active" look
        self._watching_popdown = False
        self._watch_popdown_job = None

        try:
            self.state(["!active", "!pressed"])
        except Exception:
            pass
        self._clear_selection()

        # If user clicked elsewhere, focus is already elsewhere; this just guarantees no sticky focus
        try:
            if self.winfo_toplevel().focus_get() is self:
                self.master.focus_set()
        except Exception:
            pass





# ---------------- Window center ----------------

class Window:
    
    @staticmethod
    def center_on_parent(win: tk.Toplevel | tk.Tk, parent: tk.Widget | None = None, pad: int = 16):
        win.update_idletasks()
        w = win.winfo_width()  or win.winfo_reqwidth()
        h = win.winfo_height() or win.winfo_reqheight()

        if parent and parent.winfo_ismapped():
            px, py = parent.winfo_rootx(), parent.winfo_rooty()
            pw = parent.winfo_width()  or parent.winfo_reqwidth()
            ph = parent.winfo_height() or parent.winfo_reqheight()
            x = px + (pw - w)//2
            y = py + (ph - h)//2
        else:
            sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
            x = (sw - w)//2
            y = (sh - h)//2

        x = max(pad, x)
        y = max(pad, y)
        win.geometry(f"{w}x{h}+{x}+{y}")

    @staticmethod
    def show_centered_toplevel(parent: tk.Widget, build_fn, modal: bool = False, title: str | None = None):
        top = tk.Toplevel(parent)
        if title:
            top.title(title)
        top.withdraw()
        build_fn(top)
        top.update_idletasks()
        Window.center_on_parent(top, parent)
        top.deiconify()
        top.transient(parent)
        if modal:
            top.grab_set()
        return top


# ---------------- Scrollabe ----------------

def style_scrollbar(root):
    style = ttk.Style(root)
    try: style.theme_use("clam")
    except Exception: pass

    style_name = "Custom.Vertical.TScrollbar"
    style.configure(style_name,
                    troughcolor=COLOR["scrollbar_bg"],     # rail
                    background=COLOR["scrollbar_thumb"],   # thumb
                    bordercolor=COLOR["scrollbar_bg"],
                    lightcolor=COLOR["scrollbar_bg"],
                    darkcolor=COLOR["scrollbar_bg"],
                    arrowcolor=COLOR["text"],
                    gripcount=0,
                    troughrelief="flat",            # flat rail
                    relief="flat",                  # flat thumb
                    borderwidth=1,
                    )
    style.map(style_name,
        fieldbackground=[
            ("readonly", "pressed", COLOR_PALETTE["input_bg"]),
            ("readonly", "active",  COLOR_PALETTE["input_bg"]),
            ("readonly", "focus",   COLOR_PALETTE["input_bg"]),
            ("readonly", "hover",   COLOR_PALETTE["panel_hover"]),
            ("readonly",            COLOR_PALETTE["input_bg"]),
        ],
        background=[
            ("readonly", "pressed", COLOR_PALETTE["input_bg"]),
            ("readonly", "active",  COLOR_PALETTE["input_bg"]),
            ("readonly", "focus",   COLOR_PALETTE["input_bg"]),
            ("readonly", "hover",   COLOR_PALETTE["panel_hover"]),
            ("readonly",            COLOR_PALETTE["input_bg"]),
        ],
        bordercolor=[
            ("pressed", COLOR_PALETTE["input_bd"]),
            ("active",  COLOR_PALETTE["input_bd"]),
            ("focus",   COLOR_PALETTE["input_bd"]),
            ("hover",   COLOR_PALETTE["accent_lightblue"]),
            ("",        COLOR_PALETTE["input_bd"]),
        ],
        arrowcolor=[
            ("hover", COLOR_PALETTE["accent_lightblue"]),
            ("",      COLOR_PALETTE["meta"]),
        ],
    )
    return style_name


class Scrollable(tk.Frame):
    def __init__(self, master, **kw):
        bg = kw.pop("bg", COLOR["panel"])
        super().__init__(master, bg=bg, **kw)
        style_name = style_scrollbar(self)

        self.canvas = tk.Canvas(self, bg=bg, bd=0, highlightthickness=0)
        self.vbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview, style=style_name)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._win_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.vbar.set)

        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self._win_id, width=e.width))

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vbar.grid(row=0, column=1, sticky="ns")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Mouse binds
        for target in (self.canvas, self.inner):
            # wheel (Windows/macOS)
            self.bind("<Enter>", lambda e: self.canvas.bind_all("<Button-2>", self._mmb_start), add="+")
            self.bind("<Leave>", lambda e: self.canvas.unbind_all("<Button-2>"), add="+")

            # wheel (Linux)
            target.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"), add="+")
            target.bind("<Button-5>", lambda e: self.canvas.yview_scroll( 1, "units"), add="+")

            # MMB drag
            target.bind("<Button-2>",        self._mmb_start, add="+")
            target.bind("<B2-Motion>",       self._mmb_drag,  add="+")
            target.bind("<ButtonRelease-2>", self._mmb_end,   add="+")

    def _mmb_start(self, e):
        x = self.canvas.winfo_pointerx() - self.canvas.winfo_rootx()
        y = self.canvas.winfo_pointery() - self.canvas.winfo_rooty()

        self.canvas.scan_mark(x, y)
        self._mmb_active = True
        
        # movement/release we catch globally during the drag
        self.canvas.bind_all("<B2-Motion>", self._mmb_drag)
        self.canvas.bind_all("<ButtonRelease-2>", self._mmb_end)

    def _mmb_drag(self, e):
        if self._mmb_active:
            x = self.canvas.winfo_pointerx() - self.canvas.winfo_rootx()
            y = self.canvas.winfo_pointery() - self.canvas.winfo_rooty()
            self.canvas.scan_dragto(x, y, gain=1)
            
    def _mmb_end(self, _e):
        self._mmb_active = False
        self.canvas.unbind_all("<B2-Motion>")
        self.canvas.unbind_all("<ButtonRelease-2>")
        if getattr(self, "_old_cursor", None) is not None:
            try: self.canvas.configure(cursor=self._old_cursor)
            except Exception: pass
            self._old_cursor = None


# ---------------- Button ----------------
class Button(tk.Frame):
    
    """Example Usage: Button(parent, text="RUN", command=on_run, style="Run.TButton", pack={"side":"left"})"""

    DEFAULT_BORDER      = COLOR["button_border"]
    HOVER_BORDER        = COLOR["button_bg_hover"]
    ACTIVE_BORDER       = COLOR["button_bg_active"]
    
    BUTTON_BG           = COLOR["button_bg"]
    BUTTON_BG_HOVER     = COLOR["button_bg_hover"]
    BUTTON_BG_ACTIVE    = COLOR["button_bg_active"]
    BUTTON_BG_DISABLED  = COLOR["button_bg_disabled"]    
    BUTTON_FG           = COLOR["text"] 
    BUTTON_FG_DISABLED  = COLOR["text_disabled"] 
    
        
    SPECIAL_BG           = COLOR["accent_blue"]
    SPECIAL_BG_HOVER     = COLOR["accent_lightblue"]
    SPECIAL_BG_ACTIVE    = COLOR["text"]
    SPECIAL_BG_DISABLED  = COLOR["accent_darkblue"]    
    SPECIAL_FG           = COLOR["special_fg"] 
    
    INSIDE_PADDING = (12, 6)
    SPECIAL_PADDING = (12, 5)
    FRAME_THICKNESS = 0 # <--- 0 is one pixel
    
    DEFAULT_TTK_STYLE = "ModLoader.Button.TButton"
    SPECIAL_TTK_STYLE = "ModLoader.Button.Special.TButton"
    _ttk_style_created = False    
    
    @classmethod
    def _ensure_styles(cls):
        if cls._ttk_style_created:
            return cls.DEFAULT_TTK_STYLE, cls.SPECIAL_TTK_STYLE        
        st = ttk.Style()
        try:
            
            # ----- default button style -----
            st.configure(
                cls.DEFAULT_TTK_STYLE,
                background=cls.BUTTON_BG,
                foreground=cls.BUTTON_FG,
                padding=cls.INSIDE_PADDING,
                relief="flat",
            )
            st.map(
                cls.DEFAULT_TTK_STYLE,
                background=[
                    ("pressed",  cls.BUTTON_BG_ACTIVE),
                    ("active", cls.BUTTON_BG_HOVER),
                    ("disabled", cls.BUTTON_BG_DISABLED),
                    ("!disabled", cls.BUTTON_BG),
                ],
                foreground=[
                    ("disabled", cls.BUTTON_FG_DISABLED),
                ],
            )
            
            # ----- special button style -----            
            st.configure(
                cls.SPECIAL_TTK_STYLE,
                background=cls.SPECIAL_BG,
                foreground=cls.SPECIAL_FG,
                padding=cls.SPECIAL_PADDING,
                relief="flat",
                font=FONTS["base_bold"],
            )
            st.map(
                cls.SPECIAL_TTK_STYLE,
                background=[
                    ("pressed",  cls.SPECIAL_BG_ACTIVE),
                    ("active",   cls.SPECIAL_BG_HOVER),
                    ("disabled", cls.SPECIAL_BG_DISABLED),
                    ("!disabled", cls.SPECIAL_BG),
                ],
                foreground=[("disabled", cls.SPECIAL_FG)],
            )            
        except Exception:
            pass
        
        cls._ttk_style_created = True
        return cls.DEFAULT_TTK_STYLE, cls.SPECIAL_TTK_STYLE

    def __init__(self,
                 master,
                 text: str = "",
                 command=None,
                 type: str = 'default',
                 style: Optional[str] = None,
                 tooltip: Optional[str] = None,
                 padx: int = 1,
                 pady: int = 1,
                 cursor: str = "hand2",
                 pack: Optional[dict] = None,
                 grid: Optional[dict] = None,
                 place: Optional[dict] = None,
                 **button_kwargs):

        super().__init__(master, bg=self.DEFAULT_BORDER, bd=self.FRAME_THICKNESS, highlightthickness=0)
        
        default_style, special_style = self._ensure_styles()
        if style:
            used_style = style
        else:
            used_style = special_style if str(type).lower() == "special" else default_style

        self._inner_pad_x = padx
        self._inner_pad_y = pady
        self._tooltip_obj = None

        # Create inner ttk.Button
        self.button = ttk.Button(self, text=text, command=command, style=used_style, **button_kwargs)        
        self.button.pack(fill=tk.BOTH, expand=True, padx=self._inner_pad_x, pady=self._inner_pad_y)

        # pointer cursor for the whole composite
        try:
            self.button.configure(cursor=cursor)
        except Exception:
            pass

        # hover/press handlers
        for w in (self, self.button):
            w.bind("<Enter>", self._on_enter, add="+")
            w.bind("<Leave>", self._on_leave, add="+")

        # Create tooltip
        if tooltip:
            try:
                self._tooltip_obj = Tooltip(self.button, tooltip)
            except Exception:
                self._tooltip_obj = None

        self.bind("<Destroy>", self._on_destroy, add="+")

        # expose some convenience aliases
        self.invoke = self.button.invoke

        # optionally auto-layout
        if pack:
            self.pack(**pack)
        elif grid:
            self.grid(**grid)
        elif place:
            self.place(**place)

    # ------- event handlers -------
    def _on_enter(self, _=None):
        self.configure(bg=self.DEFAULT_BORDER)

    def _on_leave(self, _=None):
        self.configure(bg=self.DEFAULT_BORDER)

    def _on_press(self, _=None):
        self.configure(bg=self.DEFAULT_BORDER)

    def _on_destroy(self, _=None):
        try:
            if getattr(self, "_tooltip_obj", None):
                self._tooltip_obj._hide()
        except Exception:
            pass




    # ------- convenience helpers -------
    def set_text(self, txt: str):
        try:
            self.button.configure(text=txt)
        except Exception:
            pass

    def set_command(self, cmd):
        try:
            self.button.configure(command=cmd)
        except Exception:
            pass
        
    # Enable/disable
    def set_enabled(self, enabled: bool):
        self.button.configure(state=("normal" if enabled else "disabled"))
        self.button.configure(cursor=("hand2" if enabled else "arrow"))

    # Forward unknown attributes to the inner ttk.Button
    def __getattr__(self, item):
        btn = object.__getattribute__(self, "button")
        if hasattr(btn, item):
            return getattr(btn, item)
        raise AttributeError(item)

    @staticmethod
    def Grid(btn_row, btn_column, padx=(6,0), sticky=None): return {
        "row": btn_row,
        "column": btn_column,
        "padx": padx,            
        **({"sticky": sticky} if sticky is not None else {})
        }















# Vertical separator
class VSeparator(tk.Frame):
    def __init__(self, master, **kw):
        super().__init__(master, bg=COLOR_PALETTE["divider"], width=3, **kw)
        '''Example usage: VSeparator(self).grid(row=1, column=1, sticky="ns", padx=10)'''

class HSeparator(tk.Frame):
    def __init__(self, master, **kw):
        super().__init__(master, bg=COLOR_PALETTE["divider"], height=2, **kw)

# Thread‑safe stream that pushes into a queue with a tag.
class QueueStream(io.TextIOBase):
    def __init__(self, q, tag: str):
        super().__init__()
        self.q = q
        self.tag = tag
    def write(self, s: str) -> int:
        if s:
            self.q.put((self.tag, s))
        return len(s)
    def flush(self) -> None:
        pass


# Draw a rounded rectangle on a Canvas as a smoothed polygon. Returns item id.
def _canvas_round_rect(canvas: tk.Canvas, x1, y1, x2, y2, r, **kwargs):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    points = [
        x1 + r, y1,
        x2 - r, y1,
        x2, y1,
        x2, y1 + r,
        x2, y2 - r,
        x2, y2,
        x2 - r, y2,
        x1 + r, y2,
        x1, y2,
        x1, y2 - r,
        x1, y1 + r,
        x1, y1
    ]
    return canvas.create_polygon(points, smooth=True, splinesteps=24, **kwargs)

# Safely get background color for both tk and ttk widgets.
def _safe_widget_bg(w: tk.Misc, fallback: str | None = None) -> str:
    if fallback is None:
        fallback = COLOR.get("panel", "#000000")

    # tk widgets
    try:
        return str(w.cget("bg"))
    except Exception:
        pass

    # ttk widgets
    try:
        st = ttk.Style(w)
        try:
            stylename = w.cget("style")
        except Exception:
            stylename = ""
        if not stylename:
            stylename = w.winfo_class()

        bg = st.lookup(stylename, "background", default="") or st.lookup(stylename, "fieldbackground", default="")
        return str(bg) if bg else fallback
    except Exception:
        return fallback


# Shift-TAB error
#    result = self.text.tk.call((self._text_orig_cmd,) + args)
#   _tkinter.TclError: text doesn't contain any characters tagged with "sel"


# Code editor
class CodeEditor(tk.Frame):
    def __init__(self, master, **kw):
        fg   = kw.pop("fg",   COLOR["text"])
        bg   = kw.pop("bg",   COLOR["input_bg"])
        font = kw.pop("font", FONTS["mono"])
        meta = kw.pop("meta", COLOR["meta"])

        border_col = kw.pop("bordercolor", COLOR["border"])
        focus_col  = kw.pop("focuscolor",  COLOR.get("focus", "#3d5566"))

        radius    = kw.pop("radius", 2)
        border_w  = kw.pop("borderwidth", 2)
        inner_pad = kw.pop("innerpad", 6)

        lineno_bg = kw.pop("lineno_bg", _darken_hex(bg, 0.10))
        lineno_fg = kw.pop("lineno_fg", meta)
        lineno_pad_x = kw.pop("lineno_pad_x", 10)

        tab_width_spaces = int(kw.pop("tab_width", 4))
        highlight_current_line = bool(kw.pop("highlight_line", True))
        
        # Height control
        height_lines = kw.pop("height_lines", None)   # e.g. 6, 10
        height_px    = kw.pop("height_px", None)      # e.g. 160
        lock_height  = bool(kw.pop("lock_height", False))

        # Optional 2-way sync
        self._ext_var = kw.pop("textvariable", None)
        self._sync_on = bool(self._ext_var is not None)

        parent_bg = _safe_widget_bg(master, fallback=COLOR["panel"])
        super().__init__(master, bg=parent_bg, bd=0, highlightthickness=0)

        self._fg = fg
        self._bg = bg
        self._meta = meta
        self._border_col = border_col
        self._focus_col = focus_col
        self._radius = radius
        self._border_w = border_w
        self._inner_pad = inner_pad

        self._lineno_bg = lineno_bg
        self._lineno_fg = lineno_fg
        self._lineno_pad_x = lineno_pad_x

        self._tabw = max(1, tab_width_spaces)
        self._highlight_line = highlight_current_line

        self._updating = False
        self._hl_after = None
        self._ln_after = None

        # make sure border properly draws
        # self.after_idle(lambda: self._redraw_border(self._border_col))

        # Outer canvas for rounded border
        self.canvas = tk.Canvas(self, bd=0, highlightthickness=0, relief="flat", bg=parent_bg)
        self._lock_height = lock_height
        self.canvas.pack(fill=("x" if lock_height else "both"), expand=(False if lock_height else True))

        # Inner container inside the border
        self.inner = tk.Frame(self.canvas, bg=bg, bd=0, highlightthickness=0)
        self._win_id = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")

        # Left: line numbers, Right: text
        self.gutter = tk.Canvas(
            self.inner, bd=0, highlightthickness=0,
            bg=self._lineno_bg, width=48
        )

        self.text = tk.Text(
            self.inner,
            wrap="none",
            font=font,
            fg=fg,
            bg=bg,
            insertbackground=fg,
            selectbackground=COLOR_PALETTE["accent_blue"],
            selectforeground=COLOR_PALETTE["special_fg"],
            bd=0,
            borderwidth=0,
            highlightthickness=0,
            undo=True,
            autoseparators=True,
            maxundo=-1,
        )

        # Scrollbars        
        self._install_text_proxy()
        style_name = style_scrollbar(self)
        self.vbar = ttk.Scrollbar(self.inner, orient="vertical", command=self._yview, style=style_name)
        self.text.configure(yscrollcommand=self._on_text_yscroll)

        # Layout
        self.gutter.grid(row=0, column=0, sticky="ns")
        self.text.grid(row=0, column=1, sticky="nsew")
        self.vbar.grid(row=0, column=2, sticky="ns")

        self.inner.grid_rowconfigure(0, weight=1)
        self.inner.grid_columnconfigure(1, weight=1)

        # Configure Text tab width
        try:
            f = tkfont.Font(font=font)
            tab_px = f.measure(" " * self._tabw)
            self.text.configure(tabs=(tab_px,))
        except Exception:
            pass

        # Border draw
        def _redraw(outline_color: str):
            self.canvas.delete("field")
            w = self.canvas.winfo_width()
            h = self.canvas.winfo_height()
            if w <= 2 or h <= 2:
                return

            _canvas_round_rect(
                self.canvas,
                1, 1,
                w - 1, h - 1,
                r=self._radius,
                fill=self._bg,
                outline=outline_color,
                width=self._border_w,
                tags=("field",)
            )

            pad = self._border_w + self._inner_pad
            self.canvas.coords(self._win_id, pad, pad)
            self.canvas.itemconfigure(self._win_id, width=max(0, w - pad * 2), height=max(0, h - pad * 2))

        self._redraw_border = _redraw
        def _redraw_when_ready():
            try:
                w = self.canvas.winfo_width()
                h = self.canvas.winfo_height()
                if w <= 2 or h <= 2:
                    self.after(16, _redraw_when_ready)  # spróbuj za chwilę
                    return
                self._redraw_border(self._border_col)
            except Exception:
                pass

        # gdy widget pojawi się na ekranie
        self.canvas.bind("<Map>", lambda e: _redraw_when_ready(), add="+")
        self.bind("<Map>", lambda e: _redraw_when_ready(), add="+")

        # oraz na starcie
        self.after_idle(_redraw_when_ready)
        
        #self.canvas.bind("<Configure>", lambda e: _redraw(self._border_col), add="+")
        #self.after_idle(lambda: self._redraw_border(self._border_col))

        # Focus handling (border color)
        def _focus_in(_=None):
            _redraw(self._focus_col)
            if self._highlight_line:
                self._update_current_line()
        def _focus_out(_=None):
            _redraw(self._border_col)
            if self._highlight_line:
                self.text.tag_remove("current_line", "1.0", "end")


        self.text.bind("<FocusIn>", _focus_in, add="+")
        self.text.bind("<FocusOut>", _focus_out, add="+")
        self.after(0, lambda: _redraw(self._border_col))

        # Keybinds
        self.text.bind("<Tab>", self._on_tab, add="+")
        self.text.bind("<Return>", self._on_return, add="+")
        self.text.bind("<KeyRelease>", self._on_key_release, add="+")
        self.text.bind("<ButtonRelease-1>", lambda e: self._after_cursor_move(), add="+")
        self.text.bind("<Control-BackSpace>", self._on_ctrl_backspace)
        
        # Scroll update
        self.text.bind("<MouseWheel>", lambda e: self._after_scroll(), add="+")  # Windows
        self.text.bind("<Button-4>", lambda e: self._after_scroll(), add="+")    # Linux
        self.text.bind("<Button-5>", lambda e: self._after_scroll(), add="+")

        # Horizontal scroll (Shift + Wheel)
        self.text.bind("<Shift-MouseWheel>", self._on_shift_wheel_xscroll, add="+")
        self.text.bind("<Shift-Button-4>", self._on_shift_wheel_xscroll, add="+")
        self.text.bind("<Shift-Button-5>", self._on_shift_wheel_xscroll, add="+")

        # Gutter redraw triggers
        self.text.bind("<<Change>>", lambda e: self._schedule_line_numbers(), add="+")
        self.text.bind("<Configure>", lambda e: self._schedule_line_numbers(), add="+")
        self.text.bind("<Expose>", lambda e: self._schedule_line_numbers(), add="+")
        
        # Ctrl+Shift+Left/Right: keep selection inside the current line (no jumping to prev/next line)
        self.text.bind("<Control-Shift-Left>",  self._on_ctrl_shift_left,  add="+")
        self.text.bind("<Control-Shift-Right>", self._on_ctrl_shift_right, add="+")

        def _on_change(_e=None):
            self._schedule_line_numbers()
            if self._highlight_line:
                self._update_current_line()
            self._schedule_highlight()
        self.text.bind("<<Change>>", _on_change, add="+")

        # Tags (colors)
        self._init_tags()

        # First paint
        self._schedule_line_numbers()
        self._schedule_highlight()

        # Optional 2-way StringVar sync
        if self._sync_on:
            def _on_ext_change(*_):
                if self._updating:
                    return
                self._updating = True
                try:
                    self.set_text(self._ext_var.get())
                finally:
                    self._updating = False

            def _sync_to_var(_=None):
                if self._updating:
                    return
                self._updating = True
                try:
                    self._ext_var.set(self.get())
                finally:
                    self._updating = False

            try:
                self._ext_var.trace_add("write", _on_ext_change)
            except Exception:
                pass

            for seq in ("<KeyRelease>", "<<Paste>>", "<<Cut>>"):
                self.text.bind(seq, _sync_to_var, add="+")
            _on_ext_change()
        self.text.tag_raise("sel")
        # Apply initial height if requested
        if height_px is not None:
            self.set_height_px(height_px, lock=True)
        elif height_lines is not None:
            self.set_height_lines(height_lines, lock=True)

    # ---- public API ----

    def get(self) -> str:
        return self.text.get("1.0", "end-1c")

    def set_text(self, text: str):
        self.text.delete("1.0", "end")
        if text:
            self.text.insert("1.0", text)
        self._schedule_line_numbers()
        self._schedule_highlight()

    def focus(self):
        self.text.focus_set()        

    def set_enabled(self, enabled: bool, *, hide_preview_on_disable: bool = False):
        enabled = bool(enabled)
        self._enabled = enabled

        # Ensure tag exists (used to hide preview without destroying content).
        try:
            if "HIDE_PREVIEW" not in self.text.tag_names():
                self.text.tag_configure("HIDE_PREVIEW", elide=1)
        except Exception:
            pass

        # Temporarily unlock to adjust tags even if currently disabled.
        prev_state = None
        try:
            prev_state = str(self.text.cget("state"))
            if prev_state == "disabled":
                self.text.configure(state="normal")
        except Exception:
            prev_state = None

        try:
            if hide_preview_on_disable and (not enabled):
                self.text.tag_add("HIDE_PREVIEW", "1.0", "end")
            else:
                self.text.tag_remove("HIDE_PREVIEW", "1.0", "end")
        except Exception:
            pass

        fg_on = self._fg
        fg_off = COLOR.get("text_disabled", self._meta)

        # Visuals
        try:
            self.text.configure(
                fg=(fg_on if enabled else fg_off),
                insertbackground=(fg_on if enabled else fg_off),
                cursor=("xterm" if enabled else "arrow"),
                takefocus=(1 if enabled else 0),
            )
        except Exception:
            pass

        # Editability
        try:
            self.text.configure(state=("normal" if enabled else "disabled"))
        except Exception:
            # fallback: restore previous state if we changed it
            try:
                if prev_state is not None:
                    self.text.configure(state=prev_state)
            except Exception:
                pass

        # If we just disabled while focused, drop focus so the border doesn't look "active".
        if not enabled:
            try:
                if self.focus_get() == self.text:
                    self.focus_set()
            except Exception:
                pass
            if self._highlight_line:
                try:
                    self.text.tag_remove("current_line", "1.0", "end")
                except Exception:
                    pass

        # Redraw border immediately (fixes the "border appears only after click" issue).
        try:
            col = self._focus_col if (enabled and self.focus_get() == self.text) else self._border_col
            self._redraw_border(col)
        except Exception:
            try:
                self.canvas.event_generate("<Configure>")
            except Exception:
                pass

    def set_height_lines(self, lines: int, *, lock: bool = True):
        """Set editor height by number of text lines."""
        try:
            lines = max(1, int(lines))
        except Exception:
            lines = 6

        self.text.configure(height=lines)

        # Convert to px and apply as a fixed visual height (optional)
        try:
            f = tkfont.Font(font=self.text["font"])
            line_px = int(f.metrics("linespace"))
        except Exception:
            line_px = 16  # fallback

        # Add padding/border budget
        pad = int(self._border_w + self._inner_pad)
        extra = pad * 2 + 2  # a tiny safety margin
        px = lines * line_px + extra

        self.set_height_px(px, lock=lock)

    def set_height_px(self, px: int, *, lock: bool = True):
        """Set editor height in pixels. If lock=True, keep canvas visually fixed."""
        try:
            px = max(40, int(px))
        except Exception:
            px = 160

        self._fixed_height_px = px
        if lock:
            self._lock_height = True
            try:
                self.canvas.configure(height=px)
                # Make sure canvas doesn't expand vertically
                self.canvas.pack_configure(fill="x", expand=False)
            except Exception:
                pass
        else:
            self._lock_height = False
            try:
                self.canvas.pack_configure(fill="both", expand=True)
            except Exception:
                pass

        # Ask geometry managers not to override requested size
        try: self.pack_propagate(False)
        except Exception: pass
        try: self.grid_propagate(False)
        except Exception: pass

        try:
            self.configure(height=px)
        except Exception:
            pass

        # Redraw border after size changes
        try:
            self.after_idle(lambda: self._redraw_border(self._border_col))
        except Exception:
            pass






    # ---- text change event proxy ----

    # Make Text emit <<Change>> on content or viewport updates.
    def _install_text_proxy(self):
        try:
            # Guard against double-install.
            if getattr(self, "_text_proxy_installed", False):
                return
            self._text_proxy_installed = True
            self._text_orig_cmd = self.text._w + "_orig"

            # Rename the original widget command and create a proxy.
            self.text.tk.call("rename", self.text._w, self._text_orig_cmd)
            self.text.tk.createcommand(self.text._w, self._text_proxy)

            # Cleanup when widget dies (prevents Tcl errors on app shutdown).
            def _cleanup(_e=None):
                try:
                    if self.text.winfo_exists():
                        return
                except Exception:
                    pass
                try:
                    self.text.tk.deletecommand(self.text._w)
                except Exception:
                    pass
            self.text.bind("<Destroy>", _cleanup, add="+")
        except Exception:
            pass
    #  Tcl-level proxy for the Text widget command.
    def _text_proxy(self, *args):
        try:
            result = self.text.tk.call((self._text_orig_cmd,) + args)
        except tk.TclError as e:
            err_msg = str(e).lower()
            
            # Ctrl+Z, Ctrl+Y fix
            if "nothing to undo" in err_msg or "nothing to redo" in err_msg:
                return ""
            
            # Ctrl+C, Ctrl+X fix
            if 'tagged with "sel"' in err_msg or "tagged with 'sel'" in err_msg:
                return ""
            
            raise
        except Exception:
            raise
        
        # Fire a unified "changed" event for the operations we care about.
        try:
            if not args:
                return result
            op = args[0]
            changed = op in ("insert", "delete", "replace")
            # viewport changes: xview/yview moveto/scroll
            if not changed and op in ("xview", "yview"):
                if len(args) >= 2 and args[1] in ("moveto", "scroll"):
                    changed = True
            # cursor move (insert mark)
            if not changed and op == "mark" and len(args) >= 3:
                if args[1] == "set" and args[2] == "insert":
                    changed = True
            if changed:
                self.text.event_generate("<<Change>>", when="tail")
        except Exception:
            pass
        return result

    # ---- horizontal scrolling (Shift + wheel) ----
    def _on_shift_wheel_xscroll(self, e):
        try:
            if getattr(e, "delta", 0):
                step = -1 if e.delta > 0 else 1
            else:
                step = -1 if getattr(e, "num", 0) == 4 else 1
            self.text.xview_scroll(step, "units")
        except Exception:
            pass
        return "break"





    # ---- keybinds ----
    
    def _on_ctrl_backspace(self, event):
        if self.text.tag_ranges("sel"):
            self.text.delete("sel.first", "sel.last")
            return "break"

        insert_pos = self.text.index("insert")
        line_start = self.text.index("insert linestart")
        text_before = self.text.get(line_start, insert_pos)

        if text_before.endswith("    "):
            start_del = self.text.index("insert - 4c")
            self.text.delete(start_del, "insert")
            return "break"
        self.text.event_generate("<<Control-Backspace-Default>>") 
        
        self.text.delete("insert -1c wordstart", "insert")
        return "break"

    def _sel_extend_to(self, target_index: str) -> None:
        """Extend selection from the anchor mark to target_index and move insert."""
        try:
            if not self.text.tag_ranges("sel"):
                self.text.mark_set("anchor", "insert")
        except Exception:
            pass

        try:
            self.text.mark_set("insert", target_index)
        except Exception:
            return

        try:
            a = self.text.index("anchor")
            b = self.text.index("insert")
            self.text.tag_remove("sel", "1.0", "end")
            if self.text.compare(a, "<=", b):
                self.text.tag_add("sel", a, b)
            else:
                self.text.tag_add("sel", b, a)
            self.text.tag_raise("sel")
        except Exception:
            pass

    def _move_word_right_next_line(self) -> str:
        line_end = self.text.index("insert lineend")
        next_line_start = self.text.index(f"{line_end}+1c")
        if self.text.compare(next_line_start, ">=", "end-1c"):
            return line_end
        return self._move_word_right_in_line_from(next_line_start)

    def _move_word_left_in_line_from(self, index: str) -> str:
        line_start = self.text.index(f"{index} linestart")
        if self.text.compare(index, "<=", line_start):
            return line_start

        prefix = self.text.get(line_start, index)
        i = len(prefix)
        while i > 0 and prefix[i - 1].isspace():
            i -= 1
        while i > 0 and (not prefix[i - 1].isspace()):
            i -= 1
        return self.text.index(f"{line_start}+{i}c")


    def _move_word_right_in_line_from(self, index: str) -> str:
        line_end = self.text.index(f"{index} lineend")
        if self.text.compare(index, ">=", line_end):
            return line_end

        suffix = self.text.get(index, line_end)
        i = 0
        while i < len(suffix) and suffix[i].isspace():
            i += 1
        while i < len(suffix) and (not suffix[i].isspace()):
            i += 1
        return self.text.index(f"{index}+{i}c")



    def _move_word_left_prev_line(self) -> str:
        line_start = self.text.index("insert linestart")
        if self.text.compare(line_start, "<=", "1.0"):
            return line_start

        prev_pos = self.text.index(f"{line_start}-1c")
        prev_line_end = self.text.index(f"{prev_pos} lineend")
        return self._move_word_left_in_line_from(prev_line_end)


    def _on_ctrl_shift_right(self, _event=None):
        insert = self.text.index("insert")
        line_end = self.text.index("insert lineend")

        # Step 1: dojdź do końca linii
        if self.text.compare(insert, "<", line_end):
            target = self._move_word_right_in_line_from(insert)
        else:
            # Step 2: (już na końcu) skocz do następnej linii
            target = self._move_word_right_next_line()

        self._sel_extend_to(target)
        return "break"

    def _on_ctrl_shift_left(self, _event=None):
        insert = self.text.index("insert")
        line_start = self.text.index("insert linestart")

        # Step 1: dojdź do początku linii
        if self.text.compare(insert, ">", line_start):
            target = self._move_word_left_in_line_from(insert)
        else:
            # Step 2: (już na początku) skocz do poprzedniej linii
            target = self._move_word_left_prev_line()

        self._sel_extend_to(target)
        return "break"


    # ---- scrolling glue ----

    def _yview(self, *args):
        self.text.yview(*args)
        self._draw_line_numbers()

    def _on_text_yscroll(self, first, last):
        self.vbar.set(first, last)
        self._draw_line_numbers()

    def _after_scroll(self):
        self._schedule_line_numbers()
        if self._highlight_line:
            self._update_current_line()

    def _after_cursor_move(self):
        if self._highlight_line:
            self._update_current_line()

    # ---- line numbers ----

    def _schedule_line_numbers(self):
        if self._ln_after is not None:
            try: self.after_cancel(self._ln_after)
            except Exception: pass
        self._ln_after = self.after(10, self._draw_line_numbers)

    def _draw_line_numbers(self):
        self._ln_after = None
        try:
            self.gutter.delete("all")
            self.gutter.configure(bg=self._lineno_bg)

            # Determine visible lines
            i = self.text.index("@0,0")
            while True:
                dline = self.text.dlineinfo(i)
                if dline is None:
                    break
                y = dline[1]
                lineno = i.split(".")[0]
                self.gutter.create_text(
                    self._lineno_pad_x, y,
                    anchor="nw",
                    text=lineno,
                    fill=self._lineno_fg,
                    font=(FONTS["mono"][0], max(9, int(FONTS["mono"][1]) - 1)),
                )
                i = self.text.index(f"{i}+1line")

            # Gutter width adapts to total lines
            total_lines = int(self.text.index("end-1c").split(".")[0])
            digits = max(2, len(str(total_lines)))
            try:
                f = tkfont.Font(font=self.text["font"])
                w = f.measure("9" * digits) + (self._lineno_pad_x * 2)
            except Exception:
                w = 48
            self.gutter.configure(width=max(44, w))
        except Exception:
            pass

    # ---- indent helpers ----

    def _get_selection_or_line_range(self):
        try:
            start = self.text.index("sel.first")
            end = self.text.index("sel.last")
            # expand to full lines
            start_line = start.split(".")[0]
            end_line = end.split(".")[0]
            return f"{start_line}.0", f"{end_line}.end"
        except tk.TclError:
            # no selection -> current line
            line = self.text.index("insert").split(".")[0]
            return f"{line}.0", f"{line}.end"

    def _on_tab(self, event):
        if self.text.tag_ranges("sel"):
            start = self.text.index("sel.first linestart")
            end   = self.text.index("sel.last lineend")
            lines = self.text.get(start, end).splitlines()
            
            if event.state & 0x0001:  # Shift → outdent
                new_lines = []
                for line in lines:
                    if line.startswith("    "):
                        new_lines.append(line[4:])
                    else:
                        new_lines.append(line)
            else:
                new_lines = ["    " + line for line in lines]
                
            self.text.replace(start, end, "\n".join(new_lines))
            self.text.tag_add("sel", start, f"{start}+{len(new_lines)}l")
            return "break"        
        self.text.insert("insert", "    ")
        return "break"

    # auto-indent based on current line leading whitespace
    def _on_return(self, event):
        cur = self.text.index("insert")
        line = self.text.get(f"{cur} linestart", f"{cur} lineend")
        
        # policz aktualne wcięcie
        indent = len(line) - len(line.lstrip())
        indent_str = " " * indent
        
        # jeśli poprzednia linia kończy się dwukropkiem → +4
        prev_line = self.text.get(f"{cur}-1l linestart", f"{cur}-1l lineend")
        if prev_line.rstrip().endswith(":"):
            indent_str += "    "
        
        # cofanie wcięcia po niektórych słowach
        if line.strip() in ("pass", "return", "break", "continue", "raise"):
            indent_str = indent_str[:-4] if len(indent_str) >= 4 else ""
        
        self.text.insert("insert", "\n" + indent_str)
        return "break"

    # ---- current line highlight ----

    def _update_current_line(self):
        try:
            self.text.tag_remove("current_line", "1.0", "end")
            line = self.text.index("insert").split(".")[0]
            self.text.tag_add("current_line", f"{line}.0", f"{line}.end+1c")
        except Exception:
            pass

    # ---- highlighting ----

    def _init_tags(self):
        # Current line
        try:
            self.text.tag_configure("current_line", background=_darken_hex(self._bg, 0.10))
            self.text.tag_lower("current_line")
        except Exception:
            pass

        # Syntax
        kw = COLOR.get("accent_yellow", "#ffd166")
        st = COLOR.get("accent_green",  "#39d353")
        cm = COLOR.get("meta",          "#9fb7d9")
        nu = COLOR.get("accent_lightblue", "#9cd2ff")
        op = COLOR.get("accent_blue",   "#72c0ff")
        fn = COLOR.get("accent_lightblue", "#9cd2ff")
        ob = COLOR.get("accent_darkblue",  "#2b84d6")
        cn = COLOR.get("accent_yellow",    "#ffd166")
        fl = COLOR.get("accent_yellow", "#ffd166")  # albo inny kolor

        self.text.tag_configure("tok_kw",  foreground=kw)
        self.text.tag_configure("tok_str", foreground=st)
        self.text.tag_configure("tok_com", foreground=cm)
        self.text.tag_configure("tok_num", foreground=nu)
        self.text.tag_configure("tok_op",  foreground=op)
        self.text.tag_configure("tok_fn",    foreground=fn)
        self.text.tag_configure("tok_obj",   foreground=ob)
        self.text.tag_configure("tok_const", foreground=cn)
        self.text.tag_configure("tok_dom",   underline=1)  # np. “ważne” symbole        
        self.text.tag_configure("tok_file", foreground=fl, underline=1)
        
        self.text.tag_raise("tok_file", "tok_str")

    def _on_key_release(self, e=None):
        self._schedule_line_numbers()
        if self._highlight_line:
            self._update_current_line()
        self._schedule_highlight()

    def _schedule_highlight(self):
        if self._hl_after is not None:
            try: self.after_cancel(self._hl_after)
            except Exception: pass
        self._hl_after = self.after(60, self._do_highlight)

    def _clear_syntax_tags(self):
        for tag in ("tok_kw","tok_str","tok_com","tok_num","tok_op","tok_fn","tok_obj","tok_const","tok_dom", "tok_file"):
            try:
                self.text.tag_remove(tag, "1.0", "end")
            except Exception:
                pass

    def _do_highlight(self):
        self._hl_after = None
        try:
            src = self.get()
        except Exception:
            return

        self._clear_syntax_tags()
        if not src:
            return

        self._highlight_language(src)
        
    def _apply_spans(self, spans, tag):
        # spans: list[(start_index_in_text, end_index_in_text)]
        for a, b in spans:
            try:
                self.text.tag_add(tag, f"1.0+{a}c", f"1.0+{b}c")
            except Exception:
                pass

    def _highlight_language(self, s: str):
        # cache compiled regexes
        if not hasattr(self, "_stormc_re"):
            # patterns inspired by your .tmlanguage
            self._stormc_re = {
                "str": re.compile(r"\"(?:\\.|[^\\\"])*\""),
                "linecom": re.compile(r"//[^\n]*"),
                "blockcom": re.compile(r"/\*[\s\S]*?\*/"),
                "kw": re.compile(r"\b(if|else|while|for|return|switch|case|break|extern|native)\b"),
                "types": re.compile(r"\b(void|bool|int|float|string|object|ref|aref)\b"),
                "dir": re.compile(r"(?m)^\s*#\s*(include|define|event_handler|script_libriary)\b.*$"),
                "num": re.compile(r"-?\b\d+(\.\d+)?\b"),
                "op": re.compile(r"[{}\[\]();,\.\+\-\*/%<>=!&|^~?:]"),
                # internal functions – you can paste the full list here (shortened sample below)
                "ifn": re.compile(
                    r"(?i)\b("
                    r"Rand|frnd|CreateClass|CreateEntity|DeleteClass|SetEventHandler|ExitProgram|GetEventData|Stop|SendMessage|"
                    r"LoadSegment|UnloadSegment|Trace|MakeInt|MakeFloat|abs|sqrt|sin|cos|tan|atan|"
                    r"DeleteAttribute|CheckAttribute|sti|stf|argb|makeref|makearef"
                    r")\b"
                ),
            }

        R = self._stormc_re

        def overlaps(a, b, spans):
            for x, y in spans:
                if not (b <= x or a >= y):
                    return True
            return False

        # 1) strings
        str_spans = [(m.start(), m.end()) for m in R["str"].finditer(s)]
        self._apply_spans(str_spans, "tok_str")

        # 2) comments (skip those inside strings)
        com_raw = [(m.start(), m.end()) for m in R["blockcom"].finditer(s)] + [(m.start(), m.end()) for m in R["linecom"].finditer(s)]
        com_spans = [(a, b) for (a, b) in com_raw if not overlaps(a, b, str_spans)]
        self._apply_spans(com_spans, "tok_com")

        # helper: skip strings/comments
        def ok(a, b):
            return (not overlaps(a, b, str_spans)) and (not overlaps(a, b, com_spans))

        # 3) directives
        dir_spans = []
        for m in R["dir"].finditer(s):
            a, b = m.start(), m.end()
            if ok(a, b):
                dir_spans.append((a, b))
        self._apply_spans(dir_spans, "tok_kw")

        # 4) numbers
        num_spans = []
        for m in R["num"].finditer(s):
            a, b = m.start(), m.end()
            if ok(a, b):
                num_spans.append((a, b))
        self._apply_spans(num_spans, "tok_num")

        # 5) keywords + types
        kw_spans, ty_spans = [], []
        for m in R["kw"].finditer(s):
            a, b = m.start(), m.end()
            if ok(a, b):
                kw_spans.append((a, b))
        for m in R["types"].finditer(s):
            a, b = m.start(), m.end()
            if ok(a, b):
                ty_spans.append((a, b))
        self._apply_spans(kw_spans, "tok_kw")
        self._apply_spans(ty_spans, "tok_const")  # użyjemy tok_const jako "typy" (albo dodaj osobny tag)

        # 6) internal functions
        fn_spans = []
        for m in R["ifn"].finditer(s):
            a, b = m.start(), m.end()
            if ok(a, b):
                fn_spans.append((a, b))
        self._apply_spans(fn_spans, "tok_fn")

        # 7) operators
        op_spans = []
        for m in R["op"].finditer(s):
            a, b = m.start(), m.end()
            if ok(a, b):
                op_spans.append((a, b))
        self._apply_spans(op_spans, "tok_op")
        
        # 8) files
        file_re = re.compile(
            r"(?i)\b[A-Za-z0-9_\-./\\]+\.(txt|c|h|ini|json|png|jpg|jpeg|tga|wav|ogg|mp3)\b"
        )
        file_spans = []
        for m in file_re.finditer(s):
            a, b = m.start(), m.end()
            if not overlaps(a, b, com_spans):
                file_spans.append((a, b))

        self._apply_spans(file_spans, "tok_file")




# Multiline Text with placeholder support
class InputMultiline(tk.Frame):
    def __init__(self, master, placeholder: str, **kw):
        fg   = kw.pop("fg",   COLOR["text"])
        bg   = kw.pop("bg",   COLOR["input_bg"])
        meta = kw.pop("meta", COLOR["meta"])
        font = kw.pop("font", FONTS["mono"])

        border_col = kw.pop("bordercolor", COLOR["border"])
        focus_col  = kw.pop("focuscolor",  COLOR.get("focus", "#3d5566"))

        radius    = kw.pop("radius", 2)
        border_w  = kw.pop("borderwidth", 2)
        inner_pad = kw.pop("innerpad", 6)

        self._ext_var = kw.pop("textvariable", None)
        self._sync_on = bool(self._ext_var is not None)

        height = kw.pop("height", 5)
        wrap   = kw.pop("wrap", "word")
        add_scrollbar = kw.pop("scrollbar", False)

        parent_bg = _safe_widget_bg(master, fallback=COLOR["panel"])
        super().__init__(master, bg=parent_bg, bd=0, highlightthickness=0)

        self._ph = placeholder
        self._ph_color = meta
        self._fg_real = fg
        self._bg_real = bg
        self._border_col = border_col
        self._focus_col = focus_col
        self._radius = radius
        self._border_w = border_w
        self._inner_pad = inner_pad

        self._has_ph = False
        self._updating = False

        self.canvas = tk.Canvas(self, bd=0, highlightthickness=0, relief="flat", bg=parent_bg)
        self.canvas.pack(fill="both", expand=True)

        self.inner = tk.Frame(self.canvas, bg=bg, bd=0, highlightthickness=0)
        self._win_id = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")

        self.text = tk.Text(
            self.inner,
            height=height,
            wrap=wrap,
            font=font,
            fg=fg,
            bg=bg,
            insertbackground=fg,
            bd=0,
            highlightthickness=0,
            undo=True,
        )

        if add_scrollbar:
            style_name = style_scrollbar(self)
            vbar = ttk.Scrollbar(self.inner, orient="vertical", command=self.text.yview, style=style_name)
            self.text.configure(yscrollcommand=vbar.set)
            self.text.grid(row=0, column=0, sticky="nsew")
            vbar.grid(row=0, column=1, sticky="ns")
            self.inner.grid_rowconfigure(0, weight=1)
            self.inner.grid_columnconfigure(0, weight=1)
        else:
            self.text.pack(fill="both", expand=True)

        self.text.tag_configure("placeholder", foreground=self._ph_color)

        def _content_is_empty() -> bool:
            return (self.text.get("1.0", "end-1c") == "")

        def _put_ph():
            if self._has_ph:
                return
            if _content_is_empty():
                self._has_ph = True
                self.text.insert("1.0", self._ph, ("placeholder",))

        def _clear_ph():
            if not self._has_ph:
                return
            self.text.delete("1.0", "end")
            self._has_ph = False

        self._put_ph = _put_ph
        self._clear_ph = _clear_ph

        def _redraw(outline_color: str):
            self.canvas.delete("field")
            w = self.canvas.winfo_width()
            h = self.canvas.winfo_height()
            if w <= 2 or h <= 2:
                return

            _canvas_round_rect(
                self.canvas,
                1, 1,
                w - 1, h - 1,
                r=self._radius,
                fill=self._bg_real,
                outline=outline_color,
                width=self._border_w,
                tags=("field",)
            )

            pad = self._border_w + self._inner_pad
            self.canvas.coords(self._win_id, pad, pad)
            self.canvas.itemconfigure(self._win_id, width=max(0, w - pad * 2), height=max(0, h - pad * 2))

        self.canvas.bind("<Configure>", lambda e: _redraw(self._border_col), add="+")

        def _focus_in(_=None):
            _clear_ph()
            _redraw(self._focus_col)

        def _focus_out(_=None):
            _redraw(self._border_col)
            if _content_is_empty():
                _put_ph()

        self.text.bind("<FocusIn>",  _focus_in,  add="+")
        self.text.bind("<FocusOut>", _focus_out, add="+")
        self.text.bind("<KeyPress>", lambda e: (_clear_ph() if self._has_ph else None), add="+")

        if self._sync_on:
            def _on_ext_change(*_):
                if self._updating:
                    return
                self._updating = True
                try:
                    self.set_text(self._ext_var.get())
                finally:
                    self._updating = False

            def _sync_to_var(_=None):
                if self._updating:
                    return
                self._updating = True
                try:
                    self._ext_var.set(self.get())
                finally:
                    self._updating = False

            try:
                self._ext_var.trace_add("write", _on_ext_change)
            except Exception:
                pass

            for seq in ("<KeyRelease>", "<<Paste>>", "<<Cut>>"):
                self.text.bind(seq, _sync_to_var, add="+")
            _on_ext_change()

        _put_ph()
        self.after(0, lambda: _redraw(self._border_col))

    def __getattr__(self, item):
        # forward methods to the inner Text for convenience (e.g. .insert, .delete, etc.)
        t = object.__getattribute__(self, "text")
        if hasattr(t, item):
            return getattr(t, item)
        raise AttributeError(item)

    def get(self) -> str:
        if self._has_ph:
            return ""
        return self.text.get("1.0", "end-1c")

    def set_text(self, text: str):
        self._clear_ph()
        self.text.delete("1.0", "end")
        if text:
            self.text.insert("1.0", text)
            self._has_ph = False
        else:
            self._put_ph()



# Minimalistic Entry with placeholder support
class InputText(ttk.Entry):
    _seq = 0
    def __init__(self, master, placeholder: str, **kw):
        fg   = kw.pop("fg",   COLOR["text"])
        bg   = kw.pop("bg",   COLOR["input_bg"])
        meta = kw.pop("meta", COLOR["meta"])
        font = kw.pop("font", FONTS["mono"])
        self._ext_var = kw.pop("textvariable", None)

        border_col = kw.pop("bordercolor", COLOR["border"])
        focus_col  = kw.pop("focuscolor",  COLOR.get("focus", "#3d5566"))

        InputText._seq += 1
        stylename = f"PlaceholderEntry{InputText._seq}.TEntry"
        style = ttk.Style(master)
        style.theme_use("clam")
        style.configure(
            stylename,
            padding=(8, 6),
            insertcolor=fg,
            foreground=fg,
            background=bg,
            fieldbackground=bg,
            borderwidth=0,
            relief="flat",
            bordercolor=border_col,
            lightcolor=border_col,
            darkcolor=border_col,
            focuscolor=focus_col,
            focusthickness=0,
        )
        style.map(
            stylename,
            bordercolor=[("focus", focus_col), ("!focus", border_col)],
            lightcolor=[("focus", focus_col), ("!focus", border_col)],
            darkcolor=[("focus", focus_col), ("!focus", border_col)],
            focuscolor=[("focus", focus_col), ("!focus", border_col)],
        )

        kw.setdefault("style", stylename)
        kw.setdefault("font", font)
        super().__init__(master, **kw)

        self._ph = placeholder
        self._ph_color = meta
        self._fg_real = fg
        self._has_ph = False
        self._updating = False

        def _put_ph():
            if not ttk.Entry.get(self):
                self._has_ph = True
                self.configure(foreground=self._ph_color)
                ttk.Entry.insert(self, 0, self._ph)

        def _clear_ph():
            if self._has_ph:
                ttk.Entry.delete(self, 0, tk.END)
                self.configure(foreground=self._fg_real)
                self._has_ph = False

        self._put_ph = _put_ph
        self._clear_ph = _clear_ph
        _put_ph()

        self.bind("<FocusIn>",  lambda e: _clear_ph(), add="+")
        self.bind("<FocusOut>", lambda e: _put_ph(),   add="+")

        # 2-way StringVar sync (optional)
        if self._ext_var is not None:
            def _on_ext_change(*_):
                if self._updating: return
                self._updating = True
                try:
                    self.set_text(self._ext_var.get())
                finally:
                    self._updating = False
            self._ext_var.trace_add("write", _on_ext_change)

            def _sync_to_var(*_):
                if self._updating: return
                self._updating = True
                try:
                    self._ext_var.set(self.get())
                finally:
                    self._updating = False

            for seq in ("<KeyRelease>", "<<Paste>>", "<<Cut>>"):
                self.bind(seq, _sync_to_var, add="+")
            _on_ext_change()

    def get(self):
        txt = ttk.Entry.get(self)
        if self._has_ph and txt == self._ph:
            return ""
        return txt

    def set_text(self, text: str):
        self._clear_ph()
        ttk.Entry.delete(self, 0, tk.END)
        if text:
            ttk.Entry.insert(self, 0, text)
            self.configure(foreground=self._fg_real)
            self._has_ph = False
        else:
            self._put_ph()

    def show_placeholder(self):
        ttk.Entry.delete(self, 0, tk.END)
        self._put_ph()
        if getattr(self, "_ext_var", None) is not None:
            self._ext_var.set("")

class InputTextStatic(tk.Frame):
    _seq = 0

    def __init__(self, master, text: str, **kw):
        fg   = kw.pop("fg",   COLOR["meta"])        # gray text
        bg   = kw.pop("bg",   COLOR["input_bg"])    # background as input
        font = kw.pop("font", FONTS["mono"])
        pad  = kw.pop("padding", (8, 6))

        border = kw.pop("bordercolor", _darken_hex(COLOR["border"], 0.15))
        border_th = kw.pop("borderthickness", 1)

        super().__init__(master, bg=border, highlightthickness=0, bd=0)

        InputTextStatic._seq += 1
        stylename = f"StaticEntryLike{InputTextStatic._seq}.TLabel"

        style = ttk.Style(master)
        style.theme_use("clam")
        style.configure(
            stylename,
            padding=pad,
            foreground=fg,
            background=bg,
            font=font,
            relief="flat",
            borderwidth=0,
        )

        self._label = ttk.Label(self, text=text, style=stylename, anchor="w")
        # The outline is made by the Frame, so we move the Label by 1px (or border_th)
        self._label.pack(fill="both", expand=True, padx=border_th, pady=border_th)

        try:
            self._label.configure(takefocus=0)
        except tk.TclError:
            pass

    def set_text(self, text: str):
        self._label.configure(text=text)

    def get(self) -> str:
        return str(self._label.cget("text"))

class Icon:
    BASE_DIR = Path(__file__).resolve().parent / "assets" / "icons"
    TEX = {
        "add": "add.png",
        "create": "create.png",
        "edit": "edit.png",
        "file": "file.png",
        "folder": "folder.png",
        "function": "function.png",
        "link": "link.png",
        "refresh": "refresh.png",
        "remove": "remove.png",
        "switch": "switch.png",
        "arrow_down": "arrow_down.png",
        "arrow_up": "arrow_up.png",
        "game": "game.png",
        "case": "case.png",
        "compact": "compact.png",
        "whale": "iconPNG.png"
    }
    _CACHE: dict[str, object] = {}
    _BG_REGISTRY: dict[int, WeakSet] = {}
    _BG_BOUND: set[int] = set()

    @staticmethod
    def _get_bg_from_widget(w: tk.Widget) -> str | None:
        # 1) for tk
        try:
            return w.cget("bg")
        except Exception:
            pass
        # 2) for ttk
        try:
            style = ttk.Style(w)
            stylename = w.cget("style") or w.winfo_class()
            return (style.lookup(stylename, "background", default=None)
                    or style.lookup(stylename, "fieldbackground", default=None))
        except Exception:
            return None

    @classmethod
    def _register_bg_follow(cls, lbl: tk.Label, master: tk.Widget) -> None:
        mid = id(master)
        if mid not in cls._BG_REGISTRY:
            cls._BG_REGISTRY[mid] = WeakSet()
        cls._BG_REGISTRY[mid].add(lbl)

        # set the starting background
        color = cls._get_bg_from_widget(master)
        if color:
            try: lbl.configure(bg=color)
            except Exception: pass

        # we bind only once on the master
        if mid not in cls._BG_BOUND:
            cls._BG_BOUND.add(mid)

            def _propagate(_=None):
                color = cls._get_bg_from_widget(master)
                if not color:
                    return
                dead = []
                for l in list(cls._BG_REGISTRY.get(mid, ())):
                    try: l.configure(bg=color)
                    except Exception: dead.append(l)
                # cleanup of dead references
                for l in dead:
                    try: cls._BG_REGISTRY[mid].discard(l)
                    except Exception: pass
                    
            # we ONLY listen to these two (no more Enter/Leave/Configure)
            for ev in ("<<BgChanged>>", "<<ThemeChanged>>"):
                try: master.bind(ev, _propagate, add="+")
                except Exception: pass
                
            # refresh after mapping just in case
            try: master.bind("<Map>", _propagate, add="+")
            except Exception: pass

        # auto-clean when label dies
        def _on_destroy(_=None):
            try: cls._BG_REGISTRY[mid].discard(lbl)
            except Exception: pass
        try: lbl.bind("<Destroy>", _on_destroy, add="+")
        except Exception: pass

    @classmethod
    def bg_changed(cls, widget: tk.Widget) -> None:
        try:
            widget.event_generate("<<BgChanged>>")
        except Exception:
            pass

    @staticmethod
    def _load(name: str, size: int, *, inactive: bool = False) -> object:
        key = f"{name}{ICON_INACTIVE_SUFFIX if inactive else ''}@{size}"
        if key in Icon._CACHE:
            return Icon._CACHE[key]
        # file selection: priority inactive if present, otherwise basic
        filename = None
        if inactive:
            cand = Icon.TEX.get(f"{name}{ICON_INACTIVE_SUFFIX}")
            if not cand:
                base = Icon.TEX.get(name, f"{name}.png")
                stem = Path(base).stem
                cand = f"{stem}{ICON_INACTIVE_SUFFIX}.png"
            if (Icon.BASE_DIR / cand).exists():
                filename = cand

        if filename is None:
            filename = Icon.TEX.get(name, f"{name}.png")

        path = (Icon.BASE_DIR / filename).resolve()
        try:            
            img = Image.open(path).convert("RGBA")
            if img.size != (size, size):
                img.thumbnail((size, size), Image.Resampling.LANCZOS)
                canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
                x = (size - img.width) // 2
                y = (size - img.height) // 2
                canvas.paste(img, (x, y))
                img = canvas     
            img = img.filter(ImageFilter.UnsharpMask(radius=1.0, percent=120, threshold=8))  
            tk_img = ImageTk.PhotoImage(img)
        except Exception:
            tk_img = tk.PhotoImage(width=1, height=1)

        Icon._CACHE[key] = tk_img
        return tk_img

    @staticmethod
    def Button(master,
               name: str,
               *,
               size: int = ICON_SIZE,
               command=None,
               enabled: bool = True,
               tooltip: str | None = None,
               cursor: str = "hand2",
               pack: dict | None = None,
               grid: dict | None = None,
               place: dict | None = None) -> tk.Label:

        img_enabled  = Icon._load(name, size, inactive=False)
        img_inactive = Icon._load(name, size, inactive=True)

        lbl = tk.Label(
            master,
            image=(img_enabled if enabled else img_inactive), bd=0, highlightthickness=0,
            cursor=(cursor if enabled else "")
        )      
        lbl._img_enabled = img_enabled
        lbl._img_inactive = img_inactive
        lbl._image_ref = img_enabled if enabled else img_inactive
        lbl._enabled = bool(enabled)
        Icon._register_bg_follow(lbl, master)

        def _on_click(_=None):
            if lbl._enabled and command:
                try: command()
                except Exception: pass

        if command:
            lbl.bind("<Button-1>", _on_click)

        if tooltip:
            try:
                Tooltip(lbl, tooltip)
            except Exception:
                pass
            
        # API for on-the-fly switching
        def set_enabled(flag: bool):
            flag = bool(flag)
            lbl._enabled = flag
            lbl.configure(
                image=(lbl._img_enabled if flag else lbl._img_inactive),
                cursor=(cursor if flag else "")
            )
            lbl._image_ref = lbl._img_enabled if flag else lbl._img_inactive
            try: lbl.event_generate("<<EnabledChanged>>")
            except Exception: pass

        lbl.set_enabled = set_enabled

        # auto-layout
        if pack:   lbl.pack(**pack)
        elif grid: lbl.grid(**grid)
        elif place:lbl.place(**place)

        return lbl
    
    @staticmethod
    def Toggle(master,
            name: str,
            *,
            size: int = ICON_SIZE,
            variable: tk.BooleanVar | None = None,
            value: bool | None = None,
            command=None,  # signature: command(state: bool)
            enabled: bool = True,
            tooltip: str | None = None,
            cursor: str = "hand2",
            pack: dict | None = None,
            grid: dict | None = None,
            place: dict | None = None) -> tk.Label:

        # initial state
        state = bool(variable.get()) if isinstance(variable, tk.BooleanVar) else bool(value)

        # name
        name_on  = name
        name_off = f"{name}{ICON_DISABLE_SUFFIX}"

        # load all icon variants (from cache)
        on_img      = Icon._load(name_on,  size, inactive=False)
        off_img     = Icon._load(name_off, size, inactive=False)
        on_img_dis  = Icon._load(name_on,  size, inactive=True)
        off_img_dis = Icon._load(name_off, size, inactive=True)

        # fallback
        if off_img == on_img:
            try: print(f"[Icon.Toggle] Missing OFF icon: {name_off}.png — using ON fallback")
            except Exception: pass

        # image selection by state + enable
        def _pick(state_: bool, ena: bool):
            if ena:
                return on_img if state_ else off_img
            else:
                return on_img_dis if state_ else off_img_dis

        lbl = tk.Label(
            master,
            bd=0, highlightthickness=0,
            image=_pick(state, bool(enabled)),
            cursor=(cursor if enabled else "")
        )
        Icon._register_bg_follow(lbl, master)

        # stash
        lbl._toggle_state   = state
        lbl._toggle_enabled = bool(enabled)

        def _render():
            try:
                lbl.configure(image=_pick(lbl._toggle_state, lbl._toggle_enabled),
                            cursor=(cursor if lbl._toggle_enabled else ""))
            except Exception:
                pass

        def _click(_=None):
            if not lbl._toggle_enabled:
                return
            new_state = not bool(lbl._toggle_state)
            lbl._toggle_state = new_state
            if isinstance(variable, tk.BooleanVar):
                try: variable.set(new_state)
                except Exception: pass
            _render()
            if command:
                try: command(new_state)
                except Exception: pass

        # bindy
        lbl.bind("<Button-1>", _click)
        lbl.configure(takefocus=1)
        lbl.bind("<Return>", lambda e: _click())
        lbl.bind("<space>",  lambda e: _click())

        if tooltip:
            try: Tooltip(lbl, tooltip)
            except Exception: pass

        # public API
        def set_enabled(flag: bool):
            lbl._toggle_enabled = bool(flag)
            _render()
            try: lbl.event_generate("<<EnabledChanged>>")
            except Exception: pass
        def set_state(flag: bool):
            lbl._toggle_state = bool(flag)
            if isinstance(variable, tk.BooleanVar):
                try: variable.set(bool(flag))
                except Exception: pass
            _render()
        def get_state() -> bool:
            return bool(lbl._toggle_state)
            
        lbl.set_enabled = set_enabled
        lbl.set_state   = set_state
        lbl.get_state   = get_state

        # binding to tk.BooleanVar (bidirectional)
        if isinstance(variable, tk.BooleanVar):
            def _trace_var(*_):
                try:
                    lbl._toggle_state = bool(variable.get())
                    _render()
                except Exception:
                    pass
            try:
                variable.trace_add("write", lambda *_: _trace_var())
            except Exception:
                pass

        # auto-layout
        if pack:   lbl.pack(**pack)
        elif grid: lbl.grid(**grid)
        elif place:lbl.place(**place)

        return lbl

class FileManagement:     
  
    # Get main game directory
    @staticmethod
    def GetDir_Game():
        return ModLoader.APP_DIR.parent        
        
    # Get ModLoader directory
    @staticmethod    
    def GetDir_ModLoader():
        return ModLoader.APP_DIR
    
     
     # Get path depending on OS
    @staticmethod
    def _open_path(p: Path, title: str = "Open") -> None:
        try:
            p = Path(p).expanduser().resolve()
            if not p.exists(): raise FileNotFoundError(str(p))

            if sys.platform.startswith("win"): os.startfile(str(p))  # type: ignore[attr-defined]
            elif sys.platform == "darwin": subprocess.run(["open", str(p)], check=False)
            else: subprocess.run(["xdg-open", str(p)], check=False)
        except Exception as e:
            messagebox.showerror(title, f"Failed to open:\n{e}")
      
    #Open file/folder
    @staticmethod
    def Open(p: Path, title: str = "Open") -> None:
        FileManagement._open_path(p, title=title)
    
    # Open PARENT file/folder
    @staticmethod
    def OpenParentDir(p: Path, title: str = "Open") -> None:
        p = Path(p).expanduser().resolve()
        target = p if p.is_dir() else p.parent
        FileManagement._open_path(target, title=title)

# Tooltip for widgets.
class Tooltip:
    def __init__(self, widget: tk.Widget, text: str, delay_ms: int = 450):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self._after: str | None = None
        self._tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self._schedule)
        widget.bind("<Leave>", self._hide)

        # Ensure single tooltip per widget
        if getattr(widget, "_tooltip_instance", None):
            try:
                widget._tooltip_instance.destroy()
            except Exception:
                pass
        widget._tooltip_instance = self

        # Mouse enter schedules show; all other events hide/cancel.
        widget.bind("<Enter>",      self._schedule, add="+")
        widget.bind("<Leave>",      self.hide,      add="+")
        widget.bind("<ButtonPress>",self.hide,      add="+")
        widget.bind("<FocusOut>",   self.hide,      add="+")
        widget.bind("<Unmap>",      self.hide,      add="+")
        widget.bind("<Destroy>",    self.destroy,   add="+")

    def _schedule(self, _=None):
        if self._after is not None:
            try: self.widget.after_cancel(self._after)
            except Exception: pass
        self._after = self.widget.after(self.delay_ms, self._show)

    def _show(self):
        # Guard: nothing to show, or already visible, or widget gone
        if self._tip or not self.text or not self.widget.winfo_exists():
            self._after = None
            return

        # Compute position *now* (widget may have moved)
        try:
            x = self.widget.winfo_rootx() + 10
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        except Exception:
            self._after = None
            return

        tip = tk.Toplevel(self.widget)  # parent = widget ensures it dies with widget
        tip.overrideredirect(True)
        tip.wm_geometry(f"+{x}+{y}")

        # Optional: keep above, but don't force focus
        try:
            tip.attributes("-topmost", True)
        except Exception:
            pass

        lbl = tk.Label(
            tip,
            text=self.text,
            bg=TOOLTIP_BG,
            fg="#cfe8ff",
            relief="solid",
            bd=1,
            padx=8,
            pady=4,
            font=("Helvetica", 9)
        )
        lbl.pack()

        # Hide when pointer leaves the tooltip itself or on any click within it
        lbl.bind("<Leave>",       self.hide, add="+")
        lbl.bind("<ButtonPress>", self.hide, add="+")

        self._tip = tip
        self._after = None

    def _hide(self, _=None):
        if self._after:
            try:
                self.widget.after_cancel(self._after)
            except Exception:
                pass
            self._after = None
        if self._tip:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None

    def update_text(self, text: str | None):
        """Update text; hide if empty."""
        self.text = text or ""
        if not self.text:
            self.hide()

    def hide(self, _evt=None):
        """Cancel timers and destroy the popup if present."""
        if self._after is not None:
            try: self.widget.after_cancel(self._after)
            except Exception: pass
            self._after = None

        if self._tip is not None:
            try: self._tip.destroy()
            except Exception: pass
            self._tip = None

    def destroy(self, _evt=None):
        """Full cleanup (called on widget Destroy)."""
        self.hide()
        # Clear back-reference if still pointing to self
        if getattr(self.widget, "_tooltip_instance", None) is self:
            try: delattr(self.widget, "_tooltip_instance")
            except Exception: pass