"""Análise de uma região desenhada à mão no mapa (polígono irregular).

Os números vêm da grelha regional já descarregada do NASA POWER: a região é resumida pelas
células cujo centro cai dentro do polígono. Uma região mais pequena do que uma célula
(cerca de 55 por 65 km) fica com os valores da célula que a contém: os dados não têm
mais detalhe do que isso, e a função diz quando foi esse o caso.
"""

from __future__ import annotations

import math

import pandas as pd

from data.grid import cell_of, normals

Polygon = list[tuple[float, float]]          # vértices (lat, lon)


def polygon_from_geojson(feature: dict | None) -> Polygon | None:
    """Vértices (lat, lon) de um desenho devolvido pelo mapa; None se não for um polígono."""
    geometry = (feature or {}).get("geometry") or {}
    if geometry.get("type") != "Polygon" or not geometry.get("coordinates"):
        return None
    ring = [(float(lat), float(lon)) for lon, lat, *_ in geometry["coordinates"][0]]
    if len(ring) > 1 and ring[0] == ring[-1]:
        ring = ring[:-1]
    return ring if len(ring) >= 3 else None


def contains(polygon: Polygon, lat: float, lon: float) -> bool:
    """Ponto dentro do polígono (regra par-ímpar)."""
    inside = False
    for (lat1, lon1), (lat2, lon2) in zip(polygon, polygon[1:] + polygon[:1], strict=True):
        if (lat1 > lat) != (lat2 > lat):
            crossing = lon1 + (lat - lat1) * (lon2 - lon1) / (lat2 - lat1)
            if lon < crossing:
                inside = not inside
    return inside


def _projected(polygon: Polygon) -> list[tuple[float, float]]:
    lat0 = sum(lat for lat, _ in polygon) / len(polygon)
    scale = 111.32 * math.cos(math.radians(lat0))
    return [(lon * scale, lat * 110.57) for lat, lon in polygon]


def area_km2(polygon: Polygon) -> float:
    """Área aproximada (projecção plana local; erro pequeno à escala de uma província)."""
    points = _projected(polygon)
    twice = sum(x1 * y2 - x2 * y1
                for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1], strict=True))
    return abs(twice) / 2


def centroid(polygon: Polygon) -> tuple[float, float]:
    """Centro geométrico da região; média dos vértices se o polígono for degenerado."""
    twice = cx = cy = 0.0
    for (lat1, lon1), (lat2, lon2) in zip(polygon, polygon[1:] + polygon[:1], strict=True):
        cross = lon1 * lat2 - lon2 * lat1
        twice += cross
        cx += (lon1 + lon2) * cross
        cy += (lat1 + lat2) * cross
    if abs(twice) < 1e-12:
        return (sum(lat for lat, _ in polygon) / len(polygon),
                sum(lon for _, lon in polygon) / len(polygon))
    return cy / (3 * twice), cx / (3 * twice)


def cells_in(polygon: Polygon, cells: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
    """Células da grelha cujo centro está na região e se foi preciso recorrer à do centro."""
    inside = cells[[contains(polygon, lat, lon)
                    for lat, lon in zip(cells["lat"], cells["lon"], strict=True)]]
    if not inside.empty:
        return inside, False
    lat, lon = cell_of(*centroid(polygon))
    near = cells[((cells["lat"] - lat).abs() < 1e-6) & ((cells["lon"] - lon).abs() < 1e-6)]
    return near, True


def region_summary(polygon: Polygon, seasons: pd.DataFrame, now: pd.DataFrame) -> dict | None:
    """Resumo da região; None se nenhuma célula com dados (terra) lhe corresponder.

    series: chuva média da região em cada campanha (label, rain_mm, tercile, complete).
    """
    normal = normals(seasons)
    cells, fallback = cells_in(polygon, normal)
    if cells.empty:
        return None
    keys = cells[["lat", "lon"]]
    series = seasons.merge(keys, on=["lat", "lon"]).groupby("season", as_index=False)[
        "rain_mm"].mean()
    series["label"] = [f"{year}/{str(year + 1)[-2:]}" for year in series["season"]]
    series["complete"] = True
    low, high = series["rain_mm"].quantile(1 / 3), series["rain_mm"].quantile(2 / 3)
    series["tercile"] = ["seco" if value <= low else "favoravel" if value >= high else "normal"
                         for value in series["rain_mm"]]
    summary = {
        "cells": int(len(cells)), "fallback": fallback, "area_km2": area_km2(polygon),
        "centroid": centroid(polygon),
        "rain_normal_mm": float(series["rain_mm"].median()),
        "rain_bad_mm": float(series["rain_mm"].quantile(0.1)),
        "rain_good_mm": float(series["rain_mm"].quantile(0.9)),
        "cell_min_mm": float(cells["rain_normal_mm"].min()),
        "cell_max_mm": float(cells["rain_normal_mm"].max()),
        "series": series.set_index("season"), "cell_list": keys.to_dict(orient="records"),
        "now_pct": None, "now_months": None, "soil_pct": None,
    }
    current = now.merge(keys, on=["lat", "lon"]) if not now.empty else now
    if not current.empty:
        total, usual = current["rain_mm"].mean(), current["rain_normal_mm"].mean()
        summary["now_pct"] = float(100 * total / usual) if usual > 0 else None
        summary["now_months"] = f"{current['months'].iloc[0]} de {int(current['season'].iloc[0])}"
        wet = current["gwet_latest"].dropna()
        summary["soil_pct"] = float(100 * wet.mean()) if len(wet) else None
    return summary
