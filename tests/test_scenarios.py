"""Cenários climáticos."""

import pytest

from data.features import complete_seasons, season_table, site_summary
from data.scenarios import apply_scenario, scenario_nature, scenario_seasons
from tests.conftest import LAT


def test_historico_keeps_only_complete_seasons(clim, rules):
    out = apply_scenario(clim, "historico", rules, LAT)
    assert sorted(out["season"].unique()) == list(range(1990, 2002))
    assert list(out.columns) == list(clim.columns)


def test_seco_and_favoravel_are_real_years_and_disjoint(clim, rules):
    table = season_table(clim, rules)
    dry = scenario_seasons(table, "seco")
    wet = scenario_seasons(table, "favoravel")
    assert len(dry) == 4 and len(wet) == 4 and not set(dry) & set(wet)
    out = apply_scenario(clim, "seco", rules, LAT)
    # os valores diários não mudam: são os anos reais
    assert out["p_mm"].equals(clim.loc[out.index, "p_mm"])
    rain = {name: site_summary(season_table(apply_scenario(clim, name, rules, LAT), rules))
            ["rain_median_mm"] for name in ("seco", "historico", "favoravel")}
    assert rain["seco"] < rain["historico"] < rain["favoravel"]


def test_scenario_blocks_include_the_months_before_sowing(clim, rules):
    out = apply_scenario(clim, "ano:1995", rules, LAT)
    assert str(out.index.min().date()) == "1995-07-01"
    assert str(out.index.max().date()) == "1996-06-30"
    assert complete_seasons(season_table(out, rules)) == [1995]


def test_seco_parametrico_scales_rain_only(clim, rules):
    base = apply_scenario(clim, "historico", rules, LAT)
    out = apply_scenario(clim, "seco_parametrico", rules, LAT)
    factor = rules["scenarios"]["seco_parametrico"]["rain_factor"]
    assert out["p_mm"].to_numpy() == pytest.approx(base["p_mm"].to_numpy() * factor)
    assert out["tmax_c"].equals(base["tmax_c"]) and out["et0_mm"].equals(base["et0_mm"])


def test_quente_raises_temperature_and_et0(clim, rules):
    base = apply_scenario(clim, "historico", rules, LAT)
    out = apply_scenario(clim, "quente", rules, LAT)
    delta = rules["scenarios"]["quente"]["delta_t_c"]
    assert (out["tmax_c"] - base["tmax_c"]).to_numpy() == pytest.approx(delta)
    assert (out["tmin_c"] - base["tmin_c"]).to_numpy() == pytest.approx(delta)
    assert (out["et0_mm"] > base["et0_mm"]).all()
    assert out["p_mm"].equals(base["p_mm"])


def test_scenarios_do_not_modify_the_input(clim, rules):
    before = clim.copy()
    for name in ("seco_parametrico", "quente", "seco"):
        apply_scenario(clim, name, rules, LAT)
    assert clim.equals(before)


def test_unknown_or_incomplete_scenarios_raise(clim, rules):
    with pytest.raises(ValueError):
        apply_scenario(clim, "apocalipse", rules, LAT)
    with pytest.raises(ValueError):
        apply_scenario(clim, "ano:2002", rules, LAT)      # campanha cortada


def test_scenario_nature():
    assert scenario_nature("seco") == "modelado"
    assert scenario_nature("ano:2015") == "modelado"
    assert scenario_nature("quente") == "simulado"
