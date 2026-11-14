"""Pastas de dados. MACHAMBA_DATA_DIR permite apontar para outra pasta (usado nos testes)."""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent


def data_dir() -> Path:
    return Path(os.environ.get("MACHAMBA_DATA_DIR", PACKAGE_DIR))


def demo_dir() -> Path:
    """Dados dos locais de demonstração, versionados no git."""
    return data_dir() / "demo"


def cache_dir() -> Path:
    """Cache local, ignorada pelo git."""
    return data_dir() / "cache"
