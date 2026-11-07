# -*- mode: python ; coding: utf-8 -*-
#? -------------------------------------------------------------------------------
#?                         _________   _____________________
#?                        / ____/   | / ___/_  __/ ____/ __ \
#?                       / /_  / /| | \__ \ / / / __/ / /_/ /
#?                      / __/ / ___ |___/ // / / /___/ _, _/
#?                     /_/   /_/  |_/____//_/ /_____/_/ |_|
#?
#? Name:        faster.spec
#? Purpose:     PyInstaller build: FASTER.exe (GUI) and faster-cli.exe (console) in one folder.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     07/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------

# Build with:  python packaging/build.py      (or: pyinstaller packaging/faster.spec)
# The folder build (onedir) starts fast and is what the installer ships.

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

ROOT  = Path(SPECPATH).parent
BUILD = ROOT / 'build'
ICON  = BUILD / 'faster.ico'
VINFO = BUILD / 'version_info.txt'

datas = [(str(ROOT / 'config.json'), '.'),                  # default analysis settings
         (str(ROOT / 'tests' / 'Test.asc'), 'examples')]    # copied to <data folder>/examples
datas += collect_data_files('pyfiglet')                     # figlet fonts (banner in log.log)
datas += collect_data_files('plotly', includes=['package_data/**/*'])
for dist in ('PyLTSpice', 'spicelib', 'numpy', 'pandas', 'plotly', 'openpyxl', 'pillow', 'pyfiglet',
             'rich', 'PySide6-Essentials', 'pyqtgraph'):
    try:
        datas += copy_metadata(dist)                        # versions shown in Settings / log.log
    except Exception:
        pass

def _no_scripts(name: str) -> bool:
    return '.scripts' not in name and '.editor_gui' not in name

hiddenimports = (collect_submodules('Lib') + collect_submodules('PyLTSpice', filter=_no_scripts)
                 + collect_submodules('spicelib', filter=_no_scripts) + ['openpyxl', 'PIL.Image'])

# scipy is only imported lazily by spicelib / pyqtgraph features FASTER does not use
excludes = ['tkinter', '_tkinter', 'matplotlib', 'IPython', 'jupyter', 'notebook', 'pytest',
            'scipy', 'pygame', 'lxml', 'OpenGL', 'pyqtgraph.opengl', 'pyqtgraph.examples',
            'PyQt5', 'PyQt6', 'PySide2', 'PySide6.QtWebEngineCore', 'PySide6.Qt3DCore',
            'PySide6.QtQuick', 'PySide6.QtQml', 'PySide6.QtMultimedia', 'PySide6.QtBluetooth']

a = Analysis([str(ROOT / 'main.py')],
             pathex=[str(ROOT)],
             datas=datas,
             hiddenimports=hiddenimports,
             excludes=excludes,
             noarchive=False,
             optimize=1)

# software OpenGL fallback and Qt translations are not needed by a widgets app
def _keep(entry) -> bool:
    dest = entry[0].replace('\\', '/').lower()
    return not dest.endswith('opengl32sw.dll') and '/translations/' not in dest

a.binaries = [b for b in a.binaries if _keep(b)]
a.datas    = [d for d in a.datas if _keep(d)]
pyz        = PYZ(a.pure)

common = dict(exclude_binaries=True, debug=False, strip=False, upx=False,
              icon=str(ICON) if ICON.is_file() else None,
              version=str(VINFO) if VINFO.is_file() else None)

gui = EXE(pyz, a.scripts, [], name='FASTER', console=False, **common)
cli = EXE(pyz, a.scripts, [], name='faster-cli', console=True, **common)

coll = COLLECT(gui, cli, a.binaries, a.datas, strip=False, upx=False, name='FASTER')
