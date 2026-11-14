"""Leitura dos ficheiros de parâmetros em params/."""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import pandas as pd
import yaml

from engine.schemas import INDICATORS, Crop, Site

PARAMS_DIR = Path(__file__).resolve().parents[1] / "params"

_INT_FIELDS = {"l_ini", "l_dev", "l_mid", "l_late"}
_STR_FIELDS = {
    "crop_id", "name_pt", "scientific", "family", "group",
    "ky_status", "src_stages_kc", "src_n", "notes",
}


def load_crops(path: Path | None = None) -> dict[str, Crop]:
    """Lê crops.csv e devolve {crop_id: Crop}. Células vazias ficam a None."""
    table = pd.read_csv(path or PARAMS_DIR / "crops.csv", dtype=str, keep_default_na=False)
    names = {f.name for f in fields(Crop)}
    crops: dict[str, Crop] = {}
    for row in table.to_dict(orient="records"):
        values: dict[str, object] = {}
        for key, text in row.items():
            if key not in names:
                continue
            text = text.strip()
            if text == "":
                values[key] = None
            elif key == "is_legume":
                values[key] = text in {"1", "true", "True", "sim"}
            elif key in _INT_FIELDS:
                values[key] = int(text)
            elif key in _STR_FIELDS:
                values[key] = text
            else:
                values[key] = float(text)
        crop = Crop(**values)
        crops[crop.crop_id] = crop
    return crops


def load_rules(path: Path | None = None) -> dict:
    """Lê rules.yaml e confirma que cada predefinição de pesos soma 1."""
    with open(path or PARAMS_DIR / "rules.yaml", encoding="utf-8") as handle:
        rules = yaml.safe_load(handle)
    for name, weights in rules["weights"].items():
        if set(weights) != set(INDICATORS):
            raise ValueError(f"Pesos '{name}': chaves diferentes de {INDICATORS}")
        if abs(sum(weights.values()) - 1.0) > 1e-9:
            raise ValueError(f"Pesos '{name}': a soma é {sum(weights.values())}, devia ser 1")
    return rules


def load_sites(path: Path | None = None) -> dict[str, Site]:
    """Lê sites.yaml e devolve {id: Site}."""
    with open(path or PARAMS_DIR / "sites.yaml", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    return {item["id"]: Site(**item) for item in raw["sites"]}


def load_economics(path: Path | None = None) -> pd.DataFrame:
    """Lê economics.csv. As colunas numéricas ficam NaN enquanto não forem preenchidas."""
    return pd.read_csv(path or PARAMS_DIR / "economics.csv").set_index("crop_id")


def load_engine_defaults(path: Path | None = None) -> dict:
    """Lê engine_defaults.yaml: valores usados quando crops.csv tem células vazias."""
    with open(path or PARAMS_DIR / "engine_defaults.yaml", encoding="utf-8") as handle:
        return yaml.safe_load(handle)
