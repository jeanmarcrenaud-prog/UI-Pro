import os
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 Mo
BLOCKED_NAMES = {".env", ".git", ".ssh", "id_rsa", "credentials", "secrets", ".aws", ".kube"}

@dataclass
class FileContent:
    path: str
    content: str
    last_modified: datetime
    size: int


class FilesystemService:
    """Sandbox fichiers limité au workspace (Phase 7)."""

    def __init__(self, root_dir: str = "workspace"):
        self.root_dir = Path(root_dir).resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)
        logger.info("FilesystemService root=%s", self.root_dir)

    def _get_abs_path(self, path: str) -> Path:
        # Interdit chemins absolus et traversal
        candidate = (self.root_dir / str(path).lstrip("/\\")).resolve()
        if not str(candidate).startswith(str(self.root_dir)):
            raise PermissionError(f"Path escapes workspace: {path}")
        # Bloque noms sensibles
        if any(part.lower() in BLOCKED_NAMES for part in candidate.parts):
            raise PermissionError(f"Access to sensitive path denied: {path}")
        return candidate

    def read_file(self, relative_path: str) -> Optional[FileContent]:
        try:
            abs_path = self._get_abs_path(relative_path)
            if not abs_path.is_file():
                return None
            size = abs_path.stat().st_size
            if size > MAX_FILE_SIZE:
                raise PermissionError(f"File too large (>{MAX_FILE_SIZE} bytes): {relative_path}")
            content = abs_path.read_text(encoding="utf-8")
            stats = abs_path.stat()
            return FileContent(
                path=relative_path,
                content=content,
                last_modified=datetime.fromtimestamp(stats.st_mtime),
                size=size,
            )
        except PermissionError:
            raise
        except Exception as e:
            logger.error("Erreur lecture %s: %s", relative_path, e)
            return None

    def write_file(self, relative_path: str, content: str) -> bool:
        try:
            if len(content.encode("utf-8")) > MAX_FILE_SIZE:
                raise PermissionError(f"Content too large (>{MAX_FILE_SIZE} bytes)")
            abs_path = self._get_abs_path(relative_path)
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            # Écriture atomique
            tmp = abs_path.with_suffix(abs_path.suffix + ".tmp")
            tmp.write_text(content, encoding="utf-8")
            tmp.replace(abs_path)
            logger.info("Fichier écrit : %s", relative_path)
            return True
        except PermissionError:
            raise
        except Exception as e:
            logger.error("Erreur écriture %s: %s", relative_path, e)
            return False

    def rename_file(self, old_path: str, new_path: str) -> bool:
        try:
            abs_old = self._get_abs_path(old_path)
            abs_new = self._get_abs_path(new_path)
            if not abs_old.exists():
                return False
            abs_new.parent.mkdir(parents=True, exist_ok=True)
            abs_old.rename(abs_new)
            return True
        except Exception as e:
            logger.error("Erreur renommage %s → %s: %s", old_path, new_path, e)
            return False

    def list_files(self, pattern: str = "*") -> List[str]:
        """Liste les fichiers sous le workspace (extensions utiles uniquement)."""
        result: List[str] = []
        try:
            for root, _dirs, filenames in os.walk(self.root_dir):
                for name in filenames:
                    if name.endswith((".py", ".json", ".md", ".txt", ".yaml", ".yml", ".toml")):
                        rel = os.path.relpath(os.path.join(root, name), self.root_dir)
                        result.append(rel)
            return result
        except Exception as e:
            logger.error("Erreur listing: %s", e)
            return []

    def search_files(self, pattern: str) -> List[str]:
        return [f for f in self.list_files() if pattern in f]

    def get_git_status(self) -> Dict[str, Any]:
        import subprocess
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.root_dir,
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
            return {"status": "modified" if result.stdout else "clean", "output": result.stdout}
        except Exception as e:
            return {"status": "error", "message": str(e)}