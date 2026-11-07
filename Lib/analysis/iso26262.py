#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?                    _________ ____     ___   ________   ________
#?                   /  _/ ___// __ \   |__ \ / ___/__ \ / ___/__ \
#?                   / / \__ \/ / / /   __/ // __ \__/ // __ \__/ /
#?                 _/ / ___/ / /_/ /   / __// /_/ / __// /_/ / __/
#?                /___//____/\____/   /____/\____/____/\____/____/
#?
#? Name:        iso26262.py
#? Purpose:     ISO 26262-5 hardware architectural metrics (SPFM, LFM, PMHF).
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     07/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------

"""ISO 26262-5:2018 hardware architectural metrics from the FMEDA.

Per failure mode with failure rate ``lambda``:

* ``safe fraction``  share of the mode that cannot violate the safety goal
* ``DC``             diagnostic coverage of the safety mechanism w.r.t. residual faults
* ``DC latent``      coverage of latent multiple-point faults (e.g. start-up tests)

Classification (ISO 26262-5 Annex B)::

    lambda_safe   = lambda * safe
    lambda_SPF    = lambda * (1 - safe)                 if no safety mechanism (DC = 0)
    lambda_RF     = lambda * (1 - safe) * (1 - DC)      if a safety mechanism exists
    lambda_MPF    = lambda * (1 - safe) * DC
    lambda_MPF,L  = lambda_MPF * (1 - DC latent)

    SPFM = 1 - sum(lambda_SPF + lambda_RF) / sum(lambda)
    LFM  = 1 - sum(lambda_MPF,L) / sum(lambda - lambda_SPF - lambda_RF)
    PMHF ~ sum(lambda_SPF + lambda_RF)   (first-order estimate, FIT)

Targets: ISO 26262-5 Tables 4 (SPFM), 5 (LFM) and 6 (PMHF).

The safe fraction / DC values depend on the system and its safety mechanisms
and must come from the safety analysis. They are set in ``config.json``::

    "iso26262": {
        "target_asil": "B",
        "not_safety_related": ["R7"],
        "safe_fraction":       {"resistor": {"drift high": 1.0}},
        "diagnostic_coverage": {"*": {"*": 0.0}, "Vin": {"*": 0.99}},
        "latent_coverage":     {"*": {"*": 0.9}}
    }

Keys are a designator, a component type or ``*``; inner keys a failure mode
or ``*``. The most specific match wins (designator > type > ``*``).
Typical DC values (ISO 26262-5 Annex D): low 60 %, medium 90 %, high 99 %.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

import pandas as pd

log = logging.getLogger(__name__)

# ISO 26262-5:2018 Tables 4, 5, 6
TARGETS: dict[str, dict[str, float | None]] = {
    'QM': {'SPFM': None, 'LFM': None, 'PMHF': None},
    'A' : {'SPFM': None, 'LFM': None, 'PMHF': 1000.0},
    'B' : {'SPFM': 0.90, 'LFM': 0.60, 'PMHF': 100.0},
    'C' : {'SPFM': 0.97, 'LFM': 0.80, 'PMHF': 100.0},
    'D' : {'SPFM': 0.99, 'LFM': 0.90, 'PMHF': 10.0},
}
DC_LEVELS = {'none': 0.0, 'low': 0.60, 'medium': 0.90, 'high': 0.99}


#? -------------------------------------------------------------------------------
def _lookup(table: dict, designator: str, comp_type: str, mode: str, default: float) -> float:
    for key in (designator, comp_type, '*'):
        inner = table.get(key)
        if inner is None:
            continue
        if not isinstance(inner, dict):
            return _value(inner)
        for mkey in (mode, '*'):
            if mkey in inner:
                return _value(inner[mkey])
    return default


#? -------------------------------------------------------------------------------
def _value(v) -> float:
    if isinstance(v, str):
        if v.lower() in DC_LEVELS:
            return DC_LEVELS[v.lower()]
        v = float(v.rstrip('%')) / 100.0 if v.endswith('%') else float(v)
    v = float(v)
    return v / 100.0 if v > 1.0 else v      # accept 90 or 0.9


#? -------------------------------------------------------------------------------
@dataclass
class HardwareMetrics:
    table   : pd.DataFrame      # FMEDA rows with ISO 26262 columns
    metrics : dict[str, float]
    targets : dict[str, float | None]
    asil    : str

    def summary(self) -> pd.DataFrame:
        rows = []
        for key, fmt in (('SPFM', '{:.2%}'), ('LFM', '{:.2%}'), ('PMHF', '{:.4g} FIT')):
            value, target = self.metrics[key], self.targets[key]
            if target is None:
                verdict, target_txt = 'n/a', '-'
            elif math.isnan(value):      # e.g. LFM without multiple-point faults
                verdict, target_txt = 'n/a', f'>= {target:.0%}'
            elif key == 'PMHF':
                verdict, target_txt = ('PASS' if value < target else 'FAIL'), f'< {target:g} FIT'
            else:
                verdict, target_txt = ('PASS' if value >= target else 'FAIL'), f'>= {target:.0%}'
            rows.append({'Metric': key, 'Value': fmt.format(value) if not math.isnan(value) else 'n/a',
                         f'Target ASIL {self.asil}': target_txt, 'Result': verdict})
        return pd.DataFrame(rows)

    def lambda_summary(self) -> pd.DataFrame:
        cols    = ['lambda', 'lambda safe', 'lambda SPF', 'lambda RF', 'lambda MPF', 'lambda MPF latent']
        by_comp = self.table.groupby(['Component', 'Type'], sort=False)[cols].sum().reset_index()
        total   = by_comp[cols].sum().to_frame().T
        total.insert(0, 'Component', 'TOTAL')
        total.insert(1, 'Type', '')
        return pd.concat([by_comp, total], ignore_index=True)

    @property
    def passed(self) -> bool:
        return all(r != 'FAIL' for r in self.summary()['Result'])


#? -------------------------------------------------------------------------------
def hardware_metrics(fmeda: pd.DataFrame, cfg: dict | None = None) -> HardwareMetrics:
    cfg  = cfg or {}
    asil = str(cfg.get('target_asil', 'B')).upper().replace('ASIL', '').strip() or 'QM'
    if asil not in TARGETS:
        raise ValueError(f'target_asil must be one of {list(TARGETS)}')
    not_sr = set(cfg.get('not_safety_related', []) or [])
    safe_t = cfg.get('safe_fraction', {}) or {}
    dc_t   = cfg.get('diagnostic_coverage', {}) or {}
    lat_t  = cfg.get('latent_coverage', {}) or {}

    rows = []
    for r in fmeda.to_dict('records'):
        comp, ctype, mode, lam = r['Component'], r['Type'], r['Failure Mode'], float(r['FIT'])
        sr        = comp not in not_sr
        safe      = 1.0 if not sr else _lookup(safe_t, comp, ctype, mode, 0.0)
        dc        = _lookup(dc_t, comp, ctype, mode, 0.0)
        dcl       = _lookup(lat_t, comp, ctype, mode, 0.0)
        dangerous = lam * (1 - safe)
        spf       = dangerous if dc == 0 else 0.0
        rf        = dangerous * (1 - dc) if dc > 0 else 0.0
        mpf       = dangerous * dc
        rows.append({**r, 'Safety Related': sr, 'Safe Fraction': safe, 'DC': dc, 'DC Latent': dcl,
                     'lambda': lam, 'lambda safe': lam * safe, 'lambda SPF': spf, 'lambda RF': rf,
                     'lambda MPF': mpf, 'lambda MPF latent': mpf * (1 - dcl)})
    table = pd.DataFrame(rows)

    sr_rows = table[table['Safety Related']] if not table.empty else table
    total   = float(sr_rows['lambda'].sum()) if not table.empty else 0.0
    spf_rf  = float((sr_rows['lambda SPF'] + sr_rows['lambda RF']).sum()) if not table.empty else 0.0
    latent  = float(sr_rows['lambda MPF latent'].sum()) if not table.empty else 0.0
    metrics = {
        'lambda total (FIT)'    : total,
        'lambda SPF+RF (FIT)'   : spf_rf,
        'lambda MPF latent (FIT)': latent,
        'SPFM'                  : 1 - spf_rf / total if total else math.nan,
        'LFM'                   : 1 - latent / (total - spf_rf) if total - spf_rf > 0 else math.nan,
        'PMHF'                  : spf_rf,
    }
    result  = HardwareMetrics(table, metrics, TARGETS[asil], asil)
    summary = result.summary().set_index('Metric')
    log.info('ISO 26262 (ASIL %s): SPFM %s, LFM %s, PMHF %s -> %s', asil, summary.loc['SPFM', 'Value'],
             summary.loc['LFM', 'Value'], summary.loc['PMHF', 'Value'], 'PASS' if result.passed else 'FAIL')
    return result

#? -------------------------------------------------------------------------------
