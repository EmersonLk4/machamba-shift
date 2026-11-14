"""Gerador de explicações em linguagem simples.

A contribuição de cada objectivo para a vantagem sobre a monocultura é
w_k * (s_k da recomendada - s_k da monocultura). As duas maiores positivas dão as
frases "porquê"; a mais negativa dá a frase "em troca", que nunca se omite.
Todos os números das frases vêm de StrategyResult.raw: nada é escrito à mão.
"""

from __future__ import annotations

from engine.schemas import StrategyResult

MIN_EFFECT = 0.005      # contribuições abaixo disto não merecem uma frase


def contributions(best: StrategyResult, baseline: StrategyResult,
                  weights: dict[str, float]) -> dict[str, float]:
    """Contribuição de cada indicador avaliado para a diferença de score."""
    result = {}
    for name, value in best.indicators.items():
        other = baseline.indicators.get(name)
        if value is None or other is None:
            continue
        result[name] = weights[name] * (value - other)
    return result


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _in_ten(share_best: float, share_base: float) -> tuple[str, str]:
    """'7 de cada 10' quando o arredondamento distingue os dois; senão percentagens."""
    a, b = round(10 * share_best), round(10 * share_base)
    if a != b:
        return f"{a} de cada 10 campanhas", f"{b}"
    return f"{100 * share_best:.0f}% das campanhas", f"{100 * share_base:.0f}%"


def _join(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " e " + names[-1]


def _sentence(name: str, best: StrategyResult, base: StrategyResult, positive: bool) -> str:
    b, o = best.raw, base.raw
    crop0 = o["names"][0].lower()
    if name == "resiliencia":
        ok_b, ok_o = _in_ten(1 - _mean(b["p_stress"]), 1 - _mean(o["p_stress"]))
        fail_b, fail_o = 100 * _mean(b["p_failure"]), 100 * _mean(o["p_failure"])
        if positive:
            return (f"Aguenta melhor os anos secos: as culturas tiveram água suficiente em "
                    f"{ok_b}, contra {ok_o} na monocultura de {crop0}. Falha grave em "
                    f"{fail_b:.0f}% das campanhas, contra {fail_o:.0f}%. (simulado)")
        return (f"fica mais exposta aos anos secos: água suficiente em {ok_b}, "
                f"contra {ok_o} na monocultura de {crop0}. (simulado)")
    if name == "agua":
        eb, eo = b["etc_total_mm"], o["etc_total_mm"]
        change = 100 * (eb / eo - 1) if eo else 0.0
        if positive:
            return (f"Pede menos água: {eb:.0f} mm nas três campanhas, contra {eo:.0f} mm "
                    f"({change:+.0f}%). (simulado)")
        return f"pede mais água: {eb:.0f} mm nas três campanhas, contra {eo:.0f} mm. (simulado)"
    if name == "solo":
        legumes = b["legumes"]
        if positive and legumes:
            shares = _join([f"{item['ndfa']:.0f}%" for item in legumes])
            names = _join([item["name"].lower() for item in legumes])
            kind = "uma leguminosa que obtém" if len(legumes) == 1 else "leguminosas que obtêm"
            return (f"Poupa o solo: inclui {names}, {kind} do ar cerca de {shares} do azoto "
                    f"de que precisa, em vez de só o retirar. (literatura)")
        if positive:
            return (f"Poupa o solo: retira menos azoto do que três campanhas de {crop0}. "
                    f"(índice qualitativo)")
        return f"retira mais azoto do solo do que a monocultura de {crop0}. (índice qualitativo)"
    if name == "rendimento":
        yb, yo = 100 * _mean(b["y_rel"]), 100 * _mean(o["y_rel"])
        if positive:
            return (f"Rende mais em relação ao potencial: {yb:.0f}% contra {yo:.0f}%. "
                    f"(simulado: conta só a água e o efeito da rotação)")
        return (f"o rendimento em relação ao potencial é mais baixo: {yb:.0f}% contra "
                f"{yo:.0f}%. (simulado: conta só a água e o efeito da rotação)")
    if name == "diversidade":
        if positive:
            return (f"Alterna {b['families']} famílias botânicas em vez de "
                    f"{o['families']}, o que reduz a pressão de pragas e doenças. "
                    f"(regra agronómica)")
        return "tem menos diversidade de famílias botânicas. (regra agronómica)"
    if positive:
        return "A margem bruta estimada é mais alta. (simulado com os preços de params/)"
    return "a margem bruta estimada é mais baixa. (simulado com os preços de params/)"


def explain(best: StrategyResult, baseline: StrategyResult,
            weights: dict[str, float]) -> list[str]:
    """Até duas razões e sempre uma frase 'Em troca'."""
    effects = contributions(best, baseline, weights)
    ordered = sorted(effects.items(), key=lambda item: item[1], reverse=True)
    reasons = [_sentence(name, best, baseline, True)
               for name, value in ordered[:2] if value > MIN_EFFECT]
    if not reasons:
        reasons = ["Com estas prioridades, nenhuma rotação viável supera claramente a "
                   "monocultura nos objectivos avaliados."]
    worst_name, worst_value = ordered[-1] if ordered else (None, 0.0)
    if worst_name is not None and worst_value < -MIN_EFFECT:
        cost = "Em troca: " + _sentence(worst_name, best, baseline, False)
    else:
        cost = ("Em troca: nenhum dos objectivos avaliados piora face à monocultura. "
                "O que não foi avaliado está na lista de avisos.")
    return [*reasons, cost]
