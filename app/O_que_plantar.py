"""Página principal: mapa e tempo, condições recentes, histórico, culturas, plano, perguntas.

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
    monthly_rain,
    monthly_temperature,
    rain_by_season,
    temperature_by_season,
)
from app.components.hover import hover_chart  # noqa: E402
from app.components.maps import add_cells, base_map, draw_map, local_map  # noqa: E402
from app.components.report import build_pdf, build_report  # noqa: E402
from data.climate import (  # noqa: E402
    get_climate,
    get_recent,
    load_cached_climate,
    recent_summary,
)
from data.features import (  # noqa: E402
    MONTHS_PT,
    complete_seasons,
    monthly_table,
    monthly_view,
    season_table,
    site_summary,
    trend,
)
from data.grid import cell_of, load_grid, normals  # noqa: E402
from data.region import polygon_from_geojson, region_summary  # noqa: E402
from data.scenarios import apply_scenario  # noqa: E402
from data.soil import get_soil  # noqa: E402
from engine.params import (  # noqa: E402
    load_crops,
    load_economics,
    load_engine_defaults,
    load_rules,
    load_sites,
)
from engine.rotation import recommend  # noqa: E402
from engine.rules import Constraints  # noqa: E402
from engine.schemas import INDICATORS  # noqa: E402
from engine.water_balance import sowing_window  # noqa: E402

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
    "historico": "Todas as campanhas desde 1990",
    "seco": "Só as mais secas (1 em cada 3)",
    "favoravel": "Só as mais chuvosas (1 em cada 3)",
    "seco_parametrico": "Se chovesse 20% menos",
    "quente": "Se estivesse 2 °C mais quente",
    "ano": "Uma campanha concreta",
}

# --- Escolhas (barra lateral) -------------------------------------------------
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

# --- Cabeçalho e navegação ----------------------------------------------------
NAV = [("mapa", "Mapa & Tempo"), ("condicoes", "Solo, Ar & Vento"),
       ("historico", "Histórico NASA"), ("culturas", "Culturas"), ("plano", "Plano"),
       ("perguntas", "Perguntas")]
st.html("""<style>
.ms-nav{display:flex;align-items:center;gap:8px;padding:10px 18px;background:#fff;
  border:1px solid #e2e8f0;border-radius:16px;box-shadow:0 4px 18px rgba(15,23,42,.07)}
.ms-brand{font-weight:800;font-size:1.15rem;color:#0f172a;letter-spacing:-.02em;
  margin-right:auto;white-space:nowrap}
.ms-brand i{font-style:normal;color:#2E7D32}
.ms-links{display:flex;flex-wrap:nowrap;gap:0;overflow-x:auto;scrollbar-width:none}
.ms-nav a{text-decoration:none!important;font-weight:600;font-size:.88rem;color:#475569!important;
  padding:6px 10px;border-radius:999px;transition:background .15s,color .15s;white-space:nowrap}
.ms-nav a:hover{background:#f1f5f9;color:#0f172a!important}
.ms-nav a.ms-cta{background:#0f766e;color:#fff!important;margin-left:auto;padding:8px 16px;
  border-radius:10px}
.ms-nav a.ms-cta:hover{background:#115e59;color:#fff!important}
div[data-testid="stElementContainer"]:has(.ms-nav),div.element-container:has(.ms-nav){
  position:sticky;top:3.6rem;z-index:99}
h2{scroll-margin-top:8rem}
div[data-testid="stMainBlockContainer"]{padding:3.5rem 2.5rem 4rem}
div[data-testid="stMetricValue"]{font-size:1.65rem}
</style>""")
links = "".join(f'<a href="#{anchor}" target="_self">{label}</a>' for anchor, label in NAV)
st.markdown(f'<div class="ms-nav"><span class="ms-brand">Machamba<i> Shift</i></span>'
            f'<span class="ms-links">{links}</span>'
            f'<a class="ms-cta" href="#relatorio" target="_self">Gerar relatório</a></div>',
            unsafe_allow_html=True)
st.title(place)


def section(number: int, code: str, title: str, anchor: str, help: str) -> None:
    """Cabeçalho de secção com âncora para a barra de navegação."""
    st.header(title, anchor=anchor, help=help)


clim = load_cached_climate(lat, lon)
recent_frame = get_recent(lat, lon)
recent = recent_summary(recent_frame) if recent_frame is not None else None

# --- Mapa e tempo ---------------------------------------------------------------
section(1, "Geo_espacial", "Mapa e tempo", "mapa",
        help="Vista local: imagem de satélite e as condições dos últimos dias na zona. "
               "Vista regional: chuva por zona, antes e agora. Clique no mapa para analisar "
               "outro ponto. Fonte: NASA POWER (valores modelados, zonas de 55 por 65 km).")
grid = load_grid()
views = {"local": "Aqui (satélite)"}
if grid is not None:
    grid_seasons, grid_now = grid
    views["normal"] = "Região: campanha normal"
    views["ano"] = "Região: uma campanha"
    if not grid_now.empty:
        views["agora"] = (f"Região: {grid_now['months'].iloc[0]} de "
                          f"{int(grid_now['season'].iloc[0])}")
        views["solo"] = "Região: humidade do solo"
    views["desenhar"] = "Desenhar região"
left, right = st.columns([3, 1])
view = left.radio("Vista", list(views), format_func=views.get, horizontal=True,
                  label_visibility="collapsed")

if view == "local":
    chips = []
    if recent:
        chips = [
            (0.17, 0.0, f"🌡 {recent['tmax_c']:.1f} °C máx · {recent['hot_days']} d calor",
             "Temperatura máxima média dos últimos 7 dias; dias com 35 °C ou mais"),
            (-0.17, 0.0, f"🌧 {recent['rain_30d_mm']:.0f} mm em 30 dias",
             "Chuva acumulada nos últimos 30 dias com dados"),
            (0.0, -0.33, f"☀ ET₀ {recent['et0_mm']:.1f} mm/d",
             "Água que a atmosfera pede por dia (evapotranspiração de referência)"),
        ]
        if recent["wind_kmh"] is not None:
            chips.append((0.0, 0.33, f"💨 {recent['wind_kmh']:.0f} km/h",
                          "Vento médio a 2 m de altura, últimos 7 dias"))
        if recent["soil_root"] is not None:
            chips.append((-0.09, -0.3, f"🌱 solo {100 * recent['soil_root']:.0f}%",
                          "Humidade do solo na zona das raízes (0 = seco, 100 = saturado)"))
    fmap = local_map(sites, (lat, lon), cell_of(lat, lon), chips)
elif view == "desenhar":
    polygon = st.session_state.get("region")
    area = region_summary(polygon, grid_seasons, grid_now) if polygon else None
    fmap = draw_map((lat, lon), polygon, area["cell_list"] if area else None)
else:
    fmap = base_map(sites, (lat, lon))
    normal = normals(grid_seasons)
    if view == "normal":
        add_cells(fmap, normal, "rain_normal_mm",
                  "Campanha normal: {rain_normal_mm:.0f} mm de chuva<br>"
                  "Campanha má: {rain_bad_mm:.0f} mm · boa: {rain_good_mm:.0f} mm",
                  False, "Chuva de Outubro a Abril numa campanha normal (mm)", 300, 1400,
                  sites=sites, point=(lat, lon))
    elif view == "ano":
        options = sorted(grid_seasons["season"].unique(), reverse=True)
        picked = right.selectbox("Campanha", options, label_visibility="collapsed",
                                 format_func=lambda y: f"Campanha {y}/{str(y + 1)[-2:]}")
        one = grid_seasons[grid_seasons["season"] == picked].merge(normal, on=["lat", "lon"])
        one["pct"] = 100 * one["rain_mm"] / one["rain_normal_mm"]
        add_cells(fmap, one, "pct",
                  "Choveram {rain_mm:.0f} mm, {pct:.0f}% de uma campanha normal "
                  "({rain_normal_mm:.0f} mm)",
                  True, "Chuva da campanha face ao normal (%)", 40, 160,
                  sites=sites, point=(lat, lon))
    elif view == "agora":
        now = grid_now.copy()
        now["pct"] = 100 * now["rain_mm"] / now["rain_normal_mm"]
        add_cells(fmap, now, "pct",
                  "Choveram {rain_mm:.0f} mm; o normal nestes meses é {rain_normal_mm:.0f} mm "
                  "({pct:.0f}%)",
                  True, "Chuva destes meses face ao normal (%)", 40, 160,
                  sites=sites, point=(lat, lon))
    else:
        now = grid_now.copy()
        now["wet"] = 100 * now["gwet_latest"]
        add_cells(fmap, now, "wet",
                  "Humidade do solo na zona das raízes: {wet:.0f}% (0 = seco, 100 = saturado)",
                  False, "Humidade do solo na zona das raízes (%)", 0, 100,
                  sites=sites, point=(lat, lon))
drawing = view == "desenhar"
result_map = st_folium(fmap, height=520, use_container_width=True,
                       returned_objects=["last_active_drawing"] if drawing else ["last_clicked"],
                       key=f"map_{view}")
if drawing:
    drawn = polygon_from_geojson((result_map or {}).get("last_active_drawing"))
    if drawn and drawn != st.session_state.get("region"):
        st.session_state["region"] = drawn
        st.rerun()
    if polygon is None:
        st.caption("Use o botão de polígono no canto do mapa: clique em cada vértice e feche "
                   "no primeiro ponto.")
    elif area is None:
        st.warning("A região desenhada não tem zonas com dados (mar ou fora de Moçambique).")
    else:
        cols = st.columns(5)
        cols[0].metric("Área", f"{area['area_km2']:,.0f} km²".replace(",", " "),
                       help="Área aproximada do polígono desenhado.")
        cols[1].metric("Zonas NASA", f"{area['cells']}",
                       help="Zonas do NASA POWER (55 por 65 km) cujo centro está na região. "
                            "Os números são a média dessas zonas.")
        cols[2].metric("Campanha normal", f"{area['rain_normal_mm']:.0f} mm",
                       help=f"Chuva de Outubro a Abril, média da região. Entre zonas vai de "
                            f"{area['cell_min_mm']:.0f} a {area['cell_max_mm']:.0f} mm.")
        cols[3].metric("Campanha má", f"{area['rain_bad_mm']:.0f} mm",
                       help="Uma em cada 10 campanhas teve menos chuva do que isto.")
        cols[4].metric("Chuva agora", "—" if area["now_pct"] is None
                       else f"{area['now_pct']:.0f}%",
                       help=f"Chuva de {area['now_months'] or 'meses recentes'} face ao normal "
                            "desses meses, média da região.")
        if area["fallback"]:
            st.caption("A região é mais pequena do que uma zona do NASA POWER: os valores são "
                       "os da zona que a contém.")
        st.markdown("**Chuva média da região em cada campanha**")
        hover_chart(rain_by_season(area["series"]), "cool")

        def use_centre() -> None:
            st.session_state["point"] = tuple(round(value, 4) for value in area["centroid"])

        def clear_region() -> None:
            st.session_state.pop("region", None)

        left, right, _ = st.columns([2, 1, 2])
        left.button("Analisar culturas e plano no centro da região", on_click=use_centre,
                    type="primary", width="stretch",
                    help="As culturas e o plano precisam de clima diário, que é pedido para "
                         "um ponto: o centro da região.")
        right.button("Limpar região", on_click=clear_region, width="stretch")
clicked = None if drawing else (result_map or {}).get("last_clicked")
if clicked:
    point = (round(clicked["lat"], 4), round(clicked["lng"], 4))
    if point != st.session_state["point"]:
        st.session_state["point"] = point
        st.rerun()

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

# --- Solo, ar e vento -------------------------------------------------------------
section(2, "Telemetria", "Solo, ar e vento", "condicoes",
        help="Condições dos últimos dias na zona, pelo NASA POWER. São valores modelados "
               "para uma área de cerca de 50 km, não medições no terreno. O POWER publica com "
               "cerca de três dias de atraso.")
if recent is None:
    st.info("Sem condições recentes: o NASA POWER não respondeu.")
else:
    def pct(value):
        return "—" if value is None else f"{100 * value:.0f}%"

    cols = st.columns(6)
    cols[0].metric("Chuva, 30 dias", f"{recent['rain_30d_mm']:.0f} mm",
                   help="Chuva acumulada nos últimos 30 dias com dados.")
    cols[1].metric("Solo, raízes", pct(recent["soil_root"]),
                   help="Humidade do solo até 1 m de profundidade. 0% = seco, 100% = saturado.")
    cols[2].metric("Solo, superfície", pct(recent["soil_top"]),
                   help="Humidade dos primeiros 5 cm do solo: o que a semente encontra.")
    cols[3].metric("Temperatura", f"{recent['tmax_c']:.0f}° / {recent['tmin_c']:.0f}°",
                   help="Máxima e mínima médias dos últimos 7 dias.")
    cols[4].metric("Vento", "—" if recent["wind_kmh"] is None
                   else f"{recent['wind_kmh']:.0f} km/h",
                   help="Vento médio a 2 m de altura, últimos 7 dias.")
    cols[5].metric("Sede do ar", f"{recent['et0_mm']:.1f} mm/d",
                   help="Evapotranspiração de referência: a água que a atmosfera retira por "
                        "dia a uma cultura bem regada. Quanto mais alta, mais depressa o solo "
                        "seca.")
    st.caption(f"Até {recent['last_date']} · NASA POWER")

# --- Histórico NASA ----------------------------------------------------------------
table = season_table(clim, rules)
summary = site_summary(table)
source = str(clim["source"].iloc[0])
soil = get_soil(lat, lon, site_id=site_id if is_demo_point else None)
done = table[table["complete"]]
rain_trend, temp_trend = trend(done["rain_mm"]), trend(done["tmean_c"])


def describe(change: dict, unit: str, digits: int) -> str:
    if not change["significant"]:
        return "estável"
    return f"{10 * change['slope']:+.{digits}f} {unit}/déc."


section(3, "Arquivo", "Histórico NASA", "historico",
        help="Cada ponto é uma campanha real (Outubro a Abril) desde 1990. Tendência pelo "
               "teste de Mann-Kendall: 'sem tendência clara' quer dizer que a variação entre "
               "anos é maior do que qualquer mudança gradual.")
if not source.startswith("NASA"):
    st.warning(f"Clima de fonte alternativa: {source}. O NASA POWER não respondeu.")
cols = st.columns(5)
cols[0].metric("Campanha normal", f"{summary['rain_median_mm']:.0f} mm",
               help="Metade das campanhas teve mais chuva do que isto e metade teve menos.")
cols[1].metric("Campanha má", f"{summary['rain_p10_mm']:.0f} mm",
               help="Uma em cada 10 campanhas teve menos chuva do que isto.")
cols[2].metric("Campanha boa", f"{summary['rain_p90_mm']:.0f} mm",
               help="Uma em cada 10 campanhas teve mais chuva do que isto.")
cols[3].metric("Tendência da chuva", describe(rain_trend, "mm", 0),
               help="Tendência da chuva das campanhas desde 1990, por década. 'Estável' quer "
                    "dizer sem tendência clara: a variação entre anos é maior do que qualquer "
                    "mudança gradual.")
cols[4].metric("Tendência do calor", describe(temp_trend, "°C", 2),
               help="Tendência da temperatura média das campanhas desde 1990, por década. "
                    "'Estável' quer dizer sem tendência clara.")
by_season, by_month = st.tabs(["Por campanha", "Por ano e por meses"])
with by_season:
    left, right = st.columns(2)
    with left:
        st.markdown("**Chuva de cada campanha**")
        hover_chart(rain_by_season(table), "cool")
    with right:
        st.markdown("**Temperatura de cada campanha**")
        hover_chart(temperature_by_season(table), "warm")
with by_month:
    months_all = monthly_table(clim)
    years_all = sorted(months_all["year"].unique())
    whole = f"{years_all[0]}–{years_all[-1]}"
    presets = {"12 meses": list(range(1, 13)), "Chuvosos": [10, 11, 12, 1, 2, 3],
               "Secos": [4, 5, 6, 7, 8, 9]}
    hints = {"12 meses": "Todos os meses", "Chuvosos": "Outubro a Março",
             "Secos": "Abril a Setembro"}
    if "months" not in st.session_state:
        st.session_state["months"] = presets["12 meses"]

    def pick_months(chosen: list[int]) -> None:
        st.session_state["months"] = chosen

    left, right = st.columns([3, 2])
    period = left.pills("Período", [whole, *[int(year) for year in years_all[::-1][:7]]],
                        default=whole, label_visibility="collapsed") or whole
    for column, (label, chosen) in zip(right.columns(3), presets.items(), strict=True):
        column.button(label, on_click=pick_months, args=(chosen,), width="stretch",
                      help=hints[label])
    picked = st.pills("Meses", list(range(1, 13)), selection_mode="multi", key="months",
                      format_func=lambda month: MONTHS_PT[month - 1],
                      label_visibility="collapsed")
    year = None if period == whole else int(period)
    view = monthly_view(months_all, year)
    view = view[view["month"].isin(picked)]
    if view.empty:
        st.info("Sem meses completos para esta escolha.")
    else:
        name = f"média {whole}" if year is None else str(year)
        left, right = st.columns(2)
        with left:
            st.markdown("**Temperatura por mês**")
            hover_chart(monthly_temperature(view, name), "warm")
        with right:
            st.markdown("**Chuva por mês**")
            hover_chart(monthly_rain(view, name, compare=year is not None), "cool")

# --- Motor ---------------------------------------------------------------------------
section(4, "Risco", "Culturas", "culturas",
        help="Para cada cultura, o Machamba Shift repete todas as campanhas reais e conta "
               "em quantas a chuva chegou. Água suficiente: cobriu pelo menos 80% do que a "
               "cultura precisava. Falha grave: cobriu menos de metade. São estimativas para "
               "comparar culturas, não previsões de colheita.")
left, right = st.columns([2, 1])
choice = left.selectbox("Campanhas a considerar", list(SCENARIOS), format_func=SCENARIOS.get)
scenario = choice
if choice == "ano":
    years = complete_seasons(table)
    year = right.selectbox("Campanha", years[::-1],
                           format_func=lambda y: f"{y}/{str(y + 1)[-2:]}")
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
today_crop = stats[current]
window = sowing_window(apply_scenario(clim, scenario, rules, lat), catalogue[current], soil,
                       site, rules, load_engine_defaults())
best_date = min(window, key=lambda key: (window[key]["p_stress"], window[key]["p_failure"]))

st.markdown(
    f"Em {result.seasons} campanhas, **{NAMES[current].lower()}** teve água suficiente em "
    f"**{10 * (1 - today_crop['p_stress']):.0f} de cada 10**. A que menos sofreu: "
    f"**{NAMES[safest].lower()}**, {10 * (1 - stats[safest]['p_stress']):.0f} de cada 10.")
often, spread, when = st.tabs(["Quantas vezes correu bem", "Do pior ao melhor ano",
                               f"Quando semear {NAMES[current].lower()}"])
with often:
    hover_chart(crop_risk(stats, NAMES), "green")
with spread:
    hover_chart(crop_range(stats, NAMES), "green")
with when:
    hover_chart(crop_risk(window, {key: f"Semear a {key}" for key in window},
                          keep_order=True), "green")

# --- Plano -----------------------------------------------------------------------------
best = result.strategy("recomendada")
mono = result.strategy("monocultura")


def share_ok(item) -> float:
    return 1 - sum(item.raw["p_stress"]) / len(item.raw["p_stress"])


section(5, "Rotação", "Plano para três campanhas", "plano",
        help=f"Se as próximas campanhas forem como as {result.seasons} analisadas, este é o "
               "plano que mais vezes se sai bem. Não é uma previsão: ninguém sabe se o próximo "
               "ano será seco ou chuvoso; o plano é escolhido para aguentar os dois.")
st.subheader(" → ".join(best.raw["names"]))
equivalent = [" → ".join(row["names"]) for row in result.ranking[1:]
              if row["score"] >= best.score - 0.005][:3]
if equivalent:
    st.caption("Praticamente tão boas: " + "; ".join(equivalent))
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
for line in result.explanation:
    st.markdown(f"- {line}")

with st.expander("Comparar com as alternativas"):
    hover_chart(indicators_by_strategy(result.strategies), "green")
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

# --- Perguntas ---------------------------------------------------------------------------
section(6, "Consulta", "Perguntas", "perguntas",
        help="Respostas calculadas a partir dos mesmos dados desta página. Não há modelo de "
               "linguagem: nenhuma resposta inventa números.")
crop0 = NAMES[current].lower()
QUESTIONS = {
    "mono": f"Porque não plantar só {crop0}?",
    "seguro": "Qual é a cultura mais segura aqui?",
    "quando": f"Quando devo semear {crop0}?",
    "seco": "E se o próximo ano for seco?",
    "previsao": "Isto é uma previsão?",
}
question = st.selectbox("Escolha uma pergunta", list(QUESTIONS), format_func=QUESTIONS.get,
                        label_visibility="collapsed")
if question == "mono":
    answer = (f"Porque, nas {result.seasons} campanhas analisadas, três anos de {crop0} tiveram "
              f"água suficiente em {10 * share_ok(mono):.1f} de cada 10 campanhas e renderam "
              f"{100 * sum(mono.raw['y_rel']) / 3:.0f}% do máximo. O plano "
              f"{' → '.join(best.raw['names']).lower()} teve {10 * share_ok(best):.1f} de cada "
              f"10 e {100 * sum(best.raw['y_rel']) / 3:.0f}%, e inclui "
              f"{len(best.raw['legumes'])} cultura(s) que repõem azoto no solo.")
elif question == "seguro":
    order = sorted(stats, key=lambda key: (stats[key]["p_stress"], stats[key]["p_failure"]))[:3]
    answer = "As três que menos sofreram com falta de água: " + "; ".join(
        f"{NAMES[key].lower()} ({10 * (1 - stats[key]['p_stress']):.0f} de cada 10 campanhas "
        f"com água suficiente, falha grave em {10 * stats[key]['p_failure']:.0f})"
        for key in order) + "."
elif question == "quando":
    answer = (f"Das datas testadas, {best_date} foi a que mais vezes correu bem: água "
              f"suficiente em {10 * (1 - window[best_date]['p_stress']):.0f} de cada 10 "
              f"campanhas. Veja todas as datas no separador \"Quando semear\". É uma regra "
              f"tirada do passado: num ano concreto, semeia-se depois de as chuvas pegarem.")
elif question == "seco":
    dry = recommend(site, clim, soil, accepted, sliders, rules, scenario="seco",
                    constraints=constraints, current_crop=current, catalogue=catalogue,
                    economics=load_economics())
    dry_best, dry_mono = dry.strategy("recomendada"), dry.strategy("monocultura")
    answer = (f"Nas {dry.seasons} campanhas mais secas, {crop0} todos os anos rendeu "
              f"{100 * sum(dry_mono.raw['y_rel']) / 3:.0f}% do máximo e falhou gravemente em "
              f"{10 * sum(dry_mono.raw['p_failure']) / 3:.1f} de cada 10. O melhor plano para "
              f"esses anos seria {' → '.join(dry_best.raw['names']).lower()}, com "
              f"{100 * sum(dry_best.raw['y_rel']) / 3:.0f}% e falha em "
              f"{10 * sum(dry_best.raw['p_failure']) / 3:.1f} de cada 10. Todos os planos "
              f"pioram num ano seco; uns pioram menos.")
else:
    answer = ("Não. A ferramenta mostra o que aconteceu a cada cultura nas campanhas reais "
              "desde 1990 e escolhe o plano que mais vezes se saiu bem. Testámos se o início "
              "da campanha permitia antecipar o resto e não permite: a relação é nula nos "
              "locais analisados.")
st.info(answer)

# --- Relatório ----------------------------------------------------------------------------
section(7, "Exportar", "Relatório", "relatorio",
        help="Uma página com o plano, o risco de cada cultura, as datas de sementeira e os "
               "limites, para imprimir ou enviar. Abre em qualquer navegador.")
args = (place, lat, lon, summary, result, NAMES, recent, window, current, source)
stem = f"machamba-shift-{place.lower().replace(' ', '-')}"
left, right, _ = st.columns([1, 1, 2])
left.download_button("Relatório em PDF", build_pdf(*args), file_name=f"{stem}.pdf",
                     mime="application/pdf", type="primary", width="stretch")
right.download_button("Relatório em HTML", build_report(*args), file_name=f"{stem}.html",
                      mime="text/html", width="stretch")
