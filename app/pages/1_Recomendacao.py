"""Página de recomendação: quatro estratégias lado a lado e painel Porquê. Fase 4."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from engine.params import load_rules  # noqa: E402
from engine.schemas import INDICATORS  # noqa: E402

st.set_page_config(page_title="Recomendação · Machamba Shift", page_icon="🌱", layout="wide")
st.title("Recomendação")

rules = load_rules()
preset = st.selectbox("Prioridades", list(rules["weights"]),
                      format_func=lambda key: key.replace("_", " ").capitalize())
weights = rules["weights"][preset]

st.subheader("Pesos do score")
columns = st.columns(len(INDICATORS))
for column, name in zip(columns, INDICATORS, strict=True):
    column.metric(name.capitalize(), f"{weights[name]:.2f}")

st.info("O motor de decisão é implementado na Fase 3. Esta página vai mostrar a rotação "
        "recomendada contra a monocultura, a rotação convencional e a rotação com leguminosa.")
