#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?                                 ____
#?                                /  _/________  ____
#?                                / // ___/ __ \/ __ \
#?                              _/ // /__/ /_/ / / / /
#?                             /___/\___/\____/_/ /_/
#?
#? Name:        make_icon.py
#? Purpose:     Render the FASTER logo to a multi-size Windows .ico for the exe and installer.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     07/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------

"""``python packaging/make_icon.py build/faster.ico``"""

from __future__ import annotations

import os
from io import BytesIO
import sys
from pathlib import Path

ROOT  = Path(__file__).resolve().parents[1]
SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


#? -------------------------------------------------------------------------------
def make_icon(target: Path) -> Path:
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    sys.path.insert(0, str(ROOT))
    from PIL import Image
    from PySide6.QtCore import QBuffer, QIODevice
    from PySide6.QtGui import QGuiApplication

    from Lib.gui.icons import LOGO_SVG, _render

    app    = QGuiApplication.instance() or QGuiApplication(['make_icon'])
    images = []
    for size in SIZES:
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        _render(LOGO_SVG, size).save(buf, 'PNG')
        images.append(Image.open(BytesIO(bytes(buf.data()))).convert('RGBA'))
    target.parent.mkdir(parents=True, exist_ok=True)
    images[-1].save(target, format='ICO', sizes=[(s, s) for s in SIZES], append_images=images[:-1])
    images[-1].save(target.with_suffix('.png'))
    del app
    return target


if __name__ == '__main__':
    print(make_icon(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'build' / 'faster.ico'))

#? -------------------------------------------------------------------------------
