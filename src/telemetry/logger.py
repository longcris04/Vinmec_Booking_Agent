import logging
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

# Console Windows mặc định là cp1252 -> ghi tiếng Việt sẽ ném UnicodeEncodeError.
# Ép stdout/stderr về UTF-8 để log (và print) tiếng Việt không vỡ.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if hasattr(record, "payload"):
            payload["payload"] = record.payload

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)

class IndustryLogger:
    """
    Structured logger that simulates industry practices.
    Logs to both console and a file in JSON format.
    """
    def __init__(self, name: str = "AI-Lab-Agent", log_dir: str = "logs"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False

        if self.logger.handlers:
            self.logger.handlers.clear()
        
        self.log_dir = os.path.abspath(log_dir)
        os.makedirs(self.log_dir, exist_ok=True)

        log_file = os.path.join(self.log_dir, f"{datetime.now().strftime('%Y-%m-%d')}.log")
        # encoding=utf-8: log tiếng Việt (mặc định FileHandler dùng cp1252 trên Windows -> lỗi)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(JSONFormatter())

        console_handler = logging.StreamHandler()
        # Console Windows có thể là cp1252 -> ép stream về utf-8 (bỏ qua nếu không hỗ trợ)
        try:
            console_handler.stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except Exception:
            pass
        console_handler.setFormatter(JSONFormatter())
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def log_event(self, event_type: str, data: Dict[str, Any]):
        """Logs an event with a timestamp and type."""
        payload = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": event_type,
            "data": data,
        }
        self.logger.info(event_type, extra={"payload": payload})

    def info(self, msg: str):
        self.logger.info(msg)

    def error(self, msg: str, exc_info=True):
        self.logger.error(msg, exc_info=exc_info)

    def read_trace(self, log_file: Optional[str] = None, event_types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Read structured trace events from a log file."""
        target_file = log_file or os.path.join(self.log_dir, f"{datetime.now().strftime('%Y-%m-%d')}.log")
        if not os.path.isabs(target_file):
            target_file = os.path.join(self.log_dir, target_file)

        if not os.path.exists(target_file):
            return []

        events: List[Dict[str, Any]] = []
        with open(target_file, "r", encoding="utf-8") as file_handle:
            for line in file_handle:
                line = line.strip()
                if not line:
                    continue

                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                payload = record.get("payload")
                if not isinstance(payload, dict):
                    continue

                if event_types and payload.get("event") not in event_types:
                    continue

                events.append(payload)

        return events

# Global logger instance
logger = IndustryLogger()
