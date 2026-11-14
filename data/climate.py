"""Ponto de entrada do clima: descarrega, valida, calcula ET0 e guarda em Parquet.

Ordem de procura para um ponto:
1. data/demo/climate/   locais de demonstração, versionados (funcionam sem Internet)
2. data/cache/climate/  pontos já pedidos nesta máquina
3. NASA POWER           e, se falhar, Open-Meteo como plano B (a fonte fica registada)
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from data.clients import openmeteo, power
from data.features import add_et0, add_season
from data.paths import cache_dir, demo_dir
from data.validate import fill_gaps

CELL_DEG = 0.05        # as coordenadas são arredondadas a esta grelha (a célula do POWER tem 0,5°)
START_YEAR = 1990

COLUMNS = ["p_mm", "tmax_c", "tmin_c", "tmean_c", "rh_pct", "wind_ms", "rad_mj",
           "et0_mm", "gwetroot", "season", "source", "qc_flag"]


def snap(lat: float, lon: float) -> tuple[float, float]:
    """Arredonda as coordenadas à grelha da cache."""
    return (round(round(lat / CELL_DEG) * CELL_DEG, 2),
            round(round(lon / CELL_DEG) * CELL_DEG, 2))


def climate_path(folder: Path, lat: float, lon: float) -> Path:
    lat, lon = snap(lat, lon)
    return folder / "climate" / f"{lat:+.2f}_{lon:+.2f}.parquet"


def default_end_year() -> int:
    """Último ano civil completo."""
    return date.today().year - 1


def load_cached_climate(lat: float, lon: float) -> pd.DataFrame | None:
    """Clima já guardado para este ponto, ou None. Nunca faz pedidos de rede."""
    for folder in (demo_dir(), cache_dir()):
        path = climate_path(folder, lat, lon)
        if path.exists():
            return pd.read_parquet(path)
    return None


def build_climate(lat: float, lon: float, start_year: int = START_YEAR,
                  end_year: int | None = None) -> pd.DataFrame:
    """Descarrega e prepara o clima de um ponto. Faz pedidos de rede.

    Lança RuntimeError se nem o POWER nem o Open-Meteo responderem.
    """
    lat, lon = snap(lat, lon)
    end_year = end_year or default_end_year()
    try:
        frame = power.fetch_years(lat, lon, start_year, end_year)
    except RuntimeError:
        frame = openmeteo.fetch_years(lat, lon, start_year, end_year)
    frame = fill_gaps(frame)
    frame["tmean_c"] = frame["tmean_c"].fillna((frame["tmax_c"] + frame["tmin_c"]) / 2)
    frame = add_season(add_et0(frame, lat))
    extra = [column for column in frame.columns if column not in COLUMNS]
    return frame[[column for column in COLUMNS if column in frame.columns] + extra]


def save_climate(clim: pd.DataFrame, lat: float, lon: float, demo: bool = False) -> Path:
    """Guarda em Parquet na cache local ou, com demo=True, em data/demo/."""
    path = climate_path(demo_dir() if demo else cache_dir(), lat, lon)
    path.parent.mkdir(parents=True, exist_ok=True)
    clim.to_parquet(path)
    return path


def get_climate(lat: float, lon: float, start_year: int = START_YEAR,
                end_year: int | None = None, refresh: bool = False) -> pd.DataFrame:
    """Clima diário de um ponto, pelo contrato ClimateDaily. Usa a cache se existir."""
    if not refresh:
        cached = load_cached_climate(lat, lon)
        if cached is not None:
            return cached
    clim = build_climate(lat, lon, start_year, end_year)
    save_climate(clim, lat, lon)
    return clim
