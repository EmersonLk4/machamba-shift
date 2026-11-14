# Machamba Shift

Ferramenta de apoio à decisão que compara rotações de culturas em três campanhas agrícolas
para um ponto no mapa, com dados de observação da Terra da NASA.

NASA Space Apps Challenge 2026 · desafio *Field Shift: Adapting Farms with NASA Data* · equipa Data Architects.

**Estado:** Fases 1 (ambiente), 2 (dados) e 3 (motor) concluídas. A aplicação descarrega o
clima diário de um ponto no NASA POWER, simula o balanço hídrico de cada cultura em cada
campanha real, avalia todas as rotações de três campanhas e recomenda uma, com a explicação.
Falta o polimento da interface, a validação e o pitch (ver `docs/ROADMAP.md`).

## Estrutura

```text
machamba-shift/
├── app/                  Interface Streamlit
│   ├── Home.py           Mapa, ficha de clima e de solo, catálogo de culturas
│   ├── pages/            Recomendação (quatro estratégias e o porquê) e Cenários
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
├── scripts/              setup.ps1, setup.sh, check_apis.py, build_demo.py, run_engine.py
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
3. **Rotações.** Todas as sequências de três campanhas que passam os filtros (sem repetir a
   cultura em anos seguidos, preferências do agricultor, pH e temperatura quando há dados).
4. **Indicadores, de 0 a 1.** Água (menos ETc é melhor), solo (índice de azoto), resiliência
   (`1 - (P(stress) + P(falha)) / 2`), rendimento relativo, margem (só com preços) e diversidade
   de famílias botânicas.
5. **Score.** Soma ponderada pelas prioridades do agricultor, menos 0,05 por cada repetição de
   família em anos seguidos. Os limites de normalização são calculados no cenário histórico e
   congelados, para os cenários serem comparáveis.
6. **Explicação.** As duas maiores contribuições para a vantagem sobre a monocultura dão as
   frases "porquê"; a mais negativa dá a frase "em troca".

Diferenças em relação ao plano inicial, decididas com os dados reais:

- A época de crescimento não é filtro (em Chókwè tem 50 dias, menos do que qualquer ciclo).
- O solo é avaliado por um índice de azoto sem unidades, não por um balanço em kg N/ha,
  porque faltam rendimentos e teores de N para todas as culturas.
- A resiliência conta o stress e a falha, em vez de um único limiar.

## O que já funciona e o que não foi testado

| Parte | Estado |
| --- | --- |
| Parâmetros, contratos, etiquetas de origem | Implementado e testado |
| Clima real de Chókwè, Gurué e Sussundenga (NASA POWER, 35 campanhas) | Descarregado a 14 de Novembro de 2026 |
| ET0, campanhas, terços, cenários, tratamento de falhas | Implementado e testado |
| Motor: balanço hídrico, regras, score, rotações, explicações | Implementado e testado com clima sintético; **falta rever os resultados com o clima real** |
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

## Licença

MIT. Ver `LICENSE`.
