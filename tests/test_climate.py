"""Ponto de entrada do clima: cache, plano B e pedidos em blocos. Sem rede."""

import numpy as np
import pandas as pd
import pytest

from data import climate
from data.clients import openmeteo, power
from engine.schemas import CLIMATE_COLUMNS
from tests.conftest import LAT, LON, synthetic_raw


def power_payload(start: str, end: str) -> dict:
    """Resposta no formato do POWER, construída a partir do clima sintético."""
    raw = synthetic_raw().loc[pd.Timestamp(start):pd.Timestamp(end)]
    inverse = {column: name for name, column in power.RENAME.items()}
    keys = raw.index.strftime("%Y%m%d")
    parameters = {inverse[column]: dict(zip(keys, raw[column].tolist(), strict=True))
                  for column in raw.columns if column in inverse}
    parameters["GWETTOP"] = dict.fromkeys(keys, 0.3)
    return {"header": {"fill_value": -999.0}, "properties": {"parameter": parameters}}


def test_snap_rounds_to_the_cache_grid():
    assert climate.snap(-24.53, 33.00) == (-24.55, 33.0)
    assert climate.snap(-24.5499, 33.012) == (-24.55, 33.0)


def test_build_climate_follows_the_contract(monkeypatch):
    monkeypatch.setattr(power, "fetch_years", lambda *args, **kwargs: synthetic_raw())
    clim = climate.build_climate(LAT, LON, 1990, 2002)
    assert set(CLIMATE_COLUMNS) <= set(clim.columns)
    assert clim["et0_mm"].notna().all() and clim["season"].between(1989, 2002).all()
    assert (clim["source"] == "SINTÉTICO").all()


def test_get_climate_fetches_once_then_reads_the_cache(monkeypatch, data_home):
    calls = []

    def fake(*args, **kwargs):
        calls.append(args)
        return synthetic_raw()

    monkeypatch.setattr(power, "fetch_years", fake)
    assert climate.load_cached_climate(LAT, LON) is None
    first = climate.get_climate(LAT, LON, 1990, 2002)
    second = climate.get_climate(LAT, LON, 1990, 2002)
    assert len(calls) == 1
    assert (data_home / "cache" / "climate" / "-24.55_+33.00.parquet").exists()
    pd.testing.assert_frame_equal(first, second, check_freq=False)
    assert climate.load_cached_climate(-24.54, 33.01) is not None     # mesma célula


def test_demo_folder_wins_over_cache(monkeypatch, data_home, clim):
    marked = clim.assign(source="DEMO")
    climate.save_climate(marked, LAT, LON, demo=True)
    climate.save_climate(clim, LAT, LON)
    assert (climate.load_cached_climate(LAT, LON)["source"] == "DEMO").all()


def test_falls_back_to_openmeteo_when_power_fails(monkeypatch):
    def down(*args, **kwargs):
        raise RuntimeError("POWER em baixo")

    def plan_b(lat, lon, start_year, end_year):
        raw = synthetic_raw()
        payload = {"daily": {
            "time": raw.index.strftime("%Y-%m-%d").tolist(),
            "precipitation_sum": raw["p_mm"].tolist(),
            "temperature_2m_max": raw["tmax_c"].tolist(),
            "temperature_2m_min": raw["tmin_c"].tolist(),
            "et0_fao_evapotranspiration": [4.0] * len(raw),
        }}
        return openmeteo.parse_daily(payload)

    monkeypatch.setattr(power, "fetch_years", down)
    monkeypatch.setattr(openmeteo, "fetch_years", plan_b)
    clim = climate.build_climate(LAT, LON, 1990, 2002)
    assert (clim["source"] == openmeteo.SOURCE).all()
    assert clim["et0_mm"].notna().all()            # ET0 do contrato é sempre a de Hargreaves
    assert "et0_ref_mm" in clim and clim["rh_pct"].isna().all()
    assert clim["tmean_c"].notna().all()


def test_raises_when_both_sources_fail(monkeypatch):
    def down(*args, **kwargs):
        raise RuntimeError("em baixo")

    monkeypatch.setattr(power, "fetch_years", down)
    monkeypatch.setattr(openmeteo, "fetch_years", down)
    with pytest.raises(RuntimeError):
        climate.build_climate(LAT, LON, 1990, 2002)


def test_power_fetch_years_splits_into_chunks_when_the_big_request_fails(monkeypatch):
    requests = []

    def fake_fetch_daily(lat, lon, start, end, **kwargs):
        requests.append((start, end))
        if len(requests) == 1:
            raise RuntimeError("pedido grande recusado")
        return power_payload(start, end)

    monkeypatch.setattr(power, "fetch_daily", fake_fetch_daily)
    frame = power.fetch_years(LAT, LON, 1990, 2002, chunk_years=5)
    assert requests == [("19900101", "20021231"), ("19900101", "19941231"),
                        ("19950101", "19991231"), ("20000101", "20021231")]
    assert len(frame) == len(synthetic_raw()) and frame.index.is_unique
    assert np.isclose(frame["p_mm"].sum(), synthetic_raw()["p_mm"].sum())


def test_openmeteo_parser():
    payload = {"daily": {
        "time": ["2023-01-01", "2023-01-02"],
        "precipitation_sum": [0.0, 7.5],
        "temperature_2m_max": [33.0, 30.0],
        "temperature_2m_min": [21.0, 20.0],
        "et0_fao_evapotranspiration": [6.1, 4.2],
    }}
    frame = openmeteo.parse_daily(payload)
    assert frame.loc["2023-01-02", "p_mm"] == 7.5
    assert frame.loc["2023-01-01", "tmean_c"] == 27.0
    assert frame.loc["2023-01-01", "et0_ref_mm"] == 6.1
