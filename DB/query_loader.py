import os
from functools import lru_cache

BASE_DIR = os.path.join(os.path.dirname(__file__), "queries")


@lru_cache()
def load_query(path: str) -> str:
    full_path = os.path.join(BASE_DIR, path)

    if not os.path.exists(full_path):
        raise FileNotFoundError(f"SQL file not found: {full_path}")

    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()
