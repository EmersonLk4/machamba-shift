"""Balanço parcial de azoto de uma rotação. A implementar na Fase 3.

    B_N(r) = soma_t [ F(c_t) - Y(c_t) * n_g(c_t) ]      [kg N/ha]

F é o N fixado (zero nas não leguminosas), Y o rendimento em grão (t/ha) e n_g o N
exportado por tonelada de grão. É um índice comparativo, não uma previsão do N no solo.
"""

from __future__ import annotations

from engine.schemas import Crop


def n_balance(sequence: list[Crop], yields_t_ha: list[float]) -> float:
    """Balanço parcial de N da rotação, em kg N/ha."""
    raise NotImplementedError("Fase 3")


def rotation_multiplier(previous: Crop | None, current: Crop, beta: float) -> float:
    """1 + beta se a cultura anterior é leguminosa e a actual é cereal; senão 1."""
    raise NotImplementedError("Fase 3")
