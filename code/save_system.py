import os
import pickle
from typing import Any

SAVE_DIR = os.path.join(os.path.dirname(__file__), "save_data")


def _save_path(filename: str) -> str:
    os.makedirs(SAVE_DIR, exist_ok=True)
    return os.path.join(SAVE_DIR, filename)


def save_game_state(state: Any, filename: str = "autosave.pkl") -> str:
    path = _save_path(filename)
    with open(path, "wb") as f:
        pickle.dump(state, f, protocol=pickle.HIGHEST_PROTOCOL)
    return path


def load_game_state(filename: str = "autosave.pkl") -> Any:
    path = _save_path(filename)
    with open(path, "rb") as f:
        return pickle.load(f)


def has_save_file(filename: str = "autosave.pkl") -> bool:
    return os.path.exists(_save_path(filename))
