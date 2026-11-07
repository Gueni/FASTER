#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?                ___   _____ ______   ____
#?               /   | / ___// ____/  / __ \____ ______________  _____
#?              / /| | \__ \/ /      / /_/ / __ `/ ___/ ___/ _ \/ ___/
#?             / ___ |___/ / /___   / ____/ /_/ / /  (__  )  __/ /
#?            /_/  |_/____/\____/  /_/    \__,_/_/  /____/\___/_/
#?
#? Name:        asc_parser.py
#? Purpose:     Parse LTspice schematic (.asc) files.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/01/2024
#? Updated:     07/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------

"""Lightweight LTspice ``.asc`` parser (no LTspice install required).

Returns a dictionary::

    {
        'components' : [{'name', 'type', 'value', 'symbol', 'position', 'rotation', 'attributes'}],
        'wires'      : [((x1, y1), (x2, y2)), ...],
        'flags'      : {(x, y): net_name},
        'connections': {(x, y): [(x, y), ...]},   # wire end-point adjacency
        'directives' : ['.tran 100m', ...],
    }
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..knowledge.components import component_type


#? -------------------------------------------------------------------------------
def _read_lines(path: Path) -> list[str]:
    """Read an .asc file; LTspice may save it as UTF-16 or Latin-1."""
    raw = path.read_bytes()
    if raw.startswith((b'\xff\xfe', b'\xfe\xff')):
        text = raw.decode('utf-16')
    elif len(raw) > 1 and raw[1:2] == b'\x00':
        text = raw.decode('utf-16-le')
    else:
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            text = raw.decode('latin-1')
    return text.splitlines()


#? -------------------------------------------------------------------------------
def _finish(component: dict | None, components: list[dict]) -> None:
    if component is None:
        return
    attrs = component['attributes']
    component['name'] = attrs.get('InstName')
    component['value'] = attrs.get('Value') or attrs.get('Value2')
    component['type'] = component_type(component['symbol'], component['name'])
    if component['name']:
        components.append(component)


#? -------------------------------------------------------------------------------
def parse_ltspice_file(file_path: str | os.PathLike) -> dict[str, Any]:
    """Parse an LTspice schematic file."""
    path = Path(file_path)
    components: list[dict] = []
    wires: list[tuple[tuple[int, int], tuple[int, int]]] = []
    flags: dict[tuple[int, int], str] = {}
    connections: dict[tuple[int, int], list[tuple[int, int]]] = {}
    directives: list[str] = []
    current: dict | None = None

    for line in _read_lines(path):
        line = line.strip()
        if not line:
            continue
        keyword, _, rest = line.partition(' ')

        if keyword == 'SYMATTR' and current is not None:
            attr, _, value = rest.partition(' ')
            current['attributes'][attr] = value.strip()
            continue
        if keyword == 'WINDOW':
            continue

        # Any other keyword closes the current symbol block
        _finish(current, components)
        current = None

        if keyword == 'SYMBOL':
            parts = rest.split()
            if len(parts) >= 3:
                current = {
                    'name'      : None,
                    'type'      : None,
                    'value'     : None,
                    'symbol'    : parts[0],
                    'position'  : (int(parts[1]), int(parts[2])),
                    'rotation'  : parts[3] if len(parts) > 3 else 'R0',
                    'attributes': {},
                }
        elif keyword == 'WIRE':
            parts = rest.split()
            if len(parts) >= 4:
                p1 = (int(parts[0]), int(parts[1]))
                p2 = (int(parts[2]), int(parts[3]))
                wires.append((p1, p2))
                connections.setdefault(p1, []).append(p2)
                connections.setdefault(p2, []).append(p1)
        elif keyword == 'FLAG':
            parts = rest.split()
            if len(parts) >= 3:
                flags[(int(parts[0]), int(parts[1]))] = parts[2]
        elif keyword == 'TEXT':
            # TEXT x y align size !.directive   ('!' = SPICE directive, ';' = comment)
            idx = line.find('!')
            if idx != -1:
                directives.extend(d.strip() for d in line[idx + 1:].split('\\n') if d.strip())

    _finish(current, components)
    return {
        'components' : components,
        'wires'      : wires,
        'flags'      : flags,
        'connections': connections,
        'directives' : directives,
    }

#? -------------------------------------------------------------------------------
