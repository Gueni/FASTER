#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?                           ______            _____
#?                          / ____/___  ____  / __(_)___ _
#?                         / /   / __ \/ __ \/ /_/ / __ `/
#?                        / /___/ /_/ / / / / __/ / /_/ /
#?                        \____/\____/_/ /_/_/ /_/\__, /
#?                                               /____/
#?
#? Name:        config.py
#? Purpose:     Project paths, LTspice discovery and analysis configuration.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/01/2024
#? Updated:     07/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------

"""Central configuration: no other module hard-codes a path."""

from __future__ import annotations

import copy
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT   = Path(__file__).resolve().parents[2]
DATA_DIR       = PROJECT_ROOT / 'data'
DEFAULT_CONFIG = PROJECT_ROOT / 'config.json'
TEST_CIRCUIT   = PROJECT_ROOT / 'tests' / 'Test.asc'

# Default analysis settings, overridden by config.json
DEFAULTS: dict[str, Any] = {
    'ltspice_path'      : None,     # None -> auto-detect
    'parallel_sims'     : 4,
    'sim_timeout'       : 600,      # seconds per simulation
    'reliability': {
        'temperature_c' : 40.0,     # component temperature of the mission profile
        'environment'   : 'GB',     # MIL-HDBK-217F environment (GB, GF, GM, NS, AIC, ...)
        'fit_overrides' : {},       # {"IC": 35, "U1": 12.5}: base FIT by type or designator
    },
    'iso26262': {
        'target_asil'           : 'B',
        'not_safety_related'    : [],
        'safe_fraction'         : {},   # {"R2": {"drift high": 1.0}}
        'diagnostic_coverage'   : {},   # {"*": {"*": "medium"}} - none / low / medium / high or 0..1
        'latent_coverage'       : {},
    },
    'fta': {
        'mission_hours' : 8760,     # mission time for failure probability
    },
    'wca': {
        'enabled'               : True,
        'analysis_type'         : 'passive',    # default for components given as a number
        'components'            : {},           # {"R1": 12} or {"R1": {"tolerance": 12, "nominal": 1e5, "analysis_type": "passive"}}
        'output_variables'      : ['V(out)'],
        'max_corner_components' : 8,            # full corner search up to 2**N runs, one-at-a-time above
    },
    'montecarlo': {
        'enabled'           : True,
        'runs'              : 50,
        'distribution'      : 'uniform',        # "uniform" or "gaussian" (3 sigma = tolerance)
        'seed'              : None,
        'output_variable'   : 'V(out)',
        'tolerances'        : {},               # {"R1": 5} -> +/-5 %
    },
}

_LTSPICE_CANDIDATES = (
    r'%LOCALAPPDATA%\Programs\ADI\LTspice\LTspice.exe',
    r'C:\Program Files\ADI\LTspice\LTspice.exe',
    r'C:\Program Files\LTC\LTspiceXVII\XVIIx64.exe',
    r'C:\Program Files (x86)\LTC\LTspiceIV\scad3.exe',
    '/Applications/LTspice.app/Contents/MacOS/LTspice',
)


#? -------------------------------------------------------------------------------
def find_ltspice(explicit: str | os.PathLike | None = None) -> Path | None:
    """Locate the LTspice executable.

    Order: explicit argument, ``FASTER_LTSPICE`` environment variable,
    well-known install locations, then ``PATH``. Returns ``None`` if not found
    (PyLTSpice will then use its own detection).
    """
    candidates = [explicit, os.environ.get('FASTER_LTSPICE'), *_LTSPICE_CANDIDATES]
    for cand in candidates:
        if cand:
            path = Path(os.path.expandvars(str(cand)))
            if path.is_file():
                return path
    for exe in ('LTspice', 'LTspice.exe', 'XVIIx64.exe'):
        found = shutil.which(exe)
        if found:
            return Path(found)
    return None


#? -------------------------------------------------------------------------------
def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


#? -------------------------------------------------------------------------------
def _upgrade_legacy(cfg: dict) -> dict:
    """Convert the legacy single-component ``cmpt.json`` format."""
    if 'component_name' not in cfg:
        return cfg
    name = cfg['component_name']
    entry = {'tolerance': float(cfg.get('tolerance', 0)),
             'analysis_type': cfg.get('analysis_type', 'passive')}
    if cfg.get('nominal_value') is not None:
        entry['nominal'] = cfg['nominal_value']
    wca = {'components': {name: entry}}
    if 'output_variables' in cfg:
        wca['output_variables'] = cfg['output_variables']
    return {'wca': wca}


#? -------------------------------------------------------------------------------
def load_config(path: str | os.PathLike | None = None) -> dict[str, Any]:
    """Load a JSON configuration merged over :data:`DEFAULTS`."""
    path = Path(path) if path else DEFAULT_CONFIG
    user: dict[str, Any] = {}
    if path.is_file():
        with open(path, encoding='utf-8') as fh:
            user = _upgrade_legacy(json.load(fh))
    elif path != DEFAULT_CONFIG:
        raise FileNotFoundError(f'Config file not found: {path}')
    return _deep_merge(DEFAULTS, user)


#? -------------------------------------------------------------------------------
def new_run_dir(name: str, base: str | os.PathLike | None = None) -> Path:
    """Create ``<base>/<name>_<timestamp>`` and return it."""
    base    = Path(base) if base else DATA_DIR
    run_dir = base / f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir

#? -------------------------------------------------------------------------------
