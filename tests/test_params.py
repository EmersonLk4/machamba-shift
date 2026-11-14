"""Os ficheiros de parâmetros estão completos no essencial e são coerentes."""

from engine.params import load_crops, load_economics, load_rules, load_sites
from engine.schemas import INDICATORS


def test_nine_crops_with_valid_stages_and_kc():
    crops = load_crops()
    assert len(crops) == 9
    for crop in crops.values():
        assert min(crop.l_ini, crop.l_dev, crop.l_mid, crop.l_late) > 0
        assert 60 <= crop.cycle_days <= 240
        assert 0 < crop.kc_ini <= crop.kc_mid <= 1.3
        assert 0 < crop.kc_end <= crop.kc_mid
        assert 0 < crop.ky <= 1.5
        assert crop.ky_status in {"tabelado_a_confirmar", "hipotese"}


def test_cycle_lengths_match_the_plan():
    crops = load_crops()
    expected = {"milho": 125, "mapira": 125, "mexoeira": 105, "feijao_vulgar": 110,
                "feijao_nhemba": 100, "amendoim": 130, "soja": 85, "gergelim": 110,
                "batata_doce": 125}
    assert {key: crop.cycle_days for key, crop in crops.items()} == expected


def test_legumes_have_ndfa_and_others_do_not():
    for crop in load_crops().values():
        if crop.is_legume:
            assert crop.family == "Fabaceae"
            assert 0 < crop.ndfa <= 100
        else:
            assert crop.ndfa is None


def test_empty_cells_are_none_not_zero():
    milho = load_crops()["milho"]
    assert milho.zr_m is None and milho.p is None and milho.tmax is None


def test_weight_presets_sum_to_one():
    rules = load_rules()
    assert "equilibrado" in rules["weights"]
    for weights in rules["weights"].values():
        assert set(weights) == set(INDICATORS)
        assert abs(sum(weights.values()) - 1.0) < 1e-9


def test_sites_are_in_mozambique_and_reference_known_crops():
    crops = load_crops()
    sites = load_sites()
    assert {"chokwe", "gurue"} <= set(sites)
    for site in sites.values():
        assert -27 < site.lat < -10 and 30 < site.lon < 41
        assert site.current_crop in crops
        assert site.common_legume in crops and crops[site.common_legume].is_legume


def test_economics_lists_every_crop():
    assert set(load_economics().index) == set(load_crops())
