"""Score multiobjectivo.

    S(r) = soma_k w_k * s_k(r) - lambda * v(r),   soma_k w_k = 1,  s_k em [0, 1]

v(r) é o número de repetições de família botânica em anos seguidos. Um indicador que não
pôde ser avaliado (None) sai do score e o seu peso é repartido pelos restantes.
"""

from __future__ import annotations

from engine.schemas import INDICATORS


def minmax(value: float, lower: float, upper: float) -> float:
    """Normalização min-max com corte em [0, 1]. Se os limites coincidem devolve 0,5."""
    if upper <= lower:
        return 0.5
    return min(1.0, max(0.0, (value - lower) / (upper - lower)))


def normalize_weights(raw: dict[str, float], available: set[str] | None = None
                      ) -> dict[str, float]:
    """Pesos não negativos que somam 1, só sobre os indicadores disponíveis.

    Aceita cursores (0 a 10) ou pesos; os indicadores fora de `available` ficam com peso 0.
    """
    available = set(INDICATORS) if available is None else available
    cleaned = {name: max(0.0, float(raw.get(name, 0.0))) if name in available else 0.0
               for name in INDICATORS}
    total = sum(cleaned.values())
    if total <= 0:
        raise ValueError("Pelo menos um objectivo disponível tem de ter peso positivo")
    return {name: value / total for name, value in cleaned.items()}


def score(indicators: dict[str, float | None], weights: dict[str, float], lam: float = 0.0,
          repeats: int = 0) -> float:
    """Score de uma rotação. `weights` já normalizados sobre os indicadores disponíveis."""
    total = sum(weights[name] * value for name, value in indicators.items()
                if value is not None)
    return total - lam * repeats
