#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?                         _________   _____________________
#?                        / ____/   | / ___/_  __/ ____/ __ \
#?                       / /_  / /| | \__ \ / / / __/ / /_/ /
#?                      / __/ / ___ |___/ // / / /___/ _, _/
#?                     /_/   /_/  |_/____//_/ /_____/_/ |_|
#?
#? Name:        __init__.py
#? Purpose:     FASTER package root.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     07/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------

"""FASTER - Failure Analysis, Simulation, Testing and Evaluation Report.

Package layout (one sub-package per functional area, one module per feature):

    core/          config.py      paths, LTspice discovery, config.json loading
                   cleanup.py     temporary file removal
                   banner.py      start-up banner
    knowledge/     components.py  component type identification (symbol / designator)
                   failures.py    failure-mode knowledge base
                   fit_rates.py   FIT-rate knowledge base
    schematic/     asc_parser.py  LTspice .asc parser
                   symbols.py     LTspice .asy symbol library loader
                   renderer.py    schematic -> SVG image export
    simulation/    runner.py      LTspice runner: single run, value / param / model sweeps
                   waveforms.py   .raw reading, trace alignment, plots
    analysis/      fmeda.py       Failure Modes, Effects and Diagnostic Analysis
                   iso26262.py    ISO 26262-5 hardware metrics (SPFM, LFM, PMHF)
                   fta.py         Fault Tree Analysis
                   wca.py         Worst-Case Analysis
                   montecarlo.py  Monte Carlo tolerance analysis
    reporting/     report.py      HTML report
                   runlog.py      per-run log.log (banner, messages, rich tables)
    pipeline.py    full analysis flow
"""

__version__ = '2.1.0'

#? -------------------------------------------------------------------------------
