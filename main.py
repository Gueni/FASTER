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
#? Purpose:     Command line entry point of FASTER.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/01/2024
#? Updated:     07/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------

"""Usage examples::

    python main.py tests/Test.asc
    python main.py                       # opens a file dialog
    python main.py circuit.asc --config my.json --mc-runs 200 --keep-sims
    python main.py circuit.asc --no-sim  # FMEDA + FTA only, no LTspice needed
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from Lib.core import config as cfg
from Lib.core.banner import banner
from Lib.pipeline import run_pipeline


#? -------------------------------------------------------------------------------
def select_file() -> str | None:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        return None
    root = tk.Tk()
    root.withdraw()
    path = filedialog.askopenfilename(title='Select an LTspice schematic',
                                      filetypes=[('LTspice schematic', '*.asc'), ('All files', '*.*')])
    root.destroy()
    return path or None


#? -------------------------------------------------------------------------------
def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description='FASTER - reliability analysis of LTspice circuits')
    p.add_argument('schematic', nargs='?', help='LTspice .asc file (file dialog if omitted)')
    p.add_argument('-c', '--config', default=None, help=f'JSON config (default: {cfg.DEFAULT_CONFIG.name})')
    p.add_argument('-o', '--output', default=None, help=f'output root folder (default: {cfg.DATA_DIR})')
    p.add_argument('--image', default=None, help='circuit image for the report (default: exported from the schematic)')
    p.add_argument('--mc-runs', type=int, default=None, help='override Monte Carlo run count')
    p.add_argument('--no-sim', action='store_true', help='skip all LTspice simulations')
    p.add_argument('--no-wca', action='store_true', help='skip worst-case analysis')
    p.add_argument('--no-mc', action='store_true', help='skip Monte Carlo analysis')
    p.add_argument('--keep-sims', action='store_true', help='keep LTspice netlists/raw files')
    p.add_argument('--open', action='store_true', help='open the report in the browser when done')
    p.add_argument('--no-tables', action='store_true', help='do not print result tables in the terminal (log.log still has them)')
    p.add_argument('-v', '--verbose', action='store_true')
    return p.parse_args(argv)


#? -------------------------------------------------------------------------------
def main(argv=None) -> int:
    args    = parse_args(argv)
    console = Console(highlight=False)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format='%(message)s',
                        datefmt='%H:%M:%S',
                        handlers=[RichHandler(console=console, show_path=False, markup=False,
                                              rich_tracebacks=True, log_time_format='%H:%M:%S')])
    for noisy in ('PyLTSpice', 'spicelib'):
        logging.getLogger(noisy).setLevel(logging.INFO if args.verbose else logging.WARNING)
    console.print(banner(), style='bold cyan')

    schematic = args.schematic or select_file()
    if not schematic:
        console.print('No schematic selected.')
        return 1

    result = run_pipeline(schematic, cfg.load_config(args.config), output_root=args.output,
                          simulate=not args.no_sim, run_wca=False if args.no_wca else None,
                          run_mc=False if args.no_mc else None, mc_runs=args.mc_runs,
                          image=args.image, keep_sims=args.keep_sims, terminal_tables=not args.no_tables)

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


if __name__ == '__main__':
    sys.exit(main())

#? -------------------------------------------------------------------------------
