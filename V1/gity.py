import os
import shutil
import time
import logging
from pathlib import Path
import git
from git import Repo, GitCommandError
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QFileDialog, QListWidget, QMessageBox,
                             QTabWidget, QProgressBar, QLineEdit, QSpinBox, QGroupBox,
                             QCheckBox, QTextEdit, QPlainTextEdit, QSizePolicy)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QTextCursor, QColor, QFont

# Constants
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB in bytes
CHUNK_SIZE = 20 * 1024 * 1024  # 20MB chunk size
CHUNK_PREFIX = "_part"  # Format: filename_part001.ext
DEFAULT_IGNORES = ['.git', 'Binaries', 'DerivedDataCache', 'Intermediate', 'Saved']
COMMIT_BATCH_SIZE = 10  # Number of files to commit at once
MAX_RETRIES = 3  # Max retries for push operations

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("ue_github_pusher.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class FileProcessor:
    """Handles file operations including splitting large files"""
    
    @staticmethod
    def get_folder_size(folder: Path) -> int:
        """Calculate total size of a folder in bytes"""
        total_size = 0
        for item in folder.rglob('*'):
            if item.is_file():
                total_size += item.stat().st_size
        return total_size

    @staticmethod
    def split_file(file_path: Path) -> List[Path]:
        """Split a large file into properly named chunks"""
        chunks = []
        try:
            if not file_path.exists():
                return []

            file_name = file_path.stem
            file_ext = file_path.suffix
            
            with open(file_path, 'rb') as f:
                chunk_num = 1
                while True:
                    chunk_data = f.read(CHUNK_SIZE)
                    if not chunk_data:
                        break
                    
                    chunk_file = file_path.parent / f"{file_name}{CHUNK_PREFIX}{chunk_num:03d}{file_ext}"
                    with open(chunk_file, 'wb') as chunk:
                        chunk.write(chunk_data)
                    chunks.append(chunk_file)
                    chunk_num += 1
            
            # Delete original file after successful split
            try:
                file_path.unlink()
                logger.info(f"Deleted original file: {file_path}")
            except Exception as e:
                logger.error(f"Failed to delete original file: {e}")
                raise
                
            return chunks
            
        except Exception as e:
            logger.error(f"Error splitting file {file_path}: {e}")
            # Clean up any partial chunks
            for chunk in chunks:
                try:
                    if chunk.exists():
                        chunk.unlink()
                except:
                    pass
            raise

    @staticmethod
    def should_ignore(path: Path, ignore_patterns: List[str]) -> bool:
        """Check if a path should be ignored based on patterns"""
        for pattern in ignore_patterns:
            if pattern.startswith('*'):
                if path.name.endswith(pattern[1:]):
                    return True
            elif path.name == pattern:
                return True
            elif path.is_dir() and pattern.lower() in path.name.lower():
                return True
        return False

class GitManager:
    """Handles all Git repository operations"""
    
    def __init__(self, project_path: Path, repo_url: str, branch: str = "main"):
        self.project_path = project_path
        self.repo_url = repo_url
        self.branch = branch
        self.repo = None
        self.processed_files = []
        self.failed_commits = []
        
    def initialize_repository(self) -> None:
        """Initialize or clone the Git repository directly in the project folder"""
        try:
            git_dir = self.project_path / '.git'
            
            if git_dir.exists():
                # Use existing repository
                self.repo = Repo(self.project_path)
                logger.info(f"Using existing repository at {self.project_path}")
            else:
                # Initialize new repository
                self.repo = Repo.init(self.project_path)
                if not any(self.repo.remotes):
                    self.repo.create_remote('origin', self.repo_url)
                logger.info(f"Initialized new repository at {self.project_path}")

            # Ensure correct branch exists
            if self.branch not in [str(b) for b in self.repo.branches]:
                self.repo.git.checkout('-b', self.branch)
                logger.info(f"Created new branch: {self.branch}")
            else:
                self.repo.git.checkout(self.branch)
                logger.info(f"Checked out existing branch: {self.branch}")
                
        except Exception as e:
            logger.error(f"Failed to initialize repository: {e}")
            raise

    def commit_and_push(self, file_paths: List[Path], operation_type: str) -> bool:
        """Commit and push changes for specific files with meaningful messages"""
        if not file_paths:
            return True

        try:
            # Generate meaningful commit message
            if len(file_paths) == 1:
                file_name = file_paths[0].name
                rel_path = str(file_paths[0].relative_to(self.project_path))
                commit_msg = f"{operation_type}: {file_name} ({rel_path})"
            else:
                file_types = {}
                for fp in file_paths:
                    ext = fp.suffix.lower()
                    file_types[ext] = file_types.get(ext, 0) + 1
                type_summary = ", ".join([f"{count} {ext[1:] if ext else 'files'}" 
                                       for ext, count in file_types.items()])
                commit_msg = f"{operation_type}: {type_summary}"

            # Add specific files
            for file_path in file_paths:
                try:
                    self.repo.git.add(str(file_path))
                except GitCommandError as e:
                    logger.warning(f"Couldn't add {file_path}: {e}")
                    self.failed_commits.append((file_path, str(e)))
                    continue

            # Commit changes
            self.repo.index.commit(commit_msg)
            self.processed_files.extend(file_paths)
            
            # Push with retry logic
            for attempt in range(MAX_RETRIES):
                try:
                    self.repo.remotes.origin.push(self.branch, set_upstream=True)
                    logger.info(f"Successfully pushed {len(file_paths)} files")
                    return True
                except GitCommandError as e:
                    if attempt == MAX_RETRIES - 1:
                        logger.error(f"Failed to push after {MAX_RETRIES} attempts: {e}")
                        self.failed_commits.extend([(fp, str(e)) for fp in file_paths])
                        return False
                    
                    logger.warning(f"Push attempt {attempt + 1} failed, retrying...")
                    try:
                        self.repo.git.pull('origin', self.branch)
                    except GitCommandError as pull_error:
                        logger.error(f"Failed to pull before retry: {pull_error}")
                        continue
                    
        except Exception as e:
            logger.error(f"Error during commit/push: {e}")
            self.failed_commits.extend([(fp, str(e)) for fp in file_paths])
            return False

    def get_failed_commits(self) -> List[Tuple[Path, str]]:
        """Return list of files that failed to commit/push with error messages"""
        return self.failed_commits

    def get_processed_files(self) -> List[Path]:
        """Return list of successfully processed files"""
        return self.processed_files

class UploadWorker(QThread):
    """Worker thread for handling the upload process"""
    progress_updated = pyqtSignal(int, int, str)
    finished = pyqtSignal(bool)
    log_message = pyqtSignal(str, str)

    def __init__(self, project_path, repo_url, branch, chunk_size_mb, batch_size, ignored_folders):
        super().__init__()
        self.project_path = Path(project_path)
        self.repo_url = repo_url
        self.branch = branch
        self.chunk_size_mb = chunk_size_mb
        self.batch_size = batch_size
        self.ignored_folders = ignored_folders
        self.stop_requested = False
        self.failed_pushes = []
        self.git_manager = None

    def run(self):
        try:
            # Initialize GitManager
            self.git_manager = GitManager(self.project_path, self.repo_url, self.branch)
            self.git_manager.initialize_repository()

            # Calculate total files to process for progress bar
            total_files = 0
            for item in self.project_path.rglob('*'):
                if item.is_file() and not FileProcessor.should_ignore(item, self.ignored_folders):
                    total_files += 1

            self.progress_updated.emit(0, total_files, "Starting upload process...")

            # Process files in batches
            current_batch = []
            processed_files = 0
            for item in self.project_path.rglob('*'):
                if self.stop_requested:
                    break

                if FileProcessor.should_ignore(item, self.ignored_folders):
                    self.log_message.emit(f"⚠️ Skipping: {item}", "yellow")
                    continue

                if item.is_file():
                    try:
                        file_size = item.stat().st_size
                        max_size = self.chunk_size_mb * 1024 * 1024
                        
                        if file_size > max_size:
                            self.log_message.emit(f"⚠️ Skipping large file: {item} ({file_size/1024/1024:.2f} MB)", "yellow")
                            continue

                        # Process the file (could return multiple files if split)
                        processed_files_list = self._process_file(item)
                        if processed_files_list:
                            current_batch.extend(processed_files_list)
                            processed_files += 1
                            self.progress_updated.emit(processed_files, total_files, f"Processing: {item.name}")

                            # Commit in batches
                            if len(current_batch) >= self.batch_size:
                                success = self.git_manager.commit_and_push(current_batch, "Add")
                                if not success:
                                    self.failed_pushes.extend([{"name": fp.name, "path": str(fp)} for fp in current_batch])
                                current_batch = []
                    except Exception as e:
                        self.log_message.emit(f"❌ Error processing {item}: {e}", "red")
                        self.failed_pushes.append({"name": item.name, "path": str(item)})

            # Commit any remaining files in the batch
            if current_batch and not self.stop_requested:
                success = self.git_manager.commit_and_push(current_batch, "Add")
                if not success:
                    self.failed_pushes.extend([{"name": fp.name, "path": str(fp)} for fp in current_batch])

            # Final status
            if not self.stop_requested:
                self.log_message.emit("\n✅ Upload completed!", "blue")
                self.finished.emit(True)
            else:
                self.log_message.emit("\n❌ Upload stopped by user!", "red")
                self.finished.emit(False)

        except Exception as e:
            self.log_message.emit(f"❌ Critical error: {e}", "red")
            self.finished.emit(False)

    def _process_file(self, file_path: Path) -> List[Path]:
        """Process an individual file and return list of files to commit"""
        try:
            file_size = file_path.stat().st_size
            max_size = self.chunk_size_mb * 1024 * 1024
            
            if file_size > max_size:
                self.log_message.emit(f"🔪 Splitting large file: {file_path}", "blue")
                chunks = FileProcessor.split_file(file_path)
                self.log_message.emit(f"✨ Created {len(chunks)} chunks from {file_path.name}", "blue")
                return chunks
            else:
                return [file_path]
        except Exception as e:
            self.log_message.emit(f"❌ Failed to process file {file_path}: {e}", "red")
            return []

    def stop(self):
        self.stop_requested = True

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
        self.batch_size_spin.setValue(10)
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
        
        # TODO: Add settings controls here
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
            # Add just the folder name, not full path
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

if __name__ == "__main__":
    app = QApplication([])
    app.setStyle('Fusion')  # Modern style
    
    # Set application font
    font = QFont()
    font.setFamily("Segoe UI")
    font.setPointSize(10)
    app.setFont(font)
    
    window = UEProjectUploader()
    window.show()
    app.exec_()