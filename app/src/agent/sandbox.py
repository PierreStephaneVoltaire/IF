
from __future__ import annotations
import os
from typing import Optional

from config import SANDBOX_PATH


def sandbox_path_for(conversation_id: str) -> str:

    path = os.path.join(SANDBOX_PATH, conversation_id)
    os.makedirs(path, exist_ok=True)
    return os.path.abspath(path)


def get_sandbox_root() -> str:

    os.makedirs(SANDBOX_PATH, exist_ok=True)
    return os.path.abspath(SANDBOX_PATH)


def file_in_sandbox(conversation_id: str, filepath: str) -> str:

    sandbox = sandbox_path_for(conversation_id)
    return os.path.join(sandbox, filepath)


def is_path_in_sandbox(conversation_id: str, filepath: str) -> bool:

    real_path = os.path.realpath(filepath)
    allowed_root = os.path.realpath(sandbox_path_for(conversation_id))
    return real_path.startswith(allowed_root)
