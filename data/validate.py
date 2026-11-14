"""Validação e tratamento de dados ausentes.

Regra geral: nunca falhar em silêncio e nunca inventar um valor sem o marcar (qc_flag = 1).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

REQUIRED = ("p_mm", "tmax_c", "tmin_c")
CONTINUOUS = ("tmax_c", "tmin_c", "tmean_c", "rh_pct", "wind_ms", "rad_mj", "gwetroot")

# Intervalos físicos plausíveis; fora deles o valor é tratado como em falta.
LIMITS = {
    "p_mm": (0.0, 600.0),
    "tmax_c": (-20.0, 60.0),
    "tmin_c": (-30.0, 45.0),
}


def quality_report(clim: pd.DataFrame) -> dict[str, object]:
    """Resumo de qualidade: período, dias em falta por variável, valores implausíveis."""
    days = len(clim)
    missing = {col: float(clim[col].isna().mean()) for col in REQUIRED if col in clim}
    out_of_range = 0
    for column, (low, high) in LIMITS.items():
        if column in clim:
            out_of_range += int(((clim[column] < low) | (clim[column] > high)).sum())
    inverted = int((clim["tmin_c"] > clim["tmax_c"]).sum()) if days else 0
    expected = (clim.index.max() - clim.index.min()).days + 1 if days else 0
    return {
        "source": str(clim["source"].iloc[0]) if days else None,
        "start": clim.index.min().date().isoformat() if days else None,
        "end": clim.index.max().date().isoformat() if days else None,
        "days": days,
        "calendar_gaps": int(expected - days),
        "missing_fraction": missing,
        "out_of_range": out_of_range,
        "tmin_above_tmax": inverted,
        "corrected_days": int((clim["qc_flag"] == 1).sum()) if "qc_flag" in clim else 0,
    }


def fill_gaps(clim: pd.DataFrame, max_gap_days: int = 5) -> pd.DataFrame:
    """Devolve uma cópia com as falhas curtas tratadas e qc_flag = 1 nos dias alterados.

    - Garante um índice diário contínuo (dias ausentes passam a linhas vazias).
    - Valores fora dos intervalos físicos passam a em falta.
    - Variáveis contínuas: interpolação linear em falhas até max_gap_days.
    - Chuva: a falha recebe a média desse dia do ano nas outras campanhas. Não se
      interpola chuva, porque um dia seco entre dois chuvosos é perfeitamente normal.
    Falhas longas ficam em falta; a campanha é excluída mais tarde se passar o limite.
    """
    out = clim.copy()
    full_index = pd.date_range(out.index.min(), out.index.max(), freq="D", name="date")
    out = out.reindex(full_index)
    if "source" in out:
        out["source"] = out["source"].ffill().bfill()
    out["qc_flag"] = out["qc_flag"].fillna(0).astype(int) if "qc_flag" in out else 0

    for column, (low, high) in LIMITS.items():
        if column in out:
            out.loc[(out[column] < low) | (out[column] > high), column] = np.nan
    before = out[[c for c in (*CONTINUOUS, "p_mm") if c in out]].isna()

    for column in CONTINUOUS:
        if column in out and out[column].notna().any():
            out[column] = out[column].interpolate(
                method="time", limit=max_gap_days, limit_area="inside")

    if "p_mm" in out and out["p_mm"].isna().any():
        day_of_year = out.index.dayofyear
        climatology = out["p_mm"].groupby(day_of_year).mean()
        gap_run = out["p_mm"].isna()
        run_id = (gap_run != gap_run.shift()).cumsum()
        run_length = gap_run.groupby(run_id).transform("sum")
        short = gap_run & (run_length <= max_gap_days)
        out.loc[short, "p_mm"] = climatology.reindex(day_of_year[short]).to_numpy()

    after = out[before.columns].isna()
    changed = (before & ~after).any(axis=1)
    out.loc[changed, "qc_flag"] = 1
    return out
