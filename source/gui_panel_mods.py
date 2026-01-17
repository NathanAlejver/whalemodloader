#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import re, sys, json, types, shutil, importlib.util, os, webbrowser, json
from gui_common import style_scrollbar, COLOR_PALETTE as COLOR, ICON_SIZE, FONTS
from gui_common import Tooltip, Button, Scrollable, Icon, HSeparator, Window, Titlebar, FileManagement, InputText, InputTextStatic, InputMultiline, CustomCombo
from PIL import Image, ImageTk, ImageOps, ImageEnhance
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional
import tkinter as tk
from tkinter import ttk, messagebox
import ModLoader
from gui_editor_replacements import ReplacementsBrowser


CARD_BG          = COLOR["card_bg"]
CARD_BG_HOVER    = COLOR["card_bg_hover"]
CARD_BG_ACTIVE   = COLOR["card_bg_active"]
CARD_BG_DISABLED = COLOR["card_bg_disabled"]

BADGE_BG         = COLOR["badge_bg"]
BADGE_FG         = COLOR["badge_fg"]
BADGE_BORDER     = COLOR["badge_border"]

DIVIDER          = COLOR["divider"]

TEXT_FG          = COLOR["text"]
TEXT_DISABLED    = COLOR["text_disabled"]
DESC_FG          = COLOR["desc"]
DESC_DISABLED    = COLOR["desc_disabled"]
META_FG          = COLOR["meta"]

INPUT_BG         = COLOR["input_bg"]
INPUT_BORDER     = COLOR["input_bd"]

FONT_TITLE_H1    = FONTS["title_h1"]
FONT_TITLE_H2    = FONTS["title_h2"]
FONT_MONO        = FONTS["mono"]
FONT_BASE        = FONTS["base"]
FONT_BASE_BOLD   = FONTS["base_bold"]
FONT_BASE_MINI   = FONTS["base_mini"]

COLLAPSE_MAX_LINES = 60

MOD_THUMB_SIZE = 128  # square thumbnail size (px)
MOD_THUMB_PADX = 12  # space between thumb and text
MOD_THUMB_SIZE_COLLAPSED = MOD_THUMB_SIZE // 2

MODS_LEFT_MARGIN = 12
SHOW_PRIORITY_BADGE = False
MODS_UI_STATE_FILE = "mods_ui_state.json"

HERE = ModLoader.APP_DIR / "assets" / "settings"
SETTINGS_PATH = HERE / ".gui_modloader_settings.json"
MODS_PATH = ModLoader.APP_DIR / "mods"
DEF_COMBO_NAME = ModLoader.DEF_COMBO_NAME

RowRefs = Tuple[
    tk.Widget, tk.Widget, tk.Widget | None, tk.Widget | None, tk.Widget | None,
    tk.Widget, tk.BooleanVar, tk.Widget, tk.Widget, List[tk.Widget]
]

# ---------- lightweight tooltip independent of ttk ----------
class LocalTip:
    def __init__(self, widget: tk.Widget, text: str, delay_ms: int = 450, pad: int = 12):
        self.widget = widget
        self.text = text
        self.delay = delay_ms
        self.pad = pad
        self._after: Optional[str] = None
        self._tip: Optional[tk.Toplevel] = None
        widget.bind("<Enter>", self._enter, add="+")
        widget.bind("<Leave>", self._leave, add="+")
        widget.bind("<Motion>", self._move, add="+")
        widget.bind("<Button-1>", self._leave, add="+")
    def _enter(self, e): self._schedule(e.x_root, e.y_root)
    def _leave(self, e=None):
        if self._after:
            try: self.widget.after_cancel(self._after)
            except Exception: pass
            self._after = None
        if self._tip:
            try: self._tip.withdraw(); self._tip.destroy()
            except Exception: pass
            self._tip = None
    def _move(self, e):
        if self._tip: self._show(e.x_root, e.y_root)
        else: self._schedule(e.x_root, e.y_root)
    def _schedule(self, x, y):
        self._leave()
        self._after = self.widget.after(self.delay, lambda: self._show(x, y))
    def _show(self, x, y):
        if self._tip:
            self._tip.geometry(f"+{x+self.pad}+{y+self.pad}")
            self._tip.deiconify(); return
        tip = tk.Toplevel(self.widget); tip.overrideredirect(True); tip.attributes("-topmost", True)
        frame = tk.Frame(tip, bg=INPUT_BG, bd=1, highlightthickness=1, highlightbackground="#18334d")
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text=self.text, bg=INPUT_BG, fg=COLOR["desc"],
                 font=FONT_BASE_MINI, padx=6, pady=4, justify="left").pack()
        tip.geometry(f"+{x+self.pad}+{y+self.pad}"); self._tip = tip


class ModsPanel(ttk.Frame):
    def __init__(self, master, palette: dict, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.palette = palette
        self.bg = palette["panel"]
        self.configure(style="Panel.TFrame")
        # --- style ---
        self.style = ttk.Style(self)
        self.style.configure("Mods.Card.TFrame",        background=CARD_BG,        relief="flat", borderwidth=0)
        self.style.configure("Mods.CardHover.TFrame",   background=CARD_BG_HOVER,  relief="flat", borderwidth=0)
        self.style.configure("Mods.CardActive.TFrame",  background=CARD_BG_ACTIVE, relief="flat", borderwidth=0)
        self.style.configure("Mods.CardDisabled.TFrame",background=CARD_BG_DISABLED,relief="flat", borderwidth=0)

        self.style.configure("Mods.Title.TLabel",           foreground=TEXT_FG, font=FONT_TITLE_H2)
        self.style.configure("Mods.TitleDisabled.TLabel",   foreground=TEXT_DISABLED, font=FONT_TITLE_H2)
        self.style.configure("Mods.Intro.TLabel",           foreground=DESC_FG, font=FONT_BASE)
        self.style.configure("Mods.IntroDisabled.TLabel",   foreground=DESC_DISABLED, font=FONT_BASE)
        self.style.configure("Mods.Changes.TLabel",         foreground=DESC_FG, font=FONT_BASE)
        self.style.configure("Mods.ChangesDisabled.TLabel", foreground=DESC_DISABLED, font=FONT_BASE)
        self.style.configure("Mods.Meta.TLabel",            foreground=META_FG, font=FONT_BASE_MINI)
        self.style.configure("Mods.MetaDisabled.TLabel",    foreground=DESC_DISABLED, font=FONT_BASE_MINI)
        self.icons: dict[str, tk.PhotoImage] = {} # icon cache
        self.thumbs: dict[str, tk.PhotoImage] = {}  # thumbnail cache

        
        # ---list/drag/collapse state ---
        self._order: List[str] = []
        self._card_by_key: Dict[str, ttk.Frame] = {}
        self._mod_by_key: Dict[str, Dict[str, Any]] = {}
        self._row_refs: Dict[str, RowRefs] = {}
        self._drag = None
        self._collapsed = {}
        self._load_collapsed_from_settings()

        # --- auto refresh state ---
        self._auto_refresh = True
        self._watch_interval_ms = 1500
        self._watch_after = None
        self._pending_refresh = None
        self._pending_snapshot = None
        self._last_snapshot = None

        # --- top area ---
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        top = ttk.Frame(self)
        top.grid(row=0, column=0, sticky="ew", padx=MODS_LEFT_MARGIN, pady=(10, 6))
        top.columnconfigure(0, weight=1)

        # Title
        title_row = tk.Frame(top, bg=self.bg, bd=0, highlightthickness=0)
        title_row.grid(row=0, column=0, sticky="w")
        ttk.Label(title_row, text="Mods", font=FONT_TITLE_H1).pack(side=tk.LEFT)

        # Add Icon
        Icon.Button(title_row, "create", size=int(ICON_SIZE*1), command=self.add_new_mod,
                    tooltip="Create a new mod (Ctrl+N)", pack={"side":"left", "padx":(6, 0)})        
        
        Icon.Button(title_row, "folder", size=int(ICON_SIZE*1), command=lambda: FileManagement.Open(MODS_PATH, title="Open local mods folder"),
                    tooltip="Open local mods folder", pack={"side":"left", "padx":(10, 0)})
        
        Icon.Button(title_row, "refresh", size=int(ICON_SIZE*1), command=self.refresh,
                    tooltip="Reload and redraw the mods list (F5)", pack={"side":"left", "padx":(10, 0)})
        
        
        # Buttons
        def btn_grid(btn_column): return {"row": 0, "column": btn_column, "padx": (6, 0)}
        #Button(top, text="Refresh mod list", command=self.refresh, grid=btn_grid(1), tooltip="Reload and redraw the mods list (F5)")
        Button(top, text="Enable All", command=lambda: self._set_all(True), grid=btn_grid(2), tooltip="Make all mods active")
        Button(top, text="Disable All", command=lambda: self._set_all(False), grid=btn_grid(3), tooltip="Make all mods inactive")
        
        # Tips
        ttk.Label(top, text="All mods located in the /mods/ directory will appear here (after refreshing).\nTip: drag cards to reorder  •  Click title to expand/collapse  •  Ctrl+click Edit to open replacements.py directly",
                  foreground=META_FG, font=FONT_BASE_MINI)\
            .grid(row=1, column=0, columnspan=4, sticky="w", pady=(18, 0))

        # --- modlist area  ---
        outer = ttk.Frame(self)
        outer.grid(row=1, column=0, sticky="nsew", padx=0, pady=(0, 10))
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)
        self.scrollable = Scrollable(outer, bg=self.bg)
        self.scrollable.grid(row=0, column=0, sticky="nsew")
        
        # aliases
        self.canvas   = self.scrollable.canvas
        self.scroll_y = self.scrollable.vbar
        
        self.cards_frame = self.scrollable.inner
        self.cards_frame_id = self.scrollable._win_id
        self.cards_frame.grid_columnconfigure(0, weight=1)
        self.cards_frame.bind("<Configure>", lambda e: self._on_frame_configure())
        self.canvas.bind("<Configure>", lambda e: (self._on_canvas_resize(), self._update_wraplengths()))

        self.mods_dir = self._get_mods_dir()
        self.cards: List[ttk.Frame] = []
        self.refresh()
        
        self._start_autorefresh()
        self.bind("<Destroy>", lambda e: self._stop_autorefresh(), add="+")       
        
        # binds
        def _on_ctrl_n(_=None):
            try: self.add_new_mod()
            except Exception: pass
            return "break"

        def _on_f5(_=None):
            try:self.refresh()
            except Exception: pass
            return "break"
        try:
            top_level = self.winfo_toplevel()
            top_level.bind("<Control-n>", _on_ctrl_n, add="+")
            top_level.bind("<Control-N>", _on_ctrl_n, add="+")  # in case of Shift
            top_level.bind("<F5>", _on_f5, add="+")
        except Exception:
            pass

    # ---------- save/load ----------
    def _load_collapsed_from_settings(self):
        try:
            if not SETTINGS_PATH.exists():
                return
            data = json.loads(SETTINGS_PATH.read_text("utf-8"))
            collapsed = data.get("mods_collapsed", {})
            if isinstance(collapsed, dict):
                self._collapsed = {str(k).lower(): bool(v) for k, v in collapsed.items()}
        except Exception:
            pass

    def _save_collapsed_to_settings(self):
        try:
            # merge with existing settings, don't wipe gui_run keys
            data = {}
            try:
                if SETTINGS_PATH.exists():
                    data = json.loads(SETTINGS_PATH.read_text("utf-8"))
                    if not isinstance(data, dict):
                        data = {}
            except Exception:
                data = {}

            # Optionally store only collapsed=True to keep file small
            data["mods_collapsed"] = {k: True for k, v in self._collapsed.items() if v}

            SETTINGS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass



    # ---------- helpers / canvas ----------
    def _get_mods_dir(self) -> Path:
        try:
            # Prefer shared APP_DIR from ModLoader
            base_dir = getattr(ModLoader, "APP_DIR", None)
            if base_dir is None:
                base_dir = Path(ModLoader.__file__).resolve().parent

            return Path(base_dir) / "mods"
        except Exception:
            # Fallback na "standalone" uruchomienie .py
            return Path(__file__).resolve().parent / "mods"

    def _on_frame_configure(self):
        # Keep the inner window anchored at (0,0) to prevent overscroll above the content
        bbox = self.canvas.bbox(self.cards_frame_id)
        if not bbox:
            return

        x0, y0, x1, y1 = bbox

        # If the window drifted (e.g. due to layout quirks), snap it back
        if x0 != 0 or y0 != 0:
            try:
                self.canvas.coords(self.cards_frame_id, 0, 0)
            except Exception:
                pass
            bbox = self.canvas.bbox(self.cards_frame_id)
            if bbox:
                x0, y0, x1, y1 = bbox

        # Clamp scrollregion to start at 0,0 (no blank area above)
        w = max(x1, self.canvas.winfo_width())
        h = max(y1, self.canvas.winfo_height())
        self.canvas.configure(scrollregion=(0, 0, w, h))


    def _on_canvas_resize(self):
        bbox = self.canvas.bbox(self.cards_frame_id)
        if not bbox: return
        self.canvas.itemconfigure(self.cards_frame_id, width=self.canvas.winfo_width())


    # ---------- opening replacements.py ----------


    def _ensure_replacements_py(self, mod_dir: Path) -> Optional[Path]:
        """
        Ensure replacements.py exists for this mod.
        If missing, create a minimal template in mod_dir/replacements.py.
        Returns path to the found/created file, or None on fatal error.
        """
        candidates = [
            mod_dir / "replacements.py",
            mod_dir / "files" / "replacements.py",
            mod_dir / "functions" / "replacements.py",
            mod_dir / "lines" / "replacements.py",
        ]

        # If any known location already exists, use it
        for p in candidates:
            try:
                if p.exists() and p.is_file():
                    return p
            except Exception:
                pass

        # Otherwise create default one in the mod root
        target = candidates[0]
        template = (
            "#!/usr/bin/env python3\n"
            "# -*- coding: utf-8 -*-\n\n"
            "\"\"\"Whale Mod Loader - replacements\n\n"
            "If your mod had no replacements.py, WML generated this file automatically.\n"
            "Fill dictionaries below to patch game files.\n"
            "\"\"\"\n\n"
            "# Function-level replacements (file -> function -> list of (find, replace, optional_label))\n"
            "FUNCTION_REPLACEMENTS = {}\n\n"
            "# Line-level replacements (file -> list of (find, replace, optional_label))\n"
            "LINE_REPLACEMENTS = {}\n\n"
            "# Whole-file replacements / redirects (file -> new_content or file_path)\n"
            "FILE_REPLACEMENTS = {}\n"
        )

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(template, encoding="utf-8")
            return target
        except Exception as e:
            messagebox.showerror("Replacements", f"Failed to create replacements.py:\n{e}")
            return None


    def _open_replacements_py(self, mod_dir: Path):
        p = self._ensure_replacements_py(mod_dir)
        if not p:
            return
        FileManagement.Open(p)



    # --- wraplength ---
    def _update_wraplengths(self):
        if not self._row_refs:
            return
        avail = self.canvas.winfo_width()
        if avail <= 0:
            return
        LEFT_PAD = MODS_LEFT_MARGIN + 10 + MOD_THUMB_SIZE + MOD_THUMB_PADX + 48
        max_right = 220
        for refs in self._row_refs.values():
            try:
                right_w = refs[8]
                max_right = max(max_right, right_w.winfo_width() + 30)
            except Exception:
                pass
        wrap_main  = max(200, avail - LEFT_PAD - max_right) 
        wrap_meta  = max(200, avail - LEFT_PAD - 24)
        for key, refs in self._row_refs.items():
            _, _, intro_w, changes_w, meta_w, *_ = refs
            for w in (intro_w, changes_w):
                if not w:
                    continue
                try:
                    w.configure(wraplength=wrap_main, justify="left")
                except Exception:
                    pass
            if meta_w:
                try:
                    meta_w.configure(wraplength=wrap_meta, justify="left")
                except Exception:
                    pass

    def _ellipsize(self, text: str, max_chars: int = 220) -> str:
        t = (text or "").strip()
        return t if len(t) <= max_chars else (t[:max_chars - 1].rstrip() + "…")

    # --- tooltips & icons ---
    def _load_icon(self, name: str, size: int = ICON_SIZE) -> tk.PhotoImage:
        key = f"{name}@{size}"
        if key in self.icons:
            return self.icons[key]
        path = Path(__file__).resolve().parent / "assets" / "icons" / f"{name}.png"
        try:
            img = tk.PhotoImage(file=str(path))
            if img.width() > size:
                factor = max(1, int(round(img.width() / size)))
                img = img.subsample(factor, factor)
        except Exception:
            img = tk.PhotoImage(width=1, height=1)
        self.icons[key] = img
        return img

    def _icon_label(self, parent: tk.Misc, icon_name: str, tooltip: str,
                    size: int = ICON_SIZE, row_key: str | None = None) -> tk.Label:
        img = self._load_icon(icon_name, size=size)
        img_hover = self._load_icon(icon_name + "_hover", size=size)
        lbl = tk.Label(parent, image=img, bg=parent["bg"], bd=0, highlightthickness=0)
        lbl.image = img; lbl._icon_default = img; lbl._icon_hover = img_hover
        lbl._tip = LocalTip(lbl, tooltip)
        def _enter(e):
            lbl.config(cursor="arrow")
            try:
                if lbl._icon_hover.width() > 1: lbl.configure(image=lbl._icon_hover)
            except Exception: pass
            if row_key: self._hover_apply(row_key)
        def _leave(e):
            lbl.configure(image=lbl._icon_default)
            if row_key: self._hover_clear(row_key)
        lbl.bind("<Enter>", _enter, add="+")
        lbl.bind("<Leave>", _leave, add="+")
        return lbl

    def _get_placeholder_thumb_path(self) -> Path:
        # Try JPG first (as requested), then PNG fallback if someone provides it
        base = Path(__file__).resolve().parent / "assets" / "icons"
        p_jpg = base / "mod_placeholder.jpg"
        if p_jpg.exists():
            return p_jpg
        p_png = base / "mod_placeholder.png"
        if p_png.exists():
            return p_png
        return p_jpg  # may not exist, but caller will handle

    # Load thumbnail
    def _resolve_mod_thumb_path(self, mod_dir: Path, raw: Dict[str, Any]) -> Path:
        candidates = [
            mod_dir / "thumbnail.png",
            mod_dir / "thumbnail.jpg",
            mod_dir / "thumbnail.jpeg",
        ]
        for p in candidates:
            try:
                if p.exists() and p.is_file():
                    return p
            except Exception:
                pass
        return self._get_placeholder_thumb_path()

    def _load_thumb_image(self, img_path: Path, size: int = MOD_THUMB_SIZE, toned_down: bool = False) -> tk.PhotoImage:
        # Cache by path + mtime + size
        try:
            rp = img_path.resolve()
        except Exception:
            rp = img_path

        mtime = 0
        try:
            if rp.exists():
                mtime = int(rp.stat().st_mtime)
        except Exception:
            mtime = 0

        key = f"{str(rp)}@{size}@{mtime}@{'td1' if toned_down else 'td0'}"
        if key in self.thumbs:
            return self.thumbs[key]

        # If the chosen file doesn't exist, fall back
        if not rp.exists():
            rp = self._get_placeholder_thumb_path()

        # PIL route (supports JPG/PNG/etc.)
        if Image is not None and ImageTk is not None:
            try:
                im = Image.open(str(rp))
                im = im.convert("RGBA")

                w, h = im.size
                s = min(w, h)
                left = (w - s) // 2
                top = (h - s) // 2
                im = im.crop((left, top, left + s, top + s))
                im = im.resize((size, size), Image.LANCZOS)
                if toned_down:
                    # // desaturate and slightly dim
                    im = ImageOps.grayscale(im).convert("RGBA")
                    im = ImageEnhance.Brightness(im).enhance(0.78)
                    im = ImageEnhance.Contrast(im).enhance(0.92)
                photo = ImageTk.PhotoImage(im)
                self.thumbs[key] = photo
                return photo
            except Exception:
                pass

        # Tk route (mostly PNG/GIF)
        try:
            photo = tk.PhotoImage(file=str(rp))
            if photo.width() > size:
                factor = max(1, int(round(photo.width() / size)))
                photo = photo.subsample(factor, factor)
            self.thumbs[key] = photo
            return photo
        except Exception:
            # Final fallback: empty image
            photo = tk.PhotoImage(width=size, height=size)
            self.thumbs[key] = photo
            return photo

    def _open_link(self, url: str):
        url = (url or "").strip()
        if not url:
            messagebox.showinfo("Link", "This mod has no link set. Use Edit to add one."); return
        if not (url.startswith("http://") or url.startswith("https://")):
            url = "https://" + url
        try:
            webbrowser.open(url)
        except Exception as e:
            messagebox.showerror("Link", f"Could not open link:\n{e}")

    # ---------- data ----------
    def _get_mod_roots(self) -> List[Tuple[Path, str]]:
        roots: List[Tuple[Path, str]] = []
    
        # Local mods folder
        try:
            if self.mods_dir.exists():
                roots.append((self.mods_dir, "Local"))
        except Exception:
            pass

        # Steam Workshop mods (if ModLoader exposes helpers)
        try:
            # game_root is defined in ModLoader; fall back to parent of script_dir
            game_root = Path(getattr(
                ModLoader,
                "game_root",
                Path(ModLoader.__file__).resolve().parent.parent
            ))
            find_ws_root = getattr(ModLoader, "find_workshop_content_root", None)
            ws_root: Optional[Path] = None

            if callable(find_ws_root):
                ws_root = find_ws_root(game_root)
            else:
                # Fallback – try to reconstruct from WORKSHOP_GAME_ID
                game_id = str(getattr(ModLoader, "WORKSHOP_GAME_ID", "")).strip()
                if game_id:
                    for anc in game_root.parents:
                        if anc.name.lower() == "steamapps":
                            ws_root = anc / "workshop" / "content" / game_id
                            break

            if ws_root and ws_root.exists():
                ws_root = ws_root.resolve()
                # top-level workshop folders (each Steam item)
                roots.append((ws_root, "Workshop"))

                # optional nested WhaleModLoader/mods per workshop item
                try:
                    for child in sorted(ws_root.iterdir()):
                        if not child.is_dir():
                            continue
                        nested = child / "WhaleModLoader" / "mods"
                        if nested.exists():
                            roots.append((nested, f"Workshop item: {child.name}"))
                except Exception:
                    pass
        except Exception:
            # If anything goes wrong here, we simply skip workshop mods
            pass

        # Deduplicate roots
        unique: List[Tuple[Path, str]] = []
        seen: set[str] = set()
        for root, label in roots:
            try:
                key = str(root.resolve())
            except Exception:
                key = str(root)
            if key in seen:
                continue
            seen.add(key)
            unique.append((root, label))
        return unique

    def _discover_mods(self) -> List[Dict[str, Any]]:
        mods: List[Dict[str, Any]] = []
        roots = self._get_mod_roots()
        if not roots:
            return mods

        for base_root, origin_label in roots:
            if not base_root.exists():
                continue
            for child in sorted(base_root.iterdir()):
                if not child.is_dir():
                    continue
                manifest = child / "manifest.json"
                if not manifest.exists():
                    continue
                try:
                    data = json.loads(manifest.read_text("utf-8"))
                except Exception as e:
                    data = {
                        "name": child.name,
                        "enabled": False,
                        "priority": 100,
                        "description": "",
                        "__error__": str(e),
                    }

                name = str(data.get("name") or child.name)
                enabled = bool(data.get("enabled", True))
                priority = int(data.get("priority", 100))
                description = str(data.get("description", ""))

                raw_changes = data.get("changes", [])
                if isinstance(raw_changes, list):
                    changes_list = [str(x).strip() for x in raw_changes if str(x).strip()]
                else:
                    changes_list = [
                        ln.strip(" \t-–")
                        for ln in str(raw_changes).splitlines()
                        if ln.strip()
                    ]

                # Get all data
                author = str(data.get("author", ""))
                game_ver = str(data.get("game_version", data.get("version_game", "")))
                mod_ver = str(data.get("mod_version", data.get("version_mod", "")))          
                
                # Variants
                variants = data.get("variants", None)
                if not isinstance(variants, list):
                    variants = []          
                variants_dir = child / "variants"
                if (not variants) and variants_dir.exists() and variants_dir.is_dir():
                    auto = []
                    try:
                        for vd in sorted(variants_dir.iterdir()):
                            if not vd.is_dir():
                                continue
                            vid = vd.name.strip()
                            if not vid:
                                continue
                            # label derived from folder name (cheap, readable)
                            lbl = vid.replace("_", " ").replace("-", " ")
                            auto.append({"id": vid, "label": lbl})
                    except Exception:
                        pass
                    variants = auto
                active_variant = str(data.get("active_variant", "")).strip()

                mods.append({
                    "dir": child,
                    "manifest": manifest,
                    "name": name,
                    "enabled": enabled,
                    "priority": priority,
                    "description": description,
                    "changes": changes_list,
                    "author": author,
                    "game_version": game_ver,
                    "mod_version": mod_ver,
                    "origin": origin_label,
                    "raw": data,
                    "variants": variants,
                    "active_variant": active_variant,
                })
        return mods




    def _set_all(self, enabled: bool):
        for m in self._discover_mods():
            m["enabled"] = enabled; self._save_manifest(m)
        self.refresh()

    def _normalize_priorities(self, mods: List[Dict[str, Any]]):
        base = 100
        for i, m in enumerate(mods):
            m["priority"] = base + i
            self._save_manifest(m)

    # ---- Drag & drop helpers ----
    def _key_for(self, m: Dict[str, Any]) -> str:
        return str(m["manifest"]).lower()

    def _ensure_order_covers(self, mods: List[Dict[str, Any]]):
        keys = [self._key_for(m) for m in mods]
        if not self._order: self._order = keys[:]
        else: self._order = [k for k in self._order if k in keys] + [k for k in keys if k not in self._order]

    def _grid_cards(self):
        for row, key in enumerate(self._order):
            card = self._card_by_key.get(key)
            if card: card.grid_configure(row=row * 2)

    def _on_card_press(self, event, key: str):
        self._drag = {"key": key, "y": event.y_root, "moved": False}
        card = self._card_by_key.get(key)
        if card:
            try: card.configure(style="Mods.CardActive.TFrame")
            except Exception: pass
        self._sync_label_bgs(key, CARD_BG_ACTIVE)

    def _on_card_motion(self, event):
        if not self._drag: return
        key = self._drag["key"]

        y_canvas = self.canvas.winfo_pointery() - self.canvas.winfo_rooty()
        h_canvas = self.canvas.winfo_height()
        if y_canvas < 40: self.canvas.yview_scroll(-1, 'units')
        elif y_canvas > h_canvas - 40: self.canvas.yview_scroll(1, 'units')

        y_local = self.cards_frame.winfo_pointery() - self.cards_frame.winfo_rooty()
        target_idx = None
        for i, k in enumerate(self._order):
            w = self._card_by_key.get(k)
            if not w: continue
            top = w.winfo_y(); h = w.winfo_height()
            if top <= y_local < top + h:
                target_idx = i; break
        if target_idx is None: return
        cur_idx = self._order.index(key)
        if target_idx != cur_idx:
            self._order.insert(target_idx, self._order.pop(cur_idx))
            self._drag["moved"] = True
            self._grid_cards(); self.cards_frame.update_idletasks()

    def _on_card_release(self, event):
        if not self._drag: return
        key = self._drag["key"]; moved = bool(self._drag.get("moved"))
        card = self._card_by_key.get(key)
        if card:
            refs = self._row_refs.get(key)
            en = refs[6].get() if refs else True
            try:
                card.configure(style=("Mods.Card.TFrame" if en else "Mods.CardDisabled.TFrame"))
                self._sync_label_bgs(key, CARD_BG if en else CARD_BG_DISABLED)
            except Exception: pass
        if moved:
            mods_in_order = [self._mod_by_key[k] for k in self._order if k in self._mod_by_key]
            self._normalize_priorities(mods_in_order)
            for k in self._order:
                m = self._mod_by_key.get(k); refs = self._row_refs.get(k)
                if not m or not refs: continue
                _, _, _, _, _, badge_w, _, _, _, _ = refs
                try: badge_w.configure(text=str(m["priority"]))
                except Exception: pass
        self._drag = None
        self.cards_frame.update_idletasks()

    # ---- Hover / Enabled sync ----
    def _sync_label_bgs(self, key: str, bg_color: str):
        refs = self._row_refs.get(key)
        if not refs: return
        _, title_w, intro_w, changes_w, meta_w, _, _, header_w, right_w, hover_children = refs
        for w in (header_w, title_w, intro_w, changes_w, meta_w, right_w, *hover_children):
            if not w: continue
            try: w.configure(background=bg_color)
            except Exception: pass
        if right_w:
            Icon.bg_changed(right_w)

    def _hover_apply(self, key: str):
        refs = self._row_refs.get(key)
        if not refs: return
        card_w, _, _, _, _, _, en_var, _, _, _ = refs
        if self._drag and self._drag.get("key") == key:
            try: card_w.configure(style="Mods.CardActive.TFrame")
            except Exception: pass
            self._sync_label_bgs(key, CARD_BG_ACTIVE)
        else:
            if en_var.get():
                try: card_w.configure(style="Mods.CardHover.TFrame")
                except Exception: pass
                self._sync_label_bgs(key, CARD_BG_HOVER)
            else:
                try: card_w.configure(style="Mods.CardDisabled.TFrame")
                except Exception: pass
                self._sync_label_bgs(key, CARD_BG_DISABLED)

    def _hover_clear(self, key: str):
        refs = self._row_refs.get(key)
        if not refs: return
        card_w, _, _, _, _, _, en_var, _, _, _ = refs
        if self._drag and self._drag.get("key") == key:
            try: card_w.configure(style="Mods.CardActive.TFrame")
            except Exception: pass
            self._sync_label_bgs(key, CARD_BG_ACTIVE)
        else:
            if en_var.get():
                try: card_w.configure(style="Mods.Card.TFrame")
                except Exception: pass
                self._sync_label_bgs(key, CARD_BG)
            else:
                try: card_w.configure(style="Mods.CardDisabled.TFrame")
                except Exception: pass
                self._sync_label_bgs(key, CARD_BG_DISABLED)

    def _apply_enabled_by_key(self, key: str, is_enabled: bool):
        refs = self._row_refs.get(key)
        if not refs: return
        card_w, title_w, intro_w, changes_w, meta_w, badge_w, _, header_w, right_w, hover_children = refs

        try:
            style = ("Mods.Card.TFrame" if is_enabled else "Mods.CardDisabled.TFrame")
            card_w.configure(style=style)
        except Exception: pass

        self._sync_label_bgs(key, CARD_BG if is_enabled else CARD_BG_DISABLED)

        try: title_w.configure(style=("Mods.Title.TLabel" if is_enabled else "Mods.TitleDisabled.TLabel"))
        except Exception: pass
        if intro_w is not None:
            try: intro_w.configure(style=("Mods.Intro.TLabel" if is_enabled else "Mods.IntroDisabled.TLabel"))
            except Exception: pass
        if changes_w is not None:
            try: changes_w.configure(style=("Mods.Changes.TLabel" if is_enabled else "Mods.ChangesDisabled.TLabel"))
            except Exception: pass
        if meta_w is not None:
            try: meta_w.configure(style=("Mods.Meta.TLabel" if is_enabled else "Mods.MetaDisabled.TLabel"))
            except Exception: pass

        try:
            badge_w.configure(bg=(BADGE_BG if is_enabled else "#0d1926"),
                              fg=(BADGE_FG if is_enabled else "#7f8da3"))
        except Exception: pass

        def _in(e=None, row_key=key): self._hover_apply(row_key)
        def _out(e=None, row_key=key): self._hover_clear(row_key)
        for w in (card_w, header_w, title_w, right_w, *(x for x in (intro_w, changes_w, meta_w) if x), *hover_children):
            try:
                w.bind("<Enter>", lambda e, rk=key: _in(row_key=rk), add="+")
                w.bind("<Leave>", lambda e, rk=key: _out(row_key=rk), add="+")
            except Exception: pass
            
        # --- update thumbnail tone when enabling/disabling ---
        try:
            collapsed_now = bool(self._collapsed.get(key, False))
            thumb_size_now = MOD_THUMB_SIZE_COLLAPSED if collapsed_now else MOD_THUMB_SIZE

            for child in card_w.winfo_children():
                if getattr(child, "_is_mod_thumb", False):
                    thumb_path_now = getattr(child, "_thumb_path", None)
                    if thumb_path_now is not None:
                        new_img = self._load_thumb_image(
                            thumb_path_now,
                            size=thumb_size_now,
                            toned_down=(not is_enabled)
                        )
                        child.configure(image=new_img)
                        child.image = new_img
                    break
        except Exception:
            pass
            

    # ---------- collapsible + opis/changes ----------
    def _split_description_fallback(self, raw: str) -> Tuple[str, List[str]]:
        text = (raw or "").strip()
        if not text:
            return "", []
        lower = text.lower()
        idx = lower.find("changes:")
        if idx != -1:
            intro = text[:idx].strip()
            rest = text[idx+8:].strip()
            lines = [ln.strip(" \t-–") for ln in rest.splitlines() if ln.strip()]
            return intro, lines
        parts = [p.rstrip() for p in text.splitlines()]
        intro_lines: List[str] = []
        changes: List[str] = []
        bullets = False
        for ln in parts:
            if ln.lstrip().startswith("-") or ln.lstrip().startswith("–"):
                bullets = True
            if bullets:
                if ln.strip():
                    changes.append(ln.strip(" \t-–"))
            else:
                intro_lines.append(ln)
        if bullets:
            return "\n".join(intro_lines).strip(), changes
        para = text.split("\n\n", 1)
        return (para[0].strip(), para[1].strip().splitlines()) if len(para) == 2 else (text, [])

    def _toggle_collapse(self, key: str):
        self._collapsed[key] = not self._collapsed.get(key, False)
        collapsed = self._collapsed.get(key, False)

        refs = self._row_refs.get(key)
        if not refs:
            return

        card_w, title_w, intro_w, changes_w, meta_w, _, _, header_w, _, _ = refs
        m = self._mod_by_key.get(key)

        # --- update chevron without rebuilding the whole list ---
        try:
            for child in header_w.winfo_children():
                if getattr(child, "_is_mod_chevron", False):
                    child.configure(text=("▸" if collapsed else "▾"))
                    break
        except Exception:
            pass

        # --- update intro text (ellipsize on collapse) ---
        if m and intro_w is not None:
            intro_text = str(m.get("description") or "")
            changes_list = m.get("changes") or []
            if not changes_list:
                intro_text, changes_list = self._split_description_fallback(intro_text)

            if collapsed:
                intro_text = self._ellipsize(intro_text, COLLAPSE_MAX_LINES)

            try:
                intro_w.configure(text=intro_text)
            except Exception:
                pass

        # --- show / hide changes block ---
        if changes_w is not None:
            try:
                if collapsed:
                    changes_w.grid_remove()
                else:
                    changes_w.grid()
            except Exception:
                pass

        # --- resize thumbnail on collapse/expand (no refresh) ---
        try:
            thumb_size = MOD_THUMB_SIZE_COLLAPSED if collapsed else MOD_THUMB_SIZE
            for child in card_w.winfo_children():
                if getattr(child, "_is_mod_thumb", False):
                    thumb_path = getattr(child, "_thumb_path", None)
                    if thumb_path is not None:                        
                        mod_data = self._mod_by_key.get(key)
                        enabled_now = True
                        if mod_data is not None:
                            enabled_now = bool(mod_data.get("enabled", True))
                        img = self._load_thumb_image(thumb_path, size=thumb_size, toned_down=(not enabled_now))
                        child.configure(image=img)
                        child.image = img
                    break
        except Exception:
            pass

        self.cards_frame.update_idletasks()
        self._on_frame_configure()
        self._update_wraplengths()
        self._save_collapsed_to_settings()

        # Snapshot of current discovered mods manifests: (path, mtime, size).
        # This catches: new/deleted mods (manifest appears/disappears), manifest edits (mtime/size changes)
    def _make_mods_snapshot(self):
        sig = []
        try:
            roots = self._get_mod_roots()
        except Exception:
            roots = []

        for root, _label in roots:
            try:
                if not root.exists():
                    continue
                for child in root.iterdir():
                    if not child.is_dir():
                        continue
                    manifest = child / "manifest.json"
                    if not manifest.exists():
                        continue
                    try:
                        st = manifest.stat()
                        sig.append((str(manifest).lower(), int(st.st_mtime), int(st.st_size)))
                    except Exception:
                        sig.append((str(manifest).lower(), 0, 0))
            except Exception:
                continue

        sig.sort()
        return tuple(sig)

    def _can_autorefresh_now(self) -> bool:
        try:
            root = self.winfo_toplevel()
            for w in root.winfo_children():
                if isinstance(w, tk.Toplevel) and w.winfo_exists():
                    try:
                        if w.state() != "withdrawn":
                            return False
                    except Exception:
                        return False
        except Exception:
            pass
        return True

    def _start_autorefresh(self):
        self._stop_autorefresh()
        self._last_snapshot = self._make_mods_snapshot()
        if self._auto_refresh:
            self._schedule_watch()

    def _stop_autorefresh(self):
        try:
            if self._watch_after:
                self.after_cancel(self._watch_after)
        except Exception:
            pass
        self._watch_after = None

        try:
            if self._pending_refresh:
                self.after_cancel(self._pending_refresh)
        except Exception:
            pass
        self._pending_refresh = None
        self._pending_snapshot = None

    def _schedule_watch(self):
        if not self._auto_refresh:
            return
        if not self.winfo_exists():
            return
        self._watch_after = self.after(self._watch_interval_ms, self._watch_tick)

    def _watch_tick(self):
        self._watch_after = None
        if not self._auto_refresh or not self.winfo_exists():
            return

        snap = self._make_mods_snapshot()

        # If changes happened:
        if snap != self._last_snapshot:
            # if we can't safely refresh now (e.g. editor window open), postpone
            if not self._can_autorefresh_now():
                self._pending_snapshot = snap
            else:
                self._last_snapshot = snap
                # debounce refresh a bit (Steam may create files in bursts)
                try:
                    if self._pending_refresh:
                        self.after_cancel(self._pending_refresh)
                except Exception:
                    pass
                self._pending_refresh = self.after(250, self.refresh)

        # If we postponed earlier and now it's safe, refresh once
        if self._pending_snapshot is not None and self._can_autorefresh_now():
            self._last_snapshot = self._pending_snapshot
            self._pending_snapshot = None
            try:
                if self._pending_refresh:
                    self.after_cancel(self._pending_refresh)
            except Exception:
                pass
            self._pending_refresh = self.after(250, self.refresh)

        self._schedule_watch()





    # ---------- render ----------
    def refresh(self):
        for c in getattr(self, 'cards', []):
            try: c.destroy()
            except Exception: pass
        self.cards = []; self._card_by_key.clear()
        self._mod_by_key.clear(); self._row_refs.clear()

        mods = self._discover_mods()
        if not mods:
            ttk.Label(self.cards_frame, text="No mods found in ./mods", font=FONT_BASE)\
                .grid(row=0, column=0, sticky="w", padx=6, pady=6)
            return

        mods.sort(key=lambda m: (m["priority"], m["name"].lower()))
        self._ensure_order_covers(mods)
        

        for row, m in enumerate(mods):
            key = self._key_for(m)
            self._mod_by_key[key] = m
            collapsed = self._collapsed.get(key, False)

            card = ttk.Frame(self.cards_frame, padding=(MODS_LEFT_MARGIN, 12, 12, 12), style="Mods.Card.TFrame")
            card.grid(row=row * 2, column=0, sticky="ew", padx=0, pady=0)
            
            is_enabled = bool(m.get("enabled", False))
            
            # Columns: [thumb] [content] [right buttons]
            card.columnconfigure(0, weight=0)
            card.columnconfigure(1, weight=1)
            card.columnconfigure(2, weight=0)
            hover_children: List[tk.Widget] = []
            
            # --- thumbnail (from manifest or placeholder) ---
            raw = m.get("raw") or {}
            thumb_path = self._resolve_mod_thumb_path(m["dir"], raw)
            thumb_size = MOD_THUMB_SIZE
            if self._collapsed.get(key, False):
                thumb_size = MOD_THUMB_SIZE_COLLAPSED

            thumb_img = self._load_thumb_image(thumb_path, size=thumb_size, toned_down=(not is_enabled))
            thumb_lbl = tk.Label(card, image=thumb_img, bg=CARD_BG, bd=0, highlightthickness=0)
            thumb_lbl.image = thumb_img
            thumb_lbl.grid(row=0, column=0, rowspan=10, sticky="nw", padx=(0, MOD_THUMB_PADX), pady=(0, 0))
            thumb_lbl._is_mod_thumb = True      # marker for collapse updates
            thumb_lbl._thumb_path   = thumb_path  # remember resolved path
            hover_children.append(thumb_lbl)
            
            self._card_by_key[key] = card

            header = tk.Frame(card, bg=CARD_BG, bd=0, highlightthickness=0)
            header.grid(row=0, column=1, sticky="ew")
            header.grid_columnconfigure(2, weight=1)
            
            pr = tk.Label(header, text=str(m['priority']),
                          font=FONT_BASE_BOLD, bg=BADGE_BG, fg=BADGE_FG,
                          padx=8, pady=2, bd=1, relief="solid", highlightthickness=0)
            pr.configure(borderwidth=1, highlightbackground=BADGE_BORDER, highlightcolor=BADGE_BORDER)
            if SHOW_PRIORITY_BADGE:
                pr.grid(row=0, column=0, padx=(0, 10), sticky="w")
                Tooltip(pr, "Priority (lower loads first)")

            chevron = tk.Label(header, text=("▸" if collapsed else "▾"), fg="#9fb7d9",
                               bg=CARD_BG, font=FONT_TITLE_H2)
            chevron.grid(row=0, column=1, padx=(0, 6), sticky="w")
            chevron.bind("<Button-1>", lambda e, k=key: self._toggle_collapse(k))
            chevron._is_mod_chevron = True  # marker for collapse updates


            title = ttk.Label(header, text=m["name"], style="Mods.Title.TLabel")
            title.grid(row=0, column=2, sticky="w")
            title.bind("<Button-1>", lambda e, k=key: self._toggle_collapse(k))

            intro_text = m.get("description") or ""
            changes_list: List[str] = m.get("changes") or []
            if not changes_list:
                intro_text, changes_list = self._split_description_fallback(intro_text)
            if collapsed:
                intro_text = self._ellipsize(intro_text, COLLAPSE_MAX_LINES)

            intro_lbl = None
            if intro_text:
                intro_lbl = ttk.Label(card, text=intro_text, style="Mods.Intro.TLabel",
                                      justify="left", wraplength=1)
                intro_lbl.grid(row=1, column=1, sticky="w", pady=(2, 0))

            changes_lbl = None
            if changes_list:
                bullets = "\n".join(f"– {x}" for x in changes_list)
                changes_lbl = ttk.Label(card, text=f"Changes:\n{bullets}",
                                        style="Mods.Changes.TLabel", justify="left", wraplength=1)
                row_changes = 2 if intro_lbl is not None else 1
                changes_lbl.grid(row=row_changes, column=1, sticky="w", pady=(6, 0))
                if collapsed:
                    changes_lbl.grid_remove()

            meta_lbl = None
            meta_parts: List[str] = []
            if m.get("game_version"): meta_parts.append(f"Game v{m['game_version']}")
            if m.get("mod_version"):  meta_parts.append(f"Mod v{m['mod_version']}")
            if m.get("author"):       meta_parts.append(f"by {m['author']}")
            
            origin_label = m.get("origin")
            if origin_label: meta_parts.append(str(origin_label))
            
            if meta_parts:
                meta_lbl = ttk.Label(
                    card, text=" • ".join(meta_parts),
                    style="Mods.Meta.TLabel", justify="left", wraplength=1
                )
                r = (3 if (intro_lbl and changes_lbl) else
                     2 if (intro_lbl and not changes_lbl) or (changes_lbl and not intro_lbl) else 1)
                meta_lbl = None
                meta_parts: List[str] = []
                if m.get("game_version"): meta_parts.append(f"Game v{m['game_version']}")
                if m.get("mod_version"):  meta_parts.append(f"Mod v{m['mod_version']}")
                if m.get("author"):       meta_parts.append(f"by {m['author']}")
                origin_label = m.get("origin")
                if origin_label:
                    meta_parts.append(str(origin_label))

                # --- spacer row pushes footer to bottom (card height often comes from thumbnail) ---
                spacer_row = (3 if (intro_lbl and changes_lbl) else
                            2 if ((intro_lbl and not changes_lbl) or (changes_lbl and not intro_lbl)) else 1)

                spacer = tk.Frame(card, bg=CARD_BG, bd=0, highlightthickness=0)
                spacer.grid(row=spacer_row, column=1, sticky="nsew")
                card.grid_rowconfigure(spacer_row, weight=1)
                hover_children.append(spacer)

                if meta_parts:
                    meta_lbl = ttk.Label(
                        card, text=" • ".join(meta_parts),
                        style="Mods.Meta.TLabel", justify="left", wraplength=1
                    )
                    meta_lbl.grid(row=spacer_row + 1, column=1, columnspan=2, sticky="sw", pady=(6, 0))


            # --- right column area ---
            right = tk.Frame(card, bg=CARD_BG, bd=0, highlightthickness=0)
            right.grid(row=0, column=2, sticky="ne", padx=(20, 0))
            Icon.bg_changed(right)
            
            # Toggle button
            enabled0 = bool(m.get("enabled", False))
            en_var = tk.BooleanVar(value=enabled0)

            def _on_toggle_enabled(state, rk=key, mm=m):
                new_val = bool(state)

                # IMPORTANT: ignore spurious initial callback (state didn't change)
                if bool(mm.get("enabled", False)) == new_val:
                    self._apply_enabled_by_key(rk, new_val)
                    return

                mm["enabled"] = new_val
                self._save_manifest(mm)
                self._apply_enabled_by_key(rk, new_val)

            # --- variant selector
            variants = m.get("variants") or []
            if isinstance(variants, list) and len(variants) > 0:
                items = [(DEF_COMBO_NAME, DEF_COMBO_NAME)]
                for v in variants:
                    if not isinstance(v, dict):
                        continue
                    vid = str(v.get("id") or "").strip()
                    if not vid:
                        continue
                    lbl = str(v.get("label") or vid).strip()
                    items.append((lbl, vid))

                if len(items) > 0:
                    # Determine current selection
                    current_vid = str(m.get("active_variant") or "").strip()
                    if current_vid == "":
                        current_vid = DEF_COMBO_NAME
                    current_lbl = items[0][0]
                    for lbl, vid in items:
                        if vid == current_vid:
                            current_lbl = lbl
                            break

                    var_box = CustomCombo(right, values=[x[0] for x in items], width=6, state="readonly")
                    var_box.set(current_lbl)
                    var_box.pack(side="left", padx=(0, 10))

                    def _on_variant_change(_e=None, mm=m, box=var_box, opts=items):
                        sel_lbl = str(box.get() or "")
                        sel_vid = ""
                        for l, v in opts:
                            if l == sel_lbl:
                                sel_vid = v
                                break
                        if not sel_vid:
                            return
                        mm["active_variant"] = sel_vid
                        raw = mm.get("raw") or {}
                        if sel_vid == DEF_COMBO_NAME:
                            if "active_variant" in raw:
                                del raw["active_variant"]
                            mm["active_variant"] = ""
                        else:
                            raw["active_variant"] = sel_vid
                            mm["active_variant"] = sel_vid

                        mm["raw"] = raw
                        self._save_manifest(mm)

                    var_box.bind("<<ComboboxSelected>>", _on_variant_change, add="+")

            # Mod switch
            btn_switch = Icon.Toggle(
                right,
                name="switch",
                variable=en_var,
                tooltip="Enable/disable this mod",
                command=_on_toggle_enabled,
                pack={"side": "left", "padx": (0, 10)}
            )



            hover_children.append(btn_switch)

            # Buttons            
            btn_edit = Icon.Button(right, "edit", command=lambda mm=m: self.edit_manifest(mm),
                        tooltip="Edit mod files", pack={"side":"left", "padx":(0, 0)})
            try: btn_edit.bind("<Control-Button-1>", lambda e, p=m["dir"]: (self._open_replacements_py(p), "break"), add="+")
            except Exception: pass

            Icon.Button(right, "folder", command=lambda p=m["dir"]: FileManagement.Open(p),
                        tooltip="Open mod directory", pack={"side":"left", "padx":(10, 0)})

            link_url = str((m.get("raw") or {}).get("link", "")).strip()
            btn_link = Icon.Button(
                right, "link",
                command=lambda url=link_url: self._open_link(url),
                tooltip=link_url or "No link in manifest (Edit to add)",
                pack={"side":"left", "padx":(10, 0)}
            )
            btn_link.set_enabled(bool(link_url))

            self._row_refs[key] = (
                card, title, intro_lbl, changes_lbl, meta_lbl, pr, en_var, header, right, hover_children
            )

            self._apply_enabled_by_key(key, bool(m["enabled"]))
            for w in (card, thumb_lbl, header, title, intro_lbl if intro_lbl else card,
                    changes_lbl if changes_lbl else card, meta_lbl if meta_lbl else card, right):
                try:
                    w.bind("<Button-1>",         lambda e, k=key: self._on_card_press(e, k), add="+")
                    w.bind("<B1-Motion>",        self._on_card_motion, add="+")
                    w.bind("<ButtonRelease-1>",  self._on_card_release, add="+")
                    w.bind("<Enter>",            lambda e, rk=key: self._hover_apply(rk), add="+")
                    w.bind("<Leave>",            lambda e, rk=key: self._hover_clear(rk), add="+")
                    self._bind_wheel_relay(w)
                except Exception: pass

            tk.Frame(self.cards_frame, height=1, bg=DIVIDER).grid(row=row * 2 + 1, column=0, sticky="ew", padx=0)
            self.cards.append(card)

        self.cards_frame.update_idletasks()
        self._on_frame_configure()
        self._update_wraplengths()
        self._grid_cards()

    # ---------- IO ----------
    
    def _open_dir(self, p: Path):
        try:
            if sys.platform.startswith("win"): os.startfile(str(p))  # type: ignore[attr-defined]
            elif sys.platform == "darwin": os.system(f'open "{p}"')
            else: os.system(f'xdg-open "{p}"')
        except Exception as e:
            messagebox.showerror("Open folder", f"Failed to open folder:\n{e}")

    def _ack_autorefresh_snapshot(self):
        try:
            if hasattr(self, "_make_mods_snapshot"):
                self._last_snapshot = self._make_mods_snapshot()
            self._pending_snapshot = None
            if getattr(self, "_pending_refresh", None):
                try: self.after_cancel(self._pending_refresh)
                except Exception: pass
                self._pending_refresh = None
        except Exception:
            pass


    def _save_manifest(self, m: Dict[str, Any]):
        data = dict(m.get("raw") or {})
        data["name"] = m["name"]
        data["enabled"] = bool(m["enabled"])
        data["priority"] = int(m["priority"])
        if m.get("description") is not None:
            data["description"] = m.get("description")
        if m.get("changes") is not None:
            data["changes"] = list(m.get("changes") or [])
        if m.get("author"): data["author"] = m.get("author")
        else: data.pop("author", None)
        if m.get("game_version"): data["game_version"] = m.get("game_version")
        else: data.pop("game_version", None)
        if m.get("mod_version"):  data["mod_version"] = m.get("mod_version")
        else: data.pop("mod_version", None)
        try:
            m["manifest"].write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            m["raw"] = data            
            self._ack_autorefresh_snapshot()
            # If auto-watcher exists, mark current state as clean (avoid redundant refresh after our own writes)
            try:
                if hasattr(self, "_make_mods_snapshot"):
                    self._last_snapshot = self._make_mods_snapshot()
                if hasattr(self, "_pending_snapshot"):
                    self._pending_snapshot = None
                if hasattr(self, "_pending_refresh") and self._pending_refresh:
                    try: self.after_cancel(self._pending_refresh)
                    except Exception: pass
                    self._pending_refresh = None
            except Exception:
                pass
            
        except Exception as e:
            messagebox.showerror("Save manifest", f"Failed to save manifest:\n{e}")

    def _open_replacements(self, mod_dir: Path):
        p = self._ensure_replacements_py(mod_dir)
        if not p:
            return
        try:
            ReplacementsBrowser(self.winfo_toplevel(), mod_dir)
        except Exception as e:
            messagebox.showerror("Replacements", f"Failed to open the editor:\n{e}")

    # ---------- Creating a new mod ----------
    def _sanitize_dir(self, name: str) -> str:
        base = "".join(ch if (ch.isalnum() or ch in "-_ ") else "_" for ch in name).strip()
        base = base.replace(" ", "_") or "mod"
        return base[:64]

    def _next_priority(self) -> int:
        mods = self._discover_mods()
        if not mods:
            return 100
        try:
            return max(int(m.get("priority", 100)) for m in mods) + 1
        except Exception:
            return 100 + len(mods)

    # Mod creation window

    # Mod creation window
    def add_new_mod(self):
        win = tk.Toplevel(self)
        win.withdraw()
        win.title("Create a new mod")
        win.configure(bg=self.palette["panel"])
        win.geometry("600x600")
        parent = self.winfo_toplevel()
        win.transient(parent)
        win.resizable(False, False)

        Titlebar.set_icon(win)

        # --- Buttons bar (ALWAYS visible at bottom) ---
        btns = ttk.Frame(win, padding=(12, 8), style="Panel.TFrame")
        btns.pack(side=tk.BOTTOM, fill=tk.X)
        btns.columnconfigure(0, weight=1)

        # --- Main layout (takes remaining space) ---
        frm = ttk.Frame(win, padding=12, style="Panel.TFrame")
        frm.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        for i in range(2):
            frm.columnconfigure(i, weight=1 if i == 1 else 0)

        # Tips
        tips = ttk.Label(
            frm,
            text="Make your mod with ease!\nHere you can create the basic frame of your mod. Fill in this fields so it can appear on the mod list. Later, you’ll be able to edit it using the mod editor.",
            foreground=META_FG,
            font=FONT_BASE_MINI,
            justify="left"
        )
        tips.grid(row=0, column=1, sticky="w", padx=(8, 0), pady=(0, 10))
        
        # Whale icon
        whale_icon = Icon.Button(frm, "whale", size=int(60))      
        whale_icon.grid(row=0, column=0, sticky="w", padx=(8, 0), pady=(4, 4))

        # Fields
        ttk.Label(frm, text="Name:").grid(row=1, column=0, sticky="w", pady=(4, 4))
        e_name = InputText(frm, "Enter mod name...")
        e_name.grid(row=1, column=1, sticky="ew", padx=(8, 0))

        ttk.Label(frm, text="Game version:").grid(row=2, column=0, sticky="w", pady=(4, 4))
        e_game = InputText(frm, "Enter current game version...")
        e_game.grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=(4, 4))

        ttk.Label(frm, text="Mod version:").grid(row=3, column=0, sticky="w", pady=(4, 4))
        e_mod = InputText(frm, "eg. 1.0")
        e_mod.grid(row=3, column=1, sticky="ew", padx=(8, 0), pady=(4, 4))

        ttk.Label(frm, text="Link (URL):").grid(row=4, column=0, sticky="w", pady=(8, 4))
        e_link = InputText(frm, "Enter your Steam Workshop link, or GitHub link...")
        e_link.grid(row=4, column=1, sticky="ew", padx=(8, 0), pady=(4, 4))

        ttk.Label(frm, text="Author:").grid(row=5, column=0, sticky="w", pady=(4, 4))
        e_author = InputText(frm, "Enter... you")
        e_author.grid(row=5, column=1, sticky="ew", padx=(8, 0), pady=(4, 4))

        ttk.Label(frm, text="Description:").grid(row=6, column=0, sticky="nw", pady=(8, 4))
        txt_desc = InputMultiline(frm, "Enter mod description...", height=2)
        txt_desc.grid(row=6, column=1, sticky="ew", padx=(8, 0), pady=(4, 4))
        txt_desc.canvas.configure(height=100)

        ttk.Label(frm, text="Changes:").grid(row=7, column=0, sticky="nw", pady=(8, 4))
        txt_changes = InputMultiline(frm, "Enter changelist...", height=1)
        txt_changes.grid(row=7, column=1, sticky="ew", padx=(8, 0), pady=(4, 4))
        txt_changes.canvas.configure(height=200)

        ttk.Label(frm, text="Thumbnail:").grid(row=8, column=0, sticky="w", pady=(4, 4))
        e_thumbnail = InputTextStatic(frm, "Add thumbnail.png (or .jpg) file into mod directory.\nSize: 256x256")
        e_thumbnail.grid(row=8, column=1, sticky="ew", padx=(8, 0), pady=(4, 4))        

        frm.rowconfigure(6, weight=1)
        frm.rowconfigure(7, weight=0)

        hint = ttk.Label(
            frm,
            text="In your 'changes' write one item per line.",
            foreground=META_FG,
            font=FONT_BASE_MINI,
            justify="left"
        )
        hint.grid(row=9, column=1, sticky="w", padx=(8, 0), pady=(6, 0))

        # Wrap text
        def _update_wrap(event=None):
            w = max(200, frm.winfo_width() - 24)  # margin
            tips.configure(wraplength=w)
            hint.configure(wraplength=w)

        frm.bind("<Configure>", _update_wrap)
        _update_wrap()

        # Save
        def _save_and_close():
            name = e_name.get().strip()
            self._stop_autorefresh()
            try:
                if not name:
                    messagebox.showerror("Create new mod", "Name cannot be empty.")
                    return

                # prepare the folder ./mods/<name>
                dir_name = self._sanitize_dir(name)
                target = self.mods_dir / dir_name
                suffix = 1
                while target.exists():
                    suffix += 1
                    target = self.mods_dir / f"{dir_name}_{suffix}"
                try:
                    target.mkdir(parents=True, exist_ok=False)
                except Exception as e:
                    messagebox.showerror("Create new mod", f"Failed to create folder:\n{e}")
                    return

                # manifest
                data = {
                    "name": name,
                    "enabled": True,
                    "priority": self._next_priority()
                }
                gv = e_game.get().strip()
                mv = e_mod.get().strip()
                lk = e_link.get().strip()
                au = e_author.get().strip()

                if gv:
                    data["game_version"] = gv
                if mv:
                    data["mod_version"] = mv
                if lk:
                    if not (lk.startswith("http://") or lk.startswith("https://")):
                        lk = "https://" + lk
                    data["link"] = lk
                if au:
                    data["author"] = au

                desc = txt_desc.get().strip()
                if desc:
                    data["description"] = desc

                ch_lines = [ln.rstrip() for ln in txt_changes.get().splitlines()]
                ch_clean = [ln.strip() for ln in ch_lines if ln.strip()]
                if ch_clean:
                    data["changes"] = ch_clean

                try:
                    (target / "manifest.json").write_text(
                        json.dumps(data, indent=2, ensure_ascii=False),
                        encoding="utf-8"
                    )
                except Exception as e:
                    messagebox.showerror("Create new mod", f"Failed to save the manifest:\n{e}")
                    return

                win.destroy()
                self.refresh()
            finally:
                self._start_autorefresh()
        # Buttons (already created btns frame above)
        btn_pack = {"side": "right", "padx": (0, 8)}
        Button(btns, text="Create", command=_save_and_close, pack=btn_pack, type="special")
        btn_cancel = Button(btns, text="Cancel", command=win.destroy, pack=btn_pack)

        def _cancel(_=None):
            try:
                if btn_cancel.winfo_exists():
                    btn_cancel.invoke()
            except Exception:
                pass
            return "break"

        win.bind("<Escape>", _cancel)

        try:
            win.update_idletasks()
            # prevent clipping: window can't be smaller than required height
            win.minsize(700, win.winfo_reqheight())
            Window.center_on_parent(win, parent)
        except Exception:
            pass

        win.deiconify()







    # ---------- Manifest Editor + Replacements ----------
    def edit_manifest(self, m: Dict[str, Any]):
        parent = self.winfo_toplevel()
        win = tk.Toplevel(parent)
        win.title(f"Edit mod – {m['name']}")
        win.configure(bg=self.palette["panel"])
        win.geometry("980x640")
        win.transient(parent)
        win.resizable(True, True)

        Titlebar.set_icon(win)
        #ok = Titlebar.set_color(win, caption_hex="#0e1b29", text_hex="#e6f1ff")
        #if not ok:
        #    try:
        #        Titlebar._dark_title_bar_SO(win)
        #    except Exception:
        #        pass

        # Separator bar / main layout
        paned = tk.PanedWindow(
            win,
            orient=tk.HORIZONTAL,
            sashwidth=2,
            sashrelief="flat",
            sashpad=2,
            sashcursor="sb_h_double_arrow",
            opaqueresize=True,
            bg=COLOR["accent_blue"],
            bd=0
        )

        # ---------DOWN: Buttons ---------
        btns = ttk.Frame(win, padding=(12, 8), style="Panel.TFrame")
        btns.pack(side=tk.BOTTOM, fill=tk.X)
        btns.columnconfigure(0, weight=1)
        
        btn_pack = {"side":"right", "padx":(4,0)}

        # placeholders to be assigned below
        e_name = e_game = e_mod = e_link = e_author = None
        txt_desc = txt_changes = None
        repl_editor = None

        def _save_all_and_close():
            nonlocal e_name, e_game, e_mod, e_link, e_author, txt_desc, txt_changes, repl_editor
            # manifest
            name = e_name.get().strip()
            if not name:
                messagebox.showerror("Edit mod", "Name cannot be empty."); return
            data = dict(m.get("raw") or {})
            data["name"] = name
            data["enabled"] = bool(m.get("enabled", True))
            data["priority"] = int(m.get("priority", 100))

            gv = e_game.get().strip(); mv = e_mod.get().strip()
            lk = e_link.get().strip(); au = e_author.get().strip()
            if gv: data["game_version"] = gv
            else:  data.pop("game_version", None)
            if mv: data["mod_version"] = mv
            else:  data.pop("mod_version", None)
            if lk:
                if not (lk.startswith("http://") or lk.startswith("https://")): lk = "https://" + lk
                data["link"] = lk
            else: data.pop("link", None)
            if au: data["author"] = au
            else:  data.pop("author", None)

            desc = txt_desc.get().strip()
            if desc: data["description"] = desc
            else:    data.pop("description", None)

            ch_lines = [ln.rstrip() for ln in txt_changes.get().splitlines()]
            ch_clean = [ln.strip() for ln in ch_lines if ln.strip()]
            if ch_clean: data["changes"] = ch_clean
            else:        data.pop("changes", None)

            try:
                m["manifest"].write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                m["raw"] = data                
                self._ack_autorefresh_snapshot()
                m["name"] = name
                m["description"] = data.get("description", "")
                m["changes"] = data.get("changes", [])
                m["author"] = data.get("author", "")
                m["game_version"] = data.get("game_version", "")
                m["mod_version"] = data.get("mod_version", "")
            except Exception as e:
                messagebox.showerror("Edit mod", f"Failed to save manifest:\n{e}")
                return

            # replacements
            if repl_editor and not repl_editor.save():
                return

            win.destroy()
            self.refresh()

        # Save button
        btn_save = Button(btns, text="Save", command=_save_all_and_close, pack=btn_pack, type="special")
        def _on_save(_=None):
            try:
                if btn_save.winfo_exists():
                    btn_save.invoke()
            except Exception:
                pass
            return "break"
        win.bind("<Control-s>", _on_save)
        win.bind("<Command-s>", _on_save)

        # Cancel button
        btn_cancel = Button(btns, text="Cancel", command=win.destroy, pack=btn_pack)
        def _on_escape(_=None):
            try:
                if btn_cancel.winfo_exists():
                    btn_cancel.invoke()
            except Exception:
                pass
            return "break"
        win.bind("<Escape>", _on_escape)        
        
        # Compact button
        def _toggle_compact(_=None):
            nonlocal repl_editor
            try:
                if repl_editor is not None:
                    repl_editor.toggle_compact_view()
            except Exception as e:
                messagebox.showerror("Compact view", f"Failed to toggle compact view:\n{e}")
            return "break"
        self.btn_view = Button(btns, text="Compact view", command=_toggle_compact, pack=btn_pack)

        paned.pack(fill=tk.BOTH, expand=True, padx=(12, 0), pady=12)
  
        # --------- LEFT: manifest ---------
        raw = dict(m.get("raw") or {})
        name_val = str(raw.get("name", m["name"]))
        game_ver_val = str(raw.get("game_version", raw.get("version_game", "")))
        mod_ver_val = str(raw.get("mod_version", raw.get("version_mod", "")))
        link_val = str(raw.get("link", ""))
        author_val = str(raw.get("author", ""))
        desc_val = str(raw.get("description", m.get("description", "")))
        changes_raw = raw.get("changes", [])
        if isinstance(changes_raw, list): changes_val = "\n".join(str(x) for x in changes_raw)
        else: changes_val = str(changes_raw)

        left = ttk.Frame(paned, padding=12)
        for i in range(2): left.columnconfigure(i, weight=1 if i == 1 else 0)
        paned.add(left, minsize=260)

        def dark_entry(parent):
            return tk.Entry(parent, bg="#0b1722", fg="#ffffff", insertbackground="#ffffff",
                            relief="flat", highlightthickness=1, highlightbackground="#18334d")


        # Title
        title_row = tk.Frame(left, bg=self.bg, bd=0, highlightthickness=0)
        title_row.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Label(title_row, text="Mod manifest", font=FONT_TITLE_H1).pack(side=tk.LEFT)
        
        # Tips
        tips = ttk.Label(left, text="General information about the mod. You can edit it if you want to change the manifest (but make sure you know what you’re doing).",
                  foreground=META_FG, font=FONT_BASE_MINI, justify="left")               
        tips.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        # Fields
        
        ttk.Label(left, text="Name:").grid(row=2, column=0, sticky="w", pady=(4, 4))
        e_name = InputText(left, "Enter mod name..."); e_name.set_text(name_val)
        e_name.grid(row=2, column=1, sticky="ew", padx=(8, 0))

        ttk.Label(left, text="Game version:").grid(row=3, column=0, sticky="w", pady=(4, 4))
        e_game = InputText(left, "Enter current game version..."); e_game.set_text(game_ver_val)
        e_game.grid(row=3, column=1, sticky="ew", padx=(8, 0), pady=(4, 4))

        ttk.Label(left, text="Mod version:").grid(row=4, column=0, sticky="w", pady=(4, 4))
        e_mod = InputText(left, "Enter mod version..."); e_mod.set_text(mod_ver_val)
        e_mod.grid(row=4, column=1, sticky="ew", padx=(8, 0), pady=(4, 4))

        ttk.Label(left, text="Link (URL):").grid(row=5, column=0, sticky="w", pady=(8, 4))
        e_link = InputText(left, "Enter your Steam Workshop link, or GitHub link..."); e_link.set_text(link_val)
        e_link.grid(row=5, column=1, sticky="ew", padx=(8, 0), pady=(4, 4))

        ttk.Label(left, text="Author:").grid(row=6, column=0, sticky="w", pady=(4, 4))
        e_author = InputText(left, "Enter... you"); e_author.set_text(author_val)
        e_author.grid(row=6, column=1, sticky="ew", padx=(8, 0), pady=(4, 4))

        ttk.Label(left, text="Description:").grid(row=7, column=0, sticky="nw", pady=(8, 4))
        txt_desc = InputMultiline(left, "Enter mod description...", height=2); txt_desc.set_text(desc_val)
        txt_desc.grid(row=7, column=1, sticky="ew", padx=(8, 0), pady=(4, 4))
        #txt_desc.canvas.configure(height=100)

        ttk.Label(left, text="Changes:").grid(row=8, column=0, sticky="nw", pady=(8, 4))
        txt_changes = InputMultiline(left, "Enter changelist...", height=1); txt_changes.set_text(changes_val)
        txt_changes.grid(row=8, column=1, sticky="ew", padx=(8, 0), pady=(4, 4))
        #txt_changes.canvas.configure(height=200)

        ttk.Label(left, text="Thumbnail:").grid(row=9, column=0, sticky="w", pady=(4, 4))
        e_thumbnail = InputTextStatic(left, "Add thumbnail.png (or .jpg) file into mod directory.\nSize: 256x256")
        e_thumbnail.grid(row=9, column=1, sticky="ew", padx=(8, 0), pady=(4, 4))
        
        # Hint (match add_new_mod)
        hint = ttk.Label(left, text="In your 'changes' write one item per line.",
                        foreground=META_FG, font=FONT_BASE_MINI, justify="left")
        hint.grid(row=10, column=1, sticky="w", padx=(8, 0), pady=(6, 0))

        # Keep rows tight (match add_new_mod behavior)
        left.rowconfigure(7, weight=3)
        left.rowconfigure(8, weight=2)     
        
        # Wrap text
        def _update_wrap(event=None):
            w = max(200, left.winfo_width() - 24) # margin
            tips.configure(wraplength=w)
            hint.configure(wraplength=w)
        left.bind("<Configure>", _update_wrap)
        _update_wrap()

        # ========== RIGHT: Replacements ==========
        right = ttk.Frame(paned, padding=12)
        paned.add(right, minsize=460)

        # Error if right panel is a piece of SHIT
        try:
            repl_editor = ReplacementsBrowser(self, m["dir"], embed_in=right)
        except Exception as e:
            messagebox.showerror("Replacements", f"Failed to build right panel:\n{e}")
            repl_editor = None

        # enable/disable compact button depending on whether editor exists
        try:
            self.btn_view.button.configure(state=("normal" if repl_editor is not None else "disabled"))
        except Exception:
            pass
        
        try:
            win.update_idletasks()
            Window.center_on_parent(win, parent)
            win.deiconify()
        except Exception:
            pass

    def _bind_wheel_relay(self, widget: tk.Widget):
        def _on_wheel(e):
            step = int(-e.delta/120) if getattr(e, "delta", 0) else (
                -3 if getattr(e, "num", None) == 4 else (3 if getattr(e, "num", None) == 5 else 0)
            )
            if step:
                self.canvas.yview_scroll(step, "units")
            return "break"
        
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
