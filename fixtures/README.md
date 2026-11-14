# Fixtures

Ficheiros de exemplo que fixam os contratos de dados entre módulos.

| Ficheiro | Para quê |
| --- | --- |
| `recommendation.example.json` | Forma do objecto `Recommendation` que o motor entrega à interface. Os zeros são marcadores de posição |
| `power_format_sample.json` | Forma da resposta do NASA POWER, para testar o parser. **Valores inventados** |
| `raw/` | Respostas reais das APIs, guardadas por `python scripts/check_apis.py`. Não versionadas |

Depois de correr `scripts/check_apis.py`, as respostas em `raw/` passam a ser as fixtures reais para a Fase 2.
