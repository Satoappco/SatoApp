"""
File-based logging configuration for Sato Backend.

This module sets up file-based logging that captures all application logs
and provides functionality to retrieve and serve log files.
"""

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
import gzip
from logging.handlers import RotatingFileHandler

# Configuration
LOG_DIR = os.getenv("LOG_DIR", "./logs")  # Default to local logs directory
LOG_FILE_NAME = os.getenv("LOG_FILE_NAME", "sato.log")
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", 10 * 1024 * 1024))  # 10MB default
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", 10))  # Keep 10 backup files
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


class FileLogger:
    """Manages file-based logging for the application."""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FileLogger, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the file logger (singleton pattern)."""
        if not self._initialized:
            self.log_dir = Path(LOG_DIR)
            self.log_file = self.log_dir / LOG_FILE_NAME
            self._setup_logging()
            FileLogger._initialized = True

    def _setup_logging(self):
        """Set up file-based logging configuration."""
        # Create logs directory if it doesn't exist
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Create rotating file handler
        file_handler = RotatingFileHandler(
            filename=str(self.log_file),
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding='utf-8'
        )

        # Set formatter with detailed information
        formatter = logging.Formatter(
            fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)

        # Set log level
        file_handler.setLevel(getattr(logging, LOG_LEVEL.upper()))

        # Add handler to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)

        # Also ensure root logger level is set
        if root_logger.level > file_handler.level:
            root_logger.setLevel(file_handler.level)

        logging.info(f"📝 File logging initialized: {self.log_file}")
        logging.info(f"📁 Log directory: {self.log_dir}")
        logging.info(f"📊 Max file size: {LOG_MAX_BYTES / (1024*1024):.1f}MB")
        logging.info(f"🔄 Backup count: {LOG_BACKUP_COUNT}")

    def get_log_files(self) -> List[Path]:
        """
        Get list of all log files (current + rotated backups).

        Returns:
            List of Path objects for all log files, sorted by modification time (newest first)
        """
        log_files = []

        # Add main log file if it exists
        if self.log_file.exists():
            log_files.append(self.log_file)

        # Add rotated log files
        for i in range(1, LOG_BACKUP_COUNT + 1):
            rotated_file = Path(f"{self.log_file}.{i}")
            if rotated_file.exists():
                log_files.append(rotated_file)

        # Sort by modification time (newest first)
        log_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        return log_files

    def read_log_file(
        self,
        file_path: Optional[Path] = None,
        lines: Optional[int] = None,
        reverse: bool = True
    ) -> str:
        """
        Read contents of a log file.

        Args:
            file_path: Path to log file (defaults to main log file)
            lines: Number of lines to read (None = all lines)
            reverse: If True, return most recent lines first

        Returns:
            String containing log file contents
        """
        if file_path is None:
            file_path = self.log_file

        if not file_path.exists():
            return f"Log file not found: {file_path}"

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()

            if reverse:
                all_lines = all_lines[::-1]

            if lines is not None:
                all_lines = all_lines[:lines]

            return ''.join(all_lines)

        except Exception as e:
            return f"Error reading log file: {str(e)}"

    def get_recent_logs(self, lines: int = 100) -> str:
        """
        Get the most recent log entries.

        Args:
            lines: Number of recent lines to retrieve

        Returns:
            String containing recent log entries
        """
        return self.read_log_file(lines=lines, reverse=True)

    def search_logs(
        self,
        search_term: str,
        max_results: int = 100,
        case_sensitive: bool = False
    ) -> str:
        """
        Search for a term in log files.

        Args:
            search_term: Text to search for
            max_results: Maximum number of matching lines to return
            case_sensitive: Whether search should be case-sensitive

        Returns:
            String containing matching log entries
        """
        matching_lines = []

        for log_file in self.get_log_files():
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if case_sensitive:
                            match = search_term in line
                        else:
                            match = search_term.lower() in line.lower()

                        if match:
                            matching_lines.append(line)
                            if len(matching_lines) >= max_results:
                                break

                if len(matching_lines) >= max_results:
                    break

            except Exception as e:
                matching_lines.append(f"Error reading {log_file}: {str(e)}\n")

        return ''.join(matching_lines)

    def get_logs_by_level(self, level: str = "ERROR", max_results: int = 100) -> str:
        """
        Get log entries of a specific level.

        Args:
            level: Log level to filter (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            max_results: Maximum number of entries to return

        Returns:
            String containing filtered log entries
        """
        return self.search_logs(f"| {level.upper()}", max_results=max_results)

    def get_logs_by_timerange(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        max_results: int = 1000
    ) -> str:
        """
        Get log entries within a time range.

        Args:
            start_time: Start of time range (defaults to 1 hour ago)
            end_time: End of time range (defaults to now)
            max_results: Maximum number of entries to return

        Returns:
            String containing filtered log entries
        """
        if start_time is None:
            start_time = datetime.now() - timedelta(hours=1)
        if end_time is None:
            end_time = datetime.now()

        matching_lines = []

        for log_file in self.get_log_files():
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        # Extract timestamp from line (format: YYYY-MM-DD HH:MM:SS)
                        try:
                            timestamp_str = line.split('|')[0].strip()
                            log_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')

                            if start_time <= log_time <= end_time:
                                matching_lines.append(line)
                                if len(matching_lines) >= max_results:
                                    break
                        except (ValueError, IndexError):
                            # Skip lines that don't match expected format
                            continue

                if len(matching_lines) >= max_results:
                    break

            except Exception as e:
                matching_lines.append(f"Error reading {log_file}: {str(e)}\n")

        return ''.join(matching_lines)

    def get_log_stats(self) -> dict:
        """
        Get statistics about log files.

        Returns:
            Dictionary containing log file statistics
        """
        log_files = self.get_log_files()

        stats = {
            "total_files": len(log_files),
            "total_size_bytes": 0,
            "total_size_mb": 0,
            "files": []
        }

        for log_file in log_files:
            file_stat = log_file.stat()
            file_info = {
                "name": log_file.name,
                "path": str(log_file),
                "size_bytes": file_stat.st_size,
                "size_mb": round(file_stat.st_size / (1024 * 1024), 2),
                "modified": datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                "lines": sum(1 for _ in open(log_file, 'r', encoding='utf-8'))
            }
            stats["files"].append(file_info)
            stats["total_size_bytes"] += file_stat.st_size

        stats["total_size_mb"] = round(stats["total_size_bytes"] / (1024 * 1024), 2)

        return stats

    def clear_old_logs(self, days: int = 7) -> int:
        """
        Clear log files older than specified days.

        Args:
            days: Number of days to keep

        Returns:
            Number of files deleted
        """
        cutoff_time = datetime.now() - timedelta(days=days)
        deleted_count = 0

        for log_file in self.get_log_files():
            file_stat = log_file.stat()
            modified_time = datetime.fromtimestamp(file_stat.st_mtime)

            if modified_time < cutoff_time and log_file != self.log_file:
                try:
                    log_file.unlink()
                    deleted_count += 1
                    logging.info(f"🗑️  Deleted old log file: {log_file}")
                except Exception as e:
                    logging.error(f"❌ Failed to delete {log_file}: {e}")

        return deleted_count


# Singleton instance
file_logger = FileLogger()


def initialize_file_logging():
    """Initialize file-based logging (called at application startup)."""
    return file_logger
