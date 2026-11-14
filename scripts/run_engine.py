"""Corre o motor para os locais de demonstração e imprime os resultados em texto.

Uso (na raiz do repositório, depois de scripts/build_demo.py):
    python scripts/run_engine.py                    # todos os locais, histórico e seco
    python scripts/run_engine.py chokwe             # só um local
    python scripts/run_engine.py chokwe quente      # um local, um cenário
    python scripts/run_engine.py chokwe ano:2015    # repetir a campanha 2015/16

Serve para rever a plausibilidade: o que o motor recomenda, porquê e com que números.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data.climate import load_cached_climate  # noqa: E402
from data.soil import get_soil  # noqa: E402
from engine.params import load_crops, load_economics, load_rules, load_sites  # noqa: E402
from engine.rotation import recommend  # noqa: E402
from engine.rules import Constraints  # noqa: E402

LABELS = {"monocultura": "Monocultura", "convencional": "Convencional",
          "com_leguminosa": "Com leguminosa", "recomendada": "RECOMENDADA"}


def show(result, catalogue) -> None:
    print(f"\n  Cenário {result.scenario} · {result.seasons} campanhas · "
          f"{result.candidates} rotações viáveis")
    print("  Culturas: WRSI mediano | % campanhas com stress (<80) | % com falha (<50) | "
          "ETc mm | rendimento relativo")
    for key, item in sorted(result.crop_stats.items(), key=lambda pair: -pair[1]["wrsi_median"]):
        print(f"    {catalogue[key].name_pt:<16} {item['wrsi_median']:5.0f} | "
              f"{100 * item['p_stress']:3.0f}% | {100 * item['p_failure']:3.0f}% | "
              f"{item['etc_median_mm']:4.0f} | {item['y_rel_median']:.2f}")
    print("  Estratégias: score | água solo resil. rend. marg. diver. | sequência")
    for item in result.strategies:
        values = " ".join("  — " if item.indicators[name] is None
                          else f"{item.indicators[name]:.2f}" for name in item.indicators)
        print(f"    {LABELS[item.label]:<15} {item.score:5.3f} | {values} | "
              + " > ".join(item.raw["names"]))
    print("  Porquê:")
    for line in result.explanation:
        print(f"    - {line}")
    print("  Cinco melhores: " + "; ".join(
        f"{' > '.join(row['names'])} ({row['score']:.3f})" for row in result.ranking[:5]))


def main(argv: list[str]) -> int:
    sites = load_sites()
    wanted = [arg for arg in argv if arg in sites]
    scenarios = [arg for arg in argv if arg not in sites] or ["historico", "seco"]
    rules = load_rules()
    catalogue = load_crops()
    economics = load_economics()
    for site_id, site in sites.items():
        if wanted and site_id not in wanted:
            continue
        clim = load_cached_climate(site.lat, site.lon)
        print(f"\n{site.name} · sementeira {site.sow_day:02d}/{site.sow_month:02d} · "
              f"cultura actual: {catalogue[site.current_crop].name_pt}")
        if clim is None:
            print("  Sem clima guardado: correr primeiro python scripts/build_demo.py")
            continue
        soil = get_soil(site.lat, site.lon, site_id=site_id)
        print(f"  Solo: {soil.texture}, {soil.taw_mm_per_m:.0f} mm/m ({soil.source}) · "
              f"pesos: equilibrado")
        for scenario in scenarios:
            result = recommend(site, clim, soil, list(catalogue), rules["weights"]["equilibrado"],
                               rules, scenario=scenario, catalogue=catalogue,
                               economics=economics)
            show(result, catalogue)
            kept = recommend(site, clim, soil, list(catalogue), rules["weights"]["equilibrado"],
                             rules, scenario=scenario, catalogue=catalogue, economics=economics,
                             constraints=Constraints(required={site.current_crop}))
            print(f"  Mantendo {catalogue[site.current_crop].name_pt.lower()} pelo menos uma vez: "
                  + "; ".join(f"{' > '.join(row['names'])} ({row['score']:.3f})"
                              for row in kept.ranking[:3]))
        for flag in result.flags:
            print(f"  Aviso: {flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
