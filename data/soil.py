"""Solo de um ponto, com plano B.

A API do SoilGrids está suspensa, por isso a ordem é:
1. data/demo/soil_<site_id>.json   valores lidos à mão em soilgrids.org para os locais de demo
2. SoilGrids                       só se try_api=True (um pedido, sem repetições)
3. Solo franco por defeito         marcado como hipótese na interface

A retenção de água (fc, wp) vem sempre da classe de textura (params/soil_defaults.yaml).
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from data.clients import soilgrids
from data.paths import demo_dir
from engine.schemas import SoilProfile

DEFAULTS_PATH = Path(__file__).resolve().parents[1] / "params" / "soil_defaults.yaml"
SOURCE_DEFAULT = "Solo por defeito (hipótese)"


def load_defaults() -> dict:
    with open(DEFAULTS_PATH, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def texture_class(sand_pct: float, clay_pct: float, silt_pct: float | None = None) -> str:
    """Classe de textura simplificada a partir de areia e argila (%).

    É uma simplificação do triângulo de texturas em sete classes, suficiente para
    escolher a retenção de água. Não substitui a classificação USDA completa.
    """
    silt = silt_pct if silt_pct is not None else 100 - sand_pct - clay_pct
    if clay_pct >= 40:
        return "argiloso"
    if clay_pct >= 27:
        return "franco_argiloso"
    if sand_pct >= 85:
        return "arenoso"
    if sand_pct >= 70:
        return "areia_franca"
    if sand_pct >= 52:
        return "franco_arenoso"
    if silt >= 50:
        return "franco_siltoso"
    return "franco"


def _with_water_retention(profile: SoilProfile, defaults: dict) -> SoilProfile:
    if profile.texture is None:
        if profile.sand_pct is not None and profile.clay_pct is not None:
            profile.texture = texture_class(profile.sand_pct, profile.clay_pct, profile.silt_pct)
        else:
            profile.texture = defaults["default_texture"]
    retention = defaults["textures"][profile.texture]
    if profile.fc_vol is None:
        profile.fc_vol = retention["fc"]
    if profile.wp_vol is None:
        profile.wp_vol = retention["wp"]
    return profile


def default_soil(lat: float, lon: float) -> SoilProfile:
    """Solo franco por defeito, sem pH nem nutrientes."""
    return _with_water_retention(SoilProfile(lat=lat, lon=lon, source=SOURCE_DEFAULT),
                                 load_defaults())


def get_soil(lat: float, lon: float, site_id: str | None = None,
             try_api: bool = False) -> SoilProfile:
    """Solo do ponto. Nunca falha: no pior caso devolve o solo por defeito."""
    defaults = load_defaults()

    if site_id:
        path = demo_dir() / f"soil_{site_id}.json"
        if path.exists():
            values = json.loads(path.read_text(encoding="utf-8"))
            values = {key: value for key, value in values.items() if not key.startswith("_")}
            if any(values.get(key) is not None for key in ("ph", "clay_pct", "sand_pct")):
                profile = SoilProfile(lat=lat, lon=lon, **values)
                return _with_water_retention(profile, defaults)

    if try_api:
        try:
            payload = soilgrids.fetch_properties(lat, lon, timeout=15, retries=0)
            raw = soilgrids.parse_properties(payload)
            if raw.get("clay") is not None and raw.get("sand") is not None:
                profile = SoilProfile(
                    lat=lat, lon=lon, ph=raw.get("phh2o"), soc_gkg=raw.get("soc"),
                    n_gkg=raw.get("nitrogen"), clay_pct=raw.get("clay"),
                    sand_pct=raw.get("sand"), silt_pct=raw.get("silt"),
                    source="SoilGrids 2.0 (ISRIC)")
                return _with_water_retention(profile, defaults)
        except (RuntimeError, KeyError, TypeError):
            pass

    return default_soil(lat, lon)
