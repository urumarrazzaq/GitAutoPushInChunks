import os
import logging
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QFileDialog, QListWidget, QMessageBox,
    QTabWidget, QProgressBar, QLineEdit, QSpinBox, QGroupBox,
    QTextEdit, QPlainTextEdit, QSizePolicy
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QTextCursor
from PyQt5.QtGui import QColor, QFont, QTextCharFormat

from ui.worker import UploadWorker
from core.constants import DEFAULT_IGNORES, COMMIT_BATCH_SIZE

logger = logging.getLogger(__name__)

class UEProjectUploader(QMainWindow):
    """Main application window for Unreal Engine Project GitHub Uploader"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Unreal Engine Project GitHub Uploader")
        self.setGeometry(100, 100, 1000, 800)
        
        # Variables
        self.upload_worker = None
        self.failed_pushes = []
        
        # Setup UI
        self.setup_ui()
        
    def setup_ui(self):
        """Initialize all UI components"""
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)
        
        # Create tabs
        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)
        
        # Main Tab
        main_tab = QWidget()
        tab_widget.addTab(main_tab, "Upload")
        
        # Settings Tab
        settings_tab = QWidget()
        tab_widget.addTab(settings_tab, "Settings")
        
        # Setup main tab
        self.setup_main_tab(main_tab)
        
        # Setup settings tab
        self.setup_settings_tab(settings_tab)
        
        # Status Bar
        self.statusBar().showMessage("Ready")
        
    def setup_main_tab(self, tab):
        """Setup the main upload tab"""
        layout = QVBoxLayout()
        tab.setLayout(layout)
        
        # Project Folder Selection
        folder_group = QGroupBox("Project Settings")
        folder_layout = QVBoxLayout()
        
        # Project Path
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Project Folder:"))
        self.folder_path_edit = QLineEdit()
        self.folder_path_edit.setPlaceholderText("Select Unreal Engine project folder")
        path_layout.addWidget(self.folder_path_edit)
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self.browse_project_folder)
        path_layout.addWidget(browse_button)
        folder_layout.addLayout(path_layout)
        
        # GitHub Repo
        repo_layout = QHBoxLayout()
        repo_layout.addWidget(QLabel("GitHub Repo URL:"))
        self.repo_url_edit = QLineEdit()
        self.repo_url_edit.setPlaceholderText("https://github.com/username/repo.git")
        repo_layout.addWidget(self.repo_url_edit)
        folder_layout.addLayout(repo_layout)
        
        # Branch
        branch_layout = QHBoxLayout()
        branch_layout.addWidget(QLabel("Branch:"))
        self.branch_edit = QLineEdit("main")
        branch_layout.addWidget(self.branch_edit)
        folder_layout.addLayout(branch_layout)
        
        folder_group.setLayout(folder_layout)
        layout.addWidget(folder_group)
        
        # File Processing Settings
        processing_group = QGroupBox("File Processing")
        processing_layout = QHBoxLayout()
        
        # Chunk Size
        chunk_layout = QVBoxLayout()
        chunk_layout.addWidget(QLabel("Max File Size (MB):"))
        self.chunk_size_spin = QSpinBox()
        self.chunk_size_spin.setRange(1, 100)
        self.chunk_size_spin.setValue(25)
        chunk_layout.addWidget(self.chunk_size_spin)
        processing_layout.addLayout(chunk_layout)
        
        # Batch Size
        batch_layout = QVBoxLayout()
        batch_layout.addWidget(QLabel("Files per Commit:"))
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(1, 50)
        self.batch_size_spin.setValue(COMMIT_BATCH_SIZE)
        batch_layout.addWidget(self.batch_size_spin)
        processing_layout.addLayout(batch_layout)
        
        processing_group.setLayout(processing_layout)
        layout.addWidget(processing_group)
        
        # Ignored Folders
        ignore_group = QGroupBox("Ignored Folders")
        ignore_layout = QVBoxLayout()
        
        self.ignored_list = QListWidget()
        for pattern in DEFAULT_IGNORES:
            self.ignored_list.addItem(pattern)
        ignore_layout.addWidget(self.ignored_list)
        
        # Ignore buttons
        ignore_buttons = QHBoxLayout()
        add_ignore_btn = QPushButton("➕ Add")
        add_ignore_btn.clicked.connect(self.add_folder_to_ignore)
        remove_ignore_btn = QPushButton("❌ Remove")
        remove_ignore_btn.clicked.connect(self.remove_selected_folder)
        ignore_buttons.addWidget(add_ignore_btn)
        ignore_buttons.addWidget(remove_ignore_btn)
        ignore_layout.addLayout(ignore_buttons)
        
        ignore_group.setLayout(ignore_layout)
        layout.addWidget(ignore_group)
        
        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.progress_bar)
        
        # Action Buttons
        buttons_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("🚀 Start")
        self.start_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        self.start_btn.clicked.connect(self.start_upload)
        buttons_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("🛑 Stop")
        self.stop_btn.setStyleSheet("background-color: #F44336; color: white;")
        self.stop_btn.clicked.connect(self.stop_push_process)
        self.stop_btn.setEnabled(False)
        buttons_layout.addWidget(self.stop_btn)
        
        self.retry_btn = QPushButton("🔄 Retry Failed")
        self.retry_btn.setStyleSheet("background-color: #9C27B0; color: white;")
        self.retry_btn.clicked.connect(self.retry_failed_pushes)
        self.retry_btn.setEnabled(False)
        buttons_layout.addWidget(self.retry_btn)
        
        self.copy_logs_btn = QPushButton("📋 Copy Logs")
        self.copy_logs_btn.setStyleSheet("background-color: #2196F3; color: white;")
        self.copy_logs_btn.clicked.connect(self.copy_logs)
        buttons_layout.addWidget(self.copy_logs_btn)
        
        self.clear_logs_btn = QPushButton("🧹 Clear Logs")
        self.clear_logs_btn.setStyleSheet("background-color: #FF9800; color: white;")
        self.clear_logs_btn.clicked.connect(self.clear_logs)
        buttons_layout.addWidget(self.clear_logs_btn)
        
        layout.addLayout(buttons_layout)
        
        # Log Output
        log_group = QGroupBox("Log Output")
        log_layout = QVBoxLayout()
        
        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        font = QFont("Consolas", 10)
        self.log_output.setFont(font)
        log_layout.addWidget(self.log_output)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
    def setup_settings_tab(self, tab):
        """Setup the settings tab"""
        layout = QVBoxLayout()
        tab.setLayout(layout)
        
        settings_label = QLabel("Additional settings will be added here in future versions.")
        settings_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(settings_label)
        
    def browse_project_folder(self):
        """Open folder dialog to select project folder"""
        folder = QFileDialog.getExistingDirectory(self, "Select Project Folder")
        if folder:
            self.folder_path_edit.setText(folder)
            
    def add_folder_to_ignore(self):
        """Add folder to ignore list"""
        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Ignore")
        if folder:
            folder_name = os.path.basename(folder)
            if not self.ignored_list.findItems(folder_name, Qt.MatchExactly):
                self.ignored_list.addItem(folder_name)
                
    def remove_selected_folder(self):
        """Remove selected folder from ignore list with confirmation"""
        selected_items = self.ignored_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a folder to remove.")
            return
            
        reply = QMessageBox.question(
            self, "Confirm Removal",
            "Are you sure you want to remove the selected folder(s) from the ignore list?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            for item in selected_items:
                self.ignored_list.takeItem(self.ignored_list.row(item))
                
    def copy_logs(self):
        """Copy log contents to clipboard"""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.log_output.toPlainText())
        QMessageBox.information(self, "Copied", "Logs copied to clipboard!")
        
    def clear_logs(self):
        """Clear log contents"""
        self.log_output.clear()
        self.log_message("🧹 Logs cleared!", "blue")
        
    def log_message(self, message: str, color: str = "black"):
        """Display a message in the log with colored prefix"""
        cursor = self.log_output.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        # Get the symbol (first 2 characters) and the rest of the message
        symbol = message[:2]
        rest = message[2:]
        
        # Format for color
        if color == "green":
            text_color = QColor(0, 128, 0)  # Dark green
        elif color == "red":
            text_color = QColor(255, 0, 0)  # Red
        elif color == "yellow":
            text_color = QColor(255, 165, 0)  # Orange
        elif color == "blue":
            text_color = QColor(0, 0, 255)  # Blue
        else:
            text_color = QColor(0, 0, 0)  # Black
            
        # Insert symbol with color
        char_format = cursor.charFormat()
        char_format.setForeground(text_color)
        cursor.setCharFormat(char_format)
        cursor.insertText(symbol)
        
        # Insert rest of message in black
        char_format.setForeground(QColor(0, 0, 0))
        cursor.setCharFormat(char_format)
        cursor.insertText(rest + "\n")
        
        # Scroll to bottom
        self.log_output.ensureCursorVisible()
        
    def start_upload(self):
        """Start the upload process in a worker thread"""
        project_path = self.folder_path_edit.text()
        repo_url = self.repo_url_edit.text()
        branch = self.branch_edit.text()
        chunk_size_mb = self.chunk_size_spin.value()
        batch_size = self.batch_size_spin.value()
        
        if not project_path or not repo_url:
            QMessageBox.critical(self, "Error", "Please select a project folder and enter a GitHub repository URL.")
            return
            
        # Get ignored folders from list
        ignored_folders = []
        for i in range(self.ignored_list.count()):
            ignored_folders.append(self.ignored_list.item(i).text())
            
        # Clear logs
        self.log_output.clear()
        self.failed_pushes = []
        
        # Disable start button, enable stop button
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.retry_btn.setEnabled(False)
        
        # Create and start worker thread
        self.upload_worker = UploadWorker(
            project_path, repo_url, branch, chunk_size_mb, batch_size, ignored_folders
        )
        self.upload_worker.progress_updated.connect(self.update_progress)
        self.upload_worker.finished.connect(self.upload_finished)
        self.upload_worker.log_message.connect(self.log_message)
        self.upload_worker.start()
        
    def stop_push_process(self):
        """Stop the current upload process"""
        if self.upload_worker:
            self.upload_worker.stop()
            self.stop_btn.setEnabled(False)
            
    def retry_failed_pushes(self):
        """Retry failed push operations"""
        if not self.failed_pushes:
            QMessageBox.information(self, "No Failed Pushes", "No failed pushes to retry.")
            return
            
        # TODO: Implement retry logic
        QMessageBox.information(self, "Coming Soon", "Retry functionality will be implemented in the next version.")
        
    def update_progress(self, value, maximum, message):
        """Update progress bar and status"""
        self.progress_bar.setMaximum(maximum)
        self.progress_bar.setValue(value)
        self.statusBar().showMessage(message)
        
    def upload_finished(self, success):
        """Handle upload completion"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.retry_btn.setEnabled(bool(self.failed_pushes))
        
        if success:
            self.statusBar().showMessage("Upload completed successfully!")
        else:
            self.statusBar().showMessage("Upload completed with errors")