"""Índice de azoto de uma rotação e efeito da leguminosa no cereal seguinte.

O plano previa um balanço em kg N/ha (N fixado menos N exportado no grão). Esse balanço
precisa de rendimentos, N fixado e N exportado para todas as culturas, que ainda não estão
em params/. Enquanto não estiverem, o motor usa um ÍNDICE sem unidades:

    I_N(r) = soma_t g(c_t)
    g(c)   = + ndfa / 100            se c é leguminosa (fracção do N que vem do ar)
           = - exigência do grupo    caso contrário (cereal 1,0; oleaginosa e raiz 0,6)

Mede se a rotação repõe ou só retira azoto. Não é uma previsão do N no solo.
"""

from __future__ import annotations

from engine.schemas import Crop


def n_points(crop: Crop, defaults: dict) -> float:
    """Contribuição de uma campanha desta cultura para o índice."""
    if crop.is_legume:
        return (crop.ndfa or 0.0) / 100.0
    return -float(defaults["n_demand_index"].get(crop.group, 1.0))


def n_index(sequence: list[Crop], defaults: dict) -> float:
    """Índice de azoto da rotação (soma das campanhas)."""
    return sum(n_points(crop, defaults) for crop in sequence)


def n_index_bounds(crops: list[Crop], defaults: dict, horizon: int) -> tuple[float, float]:
    """Limites fixos para normalizar: a pior e a melhor cultura repetidas `horizon` vezes."""
    points = [n_points(crop, defaults) for crop in crops]
    return horizon * min(points), horizon * max(points)


def rotation_multiplier(previous: Crop | None, current: Crop, beta: float) -> float:
    """1 + beta se a cultura anterior é leguminosa e a actual é cereal; senão 1."""
    if previous is not None and previous.is_legume and current.group == "cereal":
        return 1.0 + beta
    return 1.0
