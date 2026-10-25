"""Minimal security tests for Hermes Phase 7."""
import pytest
from pathlib import Path
from backend.domain.core.filesystem_service import FilesystemService, MAX_FILE_SIZE
from backend.domain.settings import Settings


def test_path_traversal_blocked(tmp_path):
    """Path traversal outside workspace must be blocked (Phase 7)."""
    fs = FilesystemService(root_dir=str(tmp_path))
    with pytest.raises(PermissionError, match="escapes workspace"):
        fs.read_file("../../etc/passwd")


def test_sensitive_name_blocked(tmp_path):
    """Sensitive names (.env, .git, etc.) must be blocked (Phase 7)."""
    fs = FilesystemService(root_dir=str(tmp_path))
    with pytest.raises(PermissionError, match="sensitive"):
        fs.read_file(".env")


def test_execute_intent_disabled_by_default():
    """Execute intent must be disabled by default (Phase 7 settings)."""
    s = Settings()
    assert s.hermes_execute_intent_enabled is False
    assert s.hermes_auto_approve_permissions is False