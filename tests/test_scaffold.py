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
    assert app.title[0].value == "Machamba Shift"
    assert [button.label for button in app.button] == ["Descarregar clima do NASA POWER"]
    assert "Solo por defeito" not in [m.value for m in app.metric]     # é legenda, não métrica
    assert any("solo franco por defeito" in caption.value for caption in app.caption)


def test_home_with_climate_shows_the_site_card(data_home, clim):
    from data.climate import save_climate
    save_climate(clim, -24.53, 33.00, demo=True)
    app = run_page("app/Home.py")
    assert not app.exception
    assert len(app.button) == 0
    labels = [metric.label for metric in app.metric]
    assert "Chuva mediana" in labels and "Época de crescimento" in labels
    assert any("12 campanhas completas" in caption.value for caption in app.caption)
    assert any("fonte alternativa" in warning.value for warning in app.warning)   # SINTÉTICO


def test_scenarios_page(data_home, clim):
    from data.climate import save_climate
    app = run_page("app/pages/2_Cenarios.py")
    assert not app.exception and len(app.metric) == 0          # sem clima: só o aviso
    save_climate(clim, -24.53, 33.00, demo=True)
    app = run_page("app/pages/2_Cenarios.py")
    assert not app.exception and len(app.metric) == 4
    app.selectbox[0].select("quente").run()
    assert not app.exception
    assert app.metric[2].delta == "+2.0 °C"
    app.selectbox[0].select("ano").run()
    assert not app.exception and len(app.selectbox) == 2
