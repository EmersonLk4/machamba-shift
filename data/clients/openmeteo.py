"""Cliente do Open-Meteo (arquivo histórico, reanálise ERA5, sem chave).

Documentação: https://open-meteo.com/en/docs/historical-weather-api
É o plano B do clima quando o NASA POWER não responde, e serve para comparar a ET0.
NÃO é uma fonte NASA: quando for usado, a interface tem de o dizer.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data.clients.http import get_json

BASE_URL = "https://archive-api.open-meteo.com/v1/archive"
SOURCE = "Open-Meteo (ERA5)"
DAILY = (
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "et0_fao_evapotranspiration",
)


def fetch_daily(lat: float, lon: float, start: str = "1990-01-01", end: str = "2024-12-31",
                use_cache: bool = True, timeout: float = 60, retries: int = 2) -> dict:
    """Pede a série diária. start e end no formato AAAA-MM-DD."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "daily": ",".join(DAILY),
        "timezone": "UTC",
    }
    return get_json(BASE_URL, params=params, use_cache=use_cache, timeout=timeout,
                    retries=retries)


def parse_daily(payload: dict) -> pd.DataFrame:
    """Converte a resposta num DataFrame diário com as colunas do contrato.

    Humidade, vento, radiação e humidade do solo ficam vazios: não são pedidos.
    et0_ref_mm é a ET0 de Penman-Monteith do próprio Open-Meteo, guardada só para
    comparação; a et0_mm do contrato é sempre calculada em data/features.py.
    """
    daily = payload["daily"]
    frame = pd.DataFrame(
        {
            "p_mm": daily["precipitation_sum"],
            "tmax_c": daily["temperature_2m_max"],
            "tmin_c": daily["temperature_2m_min"],
            "et0_ref_mm": daily["et0_fao_evapotranspiration"],
        },
        index=pd.to_datetime(daily["time"]),
        dtype="float64",
    )
    frame.index.name = "date"
    frame["tmean_c"] = (frame["tmax_c"] + frame["tmin_c"]) / 2
    for column in ("rh_pct", "wind_ms", "rad_mj", "gwetroot"):
        frame[column] = np.nan
    frame["source"] = SOURCE
    frame["qc_flag"] = 0
    return frame.sort_index()


def fetch_years(lat: float, lon: float, start_year: int, end_year: int) -> pd.DataFrame:
    """Série diária de 1 de Janeiro de start_year a 31 de Dezembro de end_year."""
    payload = fetch_daily(lat, lon, f"{start_year}-01-01", f"{end_year}-12-31")
    return parse_daily(payload)
