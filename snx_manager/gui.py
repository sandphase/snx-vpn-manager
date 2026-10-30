#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
snx_manager.gui
Modern graphical user interface built with PyQt6 featuring Dark Glassmorphism.
Provides support for First-Run Wizard, responsive visual cards, shared settings management,
corporate profile bundle import/export, and integrated pre-flight diagnostics.
"""

import sys
import os
import fcntl
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QComboBox, QCheckBox, QRadioButton,
    QButtonGroup, QTabWidget, QScrollArea, QFrame, QDialog,
    QMessageBox, QTextEdit, QFileDialog, QProgressBar, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QColor, QKeyEvent

from snx_manager.core.config import (
    load_config, save_config, get_connection_by_id, export_bundle, import_bundle
)
from snx_manager.core.backend import VpnBackend
from snx_manager.core.doctor import run_diagnostics, format_doctor_report

MODERN_STYLE = """
QMainWindow {
    background-color: #0b0f17;
}
QWidget {
    color: #e2e8f0;
    font-family: 'Noto Sans', 'Segoe UI', 'Ubuntu', sans-serif;
    font-size: 13px;
}
QTabWidget::pane {
    border: 1px solid #232c3d;
    background: #111622;
    border-radius: 12px;
    margin-top: -1px;
}
QTabBar::tab {
    background: #161c28;
    color: #94a3b8;
    padding: 10px 24px;
    margin-right: 6px;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    font-weight: 700;
    font-size: 13px;
    border: 1px solid #1f2737;
    border-bottom: none;
}
QTabBar::tab:selected {
    background: #1e2638;
    color: #38bdf8;
    border: 1px solid #38bdf8;
    border-bottom: 2px solid #1e2638;
}
QTabBar::tab:hover:!selected {
    background: #1c2333;
    color: #f1f5f9;
}

QFrame.card {
    background-color: #161c28;
    border: 1px solid #242d3e;
    border-radius: 14px;
}
QFrame.card:hover {
    border-color: #38bdf8;
    background-color: #1a2232;
}
QFrame.cardActive {
    background-color: #112423;
    border: 2px solid #10b981;
    border-radius: 14px;
}

QPushButton {
    background-color: #1f283a;
    border: 1px solid #2d3a52;
    border-radius: 8px;
    color: #f1f5f9;
    padding: 8px 16px;
    font-weight: 700;
}
QPushButton:hover {
    background-color: #2b374e;
    border-color: #38bdf8;
}
QPushButton:pressed {
    background-color: #171f2d;
}
QPushButton.primary {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #38bdf8);
    border: none;
    color: #0b0f17;
    font-weight: 800;
}
QPushButton.primary:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0369a1, stop:1 #0284c7);
    color: #ffffff;
}
QPushButton.danger {
    background-color: rgba(239, 68, 68, 0.15);
    border: 1px solid rgba(239, 68, 68, 0.4);
    color: #f87171;
    font-weight: 700;
}
QPushButton.danger:hover {
    background-color: rgba(239, 68, 68, 0.3);
    color: #ffffff;
    border-color: #ef4444;
}

QLineEdit, QComboBox {
    background-color: #0d121c;
    border: 1px solid #232d3f;
    border-radius: 8px;
    color: #f8fafc;
    padding: 8px 12px;
    min-height: 20px;
    selection-background-color: #0284c7;
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid #38bdf8;
    background-color: #131a28;
}
QTextEdit {
    background-color: #090c12;
    border: 1px solid #1e2638;
    border-radius: 8px;
    color: #a5f3fc;
    font-family: 'JetBrains Mono', 'Consolas', monospace;
    font-size: 12px;
    padding: 10px;
}
QRadioButton, QCheckBox {
    spacing: 8px;
    color: #cbd5e1;
    font-weight: 600;
}
"""


class AsyncWorker(QThread):
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, action: str, profile_id: str = ""):
        super().__init__()
        self.action = action
        self.profile_id = profile_id
        self.backend = VpnBackend()

    def run(self):
        if self.action == "connect":
            ok, msg = self.backend.connect(self.profile_id)
            self.finished_signal.emit(ok, msg)
        elif self.action == "disconnect":
            ok = self.backend.disconnect()
            self.finished_signal.emit(ok, "VPN disconnected cleanly" if ok else "Failed to disconnect VPN")


class ConnectionEditDialog(QDialog):
    """Modal dialog for creating or editing a VPN site connection."""

    def __init__(self, parent=None, connection=None, shared_dns=""):
        super().__init__(parent)
        self.connection = connection or {}
        self.shared_dns = shared_dns
        self.setWindowTitle("Configure VPN Site" if connection else "New VPN Site")
        self.resize(560, 480)
        self.setStyleSheet(MODERN_STYLE)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(26, 26, 26, 26)

        title = QLabel("Connection Details")
        title.setFont(QFont("sans-serif", 15, QFont.Weight.Bold))
        layout.addWidget(title)

        layout.addWidget(QLabel("Site or Connection Name:"))
        self.txt_name = QLineEdit(self.connection.get("name", ""))
        self.txt_name.setPlaceholderText("e.g. Headquarters, Datacenter, Branch Office...")
        layout.addWidget(self.txt_name)

        layout.addWidget(QLabel("Gateway Address (IP or FQDN):"))
        self.txt_gateway = QLineEdit(self.connection.get("gateway", ""))
        self.txt_gateway.setPlaceholderText("e.g. 203.0.113.10 or vpn.company.com")
        layout.addWidget(self.txt_gateway)

        layout.addWidget(QLabel("Description or Notes (Optional):"))
        self.txt_desc = QLineEdit(self.connection.get("description", ""))
        self.txt_desc.setPlaceholderText("e.g. Primary production servers and database clusters")
        layout.addWidget(self.txt_desc)

        # DNS Box
        dns_frame = QFrame()
        dns_frame.setStyleSheet("""
            QFrame {
                background-color: #0e1420;
                border: 1px solid #232c3f;
                border-radius: 10px;
                padding: 12px;
            }
        """)
        dns_box = QVBoxLayout(dns_frame)
        dns_box.setSpacing(10)

        dns_label = QLabel("DNS Server Configuration for this Site:")
        dns_label.setFont(QFont("sans-serif", 11, QFont.Weight.Bold))
        dns_label.setStyleSheet("color: #38bdf8;")
        dns_box.addWidget(dns_label)

        self.rb_shared_dns = QRadioButton(f"Use global shared DNS ({self.shared_dns or 'None configured'})")
        self.rb_custom_dns = QRadioButton("Assign custom DNS servers for this connection")

        self.dns_group = QButtonGroup(self)
        self.dns_group.addButton(self.rb_shared_dns)
        self.dns_group.addButton(self.rb_custom_dns)
        dns_box.addWidget(self.rb_shared_dns)
        dns_box.addWidget(self.rb_custom_dns)

        self.txt_custom_dns = QLineEdit(self.connection.get("custom_dns", ""))
        self.txt_custom_dns.setPlaceholderText("e.g. 10.150.0.5, 10.0.0.10")
        dns_box.addWidget(self.txt_custom_dns)

        if self.connection.get("use_custom_dns"):
            self.rb_custom_dns.setChecked(True)
            self.txt_custom_dns.setEnabled(True)
        else:
            self.rb_shared_dns.setChecked(True)
            self.txt_custom_dns.setEnabled(False)

        self.rb_custom_dns.toggled.connect(lambda checked: self.txt_custom_dns.setEnabled(checked))
        layout.addWidget(dns_frame)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        btn_save = QPushButton("Save Site")
        btn_save.setProperty("class", "primary")
        btn_save.clicked.connect(self.save_data)
        btn_box.addWidget(btn_save)
        layout.addLayout(btn_box)

    def save_data(self):
        name = self.txt_name.text().strip()
        gateway = self.txt_gateway.text().strip()
        if not name or not gateway:
            QMessageBox.warning(self, "Required Fields", "Please specify both Connection Name and Gateway Address.")
            return

        self.connection["name"] = name
        self.connection["gateway"] = gateway
        self.connection["description"] = self.txt_desc.text().strip()
        self.connection["use_custom_dns"] = self.rb_custom_dns.isChecked()
        self.connection["custom_dns"] = self.txt_custom_dns.text().strip() if self.rb_custom_dns.isChecked() else ""
        if "id" not in self.connection:
            import re
            slug = re.sub(r'[^a-zA-Z0-9_]', '', name.lower().replace(' ', '_'))
            self.connection["id"] = slug or "site_" + gateway.replace('.', '_')
        self.accept()


class VpnManagerMainWindow(QMainWindow):
    """Main window for the graphical VPN manager."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SNX VPN Manager — Check Point Client")
        self.setMinimumSize(960, 700)
        self.resize(960, 700)
        self.setStyleSheet(MODERN_STYLE)

        self.backend = VpnBackend()
        self.config = load_config()

        self.center_window()
        self.init_ui()

        # Status polling timer (every 3 seconds)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_status)
        self.timer.start(3000)
        self.refresh_status()

        # Check for first-time launch without profiles
        QTimer.singleShot(200, self.check_first_run)

    def center_window(self):
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = (geo.width() - self.width()) // 2
            y = (geo.height() - self.height()) // 2
            self.move(x, y)

    def check_first_run(self):
        if not self.config.get("connections"):
            reply = QMessageBox.question(
                self,
                "Welcome to SNX VPN Manager",
                "No VPN connection profiles are currently configured.\n\n"
                "Would you like to add your first VPN Gateway profile now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.add_connection()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(14)

        # Header Bar
        header = QFrame()
        header.setObjectName("mainHeader")
        header.setStyleSheet("""
            QFrame#mainHeader {
                background-color: #121724;
                border: 1px solid #1f2737;
                border-radius: 12px;
                padding: 10px 16px;
            }
            QFrame#mainHeader QLabel {
                border: none;
                background: transparent;
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 8, 10, 8)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        app_title = QLabel("🛡️ SNX Check Point VPN Manager")
        app_title.setFont(QFont("sans-serif", 16, QFont.Weight.Bold))
        app_title.setStyleSheet("color: #ffffff; letter-spacing: -0.5px;")
        title_box.addWidget(app_title)

        self.lbl_subtitle = QLabel("Profile manager & snx-rs orchestrator • Shortcuts: [1-9] Connect / [D] Disconnect / [Esc] Close")
        self.lbl_subtitle.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: 500;")
        title_box.addWidget(self.lbl_subtitle)
        header_layout.addLayout(title_box)

        header_layout.addStretch()

        self.status_badge = QLabel("⚪ Checking...")
        self.status_badge.setStyleSheet("""
            background-color: #1a2232;
            color: #94a3b8;
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: 700;
            border: 1px solid #273348;
        """)
        header_layout.addWidget(self.status_badge)

        self.btn_disconnect = QPushButton("🔌 Disconnect (D)")
        self.btn_disconnect.setProperty("class", "danger")
        self.btn_disconnect.clicked.connect(self.do_disconnect)
        header_layout.addWidget(self.btn_disconnect)

        self.btn_close = QPushButton("✕ Close (Esc)")
        self.btn_close.clicked.connect(self.close)
        header_layout.addWidget(self.btn_close)

        main_layout.addWidget(header)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: rgba(255, 255, 255, 0.05);
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background-color: #38bdf8;
                border-radius: 2px;
            }
        """)
        self.progress_bar.hide()
        main_layout.addWidget(self.progress_bar)

        # Tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.tab_connections = QWidget()
        self.init_connections_tab()
        self.tabs.addTab(self.tab_connections, "🌐 Connections (Sites)")

        self.tab_shared = QWidget()
        self.init_shared_tab()
        self.tabs.addTab(self.tab_shared, "⚙️ Shared Settings")

        self.tab_diag = QWidget()
        self.init_diag_tab()
        self.tabs.addTab(self.tab_diag, "📊 Diagnostics & Logs")

        # Footer
        self.lbl_footer_status = QLabel("Ready. Click a site card to connect or press its index number.")
        self.lbl_footer_status.setStyleSheet("color: #64748b; font-size: 12px; font-weight: 500;")
        main_layout.addWidget(self.lbl_footer_status)

    def init_connections_tab(self):
        layout = QVBoxLayout(self.tab_connections)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        top_bar = QHBoxLayout()
        desc = QLabel("Choose a site to connect immediately, or manage your connection profiles:")
        desc.setStyleSheet("color: #cbd5e1; font-weight: 600;")
        top_bar.addWidget(desc)
        top_bar.addStretch()

        btn_import = QPushButton("📥 Import Bundle")
        btn_import.clicked.connect(self.import_profiles_file)
        top_bar.addWidget(btn_import)

        btn_export = QPushButton("📤 Export")
        btn_export.clicked.connect(self.export_profiles_file)
        top_bar.addWidget(btn_export)

        btn_add = QPushButton("➕ New Site")
        btn_add.setProperty("class", "primary")
        btn_add.clicked.connect(self.add_connection)
        top_bar.addWidget(btn_add)
        layout.addLayout(top_bar)

        # Scroll area for cards
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background: transparent; border: none;")
        self.conn_container = QWidget()
        self.conn_layout = QHBoxLayout(self.conn_container)
        self.conn_layout.setSpacing(16)
        self.conn_layout.setContentsMargins(4, 4, 4, 4)
        self.scroll_area.setWidget(self.conn_container)
        layout.addWidget(self.scroll_area)

        self.render_connection_cards()

    def render_connection_cards(self):
        while self.conn_layout.count():
            item = self.conn_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        st = self.backend.get_status()
        active_id = st.get("active_id")
        current_gw = st.get("gateway") or ""
        shared_dns = self.config.get("shared", {}).get("dns_servers", "")
        shared_user = self.config.get("shared", {}).get("user_name", "")

        connections = self.config.get("connections", [])

        if not connections:
            empty_box = QVBoxLayout()
            empty_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_empty = QLabel("No sites configured yet. Click '➕ New Site' or '📥 Import Bundle' to get started.")
            lbl_empty.setStyleSheet("color: #64748b; font-size: 14px; padding: 40px;")
            empty_box.addWidget(lbl_empty)
            self.conn_layout.addLayout(empty_box)
            return

        palette_colors = [
            QColor(56, 189, 248),   # Cyan
            QColor(16, 185, 129),   # Emerald
            QColor(168, 85, 247),   # Purple
            QColor(251, 146, 60),   # Orange
            QColor(236, 72, 153),   # Pink
        ]

        for idx, conn in enumerate(connections):
            cid = conn.get("id")
            gw = conn.get("gateway")
            is_active = (st.get("connected") and (cid == active_id or gw == current_gw))

            accent = palette_colors[idx % len(palette_colors)]

            card = QFrame()
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            card.setProperty("class", "cardActive" if is_active else "card")

            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(18, 18, 18, 18)
            card_layout.setSpacing(10)

            # Top row
            top_row = QHBoxLayout()
            lbl_tag = QLabel(f"SITE #{idx+1}")
            lbl_tag.setStyleSheet(f"""
                background-color: rgba({accent.red()}, {accent.green()}, {accent.blue()}, 0.18);
                color: {accent.name()};
                font-size: 11px;
                font-weight: 800;
                padding: 4px 10px;
                border-radius: 6px;
                border: 1px solid rgba({accent.red()}, {accent.green()}, {accent.blue()}, 0.35);
            """)
            top_row.addWidget(lbl_tag)
            top_row.addStretch()

            if is_active:
                lbl_status = QLabel("● ACTIVE NOW")
                lbl_status.setStyleSheet("""
                    background-color: rgba(16, 185, 129, 0.25);
                    color: #10b981;
                    font-size: 11px;
                    font-weight: 800;
                    padding: 4px 10px;
                    border-radius: 6px;
                    border: 1px solid #10b981;
                """)
            else:
                lbl_status = QLabel("○ AVAILABLE")
                lbl_status.setStyleSheet("""
                    background-color: rgba(148, 163, 184, 0.1);
                    color: #94a3b8;
                    font-size: 11px;
                    font-weight: 700;
                    padding: 4px 8px;
                    border-radius: 6px;
                """)
            top_row.addWidget(lbl_status)
            card_layout.addLayout(top_row)

            # Title
            title_box = QVBoxLayout()
            title_box.setSpacing(2)
            lbl_name = QLabel(conn.get("name", cid))
            lbl_name.setStyleSheet("font-size: 21px; font-weight: 800; color: #ffffff;")
            title_box.addWidget(lbl_name)

            lbl_desc = QLabel(conn.get("description", "Corporate VPN Gateway"))
            lbl_desc.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: 500;")
            title_box.addWidget(lbl_desc)
            card_layout.addLayout(title_box)

            # Specs Box
            specs_box = QFrame()
            specs_box.setObjectName("specsBox")
            specs_box.setStyleSheet("""
                QFrame#specsBox {
                    background-color: rgba(10, 15, 24, 0.7);
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 10px;
                }
                QFrame#specsBox QLabel {
                    border: none;
                    background: transparent;
                }
            """)
            specs_layout = QVBoxLayout(specs_box)
            specs_layout.setContentsMargins(12, 10, 12, 10)
            specs_layout.setSpacing(6)

            dns_info = conn.get("custom_dns") if conn.get("use_custom_dns") else shared_dns
            dns_type = "⚡ Custom DNS" if conn.get("use_custom_dns") else "🌐 Shared DNS"

            specs = [
                ("🌐 Gateway", gw, True),
                (dns_type, dns_info or "Default", False),
                ("👤 User", shared_user or "Not set", False),
            ]

            for label, val, is_hl in specs:
                r_layout = QHBoxLayout()
                r_layout.setContentsMargins(0, 0, 0, 0)
                lk = QLabel(label)
                lk.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 600;")
                lv = QLabel(str(val))
                if is_hl:
                    lv.setStyleSheet(f"color: {accent.name()}; font-size: 13px; font-weight: 800; font-family: monospace;")
                else:
                    lv.setStyleSheet("color: #f1f5f9; font-size: 11px; font-weight: 600;")
                r_layout.addWidget(lk)
                r_layout.addStretch()
                r_layout.addWidget(lv)
                specs_layout.addLayout(r_layout)

            card_layout.addWidget(specs_box)
            card_layout.addStretch()

            # Connect Button
            btn_conn = QPushButton(f"Connect to {conn.get('name')}" if not is_active else f"Reconnect to {conn.get('name')}")
            btn_conn.setFixedHeight(42)
            btn_conn.setCursor(Qt.CursorShape.PointingHandCursor)
            if is_active:
                btn_conn.setStyleSheet(f"""
                    QPushButton {{
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba({accent.red()}, {accent.green()}, {accent.blue()}, 0.35), stop:1 rgba({accent.red()}, {accent.green()}, {accent.blue()}, 0.55));
                        color: #ffffff;
                        font-weight: 800;
                        font-size: 13px;
                        border: 1px solid {accent.name()};
                        border-radius: 8px;
                    }}
                """)
            else:
                btn_conn.setStyleSheet(f"""
                    QPushButton {{
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba({accent.red()}, {accent.green()}, {accent.blue()}, 0.9), stop:1 rgba({accent.red()}, {accent.green()}, {accent.blue()}, 1.0));
                        color: #070a0f;
                        font-weight: 800;
                        font-size: 13px;
                        border: none;
                        border-radius: 8px;
                    }}
                    QPushButton:hover {{
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba({accent.red()}, {accent.green()}, {accent.blue()}, 1.0), stop:1 rgba({min(255, accent.red()+35)}, {min(255, accent.green()+35)}, {min(255, accent.blue()+35)}, 1.0));
                        color: #000000;
                    }}
                """)
            btn_conn.clicked.connect(lambda checked, c_id=cid: self.do_connect(c_id))
            card_layout.addWidget(btn_conn)

            # Shortcut hint
            lbl_hint = QLabel(f"Press Key [ {idx+1} ]")
            lbl_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_hint.setStyleSheet("color: #64748b; font-size: 11px; font-weight: 600;")
            card_layout.addWidget(lbl_hint)

            # Actions Row
            actions_row = QHBoxLayout()
            actions_row.setSpacing(8)

            btn_edit = QPushButton("✏️ Edit")
            btn_edit.setFixedHeight(34)
            btn_edit.clicked.connect(lambda checked, c=conn: self.edit_connection(c))
            actions_row.addWidget(btn_edit)

            btn_del = QPushButton("🗑️")
            btn_del.setToolTip("Delete connection")
            btn_del.setFixedSize(36, 34)
            btn_del.clicked.connect(lambda checked, c_id=cid: self.delete_connection(c_id))
            actions_row.addWidget(btn_del)

            card_layout.addLayout(actions_row)
            self.conn_layout.addWidget(card)

    def init_shared_tab(self):
        layout = QVBoxLayout(self.tab_shared)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        banner = QLabel(
            "📌 <b>Shared Settings (Global):</b><br>"
            "These fields apply to all connection profiles that do not define custom overrides.<br>"
            "When corporate DNS servers or credentials change, update them here once to synchronize everywhere."
        )
        banner.setWordWrap(True)
        banner.setStyleSheet("""
            color: #cbd5e1;
            background-color: #161c28;
            padding: 14px 18px;
            border-radius: 10px;
            border: 1px solid #232d3f;
            font-size: 12px;
            line-height: 1.4;
        """)
        layout.addWidget(banner)

        form_frame = QFrame()
        form_frame.setObjectName("sharedForm")
        form_frame.setStyleSheet("""
            QFrame#sharedForm {
                background-color: #121724;
                border: 1px solid #1f2737;
                border-radius: 12px;
                padding: 16px;
            }
            QLabel {
                border: none;
                background: transparent;
                color: #f1f5f9;
                font-size: 13px;
                font-weight: 700;
            }
        """)
        form_layout = QVBoxLayout(form_frame)
        form_layout.setSpacing(12)

        shared = self.config.get("shared", {})

        form_layout.addWidget(QLabel("🌐 Shared DNS Servers (comma-separated):"))
        dns_input_box = QHBoxLayout()
        self.txt_shared_dns = QLineEdit(shared.get("dns_servers", ""))
        self.txt_shared_dns.setPlaceholderText("e.g. 10.0.0.10, 10.0.0.11")
        dns_input_box.addWidget(self.txt_shared_dns)

        btn_restore_dns = QPushButton("Reset Example")
        btn_restore_dns.clicked.connect(lambda: self.txt_shared_dns.setText("10.0.0.10, 10.0.0.11"))
        dns_input_box.addWidget(btn_restore_dns)
        form_layout.addLayout(dns_input_box)

        form_layout.addWidget(QLabel("🏢 Search Domains (Split-DNS):"))
        self.txt_search_domains = QLineEdit(shared.get("search_domains", ""))
        self.txt_search_domains.setPlaceholderText("e.g. corp.internal, company.com")
        form_layout.addWidget(self.txt_search_domains)

        form_layout.addWidget(QLabel("👤 VPN Username:"))
        self.txt_shared_user = QLineEdit(shared.get("user_name", ""))
        self.txt_shared_user.setPlaceholderText("Your corporate user identity")
        form_layout.addWidget(self.txt_shared_user)

        form_layout.addWidget(QLabel("🔑 VPN Password:"))
        pwd_box = QHBoxLayout()
        self.txt_shared_pwd = QLineEdit(shared.get("password", ""))
        self.txt_shared_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        pwd_box.addWidget(self.txt_shared_pwd)

        self.btn_show_pwd = QPushButton("👁️ Show")
        self.btn_show_pwd.setCheckable(True)
        self.btn_show_pwd.toggled.connect(self.toggle_pwd_visibility)
        pwd_box.addWidget(self.btn_show_pwd)
        form_layout.addLayout(pwd_box)

        adv_box = QHBoxLayout()
        t_box = QVBoxLayout()
        t_box.addWidget(QLabel("Tunnel Type:"))
        self.cb_tunnel = QComboBox()
        self.cb_tunnel.addItems(["ssl", "ipsec"])
        self.cb_tunnel.setCurrentText(shared.get("tunnel_type", "ssl"))
        t_box.addWidget(self.cb_tunnel)
        adv_box.addLayout(t_box)

        l_box = QVBoxLayout()
        l_box.addWidget(QLabel("Login Method:"))
        self.cb_login = QComboBox()
        self.cb_login.addItems(["vpn", "standard"])
        self.cb_login.setCurrentText(shared.get("login_type", "vpn"))
        l_box.addWidget(self.cb_login)
        adv_box.addLayout(l_box)
        form_layout.addLayout(adv_box)

        self.chk_ignore_cert = QCheckBox("Ignore TLS certificate warnings (Required if gateway SAN lacks internal IP match)")
        self.chk_ignore_cert.setChecked(shared.get("ignore_server_cert", True))
        form_layout.addWidget(self.chk_ignore_cert)

        layout.addWidget(form_frame)

        btn_save_shared = QPushButton("💾 Save Shared Settings")
        btn_save_shared.setProperty("class", "primary")
        btn_save_shared.setFixedHeight(42)
        btn_save_shared.clicked.connect(self.save_shared_fields)
        layout.addWidget(btn_save_shared)
        layout.addStretch()

    def init_diag_tab(self):
        layout = QVBoxLayout(self.tab_diag)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        btn_row = QHBoxLayout()
        btn_doctor = QPushButton("🩺 System Diagnostics (Doctor)")
        btn_doctor.clicked.connect(self.run_doctor_test)
        btn_row.addWidget(btn_doctor)

        btn_routes = QPushButton("🛣️ View Kernel Routes")
        btn_routes.clicked.connect(self.check_routes)
        btn_row.addWidget(btn_routes)

        btn_logs = QPushButton("📜 View Latest Logs")
        btn_logs.clicked.connect(self.load_snx_logs)
        btn_row.addWidget(btn_logs)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.txt_output = QTextEdit()
        self.txt_output.setReadOnly(True)
        self.txt_output.setPlaceholderText("Diagnostic results and system trace output will appear here...")
        layout.addWidget(self.txt_output)

    def toggle_pwd_visibility(self, checked):
        if checked:
            self.txt_shared_pwd.setEchoMode(QLineEdit.EchoMode.Normal)
            self.btn_show_pwd.setText("🔒 Hide")
        else:
            self.txt_shared_pwd.setEchoMode(QLineEdit.EchoMode.Password)
            self.btn_show_pwd.setText("👁️ Show")

    def save_shared_fields(self):
        shared = self.config.setdefault("shared", {})
        shared["dns_servers"] = self.txt_shared_dns.text().strip()
        shared["search_domains"] = self.txt_search_domains.text().strip()
        shared["user_name"] = self.txt_shared_user.text().strip()
        shared["password"] = self.txt_shared_pwd.text().strip()
        shared["tunnel_type"] = self.cb_tunnel.currentText()
        shared["login_type"] = self.cb_login.currentText()
        shared["ignore_server_cert"] = self.chk_ignore_cert.isChecked()

        save_config(self.config)
        self.render_connection_cards()
        self.lbl_footer_status.setText("✅ Shared settings saved successfully.")
        self.lbl_footer_status.setStyleSheet("color: #10b981; font-weight: 700;")
        QMessageBox.information(self, "Shared Settings", "Global shared configuration saved successfully.")

    def add_connection(self):
        shared_dns = self.config.get("shared", {}).get("dns_servers", "")
        dlg = ConnectionEditDialog(self, shared_dns=shared_dns)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.config.setdefault("connections", []).append(dlg.connection)
            save_config(self.config)
            self.render_connection_cards()

    def edit_connection(self, connection):
        shared_dns = self.config.get("shared", {}).get("dns_servers", "")
        dlg = ConnectionEditDialog(self, connection=connection.copy(), shared_dns=shared_dns)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            for idx, c in enumerate(self.config.get("connections", [])):
                if c.get("id") == connection.get("id"):
                    self.config["connections"][idx] = dlg.connection
                    break
            save_config(self.config)
            self.render_connection_cards()

    def delete_connection(self, conn_id):
        conn = get_connection_by_id(self.config, conn_id)
        name = conn.get("name", conn_id) if conn else conn_id
        reply = QMessageBox.question(
            self, "Confirm Deletion",
            f"Are you sure you want to delete the site profile '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.config["connections"] = [c for c in self.config.get("connections", []) if c.get("id") != conn_id]
            save_config(self.config)
            self.render_connection_cards()

    def import_profiles_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Import Profiles JSON", str(Path.home()), "JSON Files (*.json)")
        if file_path:
            if import_bundle(self.config, Path(file_path)):
                self.config = load_config()
                self.render_connection_cards()
                QMessageBox.information(self, "Import", "Profiles imported successfully.")
            else:
                QMessageBox.critical(self, "Error", "Failed to import the specified profile bundle.")

    def export_profiles_file(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Profiles JSON", str(Path.home() / "snx-profiles-bundle.json"), "JSON Files (*.json)")
        if file_path:
            if export_bundle(self.config, Path(file_path)):
                QMessageBox.information(self, "Export", "Profiles exported successfully.")
            else:
                QMessageBox.critical(self, "Error", "Failed to export profile bundle.")

    def do_connect(self, conn_id):
        conn = get_connection_by_id(self.config, conn_id)
        name = conn.get("name", conn_id) if conn else conn_id
        self.progress_bar.show()
        self.status_badge.setText("⏳ Connecting...")
        self.lbl_footer_status.setText(f"Connecting to {name}... Establishing secure tunnel.")
        self.lbl_footer_status.setStyleSheet("color: #38bdf8; font-weight: 700;")
        self.worker = AsyncWorker(action="connect", profile_id=conn_id)
        self.worker.finished_signal.connect(self.on_worker_finished)
        self.worker.start()

    def do_disconnect(self):
        self.progress_bar.show()
        self.status_badge.setText("⏳ Disconnecting...")
        self.lbl_footer_status.setText("Disconnecting VPN tunnel...")
        self.worker = AsyncWorker(action="disconnect")
        self.worker.finished_signal.connect(self.on_worker_finished)
        self.worker.start()

    def on_worker_finished(self, success, message):
        self.progress_bar.hide()
        self.refresh_status()
        self.render_connection_cards()
        if success:
            self.lbl_footer_status.setText(f"✅ {message}")
            self.lbl_footer_status.setStyleSheet("color: #10b981; font-weight: 700;")
            if self.tabs.currentIndex() == 0:
                QTimer.singleShot(2000, self.close)
        else:
            self.lbl_footer_status.setText(f"❌ {message}")
            self.lbl_footer_status.setStyleSheet("color: #f87171; font-weight: 700;")
            QMessageBox.critical(self, "Connection Status", message)

    def refresh_status(self):
        st = self.backend.get_status()
        if st.get("connected"):
            name = st.get("active_name") or "VPN Connected"
            ip = st.get("ip") or ""
            self.status_badge.setText(f"🟢 {name.upper()} ({ip})")
            self.status_badge.setStyleSheet("""
                background-color: rgba(16, 185, 129, 0.2);
                color: #10b981;
                padding: 8px 16px;
                border-radius: 20px;
                font-weight: 800;
                border: 1px solid #10b981;
            """)
            self.btn_disconnect.setEnabled(True)
        else:
            self.status_badge.setText("⚪ DISCONNECTED")
            self.status_badge.setStyleSheet("""
                background-color: #161c28;
                color: #94a3b8;
                padding: 8px 16px;
                border-radius: 20px;
                font-weight: 700;
                border: 1px solid #232d3f;
            """)
            self.btn_disconnect.setEnabled(False)

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.close()
        elif Qt.Key.Key_1 <= key <= Qt.Key.Key_9:
            idx = key - Qt.Key.Key_1
            connections = self.config.get("connections", [])
            if 0 <= idx < len(connections):
                self.do_connect(connections[idx]["id"])
        elif key == Qt.Key.Key_D:
            if self.btn_disconnect.isEnabled():
                self.do_disconnect()
        else:
            super().keyPressEvent(event)

    def run_doctor_test(self):
        self.txt_output.clear()
        subnets = [c.get("expected_subnet", "") for c in self.config.get("connections", []) if c.get("expected_subnet")]
        rep = run_diagnostics(subnets)
        self.txt_output.append(format_doctor_report(rep))

    def check_routes(self):
        self.txt_output.clear()
        self.txt_output.append("=== Active Linux Kernel Routes ===\n")
        import subprocess
        try:
            out = subprocess.check_output(["ip", "route", "show"], text=True)
            self.txt_output.append(out)
        except Exception as e:
            self.txt_output.append(f"Error querying routes: {e}")

    def load_snx_logs(self):
        self.txt_output.clear()
        self.txt_output.append("=== Last 40 lines of /var/log/snx-rs.log ===\n")
        import subprocess
        try:
            out = subprocess.check_output(["sudo", "-n", "tail", "-n", "40", "/var/log/snx-rs.log"], text=True)
            self.txt_output.append(out)
        except Exception as e:
            self.txt_output.append(f"Error reading log file: {e}")


def launch_gui():
    lock_file = "/tmp/snx-manager.lock"
    try:
        lock_fd = open(lock_file, "w")
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (IOError, BlockingIOError):
        sys.exit(0)

    os.environ.setdefault("QT_QPA_PLATFORM", "wayland;xcb")
    app = QApplication(sys.argv)
    app.setApplicationName("SNX VPN Manager")

    window = VpnManagerMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    launch_gui()
