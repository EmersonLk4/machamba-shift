# Roteiro a solo

O plano original foi desenhado para cinco pessoas. Para uma pessoa em 48 horas, o âmbito
fica reduzido ao fluxo essencial: clicar no mapa, ver clima e solo, receber a rotação
recomendada contra a monocultura, mudar de cenário e ler o porquê.

## Fases

| Fase | Conteúdo | Ficheiros principais | Pronto quando |
| --- | --- | --- | --- |
| 1. Ambiente (feita) | Repositório, dependências, parâmetros, contratos de dados | Esqueleto | `pytest` passa e a aplicação abre |
| 2. Dados (feita) | Clima real do POWER, solo, ET0, corte por campanhas, cenários, cache | `data/climate.py`, `data/features.py`, `data/scenarios.py`, `data/validate.py`, `data/soil.py` | `python scripts/build_demo.py` guarda Chókwè e Gurué em `data/demo/` |
| 3. Motor (feita) | Curva de Kc, balanço hídrico, WRSI, índice de azoto, regras, enumeração, score, explicações | `engine/*.py`, `scripts/run_engine.py` | `recommend()` devolve um `Recommendation` válido com dados reais |
| 4. Interface (em curso) | Página de recomendação já funciona; falta comparar cenários lado a lado, risco "em X de cada 10" e polimento | `app/` | O fluxo completo corre nos dois locais |
| 5. Validação e pitch | Testes de sanidade, comparação com Open-Meteo, README, vídeo, submissão | `analysis/`, `README.md` | Submissão feita com margem |

## O que fica de fora a solo

- Margem económica (o peso `margem` fica a 0 enquanto `economics.csv` estiver vazio)
- Série de NDVI do MODIS, humidade SMAP, deltas NEX-GDDP-CMIP6
- Selo de robustez dos pesos e análise de sensibilidade completa
- Ficha em PDF, endpoint FastAPI, data de sementeira calculada

Qualquer um destes só entra depois de a Fase 4 estar fechada.

## Regras de arquitectura

1. Só `data/` faz pedidos de rede. `engine/` são funções puras. `app/` não chama APIs.
2. Os números agronómicos vivem em `params/`, nunca no código.
3. Os contratos de dados estão em `engine/schemas.py`. Mudar um campo obriga a mudar a fixture.
4. Cada número mostrado declara a origem: observado, estimado, modelado, literatura, simulado ou hipótese.
5. Os locais de demonstração ficam em `data/demo/` e correm sem Internet.
