"""Mapa regional: uma camada de condições reais por célula do NASA POWER.

Sem previsão. "Antes" mostra o que choveu nas campanhas passadas; "agora" mostra os meses
já completos da campanha em curso. Cores: uma só tonalidade para quantidades; par
vermelho-cinzento-azul para o desvio face ao normal. O valor está sempre também no texto
que aparece ao passar o rato.
"""

from __future__ import annotations

import folium
import pandas as pd
from branca.colormap import LinearColormap

from data.grid import LAT_STEP, LON_STEP

SEQUENTIAL = ["#e6f0fb", "#8fbcee", "#2a78d6", "#0b3d91"]
DIVERGING = ["#d03b3b", "#e8a39c", "#e8e7e3", "#9cc3ef", "#2a78d6"]
CENTER = [-18.7, 35.5]


def base_map(sites: dict, point: tuple[float, float]) -> folium.Map:
    """Mapa de Moçambique com os locais de demonstração e o ponto seleccionado."""
    fmap = folium.Map(location=CENTER, zoom_start=5, tiles="OpenStreetMap")
    for site in sites.values():
        folium.Marker([site.lat, site.lon], tooltip=site.name).add_to(fmap)
    folium.CircleMarker(list(point), radius=9, color="#1a1a19", weight=2, fill=True,
                        fill_color="#ffffff", fill_opacity=1,
                        tooltip="Ponto em análise").add_to(fmap)
    return fmap


def add_cells(fmap: folium.Map, cells: pd.DataFrame, value: str, tooltip: str,
              diverging: bool, caption: str, vmin: float, vmax: float) -> None:
    """Desenha um rectângulo por célula, colorido pela coluna `value`.

    tooltip é um modelo com nomes de colunas, por exemplo "{rain_normal_mm:.0f} mm".
    """
    scale = LinearColormap(DIVERGING if diverging else SEQUENTIAL, vmin=vmin, vmax=vmax,
                           caption=caption)
    layer = folium.FeatureGroup(name=caption)
    for row in cells.dropna(subset=[value]).to_dict(orient="records"):
        shown = min(max(row[value], vmin), vmax)
        folium.Rectangle(
            bounds=[[row["lat"] - LAT_STEP / 2, row["lon"] - LON_STEP / 2],
                    [row["lat"] + LAT_STEP / 2, row["lon"] + LON_STEP / 2]],
            stroke=False, fill=True, fill_color=scale(shown), fill_opacity=0.72,
            tooltip=tooltip.format(**row),
        ).add_to(layer)
    layer.add_to(fmap)
    scale.add_to(fmap)
