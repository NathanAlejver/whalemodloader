#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Shared helpers for the Mod Loader """

from __future__ import annotations

import io, os, sys, math
from pathlib import Path
from typing import Optional, Tuple, Any
import tkinter as tk
import tkinter.font as tkfont
import tkinter.ttk as ttk
from tkinter import ttk
import threading
from weakref import WeakSet
import ctypes as ct
from ctypes import wintypes
import sys, time, weakref, threading

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




# Import ModLoader module that sits next to this file. Returns the imported module. Does not raise if import path injection fails.
def _import_modloader():
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    import ModLoader  # type: ignore
    return ModLoader

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




# ---------------- Styles ----------------

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
              background=[("active", COLOR["scrollbar_thumb_hover"])],
              troughcolor=[("active", COLOR["scrollbar_bg"])])
    return style_name

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
                 type: str = "default",
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


# Minimalistic Entry with placeholder support
class PlaceholderEntry(ttk.Entry):
    _seq = 0
    def __init__(self, master, placeholder: str, **kw):
        fg   = kw.pop("fg",   COLOR["text"])
        bg   = kw.pop("bg",   COLOR["input_bg"])
        meta = kw.pop("meta", COLOR["meta"])
        font = kw.pop("font", FONTS["mono"])
        self._ext_var = kw.pop("textvariable", None)
        
        border_col = kw.pop("bordercolor", COLOR["border"])
        focus_col  = kw.pop("focuscolor",  COLOR.get("focus",  "#3d5566"))
        
        # style
        PlaceholderEntry._seq += 1
        stylename = f"PlaceholderEntry{PlaceholderEntry._seq}.TEntry"
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

        # --- placeholder jak u Ciebie ---
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

        # dwukierunkowe textvariable (opcjonalnie)
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




class Icon:
    BASE_DIR = Path(__file__).resolve().parent / "assets" / "icons"
    TEX = {
        "add": "add.png",
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
                # cleanup martwych referencji
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

        # wybór pliku: priorytet inactive jeśli istnieje, inaczej podstawowy
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
            tk_img = tk.PhotoImage(file=str(path))
            if tk_img.width() > size:
                factor = max(1, int(round(tk_img.width() / size)))
                tk_img = tk_img.subsample(factor, factor)
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