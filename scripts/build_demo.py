"""Descarrega e guarda o clima dos locais de demonstração em data/demo/climate/.

Uso (na raiz do repositório):
    python scripts/build_demo.py              # todos os locais de params/sites.yaml
    python scripts/build_demo.py chokwe       # só um
    python scripts/build_demo.py --compare    # compara também com o Open-Meteo (ERA5)

Depois de correr, a aplicação mostra estes locais sem Internet. O resumo impresso serve
para o "teste de realidade": as campanhas mais secas devem coincidir com secas conhecidas.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data.clients import openmeteo  # noqa: E402
from data.climate import START_YEAR, build_climate, default_end_year, save_climate  # noqa: E402
from data.features import add_et0, add_season, season_table, site_summary  # noqa: E402
from data.validate import fill_gaps, quality_report  # noqa: E402
from engine.params import load_rules, load_sites  # noqa: E402


def compare_with_openmeteo(site, clim, table, rules) -> None:
    """Chuva sazonal e ET0 do POWER contra o Open-Meteo, nas campanhas completas."""
    try:
        other = openmeteo.fetch_years(site.lat, site.lon, START_YEAR, default_end_year())
    except RuntimeError as error:
        print(f"  Comparação indisponível: {error}")
        return
    other = add_season(add_et0(fill_gaps(other), site.lat))
    other_table = season_table(other, rules)
    both = table[table["complete"]].join(other_table[other_table["complete"]],
                                         how="inner", rsuffix="_om")
    if len(both) < 5:
        print("  Comparação indisponível: poucas campanhas em comum")
        return
    corr = both["rain_mm"].corr(both["rain_mm_om"])
    bias = (both["rain_mm"].mean() / both["rain_mm_om"].mean() - 1) * 100
    print(f"  Chuva sazonal, POWER vs Open-Meteo: correlação {corr:.2f}, viés {bias:+.0f}% "
          f"({len(both)} campanhas)")
    days = clim.join(other[["et0_ref_mm"]], how="inner").dropna(subset=["et0_mm", "et0_ref_mm"])
    wet = days[days.index.month.isin([10, 11, 12, 1, 2, 3, 4])]
    diff = (wet["et0_mm"].mean() / wet["et0_ref_mm"].mean() - 1) * 100
    print(f"  ET0 Hargreaves (POWER) vs Penman-Monteith (Open-Meteo), Out-Abr: {diff:+.0f}%")


def main(argv: list[str]) -> int:
    compare = "--compare" in argv
    wanted = [arg for arg in argv if not arg.startswith("--")]
    rules = load_rules()
    sites = load_sites()
    for site_id, site in sites.items():
        if wanted and site_id not in wanted:
            continue
        print(f"\n{site.name} ({site.lat}, {site.lon})")
        try:
            clim = build_climate(site.lat, site.lon)
        except RuntimeError as error:
            print(f"  FALHOU: {error}")
            continue
        path = save_climate(clim, site.lat, site.lon, demo=True)
        table = season_table(clim, rules)
        summary = site_summary(table)
        report = quality_report(clim)
        done = table[table["complete"]]
        print(f"  Fonte: {report['source']} · {report['start']} a {report['end']} · "
              f"{report['corrected_days']} dias corrigidos")
        print(f"  Campanhas completas: {summary['seasons']} "
              f"({done['label'].iloc[0]} a {done['label'].iloc[-1]})")
        print(f"  Chuva Out-Abr: mediana {summary['rain_median_mm']:.0f} mm, "
              f"P10 {summary['rain_p10_mm']:.0f}, P90 {summary['rain_p90_mm']:.0f}")
        print(f"  ET0 Out-Abr mediana: {summary['et0_median_mm']:.0f} mm · "
              f"T média {summary['tmean_c']:.1f} °C · "
              f"época de crescimento mediana {summary['season_length_median_days']:.0f} dias")
        driest = done.nsmallest(6, "rain_mm")
        print("  Seis campanhas mais secas: "
              + ", ".join(f"{row.label} ({row.rain_mm:.0f} mm)" for row in driest.itertuples()))
        wettest = done.nlargest(3, "rain_mm")
        print("  Três mais chuvosas: "
              + ", ".join(f"{row.label} ({row.rain_mm:.0f} mm)" for row in wettest.itertuples()))
        if compare:
            compare_with_openmeteo(site, clim, table, rules)
        print(f"  Guardado em {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
