"""Página inicial: mapa, escolha do local, ficha de clima e de solo, catálogo de culturas.

Correr na raiz do repositório:  streamlit run app/Home.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import folium  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402
from streamlit_folium import st_folium  # noqa: E402

from app.components.charts import rain_by_season  # noqa: E402
from app.components.labels import origin_label  # noqa: E402
from data.clients import power  # noqa: E402
from data.climate import get_climate, load_cached_climate, snap  # noqa: E402
from data.features import season_table, site_summary  # noqa: E402
from data.soil import get_soil  # noqa: E402
from data.validate import quality_report  # noqa: E402
from engine.params import load_crops, load_rules, load_sites  # noqa: E402

st.set_page_config(page_title="Machamba Shift", page_icon="🌱", layout="wide")

sites = load_sites()
crops = load_crops()
rules = load_rules()

st.title("Machamba Shift")
st.caption("Que rotação de culturas aguenta melhor as próximas três campanhas nesta machamba?")

# --- Escolha do local -------------------------------------------------------
with st.sidebar:
    st.header("Local")
    site_id = st.selectbox("Local de demonstração", list(sites),
                           format_func=lambda key: sites[key].name)
    site = sites[site_id]
    st.write(f"{site.province} · {site.lat:.2f}, {site.lon:.2f}")
    st.write(f"Sementeira assumida: {site.sow_day:02d}/{site.sow_month:02d}")
    if site.note:
        st.caption(site.note)

if "point" not in st.session_state or st.session_state.get("point_site") != site_id:
    st.session_state["point"] = (site.lat, site.lon)
    st.session_state["point_site"] = site_id

left, right = st.columns([3, 2])

with left:
    st.subheader("Mapa")
    lat, lon = st.session_state["point"]
    fmap = folium.Map(location=[-18.7, 35.5], zoom_start=5, tiles="OpenStreetMap")
    for item in sites.values():
        folium.Marker([item.lat, item.lon], tooltip=item.name).add_to(fmap)
    folium.CircleMarker([lat, lon], radius=8, color="#2E7D32", fill=True,
                        tooltip="Ponto seleccionado").add_to(fmap)
    result = st_folium(fmap, height=420, use_container_width=True,
                       returned_objects=["last_clicked"], key="map")
    clicked = (result or {}).get("last_clicked")
    if clicked:
        point = (round(clicked["lat"], 4), round(clicked["lng"], 4))
        if point != st.session_state["point"]:
            st.session_state["point"] = point
            st.rerun()

lat, lon = st.session_state["point"]
is_demo_point = (lat, lon) == (site.lat, site.lon)
clim = load_cached_climate(lat, lon)

with right:
    st.subheader("Ponto seleccionado")
    st.write(f"**{site.name if is_demo_point else 'Ponto escolhido no mapa'}** · "
             f"{lat:.4f}, {lon:.4f}")
    cell_lat, cell_lon = snap(lat, lon)
    st.caption(f"Clima pedido para {cell_lat:.2f}, {cell_lon:.2f}. A célula do NASA POWER "
               "tem cerca de 50 km: caracteriza a zona, não o talhão.")

    if clim is None:
        st.info("Ainda não há clima guardado para este ponto.")
        if st.button("Descarregar clima do NASA POWER", type="primary"):
            with st.spinner("A pedir mais de 30 anos de clima diário..."):
                try:
                    clim = get_climate(lat, lon)
                except RuntimeError:
                    st.error("Nem o NASA POWER nem o Open-Meteo responderam. "
                             "Verifique a ligação e tente de novo.")

    soil = get_soil(lat, lon, site_id=site_id if is_demo_point else None)
    st.markdown("**Solo**")
    soil_cols = st.columns(3)
    soil_cols[0].metric("Textura", (soil.texture or "—").replace("_", " "))
    soil_cols[1].metric("Água útil (mm/m)", f"{soil.taw_mm_per_m:.0f}",
                        help="Água disponível total por metro de solo")
    soil_cols[2].metric("pH", f"{soil.ph:.1f}" if soil.ph is not None else "—")
    if soil.source.startswith("Solo por defeito"):
        st.caption(origin_label("hipotese", "solo franco por defeito")
                   + ". A API do SoilGrids está suspensa; ver data/demo/soil_TEMPLATE.json.")
    else:
        st.caption(origin_label("modelado", soil.source))

# --- Ficha climática --------------------------------------------------------
if clim is not None:
    table = season_table(clim, rules)
    summary = site_summary(table)
    source = str(clim["source"].iloc[0])

    st.subheader("Clima da campanha (Outubro a Abril)")
    if source != power.SOURCE:
        st.warning(f"Clima de fonte alternativa: {source}. O NASA POWER não respondeu.")

    cols = st.columns(3)
    cols[0].metric("Chuva mediana", f"{summary['rain_median_mm']:.0f} mm")
    cols[1].metric("Ano seco (percentil 10)", f"{summary['rain_p10_mm']:.0f} mm")
    cols[2].metric("Ano chuvoso (percentil 90)", f"{summary['rain_p90_mm']:.0f} mm")
    cols = st.columns(3)
    cols[0].metric("ET0 mediana", f"{summary['et0_median_mm']:.0f} mm",
                   help="Evapotranspiração de referência (Hargreaves) somada na campanha")
    cols[1].metric("Temperatura média", f"{summary['tmean_c']:.1f} °C")
    cols[2].metric("Época de crescimento", f"{summary['season_length_median_days']:.0f} dias",
                   help="Mediana da maior sequência de dias com chuva ≥ 0,5 × ET0 "
                        "(médias móveis de 30 dias)")

    st.plotly_chart(rain_by_season(table), width="stretch")
    st.caption(
        f"{summary['seasons']} campanhas completas, de {summary['first_season']}/"
        f"{str(summary['first_season'] + 1)[-2:]} a {summary['last_season']}/"
        f"{str(summary['last_season'] + 1)[-2:]}. "
        + origin_label("modelado", f"{source}, reanálise") + ". ET0 e época de crescimento: "
        + origin_label("simulado").lower() + ".")

    with st.expander("Campanhas em tabela"):
        shown = table[table["complete"]].rename(columns={
            "label": "Campanha", "rain_mm": "Chuva (mm)", "et0_mm": "ET0 (mm)",
            "tmax_c": "Tmax média (°C)", "tmin_c": "Tmin média (°C)",
            "season_length_days": "Época (dias)", "tercile": "Classe"})
        st.dataframe(
            shown[["Campanha", "Chuva (mm)", "ET0 (mm)", "Tmax média (°C)", "Tmin média (°C)",
                   "Época (dias)", "Classe"]].round(1),
            hide_index=True, width="stretch")

    with st.expander("Qualidade dos dados"):
        report = quality_report(clim)
        excluded = int((~table["complete"]).sum())
        st.write(f"Período: {report['start']} a {report['end']} ({report['days']} dias). "
                 f"Dias corrigidos: {report['corrected_days']}. "
                 f"Campanhas incompletas excluídas: {excluded}.")
        st.write({name: f"{share:.2%}" for name, share in report["missing_fraction"].items()})

# --- Catálogo de culturas ---------------------------------------------------
with st.expander("Catálogo de culturas", expanded=clim is None):
    catalogue = pd.DataFrame([
        {
            "Cultura": crop.name_pt,
            "Família": crop.family,
            "Ciclo (dias)": crop.cycle_days,
            "Kc inicial": crop.kc_ini,
            "Kc médio": crop.kc_mid,
            "Kc final": crop.kc_end,
            "Ky": crop.ky,
            "Ky é": "hipótese" if crop.ky_status == "hipotese" else "tabelado, a confirmar",
            "% N do ar": crop.ndfa,
        }
        for crop in crops.values()
    ])
    st.dataframe(catalogue, hide_index=True, width="stretch")
    st.caption(origin_label("literatura", "FAO-56 (Tabelas 11, 12 e 24) e Peoples et al. 2021")
               + ". Parâmetros por preencher: ver params/README.md.")

with st.expander("Estado do projecto"):
    st.markdown(
        "- **Fase 1, ambiente:** concluída\n"
        "- **Fase 2, dados:** concluída (clima, ET0, campanhas, cenários, solo por defeito)\n"
        "- **Fase 3, motor:** concluída (balanço hídrico, WRSI, rotações, score, explicações)\n"
        "- **Fase 4, interface:** página de recomendação a funcionar; falta o polimento\n"
        "- **Fase 5, validação e pitch**"
    )
