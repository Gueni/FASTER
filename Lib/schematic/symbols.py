#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?                      _____                 __          __
#?                     / ___/__  ______ ___  / /_  ____  / /____
#?                     \__ \/ / / / __ `__ \/ __ \/ __ \/ / ___/
#?                    ___/ / /_/ / / / / / / /_/ / /_/ / (__  )
#?                   /____/\__, /_/ /_/ /_/_.___/\____/_/____/
#?                        /____/
#?
#? Name:        symbols.py
#? Purpose:     Load LTspice symbol (.asy) graphics.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     07/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------

"""Read the drawing primitives of LTspice ``.asy`` symbols.

Symbols are searched in the schematic folder first, then in the LTspice
symbol libraries (``%LOCALAPPDATA%\\LTspice\\lib\\sym`` and older locations).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from .asc_parser import _read_lines

SYMBOL_LIBRARIES = (
    r'%LOCALAPPDATA%\LTspice\lib\sym',
    r'%USERPROFILE%\Documents\LTspice\lib\sym',
    r'%USERPROFILE%\Documents\LTspiceXVII\lib\sym',
    '~/Library/Application Support/LTspice/lib/sym',
    '~/.wine/drive_c/users/' + os.environ.get('USER', '') + '/AppData/Local/LTspice/lib/sym',
)


#? -------------------------------------------------------------------------------
@dataclass
class Symbol:
    name    : str
    lines   : list[tuple[int, int, int, int]] = field(default_factory=list)
    rects   : list[tuple[int, int, int, int]] = field(default_factory=list)
    circles : list[tuple[int, int, int, int]] = field(default_factory=list)
    arcs    : list[tuple[int, ...]] = field(default_factory=list)
    texts   : list[tuple[int, int, str, int, str]] = field(default_factory=list)   # x, y, align, size, text
    pins    : list[tuple[int, int]] = field(default_factory=list)
    windows : dict[int, tuple[int, int, str, int]] = field(default_factory=dict)   # attr -> x, y, align, size
    attrs   : dict[str, str] = field(default_factory=dict)
    found   : bool = True


#? -------------------------------------------------------------------------------
def parse_shape_line(keyword: str, parts: list[str], sym: Symbol) -> bool:
    """Parse LINE / RECTANGLE / CIRCLE / ARC (shared by .asy and .asc). ``parts`` excludes the keyword."""
    try:
        nums = [int(p) for p in parts[1:] if p.lstrip('-').isdigit()]
    except ValueError:
        return False
    if keyword == 'LINE' and len(nums) >= 4:
        sym.lines.append(tuple(nums[:4]))
    elif keyword == 'RECTANGLE' and len(nums) >= 4:
        sym.rects.append(tuple(nums[:4]))
    elif keyword == 'CIRCLE' and len(nums) >= 4:
        sym.circles.append(tuple(nums[:4]))
    elif keyword == 'ARC' and len(nums) >= 8:
        sym.arcs.append(tuple(nums[:8]))
    else:
        return False
    return True


#? -------------------------------------------------------------------------------
def parse_text(rest: str) -> tuple[int, int, str, int, str] | None:
    """``x y align size text`` -> tuple."""
    parts = rest.split(' ', 4)
    if len(parts) < 5:
        return None
    try:
        return int(parts[0]), int(parts[1]), parts[2], int(parts[3]), parts[4]
    except ValueError:
        return None


#? -------------------------------------------------------------------------------
def load_symbol_file(path: Path, name: str) -> Symbol:
    sym = Symbol(name)
    try:
        lines = _read_lines(path)
    except OSError:
        return Symbol(name, found=False)
    if lines and not lines[0].startswith('Version'):
        return Symbol(name, found=False)        # encrypted / binary symbol
    for line in lines:
        keyword, _, rest = line.strip().partition(' ')
        parts = rest.split()
        if keyword in ('LINE', 'RECTANGLE', 'CIRCLE', 'ARC'):
            parse_shape_line(keyword, parts, sym)
        elif keyword == 'PIN' and len(parts) >= 2:
            sym.pins.append((int(parts[0]), int(parts[1])))
        elif keyword == 'WINDOW' and len(parts) >= 5:
            sym.windows[int(parts[0])] = (int(parts[1]), int(parts[2]), parts[3], int(parts[4]))
        elif keyword == 'SYMATTR':
            attr, _, value = rest.partition(' ')
            sym.attrs[attr] = value
        elif keyword == 'TEXT':
            t = parse_text(rest)
            if t:
                sym.texts.append(t)
    return sym


#? -------------------------------------------------------------------------------
@lru_cache(maxsize=None)
def _library_index() -> dict[str, Path]:
    """``{'res': path, 'misc\\cell': path, ...}`` for every installed symbol."""
    index: dict[str, Path] = {}
    for lib in SYMBOL_LIBRARIES:
        root = Path(os.path.expanduser(os.path.expandvars(lib)))
        if not root.is_dir():
            continue
        for dirpath, _, files in os.walk(root):
            for fn in files:
                if fn.lower().endswith('.asy'):
                    p   = Path(dirpath) / fn
                    rel = p.relative_to(root).with_suffix('').as_posix().lower().replace('/', '\\')
                    index.setdefault(rel, p)
                    index.setdefault(rel.split('\\')[-1], p)
    return index


#? -------------------------------------------------------------------------------
@lru_cache(maxsize=None)
def find_symbol(name: str, schematic_dir: str = '') -> Symbol:
    key = name.replace('/', '\\').lower()
    if schematic_dir:
        local = Path(schematic_dir) / (name.replace('\\', os.sep) + '.asy')
        if local.is_file():
            return load_symbol_file(local, name)
    path = _library_index().get(key) or _library_index().get(key.split('\\')[-1])
    if path is None:
        return Symbol(name, found=False)
    return load_symbol_file(path, name)

#? -------------------------------------------------------------------------------
