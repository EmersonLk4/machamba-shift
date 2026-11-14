"""Gráfico com painel por baixo que só aparece ao passar o rato num ponto.

O Streamlit não entrega eventos de "hover" ao Python, por isso o gráfico é desenhado numa
moldura HTML própria (plotly.js) e um pequeno script preenche o painel. Cada ponto traz em
`customdata` três textos: título, valores e uma frase. Nada é calculado no navegador.
"""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
SANS = "'Source Sans Pro', 'Segoe UI', system-ui, sans-serif"
GRID = "#e9eef3"
INK, SOFT = "#0f172a", "#64748b"
TONES = {
    "warm": ("#fffbeb", "#fcd34d", "#9a3412"),
    "cool": ("#f0f9ff", "#7dd3fc", "#0f766e"),
    "green": ("#f0fdf4", "#86efac", "#166534"),
}
PANEL_HEIGHT = 86

PAGE = """<div class="card"><div id="plot">{plot}</div>
<div id="panel" class="panel"><div class="row"><b id="p-title"></b><span id="p-values"></span>
</div><p id="p-text"></p></div></div>
<style>
html,body{{margin:0;background:transparent;font-family:{sans};color:{ink}}}
.card{{border:1px solid #e2e8f0;border-radius:14px;background:#fff;padding:10px 12px 12px}}
.panel{{visibility:hidden;opacity:0;transition:opacity .12s;border:1px solid {border};
background:{fill};border-radius:10px;padding:9px 14px;height:{inner}px;box-sizing:border-box;
overflow:hidden}}
.panel.on{{visibility:visible;opacity:1}}
.row{{display:flex;justify-content:space-between;gap:12px;align-items:baseline}}
.row b{{font-family:{mono};font-size:13.5px}}
.row span{{font-family:{mono};font-size:13px;font-weight:600;color:{accent};text-align:right}}
.panel p{{margin:5px 0 0;font-size:13.5px;color:{soft};line-height:1.35}}
</style>"""

SCRIPT = """
var plot = document.getElementById('{plot_id}');
plot.on('plotly_hover', function (event) {
  var data = null;
  event.points.forEach(function (point) {
    if (!data && point.customdata) data = point.customdata;
  });
  if (!data) return;
  document.getElementById('p-title').textContent = data[0];
  document.getElementById('p-values').textContent = data[1];
  document.getElementById('p-text').textContent = data[2];
  document.getElementById('panel').classList.add('on');
});
plot.on('plotly_unhover', function () {
  document.getElementById('panel').classList.remove('on');
});
"""


def style(figure: go.Figure, height: int, horizontal: bool = False) -> go.Figure:
    """Aspecto comum: fundo branco, grelha leve, números em letra monoespaçada, sem títulos."""
    figure.update_layout(
        height=height, margin={"l": 8, "r": 12, "t": 34, "b": 8},
        font={"family": MONO, "size": 12, "color": SOFT},
        hovermode="y" if horizontal else "x", hoverdistance=60,
        legend={"orientation": "h", "y": 1.0, "yanchor": "bottom", "x": 0, "title": None,
                "font": {"family": SANS, "size": 13, "color": INK}},
        plot_bgcolor="#ffffff", paper_bgcolor="#ffffff", dragmode=False)
    figure.update_xaxes(gridcolor=GRID, zeroline=False, showline=False, fixedrange=True,
                        showgrid=horizontal, automargin=True)
    figure.update_yaxes(gridcolor=GRID, zeroline=False, showline=False, fixedrange=True,
                        showgrid=not horizontal, automargin=True)
    return figure


def hover_html(figure: go.Figure, tone: str = "cool", cdn: bool = True) -> str:
    """HTML completo do gráfico com o painel. Os balões normais do Plotly ficam desligados."""
    for trace in figure.data:
        if trace.hoverinfo != "skip":
            trace.update(hoverinfo="none", hovertemplate=None)
    fill, border, accent = TONES[tone]
    plot = figure.to_html(full_html=False, include_plotlyjs="cdn" if cdn else True,
                          config={"displayModeBar": False, "responsive": True},
                          post_script=SCRIPT)
    return PAGE.format(plot=plot, sans=SANS, mono=MONO, ink=INK, soft=SOFT, fill=fill,
                       border=border, accent=accent, inner=PANEL_HEIGHT - 10)


def hover_chart(figure: go.Figure, tone: str = "cool") -> None:
    """Desenha o gráfico na página, com o painel que aparece ao passar o rato."""
    height = int(figure.layout.height or 320) + PANEL_HEIGHT + 30
    html = hover_html(figure, tone)
    if hasattr(st, "iframe"):
        st.iframe(html, height=height)
    else:                                   # versões do Streamlit anteriores a st.iframe
        import streamlit.components.v1 as components
        components.html(html, height=height)
