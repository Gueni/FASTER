#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?               __  ___            __          ______           __
#?              /  |/  /___  ____  / /____     / ____/___ ______/ /___
#?             / /|_/ / __ \/ __ \/ __/ _ \   / /   / __ `/ ___/ / __ \
#?            / /  / / /_/ / / / / /_/  __/  / /___/ /_/ / /  / / /_/ /
#?           /_/  /_/\____/_/ /_/\__/\___/   \____/\__,_/_/  /_/\____/
#?
#? Name:        montecarlo.py
#? Purpose:     Monte Carlo tolerance analysis.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/01/2024
#? Updated:     07/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------

"""Monte Carlo analysis: random component values within tolerance, run in parallel."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ..simulation.runner import SimJob, Simulator, parse_value
from ..simulation.waveforms import align, decimate_index, get_wave, open_raw

log = logging.getLogger(__name__)

DISTRIBUTIONS = ('uniform', 'gaussian')


#? -------------------------------------------------------------------------------
@dataclass
class MCResult:
    output_variable : str
    samples         : pd.DataFrame          # one row per run: component values + metrics
    x               : np.ndarray            # common axis (nominal run)
    nominal         : np.ndarray
    waves           : np.ndarray            # runs x len(x), NaN rows for failed runs
    raw_files       : dict[str, Path | None] = field(default_factory=dict)

    def statistics(self) -> pd.DataFrame:
        metrics = self.samples[['Peak', 'Min', 'Max', 'Mean', 'RMS']].dropna()
        return metrics.agg(['mean', 'std', 'min', 'max']).T

    def save_csv(self, out_dir: str | os.PathLike, prefix: str = 'montecarlo') -> tuple[Path, Path]:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        wave_path   = out_dir / f'{prefix}_waveforms.csv'
        sample_path = out_dir / f'{prefix}_samples.csv'
        cols        = {'Axis': self.x, 'Nominal': self.nominal}
        cols.update({f'Run_{i + 1}': w for i, w in enumerate(self.waves)})
        pd.DataFrame(cols).to_csv(wave_path, index=False)
        self.samples.to_csv(sample_path, index_label='Run')
        log.info('Monte Carlo results saved to %s and %s', wave_path, sample_path)
        return wave_path, sample_path

    def figure(self, max_traces: int = 100) -> go.Figure:
        fig = make_subplots(rows=1, cols=2, column_widths=[0.68, 0.32],
                            subplot_titles=(f'{self.output_variable} - all runs', 'Peak distribution'))
        comp_cols = [c for c in self.samples.columns if c not in ('Peak', 'Min', 'Max', 'Mean', 'RMS')]
        valid     = ~np.isnan(self.waves).all(axis=1) if len(self.waves) else np.array([], bool)
        series    = [self.nominal]
        if valid.any():
            series += [np.nanmin(self.waves[valid], axis=0), np.nanmax(self.waves[valid], axis=0)]
        idx = decimate_index(series, 1500)        # shared points keep the run envelope
        x   = self.x[idx]
        for i, (wave, (_, row)) in enumerate(zip(self.waves, self.samples.iterrows())):
            if i >= max_traces or not valid[i]:
                continue
            label = ', '.join(f'{c}={row[c]:.4g}' for c in comp_cols)
            fig.add_trace(go.Scatter(x=x, y=wave[idx], mode='lines', name=label, showlegend=False,
                                     line=dict(width=1), opacity=0.35, hovertext=label), row=1, col=1)
        fig.add_trace(go.Scatter(x=x, y=self.nominal[idx], mode='lines', name='nominal',
                                 line=dict(color='black', width=2)), row=1, col=1)
        fig.add_trace(go.Histogram(x=self.samples['Peak'].dropna(), name='Peak', nbinsx=30,
                                   showlegend=False), row=1, col=2)
        fig.update_xaxes(title_text='Time (s)', row=1, col=1)
        fig.update_yaxes(title_text=self.output_variable, row=1, col=1)
        fig.update_xaxes(title_text=f'max |{self.output_variable}|', row=1, col=2)
        fig.update_layout(title=f'Monte Carlo simulation ({len(self.samples)} runs)',
                          template='plotly_white', height=450, margin=dict(t=70, b=40))
        return fig


#? -------------------------------------------------------------------------------
class MonteCarloSimulation:
    def __init__(self, simulator: Simulator, tolerances: dict, runs: int = 50,
                 distribution: str = 'uniform', seed: int | None = None, output_variable: str = 'V(out)'):
        if not tolerances:
            raise ValueError('Monte Carlo needs at least one toleranced component')
        if distribution not in DISTRIBUTIONS:
            raise ValueError(f'distribution must be one of {DISTRIBUTIONS}')
        self.sim             = simulator
        self.runs            = int(runs)
        self.distribution    = distribution
        self.rng             = np.random.default_rng(seed)
        self.output_variable = output_variable
        # {"R1": 5} or {"R1": {"tolerance": 5, "nominal": "1k"}}  (tolerance in percent)
        self.nominals, self.tolerances = {}, {}
        for comp, entry in tolerances.items():
            if not isinstance(entry, dict):
                entry = {'tolerance': entry}
            nom = entry.get('nominal')
            self.nominals[comp] = simulator.nominal_value(comp) if nom is None else parse_value(nom)
            self.tolerances[comp] = float(entry.get('tolerance', 0)) / 100.0

    def input_table(self) -> pd.DataFrame:
        rows = []
        for comp, nom in self.nominals.items():
            tol = self.tolerances[comp]
            rows.append({'Component': comp, 'Nominal': nom, 'Tolerance (%)': 100 * tol,
                         'Min': nom * (1 - tol), 'Max': nom * (1 + tol), 'Distribution': self.distribution,
                         'Runs': self.runs, 'Output': self.output_variable})
        return pd.DataFrame(rows)

    def sample(self) -> pd.DataFrame:
        data = {}
        for comp, nom in self.nominals.items():
            tol = self.tolerances[comp]
            lo, hi = nom * (1 - tol), nom * (1 + tol)
            if self.distribution == 'uniform':
                data[comp] = self.rng.uniform(lo, hi, self.runs)
            else:  # gaussian, 3 sigma = tolerance, clipped to the tolerance band
                data[comp] = np.clip(self.rng.normal(nom, abs(nom) * tol / 3, self.runs), min(lo, hi), max(lo, hi))
        df       = pd.DataFrame(data)
        df.index = df.index + 1
        return df

    def run(self, progress=None) -> MCResult:
        samples = self.sample()
        jobs    = [SimJob('mc_nominal', values=self.nominals)]
        jobs += [SimJob(f'mc_{i:04d}', values=row.to_dict()) for i, row in samples.iterrows()]
        log.info('Monte Carlo: %d runs (%s)', self.runs, self.distribution)
        raws = self.sim.run_batch(jobs, progress)
        if raws.get('mc_nominal') is None:
            raise RuntimeError('Monte Carlo nominal simulation failed')

        x, nominal = get_wave(open_raw(raws['mc_nominal']), self.output_variable)
        waves   = np.full((self.runs, len(x)), np.nan)
        metrics = np.full((self.runs, 5), np.nan)
        for row, i in enumerate(samples.index):
            raw = raws.get(f'mc_{i:04d}')
            if raw is None:
                continue
            cx, cy = get_wave(open_raw(raw), self.output_variable)
            waves[row] = align(x, cx, cy)
            metrics[row] = [np.max(np.abs(cy)), cy.min(), cy.max(), cy.mean(), np.sqrt(np.mean(cy ** 2))]
        samples[['Peak', 'Min', 'Max', 'Mean', 'RMS']] = metrics
        failed = int(np.isnan(metrics[:, 0]).sum())
        if failed:
            log.warning('Monte Carlo: %d of %d runs failed', failed, self.runs)
        return MCResult(self.output_variable, samples, x, nominal, waves, raws)

#? -------------------------------------------------------------------------------
