# Purpose:     Persistent GUI settings (QSettings) and per-circuit analysis setups.
"""Application settings and per-circuit state.

Global preferences live in QSettings. The analysis setup of every circuit
(tolerances, diagnostic coverage ...) is stored as JSON keyed by the
schematic path, so reopening a circuit restores its setup.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSettings

ORG_NAME = 'Gueni'
APP_NAME = 'FASTER'
RECENT_MAX = 10


#? -------------------------------------------------------------------------------
def app_settings() -> QSettings:
    return QSettings(ORG_NAME, APP_NAME)


#? -------------------------------------------------------------------------------
def get(key: str, default: Any = None) -> Any:
    value = app_settings().value(key, default)
    if isinstance(default, bool):
        return value in (True, 'true', '1', 1)
    if isinstance(default, int) and not isinstance(default, bool):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
    if isinstance(default, float):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
    return value


#? -------------------------------------------------------------------------------
def put(key: str, value: Any) -> None:
    s = app_settings()
    s.setValue(key, value)
    s.sync()


#? -------------------------------------------------------------------------------
def recent_files() -> list[str]:
    raw = get('files/recent', '[]')
    try:
        items = json.loads(raw) if isinstance(raw, str) else list(raw or [])
    except ValueError:
        items = []
    return [p for p in items if Path(p).is_file()]


#? -------------------------------------------------------------------------------
def add_recent(path: str | Path) -> None:
    p     = str(Path(path).resolve())
    items = [x for x in recent_files() if x != p]
    put('files/recent', json.dumps([p] + items[:RECENT_MAX - 1]))


#? -------------------------------------------------------------------------------
def _circuit_key(path: str | Path) -> str:
    return 'circuits/' + hashlib.md5(str(Path(path).resolve()).lower().encode()).hexdigest()


#? -------------------------------------------------------------------------------
def load_circuit_state(path: str | Path) -> dict:
    raw = get(_circuit_key(path), '')
    try:
        return json.loads(raw) if raw else {}
    except ValueError:
        return {}


#? -------------------------------------------------------------------------------
def save_circuit_state(path: str | Path, state: dict) -> None:
    put(_circuit_key(path), json.dumps(state))
