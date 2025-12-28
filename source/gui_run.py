#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import os, re, sys, queue, threading, math, datetime as dt
from pathlib import Path
from contextlib import redirect_stdout, redirect_stderr
from typing import Optional
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import tkinter.font as tkfont
import webbrowser
from gui_panel_mods import ModsPanel
from gui_common import COLOR_PALETTE as COLOR, FONTS, ICON_SIZE
from gui_common import QueueStream, Tooltip, Icon, Scrollable, Button, PlaceholderEntry, HSeparator, Window, Titlebar
from gui_common import hide_console_on_windows, _import_modloader, style_scrollbar
from PIL import Image, ImageTk, ImageFilter, ImageOps

Titlebar.ensure_appid("ModLoaderGUI")

ModLoader = _import_modloader()

# Paths
def get_app_dir() -> Path:
    if getattr(sys, "frozen", False):
        # running as PyInstaller .exe
        return Path(sys.executable).resolve().parent
    else:
        # running as plain .py
        return Path(__file__).resolve().parent
APP_DIR = get_app_dir()
HERE = APP_DIR / "assets" / "settings"
SETTINGS_PATH = HERE / ".gui_modloader_settings.json"






FONT_TITLE_H1    = FONTS["title_h1"]
FONT_TITLE_H2    = FONTS["title_h2"]
FONT_TITLE_H3    = FONTS["title_h3"]
FONT_MONO        = FONTS["mono"]
FONT_BASE        = FONTS["base"]
FONT_BASE_BOLD   = FONTS["base_bold"]
FONT_BASE_MINI   = FONTS["base_mini"]

SPECIAL_FG           = COLOR["special_fg"] 
SPECIAL_BG           = COLOR["accent_blue"]
SPECIAL_BG_HOVER     = COLOR["accent_lightblue"]
SPECIAL_BG_ACTIVE    = COLOR["text"]
SPECIAL_BG_DISABLED  = COLOR["accent_darkblue"]    
SPECIAL_FG           = COLOR["special_fg"] 


def _hex(c): return c  # tiny alias for readability
LOG_PALETTE = {
    "fg_base":        "#E6E6E9",
    "fg_subtle":      "#3F546D",  # timestamp
    "info":           "#A2D5FF",  # INFO
    "success":        "#56D364",
    "warn":           "#FFC13B",  # WARN
    "error":          "#FF3E34",  # ERROR
    "action":         "#39C5CF",  # UPDATE/REPLACE/ADD
    "backup":         "#61EFB9",  # BACKUP CREATED
    "nochange":       "#8B949E",  # NO CHANGE
    "path":           "#61AFEF",  # segments 'basegame'/'workshop/...'
    "arrow":          "#75C1FF",  # '==>'
    "summary":        "#56D364",  # SUMMARY
    "report":         "#56D364",  # REPORT
    
    # search overlays (background-only so they don't override text color)
    "find_hit_bg":    "#253041",
    "find_cur_bg":    "#3B4B6B",
    
    "debug": "#94e2d5",
    "ok":    "#a6e3a1",
}
INLINE_STATUS_STYLE = {
    "NO CHANGE":         ("STATUS_NOCHANGE",   LOG_PALETTE["nochange"]),
    "BACKUP CREATED":    ("STATUS_BACKUP",     LOG_PALETTE["backup"]),
    "UPDATE FILE":       ("STATUS_UPDATE",     LOG_PALETTE["action"]),
    "FILE REPLACE":      ("STATUS_UPDATE",     LOG_PALETTE["action"]),
    "REPLACE LINE":      ("STATUS_UPDATE",     LOG_PALETTE["action"]),
    "REPLACE FILE":      ("STATUS_UPDATE",     LOG_PALETTE["action"]),
    "REPLACE FILE-LINE": ("STATUS_UPDATE",     LOG_PALETTE["action"]),
    "REPLACE FUNCTION":  ("STATUS_UPDATE",     LOG_PALETTE["action"]),
    "ADD START":         ("STATUS_UPDATE",     LOG_PALETTE["action"]),
    "ADD END":           ("STATUS_UPDATE",     LOG_PALETTE["action"]),
    "SUMMARY":           ("HEADER_SUMMARY",    LOG_PALETTE["summary"]),
}

# Precompiled regexes
RE_TIME     = re.compile(r"^\[\d{1,2}:\d{2}:\d{2}\]\s*")
RE_INFOHDR  = re.compile(r"^\[\d{1,2}:\d{2}:\d{2}\]\s*\[(INFO|WARN|ERROR)\]")
RE_STATUS   = re.compile(r"\[(NO CHANGE|BACKUP CREATED|UPDATE FILE|FILE REPLACE|REPLACE LINE|REPLACE FILE|REPLACE FILE-LINE|REPLACE FUNCTION|ADD START|ADD END)\]")
RE_SUMMARYH = re.compile(r"^\[\d{1,2}:\d{2}:\d{2}\]\s*\[SUMMARY\]")
RE_REPORT   = re.compile(r"^\[REPORT\]\s")
RE_ARROW    = re.compile(r"^\[\d{1,2}:\d{2}:\d{2}\]\s*==> ")
RE_PATH     = re.compile(r"(?:^|\s)(basegame|workshop/\d{9,})(?:/|$)")

_TS_RE = re.compile(r'^\s*(?:\[\d{1,2}:\d{2}:\d{2}\]|\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})')






class ModLoaderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        
        # Anti-white flash
        try: self.withdraw()
        except Exception: pass
        
        hide_console_on_windows()

        # High-DPI friendly scaling (best-effort)
        try:
            if sys.platform.startswith("win"):
                self.tk.call("tk", "scaling", 1.2)
            elif sys.platform == "darwin":
                self.tk.call("tk", "scaling", 2.0)
            else:
                self.tk.call("tk", "scaling", 1.0)
        except Exception:
            pass
        
        # Logo
        self._logo_img = None
        self._logo_w = self._logo_h = 0
        self._load_logo()
        
        # Main display settings
        self.title("Whale Mod Loader" + " " + self._get_version_string() + "")
        self.geometry("1000x700")
        self.minsize(920, 660)
        
        # --- App icon (cross-platform) ---
        Titlebar.set_icon(self)

        # State
        self.log_queue: "queue.Queue[tuple[str,str]]" = queue.Queue()
        self.clear_before_run = tk.BooleanVar(value=True)
        self._worker: Optional[threading.Thread] = None
        self._progress_running = False
        self._progress_phase = 0.0
        self._progress_fill = 0.0
        self._collecting_mods = False
        self.err_count = 0
        self.warn_count = 0
        self.mods_count = 0
        self.last_run_end: Optional[dt.datetime] = None

        # Fonts
        self.font_title = tkfont.Font(family="Helvetica", size=17, weight="bold")
        self.font_bold = tkfont.Font(family="Helvetica", size=11, weight="bold")

        # Palette
        self.accent = COLOR["accent_blue"]    # app-specific accent stays here
        self.accent_dark = COLOR["accent_darkblue"]
        self.bg = COLOR["main_bg"]
        self.panel = COLOR["panel"]
        self.text_bg = COLOR["panel"]      # console bg (kept)
        self.text_fg = COLOR["text"]
        
        # Log-tag colors (kept but centralized point if ever needed)
        self.file_blue = "#7fe672"
        self.info_blue = "#9fd6ff"
        self.success_green = "#93efff"
        self.path_earth = "#d8caa3"
        self.nochange = "#9aa8b0"
        self.warn_col = COLOR["accent_yellow"]
        self.err_col = COLOR["accent_red"]
        self.subtle = "#102239"

        self._setup_style()
        self._setup_ui()
        self._bind_shortcuts()
        self._load_settings()

        # Initial state of 'Restore vanilla files' based on backups
        self.after(0, self._update_restore_button_state)

        # Center only on first run (no saved geometry/position)
        if not getattr(self, "_restored_geometry", False):
            self.after_idle(lambda: Window.center_on_parent(self, None))

        # Set black titlebar
        #Titlebar.install(self)
        try:
            self.deiconify()
        except Exception:
            pass


        # Polling / animation
        self.after(80, self._drain_log_queue)
        self.after(90, self._progress_tick)
        

    # ---------- Style ----------
    def _setup_style(self):
        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except Exception:
            pass
        self.configure(bg=self.panel)
        self.style.configure("TFrame", background=self.panel, relief="flat", borderwidth=0)
        self.style.configure("Panel.TFrame", background=self.panel, relief="flat", borderwidth=0)
        self.style.configure("Card.TFrame", background="#0a1828", relief="solid")
        self.style.configure("TLabel", background=self.panel, foreground=self.text_fg)

    # ---------- UI ----------
    def _setup_ui(self):
        # Header (shared)
        header_frame = ttk.Frame(self, height=70)
        header_frame.pack(side=tk.TOP, fill=tk.X)
        self.header_canvas = tk.Canvas(header_frame, height=100, bd=0, highlightthickness=0)
        self.header_canvas.pack(fill=tk.BOTH, expand=True)        
        self._hdr_redraw_job = None
        def _schedule_header_redraw(_=None):
            if self._hdr_redraw_job:
                self.after_cancel(self._hdr_redraw_job)
            self._hdr_redraw_job = self.after(20, self._redraw_header)  # ~50 FPS

        self.header_canvas.bind("<Configure>", _schedule_header_redraw)
        
        
        # PanedWindow with Console (left) and Mods (right) ===
        self.paned = tk.PanedWindow(
            self,
            orient=tk.HORIZONTAL,
            sashwidth=2,
            sashrelief="flat",
            sashpad=2,
            sashcursor="sb_h_double_arrow",
            opaqueresize=True,
            bg=self.accent,
            bd=0
        )
        self.paned.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=(0, 0))
        
        # Left: Console area
        self.console_frame = ttk.Frame(self.paned)
        
        # Right: Mods panel
        self.mods_frame = ttk.Frame(self.paned)
            
        try:
            self.paned.add(self.console_frame, weight=3)
            self.paned.add(self.mods_frame, weight=2)
            self._build_console(self.console_frame)
        except Exception:
            self.paned.add(self.console_frame, minsize=420, stretch="always")
            self.paned.add(self.mods_frame,   minsize=260, stretch="always")
            self._build_console(self.console_frame)
        
        
        
        self.mods_panel = ModsPanel(self.mods_frame, palette={"panel": self.panel})
        self.mods_panel.pack(fill=tk.BOTH, expand=True)
        
        # Prefer a wider console by default — apply once when layout stabilizes
        self._sash_target_ratio = getattr(self, "_sash_target_ratio", 0.60)
        self._sash_init_done = False

        def _apply_initial_sash(_=None):
            if self._sash_init_done:
                return
            try:
                self.update_idletasks()
                total = self.paned.winfo_width()
                if total and total > 0:
                    self.paned.sashpos(0, int(total * self._sash_target_ratio))  # np. 0.60
                    self._sash_init_done = True
            except Exception:
                pass
        self.after_idle(_apply_initial_sash)
        self.paned.bind("<Map>", _apply_initial_sash)
        self.paned.bind("<Configure>", _apply_initial_sash)

        # Progress row
        self.progress_row = ttk.Frame(self, padding=(10, 6))
        self.progress_row.pack(fill=tk.X, padx=10)
        self.progress_canvas = tk.Canvas(self.progress_row, height=18, bd=0, highlightthickness=0)
        self.progress_canvas.pack(fill=tk.X, expand=True)
        self.progress_canvas.bind("<Configure>", lambda e: self._draw_progress())

        # Footer bar (shared)
        bottom_bar = ttk.Frame(self, padding=(10, 10))
        bottom_bar.pack(side=tk.BOTTOM, fill=tk.X)
        bottom_bar.grid_columnconfigure(0, weight=1)
        bottom_bar.grid_columnconfigure(1, weight=0)
        bottom_bar.grid_rowconfigure(0, weight=0, minsize=1)

        # Left cluster: Run + Status
        left_box = ttk.Frame(bottom_bar)
        left_box.grid(row=0, column=0, sticky="w")
        self.style.configure(
            "Run.TButton",
            background=self.accent,
            foreground=SPECIAL_FG,
            font=("Helvetica", 12, "bold"),
            padding=(14, 10),
            relief="flat",
        )

        
        
        
        self.style.map("Run.TButton", background=[("active", self.accent_dark), ("pressed", self.accent_dark)])
        self.btn_run = ttk.Button(left_box, text="RUN ModLoader", command=self.on_run_clicked, style="Run.TButton")
        self.btn_run.pack(side=tk.LEFT)
        Tooltip(self.btn_run, "Run ModLoader (Ctrl+R)")

        self.status_label = ttk.Label(left_box, text="Status: Idle", font=FONTS["base"])
        self.status_label.pack(side=tk.LEFT, padx=(10, 0))

        # Right cluster: quick actions
        right_box = ttk.Frame(bottom_bar)
        right_box.grid(row=0, column=1, sticky="e")
        btn_pack = {"side":"left", "padx":(0,8)}
        
        # Buttons
        Button(right_box, text="Open mods folder", command=self.open_mods_folder, pack=btn_pack, tooltip="Opens local modloader's mods folder")      
        Button(right_box, text="Purge backup files", command=self.on_purge_backups_clicked, pack=btn_pack, tooltip="Deletes backup files created by ModLoader (ALWAYS use after game update)")
        self.btn_factory_reset = Button(right_box, text="Restore vanilla files ▶", command=self.on_factory_reset_clicked, pack=btn_pack, tooltip="Resets your game to factory settings (Ctrl+Shift+R)")

        STEAM_URL = "steam://rungameid/2230980"
        Icon.Button(right_box, "game", size=34,
                    command= lambda: webbrowser.open(STEAM_URL),
                    tooltip="Start the game", pack=btn_pack) 
        
        
        
        
    def _build_console(self, parent: ttk.Frame):

        # --- Log area --- 
        log_outer = ttk.Frame(parent, padding=8)
        log_outer.pack(fill=tk.BOTH, expand=True, padx=0, pady=(0, 0))

        # --- Title & Buttons area ---
        title_bar = ttk.Frame(log_outer)
        title_bar.pack(fill=tk.X, pady=(4, 6))
        ttk.Label(title_bar, text="Console", font=FONT_TITLE_H1).pack(side=tk.LEFT)     
        btn_pack = {"side":"right", "padx":(0,8)}             
        Button(title_bar, text="Save log…", command=self.save_log, pack=btn_pack, tooltip="Save your log as a text file (Ctrl+S)")         
        Button(title_bar, text="Clear log", command=self.clear_log, pack=btn_pack, tooltip="As you can guess it... clears log (Ctrl+L)")
    
        
        # --- Sarch bar area ---
        search_bar = ttk.Frame(log_outer)
        search_bar.pack(fill=tk.X, pady=(12, 12))        

        self.find_var = tk.StringVar()
        self.find_match_case = tk.BooleanVar(value=False)

        # Find input
        self.find_entry = PlaceholderEntry(search_bar, "Search...", textvariable=self.find_var)  
        self.find_var.trace_add("write", lambda *a: self._apply_find(highlight_all=True, jump_first=False))
        self.find_entry.pack(side=tk.LEFT, fill="x", expand=True, padx=(0,6))         
        
        
        # Live highlight on type
        self.find_var.trace_add("write", lambda *a: self._apply_find(highlight_all=True, jump_first=False))
        
        # Enter = Next, Shift+Enter = Prev
        self.find_entry.bind("<Return>", lambda e: self._find_nav(backwards=False))
        self.find_entry.bind("<Shift-Return>", lambda e: self._find_nav(backwards=True))

        # Match case        
        case_btn = Icon.Toggle(search_bar, name="case", size=ICON_SIZE*1.2, tooltip="Enable/disable match case (Alt+C)", variable=self.find_match_case,
            command=lambda state: self._apply_find(highlight_all=True, jump_first=False),
            pack={"side": "left", "padx": (0, 4)})        

        
        # Previous / Next match buttons
        Icon.Button(search_bar, "arrow_up", command=lambda: self._find_nav(backwards=True),
                tooltip="Previous match (shift+enter)", pack={"side":"left", "padx":(0, 0)})        
        Icon.Button(search_bar, "arrow_down", command=lambda: self._find_nav(backwards=False),
                tooltip="Next match (enter)", pack={"side":"left", "padx":(0, 4)})        

        # Results text
        self.find_count = ttk.Label(search_bar, text="No results", font=FONTS["base_mini"], foreground=COLOR["meta"])
        self.find_count.pack(side=tk.LEFT, padx=(0, 8))     
        
        
        # Border + log frame as before
        border = ttk.Frame(log_outer, padding=0)
        border.pack(fill=tk.BOTH, expand=True)

        log_frame = ttk.Frame(border, padding=(6, 6))
        log_frame.pack(fill=tk.BOTH, expand=True)

        # Text widget
        self.txt = tk.Text(
            log_frame,
            wrap="word",
            state="disabled",
            font=FONTS["mono"],
            padx=6, pady=6,
            undo=False,
            background=self.text_bg,
            foreground=self.text_fg,
            insertbackground=self.text_fg,
            relief="flat", bd=0, borderwidth=0,
            highlightthickness=0, highlightbackground=self.text_bg, highlightcolor=self.text_bg,
        )
        self.txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.txt.bind("<Button-3>", self._open_context_menu)
        self._setup_console_tags()

        # Scrollbar
        if not hasattr(self, "scrollbar_style"):
            self.scrollbar_style = style_scrollbar(parent)
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.txt.yview, style=self.scrollbar_style)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt.configure(yscrollcommand=scroll.set)

        # Text tags
        self.txt.tag_configure("FIND_HIT", background="#1e4061", borderwidth=1, relief="solid")
        self.txt.tag_configure("FIND_CUR", background="#1075da", borderwidth=1, relief="solid")        
        self._find_hits = [] # list of indices as strings
        self._find_idx = -1  # current index in _find_hits

        self.txt.tag_lower("FIND_HIT")
        self.txt.tag_raise("FIND_CUR")
 

    def _setup_console_tags(self):
        """Configure Text tags for a clear, modern log color scheme."""
        p = LOG_PALETTE
        t = self.txt
        
        # base text color
        t.configure(foreground=p["fg_base"])
        
        t.tag_configure("INFO",  foreground=p["info"])
        t.tag_configure("WARN", foreground=p["warn"])
        t.tag_configure("ERROR", foreground=p["error"])
        t.tag_configure("HEADER",   foreground=p["info"])
        
        t.tag_configure("DEBUG", foreground=p["debug"])
        t.tag_configure("OK",    foreground=p["ok"])


        t.tag_configure("TS",      foreground=p["fg_subtle"])
        t.tag_configure("SUMMARY",  foreground=p["summary"])
        t.tag_configure("REPORT",   foreground=p["report"])      
        t.tag_configure("ARROW",    foreground=p["arrow"])

        # File ops and meta
        t.tag_configure("PATH",    foreground=p["path"])

        # Inline statuses
        t.tag_configure("STATUS_NOCHANGE", foreground=p["nochange"])
        t.tag_configure("STATUS_BACKUP",   foreground=p["backup"])
        t.tag_configure("STATUS_UPDATE",   foreground=p["action"])
        t.tag_configure("STATUS_ADD",      foreground=p["action"])

        # Optional: monospaced code-ish fragments (between backticks)
        t.tag_configure("CODE", font=self.font_mono if hasattr(self, "font_mono") else None)

        # Search overlays (background only)
        t.tag_configure("FIND_HIT", background=p["find_hit_bg"])
        t.tag_configure("FIND_CUR", background=p["find_cur_bg"], relief="solid", borderwidth=1)

        # Z-index: keep search overlay on top of everything else
        t.tag_lower("FIND_HIT")
        t.tag_raise("FIND_CUR")
        
        for tg in ("TS", "SUMMARY", "REPORT", "ARROW", "STATUS_NOCHANGE", "STATUS_BACKUP", "STATUS_UPDATE", "STATUS_ADD"):
            t.tag_raise(tg)
            
        for tg in ("STATUS_NOCHANGE", "STATUS_BACKUP", "STATUS_UPDATE", "STATUS_ADD", "SUMMARY", "REPORT", "ARROW"):
            self.txt.tag_raise(tg, "TS")

    def _colorize_last_line(self):
        t = self.txt
        end_idx = t.index("end-1c")
        start_idx = t.index("end-1c linestart")
        line_text = t.get(start_idx, end_idx)

        # 1) Timestamp → TS
        m = _TS_RE.match(line_text)
        if m:
            ts_end = m.end()
            if ts_end < len(line_text) and line_text[ts_end] == " ":
                ts_end += 1
            t.tag_add("TS", start_idx, f"{start_idx}+{ts_end}c")

        # 2) SUMMARY / REPORT / '==> '
        for m in re.finditer(r'\[SUMMARY\]|\[REPORT\]|==>\s', line_text):
            g = m.group()
            tag = "SUMMARY" if g.startswith("[SUMMARY]") else \
                "REPORT"  if g.startswith("[REPORT]")  else \
                "ARROW"
            t.tag_add(tag, f"{start_idx}+{m.start()}c", f"{start_idx}+{m.end()}c")

        # 3) Headers [INFO]/[WARN]/[ERROR]
        m = RE_INFOHDR.search(line_text)
        if m:
            b0 = line_text.find("[", m.start())
            b1 = line_text.find("]", b0) + 1
            if b0 != -1 and b1 > b0:
                t.tag_add(m.group(1), f"{start_idx}+{b0}c", f"{start_idx}+{b1}c")

        # 4) Summary/Report banners (cały token)
        if RE_SUMMARYH.search(line_text):
            s = line_text.find("[SUMMARY]")
            t.tag_add("SUMMARY", f"{start_idx}+{s}c", f"{start_idx}+{s+9}c")

        if RE_REPORT.search(line_text):
            s = line_text.find("[REPORT]")
            t.tag_add("REPORT", f"{start_idx}+{s}c", f"{start_idx}+{s+8}c")

        # 5) Arrow opener '==> '
        m = RE_ARROW.search(line_text)
        if m:
            s = line_text.find("==>")
            if s != -1:
                t.tag_add("ARROW", f"{start_idx}+{s}c", f"{start_idx}+{s+3}c")

        # 6) Inline [STATUS] tokens
        for m in RE_STATUS.finditer(line_text):
            status = m.group(1)
            tag, _ = INLINE_STATUS_STYLE[status]
            a, b = m.span()
            t.tag_remove("TS", f"{start_idx}+{a}c", f"{start_idx}+{b}c")
            t.tag_add(tag, f"{start_idx}+{a}c", f"{start_idx}+{b}c")

        # 7) PATH (tylko segment źródłowy)
        for m in RE_PATH.finditer(line_text):
            a, b = m.span(1)
            t.tag_add("PATH", f"{start_idx}+{a}c", f"{start_idx}+{b}c")

        # 8) Backticks `...`
        i = 0
        while True:
            s = line_text.find("`", i)
            if s == -1: break
            e = line_text.find("`", s+1)
            if e == -1: break
            t.tag_add("CODE", f"{start_idx}+{s}c", f"{start_idx}+{e+1}c")
            i = e + 1


    def _load_logo(self, target_h: int = 96, method: str = "bicubic", supersample: float = 1.0, preblur: float = 0.0, unsharp: float = 0.0):
        self._logo_img = None
        self._logo_w = self._logo_h = 0
        icons_dir = APP_DIR / "assets" / "icons"
        p = icons_dir / "logo.png"
        if not p.exists():
            return

        # Open and preserve alpha
        im = Image.open(p).convert("RGBA")
        src_w, src_h = im.size

        # --- Pick resampling kernel
        resample_map = {
            "nearest": Image.Resampling.NEAREST,
            "bilinear": Image.Resampling.BILINEAR,
            "bicubic": Image.Resampling.BICUBIC,
            "lanczos": Image.Resampling.LANCZOS,
        }
        resample = resample_map.get(method.lower(), Image.Resampling.LANCZOS)

        # --- Compute final size and optional supersampled size
        scale = target_h / src_h
        ss = max(1.0, float(supersample))
        # supersampled intermediate height
        inter_h = max(1, int(round(target_h * ss)))
        inter_w = max(1, int(round(src_w * (inter_h / src_h))))

        # --- Optional pre-blur to soften jaggies (stronger AA feel)
        if preblur > 0:
            im = im.filter(ImageFilter.GaussianBlur(radius=float(preblur)))

        # --- Upscale/downscale to intermediate (if supersample>1 it upscales)
        if (src_w, src_h) != (inter_w, inter_h):
            im = im.resize((inter_w, inter_h), resample=resample)

        # --- Downscale from intermediate to final with high-quality kernel
        if ss > 1.0:
            im = im.resize((max(1, int(round(inter_w/ss))),
                            max(1, int(round(inter_h/ss)))),
                            resample=resample)

        # --- Optional unsharp mask to recover crisp logo edges
        if unsharp > 0:
            # Map 0..1 to sensible UnsharpMask params
            amount   = 50 + int(150 * min(unsharp, 1.0))   # 50..200
            radius   = 0.4 + 1.1 * min(unsharp, 1.0)       # ~0.4..1.5
            threshold= 0                                   # keep edges clean
            im = im.filter(ImageFilter.UnsharpMask(radius=radius, percent=amount, threshold=threshold))

        tkimg = ImageTk.PhotoImage(im)
        self._logo_img = tkimg
        self._logo_w, self._logo_h = tkimg.width(), tkimg.height()



    # ---------- Header drawing ----------
    def _redraw_header(self, _=None):
        c = self.header_canvas
        c.delete("all")
        w = c.winfo_width() or 1024
        h = c.winfo_height() or 70

        # Gradient background
        start = (6, 14, 24)
        end = (6, 30, 50)
        self.header_bg = f"#{end[0]:02x}{end[1]:02x}{end[2]:02x}"
        steps = max(16, min(40, int(w / 35)))
        for i in range(steps):
            r = int(start[0] + (end[0] - start[0]) * (i / steps))
            g = int(start[1] + (end[1] - start[1]) * (i / steps))
            b = int(start[2] + (end[2] - start[2]) * (i / steps))
            color = f"#{r:02x}{g:02x}{b:02x}"
            y1 = int(i * (h / steps))
            y2 = int((i + 1) * (h / steps))
            c.create_rectangle(0, y1, w, y2, outline=color, fill=color)

        # Title + version + author        
        title_x = 18
        if getattr(self, "_logo_img", None):
            # vertically center within header height
            c.create_image(title_x, h // 2, anchor="w", image=self._logo_img)
            ver_x = title_x + self._logo_w + 16  # spacing after logo
        else:
            c.create_text(title_x, 32, anchor="w", text="Whale Mod Loader", font=self.font_title, fill="#dff4ff")
            ver_x = title_x + 128  # previous static offset 

        # --- right-aligned stat chips
        x = w - 38  # start from edge
        y = 24

        x = self._draw_stat_text(c, right=x, y=y, label="Errors", value=self.err_count, kind="err")
        x = self._draw_stat_text(c, right=x - 10, y=y, label="Warnings", value=self.warn_count, kind="warn")
        try:
            mods_now = len(self.mods_panel._discover_mods())
            self.mods_count = mods_now
        except Exception:
            pass
        x = self._draw_stat_text(c, right=x - 10, y=y, label="Mods", value=self.mods_count, kind="mods")

        # Last run
        if self.last_run_end:
            s = self.last_run_end.strftime("%H:%M:%S")
            _ = self._draw_stat_text(c, right=x - 10, y=y, label="Last run", value=s, kind="muted")


    def _hex_to_rgb(self, hx: str):
        hx = hx.lstrip("#"); return tuple(int(hx[i:i+2], 16) for i in (0,2,4))

    def _rgb_to_hex(self, rgb):
        r,g,b = [max(0, min(255, int(v))) for v in rgb]
        return f"#{r:02x}{g:02x}{b:02x}"

    def _blend(self, fg: str, bg: str, t: float) -> str:
        fr,fg_,fb = self._hex_to_rgb(fg); br,bg_,bb = self._hex_to_rgb(bg)
        return self._rgb_to_hex((br+(fr-br)*t, bg_+(fg_-bg_)*t, bb+(fb-bb)*t))



    def _draw_stat_text(self, canvas: tk.Canvas, right: int, y: int, label: str, value, kind: str) -> int:
        header_bg = getattr(self, "header_bg", "#0e1b29")
        accent_map = {
            "mods": getattr(self, "accent",   "#69b7ff"),
            "warn": getattr(self, "warn_col", "#f5c84b"),
            "err":  getattr(self, "err_col",  "#e25b5b"),
            "muted": "#8aa2bf",
        }
        accent = accent_map.get(kind, "#8aa2bf")

        def _hex_to_rgb(hx: str):
            hx = hx.lstrip("#"); return tuple(int(hx[i:i+2], 16) for i in (0,2,4))
        def _rgb_to_hex(rgb):
            r,g,b = [max(0, min(255, int(round(v)))) for v in rgb]
            return f"#{r:02x}{g:02x}{b:02x}"
        def _blend(fg: str, bg: str, t: float) -> str:
            fr,fg_,fb = _hex_to_rgb(fg); br,bg_,bb = _hex_to_rgb(bg)
            return _rgb_to_hex((br+(fr-br)*t, bg_+(fg_-bg_)*t, bb+(fb-bb)*t))

        # Colors & fonts (label = very subtle, value = accent)
        label_fg = _blend(accent, header_bg, 0.75)
        value_fg = _blend(accent, header_bg, 0.75)
        label_font = ("Helvetica", 12)
        value_font = ("Helvetica", 13, "bold")
        sep_fg   = _blend("#ffffff", header_bg, 0.35)

        # Measure helper
        def _measure(text: str, font):
            t = canvas.create_text(0, 0, text=text, font=font, anchor="nw")
            b = canvas.bbox(t) or (0,0,0,0)
            canvas.delete(t)
            return (b[2]-b[0], b[3]-b[1])

        value_str = str(value)
        label_str = str(label)    
        sep_str   = " | "

        lw, lh = _measure(label_str, label_font)
        sw, sh = _measure(sep_str,   label_font)
        vw, vh = _measure(value_str, value_font)
        h = max(lh, sh, vh)
        cy = y + h/2

        # Draw text
        x = right
        canvas.create_text(x, cy, text=value_str, font=value_font, fill=value_fg, anchor="e")
        x -= vw
        canvas.create_text(x, cy, text=sep_str, font=label_font, fill=label_fg, anchor="e")
        x -= sw
        canvas.create_text(x, cy, text=label_str, font=label_font, fill=label_fg, anchor="e")
        x -= lw

        # Small gap before next block on the left
        return int(x - 20)



    def _get_version_string(self) -> str:
        try:
            ModLoader = _import_modloader()
            ver = getattr(ModLoader, "VERSION", None)
            if ver:
                return f"{ver}"
        except Exception:
            pass
        return "version... errror? Oh."

    def _get_author_string(self) -> str:
        try:
            ModLoader = _import_modloader()
            ver = getattr(ModLoader, "AUTHOR", None)
            if ver:
                return f"{ver}"
        except Exception:
            pass
        return "Where did you go, NathanAlejver?"

    # ---------- Log handling ----------
    def append_log(self, text: str, default_tag: str = "STDOUT"):
        lines = text.splitlines(keepends=True)
        self.txt.configure(state="normal")

        for raw_line in lines:
            line = raw_line.rstrip("\n")
            skip_ts = bool(re.search(r"\[REPORT\]|\bRun at\b|={3,}", line, re.I))
            chosen = "PATH"
            stderrish = (default_tag == "STDERR")

            if re.search(r"==>\s", line):
                chosen = "INFO"
            elif re.search(r"\[REPORT\]|\bfinished\b|\bFINISHED\b", line, re.I):
                chosen = "HEADER"
            elif re.search(r"\[INFO\]", line, re.I):
                chosen = "INFO"
            elif re.search(r"\[BACKUP CREATED\]", line, re.I):
                chosen = "BACKUP_CREATED"
            elif re.search(r"\bNO CHANGE\b", line, re.I) or re.search(r"already up-?to-?date", line, re.I):
                chosen = "NOCHANGE"
            elif re.search(r"\[ERROR\]|\b(error|exception|traceback|failed|unhandled)\b", line, re.I):
                chosen = "ERROR"
                self.err_count += 1
                self._redraw_header()
            elif re.search(r"\b(warn|warning)\b", line, re.I):
                chosen = "WARN"
                self.warn_count += 1
                self._redraw_header()
            else:
                if "/" in line or "\\" in line or line.endswith((".c", ".ini", ".txt")) or re.match(r"\s*-\s*\d+\s*:", line):
                    chosen = "PATH"
                else:
                    chosen = "INFO" if not stderrish else "INFO"

            if re.search(r"\[INFO\]\s*Mods load priority", line):
                self._collecting_mods = True
                self.mods_count = 0
                self._redraw_header()
            elif self._collecting_mods:
                if re.search(r"^\s*-\s*\d+\s*:\s*", line):
                    self.mods_count += 1
                    self._redraw_header()
                elif re.search(r"\[INFO\]|\[REPORT\]|^==>", line):
                    self._collecting_mods = False

            insert_text = raw_line if (line.strip() == "" or skip_ts) else f"[{dt.datetime.now().strftime('%H:%M:%S')}] {raw_line}"
            try:
                self.txt.insert("end", insert_text, (chosen,))
            except Exception:
                self.txt.insert("end", insert_text)
            self._colorize_last_line()
        self.txt.see("end")
        self.txt.configure(state="disabled")

    def _drain_log_queue(self):
        try:
            while True:
                tag, chunk = self.log_queue.get_nowait()
                self.append_log(chunk, default_tag=tag)
        except queue.Empty:
            pass
        self.after(80, self._drain_log_queue)

    def clear_log(self):
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.configure(state="disabled")

    # ---------- Progress drawing & animation ----------
    def _draw_progress(self, fill_ratio: float = 0.0):
        c = self.progress_canvas
        c.delete("all")
        w = c.winfo_width() or 400
        h = c.winfo_height() or 18
        c.create_rectangle(0, 0, w, h, outline="#12303b", fill="#082027", width=2)
        fill_w = int(w * max(0.0, min(1.0, fill_ratio)))
        if fill_w > 0:
            c.create_rectangle(2, 2, fill_w - 2 if fill_w > 4 else fill_w, h - 2, outline="", fill=self.accent)

    def _progress_tick(self):
        if hasattr(self, 'progress_canvas'):
            if self._progress_running:
                self._progress_phase += 0.13
                ratio = (math.sin(self._progress_phase) + 1.0) / 2.0
                bias = 0.2
                fill_ratio = bias + (1.0 - bias) * ratio
                self._progress_fill = fill_ratio
                self._draw_progress(fill_ratio)
            else:
                self._progress_fill = 0.0
                self._draw_progress(0.0)
        self.after(70, self._progress_tick)

    # ---------- Controls & threading ----------
    def _set_controls_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self.btn_run.configure(state=state)
        if not enabled:
            self._progress_running = True
            self.status_label.configure(text="Status: In progress")
        else:
            self._progress_running = False
            self.status_label.configure(text="Status: Idle")



    # Enable 'Restore vanilla files' only if backup dir has files.
    def _update_restore_button_state(self) -> None:
        
        ModLoader = _import_modloader()
        backup_dir = ModLoader.BACKUP_DIR
        has_files = False

        try:
            if backup_dir.exists():
                # any file in the backup tree
                for _ in backup_dir.rglob("*"):
                    has_files = True
                    break
        except Exception:
            has_files = False

        state = "normal" if has_files else "disabled"
        try:
            if hasattr(self, "btn_factory_reset"):
                self.btn_factory_reset.configure(state=state)
        except Exception:
            pass



    def on_run_clicked(self):
        self._start_worker(factory=False, purge_backups=False)

    def on_factory_reset_clicked(self):
        ok = messagebox.askyesno("Factory Reset", "All your game files will be restored to vanilla! Are you sure?")
        if not ok:
            return
        self._start_worker(factory=True, purge_backups=False)
        
    def on_purge_backups_clicked(self):
        ok = messagebox.askyesno(
            "Purge backup files",
            "This will delete backup files created by ModLoader.\n"
            "ALWAYS use this after Steam updates the game.\n\n"
            "Are you sure?"
        )
        if not ok:
            return
        # Purge backup files only (no regular mod operations)
        self._start_worker(factory=False, purge_backups=True)        
        

    def _start_worker(self, factory: bool, purge_backups: bool = False):
        if self._worker and self._worker.is_alive():
            messagebox.showinfo("Whale", "Mod Loader is already running")
            return            
        self.clear_log() if self.clear_before_run.get() else None
        self.err_count = 0
        self.warn_count = 0
        self.mods_count = 0
        self._collecting_mods = False
        self._redraw_header()

        self._set_controls_enabled(False)
        self._worker = threading.Thread(target=self._run_modloader_once, args=(factory, purge_backups), daemon=True)
        self._worker.start()

    def _run_modloader_once(self, factory: bool, purge_backups: bool = False):
        try:
            ModLoader = _import_modloader()
            import importlib
            ModLoader = importlib.reload(ModLoader)
        except Exception as e:
            self.log_queue.put(("STDERR", "[ERROR] Could not import/reload ModLoader: {}\n".format(e)))
            self.after(0, lambda: self._set_controls_enabled(True))
            return

        try:
            setattr(ModLoader, "FACTORY_RESET", bool(factory))
            setattr(ModLoader, "PURGE_BACKUPS_ONLY", bool(purge_backups))
            if factory:
                self.log_queue.put(("STDOUT", "[INFO] FACTORY_RESET=True\n"))
            if purge_backups:
                self.log_queue.put(("STDOUT", "[INFO] PURGE_BACKUPS_ONLY=True\n"))
        except Exception:
            pass

        try:
            base_dir = getattr(ModLoader, "APP_DIR", None)
            if base_dir is None:
                base_dir = Path(ModLoader.__file__).resolve().parent
            os.chdir(Path(base_dir))
        except Exception:
            pass

        q_stdout = QueueStream(self.log_queue, "STDOUT")
        q_stderr = QueueStream(self.log_queue, "STDERR")

        now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_queue.put(("STDOUT", "\n========== Run at {} ==========\n".format(now)))

        try:
            with redirect_stdout(q_stdout), redirect_stderr(q_stderr):
                if hasattr(ModLoader, "main") and callable(ModLoader.main):
                    ModLoader.main()
                else:
                    self.log_queue.put(("STDERR", "[ERROR] ModLoader.main() not found.\n"))
        except Exception as e:
            self.log_queue.put(("STDERR", "[ERROR] Unhandled exception: {}\n".format(e)))
        finally:
            end_time = dt.datetime.now()
            self.last_run_end = end_time
            self.after(0, lambda: self._set_controls_enabled(True))
            self.after(0, lambda: self.status_label.configure(text="Status: Done"))
            self.after(1200, lambda: self.status_label.configure(text="Status: Idle"))

            # Refresh factory reset button depending on current backups
            self.after(0, self._update_restore_button_state)

            def _maybe_notify():
                if self.err_count > 0:
                    try:
                        messagebox.showwarning("ModLoader", "Run finished with {} error(s). Check the log.".format(self.err_count))
                    except Exception:
                        pass
                self._redraw_header()

            self.after(0, _maybe_notify)

    # ---------- Actions ----------
    def open_mods_folder(self):
        
        
        #try:
        #    ModLoader = _import_modloader()
        #    mods_dir = Path(ModLoader.__file__).resolve().parent / "mods"
        #except Exception:
        #    mods_dir = HERE / "mods"
        #mods_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            ModLoader = _import_modloader()
            base_dir = getattr(ModLoader, "APP_DIR", None)
            if base_dir is None:
                base_dir = Path(ModLoader.__file__).resolve().parent
            base_dir = Path(base_dir)
        except Exception:
            base_dir = APP_DIR

        mods_dir = base_dir / "mods"
        mods_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(mods_dir))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                os.system('open "{}"'.format(mods_dir))
            else:
                os.system('xdg-open "{}"'.format(mods_dir))
        except Exception as e:
            messagebox.showerror("Open mods folder", "Failed to open folder:\n{}".format(e))

    def save_log(self):
        content = self.txt.get("1.0", "end-1c")
        if not content.strip():
            messagebox.showinfo("Save log", "Log is empty.")
            return
        default_name = "modloader_log_{}.txt".format(dt.datetime.now().strftime('%Y%m%d_%H%M%S'))
        path = filedialog.asksaveasfilename(
            title="Save log",
            defaultextension=".txt",
            initialfile=default_name,
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            Path(path).write_text(content, encoding="utf-8")
            messagebox.showinfo("Save log", "Saved to:\n{}".format(path))
        except Exception as e:
            messagebox.showerror("Save log", "Could not save file:\n{}".format(e))

    # ---------- Inline Find (search bar) ----------
    def _apply_find(self, highlight_all: bool = True, jump_first: bool = False):
        self._clear_find_tags()
        needle = self.find_var.get()
        if not needle:
            self._find_hits, self._find_idx = [], -1
            if hasattr(self, "find_count"):
                self.find_count.configure(text="No results")
            return

        nocase = int(not self.find_match_case.get())
        start = "1.0"
        hits = []

        # Temporarily enable to search cleanly
        prev = self.txt.cget("state")
        self.txt.configure(state="normal")
        try:
            while True:
                pos = self.txt.search(needle, start, stopindex="end-1c", nocase=nocase)
                if not pos:
                    break
                end = f"{pos}+{len(needle)}c"
                if highlight_all:
                    self.txt.tag_add("FIND_HIT", pos, end)
                hits.append(pos)                
                start = end # Move start forward to avoid infinite loop on zero-length
        finally:
            self.txt.configure(state=prev)

        self._find_hits = hits
        
        # Choose current hit near cursor if requested
        if jump_first and hits:
            cur = self.txt.index("insert")
            # find first hit >= cursor, else wrap to 0
            idx = 0
            for i, h in enumerate(hits):
                if self.txt.compare(h, ">=", cur):
                    idx = i
                    break
            self._find_idx = idx
            self._goto_hit(idx, needle)
        else:
            # keep index if still valid; else reset
            if not (0 <= self._find_idx < len(hits)):
                self._find_idx = 0 if hits else -1
            if hits:
                self._goto_hit(self._find_idx, needle, ensure_visible=False)

        self._update_counter()


    # Navigate to next/prev match with wrap-around.
    def _find_nav(self, backwards: bool = False):
        needle = self.find_var.get()
        if not needle:
            return

        # Ensure tags are up-to-date if user toggled case
        self._apply_find(highlight_all=True, jump_first=False)        

        if not self._find_hits:
            return

        if backwards:
            self._find_idx = (self._find_idx - 1) % len(self._find_hits)
        else:
            self._find_idx = (self._find_idx + 1) % len(self._find_hits)

        self._goto_hit(self._find_idx, needle)
        self._update_counter()

    # Visually mark the current hit and move caret.
    def _goto_hit(self, idx: int, needle: str, ensure_visible: bool = True):
        if not (0 <= idx < len(self._find_hits)):
            return
        pos = self._find_hits[idx]
        end = f"{pos}+{len(needle)}c"

        prev = self.txt.cget("state")
        self.txt.configure(state="normal")
        try:
            # remove previous current marker
            self.txt.tag_remove("FIND_CUR", "1.0", "end")
            #self.txt.tag_remove("sel", "1.0", "end")

            # apply current marker + selection feedback
            self.txt.tag_add("FIND_CUR", pos, end)
            #self.txt.tag_add("sel", pos, end)
            if ensure_visible:
                self.txt.see(pos)
            self.txt.mark_set("insert", end)
        finally:
            self.txt.configure(state=prev)

    def _update_counter(self):
        total = len(self._find_hits)
        if total == 0:
            txt = "No results"
        else:
            cur = (self._find_idx + 1) if (0 <= self._find_idx < total) else 1
            txt = f"{cur} of {total}"
        if hasattr(self, "find_count"):
            self.find_count.configure(text=txt)

    def _clear_find_tags(self):
        self.txt.tag_remove("FIND_HIT", "1.0", "end")
        self.txt.tag_remove("FIND_CUR", "1.0", "end")
        #self.txt.tag_remove("sel", "1.0", "end")

    def _clear_findbar(self):
        
        # Clear query + highlights
        self.find_var.set("")
        self._find_hits, self._find_idx = [], -1
        self._clear_find_tags()
        if hasattr(self, "find_count"):
            self.find_count.configure(text="No results")
            
        # Deselect entry text and move focus back to console
        try:
            self.find_entry.selection_clear()
        except Exception:
            pass
        self.txt.focus_set()


    # ---------- Context menu handler ----------
    def _open_context_menu(self, event):
        try:
            self.ctx.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                self.ctx.grab_release()
            except Exception:
                pass

    # ---------- Settings & Shortcuts ----------
    def _bind_shortcuts(self):
        self.bind("<Control-r>", lambda e: self.on_run_clicked())
        self.bind("<Control-Shift-R>", lambda e: self.on_factory_reset_clicked())
        self.bind("<Control-s>", lambda e: self.save_log())
        self.bind("<Control-l>", lambda e: self.clear_log())
        self.bind("<Control-f>", lambda e: (
            hasattr(self, "find_entry") and self.find_entry.focus_set(),
            hasattr(self, "find_entry") and self.find_entry.select_range(0, 'end')
        ))        
        self.bind_all("<Alt-c>", lambda e: self._toggle_match_case())
        self.bind("<Escape>", lambda e: self._clear_findbar())
        self.protocol("WM_DELETE_WINDOW", self._on_close)
    
    # unused? 
    def _toggle_clear_pref(self, *_):
        self.clear_before_run.set(not self.clear_before_run.get())
        self._save_settings()

    def _toggle_match_case(self, *_):
        try:
            self.find_match_case.set(not self.find_match_case.get())
            self._apply_find(highlight_all=True, jump_first=False)
        except Exception:
            pass

    def _load_settings(self):
        self._restored_geometry = False
        try:
            if SETTINGS_PATH.exists():
                data = json.loads(SETTINGS_PATH.read_text("utf-8"))
                geo = data.get("geometry")
                if geo:
                    self.geometry(geo)
                    self._restored_geometry = True
                self.clear_before_run.set(bool(data.get("clear_before_run", True)))
                self._sash_target_ratio = float(data.get("sash_ratio", 0.60))
        except Exception:
            pass

    def _save_settings(self):
        try:
            try:
                total = max(1, int(self.paned.winfo_width()))
                pos = int(self.paned.sashpos(0)) if hasattr(self.paned, 'sashpos') else 0
                sash_ratio = max(0.0, min(1.0, pos / total))
            except Exception:
                sash_ratio = getattr(self, "_sash_target_ratio", 0.60)
            data = {
                "geometry": self.winfo_geometry(),
                "clear_before_run": bool(self.clear_before_run.get()),
                "sash_ratio": sash_ratio
            }
            SETTINGS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _on_close(self):
        self._save_settings()
        self.destroy()


# ---------- Entrypoint ----------
import json  # placed here to keep imports local for frozen apps

def main():
    app = ModLoaderApp()
    app.mainloop()


if __name__ == "__main__":
    main()
