"""Descarrega a grelha regional do mapa (condições reais por célula do NASA POWER).

Uso (na raiz do repositório):
    python scripts/build_grid.py              # grelha completa, cerca de 650 células
    python scripts/build_grid.py --step 2     # uma em cada duas células (teste rápido)

Para cada célula faz dois pedidos: o histórico mensal desde 1990 e a série diária da
campanha em curso. As respostas ficam em cache, por isso pode interromper e voltar a
correr: continua de onde parou. O resultado fica em data/demo/grid/ (versionado).
"""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data.clients import power  # noqa: E402
from data.climate import START_YEAR, default_end_year  # noqa: E402
from data.grid import fetch_cell, grid_cells, normals, save_grid  # noqa: E402

WORKERS = 4


def main(argv: list[str]) -> int:
    step = int(argv[argv.index("--step") + 1]) if "--step" in argv else 1
    cells = grid_cells(step)
    today = date.today()
    end_year = default_end_year()
    print(f"{len(cells)} células, {START_YEAR} a {end_year}, {WORKERS} pedidos em paralelo.")

    probe = power.fetch_monthly(-24.5, 33.125, START_YEAR, end_year)
    units = probe.get("parameters", {}).get("PRECTOTCORR", {}).get("units", "desconhecida")
    sample = power.parse_monthly(probe)
    print(f"Teste em Chókwè: unidade da chuva mensal = {units}; {len(sample)} meses; "
          f"chuva anual média {sample.groupby('year')['p_mm'].sum().mean():.0f} mm.")

    started = time.perf_counter()
    seasons, now, sea, failed = [], [], 0, []
    with ThreadPoolExecutor(WORKERS) as pool:
        jobs = {pool.submit(fetch_cell, lat, lon, START_YEAR, end_year, today): (lat, lon)
                for lat, lon in cells}
        for done, job in enumerate(as_completed(jobs), start=1):
            try:
                cell_seasons, cell_now = job.result()
            except Exception as error:  # noqa: BLE001 - uma célula falhada não pára as outras
                failed.append((jobs[job], error))
                continue
            if cell_seasons.empty:
                sea += 1
            else:
                seasons.append(cell_seasons)
                if cell_now is not None:
                    now.append(cell_now)
            if done % 25 == 0 or done == len(cells):
                print(f"  {done}/{len(cells)} células · {time.perf_counter() - started:.0f} s")

    if not seasons:
        print("Nenhuma célula descarregada. Verifique a ligação e volte a correr.")
        return 1
    all_seasons = pd.concat(seasons, ignore_index=True)
    folder = save_grid(all_seasons, pd.DataFrame(now))
    summary = normals(all_seasons)
    print(f"\nCélulas em terra: {len(summary)} · no mar: {sea} · falhadas: {len(failed)}")
    print(f"Campanhas por célula: {int(summary['seasons'].min())} a "
          f"{int(summary['seasons'].max())}")
    print(f"Chuva de uma campanha normal: de {summary['rain_normal_mm'].min():.0f} a "
          f"{summary['rain_normal_mm'].max():.0f} mm na região")
    if now:
        latest = pd.DataFrame(now)
        print(f"Agora: {latest['months'].iloc[0]} de {latest['season'].iloc[0]}, dados até "
              f"{latest['last_date'].max()} · chuva mediana {latest['rain_mm'].median():.0f} mm "
              f"(normal {latest['rain_normal_mm'].median():.0f} mm)")
    else:
        print("Agora: ainda sem nenhum mês completo nesta campanha.")
    for (lat, lon), error in failed[:5]:
        print(f"  Falhou {lat}, {lon}: {error}")
    if failed:
        print("Volte a correr o script: as células já descarregadas vêm da cache.")
    print(f"Guardado em {folder.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
