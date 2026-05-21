from __future__ import annotations

from datetime import datetime
from pathlib import Path


class EventLogger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, message: str) -> str:
        timestamped = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
        with self.path.open("a", encoding="utf-8") as file:
            file.write(timestamped + "\n")
        return timestamped
