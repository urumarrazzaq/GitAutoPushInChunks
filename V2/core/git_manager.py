import os
import time
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import git
from git import Repo, GitCommandError

from .constants import DEFAULT_IGNORES, MAX_RETRIES

logger = logging.getLogger(__name__)

class GitManager:
    """Handles all Git repository operations with improved commit messages and ignore handling"""
    
    def __init__(self, project_path: Path, repo_url: str, branch: str = "main"):
        self.project_path = project_path
        self.repo_url = repo_url
        self.branch = branch
        self.repo = None
        self.processed_files = []
        self.failed_commits = []
        
    def initialize_repository(self) -> None:
        """Initialize or clone the Git repository with proper .gitignore setup"""
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
                
            # Ensure .gitignore exists
            self._ensure_gitignore(DEFAULT_IGNORES)
                
        except Exception as e:
            logger.error(f"Failed to initialize repository: {e}")
            raise

    def _ensure_gitignore(self, ignore_patterns: List[str]) -> None:
        """Ensure .gitignore file exists with proper patterns"""
        gitignore_path = self.project_path / '.gitignore'
        existing_patterns = set()
        
        if gitignore_path.exists():
            with open(gitignore_path, 'r') as f:
                existing_patterns = {line.strip() for line in f if line.strip() and not line.startswith('#')}
        
        # Add our default patterns
        new_patterns = set(ignore_patterns) - existing_patterns
        if new_patterns:
            with open(gitignore_path, 'a') as f:
                f.write('\n# Added by UE GitHub Uploader\n')
                f.write('\n'.join(sorted(new_patterns)) + '\n')
            
            # Add .gitignore to repo if it's new
            if not existing_patterns:
                self.repo.git.add(str(gitignore_path))
                self.repo.index.commit("Add .gitignore file")
                logger.info(f"Created .gitignore with {len(new_patterns)} patterns")

    def commit_and_push(self, file_paths: List[Path], operation_type: str = "Add") -> bool:
        """Commit and push changes with folder-specific messages"""
        if not file_paths:
            return True

        try:
            # Group files by their parent folder
            folder_groups = {}
            for fp in file_paths:
                parent = str(fp.parent.relative_to(self.project_path))
                if parent == '.':
                    parent = 'root'
                folder_groups.setdefault(parent, []).append(fp)

            # Commit each folder group separately
            overall_success = True
            for folder, files in folder_groups.items():
                success = self._commit_folder_group(folder, files, operation_type)
                overall_success = overall_success and success
                
            return overall_success
            
        except Exception as e:
            logger.error(f"Error during commit/push: {e}")
            self.failed_commits.extend([(fp, str(e)) for fp in file_paths])
            return False

    def _commit_folder_group(self, folder: str, files: List[Path], operation_type: str) -> bool:
        """Commit a group of files from the same folder"""
        # Generate meaningful commit message
        file_types = {}
        for fp in files:
            ext = fp.suffix.lower()[1:] if fp.suffix else 'file'
            file_types[ext] = file_types.get(ext, 0) + 1
        
        type_summary = ", ".join([f"{count} {ext}" for ext, count in file_types.items()])
        commit_msg = f"{operation_type} [{folder}]: {type_summary}"
        logger.info(f"Preparing commit: {commit_msg}")

        # Add files
        for file_path in files:
            try:
                self.repo.git.add(str(file_path))
            except GitCommandError as e:
                logger.warning(f"Couldn't add {file_path}: {e}")
                self.failed_commits.append((file_path, str(e)))
                continue

        # Commit changes
        self.repo.index.commit(commit_msg)
        self.processed_files.extend(files)
        
        # Push with retry logic
        for attempt in range(MAX_RETRIES):
            try:
                self.repo.remotes.origin.push(self.branch, set_upstream=True)
                logger.info(f"Successfully pushed {len(files)} files to {folder}")
                return True
            except GitCommandError as e:
                if attempt == MAX_RETRIES - 1:
                    logger.error(f"Failed to push {folder} after {MAX_RETRIES} attempts: {e}")
                    self.failed_commits.extend([(fp, str(e)) for fp in files])
                    return False
                
                logger.warning(f"Push attempt {attempt + 1} for {folder} failed, retrying...")
                try:
                    self.repo.git.pull('origin', self.branch)
                except GitCommandError as pull_error:
                    logger.error(f"Failed to pull before retry: {pull_error}")
                time.sleep(1)

    def get_failed_commits(self) -> List[Tuple[Path, str]]:
        """Return list of files that failed to commit/push with error messages"""
        return self.failed_commits

    def get_processed_files(self) -> List[Path]:
        """Return list of successfully processed files"""
        return self.processed_files

