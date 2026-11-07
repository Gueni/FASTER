#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?                         _____                _
#?                        / ___/___  __________(_)___  ____
#?                        \__ \/ _ \/ ___/ ___/ / __ \/ __ \
#?                       ___/ /  __(__  |__  ) / /_/ / / / /
#?                      /____/\___/____/____/_/\____/_/ /_/
#?
#? Name:        session.py
#? Purpose:     The open circuit shared by all pages: load, edit, save, working copy for analyses.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     07/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------

"""Circuit session.

Edits (component values, attributes, SPICE directives) are applied to an
in-memory :class:`AscDocument`; the schematic, tables and analyses always see
the edited text. Saving writes the original file; analysing unsaved edits uses
a temporary working copy next to the original (so relative includes and local
symbols still resolve) under the original circuit name.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from ..core.paths import is_writable, work_dir
from ..schematic.asc_parser import parse_ltspice_file
from ..schematic.asc_writer import AscDocument
from ..schematic.renderer import Rendering, render
from ..simulation.runner import parse_value


#? -------------------------------------------------------------------------------
def numeric(value: str | None) -> float | None:
    try:
        return parse_value(value) if value else None
    except ValueError:
        return None


#? -------------------------------------------------------------------------------
class CircuitSession(QObject):
    loaded           = Signal(str)       # path
    changed          = Signal()          # content edited (values / directives)
    modified_changed = Signal(bool)
    closed           = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.doc: AscDocument | None = None
        self._saved_text = ''
        self._circuit: dict | None = None

    #? state                                                                            
    @property
    def is_open(self) -> bool:
        return self.doc is not None

    @property
    def path(self) -> Path | None:
        return self.doc.path if self.doc else None

    @property
    def name(self) -> str:
        return self.doc.path.stem if self.doc else ''

    @property
    def modified(self) -> bool:
        return self.doc is not None and self.doc.text != self._saved_text

    @property
    def circuit(self) -> dict:
        if self.doc is None:
            return {'components': [], 'wires': [], 'flags': {}, 'connections': {}, 'directives': []}
        if self._circuit is None:
            self._circuit = parse_ltspice_file(self.doc.path, self.doc.text)
        return self._circuit

    def components(self) -> list[dict]:
        return self.circuit['components']

    def rendering(self, colors: dict[str, str]) -> Rendering:
        return render(self.doc.path, self.doc.text, colors)

    #? file operations                                                                  
    def open(self, path: str | Path) -> None:
        self.doc         = AscDocument.load(path)
        self._saved_text = self.doc.text
        self._circuit    = None
        self.loaded.emit(str(self.doc.path))
        self.modified_changed.emit(False)

    def close(self) -> None:
        self.doc, self._circuit, self._saved_text = None, None, ''
        self.closed.emit()
        self.modified_changed.emit(False)

    def save(self, path: str | Path | None = None) -> Path:
        target = self.doc.save(path)
        if path is not None:
            self.doc.path = Path(target)
        self._saved_text = self.doc.text
        self.modified_changed.emit(False)
        if path is not None:
            self.loaded.emit(str(self.doc.path))
        return target

    def revert(self) -> None:
        if self.doc is not None:
            self.open(self.doc.path)

    def _edited(self) -> None:
        self._circuit = None
        self.changed.emit()
        self.modified_changed.emit(self.modified)

    #? edits                                                                            
    def set_value(self, name: str, value: str) -> bool:
        ok = self.doc.set_value(name, value.strip())
        if ok:
            self._edited()
        return ok

    def set_attribute(self, name: str, attr: str, value: str) -> bool:
        ok = self.doc.set_attribute(name, attr, value.strip())
        if ok:
            self._edited()
        return ok

    def directives(self) -> list[tuple[int, str]]:
        return self.doc.directives() if self.doc else []

    def set_directive(self, line_index: int, text: str) -> None:
        self.doc.set_directive(line_index, text)
        self._edited()

    def add_directive(self, text: str) -> None:
        self.doc.add_directive(text)
        self._edited()

    def remove_directive(self, line_index: int) -> None:
        self.doc.remove_line(line_index)
        self._edited()

    #? analyses                                                                         
    def analysis_input(self) -> tuple[Path, str, list[Path]]:
        """``(schematic to analyse, circuit name, files to delete afterwards)``."""
        if not self.modified:
            return self.doc.path, self.name, []
        folder = self.doc.path.parent
        if not is_writable(folder):     # e.g. an example under Program Files
            folder = work_dir()
        work = folder / f'~{self.name}.faster.asc'
        self.doc.save(work)             # saving to another path keeps doc.path on the original
        return work, self.name, [work]

#? -------------------------------------------------------------------------------
