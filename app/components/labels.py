"""Etiquetas de origem dos dados.

Cada número mostrado na interface declara de onde vem. É isto que torna a
ferramenta defensável: nunca apresentar uma simulação como se fosse uma medição.
"""

from __future__ import annotations

ORIGINS: dict[str, str] = {
    "observado": "Observado por satélite",
    "estimado": "Estimado por satélite e calibrado com estações",
    "modelado": "Modelado (reanálise ou mapa global)",
    "literatura": "Valor de literatura",
    "simulado": "Simulado pelo motor",
    "hipotese": "Hipótese de trabalho",
}


def origin_label(kind: str, source: str | None = None) -> str:
    """Texto curto para pôr ao lado de um indicador, por exemplo 'Modelado · NASA POWER'."""
    if kind not in ORIGINS:
        raise ValueError(f"Origem desconhecida: {kind}. Usar uma de {sorted(ORIGINS)}")
    name = kind.capitalize() if kind != "hipotese" else "Hipótese"
    return f"{name} · {source}" if source else name
