import logging
import time
from pathlib import Path
from typing import List, Dict
from PyQt5.QtCore import QThread, pyqtSignal

from core.file_processor import FileProcessor
from core.git_manager import GitManager
from core.constants import DEFAULT_IGNORES

logger = logging.getLogger(__name__)

class UploadWorker(QThread):
    """Worker thread for handling the upload process with improved logging"""
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
        self.ignored_folders = ignored_folders + DEFAULT_IGNORES
        self.stop_requested = False
        self.failed_pushes = []
        self.git_manager = None

    def run(self):
        try:
            # Initialize GitManager
            self.git_manager = GitManager(self.project_path, self.repo_url, self.branch)
            self.git_manager.initialize_repository()

            # Calculate total files to process for progress bar
            total_files = self._count_files_to_process()
            if total_files == 0:
                self.log_message.emit("ℹ️ No files found to process (all ignored or empty)", "blue")
                self.finished.emit(True)
                return

            self.progress_updated.emit(0, total_files, "Starting upload process...")

            # Process files in batches
            current_batch = []
            processed_files = 0
            for item in self.project_path.rglob('*'):
                if self.stop_requested:
                    break

                if FileProcessor.should_ignore(item, self.ignored_folders):
                    self._log_ignored_item(item)
                    continue

                if item.is_file():
                    processed_files_list = self._process_file(item)
                    if processed_files_list:
                        current_batch.extend(processed_files_list)
                        processed_files += 1
                        self.progress_updated.emit(
                            processed_files, 
                            total_files, 
                            f"Processing: {item.relative_to(self.project_path)}"
                        )

                        # Commit in batches
                        if len(current_batch) >= self.batch_size:
                            self._commit_batch(current_batch)
                            current_batch = []

            # Commit any remaining files
            if current_batch and not self.stop_requested:
                self._commit_batch(current_batch)

            # Final status
            if not self.stop_requested:
                self._log_completion()
                self.finished.emit(True)
            else:
                self.log_message.emit("\n❌ Upload stopped by user!", "red")
                self.finished.emit(False)

        except Exception as e:
            self.log_message.emit(f"❌ Critical error: {str(e)}", "red")
            logger.exception("Upload failed with error")
            self.finished.emit(False)

    def _count_files_to_process(self) -> int:
        """Count total files that will be processed (excluding ignored ones)"""
        total = 0
        for item in self.project_path.rglob('*'):
            if item.is_file() and not FileProcessor.should_ignore(item, self.ignored_folders):
                total += 1
        return total

    def _log_ignored_item(self, item: Path) -> None:
        """Log ignored items with appropriate level"""
        rel_path = str(item.relative_to(self.project_path))
        if any(p in rel_path for p in DEFAULT_IGNORES):
            # Default ignores are less important to log
            logger.debug(f"Ignoring (default): {rel_path}")
        else:
            self.log_message.emit(f"⚠️ Skipping: {rel_path}", "yellow")
            logger.info(f"Ignoring: {rel_path}")

    def _process_file(self, file_path: Path) -> List[Path]:
        """Process an individual file and return list of files to commit"""
        try:
            file_size = file_path.stat().st_size
            max_size = self.chunk_size_mb * 1024 * 1024
            rel_path = str(file_path.relative_to(self.project_path))
            
            if file_size > max_size:
                self.log_message.emit(
                    f"🔪 Splitting large file: {rel_path} ({file_size/1024/1024:.2f}MB)", 
                    "blue"
                )
                chunks = FileProcessor.split_file(file_path, max_size)
                self.log_message.emit(
                    f"✨ Created {len(chunks)} chunks for {rel_path}", 
                    "blue"
                )
                return chunks
            else:
                self.log_message.emit(f"📄 Processing: {rel_path}", "black")
                return [file_path]
        except Exception as e:
            self.log_message.emit(
                f"❌ Failed to process {rel_path}: {str(e)}", 
                "red"
            )
            self.failed_pushes.append({
                "name": file_path.name,
                "path": str(file_path),
                "error": str(e)
            })
            return []

    def _commit_batch(self, file_batch: List[Path]) -> bool:
        """Commit and push a batch of files"""
        success = self.git_manager.commit_and_push(file_batch, "Add")
        if not success:
            self.failed_pushes.extend([
                {"name": fp.name, "path": str(fp)} 
                for fp in file_batch
            ])
        return success

    def _log_completion(self) -> None:
        """Log completion status with summary"""
        if self.failed_pushes:
            self.log_message.emit(
                f"\n⚠️ Upload completed with {len(self.failed_pushes)} errors!", 
                "yellow"
            )
        else:
            self.log_message.emit("\n✅ Upload completed successfully!", "blue")

        # Log statistics
        processed_count = len(self.git_manager.get_processed_files())
        failed_count = len(self.failed_pushes)
        self.log_message.emit(
            f"📊 Stats: {processed_count} succeeded, {failed_count} failed", 
            "black"
        )

    def stop(self):
        """Request the worker to stop"""
        self.stop_requested = True


