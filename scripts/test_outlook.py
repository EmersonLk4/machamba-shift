"""Mede se o início da campanha diz alguma coisa sobre o resto.

Uso (na raiz do repositório, depois de scripts/build_demo.py):
    python scripts/test_outlook.py              # corte a 14 de Novembro
    python scripts/test_outlook.py 12-15        # corte a 15 de Dezembro

Para cada local compara, nas campanhas completas, a chuva de 1 de Outubro até à data de
corte com a chuva do RESTO da campanha (da data de corte a 30 de Abril). Comparar com o
total da campanha seria batota, porque o total já inclui o início.

O resultado decide o que o painel "Perspectiva para a campanha" pode afirmar.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data.climate import load_cached_climate  # noqa: E402
from data.features import complete_seasons, season_bounds, season_table  # noqa: E402
from engine.params import load_rules, load_sites  # noqa: E402


def tercile(values: pd.Series) -> pd.Series:
    low, high = values.quantile(1 / 3), values.quantile(2 / 3)
    return values.apply(lambda v: "seco" if v <= low else "chuvoso" if v >= high else "normal")


def analyse(clim: pd.DataFrame, rules: dict, month: int, day: int) -> pd.DataFrame:
    rows = []
    for year in complete_seasons(season_table(clim, rules)):
        start, end = season_bounds(year, rules)
        cut = pd.Timestamp(year if month >= 7 else year + 1, month, day)
        early = clim.loc[start:cut, "p_mm"].sum()
        rest = clim.loc[cut + pd.Timedelta(days=1):end, "p_mm"].sum()
        rows.append({"season": year, "early_mm": early, "rest_mm": rest})
    table = pd.DataFrame(rows).set_index("season")
    table["early_class"] = tercile(table["early_mm"])
    table["rest_class"] = tercile(table["rest_mm"])
    return table


def verdict(spearman: float, hit_rate: float) -> str:
    if abs(spearman) >= 0.5 and hit_rate >= 0.55:
        return "RELAÇÃO ÚTIL: os anos análogos dizem alguma coisa sobre o resto da campanha."
    if abs(spearman) >= 0.3:
        return ("RELAÇÃO FRACA: os anos análogos podem ser mostrados só como contexto, "
                "com a incerteza bem à vista.")
    return ("SEM RELAÇÃO: o início da campanha não antecipa o resto. O painel deve ficar "
            "pelo início observado e pelo risco histórico.")


def main(argv: list[str]) -> int:
    month, day = (int(part) for part in (argv[0] if argv else "11-14").split("-"))
    rules = load_rules()
    print(f"Corte a {day:02d}/{month:02d}. Início = 1 de Outubro até ao corte; "
          f"resto = do corte a 30 de Abril.")
    for site in load_sites().values():
        clim = load_cached_climate(site.lat, site.lon)
        print(f"\n{site.name}")
        if clim is None:
            print("  Sem clima guardado: correr primeiro python scripts/build_demo.py")
            continue
        table = analyse(clim, rules, month, day)
        pearson = table["early_mm"].corr(table["rest_mm"])
        # Spearman = Pearson sobre as posições; assim não é preciso instalar o scipy
        spearman = table["early_mm"].rank().corr(table["rest_mm"].rank())
        hit_rate = float((table["early_class"] == table["rest_class"]).mean())
        share = table["early_mm"].sum() / (table["early_mm"] + table["rest_mm"]).sum()
        print(f"  Campanhas: {len(table)} · o início representa {100 * share:.0f}% da chuva "
              f"da campanha, em média")
        print(f"  Correlação início vs resto: Pearson {pearson:+.2f}, Spearman {spearman:+.2f}")
        print(f"  Acerto de classe (início seco/normal/chuvoso = resto na mesma classe): "
              f"{100 * hit_rate:.0f}% (ao acaso seriam cerca de 33%)")
        cross = pd.crosstab(table["early_class"], table["rest_class"]).reindex(
            index=["seco", "normal", "chuvoso"], columns=["seco", "normal", "chuvoso"],
            fill_value=0)
        print("  Início (linhas) contra resto (colunas), em número de campanhas:")
        for line in cross.to_string().splitlines():
            print(f"    {line}")
        dry_start = table[table["early_class"] == "seco"]
        print(f"  Depois de um início seco, o resto foi também seco em "
              f"{int((dry_start['rest_class'] == 'seco').sum())} de {len(dry_start)} campanhas")
        print(f"  Leitura: {verdict(spearman, hit_rate)}")
    print("\nCom cerca de 35 campanhas, uma correlação abaixo de 0,33 em valor absoluto não "
          "se distingue do acaso (5%).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
