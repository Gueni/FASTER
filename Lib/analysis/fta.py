#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?                                  _______________
#?                                 / ____/_  __/   |
#?                                / /_    / / / /| |
#?                               / __/   / / / ___ |
#?                              /_/     /_/ /_/  |_|
#?
#? Name:        fta.py
#? Purpose:     Fault Tree Analysis.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/01/2024
#? Updated:     07/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------

"""Fault tree built from the FMEDA table.

Tree: top event "circuit failure" = OR(components), component = OR(failure
modes). With constant failure rates, ``P(t) = 1 - exp(-lambda * t)``.
"""

from __future__ import annotations

import logging
import math
import os
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

log = logging.getLogger(__name__)

FIT_TO_PER_HOUR = 1e-9


#? -------------------------------------------------------------------------------
def failure_probability(fit: float, hours: float) -> float:
    return 1.0 - math.exp(-fit * FIT_TO_PER_HOUR * hours)


#? -------------------------------------------------------------------------------
def build_fault_tree(fmeda: pd.DataFrame) -> dict[str, dict]:
    """``{designator: {'type', 'modes': {mode: {'effect', 'fit'}}}}`` from the FMEDA table."""
    tree: dict[str, dict] = {}
    for row in fmeda.to_dict('records'):
        node = tree.setdefault(row['Component'], {'type': row['Type'], 'modes': {}})
        node['modes'][row['Failure Mode']] = {'effect': row['General Failure Effect'],
                                              'fit': float(row['FIT'])}
    return tree


#? -------------------------------------------------------------------------------
def analyze_fault_tree(tree: dict[str, dict], mission_hours: float = 8760) -> dict:
    """Compute FIT, share and failure probability for every node."""
    components = {}
    system_fit = sum(m['fit'] for node in tree.values() for m in node['modes'].values())
    for name, node in tree.items():
        comp_fit = sum(m['fit'] for m in node['modes'].values())
        details  = {}
        for mode, m in node['modes'].items():
            details[mode] = {
                'Impact'                    : m['effect'],
                'FIT Rate'                  : m['fit'],
                'Share of Component (%)'    : 100 * m['fit'] / comp_fit if comp_fit else 0.0,
                'Share of System (%)'       : 100 * m['fit'] / system_fit if system_fit else 0.0,
                'Probability'               : failure_probability(m['fit'], mission_hours),
            }
        components[name] = {
            'Type'          : node['type'],
            'Total FIT'     : comp_fit,
            'Probability'   : failure_probability(comp_fit, mission_hours),
            'Failure Details': details,
        }
    overall = {
        'Total FIT'         : system_fit,
        'MTTF (h)'          : 1e9 / system_fit if system_fit else math.inf,
        'Mission (h)'       : mission_hours,
        'Probability'       : failure_probability(system_fit, mission_hours),
        'Components'        : len(tree),
        'Failure Modes'     : sum(len(n['modes']) for n in tree.values()),
    }
    return {'components': components, 'overall': overall}


#? -------------------------------------------------------------------------------
def fta_to_dataframes(results: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Flatten results into (failure-mode table, summary table)."""
    rows = []
    for name, comp in results['components'].items():
        for mode, d in comp['Failure Details'].items():
            rows.append({'Component': name, 'Type': comp['Type'], 'Component FIT': comp['Total FIT'],
                         'Failure Mode': mode, **d})
    detail  = pd.DataFrame(rows)
    summary = pd.DataFrame([results['overall']])
    return detail, summary


#? -------------------------------------------------------------------------------
def save_fta_results(results: dict, path: str | os.PathLike) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    detail, summary = fta_to_dataframes(results)
    with pd.ExcelWriter(path) as writer:
        summary.to_excel(writer, sheet_name='Summary', index=False)
        detail.to_excel(writer, sheet_name='Failure Modes', index=False)
    log.info('FTA saved to %s', path)
    return path


#? -------------------------------------------------------------------------------
def fault_tree_figure(results: dict) -> go.Figure:
    """Sunburst of the fault tree, sized by FIT rate."""
    top = 'Circuit failure'
    ids, labels, parents, values = [top], [top], [''], [results['overall']['Total FIT']]
    for name, comp in results['components'].items():
        ids.append(name); labels.append(name); parents.append(top); values.append(comp['Total FIT'])
        for mode, d in comp['Failure Details'].items():
            ids.append(f'{name}/{mode}'); labels.append(mode); parents.append(name); values.append(d['FIT Rate'])
    fig = go.Figure(go.Sunburst(ids=ids, labels=labels, parents=parents, values=values,
                                branchvalues='total', hovertemplate='%{label}<br>FIT %{value}<extra></extra>'))
    fig.update_layout(title='Fault tree (FIT contribution)', height=550, margin=dict(t=50, l=0, r=0, b=0))
    return fig

#? -------------------------------------------------------------------------------
