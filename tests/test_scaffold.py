"""O esqueleto está inteiro: módulos importáveis e fixture do contrato coerente."""

import importlib
import json
from pathlib import Path

import pytest

from app.components.labels import origin_label
from engine.schemas import INDICATORS, SCENARIOS, STRATEGY_LABELS

ROOT = Path(__file__).resolve().parents[1]

MODULES = [
    "data.clients.http", "data.clients.power", "data.clients.soilgrids",
    "data.clients.tesvis", "data.clients.openmeteo",
    "data.paths", "data.climate", "data.soil",
    "data.features", "data.scenarios", "data.validate",
    "app.components.charts",
    "engine.schemas", "engine.params", "engine.water_balance", "engine.nitrogen",
    "engine.rules", "engine.rotation", "engine.scoring", "engine.explain",
]


@pytest.mark.parametrize("name", MODULES)
def test_module_imports(name):
    importlib.import_module(name)


def test_recommendation_fixture_matches_the_contract():
    payload = json.loads(
        (ROOT / "fixtures" / "recommendation.example.json").read_text(encoding="utf-8"))
    assert payload["scenario"] in SCENARIOS
    assert set(payload["weights"]) == set(INDICATORS)
    assert abs(sum(payload["weights"].values()) - 1.0) < 1e-9
    for strategy in payload["strategies"]:
        assert strategy["label"] in STRATEGY_LABELS
        assert len(strategy["sequence"]) == 3
        assert set(strategy["indicators"]) == set(INDICATORS)


def test_origin_labels():
    assert origin_label("modelado", "NASA POWER") == "Modelado · NASA POWER"
    assert origin_label("hipotese") == "Hipótese"
    with pytest.raises(ValueError):
        origin_label("medido")


def run_page(relative: str):
    testing = pytest.importorskip("streamlit.testing.v1")
    return testing.AppTest.from_file(str(ROOT / relative), default_timeout=30).run()


def test_home_without_climate_offers_the_download(data_home):
    app = run_page("app/Home.py")
    assert not app.exception
    assert "Chókwè" in app.title[0].value                      # abre directamente no local
    assert [button.label for button in app.button] == ["Descarregar clima do NASA POWER"]
    assert len(app.metric) == 0


def test_home_with_climate_tells_the_whole_story(data_home, clim):
    from data.climate import save_climate
    save_climate(clim, -24.53, 33.00, demo=True)
    app = run_page("app/Home.py")
    assert not app.exception and len(app.button) == 0
    assert [header.value[:2] for header in app.header if header.value[0].isdigit()] == [
        "1.", "2.", "3."]
    labels = [metric.label for metric in app.metric]
    assert labels[:3] == ["Chuva de uma campanha normal", "Chuva numa campanha má",
                          "Chuva numa campanha boa"]
    assert "Campanhas com água suficiente" in labels
    assert all(metric.help for metric in app.metric)            # cada métrica explica-se
    assert any(text.value.startswith("- Em troca:") for text in app.markdown)
    assert not any("Qualidade" in expander.label for expander in app.expander)
    plan = app.subheader[0].value
    assert any(name in plan for name in ("Milho", "Mapira", "Mexoeira"))   # um cereal
    scenario = next(box for box in app.selectbox if box.label == "Ver o que teria acontecido")
    scenario.select("quente").run()
    assert not app.exception


def test_about_page(data_home, clim):
    from data.climate import save_climate
    app = run_page("app/pages/1_Sobre_os_dados.py")
    assert not app.exception
    save_climate(clim, -24.53, 33.00, demo=True)
    app = run_page("app/pages/1_Sobre_os_dados.py")
    assert not app.exception and len(app.dataframe) >= 2
