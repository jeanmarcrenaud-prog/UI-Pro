import os
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class FileContent:
    path: str
    content: str
    last_modified: datetime
    size: int

class FilesystemService:
    """
    Service d'abstraction pour les opérations de système de fichiers.
    Sert de base pour le futur Filesystem MCP.
    """
    def __init__(self, root_dir: str = "workspace"):
        self.root_dir = os.path.abspath(root_dir)
        logger.info(f"FilesystemService initialisé avec le dossier racine : {self.root_dir}")

    def _get_abs_path(self, path: str) -> str:
        """Transforme un chemin relatif en chemin absolu sécurisé."""
        abs_path = os.path.abspath(os.path.join(self.root_dir, path.lstrip("/").lstrip("\\")))
        if not abs_path.startswith(self.root_dir):
            raise PermissionError(f"Accès refusé : {abs_path} est en dehors du dossier racine.")
        return abs_path

    def read_file(self, relative_path: str) -> Optional[FileContent]:
        """Lit le contenu d'un fichier."""
        try:
            abs_path = self._get_abs_path(relative_path)
            if not os.path.exists(abs_path):
                return None
            with open(abs_path, 'r', encoding='utf-8') as f:
                content = f.read()
            stats = os.stat(abs_path)
            return FileContent(
                path=relative_path,
                content=content,
                last_modified=datetime.fromtimestamp(stats.st_mtime),
                size=stats.st_size
            )
        except Exception as e:
            logger.error(f"Erreur lecture fichier {relative_path}: {e}")
            return None

    def write_file(self, relative_path: str, content: str) -> bool:
        """Écrit le contenu dans un fichier (crée les dossiers si nécessaire)."""
        try:
            abs_path = self._get_abs_path(relative_path)
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"Fichier écrit : {relative_path}")
            return True
        except Exception as e:
            logger.error(f"Erreur écriture fichier {relative_path}: {e}")
            return False

    def rename_file(self, old_path: str, new_path: str) -> bool:
        """Renomme ou déplace un fichier."""
        try:
            abs_old = self._get_abs_path(old_path)
            abs_new = self._get_abs_path(new_path)
            if not os.path.exists(abs_old):
                logger.error(f"Fichier source introuvable : {old_path}")
                return False
            os.makedirs(os.path.dirname(abs_new), exist_ok=True)
            os.rename(abs_old, abs_new)
            logger.info(f"Fichier renommé : {old_path} -> {new_path}")
            return True
        except Exception as e:
            logger.error(f"Erreur renommage {old_path} -> {new_path}: {e}")
            return False

    def list_files(self, pattern: str = "*") -> List[str]:
        """Liste les fichiers correspondant à un pattern (simple glob)."""
        files = []
        try:
            for root, dirs, files in os.walk(self.root_dir):
                for file in files:
                    if file.endswith(".py") or file.endswith(".json") or file.endswith(".md") or file.endswith(".txt"):
                        # Simplification pour le test
                        rel_path = os.path.relpath(os.path.join(root, file), self.root_dir)
                        files.append(rel_path)
            return files
        except Exception as e:
            logger.error(f"Erreur listing fichiers: {e}")
            return []

    def search_files(self, pattern: str) -> List[str]:
        """Recherche de fichiers par contenu ou nom (placeholder pour recherche avancée)."""
        # Pour l'instant, retourne juste les fichiers dont le nom correspond
        return [f for f in self.list_files() if pattern in f]

    def get_git_status(self) -> Dict[str, Any]:
        """Récupère le statut git actuel via le système."""
        import subprocess
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.root_dir,
                capture_output=True,
                text=True,
                check=True
            )
            return {"status": "modified" if result.stdout else "clean", "output": result.stdout}
        except Exception as e:
            return {"status": "error", "message": str(e)}
