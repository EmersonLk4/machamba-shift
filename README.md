# Machamba Shift

**Which crops should a farm rotate over the next three seasons?** Machamba Shift answers
with evidence instead of a forecast: for any point in Mozambique it replays about 35 real
growing seasons of NASA POWER data for each crop, shows how often the rain was enough, and
recommends a three-season rotation with the reasons and the trade-offs.

NASA Space Apps Challenge 2026 · Challenge: *Field Shift: Adapting Farms with NASA Data* ·
solo entry. *Machamba* is the Mozambican word for a family farm.

- **Live demo:** _add the public link here after deployment_
- **Versão em português:** [README.pt.md](README.pt.md)

## What it does

| The challenge asks for | What the tool shows |
| --- | --- |
| Compare rotations | Four strategies side by side: today's crop every year, alternating with another cereal, alternating with a legume, and the recommended plan |
| Reveal trade-offs | Every recommendation states what is given up; the farmer's priorities (protect the harvest, restore the soil, maximise yield) change the plan |
| Understand risk | For each crop, in how many of every 10 real seasons the rain covered its water needs, fell short, or failed badly |
| Make uncertainty visible | Each crop from its worst year to its best; plans that are practically tied are shown as tied; a section lists what the tool does not know |

Other features: a satellite map with recent conditions (rain, temperature, wind, soil
moisture), regional rain maps for 449 NASA POWER cells, analysis of a hand-drawn region,
history by season and by month, a sowing-date comparison, and a downloadable PDF report.

## Why there is no forecast

We tested whether rain at the start of a season predicts the rest of it. At our sites it
does not: rank correlations were between −0.09 and +0.16 (`scripts/test_outlook.py`). A
forecast we cannot trust would be worse than none, so the tool describes what happened in
past seasons and chooses the plan that held up most often across dry and wet years.

## Data

| Source | Used for | Notes |
| --- | --- | --- |
| [NASA POWER](https://power.larc.nasa.gov/) daily and monthly point API | Rain, temperature, humidity, wind, solar radiation, soil wetness since 1990 | Modelled values on a 0.5° × 0.625° grid (about 55 × 65 km), not field measurements |
| [Open-Meteo archive](https://open-meteo.com/) (ERA5) | Fallback if POWER is unreachable; independent comparison | Partner-agency reanalysis |
| FAO Irrigation and Drainage Paper 56 | Crop coefficients, growth stages, water-balance method | Some parameters still to be confirmed against the tables |
| Peoples et al. 2021 | Share of nitrogen that legumes fix from the air | Literature values |

No simulated climate is shown anywhere in the app. Synthetic data exists only in the tests.

## How the engine decides

1. **Climate.** Daily series for the point, quality-checked; reference evapotranspiration
   by the Hargreaves method.
2. **Water balance.** For each crop and each real season (1 October to 30 April), a daily
   FAO-56 soil water balance gives a water satisfaction index and a relative yield.
3. **Risk.** A season counts as short of water when the rain covered less than 80% of the
   crop's needs, and as a severe failure below 50%.
4. **Rotations.** Every three-season sequence that respects the rules (no crop repeated,
   at least one staple cereal if the farmer wants one) is scored on water, soil nitrogen,
   resilience, yield and diversity, weighted by the farmer's priorities.
5. **Explanation.** Two reasons for the plan and one line on what it costs.

All agronomic numbers live in `params/`; every figure in the interface states whether it
is observed, modelled, estimated or from the literature.

## Results at the demonstration sites

| Site | Normal season rain | Bad year (1 in 10) | Good year (1 in 10) | Maize short of water |
| --- | --- | --- | --- | --- |
| Chókwè (Limpopo valley) | 633 mm | 438 mm | 874 mm | 74% of seasons, severe failure in 14% |

In Chókwè the recommended plan is groundnut › sorghum › cowpea; the top five plans score
between 0.660 and 0.664 and are presented as practically tied.

## Limitations

- **No forecast.** The tool describes past seasons; it does not predict the next one.
- **Zone, not field.** Values describe an area of about 50 km. They do not replace a soil
  test or local extension advice.
- **NASA POWER rain is uncertain.** Against ERA5, seasonal rain correlated at r = 0.64 in
  Chókwè and r = 0.55 in Sussundenga, but only r = 0.07 in Gurué. The tool flags Gurué
  as unreliable on its trust page, and its results should not be used.
- **Soil is a default loam.** The SoilGrids service was unavailable during development.
- **No prices.** `params/economics.csv` is empty, so income has zero weight.
- **Not validated against measured yields.** Outputs are for comparing options.
- **Hargreaves ET₀** ran 11–14% above Penman-Monteith at our sites.

## Run it locally

Requires Python 3.11 to 3.13.

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app/O_que_plantar.py
```

Optional, with internet access:

```bash
python scripts/build_demo.py         # download climate for the demonstration sites
python scripts/build_grid.py         # download the regional grid (449 land cells)
pytest                               # 127 tests, no network needed
```

The interface is in Portuguese, the language of its intended users.

## Repository layout

```
app/        Streamlit page, charts, maps, report (never calls an API)
data/       API clients, caching, climate features, regional grid, region analysis
engine/     Water balance, nitrogen, rules, scoring, rotation search (pure functions)
params/     Crops, thresholds, sites, soil defaults
scripts/    Setup, API check, data downloads, engine run, forecast-skill test
tests/      Unit and page tests on synthetic data
```

## Use of AI

AI assistance was used in this project. See the declaration in the submission page.

## Licence

See [LICENSE](LICENSE).
