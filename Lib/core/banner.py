#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?                          ____
#?                         / __ )____ _____  ____  ___  _____
#?                        / __  / __ `/ __ \/ __ \/ _ \/ ___/
#?                       / /_/ / /_/ / / / / / / /  __/ /
#?                      /_____/\__,_/_/ /_/_/ /_/\___/_/
#?
#? Name:        banner.py
#? Purpose:     Print the start-up banner.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/01/2024
#? Updated:     07/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------

from __future__ import annotations


#? -------------------------------------------------------------------------------
def banner(text: str = 'FASTER', font: str = 'slant') -> str:
    """Render ``text`` with pyfiglet if available, plain text otherwise."""
    try:
        from pyfiglet import Figlet
        return Figlet(font=font).renderText(text)
    except Exception:
        return f'\n  {text}\n'


#? -------------------------------------------------------------------------------
def print_banner(text: str = 'FASTER') -> None:
    print(banner(text))

#? -------------------------------------------------------------------------------
