"""Grelha regional para o mapa: condições reais por célula do NASA POWER.

Cada célula tem 0,5° de latitude por 0,625° de longitude (a grelha da reanálise MERRA-2).
Guardam-se dois ficheiros em data/demo/grid/:

  seasons.parquet  uma linha por célula e campanha: chuva de Outubro a Abril e temperatura
  now.parquet      uma linha por célula: chuva dos meses já completos desta campanha, o
                   normal desses mesmos meses e a humidade do solo mais recente

Não há previsão: o mapa mostra o que aconteceu ("antes") e o que está a acontecer ("agora").
As células sobre o mar não têm humidade do solo no POWER e ficam de fora.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from data.clients import power
from data.paths import demo_dir

LAT_STEP, LON_STEP = 0.5, 0.625
BBOX = {"lat_min": -27.0, "lat_max": -10.5, "lon_min": 30.0, "lon_max": 41.25}
SEASON_MONTHS = (10, 11, 12, 1, 2, 3, 4)
MONTH_NAMES = {1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 10: "Outubro",
               11: "Novembro", 12: "Dezembro"}


def grid_dir() -> Path:
    return demo_dir() / "grid"


def grid_cells(step: int = 1) -> list[tuple[float, float]]:
    """Centros das células dentro da caixa de Moçambique. step=2 usa uma em cada duas."""
    lats = np.arange(BBOX["lat_min"], BBOX["lat_max"] + 1e-9, LAT_STEP * step)
    lons = np.arange(BBOX["lon_min"], BBOX["lon_max"] + 1e-9, LON_STEP * step)
    return [(round(float(lat), 3), round(float(lon), 3)) for lat in lats for lon in lons]


def cell_of(lat: float, lon: float) -> tuple[float, float]:
    """Centro da célula que contém o ponto."""
    return (round(round(lat / LAT_STEP) * LAT_STEP, 3), round(round(lon / LON_STEP) * LON_STEP, 3))


def campaign_year(today: date) -> int:
    """Ano de início da campanha em curso (ou da última, entre Maio e Setembro)."""
    return today.year if today.month >= 10 else today.year - 1


def seasons_from_monthly(monthly: pd.DataFrame) -> pd.DataFrame:
    """Chuva (Outubro a Abril) e temperatura média de cada campanha completa."""
    data = monthly[monthly["month"].isin(SEASON_MONTHS)].copy()
    data["season"] = np.where(data["month"] >= 10, data["year"], data["year"] - 1)
    grouped = data.groupby("season").agg(
        rain_mm=("p_mm", "sum"), tmean_c=("tmean_c", "mean"),
        months=("p_mm", "count"))
    complete = grouped[grouped["months"] == len(SEASON_MONTHS)]
    return complete[["rain_mm", "tmean_c"]].reset_index()


def now_from_daily(daily: pd.DataFrame, monthly: pd.DataFrame, season: int) -> dict | None:
    """Condições da campanha em curso, só com meses completos.

    daily:   série diária desde 1 de Outubro da campanha `season` (contrato do parser).
    monthly: histórico mensal da mesma célula, para o normal dos mesmos meses.
    Devolve None se ainda nenhum mês estiver completo.
    """
    valid = daily.dropna(subset=["p_mm"])
    if valid.empty:
        return None
    last = valid.index.max()
    done = []
    for month in SEASON_MONTHS:
        year = season if month >= 10 else season + 1
        end = pd.Timestamp(year, month, 1) + pd.offsets.MonthEnd(0)
        if end > last:
            break
        done.append((year, month))
    if not done:
        return None
    months = [month for _, month in done]
    start = pd.Timestamp(done[0][0], done[0][1], 1)
    end = pd.Timestamp(done[-1][0], done[-1][1], 1) + pd.offsets.MonthEnd(0)
    window = daily.loc[start:end]
    history = monthly[monthly["month"].isin(months)].copy()
    history["season"] = np.where(history["month"] >= 10, history["year"], history["year"] - 1)
    history = history[history["season"] < season]
    per_season = history.groupby("season").agg(rain=("p_mm", "sum"), n=("p_mm", "count"),
                                               gwet=("gwetroot", "mean"))
    per_season = per_season[per_season["n"] == len(months)]
    wet = daily["gwetroot"].dropna() if "gwetroot" in daily else pd.Series(dtype=float)
    return {
        "months": " a ".join(dict.fromkeys([MONTH_NAMES[months[0]], MONTH_NAMES[months[-1]]])),
        "rain_mm": float(window["p_mm"].sum()),
        "rain_normal_mm": float(per_season["rain"].median()) if len(per_season) else np.nan,
        "gwet": float(window["gwetroot"].mean()) if "gwetroot" in window else np.nan,
        "gwet_normal": float(per_season["gwet"].median()) if len(per_season) else np.nan,
        "gwet_latest": float(wet.iloc[-1]) if len(wet) else np.nan,
        "last_date": last.date().isoformat(),
    }


def fetch_cell(lat: float, lon: float, start_year: int, end_year: int,
               today: date) -> tuple[pd.DataFrame, dict | None]:
    """Descarrega uma célula. Devolve (campanhas, agora); células de mar dão (vazio, None)."""
    monthly = power.parse_monthly(power.fetch_monthly(lat, lon, start_year, end_year))
    if monthly["gwetroot"].isna().all():            # mar: o POWER não tem humidade do solo
        return pd.DataFrame(), None
    seasons = seasons_from_monthly(monthly)
    seasons.insert(0, "lon", lon)
    seasons.insert(0, "lat", lat)
    season = campaign_year(today)
    now = None
    if today >= date(season, 11, 1):                # antes disso nenhum mês está completo
        payload = power.fetch_daily(lat, lon, f"{season}1001", today.strftime("%Y%m%d"),
                                    timeout=60, retries=1)
        now = now_from_daily(power.parse_daily(payload), monthly, season)
        if now is not None:
            now = {"lat": lat, "lon": lon, "season": season, **now}
    return seasons, now


def save_grid(seasons: pd.DataFrame, now: pd.DataFrame) -> Path:
    grid_dir().mkdir(parents=True, exist_ok=True)
    seasons.to_parquet(grid_dir() / "seasons.parquet", index=False)
    now.to_parquet(grid_dir() / "now.parquet", index=False)
    return grid_dir()


def load_grid() -> tuple[pd.DataFrame, pd.DataFrame] | None:
    """(campanhas, agora) já guardados, ou None se a grelha ainda não foi construída."""
    path = grid_dir() / "seasons.parquet"
    if not path.exists():
        return None
    now_path = grid_dir() / "now.parquet"
    now = pd.read_parquet(now_path) if now_path.exists() else pd.DataFrame()
    return pd.read_parquet(path), now


def normals(seasons: pd.DataFrame) -> pd.DataFrame:
    """Por célula: chuva de uma campanha normal, de uma má e de uma boa, e temperatura."""
    grouped = seasons.groupby(["lat", "lon"])
    out = grouped["rain_mm"].agg(
        rain_normal_mm="median",
        rain_bad_mm=lambda values: values.quantile(0.10),
        rain_good_mm=lambda values: values.quantile(0.90),
        seasons="count")
    out["tmean_c"] = grouped["tmean_c"].mean()
    return out.reset_index()


def trends(seasons: pd.DataFrame) -> pd.DataFrame:
    """Por célula: tendência da chuva (mm por década) e da temperatura (°C por década).

    Declive de Sen com teste de Mann-Kendall (data.features.trend). As colunas rain_trend e
    temp_trend ficam vazias (NaN) onde a tendência não é estatisticamente clara, para o mapa
    só colorir o que se pode afirmar; rain_slope e temp_slope guardam sempre o declive.
    """
    from data.features import trend
    rows = []
    for (lat, lon), cell in seasons.sort_values("season").groupby(["lat", "lon"]):
        rain, temp = trend(cell["rain_mm"]), trend(cell["tmean_c"])
        rows.append({
            "lat": lat, "lon": lon, "seasons": int(len(cell)),
            "rain_slope": 10 * rain["slope"], "temp_slope": 10 * temp["slope"],
            "rain_trend": 10 * rain["slope"] if rain["significant"] else np.nan,
            "temp_trend": 10 * temp["slope"] if temp["significant"] else np.nan})
    return pd.DataFrame(rows)
