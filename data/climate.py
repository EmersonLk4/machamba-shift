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


# --- Condições recentes (os últimos dias, para "agora") ------------------------------

RECENT_DAYS = 45


def _recent_path(folder: Path, lat: float, lon: float) -> Path:
    lat, lon = snap(lat, lon)
    return folder / "recent" / f"{lat:+.2f}_{lon:+.2f}.parquet"


def offline() -> bool:
    """MACHAMBA_OFFLINE=1 impede qualquer pedido de rede (testes e demonstração sem Internet)."""
    import os
    return os.environ.get("MACHAMBA_OFFLINE", "") == "1"


def get_recent(lat: float, lon: float, today: date | None = None,
               demo: bool = False) -> pd.DataFrame | None:
    """Série diária dos últimos RECENT_DAYS dias no NASA POWER, com ET0.

    Pede ao POWER uma vez por dia e por ponto. Se o pedido falhar (ou em modo offline),
    devolve a última série guardada, que pode ter alguns dias; None se não houver nenhuma.
    O POWER publica com cerca de três dias de atraso: os últimos dias vêm vazios.
    """
    today = today or date.today()
    cached = _recent_path(cache_dir(), lat, lon)
    stored = next((path for path in (cached, _recent_path(demo_dir(), lat, lon))
                   if path.exists()), None)
    if stored is not None:
        frame = pd.read_parquet(stored)
        fresh = stored == cached and date.fromtimestamp(stored.stat().st_mtime) == today
        if offline() or fresh:
            return frame
    if offline():
        return None
    start = today - pd.Timedelta(days=RECENT_DAYS)
    try:
        payload = power.fetch_daily(*snap(lat, lon), start.strftime("%Y%m%d"),
                                    today.strftime("%Y%m%d"), use_cache=False,
                                    timeout=25, retries=0)
        frame = add_et0(power.parse_daily(payload), snap(lat, lon)[0])
    except (RuntimeError, KeyError):
        return pd.read_parquet(stored) if stored is not None else None
    path = _recent_path(demo_dir() if demo else cache_dir(), lat, lon)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path)
    return frame


def recent_summary(frame: pd.DataFrame) -> dict[str, object] | None:
    """Resumo das condições recentes, só com dias que têm dados."""
    valid = frame.dropna(subset=["p_mm", "tmax_c"])
    if valid.empty:
        return None
    week = valid.tail(7)
    month = valid.tail(30)

    def latest(column: str) -> float | None:
        values = frame[column].dropna() if column in frame else pd.Series(dtype=float)
        return float(values.iloc[-1]) if len(values) else None

    return {
        "last_date": valid.index.max().date().isoformat(),
        "rain_7d_mm": float(week["p_mm"].sum()),
        "rain_30d_mm": float(month["p_mm"].sum()),
        "days_30": int(len(month)),
        "tmax_c": float(week["tmax_c"].mean()),
        "tmin_c": float(week["tmin_c"].mean()),
        "hot_days": int((week["tmax_c"] >= 35).sum()),
        "wind_kmh": None if week["wind_ms"].isna().all() else float(week["wind_ms"].mean() * 3.6),
        "rh_pct": None if week["rh_pct"].isna().all() else float(week["rh_pct"].mean()),
        "rad_mj": None if week["rad_mj"].isna().all() else float(week["rad_mj"].mean()),
        "et0_mm": float(week["et0_mm"].mean()),
        "soil_root": latest("gwetroot"),
        "soil_top": latest("gwettop"),
    }
