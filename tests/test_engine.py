"""Motor de decisão: balanço hídrico, regras, score, rotações e explicações."""

import json
from dataclasses import replace

import pandas as pd
import pytest

from data.scenarios import apply_scenario
from data.soil import default_soil
from engine.explain import contributions, explain
from engine.nitrogen import n_index, n_index_bounds, n_points, rotation_multiplier
from engine.params import load_crops, load_engine_defaults, load_sites
from engine.rotation import crop_statistics, recommend
from engine.rules import Constraints, family_repeats, feasible, ph_ok, thermal_suitability
from engine.schemas import INDICATORS, STRATEGY_LABELS, StrategyResult
from engine.scoring import minmax, normalize_weights, score
from engine.water_balance import (
    kc_curve,
    root_params,
    run_balance,
    season_stats,
    simulate_season,
    sowing_date,
    summarize,
    total_available_water,
)
from tests.conftest import LAT, LON


@pytest.fixture(scope="module")
def crops():
    return load_crops()


@pytest.fixture(scope="module")
def defaults():
    return load_engine_defaults()


@pytest.fixture(scope="module")
def site():
    return load_sites()["chokwe"]


@pytest.fixture()
def soil():
    return default_soil(LAT, LON)


def days(rain: float, et0: float, n: int, start: str = "2000-11-15") -> pd.DataFrame:
    index = pd.date_range(start, periods=n, freq="D")
    return pd.DataFrame({"p_mm": rain, "et0_mm": et0}, index=index)


# --- Curva de Kc e balanço hídrico ---------------------------------------------

def test_kc_curve_shape(crops):
    milho = crops["milho"]
    curve = kc_curve(milho)
    assert len(curve) == milho.cycle_days == 125
    assert curve[0] == milho.kc_ini and curve.max() == milho.kc_mid
    assert curve[:20].tolist() == [0.30] * 20
    assert milho.kc_end < curve[-1] < milho.kc_end + 0.03
    assert curve.sum() == pytest.approx(103.5)          # o valor do exemplo do plano
    assert kc_curve(crops["feijao_nhemba"]).sum() == pytest.approx(75.25)


def test_balance_without_rain_from_dry_soil_gives_no_transpiration():
    result = run_balance([0.0] * 30, [5.0] * 30, [1.0] * 30, taw=100, p_frac=0.5, dr0=100)
    assert result.eta_mm == 0 and result.etc_mm == 150 and result.dr_end == 100


def test_balance_with_plenty_of_rain_meets_full_demand():
    result = run_balance([20.0] * 30, [5.0] * 30, [1.0] * 30, taw=100, p_frac=0.5, dr0=0)
    assert result.eta_mm == pytest.approx(result.etc_mm) == pytest.approx(150)
    assert result.drainage_mm > 0


def test_stress_starts_only_after_readily_available_water_is_used():
    # TAW 100, p 0,5: sem chuva, os primeiros 50 mm saem sem stress (10 dias a 5 mm)
    result = run_balance([0.0] * 10, [5.0] * 10, [1.0] * 10, taw=100, p_frac=0.5, dr0=0)
    assert result.eta_mm == pytest.approx(50)
    later = run_balance([0.0] * 11, [5.0] * 11, [1.0] * 11, taw=100, p_frac=0.5, dr0=0)
    assert later.eta_mm == pytest.approx(55)             # no 11.º dia Dr = RAW: ainda sem stress
    after = run_balance([0.0] * 12, [5.0] * 12, [1.0] * 12, taw=100, p_frac=0.5, dr0=0)
    assert after.eta_mm < 60


def test_balance_conserves_mass(clim):
    window = clim.loc["1995-11-15":"1996-03-18"]
    kc = [0.9] * len(window)
    result = run_balance(window["p_mm"].tolist(), window["et0_mm"].tolist(), kc,
                         taw=130, p_frac=0.55, dr0=60)
    closure = 60 - result.rain_mm + result.eta_mm + result.drainage_mm
    assert result.dr_end == pytest.approx(closure, abs=1e-6)
    assert 0 <= result.dr_end <= 130 and result.eta_mm <= result.etc_mm + 1e-9


def test_simulate_season_limits_and_yield_formula(crops, defaults, soil):
    milho = crops["milho"]
    dry = simulate_season(days(0, 5, 125), milho, soil, defaults)
    assert dry["wrsi"] == 0 and dry["y_rel"] == 0
    wet = simulate_season(days(15, 5, 125), milho, soil, defaults, spin_up=days(15, 5, 60))
    assert wet["wrsi"] == pytest.approx(100) and wet["y_rel"] == pytest.approx(1)
    assert wet["etc_mm"] == pytest.approx(5 * 103.5)
    mid = simulate_season(days(2.5, 5, 125), milho, soil, defaults)
    assert 0 < mid["wrsi"] < 100
    assert mid["y_rel"] == pytest.approx(max(0, 1 - milho.ky * (1 - mid["wrsi"] / 100)))


def test_wet_spin_up_helps_and_deeper_water_store_helps(crops, defaults, soil):
    milho = crops["milho"]
    season = days(2.5, 5, 125)
    without = simulate_season(season, milho, soil, defaults)
    with_rain = simulate_season(season, milho, soil, defaults, spin_up=days(8, 4, 60, "2000-09-16"))
    assert with_rain["wrsi"] > without["wrsi"]
    richer = replace(soil, fc_vol=soil.fc_vol + 0.08)
    assert total_available_water(richer, 1.0) > total_available_water(soil, 1.0)
    assert simulate_season(season, milho, richer, defaults, spin_up=days(8, 4, 60, "2000-09-16"))[
        "wrsi"] >= with_rain["wrsi"]


def test_root_params_prefer_the_csv_value(crops, defaults):
    assert root_params(crops["milho"], defaults) == (1.35, 0.55)
    assert root_params(replace(crops["milho"], zr_m=0.6, p=0.4), defaults) == (0.6, 0.4)
    unknown = replace(crops["milho"], crop_id="quiabo")
    assert root_params(unknown, defaults) == (1.0, 0.5)


def test_sowing_date_follows_the_agricultural_year(site):
    assert sowing_date(1995, site) == pd.Timestamp("1995-11-15")
    assert sowing_date(1995, replace(site, sow_month=1, sow_day=10)) == pd.Timestamp("1996-01-10")


def test_season_stats_one_row_per_simulable_season(clim, crops, defaults, soil, site, rules):
    stats = season_stats(clim, crops["milho"], soil, site, rules, defaults)
    assert list(stats.index) == list(range(1990, 2002))    # 1989 e 2002 não cabem nos dados
    assert stats["wrsi"].between(0, 100).all() and stats["y_rel"].between(0, 1).all()
    summary = summarize(stats, rules)
    assert summary["seasons"] == 12
    assert summary["p_failure"] <= summary["p_stress"] <= 1
    assert summary["wrsi_p10"] <= summary["wrsi_median"] <= summary["wrsi_p90"]


def test_drier_and_hotter_scenarios_move_in_the_expected_direction(clim, crops, defaults, soil,
                                                                  site, rules):
    base = apply_scenario(clim, "historico", rules, LAT)
    dry = apply_scenario(clim, "seco_parametrico", rules, LAT)
    hot = apply_scenario(clim, "quente", rules, LAT)
    for key in ("milho", "mapira", "feijao_nhemba"):
        ref = season_stats(base, crops[key], soil, site, rules, defaults)
        less_rain = season_stats(dry, crops[key], soil, site, rules, defaults)
        warmer = season_stats(hot, crops[key], soil, site, rules, defaults)
        assert (less_rain["wrsi"] <= ref["wrsi"] + 1e-6).all()
        assert (warmer["etc_mm"] > ref["etc_mm"]).all()
        assert (warmer["wrsi"] <= ref["wrsi"] + 1e-6).all()


# --- Azoto e regras --------------------------------------------------------------

def test_nitrogen_index(crops, defaults):
    milho, nhemba, gergelim = crops["milho"], crops["feijao_nhemba"], crops["gergelim"]
    assert n_points(milho, defaults) == -1.0 and n_points(nhemba, defaults) == 0.62
    assert n_points(gergelim, defaults) == -0.6
    assert n_index([milho, milho, milho], defaults) == pytest.approx(-3.0)
    assert n_index([milho, nhemba, milho], defaults) == pytest.approx(-1.38)
    assert n_index_bounds(list(crops.values()), defaults, 3) == pytest.approx((-3.0, 1.86))


def test_rotation_multiplier_only_for_cereal_after_legume(crops):
    milho, nhemba, gergelim = crops["milho"], crops["feijao_nhemba"], crops["gergelim"]
    assert rotation_multiplier(nhemba, milho, 0.2) == 1.2
    assert rotation_multiplier(milho, milho, 0.2) == 1.0
    assert rotation_multiplier(nhemba, gergelim, 0.2) == 1.0
    assert rotation_multiplier(None, milho, 0.2) == 1.0


def test_rules(crops, soil):
    milho, mapira, nhemba, soja = (crops[k] for k in ("milho", "mapira", "feijao_nhemba", "soja"))
    free = Constraints()
    assert feasible([milho, nhemba, mapira], soil, 25, free)
    assert not feasible([milho, milho, nhemba], soil, 25, free)                       # R4
    assert not feasible([milho, nhemba, milho], soil, 25, free)       # R4: volta cedo de mais
    assert not feasible([milho, nhemba, mapira], soil, 25, Constraints(excluded={"mapira"}))
    assert not feasible([mapira, nhemba, soja], soil, 25, Constraints(required={"milho"}))
    staple = Constraints(require_staple=True)                                          # R9
    assert feasible([nhemba, milho, soja], soil, 25, staple)
    assert not feasible([nhemba, crops["gergelim"], soja], soil, 25, staple)
    assert family_repeats([milho, mapira, nhemba]) == 1
    assert family_repeats([milho, milho, milho]) == 2
    assert family_repeats([nhemba, soja, nhemba]) == 2
    assert family_repeats([milho, nhemba, milho]) == 0


def test_thermal_and_ph_rules_apply_only_when_parameters_exist(crops, soil):
    milho = crops["milho"]
    assert thermal_suitability(milho, 25) is None           # limites ECOCROP por preencher
    filled = replace(milho, tmin=10, topmin=18, topmax=30, tmax=40, ph_min=5.0, ph_max=7.5)
    assert thermal_suitability(filled, 24) == 1
    assert thermal_suitability(filled, 14) == pytest.approx(0.5)
    assert thermal_suitability(filled, 35) == pytest.approx(0.5)
    assert thermal_suitability(filled, 45) == 0
    assert not feasible([filled, crops["soja"], crops["mapira"]], soil, 45, Constraints())  # R2
    assert ph_ok(filled, soil)                                # pH do solo desconhecido
    acid = replace(soil, ph=4.2)
    assert not ph_ok(filled, acid) and ph_ok(milho, acid)
    assert not feasible([filled, crops["soja"], crops["mapira"]], acid, 24, Constraints())  # R3
    assert feasible([filled, crops["soja"], crops["mapira"]], soil, 24, Constraints())


# --- Score ------------------------------------------------------------------------

def test_minmax_and_weights():
    assert minmax(5, 0, 10) == 0.5 and minmax(-3, 0, 10) == 0 and minmax(30, 0, 10) == 1
    assert minmax(4, 7, 7) == 0.5
    weights = normalize_weights({"agua": 5, "solo": 5, "margem": 10},
                                available=set(INDICATORS) - {"margem"})
    assert weights["agua"] == weights["solo"] == 0.5 and weights["margem"] == 0
    assert sum(weights.values()) == pytest.approx(1)
    with pytest.raises(ValueError):
        normalize_weights({"margem": 3}, available=set(INDICATORS) - {"margem"})


def test_score_skips_unevaluated_indicators_and_applies_the_penalty():
    indicators = {"agua": 1.0, "solo": 0.5, "resiliencia": 0.0, "rendimento": 0.0,
                  "margem": None, "diversidade": 1.0}
    weights = normalize_weights({"agua": 1, "solo": 1}, set(INDICATORS) - {"margem"})
    assert score(indicators, weights) == pytest.approx(0.75)
    assert score(indicators, weights, lam=0.05, repeats=2) == pytest.approx(0.65)


# --- Rotações ---------------------------------------------------------------------

@pytest.fixture()
def result(clim, soil, site, rules, crops):
    return recommend(site, clim, soil, list(crops), rules["weights"]["equilibrado"], rules,
                     catalogue=crops)


def test_recommend_returns_the_four_strategies(result, crops):
    assert [item.label for item in result.strategies] == list(STRATEGY_LABELS)
    assert result.strategy("monocultura").sequence == ["milho"] * 3
    assert result.strategy("com_leguminosa").sequence == ["milho", "feijao_nhemba", "milho"]
    conventional = result.strategy("convencional").sequence
    assert conventional[0] == conventional[2] == "milho"
    assert crops[conventional[1]].group == "cereal" and conventional[1] != "milho"
    best = result.strategy("recomendada")
    assert len(set(best.sequence)) == 3                       # nenhuma cultura volta
    assert result.candidates == 9 * 8 * 7 and result.seasons == 12


def test_recommended_is_the_top_of_the_ranking(result):
    scores = [row["score"] for row in result.ranking]
    assert len(scores) == 10
    # ordenado por score, com empates até 0,005 resolvidos a favor da cultura actual
    assert all(a >= b - 0.005 for a, b in zip(scores, scores[1:], strict=False))
    best = result.strategy("recomendada")
    assert result.ranking[0]["sequence"] == best.sequence
    assert best.score >= max(scores) - 0.005


def test_indicators_are_bounded_and_margin_is_left_out_without_prices(result):
    assert result.weights["margem"] == 0 and sum(result.weights.values()) == pytest.approx(1)
    for item in result.strategies:
        assert set(item.indicators) == set(INDICATORS) and item.indicators["margem"] is None
        assert all(0 <= value <= 1 for value in item.indicators.values() if value is not None)
    mono = result.strategy("monocultura")
    assert mono.indicators["diversidade"] == 0 and mono.indicators["solo"] == 0
    assert mono.raw["family_repeats"] == 2
    assert any("Margem económica não avaliada" in flag for flag in result.flags)
    assert any("Solo por defeito" in flag for flag in result.flags)


def test_contributions_add_up_to_the_score_difference(result, rules):
    best, mono = result.strategy("recomendada"), result.strategy("monocultura")
    lam = rules["rotation"]["lambda_family_repeat"]
    penalty = lam * (best.raw["family_repeats"] - mono.raw["family_repeats"])
    total = sum(best.contributions_vs_baseline.values()) - penalty
    assert total == pytest.approx(best.score - mono.score, abs=2e-3)
    assert all(value == 0 for value in mono.contributions_vs_baseline.values())


def test_explanation_has_reasons_and_always_a_cost_line(result):
    assert 2 <= len(result.explanation) <= 3
    assert result.explanation[-1].startswith("Em troca:")
    assert all(line.endswith(")") or line.endswith(".") for line in result.explanation)


def test_result_is_json_serialisable(result):
    payload = json.loads(json.dumps(result.to_dict(), ensure_ascii=False))
    assert payload["scenario"] == "historico" and len(payload["strategies"]) == 4
    assert set(payload["provenance"]) == {"clima", "solo", "culturas"}


def test_farmer_constraints_are_respected(clim, soil, site, rules, crops):
    accepted = [key for key in crops if key not in {"mexoeira", "gergelim"}]
    out = recommend(site, clim, soil, accepted, rules["weights"]["equilibrado"], rules,
                    constraints=Constraints(required={"milho"}), catalogue=crops)
    for row in out.ranking:
        assert "milho" in row["sequence"]
        assert not {"mexoeira", "gergelim"} & set(row["sequence"])
    assert out.candidates < 7 * 6 * 5
    staple = recommend(site, clim, soil, list(crops), {"solo": 10}, rules, catalogue=crops,
                       constraints=Constraints(require_staple=True))
    assert all(any(crops[key].group == "cereal" for key in row["sequence"])
               for row in staple.ranking)


def test_weights_change_the_recommendation_target(clim, soil, site, rules, crops):
    only_soil = recommend(site, clim, soil, list(crops), {"solo": 10}, rules, catalogue=crops)
    best = only_soil.strategy("recomendada")
    assert all(crops[key].is_legume for key in best.sequence)      # só o azoto conta
    only_water = recommend(site, clim, soil, list(crops), {"agua": 10}, rules, catalogue=crops)
    stats = only_water.crop_stats
    top3 = sorted(stats, key=lambda key: -stats[key]["wrsi_median"])[:3]
    chosen = only_water.strategy("recomendada")
    floor = sum(stats[key]["wrsi_median"] for key in top3) / 300
    assert chosen.indicators["agua"] >= floor - 0.005


def test_bounds_are_frozen_across_scenarios(clim, soil, site, rules, crops):
    args = (site, clim, soil, list(crops), rules["weights"]["equilibrado"], rules)
    base = recommend(*args, catalogue=crops).strategy("monocultura")
    hot = recommend(*args, scenario="quente", catalogue=crops).strategy("monocultura")
    dry = recommend(*args, scenario="seco_parametrico", catalogue=crops).strategy("monocultura")
    assert hot.indicators["agua"] <= base.indicators["agua"]         # mais ET0, menos cobertura
    assert dry.indicators["agua"] <= base.indicators["agua"]         # menos chuva, menos cobertura
    assert hot.raw["etc_total_mm"] > base.raw["etc_total_mm"]
    assert dry.indicators["resiliencia"] <= base.indicators["resiliencia"]
    assert dry.indicators["rendimento"] <= base.indicators["rendimento"]
    assert dry.score <= base.score


def test_single_real_season_can_be_replayed(clim, soil, site, rules, crops):
    out = recommend(site, clim, soil, list(crops), rules["weights"]["equilibrado"], rules,
                    scenario="ano:1995", catalogue=crops)
    assert out.seasons == 1 and out.scenario == "ano:1995"
    assert "modelado" in out.provenance["clima"]


def test_margin_enters_the_score_when_economics_is_filled(clim, soil, site, rules, crops):
    economics = pd.DataFrame({
        "yield_ref_t_ha": 1.0, "price_mzn_kg": [float(10 + i) for i in range(len(crops))],
        "cost_mzn_ha": float("nan")}, index=pd.Index(list(crops), name="crop_id"))
    out = recommend(site, clim, soil, list(crops), rules["weights"]["rendimento"], rules,
                    catalogue=crops, economics=economics)
    assert out.weights["margem"] == pytest.approx(0.35)
    assert all(item.indicators["margem"] is not None for item in out.strategies)
    assert not any("Margem" in flag for flag in out.flags)


def test_needs_at_least_three_crops(clim, soil, site, rules, crops):
    with pytest.raises(ValueError, match="Nenhuma rotação viável"):
        recommend(site, clim, soil, ["milho", "soja"], rules["weights"]["equilibrado"], rules,
                  catalogue=crops)


def test_ties_are_broken_in_favour_of_the_current_crop(clim, soil, site, rules, crops):
    # só a diversidade conta: todas as rotações de três famílias empatam
    out = recommend(site, clim, soil, list(crops), {"diversidade": 10}, rules, catalogue=crops)
    assert "milho" in out.strategy("recomendada").sequence
    other = recommend(site, clim, soil, list(crops), {"diversidade": 10}, rules, catalogue=crops,
                      current_crop="gergelim")
    assert "gergelim" in other.strategy("recomendada").sequence


def test_crop_statistics_cover_every_requested_crop(clim, soil, site, rules, crops, defaults):
    base = apply_scenario(clim, "historico", rules, LAT)
    stats = crop_statistics(base, [crops["milho"], crops["soja"]], soil, site, rules, defaults)
    assert set(stats) == {"milho", "soja"}
    assert stats["milho"]["etc_median_mm"] > stats["soja"]["etc_median_mm"]


# --- Explicações -------------------------------------------------------------------

def make(label, indicators, **raw) -> StrategyResult:
    base = {"names": ["Milho"] * 3, "p_stress": [0.5] * 3, "p_failure": [0.2] * 3,
            "etc_total_mm": 1500, "coverage": [0.6] * 3, "y_rel": [0.5] * 3, "families": 1,
            "legumes": []}
    full = dict.fromkeys(INDICATORS, 0.5) | {"margem": None} | indicators
    return StrategyResult(label, ["x"] * 3, 0.0, full, {**base, **raw})


def test_explain_names_the_cost_when_something_gets_worse():
    weights = normalize_weights(dict.fromkeys(INDICATORS, 1), set(INDICATORS) - {"margem"})
    mono = make("monocultura", {})
    best = make("recomendada", {"resiliencia": 0.9, "solo": 0.8, "rendimento": 0.3},
                names=["Mapira (sorgo)", "Feijão-nhemba", "Milho"], p_stress=[0.1] * 3,
                y_rel=[0.3] * 3, legumes=[{"name": "Feijão-nhemba", "ndfa": 62.0}], families=2)
    effects = contributions(best, mono, weights)
    assert effects["resiliencia"] > effects["solo"] > 0 > effects["rendimento"]
    assert "margem" not in effects
    lines = explain(best, mono, weights)
    assert lines[0].startswith("Aguenta melhor os anos secos") and "9 de cada 10" in lines[0]
    assert "feijão-nhemba" in lines[1] and "62%" in lines[1]
    assert lines[2].startswith("Em troca: o rendimento") and "30% contra 50%" in lines[2]


def test_explain_when_nothing_beats_the_monoculture():
    weights = normalize_weights(dict.fromkeys(INDICATORS, 1), set(INDICATORS) - {"margem"})
    mono = make("monocultura", {})
    lines = explain(make("recomendada", {}), mono, weights)
    assert "nenhuma rotação viável supera" in lines[0]
    assert lines[-1].startswith("Em troca: nenhum dos objectivos avaliados piora")


def test_sowing_window_and_report(clim, rules):
    from app.components.report import build_pdf, build_report
    from data.features import season_table, site_summary
    from data.soil import default_soil
    from engine.params import load_crops, load_engine_defaults, load_sites
    from engine.rotation import recommend
    from engine.water_balance import SOWING_DATES, sowing_window
    crops, site = load_crops(), load_sites()["chokwe"]
    soil = default_soil(site.lat, site.lon)
    window = sowing_window(clim, crops["milho"], soil, site, rules, load_engine_defaults())
    assert len(window) == len(SOWING_DATES) and "15/11" in window
    assert all(0 <= item["p_failure"] <= item["p_stress"] <= 1 for item in window.values())
    weights = rules["weights"]["equilibrado"]
    result = recommend(site, clim, soil, list(crops), weights, rules, catalogue=crops)
    names = {key: crop.name_pt for key, crop in crops.items()}
    html = build_report(site.name, site.lat, site.lon, site_summary(season_table(clim, rules)),
                        result, names, None, window, "milho", "SINTÉTICO")
    assert html.startswith("<!doctype html>") and "Plano recomendado" in html
    assert "15/11" in html and "Condições recentes" not in html
    pdf = build_pdf(site.name, site.lat, site.lon, site_summary(season_table(clim, rules)),
                    result, names, None, window, "milho", "SINTÉTICO")
    assert pdf.startswith(b"%PDF") and len(pdf) > 3000
