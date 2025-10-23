"""
Main GUI Application - Stunning Modern Interface
"""

import sys
import asyncio
import cv2
import numpy as np
import pyaudio
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from client_core import ScalableCommClient

class VideoWidget(QLabel):
    """Custom widget for displaying video streams"""
    
    def __init__(self, username=""):
        super().__init__()
        self.username = username
        self.setMinimumSize(320, 240)
        self.setMaximumSize(640, 480)
        self.setStyleSheet("""
            QLabel {
                background-color: #1e1e1e;
                border: 2px solid #3a3a3a;
                border-radius: 10px;
            }
        """)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText("No Video" if not username else username)
        self.setScaledContents(False)
    
    def update_frame(self, frame):
        """Update video frame"""
        try:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            
            pixmap = QPixmap.fromImage(qt_image)
            scaled_pixmap = pixmap.scaled(
                self.size(), 
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.setPixmap(scaled_pixmap)
        except Exception as e:
            print(f"Frame update error: {e}")

class ChatWidget(QWidget):
    """Modern chat interface"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(10)
        
        # Chat display
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("""
            QTextEdit {
                background-color: #2b2b2b;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 10px;
                font-size: 14px;
                font-family: 'Segoe UI', Arial;
            }
        """)
        
        # Input area
        input_layout = QHBoxLayout()
        
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Type a message...")
        self.message_input.setStyleSheet("""
            QLineEdit {
                background-color: #3a3a3a;
                color: #ffffff;
                border: 2px solid #4a4a4a;
                border-radius: 20px;
                padding: 10px 15px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 2px solid #0078d4;
            }
        """)
        
        self.send_button = QPushButton("Send")
        self.send_button.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 20px;
                padding: 10px 25px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #005a9e;
            }
            QPushButton:pressed {
                background-color: #004578;
            }
        """)
        
        input_layout.addWidget(self.message_input)
        input_layout.addWidget(self.send_button)
        
        layout.addWidget(self.chat_display)
        layout.addLayout(input_layout)
        
        self.setLayout(layout)
    
    def add_message(self, username, message):
        """Add message to chat"""
        timestamp = QTime.currentTime().toString("HH:mm")
        self.chat_display.append(
            f"<span style='color: #888;'>[{timestamp}]</span> "
            f"<b style='color: #0078d4;'>{username}:</b> {message}"
        )
    
    def add_system_message(self, message):
        """Add system message"""
        self.chat_display.append(f"<i style='color: #888;'>🔔 {message}</i>")

class MainWindow(QMainWindow):
    """Main application window"""
    
    # Signals for thread-safe GUI updates
    video_signal = pyqtSignal(str, object)
    audio_signal = pyqtSignal(str, bytes)
    chat_signal = pyqtSignal(str, str)
    users_signal = pyqtSignal(list)
    
    def __init__(self):
        super().__init__()
        
        # Client
        self.client = None
        self.audio_player = None
        self.audio_stream = None
        
        # Video widgets mapping
        self.video_widgets_map = {}  # username -> widget
        self.my_video_widget = None  # Widget for own video
        self.my_username = None
        
        # Connect signals
        self.video_signal.connect(self.handle_video_frame_gui)
        self.audio_signal.connect(self.handle_audio_chunk_gui)
        self.chat_signal.connect(self.handle_chat_message_gui)
        self.users_signal.connect(self.handle_user_list_gui)
        
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("ScaleComm - LAN Communication Platform")
        self.setGeometry(100, 100, 1400, 900)
        
        # Dark theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QWidget {
                color: #ffffff;
                font-family: 'Segoe UI', Arial;
            }
        """)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout()
        
        # Left panel - Video grid
        left_panel = self.create_video_panel()
        
        # Right panel - Chat and controls
        right_panel = self.create_right_panel()
        
        main_layout.addWidget(left_panel, 3)
        main_layout.addWidget(right_panel, 1)
        
        central_widget.setLayout(main_layout)
        
        # Menu bar
        self.create_menu_bar()
        
        # Status bar
        self.statusBar().setStyleSheet("""
            QStatusBar {
                background-color: #2b2b2b;
                color: #ffffff;
                font-size: 12px;
            }
        """)
        self.statusBar().showMessage("Ready to connect")
        
        # Initialize audio player
        self.init_audio_player()
    
    def create_video_panel(self):
        """Create video grid panel"""
        panel = QWidget()
        layout = QVBoxLayout()
        
        # Scroll area for video grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #1e1e1e;
            }
        """)
        
        # Video container
        video_container = QWidget()
        self.video_grid = QGridLayout()
        self.video_grid.setSpacing(10)
        
        # Create 9 video widgets (3x3 grid)
        self.video_widgets = []
        for i in range(9):
            video_widget = VideoWidget()
            self.video_widgets.append(video_widget)
            row = i // 3
            col = i % 3
            self.video_grid.addWidget(video_widget, row, col)
        
        video_container.setLayout(self.video_grid)
        scroll.setWidget(video_container)
        
        # Control buttons
        control_layout = QHBoxLayout()
        control_layout.setSpacing(15)
        
        self.video_btn = QPushButton("📹 Video")
        self.audio_btn = QPushButton("🎤 Audio")
        self.screen_btn = QPushButton("🖥️ Screen")
        
        for btn in [self.video_btn, self.audio_btn, self.screen_btn]:
            btn.setCheckable(True)
            btn.setMinimumHeight(50)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #3a3a3a;
                    border: none;
                    border-radius: 25px;
                    padding: 12px 20px;
                    font-size: 16px;
                    font-weight: bold;
                }
                QPushButton:checked {
                    background-color: #0078d4;
                }
                QPushButton:hover {
                    background-color: #4a4a4a;
                }
                QPushButton:checked:hover {
                    background-color: #005a9e;
                }
            """)
            control_layout.addWidget(btn)
        
        # Connect button signals
        self.video_btn.toggled.connect(self.toggle_video)
        self.audio_btn.toggled.connect(self.toggle_audio)
        self.screen_btn.toggled.connect(self.toggle_screen)
        
        layout.addWidget(scroll)
        layout.addLayout(control_layout)
        
        panel.setLayout(layout)
        return panel
    
    def create_right_panel(self):
        """Create right panel with chat and user list"""
        panel = QWidget()
        layout = QVBoxLayout()
        
        # User list
        user_label = QLabel("Connected Users")
        user_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                padding: 10px;
                color: #0078d4;
            }
        """)
        
        self.user_list = QListWidget()
        self.user_list.setStyleSheet("""
            QListWidget {
                background-color: #2b2b2b;
                border: none;
                border-radius: 8px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 5px;
                margin: 2px;
            }
            QListWidget::item:hover {
                background-color: #3a3a3a;
            }
        """)
        
        # Chat widget
        self.chat_widget = ChatWidget()
        
        # Connect chat send
        self.chat_widget.send_button.clicked.connect(self.send_chat)
        self.chat_widget.message_input.returnPressed.connect(self.send_chat)
        
        # File sharing button
        self.file_btn = QPushButton("📎 Share File")
        self.file_btn.setMinimumHeight(40)
        self.file_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                border: none;
                border-radius: 20px;
                padding: 12px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #005a9e;
            }
        """)
        self.file_btn.clicked.connect(self.share_file)
        
        layout.addWidget(user_label)
        layout.addWidget(self.user_list, 1)
        layout.addWidget(self.chat_widget, 3)
        layout.addWidget(self.file_btn)
        
        panel.setLayout(layout)
        return panel
    
    def create_menu_bar(self):
        """Create menu bar"""
        menubar = self.menuBar()
        menubar.setStyleSheet("""
            QMenuBar {
                background-color: #2b2b2b;
                color: #ffffff;
                padding: 5px;
            }
            QMenuBar::item:selected {
                background-color: #3a3a3a;
            }
            QMenu {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QMenu::item:selected {
                background-color: #0078d4;
            }
        """)
        
        # Connection menu
        connection_menu = menubar.addMenu("Connection")
        
        connect_action = QAction("Connect to Server", self)
        connect_action.setShortcut("Ctrl+N")
        connect_action.triggered.connect(self.show_connect_dialog)
        connection_menu.addAction(connect_action)
        
        disconnect_action = QAction("Disconnect", self)
        disconnect_action.setShortcut("Ctrl+D")
        disconnect_action.triggered.connect(self.disconnect)
        connection_menu.addAction(disconnect_action)
        
        connection_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        connection_menu.addAction(exit_action)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def init_audio_player(self):
        """Initialize audio player for playback"""
        try:
            self.audio_player = pyaudio.PyAudio()
            self.audio_stream = self.audio_player.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                output=True,
                frames_per_buffer=1024
            )
        except Exception as e:
            print(f"Audio player init error: {e}")
    
    def show_connect_dialog(self):
        """Show connection dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Connect to Server")
        dialog.setModal(True)
        dialog.setFixedSize(400, 200)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
            }
            QLabel {
                color: #ffffff;
                font-size: 14px;
            }
            QLineEdit {
                background-color: #3a3a3a;
                color: #ffffff;
                border: 2px solid #4a4a4a;
                border-radius: 5px;
                padding: 8px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 2px solid #0078d4;
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #005a9e;
            }
        """)
        
        layout = QFormLayout()
        layout.setSpacing(15)
        
        server_input = QLineEdit("192.168.1.5")
        username_input = QLineEdit()
        username_input.setPlaceholderText("Enter your name")
        
        layout.addRow("Server IP:", server_input)
        layout.addRow("Username:", username_input)
        
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        
        layout.addRow(button_box)
        dialog.setLayout(layout)
        
        if dialog.exec():
            server_ip = server_input.text().strip()
            username = username_input.text().strip()
            
            if server_ip and username:
                self.connect_to_server(server_ip, username)
            else:
                QMessageBox.warning(self, "Invalid Input", "Please enter both server IP and username")
    
    def connect_to_server(self, server_ip, username):
        """Connect to server"""
        self.my_username = username
        self.client = ScalableCommClient(server_ip)
        
        # Set up callbacks
        self.client.on_video_frame = lambda sender, frame: self.video_signal.emit(sender, frame)
        self.client.on_audio_chunk = lambda sender, chunk: self.audio_signal.emit(sender, chunk)
        self.client.on_chat_message = lambda sender, msg: self.chat_signal.emit(sender, msg)
        self.client.on_user_list = lambda users: self.users_signal.emit(users)
        
        # Reserve first video slot for own video
        self.my_video_widget = self.video_widgets[0]
        self.my_video_widget.username = username
        self.my_video_widget.setText(f"{username} (You)")
        self.my_video_widget.setStyleSheet("""
            QLabel {
                background-color: #1e1e1e;
                border: 3px solid #0078d4;
                border-radius: 10px;
            }
        """)
        
        # Connect in thread
        def connect_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self.client.connect(username))
            
            if result:
                self.statusBar().showMessage(f"✅ Connected as {username}")
                self.chat_widget.add_system_message(f"Connected to {server_ip}")
            else:
                self.statusBar().showMessage("❌ Connection failed")
                QMessageBox.critical(self, "Connection Failed", "Could not connect to server")
        
        import threading
        threading.Thread(target=connect_thread, daemon=True).start()
    
    def disconnect(self):
        """Disconnect from server"""
        if self.client:
            self.client.disconnect()
            self.client = None
            self.statusBar().showMessage("Disconnected")
            self.chat_widget.add_system_message("Disconnected from server")
            
            # Clear video widgets
            for widget in self.video_widgets:
                widget.clear()
                widget.username = ""
                widget.setText("No Video")
                widget.setStyleSheet("""
                    QLabel {
                        background-color: #1e1e1e;
                        border: 2px solid #3a3a3a;
                        border-radius: 10px;
                    }
                """)
            
            self.video_widgets_map.clear()
            self.my_video_widget = None
            self.my_username = None
    
    def toggle_video(self, checked):
        """Toggle video streaming"""
        if not self.client or not self.client.connected:
            self.video_btn.setChecked(False)
            QMessageBox.warning(self, "Not Connected", "Please connect to server first")
            return
        
        if checked:
            # Start client video streaming (this also shows preview via callback)
            success = self.client.start_video(0)
            
            if not success:
                self.video_btn.setChecked(False)
                QMessageBox.warning(
                    self, 
                    "Camera Error", 
                    "Failed to start camera.\n\n"
                    "Make sure:\n"
                    "• Camera is not in use by another app\n"
                    "• You have camera permissions"
                )
        else:
            self.client.stop_video()
    
    def toggle_audio(self, checked):
        """Toggle audio streaming"""
        if not self.client or not self.client.connected:
            self.audio_btn.setChecked(False)
            QMessageBox.warning(self, "Not Connected", "Please connect to server first")
            return
        
        if checked:
            self.client.start_audio()
        else:
            self.client.stop_audio()
    
    def toggle_screen(self, checked):
        """Toggle screen sharing"""
        if not self.client or not self.client.connected:
            self.screen_btn.setChecked(False)
            QMessageBox.warning(self, "Not Connected", "Please connect to server first")
            return
        
        if checked:
            self.client.start_screen_share()
        else:
            self.client.stop_screen_share()
    
    def send_chat(self):
        """Send chat message"""
        if not self.client or not self.client.connected:
            QMessageBox.warning(self, "Not Connected", "Please connect to server first")
            return
        
        message = self.chat_widget.message_input.text().strip()
        if message:
            self.client.send_chat_message(message)
            # Add own message to chat
            self.chat_widget.add_message("You", message)
            self.chat_widget.message_input.clear()
    
    def share_file(self):
        """Share file"""
        if not self.client or not self.client.connected:
            QMessageBox.warning(self, "Not Connected", "Please connect to server first")
            return
        
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File to Share")
        if file_path:
            self.chat_widget.add_system_message(f"File sharing: {file_path}")
            # TODO: Implement file transfer
    
    def handle_video_frame_gui(self, sender, frame):
        """Handle incoming video frame (GUI thread)"""
        # Show YOUR OWN video in first slot
        if sender == self.my_username:
            if self.my_video_widget:
                self.my_video_widget.update_frame(frame)
            return
        
        # Get or create widget for other users
        if sender not in self.video_widgets_map:
            # Find available widget (skip first one - reserved for own video)
            for widget in self.video_widgets[1:]:
                if widget.username == "" or widget.username == sender:
                    widget.username = sender
                    widget.setText(sender)
                    widget.setStyleSheet("""
                        QLabel {
                            background-color: #1e1e1e;
                            border: 2px solid #3a3a3a;
                            border-radius: 10px;
                        }
                    """)
                    self.video_widgets_map[sender] = widget
                    break
        
        # Update frame
        if sender in self.video_widgets_map:
            self.video_widgets_map[sender].update_frame(frame)
    
    def handle_audio_chunk_gui(self, sender, chunk):
        """Handle incoming audio chunk (GUI thread)"""
        try:
            if self.audio_stream:
                self.audio_stream.write(chunk)
        except Exception as e:
            print(f"Audio playback error: {e}")
    
    def handle_chat_message_gui(self, sender, message):
        """Handle incoming chat message (GUI thread)"""
        self.chat_widget.add_message(sender, message)
    
    def handle_user_list_gui(self, users):
        """Handle user list update (GUI thread)"""
        self.user_list.clear()
        for user in users:
            username = user.get('username', 'Unknown')
            status_icons = []
            if user.get('video'):
                status_icons.append('📹')
            if user.get('audio'):
                status_icons.append('🎤')
            if user.get('screen'):
                status_icons.append('🖥️')
            
            status = ' '.join(status_icons) if status_icons else '💤'
            self.user_list.addItem(f"{username} {status}")
    
    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            "About ScaleComm",
            "<h2>ScaleComm</h2>"
            "<p>Highly Scalable LAN Communication Platform</p>"
            "<p><b>Features:</b></p>"
            "<ul>"
            "<li>Multi-user video conferencing</li>"
            "<li>Multi-user audio conferencing</li>"
            "<li>Screen sharing</li>"
            "<li>Group text chat</li>"
            "<li>File sharing</li>"
            "</ul>"
            "<p>Optimized for maximum efficiency and scalability.</p>"
        )
    
    def closeEvent(self, event):
        """Handle window close"""
        if self.client:
            self.client.disconnect()
        
        if self.audio_stream:
            self.audio_stream.stop_stream()
            self.audio_stream.close()
        
        if self.audio_player:
            self.audio_player.terminate()
        
        event.accept()

def main():
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle("Fusion")
    
    # Dark palette
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
    palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Base, QColor(43, 43, 43))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(58, 58, 58))
    palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Button, QColor(58, 58, 58))
    palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Link, QColor(0, 120, 212))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 120, 212))
    palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
    app.setPalette(palette)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()