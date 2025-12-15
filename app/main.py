from PySide6 import QtWidgets, QtGui, QtCore
import sys
import os
import subprocess
from pathlib import Path
import threading
import logging
import webbrowser
import argparse

from app.services.betterfox import BetterfoxService, Settings, AppPaths

APP_NAME = "BetterfoxUpdater"
APP_VERSION = "4.2.0"


def resource_path(rel: str) -> Path:
    """Gestisce i path delle risorse in dev e in eseguibile frozen."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent
    return base / rel


def build_paths() -> AppPaths:
    home = Path(os.getenv("LOCALAPPDATA" if sys.platform.startswith("win") else "HOME", "."))
    base = home / APP_NAME
    base.mkdir(parents=True, exist_ok=True)
    return AppPaths(
        base=base,
        config=base / "config.ini",
        log_file=base / "error.log",
        resources=resource_path("resources"),
    )


def setup_logger(paths: AppPaths) -> logging.Logger:
    logger = logging.getLogger(APP_NAME)
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(paths.log_file, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(fh)
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
    logger.addHandler(ch)
    return logger


class MainWindow(QtWidgets.QMainWindow):
    class Signals(QtCore.QObject):
        log = QtCore.Signal(str)
        status = QtCore.Signal(str)
        stats = QtCore.Signal(str, str, str, str)
        busy = QtCore.Signal(bool)
        progress = QtCore.Signal(int, int)

    def __init__(self, svc: BetterfoxService, settings: Settings, paths: AppPaths):
        super().__init__()
        self.svc = svc
        self.settings = settings
        self.paths = paths
        self.accent = "#3cd0a7"
        self.sig = self.Signals()
        self.sig.log.connect(self._append_log)
        self.sig.status.connect(self._set_status)
        self.sig.stats.connect(self._update_stats)
        self.sig.busy.connect(self._set_busy)
        self.sig.progress.connect(self._set_progress)
        self.setWindowTitle(f"Betterfox Updater v{APP_VERSION}")
        self.resize(760, 520)
        self.setMinimumSize(700, 460)
        self.tray = None
        self.theme_action = None
        self._apply_stylesheet()
        self._build_ui()
        self._load_settings()
        self._bind_settings()
        self._load_profiles()
        self._build_tray()

    def _build_ui(self):
        cw = QtWidgets.QWidget()
        self.setCentralWidget(cw)
        layout = QtWidgets.QVBoxLayout(cw)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        style = self.style()

        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Betterfox Updater")
        title.setStyleSheet("font-size:18px; font-weight:700;")
        subtitle = QtWidgets.QLabel("Aggiorna Betterfox in modo sicuro e leggero.")
        subtitle.setStyleSheet("color:#9aa5b5;")
        header_text = QtWidgets.QVBoxLayout()
        header_text.addWidget(title)
        header_text.addWidget(subtitle)
        header.addLayout(header_text)
        header.addStretch()
        self.status = QtWidgets.QLabel("Pronto")
        self.status.setObjectName("statusChip")
        header.addWidget(self.status)
        layout.addLayout(header)

        tabs = QtWidgets.QTabWidget()

        base_tab = QtWidgets.QWidget()
        base_layout = QtWidgets.QVBoxLayout(base_tab)
        base_layout.setSpacing(12)

        versions_box = QtWidgets.QGroupBox("Versioni e stato")
        versions_grid = QtWidgets.QGridLayout(versions_box)
        versions_grid.setVerticalSpacing(6)
        self.local_lbl = QtWidgets.QLabel("n/d")
        self.remote_lbl = QtWidgets.QLabel("n/d")
        self.github_lbl = QtWidgets.QLabel("n/d")
        self.fx_lbl = QtWidgets.QLabel("n/d")
        for lbl in (self.local_lbl, self.remote_lbl, self.github_lbl, self.fx_lbl):
            lbl.setObjectName("pill")
        versions_grid.addWidget(QtWidgets.QLabel("Locale"), 0, 0)
        versions_grid.addWidget(QtWidgets.QLabel("Remoto"), 0, 1)
        versions_grid.addWidget(QtWidgets.QLabel("GitHub"), 0, 2)
        versions_grid.addWidget(QtWidgets.QLabel("Firefox"), 0, 3)
        versions_grid.addWidget(self.local_lbl, 1, 0)
        versions_grid.addWidget(self.remote_lbl, 1, 1)
        versions_grid.addWidget(self.github_lbl, 1, 2)
        versions_grid.addWidget(self.fx_lbl, 1, 3)
        base_layout.addWidget(versions_box)

        body = QtWidgets.QHBoxLayout()
        body.setSpacing(12)

        left_col = QtWidgets.QVBoxLayout()
        left_col.setSpacing(10)

        actions_box = QtWidgets.QGroupBox("Azioni rapide")
        actions_layout = QtWidgets.QGridLayout(actions_box)
        actions_layout.setHorizontalSpacing(10)
        actions_layout.setVerticalSpacing(8)
        self.check_btn = QtWidgets.QPushButton("Controlla versioni")
        self.check_btn.setIcon(style.standardIcon(QtWidgets.QStyle.SP_BrowserReload))
        self.update_btn = QtWidgets.QPushButton("Aggiorna Betterfox")
        self.update_btn.setProperty("class", "primary")
        self.update_btn.setIcon(style.standardIcon(QtWidgets.QStyle.SP_ArrowDown))
        self.backup_btn = QtWidgets.QPushButton("Backup profilo")
        self.backup_btn.setIcon(style.standardIcon(QtWidgets.QStyle.SP_DriveHDIcon))
        self.check_btn.clicked.connect(self.check_versions)
        self.update_btn.clicked.connect(self.run_update)
        self.backup_btn.clicked.connect(self.run_backup)
        actions_layout.addWidget(self.check_btn, 0, 0)
        actions_layout.addWidget(self.update_btn, 0, 1)
        actions_layout.addWidget(self.backup_btn, 1, 0, 1, 2)
        left_col.addWidget(actions_box)

        paths_box = QtWidgets.QGroupBox("Percorsi")
        form = QtWidgets.QFormLayout(paths_box)
        form.setLabelAlignment(QtCore.Qt.AlignLeft)
        form.setFormAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        form.setHorizontalSpacing(10)
        self.profile_edit = QtWidgets.QLineEdit()
        profile_row = QtWidgets.QHBoxLayout()
        browse_btn = QtWidgets.QPushButton("Sfoglia")
        browse_btn.setIcon(style.standardIcon(QtWidgets.QStyle.SP_DirOpenIcon))
        browse_btn.clicked.connect(self.choose_profile)
        profile_row.addWidget(self.profile_edit, 1)
        profile_row.addWidget(browse_btn)
        profile_row.setSpacing(6)
        profile_wrap = QtWidgets.QWidget()
        profile_wrap.setLayout(profile_row)
        form.addRow("Profilo Firefox", profile_wrap)

        self.profile_combo = QtWidgets.QComboBox()
        self.profile_combo.currentTextChanged.connect(self._on_profile_selected)
        reload_btn = QtWidgets.QPushButton("Rileva")
        reload_btn.setIcon(style.standardIcon(QtWidgets.QStyle.SP_BrowserReload))
        reload_btn.clicked.connect(self._load_profiles)
        combo_row = QtWidgets.QHBoxLayout()
        combo_row.addWidget(self.profile_combo, 1)
        combo_row.addWidget(reload_btn)
        combo_wrap = QtWidgets.QWidget()
        combo_wrap.setLayout(combo_row)
        form.addRow("Profili trovati", combo_wrap)

        self.backup_edit = QtWidgets.QLineEdit()
        backup_btn = QtWidgets.QPushButton("Scegli")
        backup_btn.setIcon(style.standardIcon(QtWidgets.QStyle.SP_DialogOpenButton))
        backup_btn.clicked.connect(self.choose_backup)
        backup_row = QtWidgets.QHBoxLayout()
        backup_row.addWidget(self.backup_edit, 1)
        backup_row.addWidget(backup_btn)
        backup_wrap = QtWidgets.QWidget()
        backup_wrap.setLayout(backup_row)
        form.addRow("Cartella backup", backup_wrap)

        self.retention_spin = QtWidgets.QSpinBox()
        self.retention_spin.setRange(7, 120)
        form.addRow("Retention (giorni)", self.retention_spin)
        left_col.addWidget(paths_box)

        prefs_box = QtWidgets.QGroupBox("Preferenze")
        prefs_layout = QtWidgets.QHBoxLayout(prefs_box)
        prefs_layout.setSpacing(10)
        self.compress_chk = QtWidgets.QCheckBox("Comprimi backup")
        self.auto_backup_chk = QtWidgets.QCheckBox("Backup prima di aggiornare")
        self.auto_restart_chk = QtWidgets.QCheckBox("Riavvia Firefox dopo update")
        self.theme_toggle = QtWidgets.QComboBox()
        self.theme_toggle.addItems(["System", "Light", "Dark"])
        self.theme_toggle.setCurrentText(self.settings.get("theme", "System").capitalize())
        self.theme_toggle.currentTextChanged.connect(self._on_theme_change)
        prefs_layout.addWidget(self.compress_chk)
        prefs_layout.addWidget(self.auto_backup_chk)
        prefs_layout.addWidget(self.auto_restart_chk)
        prefs_layout.addStretch()
        prefs_layout.addWidget(QtWidgets.QLabel("Tema"))
        prefs_layout.addWidget(self.theme_toggle)
        left_col.addWidget(prefs_box)

        left_col.addStretch()

        right_col = QtWidgets.QVBoxLayout()
        right_col.setSpacing(10)

        log_box = QtWidgets.QGroupBox("Log")
        log_layout = QtWidgets.QVBoxLayout(log_box)
        self.log_text = QtWidgets.QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText("Log di esecuzione...")
        self.log_text.setFixedHeight(200)
        log_layout.addWidget(self.log_text)
        util_box = QtWidgets.QHBoxLayout()
        open_log_btn = QtWidgets.QPushButton("Apri log")
        open_log_btn.setIcon(style.standardIcon(QtWidgets.QStyle.SP_FileIcon))
        open_log_btn.clicked.connect(lambda: self._open_path(self.paths.log_file))
        open_backup_btn = QtWidgets.QPushButton("Cartella backup")
        open_backup_btn.setIcon(style.standardIcon(QtWidgets.QStyle.SP_DirIcon))
        open_backup_btn.clicked.connect(self._open_backup_dir)
        clear_log_btn = QtWidgets.QPushButton("Pulisci log")
        clear_log_btn.setIcon(style.standardIcon(QtWidgets.QStyle.SP_DialogResetButton))
        clear_log_btn.clicked.connect(self.log_text.clear)
        about_btn = QtWidgets.QPushButton("About")
        about_btn.setIcon(style.standardIcon(QtWidgets.QStyle.SP_MessageBoxInformation))
        about_btn.clicked.connect(self._show_about)
        util_box.addWidget(open_log_btn)
        util_box.addWidget(open_backup_btn)
        util_box.addWidget(clear_log_btn)
        util_box.addWidget(about_btn)
        util_box.addStretch()
        log_layout.addLayout(util_box)
        right_col.addWidget(log_box)

        progress_row = QtWidgets.QHBoxLayout()
        self.progress = QtWidgets.QProgressBar()
        self.progress.setMinimum(0)
        self.progress.setMaximum(1)
        self.progress.setValue(0)
        progress_row.addWidget(self.progress, 1)
        right_col.addLayout(progress_row)

        body.addLayout(left_col, 3)
        body.addLayout(right_col, 2)
        base_layout.addLayout(body)
        self._set_status("Pronto")

        adv_tab = QtWidgets.QWidget()
        adv_layout = QtWidgets.QVBoxLayout(adv_tab)
        adv_layout.setSpacing(10)

        network_box = QtWidgets.QGroupBox("Rete e download")
        net_layout = QtWidgets.QGridLayout(network_box)
        net_layout.setVerticalSpacing(8)
        self.proxy_edit = QtWidgets.QLineEdit()
        self.proxy_edit.setPlaceholderText("http://user:pass@host:port")
        net_layout.addWidget(QtWidgets.QLabel("Proxy"), 0, 0)
        net_layout.addWidget(self.proxy_edit, 0, 1)
        self.timeout_spin = QtWidgets.QSpinBox()
        self.timeout_spin.setRange(5, 90)
        net_layout.addWidget(QtWidgets.QLabel("Timeout (s)"), 1, 0)
        net_layout.addWidget(self.timeout_spin, 1, 1)
        self.retries_spin = QtWidgets.QSpinBox()
        self.retries_spin.setRange(1, 8)
        net_layout.addWidget(QtWidgets.QLabel("Tentativi"), 2, 0)
        net_layout.addWidget(self.retries_spin, 2, 1)
        self.apply_net_btn = QtWidgets.QPushButton("Applica rete")
        self.apply_net_btn.setProperty("class", "primary")
        self.apply_net_btn.setIcon(style.standardIcon(QtWidgets.QStyle.SP_DialogApplyButton))
        self.apply_net_btn.clicked.connect(self.apply_network_settings)
        self.test_net_btn = QtWidgets.QPushButton("Test download")
        self.test_net_btn.setIcon(style.standardIcon(QtWidgets.QStyle.SP_BrowserReload))
        self.test_net_btn.clicked.connect(self.test_network)
        net_layout.addWidget(self.apply_net_btn, 3, 0)
        net_layout.addWidget(self.test_net_btn, 3, 1)
        adv_layout.addWidget(network_box)
        self.network_box = network_box

        adv_util_box = QtWidgets.QHBoxLayout()
        open_cfg_btn = QtWidgets.QPushButton("Apri config")
        open_cfg_btn.setIcon(style.standardIcon(QtWidgets.QStyle.SP_FileDialogStart))
        open_cfg_btn.clicked.connect(lambda: self._open_path(self.paths.config))
        open_data_btn = QtWidgets.QPushButton("Cartella dati app")
        open_data_btn.setIcon(style.standardIcon(QtWidgets.QStyle.SP_DirHomeIcon))
        open_data_btn.clicked.connect(lambda: self._open_path(self.paths.base))
        release_btn = QtWidgets.QPushButton("Cartella release")
        release_btn.setIcon(style.standardIcon(QtWidgets.QStyle.SP_DirOpenIcon))
        release_btn.clicked.connect(lambda: self._open_path(Path(__file__).resolve().parent.parent / "release_app"))
        open_profile_btn = QtWidgets.QPushButton("Apri profilo")
        open_profile_btn.setIcon(style.standardIcon(QtWidgets.QStyle.SP_DirIcon))
        open_profile_btn.clicked.connect(self._open_profile_dir)
        open_userjs_btn = QtWidgets.QPushButton("Apri user.js")
        open_userjs_btn.setIcon(style.standardIcon(QtWidgets.QStyle.SP_FileIcon))
        open_userjs_btn.clicked.connect(self._open_userjs)
        repo_btn = QtWidgets.QPushButton("Betterfox GitHub")
        repo_btn.clicked.connect(lambda: webbrowser.open("https://github.com/yokoffing/Betterfox"))
        changelog_btn = QtWidgets.QPushButton("Changelog locale")
        changelog_btn.clicked.connect(lambda: self._open_path(Path("CHANGELOG.md").resolve()))
        adv_util_box.addWidget(open_cfg_btn)
        adv_util_box.addWidget(open_data_btn)
        adv_util_box.addWidget(release_btn)
        adv_util_box.addWidget(open_profile_btn)
        adv_util_box.addWidget(open_userjs_btn)
        adv_util_box.addWidget(repo_btn)
        adv_util_box.addWidget(changelog_btn)
        adv_util_box.addStretch()
        adv_layout.addLayout(adv_util_box)

        tabs.addTab(base_tab, "Base")
        tabs.addTab(adv_tab, "Avanzate")
        layout.addWidget(tabs)

    def _apply_stylesheet(self):
        self.setStyleSheet(
            f"""
            QWidget {{
                background-color: #0b0d10;
                color: #f4f7fb;
                font-family: "Segoe UI", "Inter", sans-serif;
                font-size: 13px;
            }}
            QGroupBox {{
                border: 1px solid #181e29;
                border-radius: 12px;
                margin-top: 10px;
                padding-top: 14px;
                background-color: #0f131b;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
                color: #6ee0c2;
                font-weight: 600;
                letter-spacing: 0.2px;
            }}
            QPushButton {{
                padding: 9px 12px;
                border-radius: 10px;
                border: 1px solid #1a202b;
                background-color: #0f131b;
                color: #f4f7fb;
            }}
            QPushButton:hover {{
                border-color: rgba(60,208,167,0.5);
                background-color: rgba(60,208,167,0.12);
            }}
            QPushButton[class="primary"] {{
                background-color: {self.accent};
                color: #0a120f;
                border: none;
                font-weight: 700;
            }}
            QPushButton[class="primary"]:hover {{
                background-color: #58e4c8;
            }}
            QLineEdit, QComboBox, QSpinBox, QPlainTextEdit {{
                padding: 7px 9px;
                border-radius: 10px;
                border: 1px solid #181e29;
                background-color: #0d1118;
                selection-background-color: {self.accent};
                selection-color: #0b0d10;
            }}
            QPlainTextEdit {{
                min-height: 140px;
                line-height: 1.3em;
            }}
            QTabWidget::pane {{
                border: 1px solid #181e29;
                border-radius: 10px;
                top: -1px;
                background: #0d1118;
            }}
            QTabBar::tab {{
                padding: 8px 12px;
                border: 1px solid #181e29;
                border-bottom: none;
                background: #0d1118;
                margin-right: 4px;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
            }}
            QTabBar::tab:selected {{
                background: #111826;
                color: #f4f7fb;
                border-color: #222c3b;
            }}
            QTabBar::tab:!selected {{
                color: #94a1b0;
            }}
            #statusChip {{
                padding: 6px 12px;
                border-radius: 10px;
                background-color: rgba(60,208,167,0.16);
                color: #f4f7fb;
                font-weight: 700;
            }}
            #pill {{
                padding: 6px 10px;
                border-radius: 8px;
                background-color: #0f1923;
                border: 1px solid #1b2736;
                font-weight: 600;
            }}
            QProgressBar {{
                border: 1px solid #181e29;
                border-radius: 8px;
                background: #0f131b;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {self.accent};
                border-radius: 8px;
            }}
            """
        )

    def _apply_palette(self, mode: str):
        """Applica palette chiara/scura o sistema."""
        mode = mode.lower()
        if mode == "system":
            QtWidgets.QApplication.instance().setStyle("Fusion")
            QtWidgets.QApplication.instance().setPalette(QtWidgets.QApplication.style().standardPalette())
            return
        dark = mode == "dark"
        palette = QtGui.QPalette()
        if dark:
            palette.setColor(QtGui.QPalette.Window, QtGui.QColor(45, 45, 48))
            palette.setColor(QtGui.QPalette.WindowText, QtCore.Qt.white)
            palette.setColor(QtGui.QPalette.Base, QtGui.QColor(30, 30, 30))
            palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(45, 45, 48))
            palette.setColor(QtGui.QPalette.ToolTipBase, QtCore.Qt.white)
            palette.setColor(QtGui.QPalette.ToolTipText, QtCore.Qt.white)
            palette.setColor(QtGui.QPalette.Text, QtCore.Qt.white)
            palette.setColor(QtGui.QPalette.Button, QtGui.QColor(45, 45, 48))
            palette.setColor(QtGui.QPalette.ButtonText, QtCore.Qt.white)
            palette.setColor(QtGui.QPalette.BrightText, QtCore.Qt.red)
            palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(38, 79, 120))
            palette.setColor(QtGui.QPalette.HighlightedText, QtCore.Qt.white)
        else:
            palette = QtWidgets.QApplication.style().standardPalette()
        QtWidgets.QApplication.instance().setPalette(palette)

    def _load_settings(self):
        self.profile_edit.setText(self.settings.get("profile_path", ""))
        self.backup_edit.setText(self.settings.get("backup_folder", ""))
        try:
            self.retention_spin.setValue(int(self.settings.get("retention_days", "60") or "60"))
        except Exception:
            self.retention_spin.setValue(60)
        self.compress_chk.setChecked(self.settings.get("compress_backup", "yes") == "yes")
        self.auto_backup_chk.setChecked(self.settings.get("auto_backup", "yes") == "yes")
        self.auto_restart_chk.setChecked(self.settings.get("auto_restart", "yes") == "yes")
        self.proxy_edit.setText(self.settings.get("Network", "proxy", ""))
        try:
            self.timeout_spin.setValue(int(self.settings.get("Network", "timeout", "12") or "12"))
            self.retries_spin.setValue(int(self.settings.get("Network", "retries", "3") or "3"))
        except Exception:
            self.timeout_spin.setValue(12)
            self.retries_spin.setValue(3)
        if not self.backup_edit.text():
            self.backup_edit.setText(str(self.paths.base / "backups"))
        # fallback sicuro per retention
        try:
            self.retention_spin.setValue(int(self.settings.get("retention_days", "60") or "60"))
        except Exception:
            self.retention_spin.setValue(60)

    def _bind_settings(self):
        self.profile_edit.editingFinished.connect(lambda: self.settings.set("profile_path", self.profile_edit.text()))
        self.backup_edit.editingFinished.connect(lambda: self.settings.set("backup_folder", self.backup_edit.text()))
        self.retention_spin.valueChanged.connect(lambda val: self.settings.set("retention_days", str(val)))
        self.compress_chk.toggled.connect(lambda v: self.settings.set("compress_backup", "yes" if v else "no"))
        self.auto_backup_chk.toggled.connect(lambda v: self.settings.set("auto_backup", "yes" if v else "no"))
        self.auto_restart_chk.toggled.connect(lambda v: self.settings.set("auto_restart", "yes" if v else "no"))
        self.proxy_edit.editingFinished.connect(lambda: self.settings.set("Network", "proxy", self.proxy_edit.text()))
        self.timeout_spin.valueChanged.connect(lambda val: self.settings.set("Network", "timeout", str(val)))
        self.retries_spin.valueChanged.connect(lambda val: self.settings.set("Network", "retries", str(val)))

    def _load_profiles(self):
        profiles = [str(p) for p in self.svc.discover_profiles()]
        self.profile_combo.clear()
        self.profile_combo.addItems(profiles)
        if profiles and not self.profile_edit.text():
            self.profile_edit.setText(profiles[0])
        self.sig.log.emit("Profili rilevati: " + (", ".join(profiles) if profiles else "nessuno"))

    def _on_profile_selected(self, text: str):
        if text:
            self.profile_edit.setText(text)
            self.settings.set("profile_path", text)

    @QtCore.Slot(str)
    def _append_log(self, msg: str):
        self.log_text.appendPlainText(msg)
        if self.tray and msg.startswith("[err]"):
            self.tray.showMessage(APP_NAME, msg, QtWidgets.QSystemTrayIcon.Critical, 3000)
        elif self.tray and msg.startswith("[ok]"):
            self.tray.showMessage(APP_NAME, msg, QtWidgets.QSystemTrayIcon.Information, 2000)

    @QtCore.Slot(str)
    def _set_status(self, msg: str):
        self.status.setText(msg)
        lower = msg.lower()
        if "errore" in lower or "[err" in lower:
            self.status.setStyleSheet("background-color: rgba(200,70,70,0.25); color: white;")
        elif "ok" in lower or "aggiornato" in lower:
            self.status.setStyleSheet("background-color: rgba(60,180,90,0.3); color: white;")
        elif "warn" in lower or "!" in lower:
            self.status.setStyleSheet("background-color: rgba(220,170,70,0.25); color: white;")
        else:
            self.status.setStyleSheet("background-color: rgba(79,140,245,0.12); color: white;")

    def _on_theme_change(self, text: str):
        val = text.lower()
        self._apply_palette(val if val in ("light", "dark") else "system")
        self.settings.set("theme", text.lower())
        self.sig.status.emit(f"Tema: {text}")

    def _build_tray(self):
        icon_path = self.paths.resources / "betterfox.ico"
        if not icon_path.exists():
            return
        icon = QtGui.QIcon(str(icon_path))
        tray = QtWidgets.QSystemTrayIcon(icon, self)
        tray.setToolTip(f"{APP_NAME} v{APP_VERSION}")
        menu = QtWidgets.QMenu()
        show_act = menu.addAction("Mostra")
        show_act.triggered.connect(self.showNormal)
        quit_act = menu.addAction("Esci")
        quit_act.triggered.connect(QtWidgets.QApplication.instance().quit)
        tray.setContextMenu(menu)
        tray.show()
        self.tray = tray

    def choose_profile(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Seleziona profilo Firefox", self.profile_edit.text() or str(Path.home()))
        if d:
            self.profile_edit.setText(d)
            self.settings.set("profile_path", d)

    def choose_backup(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Seleziona cartella backup", self.backup_edit.text() or str(Path.home()))
        if d:
            self.backup_edit.setText(d)
            self.settings.set("backup_folder", d)

    def _open_backup_dir(self):
        dest = self.backup_edit.text()
        if dest:
            self._open_path(Path(dest))

    def _open_profile_dir(self):
        prof = self.profile_edit.text()
        if prof:
            self._open_path(Path(prof))

    def _open_userjs(self):
        prof = Path(self.profile_edit.text())
        target = prof / "user.js"
        self._open_path(target)

    def _open_path(self, path: Path):
        if not path.exists():
            self.sig.log.emit(f"[err] Risorsa non trovata: {path}")
            return
        if path.is_dir() or path.suffix:
            if sys.platform.startswith("win"):
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])

    def _show_about(self):
        text = (
            f"<b>Betterfox Updater</b> v{APP_VERSION}<br>"
            "Aggiorna user.js Betterfox con backup e controlli versioni.<br><br>"
            "<a href='https://github.com/alesilveri/BetterfoxUpdater'>Repository</a>"
        )
        QtWidgets.QMessageBox.about(self, "About", text)
    def apply_network_settings(self):
        proxy = self.proxy_edit.text().strip()
        timeout = self.timeout_spin.value()
        retries = self.retries_spin.value()
        self.settings.set("Network", "proxy", proxy)
        self.settings.set("Network", "timeout", str(timeout))
        self.settings.set("Network", "retries", str(retries))
        self.svc.update_network(proxy, timeout, retries)
        self.sig.log.emit("[ok] Impostazioni rete applicate")
        self.sig.status.emit("Rete aggiornata")

    def test_network(self):
        self._set_busy(True)
        threading.Thread(target=self._do_test_network, daemon=True).start()

    def _do_test_network(self):
        rv, _ = self.svc.get_remote()
        if rv:
            self.sig.log.emit(f"[ok] Test rete ok, versione remota {rv}")
            self.sig.status.emit("Rete ok")
        else:
            self.sig.log.emit("[err] Test rete fallito")
            self.sig.status.emit("Errore rete")
        self.sig.busy.emit(False)

    @QtCore.Slot(bool)
    def _set_busy(self, busy: bool):
        for btn in (self.check_btn, self.update_btn, self.backup_btn, self.apply_net_btn, self.test_net_btn):
            btn.setEnabled(not busy)
        if busy:
            self.progress.setMaximum(0)
        else:
            self.progress.setMaximum(1)
            self.progress.setValue(0)

    @QtCore.Slot(int, int)
    def _set_progress(self, step: int, total: int):
        if total > 0:
            if self.progress.maximum() != total:
                self.progress.setMaximum(total)
                self.progress.setValue(0)
            self.progress.setValue(self.progress.value() + step)

    def check_versions(self):
        prof = Path(self.profile_edit.text())
        if not prof.exists():
            QtWidgets.QMessageBox.critical(self, APP_NAME, "Profilo non valido")
            return
        self._set_busy(True)
        threading.Thread(target=self._do_check, args=(prof,), daemon=True).start()

    def _do_check(self, prof: Path):
        lv = self.svc.get_local_version(prof)
        rv, _ = self.svc.get_remote()
        gh = self.svc.get_last_commit()
        fx = self.svc.get_firefox_version(prof)
        self.sig.stats.emit(lv or "n/d", rv or "n/d", gh, fx)
        self.sig.status.emit("Pronto")
        self.sig.busy.emit(False)

    @QtCore.Slot(str, str, str, str)
    def _update_stats(self, lv: str, rv: str, gh: str, fx: str):
        self.local_lbl.setText(lv)
        self.remote_lbl.setText(rv)
        self.github_lbl.setText(gh)
        self.fx_lbl.setText(fx)
        self.status.setText("Pronto")

    def run_backup(self):
        prof = Path(self.profile_edit.text())
        dest = Path(self.backup_edit.text()) if self.backup_edit.text() else None
        if not prof.exists() or dest is None:
            QtWidgets.QMessageBox.warning(self, APP_NAME, "Profilo o cartella backup non validi")
            return
        self._set_busy(True)
        threading.Thread(target=self._do_backup, args=(prof, dest), daemon=True).start()

    def _do_backup(self, prof: Path, dest: Path):
        try:
            self.svc.close_firefox()
            self.svc.backup_profile(prof, dest, self.compress_chk.isChecked(), self.retention_spin.value(), self.sig.log.emit)
            self.sig.status.emit("Backup completato")
        except Exception as exc:
            self.sig.log.emit(f"[err] Backup: {exc}")
            self.sig.status.emit("Errore backup")
        self.sig.busy.emit(False)

    def run_update(self):
        prof = Path(self.profile_edit.text())
        dest = Path(self.backup_edit.text()) if self.backup_edit.text() else None
        if not prof.exists():
            QtWidgets.QMessageBox.warning(self, APP_NAME, "Profilo non valido")
            return
        self._set_busy(True)
        threading.Thread(target=self._do_update, args=(prof, dest), daemon=True).start()

    def _do_update(self, prof: Path, dest: Path):
        try:
            lv = self.svc.get_local_version(prof)
            rv, content = self.svc.fetch_userjs_with_progress(lambda step, total: self.sig.progress.emit(step, total))
            if not content:
                self.sig.log.emit("[err] Impossibile scaricare user.js")
                self.sig.status.emit("Errore rete")
                self.sig.busy.emit(False)
                return
            if not self.svc.needs_update(lv, rv):
                self.sig.log.emit("Nessun aggiornamento necessario")
                self.sig.status.emit("Gia' aggiornato")
                self.sig.busy.emit(False)
                return
            if self.auto_backup_chk.isChecked() and dest:
                self.svc.backup_profile(prof, dest, self.compress_chk.isChecked(), self.retention_spin.value(), self.sig.log.emit)
            elif self.auto_backup_chk.isChecked():
                self.sig.log.emit("[!] Backup saltato: cartella non configurata")
            self.svc.close_firefox()
            (prof / "user.js").write_text(content, "utf-8")
            self.sig.log.emit(f"[ok] Betterfox aggiornato a {rv}")
            if self.settings.get("auto_restart", "yes") == "yes":
                self.svc.launch_firefox()
            self.sig.status.emit("Aggiornato")
        except Exception as exc:
            self.sig.log.emit(f"[err] Update: {exc}")
            self.sig.status.emit("Errore update")
        self.sig.busy.emit(False)


def main():
    parser = argparse.ArgumentParser(description="Betterfox Updater")
    parser.add_argument("--update", action="store_true", help="Esegui update headless")
    parser.add_argument("--profile", help="Percorso profilo Firefox")
    parser.add_argument("--backup", help="Cartella backup")
    parser.add_argument("--no-backup", action="store_true", help="Salta backup")
    parser.add_argument("--no-restart", action="store_true", help="Non riavviare Firefox dopo update")
    args, unknown = parser.parse_known_args()

    paths = build_paths()
    logger = setup_logger(paths)
    settings = Settings(paths)
    svc = BetterfoxService(paths, logger, settings=settings)

    if args.update:
        prof = Path(args.profile or settings.get("profile_path", ""))
        bk = Path(args.backup) if args.backup else (Path(settings.get("backup_folder", "")) if settings.get("backup_folder") else None)
        if not prof.exists():
            print("Profilo non valido")
            sys.exit(2)
        lv = svc.get_local_version(prof)
        rv, content = svc.fetch_userjs_with_progress(lambda step, total: None)
        if not content:
            print("Errore download")
            sys.exit(1)
        if not svc.needs_update(lv, rv):
            print("Gia' aggiornato")
            sys.exit(0)
        if not args.no_backup and bk:
            svc.close_firefox()
            try:
                retention = int(settings.get("retention_days", "60") or "60")
            except Exception:
                retention = 60
            svc.backup_profile(prof, bk, True, retention, print)
        svc.close_firefox()
        (prof / "user.js").write_text(content, "utf-8")
        print(f"Aggiornato a {rv}")
        if not args.no_restart and settings.get("auto_restart", "yes") == "yes":
            svc.launch_firefox()
        sys.exit(0)

    app = QtWidgets.QApplication(sys.argv)
    QtWidgets.QApplication.instance().setStyle("Fusion")
    win = MainWindow(svc, settings, paths)
    win._apply_palette(settings.get("theme", "system"))
    if (paths.resources / "betterfox.ico").exists():
        app.setWindowIcon(QtGui.QIcon(str(paths.resources / "betterfox.ico")))
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
