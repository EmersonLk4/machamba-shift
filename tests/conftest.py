"""Dados de teste. O clima aqui é SINTÉTICO: serve só para testar o código, nunca como dado."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from data.features import add_et0, add_season
from engine.params import load_rules

LAT, LON = -24.53, 33.00


def synthetic_raw(start: str = "1990-01-01", end: str = "2002-12-31") -> pd.DataFrame:
    """Clima diário sintético, no formato que sai dos parsers (sem et0 nem season).

    Chuva concentrada de Outubro a Abril, com um multiplicador diferente em cada ano
    agrícola para que as campanhas tenham totais bem distintos.
    """
    index = pd.date_range(start, end, freq="D", name="date")
    rng = np.random.default_rng(42)
    doy = index.dayofyear.to_numpy()
    season = np.where(index.month >= 7, index.year, index.year - 1)
    wet = np.isin(index.month, [10, 11, 12, 1, 2, 3, 4])
    multiplier = 0.5 + ((season * 37) % 11) / 10          # 0,5 a 1,5 por ano agrícola
    rains = rng.random(len(index)) < np.where(wet, 0.35, 0.03)
    p_mm = np.where(rains, rng.gamma(2.0, 6.0, len(index)) * multiplier, 0.0)
    warm = np.cos(2 * np.pi * (doy - 15) / 365)             # máximo em Janeiro (hemisfério sul)
    tmax = 29 + 4 * warm + rng.normal(0, 1.2, len(index))
    tmin = 16 + 5 * warm + rng.normal(0, 1.0, len(index))
    return pd.DataFrame({
        "p_mm": p_mm.round(2), "tmax_c": tmax.round(2), "tmin_c": tmin.round(2),
        "tmean_c": ((tmax + tmin) / 2).round(2), "rh_pct": 65.0, "wind_ms": 2.0,
        "rad_mj": 20.0, "gwetroot": 0.4, "source": "SINTÉTICO", "qc_flag": 0,
    }, index=index)


@pytest.fixture(scope="session")
def rules() -> dict:
    return load_rules()


@pytest.fixture()
def raw() -> pd.DataFrame:
    return synthetic_raw()


@pytest.fixture()
def clim(raw) -> pd.DataFrame:
    """Clima sintético completo, como sai de build_climate."""
    return add_season(add_et0(raw, LAT))


@pytest.fixture()
def data_home(tmp_path, monkeypatch):
    """Aponta data/demo e data/cache para uma pasta temporária."""
    monkeypatch.setenv("MACHAMBA_DATA_DIR", str(tmp_path))
    return tmp_path
