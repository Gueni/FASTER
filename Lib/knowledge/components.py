#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?            ______                                             __
#?           / ____/___  ____ ___  ____  ____  ____  ___  ____  / /______
#?          / /   / __ \/ __ `__ \/ __ \/ __ \/ __ \/ _ \/ __ \/ __/ ___/
#?         / /___/ /_/ / / / / / / /_/ / /_/ / / / /  __/ / / / /_(__  )
#?         \____/\____/_/ /_/ /_/ .___/\____/_/ /_/\___/_/ /_/\__/____/
#?                             /_/
#?
#? Name:        components.py
#? Purpose:     Identify the component type of an LTspice symbol / designator.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/01/2024
#? Updated:     07/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------

"""Component type identification.

The type is resolved from the LTspice symbol name first (``res``, ``cap``,
``Opamps\\LT1001`` ...) and falls back to the designator prefix (``R1``,
``C3`` ...). Type names match the keys of :mod:`Lib.knowledge.failures` and
:mod:`Lib.knowledge.fit_rates`.
"""

from __future__ import annotations

# Exact LTspice symbol names (lower case, without library folder) -> type
SYMBOL_TYPES: dict[str, str] = {
    'voltage'       : 'voltage',
    'signal'        : 'voltage',
    'current'       : 'current',
    'battery'       : 'battery',
    'cell'          : 'battery',
    'res'           : 'resistor',
    'res2'          : 'resistor',
    'europeanresistor': 'resistor',
    'cap'           : 'capacitor',
    'europeancap'   : 'capacitor',
    'polcap'        : 'electrolytic capacitor',
    'europeanpolcap': 'electrolytic capacitor',
    'ind'           : 'inductor',
    'ind2'          : 'inductor',
    'fixedind'      : 'inductor',
    'ferritebead'   : 'ferrite bead',
    'ferritebead2'  : 'ferrite bead',
    'transformer'   : 'transformer',
    'xtal'          : 'crystal',
    'fuse'          : 'fuse',
    'diode'         : 'diode',
    'varactor'      : 'diode',
    'zener'         : 'zener',
    'schottky'      : 'schottky',
    'tvsdiode'      : 'tvs',
    'xvaristor'     : 'tvs',
    'led'           : 'LED',
    'npn'           : 'bjt',
    'npn2'          : 'bjt',
    'npn3'          : 'bjt',
    'npn4'          : 'bjt',
    'pnp'           : 'bjt',
    'pnp2'          : 'bjt',
    'pnp4'          : 'bjt',
    'nmos'          : 'mosfet',
    'nmos4'         : 'mosfet',
    'pmos'          : 'mosfet',
    'pmos4'         : 'mosfet',
    'njf'           : 'jfet',
    'pjf'           : 'jfet',
    'nigbt'         : 'igbt',
    'pigbt'         : 'igbt',
    'scr'           : 'thyristor',
    'triac'         : 'thyristor',
    'diac'          : 'thyristor',
    'opamp'         : 'op-amp',
    'opamp2'        : 'op-amp',
    'ne555'         : 'IC',
    'sw'            : 'switch',
    'csw'           : 'switch',
    'relay'         : 'relay',
    'connector'     : 'connector',
}

# Symbol library folders (lower case) -> type
LIBRARY_TYPES: dict[str, str] = {
    'opamps'        : 'op-amp',
    'comparators'   : 'op-amp',
}

# Designator prefixes -> type (longest prefix wins)
DESIGNATOR_TYPES: dict[str, str] = {
    'LED'   : 'LED',
    'FB'    : 'ferrite bead',
    'L_FERRITE': 'ferrite bead',
    'XTAL'  : 'crystal',
    'Y'     : 'crystal',
    'V'     : 'voltage',
    'I'     : 'current',
    'B'     : 'voltage',
    'R'     : 'resistor',
    'C'     : 'capacitor',
    'L'     : 'inductor',
    'D'     : 'diode',
    'Q'     : 'bjt',
    'M'     : 'mosfet',
    'J'     : 'jfet',
    'Z'     : 'mosfet',
    'U'     : 'IC',
    'X'     : 'IC',
    'T'     : 'transformer',
    'K'     : 'transformer',
    'F'     : 'fuse',
    'S'     : 'switch',
    'W'     : 'switch',
    'RL'    : 'relay',
    'CN'    : 'connector',
}
_PREFIXES = sorted(DESIGNATOR_TYPES, key=len, reverse=True)


#? -------------------------------------------------------------------------------
def type_from_symbol(symbol: str | None) -> str | None:
    """Return the component type for an LTspice symbol name, or ``None``."""
    if not symbol:
        return None
    parts = symbol.replace('/', '\\').lower().split('\\')
    name  = parts[-1]
    if name in SYMBOL_TYPES:
        return SYMBOL_TYPES[name]
    for folder in parts[:-1]:
        if folder in LIBRARY_TYPES:
            return LIBRARY_TYPES[folder]
    return None


#? -------------------------------------------------------------------------------
def type_from_designator(designator: str | None) -> str:
    """Return the component type for a designator such as ``R12``."""
    if not designator:
        return 'Unknown'
    upper = designator.upper()
    for prefix in _PREFIXES:
        if upper.startswith(prefix):
            return DESIGNATOR_TYPES[prefix]
    return 'Unknown'


#? -------------------------------------------------------------------------------
def component_type(symbol: str | None, designator: str | None) -> str:
    """Resolve a component type using the symbol first, then the designator."""
    return type_from_symbol(symbol) or type_from_designator(designator)

#? -------------------------------------------------------------------------------
