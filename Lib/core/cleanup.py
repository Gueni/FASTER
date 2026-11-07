#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?                        ________
#?                       / ____/ /__  ____ _____  __  ______
#?                      / /   / / _ \/ __ `/ __ \/ / / / __ \
#?                     / /___/ /  __/ /_/ / / / / /_/ / /_/ /
#?                     \____/_/\___/\__,_/_/ /_/\__,_/ .___/
#?                                                  /_/
#?
#? Name:        cleanup.py
#? Purpose:     Remove temporary simulation files.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/01/2024
#? Updated:     07/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------

"""Safe cleanup helpers (they only touch the folder you pass in)."""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Iterable

log = logging.getLogger(__name__)

SIM_EXTENSIONS = ('.asc', '.net', '.log', '.raw', '.op.raw', '.fail', '.meas')


#? -------------------------------------------------------------------------------
def delete_files_in_folder(folder: str | os.PathLike, extensions: Iterable[str] | None = None) -> int:
    """Delete files (optionally only those with ``extensions``) directly inside ``folder``."""
    folder = Path(folder)
    if not folder.is_dir():
        log.warning('Not a directory: %s', folder)
        return 0
    exts  = tuple(e.lower() for e in extensions) if extensions else None
    count = 0
    for path in folder.iterdir():
        if path.is_file() and (exts is None or path.name.lower().endswith(exts)):
            path.unlink()
            count += 1
    return count


#? -------------------------------------------------------------------------------
def remove_sim_dir(folder: str | os.PathLike) -> None:
    """Remove a simulation work folder entirely."""
    shutil.rmtree(folder, ignore_errors=True)


#? -------------------------------------------------------------------------------
def clear_all(folders: Iterable[str | os.PathLike]) -> None:
    for folder in folders:
        n = delete_files_in_folder(folder)
        log.info('Deleted %d files from %s', n, folder)

#? -------------------------------------------------------------------------------
