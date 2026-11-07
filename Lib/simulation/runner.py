#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?                          ____
#?                         / __ \__  ______  ____  ___  _____
#?                        / /_/ / / / / __ \/ __ \/ _ \/ ___/
#?                       / _, _/ /_/ / / / / / / /  __/ /
#?                      /_/ |_|\__,_/_/ /_/_/ /_/\___/_/
#?
#? Name:        runner.py
#? Purpose:     Run LTspice simulations (single, value sweeps, model sweeps).
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/01/2024
#? Updated:     07/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------

"""LTspice simulation engine built on PyLTSpice.

All analyses go through :class:`Simulator`, which edits the schematic in
memory, writes one netlist per job and runs the jobs in parallel.

Example::

    sim = Simulator('Test.asc', 'data/sims')
    raws = sim.run_batch([SimJob('a', values={'R1': '10k'}),
                          SimJob('b', values={'R1': '20k'})])
"""

from __future__ import annotations

import itertools
import logging
import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Union

from ..core.config import find_ltspice

log = logging.getLogger(__name__)

POLL_S = 0.05      # completion polling period of run_batch

Value = Union[str, float, int]


_SUFFIXES = {'t': 1e12, 'g': 1e9, 'meg': 1e6, 'k': 1e3, 'mil': 25.4e-6, 'm': 1e-3,
             'u': 1e-6, 'µ': 1e-6, 'μ': 1e-6, 'n': 1e-9, 'p': 1e-12, 'f': 1e-15}
_VALUE_RE = re.compile(r'^\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?)\s*(meg|mil|[tgkmuµμnpf])?', re.I)


#? -------------------------------------------------------------------------------
def parse_value(value: Value) -> float:
    """Parse a SPICE number: ``'11.5K' -> 11500``, ``'1meg' -> 1e6``, ``'4k7'`` style is not SPICE."""
    if isinstance(value, (int, float)):
        return float(value)
    match = _VALUE_RE.match(str(value))
    if not match:
        raise ValueError(f'Not a numeric SPICE value: {value!r}')
    number, suffix = match.groups()
    return float(number) * (_SUFFIXES[suffix.lower()] if suffix else 1.0)


#? -------------------------------------------------------------------------------
def format_value(value: Value) -> str:
    """Format a component value for LTspice (``1234.5678 -> '1234.57'``)."""
    if isinstance(value, str):
        return value
    return f'{float(value):.6g}'


#? -------------------------------------------------------------------------------
@dataclass
class SimJob:
    """One simulation: component values, ``.param`` values and model changes."""
    name    : str
    values  : Mapping[str, Value] = field(default_factory=dict)
    params  : Mapping[str, Value] = field(default_factory=dict)
    models  : Mapping[str, str]   = field(default_factory=dict)


#? -------------------------------------------------------------------------------
class Simulator:
    """Thin wrapper around :class:`PyLTSpice.SimRunner`."""

    def __init__(self, circuit: str | os.PathLike, output_dir: str | os.PathLike,
                 parallel: int = 4, timeout: float = 600, ltspice_path: str | os.PathLike | None = None):
        from PyLTSpice import AscEditor, LTspice, SimRunner

        self.circuit = Path(circuit).resolve()
        if not self.circuit.is_file():
            raise FileNotFoundError(f'Circuit not found: {self.circuit}')
        self.output_dir = Path(output_dir).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)

        simulator = LTspice
        exe       = find_ltspice(ltspice_path)
        if exe is not None:
            simulator = LTspice.create_from(str(exe))
        self.runner = SimRunner(simulator=simulator, parallel_sims=max(1, int(parallel)),
                                timeout=timeout, output_folder=str(self.output_dir))
        self.editor = AscEditor(str(self.circuit))

    #? netlist access                                                             
    def nominal_value(self, component: str) -> float:
        """Numeric value of a component in the original schematic."""
        self.editor.reset_netlist()
        return parse_value(self.editor.get_component_value(component))

    def components(self) -> list[str]:
        self.editor.reset_netlist()
        return list(self.editor.get_components())

    #? running                                                                    
    def _apply(self, job: SimJob) -> None:
        editor = self.editor
        editor.reset_netlist()
        for ref, value in job.values.items():
            editor.set_component_value(ref, format_value(value))
        for ref, model in job.models.items():
            editor.set_element_model(ref, model)
        if job.params:
            editor.set_parameters(**{k: format_value(v) for k, v in job.params.items()})

    def _finished_count(self) -> int:
        self.runner.update_completed()
        return self.runner.okSim + self.runner.failSim

    def run_batch(self, jobs: Iterable[SimJob],
                  progress: Callable[[int, int], None] | None = None) -> dict[str, Path | None]:
        """Run all jobs in parallel; return ``{job name: raw file or None}``.

        ``progress(done, total)`` is called as simulations complete. Completion is
        polled every 50 ms (SimRunner.wait_completion() polls only once per second).
        """
        jobs  = list(jobs)
        total = len(jobs)
        base  = self._finished_count()
        last  = -1

        def report() -> None:
            nonlocal last
            done = self._finished_count() - base
            if progress is not None and done != last:
                last = done
                progress(done, total)

        tasks = {}
        for job in jobs:
            self._apply(job)
            # The netlist is written synchronously, so the editor can be reused.
            tasks[job.name] = self.runner.run(self.editor, run_filename=f'{job.name}.asc')
            report()
        while self.runner.active_tasks:
            time.sleep(POLL_S)
            report()
        report()
        self.editor.reset_netlist()

        results: dict[str, Path | None] = {}
        for name, task in tasks.items():
            raw = getattr(task, 'raw_file', None) if task is not None else None
            if raw is not None and Path(raw).is_file() and getattr(task, 'retcode', 0) == 0:
                results[name] = Path(raw)
            else:
                log.error('Simulation %s failed', name)
                results[name] = None
        return results

    def run(self, job: SimJob) -> Path | None:
        """Run a single job and return its raw file."""
        return self.run_batch([job])[job.name]

    def cleanup(self) -> None:
        """Delete the files generated by the simulation runner."""
        self.runner.file_cleanup()


#? -------------------------------------------------------------------------------
#? functional helpers                                                             
def generate_all_combinations(**value_lists: Iterable[Value]) -> list[list[tuple[str, Value]]]:
    """``R1=['1k','2k'], C1=['1u']`` -> ``[[('R1','1k'),('C1','1u')], [('R1','2k'),('C1','1u')]]``."""
    names = list(value_lists)
    return [list(zip(names, combo)) for combo in itertools.product(*value_lists.values())]


#? -------------------------------------------------------------------------------
def single_sim(circuit, output_dir, component_list: Iterable[tuple[str, Value]], **kwargs) -> Path | None:
    """Run one simulation with modified component values."""
    sim = Simulator(circuit, output_dir, **kwargs)
    return sim.run(SimJob('single', values=dict(component_list)))


#? -------------------------------------------------------------------------------
def values_sweep_sim(circuit, output_dir, parallel: int = 4, **value_lists) -> dict[str, Path | None]:
    """Simulate every combination of the given component value lists."""
    sim = Simulator(circuit, output_dir, parallel=parallel)
    jobs = [SimJob(f'sweep_{i:04d}', values=dict(combo))
            for i, combo in enumerate(generate_all_combinations(**value_lists))]
    return sim.run_batch(jobs)


#? -------------------------------------------------------------------------------
def param_sweep_sim(circuit, output_dir, parallel: int = 4, **param_lists) -> dict[str, Path | None]:
    """Simulate every combination of ``.param`` values."""
    sim = Simulator(circuit, output_dir, parallel=parallel)
    jobs = [SimJob(f'param_{i:04d}', params=dict(combo))
            for i, combo in enumerate(generate_all_combinations(**param_lists))]
    return sim.run_batch(jobs)


#? -------------------------------------------------------------------------------
def model_sweep_sim(circuit, output_dir, parallel: int = 4, **model_lists) -> dict[str, Path | None]:
    """Simulate every combination of component models/references (e.g. ``D1=['1N4148','1N914']``)."""
    sim = Simulator(circuit, output_dir, parallel=parallel)
    jobs = [SimJob(f'model_{i:04d}', models=dict(combo))
            for i, combo in enumerate(generate_all_combinations(**model_lists))]
    return sim.run_batch(jobs)

#? -------------------------------------------------------------------------------
