"""Features climáticas: ET0, campanhas e indicadores do local. Funções puras, sem rede.

Convenções
- Campanha Y: 1 de Outubro de Y a 30 de Abril de Y+1 (datas em params/rules.yaml).
- Coluna `season`: ano agrícola de 1 de Julho de Y a 30 de Junho de Y+1. Cada dia
  pertence a um só ano agrícola, que contém a campanha Y e os meses secos anteriores
  (necessários para o aquecimento do balanço hídrico na Fase 3).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

GSC = 0.0820            # constante solar, MJ/m²/min (FAO-56)
MJ_TO_MM = 0.408        # MJ/m²/dia -> mm/dia de evaporação equivalente
SEASON_YEAR_START_MONTH = 7
REQUIRED = ("p_mm", "tmax_c", "tmin_c", "et0_mm")


# --- ET0 ---------------------------------------------------------------------

def extraterrestrial_radiation_mj(lat: float, day_of_year) -> np.ndarray:
    """Radiação extraterrestre Ra em MJ/m²/dia (FAO-56, equações 21 a 25)."""
    phi = np.radians(lat)
    j = np.asarray(day_of_year, dtype="float64")
    dr = 1 + 0.033 * np.cos(2 * np.pi * j / 365)
    delta = 0.409 * np.sin(2 * np.pi * j / 365 - 1.39)
    ws = np.arccos(np.clip(-np.tan(phi) * np.tan(delta), -1.0, 1.0))
    return (24 * 60 / np.pi) * GSC * dr * (
        ws * np.sin(phi) * np.sin(delta) + np.cos(phi) * np.cos(delta) * np.sin(ws))


def hargreaves_et0(tmax, tmin, ra_mm):
    """ET0 de Hargreaves-Samani em mm/dia (FAO-56, equação 52). Ra em mm/dia."""
    tmean = (tmax + tmin) / 2
    spread = np.clip(tmax - tmin, 0, None)
    return 0.0023 * (tmean + 17.8) * np.sqrt(spread) * ra_mm


def add_et0(clim: pd.DataFrame, lat: float) -> pd.DataFrame:
    """Devolve uma cópia com a coluna et0_mm calculada a partir de tmax_c e tmin_c."""
    out = clim.copy()
    ra_mm = extraterrestrial_radiation_mj(lat, out.index.dayofyear) * MJ_TO_MM
    out["et0_mm"] = hargreaves_et0(out["tmax_c"].to_numpy(), out["tmin_c"].to_numpy(), ra_mm)
    return out


# --- Campanhas ----------------------------------------------------------------

def add_season(clim: pd.DataFrame) -> pd.DataFrame:
    """Devolve uma cópia com a coluna `season` (ano agrícola, Julho a Junho)."""
    out = clim.copy()
    out["season"] = np.where(out.index.month >= SEASON_YEAR_START_MONTH,
                             out.index.year, out.index.year - 1)
    return out


def season_bounds(year: int, rules: dict) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Primeiro e último dia da campanha `year`."""
    cfg = rules["season"]
    start = pd.Timestamp(year, cfg["start_month"], cfg["start_day"])
    end_year = year + 1 if cfg["end_month"] < cfg["start_month"] else year
    end = pd.Timestamp(end_year, cfg["end_month"], cfg["end_day"])
    return start, end


def season_window(clim: pd.DataFrame, year: int, rules: dict) -> pd.DataFrame:
    """Linhas da campanha `year` (por defeito 1 de Outubro a 30 de Abril)."""
    start, end = season_bounds(year, rules)
    return clim.loc[start:end]


def growing_season_length(window: pd.DataFrame, smooth_days: int = 30) -> int:
    """Duração da época de crescimento, em dias.

    Maior sequência de dias em que a chuva média móvel é pelo menos metade da ET0
    média móvel (critério FAO de período de crescimento, P >= 0,5 x ET0). A média de
    30 dias aproxima a escala mensal em que a FAO define o critério; com janelas
    curtas, qualquer veranico partiria a época em bocados. É um indicador a calibrar
    com dados reais antes de servir de filtro (regra R1).
    """
    rain = window["p_mm"].rolling(smooth_days, min_periods=smooth_days // 2, center=True).mean()
    et0 = window["et0_mm"].rolling(smooth_days, min_periods=smooth_days // 2, center=True).mean()
    wet = (rain >= 0.5 * et0).to_numpy()
    longest = current = 0
    for flag in wet:
        current = current + 1 if flag else 0
        longest = max(longest, current)
    return longest


def season_table(clim: pd.DataFrame, rules: dict) -> pd.DataFrame:
    """Uma linha por campanha: chuva, ET0, temperaturas, duração da época e classe.

    Colunas: rain_mm, et0_mm, tmax_c, tmin_c, tmean_c, season_length_days,
    missing_fraction, complete, tercile ("seco", "normal", "favoravel" ou None).
    Os terços são calculados só com campanhas completas.
    """
    max_missing = rules["thresholds"]["max_missing_fraction"]
    share = rules["scenarios"]["tercile"]
    first, last = clim.index.min(), clim.index.max()
    rows = []
    for year in range(first.year - 1, last.year + 1):
        start, end = season_bounds(year, rules)
        expected = (end - start).days + 1
        window = clim.loc[start:end]
        if window.empty:
            continue
        present = int(window[list(REQUIRED)].notna().all(axis=1).sum())
        missing = 1 - present / expected
        rows.append({
            "season": year,
            "label": f"{year}/{str(year + 1)[-2:]}",
            "rain_mm": float(window["p_mm"].sum()),
            "et0_mm": float(window["et0_mm"].sum()),
            "tmax_c": float(window["tmax_c"].mean()),
            "tmin_c": float(window["tmin_c"].mean()),
            "tmean_c": float(((window["tmax_c"] + window["tmin_c"]) / 2).mean()),
            "season_length_days": growing_season_length(window),
            "missing_fraction": round(missing, 4),
            "complete": bool(missing <= max_missing),
        })
    table = pd.DataFrame(rows).set_index("season")
    table["tercile"] = None
    complete = table[table["complete"]]
    if len(complete) >= 3:
        low = complete["rain_mm"].quantile(share)
        high = complete["rain_mm"].quantile(1 - share)
        table.loc[complete.index, "tercile"] = np.select(
            [complete["rain_mm"] <= low, complete["rain_mm"] >= high],
            ["seco", "favoravel"], default="normal")
    return table


def complete_seasons(table: pd.DataFrame) -> list[int]:
    """Anos das campanhas completas, por ordem."""
    return [int(year) for year in table.index[table["complete"]]]


def site_summary(table: pd.DataFrame) -> dict[str, float]:
    """Indicadores do local sobre as campanhas completas."""
    done = table[table["complete"]]
    return {
        "seasons": int(len(done)),
        "first_season": int(done.index.min()),
        "last_season": int(done.index.max()),
        "rain_median_mm": float(done["rain_mm"].median()),
        "rain_p10_mm": float(done["rain_mm"].quantile(0.10)),
        "rain_p90_mm": float(done["rain_mm"].quantile(0.90)),
        "et0_median_mm": float(done["et0_mm"].median()),
        "tmax_mean_c": float(done["tmax_c"].mean()),
        "tmin_mean_c": float(done["tmin_c"].mean()),
        "tmean_c": float(done["tmean_c"].mean()),
        "season_length_median_days": float(done["season_length_days"].median()),
        "dry_seasons": int((done["tercile"] == "seco").sum()),
    }


# --- Tendência ----------------------------------------------------------------------

def trend(values: pd.Series) -> dict[str, float | bool]:
    """Tendência de uma série anual: declive de Sen e teste de Mann-Kendall.

    Devolve slope (unidades por ano), z e significant (|z| > 1,96, ou seja, 5%).
    O teste não assume distribuição normal e resiste a anos extremos; não corrige empates.
    """
    data = values.dropna().to_numpy(dtype="float64")
    n = len(data)
    if n < 8:
        return {"slope": 0.0, "z": 0.0, "significant": False, "n": n}
    i, j = np.triu_indices(n, k=1)
    diffs = data[j] - data[i]
    s = float(np.sign(diffs).sum())
    variance = n * (n - 1) * (2 * n + 5) / 18
    z = 0.0 if s == 0 else (s - np.sign(s)) / np.sqrt(variance)
    slope = float(np.median(diffs / (j - i)))
    return {"slope": slope, "z": float(z), "significant": bool(abs(z) > 1.96), "n": n}
