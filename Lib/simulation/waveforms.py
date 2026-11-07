#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?             _       __                 ____
#?            | |     / /___ __   _____  / __/___  _________ ___  _____
#?            | | /| / / __ `/ | / / _ \/ /_/ __ \/ ___/ __ `__ \/ ___/
#?            | |/ |/ / /_/ /| |/ /  __/ __/ /_/ / /  / / / / / (__  )
#?            |__/|__/\__,_/ |___/\___/_/  \____/_/  /_/ /_/ /_/____/
#?
#? Name:        waveforms.py
#? Purpose:     Read LTspice .raw files and plot traces.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/01/2024
#? Updated:     07/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------

"""Raw-file helpers shared by WCA, Monte Carlo and the report."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import plotly.graph_objects as go

AXIS_NAMES = ('time', 'frequency')


#? -------------------------------------------------------------------------------
def open_raw(raw_file: str | os.PathLike):
    from PyLTSpice import RawRead
    return RawRead(str(raw_file))


#? -------------------------------------------------------------------------------
def resolve_trace(raw, name: str) -> str:
    """Return the trace name as stored in the raw file (case-insensitive match)."""
    names = raw.get_trace_names()
    if name in names:
        return name
    lookup = {n.lower(): n for n in names}
    try:
        return lookup[name.lower()]
    except KeyError:
        raise KeyError(f"Trace '{name}' not found. Available: {', '.join(names)}") from None


#? -------------------------------------------------------------------------------
def axis_name(raw) -> str | None:
    for n in raw.get_trace_names():
        if n.lower() in AXIS_NAMES:
            return n
    return None


#? -------------------------------------------------------------------------------
def get_wave(raw, name: str, step: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(axis, values)`` of a trace; complex (AC) data becomes magnitude."""
    y  = np.asarray(raw.get_trace(resolve_trace(raw, name)).get_wave(step))
    ax = axis_name(raw)
    x  = np.abs(np.asarray(raw.get_trace(ax).get_wave(step))) if ax else np.arange(len(y), dtype=float)
    if np.iscomplexobj(y):
        y = np.abs(y)
    return x, y.astype(float)


#? -------------------------------------------------------------------------------
def align(x_ref: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Resample ``y(x)`` onto ``x_ref`` (simulations rarely share time points)."""
    if len(x) == len(x_ref) and np.array_equal(x, x_ref):
        return y
    order = np.argsort(x, kind='stable')
    return np.interp(x_ref, x[order], y[order])


#? -------------------------------------------------------------------------------
def decimate_index(series: list[np.ndarray], max_points: int = 4000) -> np.ndarray:
    """Indices that keep the min and max of every series in each bucket.

    Report figures use SVG lines (WebGL contexts are limited per page), so long
    waveforms are reduced to ``max_points`` without losing peaks. The same
    indices are used for all ``series`` so envelopes stay aligned.
    """
    n = len(series[0]) if series else 0
    if n <= max_points:
        return np.arange(n)
    buckets = max(1, max_points // (2 * len(series)))
    edges   = np.linspace(0, n, buckets + 1, dtype=int)
    keep    = [0, n - 1]
    for a, b in zip(edges[:-1], edges[1:]):
        if b <= a:
            continue
        for y in series:
            seg = y[a:b]
            keep += [a + int(np.argmin(seg)), a + int(np.argmax(seg))]
    return np.unique(keep)


#? -------------------------------------------------------------------------------
def trace_statistics(raw_file: str | os.PathLike) -> 'pd.DataFrame':
    """Min / max / mean / RMS / peak-to-peak of every trace and step of a raw file."""
    import pandas as pd
    raw   = open_raw(raw_file)
    ax    = axis_name(raw)
    steps = list(raw.get_steps())
    rows  = []
    for name in raw.get_trace_names():
        if name == ax:
            continue
        for step in steps:
            x, y = get_wave(raw, name, step)
            row = {'Trace': name}
            if len(steps) > 1:
                row['Step'] = step
            row.update({'Points': len(y), 'Min': y.min(), 'Max': y.max(), 'Mean': y.mean(),
                        'RMS': float(np.sqrt(np.mean(y ** 2))), 'Peak-Peak': y.max() - y.min()})
            if len(x):
                row['Axis end'] = x[-1]
            rows.append(row)
    return pd.DataFrame(rows)


#? -------------------------------------------------------------------------------
def trace_figures(raw_file: str | os.PathLike, traces: list[str] | None = None,
                  max_points: int = 4000) -> list[go.Figure]:
    """One figure per trace, one line per ``.step`` (peak-preserving decimation to ``max_points``)."""
    raw   = open_raw(raw_file)
    ax    = axis_name(raw)
    names = [n for n in raw.get_trace_names() if n != ax]
    if traces:
        names = [resolve_trace(raw, t) for t in traces]
    steps   = list(raw.get_steps())
    x_title = {'time': 'Time (s)', 'frequency': 'Frequency (Hz)'}.get((ax or '').lower(), 'Point')
    figs    = []
    for name in names:
        fig = go.Figure()
        for step in steps:
            x, y  = get_wave(raw, name, step)
            idx   = decimate_index([y], max_points)
            label = f'step {step}' if len(steps) > 1 else name
            fig.add_trace(go.Scatter(x=x[idx], y=y[idx], mode='lines', name=label))
        unit = 'A' if name.upper().startswith('I(') else 'V'
        fig.update_layout(title=name, xaxis_title=x_title, yaxis_title=f'{name} ({unit})',
                          template='plotly_white', height=380, margin=dict(t=50, b=40))
        if (ax or '').lower() == 'frequency':
            fig.update_xaxes(type='log')
        figs.append(fig)
    return figs


#? -------------------------------------------------------------------------------
def show_raw(raw_file: str | os.PathLike, traces: list[str] | None = None) -> None:
    """Quick interactive look at a raw file in the browser."""
    for fig in trace_figures(raw_file, traces):
        fig.show()


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        sys.exit('usage: python -m Lib.simulation.waveforms <file.raw> [trace ...]')
    show_raw(Path(sys.argv[1]), sys.argv[2:] or None)

#? -------------------------------------------------------------------------------
