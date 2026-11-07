#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?                 ___   _____ ______   _       __     _ __
#?                /   | / ___// ____/  | |     / /____(_) /____  _____
#?               / /| | \__ \/ /       | | /| / / ___/ / __/ _ \/ ___/
#?              / ___ |___/ / /___     | |/ |/ / /  / / /_/  __/ /
#?             /_/  |_/____/\____/     |__/|__/_/  /_/\__/\___/_/
#?
#? Name:        asc_writer.py
#? Purpose:     Edit LTspice schematics: component values / attributes and SPICE directives.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     07/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------

"""Text-level editing of ``.asc`` schematics.

Only the edited lines change; everything else (layout, windows, comments) is
kept byte for byte, and the file is written back in its original encoding and
line ending so LTspice opens it unchanged.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


#? -------------------------------------------------------------------------------
@dataclass
class AscDocument:
    path     : Path
    lines    : list[str]
    encoding : str = 'utf-8'
    newline  : str = '\n'

    @property
    def text(self) -> str:
        return '\n'.join(self.lines)

    #? loading / saving                                                             
    @classmethod
    def load(cls, path: str | os.PathLike) -> 'AscDocument':
        path = Path(path)
        raw  = path.read_bytes()
        if raw.startswith((b'\xff\xfe', b'\xfe\xff')):
            enc = 'utf-16'
        elif len(raw) > 1 and raw[1:2] == b'\x00':
            enc = 'utf-16-le'
        else:
            try:
                raw.decode('utf-8')
                enc = 'utf-8'
            except UnicodeDecodeError:
                enc = 'latin-1'
        text    = raw.decode(enc)
        newline = '\r\n' if '\r\n' in text else '\n'
        return cls(path, text.replace('\r\n', '\n').split('\n'), enc, newline)

    def save(self, path: str | os.PathLike | None = None) -> Path:
        target = Path(path) if path else self.path
        data   = self.newline.join(self.lines)
        target.write_bytes(data.encode(self.encoding))
        if path is None or target == self.path:
            self.path = target
        return target

    #? components                                                                   
    def _blocks(self) -> list[tuple[int, int, str | None]]:
        """``(first line, last line, InstName)`` of every SYMBOL block."""
        blocks, start, name = [], None, None
        for i, line in enumerate(self.lines + ['']):
            key = line.strip().split(' ', 1)[0]
            if start is not None and key not in ('SYMATTR', 'WINDOW'):
                blocks.append((start, i - 1, name))
                start, name = None, None
            if key == 'SYMBOL':
                start = i
            elif key == 'SYMATTR' and start is not None:
                attr, _, value = line.strip()[8:].partition(' ')
                if attr == 'InstName':
                    name = value.strip()
        return blocks

    def components(self) -> list[str]:
        return [n for _, _, n in self._blocks() if n]

    def get_attribute(self, name: str, attr: str) -> str | None:
        for a, b, n in self._blocks():
            if n == name:
                for line in self.lines[a:b + 1]:
                    s = line.strip()
                    if s.startswith(f'SYMATTR {attr} ') or s == f'SYMATTR {attr}':
                        return s[len(f'SYMATTR {attr}'):].strip()
        return None

    def set_attribute(self, name: str, attr: str, value: str) -> bool:
        """Set ``SYMATTR <attr> <value>`` of instance ``name`` (added if missing)."""
        for a, b, n in self._blocks():
            if n != name:
                continue
            last = a
            for i in range(a, b + 1):
                s = self.lines[i].strip()
                if s.startswith('SYMATTR'):
                    last = i
                if s.startswith(f'SYMATTR {attr} ') or s == f'SYMATTR {attr}':
                    self.lines[i] = f'SYMATTR {attr} {value}'
                    return True
            self.lines.insert(last + 1, f'SYMATTR {attr} {value}')
            return True
        return False

    def set_value(self, name: str, value: str) -> bool:
        return self.set_attribute(name, 'Value', value)

    def set_values(self, values: dict[str, str]) -> list[str]:
        """Set several values; return the names that were not found."""
        return [n for n, v in values.items() if not self.set_value(n, str(v))]

    #? directives                                                                   
    _TEXT = re.compile(r'^(TEXT\s+-?\d+\s+-?\d+\s+\S+\s+\d+\s+)([!;])(.*)$')

    def directives(self) -> list[tuple[int, str]]:
        """``(line index, directive)`` of every SPICE directive (``TEXT ... !``)."""
        out = []
        for i, line in enumerate(self.lines):
            m = self._TEXT.match(line.strip())
            if m and m.group(2) == '!':
                out.append((i, m.group(3).replace('\\n', '\n')))
        return out

    def set_directive(self, line_index: int, directive: str) -> None:
        m = self._TEXT.match(self.lines[line_index].strip())
        if not m:
            raise ValueError(f'Line {line_index} is not a directive')
        self.lines[line_index] = f"{m.group(1)}!{directive.strip().replace(chr(10), chr(92) + 'n')}"

    def add_directive(self, directive: str) -> int:
        """Add a directive below the existing ones; return its line index."""
        existing = self.directives()
        x, y     = 0, 0
        for i, _ in existing:
            parts = self.lines[i].split()
            x, y  = int(parts[1]), max(y, int(parts[2]))
        if existing:
            y += 40
        self.lines.append(f"TEXT {x} {y} Left 2 !{directive.strip().replace(chr(10), chr(92) + 'n')}")
        return len(self.lines) - 1

    def remove_line(self, line_index: int) -> None:
        del self.lines[line_index]

#? -------------------------------------------------------------------------------
