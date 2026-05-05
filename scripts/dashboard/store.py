import sys
from pathlib import Path
from functools import lru_cache

scripts_dir = Path(__file__).resolve().parent.parent
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

from core.sqlite_store import SQLiteStore
from core.embedder import HarrierEmbedder

_db_path = str(Path(__file__).resolve().parent.parent.parent / "graph.db")


@lru_cache(maxsize=1)
def get_store() -> SQLiteStore:
    return SQLiteStore(db_path=_db_path, embedder=HarrierEmbedder())
