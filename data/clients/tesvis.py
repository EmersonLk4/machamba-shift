"""Cliente do TESViS (ORNL DAAC): subconjuntos MODIS/VIIRS por ponto, sem autenticação.

Documentação: https://modis.ornl.gov/data/modis_webservice.html
Cada pedido devolve no máximo 10 datas de composição: séries longas pedem-se em blocos.
MOD13Q1 = índices de vegetação (NDVI, EVI), 250 m, composições de 16 dias. Dados OBSERVADOS.
"""

from __future__ import annotations

from data.clients.http import get_json

BASE_URL = "https://modis.ornl.gov/rst/api/v1"
HEADERS = {"Accept": "application/json"}


def fetch_dates(product: str, lat: float, lon: float, use_cache: bool = True) -> dict:
    """Datas de composição disponíveis para o produto e o ponto."""
    return get_json(f"{BASE_URL}/{product}/dates",
                    params={"latitude": lat, "longitude": lon},
                    headers=HEADERS, use_cache=use_cache)


def fetch_subset(product: str, lat: float, lon: float, start: str, end: str,
                 use_cache: bool = True) -> dict:
    """Subconjunto de um píxel. start e end no formato MODIS, por exemplo A2023001."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "startDate": start,
        "endDate": end,
        "kmAboveBelow": 0,
        "kmLeftRight": 0,
    }
    return get_json(f"{BASE_URL}/{product}/subset", params=params,
                    headers=HEADERS, use_cache=use_cache)
