# backend/infrastructure/checkpointer.py (new file)
from langgraph.checkpoint.sqlite import AsyncSqliteSaver
from pathlib import Path
from contextlib import asynccontextmanager

class CheckpointManager:
    def __init__(self, settings):
        self.db_path = Path(settings.data_dir) / "checkpoints.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.saver = None

    async def get_saver(self):
        if not self.saver:
            self.saver = AsyncSqliteSaver.from_conn_string(f"sqlite+aiosqlite:///{self.db_path}")
        return self.saver