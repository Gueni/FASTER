#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?                         _________   _____________________
#?                        / ____/   | / ___/_  __/ ____/ __ \
#?                       / /_  / /| | \__ \ / / / __/ / /_/ /
#?                      / __/ / ___ |___/ // / / /___/ _, _/
#?                     /_/   /_/  |_/____//_/ /_____/_/ |_|
#?
#? Name:        main.py
#? Purpose:     Entry point of FASTER: desktop GUI, or command line analysis.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/01/2024
#? Updated:     07/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------

"""Usage examples::

    python main.py                          # desktop GUI
    python main.py tests/Test.asc           # command line analysis
    python main.py circuit.asc --config my.json --mc-runs 200 --keep-sims
    python main.py circuit.asc --no-sim     # FMEDA + FTA only, no LTspice needed
    python main.py --gui circuit.asc        # GUI with a circuit already open
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

WORKER_FLAG = '--gui-worker'        # internal: analysis process started by the GUI


#? -------------------------------------------------------------------------------
def parse_args(argv=None) -> argparse.Namespace:
    from Lib.core import config as cfg
    p = argparse.ArgumentParser(description='FASTER - reliability analysis of LTspice circuits')
    p.add_argument('schematic', nargs='?', help='LTspice .asc file (no file: start the GUI)')
    p.add_argument('-c', '--config', default=None, help=f'JSON config (default: {cfg.DEFAULT_CONFIG.name})')
    p.add_argument('-o', '--output', default=None, help=f'output root folder (default: {cfg.DATA_DIR})')
    p.add_argument('--name', default=None, help='circuit name for the run folder and outputs (default: file name)')
    p.add_argument('--image', default=None, help='circuit image for the report (default: exported from the schematic)')
    p.add_argument('--mc-runs', type=int, default=None, help='override Monte Carlo run count')
    p.add_argument('--no-sim', action='store_true', help='skip all LTspice simulations')
    p.add_argument('--no-wca', action='store_true', help='skip worst-case analysis')
    p.add_argument('--no-mc', action='store_true', help='skip Monte Carlo analysis')
    p.add_argument('--keep-sims', action='store_true', help='keep LTspice netlists/raw files')
    p.add_argument('--open', action='store_true', help='open the report in the browser when done')
    p.add_argument('--no-tables', action='store_true', help='do not print result tables in the terminal (log.log still has them)')
    p.add_argument('--gui', action='store_true', help='start the desktop GUI (optionally with the given schematic)')
    p.add_argument(WORKER_FLAG, action='store_true', help='internal: plain output with progress markers for the GUI')
    p.add_argument('-v', '--verbose', action='store_true')
    return p.parse_args(argv)


#? -------------------------------------------------------------------------------
def run_worker(args) -> int:
    """Analysis process driven by the GUI: plain log lines plus ``@@`` markers on stdout."""
    from Lib.core import config as cfg
    from Lib.pipeline import run_pipeline

    def emit(line: str) -> None:
        print(line, flush=True)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, stream=sys.stdout,
                        format='%(asctime)s %(levelname)-7s %(message)s', datefmt='%H:%M:%S', force=True)
    for noisy in ('PyLTSpice', 'spicelib'):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    try:
        result = run_pipeline(args.schematic, cfg.load_config(args.config), output_root=args.output,
                              simulate=not args.no_sim, run_wca=False if args.no_wca else None,
                              run_mc=False if args.no_mc else None, mc_runs=args.mc_runs, image=args.image,
                              keep_sims=args.keep_sims, terminal_tables=False, name=args.name,
                              progress=lambda pct, step: emit(f'@@PROGRESS {pct:.1f} {step}'))
    except Exception as exc:
        logging.getLogger('FASTER').exception('Analysis failed')
        emit(f'@@ERROR {exc}')
        return 1
    emit(f'@@RESULT {result.run_dir}')
    return 2 if result.errors else 0


#? -------------------------------------------------------------------------------
def run_cli(args) -> int:
    from rich.console import Console
    from rich.logging import RichHandler
    from rich.table import Table

    from Lib.core import config as cfg
    from Lib.core.banner import banner
    from Lib.pipeline import run_pipeline

    console = Console(highlight=False)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format='%(message)s',
                        datefmt='%H:%M:%S',
                        handlers=[RichHandler(console=console, show_path=False, markup=False,
                                              rich_tracebacks=True, log_time_format='%H:%M:%S')])
    for noisy in ('PyLTSpice', 'spicelib'):
        logging.getLogger(noisy).setLevel(logging.INFO if args.verbose else logging.WARNING)
    console.print(banner(), style='bold cyan')

    result = run_pipeline(args.schematic, cfg.load_config(args.config), output_root=args.output,
                          simulate=not args.no_sim, run_wca=False if args.no_wca else None,
                          run_mc=False if args.no_mc else None, mc_runs=args.mc_runs,
                          image=args.image, keep_sims=args.keep_sims, terminal_tables=not args.no_tables,
                          name=args.name)

    table = Table(title='Outputs', caption=str(result.run_dir), title_justify='left',
                  caption_justify='left', header_style='bold')
    table.add_column('Output', style='bold')
    table.add_column('File', overflow='fold')
    for name, path in result.outputs.items():
        table.add_row(name, Path(path).name)
    for step, err in result.errors.items():
        table.add_row(f'[red]FAILED {step}[/red]', err)
    console.print(table)
    if args.open and 'report' in result.outputs:
        import webbrowser
        webbrowser.open(Path(result.outputs['report']).as_uri())
    return 2 if result.errors else 0


#? -------------------------------------------------------------------------------
def main(argv=None) -> int:
    args = parse_args(argv)
    if getattr(args, WORKER_FLAG.lstrip('-').replace('-', '_')):
        return run_worker(args)
    if args.gui or not args.schematic:
        from Lib.gui.app import run_gui
        return run_gui(args.schematic)
    return run_cli(args)


if __name__ == '__main__':
    sys.exit(main())

#? -------------------------------------------------------------------------------
