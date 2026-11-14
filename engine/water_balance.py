"""Balanço hídrico diário do solo (FAO-56, capítulo 8) e WRSI.

    ETc  = Kc * ET0
    TAW  = 1000 * (fc_vol - wp_vol) * zr_m          [mm]
    RAW  = p * TAW
    Ks   = 1 se Dr <= RAW; senão (TAW - Dr) / ((1 - p) * TAW)
    ETa  = Ks * ETc
    Dr_i = min(TAW, max(0, Dr_{i-1} - P_i + ETa_i))     (o excesso de chuva drena)
    WRSI = 100 * soma(ETa) / soma(ETc)
    Yrel = max(0, 1 - Ky * (1 - soma(ETa) / soma(ETc)))

Hipóteses: sem escoamento superficial, ascensão capilar ou rega; profundidade radicular
constante; data de sementeira fixa; o solo chega ao fim da estação seca sem água útil e é
"aquecido" com um período de solo nu antes da sementeira.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from engine.schemas import Crop, Site, SoilProfile


@dataclass(frozen=True)
class Balance:
    """Resultado de um balanço: somas em mm e esgotamento final."""

    eta_mm: float
    etc_mm: float
    rain_mm: float
    drainage_mm: float
    dr_end: float


def kc_curve(crop: Crop) -> np.ndarray:
    """Kc diário ao longo do ciclo: quatro fases, com interpolação linear nas de transição."""
    def ramp(start: float, end: float, days: int) -> np.ndarray:
        return start + (end - start) * (np.arange(days) + 0.5) / days

    return np.concatenate([
        np.full(crop.l_ini, crop.kc_ini),
        ramp(crop.kc_ini, crop.kc_mid, crop.l_dev),
        np.full(crop.l_mid, crop.kc_mid),
        ramp(crop.kc_mid, crop.kc_end, crop.l_late),
    ])


def root_params(crop: Crop, defaults: dict) -> tuple[float, float]:
    """(zr_m, p) da cultura: crops.csv se preenchido, senão engine_defaults.yaml."""
    table = defaults["root_and_depletion"]
    fallback = table.get(crop.crop_id, table["fallback"])
    zr = crop.zr_m if crop.zr_m is not None else fallback["zr_m"]
    p = crop.p if crop.p is not None else fallback["p"]
    return float(zr), float(p)


def total_available_water(soil: SoilProfile, zr_m: float) -> float:
    """TAW em mm para a profundidade radicular dada."""
    return 1000.0 * (soil.fc_vol - soil.wp_vol) * zr_m


def run_balance(p_mm, et0_mm, kc, taw: float, p_frac: float, dr0: float) -> Balance:
    """Corre o balanço diário. p_mm, et0_mm e kc são sequências do mesmo comprimento."""
    raw = p_frac * taw
    dr = min(max(dr0, 0.0), taw)
    eta_sum = etc_sum = rain_sum = drain_sum = 0.0
    for rain, et0, k in zip(p_mm, et0_mm, kc, strict=True):
        etc = k * et0
        ks = 1.0 if dr <= raw else max(0.0, (taw - dr) / (taw - raw))
        eta = ks * etc
        level = dr - rain + eta
        if level < 0.0:                 # solo cheio: o excesso drena
            drain_sum += -level
            level = 0.0
        dr = min(taw, level)
        eta_sum += eta
        etc_sum += etc
        rain_sum += rain
    return Balance(eta_sum, etc_sum, rain_sum, drain_sum, dr)


def _clean(frame: pd.DataFrame) -> tuple[list[float], list[float]]:
    """Chuva em falta conta como zero; ET0 em falta recebe a média do período."""
    rain = frame["p_mm"].fillna(0.0).tolist()
    et0 = frame["et0_mm"]
    et0 = et0.fillna(et0.mean() if et0.notna().any() else 0.0).tolist()
    return rain, et0


def simulate_season(days: pd.DataFrame, crop: Crop, soil: SoilProfile, defaults: dict,
                    spin_up: pd.DataFrame | None = None, spin_up_kc: float = 0.3
                    ) -> dict[str, float]:
    """Simula uma cultura numa campanha.

    days:    linhas diárias da sementeira à colheita (cycle_days linhas), com p_mm e et0_mm.
    spin_up: dias anteriores à sementeira, simulados como solo nu a partir de solo seco.
    Devolve wrsi (0 a 100), y_rel (0 a 1), etc_mm, eta_mm e rain_mm do ciclo.
    """
    zr_m, p_frac = root_params(crop, defaults)
    taw = total_available_water(soil, zr_m)
    dr = taw                                    # fim da estação seca: sem água útil
    if spin_up is not None and len(spin_up):
        rain, et0 = _clean(spin_up)
        dr = run_balance(rain, et0, [spin_up_kc] * len(rain), taw, p_frac, dr).dr_end
    rain, et0 = _clean(days)
    result = run_balance(rain, et0, kc_curve(crop)[:len(rain)], taw, p_frac, dr)
    ratio = result.eta_mm / result.etc_mm if result.etc_mm > 0 else 0.0
    return {
        "wrsi": 100.0 * ratio,
        "y_rel": max(0.0, 1.0 - crop.ky * (1.0 - ratio)),
        "etc_mm": result.etc_mm,
        "eta_mm": result.eta_mm,
        "rain_mm": result.rain_mm,
    }


def sowing_date(season: int, site: Site) -> pd.Timestamp:
    """Data de sementeira da campanha: no ano `season` se for de Julho em diante."""
    year = season if site.sow_month >= 7 else season + 1
    return pd.Timestamp(year, site.sow_month, site.sow_day)


def season_stats(clim: pd.DataFrame, crop: Crop, soil: SoilProfile, site: Site, rules: dict,
                 defaults: dict) -> pd.DataFrame:
    """Uma linha por campanha presente em `clim`, com o resultado de simulate_season.

    Campanhas em que o ciclo não cabe nos dados disponíveis são ignoradas.
    """
    cfg = rules["water_balance"]
    rows = []
    for season in sorted(int(value) for value in clim["season"].unique()):
        sow = sowing_date(season, site)
        days = clim.loc[sow:sow + pd.Timedelta(days=crop.cycle_days - 1)]
        if len(days) < crop.cycle_days:
            continue
        spin = clim.loc[sow - pd.Timedelta(days=cfg["spin_up_days"]):sow - pd.Timedelta(days=1)]
        rows.append({"season": season,
                     **simulate_season(days, crop, soil, defaults, spin, cfg["spin_up_kc"])})
    columns = ["season", "wrsi", "y_rel", "etc_mm", "eta_mm", "rain_mm"]
    return pd.DataFrame(rows, columns=columns).set_index("season")


def summarize(stats: pd.DataFrame, rules: dict) -> dict[str, float]:
    """Resumo de uma cultura nas campanhas simuladas."""
    stress = rules["thresholds"]["wrsi_stress"]
    failure = rules["thresholds"]["wrsi_failure"]
    if stats.empty:
        raise ValueError("Nenhuma campanha simulada: o ciclo não cabe nos dados")
    return {
        "seasons": int(len(stats)),
        "wrsi_median": float(stats["wrsi"].median()),
        "wrsi_p10": float(stats["wrsi"].quantile(0.10)),
        "wrsi_p90": float(stats["wrsi"].quantile(0.90)),
        "p_stress": float((stats["wrsi"] < stress).mean()),
        "p_failure": float((stats["wrsi"] < failure).mean()),
        "y_rel_median": float(stats["y_rel"].median()),
        "etc_median_mm": float(stats["etc_mm"].median()),
        "rain_median_mm": float(stats["rain_mm"].median()),
    }


SOWING_DATES = ((10, 15), (11, 1), (11, 15), (12, 1), (12, 15), (1, 1), (1, 15))


def sowing_window(clim: pd.DataFrame, crop: Crop, soil: SoilProfile, site: Site, rules: dict,
                  defaults: dict, dates=SOWING_DATES) -> dict[str, dict[str, float]]:
    """Resumo do balanço hídrico da cultura para várias datas de sementeira.

    Responde a "quando semear": para cada data, em quantas campanhas reais a cultura teria
    tido água suficiente. Devolve {"15/11": resumo, ...} pela ordem das datas.
    """
    from dataclasses import replace

    out = {}
    for month, day in dates:
        shifted = replace(site, sow_month=month, sow_day=day)
        stats = season_stats(clim, crop, soil, shifted, rules, defaults)
        if not stats.empty:
            out[f"{day:02d}/{month:02d}"] = summarize(stats, rules)
    return out
