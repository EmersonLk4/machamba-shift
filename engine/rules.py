"""Regras agronómicas R1 a R8: filtros e penalizações. A implementar na Fase 3.

R1 ciclo cabe na época · R2 temperatura tolerável · R3 pH tolerável ·
R4 sem repetir a cultura em anos seguidos · R5 penalização por família repetida ·
R8 preferências do agricultor. R6 e R7 resultam do próprio modelo.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.schemas import Crop, SoilProfile


@dataclass
class Constraints:
    """Preferências do agricultor que funcionam como filtros."""

    excluded: set[str] = field(default_factory=set)      # crop_id que não aceita plantar
    required: set[str] = field(default_factory=set)      # crop_id que têm de aparecer


def feasible(sequence: list[Crop], soil: SoilProfile, season_length_days: float,
             mean_temp_c: float, constraints: Constraints) -> bool:
    """True se a rotação passa todos os filtros."""
    raise NotImplementedError("Fase 3")


def family_repeats(sequence: list[Crop]) -> int:
    """Número de vezes que a mesma família botânica aparece em anos seguidos."""
    raise NotImplementedError("Fase 3")
