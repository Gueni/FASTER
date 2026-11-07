#!/usr/bin/env python
# coding=utf-8
# -------------------------------------------------------------------------------
# Name:        fmeda.py
# Purpose:     Failure Modes, Effects and Diagnostic Analysis.
#
# Author:      Mohamed Gueni (mohamedgueni@outlook.com)
# Created:     09/01/2024
# Licence:     Refer to the LICENSE file
# -------------------------------------------------------------------------------
"""Build the FMEDA table of a circuit from the failure-mode knowledge base."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pandas as pd

from .failures import component_failures
from .fit_rates import fit_rates as default_fit_rates

log = logging.getLogger(__name__)

FMEDA_COLUMNS = ['Component', 'Type', 'Value', 'Failure Mode', 'General Failure Effect',
                 'FIT', 'Mode Distribution (%)']


def analyze_failure_modes(components: list[dict]) -> dict[str, dict[str, str]]:
    """``{designator: {failure mode: effect}}`` for every known component type."""
    modes = {}
    for comp in components:
        known = component_failures.get(comp['type'])
        if known:
            modes[comp['name']] = known
        else:
            log.warning('No failure modes for %s (type %s)', comp['name'], comp['type'])
    return modes


def build_fmeda_table(components: list[dict], fit_rates: dict | None = None) -> pd.DataFrame:
    """One row per component failure mode, with FIT rate and mode distribution."""
    fit_rates = fit_rates or default_fit_rates
    rows = []
    for comp in components:
        modes = component_failures.get(comp['type'])
        if not modes:
            continue
        rates = fit_rates.get(comp['type'], {})
        total = sum(rates.get(m, 0) for m in modes)
        for mode, effect in modes.items():
            fit = rates.get(mode, 0)
            rows.append([comp['name'], comp['type'], comp.get('value'), mode, effect, fit,
                         round(100 * fit / total, 2) if total else 0.0])
    return pd.DataFrame(rows, columns=FMEDA_COLUMNS)


def save_fmeda(df: pd.DataFrame, path: str | os.PathLike) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, index=False, sheet_name='FMEDA')
    log.info('FMEDA saved to %s', path)
    return path
