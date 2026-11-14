"""Cliente do SoilGrids 2.0 (ISRIC), propriedades do solo por ponto.

Documentação: https://rest.isric.org/soilgrids/v2.0/docs
API em fase beta, limite de 5 pedidos por minuto. A ISRIC anunciou a suspensão
temporária do serviço: se o pedido falhar, usar os valores guardados em data/demo/.

São previsões de um modelo a 250 m, não análises do talhão.

ATENÇÃO: parse_properties foi escrito a partir da estrutura documentada e ainda não
foi testado com uma resposta real. Correr scripts/check_apis.py e confirmar com o
ficheiro guardado em fixtures/raw/soilgrids.json.
"""

from __future__ import annotations

from data.clients.http import get_json

BASE_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"
PROPERTIES = ("phh2o", "soc", "nitrogen", "clay", "sand", "silt")
DEPTHS = ("0-5cm", "5-15cm", "15-30cm")
THICKNESS_CM = {"0-5cm": 5, "5-15cm": 10, "15-30cm": 15}


def build_params(lat: float, lon: float) -> list[tuple[str, str]]:
    """Parâmetros do pedido. property, depth e value repetem-se, por isso é uma lista."""
    params: list[tuple[str, str]] = [("lon", f"{lon:.5f}"), ("lat", f"{lat:.5f}")]
    params += [("property", name) for name in PROPERTIES]
    params += [("depth", depth) for depth in DEPTHS]
    params += [("value", "mean"), ("value", "uncertainty")]
    return params


def fetch_properties(lat: float, lon: float, use_cache: bool = True, timeout: float = 30,
                     retries: int = 2) -> dict:
    """Pede as propriedades e devolve o JSON tal como chega."""
    return get_json(BASE_URL, params=build_params(lat, lon), use_cache=use_cache,
                    timeout=timeout, retries=retries)


def parse_properties(payload: dict) -> dict[str, float | None]:
    """Média ponderada de 0 a 30 cm de cada propriedade, em unidades convencionais.

    Os valores chegam como inteiros escalados; divide-se por unit_measure.d_factor
    (por exemplo pH x 10, argila em g/kg). Devolve None quando o píxel não tem dados.
    """
    result: dict[str, float | None] = {}
    for layer in payload["properties"]["layers"]:
        factor = layer["unit_measure"]["d_factor"]
        total = weight = 0.0
        for depth in layer["depths"]:
            mean = depth["values"].get("mean")
            thickness = THICKNESS_CM.get(depth["label"])
            if mean is None or thickness is None:
                continue
            total += mean / factor * thickness
            weight += thickness
        result[layer["name"]] = total / weight if weight else None
    return result
