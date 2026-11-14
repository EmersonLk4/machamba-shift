"""Balanço hídrico diário do solo (FAO-56) e WRSI. A implementar na Fase 3.

Fórmulas (secção 5B do plano):
    ETc  = Kc * ET0
    TAW  = 1000 * (fc_vol - wp_vol) * zr_m          [mm]
    RAW  = p * TAW
    Ks   = 1 se Dr <= RAW; senão (TAW - Dr) / ((1 - p) * TAW)
    ETa  = Ks * ETc
    Dr_i = min(TAW, max(0, Dr_{i-1} - P_i + ETa_i))
    WRSI = 100 * soma(ETa) / soma(ETc)
    Yrel = max(0, 1 - Ky * (1 - soma(ETa) / soma(ETc)))
"""

from __future__ import annotations

import pandas as pd

from engine.schemas import Crop, SoilProfile


def kc_curve(crop: Crop) -> list[float]:
    """Kc diário ao longo do ciclo: quatro fases, interpolação linear nas de transição."""
    raise NotImplementedError("Fase 3")


def simulate_season(days: pd.DataFrame, crop: Crop, soil: SoilProfile) -> dict[str, float]:
    """Simula uma cultura numa campanha.

    days: DataFrame diário da sementeira à colheita, com as colunas p_mm e et0_mm.
    Devolve {"wrsi": ..., "y_rel": ..., "etc_mm": ...}.
    """
    raise NotImplementedError("Fase 3")


def season_stats(clim: pd.DataFrame, crop: Crop, soil: SoilProfile, sow_month: int,
                 sow_day: int) -> pd.DataFrame:
    """Corre simulate_season para cada campanha e devolve uma linha por campanha."""
    raise NotImplementedError("Fase 3")
