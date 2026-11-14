"""Página de cenários: o clima do ponto em cada cenário, comparado com o histórico.

A comparação das rotações por cenário entra na Fase 4, quando o motor existir.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from app.components.labels import origin_label  # noqa: E402
from data.climate import load_cached_climate  # noqa: E402
from data.features import complete_seasons, season_table, site_summary  # noqa: E402
from data.scenarios import apply_scenario, scenario_nature  # noqa: E402
from engine.params import load_rules, load_sites  # noqa: E402

st.set_page_config(page_title="Cenários · Machamba Shift", page_icon="🌱", layout="wide")
st.title("Cenários")

rules = load_rules()
sites = load_sites()
first = next(iter(sites.values()))
lat, lon = st.session_state.get("point", (first.lat, first.lon))
clim = load_cached_climate(lat, lon)

if clim is None:
    st.info(f"Ainda não há clima guardado para {lat:.4f}, {lon:.4f}. "
            "Descarregue-o na página inicial.")
    st.stop()

history = season_table(clim, rules)
years = complete_seasons(history)

NAMES = {
    "historico": "Histórico: todas as campanhas",
    "seco": "Seco: terço de campanhas com menos chuva",
    "favoravel": "Favorável: terço de campanhas com mais chuva",
    "seco_parametrico": "Seco paramétrico: chuva × "
                        f"{rules['scenarios']['seco_parametrico']['rain_factor']}",
    "quente": f"Quente: +{rules['scenarios']['quente']['delta_t_c']:.0f} °C",
    "ano": "Repetir uma campanha real",
}
choice = st.selectbox("Cenário", list(NAMES), format_func=NAMES.get)
scenario = choice
if choice == "ano":
    year = st.selectbox("Campanha", years[::-1],
                        format_func=lambda y: f"{y}/{str(y + 1)[-2:]}")
    scenario = f"ano:{year}"

scenario_clim = apply_scenario(clim, scenario, rules, lat)
table = season_table(scenario_clim, rules)
base = site_summary(history)
current = site_summary(table)

st.caption(f"Ponto {lat:.4f}, {lon:.4f} · {current['seasons']} de {base['seasons']} campanhas · "
           + origin_label(scenario_nature(scenario),
                          "anos reais" if scenario_nature(scenario) == "modelado"
                          else "alteração aplicada ao histórico"))

def delta(value: float, unit: str, digits: int = 0) -> str | None:
    """Diferença para o histórico; nada a mostrar no próprio histórico."""
    return None if scenario == "historico" else f"{value:+.{digits}f} {unit}"


cols = st.columns(4)
cols[0].metric("Chuva mediana", f"{current['rain_median_mm']:.0f} mm",
               delta(current["rain_median_mm"] - base["rain_median_mm"], "mm"))
cols[1].metric("ET0 mediana", f"{current['et0_median_mm']:.0f} mm",
               delta(current["et0_median_mm"] - base["et0_median_mm"], "mm"),
               delta_color="inverse")
cols[2].metric("Temperatura média", f"{current['tmean_c']:.1f} °C",
               delta(current["tmean_c"] - base["tmean_c"], "°C", 1), delta_color="inverse")
cols[3].metric("Época de crescimento", f"{current['season_length_median_days']:.0f} dias",
               delta(current["season_length_median_days"] - base["season_length_median_days"],
                     "dias"))

done = table[table["complete"]]
st.write("Campanhas incluídas: " + ", ".join(done["label"]))
st.dataframe(
    done.rename(columns={"label": "Campanha", "rain_mm": "Chuva (mm)", "et0_mm": "ET0 (mm)",
                         "tmean_c": "T média (°C)", "season_length_days": "Época (dias)"})
    [["Campanha", "Chuva (mm)", "ET0 (mm)", "T média (°C)", "Época (dias)"]].round(1),
    hide_index=True, width="stretch")
st.info("A comparação das rotações em cada cenário entra na Fase 4, com o motor de decisão.")
