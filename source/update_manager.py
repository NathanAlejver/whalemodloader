from __future__ import annotations
import json, shutil, zipfile, tempfile
from pathlib import Path
from urllib.request import Request, urlopen
import ModLoader

# ---- CONFIG ----
GITHUB_OWNER = "NathanAlejver"
GITHUB_REPO  = "whalemodloader"

# Only update modloader core files + icons (keep mods/backups/user settings)
ALLOWLIST_FILES = {
    "gui_run.py",
    "ModLoader.py",
    "gui_common.py",
    "gui_panel_mods.py",
    "gui_editor_replacements.py",
    "gui_editor_replacements_sheet.py",
    "update_manager.py"
}
ALLOWLIST_DIRS = {
    "assets/icons",
}

# This file should never be overwritten by updater:
NEVER_OVERWRITE = {
    "assets/settings/.gui_modloader_settings.json",
}

def _http_json(url: str) -> dict:
    req = Request(url, headers={"User-Agent": "WhaleModLoader-Updater"})
    with urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

def _download(url: str, out_path: Path) -> None:
    req = Request(url, headers={"User-Agent": "WhaleModLoader-Updater"})
    with urlopen(req, timeout=30) as r, open(out_path, "wb") as f:
        shutil.copyfileobj(r, f)

def _version_tuple(s: str) -> tuple[int, ...]:
    # extracts numbers from strings like "BETA 0.1" -> (0, 1)
    import re
    nums = re.findall(r"\d+", s or "")
    return tuple(int(x) for x in nums) if nums else (0,)

def is_newer(latest: str, current: str) -> bool:
    return _version_tuple(latest) > _version_tuple(current)

# Returns (tag_name, zip_url). Uses /releases/latest and zipball_url to avoid guessing assets naming.
def get_latest_release() -> tuple[str, str]:
    api = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
    data = _http_json(api)
    tag = (data.get("tag_name") or "").strip()
    zip_url = (data.get("zipball_url") or "").strip()
    return tag, zip_url

# Extracts zipball, then copies allowlisted files/dirs into app_dir.
def apply_update_from_zip(zip_path: Path, app_dir: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="wml_upd_") as td:
        td_path = Path(td)
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(td_path)

        # zipball typically contains one top-level folder
        roots = [p for p in td_path.iterdir() if p.is_dir()]
        src_root = roots[0] if roots else td_path

        # Copy allowlisted files
        for rel in ALLOWLIST_FILES:
            src = src_root / rel
            dst = app_dir / rel
            if not src.exists():
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

        # Copy allowlisted dirs
        for rel_dir in ALLOWLIST_DIRS:
            srcd = src_root / rel_dir
            dstd = app_dir / rel_dir
            if not srcd.exists():
                continue
            for item in srcd.rglob("*"):
                if item.is_dir():
                    continue
                rel_item = item.relative_to(src_root).as_posix().replace("\\", "/")
                if rel_item in NEVER_OVERWRITE:
                    continue
                out = app_dir / rel_item
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, out)

# Tk-friendly: uses messagebox for prompts.
def check_and_update_gui(parent_tk) -> None:
    from tkinter import messagebox
    try:
        current = getattr(ModLoader, "VERSION", "0")
        latest, zip_url = get_latest_release()
        if not latest or not zip_url:
            messagebox.showerror("Updates", "Could not fetch latest release info.")
            return

        if not is_newer(latest, current):
            messagebox.showinfo("Updates", f"You're up-to-date.\n\nCurrent: {current}\nLatest:  {latest}")
            return

        ok = messagebox.askyesno(
            "Updates",
            f"Update available!\n\nCurrent: {current}\nLatest:  {latest}\n\nDownload and apply now?"
        )
        if not ok:
            return

        app_dir = Path(ModLoader.get_app_dir())
        tmp_zip = app_dir / "_update_download.zip"
        _download(zip_url, tmp_zip)

        apply_update_from_zip(tmp_zip, app_dir)

        try:
            tmp_zip.unlink()
        except Exception:
            pass

        messagebox.showinfo("Updates", "Update applied.\nRestart Whale Mod Loader to use the new version.")
    except Exception as e:
        messagebox.showerror("Updates", f"Update failed:\n{e}")
