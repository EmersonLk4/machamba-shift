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
    "data.paths", "data.climate", "data.soil", "data.grid", "app.components.maps",
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
    app = run_page("app/O_que_plantar.py")
    assert not app.exception
    assert "Chókwè" in app.title[0].value                      # abre directamente no local
    assert [button.label for button in app.button] == ["Descarregar clima do NASA POWER"]
    assert len(app.metric) == 0


def test_home_with_climate_tells_the_whole_story(data_home, clim):
    from data.climate import save_climate
    save_climate(clim, -24.53, 33.00, demo=True)
    app = run_page("app/O_que_plantar.py")
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
    app = run_page("app/pages/1_Posso_confiar.py")
    assert not app.exception
    save_climate(clim, -24.53, 33.00, demo=True)
    app = run_page("app/pages/1_Posso_confiar.py")
    assert not app.exception and len(app.dataframe) >= 2


def test_home_shows_map_layers_when_the_grid_exists(data_home, clim):
    import numpy as np
    import pandas as pd

    from data import grid
    from data.climate import save_climate
    save_climate(clim, -24.53, 33.00, demo=True)
    cells = [(lat, lon) for lat, lon in grid.grid_cells(step=4)]
    seasons = pd.DataFrame([
        {"lat": lat, "lon": lon, "season": year, "rain_mm": 600.0 + 10 * (year - 1990) - 8 * lat,
         "tmean_c": 25.0} for lat, lon in cells for year in range(1990, 2000)])
    now = pd.DataFrame([
        {"lat": lat, "lon": lon, "season": 2026, "months": "Outubro", "rain_mm": 30.0,
         "rain_normal_mm": 40.0, "gwet": 0.3, "gwet_normal": 0.35, "gwet_latest": np.nan
         if lon > 40 else 0.3, "last_date": "2026-11-10"} for lat, lon in cells])
    grid.save_grid(seasons, now)
    app = run_page("app/O_que_plantar.py")
    assert not app.exception
    layer = next(radio for radio in app.radio if radio.label == "O que o mapa mostra")
    assert layer.options[-2].startswith("Agora: chuva de Outubro de 2026")
    for option in ("ano", "agora", "solo"):
        layer.set_value(option).run()
        assert not app.exception
