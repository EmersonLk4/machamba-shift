"""Enumeração de rotações e ponto de entrada do motor. A implementar na Fase 3."""

from __future__ import annotations

from engine.rules import Constraints
from engine.schemas import Recommendation, Site


def recommend(site: Site, crops: list[str], weights: dict[str, float], scenario: str,
              constraints: Constraints | None = None) -> Recommendation:
    """Devolve as quatro estratégias comparadas para um local e um cenário.

    Passos: clima do cenário -> estatísticas por cultura -> candidatos viáveis
    (itertools.product, 3 campanhas) -> indicadores -> score -> explicação.
    """
    raise NotImplementedError("Fase 3")
