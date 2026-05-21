"""Tests for event_logger module."""
import pytest
import sys
from pathlib import Path
import tempfile
import os

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from event_logger import EventLogger


class TestEventLoggerInit:
    """Test EventLogger initialization."""

    def test_init_with_string_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "test.log")
            logger = EventLogger(log_path)
            assert logger.path == Path(log_path)

    def test_init_with_path_object(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "test.log"
            logger = EventLogger(log_path)
            assert logger.path == log_path

    def test_creates_parent_directories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_path = Path(tmpdir) / "nested" / "dir" / "test.log"
            logger = EventLogger(nested_path)
            assert nested_path.parent.exists()


class TestEventLoggerLog:
    """Test EventLogger log method."""

    def test_log_writes_to_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "test.log"
            logger = EventLogger(log_path)
            
            message = "Test event"
            result = logger.log(message)
            
            # Check return value contains the message
            assert message in result
            
            # Check file was created and contains the message
            assert log_path.exists()
            content = log_path.read_text(encoding="utf-8")
            assert message in content

    def test_log_adds_timestamp(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "test.log"
            logger = EventLogger(log_path)
            
            result = logger.log("Test")
            
            # Timestamp format: [YYYY-MM-DD HH:MM:SS]
            assert result.startswith("[")
            assert "]" in result

    def test_log_multiple_entries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "test.log"
            logger = EventLogger(log_path)
            
            logger.log("First event")
            logger.log("Second event")
            logger.log("Third event")
            
            content = log_path.read_text(encoding="utf-8")
            lines = content.strip().split("\n")
            
            assert len(lines) == 3
            assert "First event" in lines[0]
            assert "Second event" in lines[1]
            assert "Third event" in lines[2]

    def test_log_appends_to_existing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "test.log"
            
            # Write initial content
            log_path.write_text("Initial content\n", encoding="utf-8")
            
            logger = EventLogger(log_path)
            logger.log("New event")
            
            content = log_path.read_text(encoding="utf-8")
            assert "Initial content" in content
            assert "New event" in content

    def test_log_handles_unicode(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "test.log"
            logger = EventLogger(log_path)
            
            unicode_message = "Событие тестирования 🚀"
            logger.log(unicode_message)
            
            content = log_path.read_text(encoding="utf-8")
            assert unicode_message in content

    def test_log_returns_formatted_string(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "test.log"
            logger = EventLogger(log_path)
            
            result = logger.log("Test message")
            
            # Should match format: [YYYY-MM-DD HH:MM:SS] message
            import re
            pattern = r'^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] .+$'
            assert re.match(pattern, result) is not None
