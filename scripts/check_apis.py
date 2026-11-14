"""Testa as quatro APIs do projecto a partir desta máquina.

Uso (na raiz do repositório):
    python scripts/check_apis.py

Faz um pedido pequeno a cada serviço, mostra se respondeu e quanto demorou, e guarda
a resposta bruta em fixtures/raw/ para servir de fixture real nas fases seguintes.
Não usa a cache: o objectivo é saber o que está a funcionar agora.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data.clients import openmeteo, power, soilgrids, tesvis  # noqa: E402

RAW_DIR = ROOT / "fixtures" / "raw"
LAT, LON = -24.53, 33.00   # Chókwè


def describe_power(payload: dict) -> str:
    frame = power.parse_daily(payload)
    return f"{len(frame)} dias, colunas: {', '.join(c for c in frame.columns if c != 'source')}"


def describe_soilgrids(payload: dict) -> str:
    values = soilgrids.parse_properties(payload)
    return ", ".join(f"{k}={v:.2f}" if v is not None else f"{k}=sem dados"
                     for k, v in values.items())


def describe_tesvis(payload: dict) -> str:
    return f"{len(payload.get('subset', []))} registos (banda x data)"


def describe_openmeteo(payload: dict) -> str:
    return f"{len(payload.get('daily', {}).get('time', []))} dias"


CHECKS = [
    ("NASA POWER (clima)", "power",
     lambda: power.fetch_daily(LAT, LON, "20230101", "20230131", use_cache=False),
     describe_power),
    ("SoilGrids (solo)", "soilgrids",
     lambda: soilgrids.fetch_properties(LAT, LON, use_cache=False),
     describe_soilgrids),
    ("TESViS MODIS (NDVI)", "tesvis",
     lambda: tesvis.fetch_subset("MOD13Q1", LAT, LON, "A2023001", "A2023145", use_cache=False),
     describe_tesvis),
    ("Open-Meteo (plano B)", "openmeteo",
     lambda: openmeteo.fetch_daily(LAT, LON, "2023-01-01", "2023-01-31", use_cache=False),
     describe_openmeteo),
]


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    failures = 0
    print(f"A testar as APIs para Chókwè ({LAT}, {LON})\n")
    for title, slug, fetch, describe in CHECKS:
        started = time.perf_counter()
        try:
            payload = fetch()
        except Exception as error:  # noqa: BLE001 - diagnóstico: queremos ver qualquer falha
            failures += 1
            cause = error.__cause__ or error
            print(f"[FALHOU] {title}: {cause}")
            continue
        elapsed = time.perf_counter() - started
        (RAW_DIR / f"{slug}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        try:
            summary = describe(payload)
        except Exception as error:  # noqa: BLE001
            summary = f"respondeu, mas o formato não é o esperado ({error!r})"
        print(f"[OK]     {title}: {elapsed:.1f} s. {summary}")
    print(f"\nRespostas guardadas em {RAW_DIR.relative_to(ROOT)}/")
    if failures:
        print(f"{failures} serviço(s) sem resposta: activar o plano B correspondente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
