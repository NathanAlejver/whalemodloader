
import re, sys, json, types, shutil, importlib.util
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Any, Optional

# =====================================
#           PATHS & CONSTANTS
# =====================================

script_dir = Path(__file__).resolve().parent
game_root = script_dir.parent
mods_dir = script_dir / "mods"

NAME = "Whale Mod Loader"
AUTHOR = 'NathanAlejver'
VERSION = 'BETA'

WORKSHOP_GAME_ID = '2230980'
STEAM_URL = "steam://rungameid/" + WORKSHOP_GAME_ID
FOLDER_NAME = "WhaleModLoader"

FACTORY_RESET = False # switched automatically by gui
PURGE_BACKUPS_ONLY = False # switched automatically by gui

BACKUP_DIR = script_dir / "assets" / "backups" / "original_game_files"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
ERROR_COUNT = 0
WARN_COUNT = 0

# =====================================
#               LOGGING
# =====================================

def log(msg: str) -> None:
    print(msg, file=sys.stderr)
    
    global ERROR_COUNT
    global WARN_COUNT
    if "[ERROR]" in msg:     ERROR_COUNT += 1        
    if "[WARN]" in msg:      WARN_COUNT += 1

# =====================================
#   MOD DISCOVERY + MANIFEST LOADING
# =====================================

# Returns mods (datapacks) from /mods/ folder and Workshop subfolders.
def discover_all_mods(local_mods_root: Path, ws_root: Optional[Path]) -> List[Mod]:
    mods: List[Mod] = []

    # 1) Local mods
    local_mods = discover_mods(local_mods_root)
    for m in local_mods:
        m.meta.setdefault("origin", "local")
    mods.extend(local_mods)

    # 2) Mods in the Workshop/content/
    if ws_root and ws_root.exists():
        ws_top_level_mods = discover_mods(ws_root)
        for m in ws_top_level_mods:
            m.meta.setdefault("origin", "workshop")
        mods.extend(ws_top_level_mods)

        # 3) Mods in subdirectories
        for child in ws_root.iterdir():
            if not child.is_dir():
                continue
            nested_mods_root = child / FOLDER_NAME / "mods"
            if nested_mods_root.exists():
                nested_mods = discover_mods(nested_mods_root)
                for m in nested_mods:
                    m.meta.setdefault("origin", f"workshop:{child.name}")
                mods.extend(nested_mods)
                
    # 4) Remove duplicates (by base folder + directory name)
    unique: Dict[Tuple[Path, str], Mod] = {}
    for m in mods:
        key = (m.base, m.dir_name)
        unique[key] = m


    
    # Result with sorting (by priority, then by name)
    result = list(unique.values())
    result.sort(key=lambda m: (m.priority, m.name.lower()))
    return result


# Single mod definition taken from /mods/ folder 
class Mod:
    def __init__(self, base: Path, name: str, priority: int = 100, enabled: bool = True):
        self.base = base
        self.dir_name = name  # folder name on disk
        self.priority = priority
        self.enabled = enabled
        self.meta: Dict[str, Any] = {}
        # replacement asset folders (optional)
        self.repl_root = self.base / "replacements"
        self.lines_dir = self.repl_root / "lines"
        self.functions_dir = self.repl_root / "functions"
        self.files_dir = self.repl_root / "files"
        # python definitions file (optional)
        self.replacements_py = self.base / "replacements.py"

    def __repr__(self) -> str:
        return f"Mod(name={self.name!r}, priority={self.priority}, enabled={self.enabled})"

    @property
    def name(self) -> str:
        # Prefer manifest name, fall back to folder name
        return str(self.meta.get("name") or self.dir_name)

# Find mods that contain a manifest.json with basic metadata.
def discover_mods(mods_root: Path) -> List[Mod]:
    mods: List[Mod] = []
    if not mods_root.exists():
        return mods

    for child in sorted(mods_root.iterdir()):
        if not child.is_dir():
            continue
        manifest_path = child / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as e:
            log(f"[ERROR] Failed to read manifest for mod '{child.name}': {e}")
            continue

        enabled = bool(manifest.get("enabled", True))
        priority = int(manifest.get("priority", 100))
        mod = Mod(base=child, name=child.name, priority=priority, enabled=enabled)
        mod.meta = manifest
        if not mod.enabled:
            log(f"[INFO] Mod disabled, skipping: {mod.name}")
            continue
        mods.append(mod)

    # Sort by (priority, name). Lower priority loads first; later mods take precedence.
    mods.sort(key=lambda m: (m.priority, m.name.lower()))
    return mods

# =====================================
#      REPLACEMENT CONTENT RESOLUTION
# =====================================

LINES_SEARCH: List[Path] = []
FUNCS_SEARCH: List[Path] = []
FILES_SEARCH: List[Path] = []

def _read_text_best_effort(p: Path) -> str:
    try:
        return p.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        return p.read_bytes().decode('utf-8', errors='replace')

# Find first existing file named `spec` inside any directory from `paths`
def _resolve_in(paths: List[Path], spec: str) -> Path:
    p = Path(spec)
    if p.exists():
        return p
    for base in paths:
        cand = base / spec
        if cand.exists():
            return cand
    return p

def load_file_replacement(spec: str) -> str:
    p = _resolve_in(list(reversed(FILES_SEARCH)), spec)
    if p.exists() and p.is_file():
        return _read_text_best_effort(p)
    return spec

def load_line_replacement(spec: str) -> str:
    p = _resolve_in(list(reversed(LINES_SEARCH)), spec)
    if p.exists() and p.is_file():
        return _read_text_best_effort(p)
    return spec

def load_function_replacement(spec: str) -> str:
    p = _resolve_in(list(reversed(FUNCS_SEARCH)), spec)
    if p.exists() and p.is_file():
        return _read_text_best_effort(p)
    return spec

# =====================================
#           PATH NORMALIZATION
# =====================================

# game-relative path coming from replacements.py keys.
def norm_relpath(p: str) -> str:
    s = p.replace('\\\\', '/').replace('\\', '/')
    s = s.lstrip('./')
    while s.startswith('/'):
        s = s[1:]
    return s

# =====================================
#         .PY REPLACEMENTS LOADING
# =====================================

# In-memory bundle of all rule dictionaries collected from mods.
class ReplBundle:
    def __init__(self) -> None:
        self.line_replacements: Dict[str, Dict[str, List[Tuple[str, str]]]] = {}
        self.function_replacements: Dict[str, Dict[str, str]] = {}
        self.file_line_replacements: Dict[str, List[Tuple[str, str]]] = {}
        self.file_additions: Dict[str, List[Tuple[str, str]]] = {}
        self.file_replacements: Dict[str, str] = {}

    # Deep merge with override precedence (later call wins)
    def merge_from(self, other: 'ReplBundle') -> None:
        def _merge_dict(dst: Dict[str, Any], src: Dict[str, Any]) -> None:
            for k, v in src.items():
                if k not in dst:
                    dst[k] = json.loads(json.dumps(v)) if isinstance(v, (dict, list)) else v
                    continue
                if isinstance(dst[k], dict) and isinstance(v, dict):
                    _merge_dict(dst[k], v)
                elif isinstance(dst[k], list) and isinstance(v, list):
                    dst[k].extend(v)
                else:
                    dst[k] = v
        _merge_dict(self.line_replacements, other.line_replacements)
        _merge_dict(self.function_replacements, other.function_replacements)
        _merge_dict(self.file_line_replacements, other.file_line_replacements)
        _merge_dict(self.file_additions, other.file_additions)
        self.file_replacements.update(other.file_replacements)


def _safe_getattr(mod: types.ModuleType, name: str, default: Any) -> Any:
    return getattr(mod, name, default)


def _load_replacements_py(py_path: Path, module_name: str) -> Optional[types.ModuleType]:
    if not py_path.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location(module_name, py_path)
        if spec is None or spec.loader is None:
            log(f"[ERROR] Could not load spec for {py_path}")
            return None
        mod = importlib.util.module_from_spec(spec)
        # Execute the module code (user-provided). This is trusted in the modding context.
        spec.loader.exec_module(mod)  # type: ignore
        return mod
    except Exception as e:
        log(f"[ERROR] Failed to import replacements.py from {py_path}: {e}")
        return None


def load_bundle_from_mod(mod: Mod) -> ReplBundle:
    bundle = ReplBundle()
    py = _load_replacements_py(mod.replacements_py, module_name=f"mod_{mod.name}_replacements")
    if py is not None:
        lr = _safe_getattr(py, 'LINE_REPLACEMENTS', {})
        fr = _safe_getattr(py, 'FUNCTION_REPLACEMENTS', {})
        flr = _safe_getattr(py, 'FILE_LINE_REPLACEMENTS', {})
        fa = _safe_getattr(py, 'FILE_ADDITIONS', {})
        ff = _safe_getattr(py, 'FILE_REPLACEMENTS', {})

        # Normalize keys (paths)
        def norm_paths(d: Dict[str, Any]) -> Dict[str, Any]:
            out: Dict[str, Any] = {}
            for k, v in d.items():
                out[norm_relpath(k)] = v
            return out

        bundle.line_replacements = { norm_relpath(fp): funcs for fp, funcs in norm_paths(lr).items() }
        bundle.function_replacements = { norm_relpath(fp): funcs for fp, funcs in norm_paths(fr).items() }        
        bundle.file_line_replacements = norm_paths(flr)
        bundle.file_additions = norm_paths(fa)
        bundle.file_replacements = { norm_relpath(k): v for k, v in ff.items() }

    return bundle

# =====================================
#          PATTERN / PARSING HELPERS
# =====================================

# Create regex (insensivie to spaces, splits & shit like that)
def make_ws_agnostic_pattern(text: str) -> re.Pattern:
    s = text.strip()
    if not s:
        return re.compile(r"", re.DOTALL)
    parts = re.split(r'\s+', s)  # division after whitespace characters
    pattern_parts: List[str] = []

    for part in parts:
        escaped = re.escape(part) # change espaced-operator to \s*OP\s*
        def _op_repl(m: re.Match) -> str:
            op = m.group(1)
            return r'\s*' + re.escape(op) + r'\s*'
        escaped2 = re.sub(r'\\([=+\-*/<>]{1,2})', _op_repl, escaped)
        pattern_parts.append(escaped2)
    pattern = r'\s+'.join(pattern_parts)

    try:
        return re.compile(pattern, re.DOTALL)
    except re.error:
        fallback = re.escape(s).replace(r'\ ', r'\s+') # simpler fallback
        return re.compile(fallback, re.DOTALL)

# Detect function definition header even if '{' is on the same line.
def is_function_header(line: str, func_name: str) -> bool:
    pattern = re.compile(rf"^\s*[\w\*\s]*\b{re.escape(func_name)}\b\s*\([^;]*\)\s*(\{{)?\s*$")
    if not pattern.search(line):
        return False
    return not line.rstrip().endswith(';')

def is_function_header_or_start(line: str, func_name: str) -> Tuple[bool, bool]:
    ln = strip_c_line_comments(line)
    full = re.compile(rf"^\s*[\w\*\s]*\b{re.escape(func_name)}\b\s*\([^;]*\)\s*(\{{)?\s*$")
    if full.search(ln) and not ln.rstrip().endswith(';'):
        return True, True
    start = re.compile(rf"^\s*[\w\*\s]*\b{re.escape(func_name)}\b\s*\([^;]*$")
    if start.search(ln) and not ln.rstrip().endswith(';'):
        return True, False
    return False, False

# Remove //comments at the end of the line
def strip_c_line_comments(s: str) -> str:
    s = re.sub(r'/\*.*?\*/', '', s)
    s = re.sub(r'//.*$', '', s)
    return s


# =====================================
#     MISC HELPERS
# =====================================

#  If `spec` names a file, return file contents. Otherwise return spec unchanged
def resolve_line_spec_to_text(spec: str) -> str:
    p = Path(spec)
    if p.exists() and p.is_file():
        return _read_text_best_effort(p)
    p = _resolve_in(list(reversed(LINES_SEARCH)), spec)
    if p.exists() and p.is_file():
        return _read_text_best_effort(p)
    return spec

# Get 'steamapps' folder based on _game_root
def find_workshop_content_root(game_root: Path) -> Optional[Path]:
    for anc in game_root.parents:
        if anc.name.lower() == "steamapps":
            return anc / "workshop" / "content" / WORKSHOP_GAME_ID
    if game_root.parent.name.lower() == "common" and game_root.parent.parent.name.lower() == "steamapps":
        return game_root.parent.parent / "workshop" / "content" / WORKSHOP_GAME_ID
    return None

# Get mods list (only for the ones with Program/ and Resources/) 
def discover_workshop_targets(ws_root: Optional[Path]) -> List[Tuple[str, Path]]:
    results: List[Tuple[str, Path]] = []
    if not ws_root or not ws_root.exists():
        return results
    for child in sorted(ws_root.iterdir()):
        if not child.is_dir():
            continue
        if not child.name.isdigit():
            continue
        has_game_dirs = any((child / d).exists() for d in ("Program", "Resource", "Resources"))
        if has_game_dirs:
            results.append((f"workshop/{child.name}", child))
    return results

# =====================================
#       FACTORY RESET IMPLEMENTATION
# =====================================

# Map label parts tuple -> root path.
def _build_label_map_from_targets(targets: List[Tuple[str, Path]]) -> Dict[Tuple[str, ...], Path]:
    out: Dict[Tuple[str, ...], Path] = {}
    for label, root in targets:
        key = tuple(label.split('/'))
        out[key] = root
    return out

# Find the longest label_key which is a prefix of parts.
def _find_best_label_for(parts: Tuple[str, ...], label_keys: List[Tuple[str, ...]]) -> Optional[Tuple[str, ...]]:
    best: Optional[Tuple[str, ...]] = None
    best_len = 0
    for key in label_keys:
        if len(key) > len(parts):
            continue
        if parts[:len(key)] == key and len(key) > best_len:
            best = key
            best_len = len(key)
    return best


def perform_factory_reset(backup_root: Path, targets: List[Tuple[str, Path]]) -> None:
    if not backup_root.exists():
        log("[INFO] No backups to restore (backup dir missing).")
        return

    targets_map = _build_label_map_from_targets(targets)
    label_keys = list(targets_map.keys())

    # Collect all backup files
    files = [p for p in backup_root.rglob('*') if p.is_file()]
    if not files:
        log("[INFO] No backup files found to restore.")
        return
    for f in files:
        rel_parts = tuple(f.relative_to(backup_root).parts)
        label_key = _find_best_label_for(rel_parts, label_keys)
        if label_key is None:
            log(f"[WARN] Could not map backup file to any target, skipping: {f.name}")
            continue
        rel_path = Path(*rel_parts[len(label_key):])
        dest_root = targets_map[label_key]
        dest = dest_root / rel_path
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
            log(f"[INFO] Restored backup: {f.name}")
            try:
                f.unlink()
            except Exception as e:
                log(f"[WARN] Could not remove backup file {f.name}")
        except Exception as e:
            log(f"[ERROR] Failed to restore backup {f.name}")

    # Try deleting empty directories under backup root
    for d in sorted([p for p in backup_root.rglob('*') if p.is_dir()], key=lambda p: -len(p.parts)):
        try:
            if not any(d.iterdir()):
                d.rmdir()
        except Exception:
            pass
    try:
        if BACKUP_DIR.exists() and not any(BACKUP_DIR.iterdir()):
            BACKUP_DIR.rmdir()
            log("[INFO] All original backup files removed.")
    except Exception:
        pass

def purge_all_backups(backup_root: Path) -> None:
    if not backup_root.exists():
        log("[INFO] No backups directory found. Nothing to purge.")
        return

    # Delete all files under backup_root
    files = [p for p in backup_root.rglob('*') if p.is_file()]
    if not files:
        log("[INFO] No backup files found. Nothing to purge.")
    else:
        for f in files:
            try:
                f.unlink()
                # log(f"[INFO] Purged backup file: {f}")
            except Exception as e:
                log(f"[WARN] Could not delete backup file {f}: {e}")

    # Try deleting empty directories under backup root
    for d in sorted([p for p in backup_root.rglob('*') if p.is_dir()], key=lambda p: -len(p.parts)):
        try:
            if not any(d.iterdir()):
                d.rmdir()
        except Exception:
            pass

    # Remove root dir if empty
    try:
        if backup_root.exists() and not any(backup_root.iterdir()):
            backup_root.rmdir()
            log("[INFO] All backup files removed, backup directory deleted.")
    except Exception:
        pass



# =====================================
#               MAIN
# =====================================

def main() -> None:
    print(""), log(f'STARTING MODLOADER PROCESS...')

    # Find Steam Workshop root
    ws_root = find_workshop_content_root(game_root)
    if ws_root is None:
        log("[INFO] Steam Workshop content root NOT found - only local mods will be used.")


    # 1) Discover mods
    mods = discover_all_mods(mods_dir, ws_root)
    if not mods:
        log(f"[INFO] No mods found in any known directory")
    else:
        log("[INFO] Mods load priority:")
        for m in mods:
            origin = m.meta.get("origin", "unknown")
            log(f"      - {m.priority:>3} : {m.name} [{origin}]")

    # 2) Prepare global search paths for replacement specs
    global LINES_SEARCH, FUNCS_SEARCH, FILES_SEARCH
    LINES_SEARCH = [m.lines_dir for m in mods]
    FUNCS_SEARCH = [m.functions_dir for m in mods]
    FILES_SEARCH = [m.files_dir for m in mods]
    
    # 2a) Discover workshop targets
    ws_targets = discover_workshop_targets(ws_root)
    targets: List[Tuple[str, Path]] = [("basegame", game_root)] + ws_targets    
    log("[INFO] Processing target file locations:")
    for label, root in targets:
        log(f"  - {label:>18}")
    log("[INFO] Processing files:")


    # If factory reset requested -> perform it and exit

    # If purge-only requested -> delete backups and exit
    if PURGE_BACKUPS_ONLY:
        log("[INFO] PURGE_BACKUPS_ONLY --> deleting all backup files without touching game files...")
        purge_all_backups(BACKUP_DIR)
        log("[REPORT] BACKUP PURGE FINISHED!"), print('\n')
        return

    if FACTORY_RESET:
        log("[INFO] FACTORY_RESET --> restoring backups and removing them...")
        perform_factory_reset(BACKUP_DIR, targets)
        log("[REPORT] FACTORY RESET FINISHED!"), print('\n')  
        return


    # 3) Load all replacement bundles in order, merge so that later mods override
    merged = ReplBundle()
    for m in mods:
        b = load_bundle_from_mod(m)
        merged.merge_from(b)

    # 4) Determine all target file paths (no explicit targets: union of keys used anywhere)
    file_keys = set()
    file_keys.update(merged.line_replacements.keys())
    file_keys.update(merged.function_replacements.keys())
    file_keys.update(merged.file_line_replacements.keys())
    file_keys.update(merged.file_additions.keys())
    file_keys.update(merged.file_replacements.keys())

    if not file_keys:
        log("[INFO] No replacement rules found across enabled mods. Nothing to do.")
        return

    # 5) Stats
    file_stats = defaultdict(lambda: defaultdict(int))  # file -> function -> count
    file_func_swaps = defaultdict(int)  # file -> num function swaps
    file_file_swaps = defaultdict(int)  # file -> num whole-file swaps

    # Ensure backup dir exists
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # 6) PROCESS FILES
    for rel in sorted(file_keys):
        target_rel = Path(rel)  # Path to file, example: "Program/interface/seadogs.c"

        for label, root in targets:
            filename_display = f"{rel} ({label})"
            full_path = root / target_rel
            
            # Load all shit
            funcs_lines = merged.line_replacements.get(rel, {})
            funcs_full  = merged.function_replacements.get(rel, {})
            file_line_repls = merged.file_line_replacements.get(rel, [])
            file_adds   = merged.file_additions.get(rel, [])
            spec_file   = merged.file_replacements.get(rel)  
            
            
            
            # Leave idle files for logging
            backup_path = BACKUP_DIR / label / target_rel
            exists_now = full_path.exists()
            had_backup = backup_path.exists()
            if not exists_now and not had_backup:
                continue
            
            log(f"==> {filename_display}")

            # Ensure backup exists (create once)
            try:
                if exists_now:
                    if not had_backup:
                        backup_path.parent.mkdir(parents=True, exist_ok=True)
                        try:
                            shutil.copy2(full_path, backup_path)
                            log(f"\t     [BACKUP CREATED]")
                            had_backup = True
                        except Exception as e:
                            log(f"\t     [ERROR] Could not create backup! {e}")
                else:                    
                    log(f"\t     [INFO] Target missing, will use existing backup")
            except Exception as e:
                log(f"\t     [ERROR] Checking/creating backup {e}")
                continue

            # Source: always a backup of the original if we have it, otherwise a live file
            source_path = backup_path if backup_path.exists() else full_path
            try:
                source_text = source_path.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                log(f"\t|     [ERROR] Encoding issue reading source (expected UTF-8)...")
                continue
            except FileNotFoundError:
                log(f"\t|     [WARN] Source file not found, skipping...")
                continue


            pending_events: List[str] = []
            source_lines = source_text.splitlines(keepends=True)
            out_lines: List[str] = []

            # --- state for function capture ---
            in_function: Optional[str] = None
            brace_level = 0
            wait_for_brace = False
            buffer_lines: List[str] = []

            # ---------- function-scope processing ----------
            source_lines_iter = iter(source_lines)
            for raw_line in source_lines_iter:
                line = raw_line
                stripped = line.rstrip('\n')

                if in_function is None:
                    
                    # Check 'detected'
                    detected: Optional[str] = None
                    header_complete = False                    
                    for func_name in set(list(funcs_lines.keys()) + list(funcs_full.keys())):                        
                        d, c = is_function_header_or_start(stripped, func_name)
                        if d:
                            detected = func_name
                            header_complete = c
                            break
                    if detected is None:
                        out_lines.append(line)
                        continue

                    # Start capture
                    in_function = detected
                    buffer_lines = [line]
                    
                    # Jeśli ) nie było w tej linii, dociągamy nagłówek aż do zamknięcia ')'
                    if not header_complete:
                        ln = strip_c_line_comments(stripped)
                        paren_depth = ln.count('(') - ln.count(')')
                        continue_capture = True
                        while continue_capture:
                            try:
                                next_raw = next(source_lines_iter)
                            except StopIteration:
                                break
                            buffer_lines.append(next_raw)
                            nr = next_raw.rstrip('\n')
                            lnc = strip_c_line_comments(nr)
                            paren_depth += lnc.count('(') - lnc.count(')')
                            if paren_depth <= 0:
                                continue_capture = False
                        wait_for_brace = True
                        continue
                    
                    if '{' in stripped and not stripped.strip().endswith(';'):
                        brace_level = stripped.count('{') - stripped.count('}')
                        wait_for_brace = False
                    else:
                        wait_for_brace = True
                    continue                

                # Inside function capture
                buffer_lines.append(line)

                if wait_for_brace:
                    if '{' in stripped:
                        brace_level = stripped.count('{') - stripped.count('}')
                        wait_for_brace = False
                else:
                    brace_level += stripped.count('{') - stripped.count('}')

                if brace_level <= 0 and not wait_for_brace:
                    func_text = ''.join(buffer_lines)

                    # Decide output: full-function swap (preferred) or modified original
                    out_text = None
                    if in_function in funcs_full:
                        spec = funcs_full[in_function]
                        new_text = load_function_replacement(spec) if isinstance(spec, str) else str(spec)
                        out_text = new_text
                        file_func_swaps[f"{label}/{rel}"] += 1
                        pending_events.append(f"\t > [REPLACE FUNCTION]  {in_function}\t\t`{str(spec)[:50]}`")
                    else:
                        # Apply line/block replacements (multiline-aware)
                        for old, new_spec in funcs_lines.get(in_function, []):                            
                            old_text = resolve_line_spec_to_text(old) if isinstance(old, str) else str(old)
                            pat = make_ws_agnostic_pattern(old_text)
                            replacement = load_line_replacement(new_spec) if isinstance(new_spec, str) else str(new_spec)
                            
                            func_text, n = pat.subn(replacement, func_text, count=1)
                            if n > 0:
                                file_stats[f"{label}/{rel}"][in_function] += n
                                new_spec_log = ' '.join(str(new_spec).split())
                                pending_events.append(f"\t > [REPLACE LINE]      {in_function}\t\t`{new_spec_log[:50]}`")

                        out_text = func_text

                    # Emit processed function ONCE
                    out_lines.append(out_text)

                    # Reset capture state
                    in_function = None
                    buffer_lines = []
                    brace_level = 0
                    wait_for_brace = False

                    continue

            # Jeśli niedomknięta funkcja – flush
            if buffer_lines:
                out_lines.append(''.join(buffer_lines))
                buffer_lines = []

            new_content = ''.join(out_lines)

            # ---------- file-level replacements & additions ----------
            if file_line_repls:
                for old, new_spec in file_line_repls:
                    old_text = resolve_line_spec_to_text(old) if isinstance(old, str) else str(old)
                    pat = make_ws_agnostic_pattern(old_text)
                    replacement = load_line_replacement(new_spec) if isinstance(new_spec, str) else str(new_spec)
                    matches = list(pat.finditer(new_content))
                    if matches:
                        new_content = pat.sub(replacement, new_content)
                        pending_events.append(f"\t > [REPLACE FILE-LINE] {rel} -> `{str(new_spec)[:60]}`")
                        file_stats[f"{label}/{rel}"]['<file>'] += len(matches)

            if file_adds:
                for position, spec in file_adds:
                    addition = load_line_replacement(spec) if isinstance(spec, str) else str(spec)
                    if not addition:
                        continue
                    if position == 'start':
                        if addition in new_content:
                            pending_events.append(f"\t > [ADD SKIP] {rel} start -> `{str(spec)[:60]}` already present")
                        else:
                            sep = ''
                            if (not new_content.startswith('\n')) and (not addition.endswith('\n')) and new_content:
                                sep = '\n'
                            new_content = addition + sep + new_content
                            pending_events.append(f"\t > [ADD START] {rel} -> `{str(spec)[:60]}`")
                    else:
                        if addition in new_content:
                            pending_events.append(f"\t > [ADD SKIP] {rel} end -> `{str(spec)[:60]}` already present")
                        else:
                            sep = ''
                            if (not new_content.endswith('\n')) and (not addition.startswith('\n')) and new_content:
                                sep = '\n'
                            new_content = new_content + sep + addition
                            pending_events.append(f"\t > [ADD END] {rel} -> `{str(spec)[:60]}`")

            if spec_file is not None:
                replacement = load_file_replacement(spec_file) if isinstance(spec_file, str) else str(spec_file)
                if replacement != new_content:
                    new_content = replacement
                    pending_events.append(f"\t > [FILE REPLACE] {rel} -> `{str(spec_file)[:60]}`")
                    file_stats[f"{label}/{rel}"]['<file>'] += 1
                    file_file_swaps[f"{label}/{rel}"] += 1
                else:
                    pending_events.append(f"\t > [FILE REPLACE] {rel} -> already up-to-date")

            # Read current target file content (may be missing)
            try:
                current_content = full_path.read_text(encoding='utf-8') if full_path.exists() else ''
            except UnicodeDecodeError:
                log(f"\t [ERROR] Encoding issue reading target game file (expected UTF-8): {full_path}")
                continue

            # If nothing changed compared to current live file, skip write
            if new_content == current_content:
                if pending_events:
                    log(f"\t     [NO CHANGE]         File is already up-to-date")
                else:
                    log(f"\t     [NO CHANGE]         No write needed")
                continue

            # Write new file
            try:
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(new_content, encoding='utf-8')
                log(f"\t     [UPDATE FILE]")
                for ev in pending_events:
                    log("\t\t" + ev)
            except Exception as e:
                log(f"\t     [ERROR] Writing updated file {full_path}: {e}")
                continue


    # Summary
    log('\n[SUMMARY]')
    _max_len = max((len(fname) for fname in file_stats), default=0)
    _total_line_changes = 0
    for fname, funcs in file_stats.items():
        file_total = sum(funcs.values())
        _total_line_changes += file_total
        log(f" | {fname:<{_max_len}}\t replaced {file_total} line(s)")
    _total_func_swaps = sum(file_func_swaps.values())
    for fname, cnt in file_func_swaps.items():
        log(f" | {fname:<{_max_len}}\t replaced {cnt} function(s)")
    _total_file_swaps = sum(file_file_swaps.values())
    for fname, cnt in file_file_swaps.items():
        log(f" | {fname:<{_max_len}}\t replaced {cnt} file(s)")

    # report
    error_status = f"There are {ERROR_COUNT} errors!" if ERROR_COUNT > 0 else "No errors detected."
    log(f"\nMODLOADER FINISHED! Loaded total {len(mods)} mods, changed {_total_line_changes} lines, {_total_func_swaps} functions, and {_total_file_swaps} files. {error_status}")    
    if ERROR_COUNT > 0:
        log(f" | Warning! Game may CRASH! You should check logs for details and fix all {ERROR_COUNT} errros")
    if WARN_COUNT > 0:
        log(f" | Warning! There are {WARN_COUNT} files that require your attention! Check [WARN] logs for details")
    print('')    
    
if __name__ == "__main__":
    main()
