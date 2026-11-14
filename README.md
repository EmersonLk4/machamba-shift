# Machamba Shift

Ferramenta de apoio à decisão que compara rotações de culturas em três campanhas agrícolas
para um ponto no mapa, com dados de observação da Terra da NASA.

NASA Space Apps Challenge 2026 · desafio *Field Shift: Adapting Farms with NASA Data* · equipa Data Architects.

**Estado:** Fases 1 (ambiente) e 2 (dados) concluídas. A aplicação descarrega o clima
diário de um ponto no NASA POWER, calcula a ET0, divide a série em campanhas, classifica os
anos secos e constrói os cenários. O motor de decisão está por implementar (ver `docs/ROADMAP.md`).

## Tecnologias a instalar

| O quê | Versão | Para quê |
| --- | --- | --- |
| Python (64 bits) | 3.11, 3.12 ou 3.13 | Linguagem única do projecto |
| Git | Qualquer versão recente | Controlo de versões e deploy |
| Editor (VS Code com a extensão Python) | — | Opcional, recomendado |

As bibliotecas instalam-se com `pip` a partir de `requirements.txt`:

| Biblioteca | Para quê |
| --- | --- |
| `streamlit`, `streamlit-folium`, `folium` | Interface e mapa clicável |
| `plotly` | Gráficos interactivos |
| `pandas`, `numpy` | Séries temporais e cálculo do motor |
| `pyarrow` | Cache em Parquet |
| `requests`, `requests-cache` | Pedidos às APIs com cache em disco |
| `pyyaml` | Leitura de `params/*.yaml` |
| `pytest`, `ruff` (só desenvolvimento) | Testes e verificação de estilo |

Não é preciso instalar Node.js, Docker, PostgreSQL nem GDAL.

Contas úteis: GitHub (repositório e deploy), Streamlit Community Cloud (deploy gratuito) e,
só se forem usados SMAP ou IMERG, Earthdata Login.

## Instalação

Windows (PowerShell), na raiz do repositório:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
.\.venv\Scripts\Activate.ps1
```

Linux ou macOS:

```bash
bash scripts/setup.sh
source .venv/bin/activate
```

Os scripts criam o ambiente virtual, instalam as dependências e correm os testes.

## Verificar que está tudo a funcionar

```bash
pytest                              # 78 testes, sem rede
python scripts/check_apis.py        # testa POWER, SoilGrids, TESViS e Open-Meteo
python scripts/build_demo.py --compare   # descarrega o clima dos locais de demonstração
streamlit run app/Home.py           # abre a aplicação em http://localhost:8501
```

`build_demo.py` guarda o clima de Chókwè, Gurué e Sussundenga em `data/demo/climate/`
(versionado, para a demonstração correr sem Internet) e imprime um resumo por local:
campanhas completas, chuva mediana, campanhas mais secas e, com `--compare`, a diferença
para o Open-Meteo. Para qualquer outro ponto, o botão "Descarregar clima" da aplicação faz
o mesmo e guarda em `data/cache/`.

## Primeiro commit

O repositório já está inicializado (`git init`, ramo `main`), sem commits.

```bash
git add .
git commit -m "Fase 1: estrutura do projecto"
git remote add origin https://github.com/<utilizador>/machamba-shift.git
git push -u origin main
```

## Estrutura

```text
machamba-shift/
├── app/                  Interface Streamlit
│   ├── Home.py           Mapa, ficha de clima e de solo, catálogo de culturas
│   ├── pages/            Cenários (clima por cenário) e Recomendação (Fase 4)
│   └── components/       Gráficos e etiquetas de origem dos dados
├── data/                 Único pacote que faz pedidos de rede
│   ├── clients/          power.py, soilgrids.py, tesvis.py, openmeteo.py, http.py
│   ├── climate.py        get_climate(): POWER ou plano B, validação, ET0, cache
│   ├── features.py       ET0 de Hargreaves, campanhas, terços, época de crescimento
│   ├── scenarios.py      Histórico, seco, favorável, seco paramétrico, quente, ano real
│   ├── validate.py       Dados ausentes e relatório de qualidade
│   ├── soil.py           Solo com plano B (ficheiro de demo ou solo por defeito)
│   ├── cache/            Cache local, ignorada pelo git
│   └── demo/             Dados dos locais de demonstração, versionados
├── engine/               Motor de decisão: funções puras
│   ├── schemas.py        Contratos de dados
│   ├── params.py         Leitura de params/
│   └── water_balance.py, nitrogen.py, rules.py, rotation.py, scoring.py, explain.py (Fase 3)
├── params/               crops.csv, rules.yaml, sites.yaml, soil_defaults.yaml, economics.csv
├── fixtures/             Exemplos dos contratos; raw/ recebe respostas reais
├── analysis/             Validação e sensibilidade (Fase 5)
├── scripts/              setup.ps1, setup.sh, check_apis.py, build_demo.py
├── tests/
└── docs/ROADMAP.md       Fases e âmbito a solo
```

## Convenções dos dados

- **Campanha Y:** 1 de Outubro de Y a 30 de Abril de Y+1 (`params/rules.yaml`).
- **Coluna `season`:** ano agrícola de 1 de Julho a 30 de Junho, para cada dia pertencer a
  uma só campanha e o motor ter os meses secos antes da sementeira.
- **Campanha completa:** no máximo 10% de dias em falta. Só estas entram nos terços e nos cenários.
- **Terços:** o terço de campanhas com menos chuva é "seco", o de mais chuva é "favorável".
- **ET0:** sempre Hargreaves-Samani sobre Tmax e Tmin, mesmo quando a fonte é o Open-Meteo,
  para os cenários serem comparáveis.
- **Falhas:** temperaturas interpoladas até 5 dias; chuva em falta recebe a média desse dia
  do ano; cada dia alterado fica com `qc_flag = 1`.

## O que já funciona e o que não foi testado

| Parte | Estado |
| --- | --- |
| Parâmetros, contratos, etiquetas de origem | Implementado e testado |
| Clientes POWER, TESViS e Open-Meteo | Responderam em `check_apis.py` (14 de Novembro de 2026) |
| ET0, campanhas, terços, cenários, tratamento de falhas | Implementado e testado com clima sintético |
| Descarga de 35 anos do POWER num só pedido | **Não testado com o servidor.** Se falhar, o código pede em blocos de 5 anos |
| Ficha de clima e página de cenários | Testadas com clima sintético; falta ver com dados reais |
| Solo | Solo franco por defeito (hipótese). SoilGrids suspenso; parser por confirmar |
| Época de crescimento | Indicador por calibrar com dados reais antes de servir de filtro |
| Motor e recomendação | Só assinaturas (`NotImplementedError`) |

## Fontes de dados

| Fonte | Uso | Natureza |
| --- | --- | --- |
| [NASA POWER](https://power.larc.nasa.gov/) | Clima diário por ponto | Modelado (reanálise MERRA-2) |
| [SoilGrids](https://www.isric.org/explore/soilgrids), ISRIC | pH, textura, carbono, azoto | Modelado (mapa global a 250 m) |
| [TESViS](https://modis.ornl.gov/data/modis_webservice.html), ORNL DAAC | NDVI do MODIS | Observado |
| [FAO-56](https://www.fao.org/4/X0490e/x0490e0b.htm), ECOCROP | Coeficientes das culturas | Literatura |
| [Open-Meteo](https://open-meteo.com/en/docs/historical-weather-api) | Plano B do clima (não é NASA) | Modelado (reanálise ERA5) |

## Limites

A ferramenta caracteriza a zona, não o talhão: o clima vem de uma célula de cerca de 50 km.
Os resultados são estimativas comparativas entre rotações. Não são previsões de produção
nem substituem a análise de solo.

## Documentos do projecto

- Plano técnico e estratégico: https://claude.ai/artifact/FTrTAtuGBzpYv5qGyBBt1q
- Quadro do plano de 48 horas: https://claude.ai/artifact/X8ccZz5AUQFwUphopCn9h9

## Licença

MIT. Ver `LICENSE`.
