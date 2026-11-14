"""Regras agronómicas: filtros e penalizações.

R2 temperatura tolerável   filtro, só quando os limites ECOCROP estão preenchidos
R3 pH tolerável            filtro, só quando há pH do solo e limites da cultura
R4 sem repetir a cultura   filtro (a monocultura é calculada à parte, como referência)
R5 família repetida        penalização no score (family_repeats)
R8 preferências            filtro (culturas excluídas e obrigatórias)

R1 (o ciclo cabe na época das chuvas) NÃO é filtro. Com dados reais, a época de crescimento
pelo critério FAO é mais curta do que qualquer ciclo em zonas semi-áridas (50 dias em
Chókwè), e o filtro eliminaria todas as culturas. O balanço hídrico já penaliza um ciclo
que não cabe na chuva, através do WRSI. R6 e R7 também resultam do próprio modelo.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.schemas import Crop, SoilProfile


@dataclass
class Constraints:
    """Preferências do agricultor que funcionam como filtros."""

    excluded: set[str] = field(default_factory=set)      # crop_id que não aceita plantar
    required: set[str] = field(default_factory=set)      # crop_id que têm de aparecer


def thermal_suitability(crop: Crop, mean_temp_c: float) -> float | None:
    """Adequação térmica de 0 a 1 (trapézio ECOCROP), ou None se faltarem os limites."""
    limits = (crop.tmin, crop.topmin, crop.topmax, crop.tmax)
    if any(value is None for value in limits):
        return None
    tmin, topmin, topmax, tmax = limits
    if mean_temp_c < tmin or mean_temp_c > tmax:
        return 0.0
    if mean_temp_c < topmin:
        return (mean_temp_c - tmin) / (topmin - tmin) if topmin > tmin else 1.0
    if mean_temp_c > topmax:
        return (tmax - mean_temp_c) / (tmax - topmax) if tmax > topmax else 1.0
    return 1.0


def ph_ok(crop: Crop, soil: SoilProfile) -> bool:
    """False só quando há dados e o pH está fora do intervalo da cultura."""
    if soil.ph is None or crop.ph_min is None or crop.ph_max is None:
        return True
    return crop.ph_min <= soil.ph <= crop.ph_max


def family_repeats(sequence: list[Crop]) -> int:
    """Número de vezes que a mesma família botânica aparece em anos seguidos."""
    return sum(1 for a, b in zip(sequence, sequence[1:], strict=False) if a.family == b.family)


def feasible(sequence: list[Crop], soil: SoilProfile, mean_temp_c: float,
             constraints: Constraints) -> bool:
    """True se a rotação passa todos os filtros."""
    ids = [crop.crop_id for crop in sequence]
    if any(a == b for a, b in zip(ids, ids[1:], strict=False)):          # R4
        return False
    if constraints.excluded & set(ids):                                   # R8
        return False
    if not constraints.required <= set(ids):                              # R8
        return False
    for crop in sequence:
        if thermal_suitability(crop, mean_temp_c) == 0.0:                 # R2
            return False
        if not ph_ok(crop, soil):                                         # R3
            return False
    return True
