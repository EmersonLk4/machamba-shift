"""Gráficos da ficha do local.

Cores: par divergente azul/vermelho com cinzento neutro no meio (seco, normal,
favorável). A classe está sempre também na legenda e no texto ao passar o rato,
para não depender só da cor.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

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
    figure = go.Figure()
    for key, (name, color) in TERCILE_STYLE.items():
        part = done[done["tercile"] == key]
        figure.add_bar(
            x=part["label"], y=part["rain_mm"].round(0), name=name,
            marker={"color": color, "cornerradius": 3, "line": {"width": 0}},
            hovertemplate="Campanha %{x}<br>%{y:.0f} mm · " + name + "<extra></extra>",
        )
    median = float(done["rain_mm"].median())
    figure.add_hline(y=median, line={"color": MUTED, "width": 1, "dash": "dot"},
                     annotation_text="mediana", annotation_position="right",
                     annotation_font={"size": 12, "color": MUTED})
    figure.update_layout(
        barmode="overlay", bargap=0.25, height=340,
        margin={"l": 10, "r": 70, "t": 30, "b": 10},
        legend={"orientation": "h", "y": 1.12, "x": 0, "title": None},
        xaxis={"categoryorder": "array", "categoryarray": labels, "tickangle": -45,
               "tickmode": "array", "tickvals": labels[::3], "showgrid": False,
               "title": None},
        yaxis={"title": "Chuva da campanha (mm)", "rangemode": "tozero",
               "gridcolor": "rgba(137,135,129,0.25)", "zeroline": False},
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
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


def indicators_by_strategy(strategies) -> go.Figure:
    """Indicadores (0 a 1, mais é melhor) de cada estratégia, lado a lado."""
    names = [key for key in INDICATOR_NAMES
             if any(item.indicators.get(key) is not None for item in strategies)]
    figure = go.Figure()
    for item in strategies:
        label, color = STRATEGY_STYLE[item.label]
        figure.add_bar(
            x=[INDICATOR_NAMES[key] for key in names],
            y=[item.indicators[key] for key in names], name=label,
            marker={"color": color, "cornerradius": 3, "line": {"width": 0}},
            customdata=[" → ".join(item.raw["names"])] * len(names),
            hovertemplate=label + " · %{x}: %{y:.2f}<br>%{customdata}<extra></extra>",
        )
    figure.update_layout(
        barmode="group", bargap=0.3, bargroupgap=0.08, height=340,
        margin={"l": 10, "r": 10, "t": 30, "b": 10},
        legend={"orientation": "h", "y": 1.12, "x": 0, "title": None},
        xaxis={"showgrid": False, "title": None},
        yaxis={"title": "Indicador (0 a 1, mais é melhor)", "range": [0, 1.02],
               "gridcolor": "rgba(137,135,129,0.25)", "zeroline": False},
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    return figure


RISK_STYLE = [
    ("ok", "Água suficiente", "#1baf7a"),
    ("stress", "Faltou água", "#eda100"),
    ("failure", "Falha grave", "#d03b3b"),
]


def crop_risk(crop_stats: dict, names: dict[str, str]) -> go.Figure:
    """Para cada cultura, em quantas de cada 10 campanhas houve água suficiente, falta ou falha."""
    order = sorted(crop_stats, key=lambda key: (1 - crop_stats[key]["p_stress"],
                                                -crop_stats[key]["p_failure"]))
    parts = {
        "ok": [10 * (1 - crop_stats[key]["p_stress"]) for key in order],
        "stress": [10 * (crop_stats[key]["p_stress"] - crop_stats[key]["p_failure"])
                   for key in order],
        "failure": [10 * crop_stats[key]["p_failure"] for key in order],
    }
    figure = go.Figure()
    for key, label, color in RISK_STYLE:
        figure.add_bar(
            y=[names[item] for item in order], x=parts[key], name=label, orientation="h",
            marker={"color": color, "line": {"color": "rgba(255,255,255,0.9)", "width": 2}},
            text=[f"{value:.0f}" if value >= 0.5 else "" for value in parts[key]],
            textposition="inside", insidetextanchor="middle", textangle=0,
            textfont={"color": "#1a1a19", "size": 13},
            hovertemplate="%{y} · " + label + " em %{x:.1f} de cada 10 campanhas<extra></extra>",
        )
    figure.update_layout(
        barmode="stack", bargap=0.3, height=60 + 34 * len(order),
        margin={"l": 10, "r": 10, "t": 30, "b": 10},
        legend={"orientation": "h", "y": 1.0, "yanchor": "bottom", "x": 0, "title": None,
                "traceorder": "normal"},
        xaxis={"range": [0, 10], "dtick": 2, "title": "Em cada 10 campanhas",
               "gridcolor": "rgba(137,135,129,0.25)", "zeroline": False},
        yaxis={"title": None, "showgrid": False},
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    return figure


def crop_range(crop_stats: dict, names: dict[str, str], threshold: float = 80) -> go.Figure:
    """Leque de resultados de cada cultura: de uma campanha má a uma boa, com a normal ao meio."""
    order = sorted(crop_stats, key=lambda key: crop_stats[key]["wrsi_median"])
    labels = [names[key] for key in order]
    low = [crop_stats[key]["wrsi_p10"] for key in order]
    mid = [crop_stats[key]["wrsi_median"] for key in order]
    high = [crop_stats[key]["wrsi_p90"] for key in order]
    figure = go.Figure()
    for label, a, b in zip(labels, low, high, strict=True):
        figure.add_scatter(x=[a, b], y=[label, label], mode="lines", showlegend=False,
                           line={"color": MUTED, "width": 6}, hoverinfo="skip")
    figure.add_scatter(x=low, y=labels, mode="markers", name="Campanha má (1 em cada 10)",
                       marker={"color": "#d03b3b", "size": 12,
                               "line": {"color": "white", "width": 2}},
                       hovertemplate="%{y} · campanha má: a chuva cobriu %{x:.0f}%<extra></extra>")
    figure.add_scatter(x=mid, y=labels, mode="markers", name="Campanha normal",
                       marker={"color": "#1a1a19", "size": 13, "symbol": "diamond",
                               "line": {"color": "white", "width": 2}},
                       hovertemplate="%{y} · campanha normal: a chuva cobriu %{x:.0f}%"
                                     "<extra></extra>")
    figure.add_scatter(x=high, y=labels, mode="markers", name="Campanha boa (1 em cada 10)",
                       marker={"color": "#2a78d6", "size": 12,
                               "line": {"color": "white", "width": 2}},
                       hovertemplate="%{y} · campanha boa: a chuva cobriu %{x:.0f}%<extra></extra>")
    figure.add_vline(x=threshold, line={"color": MUTED, "width": 1, "dash": "dot"},
                     annotation_text="água suficiente", annotation_position="top",
                     annotation_font={"size": 12, "color": MUTED})
    figure.update_layout(
        height=70 + 34 * len(order), margin={"l": 10, "r": 10, "t": 40, "b": 10},
        legend={"orientation": "h", "y": 1.0, "yanchor": "bottom", "x": 0, "title": None},
        xaxis={"range": [0, 102], "title": "Água de que a cultura precisa coberta pela chuva (%)",
               "gridcolor": "rgba(137,135,129,0.25)", "zeroline": False},
        yaxis={"title": None, "showgrid": False},
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    return figure
