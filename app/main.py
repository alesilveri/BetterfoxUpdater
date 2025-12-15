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
        self.accent = "#5B8CFF"
        self.sig = self.Signals()
        self.sig.log.connect(self._append_log)
        self.sig.status.connect(self._set_status)
        self.sig.stats.connect(self._update_stats)
        self.sig.busy.connect(self._set_busy)
        self.sig.progress.connect(self._set_progress)
        self.setWindowTitle(f"Betterfox Updater v{APP_VERSION}")
        self.resize(960, 640)
        self.tray = None
        self.theme_action = None
        self._apply_stylesheet()
        self._build_ui()
        self._load_settings()
        self._bind_settings()
        self._load_profiles()
        self._build_tray()
        self._toggle_advanced(False)

    def _build_ui(self):
        cw = QtWidgets.QWidget()
        self.setCentralWidget(cw)
        layout = QtWidgets.QVBoxLayout(cw)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Betterfox Updater")
        title.setStyleSheet("font-size:18px; font-weight:600;")
        subtitle = QtWidgets.QLabel("Aggiorna Betterfox con backup e check versioni")
        subtitle.setStyleSheet("color:gray;")
        header_text = QtWidgets.QVBoxLayout()
        header_text.addWidget(title)
        header_text.addWidget(subtitle)
        header.addLayout(header_text)
        header.addStretch()
        layout.addLayout(header)

        hero = QtWidgets.QFrame()
        hero.setObjectName("heroCard")
        hero_layout = QtWidgets.QHBoxLayout(hero)
        hero_title = QtWidgets.QVBoxLayout()
        hero_head = QtWidgets.QLabel("Pronto per l'update")
        hero_head.setStyleSheet("font-size:16px; font-weight:600;")
        hero_body = QtWidgets.QLabel("Backup automatico, download Betterfox in streaming, riavvio Firefox opzionale.")
        hero_body.setWordWrap(True)
        hero_title.addWidget(hero_head)
        hero_title.addWidget(hero_body)
        hero_layout.addLayout(hero_title, 1)
        hero_actions = QtWidgets.QHBoxLayout()
        repo_btn = QtWidgets.QPushButton("Apri Betterfox GitHub")
        repo_btn.clicked.connect(lambda: webbrowser.open("https://github.com/yokoffing/Betterfox"))
        changelog_btn = QtWidgets.QPushButton("Changelog locale")
        changelog_btn.clicked.connect(lambda: self._open_path(Path("CHANGELOG.md").resolve()))
        hero_actions.addWidget(repo_btn)
        hero_actions.addWidget(changelog_btn)
        hero_layout.addLayout(hero_actions)
        layout.addWidget(hero)

        # Toggle avanzate
        toggle_row = QtWidgets.QHBoxLayout()
        self.advanced_toggle = QtWidgets.QCheckBox("Mostra opzioni avanzate")
        self.advanced_toggle.stateChanged.connect(lambda _: self._toggle_advanced(self.advanced_toggle.isChecked()))
        toggle_row.addWidget(self.advanced_toggle)
        toggle_row.addStretch()
        layout.addLayout(toggle_row)

        # Profile area
        profile_box = QtWidgets.QGroupBox("Profilo Firefox")
        profile_layout = QtWidgets.QGridLayout(profile_box)
        profile_layout.addWidget(QtWidgets.QLabel("Percorso profilo"), 0, 0)
        self.profile_edit = QtWidgets.QLineEdit()
        profile_layout.addWidget(self.profile_edit, 0, 1)
        browse_btn = QtWidgets.QPushButton("Sfoglia")
        browse_btn.clicked.connect(self.choose_profile)
        profile_layout.addWidget(browse_btn, 0, 2)

        self.profile_combo = QtWidgets.QComboBox()
        self.profile_combo.currentTextChanged.connect(self._on_profile_selected)
        profile_layout.addWidget(QtWidgets.QLabel("Profili rilevati"), 1, 0)
        profile_layout.addWidget(self.profile_combo, 1, 1)
        reload_btn = QtWidgets.QPushButton("Rileva")
        reload_btn.clicked.connect(self._load_profiles)
        profile_layout.addWidget(reload_btn, 1, 2)

        self.theme_toggle = QtWidgets.QComboBox()
        self.theme_toggle.addItems(["System", "Light", "Dark"])
        self.theme_toggle.setCurrentText(self.settings.get("theme", "System").capitalize())
        self.theme_toggle.currentTextChanged.connect(self._on_theme_change)
        profile_layout.addWidget(QtWidgets.QLabel("Tema"), 2, 0)
        profile_layout.addWidget(self.theme_toggle, 2, 1)
        layout.addWidget(profile_box)

        # Actions
        actions = QtWidgets.QHBoxLayout()
        self.check_btn = QtWidgets.QPushButton("Controlla versioni")
        self.check_btn.clicked.connect(self.check_versions)
        self.update_btn = QtWidgets.QPushButton("Aggiorna")
        self.update_btn.clicked.connect(self.run_update)
        self.update_btn.setProperty("class", "primary")
        self.backup_btn = QtWidgets.QPushButton("Solo backup")
        self.backup_btn.clicked.connect(self.run_backup)
        actions.addWidget(self.check_btn)
        actions.addWidget(self.update_btn)
        actions.addWidget(self.backup_btn)
        layout.addLayout(actions)

        # Stats grid
        stats_box = QtWidgets.QGroupBox("Stato")
        stats = QtWidgets.QGridLayout(stats_box)
        self.local_lbl = QtWidgets.QLabel("n/d")
        self.remote_lbl = QtWidgets.QLabel("n/d")
        self.github_lbl = QtWidgets.QLabel("n/d")
        self.fx_lbl = QtWidgets.QLabel("n/d")
        stats.addWidget(QtWidgets.QLabel("Locale"), 0, 0)
        stats.addWidget(self.local_lbl, 1, 0)
        stats.addWidget(QtWidgets.QLabel("Remoto"), 0, 1)
        stats.addWidget(self.remote_lbl, 1, 1)
        stats.addWidget(QtWidgets.QLabel("GitHub"), 0, 2)
        stats.addWidget(self.github_lbl, 1, 2)
        stats.addWidget(QtWidgets.QLabel("Firefox"), 0, 3)
        stats.addWidget(self.fx_lbl, 1, 3)
        layout.addWidget(stats_box)

        # Backup settings
        backup_box = QtWidgets.QGroupBox("Backup")
        backup_layout = QtWidgets.QGridLayout(backup_box)
        backup_layout.addWidget(QtWidgets.QLabel("Cartella backup"), 0, 0)
        self.backup_edit = QtWidgets.QLineEdit()
        backup_layout.addWidget(self.backup_edit, 0, 1)
        backup_btn = QtWidgets.QPushButton("Scegli")
        backup_btn.clicked.connect(self.choose_backup)
        backup_layout.addWidget(backup_btn, 0, 2)
        backup_layout.addWidget(QtWidgets.QLabel("Giorni retention"), 1, 0)
        self.retention_spin = QtWidgets.QSpinBox()
        self.retention_spin.setRange(7, 120)
        backup_layout.addWidget(self.retention_spin, 1, 1)
        self.compress_chk = QtWidgets.QCheckBox("Comprimi zip")
        backup_layout.addWidget(self.compress_chk, 2, 0)
        self.auto_backup_chk = QtWidgets.QCheckBox("Backup automatico prima di aggiornare")
        backup_layout.addWidget(self.auto_backup_chk, 2, 1, 1, 2)
        self.auto_restart_chk = QtWidgets.QCheckBox("Riavvia Firefox dopo l'update")
        backup_layout.addWidget(self.auto_restart_chk, 3, 0, 1, 2)
        layout.addWidget(backup_box)

        network_box = QtWidgets.QGroupBox("Rete e resilienza download")
        net_layout = QtWidgets.QGridLayout(network_box)
        self.proxy_edit = QtWidgets.QLineEdit()
        self.proxy_edit.setPlaceholderText("http://user:pass@host:port")
        net_layout.addWidget(QtWidgets.QLabel("Proxy (opzionale)"), 0, 0)
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
        self.apply_net_btn.clicked.connect(self.apply_network_settings)
        self.test_net_btn = QtWidgets.QPushButton("Test download")
        self.test_net_btn.clicked.connect(self.test_network)
        net_layout.addWidget(self.apply_net_btn, 3, 0)
        net_layout.addWidget(self.test_net_btn, 3, 1)
        layout.addWidget(network_box)
        self.network_box = network_box

        # Log area
        self.log_text = QtWidgets.QPlainTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text, 1)

        # Progress + status
        bottom = QtWidgets.QHBoxLayout()
        self.progress = QtWidgets.QProgressBar()
        self.progress.setMinimum(0)
        self.progress.setMaximum(1)
        self.progress.setValue(0)
        bottom.addWidget(self.progress, 1)
        self.status = QtWidgets.QLabel("Pronto")
        self.status.setObjectName("statusChip")
        bottom.addWidget(self.status)
        layout.addLayout(bottom)
        self._set_status("Pronto")

        # Utility buttons
        basic_util = QtWidgets.QHBoxLayout()
        open_log_btn = QtWidgets.QPushButton("Apri log")
        open_log_btn.clicked.connect(lambda: self._open_path(self.paths.log_file))
        open_backup_btn = QtWidgets.QPushButton("Apri cartella backup")
        open_backup_btn.clicked.connect(self._open_backup_dir)
        clear_log_btn = QtWidgets.QPushButton("Pulisci log")
        clear_log_btn.clicked.connect(self.log_text.clear)
        about_btn = QtWidgets.QPushButton("About")
        about_btn.clicked.connect(self._show_about)
        basic_util.addWidget(open_log_btn)
        basic_util.addWidget(open_backup_btn)
        basic_util.addWidget(clear_log_btn)
        basic_util.addWidget(about_btn)
        basic_util.addStretch()
        layout.addLayout(basic_util)

        adv_util_box = QtWidgets.QHBoxLayout()
        open_cfg_btn = QtWidgets.QPushButton("Apri config")
        open_cfg_btn.clicked.connect(lambda: self._open_path(self.paths.config))
        open_data_btn = QtWidgets.QPushButton("Cartella dati app")
        open_data_btn.clicked.connect(lambda: self._open_path(self.paths.base))
        release_btn = QtWidgets.QPushButton("Cartella release")
        release_btn.clicked.connect(lambda: self._open_path(Path(__file__).resolve().parent.parent / "release_app"))
        open_profile_btn = QtWidgets.QPushButton("Apri profilo")
        open_profile_btn.clicked.connect(self._open_profile_dir)
        open_userjs_btn = QtWidgets.QPushButton("Apri user.js")
        open_userjs_btn.clicked.connect(self._open_userjs)
        adv_util_box.addWidget(open_cfg_btn)
        adv_util_box.addWidget(open_data_btn)
        adv_util_box.addWidget(release_btn)
        adv_util_box.addWidget(open_profile_btn)
        adv_util_box.addWidget(open_userjs_btn)
        adv_util_box.addStretch()
        adv_container = QtWidgets.QWidget()
        adv_container.setLayout(adv_util_box)
        layout.addWidget(adv_container)
        self.advanced_container = adv_container

    def _apply_stylesheet(self):
        self.setStyleSheet(
            f"""
            QWidget {{
                background-color: #0b1220;
                color: #e7eaf2;
                font-family: "Segoe UI", "Segoe UI Variable", "Inter", sans-serif;
                font-size: 13px;
            }}
            QGroupBox {{
                border: 1px solid #1f2737;
                border-radius: 12px;
                margin-top: 12px;
                padding-top: 16px;
                background-color: #0f172a;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
                color: #9fb3ff;
                font-weight: 600;
            }}
            QPushButton {{
                padding: 9px 14px;
                border-radius: 10px;
                border: 1px solid #1f2737;
                background-color: #121a2b;
                color: #e7eaf2;
            }}
            QPushButton:hover {{
                border-color: rgba(91,140,255,0.6);
                background-color: rgba(91,140,255,0.12);
            }}
            QPushButton[class="primary"] {{
                background-color: {self.accent};
                color: #0b1220;
                border: none;
                font-weight: 600;
            }}
            QPushButton[class="primary"]:hover {{
                background-color: #6b9cff;
            }}
            QLineEdit, QComboBox, QSpinBox {{
                padding: 8px 10px;
                border-radius: 10px;
                border: 1px solid #1f2737;
                background-color: #0f1627;
                selection-background-color: {self.accent};
                selection-color: #0b1220;
            }}
            QPlainTextEdit {{
                background-color: #0a101d;
                color: #e7eaf2;
                border-radius: 12px;
                border: 1px solid #1f2737;
                padding: 8px;
            }}
            #heroCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(91,140,255,0.18),
                    stop:1 rgba(16,24,40,0.95));
                border: 1px solid rgba(91,140,255,0.35);
                border-radius: 14px;
                padding: 16px;
            }}
            #statusChip {{
                padding: 6px 12px;
                border-radius: 10px;
                background-color: rgba(91,140,255,0.12);
                color: #e7eaf2;
                font-weight: 600;
            }}
            QProgressBar {{
                border: 1px solid #1f2737;
                border-radius: 8px;
                background: #0f1627;
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
        # nascondi avanzate di default alla partenza per vista compatta
        self._toggle_advanced(self.advanced_toggle.isChecked())

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

    def _toggle_advanced(self, visible: bool):
        if hasattr(self, "advanced_container"):
            self.advanced_container.setVisible(visible)
        if hasattr(self, "network_box"):
            self.network_box.setVisible(visible)
        label = "Mostra opzioni avanzate" if not visible else "Nascondi opzioni avanzate"
        self.advanced_toggle.setText(label)

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
