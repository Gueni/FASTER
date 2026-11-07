#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?                            ________  _____________  ___
#?                           / ____/  |/  / ____/ __ \/   |
#?                          / /_  / /|_/ / __/ / / / / /| |
#?                         / __/ / /  / / /___/ /_/ / ___ |
#?                        /_/   /_/  /_/_____/_____/_/  |_|
#?
#? Name:        fmeda.py
#? Purpose:     Failure Modes, Effects and Diagnostic Analysis.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/01/2024
#? Updated:     07/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------

"""Build the FMEDA table of a circuit from the knowledge base.

Every component is expanded into its failure modes. The component FIT is
adjusted to the mission profile (temperature, environment) and split over the
modes with the published mode distributions.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pandas as pd

from ..knowledge.failures import FAILURE_MODES
from ..knowledge.fit_rates import BASE_FIT, T_REF_C, component_fit

log = logging.getLogger(__name__)

FMEDA_COLUMNS = ['Component', 'Type', 'Value', 'Failure Mode', 'Distribution (%)', 'Mechanism',
                 'General Failure Effect', 'Base FIT', 'pi_T', 'pi_E', 'Component FIT', 'FIT',
                 'Mode Source', 'FIT Source']


#? -------------------------------------------------------------------------------
def analyze_failure_modes(components: list[dict]) -> dict[str, dict[str, str]]:
    """``{designator: {failure mode: effect}}`` for every known component type."""
    out = {}
    for comp in components:
        entry = FAILURE_MODES.get(comp['type'])
        if entry:
            out[comp['name']] = {m.name: m.effect for m in entry.modes}
        else:
            log.warning('No failure modes for %s (type %s)', comp['name'], comp['type'])
    return out


#? -------------------------------------------------------------------------------
def build_fmeda_table(components: list[dict], reliability: dict | None = None) -> pd.DataFrame:
    """One row per component failure mode.

    ``reliability`` (from config.json)::

        {"temperature_c": 55, "environment": "GM",
         "fit_overrides": {"IC": 35, "U1": 12.5}}     # by type or designator
    """
    rel         = reliability or {}
    temperature = float(rel.get('temperature_c', T_REF_C))
    environment = str(rel.get('environment', 'GB'))
    overrides   = rel.get('fit_overrides', {}) or {}
    rows        = []
    for comp in components:
        entry = FAILURE_MODES.get(comp['type'])
        if not entry:
            log.warning('No failure modes for %s (type %s) - excluded from FMEDA', comp['name'], comp['type'])
            continue
        fit = component_fit(comp['type'], temperature, environment,
                            {comp['type']: overrides[comp['type']]} if comp['type'] in overrides else None)
        fit_source = BASE_FIT[comp['type']].source
        if comp['name'] in overrides:      # designator override = supplier FIT at reference conditions
            fit = {**fit, 'base': float(overrides[comp['name']])}
            fit['fit'] = fit['base'] * fit['pi_T'] * fit['pi_E']
            fit_source = 'user override'
        for mode in entry.modes:
            rows.append([comp['name'], comp['type'], comp.get('value'), mode.name, mode.distribution,
                         mode.mechanism, mode.effect, fit['base'], fit['pi_T'], fit['pi_E'], fit['fit'],
                         fit['fit'] * mode.distribution / 100.0, entry.source, fit_source])
    df = pd.DataFrame(rows, columns=FMEDA_COLUMNS)
    log.info('FMEDA: %d failure modes, %.4g FIT total (%.0f degC, %s)', len(df), df['FIT'].sum(),
             temperature, environment)
    return df


#? -------------------------------------------------------------------------------
def save_fmeda(df: pd.DataFrame, path: str | os.PathLike, extra_sheets: dict[str, pd.DataFrame] | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path) as writer:
        df.to_excel(writer, index=False, sheet_name='FMEDA')
        for name, sheet in (extra_sheets or {}).items():
            sheet.to_excel(writer, index=False, sheet_name=name[:31])
    log.info('FMEDA saved to %s', path)
    return path

#? -------------------------------------------------------------------------------
