# Core constants and default values
import os
from pathlib import Path

# File processing constants
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB in bytes
CHUNK_SIZE = 20 * 1024 * 1024  # 20MB chunk size
CHUNK_PREFIX = "_part"  # Format: filename_part001.ext
COMMIT_BATCH_SIZE = 10  # Number of files to commit at once
MAX_RETRIES = 3  # Max retries for push operations

# Default ignored patterns
DEFAULT_IGNORES = [
    '.git',
    'Binaries',
    'DerivedDataCache',
    'Intermediate',
    'Saved',
    'Build',
    '*.sln',
    '*.vcxproj',
    '*.opendb',
    '*.ide',
    '*.suo',
    '*.user'
]

# Logging format
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"