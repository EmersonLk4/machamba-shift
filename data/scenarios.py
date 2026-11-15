"""Cenários climáticos como funções puras sobre o clima histórico.

historico         todas as campanhas completas
seco              terço de campanhas com menos chuva sazonal (anos reais)
favoravel         terço de campanhas com mais chuva sazonal (anos reais)
seco_parametrico  todas as campanhas, chuva diária x 0,8          (simulado)
quente            todas as campanhas, Tmax e Tmin + 2 °C, ET0 recalculada (simulado)
ano:AAAA          repetição de uma campanha real, por exemplo "ano:2015" = 2015/16

O resultado tem as mesmas colunas da entrada e só contém os anos agrícolas das
campanhas incluídas (de Julho a Junho, para o motor ter os meses anteriores à sementeira).
"""

from __future__ import annotations

import pandas as pd

from data.features import add_et0, complete_seasons, season_table

NATURE = {
    "historico": "modelado",
    "seco": "modelado",
    "favoravel": "modelado",
    "seco_parametrico": "simulado",
    "quente": "simulado",
}


def scenario_nature(scenario: str) -> str:
    """'modelado' para cenários feitos de anos reais, 'simulado' para os paramétricos."""
    return "modelado" if scenario.startswith("ano:") else NATURE[scenario]


def scenario_seasons(table: pd.DataFrame, scenario: str) -> list[int]:
    """Campanhas incluídas no cenário, a partir da tabela de season_table()."""
    complete = complete_seasons(table)
    if scenario in ("historico", "seco_parametrico", "quente"):
        return complete
    if scenario in ("seco", "favoravel"):
        return [year for year in complete if table.loc[year, "tercile"] == scenario]
    if scenario.startswith("ano:"):
        year = int(scenario.split(":", 1)[1])
        if year not in complete:
            label = f"{year}/{str(year + 1)[-2:]}"
            raise ValueError(f"A campanha {label} não existe ou está incompleta")
        return [year]
    raise ValueError(f"Cenário desconhecido: {scenario}")


def apply_scenario(clim: pd.DataFrame, scenario: str, rules: dict, lat: float) -> pd.DataFrame:
    """Devolve o clima do cenário pedido.

    Os terços e a lista de campanhas completas são sempre calculados sobre o clima
    histórico, antes de qualquer alteração, para os cenários serem comparáveis.
    """
    table = season_table(clim, rules)
    years = scenario_seasons(table, scenario)
    out = clim[clim["season"].isin(years)].copy()

    if scenario == "seco_parametrico":
        out["p_mm"] = out["p_mm"] * rules["scenarios"]["seco_parametrico"]["rain_factor"]
    elif scenario == "quente":
        delta = rules["scenarios"]["quente"]["delta_t_c"]
        for column in ("tmax_c", "tmin_c", "tmean_c"):
            out[column] = out[column] + delta
        out = add_et0(out, lat)
    return out


def adjust_climate(clim: pd.DataFrame, rain_pct: float, delta_t_c: float,
                   lat: float) -> pd.DataFrame:
    """Clima hipotético: chuva diária alterada em rain_pct por cento e temperaturas somadas
    de delta_t_c graus, com a ET0 recalculada. É uma simulação, não uma previsão: as datas
    e a sequência dos dias de chuva ficam as do passado.
    """
    if rain_pct == 0 and delta_t_c == 0:
        return clim
    out = clim.copy()
    out["p_mm"] = out["p_mm"] * (1 + rain_pct / 100)
    if delta_t_c:
        for column in ("tmax_c", "tmin_c", "tmean_c"):
            out[column] = out[column] + delta_t_c
        out = add_et0(out, lat)
    return out
