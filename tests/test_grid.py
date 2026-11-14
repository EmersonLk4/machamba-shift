"""Grelha regional do mapa, cliente mensal do POWER e teste de tendência. Sem rede."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from data import grid
from data.clients import power
from data.features import trend
from tests.conftest import synthetic_raw


def monthly_payload(raw: pd.DataFrame, units: str = "mm/day", sea: bool = False) -> dict:
    """Resposta mensal no formato do POWER, a partir do clima sintético diário."""
    by_month = raw.groupby([raw.index.year, raw.index.month])
    rain = by_month["p_mm"].mean() if "day" in units else by_month["p_mm"].sum()
    temp = by_month["tmean_c"].mean()
    keys = [f"{year}{month:02d}" for year, month in rain.index]
    wet = -999.0 if sea else 0.4
    parameters = {
        "PRECTOTCORR": dict(zip(keys, rain.tolist(), strict=True)) | {"199013": 2.0},
        "T2M": dict(zip(keys, temp.tolist(), strict=True)) | {"199013": 24.0},
        "GWETROOT": dict.fromkeys(keys, wet) | {"199013": wet},
    }
    return {"header": {"fill_value": -999.0}, "properties": {"parameter": parameters},
            "parameters": {"PRECTOTCORR": {"units": units}}}


def test_monthly_parser_uses_real_days_and_skips_the_annual_value():
    raw = synthetic_raw("1990-01-01", "1992-12-31")
    table = power.parse_monthly(monthly_payload(raw))
    assert len(table) == 36 and set(table["month"]) == set(range(1, 13))
    for year, month in [(1992, 2), (1991, 2), (1990, 10)]:        # 1992 é bissexto
        expected = raw.loc[f"{year}-{month:02d}", "p_mm"].sum()
        got = table[(table["year"] == year) & (table["month"] == month)]["p_mm"].iloc[0]
        assert got == pytest.approx(expected)
    already_mm = power.parse_monthly(monthly_payload(raw, units="mm"))
    assert already_mm["p_mm"].sum() == pytest.approx(raw["p_mm"].sum())


def test_grid_cells_follow_the_power_grid():
    cells = grid.grid_cells()
    assert len(cells) == 34 * 19
    assert all(lat * 2 == round(lat * 2) and lon / 0.625 == round(lon / 0.625)
               for lat, lon in cells)
    assert len(grid.grid_cells(step=2)) == 17 * 10
    assert grid.cell_of(-24.53, 33.0) == (-24.5, 33.125)
    assert grid.cell_of(-24.5, 33.125) in cells


def test_campaign_year():
    assert grid.campaign_year(date(2026, 11, 14)) == 2026
    assert grid.campaign_year(date(2027, 2, 1)) == 2026
    assert grid.campaign_year(date(2026, 9, 30)) == 2025


def test_seasons_from_monthly_keeps_only_complete_campaigns():
    raw = synthetic_raw("1990-01-01", "1994-12-31")
    seasons = grid.seasons_from_monthly(power.parse_monthly(monthly_payload(raw)))
    assert list(seasons["season"]) == [1990, 1991, 1992, 1993]
    expected = raw.loc["1991-10-01":"1992-04-30", "p_mm"].sum()
    assert seasons.set_index("season").loc[1991, "rain_mm"] == pytest.approx(expected)


def test_now_counts_only_complete_months():
    raw = synthetic_raw("1990-01-01", "2002-12-31")
    monthly = power.parse_monthly(monthly_payload(raw.loc[:"2001-12-31"]))
    daily = raw.loc["2002-10-01":"2002-11-14"]
    now = grid.now_from_daily(daily, monthly, 2002)
    assert now["months"] == "Outubro" and now["last_date"] == "2002-11-14"
    assert now["rain_mm"] == pytest.approx(raw.loc["2002-10", "p_mm"].sum())
    octobers = [raw.loc[f"{year}-10", "p_mm"].sum() for year in range(1990, 2002)]
    assert now["rain_normal_mm"] == pytest.approx(np.median(octobers))
    two = grid.now_from_daily(raw.loc["2002-10-01":"2002-12-02"], monthly, 2002)
    assert two["months"] == "Outubro a Novembro"
    assert grid.now_from_daily(raw.loc["2002-10-01":"2002-10-20"], monthly, 2002) is None


def test_fetch_cell_skips_sea_and_builds_land(monkeypatch):
    raw = synthetic_raw("1990-01-01", "2002-12-31")
    history = raw.loc[:"2001-12-31"]
    monkeypatch.setattr(power, "fetch_monthly",
                        lambda lat, lon, a, b, **k: monthly_payload(history, sea=lon > 40))
    keys = raw.loc["2002-10-01":"2002-11-14"].index
    daily = {"header": {"fill_value": -999.0}, "properties": {"parameter": {
        name: dict(zip(keys.strftime("%Y%m%d"), raw.loc[keys, column].tolist(), strict=True))
        for name, column in power.RENAME.items() if column in raw}}}
    monkeypatch.setattr(power, "fetch_daily", lambda *a, **k: daily)
    seasons, now = grid.fetch_cell(-24.5, 33.125, 1990, 2001, date(2002, 11, 14))
    assert len(seasons) == 11 and now["months"] == "Outubro" and now["season"] == 2002
    sea_seasons, sea_now = grid.fetch_cell(-24.5, 40.625, 1990, 2001, date(2002, 11, 14))
    assert sea_seasons.empty and sea_now is None
    early, none_yet = grid.fetch_cell(-24.5, 33.125, 1990, 2001, date(2002, 10, 20))
    assert len(early) == 11 and none_yet is None


def test_save_load_and_normals(data_home):
    assert grid.load_grid() is None
    seasons = pd.DataFrame({"lat": -24.5, "lon": 33.125, "season": range(1990, 2000),
                            "rain_mm": np.arange(100.0, 1100.0, 100.0), "tmean_c": 25.0})
    grid.save_grid(seasons, pd.DataFrame())
    loaded, now = grid.load_grid()
    assert len(loaded) == 10 and now.empty
    normal = grid.normals(loaded).iloc[0]
    assert normal["rain_normal_mm"] == 550 and normal["seasons"] == 10
    assert normal["rain_bad_mm"] < normal["rain_normal_mm"] < normal["rain_good_mm"]


def test_trend_detects_a_real_change_and_ignores_noise():
    rng = np.random.default_rng(7)
    rising = pd.Series(20 + 0.03 * np.arange(35) + rng.normal(0, 0.2, 35))
    result = trend(rising)
    assert result["significant"] and result["slope"] == pytest.approx(0.03, abs=0.01)
    noise = trend(pd.Series(rng.normal(600, 150, 35)))
    assert not noise["significant"]
    assert not trend(pd.Series([1.0, 2.0, 3.0]))["significant"]       # poucos anos


def test_region_geometry_and_summary():
    import numpy as np
    import pandas as pd

    from data import grid, region
    square = [(-25.0, 32.0), (-25.0, 34.0), (-23.0, 34.0), (-23.0, 32.0)]
    assert region.contains(square, -24.0, 33.0) and not region.contains(square, -22.0, 33.0)
    assert region.centroid(square) == pytest.approx((-24.0, 33.0))
    assert region.area_km2(square) == pytest.approx(221.14 * 203.4, rel=0.02)
    feature = {"geometry": {"type": "Polygon", "coordinates": [
        [[32.0, -25.0], [34.0, -25.0], [34.0, -23.0], [32.0, -23.0], [32.0, -25.0]]]}}
    assert region.polygon_from_geojson(feature) == square
    assert region.polygon_from_geojson({"geometry": {"type": "Point"}}) is None

    cells = grid.grid_cells()
    seasons = pd.DataFrame([{"lat": lat, "lon": lon, "season": year,
                             "rain_mm": 500.0 + 20 * (year - 1990) - 10 * lat, "tmean_c": 25.0}
                            for lat, lon in cells for year in range(1990, 2000)])
    now = pd.DataFrame([{"lat": lat, "lon": lon, "season": 2026, "months": "Outubro",
                         "rain_mm": 30.0, "rain_normal_mm": 40.0, "gwet_latest": 0.3}
                        for lat, lon in cells])
    summary = region.region_summary(square, seasons, now)
    inside = [cell for cell in cells if region.contains(square, *cell)]
    assert summary["cells"] == len(inside) > 4 and not summary["fallback"]
    assert summary["cell_min_mm"] <= summary["rain_normal_mm"] <= summary["cell_max_mm"]
    assert summary["now_pct"] == pytest.approx(75.0) and summary["soil_pct"] == pytest.approx(30)
    assert len(summary["series"]) == 10 and set(summary["series"]["tercile"]) == {
        "seco", "normal", "favoravel"}
    tiny = [(-24.5, 33.0), (-24.5, 33.05), (-24.45, 33.05)]
    small = region.region_summary(tiny, seasons, now)
    assert small["cells"] == 1 and small["fallback"]
    assert region.region_summary([(0.0, 0.0), (0.0, 1.0), (1.0, 1.0)], seasons, now) is None
    assert np.isfinite(small["area_km2"])
