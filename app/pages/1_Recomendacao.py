"""Página de recomendação: quatro estratégias lado a lado e o porquê."""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from app.components.charts import STRATEGY_STYLE, indicators_by_strategy  # noqa: E402
from data.climate import load_cached_climate  # noqa: E402
from data.features import complete_seasons, season_table  # noqa: E402
from data.soil import get_soil  # noqa: E402
from engine.params import load_crops, load_economics, load_rules, load_sites  # noqa: E402
from engine.rotation import recommend  # noqa: E402
from engine.rules import Constraints  # noqa: E402
from engine.schemas import INDICATORS  # noqa: E402

st.set_page_config(page_title="Recomendação · Machamba Shift", page_icon="🌱", layout="wide")
st.title("Recomendação")

rules = load_rules()
sites = load_sites()
catalogue = load_crops()

# --- Local ------------------------------------------------------------------
site_id = st.session_state.get("point_site", next(iter(sites)))
base_site = sites[site_id]
lat, lon = st.session_state.get("point", (base_site.lat, base_site.lon))
is_demo_point = (lat, lon) == (base_site.lat, base_site.lon)
clim = load_cached_climate(lat, lon)
if clim is None:
    st.info(f"Ainda não há clima guardado para {lat:.4f}, {lon:.4f}. "
            "Descarregue-o na página inicial.")
    st.stop()

# --- Escolhas do agricultor ---------------------------------------------------
NAMES = {key: crop.name_pt for key, crop in catalogue.items()}
PRESETS = {"equilibrado": "Equilibrado", "seguranca_alimentar": "Segurança alimentar",
           "recuperar_solo": "Recuperar o solo", "rendimento": "Rendimento"}
OBJECTIVES = {"agua": "Poupar água", "solo": "Cuidar do solo",
              "resiliencia": "Aguentar anos secos", "rendimento": "Rendimento",
              "margem": "Margem económica", "diversidade": "Diversidade"}
SCENARIOS = {
    "historico": "Histórico: todas as campanhas",
    "seco": "Seco: terço de campanhas com menos chuva",
    "favoravel": "Favorável: terço de campanhas com mais chuva",
    "seco_parametrico": "Seco paramétrico: menos 20% de chuva",
    "quente": "Quente: mais 2 °C",
    "ano": "Repetir uma campanha real",
}

with st.sidebar:
    st.header("Escolhas")
    current = st.selectbox("Cultura actual", list(NAMES), format_func=NAMES.get,
                           index=list(NAMES).index(base_site.current_crop))
    accepted = st.multiselect("Culturas que aceita plantar", list(NAMES), default=list(NAMES),
                              format_func=NAMES.get)
    keep_current = st.checkbox(f"Manter {NAMES[current].lower()} pelo menos uma vez", value=True)
    preset = st.selectbox("Prioridades", list(PRESETS), format_func=PRESETS.get)
    with st.expander("Ajustar prioridades"):
        sliders = {name: st.slider(OBJECTIVES[name], 0.0, 10.0,
                                   float(round(rules["weights"][preset][name] * 20) / 2), 0.5,
                                   key=f"w_{preset}_{name}")
                   for name in INDICATORS}
    with st.expander("Data de sementeira"):
        months = {10: "Outubro", 11: "Novembro", 12: "Dezembro", 1: "Janeiro"}
        sow_month = st.selectbox("Mês", list(months), format_func=months.get,
                                 index=list(months).index(base_site.sow_month))
        sow_day = st.number_input("Dia", 1, 28, min(base_site.sow_day, 28))

choice = st.selectbox("Cenário", list(SCENARIOS), format_func=SCENARIOS.get)
scenario = choice
if choice == "ano":
    years = complete_seasons(season_table(clim, rules))
    year = st.selectbox("Campanha", years[::-1], format_func=lambda y: f"{y}/{str(y + 1)[-2:]}")
    scenario = f"ano:{year}"

site = replace(base_site, lat=lat, lon=lon, sow_month=int(sow_month), sow_day=int(sow_day),
               current_crop=current,
               name=base_site.name if is_demo_point else "Ponto escolhido no mapa")
soil = get_soil(lat, lon, site_id=site_id if is_demo_point else None)
constraints = Constraints(required={current} if keep_current and current in accepted else set())

# --- Motor --------------------------------------------------------------------
try:
    result = recommend(site, clim, soil, accepted, sliders, rules, scenario=scenario,
                       constraints=constraints, current_crop=current, catalogue=catalogue,
                       economics=load_economics())
except ValueError as error:
    st.error(str(error))
    st.stop()

best = result.strategy("recomendada")
mono = result.strategy("monocultura")


def share_ok(item) -> float:
    return 1 - sum(item.raw["p_stress"]) / len(item.raw["p_stress"])


st.subheader(" → ".join(best.raw["names"]))
st.caption(f"{site.name} · {lat:.4f}, {lon:.4f} · {result.seasons} campanhas simuladas · "
           f"{result.candidates} rotações avaliadas")

cols = st.columns(4)
cols[0].metric("Score", f"{best.score:.2f}", f"{best.score - mono.score:+.2f} face à monocultura")
cols[1].metric("Água suficiente", f"{100 * share_ok(best):.0f}% das campanhas",
               f"{100 * (share_ok(best) - share_ok(mono)):+.0f} pontos",
               help="Campanhas em que a cultura recebeu pelo menos 80% da água de que precisa "
                    "(WRSI ≥ 80), em média nas três culturas da rotação")
cols[2].metric("Água pedida", f"{best.raw['etc_total_mm']:.0f} mm",
               f"{best.raw['etc_total_mm'] - mono.raw['etc_total_mm']:+.0f} mm",
               delta_color="inverse", help="Soma da ETc das três campanhas")
cols[3].metric("Rendimento relativo",
               f"{100 * sum(best.raw['y_rel']) / len(best.raw['y_rel']):.0f}%",
               f"{100 * (sum(best.raw['y_rel']) - sum(mono.raw['y_rel'])) / 3:+.0f} pontos",
               help="Fracção do rendimento potencial; conta só a água e o efeito da rotação")

st.markdown("**Porquê**")
for line in result.explanation:
    st.markdown(f"- {line}")

st.subheader("Comparação das estratégias")
st.plotly_chart(indicators_by_strategy(result.strategies), width="stretch")
st.dataframe(pd.DataFrame([
    {
        "Estratégia": STRATEGY_STYLE[item.label][0],
        "Rotação": " → ".join(item.raw["names"]),
        "Score": item.score,
        "Água suficiente (% campanhas)": round(100 * share_ok(item)),
        "Falha grave (% campanhas)": round(100 * sum(item.raw["p_failure"]) / 3),
        "Água pedida (mm)": item.raw["etc_total_mm"],
        "Rendimento relativo (%)": round(100 * sum(item.raw["y_rel"]) / 3),
        "Índice de azoto": item.raw["n_index"],
        "Famílias": item.raw["families"],
    }
    for item in result.strategies]), hide_index=True, width="stretch")
st.caption("Simulado pelo motor com clima " + result.provenance["clima"]
           + ". Estimativas para comparar rotações entre si, não previsões de colheita.")

with st.expander(f"Avisos e hipóteses ({len(result.flags)} avisos)", expanded=True):
    for flag in result.flags:
        st.markdown(f"- {flag}")
    st.markdown("**Hipóteses**")
    for line in result.assumptions:
        st.markdown(f"- {line}")
    st.markdown("**Origem dos dados**")
    for key, value in result.provenance.items():
        st.markdown(f"- {key.capitalize()}: {value}")

with st.expander("Culturas neste cenário"):
    st.dataframe(pd.DataFrame([
        {
            "Cultura": NAMES[key],
            "WRSI mediano": round(item["wrsi_median"]),
            "Campanhas com stress (%)": round(100 * item["p_stress"]),
            "Campanhas com falha (%)": round(100 * item["p_failure"]),
            "ETc (mm)": round(item["etc_median_mm"]),
            "Rendimento relativo (%)": round(100 * item["y_rel_median"]),
        }
        for key, item in sorted(result.crop_stats.items(),
                                key=lambda pair: -pair[1]["wrsi_median"])]),
        hide_index=True, width="stretch")
    st.caption("WRSI: percentagem das necessidades de água da cultura satisfeitas pela chuva. "
               "Stress: WRSI abaixo de 80. Falha: abaixo de 50.")

with st.expander("Dez melhores rotações"):
    st.dataframe(pd.DataFrame([
        {"Rotação": " → ".join(row["names"]), "Score": row["score"],
         **{OBJECTIVES[key]: value for key, value in row["indicators"].items()
            if value is not None}}
        for row in result.ranking]), hide_index=True, width="stretch")
