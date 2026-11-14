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


SATELLITE = ("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/"
             "tile/{z}/{y}/{x}")
PLACE_NAMES = ("https://server.arcgisonline.com/ArcGIS/rest/services/Reference/"
               "World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}")
LEGEND_STYLE = ("<style>.legend.leaflet-control{background:rgba(255,255,255,.92);"
                "border-radius:8px;padding:6px 10px 2px;box-shadow:0 1px 4px rgba(0,0,0,.35)}"
                "</style>")


def _satellite(location: list[float], zoom: int) -> folium.Map:
    """Fundo comum a todas as vistas: imagem de satélite com fronteiras e nomes por cima."""
    fmap = folium.Map(location=location, zoom_start=zoom, tiles=None)
    folium.TileLayer(SATELLITE, attr="Esri, Maxar, Earthstar Geographics",
                     name="Satélite").add_to(fmap)
    folium.TileLayer(PLACE_NAMES, attr="Esri", name="Nomes", overlay=True).add_to(fmap)
    fmap.get_root().header.add_child(folium.Element(LEGEND_STYLE))
    return fmap


def _markers(fmap: folium.Map, sites: dict, point: tuple[float, float]) -> None:
    for site in sites.values():
        folium.CircleMarker([site.lat, site.lon], radius=5, color="#ffffff", weight=2,
                            fill=True, fill_color="#eda100", fill_opacity=1,
                            tooltip=site.name).add_to(fmap)
    folium.CircleMarker(list(point), radius=9, color="#1a1a19", weight=2, fill=True,
                        fill_color="#ffffff", fill_opacity=1,
                        tooltip="Ponto em análise").add_to(fmap)


def base_map(sites: dict, point: tuple[float, float]) -> folium.Map:
    """Vista regional: Moçambique em satélite; os marcadores entram depois das células."""
    return _satellite(CENTER, 6)


def _spacing(values: pd.Series, default: float) -> float:
    """Distância entre células vizinhas, para a grelha encher o mapa mesmo se for esparsa."""
    unique = sorted(set(values.round(4)))
    gaps = [b - a for a, b in zip(unique, unique[1:], strict=False)]
    return min(gaps) if gaps else default


def add_cells(fmap: folium.Map, cells: pd.DataFrame, value: str, tooltip: str,
              diverging: bool, caption: str, vmin: float, vmax: float,
              sites: dict | None = None, point: tuple[float, float] | None = None) -> None:
    """Desenha um rectângulo por célula, colorido pela coluna `value`.

    tooltip é um modelo com nomes de colunas, por exemplo "{rain_normal_mm:.0f} mm".
    """
    scale = LinearColormap(DIVERGING if diverging else SEQUENTIAL, vmin=vmin, vmax=vmax,
                           caption=caption)
    layer = folium.FeatureGroup(name=caption)
    dlat, dlon = _spacing(cells["lat"], LAT_STEP), _spacing(cells["lon"], LON_STEP)
    for row in cells.dropna(subset=[value]).to_dict(orient="records"):
        shown = min(max(row[value], vmin), vmax)
        folium.Rectangle(
            bounds=[[row["lat"] - dlat / 2, row["lon"] - dlon / 2],
                    [row["lat"] + dlat / 2, row["lon"] + dlon / 2]],
            stroke=False, fill=True, fill_color=scale(shown), fill_opacity=0.78,
            tooltip=tooltip.format(**row),
        ).add_to(layer)
    layer.add_to(fmap)
    scale.add_to(fmap)
    folium.TileLayer(PLACE_NAMES, attr="Esri", name="Nomes por cima", overlay=True).add_to(fmap)
    if sites is not None and point is not None:
        _markers(fmap, sites, point)


CHIP = ("display:inline-block;white-space:nowrap;background:#ffffff;color:#1a1a19;"
        "border:1px solid #c9c8c2;border-radius:6px;padding:3px 8px;font:600 12px monospace;"
        "box-shadow:0 1px 3px rgba(0,0,0,.35);transform:translate(-50%,-50%)")


def draw_map(point: tuple[float, float], polygon: list[tuple[float, float]] | None,
             cells: list[dict] | None) -> folium.Map:
    """Mapa para desenhar uma região irregular; mostra a região guardada e as suas células."""
    from folium.plugins import Draw
    fmap = _satellite(list(point), 7)
    for cell in cells or []:
        folium.Rectangle(
            bounds=[[cell["lat"] - LAT_STEP / 2, cell["lon"] - LON_STEP / 2],
                    [cell["lat"] + LAT_STEP / 2, cell["lon"] + LON_STEP / 2]],
            color="#ffffff", weight=1, fill=True, fill_color="#2a78d6", fill_opacity=0.18,
            tooltip="Zona do NASA POWER usada no resumo").add_to(fmap)
    if polygon:
        folium.Polygon([list(vertex) for vertex in polygon], color="#facc15", weight=3,
                       fill=True, fill_color="#facc15", fill_opacity=0.08,
                       tooltip="Região em análise").add_to(fmap)
        fmap.fit_bounds([[min(lat for lat, _ in polygon), min(lon for _, lon in polygon)],
                         [max(lat for lat, _ in polygon), max(lon for _, lon in polygon)]],
                        padding=(40, 40))
    shape = {"shapeOptions": {"color": "#facc15", "weight": 3}}
    Draw(export=False, position="topleft",
         draw_options={"polygon": {**shape, "allowIntersection": False}, "rectangle": shape,
                       "polyline": False, "circle": False, "marker": False,
                       "circlemarker": False},
         edit_options={"edit": False, "remove": False}).add_to(fmap)
    folium.CircleMarker(list(point), radius=7, color="#08111f", weight=2, fill=True,
                        fill_color="#ffffff", fill_opacity=1,
                        tooltip="Ponto em análise").add_to(fmap)
    return fmap


def local_map(sites: dict, point: tuple[float, float], cell: tuple[float, float],
              chips: list[tuple[float, float, str, str]]) -> folium.Map:
    """Vista de satélite centrada no ponto, com a zona que os dados representam.

    cell:  centro da célula do NASA POWER; o rectângulo mostra a área a que os números
           dizem respeito (cerca de 55 por 65 km), para não sugerir precisão de talhão.
    chips: (desvio em latitude, desvio em longitude, texto, explicação ao passar o rato).
    """
    fmap = _satellite(list(point), 9)
    folium.Rectangle(
        bounds=[[cell[0] - LAT_STEP / 2, cell[1] - LON_STEP / 2],
                [cell[0] + LAT_STEP / 2, cell[1] + LON_STEP / 2]],
        color="#ffffff", weight=2, dash_array="6 6", fill=True, fill_color="#2a78d6",
        fill_opacity=0.12,
        tooltip="Zona a que os dados dizem respeito (célula do NASA POWER)").add_to(fmap)
    _markers(fmap, sites, point)
    for dlat, dlon, text, hint in chips:
        folium.Marker(
            [point[0] + dlat, point[1] + dlon], tooltip=hint,
            icon=folium.DivIcon(html=f'<span style="{CHIP}">{text}</span>',
                                icon_size=(0, 0), icon_anchor=(0, 0))).add_to(fmap)
    return fmap
