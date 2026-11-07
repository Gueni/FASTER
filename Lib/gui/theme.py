# Purpose:     Light and dark themes built from a small set of colour tokens (shared design with Flash).
"""Theme manager: palette tokens, Qt stylesheet, schematic and plot colours."""

from __future__ import annotations

import sys
from dataclasses import dataclass

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

from . import icons


#? -------------------------------------------------------------------------------
@dataclass(frozen=True)
class Palette:
    name         : str
    bg           : str
    surface      : str
    surface2     : str
    hover        : str
    border       : str
    text         : str
    muted        : str
    accent       : str
    accent_hover : str
    accent_text  : str
    accent_soft  : str
    danger       : str
    danger_soft  : str
    warning      : str
    warning_soft : str
    success      : str
    success_soft : str
    console_bg   : str
    console_text : str
    selection    : str
    sheet        : str          # schematic background
    wire         : str
    symbol       : str


DARK = Palette(
    name='dark', bg='#0e1116', surface='#161a21', surface2='#1d222b', hover='#242a35', border='#2a303c',
    text='#e7e9ee', muted='#8d95a8', accent='#4c8dff', accent_hover='#6aa1ff', accent_text='#ffffff',
    accent_soft='#1d2c47', danger='#f05252', danger_soft='#3a1c20', warning='#f5a524', warning_soft='#3a2c14',
    success='#2fbf71', success_soft='#163626', console_bg='#0a0c10', console_text='#cdd3de', selection='#2b4a80',
    sheet='#0f131a', wire='#6aa1ff', symbol='#d9dde6',
)

LIGHT = Palette(
    name='light', bg='#f3f5f8', surface='#ffffff', surface2='#f6f7f9', hover='#eceff4', border='#dde2ea',
    text='#171b22', muted='#5f6878', accent='#2563eb', accent_hover='#1d4fd8', accent_text='#ffffff',
    accent_soft='#e3ecff', danger='#dc2626', danger_soft='#fde8e8', warning='#b45309', warning_soft='#fdf1e1',
    success='#15803d', success_soft='#dcf5e6', console_bg='#fbfcfd', console_text='#232833', selection='#c7d9ff',
    sheet='#ffffff', wire='#1e3a8a', symbol='#202020',
)


#? -------------------------------------------------------------------------------
def _mono_family() -> str:
    families = set(QFontDatabase.families())
    for fam in ('Cascadia Mono', 'JetBrains Mono', 'Consolas', 'SF Mono', 'Menlo', 'DejaVu Sans Mono',
                'Ubuntu Mono', 'Liberation Mono'):
        if fam in families:
            return fam
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()


#? -------------------------------------------------------------------------------
def _ui_family() -> str:
    families   = set(QFontDatabase.families())
    candidates = ['Segoe UI Variable Text', 'Segoe UI'] if sys.platform == 'win32' else \
                 ['Inter', 'Cantarell', 'Ubuntu', 'Noto Sans', 'DejaVu Sans']
    for fam in candidates:
        if fam in families:
            return fam
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family()


#? -------------------------------------------------------------------------------
def schematic_colors(p: Palette) -> dict[str, str]:
    """Renderer colours (Lib.schematic.renderer.COLORS keys) for a palette."""
    return {'background': p.sheet, 'wire': p.wire, 'symbol': p.symbol, 'text': p.text,
            'directive': p.text, 'comment': p.accent, 'flag': p.symbol, 'missing': p.danger}


#? -------------------------------------------------------------------------------
def build_qss(p: Palette, mono: str) -> str:
    chevron = icons.svg_file('chevron-down', p.muted)
    check   = icons.svg_file('check', p.accent_text)
    up      = icons.svg_file('chevron-up', p.muted)
    return f"""
* {{ outline: none; }}
QWidget {{ color: {p.text}; font-size: 10pt; }}
QMainWindow, #Root {{ background: {p.bg}; }}
QToolTip {{ background: {p.surface2}; color: {p.text}; border: 1px solid {p.border}; padding: 6px 8px; border-radius: 6px; }}

/* ---------- custom title bar ---------- */
#TitleBar {{ background: {p.surface}; border-bottom: 1px solid {p.border}; }}
#TitleText {{ font-weight: 700; font-size: 10pt; }}
#TitleText:disabled, #TitleSub:disabled {{ color: {p.muted}; }}
#TitleSub {{ color: {p.muted}; font-size: 9pt; }}
QToolButton#WinButton, QToolButton#WinClose {{ background: transparent; border: none; border-radius: 0; padding: 0; }}
QToolButton#WinButton:hover {{ background: {p.hover}; }}
QToolButton#WinButton:pressed {{ background: {p.border}; }}
QToolButton#WinClose:hover {{ background: #e81123; }}
QToolButton#WinClose:pressed {{ background: #f1707a; }}
#Root[framed="true"] {{ border: 1px solid {p.border}; }}

/* ---------- sidebar ---------- */
#Sidebar {{ background: {p.surface}; border-right: 1px solid {p.border}; }}
#NavButton {{
    text-align: left; border: none; border-radius: 10px; padding: 9px 12px; margin: 1px 0;
    color: {p.muted}; background: transparent; font-weight: 600;
}}
#NavButton:hover {{ background: {p.hover}; color: {p.text}; }}
#NavButton:checked {{ background: {p.accent_soft}; color: {p.accent}; }}
#SidebarFooter {{ color: {p.muted}; font-size: 8pt; }}

/* ---------- top bar ---------- */
#TopBar {{ background: {p.surface}; border-bottom: 1px solid {p.border}; }}
#PageTitle {{ font-size: 17pt; font-weight: 700; }}
#PageSubtitle {{ color: {p.muted}; }}
#FieldLabel {{ color: {p.muted}; font-size: 8.5pt; font-weight: 600; }}
#Hint {{ color: {p.muted}; font-size: 9pt; }}
#Chip {{ background: {p.surface2}; border: 1px solid {p.border}; border-radius: 12px; padding: 4px 12px; font-weight: 600; }}
#Chip[modified="true"] {{ background: {p.warning_soft}; color: {p.warning}; border-color: {p.warning_soft}; }}
#Pill {{ border-radius: 11px; padding: 3px 10px; font-weight: 600; font-size: 9pt; }}
#Pill[state="idle"] {{ background: {p.surface2}; color: {p.muted}; border: 1px solid {p.border}; }}
#Pill[state="ok"] {{ background: {p.accent_soft}; color: {p.accent}; border: 1px solid {p.accent_soft}; }}
#Pill[state="busy"] {{ background: {p.accent}; color: {p.accent_text}; border: 1px solid {p.accent}; }}
#Pill[state="error"] {{ background: {p.danger_soft}; color: {p.danger}; border: 1px solid {p.danger_soft}; }}
#Pill[state="pass"] {{ background: {p.success_soft}; color: {p.success}; border: 1px solid {p.success_soft}; }}
#Pill[state="fail"] {{ background: {p.danger_soft}; color: {p.danger}; border: 1px solid {p.danger_soft}; }}

/* ---------- cards / KPIs ---------- */
QScrollArea, #PageBody {{ background: transparent; border: none; }}
#Card {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: 14px; }}
#CardTitle {{ font-size: 11.5pt; font-weight: 700; }}
#CardSubtitle {{ color: {p.muted}; font-size: 9pt; }}
#Kpi {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: 12px; }}
#Kpi[state="pass"] {{ background: {p.success_soft}; border-color: {p.success}; }}
#Kpi[state="fail"] {{ background: {p.danger_soft}; border-color: {p.danger}; }}
#KpiValue {{ font-size: 18pt; font-weight: 700; }}
#Kpi[state="pass"] #KpiValue {{ color: {p.success}; }}
#Kpi[state="fail"] #KpiValue {{ color: {p.danger}; }}
#KpiLabel {{ color: {p.muted}; font-size: 8.5pt; font-weight: 600; }}
#KpiSub {{ color: {p.muted}; font-size: 8.5pt; }}
#Empty {{ color: {p.muted}; font-size: 11pt; }}
#DropZone {{ border: 2px dashed {p.border}; border-radius: 16px; background: {p.surface}; }}
#DropZone[active="true"] {{ border-color: {p.accent}; background: {p.accent_soft}; }}
#BigTitle {{ font-size: 20pt; font-weight: 700; }}

/* ---------- inputs ---------- */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit#Input {{
    background: {p.surface2}; border: 1px solid {p.border}; border-radius: 8px;
    padding: 6px 10px; min-height: 22px; selection-background-color: {p.selection};
}}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {{ border-color: {p.muted}; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border: 1px solid {p.accent}; }}
QLineEdit[invalid="true"] {{ border: 1px solid {p.danger}; background: {p.danger_soft}; }}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{ color: {p.muted}; background: {p.bg}; }}
QLineEdit#Mono {{ font-family: "{mono}"; }}
QComboBox {{ padding-right: 28px; }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox::down-arrow {{ image: url({chevron}); width: 14px; height: 14px; }}
QComboBox QAbstractItemView {{
    background: {p.surface}; border: 1px solid {p.border}; border-radius: 8px; padding: 4px;
    selection-background-color: {p.accent_soft}; selection-color: {p.text}; outline: none;
}}
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    width: 18px; border: none; background: transparent; }}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{ image: url({up}); width: 10px; height: 10px; }}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{ image: url({chevron}); width: 10px; height: 10px; }}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator, QTableView::indicator, QListView::indicator {{
    width: 18px; height: 18px; border-radius: 5px; border: 1px solid {p.border}; background: {p.surface2}; }}
QCheckBox::indicator:hover, QListView::indicator:hover {{ border-color: {p.accent}; }}
QCheckBox::indicator:checked, QTableView::indicator:checked, QListView::indicator:checked {{
    background: {p.accent}; border-color: {p.accent}; image: url({check}); }}
QCheckBox:disabled {{ color: {p.muted}; }}

/* ---------- buttons ---------- */
QPushButton, QToolButton#Button {{
    background: {p.surface2}; border: 1px solid {p.border}; border-radius: 8px;
    padding: 7px 14px; font-weight: 600; min-height: 20px;
}}
QPushButton:hover, QToolButton#Button:hover {{ background: {p.hover}; border-color: {p.muted}; }}
QPushButton:pressed {{ background: {p.border}; }}
QPushButton:disabled {{ color: {p.muted}; background: {p.bg}; border-color: {p.border}; }}
QPushButton[kind="primary"] {{ background: {p.accent}; color: {p.accent_text}; border: 1px solid {p.accent}; }}
QPushButton[kind="primary"]:hover {{ background: {p.accent_hover}; border-color: {p.accent_hover}; }}
QPushButton[kind="primary"]:disabled {{ background: {p.accent_soft}; color: {p.muted}; border-color: {p.accent_soft}; }}
QPushButton[kind="danger"] {{ background: {p.danger_soft}; color: {p.danger}; border: 1px solid {p.danger_soft}; }}
QPushButton[kind="danger"]:hover {{ background: {p.danger}; color: #ffffff; border-color: {p.danger}; }}
QPushButton[kind="ghost"], QToolButton#Ghost {{ background: transparent; border: 1px solid transparent; }}
QPushButton[kind="ghost"]:hover, QToolButton#Ghost:hover {{ background: {p.hover}; border-color: {p.border}; }}
QPushButton[size="big"] {{ padding: 11px 22px; font-size: 11pt; border-radius: 10px; }}
QToolButton#Ghost {{ border-radius: 8px; padding: 6px; }}
QToolButton#Ghost:checked {{ background: {p.accent_soft}; }}
QToolButton#Overlay {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: 8px; padding: 6px; }}
QToolButton#Overlay:hover {{ background: {p.hover}; }}

/* ---------- tables / lists / tabs ---------- */
QTableView, QTableWidget, QListWidget, QTreeWidget {{
    background: {p.surface}; alternate-background-color: {p.surface2}; border: 1px solid {p.border};
    border-radius: 10px; gridline-color: transparent; selection-background-color: {p.accent_soft};
    selection-color: {p.text};
}}
QTableView::item {{ padding: 4px 8px; border: none; }}
QListWidget::item {{ padding: 6px 8px; border-radius: 6px; }}
QListWidget::item:hover {{ background: {p.hover}; }}
QListWidget::item:selected {{ background: {p.accent_soft}; color: {p.text}; }}
QHeaderView::section {{
    background: {p.surface2}; color: {p.muted}; border: none; border-bottom: 1px solid {p.border};
    padding: 8px; font-weight: 700; font-size: 9pt;
}}
QTableCornerButton::section {{ background: {p.surface2}; border: none; }}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{
    background: transparent; color: {p.muted}; padding: 8px 14px; margin-right: 4px; border-radius: 8px; font-weight: 600;
}}
QTabBar::tab:hover {{ background: {p.hover}; color: {p.text}; }}
QTabBar::tab:selected {{ background: {p.accent_soft}; color: {p.accent}; }}

/* ---------- schematic / plots ---------- */
#Viewer {{ background: {p.sheet}; border: 1px solid {p.border}; border-radius: 12px; }}

/* ---------- console ---------- */
#ConsolePanel {{ background: {p.surface}; border-top: 1px solid {p.border}; }}
#ConsoleTitle {{ font-weight: 700; }}
QPlainTextEdit#Console {{
    background: {p.console_bg}; color: {p.console_text}; border: 1px solid {p.border}; border-radius: 10px;
    padding: 8px; font-family: "{mono}"; font-size: 9.5pt; selection-background-color: {p.selection};
}}
QProgressBar {{ background: {p.surface2}; border: none; border-radius: 4px; height: 8px; text-align: center; color: transparent; }}
QProgressBar::chunk {{ background: {p.accent}; border-radius: 4px; }}
QSplitter::handle {{ background: {p.border}; }}
QSplitter::handle:hover {{ background: {p.accent}; }}
QSplitter::handle:vertical {{ height: 3px; }}
QSplitter::handle:horizontal {{ width: 3px; }}

/* ---------- scrollbars ---------- */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle {{ background: {p.border}; border-radius: 4px; min-height: 30px; min-width: 30px; }}
QScrollBar::handle:hover {{ background: {p.muted}; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ background: none; border: none; width: 0; height: 0; }}

QStatusBar {{ background: {p.surface}; border-top: 1px solid {p.border}; color: {p.muted}; }}
QStatusBar::item {{ border: none; }}
QMenu {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: 8px; padding: 4px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: {p.accent_soft}; }}
QDialog, QMessageBox {{ background: {p.bg}; }}

#Toast {{ border-radius: 10px; padding: 10px 16px; font-weight: 600; }}
#Toast[kind="info"] {{ background: {p.surface2}; color: {p.text}; border: 1px solid {p.border}; }}
#Toast[kind="success"] {{ background: {p.success}; color: #ffffff; }}
#Toast[kind="error"] {{ background: {p.danger}; color: #ffffff; }}
#Toast[kind="warning"] {{ background: {p.warning}; color: #ffffff; }}
"""


#? -------------------------------------------------------------------------------
class ThemeManager(QObject):
    """Applies the active palette to the whole application and notifies widgets."""

    changed = Signal(object)        # Palette
    MODES   = ('system', 'light', 'dark')

    def __init__(self) -> None:
        super().__init__()
        self.mode    = 'system'
        self.palette = DARK
        self.mono    = 'monospace'
        hints        = QGuiApplication.styleHints()
        if hasattr(hints, 'colorSchemeChanged'):
            hints.colorSchemeChanged.connect(lambda *_: self.mode == 'system' and self.apply())

    def _system_is_dark(self) -> bool:
        hints = QGuiApplication.styleHints()
        if hasattr(hints, 'colorScheme'):
            scheme = hints.colorScheme()
            if scheme == Qt.ColorScheme.Dark:
                return True
            if scheme == Qt.ColorScheme.Light:
                return False
        return QGuiApplication.palette().window().color().lightness() < 128

    def set_mode(self, mode: str) -> None:
        self.mode = mode if mode in self.MODES else 'system'
        self.apply()

    def toggle(self) -> None:
        self.set_mode('light' if self.palette.name == 'dark' else 'dark')

    def apply(self) -> None:
        app = QApplication.instance()
        p   = DARK if self.mode == 'dark' or (self.mode == 'system' and self._system_is_dark()) else LIGHT
        self.palette = p
        self.mono    = _mono_family()
        app.setStyle('Fusion')
        font = QFont(_ui_family())
        font.setPointSizeF(10)
        app.setFont(font)
        qp = QPalette()
        for role, color in (
            (QPalette.ColorRole.Window, p.bg), (QPalette.ColorRole.WindowText, p.text),
            (QPalette.ColorRole.Base, p.surface2), (QPalette.ColorRole.AlternateBase, p.surface),
            (QPalette.ColorRole.Text, p.text), (QPalette.ColorRole.Button, p.surface2),
            (QPalette.ColorRole.ButtonText, p.text), (QPalette.ColorRole.Highlight, p.accent),
            (QPalette.ColorRole.HighlightedText, p.accent_text), (QPalette.ColorRole.ToolTipBase, p.surface2),
            (QPalette.ColorRole.ToolTipText, p.text), (QPalette.ColorRole.PlaceholderText, p.muted),
            (QPalette.ColorRole.Link, p.accent),
        ):
            qp.setColor(role, QColor(color))
        qp.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(p.muted))
        qp.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(p.muted))
        app.setPalette(qp)
        app.setStyleSheet(build_qss(p, self.mono))
        self.changed.emit(p)

    def icon(self, name: str, role: str = 'text'):
        p     = self.palette
        color = {'text': p.text, 'muted': p.muted, 'accent': p.accent, 'danger': p.danger,
                 'on-accent': p.accent_text, 'success': p.success, 'warning': p.warning}.get(role, role)
        return icons.icon(name, color, p.accent, p.border)


_theme: ThemeManager | None = None


#? -------------------------------------------------------------------------------
def theme() -> ThemeManager:
    global _theme
    if _theme is None:
        _theme = ThemeManager()
    return _theme
