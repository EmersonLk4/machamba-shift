"""Gráficos da ficha do local.

Cores: par divergente azul/vermelho com cinzento neutro no meio (seco, normal,
favorável). A classe está sempre também na legenda e no texto ao passar o rato,
para não depender só da cor.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from app.components.hover import INK, MONO, SANS, style

TERCILE_STYLE = {
    "seco": ("Terço mais seco", "#d03b3b"),
    "normal": ("Normal", "#8f8e87"),
    "favoravel": ("Terço mais chuvoso", "#2a78d6"),
}
MUTED = "#898781"


def rain_by_season(table: pd.DataFrame) -> go.Figure:
    """Chuva de cada campanha (Outubro a Abril), com a classe de cada ano."""
    done = table[table["complete"]]
    labels = list(done["label"])
    median = float(done["rain_mm"].median())
    rank = done["rain_mm"].rank(method="min").astype(int)
    figure = go.Figure()
    for key, (name, color) in TERCILE_STYLE.items():
        part = done[done["tercile"] == key]
        figure.add_bar(
            x=part["label"], y=part["rain_mm"].round(0), name=name,
            marker={"color": color, "cornerradius": 4, "line": {"width": 0}},
            customdata=[[f"Campanha {row.label}", f"{row.rain_mm:.0f} mm · {name}",
                         f"{100 * row.rain_mm / median:.0f}% de uma campanha normal "
                         f"({median:.0f} mm). É a {rank[index]}.ª mais seca das {len(done)} "
                         f"campanhas desde {labels[0][:4]}."]
                        for index, row in part.iterrows()])
    figure.add_hline(y=median, line={"color": MUTED, "width": 1, "dash": "dot"},
                     annotation_text="normal", annotation_position="right",
                     annotation_font={"size": 12, "color": MUTED})
    style(figure, 320)
    figure.update_layout(barmode="overlay", bargap=0.25, margin={"r": 60})
    figure.update_xaxes(categoryorder="array", categoryarray=labels, tickangle=-45,
                        tickmode="array", tickvals=labels[::3])
    figure.update_yaxes(rangemode="tozero", ticksuffix=" mm")
    return figure


STRATEGY_STYLE = {
    "monocultura": ("Monocultura", "#2a78d6"),
    "convencional": ("Convencional", "#eb6834"),
    "com_leguminosa": ("Com leguminosa", "#1baf7a"),
    "recomendada": ("Recomendada", "#eda100"),
}
INDICATOR_NAMES = {
    "agua": "Água", "solo": "Solo", "resiliencia": "Resiliência",
    "rendimento": "Rendimento", "margem": "Margem", "diversidade": "Diversidade",
}


INDICATOR_HELP = {
    "agua": "Parte da água de que as culturas precisam que a chuva cobriu.",
    "solo": "Balanço de azoto do plano: sobe com leguminosas, desce com cereais seguidos.",
    "resiliencia": "Quão raramente faltou água ou houve falha grave.",
    "rendimento": "Colheita esperada face ao máximo, só pela água e pela rotação.",
    "margem": "Dinheiro esperado, com os preços indicados.",
    "diversidade": "Quantas famílias de culturas diferentes entram no plano.",
}


def indicators_by_strategy(strategies) -> go.Figure:
    """Indicadores (0 a 1, mais é melhor) de cada estratégia, lado a lado."""
    names = [key for key in INDICATOR_NAMES
             if any(item.indicators.get(key) is not None for item in strategies)]
    panel = [[INDICATOR_NAMES[key],
              " · ".join(f"{STRATEGY_STYLE[item.label][0]} {item.indicators[key]:.2f}"
                         for item in strategies),
              INDICATOR_HELP[key] + " De 0 a 1; mais é melhor."] for key in names]
    figure = go.Figure()
    for item in strategies:
        label, color = STRATEGY_STYLE[item.label]
        figure.add_bar(
            x=[INDICATOR_NAMES[key] for key in names],
            y=[item.indicators[key] for key in names], name=label,
            marker={"color": color, "cornerradius": 4, "line": {"width": 0}},
            customdata=panel)
    style(figure, 320)
    figure.update_layout(barmode="group", bargap=0.3, bargroupgap=0.08)
    figure.update_yaxes(range=[0, 1.02])
    return figure


RISK_STYLE = [
    ("ok", "Água suficiente", "#1baf7a"),
    ("stress", "Faltou água", "#eda100"),
    ("failure", "Falha grave", "#d03b3b"),
]


def crop_risk(crop_stats: dict, names: dict[str, str], keep_order: bool = False) -> go.Figure:
    """Para cada cultura, em quantas de cada 10 campanhas houve água suficiente, falta ou falha.

    Com keep_order=True as linhas ficam pela ordem dada (usado para as datas de sementeira).
    """
    order = list(crop_stats)[::-1] if keep_order else sorted(
        crop_stats, key=lambda key: (1 - crop_stats[key]["p_stress"],
                                     -crop_stats[key]["p_failure"]))
    parts = {
        "ok": [10 * (1 - crop_stats[key]["p_stress"]) for key in order],
        "stress": [10 * (crop_stats[key]["p_stress"] - crop_stats[key]["p_failure"])
                   for key in order],
        "failure": [10 * crop_stats[key]["p_failure"] for key in order],
    }
    panel = [[names[item],
              " · ".join(f"{label} {parts[key][index]:.0f}" for key, label, _ in RISK_STYLE),
              "Em cada 10 campanhas reais. Água suficiente: a chuva cobriu pelo menos 80% do "
              "que a cultura precisava. Falha grave: cobriu menos de metade."]
             for index, item in enumerate(order)]
    figure = go.Figure()
    for key, label, color in RISK_STYLE:
        figure.add_bar(
            y=[names[item] for item in order], x=parts[key], name=label, orientation="h",
            marker={"color": color, "line": {"color": "#ffffff", "width": 2}},
            text=[f"{value:.0f}" if value >= 0.5 else "" for value in parts[key]],
            textposition="inside", insidetextanchor="middle", textangle=0,
            textfont={"color": "#1a1a19", "size": 13}, customdata=panel)
    style(figure, 70 + 34 * len(order), horizontal=True)
    figure.update_layout(barmode="stack", bargap=0.3, legend={"traceorder": "normal"})
    figure.update_xaxes(range=[0, 10], dtick=2)
    figure.update_yaxes(tickfont={"family": SANS, "size": 14, "color": INK})
    return figure


def crop_range(crop_stats: dict, names: dict[str, str], threshold: float = 80) -> go.Figure:
    """Leque de resultados de cada cultura: de uma campanha má a uma boa, com a normal ao meio."""
    order = sorted(crop_stats, key=lambda key: crop_stats[key]["wrsi_median"])
    labels = [names[key] for key in order]
    low = [crop_stats[key]["wrsi_p10"] for key in order]
    mid = [crop_stats[key]["wrsi_median"] for key in order]
    high = [crop_stats[key]["wrsi_p90"] for key in order]
    panel = [[label, f"Má {a:.0f}% · Normal {m:.0f}% · Boa {b:.0f}%",
              "Parte da água necessária que a chuva cobriu numa campanha má (1 em 10), numa "
              f"normal e numa boa (1 em 10). Acima de {threshold:.0f}% é suficiente."]
             for label, a, m, b in zip(labels, low, mid, high, strict=True)]
    figure = go.Figure()
    for label, a, b in zip(labels, low, high, strict=True):
        figure.add_scatter(x=[a, b], y=[label, label], mode="lines", showlegend=False,
                           line={"color": "#cbd5e1", "width": 6}, hoverinfo="skip")
    marks = [(low, "Campanha má", "#d03b3b", "circle", 12),
             (mid, "Campanha normal", "#0f172a", "diamond", 13),
             (high, "Campanha boa", "#2a78d6", "circle", 12)]
    for values, name, color, symbol, size in marks:
        figure.add_scatter(x=values, y=labels, mode="markers", name=name, customdata=panel,
                           marker={"color": color, "size": size, "symbol": symbol,
                                   "line": {"color": "white", "width": 2}})
    figure.add_vline(x=threshold, line={"color": MUTED, "width": 1, "dash": "dot"})
    style(figure, 70 + 34 * len(order), horizontal=True)
    figure.update_xaxes(range=[0, 102], ticksuffix="%")
    figure.update_yaxes(tickfont={"family": SANS, "size": 14, "color": INK})
    return figure


WARM, WARM_BAND, RAIN = "#d97706", "rgba(251,191,36,0.22)", "#3b9bd4"


def _band(figure: go.Figure, x, low, high) -> None:
    figure.add_scatter(x=x, y=low, mode="lines", line={"width": 0}, showlegend=False,
                       hoverinfo="skip")
    figure.add_scatter(x=x, y=high, mode="lines", line={"width": 0}, fill="tonexty",
                       fillcolor=WARM_BAND, showlegend=False, hoverinfo="skip")


def temperature_by_season(table: pd.DataFrame) -> go.Figure:
    """Temperatura de cada campanha: média, com a faixa da mínima à máxima."""
    done = table[table["complete"]]
    labels = list(done["label"])
    mean = float(done["tmean_c"].mean())
    figure = go.Figure()
    _band(figure, done["label"], done["tmin_c"].round(2), done["tmax_c"].round(2))
    figure.add_scatter(
        x=done["label"], y=done["tmean_c"].round(2), mode="lines+markers", showlegend=False,
        line={"color": WARM, "width": 2},
        marker={"size": 8, "color": WARM, "line": {"color": "white", "width": 2}},
        customdata=[[f"Campanha {row.label}",
                     f"Mín {row.tmin_c:.1f} · Méd {row.tmean_c:.1f} · Máx {row.tmax_c:.1f} °C",
                     f"{row.tmean_c - mean:+.1f} °C face à média de todas as campanhas "
                     f"({mean:.1f} °C). A faixa vai da mínima à máxima médias."]
                    for row in done.itertuples()])
    style(figure, 300)
    figure.update_xaxes(tickangle=-45, tickmode="array", tickvals=labels[::3])
    figure.update_yaxes(ticksuffix="°C")
    return figure


def monthly_temperature(view: pd.DataFrame, period: str) -> go.Figure:
    """Temperatura por mês: média com valor escrito, e faixa da mínima à máxima."""
    figure = go.Figure()
    _band(figure, view["label"], view["tmin_c"].round(2), view["tmax_c"].round(2))
    panel = []
    for row in view.itertuples():
        gap = row.tmean_c - row.tmean_normal_c
        text = (f"Média de {row.years} anos para este mês." if abs(gap) < 0.005 else
                f"{abs(gap):.1f} °C {'acima' if gap > 0 else 'abaixo'} da média de "
                f"{row.label} em {row.years} anos ({row.tmean_normal_c:.1f} °C).")
        panel.append([f"{row.label} · {period}",
                      f"Mín {row.tmin_c:.1f} · Méd {row.tmean_c:.1f} · Máx {row.tmax_c:.1f} °C",
                      text])
    figure.add_scatter(
        x=view["label"], y=view["tmean_c"].round(2), mode="lines+markers+text",
        showlegend=False, line={"color": WARM, "width": 2},
        marker={"size": 9, "color": WARM, "line": {"color": "white", "width": 2}},
        text=[f"{value:.1f}°" for value in view["tmean_c"]], textposition="top center",
        textfont={"family": MONO, "size": 12, "color": INK}, customdata=panel)
    style(figure, 300)
    figure.update_yaxes(ticksuffix="°C")
    return figure


def monthly_rain(view: pd.DataFrame, period: str, compare: bool) -> go.Figure:
    """Chuva por mês, com o valor escrito; com compare=True marca também a média do mês."""
    panel = []
    for row in view.itertuples():
        extras = [f"Chuva {row.rain_mm:.0f} mm"]
        if pd.notna(row.soil_pct):
            extras.append(f"Solo {row.soil_pct:.0f}%")
        if pd.notna(row.rh_pct):
            extras.append(f"Ar {row.rh_pct:.0f}%")
        if pd.notna(row.wind_kmh):
            extras.append(f"Vento {row.wind_kmh:.0f} km/h")
        if compare:
            share = 100 * row.rain_mm / row.rain_normal_mm if row.rain_normal_mm > 0 else 0
            text = (f"{share:.0f}% da chuva média de {row.label} "
                    f"({row.rain_normal_mm:.0f} mm em {row.years} anos).")
        else:
            text = (f"Média de {row.years} anos. O mais chuvoso foi {int(row.wet_year)} "
                    f"({row.wet_mm:.0f} mm); o mais seco, {int(row.dry_year)} "
                    f"({row.dry_mm:.0f} mm).")
        panel.append([f"{row.label} · {period}", " · ".join(extras), text])
    figure = go.Figure()
    figure.add_bar(
        x=view["label"], y=view["rain_mm"].round(0), name="Chuva do mês",
        marker={"color": RAIN, "cornerradius": 4, "line": {"width": 0}},
        showlegend=compare, customdata=panel)
    above = view[["rain_mm", "rain_normal_mm"]].max(axis=1) if compare else view["rain_mm"]
    figure.add_scatter(                       # valor escrito acima da barra e da marca da média
        x=view["label"], y=above, mode="text", showlegend=False, hoverinfo="skip",
        text=[f"{value:.0f}mm" for value in view["rain_mm"]], textposition="top center",
        textfont={"family": MONO, "size": 11, "color": INK}, cliponaxis=False)
    if compare:
        figure.add_scatter(
            x=view["label"], y=view["rain_normal_mm"].round(0), mode="markers",
            name="Média do mês", hoverinfo="skip",
            marker={"symbol": "line-ew", "size": 22,
                    "line": {"color": "#0f172a", "width": 2.5}})
    style(figure, 300)
    figure.update_layout(bargap=0.45)
    top = max(float(view["rain_mm"].max()), float(view["rain_normal_mm"].max()), 1.0)
    figure.update_yaxes(range=[0, top * 1.18], ticksuffix="mm")
    return figure
