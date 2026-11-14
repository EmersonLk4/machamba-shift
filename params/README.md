# Parâmetros

Todos os números agronómicos do projecto vivem nesta pasta. O código não tem constantes agronómicas.

| Ficheiro | Conteúdo |
| --- | --- |
| `crops.csv` | Uma linha por cultura: fases, Kc, Ky, limites térmicos e de pH, fixação de N |
| `rules.yaml` | Limiares, constantes do motor, cenários e predefinições de pesos |
| `sites.yaml` | Locais de demonstração e datas de sementeira |
| `soil_defaults.yaml` | Retenção de água por classe de textura (FAO-56, Tabela 19, a confirmar) |
| `economics.csv` | Rendimento de referência, preço e custo por cultura |

## Estado de `crops.csv`

| Colunas | Estado | Fonte |
| --- | --- | --- |
| `l_ini`, `l_dev`, `l_mid`, `l_late`, `kc_mid`, `kc_end` | Preenchidas e conferidas | FAO-56, Tabelas 11 e 12 |
| `kc_ini` | Preenchida com o valor do grupo; confirmar | FAO-56, Tabela 12 |
| `ky` | `ky_status` diz se é valor tabelado por confirmar ou hipótese (1,0) | FAO-56, Tabela 24 |
| `ndfa` | Preenchida para as leguminosas | Peoples et al. 2021 |
| `n_fix_kg_ha` | Só feijão-nhemba (47) e feijão vulgar (29) | Peoples et al. 2021, médias para África |
| `zr_m`, `p` | **Por preencher** | FAO-56, Tabela 22 |
| `tmin`, `topmin`, `topmax`, `tmax`, `ph_min`, `ph_max` | **Por preencher** | ECOCROP |
| `n_export_kg_t` | **Por preencher** | Literatura de remoção de nutrientes |

`economics.csv` está vazio de propósito: preencher com FAOSTAT ou preços locais, indicando a fonte em cada linha.

## Ligações

- FAO-56, Capítulo 6: https://www.fao.org/4/X0490e/x0490e0b.htm
- FAO-56, índice: https://www.fao.org/3/X0490E/x0490e00.htm
- ECOCROP: https://gaez.fao.org/pages/ecocrop
- Peoples et al. 2021: https://doi.org/10.1007/s11104-021-05167-6
