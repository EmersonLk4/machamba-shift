"""ET0, campanhas e indicadores do local."""

import numpy as np
import pandas as pd
import pytest

from data.features import (
    MJ_TO_MM,
    add_et0,
    add_season,
    complete_seasons,
    extraterrestrial_radiation_mj,
    growing_season_length,
    hargreaves_et0,
    season_bounds,
    season_table,
    season_window,
    site_summary,
)
from tests.conftest import LAT


def test_extraterrestrial_radiation_matches_fao56_example():
    # FAO-56, exemplo 8: 3 de Setembro (dia 246) a 20°S -> Ra = 32,2 MJ/m²/dia
    assert extraterrestrial_radiation_mj(-20.0, 246) == pytest.approx(32.2, abs=0.1)


def test_radiation_is_higher_in_southern_summer():
    january, july = extraterrestrial_radiation_mj(LAT, [15, 196])
    assert january > july > 0


def test_hargreaves_formula():
    # 0,0023 x (20,7 + 17,8) x sqrt(26,6 - 14,8) x 16,5 = 5,02 mm/dia
    assert hargreaves_et0(26.6, 14.8, 16.5) == pytest.approx(5.02, abs=0.01)
    assert hargreaves_et0(20.0, 25.0, 15.0) == 0     # Tmin > Tmax não rebenta


def test_add_et0_gives_plausible_daily_values(raw):
    out = add_et0(raw, LAT)
    assert "et0_mm" not in raw                     # não altera a entrada
    assert out["et0_mm"].between(1.0, 9.0).all()
    ra_mm = extraterrestrial_radiation_mj(LAT, out.index.dayofyear) * MJ_TO_MM
    assert (out["et0_mm"] < ra_mm).all()


def test_season_label_runs_from_july_to_june(raw):
    out = add_season(raw)
    assert out.loc["1995-06-30", "season"] == 1994
    assert out.loc["1995-07-01", "season"] == 1995
    assert out.loc["1996-02-10", "season"] == 1995


def test_season_window_is_october_to_april(clim, rules):
    start, end = season_bounds(1995, rules)
    assert (start, end) == (pd.Timestamp("1995-10-01"), pd.Timestamp("1996-04-30"))
    window = season_window(clim, 1995, rules)
    assert len(window) == 213                      # 1996 é bissexto
    assert window.index.min() == start and window.index.max() == end


def test_season_table_sums_rain_inside_the_window(clim, rules):
    table = season_table(clim, rules)
    manual = clim.loc["1995-10-01":"1996-04-30", "p_mm"].sum()
    assert table.loc[1995, "rain_mm"] == pytest.approx(manual)
    assert table.loc[1995, "label"] == "1995/96"


def test_incomplete_seasons_are_flagged(clim, rules):
    table = season_table(clim, rules)
    # os dados vão de Janeiro de 1990 a Dezembro de 2002: 1989/90 e 2002/03 estão cortadas
    assert not table.loc[1989, "complete"] and not table.loc[2002, "complete"]
    assert complete_seasons(table) == list(range(1990, 2002))
    assert table.loc[1989, "tercile"] is None


def test_season_with_long_gap_is_excluded(clim, rules):
    broken = clim.copy()
    broken.loc["1996-11-01":"1996-12-31", "p_mm"] = np.nan    # 61 dias em 212
    table = season_table(broken, rules)
    assert not table.loc[1996, "complete"]
    assert table.loc[1995, "complete"]


def test_terciles_split_complete_seasons_by_rain(clim, rules):
    table = season_table(clim, rules)
    done = table[table["complete"]]
    counts = done["tercile"].value_counts()
    assert counts["seco"] == 4 and counts["favoravel"] == 4 and counts["normal"] == 4
    assert done[done["tercile"] == "seco"]["rain_mm"].max() \
        < done[done["tercile"] == "normal"]["rain_mm"].min()
    assert done[done["tercile"] == "normal"]["rain_mm"].max() \
        < done[done["tercile"] == "favoravel"]["rain_mm"].min()


def test_growing_season_length_counts_the_longest_wet_run():
    index = pd.date_range("2000-10-01", periods=200, freq="D")
    window = pd.DataFrame({"p_mm": 0.0, "et0_mm": 5.0}, index=index)
    assert growing_season_length(window) == 0
    window.loc["2000-11-01":"2001-01-29", "p_mm"] = 6.0       # 90 dias húmidos
    assert 88 <= growing_season_length(window) <= 100          # a média móvel alarga as margens
    window.loc["2000-12-10":"2000-12-14", "p_mm"] = 0.0       # veranico de 5 dias não parte a época
    assert 88 <= growing_season_length(window) <= 100


def test_site_summary_uses_only_complete_seasons(clim, rules):
    table = season_table(clim, rules)
    summary = site_summary(table)
    assert summary["seasons"] == 12
    assert (summary["first_season"], summary["last_season"]) == (1990, 2001)
    assert summary["rain_p10_mm"] < summary["rain_median_mm"] < summary["rain_p90_mm"]
    assert summary["dry_seasons"] == 4


def test_monthly_table_and_view(clim):
    from data.features import monthly_table, monthly_view
    months = monthly_table(clim)
    assert len(months) == 13 * 12 and (months["rain_mm"] >= 0).all()
    short = monthly_table(clim.iloc[:-20])                 # Dezembro de 2002 fica incompleto
    assert len(short) == len(months) - 1
    year = monthly_view(months, 2001)
    assert list(year["label"])[:2] == ["Jan", "Fev"] and len(year) == 12
    assert (year["tmin_c"] < year["tmean_c"]).all() and (year["tmean_c"] < year["tmax_c"]).all()
    every = monthly_view(months)
    assert (every["rain_mm"] - every["rain_normal_mm"]).abs().max() < 1e-9
    assert (every["dry_mm"] <= every["rain_mm"]).all()
    assert (every["rain_mm"] <= every["wet_mm"]).all()


def test_hover_charts_carry_panel_text(clim, rules):
    from app.components.charts import monthly_rain, monthly_temperature, rain_by_season
    from app.components.hover import hover_html
    from data.features import monthly_table, monthly_view, season_table
    view = monthly_view(monthly_table(clim), 2001)
    for figure in (monthly_rain(view, "2001", True), monthly_temperature(view, "2001"),
                   rain_by_season(season_table(clim, rules))):
        panels = [point for trace in figure.data if trace.customdata is not None
                  for point in trace.customdata]
        assert panels and all(len(point) == 3 and all(point) for point in panels)
        html = hover_html(figure)
        assert "plotly_hover" in html and 'id="panel"' in html
