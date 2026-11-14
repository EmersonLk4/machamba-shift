"""Página única: o local, o risco de cada cultura e o plano para três campanhas.

Correr na raiz do repositório:  streamlit run app/O_que_plantar.py
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402
from streamlit_folium import st_folium  # noqa: E402

from app.components.charts import (  # noqa: E402
    STRATEGY_STYLE,
    crop_range,
    crop_risk,
    indicators_by_strategy,
    rain_by_season,
)
from app.components.maps import add_cells, base_map  # noqa: E402
from data.climate import get_climate, load_cached_climate  # noqa: E402
from data.features import complete_seasons, season_table, site_summary, trend  # noqa: E402
from data.grid import cell_of, load_grid, normals  # noqa: E402
from data.soil import get_soil  # noqa: E402
from engine.params import load_crops, load_economics, load_rules, load_sites  # noqa: E402
from engine.rotation import recommend  # noqa: E402
from engine.rules import Constraints  # noqa: E402
from engine.schemas import INDICATORS  # noqa: E402

st.set_page_config(page_title="Machamba Shift", page_icon="🌱", layout="wide")

rules = load_rules()
sites = load_sites()
catalogue = load_crops()
NAMES = {key: crop.name_pt for key, crop in catalogue.items()}
PRESETS = {"equilibrado": "Equilíbrio entre tudo", "seguranca_alimentar": "Não perder a colheita",
           "recuperar_solo": "Recuperar o solo", "rendimento": "Colher o máximo"}
OBJECTIVES = {"agua": "Água que a chuva cobre", "solo": "Cuidar do solo",
              "resiliencia": "Aguentar anos secos", "rendimento": "Colheita",
              "margem": "Dinheiro", "diversidade": "Variar as culturas"}
SCENARIOS = {
    "historico": "Em todas as campanhas desde 1990",
    "seco": "Só nas campanhas mais secas (1 em cada 3)",
    "favoravel": "Só nas campanhas mais chuvosas (1 em cada 3)",
    "seco_parametrico": "Se chovesse 20% menos",
    "quente": "Se estivesse 2 °C mais quente",
    "ano": "Numa campanha concreta",
}

# --- Escolhas ---------------------------------------------------------------
with st.sidebar:
    st.header("Local")
    site_id = st.selectbox("Zona", list(sites), format_func=lambda key: sites[key].name)
    base_site = sites[site_id]
    if "point" not in st.session_state or st.session_state.get("point_site") != site_id:
        st.session_state["point"] = (base_site.lat, base_site.lon)
        st.session_state["point_site"] = site_id
    st.header("O agricultor")
    current = st.selectbox("O que planta hoje", list(NAMES), format_func=NAMES.get,
                           index=list(NAMES).index(base_site.current_crop))
    accepted = st.multiselect("O que aceita plantar", list(NAMES), default=list(NAMES),
                              format_func=NAMES.get)
    staple = st.checkbox("Quer pelo menos uma campanha de cereal", value=True,
                         help="Milho, mapira ou mexoeira: o alimento de base da família")
    keep_current = st.checkbox(f"Quer manter {NAMES[current].lower()} pelo menos uma vez",
                               value=False)
    preset = st.selectbox("O que é mais importante", list(PRESETS), format_func=PRESETS.get)
    with st.expander("Afinar as prioridades"):
        sliders = {name: st.slider(OBJECTIVES[name], 0.0, 10.0,
                                   float(round(rules["weights"][preset][name] * 20) / 2), 0.5,
                                   key=f"w_{preset}_{name}")
                   for name in INDICATORS}
    with st.expander("Data de sementeira"):
        months = {10: "Outubro", 11: "Novembro", 12: "Dezembro", 1: "Janeiro"}
        sow_month = st.selectbox("Mês", list(months), format_func=months.get,
                                 index=list(months).index(base_site.sow_month))
        sow_day = st.number_input("Dia", 1, 28, min(base_site.sow_day, 28))

lat, lon = st.session_state["point"]
is_demo_point = (lat, lon) == (base_site.lat, base_site.lon)
place = base_site.name if is_demo_point else f"Ponto {lat:.2f}, {lon:.2f}"

st.title(f"{place}: o que plantar nas próximas três campanhas?")
st.caption("Machamba Shift repete mais de 30 campanhas reais, vistas pela NASA, em cada "
           "cultura, e mostra em quantas teria faltado água.")

# --- Mapa: condições reais, antes e agora -------------------------------------
grid = load_grid()
fmap = base_map(sites, (lat, lon))
if grid is None:
    st.caption("Clique no mapa para analisar outro ponto. O mapa de condições da região "
               "aparece depois de correr python scripts/build_grid.py.")
else:
    grid_seasons, grid_now = grid
    normal = normals(grid_seasons)
    layers = {"normal": "Antes: chuva de uma campanha normal",
              "ano": "Antes: como foi uma campanha concreta"}
    if not grid_now.empty:
        label = f"{grid_now['months'].iloc[0]} de {int(grid_now['season'].iloc[0])}"
        layers["agora"] = f"Agora: chuva de {label} face ao normal"
        layers["solo"] = "Agora: humidade do solo"
    left, right = st.columns([2, 1])
    layer = left.radio("O que o mapa mostra", list(layers), format_func=layers.get,
                       horizontal=True)
    if layer == "normal":
        add_cells(fmap, normal, "rain_normal_mm",
                  "Campanha normal: {rain_normal_mm:.0f} mm de chuva<br>"
                  "Campanha má: {rain_bad_mm:.0f} mm · boa: {rain_good_mm:.0f} mm",
                  False, "Chuva de Outubro a Abril numa campanha normal (mm)", 300, 1600)
    elif layer == "ano":
        options = sorted(grid_seasons["season"].unique(), reverse=True)
        picked = right.selectbox("Campanha", options,
                                 format_func=lambda y: f"{y}/{str(y + 1)[-2:]}")
        one = grid_seasons[grid_seasons["season"] == picked].merge(normal, on=["lat", "lon"])
        one["pct"] = 100 * one["rain_mm"] / one["rain_normal_mm"]
        add_cells(fmap, one, "pct",
                  "Choveram {rain_mm:.0f} mm, {pct:.0f}% de uma campanha normal "
                  "({rain_normal_mm:.0f} mm)",
                  True, "Chuva da campanha face ao normal (%)", 40, 160)
    elif layer == "agora":
        now = grid_now.copy()
        now["pct"] = 100 * now["rain_mm"] / now["rain_normal_mm"]
        add_cells(fmap, now, "pct",
                  "Choveram {rain_mm:.0f} mm; o normal nestes meses é {rain_normal_mm:.0f} mm "
                  "({pct:.0f}%)",
                  True, "Chuva destes meses face ao normal (%)", 40, 160)
    else:
        now = grid_now.copy()
        now["wet"] = 100 * now["gwet_latest"]
        add_cells(fmap, now, "wet",
                  "Humidade do solo na zona das raízes: {wet:.0f}% (0 = seco, 100 = saturado)",
                  False, "Humidade do solo na zona das raízes (%)", 0, 100)
    notes = {
        "normal": "Metade das campanhas desde 1990 teve mais chuva do que o valor mostrado.",
        "ano": "Vermelho: choveu menos do que o normal dessa célula. Azul: choveu mais.",
        "agora": "Só conta meses já completos. Isto não é uma previsão: o início da campanha "
                 "não antecipa o resto.",
        "solo": "Valor modelado mais recente do NASA POWER; não é uma medição no terreno.",
    }
    st.caption(notes[layer] + " Cada quadrado tem cerca de 55 por 65 km. Fonte: NASA POWER "
               "(valores modelados). Clique no mapa para analisar outro ponto.")
result_map = st_folium(fmap, height=460, use_container_width=True,
                       returned_objects=["last_clicked"], key="map")
clicked = (result_map or {}).get("last_clicked")
if clicked:
    point = cell_of(clicked["lat"], clicked["lng"])
    if point != st.session_state["point"]:
        st.session_state["point"] = point
        st.rerun()

clim = load_cached_climate(lat, lon)
if clim is None:
    st.info("Ainda não há clima guardado para este ponto.")
    if st.button("Descarregar clima do NASA POWER", type="primary"):
        with st.spinner("A pedir mais de 30 anos de clima diário..."):
            try:
                clim = get_climate(lat, lon)
            except RuntimeError:
                st.error("Nem o NASA POWER nem o Open-Meteo responderam. "
                         "Verifique a ligação e tente de novo.")
    if clim is None:
        st.stop()

# --- 1. O local ---------------------------------------------------------------
table = season_table(clim, rules)
summary = site_summary(table)
source = str(clim["source"].iloc[0])
soil = get_soil(lat, lon, site_id=site_id if is_demo_point else None)

st.header("1. Como é a chuva aqui")
if not source.startswith("NASA"):
    st.warning(f"Clima de fonte alternativa: {source}. O NASA POWER não respondeu.")
cols = st.columns(3)
cols[0].metric("Chuva de uma campanha normal", f"{summary['rain_median_mm']:.0f} mm",
               help="Metade das campanhas (Outubro a Abril) teve mais chuva do que isto e "
                    "metade teve menos. Fonte: NASA POWER, valores modelados para uma zona "
                    "de cerca de 50 km.")
cols[1].metric("Chuva numa campanha má", f"{summary['rain_p10_mm']:.0f} mm",
               help="Uma em cada 10 campanhas teve menos chuva do que isto.")
cols[2].metric("Chuva numa campanha boa", f"{summary['rain_p90_mm']:.0f} mm",
               help="Uma em cada 10 campanhas teve mais chuva do que isto.")
st.plotly_chart(rain_by_season(table), width="stretch")
st.caption(f"Cada barra é uma campanha real, de {summary['first_season']} a "
           f"{summary['last_season'] + 1}. A vermelho, o terço de campanhas com menos chuva.")

done = table[table["complete"]]
rain_trend, temp_trend = trend(done["rain_mm"]), trend(done["tmean_c"])


def describe(change: dict, unit: str, up: str, down: str, digits: int) -> str:
    if not change["significant"]:
        return "sem tendência clara"
    per_decade = 10 * change["slope"]
    direction = up if per_decade > 0 else down
    return f"{direction} cerca de {abs(per_decade):.{digits}f} {unit} por década"


st.markdown(
    f"**O padrão desde {summary['first_season']}.** Chuva das campanhas: "
    f"{describe(rain_trend, 'mm', 'a subir', 'a descer', 0)}. Temperatura: "
    f"{describe(temp_trend, '°C', 'a subir', 'a descer', 2)}. "
    f"Entre uma campanha má e uma boa a chuva varia de {summary['rain_p10_mm']:.0f} a "
    f"{summary['rain_p90_mm']:.0f} mm: é esse leque que qualquer plano tem de aguentar.",
    help="Tendência pelo teste de Mann-Kendall (5%) e declive de Sen. 'Sem tendência clara' "
         "quer dizer que a variação entre anos é maior do que qualquer mudança gradual.")

# --- Motor ----------------------------------------------------------------------
st.header("2. Que culturas aguentam melhor este clima")
choice = st.selectbox("Ver o que teria acontecido", list(SCENARIOS), format_func=SCENARIOS.get)
scenario = choice
if choice == "ano":
    years = complete_seasons(table)
    year = st.selectbox("Campanha", years[::-1], format_func=lambda y: f"{y}/{str(y + 1)[-2:]}")
    scenario = f"ano:{year}"

site = replace(base_site, lat=lat, lon=lon, sow_month=int(sow_month), sow_day=int(sow_day),
               current_crop=current, name=place)
constraints = Constraints(required={current} if keep_current and current in accepted else set(),
                          require_staple=staple)
try:
    result = recommend(site, clim, soil, accepted, sliders, rules, scenario=scenario,
                       constraints=constraints, current_crop=current, catalogue=catalogue,
                       economics=load_economics())
except ValueError as error:
    st.error(str(error))
    st.stop()

stats = result.crop_stats
safest = min(stats, key=lambda key: (stats[key]["p_stress"], stats[key]["p_failure"]))
today = stats[current]
st.markdown(
    f"Em **{result.seasons} campanhas**, {NAMES[current].lower()} teve água suficiente em "
    f"**{10 * (1 - today['p_stress']):.0f} de cada 10** e falhou gravemente em "
    f"**{10 * today['p_failure']:.0f} de cada 10**. A cultura que menos sofreu foi "
    f"**{NAMES[safest].lower()}**, com água suficiente em "
    f"{10 * (1 - stats[safest]['p_stress']):.0f} de cada 10.")
often, spread = st.tabs(["Quantas vezes correu bem", "Do pior ao melhor ano"])
with often:
    st.plotly_chart(crop_risk(stats, NAMES), width="stretch")
    st.caption("Água suficiente: a chuva cobriu pelo menos 80% do que a cultura precisava. "
               "Falha grave: cobriu menos de metade.")
with spread:
    st.plotly_chart(crop_range(stats, NAMES), width="stretch")
    st.caption("O leque de possibilidades de cada cultura: quanto da água de que precisa a "
               "chuva cobriu numa campanha má, numa normal e numa boa. Quanto mais curta a "
               "barra e mais à direita, mais segura é a cultura.")
st.caption(f"Simulado pelo Machamba Shift com o clima {source}; são estimativas para comparar "
           "culturas, não previsões de colheita.")

# --- 3. O plano -----------------------------------------------------------------
best = result.strategy("recomendada")
mono = result.strategy("monocultura")


def share_ok(item) -> float:
    return 1 - sum(item.raw["p_stress"]) / len(item.raw["p_stress"])


st.header("3. Plano para três campanhas")
st.subheader(" → ".join(best.raw["names"]))
st.markdown(
    "**O que esta recomendação quer dizer:** se as próximas campanhas forem como as "
    f"{result.seasons} analisadas, este é o plano que mais vezes se sai bem. Ninguém sabe se "
    "o próximo ano será seco ou chuvoso; o plano é escolhido para aguentar os dois.")
equivalent = [" → ".join(row["names"]) for row in result.ranking[1:]
              if row["score"] >= best.score - 0.005][:3]
if equivalent:
    st.markdown("Praticamente tão boas: " + "; ".join(equivalent) + ".")
cols = st.columns(3)
cols[0].metric("Campanhas com água suficiente", f"{10 * share_ok(best):.0f} de cada 10",
               f"{10 * (share_ok(best) - share_ok(mono)):+.1f} face a só {NAMES[current].lower()}",
               help="Média das três culturas do plano. Conta as campanhas em que a chuva "
                    "cobriu pelo menos 80% da água de que a cultura precisava.")
cols[1].metric("Colheita face ao máximo possível",
               f"{100 * sum(best.raw['y_rel']) / 3:.0f}%",
               f"{100 * (sum(best.raw['y_rel']) - sum(mono.raw['y_rel'])) / 3:+.0f} pontos",
               help="Quanto do rendimento máximo se espera numa campanha normal, contando só "
                    "a falta de água e o efeito de plantar um cereal depois de uma leguminosa.")
cols[2].metric("Culturas que repõem azoto", f"{len(best.raw['legumes'])} de 3",
               f"{len(best.raw['legumes']) - len(mono.raw['legumes']):+d}",
               help="As leguminosas vão buscar ao ar parte do azoto de que precisam, em vez "
                    "de o retirar todo do solo. Valores de literatura.")

st.markdown("**Porquê este plano**")
for line in result.explanation:
    st.markdown(f"- {line}")

with st.expander("Comparar com as alternativas"):
    st.plotly_chart(indicators_by_strategy(result.strategies), width="stretch")
    st.dataframe(pd.DataFrame([
        {
            "Estratégia": STRATEGY_STYLE[item.label][0],
            "Plano": " → ".join(item.raw["names"]),
            "Água suficiente": round(10 * share_ok(item), 1),
            "Falha grave": round(10 * sum(item.raw["p_failure"]) / 3, 1),
            "Colheita": round(100 * sum(item.raw["y_rel"]) / 3),
            "Repõem azoto": len(item.raw["legumes"]),
            "Nota global": round(item.score, 2),
        }
        for item in result.strategies]), hide_index=True, width="stretch", column_config={
            "Estratégia": st.column_config.TextColumn(help=(
                "Monocultura: a cultura de hoje, repetida. Convencional: alternada com outro "
                "cereal. Com leguminosa: alternada com uma leguminosa. Recomendada: a de "
                "melhor nota global.")),
            "Água suficiente": st.column_config.NumberColumn(format="%.1f em 10", help=(
                "Em quantas de cada 10 campanhas a chuva cobriu pelo menos 80% da água de "
                "que as culturas precisavam. Mais é melhor.")),
            "Falha grave": st.column_config.NumberColumn(format="%.1f em 10", help=(
                "Em quantas de cada 10 campanhas a chuva cobriu menos de metade da água "
                "necessária. Menos é melhor.")),
            "Colheita": st.column_config.NumberColumn(format="%d%%", help=(
                "Colheita esperada numa campanha normal, em percentagem do máximo possível. "
                "Conta só a falta de água e o efeito de um cereal depois de uma leguminosa.")),
            "Repõem azoto": st.column_config.NumberColumn(format="%d de 3", help=(
                "Quantas das três culturas são leguminosas, que vão buscar azoto ao ar.")),
            "Nota global": st.column_config.NumberColumn(format="%.2f", help=(
                "De 0 a 1. Média dos objectivos (água, solo, anos secos, colheita, variedade) "
                "pesada pelas prioridades escolhidas à esquerda. Serve para ordenar os planos; "
                "diferenças abaixo de 0,01 não são significativas.")),
        })

with st.expander("O que esta ferramenta não sabe"):
    for flag in result.flags:
        st.markdown(f"- {flag}")
    st.markdown("- Não prevê como vai ser a próxima campanha: mostra o que aconteceu nas "
                "campanhas passadas.")
    st.markdown("- Caracteriza a zona (cerca de 50 km), não o talhão. Não substitui a análise "
                "de solo nem o conhecimento do extensionista.")
    st.caption("Mais pormenores na página Posso confiar.")
