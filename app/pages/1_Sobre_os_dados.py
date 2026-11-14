"""De onde vêm os números, como são calculados e o que não se sabe."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from data.climate import load_cached_climate  # noqa: E402
from data.features import season_table  # noqa: E402
from data.validate import quality_report  # noqa: E402
from engine.params import load_crops, load_rules, load_sites  # noqa: E402

st.set_page_config(page_title="Sobre os dados · Machamba Shift", page_icon="🌱", layout="wide")
st.title("Sobre os dados")

st.header("De onde vem cada número")
st.dataframe(pd.DataFrame([
    ["Chuva e temperatura diárias", "NASA POWER", "Modelado",
     "Reanálise MERRA-2; uma célula tem cerca de 50 km"],
    ["Água que a cultura pede (ET0, ETc)", "Machamba Shift", "Simulado",
     "ET0 de Hargreaves; coeficientes de cultura do FAO-56"],
    ["Água suficiente, falha grave, colheita", "Machamba Shift", "Simulado",
     "Balanço hídrico diário do solo (FAO-56) em cada campanha real"],
    ["Fases e coeficientes das culturas", "FAO-56, Tabelas 11 e 12", "Literatura",
     "Valores genéricos, não calibrados para variedades moçambicanas"],
    ["Azoto vindo do ar", "Peoples et al. 2021", "Literatura", "Médias por grupo de leguminosas"],
    ["Solo", "Solo franco por defeito", "Hipótese",
     "A API do SoilGrids está suspensa; a água disponível não é a do local"],
    ["Raízes e sensibilidade à seca", "params/engine_defaults.yaml", "Hipótese",
     "Por confirmar no FAO-56, Tabelas 22 e 24"],
], columns=["O quê", "Fonte", "Natureza", "Nota"]), hide_index=True, width="stretch")

st.header("O que testámos e não funcionou")
st.markdown(
    "- **Prever a campanha pelo seu início.** A chuva de Outubro a meados de Novembro não "
    "antecipa a do resto da campanha em nenhum dos três locais (correlações entre -0,09 e "
    "+0,16 em 35 campanhas). Por isso a ferramenta mostra o risco histórico e não uma previsão.\n"
    "- **Gurué.** A chuva do NASA POWER e a do ERA5 não concordam sobre quais foram os anos "
    "secos (correlação 0,07). Os resultados desse local não são fiáveis.\n"
    "- **Concordância entre fontes.** Em Chókwè a correlação da chuva por campanha entre o "
    "NASA POWER e o ERA5 é 0,64 e em Sussundenga 0,55; o POWER dá mais 32% e mais 13% de chuva.")

st.header("O que a ferramenta não avalia")
st.markdown(
    "- Preços, custos e valor alimentar das culturas.\n"
    "- Pragas, doenças, fertilização, variedades e rega.\n"
    "- Adequação térmica e pH, enquanto os limites das culturas não estiverem preenchidos.\n"
    "- Os resultados ainda não foram validados com dados de campo.")

st.header("Qualidade do clima guardado")
rules = load_rules()
rows = []
for site in load_sites().values():
    clim = load_cached_climate(site.lat, site.lon)
    if clim is None:
        continue
    report = quality_report(clim)
    seasons = season_table(clim, rules)
    rows.append({"Local": site.name, "Fonte": report["source"],
                 "Período": f"{report['start']} a {report['end']}",
                 "Campanhas completas": int(seasons["complete"].sum()),
                 "Dias corrigidos": report["corrected_days"]})
if rows:
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
else:
    st.info("Sem clima guardado. Correr python scripts/build_demo.py.")

with st.expander("Parâmetros das culturas"):
    st.dataframe(pd.DataFrame([
        {"Cultura": crop.name_pt, "Família": crop.family, "Ciclo (dias)": crop.cycle_days,
         "Kc inicial": crop.kc_ini, "Kc médio": crop.kc_mid, "Kc final": crop.kc_end,
         "Ky": crop.ky, "Ky é": "hipótese" if crop.ky_status == "hipotese"
         else "tabelado, a confirmar", "% N do ar": crop.ndfa}
        for crop in load_crops().values()]), hide_index=True, width="stretch")
