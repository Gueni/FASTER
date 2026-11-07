#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?                              ____
#?                             /  _/________  ____  _____
#?                             / // ___/ __ \/ __ \/ ___/
#?                           _/ // /__/ /_/ / / / (__  )
#?                          /___/\___/\____/_/ /_/____/
#?
#? Name:        icons.py
#? Purpose:     Crisp, theme-coloured line icons rendered from inline SVG (no image files needed).
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     07/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------

"""Vector icons (24x24 stroke paths in the Lucide design language, ISC licence)."""

from __future__ import annotations

import hashlib
import tempfile
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

PATHS: dict[str, str] = {
    'circuit'     : '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M11 9h4a2 2 0 0 0 2-2V3"/><circle cx="9" cy="9" r="2"/><path d="M7 21v-4a2 2 0 0 1 2-2h4"/><circle cx="15" cy="15" r="2"/>',
    'flask'       : '<path d="M10 2v7.5a2 2 0 0 1-.2.9L4.7 20.5a1 1 0 0 0 .9 1.5h12.8a1 1 0 0 0 .9-1.5l-5.1-10.1A2 2 0 0 1 14 9.5V2"/><path d="M8.5 2h7M7 16h10"/>',
    'chart'       : '<path d="M3 3v18h18"/><path d="M18 17V9M13 17V5M8 17v-3"/>',
    'activity'    : '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    'book'        : '<path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/>',
    'history'     : '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5M12 7v5l4 2"/>',
    'settings'    : '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6"/>',
    'info'        : '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
    'alert'       : '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3z"/><path d="M12 9v4M12 17h.01"/>',
    'shield'      : '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
    'thermometer' : '<path d="M14 4v10.54a4 4 0 1 1-4 0V4a2 2 0 0 1 4 0z"/>',
    'target'      : '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    'dice'        : '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M8 8h.01M16 8h.01M12 12h.01M8 16h.01M16 16h.01"/>',
    'cpu'         : '<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M15 2v2M15 20v2M2 15h2M2 9h2M20 15h2M20 9h2M9 2v2M9 20v2"/>',
    'list'        : '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
    'tag'         : '<path d="M12.6 2.6A2 2 0 0 0 11.2 2H4a2 2 0 0 0-2 2v7.2a2 2 0 0 0 .6 1.4l8.7 8.7a2.4 2.4 0 0 0 3.4 0l6.6-6.6a2.4 2.4 0 0 0 0-3.4z"/><circle cx="7.5" cy="7.5" r=".5"/>',
    'refresh'     : '<path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/>',
    'sun'         : '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>',
    'moon'        : '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9z"/>',
    'menu'        : '<path d="M4 6h16M4 12h16M4 18h16"/>',
    'play'        : '<path d="M6 3l14 9-14 9z"/>',
    'stop'        : '<rect x="6" y="6" width="12" height="12" rx="2"/>',
    'trash'       : '<path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
    'folder'      : '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2z"/>',
    'open'        : '<path d="m6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2"/>',
    'plus'        : '<path d="M12 5v14M5 12h14"/>',
    'minus'       : '<path d="M5 12h14"/>',
    'x'           : '<path d="M18 6 6 18M6 6l12 12"/>',
    'check'       : '<path d="M20 6 9 17l-5-5"/>',
    'copy'        : '<rect x="8" y="8" width="14" height="14" rx="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
    'save'        : '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><path d="M17 21v-8H7v8M7 3v5h8"/>',
    'save-as'     : '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v4"/><path d="M7 3v5h8M7 21v-8h6M18 15v6M15 18h6"/>',
    'undo'        : '<path d="M3 7v6h6"/><path d="M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13"/>',
    'search'      : '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    'file'        : '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/>',
    'report'      : '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M16 13H8M16 17H8M10 9H8"/>',
    'external'    : '<path d="M15 3h6v6M10 14 21 3M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
    'chevron-down': '<path d="m6 9 6 6 6-6"/>',
    'chevron-up'  : '<path d="m18 15-6-6-6 6"/>',
    'panel'       : '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 15h18"/>',
    'image'       : '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.1-3.1a2 2 0 0 0-2.8 0L6 21"/>',
    'zoom-in'     : '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3M11 8v6M8 11h6"/>',
    'zoom-out'    : '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3M8 11h6"/>',
    'fit'         : '<path d="M8 3H5a2 2 0 0 0-2 2v3M21 8V5a2 2 0 0 0-2-2h-3M3 16v3a2 2 0 0 0 2 2h3M16 21h3a2 2 0 0 0 2-2v-3"/>',
    'layers'      : '<path d="m12 2 10 5-10 5L2 7z"/><path d="m2 17 10 5 10-5M2 12l10 5 10-5"/>',
    'clock'       : '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    'zap'         : '<path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/>',
    # window buttons (custom title bar)
    'win-min'     : '<path d="M4 12h16"/>',
    'win-max'     : '<rect x="4" y="4" width="16" height="16" rx="2.5"/>',
    'win-restore' : '<rect x="4" y="8" width="12" height="12" rx="2"/><path d="M8 8V6.5A2.5 2.5 0 0 1 10.5 4h7A2.5 2.5 0 0 1 20 6.5v7a2.5 2.5 0 0 1-2.5 2.5H16"/>',
    'win-close'   : '<path d="M5 5l14 14M19 5 5 19"/>',
}

LOGO_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
            '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
            '<stop offset="0" stop-color="#4c8dff"/><stop offset="1" stop-color="#7c5cff"/></linearGradient></defs>'
            '<rect x="2" y="2" width="60" height="60" rx="16" fill="url(#g)"/>'
            '<path d="M10 38h9l5-16 8 26 6-18 4 8h12" fill="none" stroke="#fff" stroke-width="4.5" '
            'stroke-linecap="round" stroke-linejoin="round"/></svg>')


#? -------------------------------------------------------------------------------
def svg(name: str, color: str, stroke: float = 2.0) -> str:
    body = PATHS.get(name, PATHS['info'])
    fill = color if name in ('play',) else 'none'
    if name.startswith('win-'):
        stroke = 1.6                       # thin glyphs like native caption buttons
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="{fill}" stroke="{color}" '
            f'stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round">{body}</svg>')


#? -------------------------------------------------------------------------------
def _render(svg_text: str, size: int) -> QPixmap:
    app   = QGuiApplication.instance()
    ratio = max(app.devicePixelRatio() if app else 1.0, 2.0)     # oversample: sharp on any screen
    px    = QPixmap(int(size * ratio), int(size * ratio))
    px.fill(Qt.GlobalColor.transparent)
    renderer = QSvgRenderer(QByteArray(svg_text.encode()))
    painter  = QPainter(px)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, px.width(), px.height()))
    painter.end()
    px.setDevicePixelRatio(ratio)
    return px


#? -------------------------------------------------------------------------------
def pixmap(name: str, color: str, size: int = 18) -> QPixmap:
    return _render(svg(name, color), size)


#? -------------------------------------------------------------------------------
@lru_cache(maxsize=512)
def icon(name: str, color: str, active_color: str | None = None, disabled_color: str | None = None) -> QIcon:
    ic = QIcon()
    for size in (16, 20, 24, 32):
        ic.addPixmap(pixmap(name, color, size), QIcon.Mode.Normal, QIcon.State.Off)
        if active_color:
            ic.addPixmap(pixmap(name, active_color, size), QIcon.Mode.Normal, QIcon.State.On)
            ic.addPixmap(pixmap(name, active_color, size), QIcon.Mode.Active, QIcon.State.On)
        if disabled_color:
            ic.addPixmap(pixmap(name, disabled_color, size), QIcon.Mode.Disabled, QIcon.State.Off)
    return ic


#? -------------------------------------------------------------------------------
@lru_cache(maxsize=1)
def app_icon() -> QIcon:
    ic = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        ic.addPixmap(_render(LOGO_SVG, size))
    return ic


#? -------------------------------------------------------------------------------
def svg_file(name: str, color: str) -> str:
    """Write an icon to a cache file so stylesheets can reference it with ``url(...)``."""
    key    = hashlib.md5(f'{name}{color}'.encode()).hexdigest()[:10]
    folder = Path(tempfile.gettempdir()) / 'faster-ui-icons'
    folder.mkdir(parents=True, exist_ok=True)
    path   = folder / f'{name}-{key}.svg'
    if not path.exists():
        path.write_text(svg(name, color, 2.4), encoding='utf-8')
    return path.as_posix()

#? -------------------------------------------------------------------------------
