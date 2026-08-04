#!/usr/bin/env python3

from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings, QWebEngineScript, QWebEngineDownloadRequest, QWebEnginePermission
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtGui import (
    QIcon, QPixmap, QFont, QPalette, QColor, QAction, QDesktopServices,
    QKeySequence, QClipboard, QFontDatabase, QLinearGradient, QBrush,
    QPainter, QPen, QFontMetrics
)
from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, QThread, QUrl, QPropertyAnimation,
    QEasingCurve, QPoint, QRect, QSize, QParallelAnimationGroup
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QPushButton, QLabel, QLineEdit, QTextEdit, QListWidget,
    QListWidgetItem, QFileDialog, QMessageBox, QMenu, QSystemTrayIcon,
    QStackedWidget, QSplitter, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QProgressBar, QTextBrowser, QFrame, QToolButton,
    QStyle, QSizePolicy, QSpacerItem, QGridLayout, QScrollArea,
    QInputDialog, QCheckBox
)
import sys
import os
import json
import shutil
import base64
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

sys.argv.extend(
    [
        "--unlimited-storage",
        "--enable-aggressive-dom-storage-flushing",
        "--disable-features=IsolateOrigins,site-per-process",
    ]
)

os.environ["QTWEBENGINE_DISABLE_SANDBOX"] = "1"
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu --disable-software-rasterizer --disable-blink-features=AutomationControlled"

APP_NAME = "Alinvault"
APP_VERSION = "3.0.0"
CONFIG_DIR = Path.home() / ".alinvault"
CACHE_DIR = CONFIG_DIR / "web_cache"
STORAGE_DIR = CONFIG_DIR / "web_storage"
DOWNLOADS_DIR = Path.home() / "Downloads" / "alinvault"
NOTES_FILE = CONFIG_DIR / "notes.json"
CLIPBOARD_FILE = CONFIG_DIR / "clipboard.json"
CONFIG_FILE = CONFIG_DIR / "config.json"
TABS_FILE = CONFIG_DIR / "tabs.json"
AUTOSAVE_FILE = CONFIG_DIR / "autosave.json"
SESSION_FILE = CONFIG_DIR / "session.json"
KEY_FILE = CONFIG_DIR / "key.key"

CONFIG_DIR.mkdir(exist_ok=True)
DOWNLOADS_DIR.mkdir(exist_ok=True)

DEFAULT_TABS = [
    {"name": "Claude", "url": "https://claude.ai/new"},
    {"name": "Gemini", "url": "https://gemini.google.com/app"},
    {"name": "Kimi", "url": "https://www.kimi.com/?chat_enter_method=new_chat"},
    {"name": "ChatGPT", "url": "https://chatgpt.com/"},
    {"name": "WhatsApp", "url": "https://web.whatsapp.com/"}
]

_GLOBAL_PROFILE = None


def get_global_profile():
    global _GLOBAL_PROFILE
    if _GLOBAL_PROFILE is None:
        _GLOBAL_PROFILE = QWebEngineProfile("AlinvaultStorageProfile")
        _GLOBAL_PROFILE.setCachePath(str(CACHE_DIR))
        _GLOBAL_PROFILE.setPersistentStoragePath(str(STORAGE_DIR))
        _GLOBAL_PROFILE.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
        )
        _GLOBAL_PROFILE.setHttpCacheType(
            QWebEngineProfile.HttpCacheType.DiskHttpCache
        )
        user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        _GLOBAL_PROFILE.setHttpUserAgent(user_agent)
    return _GLOBAL_PROFILE


class SessionManager:
    def __init__(self):
        self.fernet = None
        self.init_encryption()

    def init_encryption(self):
        if KEY_FILE.exists():
            try:
                with open(KEY_FILE, 'rb') as f:
                    key = f.read()
                self.fernet = Fernet(key)
            except:
                self.generate_key()
        else:
            self.generate_key()

    def generate_key(self):
        salt = b'alinvault_salt_2024'
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        password = APP_NAME + APP_VERSION
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        with open(KEY_FILE, 'wb') as f:
            f.write(key)
        self.fernet = Fernet(key)

    def save_session(self, data: Dict):
        try:
            json_str = json.dumps(data, default=str)
            encrypted = self.fernet.encrypt(json_str.encode())
            with open(SESSION_FILE, 'wb') as f:
                f.write(encrypted)
            return True
        except Exception as e:
            print(f"Session save error: {e}")
            return False

    def load_session(self) -> Optional[Dict]:
        if not SESSION_FILE.exists():
            return None
        try:
            with open(SESSION_FILE, 'rb') as f:
                encrypted = f.read()
            decrypted = self.fernet.decrypt(encrypted)
            data = json.loads(decrypted.decode())
            return data
        except Exception as e:
            print(f"Session load error: {e}")
            return None

    def clear_session(self):
        if SESSION_FILE.exists():
            SESSION_FILE.unlink()


class DownloadHandler:
    def __init__(self):
        self.downloads = []
        self.download_progress = {}
        self.download_widgets = {}

    def handle_download(self, download: QWebEngineDownloadRequest, parent=None):
        DOWNLOADS_DIR.mkdir(exist_ok=True)
        suggested_filename = download.suggestedFileName()
        if not suggested_filename:
            suggested_filename = f"download_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        file_path = DOWNLOADS_DIR / suggested_filename
        counter = 1
        while file_path.exists():
            name, ext = os.path.splitext(suggested_filename)
            new_name = f"{name}_{counter}{ext}"
            file_path = DOWNLOADS_DIR / new_name
            counter += 1
        download.setDownloadDirectory(str(DOWNLOADS_DIR))
        download.setDownloadFileName(file_path.name)
        download.accept()
        download_id = id(download)
        self.download_progress[download_id] = 0
        progress_dialog = QDialog(parent) if parent else QDialog()
        progress_dialog.setWindowTitle("Downloading")
        progress_dialog.setFixedSize(400, 120)
        progress_dialog.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        layout = QVBoxLayout(progress_dialog)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        filename_label = QLabel(f"Downloading: {file_path.name}")
        filename_label.setStyleSheet(
            "font-weight: 500; font-size: 13px; color: #e8e8f0;")
        layout.addWidget(filename_label)
        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setTextVisible(True)
        progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background: #1a1a2e;
                border-radius: 6px;
                height: 20px;
            }
            QProgressBar::chunk {
                background: #6c8cff;
                border-radius: 6px;
            }
        """)
        layout.addWidget(progress_bar)
        status_label = QLabel("Starting download...")
        status_label.setStyleSheet("color: #8888a0; font-size: 12px;")
        layout.addWidget(status_label)
        progress_dialog.setStyleSheet("""
            QDialog {
                background: #0d0d1a;
                border-radius: 12px;
                border: 1px solid #1a1a2e;
            }
        """)
        progress_dialog.show()

        def update_progress(bytes_received, bytes_total):
            if bytes_total > 0:
                progress = int((bytes_received / bytes_total) * 100)
                self.download_progress[download_id] = progress
                progress_bar.setValue(progress)
                status_label.setText(
                    f"Downloaded: {self.format_size(bytes_received)} / {self.format_size(bytes_total)}")

        def download_finished():
            if download.state() == QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
                progress_bar.setValue(100)
                status_label.setText("Download complete!")
                filename = download.downloadFileName()
                QMessageBox.information(
                    parent or progress_dialog,
                    "Download Complete",
                    f'"{filename}" has been downloaded!\nYou can view at Downloads/alinvault'
                )
                if progress_dialog:
                    progress_dialog.accept()
                if parent and hasattr(parent, 'refresh_files'):
                    parent.refresh_files()
            elif download.state() == QWebEngineDownloadRequest.DownloadState.DownloadCancelled:
                status_label.setText("Download cancelled")
                QTimer.singleShot(1500, progress_dialog.accept)
            elif download.state() == QWebEngineDownloadRequest.DownloadState.DownloadInterrupted:
                status_label.setText("Download interrupted")
                QTimer.singleShot(1500, progress_dialog.accept)
            if download_id in self.download_progress:
                del self.download_progress[download_id]

        download.downloadProgress.connect(update_progress)
        download.finished.connect(download_finished)
        download.stateChanged.connect(
            lambda state: self.state_changed(download, state, progress_dialog))
        self.downloads.append(download)

    def format_size(self, bytes_size):
        if bytes_size < 1024:
            return f"{bytes_size} B"
        elif bytes_size < 1024 * 1024:
            return f"{bytes_size/1024:.1f} KB"
        elif bytes_size < 1024 * 1024 * 1024:
            return f"{bytes_size/(1024*1024):.1f} MB"
        else:
            return f"{bytes_size/(1024*1024*1024):.2f} GB"

    def state_changed(self, download, state, dialog):
        if state == QWebEngineDownloadRequest.DownloadState.DownloadCancelled:
            print(f"Download cancelled: {download.downloadFileName()}")
            if dialog:
                QTimer.singleShot(1000, dialog.accept)
        elif state == QWebEngineDownloadRequest.DownloadState.DownloadInterrupted:
            print(f"Download interrupted: {download.downloadFileName()}")
            if dialog:
                QTimer.singleShot(1000, dialog.accept)


class CustomWebEnginePage(QWebEnginePage):
    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        try:
            self.permissionRequested.connect(self.handle_permission)
        except Exception:
            pass
        self.download_handler = DownloadHandler()
        self.profile().downloadRequested.connect(self.on_download_requested)

    def handle_permission(self, permission):
        try:
            permission.grant()
        except AttributeError:
            self.setFeaturePermission(
                permission,
                QWebEnginePage.PermissionPolicy.PermissionGrantedByUser,
            )

    def on_download_requested(self, download):
        parent = self.parent() if self.parent() else None
        self.download_handler.handle_download(download, parent)


class WebTabContent(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        nav_bar = QWidget()
        nav_bar.setObjectName("navBar")
        nav_bar.setFixedHeight(40)
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setContentsMargins(8, 2, 8, 2)
        nav_layout.setSpacing(2)

        self.back_btn = QToolButton()
        self.back_btn.setText("←")
        self.back_btn.setObjectName("navBtn")
        self.back_btn.setFixedSize(28, 28)
        self.back_btn.clicked.connect(self.go_back)

        self.forward_btn = QToolButton()
        self.forward_btn.setText("→")
        self.forward_btn.setObjectName("navBtn")
        self.forward_btn.setFixedSize(28, 28)
        self.forward_btn.clicked.connect(self.go_forward)

        self.reload_btn = QToolButton()
        self.reload_btn.setText("↻")
        self.reload_btn.setObjectName("navBtn")
        self.reload_btn.setFixedSize(28, 28)
        self.reload_btn.clicked.connect(self.reload_page)

        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Search or enter address...")
        self.url_bar.setObjectName("urlBar")
        self.url_bar.setFixedHeight(28)
        self.url_bar.returnPressed.connect(self.navigate)

        nav_layout.addWidget(self.back_btn)
        nav_layout.addWidget(self.forward_btn)
        nav_layout.addWidget(self.reload_btn)
        nav_layout.addWidget(self.url_bar, 1)

        layout.addWidget(nav_bar)

        self.progress = QProgressBar()
        self.progress.setObjectName("progressBar")
        self.progress.setFixedHeight(2)
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.web = QWebEngineView()
        profile = get_global_profile()
        page = CustomWebEnginePage(profile, self.web)

        script_code = """
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });

        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en', 'en-GB']
        });

        Object.defineProperty(navigator, 'platform', {
            get: () => 'Win32'
        });

        Object.defineProperty(navigator, 'hardwareConcurrency', {
            get: () => 8
        });

        window.chrome = {
            runtime: {},
            loadTimes: function() {},
            csi: function() {},
            app: {}
        };

        delete navigator.webdriver;

        if (!navigator.permissions) {
            navigator.permissions = {
                query: (desc) => {
                    if (desc.name === 'notifications') {
                        return Promise.resolve({state: 'granted'});
                    }
                    return Promise.resolve({state: 'prompt'});
                }
            };
        } else {
            const originalQuery = navigator.permissions.query;
            navigator.permissions.query = function(desc) {
                if (desc.name === 'notifications') {
                    return Promise.resolve({state: 'granted'});
                }
                return originalQuery.call(this, desc);
            };
        }

        if (!navigator.mediaDevices) {
            navigator.mediaDevices = {};
        }
        if (!navigator.mediaDevices.getUserMedia) {
            navigator.mediaDevices.getUserMedia = function(constraints) {
                return new Promise((resolve, reject) => {
                    resolve(new MediaStream());
                });
            };
        }

        if (!navigator.geolocation) {
            navigator.geolocation = {
                getCurrentPosition: function(success, error, options) {
                    if (success) {
                        success({
                            coords: {
                                latitude: 0,
                                longitude: 0,
                                accuracy: 0,
                                altitude: null,
                                altitudeAccuracy: null,
                                heading: null,
                                speed: null
                            },
                            timestamp: Date.now()
                        });
                    }
                },
                watchPosition: function(success, error, options) {
                    if (success) {
                        success({
                            coords: {
                                latitude: 0,
                                longitude: 0,
                                accuracy: 0,
                                altitude: null,
                                altitudeAccuracy: null,
                                heading: null,
                                speed: null
                            },
                            timestamp: Date.now()
                        });
                    }
                    return 0;
                },
                clearWatch: function(id) {}
            };
        }

        if (!navigator.getBattery) {
            navigator.getBattery = function() {
                return Promise.resolve({
                    charging: true,
                    chargingTime: 0,
                    dischargingTime: Infinity,
                    level: 1
                });
            };
        }

        if (!navigator.vibrate) {
            navigator.vibrate = function() { return true; };
        }

        if (!navigator.connection) {
            navigator.connection = {
                effectiveType: '4g',
                rtt: 50,
                downlink: 10,
                saveData: false
            };
        }

        if (!navigator.storage) {
            navigator.storage = {
                estimate: function() {
                    return Promise.resolve({
                        quota: 1073741824,
                        usage: 0
                    });
                }
            };
        }

        if (!navigator.clipboard) {
            navigator.clipboard = {
                writeText: function(text) {
                    return Promise.resolve();
                },
                readText: function() {
                    return Promise.resolve('');
                }
            };
        }

        if (!navigator.permissions) {
            navigator.permissions = {
                query: function(desc) {
                    return Promise.resolve({state: 'granted'});
                },
                request: function(desc) {
                    return Promise.resolve({state: 'granted'});
                }
            };
        } else {
            const origQuery = navigator.permissions.query;
            navigator.permissions.query = function(desc) {
                return Promise.resolve({state: 'granted'});
            };
            if (navigator.permissions.request) {
                const origRequest = navigator.permissions.request;
                navigator.permissions.request = function(desc) {
                    return Promise.resolve({state: 'granted'});
                };
            }
        }

        if (!navigator.getUserMedia) {
            navigator.getUserMedia = function(constraints, success, error) {
                if (success) {
                    success(new MediaStream());
                }
            };
        }

        if (!window.Notification) {
            window.Notification = function(title, options) {
                this.title = title;
                this.options = options;
                this.onclick = null;
                this.onclose = null;
                this.onerror = null;
                this.onshow = null;
                this.close = function() {};
            };
            window.Notification.permission = 'granted';
            window.Notification.requestPermission = function(callback) {
                if (callback) {
                    callback('granted');
                }
                return Promise.resolve('granted');
            };
        } else {
            if (Notification.permission !== 'granted') {
                Notification.permission = 'granted';
            }
            const origRequestPermission = Notification.requestPermission;
            Notification.requestPermission = function(callback) {
                if (callback) {
                    callback('granted');
                }
                return Promise.resolve('granted');
            };
        }

        if (!window.speechSynthesis) {
            window.speechSynthesis = {
                speaking: false,
                paused: false,
                pending: false,
                getVoices: function() { return []; },
                speak: function(utterance) {},
                cancel: function() {},
                pause: function() {},
                resume: function() {}
            };
        }

        if (!window.speechRecognition) {
            window.speechRecognition = function() {};
            window.SpeechRecognition = function() {};
        }

        if (!window.webkitSpeechRecognition) {
            window.webkitSpeechRecognition = function() {};
        }

        if (!window.indexedDB) {
            window.indexedDB = {
                open: function() {
                    return {
                        result: null,
                        error: null,
                        onerror: null,
                        onsuccess: null,
                        onupgradeneeded: null
                    };
                },
                deleteDatabase: function() {},
                cmp: function() { return 0; }
            };
        }
        """

        script = QWebEngineScript()
        script.setSourceCode(script_code)
        script.setInjectionPoint(
            QWebEngineScript.InjectionPoint.DocumentCreation)
        script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        script.setRunsOnSubFrames(True)
        page.scripts().insert(script)

        self.web.setPage(page)

        self.web.loadProgress.connect(self.progress.setValue)
        self.web.loadFinished.connect(self.on_load_finished)
        self.web.urlChanged.connect(self.on_url_changed)
        self.web.titleChanged.connect(self.on_title_changed)

        settings = self.web.settings()
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True)
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.PluginsEnabled, True)
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.AutoLoadImages, True)
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.ErrorPageEnabled, True)
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True)
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.XSSAuditingEnabled, False)
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.SpatialNavigationEnabled, False)
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.HyperlinkAuditingEnabled, False)
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, True)
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.AllowRunningInsecureContent, False)

        layout.addWidget(self.web)
        self.progress.hide()

    def on_load_finished(self, ok):
        self.progress.hide()

    def navigate(self):
        url = self.url_bar.text().strip()
        if not url:
            return
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        self.progress.show()
        self.web.load(QUrl(url))

    def on_url_changed(self, url):
        self.url_bar.setText(url.toString())

    def on_title_changed(self, title):
        parent = self.parent()
        if hasattr(parent, 'update_tab_title'):
            parent.update_tab_title(title)

    def go_back(self):
        self.web.back()

    def go_forward(self):
        self.web.forward()

    def reload_page(self):
        self.web.reload()

    def load_url(self, url):
        self.progress.show()
        self.web.load(QUrl(url))

    def get_current_url(self):
        return self.url_bar.text()


class AddTabDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Tab")
        self.setModal(True)
        self.setFixedSize(500, 200)
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(32, 32, 32, 32)
        form = QFormLayout()
        form.setSpacing(12)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter tab name")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com")
        form.addRow("Tab Name:", self.name_input)
        form.addRow("URL:", self.url_input)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setStyleSheet("""
            QDialog {
                background: #ffffff;
                border-radius: 12px;
            }
            QLabel {
                color: #1a1a2e;
                font-weight: 500;
                font-size: 13px;
            }
            QLineEdit {
                background: #f5f5fa;
                border: 1.5px solid #e0e0e8;
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 13px;
                color: #1a1a2e;
            }
            QLineEdit:focus {
                border-color: #4a6cf7;
                background: #ffffff;
            }
            QPushButton {
                background: #4a6cf7;
                color: white;
                border: none;
                padding: 10px 24px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #3a5cd7;
            }
            QPushButton[text="Cancel"] {
                background: transparent;
                color: #4a6cf7;
            }
            QPushButton[text="Cancel"]:hover {
                background: #f0f0f5;
            }
        """)

    def get_tab_data(self):
        return {
            'name': self.name_input.text().strip() or "New Tab",
            'url': self.url_input.text().strip() or "https://example.com"
        }


class DateTimeWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        self.date_label = QLabel()
        self.date_label.setObjectName("dateTimeLabel")
        self.date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label = QLabel()
        self.time_label.setObjectName("dateTimeLabel")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.date_label)
        layout.addWidget(self.time_label)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_datetime)
        self.timer.start(1000)
        self.update_datetime()
        self.setStyleSheet("""
            #dateTimeLabel {
                font-size: 13px;
                font-weight: 500;
                color: #8888a0;
                padding: 4px 8px;
                background: transparent;
                border-radius: 6px;
            }
        """)

    def update_datetime(self):
        now = datetime.now()
        self.date_label.setText(now.strftime("%d/%m/%Y"))
        self.time_label.setText(now.strftime("%H:%M:%S"))


class ThemeAwareWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.dark_mode = True

    def set_dark_mode(self, dark_mode):
        self.dark_mode = dark_mode
        self.apply_style()

    def apply_style(self):
        pass


class NoteManager:
    def __init__(self):
        self.notes = []
        self.todos = []
        self.current_note_index = -1
        self.current_todo_index = -1
        self.is_editing_note = False
        self.is_editing_todo = False
        self.last_autosave_content = ""
        self.session_mgr = SessionManager()
        self.load()

    def load(self):
        if NOTES_FILE.exists():
            try:
                with open(NOTES_FILE, 'r') as f:
                    data = json.load(f)
                    self.notes = data.get('notes', [])
                    self.todos = data.get('todos', [])
            except:
                self.notes = []
                self.todos = []
        else:
            self.notes = []
            self.todos = []
            self.save()
        self.load_autosave()

    def load_autosave(self):
        if AUTOSAVE_FILE.exists():
            try:
                with open(AUTOSAVE_FILE, 'r') as f:
                    data = json.load(f)
                    self.current_note_index = data.get('note_index', -1)
                    self.current_todo_index = data.get('todo_index', -1)
                    self.is_editing_note = data.get('editing_note', False)
                    self.is_editing_todo = data.get('editing_todo', False)
                    self.last_autosave_content = data.get('last_content', '')
            except:
                pass

    def save_autosave(self):
        try:
            content = ""
            if self.is_editing_note and 0 <= self.current_note_index < len(self.notes):
                content = self.notes[self.current_note_index].get(
                    'content', '')
            elif self.is_editing_todo and 0 <= self.current_todo_index < len(self.todos):
                content = self.todos[self.current_todo_index].get(
                    'content', '')
            with open(AUTOSAVE_FILE, 'w') as f:
                json.dump({
                    'note_index': self.current_note_index,
                    'todo_index': self.current_todo_index,
                    'editing_note': self.is_editing_note,
                    'editing_todo': self.is_editing_todo,
                    'last_content': content
                }, f, indent=2)
        except Exception as e:
            print(f"Error saving autosave: {e}")

    def save(self):
        try:
            with open(NOTES_FILE, 'w') as f:
                json.dump(
                    {'notes': self.notes, 'todos': self.todos}, f, indent=2)
        except Exception as e:
            print(f"Error saving notes: {e}")

    def add_note(self, title: str, content: str):
        if content.strip() or title.strip():
            self.notes.append({
                'title': title.strip() or f"Note {len(self.notes) + 1}",
                'content': content,
                'timestamp': datetime.now().isoformat(),
                'type': 'note'
            })
            self.save()
            self.current_note_index = len(self.notes) - 1
            self.is_editing_note = True
            self.save_autosave()
            return True
        return False

    def add_todo(self, title: str, content: str):
        if content.strip() or title.strip():
            self.todos.append({
                'title': title.strip() or f"Task {len(self.todos) + 1}",
                'content': content,
                'timestamp': datetime.now().isoformat(),
                'completed': False,
                'type': 'todo'
            })
            self.save()
            self.current_todo_index = len(self.todos) - 1
            self.is_editing_todo = True
            self.save_autosave()
            return True
        return False

    def delete_item(self, index: int, item_type: str = 'note'):
        if item_type == 'note':
            if 0 <= index < len(self.notes):
                del self.notes[index]
                self.save()
                if self.current_note_index == index:
                    self.current_note_index = -1
                    self.is_editing_note = False
                    self.save_autosave()
                elif self.current_note_index > index:
                    self.current_note_index -= 1
                    self.save_autosave()
                return True
        else:
            if 0 <= index < len(self.todos):
                del self.todos[index]
                self.save()
                if self.current_todo_index == index:
                    self.current_todo_index = -1
                    self.is_editing_todo = False
                    self.save_autosave()
                elif self.current_todo_index > index:
                    self.current_todo_index -= 1
                    self.save_autosave()
                return True
        return False

    def toggle_todo(self, index: int):
        if 0 <= index < len(self.todos):
            self.todos[index]['completed'] = not self.todos[index]['completed']
            self.save()
            return True
        return False

    def update_note(self, index: int, title: str, content: str):
        if 0 <= index < len(self.notes):
            self.notes[index]['content'] = content
            if title:
                self.notes[index]['title'] = title
            self.notes[index]['timestamp'] = datetime.now().isoformat()
            self.save()
            return True
        return False

    def update_todo(self, index: int, title: str, content: str):
        if 0 <= index < len(self.todos):
            self.todos[index]['content'] = content
            if title:
                self.todos[index]['title'] = title
            self.todos[index]['timestamp'] = datetime.now().isoformat()
            self.save()
            return True
        return False

    def get_notes(self):
        return self.notes

    def get_todos(self):
        return self.todos

    def get_current_note(self):
        if 0 <= self.current_note_index < len(self.notes):
            return self.notes[self.current_note_index].get('content', '')
        return ""

    def get_current_todo(self):
        if 0 <= self.current_todo_index < len(self.todos):
            return self.todos[self.current_todo_index].get('content', '')
        return ""

    def get_note_title(self, index: int):
        if 0 <= index < len(self.notes):
            return self.notes[index].get('title', f"Note {index + 1}")
        return ""

    def get_todo_title(self, index: int):
        if 0 <= index < len(self.todos):
            return self.todos[index].get('title', f"Task {index + 1}")
        return ""


class ClipboardManager:
    def __init__(self):
        self.clipboard_items = []
        self.max_items = 100
        self.load()
        self.monitoring = False

    def load(self):
        if CLIPBOARD_FILE.exists():
            try:
                with open(CLIPBOARD_FILE, 'r') as f:
                    self.clipboard_items = json.load(f)
            except:
                self.clipboard_items = []
        else:
            self.clipboard_items = []
            self.save()

    def save(self):
        try:
            with open(CLIPBOARD_FILE, 'w') as f:
                json.dump(self.clipboard_items[:self.max_items], f, indent=2)
        except Exception as e:
            print(f"Error saving clipboard: {e}")

    def add_item(self, text: str):
        if not text or not text.strip():
            return
        for item in self.clipboard_items:
            if item['content'] == text:
                self.clipboard_items.remove(item)
                break
        self.clipboard_items.insert(0, {
            'content': text,
            'timestamp': datetime.now().isoformat()
        })
        if len(self.clipboard_items) > self.max_items:
            self.clipboard_items = self.clipboard_items[:self.max_items]
        self.save()

    def get_items(self):
        return self.clipboard_items

    def delete_item(self, index: int):
        if 0 <= index < len(self.clipboard_items):
            del self.clipboard_items[index]
            self.save()
            return True
        return False

    def clear_all(self):
        self.clipboard_items = []
        self.save()


class NotesWidget(ThemeAwareWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager = NoteManager()
        self.current_mode = "Notes"
        self.edit_index = -1
        self.edit_type = "note"
        self.unsaved_changes = False
        self.autosave_timer = QTimer()
        self.autosave_timer.timeout.connect(self.autosave)
        self.autosave_timer.start(3000)
        self.is_new_unsaved_note = False
        self.new_note_counter = 1

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(4)

        header_widget = QWidget()
        header_widget.setObjectName("headerWidget")
        header_widget.setFixedHeight(32)
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        title = QLabel("📝 Notes & Tasks")
        title.setObjectName("notesTitle")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.mode_btn_notes = QPushButton("Notes")
        self.mode_btn_notes.setObjectName("modeToggle")
        self.mode_btn_notes.setCheckable(True)
        self.mode_btn_notes.setChecked(True)
        self.mode_btn_notes.clicked.connect(lambda: self.switch_mode("Notes"))

        self.mode_btn_tasks = QPushButton("Tasks")
        self.mode_btn_tasks.setObjectName("modeToggle")
        self.mode_btn_tasks.setCheckable(True)
        self.mode_btn_tasks.clicked.connect(lambda: self.switch_mode("Tasks"))

        mode_group = QWidget()
        mode_group_layout = QHBoxLayout(mode_group)
        mode_group_layout.setContentsMargins(0, 0, 0, 0)
        mode_group_layout.setSpacing(0)
        mode_group_layout.addWidget(self.mode_btn_notes)
        mode_group_layout.addWidget(self.mode_btn_tasks)
        header_layout.addWidget(mode_group)

        layout.addWidget(header_widget)

        content_split = QSplitter(Qt.Orientation.Horizontal)
        content_split.setHandleWidth(1)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 4, 0)
        left_layout.setSpacing(3)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search...")
        self.search_bar.setObjectName("notesSearch")
        self.search_bar.setFixedHeight(24)
        self.search_bar.textChanged.connect(self.filter_items)
        left_layout.addWidget(self.search_bar)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("notesList")
        self.list_widget.itemClicked.connect(self.on_item_selected)
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_click)
        left_layout.addWidget(self.list_widget)

        self.stats_label = QLabel("")
        self.stats_label.setObjectName("statsLabel")
        left_layout.addWidget(self.stats_label)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)

        btn_font = QFont()
        btn_font.setPointSize(11)
        btn_font.setBold(True)

        icon_font = QFont()
        icon_font.setPointSize(14)

        self.new_btn = QPushButton("+ New")
        self.new_btn.setObjectName("notesBtn")
        self.new_btn.clicked.connect(self.new_item)
        self.new_btn.setFont(btn_font)

        self.rename_btn = QPushButton("✏️")
        self.rename_btn.setObjectName("notesBtn")
        self.rename_btn.setToolTip("Rename")
        self.rename_btn.clicked.connect(self.rename_item)
        self.rename_btn.setFont(icon_font)

        self.delete_btn = QPushButton("🗑")
        self.delete_btn.setObjectName("notesBtn")
        self.delete_btn.setToolTip("Delete")
        self.delete_btn.clicked.connect(self.delete_item)
        self.delete_btn.setFont(icon_font)

        btn_layout.addWidget(self.new_btn)
        btn_layout.addWidget(self.rename_btn)
        btn_layout.addWidget(self.delete_btn)
        btn_layout.addStretch()

        left_layout.addLayout(btn_layout)
        content_split.addWidget(left_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(4, 0, 0, 0)
        right_layout.setSpacing(3)

        editor_header = QWidget()
        editor_header.setObjectName("editorHeader")
        editor_header.setFixedHeight(26)
        editor_header_layout = QHBoxLayout(editor_header)
        editor_header_layout.setContentsMargins(6, 1, 6, 1)

        self.editor_title = QLabel("Start writing...")
        self.editor_title.setObjectName("editorTitle")
        editor_header_layout.addWidget(self.editor_title)
        editor_header_layout.addStretch()

        self.editor_status = QLabel("")
        self.editor_status.setObjectName("editorStatus")
        editor_header_layout.addWidget(self.editor_status)

        right_layout.addWidget(editor_header)

        self.editor = QTextEdit()
        self.editor.setPlaceholderText("Start writing your note here...")
        self.editor.setObjectName("editorArea")
        self.editor.textChanged.connect(self.on_text_changed)
        right_layout.addWidget(self.editor)

        content_split.addWidget(right_panel)
        content_split.setSizes([280, 720])
        layout.addWidget(content_split)

        status_bar = QWidget()
        status_bar.setObjectName("statusBar")
        status_bar.setFixedHeight(22)
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(6, 1, 6, 1)

        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusLabel")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()

        self.datetime_widget = DateTimeWidget()
        status_layout.addWidget(self.datetime_widget)

        layout.addWidget(status_bar)

        self.refresh()
        self.restore_autosave()

        QTimer.singleShot(10, lambda: self.set_dark_mode(True))
        self.setup_new_unsaved_note()
        self.apply_style()

    def setup_new_unsaved_note(self):
        self.is_new_unsaved_note = True
        self.edit_index = -1
        self.edit_type = "note"
        self.editor.clear()
        self.editor.setFocus()
        self.editor_title.setText("📄 Untitled")
        self.editor_status.setText("New note - start typing to save")
        self.status_label.setText("✏️ Start typing to create a new note")
        self.unsaved_changes = False

        notes = self.manager.get_notes()
        existing_numbers = []
        for note in notes:
            title = note.get('title', '')
            if title.startswith('Untitled '):
                try:
                    num = int(title.split(' ')[1])
                    existing_numbers.append(num)
                except:
                    pass
            elif title == 'Untitled':
                existing_numbers.append(0)

        if existing_numbers:
            self.new_note_counter = max(existing_numbers) + 1
        else:
            self.new_note_counter = 1

    def switch_mode(self, mode):
        if mode == self.current_mode:
            return
        if self.unsaved_changes:
            self.autosave()
        self.current_mode = mode
        self.mode_btn_notes.setChecked(mode == "Notes")
        self.mode_btn_tasks.setChecked(mode == "Tasks")
        self.search_bar.clear()
        self.editor.clear()
        self.editor_title.setText("Start writing...")
        self.editor_status.setText("")
        self.edit_index = -1
        self.edit_type = "note"
        self.refresh()
        if mode == "Notes":
            self.setup_new_unsaved_note()
        else:
            self.editor.setPlaceholderText("Start writing your task here...")
            self.editor.clear()

    def filter_items(self):
        search_text = self.search_bar.text().lower().strip()
        self.list_widget.clear()
        if self.current_mode == "Notes":
            items = self.manager.get_notes()
            for i, note in enumerate(items):
                title = note.get('title', f"Note {i + 1}").lower()
                content = note['content'].lower()
                if search_text and search_text not in title and search_text not in content:
                    continue
                self.add_list_item(i, note, "note")
        else:
            items = self.manager.get_todos()
            for i, todo in enumerate(items):
                title = todo.get('title', f"Task {i + 1}").lower()
                content = todo['content'].lower()
                if search_text and search_text not in title and search_text not in content:
                    continue
                self.add_list_item(i, todo, "todo")
        self.update_stats()

    def add_list_item(self, index, item, item_type):
        title = item.get(
            'title', f"{'Note' if item_type == 'note' else 'Task'} {index + 1}")
        content = item['content'] if item['content'] else "Empty"
        display_content = content[:80] + \
            "..." if len(content) > 80 else content
        display_content = display_content.replace('\n', ' ')
        timestamp = ""
        if 'timestamp' in item:
            try:
                dt = datetime.fromisoformat(item['timestamp'])
                timestamp = dt.strftime("%d/%m %Y")
            except:
                pass
        if item_type == "note":
            icon = "📄"
            display = f"{icon} {title}"
            if timestamp:
                display += f"  ·  {timestamp}"
            if display_content:
                display += f"\n   {display_content}"
        else:
            icon = "✅" if item.get('completed', False) else "⭕"
            display = f"{icon} {title}"
            if timestamp:
                display += f"  ·  {timestamp}"
            if display_content:
                display += f"\n   {display_content}"
        list_item = QListWidgetItem(display)
        list_item.setData(Qt.ItemDataRole.UserRole, {
            'index': index,
            'type': item_type
        })
        if self.edit_index == index and self.edit_type == item_type:
            list_item.setSelected(True)
        self.list_widget.addItem(list_item)

    def refresh(self):
        self.list_widget.clear()
        if self.current_mode == "Notes":
            items = self.manager.get_notes()
            for i, note in enumerate(items):
                self.add_list_item(i, note, "note")
        else:
            items = self.manager.get_todos()
            for i, todo in enumerate(items):
                self.add_list_item(i, todo, "todo")
        self.update_stats()

    def update_stats(self):
        count = self.list_widget.count()
        total = len(self.manager.get_notes() if self.current_mode ==
                    "Notes" else self.manager.get_todos())
        self.stats_label.setText(f"Showing {count} of {total}")

    def update_editor_status(self):
        if self.edit_type == "note":
            notes = self.manager.get_notes()
            if 0 <= self.edit_index < len(notes):
                note = notes[self.edit_index]
                ts = note.get('timestamp', '')
                if ts:
                    try:
                        dt = datetime.fromisoformat(ts)
                        self.editor_status.setText(
                            f"Updated: {dt.strftime('%d/%m/%Y %H:%M')}")
                    except:
                        self.editor_status.setText("")
                else:
                    self.editor_status.setText("")
        else:
            todos = self.manager.get_todos()
            if 0 <= self.edit_index < len(todos):
                todo = todos[self.edit_index]
                ts = todo.get('timestamp', '')
                if ts:
                    try:
                        dt = datetime.fromisoformat(ts)
                        self.editor_status.setText(
                            f"Updated: {dt.strftime('%d/%m/%Y %H:%M')}")
                    except:
                        self.editor_status.setText("")
                else:
                    self.editor_status.setText("")

    def on_text_changed(self):
        content = self.editor.toPlainText()
        if self.is_new_unsaved_note and content.strip():
            title = f"Untitled {self.new_note_counter}"
            if self.manager.add_note(title, content):
                self.is_new_unsaved_note = False
                self.edit_index = len(self.manager.get_notes()) - 1
                self.edit_type = "note"
                self.editor_title.setText(f"📄 {title}")
                self.editor_status.setText("Auto-saved")
                self.status_label.setText(f"✅ Auto-saved as '{title}'")
                self.unsaved_changes = False
                self.new_note_counter += 1
                self.refresh()
                for i in range(self.list_widget.count()):
                    item = self.list_widget.item(i)
                    data = item.data(Qt.ItemDataRole.UserRole)
                    if data and data['index'] == self.edit_index and data['type'] == 'note':
                        self.list_widget.setCurrentItem(item)
                        break
                return
        if not self.is_new_unsaved_note and self.edit_index >= 0:
            self.unsaved_changes = True
            self.status_label.setText("✏️ Typing...")

    def autosave(self):
        if self.is_new_unsaved_note:
            content = self.editor.toPlainText()
            if content.strip():
                title = f"Untitled {self.new_note_counter}"
                if self.manager.add_note(title, content):
                    self.is_new_unsaved_note = False
                    self.edit_index = len(self.manager.get_notes()) - 1
                    self.edit_type = "note"
                    self.editor_title.setText(f"📄 {title}")
                    self.editor_status.setText("Auto-saved")
                    self.status_label.setText(f"✅ Auto-saved as '{title}'")
                    self.unsaved_changes = False
                    self.new_note_counter += 1
                    self.refresh()
                    for i in range(self.list_widget.count()):
                        item = self.list_widget.item(i)
                        data = item.data(Qt.ItemDataRole.UserRole)
                        if data and data['index'] == self.edit_index and data['type'] == 'note':
                            self.list_widget.setCurrentItem(item)
                            break
            return
        if self.unsaved_changes and self.edit_index >= 0:
            content = self.editor.toPlainText()
            if self.edit_type == "note":
                title = self.manager.get_note_title(self.edit_index)
                if self.manager.update_note(self.edit_index, title, content):
                    self.unsaved_changes = False
                    self.manager.current_note_index = self.edit_index
                    self.manager.is_editing_note = True
                    self.manager.save_autosave()
                    self.status_label.setText("✅ Saved")
                    self.update_editor_status()
                    self.refresh()
            else:
                title = self.manager.get_todo_title(self.edit_index)
                if self.manager.update_todo(self.edit_index, title, content):
                    self.unsaved_changes = False
                    self.manager.current_todo_index = self.edit_index
                    self.manager.is_editing_todo = True
                    self.manager.save_autosave()
                    self.status_label.setText("✅ Saved")
                    self.update_editor_status()
                    self.refresh()

    def on_item_selected(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        if self.unsaved_changes:
            self.autosave()
        self.is_new_unsaved_note = False
        self.edit_index = data['index']
        self.edit_type = data['type']
        if self.edit_type == "note":
            notes = self.manager.get_notes()
            if 0 <= self.edit_index < len(notes):
                note = notes[self.edit_index]
                self.editor.setText(note['content'])
                self.editor_title.setText(f"📄 {note.get('title', 'Note')}")
                self.update_editor_status()
                self.manager.current_note_index = self.edit_index
                self.manager.is_editing_note = True
                self.manager.save_autosave()
        else:
            todos = self.manager.get_todos()
            if 0 <= self.edit_index < len(todos):
                todo = todos[self.edit_index]
                self.editor.setText(todo['content'])
                icon = "✅" if todo.get('completed', False) else "⭕"
                self.editor_title.setText(
                    f"{icon} {todo.get('title', 'Task')}")
                self.update_editor_status()
                self.manager.current_todo_index = self.edit_index
                self.manager.is_editing_todo = True
                self.manager.save_autosave()
        self.unsaved_changes = False
        self.status_label.setText("Editing")

    def on_item_double_click(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if data and data['type'] == "todo":
            self.manager.toggle_todo(data['index'])
            self.refresh()
            self.on_item_selected(item)

    def new_item(self):
        if self.unsaved_changes:
            self.autosave()
        title, ok = QInputDialog.getText(
            self,
            f"New {self.current_mode[:-1] if self.current_mode == 'Notes' else 'Task'}",
            f"Enter title:"
        )
        if not ok:
            return
        self.editor.clear()
        self.editor.setFocus()
        if self.current_mode == "Notes":
            if self.manager.add_note(title, ""):
                self.is_new_unsaved_note = False
                self.edit_index = len(self.manager.get_notes()) - 1
                self.edit_type = "note"
                self.editor_title.setText(f"📄 {title}")
                self.status_label.setText(f"New note: {title}")
        else:
            if self.manager.add_todo(title, ""):
                self.edit_index = len(self.manager.get_todos()) - 1
                self.edit_type = "todo"
                self.editor_title.setText(f"⭕ {title}")
                self.status_label.setText(f"New task: {title}")
        self.unsaved_changes = False
        self.refresh()
        self.update_editor_status()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            data = item.data(Qt.ItemDataRole.UserRole)
            if data and data['index'] == self.edit_index and data['type'] == self.edit_type:
                self.list_widget.setCurrentItem(item)
                break

    def rename_item(self):
        if self.edit_index < 0:
            QMessageBox.information(
                self, "Info", "Please select an item to rename.")
            return
        if self.edit_type == "note":
            current = self.manager.get_note_title(self.edit_index)
            new, ok = QInputDialog.getText(
                self, "Rename Note", "New title:", text=current)
            if ok and new:
                content = self.editor.toPlainText()
                if self.manager.update_note(self.edit_index, new, content):
                    self.editor_title.setText(f"📄 {new}")
                    self.status_label.setText(f"Renamed: {new}")
                    self.manager.save()
                    self.refresh()
                    self.update_editor_status()
        else:
            current = self.manager.get_todo_title(self.edit_index)
            new, ok = QInputDialog.getText(
                self, "Rename Task", "New title:", text=current)
            if ok and new:
                content = self.editor.toPlainText()
                if self.manager.update_todo(self.edit_index, new, content):
                    todos = self.manager.get_todos()
                    if 0 <= self.edit_index < len(todos):
                        icon = "✅" if todos[self.edit_index].get(
                            'completed', False) else "⭕"
                        self.editor_title.setText(f"{icon} {new}")
                    self.status_label.setText(f"Renamed: {new}")
                    self.manager.save()
                    self.refresh()
                    self.update_editor_status()

    def delete_item(self):
        if self.edit_index < 0:
            QMessageBox.information(
                self, "Info", "Please select an item to delete.")
            return
        item_type = "note" if self.edit_type == "note" else "task"
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete this {item_type}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            if self.edit_type == "note":
                self.manager.delete_item(self.edit_index, "note")
            else:
                self.manager.delete_item(self.edit_index, "todo")
            self.edit_index = -1
            self.edit_type = "note"
            self.editor.clear()
            self.editor_title.setText("Select an item")
            self.editor_status.setText("")
            self.status_label.setText("")
            self.refresh()
            self.setup_new_unsaved_note()

    def restore_autosave(self):
        if self.manager.is_editing_note:
            content = self.manager.get_current_note()
            if content:
                self.is_new_unsaved_note = False
                self.edit_index = self.manager.current_note_index
                self.edit_type = "note"
                self.editor.setText(content)
                notes = self.manager.get_notes()
                if 0 <= self.edit_index < len(notes):
                    self.editor_title.setText(
                        f"📄 {notes[self.edit_index].get('title', 'Note')}")
                self.update_editor_status()
                self.status_label.setText("Restored from autosave")
                self.unsaved_changes = False
                self.refresh()
                return
        if self.manager.is_editing_todo:
            content = self.manager.get_current_todo()
            if content:
                self.is_new_unsaved_note = False
                self.edit_index = self.manager.current_todo_index
                self.edit_type = "todo"
                self.editor.setText(content)
                todos = self.manager.get_todos()
                if 0 <= self.edit_index < len(todos):
                    icon = "✅" if todos[self.edit_index].get(
                        'completed', False) else "⭕"
                    self.editor_title.setText(
                        f"{icon} {todos[self.edit_index].get('title', 'Task')}")
                self.update_editor_status()
                self.status_label.setText("Restored from autosave")
                self.unsaved_changes = False
                self.refresh()
                return
        self.setup_new_unsaved_note()

    def force_save(self):
        if self.unsaved_changes:
            self.autosave()
        self.manager.save()
        self.manager.save_autosave()

    def save_all(self):
        self.manager.save()
        self.manager.save_autosave()
        if self.unsaved_changes:
            self.autosave()

    def apply_style(self):
        if self.dark_mode:
            self.setStyleSheet("""
                NotesWidget {
                    background: #0d0d1a;
                }
                #headerWidget {
                    background: transparent;
                }
                #notesTitle {
                    font-size: 13px;
                    font-weight: 700;
                    color: #e8e8f0;
                }
                #modeToggle {
                    background: transparent;
                    border: 1px solid #2a2a4a;
                    border-radius: 3px;
                    padding: 2px 8px;
                    font-weight: 500;
                    font-size: 10px;
                    color: #8888a0;
                }
                #modeToggle:checked {
                    background: #2a2a4a;
                    color: #6c8cff;
                    border-color: #6c8cff;
                }
                #modeToggle:hover {
                    background: #1a1a2e;
                }
                #notesSearch {
                    background: #141424;
                    border: 1px solid #1e1e32;
                    border-radius: 4px;
                    padding: 2px 6px;
                    color: #e8e8f0;
                    font-size: 11px;
                }
                #notesSearch:focus {
                    border-color: #6c8cff;
                }
                #notesSearch::placeholder {
                    color: #555;
                }
                #notesList {
                    background: #0d0d1a;
                    border: 1px solid #1a1a2e;
                    border-radius: 4px;
                    padding: 2px;
                }
                #notesList::item {
                    padding: 3px 6px;
                    border-radius: 3px;
                    color: #e8e8f0;
                    border-bottom: 1px solid #141424;
                    font-size: 11px;
                }
                #notesList::item:selected {
                    background: #2a2a4a;
                    color: #6c8cff;
                }
                #notesList::item:hover {
                    background: #141424;
                }
                #notesBtn {
                    background: #1a1a2e;
                    border: none;
                    border-radius: 4px;
                    padding: 4px 10px;
                    color: #e8e8f0;
                }
                #notesBtn:hover {
                    background: #2a2a4a;
                    color: #6c8cff;
                }
                #statsLabel {
                    color: #555;
                    font-size: 9px;
                    padding: 1px 0;
                }
                #editorHeader {
                    background: #141424;
                    border-radius: 4px 4px 0 0;
                }
                #editorTitle {
                    font-weight: 600;
                    font-size: 11px;
                    color: #e8e8f0;
                }
                #editorStatus {
                    color: #555;
                    font-size: 9px;
                }
                #editorArea {
                    background: #0d0d1a;
                    border: 1px solid #1a1a2e;
                    border-radius: 0 0 4px 4px;
                    padding: 4px 8px;
                    color: #e8e8f0;
                    font-size: 12px;
                    line-height: 1.4;
                }
                #editorArea:focus {
                    border-color: #6c8cff;
                }
                #statusBar {
                    background: #141424;
                    border-radius: 4px;
                }
                #statusLabel {
                    color: #6c8cff;
                    font-size: 10px;
                }
                QSplitter::handle {
                    background: #1a1a2e;
                }
                QSplitter::handle:hover {
                    background: #6c8cff;
                }
                QLabel {
                    color: #e8e8f0;
                }
            """)
        else:
            self.setStyleSheet("""
                NotesWidget {
                    background: #f5f5fa;
                }
                #headerWidget {
                    background: transparent;
                }
                #notesTitle {
                    font-size: 13px;
                    font-weight: 700;
                    color: #1a1a2e;
                }
                #modeToggle {
                    background: transparent;
                    border: 1px solid #d0d0d8;
                    border-radius: 3px;
                    padding: 2px 8px;
                    font-weight: 500;
                    font-size: 10px;
                    color: #6b6b80;
                }
                #modeToggle:checked {
                    background: #e8ecff;
                    color: #4a6cf7;
                    border-color: #4a6cf7;
                }
                #modeToggle:hover {
                    background: #f0f0f5;
                }
                #notesSearch {
                    background: #ffffff;
                    border: 1px solid #d0d0d8;
                    border-radius: 4px;
                    padding: 2px 6px;
                    color: #1a1a2e;
                    font-size: 11px;
                }
                #notesSearch:focus {
                    border-color: #4a6cf7;
                }
                #notesSearch::placeholder {
                    color: #aaa;
                }
                #notesList {
                    background: #ffffff;
                    border: 1px solid #e0e0e8;
                    border-radius: 4px;
                    padding: 2px;
                }
                #notesList::item {
                    padding: 3px 6px;
                    border-radius: 3px;
                    color: #1a1a2e;
                    border-bottom: 1px solid #f0f0f5;
                    font-size: 11px;
                }
                #notesList::item:selected {
                    background: #e8ecff;
                    color: #4a6cf7;
                }
                #notesList::item:hover {
                    background: #f5f5fa;
                }
                #notesBtn {
                    background: #f0f0f5;
                    border: none;
                    border-radius: 4px;
                    padding: 4px 10px;
                    color: #1a1a2e;
                }
                #notesBtn:hover {
                    background: #e8ecff;
                    color: #4a6cf7;
                }
                #statsLabel {
                    color: #999;
                    font-size: 9px;
                    padding: 1px 0;
                }
                #editorHeader {
                    background: #f0f0f5;
                    border-radius: 4px 4px 0 0;
                }
                #editorTitle {
                    font-weight: 600;
                    font-size: 11px;
                    color: #1a1a2e;
                }
                #editorStatus {
                    color: #999;
                    font-size: 9px;
                }
                #editorArea {
                    background: #ffffff;
                    border: 1px solid #e0e0e8;
                    border-radius: 0 0 4px 4px;
                    padding: 4px 8px;
                    color: #1a1a2e;
                    font-size: 12px;
                    line-height: 1.4;
                }
                #editorArea:focus {
                    border-color: #4a6cf7;
                }
                #statusBar {
                    background: #f0f0f5;
                    border-radius: 4px;
                }
                #statusLabel {
                    color: #4a6cf7;
                    font-size: 10px;
                }
                QSplitter::handle {
                    background: #e0e0e8;
                }
                QSplitter::handle:hover {
                    background: #4a6cf7;
                }
                QLabel {
                    color: #1a1a2e;
                }
            """)
        self.update()


class ClipboardWidget(ThemeAwareWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager = ClipboardManager()
        self.clipboard = QApplication.clipboard()
        self.last_text = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        header = QLabel("Clipboard History")
        header.setObjectName("sectionHeader")
        layout.addWidget(header)

        controls = QHBoxLayout()
        controls.setSpacing(10)

        self.copy_btn = QPushButton("Copy")
        self.copy_btn.setObjectName("actionBtn")
        self.copy_btn.clicked.connect(self.copy_item)

        self.view_btn = QPushButton("View")
        self.view_btn.setObjectName("actionBtn")
        self.view_btn.clicked.connect(self.view_item)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setObjectName("actionBtn")
        self.delete_btn.clicked.connect(self.delete_item)

        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.setObjectName("actionBtn")
        self.clear_btn.clicked.connect(self.clear_all)

        controls.addStretch()
        controls.addWidget(self.copy_btn)
        controls.addWidget(self.view_btn)
        controls.addWidget(self.delete_btn)
        controls.addWidget(self.clear_btn)
        layout.addLayout(controls)

        self.item_list = QListWidget()
        self.item_list.setObjectName("itemList")
        self.item_list.itemDoubleClicked.connect(self.copy_item)
        layout.addWidget(self.item_list)

        self.datetime_widget = DateTimeWidget()
        layout.addWidget(self.datetime_widget)

        self.timer = QTimer()
        self.timer.timeout.connect(self.check_clipboard)
        self.timer.start(500)

        self.refresh()
        self.apply_style()

    def check_clipboard(self):
        text = self.clipboard.text()
        if text and text != self.last_text:
            self.last_text = text
            self.manager.add_item(text)
            self.refresh()

    def refresh(self):
        self.item_list.clear()
        items = self.manager.get_items()
        for i, item in enumerate(items):
            content = item['content'][:200]
            if len(item['content']) > 200:
                content += "..."
            list_item = QListWidgetItem(f"{content}")
            list_item.setData(Qt.ItemDataRole.UserRole, i)
            self.item_list.addItem(list_item)

    def copy_item(self):
        current = self.item_list.currentItem()
        if current:
            idx = current.data(Qt.ItemDataRole.UserRole)
            items = self.manager.get_items()
            if 0 <= idx < len(items):
                self.clipboard.setText(items[idx]['content'])
                QMessageBox.information(
                    self, "Copied", "Item copied to clipboard!")

    def view_item(self):
        current = self.item_list.currentItem()
        if current:
            idx = current.data(Qt.ItemDataRole.UserRole)
            items = self.manager.get_items()
            if 0 <= idx < len(items):
                dialog = QDialog(self)
                dialog.setWindowTitle("View Content")
                dialog.setMinimumSize(550, 400)
                layout = QVBoxLayout(dialog)
                layout.setContentsMargins(28, 28, 28, 28)
                layout.setSpacing(16)
                browser = QTextBrowser()
                browser.setPlainText(items[idx]['content'])
                layout.addWidget(browser)
                ts = items[idx].get('timestamp', '')
                if ts:
                    try:
                        dt = datetime.fromisoformat(ts)
                        time_label = QLabel(
                            f"{dt.strftime('%d/%m/%Y %H:%M:%S')}")
                        if self.dark_mode:
                            time_label.setStyleSheet(
                                "color: #6c8cff; font-size: 12px; font-weight: 500;")
                        else:
                            time_label.setStyleSheet(
                                "color: #4a6cf7; font-size: 12px; font-weight: 500;")
                        layout.addWidget(time_label)
                    except:
                        pass
                close_btn = QPushButton("Close")
                close_btn.clicked.connect(dialog.accept)
                layout.addWidget(close_btn)
                if self.dark_mode:
                    dialog.setStyleSheet("""
                        QDialog {
                            background: #0d0d1a;
                            border-radius: 12px;
                        }
                        QTextBrowser {
                            background: #141424;
                            border: 1.5px solid #1a1a2e;
                            border-radius: 8px;
                            padding: 14px;
                            font-size: 13px;
                            color: #e8e8f0;
                            line-height: 1.8;
                        }
                        QPushButton {
                            background: #6c8cff;
                            color: white;
                            border: none;
                            padding: 10px 24px;
                            border-radius: 8px;
                            font-weight: 600;
                        }
                        QPushButton:hover {
                            background: #5a7ce7;
                        }
                        QLabel {
                            color: #e8e8f0;
                        }
                    """)
                else:
                    dialog.setStyleSheet("""
                        QDialog {
                            background: #ffffff;
                            border-radius: 12px;
                        }
                        QTextBrowser {
                            background: #f5f5fa;
                            border: 1.5px solid #e0e0e8;
                            border-radius: 8px;
                            padding: 14px;
                            font-size: 13px;
                            color: #1a1a2e;
                            line-height: 1.8;
                        }
                        QPushButton {
                            background: #4a6cf7;
                            color: white;
                            border: none;
                            padding: 10px 24px;
                            border-radius: 8px;
                            font-weight: 600;
                        }
                        QPushButton:hover {
                            background: #3a5cd7;
                        }
                        QLabel {
                            color: #1a1a2e;
                        }
                    """)
                dialog.exec()

    def delete_item(self):
        current = self.item_list.currentItem()
        if current:
            idx = current.data(Qt.ItemDataRole.UserRole)
            if self.manager.delete_item(idx):
                self.refresh()

    def clear_all(self):
        reply = QMessageBox.question(
            self, "Confirm", "Clear all clipboard history?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.manager.clear_all()
            self.refresh()

    def apply_style(self):
        if self.dark_mode:
            self.setStyleSheet("""
                ClipboardWidget {
                    background: #0d0d1a;
                }
                #sectionHeader {
                    font-size: 20px;
                    font-weight: 700;
                    color: #e8e8f0;
                    letter-spacing: -0.3px;
                }
                #actionBtn {
                    background: #6c8cff;
                    color: white;
                    border: none;
                    padding: 8px 18px;
                    border-radius: 8px;
                    font-weight: 600;
                    font-size: 12px;
                }
                #actionBtn:hover {
                    background: #5a7ce7;
                }
                #itemList {
                    background: #0d0d1a;
                    border: 1.5px solid #1a1a2e;
                    border-radius: 10px;
                    padding: 4px;
                }
                #itemList::item {
                    padding: 10px 14px;
                    border-radius: 6px;
                    font-size: 13px;
                    color: #e8e8f0;
                }
                #itemList::item:selected {
                    background: #2a2a4a;
                    color: #6c8cff;
                }
                #itemList::item:hover {
                    background: #141424;
                }
                QLabel {
                    color: #e8e8f0;
                }
            """)
        else:
            self.setStyleSheet("""
                ClipboardWidget {
                    background: #f5f5fa;
                }
                #sectionHeader {
                    font-size: 20px;
                    font-weight: 700;
                    color: #1a1a2e;
                    letter-spacing: -0.3px;
                }
                #actionBtn {
                    background: #4a6cf7;
                    color: white;
                    border: none;
                    padding: 8px 18px;
                    border-radius: 8px;
                    font-weight: 600;
                    font-size: 12px;
                }
                #actionBtn:hover {
                    background: #3a5cd7;
                }
                #itemList {
                    background: #ffffff;
                    border: 1.5px solid #e0e0e8;
                    border-radius: 10px;
                    padding: 4px;
                }
                #itemList::item {
                    padding: 10px 14px;
                    border-radius: 6px;
                    font-size: 13px;
                    color: #1a1a2e;
                }
                #itemList::item:selected {
                    background: #e8ecff;
                    color: #4a6cf7;
                }
                #itemList::item:hover {
                    background: #f0f0f5;
                }
                QLabel {
                    color: #1a1a2e;
                }
            """)
        self.update()


class DownloadsWidget(ThemeAwareWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        header = QLabel("Downloads")
        header.setObjectName("sectionHeader")
        layout.addWidget(header)

        info = QLabel(f"{DOWNLOADS_DIR}")
        info.setObjectName("infoLabel")
        layout.addWidget(info)

        self.open_btn = QPushButton("Open Folder")
        self.open_btn.setObjectName("actionBtn")
        self.open_btn.clicked.connect(self.open_folder)
        layout.addWidget(self.open_btn)

        self.file_list = QListWidget()
        self.file_list.setObjectName("itemList")
        self.file_list.itemDoubleClicked.connect(self.open_file)
        layout.addWidget(self.file_list)

        self.datetime_widget = DateTimeWidget()
        layout.addWidget(self.datetime_widget)

        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_files)
        self.timer.start(3000)
        self.refresh_files()

        self.apply_style()

    def refresh_files(self):
        self.file_list.clear()
        if DOWNLOADS_DIR.exists():
            files = list(DOWNLOADS_DIR.iterdir())
            files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            for f in files:
                size = f.stat().st_size
                size_str = f"{size} B"
                if size > 1024:
                    size_str = f"{size/1024:.1f} KB"
                if size > 1024*1024:
                    size_str = f"{size/(1024*1024):.1f} MB"
                item = QListWidgetItem(f"{f.name}  ·  {size_str}")
                item.setData(Qt.ItemDataRole.UserRole, str(f))
                self.file_list.addItem(item)

    def open_folder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(DOWNLOADS_DIR)))

    def open_file(self, item):
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if file_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))

    def apply_style(self):
        if self.dark_mode:
            self.setStyleSheet("""
                DownloadsWidget {
                    background: #0d0d1a;
                }
                #sectionHeader {
                    font-size: 20px;
                    font-weight: 700;
                    color: #e8e8f0;
                    letter-spacing: -0.3px;
                }
                #infoLabel {
                    color: #8888a0;
                    font-size: 13px;
                    font-weight: 500;
                }
                #actionBtn {
                    background: #6c8cff;
                    color: white;
                    border: none;
                    padding: 8px 18px;
                    border-radius: 8px;
                    font-weight: 600;
                    font-size: 12px;
                }
                #actionBtn:hover {
                    background: #5a7ce7;
                }
                #itemList {
                    background: #0d0d1a;
                    border: 1.5px solid #1a1a2e;
                    border-radius: 10px;
                    padding: 4px;
                }
                #itemList::item {
                    padding: 10px 14px;
                    border-radius: 6px;
                    font-size: 13px;
                    color: #e8e8f0;
                }
                #itemList::item:selected {
                    background: #2a2a4a;
                    color: #6c8cff;
                }
                #itemList::item:hover {
                    background: #141424;
                }
                QLabel {
                    color: #e8e8f0;
                }
            """)
        else:
            self.setStyleSheet("""
                DownloadsWidget {
                    background: #f5f5fa;
                }
                #sectionHeader {
                    font-size: 20px;
                    font-weight: 700;
                    color: #1a1a2e;
                    letter-spacing: -0.3px;
                }
                #infoLabel {
                    color: #6b6b80;
                    font-size: 13px;
                    font-weight: 500;
                }
                #actionBtn {
                    background: #4a6cf7;
                    color: white;
                    border: none;
                    padding: 8px 18px;
                    border-radius: 8px;
                    font-weight: 600;
                    font-size: 12px;
                }
                #actionBtn:hover {
                    background: #3a5cd7;
                }
                #itemList {
                    background: #ffffff;
                    border: 1.5px solid #e0e0e8;
                    border-radius: 10px;
                    padding: 4px;
                }
                #itemList::item {
                    padding: 10px 14px;
                    border-radius: 6px;
                    font-size: 13px;
                    color: #1a1a2e;
                }
                #itemList::item:selected {
                    background: #e8ecff;
                    color: #4a6cf7;
                }
                #itemList::item:hover {
                    background: #f0f0f5;
                }
                QLabel {
                    color: #1a1a2e;
                }
            """)
        self.update()


class AlinvaultWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1200, 800)
        self.sidebar_visible = True
        self.dark_mode = True
        self.session_mgr = SessionManager()

        icon_path = self.find_icon()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))

        main = QWidget()
        main.setObjectName("mainWidget")
        self.setCentralWidget(main)

        layout = QVBoxLayout(main)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_bar.setFixedHeight(56)
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(24, 0, 24, 0)

        logo = QLabel("Alinvault")
        logo.setObjectName("logoLabel")
        title_layout.addWidget(logo)
        title_layout.addStretch()

        self.datetime_widget = DateTimeWidget()
        title_layout.addWidget(self.datetime_widget)

        self.sidebar_toggle_btn = QPushButton("☰")
        self.sidebar_toggle_btn.setObjectName("sidebarToggleBtn")
        self.sidebar_toggle_btn.setFixedSize(36, 36)
        self.sidebar_toggle_btn.clicked.connect(self.toggle_sidebar)
        title_layout.addWidget(self.sidebar_toggle_btn)

        self.theme_btn = QPushButton("☀️")
        self.theme_btn.setObjectName("themeBtn")
        self.theme_btn.setFixedSize(36, 36)
        self.theme_btn.clicked.connect(self.toggle_theme)
        title_layout.addWidget(self.theme_btn)

        layout.addWidget(title_bar)

        content = QWidget()
        content.setObjectName("contentWidget")
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        sidebar = QWidget()
        sidebar.setFixedWidth(200)
        sidebar.setObjectName("sidebar")
        self.sidebar = sidebar
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 20, 12, 20)
        sidebar_layout.setSpacing(4)

        self.sidebar_btns = {}
        tools = [
            ("Browser", "web"),
            ("Notes", "notes"),
            ("Clipboard", "clipboard"),
            ("Downloads", "downloads")
        ]

        for text, name in tools:
            btn = QPushButton(text)
            btn.setObjectName("sidebarBtn")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, n=name: self.switch_tool(n))
            sidebar_layout.addWidget(btn)
            self.sidebar_btns[name] = btn

        sidebar_layout.addStretch()

        add_btn = QPushButton("+ Add Tab")
        add_btn.setObjectName("addTabBtn")
        add_btn.clicked.connect(self.add_custom_tab)
        sidebar_layout.addWidget(add_btn)

        content_layout.addWidget(sidebar)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("mainTabs")
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.setMovable(True)
        content_layout.addWidget(self.tabs, 1)

        layout.addWidget(content)

        self.tool_widgets = {}
        self.init_tools()
        self.load_session_data()
        self.apply_theme()
        self.setup_tray()

        self.sidebar_btns["web"].setChecked(True)

        self.save_timer = QTimer()
        self.save_timer.timeout.connect(self.force_save_all)
        self.save_timer.start(5000)

        self.session_save_timer = QTimer()
        self.session_save_timer.timeout.connect(self.save_session_data)
        self.session_save_timer.start(10000)

    def load_session_data(self):
        session = self.session_mgr.load_session()
        if not session:
            self.load_tabs()
            return

        tabs_data = session.get('tabs', [])
        current_tab = session.get('current_tab', 0)

        if tabs_data:
            for tab in tabs_data:
                self.add_web_tab(tab.get('name', 'Tab'),
                                 tab.get('url', 'https://example.com'))
                if hasattr(self, '_tab_data'):
                    idx = self.tabs.count() - 1
                    self._tab_data[idx] = tab

            if 0 <= current_tab < self.tabs.count():
                self.tabs.setCurrentIndex(current_tab)
        else:
            self.load_tabs()

        tool = session.get('active_tool', 'web')
        if tool != 'web':
            self.switch_tool(tool)

        dark_mode = session.get('dark_mode', True)
        if dark_mode != self.dark_mode:
            self.toggle_theme()

    def save_session_data(self):
        session_data = {
            'timestamp': datetime.now().isoformat(),
            'dark_mode': self.dark_mode,
            'active_tool': 'web'
        }

        for name, btn in self.sidebar_btns.items():
            if btn.isChecked():
                session_data['active_tool'] = name
                break

        tabs = []
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if widget and isinstance(widget, WebTabContent):
                name = self.tabs.tabText(i)
                url = widget.get_current_url()
                tabs.append({'name': name, 'url': url})

        session_data['tabs'] = tabs
        session_data['current_tab'] = self.tabs.currentIndex()

        self.session_mgr.save_session(session_data)

    def force_save_all(self):
        notes_widget = self.tool_widgets.get('notes')
        if notes_widget and hasattr(notes_widget, 'force_save'):
            notes_widget.force_save()
        self.save_session_data()

    def toggle_sidebar(self):
        self.sidebar_visible = not self.sidebar_visible
        if self.sidebar_visible:
            self.sidebar.show()
            self.sidebar_toggle_btn.setText("☰")
        else:
            self.sidebar.hide()
            self.sidebar_toggle_btn.setText("☱")

    def find_icon(self):
        paths = [
            "wolf.png",
            "wolf.ico",
            "/usr/share/icons/wolf.png",
            os.path.join(os.path.dirname(__file__), "wolf.png"),
            os.path.join(os.path.dirname(__file__), "wolf.ico")
        ]
        for path in paths:
            if os.path.exists(path):
                return path
        return None

    def init_tools(self):
        self.tool_widgets['notes'] = NotesWidget()
        self.tool_widgets['clipboard'] = ClipboardWidget()
        self.tool_widgets['downloads'] = DownloadsWidget()
        self.update_tool_styles()

    def load_tabs(self):
        tabs = DEFAULT_TABS.copy()
        if TABS_FILE.exists():
            try:
                with open(TABS_FILE, 'r') as f:
                    custom = json.load(f)
                    tabs.extend(custom)
            except:
                pass

        for tab in tabs:
            self.add_web_tab(tab['name'], tab['url'])

        if self.tabs.count() > 0:
            self.tabs.setCurrentIndex(0)

    def add_web_tab(self, name, url):
        content = WebTabContent(self)
        content.load_url(url)
        idx = self.tabs.addTab(content, name)
        self.tabs.setCurrentIndex(idx)

        if not hasattr(self, '_tab_data'):
            self._tab_data = {}
        self._tab_data[idx] = {'name': name, 'url': url}

    def add_custom_tab(self):
        dialog = AddTabDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_tab_data()
            self.add_web_tab(data['name'], data['url'])
            self.save_custom_tabs()

    def save_custom_tabs(self):
        custom = []
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if widget and isinstance(widget, WebTabContent):
                name = self.tabs.tabText(i)
                url = widget.get_current_url()
                if name not in [d['name'] for d in DEFAULT_TABS]:
                    custom.append({'name': name, 'url': url})

        try:
            with open(TABS_FILE, 'w') as f:
                json.dump(custom, f, indent=2)
        except Exception as e:
            print(f"Error saving tabs: {e}")

    def close_tab(self, idx):
        if self.tabs.count() <= 1:
            QMessageBox.information(self, "Info", "Cannot close the last tab.")
            return

        widget = self.tabs.widget(idx)
        self.tabs.removeTab(idx)
        if widget:
            widget.deleteLater()

    def switch_tool(self, tool_name):
        for btn in self.sidebar_btns.values():
            btn.setChecked(False)
        self.sidebar_btns[tool_name].setChecked(True)

        if tool_name == 'web':
            for i in range(self.tabs.count()):
                self.tabs.setTabVisible(i, True)
            if self.tabs.count() > 0:
                self.tabs.setCurrentIndex(0)
            return

        for i in range(self.tabs.count()):
            self.tabs.setTabVisible(i, False)

        if tool_name in self.tool_widgets:
            widget = self.tool_widgets[tool_name]
            for i in range(self.tabs.count()):
                if self.tabs.widget(i) == widget:
                    self.tabs.setCurrentIndex(i)
                    self.tabs.setTabVisible(i, True)
                    return

            names = {
                'notes': 'Notes',
                'clipboard': 'Clipboard',
                'downloads': 'Downloads'
            }
            idx = self.tabs.addTab(widget, names.get(tool_name, tool_name))
            self.tabs.setCurrentIndex(idx)
            self.tabs.setTabVisible(idx, True)

    def update_tab_title(self, title):
        current = self.tabs.currentIndex()
        if current >= 0:
            text = self.tabs.tabText(current)
            if title and not text in ['Notes', 'Clipboard', 'Downloads']:
                if len(title) > 30:
                    title = title[:27] + "..."
                self.tabs.setTabText(current, title)

    def toggle_theme(self):
        if self.dark_mode:
            self.apply_light()
            self.dark_mode = False
            self.theme_btn.setText("🌙")
        else:
            self.apply_dark()
            self.dark_mode = True
            self.theme_btn.setText("☀️")

        self.update_tool_styles()

    def apply_theme(self):
        self.dark_mode = True
        self.apply_dark()
        self.update_tool_styles()

    def apply_dark(self):
        self.setStyleSheet("""
            QWidget {
                font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Roboto, sans-serif;
                font-size: 13px;
                background: #0d0d1a;
                color: #e8e8f0;
            }
            #mainWidget {
                background: #0d0d1a;
            }
            #titleBar {
                background: #141424;
                border-bottom: 1px solid #1e1e32;
            }
            #logoLabel {
                font-weight: 700;
                font-size: 18px;
                color: #6c8cff;
                letter-spacing: -0.5px;
            }
            #themeBtn {
                background: transparent;
                border: none;
                font-size: 16px;
                border-radius: 8px;
            }
            #themeBtn:hover {
                background: #1e1e32;
            }
            #sidebarToggleBtn {
                background: transparent;
                border: none;
                font-size: 18px;
                border-radius: 8px;
                color: #8888a0;
            }
            #sidebarToggleBtn:hover {
                background: #1e1e32;
                color: #e8e8f0;
            }
            #contentWidget {
                background: #0d0d1a;
            }
            #sidebar {
                background: #0d0d1a;
                border-right: 1px solid #1a1a2e;
            }
            #sidebarBtn {
                background: transparent;
                border: none;
                padding: 10px 14px;
                border-radius: 8px;
                text-align: left;
                font-weight: 500;
                color: #8888a0;
                font-size: 13px;
            }
            #sidebarBtn:hover {
                background: #141424;
                color: #e8e8f0;
            }
            #sidebarBtn:checked {
                background: #2a2a4a;
                color: #6c8cff;
            }
            #addTabBtn {
                background: #2a2a4a;
                color: #6c8cff;
                border: none;
                padding: 10px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 12px;
            }
            #addTabBtn:hover {
                background: #3a3a5a;
            }
            QTabWidget::pane {
                border: none;
                background: #0d0d1a;
            }
            QTabBar::tab {
                background: transparent;
                padding: 8px 16px;
                border: none;
                border-radius: 6px;
                margin: 2px 3px;
                font-weight: 500;
                font-size: 12px;
                color: #8888a0;
            }
            QTabBar::tab:selected {
                background: #141424;
                color: #e8e8f0;
            }
            QTabBar::tab:hover {
                background: #141424;
                color: #e8e8f0;
            }
            #navBar {
                background: #0d0d1a;
                border-bottom: 1px solid #1a1a2e;
            }
            #urlBar {
                background: #141424;
                border: 1.5px solid #1e1e32;
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 13px;
                color: #e8e8f0;
            }
            #urlBar:focus {
                border-color: #6c8cff;
                background: #141424;
            }
            #urlBar::placeholder {
                color: #555;
            }
            #navBtn {
                background: transparent;
                border: none;
                border-radius: 6px;
                font-size: 16px;
                color: #8888a0;
                padding: 4px 8px;
            }
            #navBtn:hover {
                background: #141424;
                color: #e8e8f0;
            }
            #progressBar {
                background: transparent;
                border: none;
                height: 2px;
            }
            #progressBar::chunk {
                background: #6c8cff;
            }
            QMessageBox {
                background: #141424;
                border-radius: 12px;
            }
            QMessageBox QPushButton {
                background: #6c8cff;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 12px;
            }
            QMessageBox QPushButton:hover {
                background: #5a7ce7;
            }
            #dateTimeLabel {
                color: #8888a0;
            }
        """)

    def apply_light(self):
        self.setStyleSheet("""
            QWidget {
                font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Roboto, sans-serif;
                font-size: 13px;
                background: #f5f5fa;
                color: #1a1a2e;
            }
            #sidebarToggleBtn {
                background: transparent;
                border: none;
                font-size: 18px;
                border-radius: 8px;
                color: #6b6b80;
            }
            #sidebarToggleBtn:hover {
                background: #f0f0f5;
                color: #1a1a2e;
            }
            #mainWidget {
                background: #f5f5fa;
            }
            #titleBar {
                background: #ffffff;
                border-bottom: 1px solid #e0e0e8;
            }
            #logoLabel {
                font-weight: 700;
                font-size: 18px;
                color: #4a6cf7;
                letter-spacing: -0.5px;
            }
            #themeBtn {
                background: transparent;
                border: none;
                font-size: 16px;
                border-radius: 8px;
            }
            #themeBtn:hover {
                background: #f0f0f5;
            }
            #contentWidget {
                background: #f5f5fa;
            }
            #sidebar {
                background: #f5f5fa;
                border-right: 1px solid #e0e0e8;
            }
            #sidebarBtn {
                background: transparent;
                border: none;
                padding: 10px 14px;
                border-radius: 8px;
                text-align: left;
                font-weight: 500;
                color: #6b6b80;
                font-size: 13px;
            }
            #sidebarBtn:hover {
                background: #ffffff;
                color: #1a1a2e;
            }
            #sidebarBtn:checked {
                background: #e8ecff;
                color: #4a6cf7;
            }
            #addTabBtn {
                background: #e8ecff;
                color: #4a6cf7;
                border: none;
                padding: 10px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 12px;
            }
            #addTabBtn:hover {
                background: #d0d8ff;
            }
            QTabWidget::pane {
                border: none;
                background: #f5f5fa;
            }
            QTabBar::tab {
                background: transparent;
                padding: 8px 16px;
                border: none;
                border-radius: 6px;
                margin: 2px 3px;
                font-weight: 500;
                font-size: 12px;
                color: #6b6b80;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #1a1a2e;
            }
            QTabBar::tab:hover {
                background: #ffffff;
                color: #1a1a2e;
            }
            #navBar {
                background: #f5f5fa;
                border-bottom: 1px solid #e0e0e8;
            }
            #urlBar {
                background: #ffffff;
                border: 1.5px solid #e0e0e8;
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 13px;
                color: #1a1a2e;
            }
            #urlBar:focus {
                border-color: #4a6cf7;
                background: #ffffff;
            }
            #urlBar::placeholder {
                color: #aaa;
            }
            #navBtn {
                background: transparent;
                border: none;
                border-radius: 6px;
                font-size: 16px;
                color: #6b6b80;
                padding: 4px 8px;
            }
            #navBtn:hover {
                background: #ffffff;
                color: #1a1a2e;
            }
            #progressBar {
                background: transparent;
                border: none;
                height: 2px;
            }
            #progressBar::chunk {
                background: #4a6cf7;
            }
            QMessageBox {
                background: #ffffff;
                border-radius: 12px;
            }
            QMessageBox QPushButton {
                background: #4a6cf7;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 12px;
            }
            QMessageBox QPushButton:hover {
                background: #3a5cd7;
            }
            #dateTimeLabel {
                color: #6b6b80;
            }
        """)

    def update_tool_styles(self):
        for widget in self.tool_widgets.values():
            if hasattr(widget, 'set_dark_mode'):
                widget.set_dark_mode(self.dark_mode)
            if hasattr(widget, 'update'):
                widget.update()

    def setup_tray(self):
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(self)
            icon_path = self.find_icon()
            if icon_path:
                self.tray.setIcon(QIcon(icon_path))
            else:
                self.tray.setIcon(self.style().standardIcon(
                    QStyle.StandardPixmap.SP_ComputerIcon
                ))
            menu = QMenu()
            show_action = QAction("Show", self)
            show_action.triggered.connect(self.show)
            quit_action = QAction("Quit", self)
            quit_action.triggered.connect(self.quit_app)
            menu.addAction(show_action)
            menu.addAction(quit_action)
            self.tray.setContextMenu(menu)
            self.tray.show()

    def quit_app(self):
        self.force_save_all()
        self.save_session_data()
        self.save_custom_tabs()
        QApplication.quit()

    def closeEvent(self, event):
        notes_widget = self.tool_widgets.get('notes')
        if notes_widget:
            if hasattr(notes_widget, 'force_save'):
                notes_widget.force_save()
            if hasattr(notes_widget, 'manager'):
                notes_widget.manager.save()
                notes_widget.manager.save_autosave()
        self.save_session_data()
        self.save_custom_tabs()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName("Alinvault")

    icon_path = None
    for path in ["wolf.png", "wolf.ico"]:
        if os.path.exists(path):
            icon_path = path
            break

    if icon_path:
        app.setWindowIcon(QIcon(icon_path))

    window = AlinvaultWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
