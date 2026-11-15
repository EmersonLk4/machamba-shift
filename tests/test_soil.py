"""Solo: plano B, classe de textura e retenção de água."""

import json

import pytest

from data import soil
from data.clients import soilgrids


def test_default_soil_is_loam_and_says_so():
    profile = soil.get_soil(-24.53, 33.0)
    assert profile.texture == "franco"
    assert profile.source == soil.SOURCE_DEFAULT
    assert profile.ph is None
    assert profile.taw_mm_per_m == pytest.approx(130.0)


def test_texture_classes():
    assert soil.texture_class(90, 5) == "arenoso"
    assert soil.texture_class(75, 10) == "areia_franca"
    assert soil.texture_class(60, 15) == "franco_arenoso"
    assert soil.texture_class(40, 20) == "franco"
    assert soil.texture_class(20, 20) == "franco_siltoso"
    assert soil.texture_class(30, 32) == "franco_argiloso"
    assert soil.texture_class(20, 50) == "argiloso"


def test_every_texture_has_positive_available_water():
    defaults = soil.load_defaults()
    assert defaults["default_texture"] in defaults["textures"]
    for values in defaults["textures"].values():
        assert 0 < values["wp"] < values["fc"] < 0.6


def test_demo_file_is_used_when_filled(data_home):
    (data_home / "demo").mkdir()
    (data_home / "demo" / "soil_chokwe.json").write_text(json.dumps({
        "_como_usar": "ignorado", "ph": 6.4, "clay_pct": 45.0, "sand_pct": 25.0,
        "silt_pct": 30.0, "soc_gkg": None, "n_gkg": None, "source": "teste"}), encoding="utf-8")
    profile = soil.get_soil(-24.53, 33.0, site_id="chokwe")
    assert profile.ph == 6.4 and profile.texture == "argiloso" and profile.source == "teste"
    assert profile.taw_mm_per_m == pytest.approx(140.0)


def test_unfilled_template_falls_back_to_default(data_home):
    (data_home / "demo").mkdir()
    (data_home / "demo" / "soil_chokwe.json").write_text(json.dumps({
        "ph": None, "clay_pct": None, "sand_pct": None, "source": "x"}), encoding="utf-8")
    assert soil.get_soil(-24.53, 33.0, site_id="chokwe").source == soil.SOURCE_DEFAULT


def test_api_failure_falls_back_to_default(monkeypatch):
    def down(*args, **kwargs):
        raise RuntimeError("SoilGrids suspenso")

    monkeypatch.setattr(soilgrids, "fetch_properties", down)
    assert soil.get_soil(-24.53, 33.0, try_api=True).source == soil.SOURCE_DEFAULT


def test_api_values_are_used_when_the_service_answers(monkeypatch):
    def layer(name, factor, value):
        return {"name": name, "unit_measure": {"d_factor": factor},
                "depths": [{"label": "0-5cm", "values": {"mean": value}}]}

    payload = {"properties": {"layers": [
        layer("phh2o", 10, 62), layer("clay", 10, 180), layer("sand", 10, 600),
        layer("silt", 10, 220), layer("soc", 10, 80), layer("nitrogen", 100, 90)]}}
    monkeypatch.setattr(soilgrids, "fetch_properties", lambda *args, **kwargs: payload)
    profile = soil.get_soil(-24.53, 33.0, try_api=True)
    assert profile.ph == pytest.approx(6.2) and profile.clay_pct == pytest.approx(18.0)
    assert profile.texture == "franco_arenoso" and profile.source.startswith("SoilGrids")


def test_soil_for_texture_changes_water_storage():
    from data.soil import SOURCE_FARMER, soil_for_texture
    sand, clay = soil_for_texture(-24.5, 33.0, "arenoso"), soil_for_texture(-24.5, 33.0, "argiloso")
    assert sand.source == SOURCE_FARMER and sand.taw_mm_per_m < clay.taw_mm_per_m
    with pytest.raises(ValueError):
        soil_for_texture(-24.5, 33.0, "pedra")
