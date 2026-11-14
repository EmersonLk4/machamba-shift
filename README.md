# Machamba Shift

Ferramenta de apoio à decisão que compara rotações de culturas em três campanhas agrícolas
para um ponto no mapa, com dados de observação da Terra da NASA.

NASA Space Apps Challenge 2026 · desafio *Field Shift: Adapting Farms with NASA Data* · equipa Data Architects.

**Estado:** dados, motor e interface concluídos. A página única (`streamlit run
app/O_que_plantar.py`) tem mapa de satélite com as condições recentes do NASA POWER, histórico,
risco por cultura, datas de sementeira, plano de três campanhas, perguntas e relatório para
descarregar. Falta: publicação, documentação em inglês e diapositivos.

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
pytest                              # 111 testes, sem rede
python scripts/check_apis.py        # testa POWER, SoilGrids, TESViS e Open-Meteo
python scripts/build_demo.py --compare   # descarrega o clima dos locais de demonstração
python scripts/build_grid.py        # descarrega a grelha regional do mapa (demora)
python scripts/run_engine.py        # corre o motor nos locais de demonstração, em texto
streamlit run app/O_que_plantar.py           # abre a aplicação em http://localhost:8501
```

`run_engine.py` imprime, por local e cenário, o WRSI de cada cultura, as quatro estratégias
com os seus indicadores, a explicação e as cinco melhores rotações. É a forma mais rápida
de rever a plausibilidade do motor.

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
│   ├── O_que_plantar.py  Página principal: mapa, chuva do local, risco das culturas, plano
│   ├── pages/            Posso confiar (fontes, limites, qualidade)
│   └── components/       Gráficos e etiquetas de origem dos dados
├── data/                 Único pacote que faz pedidos de rede
│   ├── clients/          power.py, soilgrids.py, tesvis.py, openmeteo.py, http.py
│   ├── climate.py        get_climate(): POWER ou plano B, validação, ET0, cache
│   ├── features.py       ET0 de Hargreaves, campanhas, terços, época de crescimento
│   ├── scenarios.py      Histórico, seco, favorável, seco paramétrico, quente, ano real
│   ├── validate.py       Dados ausentes e relatório de qualidade
│   ├── soil.py           Solo com plano B (ficheiro de demo ou solo por defeito)
│   ├── grid.py           Grelha regional para o mapa (condições reais por célula)
│   ├── cache/            Cache local, ignorada pelo git
│   └── demo/             Dados dos locais de demonstração, versionados
├── engine/               Motor de decisão: funções puras
│   ├── schemas.py        Contratos de dados
│   ├── params.py         Leitura de params/
│   ├── water_balance.py  Curva de Kc, balanço hídrico diário FAO-56, WRSI
│   ├── nitrogen.py       Índice de azoto e efeito leguminosa -> cereal
│   ├── rules.py          Filtros e penalizações agronómicas
│   ├── scoring.py        Normalização, pesos e score
│   ├── rotation.py       recommend(): enumeração e as quatro estratégias
│   └── explain.py        Frases "porquê" e "em troca"
├── params/               crops.csv, rules.yaml, sites.yaml, soil_defaults.yaml,
│                         engine_defaults.yaml, economics.csv
├── fixtures/             Exemplos dos contratos; raw/ recebe respostas reais
├── analysis/             Validação e sensibilidade (Fase 5)
├── scripts/              setup.ps1, setup.sh, check_apis.py, build_demo.py, run_engine.py,
│                         test_outlook.py
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

## Como o motor decide

1. **Simulação.** Para cada cultura e cada campanha real corre um balanço hídrico diário do
   solo (FAO-56). Daí saem o WRSI (percentagem das necessidades de água satisfeitas pela
   chuva), a ETc e o rendimento relativo `1 - Ky x (1 - ETa/ETc)`.
2. **Risco.** Uma campanha com WRSI abaixo de 80 conta como stress; abaixo de 50, como falha.
3. **Rotações.** Todas as sequências de três campanhas que passam os filtros (a mesma
   cultura não volta dentro das três campanhas, pelo menos um cereal de base se pedido,
   preferências do agricultor, pH e temperatura quando há dados).
4. **Indicadores, de 0 a 1.** Água (fracção das necessidades que a chuva cobre num ano
   típico), solo (índice de azoto), resiliência
   (`1 - (P(stress) + P(falha)) / 2`), rendimento relativo, margem (só com preços) e diversidade
   de famílias botânicas.
5. **Score.** Soma ponderada pelas prioridades do agricultor, menos 0,05 por cada repetição de
   família em anos seguidos. Os limites de normalização são calculados no cenário histórico e
   congelados, para os cenários serem comparáveis. Em caso de empate (até 0,005) prefere-se
   a rotação que mantém a cultura actual.
6. **Explicação.** As duas maiores contribuições para a vantagem sobre a monocultura dão as
   frases "porquê"; a mais negativa dá a frase "em troca".

Diferenças em relação ao plano inicial, decididas com os dados reais:

- A época de crescimento não é filtro (em Chókwè tem 50 dias, menos do que qualquer ciclo).
- O solo é avaliado por um índice de azoto sem unidades, não por um balanço em kg N/ha,
  porque faltam rendimentos e teores de N para todas as culturas.
- A resiliência conta o stress e a falha, em vez de um único limiar.
- A água mede a cobertura pela chuva, não a procura: premiar culturas que pedem pouca água
  onde a água sobra fazia o motor recomendar o mesmo em todo o lado.
- Não há previsão da campanha. `scripts/test_outlook.py` mostra que a chuva do início não
  antecipa a do resto em nenhum dos três locais (correlações entre -0,09 e +0,16).

## O que já funciona e o que não foi testado

| Parte | Estado |
| --- | --- |
| Parâmetros, contratos, etiquetas de origem | Implementado e testado |
| Clima real de Chókwè, Gurué e Sussundenga (NASA POWER, 35 campanhas) | Descarregado a 14 de Novembro de 2026 |
| ET0, campanhas, terços, cenários, tratamento de falhas | Implementado e testado |
| Motor: balanço hídrico, regras, score, rotações, explicações | Implementado e testado. Revisto com clima real e corrigido a 14 de Novembro; **a correcção falta rever com clima real** |
| Chuva do POWER contra o Open-Meteo | Chókwè: correlação 0,64, viés +32%. Gurué: correlação 0,07, pouco fiável |
| Solo | Solo franco por defeito (hipótese). SoilGrids suspenso |
| Profundidade radicular e fracção p | Hipóteses em `params/engine_defaults.yaml`, por confirmar na Tabela 22 do FAO-56 |
| Adequação térmica e filtro de pH | Só actuam quando `crops.csv` tiver os limites ECOCROP |
| Margem económica | Fora do score enquanto `economics.csv` estiver vazio |

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
