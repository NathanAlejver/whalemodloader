#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
import os
import tkinter as tk
from tkinter import ttk, messagebox
import pprint
import traceback
from tkinter import ttk, messagebox, filedialog

from gui_common import COLOR_PALETTE as COLOR, ICON_SIZE, FONTS
from gui_common import Tooltip, VSeparator, PlaceholderEntry, Icon, Button, Scrollable, Window, Titlebar
from gui_common import style_scrollbar

# -------------------- Palette --------------------
C_BG         = COLOR["panel"]
C_CARD       = COLOR["card_bg_hover"]
C_CARD_HOVER = COLOR["card_bg_active"]
C_TEXT       = COLOR["text"]
C_SUB        = COLOR["meta"]
C_MUTED      = COLOR["desc_disabled"]
C_PILL_BG    = COLOR["pill_bg"]
C_PILL_BG_2  = COLOR["pill_bg_2"]
C_YELLOW     = COLOR["accent_yellow"]

MONO            = FONTS["mono"]
BASE            = FONTS["base"]
TITLE           = FONTS["title_h2"]

FONT_TITLE_H1    = FONTS["title_h1"]
FONT_TITLE_H2    = FONTS["title_h2"]
FONT_TITLE_H3    = FONTS["title_h3"]
FONT_MONO        = FONTS["mono"]
FONT_BASE        = FONTS["base"]
FONT_BASE_BOLD   = FONTS["base_bold"]
FONT_BASE_MINI   = FONTS["base_mini"]

META_FG          = COLOR["meta"]

# ---- Spacing ----
CARD_OUTER_VPAD   = 12
CARD_INNER_PAD    = 14
SECTION_GAP       = 12
HEADER_BOTTOM_GAP = 8
CHIP_GAP          = 8
TAG_GAP           = 8
SIDE_PADDING      = 14

# -------------------- IO helpers --------------------
def _safe_exec_replacements(py_path: Path) -> Dict[str, Any]:
    env: Dict[str, Any] = {
        "LINE_REPLACEMENTS": {},
        "FUNCTION_REPLACEMENTS": {},
        "FILE_LINE_REPLACEMENTS": {},
        "FILE_ADDITIONS": {},
        "FILE_REPLACEMENTS": {},
    }
    if not py_path.exists():
        return env
    code = py_path.read_text("utf-8")
    safe_builtins = {"True": True, "False": False, "None": None}
    local_env: Dict[str, Any] = {}
    exec(compile(code, str(py_path), "exec"), {"__builtins__": safe_builtins}, local_env)
    for k in env.keys():
        env[k] = local_env.get(k, {})
    return env

def _pairs_to_py(pairs: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for it in pairs:
        if isinstance(it, (list, tuple)) and len(it) == 2:
            a, b = it
            out.append((str(a), str(b)))
    return out

def _normalize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    norm: Dict[str, Any] = {}
    # LINE_REPLACEMENTS
    lr = payload.get("LINE_REPLACEMENTS", {})
    lr_out: Dict[str, Dict[str, List[Tuple[str, str]]]] = {}
    if isinstance(lr, dict):
        for f, fmap in lr.items():
            inner: Dict[str, List[Tuple[str, str]]] = {}
            if isinstance(fmap, dict):
                for fn, pairs in fmap.items():
                    inner[str(fn)] = _pairs_to_py(pairs or [])
            lr_out[str(f)] = inner
    norm["LINE_REPLACEMENTS"] = lr_out
    # FUNCTION_REPLACEMENTS
    fr = payload.get("FUNCTION_REPLACEMENTS", {})
    fr_out: Dict[str, Dict[str, str]] = {}
    if isinstance(fr, dict):
        for f, fmap in fr.items():
            inner: Dict[str, str] = {}
            if isinstance(fmap, dict):
                for fn, filename in fmap.items():
                    inner[str(fn)] = str(filename)
            fr_out[str(f)] = inner
    norm["FUNCTION_REPLACEMENTS"] = fr_out
    # FILE_LINE_REPLACEMENTS
    flr = payload.get("FILE_LINE_REPLACEMENTS", {})
    flr_out: Dict[str, List[Tuple[str, str]]] = {}
    if isinstance(flr, dict):
        for f, pairs in flr.items():
            flr_out[str(f)] = _pairs_to_py(pairs or [])
    norm["FILE_LINE_REPLACEMENTS"] = flr_out
    # FILE_ADDITIONS
    fa = payload.get("FILE_ADDITIONS", {})
    fa_out: Dict[str, List[Tuple[str, str]]] = {}
    if isinstance(fa, dict):
        for f, pairs in fa.items():
            fa_out[str(f)] = _pairs_to_py(pairs or [])
    norm["FILE_ADDITIONS"] = fa_out
    # FILE_REPLACEMENTS
    frr = payload.get("FILE_REPLACEMENTS", {})
    frr_out: Dict[str, str] = {}
    if isinstance(frr, dict):
        for f, val in frr.items():
            frr_out[str(f)] = str(val)
    norm["FILE_REPLACEMENTS"] = frr_out
    return norm

def _generate_py(data: Dict[str, Any]) -> str:
    header = (
        "# -*- coding: utf-8 -*-\n"
    )
    parts: List[str] = []
    for key in [
        "LINE_REPLACEMENTS",
        "FUNCTION_REPLACEMENTS",
        "FILE_LINE_REPLACEMENTS",
        "FILE_ADDITIONS",
        "FILE_REPLACEMENTS",
    ]:
        obj = data.get(key, {})
        parts.append(f"{key} = " + pprint.pformat(obj, indent=4, width=100, compact=False, sort_dicts=True))
        parts.append("\n")
    return header + "\n".join(parts)

class AddFileDialog(tk.Toplevel):
    def __init__(self, master, game_root, on_ok):
        super().__init__(master)
        self.title("Add file")
        self.configure(bg=C_BG)
        self.resizable(False, False)
        self.game_root = game_root
        self.on_ok = on_ok
        self._can_ok = False
        self.result = None        

        self.transient(master)
        self.withdraw() 
        
        # icon
        Titlebar.set_icon(self)
        
        # hotkeys
        self.bind("<Escape>", lambda e: self._cancel())
        self.bind("<Return>", lambda e: self._ok() if self._can_ok else None)

        pad = 12
        frm = tk.Frame(self, bg=C_BG)
        frm.pack(fill="both", expand=True, padx=pad, pady=pad)

        lbl = tk.Label(frm, text="Path relative to game root:", bg=C_BG, fg=C_SUB)
        lbl.grid(row=0, column=0, sticky="w")

        self.var = tk.StringVar()
        ent = tk.Entry(frm, textvariable=self.var, relief="flat", bg=C_CARD, fg=C_TEXT, insertbackground=C_TEXT, width=56)
        ent.grid(row=1, column=0, columnspan=2, sticky="we", pady=(6,8))
        ent.bind("<KeyRelease>", self._on_change)
        ent.focus_set()
        
        # Browse
        btn_browse = tk.Label(frm, text="Browse…", bg=C_CARD, fg=C_SUB, padx=10, pady=6, cursor="hand2")
        btn_browse.grid(row=1, column=2, sticky="e", padx=(8,0))
        btn_browse.bind("<Enter>", lambda e: btn_browse.config(bg=C_CARD_HOVER))
        btn_browse.bind("<Leave>", lambda e: btn_browse.config(bg=C_CARD))
        btn_browse.bind("<Button-1>", lambda e: self._browse())          

        # status pill
        self.pill = tk.Label(frm, text="", bg=C_PILL_BG, fg=C_SUB, padx=10, pady=4)
        self.pill.grid(row=2, column=0, sticky="w")

        # actions
        self.btn_cancel = tk.Label(frm, text="Cancel", bg=C_CARD, fg=C_SUB, padx=10, pady=6, cursor="hand2")
        self.btn_ok     = tk.Label(frm, text="Add",    bg=C_PILL_BG_2, fg=C_YELLOW, padx=12, pady=6, cursor="arrow")
        self.btn_cancel.grid(row=3, column=1, sticky="e", pady=(10,0))
        self.btn_ok.grid(row=3, column=2, sticky="e", padx=(8,0), pady=(10,0))        
        self.btn_cancel.bind("<Enter>", lambda e: self.btn_cancel.config(bg=C_CARD_HOVER))
        self.btn_cancel.bind("<Leave>", lambda e: self.btn_cancel.config(bg=C_CARD))        
        self.btn_ok.bind("<Enter>", lambda e: self._ok_hover(True))
        self.btn_ok.bind("<Leave>", lambda e: self._ok_hover(False))
        self.btn_cancel.bind("<Button-1>", lambda e: self._cancel())
        self.btn_ok.bind("<Button-1>", lambda e: self._ok())
        
        frm.columnconfigure(0, weight=1)
        self._on_change()
        self.update_idletasks()        
        self.minsize(480, self.winfo_height())
        Window.center_on_parent(self, master.winfo_toplevel())
        self.deiconify()
        self.grab_set()
        
        

    def _ok_hover(self, inside):
        if not self._can_ok:
            return
        self.btn_ok.config(bg=C_CARD_HOVER if inside else C_PILL_BG_2)
        
    def _set_ok_enabled(self, enabled: bool):
        self._can_ok = enabled
        if enabled:
            self.btn_ok.config(cursor="hand2", fg=C_YELLOW, bg=C_PILL_BG_2)
        else:
            self.btn_ok.config(cursor="arrow", fg=C_MUTED, bg=C_PILL_BG)

    def _on_change(self, *_):
        raw = self.var.get().strip()
        if not raw:
            self._set_status("missing", "Enter relative path (e.g. data/scripts/ai.lua)")
            self._set_ok_enabled(False)
            return
        
        
        rel = raw.replace("\\", "/")
        abs_path = (self.game_root / rel )

        # If it points to something outside game_root, treat it as invalid
        try:
            abs_path_resolved = abs_path.resolve()
            inside_root = str(abs_path_resolved).startswith(str(self.game_root.resolve()))
        except Exception:
            inside_root = False

        if not inside_root:
            self._set_status("outside", "Selected path is outside the project root.")
            self._set_ok_enabled(False)
            return

        if abs_path.exists() and abs_path.is_file():
            self._set_status("ok", f"File exists:\n{abs_path}")
            self._set_ok_enabled(True)
        elif abs_path.is_dir() or rel.endswith("/"):
            self._set_status("dir", f"This is a directory or incomplete path:\n{abs_path}")
            self._set_ok_enabled(False)
        else:
            self._set_status("missing", f"File does not exist:\n{abs_path}")
            self._set_ok_enabled(False)

    def _set_status(self, kind, tip):
        if kind == "ok":
            bg, fg, txt = C_PILL_BG_2, C_YELLOW, "OK · file exists"
        elif kind == "dir":
            bg, fg, txt = C_PILL_BG_2, C_SUB, "Invalid · is a directory"
        else:
            bg, fg, txt = C_PILL_BG, C_SUB, "Invalid · missing file"
        self.pill.configure(text=txt, bg=bg, fg=fg)
        self._current_status = kind
        self._pill_tip = tip

    def _ok(self):
        if not self._can_ok:
            return  # twarda blokada
        rel = self.var.get().strip().replace("\\", "/").rstrip("/")
        self.result = (rel, self._current_status)
        self.grab_release()
        self.destroy()
        if self.on_ok:
            self.on_ok(self.result)

    def _browse(self):  # NEW
        abs_path = filedialog.askopenfilename(
            initialdir=self.game_root,
            title="Select existing file to edit",
            filetypes=[("All files", "*.*")]
        )
        if not abs_path:
            return
        try:
            abs_path = Path(abs_path).resolve()
            root = self.game_root.resolve()
            if str(abs_path).startswith(str(root)) and abs_path.is_file():
                rel = abs_path.relative_to(root).as_posix()
                self.var.set(rel)
                self._on_change()
            else:
                messagebox.showerror("Add file", "Selected file must be inside the project root.")
        except Exception as e:
            messagebox.showerror("Add file", f"Cannot use selected file:\n{e}")

    def _cancel(self):
        self.result = None
        self.grab_release()
        self.destroy()


# -------------------- Main Browser (cards) --------------------
class ReplacementsBrowser:
    def __init__(self, master, mod_dir: Path, embed_in: tk.Misc | None = None):
        self.master = master
        self.mod_dir = Path(mod_dir)
        self.py_path = self.mod_dir / "replacements.py"
        self.is_embedded = embed_in is not None

        Titlebar.set_icon(self)

        # root widget
        if self.is_embedded:
            self.root = embed_in
        else:
            self.root = tk.Toplevel(master)
            self.root.title("Replacements")
            self.root.configure(bg=C_BG)
            self.root.geometry("1060x740")
            self.root.update_idletasks()
            self.root.geometry("1060x740")
            self.root.minsize(920, 640)
            self.root.transient(master.winfo_toplevel())
            self.root.withdraw()

        # Style
        s = ttk.Style(self.root)
        s.configure("Panel.TFrame", background=C_BG)
        s.configure("Card.TFrame", background=C_CARD, borderwidth=0, relief="flat")
        s.configure("Card.TLabel",  background=C_CARD, foreground=C_TEXT, font=BASE)

        # game_root from ModLoader (shared between GUI / CLI / exe)
        try:
            import ModLoader

            # Prefer explicit game_root set in ModLoader
            base_dir = getattr(ModLoader, "game_root", None)

            if base_dir is None:
                # Fallback: APP_DIR one level up
                app_dir = getattr(ModLoader, "APP_DIR", None)
                if app_dir is None:
                    app_dir = Path(ModLoader.__file__).resolve().parent
                base_dir = Path(app_dir).parent

            self.game_root = Path(base_dir).resolve()
        except Exception:
            # Fallback – parent of current working directory
            self.game_root = Path.cwd().resolve().parent

        # load payload
        try:
            env = _safe_exec_replacements(self.py_path)
        except Exception as e:
            messagebox.showerror("Load", f"Failed to load:\n{e}\n\n{traceback.format_exc()}")
            env = {
                "LINE_REPLACEMENTS": {},
                "FUNCTION_REPLACEMENTS": {},
                "FILE_LINE_REPLACEMENTS": {},
                "FILE_ADDITIONS": {},
                "FILE_REPLACEMENTS": {},
            }

        self.payload: Dict[str, Any] = {
            "LINE_REPLACEMENTS":       dict(env.get("LINE_REPLACEMENTS", {})),
            "FUNCTION_REPLACEMENTS":   dict(env.get("FUNCTION_REPLACEMENTS", {})),
            "FILE_LINE_REPLACEMENTS":  dict(env.get("FILE_LINE_REPLACEMENTS", {})),
            "FILE_ADDITIONS":          dict(env.get("FILE_ADDITIONS", {})),
            "FILE_REPLACEMENTS":       dict(env.get("FILE_REPLACEMENTS", {})),
        }

        self._cards: List[tk.Frame] = []
        self._card_refs: Dict[str, Dict[str, List[tk.Misc]]] = {}

        self._build_ui()
        self.root.update_idletasks()
        if not self.is_embedded:
            Window.center_on_parent(self.root, master.winfo_toplevel())
            self.root.deiconify()

    # ---------- mouse wheel helpers ----------
    def _bind_mousewheel(self, widget: tk.Widget):
        def _on_mousewheel(event):
            if event.delta:
                widget.yview_scroll(int(-event.delta/120), "units")
            else:
                if getattr(event, "num", None) == 4:
                    widget.yview_scroll(-1, "units")
                elif getattr(event, "num", None) == 5:
                    widget.yview_scroll(1, "units")
            return "break"
        widget.bind("<Enter>", lambda e: widget.focus_set(), add="+")
        widget.bind("<MouseWheel>", _on_mousewheel, add="+")
        widget.bind("<Button-4>", _on_mousewheel, add="+")
        widget.bind("<Button-5>", _on_mousewheel, add="+")

    def _bind_wheel_relay_to_canvas(self, widget: tk.Widget):
        def _on_wheel(e):
            if getattr(e, "delta", 0):
                step = int(-e.delta/120)
            else:
                if getattr(e, "num", None) == 4:
                    step = -1
                elif getattr(e, "num", None) == 5:
                    step = 1
                else:
                    step = 0
            if step:
                self.canvas.yview_scroll(step, "units")
            return "break"
        widget.bind("<MouseWheel>", _on_wheel, add="+")
        widget.bind("<Button-4>",  _on_wheel, add="+")
        widget.bind("<Button-5>",  _on_wheel, add="+")

    def _bind_wheel_relay_tree(self, root: tk.Misc):
        self._bind_wheel_relay_to_canvas(root)
        for ch in getattr(root, "winfo_children", lambda: [])():
            self._bind_wheel_relay_tree(ch)

    # ---------- UI builder ----------
    def _build_ui(self):
        if self.is_embedded:
            for ch in list(self.root.winfo_children()):
                try: ch.destroy()
                except Exception: pass

        header = ttk.Frame(self.root, padding=(0, 0), style="Panel.TFrame")
        header.pack(fill="x")

        row_title = ttk.Frame(header, style="Panel.TFrame")
        row_title.pack(fill="x")

        row_tips = ttk.Frame(header, style="Panel.TFrame")
        row_tips.pack(fill="x", pady=(0, 0))

        row_controls = ttk.Frame(header, style="Panel.TFrame")
        row_controls.pack(fill="x", padx=(4,0), pady=(8, 12))

        # 1) Title
        ttk.Label(row_title, text="Replacements", font=FONT_TITLE_H1).pack(side="left")
        
        # 2) Tips
        tips = ttk.Label(
            row_tips,
            text="Here are all the game files that this mod changed. Each “card” shows exactly what was modified, as well as a list of functions that were affected.",
            foreground=META_FG,
            font=FONT_BASE_MINI,
            justify="left"
        )
        tips.pack(fill="x", anchor="w")
        
        # wrap tips
        def _update_wrap(event=None):
            w = max(200, row_tips.winfo_width() - 12)
            tips.configure(wraplength=w)
        row_tips.bind("<Configure>", _update_wrap)
        _update_wrap()

        # 3) Search + button
        self.e_search = PlaceholderEntry(row_controls, "Filter files/functions...")
        self.e_search.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.e_search.bind("<KeyRelease>", lambda e: self._rebuild_cards())
        Icon.Button(row_controls, "add", command=self._add_entry, tooltip="Add file entry", pack={"side": "right", "padx": (6, 6)})
            
        # Scroll area
        outer = Scrollable(self.root, bg=C_BG)
        outer.pack(fill="both", expand=True, padx=4, pady=(4,10))
        self.canvas = outer.canvas

        self.cards_frame = ttk.Frame(outer.inner, style="Panel.TFrame")
        self.cards_frame.pack(fill="both", expand=True, padx=(0, 10))


        self._rebuild_cards()

    # ---------- bg sync ----------
    def _register_card(self, key: str, widgets: List[tk.Misc]):
        self._card_refs[key] = {"ws": widgets}

    def _sync_bg(self, key: str, bg: str):
        refs = self._card_refs.get(key)
        if not refs: return
        for w in refs["ws"]:
            try:
                if isinstance(w, (tk.Frame, tk.Label)):
                    w.configure(bg=bg)
                elif isinstance(w, ttk.Frame):
                    w.configure(style="Card.TFrame")
                elif isinstance(w, ttk.Label):
                    w.configure(style="Card.TLabel")
            except Exception:
                pass
            try:
                for ch in w.winfo_children():
                    if isinstance(ch, tk.Label):
                        try: ch.configure(bg=bg)
                        except Exception: pass
            except Exception:
                pass

    # ---------- cards ----------
    def _rebuild_cards(self):
        for c in self._cards:
            try: c.destroy()
            except Exception: pass
        self._cards.clear()
        self._card_refs.clear()

        filter_q = (self.e_search.get() or "").strip().lower()
        if filter_q == "filter files/functions…":
            filter_q = ""

        def matches(fpath: str) -> bool:
            if not filter_q:
                return True
            if filter_q in fpath.lower(): return True
            lr = self.payload["LINE_REPLACEMENTS"].get(fpath, {})
            for fn in lr.keys():
                if filter_q in fn.lower(): return True
            fr = self.payload["FUNCTION_REPLACEMENTS"].get(fpath, {})
            for fn in fr.keys():
                if filter_q in fn.lower(): return True
            return False

        files = set()
        files |= set(self.payload["LINE_REPLACEMENTS"].keys())
        files |= set(self.payload["FUNCTION_REPLACEMENTS"].keys())
        files |= set(self.payload["FILE_LINE_REPLACEMENTS"].keys())
        files |= set(self.payload["FILE_ADDITIONS"].keys())
        files |= set(self.payload["FILE_REPLACEMENTS"].keys())
        files = {f for f in files if matches(f)}

        sorted_files = sorted(files, key=lambda p: Path(p).name.lower())
        for fpath in sorted_files:
            self._cards.append(self._make_card(fpath))

    def _open_original_folder(self, fpath: str):
        abs_path = (self.game_root / fpath).resolve()
        target = abs_path if abs_path.is_dir() else abs_path.parent
        if target.exists():
            try:
                os.startfile(target)  # Windows
            except Exception:
                try:
                    import subprocess
                    subprocess.Popen(["xdg-open", str(target)])
                except Exception:
                    messagebox.showerror("Open", f"I can't open: {target}")
        else:
            messagebox.showerror("Open", f"The path does not exist:\n{target}")

    def _make_card(self, fpath: str) -> tk.Frame:
        key = fpath
        card = tk.Frame(self.cards_frame, bg=C_CARD, bd=0, highlightthickness=0)
        card.pack(fill="x", pady=(0, CARD_OUTER_VPAD))
        pad = tk.Frame(card, bg=C_CARD, bd=0, highlightthickness=0)
        pad.pack(fill="x", padx=SIDE_PADDING, pady=CARD_INNER_PAD)

        def bind_hover_tree(w: tk.Misc):
            w.bind("<Enter>", lambda e, k=key: self._sync_bg(k, C_CARD_HOVER), add="+")
            w.bind("<Leave>", lambda e, k=key: self._sync_bg(k, C_CARD), add="+")
            for ch in getattr(w, "winfo_children", lambda: [])():
                bind_hover_tree(ch)

        header = tk.Frame(pad, bg=C_CARD, bd=0, highlightthickness=0)
        header.pack(fill="x", pady=(0, HEADER_BOTTOM_GAP))
        
        Icon.Button(header, "file", pack={"side": "left", "padx": (0, 8)})

        

        lbl_title = tk.Label(header, text=Path(fpath).name, bg=C_CARD, fg=C_TEXT,
                             font=TITLE, bd=0, highlightthickness=0)
        lbl_title.pack(side="left")

        right = tk.Frame(header, bg=C_CARD, bd=0, highlightthickness=0)
        right.pack(side="right")
    
        # Button - edit        
        from gui_editor_replacements_sheet import open_edit_sheet        
        btn_edit = Icon.Button(right, "edit",
            command=lambda fp=fpath: open_edit_sheet(self.root, self.payload, fp),
            tooltip="Edit replacements", pack={"side": "left", "padx": (8, 0)},
        )
        
        # Button - folder    
        btn_folder = Icon.Button(right, "folder",
            command=lambda fp=fpath: self._open_original_folder(fp),
            tooltip="Open original file location", pack={"side": "left", "padx": (8, 0)},
        )       
        
        # Button - remove    
        btn_remove = Icon.Button(right, "remove",
            command=lambda key=fpath: self._remove_entry(key),
            tooltip="Remove this entry", pack={"side": "left", "padx": (8, 0)},
        )      

        folder = (str(Path(fpath).parent).replace("\\", "/") + "/") if Path(fpath).parent != Path(".") else "Game root"        
        lbl_path = tk.Label(pad, text=folder, bg=C_CARD, fg=C_MUTED, font=FONT_BASE_MINI, bd=0, highlightthickness=0)
        lbl_path.pack(anchor="w", pady=(0, SECTION_GAP))

        # counters
        chips = tk.Frame(pad, bg=C_CARD, bd=0, highlightthickness=0)
        chips.pack(fill="x", pady=(0, SECTION_GAP))

        lr   = self.payload["LINE_REPLACEMENTS"].get(fpath, {})
        fr   = self.payload["FUNCTION_REPLACEMENTS"].get(fpath, {})
        flr  = self.payload["FILE_LINE_REPLACEMENTS"].get(fpath, [])
        fa   = self.payload["FILE_ADDITIONS"].get(fpath, [])
        frr  = self.payload["FILE_REPLACEMENTS"].get(fpath, "")

        cnt_func_lines = sum(len(v or []) for v in lr.values())
        cnt_functions  = len(fr)
        cnt_gen_lines  = len(flr)
        cnt_additions  = len(fa)
        cnt_repl_files = 1 if frr else 0

        def add_chip(lbl, val):
            wrap = tk.Frame(chips, bg=C_PILL_BG, bd=0, highlightthickness=0)
            tk.Label(wrap, text=f"{lbl}:", bg=C_PILL_BG, fg=C_TEXT,
                     font=FONT_BASE_MINI, padx=8, pady=3, bd=0, highlightthickness=0).pack(side="left")
            tk.Label(wrap, text=str(val), bg=C_PILL_BG, fg=C_YELLOW,
                     font=("Helvetica",9,"bold"), padx=0, pady=3, bd=0, highlightthickness=0).pack(side="left", padx=(6,8))
            wrap.pack(side="left", padx=(0, CHIP_GAP)) 
            Tooltip(wrap, "Modified elements number")

        if cnt_func_lines: add_chip("Function lines", cnt_func_lines)
        if cnt_functions:  add_chip("Functions",      cnt_functions)
        if cnt_gen_lines:  add_chip("General lines",  cnt_gen_lines)
        if cnt_additions:  add_chip("Additions",      cnt_additions)
        if cnt_repl_files: add_chip("Replaced files", cnt_repl_files)

        # function tags (first 6)
        funcs_frame = tk.Frame(pad, bg=C_CARD, bd=0, highlightthickness=0)
        funcs_frame.pack(fill="x")
        if lr:
            funcs_sorted = sorted(lr.keys())
            max_show = 6
            for fn in funcs_sorted[:max_show]:
                tk.Label(funcs_frame, text=fn, bg=C_PILL_BG_2, fg=C_TEXT,
                         padx=8, pady=3, font=FONT_BASE_MINI, bd=0, highlightthickness=0).pack(side="left", padx=(0, TAG_GAP))
            extra = len(funcs_sorted) - max_show
            if extra > 0:
                tk.Label(funcs_frame, text=f"+{extra} more", bg=C_PILL_BG_2, fg=C_TEXT,
                         padx=8, pady=3, font=FONT_BASE_MINI, bd=0, highlightthickness=0).pack(side="left", padx=(0, TAG_GAP))

        widgets = [card, pad, header, lbl_title, right, btn_edit, btn_folder, btn_remove, chips, funcs_frame]
        self._register_card(key, widgets)
        bind_hover_tree(card)
        self._sync_bg(key, C_CARD)
        self._bind_wheel_relay_tree(card)
        return card
    
    

    # ---------- Validate / Save ----------

    def _save(self) -> bool:
        try:
            norm = _normalize_payload(self.payload)
            src = _generate_py(norm)
            self.py_path.write_text(src, encoding="utf-8")
            if not self.is_embedded:
                messagebox.showinfo("Save", f"Saved: {self.py_path.name}")
            return True
        except Exception as e:
            messagebox.showerror("Save", f"Failed to save:\n{e}")
            return False

    def save(self) -> bool:
        return self._save()

    def destroy(self):
        if not self.is_embedded:
            try:
                self.root.destroy()
            except Exception:
                pass
            
    def _add_entry(self):
        def _on_ok(res):
            if not res:
                return
            fpath, _ = res
            fpath = self._resolve_game_path(fpath)

            # Ostateczna walidacja (odporność na modyfikacje poza modalem)
            if not self._is_existing_file(fpath):
                messagebox.showerror("Add file", "Selected path is not an existing file within project root.")
                return

            # jeśli już jest – tylko fokus
            already = (
                fpath in self.payload.get("LINE_REPLACEMENTS", {}) or
                fpath in self.payload.get("FUNCTION_REPLACEMENTS", {}) or
                fpath in self.payload.get("FILE_LINE_REPLACEMENTS", {}) or
                fpath in self.payload.get("FILE_ADDITIONS", {}) or
                fpath in self.payload.get("FILE_REPLACEMENTS", {})
            )

            # utwórz puste gałęzie tak, by karta od razu była widoczna
            self.payload.setdefault("LINE_REPLACEMENTS", {}).setdefault(fpath, {})
            self.payload.setdefault("FUNCTION_REPLACEMENTS", {}).setdefault(fpath, {})
            self.payload.setdefault("FILE_LINE_REPLACEMENTS", {}).setdefault(fpath, [])
            self.payload.setdefault("FILE_ADDITIONS", {}).setdefault(fpath, [])
            self.payload.setdefault("FILE_REPLACEMENTS", {}).setdefault(fpath, "")

            # clear filder & rebuild list
            try:
                self.e_search.delete(0, "end")
            except Exception:
                pass
            self._rebuild_cards()
            self._focus_card(fpath)
            if already:
                messagebox.showinfo("Add file", f"Entry already existed. Focused:\n{fpath}")

        AddFileDialog(self.root, self.game_root, _on_ok)


    def _remove_entry(self, file_key: str):
        if not messagebox.askyesno(
            "Remove Entry",
            f"Delete entry for: {file_key}\n\n"
            "This will NOT delete the file from the game — it only removes changes made by this mod.\n\n"
            "WARNING:\n"
            "Deleting this entry will likely cause the game to crash because the mod will become incomplete. Do this only if you are the mod author."
        ):
            return

        for sect in ("LINE_REPLACEMENTS", "FUNCTION_REPLACEMENTS", "FILE_LINE_REPLACEMENTS", "FILE_ADDITIONS", "FILE_REPLACEMENTS"):
            branch = self.payload.get(sect)
            if isinstance(branch, dict):
                branch.pop(file_key, None)

        self._rebuild_cards()


    def _resolve_game_path(self, fpath: str) -> str:
        fpath = fpath.strip().replace("\\", "/")
        if fpath.startswith("./"):
            fpath = fpath[2:]        
        p = Path(fpath)
        if p.is_absolute():
            try:
                return Path(os.path.relpath(p, self.game_root)).as_posix()
            except Exception:
                return p.as_posix()
        return fpath

    def _is_existing_file(self, rel_path: str) -> bool:
        try:
            p = (Path(self.game_root) / rel_path).resolve()
            root = Path(self.game_root).resolve()
            return str(p).startswith(str(root)) and p.exists() and p.is_file()
        except Exception:
            return False

    def _file_status(self, rel_path: str):
        abs_path = Path(self.game_root) / rel_path
        if abs_path.exists():
            return "ok", f"File exists:\n{abs_path}"
        if not abs_path.parent.exists():
            return "no-parent", f"Parent directory does not exist:\n{abs_path.parent}"
        return "missing", f"File not found (can be newly created later):\n{abs_path}"
    
    # Scrolls to the card and gently highlights it.
    def _focus_card(self, key: str):
        try:
            self.root.update_idletasks()
            # the easiest way: scroll down - new entries often end up near the end after sorting
            self.canvas.yview_moveto(1.0)
            # short flash
            self._flash_card(key)
        except Exception:
            pass

    def _flash_card(self, key: str, pulses: int = 3, interval_ms: int = 120):
        """Krótko miga tłem karty, by przyciągnąć wzrok."""
        try:
            def step(i=0):
                self._sync_bg(key, C_CARD_HOVER if i % 2 == 0 else C_CARD)
                if i < pulses * 2:
                    self.root.after(interval_ms, step, i + 1)
            step(0)
        except Exception:
            pass
    


# launcher for manual testing
if __name__ == "__main__":
    root = tk.Tk(); root.withdraw()
    mod_path = Path.cwd()
    ReplacementsBrowser(root, mod_path)
    root.mainloop()
