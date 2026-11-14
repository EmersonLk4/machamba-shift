"""Sessão HTTP partilhada, com cache em disco e novas tentativas.

O mesmo URL nunca é pedido duas vezes: as respostas ficam em data/cache/http_cache.sqlite
sem prazo de validade (os dados históricos não mudam).
"""

from __future__ import annotations

import time

import requests
import requests_cache

from data.paths import cache_dir

TIMEOUT_S = 30
RETRIES = 2

_session: requests_cache.CachedSession | None = None


def session() -> requests_cache.CachedSession:
    """Devolve a sessão com cache, criando-a na primeira chamada."""
    global _session
    if _session is None:
        cache_dir().mkdir(parents=True, exist_ok=True)
        _session = requests_cache.CachedSession(
            str(cache_dir() / "http_cache"),
            backend="sqlite",
            expire_after=requests_cache.NEVER_EXPIRE,
            allowable_codes=(200,),
        )
    return _session


def get_json(url: str, params=None, headers: dict | None = None, use_cache: bool = True,
             timeout: float = TIMEOUT_S, retries: int = RETRIES) -> dict:
    """GET que devolve JSON. Tenta de novo com espera crescente; no fim lança RuntimeError."""
    client = session() if use_cache else requests
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = client.get(url, params=params, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as error:
            last_error = error
            if attempt < retries:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Pedido falhou depois de {retries + 1} tentativas: {url}") from last_error
