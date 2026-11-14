"""Cliente do NASA POWER (clima diário por ponto, sem chave).

Documentação: https://power.larc.nasa.gov/docs/services/api/temporal/
A resposta JSON traz os valores em properties.parameter.<PARAM>.<AAAAMMDD>.
Valores em falta vêm como -999.

Meteorologia: reanálise MERRA-2 (0,5° x 0,625°). Radiação: CERES (1°).
São dados MODELADOS, não medições no local.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data.clients.http import get_json

BASE_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
FILL_VALUE = -999.0
SOURCE = "NASA POWER"

# Parâmetro POWER -> coluna do contrato ClimateDaily
RENAME = {
    "PRECTOTCORR": "p_mm",
    "T2M_MAX": "tmax_c",
    "T2M_MIN": "tmin_c",
    "T2M": "tmean_c",
    "RH2M": "rh_pct",
    "WS2M": "wind_ms",
    "ALLSKY_SFC_SW_DWN": "rad_mj",   # MJ/m²/dia na comunidade AG
    "GWETROOT": "gwetroot",
    "GWETTOP": "gwettop",
}


def build_params(lat: float, lon: float, start: str, end: str) -> dict[str, str]:
    """Parâmetros do pedido. start e end no formato AAAAMMDD."""
    return {
        "parameters": ",".join(RENAME),
        "community": "AG",
        "longitude": f"{lon:.4f}",
        "latitude": f"{lat:.4f}",
        "start": start,
        "end": end,
        "format": "JSON",
    }


def fetch_daily(lat: float, lon: float, start: str = "19900101", end: str = "20241231",
                use_cache: bool = True, timeout: float = 30, retries: int = 2) -> dict:
    """Pede a série diária e devolve o JSON tal como chega."""
    return get_json(BASE_URL, params=build_params(lat, lon, start, end), use_cache=use_cache,
                    timeout=timeout, retries=retries)


def parse_daily(payload: dict) -> pd.DataFrame:
    """Converte a resposta num DataFrame diário com as colunas do contrato.

    A coluna et0_mm não vem do POWER: é calculada em data/features.py.
    """
    parameters = payload["properties"]["parameter"]
    fill = float(payload.get("header", {}).get("fill_value", FILL_VALUE))
    frame = pd.DataFrame(parameters, dtype="float64")
    frame.index = pd.to_datetime(frame.index, format="%Y%m%d")
    frame.index.name = "date"
    frame = frame.sort_index().replace(fill, np.nan).rename(columns=RENAME)
    frame["source"] = SOURCE
    frame["qc_flag"] = 0
    return frame


def fetch_years(lat: float, lon: float, start_year: int, end_year: int,
                chunk_years: int = 5) -> pd.DataFrame:
    """Série diária de 1 de Janeiro de start_year a 31 de Dezembro de end_year.

    Tenta um único pedido (mais rápido). Se falhar, pede em blocos de chunk_years anos.
    Lança RuntimeError se nem os blocos responderem.
    """
    try:
        payload = fetch_daily(lat, lon, f"{start_year}0101", f"{end_year}1231",
                              timeout=120, retries=0)
        return parse_daily(payload)
    except RuntimeError:
        pass
    frames = []
    for first in range(start_year, end_year + 1, chunk_years):
        last = min(first + chunk_years - 1, end_year)
        payload = fetch_daily(lat, lon, f"{first}0101", f"{last}1231", timeout=60, retries=1)
        frames.append(parse_daily(payload))
    frame = pd.concat(frames).sort_index()
    return frame[~frame.index.duplicated(keep="first")]
