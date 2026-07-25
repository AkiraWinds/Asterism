import os
from pathlib import Path


def get_data_root() -> Path:
    root = os.environ.get("ASTERISM_DATA_ROOT")
    if root:
        return Path(root)
    return Path.home() / "AsterismData"
