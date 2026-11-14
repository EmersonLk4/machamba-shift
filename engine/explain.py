"""Gerador de explicações em linguagem simples. A implementar na Fase 3.

A contribuição de cada objectivo para a vantagem sobre a monocultura é
w_k * (s_k da recomendada - s_k da monocultura). As duas maiores positivas dão as
frases "porquê"; a mais negativa dá a frase "em troca de quê", que nunca se omite.
"""

from __future__ import annotations

from engine.schemas import StrategyResult


def contributions(best: StrategyResult, baseline: StrategyResult,
                  weights: dict[str, float]) -> dict[str, float]:
    """Contribuição de cada indicador para a diferença de score."""
    raise NotImplementedError("Fase 3")


def explain(best: StrategyResult, baseline: StrategyResult,
            weights: dict[str, float]) -> list[str]:
    """Três frases: duas razões e um custo."""
    raise NotImplementedError("Fase 3")
