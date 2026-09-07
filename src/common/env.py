"""Общий доступ к .env и корню репозитория.

Вынесено сюда, а не скопировано: читалка .env уже написана в notify.py
и работает — дублировать её значит завести второе место, где может
разойтись формат файла.
"""
from __future__ import annotations

import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _ensure_root_on_path() -> None:
    root = str(repo_root())
    if root not in sys.path:
        sys.path.insert(0, root)


def load_env() -> dict:
    _ensure_root_on_path()
    import notify                                   # noqa: E402
    return notify.load_env()
