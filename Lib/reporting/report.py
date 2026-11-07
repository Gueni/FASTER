#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?                           ____                        __
#?                          / __ \___  ____  ____  _____/ /_
#?                         / /_/ / _ \/ __ \/ __ \/ ___/ __/
#?                        / _, _/  __/ /_/ / /_/ / /  / /_
#?                       /_/ |_|\___/ .___/\____/_/   \__/
#?                                 /_/
#?
#? Name:        report.py
#? Purpose:     Generate the interactive HTML report.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/01/2024
#? Updated:     07/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------

"""Self-contained HTML report (Plotly is embedded once, so it works offline)."""

from __future__ import annotations

import base64
import html
import io
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

log = logging.getLogger(__name__)

IMAGE_MAX_WIDTH = 1400

_CSS = """
:root { --fg:#1f2328; --muted:#59636e; --bg:#ffffff; --card:#f6f8fa; --line:#d1d9e0; --accent:#0969da; }
* { box-sizing:border-box; }
body { margin:0; font-family:Segoe UI, Roboto, Helvetica, Arial, sans-serif; color:var(--fg); background:var(--bg); }
header { padding:24px 32px; border-bottom:1px solid var(--line); }
header h1 { margin:0 0 4px; font-size:26px; }
header p { margin:0; color:var(--muted); }
nav { padding:8px 32px; border-bottom:1px solid var(--line); position:sticky; top:0; background:var(--bg); z-index:10; }
nav a { margin-right:16px; color:var(--accent); text-decoration:none; font-size:14px; }
main { padding:16px 32px 48px; max-width:1400px; }
section { margin-top:28px; }
h2 { font-size:20px; border-bottom:1px solid var(--line); padding-bottom:6px; }
.kpis { display:flex; flex-wrap:wrap; gap:12px; }
.kpi { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:10px 16px; min-width:150px; }
.kpi b { display:block; font-size:20px; }
.kpi span { color:var(--muted); font-size:13px; }
table.data { border-collapse:collapse; width:100%; font-size:13px; margin:8px 0; }
table.data th, table.data td { border:1px solid var(--line); padding:5px 8px; text-align:left; vertical-align:top; }
table.data th { background:var(--card); }
table.data td { overflow-wrap:break-word; word-break:normal; }
table.data td.num { white-space:nowrap; }
.pass { color:#1a7f37; font-weight:700; } td.pass { background:#dafbe1; }
.fail { color:#cf222e; font-weight:700; } td.fail { background:#ffebe9; }
.na   { color:var(--muted); }
.circuit { text-align:center; margin-top:16px; } .circuit img { max-width:100%; max-height:80vh; height:auto; border:1px solid var(--line); background:#fff; }
"""


#? -------------------------------------------------------------------------------
def image_to_base64(path: str | os.PathLike, max_width: int = IMAGE_MAX_WIDTH) -> tuple[str, str]:
    """Return ``(mime, base64)``; large images are downscaled in memory."""
    path = Path(path)
    data = path.read_bytes()
    if path.suffix.lower() == '.svg':
        return 'image/svg+xml', base64.b64encode(data).decode('ascii')
    mime = 'image/png' if path.suffix.lower() == '.png' else 'image/jpeg'
    try:
        from PIL import Image
        with Image.open(io.BytesIO(data)) as img:
            if img.width > max_width:
                img = img.resize((max_width, round(img.height * max_width / img.width)), Image.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format='PNG')
                data, mime = buf.getvalue(), 'image/png'
    except ImportError:
        pass
    return mime, base64.b64encode(data).decode('ascii')


#? -------------------------------------------------------------------------------
def _table(df: pd.DataFrame, float_format: str = '{:.4g}') -> str:
    fmt = df.copy()
    for col in fmt.select_dtypes('number').columns:
        fmt[col] = fmt[col].map(lambda v: float_format.format(v) if pd.notna(v) else '')
    table_html = fmt.to_html(index=False, classes='data', border=0, escape=True)
    table_html = re.sub(r'<td>([-+]?\d[\d.,eE+%-]*(?: FIT)?)</td>', r'<td class="num">\1</td>', table_html)
    return _verdicts(table_html)


#? -------------------------------------------------------------------------------
_VERDICT_CLASS = {'PASS': 'pass', 'FAIL': 'fail', 'n/a': 'na'}


#? -------------------------------------------------------------------------------
def _verdict_class(value: str) -> str:
    """CSS class for a PASS / FAIL / n/a verdict, '' otherwise."""
    return _VERDICT_CLASS.get(str(value).strip(), '')


#? -------------------------------------------------------------------------------
def _verdicts(table_html: str) -> str:
    """Colour PASS (green) and FAIL (red) cells of a rendered table."""
    for word, css in _VERDICT_CLASS.items():
        table_html = table_html.replace(f'<td>{word}</td>', f'<td class="{css}">{word}</td>')
    return table_html


#? -------------------------------------------------------------------------------
def _kpis(items: dict[str, str]) -> str:
    return '<div class="kpis">' + ''.join(
        f'<div class="kpi"><b class="{_verdict_class(v)}">{html.escape(str(v))}</b><span>{html.escape(k)}</span></div>'
        for k, v in items.items()
    ) + '</div>'


#? -------------------------------------------------------------------------------
class Report:
    """Collect sections, then :meth:`write` a single HTML file."""

    def __init__(self, title: str = 'LTspice Analysis Report', subtitle: str = ''):
        self.title    = title
        self.subtitle = subtitle
        self.sections: list[tuple[str, str]] = []
        self._plotly_included = False

    def _fig(self, fig: go.Figure) -> str:
        include               = not self._plotly_included      # embed plotly.js only with the first figure
        self._plotly_included = True
        return pio.to_html(fig, full_html=False, include_plotlyjs=include,
                           config={'displaylogo': False, 'responsive': True})

    def add_section(self, title: str, *, text: str = '', kpis: dict | None = None,
                    tables: Iterable[tuple[str, pd.DataFrame]] = (), figures: Iterable[go.Figure] = (),
                    image: str | os.PathLike | None = None) -> None:
        parts = []
        if text:
            parts.append(f'<p>{html.escape(text)}</p>')
        if kpis:
            parts.append(_kpis(kpis))
        if image:
            mime, data = image_to_base64(image)
            parts.append(f'<div class="circuit"><img src="data:{mime};base64,{data}" alt="circuit"></div>')
        for fig in figures:
            parts.append(self._fig(fig))
        for caption, df in tables:
            if caption:
                parts.append(f'<h3>{html.escape(caption)}</h3>')
            parts.append(_table(df))
        self.sections.append((title, '\n'.join(parts)))

    def write(self, path: str | os.PathLike) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        anchors = [(f's{i}', t) for i, (t, _) in enumerate(self.sections)]
        nav     = ''.join(f'<a href="#{a}">{html.escape(t)}</a>' for a, t in anchors)
        body = ''.join(f'<section id="{a}"><h2>{html.escape(t)}</h2>{content}</section>'
                       for (a, t), (_, content) in zip(anchors, self.sections))
        stamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        doc = (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
               f'<meta name="viewport" content="width=device-width, initial-scale=1">'
               f'<title>{html.escape(self.title)}</title><style>{_CSS}</style></head><body>'
               f'<header><h1>{html.escape(self.title)}</h1><p>{html.escape(self.subtitle)} &middot; {stamp}</p></header>'
               f'<nav>{nav}</nav><main>{body}</main></body></html>')
        path.write_text(doc, encoding='utf-8')
        log.info('HTML report written to %s', path)
        return path

#? -------------------------------------------------------------------------------
