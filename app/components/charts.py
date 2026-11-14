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
