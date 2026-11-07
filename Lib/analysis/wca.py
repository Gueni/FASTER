#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?                               _       ___________
#?                              | |     / / ____/   |
#?                              | | /| / / /   / /| |
#?                              | |/ |/ / /___/ ___ |
#?                              |__/|__/\____/_/  |_|
#?
#? Name:        wca.py
#? Purpose:     Worst-Case Analysis (extreme value / corner analysis).
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/01/2024
#? Updated:     07/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------

"""Worst-case analysis.

Every toleranced component is set to its minimum and maximum value. With up
to ``max_corner_components`` components all ``2**N`` corners are simulated
(true extreme value analysis); above that, components are varied one at a
time. Each output waveform is resampled onto the nominal axis and compared.
"""

from __future__ import annotations

import itertools
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from ..simulation.runner import SimJob, Simulator, parse_value
from ..simulation.waveforms import align, decimate_index, get_wave, open_raw

log = logging.getLogger(__name__)


#? -------------------------------------------------------------------------------
@dataclass
class Tolerance:
    component       : str
    nominal         : float
    tolerance       : float                 # percent (passive) or absolute (active)
    analysis_type   : str = 'passive'

    @property
    def limits(self) -> tuple[float, float]:
        if self.analysis_type == 'passive':
            delta = abs(self.nominal) * self.tolerance / 100.0
        elif self.analysis_type == 'active':
            delta = abs(self.tolerance)
        else:
            raise ValueError(f"Invalid analysis_type '{self.analysis_type}' for {self.component}")
        return self.nominal - delta, self.nominal + delta


#? -------------------------------------------------------------------------------
def parse_tolerances(spec: dict, simulator: Simulator, default_type: str = 'passive') -> list[Tolerance]:
    """Accept ``{"R1": 5}`` or ``{"R1": {"tolerance": 5, "nominal": 1e3, "analysis_type": "passive"}}``."""
    out = []
    for comp, entry in spec.items():
        if not isinstance(entry, dict):
            entry = {'tolerance': entry}
        nominal = entry.get('nominal')
        nominal = simulator.nominal_value(comp) if nominal is None else parse_value(nominal)
        out.append(Tolerance(comp, nominal, float(entry.get('tolerance', 0)),
                             entry.get('analysis_type', default_type)))
    return out


#? -------------------------------------------------------------------------------
def _describe(values: dict[str, float]) -> str:
    return ', '.join(f'{k}={v:.4g}' for k, v in values.items())


#? -------------------------------------------------------------------------------
@dataclass
class WCAResult:
    tolerances  : list[Tolerance]
    cases       : dict[str, dict[str, float]]
    summary     : pd.DataFrame
    waves       : dict[str, dict[str, np.ndarray]]
    raw_files   : dict[str, Path | None] = field(default_factory=dict)

    def figures(self) -> list[go.Figure]:
        figs = []
        for var, w in self.waves.items():
            fig = go.Figure()
            i   = decimate_index([w['high'], w['low'], w['nominal'], w['worst']], 4000)
            x   = w['x'][i]
            fig.add_trace(go.Scatter(x=x, y=w['high'][i], mode='lines', line=dict(width=0),
                                     showlegend=False, hoverinfo='skip'))
            fig.add_trace(go.Scatter(x=x, y=w['low'][i], mode='lines', line=dict(width=0),
                                     fill='tonexty', fillcolor='rgba(99,110,250,0.2)', name='WC envelope'))
            fig.add_trace(go.Scatter(x=x, y=w['nominal'][i], mode='lines', name='nominal'))
            fig.add_trace(go.Scatter(x=x, y=w['worst'][i], mode='lines', line=dict(dash='dash'),
                                     name=f"worst: {w['worst_label']}"))
            fig.update_layout(title=f'Worst-case analysis - {var}', template='plotly_white', height=400,
                              xaxis_title='Time (s)', yaxis_title=var, margin=dict(t=50, b=40))
            figs.append(fig)
        return figs

    def tolerance_table(self) -> pd.DataFrame:
        return pd.DataFrame([{'Component': t.component, 'Nominal': t.nominal, 'Tolerance': t.tolerance,
                              'Type': t.analysis_type, 'Min': t.limits[0], 'Max': t.limits[1]}
                             for t in self.tolerances])

    def case_table(self) -> pd.DataFrame:
        cases = pd.DataFrame.from_dict(self.cases, orient='index')
        cases['Simulated'] = [self.raw_files.get(c) is not None for c in cases.index]
        return cases.rename_axis('Case').reset_index()

    def save(self, path: str | os.PathLike) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with pd.ExcelWriter(path) as writer:
            self.summary.to_excel(writer, sheet_name='Summary', index=False)
            self.tolerance_table().to_excel(writer, sheet_name='Tolerances', index=False)
            self.case_table().to_excel(writer, sheet_name='Cases', index=False)
        log.info('WCA saved to %s', path)
        return path


#? -------------------------------------------------------------------------------
class WorstCaseAnalysis:
    def __init__(self, simulator: Simulator, tolerances: list[Tolerance],
                 output_variables: list[str], max_corner_components: int = 8):
        if not tolerances:
            raise ValueError('WCA needs at least one toleranced component')
        self.sim                   = simulator
        self.tolerances            = tolerances
        self.output_variables      = list(output_variables)
        self.max_corner_components = max_corner_components

    def build_cases(self) -> dict[str, dict[str, float]]:
        nominal = {t.component: t.nominal for t in self.tolerances}
        cases   = {'wca_nominal': nominal}
        if len(self.tolerances) <= self.max_corner_components:
            for i, combo in enumerate(itertools.product(*(t.limits for t in self.tolerances))):
                cases[f'wca_corner_{i:03d}'] = dict(zip(nominal, combo))
        else:
            for t in self.tolerances:
                lo, hi = t.limits
                cases[f'wca_{t.component}_min'] = {**nominal, t.component: lo}
                cases[f'wca_{t.component}_max'] = {**nominal, t.component: hi}
        return cases

    def run(self, progress=None) -> WCAResult:
        cases = self.build_cases()
        log.info('WCA: %d simulations for %s', len(cases), ', '.join(t.component for t in self.tolerances))
        raws = self.sim.run_batch((SimJob(name, values=vals) for name, vals in cases.items()), progress)
        if raws.get('wca_nominal') is None:
            raise RuntimeError('WCA nominal simulation failed')

        opened = {name: open_raw(p) for name, p in raws.items() if p is not None}
        rows, waves = [], {}
        for var in self.output_variables:
            x, nom = get_wave(opened['wca_nominal'], var)
            stack, labels = [], []
            for name, raw in opened.items():
                if name == 'wca_nominal':
                    continue
                cx, cy = get_wave(raw, var)
                stack.append(align(x, cx, cy))
                labels.append(name)
            if not stack:
                raise RuntimeError('All WCA corner simulations failed')
            stack       = np.vstack(stack)
            deviation   = np.max(np.abs(stack - nom), axis=1)
            worst       = int(np.argmax(deviation))
            nom_peak    = float(np.max(np.abs(nom)))
            worst_label = _describe(cases[labels[worst]])
            rows.append({
                'Output'            : var,
                'Nominal Peak'      : nom_peak,
                'Worst Deviation'   : float(deviation[worst]),
                'Deviation (%)'     : 100 * float(deviation[worst]) / nom_peak if nom_peak else 0.0,
                'Min (all cases)'   : float(stack.min()),
                'Max (all cases)'   : float(stack.max()),
                'Worst Case'        : labels[worst],
                'Worst Case Values' : worst_label,
            })
            waves[var] = {'x': x, 'nominal': nom, 'low': stack.min(axis=0), 'high': stack.max(axis=0),
                          'worst': stack[worst], 'worst_label': worst_label}
            log.info('WCA %s: worst deviation %.4g (%.2f %%) at %s', var, deviation[worst],
                     rows[-1]['Deviation (%)'], worst_label)
        return WCAResult(self.tolerances, cases, pd.DataFrame(rows), waves, raws)

#? -------------------------------------------------------------------------------
