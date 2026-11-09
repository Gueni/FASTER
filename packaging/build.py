#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?                               ____        _ __    __
#?                              / __ )__  __(_) /___/ /
#?                             / __  / / / / / / __  /
#?                            / /_/ / /_/ / / / /_/ /
#?                           /_____/\__,_/_/_/\__,_/
#?
#? Name:        build.py
#? Purpose:     Build FASTER.exe / faster-cli.exe (PyInstaller) and the Windows installer (Inno Setup).
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     07/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------

"""One command release build::

    python packaging/build.py              # icon, exe folder, smoke test, installer
    python packaging/build.py --no-installer
    python packaging/build.py --no-test
    python packaging/build.py --stage C:\Temp\faster-build   # build outside the source tree, then copy to dist/

Results::

    dist/FASTER/                    portable program folder (FASTER.exe, faster-cli.exe)
    dist/installer/FASTER-<version>-setup.exe

Inno Setup 6 is found on PATH, in ``ISCC`` or in its default install folders.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT      = Path(__file__).resolve().parents[1]
PACKAGING = ROOT / 'packaging'
BUILD     = ROOT / 'build'
DIST      = ROOT / 'dist'
APP_DIR   = DIST / 'FASTER'


#? -------------------------------------------------------------------------------
def version() -> str:
    text = (ROOT / 'Lib' / '__init__.py').read_text(encoding='utf-8')
    return re.search(r"__version__\s*=\s*'([^']+)'", text).group(1)


#? -------------------------------------------------------------------------------
def step(text: str) -> None:
    print(f'\n== {text}', flush=True)


#? -------------------------------------------------------------------------------
def run(cmd: list[str], **kw) -> None:
    print('  >', ' '.join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, **kw)


#? -------------------------------------------------------------------------------
def write_version_info(ver: str) -> Path:
    nums = [int(n) for n in re.findall(r'\d+', ver)[:4]]
    nums += [0] * (4 - len(nums))
    tup  = tuple(nums)
    text = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={tup}, prodvers={tup}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'Mohamed Gueni'),
      StringStruct('FileDescription', 'FASTER - reliability analysis of LTspice circuits'),
      StringStruct('FileVersion', '{ver}'),
      StringStruct('InternalName', 'FASTER'),
      StringStruct('LegalCopyright', 'Mohamed Gueni'),
      StringStruct('OriginalFilename', 'FASTER.exe'),
      StringStruct('ProductName', 'FASTER'),
      StringStruct('ProductVersion', '{ver}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
    path = BUILD / 'version_info.txt'
    path.write_text(text, encoding='utf-8')
    return path


#? -------------------------------------------------------------------------------
def find_iscc() -> Path | None:
    candidates = [os.environ.get('ISCC'), shutil.which('ISCC'), shutil.which('iscc'),
                  Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Inno Setup 6' / 'ISCC.exe',
                  Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')) / 'Inno Setup 6' / 'ISCC.exe',
                  Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'Inno Setup 6' / 'ISCC.exe']
    for cand in candidates:
        if cand and Path(cand).is_file():
            return Path(cand)
    return None


#? -------------------------------------------------------------------------------
def smoke_test() -> None:
    """The frozen CLI runs an analysis (no LTspice) into a temporary data folder."""
    cli = APP_DIR / 'faster-cli.exe'
    with tempfile.TemporaryDirectory(prefix='faster-smoke-') as tmp:
        env = dict(os.environ, FASTER_DATA=tmp)
        run([cli, '--help'], env=env, stdout=subprocess.DEVNULL)
        run([cli, ROOT / 'tests' / 'Test.asc', '--no-sim', '--no-tables'], env=env, stdout=subprocess.DEVNULL)
        runs = list((Path(tmp) / 'results').glob('Test_*'))
        if not runs or not list(runs[0].glob('report_*.html')):
            raise SystemExit('Smoke test failed: no report written')
        print(f'  ok: {runs[0].name} ({len(list(runs[0].iterdir()))} files)')
        if any(APP_DIR.rglob('results')):
            raise SystemExit('Smoke test failed: the app wrote into its own folder')


#? -------------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description='Build the FASTER executables and installer')
    ap.add_argument('--no-installer', action='store_true', help='only build dist/FASTER')
    ap.add_argument('--no-test', action='store_true', help='skip the smoke test of the frozen app')
    ap.add_argument('--stage', type=Path, default=None,
                    help='build in this folder (outside the source tree, e.g. when a file watcher or '
                         'antivirus locks files under dist/ or build/), then copy the results to dist/')
    args = ap.parse_args()
    global APP_DIR
    stage    = args.stage.resolve() if args.stage else None
    dist     = stage / 'dist' if stage else DIST
    workpath = stage / 'pyinstaller' if stage else BUILD / 'pyinstaller'
    APP_DIR  = dist / 'FASTER'
    ver  = version()
    t0   = time.monotonic()
    BUILD.mkdir(exist_ok=True)

    step(f'FASTER {ver}: icon and version resource')
    run([sys.executable, PACKAGING / 'make_icon.py', BUILD / 'faster.ico'])
    write_version_info(ver)

    step('PyInstaller')
    run([sys.executable, '-m', 'PyInstaller', PACKAGING / 'faster.spec', '--noconfirm', '--clean',
         '--distpath', dist, '--workpath', workpath], cwd=ROOT)

    if not args.no_test:
        step('Smoke test')
        smoke_test()

    if not args.no_installer:
        step('Inno Setup')
        iscc = find_iscc()
        if iscc is None:
            print('  Inno Setup 6 not found - install it from https://jrsoftware.org/isdl.php '
                  'or set ISCC; skipping the installer.')
        else:
            run([iscc, '/Q', f'/DAppVersion={ver}', f'/DSrcDir={APP_DIR}', f'/O{dist / "installer"}',
                 PACKAGING / 'installer.iss'])
            for exe in (dist / 'installer').glob(f'FASTER-{ver}-setup.exe'):
                print(f'  installer: {exe} ({exe.stat().st_size / 1e6:.1f} MB)')

    if stage:
        step(f'Copy results from {stage} to {DIST}')
        shutil.rmtree(DIST / 'FASTER', ignore_errors=True)
        shutil.copytree(APP_DIR, DIST / 'FASTER', dirs_exist_ok=True)      # leftovers may be locked
        if (dist / 'installer').is_dir():
            (DIST / 'installer').mkdir(parents=True, exist_ok=True)
            for exe in (dist / 'installer').glob('*.exe'):
                shutil.copy2(exe, DIST / 'installer' / exe.name)
                print(f'  {DIST / "installer" / exe.name}')
        APP_DIR = DIST / 'FASTER'

    size = sum(f.stat().st_size for f in APP_DIR.rglob('*') if f.is_file()) / 1e6
    print(f'\nDone in {time.monotonic() - t0:.0f} s - {APP_DIR} ({size:.0f} MB)')
    return 0


if __name__ == '__main__':
    sys.exit(main())

#? -------------------------------------------------------------------------------
