"""Score multiobjectivo. A implementar na Fase 3.

    S(r) = soma_k w_k * s_k(r) - lambda * v(r),   soma_k w_k = 1,  s_k em [0, 1]

Os indicadores sem escala natural (água, solo, margem) são normalizados por min-max
sobre os candidatos do local. Os limites são calculados no cenário histórico e
congelados para os outros cenários.
"""

from __future__ import annotations

import pandas as pd


def normalize_weights(sliders: dict[str, float]) -> dict[str, float]:
    """Converte cursores de 0 a 10 em pesos que somam 1."""
    raise NotImplementedError("Fase 3")


def minmax(values: pd.Series, lower: float, upper: float) -> pd.Series:
    """Normalização min-max com corte em [0, 1]."""
    raise NotImplementedError("Fase 3")


def score(table: pd.DataFrame, weights: dict[str, float], lam: float) -> pd.DataFrame:
    """Acrescenta a coluna 'score' a uma tabela com uma linha por rotação candidata."""
    raise NotImplementedError("Fase 3")
