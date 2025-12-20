#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

def _ml_dbg(msg):
    try:
        print(f"[ML:edit] {msg}")
    except Exception:
        pass

from typing import Dict, List, Tuple, Any, Optional, Union
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os, math, copy, itertools, traceback
from gui_common import COLOR_PALETTE as COLOR, ICON_SIZE, FONTS
from gui_common import Tooltip, VSeparator, PlaceholderEntry, Icon, Scrollable, Button, Window, Titlebar







# ====== Theme ======
C_BG           = COLOR["panel"]
C_PANEL        = COLOR["panel"]
C_PANEL_HOVER  = COLOR["panel_hover"]
C_PANEL_SEL    = COLOR["panel_active"]
C_TEXT         = COLOR["text"]
C_SUB          = COLOR["meta"]
C_BORDER       = COLOR["badge_border"]
C_DIVIDER      = COLOR["divider"]
C_INPUT_BG     = COLOR["input_bg"]
C_INPUT_BD     = COLOR["input_bd"]
C_ACCENT_GREEN = COLOR["accent_green"]
C_ACCENT_RED   = COLOR["accent_red"]
C_ACCENT_BLUE   = COLOR["accent_blue"]

BADGE_BG         = COLOR["badge_bg"]
BADGE_FG         = COLOR["badge_fg"]
BADGE_BORDER     = COLOR["badge_border"]

CARD_BG          = COLOR["card_bg"]
CARD_BG_HOVER    = COLOR["card_bg_hover"]
CARD_BG_ACTIVE   = COLOR["card_bg_active"]
CARD_BG_DISABLED = COLOR["card_bg_disabled"]

FONT_TITLE_H1    = FONTS["title_h1"]
FONT_TITLE_H2    = FONTS["title_h2"]
FONT_TITLE_H3    = FONTS["title_h3"]
FONT_MONO        = FONTS["mono"]
FONT_BASE        = FONTS["base"]
FONT_BASE_BOLD   = FONTS["base_bold"]
FONT_BASE_MINI   = FONTS["base_mini"]

SHEET_PANEL            = COLOR["sheet_panel"]
SHEET_PANEL_HOVER      = COLOR["sheet_panel_hover"]
SHEET_PANEL_ACTIVE     = COLOR["sheet_panel_active"]
SHEET_PANEL            = COLOR["sheet_panel"]

TITLE_FONT  = ("Segoe UI", 12, "bold")





# ====== Helpers ======

# Enable/disable text field
def set_texts_enabled(enabled: bool, *texts: "tk.Text", hide_preview_on_disable: bool = True):
    for t in texts:
        try:
            # ensure our hide tag exists
            if "HIDE_PREVIEW" not in t.tag_names():
                t.tag_configure("HIDE_PREVIEW", elide=1)

            prev = str(t.cget("state"))
            t.config(state="normal")  # temporarily unlock to change tags & styles

            # show/hide preview
            if hide_preview_on_disable and not enabled:
                t.tag_add("HIDE_PREVIEW", "1.0", "end")
            else:
                t.tag_remove("HIDE_PREVIEW", "1.0", "end")

            # colors for active/inactive
            t.config(
                fg=C_TEXT if enabled else C_SUB,
                insertbackground=C_TEXT if enabled else C_SUB
            )

            # lock back
            t.config(state="normal" if enabled else "disabled")
        except Exception:
            pass
    
    
    

# ====== Toolkit ======
def _ttk_setup():
    s = ttk.Style()
    try: s.theme_use("clam")
    except Exception: pass
    s.configure("TFrame", background=C_BG)
    s.configure("TLabel", background=C_BG, foreground=C_TEXT)
    s.configure("TButton", padding=6)
    
    s.configure("TNotebook", 
                background=C_PANEL,
                borderwidth=0,
                tabmargins=(8, 6, 8, 0)
                )
    s.configure("TNotebook.Tab", 
                background=C_PANEL,
                foreground=C_TEXT,
                padding=(14, 8),
                borderwidth=0,
                relief="flat",
                )    
    
    s.map("TNotebook.Tab",
        background=[("selected", C_PANEL_SEL), ("active", C_PANEL_HOVER)],
        foreground=[("selected", C_TEXT)],
        borderwidth=[("selected", 0), ("active", 0)],
        relief=[("selected", "flat"), ("active", "flat")],
        padding=[("selected", (14, 8)), ("active", (14, 8))]
        
    )
    
    

def resolve_asset(requested_path: str) -> Optional[str]:
    here = os.path.dirname(os.path.abspath(__file__))
    norm = requested_path.replace("\\", "/").lstrip("/")
    try_paths = [requested_path, os.path.join(here, norm)]
    parent = here
    for _ in range(6):
        parent = os.path.dirname(parent)
        try_paths.append(os.path.join(parent, norm))
    for p in try_paths:
        if os.path.exists(p): return p
    return None


def _set_bg_recursive(widget: tk.Misc, color: str):
    try: widget.configure(bg=color)
    except Exception: pass
    for ch in getattr(widget, "winfo_children", lambda: [])():
        _set_bg_recursive(ch, color)

def _event_changed(widget: tk.Misc):
    try: widget.event_generate("<<ReplacementsChanged>>", when="tail")
    except Exception: pass

# Look for 'replacements/functions' folder. Returns first existing path or None.
def guess_mod_functions_dir() -> Optional[str]:
    def search_up(start: str) -> Optional[str]:
        path = os.path.abspath(start)
        seen = set()
        for _ in range(12):
            if path in seen: break
            seen.add(path)
            cand = os.path.join(path, "replacements", "functions")
            if os.path.isdir(cand): return cand
            path_new = os.path.dirname(path)
            if path_new == path: break
            path = path_new
        return None
    here = os.path.dirname(os.path.abspath(__file__))
    for base in (here, os.getcwd()):
        found = search_up(base)
        if found: return found
    return None

def mk_text(parent, h=6, wrap="word"):
    t = tk.Text(parent, height=h, wrap=wrap, bg=C_INPUT_BG, fg=C_TEXT,
                insertbackground=C_TEXT, highlightthickness=1,
                highlightbackground=C_INPUT_BD, relief="flat", bd=0, font=FONT_MONO,
                undo=True, autoseparators=True, maxundo=128)
    def _safe_undo(_e=None):
        try: t.edit_undo()
        except tk.TclError: pass
        return "break"
    def _safe_redo(_e=None):
        try: t.edit_redo()
        except tk.TclError: pass
        return "break"
    t.bind("<Control-z>", _safe_undo)
    t.bind("<Control-y>", _safe_redo)
    t.bind("<Control-Shift-Z>", _safe_redo)
    def _maybe_sep(e):
        ks = e.keysym
        if len(ks) == 1 or ks in ("Return","BackSpace","Delete","Tab","space"):
            try: t.edit_separator()
            except Exception: pass
    t.bind("<KeyRelease>", _maybe_sep, add="+")
    return t

def mk_entry(parent):
    return tk.Entry(parent, bg=C_INPUT_BG, fg=C_TEXT, insertbackground=C_TEXT,
                    highlightthickness=1, highlightbackground=C_INPUT_BD,
                    relief="flat", bd=0, font=FONT_MONO)


# ====== Cards ======
class FunctionCard(tk.Frame):
    def __init__(self, master, title: str, subtitle: str,
                 icon_main: str, icon_delete: str,
                 on_select, on_delete, selected: bool = False):
        super().__init__(master, bg=C_PANEL, highlightthickness=0, bd=0, cursor="hand2")
        self._selected = selected
        self._on_select = on_select
        self._on_delete = on_delete

        row = tk.Frame(self, bg=self["bg"])
        row.grid(row=0, column=0, sticky="ew", padx=(6, 12), pady=6)
        
        self.grid_columnconfigure(0, weight=1)
        row.grid_columnconfigure(1, weight=0)
        row.grid_columnconfigure(2, weight=1) 

        # function icon
        Icon.Button(
            row, icon_main,
            command=lambda: self._on_select(),
            grid={"row": 0, "column": 0, "padx": (2, 10), "sticky": "w"}
        )

        txt = tk.Frame(row, bg=row["bg"])
        txt.grid(row=0, column=1, sticky="ew")
        
        self.lbl_title = tk.Label(txt, text=title, font=FONT_TITLE_H3,
                                  bg=txt["bg"], fg=C_TEXT, anchor="w")
        self.lbl_title.pack(fill="x")
        
        # delete icon
        Icon.Button(
            row, icon_delete, size=ICON_SIZE-2,
            command=lambda: self._on_delete(),
            tooltip="Delete",
            grid={"row": 0, "column": 2, "sticky": "e"}
        )

        VSeparator(self).grid(row=1, column=0, sticky="ew")
        
        # click anywhere on the card = select
        for w in (self, row, txt, self.lbl_title):
            w.bind("<Button-1>", lambda e: self._on_select())
            w.bind("<Enter>",  lambda e: self._hover(True))
            w.bind("<Leave>",  lambda e: self._hover(False))
            

        self._apply()

    def _apply(self):
        _set_bg_recursive(self, C_PANEL_SEL if self._selected else C_PANEL)
        Icon.bg_changed(self)  # <-- notify icons when background changes

    def set_selected(self, v: bool):
        self._selected = v
        self._apply()

    def _hover(self, on: bool):
        if self._selected:
            return
        _set_bg_recursive(self, C_PANEL_HOVER if on else C_PANEL)
        Icon.bg_changed(self)

class PairCard(tk.Frame):
    def __init__(self, master, idx: int, top_text: str, bottom_text: str,
                 on_click, on_delete, on_select):
        
        # container
        super().__init__(master, bg=C_PANEL, highlightthickness=1, highlightbackground=C_BORDER, bd=1, cursor="hand2")
        self._selected = False; self._on_click=on_click; self._on_select=on_select
        badge_wrap = tk.Frame(self, bg=self["bg"])
        badge_wrap.grid(row=0, column=0, rowspan=2, sticky="nsw", padx=(8,0), pady=(8,8))
        
        # no.
        tk.Label(badge_wrap, text=str(idx+1), font=FONT_BASE_BOLD, fg=BADGE_FG, bg=C_INPUT_BG,
                 width=3, height=1, padx=8, pady=2, bd=1, relief="solid", highlightthickness=0, highlightbackground=BADGE_BORDER).pack()
        body = tk.Frame(self, bg=self["bg"])
        body.grid(row=0, column=1, sticky="nsew", padx=(10,0), pady=(8,2))
        self.grid_columnconfigure(1, weight=1); self.grid_columnconfigure(2, weight=0)
        
        # text
        self.lbl_top = tk.Label(body, text=(top_text or "").strip(), bg=self["bg"], fg=C_ACCENT_RED,
                                font=FONT_MONO, anchor="w", justify="left", wraplength=10)
        self.lbl_bot = tk.Label(body, text=(bottom_text or "").strip(), bg=self["bg"], fg=C_ACCENT_GREEN,
                                font=FONT_MONO, anchor="w", justify="left", wraplength=10)
        self.lbl_top.pack(fill="x", expand=True); self.lbl_bot.pack(fill="x", expand=True, pady=(3,0))
        
        def _wrap(_e=None):
            wl = max(10, body.winfo_width()-90); self.lbl_top.configure(wraplength=wl); self.lbl_bot.configure(wraplength=wl)
        body.bind("<Configure>", _wrap)
        actions = tk.Frame(self, bg=self["bg"]); actions.grid(row=0, column=2, sticky="ne", padx=(0,10), pady=6)
        
        Icon.Button(actions, "remove",command=on_delete,
                    tooltip="Remove pair", pack={"side":"left", "padx":(0, 0)})  
        
        tk.Frame(self, bg=self["bg"]).grid(row=1, column=1, sticky="ew", pady=(0,6))
        def _hover(on: bool):
            if self._selected: return
            _set_bg_recursive(self, CARD_BG_HOVER if on else CARD_BG)
        for w in (self, body, self.lbl_top, self.lbl_bot, badge_wrap):
            w.bind("<Enter>", lambda e: _hover(True))
            w.bind("<Leave>", lambda e: _hover(False))
            w.bind("<Button-1>", lambda e: (self._on_select(), on_click()))
    def set_selected(self, v: bool):
        self._selected=v
        _set_bg_recursive(self, CARD_BG_ACTIVE if v else CARD_BG)
        try: self.configure(highlightbackground="#2b4d7a" if v else C_BORDER)
        except Exception: pass

# ====== Function lines ======
class EditorLineRepl(ttk.Frame):

    # --- save/export: Function lines ---
    save_key = "LINE_REPLACEMENTS"
    def export_for_file(self):
            import copy as _copy
            file_key = getattr(self, "file", None)
            if not file_key:
                return None
            fmap = self.data.get(file_key, {})
            if not isinstance(fmap, dict):
                fmap = {}
            return (file_key, _copy.deepcopy(fmap))

    def __init__(self, master, data: Dict[str, Dict[str, List[Tuple[str,str]]]], file_path: str):
        super().__init__(master, padding=10); _ttk_setup()
        self.data = data; self.file = file_path

        self._current_fun: Optional[str] = None
        self._current_pair_idx: Optional[int] = None
        self._updating_from_code = False
        self._handling_delete = False

        self._hist: List[Tuple[str, tuple]] = []
        self._redo: List[Tuple[str, tuple]] = []
        self._replaying = False

        self._editors_by_key: Dict[Tuple[str,int], Tuple[tk.Text, tk.Text]] = {}
        self._pair_ids: Dict[str, List[int]] = {}
        self._id_counter = itertools.count(1)
        self._shown_key: Optional[Tuple[str,int]] = None

        # title
        top = tk.Frame(self, bg=C_BG); top.grid(row=0, column=0, columnspan=3, sticky="ew")
        tk.Label(top, text="Replace function lines", font=FONT_TITLE_H2, bg=C_BG, fg=C_TEXT).pack(side="left")
        tk.Label(top, text=f"{file_path}", font=FONT_BASE_BOLD, bg=C_BG, fg=C_SUB).pack(side="right")

        # columns
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=1)    
        
        
        # ==== left column
        left_wrap = tk.Frame(self, bg=C_BG); left_wrap.grid(row=1, column=0, sticky="nsew")
        
        tk.Label(left_wrap, text="Functions", bg=C_BG, fg=C_SUB, font=FONT_BASE_BOLD).pack(anchor="w")
        self.fn_scroll = Scrollable(left_wrap); self.fn_scroll.pack(fill="both", expand=True, pady=(4,0))

        footer_fn = tk.Frame(left_wrap, bg=C_BG); footer_fn.pack(fill="x", pady=(6,4))
        
        
        
        
        
        self.e_fun = PlaceholderEntry(footer_fn, "Enter function name...")
        self.e_fun.pack(side="left", fill="x", expand=True, pady=(8, 0))        
        self.e_fun.bind("<Return>", lambda e: (self._add_fun(), "break"))
        
        # Button: Add function key
        Icon.Button(footer_fn, "add", command=self._add_fun,
            tooltip="Adds a new function to edit",pack={"side": "left", "padx": (8, 0), "pady": (8, 0)})
        
        VSeparator(self).grid(row=1, column=1, sticky="ns", padx=10)

        # right column
        right_wrap = tk.Frame(self, bg=C_BG); right_wrap.grid(row=1, column=2, sticky="nsew")
        self.pairs_scroll = Scrollable(right_wrap); self.pairs_scroll.pack(fill="both", expand=True, pady=(4,0))

        def _bg_click(_e=None):
            self._deselect_pair(); self.focus_set()
        self.pairs_scroll.inner.bind("<Button-1>", _bg_click)
        self.pairs_scroll.canvas.bind("<Button-1>", _bg_click)

        footer_pairs = tk.Frame(right_wrap, bg=C_BG)
        footer_pairs.pack(fill="x", pady=(8,0))
        
        # Button: Add new pair
        self.plus_pair = Icon.Button(
            footer_pairs, "add", command=self._add, tooltip="Add new pair", 
            pack={"side": "left", "padx": (0, 6), "pady": (3, 0)})

        self.editors_container = tk.Frame(self, bg=C_BG)
        self.editors_container.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(8,0))
        
        # Move up & down
        Button(footer_pairs, text="Move down", command=lambda: self._move(+1), pack={"side": "right", "padx": (0, 6), "pady": (8,0)})
        Button(footer_pairs, text="Move up", command=lambda: self._move(-1), pack={"side": "right", "padx": (0, 6), "pady": (8,0)})

        
        self.editors_container.grid_columnconfigure(0, weight=1)
        self.editors_container.grid_columnconfigure(1, weight=1)
        tk.Label(self.editors_container, text="Old", bg=C_BG, fg=C_SUB, font=FONT_BASE_BOLD).grid(row=0, column=0, sticky="w")
        tk.Label(self.editors_container, text="New", bg=C_BG, fg=C_SUB, font=FONT_BASE_BOLD).grid(row=0, column=1, sticky="w")
        self._neutral_old = mk_text(self.editors_container, 6)
        self._neutral_new = mk_text(self.editors_container, 6)
        self._neutral_old.grid(row=1, column=0, sticky="nsew", padx=(0,6))
        self._neutral_new.grid(row=1, column=1, sticky="nsew")
        self._set_editors_enabled(self._neutral_old, self._neutral_new, False)        

        for bgw in (self, left_wrap, self.fn_scroll.inner, self.fn_scroll.canvas):
            bgw.bind("<Button-1>", lambda e: self.focus_set(), add="+")

        self._render_functions()




    def _bind_wheel_relay(self, widget, canvas):
        def _on_wheel(e):
            step = int(-e.delta/120) if getattr(e, "delta", 0) else (
                -3 if getattr(e, "num", None) == 4 else (3 if getattr(e, "num", None) == 5 else 0)
            )
            if step:
                canvas.yview_scroll(step, "units")
            return "break"
        # bind to the widget and ALL its children
        stack = [widget]
        while stack:
            w = stack.pop()
            w.bind("<MouseWheel>", _on_wheel, add="+")
            w.bind("<Button-4>",  _on_wheel, add="+")
            w.bind("<Button-5>",  _on_wheel, add="+")
            try:
                stack.extend(w.winfo_children())
            except Exception:
                pass

    def _set_editors_enabled(self, t_old: "tk.Text", t_new: "tk.Text", enabled: bool):
        set_texts_enabled(enabled, t_old, t_new)

    def _clear_and_disable_neutral(self):
        self._neutral_old.config(state="normal"); self._neutral_new.config(state="normal")
        self._neutral_old.delete("1.0", "end"); self._neutral_new.delete("1.0","end")
        self._neutral_old.config(state="disabled"); self._neutral_new.config(state="disabled")

    # ===== History of list-ops =====
    def _push_hist(self, op: str, data: tuple):
        if self._replaying: return
        self._hist.append((op, data)); self._redo.clear()
    def undo_list(self):
        if not self._hist: return
        op, data = self._hist.pop()
        self._replaying = True
        try: self._apply_inverse(op, data)
        finally: self._replaying = False
        self._redo.append((op, data))
    def redo_list(self):
        if not self._redo: return
        op, data = self._redo.pop()
        self._replaying = True
        try: self._apply(op, data)
        finally: self._replaying = False
        self._hist.append((op, data))
    def _apply(self, op: str, data: tuple):
        if op == "ADD_FUN":           (name,) = data; self._add_fun_raw(name)
        elif op == "DEL_FUN":         (name, _, _) = data; self._del_fun_raw(name)
        elif op == "ADD_PAIR":        (fun, idx, val) = data; self._add_pair_raw(fun, idx, val)
        elif op == "DEL_PAIR":        (fun, idx, _, _) = data; self._del_pair_raw(fun, idx)
        elif op == "MOVE_PAIR":       (fun, i, j) = data; self._swap_pair_raw(fun, i, j)
    def _apply_inverse(self, op: str, data: tuple):
        if op == "ADD_FUN":           (name,) = data; self._del_fun_raw(name)
        elif op == "DEL_FUN":         (name, pairs, ids) = data; self._restore_fun_raw(name, pairs, ids)
        elif op == "ADD_PAIR":        (fun, idx, _) = data; self._del_pair_raw(fun, idx)
        elif op == "DEL_PAIR":        (fun, idx, val, pid) = data; self._insert_pair_raw(fun, idx, val, pid)
        elif op == "MOVE_PAIR":       (fun, i, j) = data; self._swap_pair_raw(fun, i, j)

    # ===== low-level list ops =====
    def _add_fun_raw(self, name: str):
        fmap = self.data.setdefault(self.file, {})
        if name not in fmap: fmap[name] = []
        self._pair_ids.setdefault(name, [])
        self._render_functions(); self._select_fun(name); _event_changed(self)
        
    def _del_fun_raw(self, name: str):
        fmap = self.data.setdefault(self.file, {})
        if name in fmap: del fmap[name]
        self._pair_ids.pop(name, None)
        for key in [k for k in list(self._editors_by_key) if k[0]==name]:
            t_old, t_new = self._editors_by_key.pop(key)
            try: t_old.destroy(); t_new.destroy()
            except Exception: pass
        if self._shown_key and self._shown_key[0] == name:
            self._shown_key = None
            self._neutral_old.tkraise(); self._neutral_new.tkraise()
            self._clear_and_disable_neutral()
        if self._current_fun == name: self._current_fun = None
        self._render_functions(); self._render_pairs(); _event_changed(self)
        
    def _restore_fun_raw(self, name: str, pairs_snapshot: List[Tuple[str,str]], ids_snapshot: List[int]):
        self.data.setdefault(self.file, {})[name] = copy.deepcopy(pairs_snapshot)
        self._pair_ids[name] = list(ids_snapshot)
        self._render_functions(); self._select_fun(name); _event_changed(self)
        
    def _insert_pair_raw(self, fun: str, idx: int, val: Tuple[str,str], pid: int):
        arr = self.data.setdefault(self.file, {}).setdefault(fun, [])
        arr.insert(idx, val)
        self._pair_ids.setdefault(fun, []).insert(idx, pid)
        self._current_fun = fun; self._current_pair_idx = idx
        self._render_pairs(); self._select_pair(idx); _event_changed(self)
        
    def _add_pair_raw(self, fun: str, idx: int, val: tuple):
        arr = self.data.setdefault(self.file, {}).setdefault(fun, [])
        if idx is None or idx > len(arr): idx = len(arr)
        arr.insert(idx, val)
        self._pair_ids.setdefault(fun, []).insert(idx, next(self._id_counter))
        self._current_fun = fun; self._current_pair_idx = idx
        self._render_pairs(); self._select_pair(idx); _event_changed(self)
                      
    def _del_pair_raw(self, fun: str, idx: int):
        arr = self.data.setdefault(self.file, {}).setdefault(fun, [])
        if 0 <= idx < len(arr):
            arr.pop(idx); self._pair_ids.setdefault(fun, []).pop(idx)
        if self._shown_key and self._shown_key == (fun, self._pair_ids.get(fun, [None])[idx] if 0<=idx<len(self._pair_ids.get(fun,[])) else None):
            self._shown_key = None
            self._clear_and_disable_neutral()
        self._current_fun = fun; self._current_pair_idx = None
        self._render_pairs(); _event_changed(self)
        
    def _swap_pair_raw(self, fun: str, i: int, j: int):
        arr = self.data.setdefault(self.file, {}).setdefault(fun, [])
        ids = self._pair_ids.setdefault(fun, [])
        if 0 <= i < len(arr) and 0 <= j < len(arr):
            arr[i], arr[j] = arr[j], arr[i]; ids[i], ids[j] = ids[j], ids[i]
            self._current_pair_idx = j
            self._render_pairs(); self._select_pair(j); _event_changed(self)

    def _get_key_for_index(self, fun: str, idx: int) -> Optional[Tuple[str,int]]:
        ids = self._pair_ids.setdefault(fun, [])
        if 0 <= idx < len(ids): return (fun, ids[idx])
        return None
    def _ensure_ids_for_fun(self, fun: str):
        if fun in self._pair_ids: return
        arr = self.data.get(self.file, {}).get(fun, [])
        self._pair_ids[fun] = [next(self._id_counter) for _ in arr]

    # ---------- ANTI-FLICKER ----------
    def _update_pair_card_inplace(self, fn: str, idx: int, a: str, b: str):
        if fn != self._current_fun: return
        ch = [w for w in self.pairs_scroll.inner.winfo_children() if isinstance(w, PairCard)]
        if 0 <= idx < len(ch):
            card: PairCard = ch[idx]
            card.lbl_top.config(text=(a or "").strip())
            card.lbl_bot.config(text=(b or "").strip())

    def _ensure_editors_for_key(self, key: Tuple[str,int]):
        if key in self._editors_by_key: return
        t_old = mk_text(self.editors_container, 6)
        t_new = mk_text(self.editors_container, 6)
        def _mod():
            if self._updating_from_code: return
            fun, pid = key
            ids = self._pair_ids.get(fun, [])
            if pid not in ids: return
            idx = ids.index(pid)
            arr = self.data.setdefault(self.file, {}).setdefault(fun, [])
            
            if 0 <= idx < len(arr):
                a = t_old.get("1.0","end-1c"); b = t_new.get("1.0","end-1c")
                arr[idx] = (a, b)
                self._update_pair_card_inplace(fun, idx, a, b)
                _event_changed(self)
                            
            arr_dbg = self.data.get(self.file, {}).get(fun, [])
            cur = arr_dbg[idx] if 0 <= idx < len(arr_dbg) else None
                
        t_old.bind("<<Modified>>", lambda e: (t_old.edit_modified(False), _mod()), add="+")
        t_new.bind("<<Modified>>", lambda e: (t_new.edit_modified(False), _mod()), add="+")
        t_old.edit_modified(False); t_new.edit_modified(False)
        self._editors_by_key[key] = (t_old, t_new)

    def _show_editors_for_key(self, key: Tuple[str,int]):
        self._neutral_old.grid_remove(); self._neutral_new.grid_remove()
        if self._shown_key and self._shown_key in self._editors_by_key:
            o, n = self._editors_by_key[self._shown_key]
            try: o.grid_remove(); n.grid_remove()
            except Exception: pass
        t_old, t_new = self._editors_by_key[key]
        t_old.grid(row=1, column=0, sticky="nsew", padx=(0,6))
        t_new.grid(row=1, column=1, sticky="nsew")
        self._set_editors_enabled(t_old, t_new, True)
        self._shown_key = key

    def _disable_current_editors(self):
        if self._shown_key and self._shown_key in self._editors_by_key:
            t_old, t_new = self._editors_by_key[self._shown_key]
            self._set_editors_enabled(t_old, t_new, False)
        self._neutral_old.grid(row=1, column=0, sticky="nsew", padx=(0,6))
        self._neutral_new.grid(row=1, column=1, sticky="nsew")
        self._clear_and_disable_neutral()

    def _refresh_pairs_keep(self, keep_idx: Optional[int]):
        y = self.pairs_scroll.canvas.yview()
        self._render_pairs()
        self.pairs_scroll.canvas.yview_moveto(y[0])
        if keep_idx is not None: self._select_pair(keep_idx)

    # render/select
    def _render_functions(self):
        for w in self.fn_scroll.inner.winfo_children(): w.destroy()        
        fmap = self.data.get(self.file, {})
        funs = sorted(fmap.keys()); cur = self._current_fun
        
        for fn in funs:
            card = FunctionCard(self.fn_scroll.inner, fn, "",
                                icon_main="function",
                                icon_delete="remove",
                                on_select=lambda name=fn: self._select_fun(name),
                                on_delete=lambda name=fn: self._delete_fun(name),
                                selected=(fn==cur))
            card.pack(fill="x", padx=(0,10), pady=0)
            self._bind_wheel_relay(card, self.fn_scroll.canvas)
            for w in card.winfo_children():
                self._bind_wheel_relay(w, self.fn_scroll.canvas)       
        if funs and cur not in funs: self._select_fun(funs[0])
        elif cur: self._render_pairs()

    def _select_fun(self, name: str):
        self._current_fun = name
        for w in self.fn_scroll.inner.winfo_children():
            if isinstance(w, FunctionCard):
                w.set_selected(w.lbl_title.cget("text")==name)
        self._current_pair_idx = None
        self._disable_current_editors()
        self._ensure_ids_for_fun(name)
        self._render_pairs()

    def _add_fun(self):
        name = self.e_fun.get().strip()
        if not name: return
        self._push_hist("ADD_FUN", (name,))
        self._add_fun_raw(name)
        #self.e_fun.delete(0, "end")
        self.e_fun.set_text("")

    def _delete_fun(self, name: str):
        pairs_snapshot = copy.deepcopy(self.data.get(self.file, {}).get(name, []))
        ids_snapshot = list(self._pair_ids.get(name, []))
        self._push_hist("DEL_FUN", (name, pairs_snapshot, ids_snapshot))
        self._del_fun_raw(name)

    def _render_pairs(self):
        for w in self.pairs_scroll.inner.winfo_children(): w.destroy()
        fn = self._current_fun
        if not fn: return
        self._ensure_ids_for_fun(fn)
        pairs = list(self.data.get(self.file, {}).get(fn, []))
        ids = self._pair_ids[fn]
        while len(ids) < len(pairs): ids.append(next(self._id_counter))
        if len(ids) > len(pairs): ids[:] = ids[:len(pairs)]
        for i, (old, new) in enumerate(pairs):
            card = PairCard(self.pairs_scroll.inner, i, old, new,
                            on_click = lambda idx=i: self._edit_into_fields(idx),
                            on_delete= lambda idx=i: self._delete_pair_by_index(idx),
                            on_select= lambda idx=i: self._select_pair(idx))
            card.pack(fill="x", padx=(0,10), pady=6)
            self._bind_wheel_relay(card, self.pairs_scroll.canvas)
            for w in card.winfo_children():
                self._bind_wheel_relay(w, self.pairs_scroll.canvas)
        if self._current_pair_idx is not None and 0 <= self._current_pair_idx < len(pairs):
            self._select_pair(self._current_pair_idx)

    def _deselect_pair(self):
        self._current_pair_idx = None
        for w in self.pairs_scroll.inner.winfo_children():
            if isinstance(w, PairCard): w.set_selected(False)
        self._disable_current_editors()

    def _select_pair(self, idx: int):
        self._current_pair_idx = idx
        i = 0
        for w in self.pairs_scroll.inner.winfo_children():
            if isinstance(w, PairCard):
                w.set_selected(i==idx); i += 1

    def _edit_into_fields(self, idx: int):
        fn = self._current_fun
        if not fn: return
        key = self._get_key_for_index(fn, idx)
        if not key: return
        a, b = self.data[self.file][fn][idx]
        self._ensure_editors_for_key(key)
        self._updating_from_code = True
        try:
            t_old, t_new = self._editors_by_key[key]
            self._show_editors_for_key(key)
            t_old.delete("1.0","end"); t_old.insert("1.0", a)
            t_new.delete("1.0","end"); t_new.insert("1.0", b)
            t_old.edit_reset(); t_old.edit_separator()
            t_new.edit_reset(); t_new.edit_separator()
        finally:
            self._updating_from_code = False
        self._select_pair(idx)

    def _delete_pair_by_index(self, idx: int):
        fn = self._current_fun
        if not fn: return
        arr = self.data[self.file][fn]
        val = arr[idx] if 0 <= idx < len(arr) else ("","")
        pid = self._pair_ids.get(fn, [])[idx] if 0 <= idx < len(self._pair_ids.get(fn, [])) else next(self._id_counter)
        self._push_hist("DEL_PAIR", (fn, idx, val, pid))
        self._del_pair_raw(fn, idx)

    def _add(self):
        fn = self._current_fun
        if not fn:
            messagebox.showinfo("Add", "First, add or select a feature (left column).")
            return
        idx = (self._current_pair_idx + 1) if self._current_pair_idx is not None else len(self.data.setdefault(self.file, {}).setdefault(fn, []))
        val = ("","")
        self._push_hist("ADD_PAIR", (fn, idx, val))
        self._add_pair_raw(fn, idx, val)

    def _move(self, d: int):
        fn = self._current_fun; idx = self._current_pair_idx
        if not fn or idx is None: return
        j = idx + d
        arr = self.data.setdefault(self.file, {}).setdefault(fn, [])
        if 0 <= j < len(arr):
            self._push_hist("MOVE_PAIR", (fn, idx, j))
            self._swap_pair_raw(fn, idx, j)

    # aliases
    def _on_delete(self, e=None):
        if self._handling_delete: return "break"
        fw = self.focus_get()
        if isinstance(fw, (tk.Entry, tk.Text)): return
        self._handling_delete = True
        try:
            if self._current_pair_idx is not None:
                self._delete_pair_by_index(self._current_pair_idx); return "break"
            if self._current_fun:
                self._delete_fun(self._current_fun); return "break"
        finally:
            self._handling_delete = False
    def _on_undo(self, e=None):
        fw = self.focus_get()
        if isinstance(fw, (tk.Entry, tk.Text)): return
        self.undo_list(); return "break"
    def _on_redo(self, e=None):
        fw = self.focus_get()
        if isinstance(fw, (tk.Entry, tk.Text)): return
        self.redo_list(); return "break"

    # navigation (delegated by window)
    def _nav_up(self, e=None):
        fw = self.focus_get()
        if isinstance(fw, (tk.Entry, tk.Text)): return
        if self._current_pair_idx is not None:
            if self._current_pair_idx > 0:
                self._edit_into_fields(self._current_pair_idx - 1)
        else:
            fmap = sorted(self.data.get(self.file, {}).keys())
            if self._current_fun and self._current_fun in fmap:
                i = fmap.index(self._current_fun)
                if i > 0: self._select_fun(fmap[i-1])
        return "break"
    def _nav_down(self, e=None):
        fw = self.focus_get()
        if isinstance(fw, (tk.Entry, tk.Text)): return
        if self._current_pair_idx is not None:
            arr = self.data.get(self.file, {}).get(self._current_fun, [])
            if self._current_pair_idx < len(arr)-1:
                self._edit_into_fields(self._current_pair_idx + 1)
        else:
            fmap = sorted(self.data.get(self.file, {}).keys())
            if self._current_fun and self._current_fun in fmap:
                i = fmap.index(self._current_fun)
                if i < len(fmap)-1: self._select_fun(fmap[i+1])
        return "break"

# ====== Functions tab (function -> filename) ======
class EditorFunctionMappings(ttk.Frame):

    # --- save/export: Functions (mapping) ---
    save_key = "FUNCTION_REPLACEMENTS"
    def export_for_file(self):
            import copy as _copy
            file_key = getattr(self, "file", None)
            if not file_key:
                return None
            fmap = self.data.get(file_key, {})
            if not isinstance(fmap, dict):
                fmap = {}
            return (file_key, _copy.deepcopy(fmap))

    def __init__(self, master, data: Dict[str, Dict[str,str]], file_path: str):
        super().__init__(master, padding=10); _ttk_setup()
        self.data = data; self.file = file_path

        self._selected: Optional[str] = None
        self._hist: List[Tuple[str, tuple]] = []; self._redo: List[Tuple[str, tuple]] = []; self._replaying=False

        top = tk.Frame(self, bg=C_BG); top.grid(row=0, column=0, columnspan=3, sticky="ew")        
        tk.Label(top, text="Replace functions", font=FONT_TITLE_H2, bg=C_BG, fg=C_TEXT).pack(side="left")
        tk.Label(top, text=f"{file_path}", font=FONT_BASE_BOLD, bg=C_BG, fg=C_SUB).pack(side="right")

        self.grid_rowconfigure(1, weight=1); self.grid_columnconfigure(2, weight=1)

        # LEFT PANEL (Functions)
        left = tk.Frame(self, bg=C_BG); left.grid(row=1, column=0, sticky="nsew")
        tk.Label(left, text="Functions", bg=C_BG, fg=C_SUB, font=FONT_BASE_BOLD).pack(anchor="w")
        self.scroll = Scrollable(left); self.scroll.pack(fill="both", expand=True, pady=(4,0)) #scroll
        
        # Footer
        footer_fn = tk.Frame(left, bg=C_BG)
        footer_fn.pack(fill="x", pady=(6,4))        
        self.e_newfun = PlaceholderEntry(footer_fn, "Enter function name...")
        self.e_newfun.pack(side="left", fill="x", expand=True, pady=(8, 0))                    
                
        # Button - add
        self.plus_pair = Icon.Button(footer_fn, "add", command=self._new_function, 
            tooltip="Add function key", pack={"side": "left", "padx": (8,0), "pady": (8,0)}
)    

        VSeparator(self).grid(row=1, column=1, sticky="ns", padx=10)

        # RIGHT PANEL (pairs)
        right = tk.Frame(self, bg=C_BG); right.grid(row=1, column=2, sticky="nsew")
        frm = tk.Frame(right, bg=C_BG); frm.pack(fill="x", pady=(6,0))        
        
        
        # Textfield #1
        tk.Label(frm, text="Function name (no () needed)", bg=C_BG, fg=C_SUB).grid(row=0, column=0, sticky="w", pady=(0,4))
        self.e_fun = PlaceholderEntry(frm, "e.g. SaveStartGameParam")
        self.e_fun.grid(row=1, column=0, sticky="ew")
        
        # Textfield #2
        tk.Label(frm, text="Filename (only name, no path)", bg=C_BG, fg=C_SUB).grid(row=2, column=0, sticky="w", pady=(8,4))
        self.e_file = PlaceholderEntry(frm, "e.g. utilite.c")        
        self.e_file.grid(row=3, column=0, sticky="ew")
        
        # Button "browse"
        btn_grid = Button.Grid(3, 1, (8,0), sticky="w")
        Button(frm, text="Browse…", command=self._browse, grid=btn_grid, tooltip="Choose your file with Windows Explorer")
        frm.grid_columnconfigure(0, weight=1)

        # live-save filename
        def _save_live_file(_e=None):
            fn = (self.e_fun.get() or "").strip()
            if not fn: return
            name_only = os.path.basename((self.e_file.get() or "").strip())
            old = self.data.get(self.file, {}).get(fn)
            self._push("SET", (fn, old))
            self._set_raw(fn, name_only)
        self.e_file.bind("<KeyRelease>", _save_live_file, add="+")
        self.e_file.bind("<Return>", lambda e: (_save_live_file(), "break"))

        # live-rename function key
        def _rename_live(_e=None):
            if self._selected is None: return
            new_name = (self.e_fun.get() or "").strip()
            if not new_name or new_name == self._selected: return
            self._rename_key(self._selected, new_name)
        self.e_fun.bind("<KeyRelease>", _rename_live, add="+")
        self.e_fun.bind("<Return>", lambda e: (_rename_live(), "break"))

        self._render()

    def _push(self, op, data):
        if self._replaying: return
        self._hist.append((op, data)); self._redo.clear()
    def _undo(self):
        if not self._hist: return
        op,data = self._hist.pop(); self._replaying=True
        try:
            if op=="SET": fn, old = data; self._set_raw(fn, old)
            elif op=="DEL": fn, path = data; self._del_raw(fn)
            elif op=="RENAME": old,new = data; self._do_rename(new, old)
        finally: self._replaying=False
        self._redo.append((op,data))
    def _redo(self):
        if not self._redo: return
        op,data = self._redo.pop(); self._replaying=True
        try:
            if op=="SET": fn, new = data; self._set_raw(fn, new)
            elif op=="DEL": fn, path = data; self._set_raw(fn, path)
            elif op=="RENAME": old,new = data; self._do_rename(old, new)
        finally: self._replaying=False
        self._hist.append((op,data))

    def _set_raw(self, fn: str, path: Optional[str]):
        if path is None:
            if fn in self.data.setdefault(self.file, {}): del self.data[self.file][fn]
        else:
            self.data.setdefault(self.file, {})[fn] = os.path.basename(path or "")
        self._render(); _event_changed(self)
        if fn in self.data.get(self.file, {}): self._select(fn)

    def _del_raw(self, fn: str):
        if fn in self.data.setdefault(self.file, {}): del self.data[self.file][fn]
        self._render(); _event_changed(self); self._selected = None

    def _render(self):
        for w in self.scroll.inner.winfo_children(): w.destroy()
        items = sorted(self.data.get(self.file, {}).items())
        for fn, path in items:
            card = FunctionCard(self.scroll.inner, fn, path,
                                icon_main="function", icon_delete="remove",
                                on_select=lambda n=fn: self._select(n),
                                on_delete=lambda n=fn: self._delete(n),
                                selected=(fn==self._selected))
            card.pack(fill="x", padx=(0,10), pady=0)

    def _select(self, fn: str):
        self._selected = fn
        
        # Use set_text() to ensure it's not treated as placeholder
        self.e_fun.set_text(fn)
        self.e_file.set_text(os.path.basename(self.data.get(self.file, {}).get(fn,"")))
        
        #self.e_fun.delete(0,"end"); self.e_fun.insert(0, fn)
        #self.e_file.delete(0,"end"); self.e_file.insert(0, os.path.basename(self.data.get(self.file, {}).get(fn,"")))
        for w in self.scroll.inner.winfo_children():
            if isinstance(w, FunctionCard): w.set_selected(w.lbl_title.cget("text")==fn)

    def _new_function(self):
        fn = (self.e_newfun.get() or "").strip()
        if not fn: return
        if fn in self.data.setdefault(self.file, {}):
            self._select(fn)
        else:
            self._push("SET", (fn, None))
            self._set_raw(fn, "")
            self._select(fn)
        #self.e_newfun.delete(0, "end")
        self.e_newfun.set_text("")

    def _delete(self, fn: str):
        old = self.data.get(self.file, {}).get(fn)
        self._push("DEL", (fn, old))
        self._del_raw(fn)

    def _rename_key(self, old: str, new: str):
        if not new or new == old: return
        mp = self.data.setdefault(self.file, {})
        if new in mp:
            messagebox.showwarning("Rename", f"Function '{new}' already exists.")
            #self.e_fun.delete(0, "end"); self.e_fun.insert(0, old)
            self.e_fun.set_text(old)
            return
        self._push("RENAME", (old, new))
        self._do_rename(old, new)

    def _do_rename(self, old: str, new: str):
        mp = self.data.setdefault(self.file, {})
        if old in mp:
            mp[new] = mp.pop(old)
        self._render(); self._select(new); _event_changed(self)

    def _browse(self):
        initdir = guess_mod_functions_dir() or os.path.expanduser("~")
        p = filedialog.askopenfilename(title="Select file", initialdir=initdir)
        if p:
            name_only = os.path.basename(p)
            #self.e_file.delete(0,"end"); self.e_file.insert(0,name_only)
            self.e_file.set_text(name_only)
            fn = (self.e_fun.get() or "").strip()
            if fn:
                old = self.data.get(self.file, {}).get(fn)
                self._push("SET", (fn, old))
                self._set_raw(fn, name_only)

    # navigation (delegated by window)
    def _nav_up(self, e=None):
        fw = self.focus_get()
        if isinstance(fw, (tk.Entry, tk.Text)): return
        items = sorted(self.data.get(self.file, {}).keys())
        if self._selected and self._selected in items:
            i = items.index(self._selected)
            if i > 0: self._select(items[i-1])
        return "break"
    def _nav_down(self, e=None):
        fw = self.focus_get()
        if isinstance(fw, (tk.Entry, tk.Text)): return
        items = sorted(self.data.get(self.file, {}).keys())
        if self._selected and self._selected in items:
            i = items.index(self._selected)
            if i < len(items)-1: self._select(items[i+1])
        return "break"

# ====== General lines ======
class EditorGeneralPairs(ttk.Frame):

    # --- save/export: General lines ---
    save_key = "FILE_LINE_REPLACEMENTS"

    def export_for_file(self):
            import copy as _copy
            file_key = getattr(self, "file", None)
            if not file_key:
                return None
            arr = self.data.get(file_key, [])
            # normalize + dedup (keep order)
            norm = []
            if isinstance(arr, list):
                for it in arr:
                    if isinstance(it, (list, tuple)) and len(it) >= 2:
                        a, b = it[0], it[1]
                    else:
                        a, b = it, ""
                    norm.append((str(a) if a is not None else "", str(b) if b is not None else ""))
            out, seen = [], set()
            for pair in norm:
                if pair not in seen:
                    seen.add(pair); out.append(pair)
            return (file_key, _copy.deepcopy(out))

    def __init__(self, master, data: Dict[str, List[Tuple[str,str]]], file_path: str):
        super().__init__(master, padding=10); _ttk_setup()
        self.data = data; self.file=file_path
        self._idx: Optional[int]=None
        self._hist: List[Tuple[str, tuple]]=[]; self._redo: List[Tuple[str, tuple]]=[]; self._replaying=False

        top = tk.Frame(self, bg=C_BG); top.grid(row=0, column=0, columnspan=2, sticky="ew")       
        tk.Label(top, text="Replace general lines", font=FONT_TITLE_H2, bg=C_BG, fg=C_TEXT).pack(side="left")
        tk.Label(top, text=f"{file_path}", font=FONT_BASE_BOLD, bg=C_BG, fg=C_SUB).pack(side="right")

        self.grid_columnconfigure(0, weight=1); self.grid_rowconfigure(1, weight=1)

        listfrm = tk.Frame(self, bg=C_BG); listfrm.grid(row=1, column=0, sticky="nsew")
        self.scroll = Scrollable(listfrm); self.scroll.pack(fill="both", expand=True, pady=(4,0))
        
        # Buttons:
        self.plus_pair = Icon.Button(
            listfrm, "add", command=self._add, tooltip="Add new pair", pack={"side": "left", "padx": (0,0), "pady": (8,0)}) 
        Button(listfrm, text="Move down", command=lambda: self._move(+1), pack={"side": "right", "padx": (0, 6), "pady": (8,0)})
        Button(listfrm, text="Move up",   command=lambda: self._move(-1), pack={"side": "right", "padx": (0, 6), "pady": (8,0)})
        

        ed = tk.Frame(self, bg=C_BG); ed.grid(row=2, column=0, sticky="ew", pady=(8,0))
        ed.grid_columnconfigure(0, weight=1); ed.grid_columnconfigure(1, weight=1)
        tk.Label(ed, text="Old", bg=C_BG, fg=C_SUB, font=FONT_BASE_BOLD).grid(row=0, column=0, sticky="w")
        tk.Label(ed, text="New", bg=C_BG, fg=C_SUB, font=FONT_BASE_BOLD).grid(row=0, column=1, sticky="w")
        self.t_old = mk_text(ed, 6); self.t_new = mk_text(ed, 6)
        self.t_old.grid(row=1, column=0, sticky="nsew", padx=(0,6)); self.t_new.grid(row=1, column=1, sticky="nsew")
        self._set_enabled(False)

        mv = tk.Frame(self, bg=C_BG); mv.grid(row=3, column=0, sticky="ew", pady=(8,0))

        self._render()

        # Delete: Also from text, if no selection
        def _on_del(e=None):
            fw=self.focus_get()
            if isinstance(fw, tk.Text):
                try: sel = bool(fw.tag_ranges("sel"))
                except Exception: sel = False
                if sel: return
            if self._idx is not None:
                self._del(self._idx); return "break"
        self.bind_all("<Delete>", _on_del, add="+")
        self.bind_all("<Control-z>", self._on_undo, add="+")
        self.bind_all("<Control-y>", self._on_redo, add="+")
        self.bind_all("<Control-Shift-Z>", self._on_redo, add="+")
        for bg in (self.scroll.inner, self.scroll.canvas):
            bg.bind("<Button-1>", lambda e: self._deselect())

    def _set_enabled(self, en: bool):
        set_texts_enabled(en, self.t_old, self.t_new)

    def _update_card_inplace(self, idx:int, a:str, b:str):
        ch = [w for w in self.scroll.inner.winfo_children() if isinstance(w, PairCard)]
        if 0 <= idx < len(ch):
            card: PairCard = ch[idx]
            card.lbl_top.config(text=(a or "").strip())
            card.lbl_bot.config(text=(b or "").strip())

    def _render(self):
        for w in self.scroll.inner.winfo_children(): w.destroy()
        pairs = self.data.get(self.file, [])
        for i,(a,b) in enumerate(pairs):
            card = PairCard(self.scroll.inner, i, a, b,
                            on_click=lambda idx=i: self._edit(idx),
                            on_delete=lambda idx=i: self._del(idx),
                            on_select=lambda idx=i: self._select(idx))
            card.pack(fill="x", padx=(0,10), pady=6)
        if pairs and self._idx is None:
            self._edit(0)
        elif self._idx is not None and 0 <= self._idx < len(pairs):
            self._select(self._idx)

        # live update in-place
        def _mod(_e=None):
            if self._idx is None: return
            arr = self.data.setdefault(self.file, [])
            if not (0 <= self._idx < len(arr)): return
            a = self.t_old.get("1.0","end-1c"); b = self.t_new.get("1.0","end-1c")
            arr[self._idx] = (a, b)
            self._update_card_inplace(self._idx, a, b)
            _event_changed(self)
        self.t_old.bind("<<Modified>>", lambda e: (self.t_old.edit_modified(False), _mod()), add="+")
        self.t_new.bind("<<Modified>>", lambda e: (self.t_new.edit_modified(False), _mod()), add="+")

    def _refresh_keep(self, keep):
        y = self.scroll.canvas.yview(); self._render(); self.scroll.canvas.yview_moveto(y[0]); self._select(keep)

    def _select(self, idx: int):
        self._idx = idx; i=0
        for w in self.scroll.inner.winfo_children():
            if isinstance(w, PairCard): w.set_selected(i==idx); i+=1

    def _edit(self, idx: int):
        arr = self.data.setdefault(self.file, [])
        if not (0 <= idx < len(arr)): return
        a,b = arr[idx]; self._select(idx)
        self._set_enabled(True)
        self.t_old.delete("1.0","end"); self.t_old.insert("1.0", a); self.t_old.edit_reset(); self.t_old.edit_separator()
        self.t_new.delete("1.0","end"); self.t_new.insert("1.0", b); self.t_new.edit_reset(); self.t_new.edit_separator()

    def _deselect(self):
        self._idx = None
        for w in self.scroll.inner.winfo_children():
            if isinstance(w, PairCard): w.set_selected(False)
        self._set_enabled(False)

    def _push(self, op,data):
        if self._replaying: return
        self._hist.append((op,data)); self._redo.clear()
    def _undo(self):
        if not self._hist: return
        op,data = self._hist.pop(); self._replaying=True
        try:
            if op=="ADD": idx,val=data; self._raw_del(idx)
            elif op=="DEL": idx,val=data; self._raw_insert(idx,val)
            elif op=="MOVE": i,j=data; self._raw_swap(i,j)
        finally: self._replaying=False
        self._redo.append((op,data))
    def _redo(self):
        if not self._redo: return
        op,data = self._redo.pop(); self._replaying=True
        try:
            if op=="ADD": idx,val=data; self._raw_insert(idx,val)
            elif op=="DEL": idx,val=data; self._raw_del(idx)
            elif op=="MOVE": i,j=data; self._raw_swap(i,j)
        finally: self._replaying=False
        self._hist.append((op,data))

    def _raw_insert(self, idx, val):
        arr = self.data.setdefault(self.file, []); arr.insert(idx, val)
        self._refresh_keep(idx); _event_changed(self)
    def _raw_del(self, idx):
        arr = self.data.setdefault(self.file, [])
        if 0<=idx<len(arr): arr.pop(idx)
        self._idx=None; self._render(); _event_changed(self)
    def _raw_swap(self, i,j):
        arr = self.data.setdefault(self.file, [])
        if 0<=i<len(arr) and 0<=j<len(arr): arr[i],arr[j] = arr[j],arr[i]
        self._refresh_keep(j); _event_changed(self)

    def _add(self):
        arr = self.data.setdefault(self.file, [])
        idx = self._idx+1 if self._idx is not None else len(arr)
        val = ("",""); self._push("ADD",(idx,val)); self._raw_insert(idx,val)
    def _del(self, idx):
        arr = self.data.setdefault(self.file, [])
        if not (0<=idx<len(arr)): return
        self._push("DEL",(idx, arr[idx])); self._raw_del(idx)
    def _move(self, d):
        if self._idx is None: return
        i=self._idx; j=i+d; arr=self.data.setdefault(self.file,[])
        if 0<=j<len(arr): self._push("MOVE",(i,j)); self._raw_swap(i,j)

    # navigation (delegated by window)
    def _nav_up(self, e=None):
        fw=self.focus_get()
        if isinstance(fw,(tk.Entry,tk.Text)): return
        pairs = self.data.get(self.file, [])
        if not pairs: return "break"
        if self._idx is None: 
            self._edit(0)
        else:
            if self._idx > 0: self._edit(self._idx-1)
        return "break"
    def _nav_down(self, e=None):
        fw=self.focus_get()
        if isinstance(fw,(tk.Entry,tk.Text)): return
        pairs = self.data.get(self.file, [])
        if not pairs: return "break"
        if self._idx is None: 
            self._edit(0)
        else:
            if self._idx < len(pairs)-1: self._edit(self._idx+1)
        return "break"    
    
    # Undo list-ops unless focus is in Entry/Text
    def _on_undo(self, e=None):
        fw = self.focus_get()
        if isinstance(fw, (tk.Entry, tk.Text)):
            return
        self._undo()
        return "break"
    
    # Redo list-ops unless focus is in Entry/Text
    def _on_redo(self, e=None):
        fw = self.focus_get()
        if isinstance(fw, (tk.Entry, tk.Text)):
            return
        self._redo()
        return "break"

    
def flush_current(self):
        # Only update when an item is selected; do not create new entries here
        if getattr(self, "file", None) is None:
            return
        idx = getattr(self, "_idx", None)
        if idx is None:
            return
        old = self.t_old.get("1.0", "end-1c")
        new = self.t_new.get("1.0", "end-1c")
        arr = self.data.setdefault(self.file, [])
        if 0 <= idx < len(arr):
            arr[idx] = (old, new)
        old = self.t_old.get("1.0", "end-1c")
        new = self.t_new.get("1.0", "end-1c")

        file_map = self.data.setdefault(self.file, [])

        # If nothing typed, nothing to do
        if (not old and not new) and self._idx is None:
            return

        idx = self._idx

        # If no card selected yet, append as a new pair
        if idx is None:
            file_map.append((old, new))      # tuple
            self._idx = len(file_map) - 1
            return

        # If index beyond list (rare), append
        if idx >= len(file_map):
            file_map.append((old, new))      # tuple
            self._idx = len(file_map) - 1
            return

        # Normal in-place update
        file_map[idx] = (old, new)           # tuple




# ====== Additions (BEGIN/END + text) ======
AdditionItem = Tuple[str, str]


class EditorAdditions(ttk.Frame):

    # --- save/export: Additions ---
    save_key = "FILE_ADDITIONS"
    def export_for_file(self):
            import copy as _copy
            file_key = getattr(self, "file", None)
            if not file_key:
                return None
            # Use normalized live array to reflect deletions
            if hasattr(self, "_arr"):
                arr = list(self._arr())
            else:
                arr = self.data.get(file_key, [])
            # normalize tuples
            norm = []
            if isinstance(arr, list):
                for it in arr:
                    if isinstance(it, (list, tuple)) and len(it) >= 2:
                        pos, txt = it[0], it[1]
                    else:
                        pos, txt = "end", it
                    pos = pos if pos in ("begin","end") else "end"
                    norm.append((pos, str(txt) if txt is not None else ""))
            return (file_key, _copy.deepcopy(norm))

    def __init__(self, master, data: Dict[str, List[Union[str, AdditionItem]]], file_path: str):
        super().__init__(master, padding=10); _ttk_setup()
        self.data = data; self.file=file_path
        self._idx: Optional[int]=None
        self._hist: List[Tuple[str, tuple]]=[]; self._redo: List[Tuple[str, tuple]]=[]; self._replaying=False

        top = tk.Frame(self, bg=C_BG); top.grid(row=0, column=0, columnspan=2, sticky="ew")
        tk.Label(top, text="File additions", font=FONT_TITLE_H2, bg=C_BG, fg=C_TEXT).pack(side="left")
        tk.Label(top, text=f"{file_path}", font=FONT_BASE_BOLD, bg=C_BG, fg=C_SUB).pack(side="right")

        self.grid_columnconfigure(0, weight=1); self.grid_rowconfigure(1, weight=1)

        listfrm = tk.Frame(self, bg=C_BG); listfrm.grid(row=1, column=0, sticky="nsew")
        self.scroll = Scrollable(listfrm); self.scroll.pack(fill="both", expand=True, pady=(4,0))
        
        fbar = tk.Frame(listfrm, bg=C_BG); fbar.pack(fill="x", pady=(6,4))
        # Button: Add new pair
        self.plus_pair = Icon.Button(
            fbar, "add", command=self._add, tooltip="Add new entry", pack={"side": "left", "padx": (0,0)}) 




        ed = tk.Frame(self, bg=C_BG); ed.grid(row=2, column=0, sticky="ew", pady=(8,0))
        ed.grid_columnconfigure(0, weight=1)
        tk.Label(ed, text="Position", bg=C_BG, fg=C_SUB, font=FONT_BASE_BOLD).grid(row=0, column=0, sticky="w")
        pos = tk.Frame(ed, bg=C_BG); pos.grid(row=1, column=0, sticky="w", pady=(0,6))
        self.pos_var = tk.StringVar(value="end")
        self.rb_begin = tk.Radiobutton(pos, text="BEGIN", value="begin", variable=self.pos_var,
                             bg=C_BG, fg=C_TEXT, activebackground=C_PANEL_HOVER,
                             selectcolor=C_PANEL_SEL, highlightthickness=0, state="disabled")
        self.rb_end = tk.Radiobutton(pos, text="END", value="end", variable=self.pos_var,
                             bg=C_BG, fg=C_TEXT, activebackground=C_PANEL_HOVER,
                             selectcolor=C_PANEL_SEL, highlightthickness=0, state="disabled")
        self.rb_begin.pack(side="left"); self.rb_end.pack(side="left", padx=(10,0))
        tk.Label(ed, text="Text", bg=C_BG, fg=C_SUB, font=FONT_BASE_BOLD).grid(row=2, column=0, sticky="w")
        self.t = mk_text(ed, 8); self.t.grid(row=3, column=0, sticky="nsew"); self.t.config(state="disabled")

        self._render()

        def _mod(_e=None):
            if self._idx is None: return
            arr = self._arr()
            if not (0<=self._idx<len(arr)): return
            arr[self._idx] = (self.pos_var.get(), self.t.get("1.0","end-1c"))
            self._update_card_inplace(self._idx)
            _event_changed(self)
        self.t.bind("<<Modified>>", lambda e: (self.t.edit_modified(False), _mod()), add="+")
        self.pos_var.trace_add("write", lambda *_: _mod())

        # DELETE: works even if focus in Text, as long as no selection
        def _on_del(e=None):
            fw=self.focus_get()
            if isinstance(fw, tk.Text):
                try: sel = bool(fw.tag_ranges("sel"))
                except Exception: sel = False
                if sel: return
            if self._idx is not None:
                self._del(self._idx); return "break"
        self.bind_all("<Delete>", _on_del, add="+")
        self.bind_all("<Control-z>", self._on_undo, add="+")
        self.bind_all("<Control-y>", self._on_redo, add="+")
        self.bind_all("<Control-Shift-Z>", self._on_redo, add="+")
        for bg in (self.scroll.inner, self.scroll.canvas):
            bg.bind("<Button-1>", lambda e: self._deselect())

    def flush_current(self):
        if self._idx is None: return
        arr = self._arr()
        if 0 <= self._idx < len(arr):
            arr[self._idx] = (self.pos_var.get(), self.t.get("1.0","end-1c"))

    def _arr(self) -> List[AdditionItem]:
        raw = self.data.setdefault(self.file, [])
        coerced: List[AdditionItem] = []
        changed = False
        for it in raw:
            if isinstance(it, tuple) and len(it)==2 and it[0] in ("begin","end"):
                coerced.append((it[0], it[1]))
            else:
                coerced.append(("end", str(it))); changed = True
        if changed: self.data[self.file] = coerced
        return self.data[self.file]

    def _render(self):
        for w in self.scroll.inner.winfo_children(): w.destroy()
        for i,(pos, txt) in enumerate(self._arr()):
            top = f"[{pos.upper()}]"
            card = PairCard(self.scroll.inner, i, top, txt,
                            on_click=lambda idx=i: self._edit(idx),
                            on_delete=lambda idx=i: self._del(idx),
                            on_select=lambda idx=i: self._select(idx))
            card.lbl_top.configure(fg="#9fd1ff")
            card.pack(fill="x", padx=(0,10), pady=6)
        if self._arr() and self._idx is None:
            self._edit(0)
        elif self._idx is not None and 0 <= self._idx < len(self._arr()):
            self._select(self._idx)

    def _update_card_inplace(self, idx:int):
        ch = [w for w in self.scroll.inner.winfo_children() if isinstance(w, PairCard)]
        if 0 <= idx < len(ch):
            pos, txt = self._arr()[idx]
            card: PairCard = ch[idx]
            card.lbl_top.config(text=f"[{pos.upper()}]")
            card.lbl_bot.config(text=(txt or "").strip())

    def _render_keep(self, keep):
        y = self.scroll.canvas.yview(); self._render(); self.scroll.canvas.yview_moveto(y[0]); self._select(keep)
    def _select(self, idx:int):
        self._idx = idx; i=0
        for w in self.scroll.inner.winfo_children():
            if isinstance(w, PairCard): w.set_selected(i==idx); i+=1
    def _edit(self, idx:int):
        if not (0<=idx<len(self._arr())): return
        pos, txt = self._arr()[idx]; self._select(idx)
        self.rb_begin.config(state="normal"); self.rb_end.config(state="normal")
        self.t.config(state="normal")
        self.pos_var.set(pos)
        self.t.delete("1.0","end"); self.t.insert("1.0", txt)
        self.t.edit_reset(); self.t.edit_separator()
    def _deselect(self):
        self._idx=None
        for w in self.scroll.inner.winfo_children():
            if isinstance(w, PairCard): w.set_selected(False)
        # lock and clear editors
        self.rb_begin.config(state="disabled"); self.rb_end.config(state="disabled")
        self.t.config(state="normal"); self.t.delete("1.0","end"); self.t.config(state="disabled")

    def _push(self,op,data):
        if self._replaying: return
        self._hist.append((op,data)); self._redo.clear()
    def _undo(self):
        if not self._hist: return
        op,data=self._hist.pop(); self._replaying=True
        try:
            if op=="ADD": idx,val=data; self._raw_del(idx)
            elif op=="DEL": idx,val=data; self._raw_insert(idx,val)
            elif op=="MOVE": i,j=data; self._raw_swap(i,j)
        finally: self._replaying=False
        self._redo.append((op,data))
    def _redo(self):
        if not self._redo: return
        op,data=self._redo.pop(); self._replaying=True
        try:
            if op=="ADD": idx,val=data; self._raw_insert(idx,val)
            elif op=="DEL": idx,val=data; self._raw_del(idx)
            elif op=="MOVE": i,j=data; self._raw_swap(i,j)
        finally: self._replaying=False
        self._hist.append((op,data))

    def _raw_insert(self, idx, val: AdditionItem):
        arr=self._arr(); arr.insert(idx,val); self._render_keep(idx); _event_changed(self)
    def _raw_del(self, idx):
        arr=self._arr()
        if 0<=idx<len(arr): arr.pop(idx)
        self._idx=None; self._render(); _event_changed(self)
    def _raw_swap(self, i,j):
        arr=self._arr()
        if 0<=i<len(arr) and 0<=j<len(arr): arr[i],arr[j]=arr[j],arr[i]
        self._render_keep(j); _event_changed(self)

    def _add(self):
        arr=self._arr(); idx = self._idx+1 if self._idx is not None else len(arr)
        val=("end","")
        self._push("ADD",(idx,val)); self._raw_insert(idx,val)
    def _del(self, idx):
        arr=self._arr()
        if not (0<=idx<len(arr)): return
        self._push("DEL",(idx, arr[idx])); self._raw_del(idx)
    def _move(self, d:int):
        if self._idx is None: return
        i=self._idx; j=i+d; arr=self._arr()
        if 0<=j<len(arr): self._push("MOVE",(i,j)); self._raw_swap(i,j)

    # navigation (delegated by window)
    def _nav_up(self, e=None):
        fw=self.focus_get()
        if isinstance(fw,(tk.Entry,tk.Text)): return
        arr=self._arr()
        if not arr: return "break"
        if self._idx is None: self._edit(0)
        else:
            if self._idx>0: self._edit(self._idx-1)
        return "break"
    def _nav_down(self, e=None):
        fw=self.focus_get()
        if isinstance(fw,(tk.Entry,tk.Text)): return
        arr=self._arr()
        if not arr: return "break"
        if self._idx is None: self._edit(0)
        else:
            if self._idx<len(arr)-1: self._edit(self._idx+1)
        return "break"
    
    def _on_undo(self, e=None):
        fw = self.focus_get()
        if isinstance(fw, (tk.Entry, tk.Text)):
            return
        self._undo()
        return "break"

    def _on_redo(self, e=None):
        fw = self.focus_get()
        if isinstance(fw, (tk.Entry, tk.Text)):
            return
        self._redo()
        return "break"

# ====== Files (single mapping for the file) ======
class EditorFileMap(ttk.Frame):
    def __init__(self, master, data: Dict[str,str], file_path: str):
        super().__init__(master, padding=10); _ttk_setup()
        self.data = data; self.file = file_path
        self.columnconfigure(1, weight=1)   
        
        top = tk.Frame(self, bg=C_BG); top.grid(row=0, column=0, columnspan=2, sticky="ew")     
        tk.Label(top, text="Replace whole files", font=FONT_TITLE_H2, bg=C_BG, fg=C_TEXT).pack(side="left")
        tk.Label(top, text=f"{file_path}", font=FONT_BASE_BOLD, bg=C_BG, fg=C_SUB).pack(side="right")
        
        ttk.Label(self, text="Replacement filename:", font=FONT_BASE_BOLD).grid(row=1, column=0, sticky="e", pady=(10,0))        
        self.e = PlaceholderEntry(self, "e.g. cabin.c (no path!)")
        self.e.grid(row=1, column=1, sticky="ew", padx=(6,0), pady=(10,0))
        
        # Button
        def btn_grid(btn_row, btn_column): return {"row": btn_row, "column": btn_column, "padx": (6, 0), "pady": (10,0)}
        Button(self, text="Browse…", command=self._browse, grid=btn_grid(1,2), tooltip="Choose the file")        
        Button(self, text="Save", command=self._save, grid=btn_grid(2,2), tooltip="Save the file mapping")
        
        if self.file in self.data: self.e.insert(0, os.path.basename(self.data[self.file]))
        
        
        
    def _browse(self):
        p = filedialog.askopenfilename(title="Select file")
        if p: 
            self.e.delete(0, tk.END); self.e.insert(0, os.path.basename(p))
    def _save(self):
        v = os.path.basename((self.e.get() or "").strip())
        if not v:
            if self.file in self.data: del self.data[self.file]
        else:
            self.data[self.file] = v
        messagebox.showinfo("Saved", "Mapping updated."); _event_changed(self)


def _summarize_line_repl(d):
    # Zwraca: {file: {fun: len(par)}}
    out = {}
    if not isinstance(d, dict): return out
    for f, fmap in d.items():
        m = {}
        if isinstance(fmap, dict):
            for fun, seq in fmap.items():
                if isinstance(seq, list):
                    m[fun] = len(seq)
        out[f] = m
    return out

def _first_chars(s, n=40):
    s = "" if s is None else str(s)
    s = s.replace("\n","⏎")
    return (s[:n] + "…") if len(s) > n else s






# ====== Public factory (window) ======
def open_edit_sheet(parent: tk.Misc, payload: Dict[str, Any], fpath: str, on_save=None):
    working = payload    
    
    def _resolve_file_key(d: dict, fpath: str) -> str:
        import os
        base = os.path.basename(fpath or "")
        if isinstance(d, dict):
            for k in d.keys():
                try:
                    if os.path.basename(k) == base:
                        return k
                except Exception:
                    pass
        return fpath  # jeśli nie znaleziono – używaj przekazanej ścieżki

    fkey_line = _resolve_file_key(working.get("LINE_REPLACEMENTS", {}), fpath)
    fkey_fun  = _resolve_file_key(working.get("FUNCTION_REPLACEMENTS", {}), fpath)
    fkey_gen  = _resolve_file_key(working.get("FILE_LINE_REPLACEMENTS", {}), fpath)
    fkey_add  = _resolve_file_key(working.get("FILE_ADDITIONS", {}), fpath)
    fkey_file = _resolve_file_key(working.get("FILE_REPLACEMENTS", {}), fpath)
    
    
    
    
    win = tk.Toplevel(parent)
    win.title("Edit")
    win.configure(bg=C_BG)
    win.geometry("1100x760")
    win.minsize(980, 620)
    win.transient(parent.winfo_toplevel())
    win.withdraw()
    
    Titlebar.set_icon(win)

    nb = ttk.Notebook(win); nb.pack(fill="both", expand=True, padx=8, pady=8)    

    def add_tab(widget_factory, title: str):
        try:
            tab = widget_factory(nb)
            nb.add(tab, text=title)
        except Exception:
            holder = ttk.Frame(nb)
            txt = tk.Text(holder, bg="#1b2a44", fg="#ffcccc", relief="flat")
            txt.pack(fill="both", expand=True, padx=6, pady=6)
            txt.insert("1.0", f"Error while building '{title}':\n\n{traceback.format_exc()}")
            txt.configure(state="disabled")
            nb.add(holder, text=f"{title} (error)")

    add_tab(lambda p: EditorLineRepl(p,           working["LINE_REPLACEMENTS"],     fkey_line), "Function lines")
    add_tab(lambda p: EditorFunctionMappings(p,   working["FUNCTION_REPLACEMENTS"], fkey_fun),  "Functions")
    add_tab(lambda p: EditorGeneralPairs(p,       working["FILE_LINE_REPLACEMENTS"],fkey_gen),  "General lines")
    add_tab(lambda p: EditorAdditions(p,          working["FILE_ADDITIONS"],        fkey_add),  "Additions")
    add_tab(lambda p: EditorFileMap(p,            working["FILE_REPLACEMENTS"],     fkey_file), "Files")




    # delegate shortcuts to active tab
    def _delegate(name):
        try: cur = nb.nametowidget(nb.select()); return getattr(cur, name, None)
        except Exception: return None

    def _on_delete(e=None):
        m = _delegate("_on_delete")
        if callable(m):
            r = m()
            if r == "break": return "break"

    def _on_undo(e=None):
        m = _delegate("_on_undo")
        if callable(m):
            r = m()
            if r == "break": return "break"

    def _on_redo(e=None):
        m = _delegate("_on_redo")
        if callable(m):
            r = m()
            if r == "break": return "break"

    # Global arrow ↑/↓ delegation
    def _on_up(e=None):
        m = _delegate("_nav_up")
        if callable(m):
            r = m()
            if r == "break": return "break"
    def _on_down(e=None):
        m = _delegate("_nav_down")
        if callable(m):
            r = m()
            if r == "break": return "break"

    # Clear focus when clicking outside Entry/Text
    def _click_clear_focus(e=None):
        w = e.widget
        while isinstance(w, tk.Misc):
            if isinstance(w, (tk.Entry, tk.Text)):
                return
            w = w.master
        try:
            win.focus_set()
        except Exception:
            pass
        
    # Use bind_all so work for the whole window, but we do not interrupt other handlers (add = "+")
    win.bind_all("<Button-1>", _click_clear_focus, add="+")

    win.bind("<Delete>", _on_delete)
    win.bind("<Control-z>", _on_undo)
    win.bind("<Control-y>", _on_redo)
    win.bind("<Control-Shift-Z>", _on_redo)
    win.bind("<Up>", _on_up)
    win.bind("<Down>", _on_down)
    
    

    # Save / Cancel
    bar = ttk.Frame(win); bar.pack(fill="x", padx=8, pady=(0,8))



    def _is_blank(v):
        if v is None: return True
        if isinstance(v, str): return v.strip() == ""
        if isinstance(v, (list, tuple, dict)): return len(v) == 0
        return False
    
    def _clean_seq(seq):
        out = []
        removed = 0
        for a,b in seq:
            if (isinstance(a, str) and a.strip()) or (isinstance(b, str) and b.strip()):
                out.append((a,b))
            else:
                removed += 1
        return out
    
    def _clean_seq_map(d):
        if not isinstance(d, dict): return {}
        out = {}
        for fp, seq in d.items():
            if isinstance(seq, list):
                seq2 = [it for it in seq if it]  # usuń puste elementy
                if seq2: out[fp] = seq2
        return out
    for key in ("FILE_ADDITIONS", "FILE_LINE_REPLACEMENTS"):
        working[key] = _clean_seq_map(working.get(key, {}))
    
    def _clean_fun_map(d):
        if not isinstance(d, dict):
            return {}
        out = {}
        for fp, fmap in d.items():
            if not isinstance(fmap, dict):
                continue
            cleaned_fmap = {}
            for fn, seq in fmap.items():
                if isinstance(seq, list):
                    cleaned_seq = _clean_seq(seq)
                    # ZAPISUJEMY NAWET JEŚLI PUSTE:
                    cleaned_fmap[fn] = cleaned_seq
            # ZAPISUJEMY NAWET JEŚLI PUSTY SŁOWNIK FUNKCJI:
            out[fp] = cleaned_fmap
        return out
            
    working["LINE_REPLACEMENTS"] = _clean_fun_map(working.get("LINE_REPLACEMENTS", {}))
    
    
    def _cleanup_inplace(w: Dict[str, Any]):
        
        # 1) FILE_REPLACEMENTS
        fr = w.get("FILE_REPLACEMENTS", {})
        if isinstance(fr, dict):
            w["FILE_REPLACEMENTS"] = {k: v for k, v in fr.items() if not _is_blank(v)}
    
        # 2) FILE_ADDITIONS
        fa = w.get("FILE_ADDITIONS", {})
        if isinstance(fa, dict):
            fa2 = {}
            for fp, seq in fa.items():
                if isinstance(seq, list):
                    cleaned = _clean_seq(seq)
                    fa2[fp] = cleaned  # keep empty to signal explicit clear
            w["FILE_ADDITIONS"] = fa2
            
        # 3) FILE_LINE_REPLACEMENTS
        flr = w.get("FILE_LINE_REPLACEMENTS", {})
        if isinstance(flr, dict):
            flr2 = {}
            for fp, seq in flr.items():
                if isinstance(seq, list):
                    cleaned = _clean_seq(seq)
                    flr2[fp] = cleaned  # keep empty to signal explicit clear
            w["FILE_LINE_REPLACEMENTS"] = flr2

        # 4) LINE_REPLACEMENTS
        lr = w.get("LINE_REPLACEMENTS", {})
        if isinstance(lr, dict):
            w["LINE_REPLACEMENTS"] = _clean_fun_map(lr)
            
        # 5) FUNCTION_REPLACEMENTS
        frf = w.get("FUNCTION_REPLACEMENTS", {})
        if isinstance(frf, dict):
            # keep even empty per-file dicts to signal clear
            w["FUNCTION_REPLACEMENTS"] = {fp: d for fp, d in frf.items() if isinstance(d, dict)}
    def do_save():
        import copy
        try:
            win.update_idletasks()
        except Exception:
            pass
        cur = nb.select()
        try:
            widget = nb.nametowidget(cur)
        except Exception:
            widget = None
        # Collect editors
        try:
            tab_ids = list(nb.tabs())
        except Exception:
            tab_ids = []
        editors = []
        for tid in tab_ids:
            try:
                w = nb.nametowidget(tid)
                editors.append(w)
            except Exception:
                pass
        _ml_dbg(f"tabs={len(editors)} cur={getattr(widget,'__class__',type(widget)).__name__ if widget else None} file={getattr(widget,'file',None)}")
        # PASS 1: flush all
        for w in editors:
            try:
                if hasattr(w, 'flush_current'):
                    w.flush_current()
            except Exception as e:
                _ml_dbg(f"flush err {type(w).__name__}: {e}")
        
        # PASS 2: export all into working
        for w in editors:
            try:
                if hasattr(w, 'export_for_file') and hasattr(w, 'save_key'):
                    kv = w.export_for_file()
                    if kv:
                        _k, _v = kv
                        working.setdefault(w.save_key, {})
                        working[w.save_key][_k] = _v
                        _ml_dbg(f"export {w.save_key} file={_k} size={len(_v) if hasattr(_v,'__len__') else 'n/a'}")
            except Exception as e:
                _ml_dbg(f"export err {type(w).__name__}: {e}")
        # Cleanup
        _cleanup_inplace(working)
        # Snapshot -> payload
        snapshot = copy.deepcopy(working)
        for key, wval in snapshot.items():
            if isinstance(wval, dict):
                if not isinstance(payload.get(key), dict):
                    payload[key] = {}
                payload[key].clear(); payload[key].update(wval)
            elif isinstance(wval, list):
                if not isinstance(payload.get(key), list):
                    payload[key] = []
                del payload[key][:]; payload[key].extend(wval)
            else:
                payload[key] = wval
        # Fire change + close
        try:
            root = win
            while root.master:
                root = root.master
        except Exception:
            root = parent
        _event_changed(root)
        win.destroy()
    btn_pack = {'side': 'right', 'padx': (0, 6)}


    btn_save = Button(bar, text="Save", command=do_save, pack=btn_pack, type="special")
    btn_cancel = Button(bar, text="Cancel", command=win.destroy, pack=btn_pack)         
    win.bind_all("<Escape>",    lambda e: btn_cancel.invoke())
    win.bind_all("<Control-s>", lambda e: btn_save.invoke())
    win.bind_all("<Command-s>", lambda e: btn_save.invoke())
    
    win.update_idletasks()
    Window.center_on_parent(win, parent.winfo_toplevel())
    win.deiconify()
    win.grab_set()
    
    # Start with no focused input (caret off)
    win.after_idle(lambda: win.focus_set())
    
    


def flush_current(self):
    v = os.path.basename((self.e.get() or "").strip())
    if not v:
        if self.file in self.data:
            try:
                del self.data[self.file]
            except KeyError:
                pass
    else:
        self.data[self.file] = v

