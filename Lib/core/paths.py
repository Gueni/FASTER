#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?                             ____        __  __
#?                            / __ \____ _/ /_/ /_  _____
#?                           / /_/ / __ `/ __/ __ \/ ___/
#?                          / ____/ /_/ / /_/ / / (__  )
#?                         /_/    \__,_/\__/_/ /_/____/
#?
#? Name:        paths.py
#? Purpose:     Application locations: install folder, bundled resources and the user's data folder.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     07/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------

"""Where FASTER reads and writes files.

The application folder (``APP_DIR``) is treated as read-only so FASTER can be
installed under *Program Files*. Everything a user produces lives in the
**data folder**, chosen by the user (installer page, first start of the GUI,
Settings page or ``FASTER_DATA``)::

    <data folder>/
        results/        one time-stamped folder per analysis run
        examples/       example circuits (copied on first start)
        work/           working copies of edited schematics in read-only folders
        config.json     default analysis settings (editable)

The location of the data folder itself is stored in
``%APPDATA%\\FASTER\\preferences.json`` so the GUI, the command line and the
analysis worker all agree on it.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

APP_NAME         = 'FASTER'
FROZEN           = bool(getattr(sys, 'frozen', False))                  # PyInstaller build
PROJECT_ROOT_SRC = Path(__file__).resolve().parents[2]                # source tree (main.py)
APP_DIR          = Path(sys.executable).resolve().parent if FROZEN else PROJECT_ROOT_SRC
RESOURCE_DIR     = Path(getattr(sys, '_MEIPASS', APP_DIR))               # bundled read-only files
TEMPLATE_CFG     = RESOURCE_DIR / 'config.json'
EXAMPLES_SRC     = RESOURCE_DIR / ('examples' if FROZEN else 'tests')
EXAMPLE_GLOB     = ('*.asc', '*.asy', '*.lib', '*.sub', '*.inc')


#? -------------------------------------------------------------------------------
def _known_folder(guid: str) -> Path | None:
    """Windows known folder (follows OneDrive / redirected folders)."""
    if sys.platform != 'win32':
        return None
    try:
        import ctypes
        from ctypes import wintypes
        import uuid

        class GUID(ctypes.Structure):
            _fields_ = [('Data1', wintypes.DWORD), ('Data2', wintypes.WORD),
                        ('Data3', wintypes.WORD), ('Data4', ctypes.c_ubyte * 8)]

        u   = uuid.UUID(guid)
        g   = GUID(u.fields[0], u.fields[1], u.fields[2], (ctypes.c_ubyte * 8)(*u.bytes[8:]))
        ptr = ctypes.c_wchar_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(ptr)) != 0:
            return None
        path = Path(ptr.value)
        ctypes.windll.ole32.CoTaskMemFree(ptr)
        return path
    except Exception:
        return None


#? -------------------------------------------------------------------------------
def documents_dir() -> Path:
    found = _known_folder('{FDD39AD0-238F-46AF-ADB4-6C85480369C7}')      # FOLDERID_Documents
    if found and found.is_dir():
        return found
    docs = Path.home() / 'Documents'
    return docs if docs.is_dir() else Path.home()


#? -------------------------------------------------------------------------------
def config_home() -> Path:
    """Per-user settings folder (``%APPDATA%\\FASTER``, ``~/Library/...``, ``~/.config/...``)."""
    if sys.platform == 'win32':
        base = Path(os.environ.get('APPDATA') or Path.home() / 'AppData' / 'Roaming')
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Application Support'
    else:
        base = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')
    return base / APP_NAME


PREFS_FILE       = config_home() / 'preferences.json'
DEFAULT_DATA_DIR = documents_dir() / APP_NAME


#? -------------------------------------------------------------------------------
#? preferences
def load_prefs() -> dict[str, Any]:
    try:
        return json.loads(PREFS_FILE.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return {}


#? -------------------------------------------------------------------------------
def save_prefs(**changes: Any) -> None:
    prefs = load_prefs()
    prefs.update(changes)
    PREFS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PREFS_FILE.write_text(json.dumps(prefs, indent=2), encoding='utf-8')


#? -------------------------------------------------------------------------------
#? data folder
def data_dir_configured() -> bool:
    """``True`` once the user (or the installer) has chosen a data folder."""
    return bool(os.environ.get('FASTER_DATA') or load_prefs().get('data_dir'))


#? -------------------------------------------------------------------------------
def data_dir() -> Path:
    """The user's data folder: ``FASTER_DATA`` > preferences > ``Documents/FASTER``."""
    chosen = os.environ.get('FASTER_DATA') or load_prefs().get('data_dir')
    return Path(os.path.expandvars(os.path.expanduser(chosen))) if chosen else DEFAULT_DATA_DIR


#? -------------------------------------------------------------------------------
def set_data_dir(path: str | os.PathLike) -> Path:
    path = Path(path).expanduser().resolve()
    save_prefs(data_dir=str(path))
    return ensure_data_dir(path)


#? -------------------------------------------------------------------------------
def results_dir() -> Path:
    return data_dir() / 'results'


#? -------------------------------------------------------------------------------
def examples_dir() -> Path:
    return data_dir() / 'examples'


#? -------------------------------------------------------------------------------
def work_dir() -> Path:
    path = data_dir() / 'work'
    path.mkdir(parents=True, exist_ok=True)
    return path


#? -------------------------------------------------------------------------------
def user_config() -> Path:
    return data_dir() / 'config.json'


#? -------------------------------------------------------------------------------
def ensure_data_dir(root: str | os.PathLike | None = None) -> Path:
    """Create the data folder layout; copy the default config and examples if missing."""
    root = Path(root) if root else data_dir()
    for sub in ('results', 'examples'):
        (root / sub).mkdir(parents=True, exist_ok=True)
    cfg = root / 'config.json'
    if not cfg.exists() and TEMPLATE_CFG.is_file():
        shutil.copy2(TEMPLATE_CFG, cfg)
    if EXAMPLES_SRC.is_dir():
        for pattern in EXAMPLE_GLOB:
            for src in EXAMPLES_SRC.glob(pattern):
                dst = root / 'examples' / src.name
                if not src.name.startswith('~') and not dst.exists():
                    shutil.copy2(src, dst)
    return root


#? -------------------------------------------------------------------------------
def is_writable(folder: str | os.PathLike) -> bool:
    folder = Path(folder)
    probe  = folder / f'.faster-write-test-{os.getpid()}'
    try:
        probe.write_bytes(b'')
        probe.unlink()
        return True
    except OSError:
        return False

#? -------------------------------------------------------------------------------
