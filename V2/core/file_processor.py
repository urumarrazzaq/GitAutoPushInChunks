import os
import logging
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)

class FileProcessor:
    """Handles file operations including splitting large files and ignore patterns"""
    
    @staticmethod
    def get_folder_size(folder: Path) -> int:
        """Calculate total size of a folder in bytes"""
        total_size = 0
        for item in folder.rglob('*'):
            if item.is_file():
                total_size += item.stat().st_size
        return total_size

    @staticmethod
    def split_file(file_path: Path, chunk_size: int) -> List[Path]:
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
                    chunk_data = f.read(chunk_size)
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
            # Handle wildcard patterns
            if pattern.startswith('*'):
                if path.name.endswith(pattern[1:]):
                    return True
            # Exact match
            elif path.name == pattern:
                return True
            # Directory name contains pattern (case insensitive)
            elif path.is_dir() and pattern.lower() in path.name.lower():
                return True
        return False

