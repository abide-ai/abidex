"""
JSONL (JSON Lines) file sink for telemetry events.
"""

import json
import os
from pathlib import Path
from typing import Optional, TextIO
from threading import Lock

from ..client import Event, TelemetrySink
from ..utils.redaction import redact_sensitive_data


class JSONLSink:
    """
    Sink that writes events to a JSONL file.
    """
    
    def __init__(
        self,
        file_path: str,
        auto_flush: bool = True,
        create_dirs: bool = True,
        redact_sensitive: bool = True,
        max_file_size: Optional[int] = None,  # Max size in bytes before rotation
        backup_count: int = 5
    ):
        self.file_path = Path(file_path)
        self.auto_flush = auto_flush
        self.redact_sensitive = redact_sensitive
        self.max_file_size = max_file_size
        self.backup_count = backup_count
        self._file: Optional[TextIO] = None
        self._lock = Lock()
        
        # Create directories if needed
        if create_dirs:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._open_file()
    
    def _open_file(self) -> None:
        """Open the log file for writing."""
        self._file = open(self.file_path, 'a', encoding='utf-8')
    
    def _close_file(self) -> None:
        """Close the log file."""
        if self._file:
            self._file.close()
            self._file = None
    
    def _rotate_file_if_needed(self) -> None:
        """Rotate the log file if it exceeds max size."""
        if not self.max_file_size or not self._file:
            return
        
        try:
            current_size = self.file_path.stat().st_size
            if current_size >= self.max_file_size:
                self._rotate_file()
        except OSError:
            pass  # File might not exist yet
    
    def _rotate_file(self) -> None:
        """Rotate the log file."""
        self._close_file()
        
        # Rotate existing backup files
        for i in range(self.backup_count - 1, 0, -1):
            old_file = self.file_path.with_suffix(f"{self.file_path.suffix}.{i}")
            new_file = self.file_path.with_suffix(f"{self.file_path.suffix}.{i + 1}")
            
            if old_file.exists():
                if new_file.exists():
                    new_file.unlink()
                old_file.rename(new_file)
        
        # Move current file to .1
        backup_file = self.file_path.with_suffix(f"{self.file_path.suffix}.1")
        if self.file_path.exists():
            if backup_file.exists():
                backup_file.unlink()
            self.file_path.rename(backup_file)
        
        # Reopen new file
        self._open_file()
    
    def send(self, event: Event) -> None:
        """Send an event to the JSONL file."""
        # Skip unsampled events
        if not event.sampled:
            return
            
        with self._lock:
            if not self._file:
                return
            
            try:
                # Convert event to dict
                event_dict = event.to_dict()
                
                # Redact sensitive data if enabled
                if self.redact_sensitive:
                    event_dict = redact_sensitive_data(event_dict)
                
                # Write as JSON line
                json_line = json.dumps(event_dict, default=str, separators=(',', ':'))
                self._file.write(json_line + '\n')
                
                if self.auto_flush:
                    self._file.flush()
                
                # Check if rotation is needed
                self._rotate_file_if_needed()
                
            except Exception as e:
                print(f"Error writing to JSONL sink: {e}")
    
    def flush(self) -> None:
        """Flush the file buffer."""
        with self._lock:
            if self._file:
                try:
                    self._file.flush()
                    os.fsync(self._file.fileno())
                except Exception as e:
                    print(f"Error flushing JSONL sink: {e}")
    
    def close(self) -> None:
        """Close the sink and file."""
        with self._lock:
            self.flush()
            self._close_file()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class RotatingJSONLSink(JSONLSink):
    """
    JSONL sink with automatic file rotation based on size or time.
    """
    
    def __init__(
        self,
        file_path: str,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        **kwargs
    ):
        super().__init__(
            file_path=file_path,
            max_file_size=max_file_size,
            backup_count=backup_count,
            **kwargs
        )
