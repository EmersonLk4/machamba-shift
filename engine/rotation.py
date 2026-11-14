"""Enumeração de rotações e ponto de entrada do motor.

recommend() não faz pedidos de rede: recebe o clima histórico e o solo já carregados.
Como cada campanha de sequeiro começa depois da estação seca, o balanço hídrico de uma
cultura não depende da cultura anterior: cada cultura é simulada uma vez por campanha e
as rotações são combinações desses resultados. A ligação entre anos faz-se pelo índice de
azoto, pelo efeito leguminosa -> cereal e pela regra das famílias botânicas.
"""

from __future__ import annotations

from itertools import product

import pandas as pd

from data.features import season_table
from data.scenarios import apply_scenario, scenario_nature
from engine.explain import contributions, explain
from engine.nitrogen import n_index, n_index_bounds, rotation_multiplier
from engine.params import load_crops, load_engine_defaults
from engine.rules import Constraints, family_repeats, feasible, thermal_suitability
from engine.schemas import INDICATORS, Crop, Recommendation, Site, SoilProfile, StrategyResult
from engine.scoring import minmax, normalize_weights, score
from engine.water_balance import season_stats, summarize


def crop_statistics(clim: pd.DataFrame, crops: list[Crop], soil: SoilProfile, site: Site,
                    rules: dict, defaults: dict) -> dict[str, dict[str, float]]:
    """Resumo do balanço hídrico de cada cultura nas campanhas de `clim`."""
    return {crop.crop_id: summarize(season_stats(clim, crop, soil, site, rules, defaults), rules)
            for crop in crops}


def _margin(sequence: tuple[Crop, ...], yields: list[float],
            economics: pd.DataFrame | None) -> float | None:
    """Margem bruta da rotação (moeda de economics.csv por hectare), ou None sem preços."""
    if economics is None:
        return None
    total = 0.0
    for crop, y_rel in zip(sequence, yields, strict=True):
        if crop.crop_id not in economics.index:
            return None
        row = economics.loc[crop.crop_id]
        if pd.isna(row["yield_ref_t_ha"]) or pd.isna(row["price_mzn_kg"]):
            return None
        cost = 0.0 if pd.isna(row["cost_mzn_ha"]) else float(row["cost_mzn_ha"])
        total += float(row["yield_ref_t_ha"]) * y_rel * 1000 * float(row["price_mzn_kg"]) - cost
    return total


def raw_values(sequence: tuple[Crop, ...], stats: dict[str, dict[str, float]], rules: dict,
               defaults: dict, mean_temp_c: float,
               economics: pd.DataFrame | None = None) -> dict[str, object]:
    """Valores brutos de uma rotação, antes de normalizar."""
    beta = rules["rotation"]["beta_legume_cereal"]
    weights = defaults["resilience"]
    per_crop = [stats[crop.crop_id] for crop in sequence]
    yields, thermal_missing = [], []
    for position, crop in enumerate(sequence):
        previous = sequence[position - 1] if position else None
        suitability = thermal_suitability(crop, mean_temp_c)
        if suitability is None:
            thermal_missing.append(crop.crop_id)
            suitability = 1.0
        value = per_crop[position]["y_rel_median"] * suitability
        yields.append(min(1.0, value * rotation_multiplier(previous, crop, beta)))
    resilience = [1 - (weights["stress_weight"] * item["p_stress"]
                       + weights["failure_weight"] * item["p_failure"]) for item in per_crop]
    etc = [item["etc_median_mm"] for item in per_crop]
    return {
        "names": [crop.name_pt for crop in sequence],
        "wrsi_median": [round(item["wrsi_median"], 1) for item in per_crop],
        "p_stress": [round(item["p_stress"], 3) for item in per_crop],
        "p_failure": [round(item["p_failure"], 3) for item in per_crop],
        "coverage": [round(item["wrsi_median"] / 100, 3) for item in per_crop],
        "etc_mm": [round(value, 0) for value in etc],
        "etc_total_mm": round(sum(etc), 0),
        "y_rel": [round(value, 3) for value in yields],
        "resilience": [round(value, 3) for value in resilience],
        "n_index": round(n_index(list(sequence), defaults), 3),
        "families": len({crop.family for crop in sequence}),
        "family_repeats": family_repeats(list(sequence)),
        "legumes": [{"name": crop.name_pt, "ndfa": crop.ndfa}
                    for crop in dict.fromkeys(sequence) if crop.is_legume],
        "margin": _margin(sequence, yields, economics),
        "thermal_not_evaluated": sorted(set(thermal_missing)),
    }


def to_indicators(raw: dict[str, object], bounds: dict[str, tuple[float, float]],
                  horizon: int) -> dict[str, float | None]:
    """Indicadores em [0, 1] a partir dos valores brutos e dos limites congelados."""
    margin = raw["margin"]
    return {
        "agua": sum(raw["coverage"]) / horizon,
        "solo": minmax(raw["n_index"], *bounds["n_index"]),
        "resiliencia": sum(raw["resilience"]) / horizon,
        "rendimento": sum(raw["y_rel"]) / horizon,
        "margem": None if margin is None or bounds.get("margin") is None
        else minmax(margin, *bounds["margin"]),
        "diversidade": (raw["families"] - 1) / (horizon - 1) if horizon > 1 else 0.0,
    }


def _unique(crops: list[Crop | None]) -> list[Crop]:
    return list({crop.crop_id: crop for crop in crops if crop is not None}.values())


def recommend(site: Site, clim: pd.DataFrame, soil: SoilProfile, crops: list[str],
              weights: dict[str, float], rules: dict, scenario: str = "historico",
              constraints: Constraints | None = None, current_crop: str | None = None,
              catalogue: dict[str, Crop] | None = None, defaults: dict | None = None,
              economics: pd.DataFrame | None = None, top: int = 10) -> Recommendation:
    """Compara quatro estratégias para um local e um cenário.

    clim:    clima HISTÓRICO do ponto (contrato ClimateDaily); o cenário é aplicado aqui.
    crops:   crop_id que o agricultor aceita plantar.
    weights: pesos ou cursores dos seis objectivos (são normalizados).
    Lança ValueError se nenhuma rotação passar os filtros.
    """
    catalogue = catalogue or load_crops()
    defaults = defaults or load_engine_defaults()
    constraints = constraints or Constraints()
    horizon = rules["rotation"]["horizon_seasons"]
    lam = rules["rotation"]["lambda_family_repeat"]

    selected = [catalogue[key] for key in crops if key not in constraints.excluded]
    baseline_crop = catalogue[current_crop or site.current_crop]
    legume = catalogue.get(site.common_legume) if site.common_legume else None
    pool = _unique([*selected, baseline_crop, legume])

    historic = apply_scenario(clim, "historico", rules, site.lat)
    scenario_clim = historic if scenario == "historico" else apply_scenario(
        clim, scenario, rules, site.lat)
    stats_hist = crop_statistics(historic, pool, soil, site, rules, defaults)
    stats = stats_hist if scenario == "historico" else crop_statistics(
        scenario_clim, pool, soil, site, rules, defaults)
    seasons = season_table(scenario_clim, rules)
    mean_temp = float(seasons.loc[seasons["complete"], "tmean_c"].mean())

    candidates = [sequence for sequence in product(selected, repeat=horizon)
                  if feasible(list(sequence), soil, mean_temp, constraints)]
    if not candidates:
        raise ValueError("Nenhuma rotação viável com estas culturas e restrições. "
                         "É preciso aceitar pelo menos três culturas diferentes.")

    monoculture = (baseline_crop,) * horizon
    with_legume = None
    if legume is not None and legume.crop_id != baseline_crop.crop_id and horizon == 3:
        with_legume = (baseline_crop, legume, baseline_crop)

    def raw_of(sequence, source):
        return raw_values(sequence, source, rules, defaults, mean_temp, economics)

    # Limites congelados no cenário histórico, para os cenários serem comparáveis.
    bounds: dict[str, tuple[float, float] | None] = {
        "n_index": n_index_bounds(pool, defaults, horizon),
        "margin": None,
    }
    margins = [raw_of(sequence, stats_hist)["margin"] for sequence in [*candidates, monoculture]]
    if all(value is not None for value in margins):
        bounds["margin"] = (min(margins), max(margins))
    available = set(INDICATORS) - ({"margem"} if bounds["margin"] is None else set())
    used_weights = normalize_weights(weights, available)

    def evaluate(sequence: tuple[Crop, ...], label: str) -> StrategyResult:
        raw = raw_of(sequence, stats)
        indicators = to_indicators(raw, bounds, horizon)
        value = score(indicators, used_weights, lam, raw["family_repeats"])
        return StrategyResult(
            label=label, sequence=[crop.crop_id for crop in sequence], score=round(value, 4),
            indicators={key: None if item is None else round(item, 4)
                        for key, item in indicators.items()},
            raw=raw)

    # Em caso de empate (até 0,005), prefere-se a rotação que mantém a cultura actual.
    ranked = sorted((evaluate(sequence, "candidata") for sequence in candidates),
                    key=lambda item: (-round(item.score / 0.005),
                                      baseline_crop.crop_id not in item.sequence,
                                      -item.score, item.sequence))
    best = ranked[0]
    best.label = "recomendada"
    base = evaluate(monoculture, "monocultura")
    strategies = [base]
    # Convencional: a cultura actual alternada com outro cereal aceite (o de melhor score).
    others = [crop for crop in selected
              if crop.group == "cereal" and crop.crop_id != baseline_crop.crop_id]
    if others and horizon == 3:
        strategies.append(max(
            (evaluate((baseline_crop, crop, baseline_crop), "convencional") for crop in others),
            key=lambda item: item.score))
    if with_legume is not None:
        strategies.append(evaluate(with_legume, "com_leguminosa"))
    strategies.append(best)
    for item in strategies:
        item.contributions_vs_baseline = {
            key: round(value, 4) for key, value in contributions(item, base, used_weights).items()}

    flags = []
    if bounds["margin"] is None:
        flags.append("Margem económica não avaliada: params/economics.csv está por preencher.")
    not_evaluated = sorted({key for item in strategies
                            for key in item.raw["thermal_not_evaluated"]})
    if not_evaluated:
        flags.append("Adequação térmica não avaliada (limites ECOCROP por preencher): "
                     + ", ".join(catalogue[key].name_pt for key in not_evaluated) + ".")
    assumed_ky = [catalogue[key].name_pt for key in dict.fromkeys(best.sequence)
                  if catalogue[key].ky_status == "hipotese"]
    if assumed_ky:
        flags.append("Ky é hipótese (1,0) para: " + ", ".join(assumed_ky) + ".")
    if soil.source.startswith("Solo por defeito"):
        flags.append("Solo por defeito (franco): a água disponível não é a do local.")
    if soil.ph is None:
        flags.append("pH do solo desconhecido: o filtro de pH não foi aplicado.")

    source = str(clim["source"].iloc[0])
    return Recommendation(
        site={"id": site.id, "name": site.name, "lat": site.lat, "lon": site.lon},
        scenario=scenario,
        weights=dict(used_weights),
        strategies=strategies,
        explanation=explain(best, base, used_weights),
        assumptions=[
            "Agricultura de sequeiro, uma campanha por ano.",
            f"Sementeira a {site.sow_day:02d}/{site.sow_month:02d} em todas as campanhas.",
            "Sem escoamento superficial, rega ou ascensão capilar.",
            "O rendimento relativo conta só a água e o efeito leguminosa -> cereal.",
            "O solo é avaliado por um índice de azoto sem unidades, não por um balanço em kg.",
            "A mesma cultura não se repete dentro das três campanhas.",
        ],
        provenance={
            "clima": f"{source} ({scenario_nature(scenario)})",
            "solo": soil.source,
            "culturas": "FAO-56 e Peoples et al. 2021 (literatura); params/engine_defaults.yaml "
                        "(hipóteses)",
        },
        flags=flags,
        ranking=[{"sequence": item.sequence, "names": item.raw["names"], "score": item.score,
                  "indicators": item.indicators} for item in ranked[:top]],
        candidates=len(candidates),
        crop_stats={key: {name: round(value, 3) for name, value in item.items()}
                    for key, item in stats.items()},
        seasons=int(stats[baseline_crop.crop_id]["seasons"]),
    )
