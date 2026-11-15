# Submission page texts (English)

Copy each block into the matching field of the NASA Space Apps project page. Replace the
items in [brackets] before submitting.

## 1. Project name

Machamba Shift

## 2. High-level project summary

Machamba Shift helps a farmer in Mozambique decide which crops to rotate over the next
three seasons. Instead of forecasting a future nobody can know, it replays the past: for
any point in the country it runs a daily soil water balance for nine local crops through
about 35 real growing seasons of NASA POWER data, and shows in how many of every 10 seasons
the rain was enough, fell short, or failed badly. It then compares crop rotations, recommends
one, explains why, and states what is given up. It addresses the challenge directly: it
compares rotations, reveals trade-offs, expresses risk in a farmer's own terms, and keeps
uncertainty visible, including a list of what the tool does not know. It matters because a
smallholder who plants maize every year in a place where maize ran short of water in three
seasons out of four is carrying a risk that open NASA data can show her today.

## 3. Project demo link

[public link to the 7-slide deck]

## 4. Final project link

[public Streamlit link], source code: [public GitHub repository link]

## 5. Detailed project description

**What it does.** The user picks a place in Mozambique (a listed farming zone, a click on
the satellite map, or a hand-drawn region), describes the land (soil type), the crop grown
today, the crops the farmer accepts, and what matters most (protecting the harvest,
restoring the soil, maximising yield, or a balance). The tool returns:

- recent conditions for the area (rain, temperature, wind, soil wetness);
- the rain and temperature history by season and by month since 1990;
- for each crop, how many of every 10 real seasons had enough water, a water shortage, or a
  severe failure, and the range from its worst year to its best;
- a comparison of sowing dates for the current crop;
- what-if sliders that change rain and temperature, clearly labelled as hypothetical;
- regional maps of normal rain, of any past season, and of the rain and temperature trends
  since 1990, coloured only where the trend is statistically clear;
- a recommended three-season rotation compared with three alternatives (the same crop every
  year, alternating with another cereal, alternating with a legume), with two reasons and
  one explicit trade-off;
- a downloadable PDF report for use where there is no internet.

**How it works.** Daily NASA POWER climate is downloaded for the point and quality-checked.
For every crop and every real season (1 October to 30 April) a daily FAO-56 soil water
balance gives a water satisfaction index and a relative yield. A season counts as short of
water when rain covered less than 80% of the crop's needs, and as a severe failure below
50%. Every valid three-season sequence is then scored on water, soil nitrogen (legumes add,
cereals remove), resilience, yield and diversity, weighted by the farmer's priorities.
Plans that are practically tied are shown as tied.

**Scientific honesty.** We tested whether rain at the start of a season predicts the rest
of it. At our sites it does not (rank correlations between −0.09 and +0.16), so the tool
contains no forecast and says so. We compared NASA POWER seasonal rain with ERA5: agreement
was moderate in Chókwè (r = 0.64) and Sussundenga (r = 0.55) and absent in Gurué (r = 0.07),
and the tool flags Gurué as unreliable. Every number in the interface states whether it is
modelled, estimated or from the literature. The outputs are for comparing options; they
have not been validated against measured yields.

**Example.** In Chókwè (Limpopo valley) a normal season brings 633 mm of rain, a bad year
438 mm and a good year 874 mm. Maize ran short of water in 74% of the seasons analysed and
failed severely in 14%. The recommended plan is groundnut, then sorghum, then cowpea.

**Supporting, not replacing, local knowledge.** The tool states that it supports the
decision and does not make it, and names where human judgement matters most: pests and
diseases, the soil of each field, seed and labour, local prices and what the family eats.

**Benefits.** Risk is expressed as "in how many of every 10 seasons", which a farmer or an
extension officer can act on without statistics. The regional maps cover Mozambique in 449
NASA POWER cells, so the same analysis is available anywhere in the country.

**What we hope to achieve.** A tool that extension services can use to discuss rotation
with farmers. Next steps: local soil data, prices and yields to add income, a second rain
source (CHIRPS or GPM IMERG), vegetation history (MODIS), cyclone history, and a link to the
official seasonal forecast of Mozambique's National Institute of Meteorology (INAM).

**Tools.** Python, Streamlit, Folium and Leaflet (with Leaflet.draw), Plotly, pandas, NumPy,
PyArrow, requests and requests-cache, PyYAML, ReportLab, pytest and ruff. The interface is
in Portuguese, the language of its intended users. 130 automated tests run without network
access.

## 6. Use of Super Intelligence (SI)

Yes. The idea for the project came from a brainstorming session among the team members. An
AI assistant (Claude, by Anthropic) was then used extensively to turn those ideas into the
project: it drafted the technical plan and wrote most of the code, the automated tests and
the documentation, and it helped draft the texts on this page and the presentation, under
the author's direction. The author ran every data download and every engine run on real
NASA POWER data, reviewed the results, and decided what to keep or discard. No AI model runs
inside the application: every number and sentence shown to the user is computed
deterministically from the data. No AI-generated images, video or audio are used. The use
of AI is also declared in the repository README.

## 7. NASA data

- **NASA POWER (Prediction Of Worldwide Energy Resources), Daily API**, agroclimatology
  community, point queries, 1990 to 2026. Parameters: PRECTOTCORR (precipitation), T2M,
  T2M_MAX, T2M_MIN (air temperature at 2 m), RH2M (relative humidity), WS2M (wind speed),
  ALLSKY_SFC_SW_DWN (solar radiation), GWETROOT and GWETTOP (root-zone and surface soil
  wetness). Used for the water balance of each crop and for recent conditions.
  https://power.larc.nasa.gov/
- **NASA POWER Monthly API**, parameter PRECTOTCORR, for the regional rain maps (449 land
  cells of 0.5° × 0.625° over Mozambique) and the hand-drawn region analysis.

## 8. Space Agency Partner data and other references

Data:

- Open-Meteo Historical Weather API (ERA5 reanalysis, ECMWF / Copernicus Climate Change
  Service): fallback source and independent comparison of seasonal rain.
  https://open-meteo.com/
- Esri World Imagery and World Boundaries and Places map tiles (Esri, Maxar, Earthstar
  Geographics): satellite basemap.

Methods and parameters:

- Allen, Pereira, Raes and Smith (1998), *Crop evapotranspiration*, FAO Irrigation and
  Drainage Paper 56: crop coefficients, growth stages, soil water balance, yield response
  factors, soil water retention by texture.
- FAO ECOCROP: temperature limits of the crops.
- Peoples et al. (2021): share of nitrogen that legumes fix from the air.
- Hargreaves and Samani (1985): reference evapotranspiration.

Software: Python, Streamlit, streamlit-folium, Folium, Leaflet, Leaflet.draw, Plotly,
pandas, NumPy, PyArrow, requests, requests-cache, PyYAML, ReportLab, pytest, ruff.

AI tool: Claude (Anthropic), as described in field 6.

No copyrighted images are used. No NASA logos or mission identifiers are used.
