"""Construção dos pedidos e parsers dos clientes. Nenhum teste faz pedidos de rede."""

import json
from pathlib import Path

import numpy as np

from data.clients import power, soilgrids
from engine.schemas import CLIMATE_COLUMNS

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_power_request_parameters():
    params = power.build_params(-24.53, 33.0, "19900101", "20241231")
    assert params["community"] == "AG"
    assert params["format"] == "JSON"
    assert params["latitude"] == "-24.5300" and params["longitude"] == "33.0000"
    assert params["parameters"].split(",")[0] == "PRECTOTCORR"
    assert len(params["parameters"].split(",")) <= 20   # limite da API por pedido


def test_power_parser_follows_the_contract():
    payload = json.loads((FIXTURES / "power_format_sample.json").read_text(encoding="utf-8"))
    frame = power.parse_daily(payload)
    assert len(frame) == 3
    assert frame.index.is_monotonic_increasing
    assert str(frame.index[0].date()) == "2023-01-01"
    # tudo o que o parser devolve pertence ao contrato, excepto gwettop (extra informativo)
    assert set(frame.columns) - {"gwettop"} <= set(CLIMATE_COLUMNS)
    assert frame.loc["2023-01-02", "p_mm"] == 12.5
    assert (frame["source"] == "NASA POWER").all()


def test_power_parser_turns_fill_value_into_nan():
    payload = json.loads((FIXTURES / "power_format_sample.json").read_text(encoding="utf-8"))
    frame = power.parse_daily(payload)
    assert np.isnan(frame.loc["2023-01-03", "p_mm"])
    assert np.isnan(frame.loc["2023-01-03", "rad_mj"])
    assert not (frame.select_dtypes("number") == -999).any().any()


def test_soilgrids_request_repeats_property_and_depth():
    params = soilgrids.build_params(-24.53, 33.0)
    assert [value for key, value in params if key == "property"] == list(soilgrids.PROPERTIES)
    assert [value for key, value in params if key == "depth"] == list(soilgrids.DEPTHS)


def test_soilgrids_parser_weights_by_layer_thickness():
    payload = {"properties": {"layers": [{
        "name": "phh2o",
        "unit_measure": {"d_factor": 10},
        "depths": [
            {"label": "0-5cm", "values": {"mean": 60}},
            {"label": "5-15cm", "values": {"mean": 63}},
            {"label": "15-30cm", "values": {"mean": 66}},
        ],
    }, {
        "name": "clay",
        "unit_measure": {"d_factor": 10},
        "depths": [{"label": "0-5cm", "values": {"mean": None}}],
    }]}}
    values = soilgrids.parse_properties(payload)
    assert abs(values["phh2o"] - (6.0 * 5 + 6.3 * 10 + 6.6 * 15) / 30) < 1e-9
    assert values["clay"] is None
