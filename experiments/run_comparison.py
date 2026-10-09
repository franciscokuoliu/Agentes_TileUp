"""Comparación experimental de los dos agentes.

Seis configuraciones de N, K y M, tres semillas por configuración y el mismo
límite de tiempo para ambos agentes. Para cada semilla se genera una
instancia distinta con ``generate.py``; las instancias, las soluciones y los
resultados quedan en ``experiments/comparison/`` para poder verificarlos con
el validador.

Uso (desde la raíz del repositorio)::

    python experiments/run_comparison.py [--time-limit 10]

Escribe ``results.csv`` (una fila por ejecución) y ``summary.md`` (tabla por
agente y configuración con media ± desviación estándar entre semillas).
Las ejecuciones ya guardadas se omiten; para repetir la batería completa hay
que borrar ``experiments/comparison/runs/``.
"""

from __future__ import annotations

import argparse
import statistics
from pathlib import Path

from common import ROOT, mean_sd, run_battery

STUDY = ROOT / "experiments" / "comparison"

#: (nombre, N, K, M). Van de instancias holgadas a instancias donde el
#: tablero se llena, y la última tiene una secuencia larga.
CONFIGS = (
    ("C1_N4_K3_M40", 4, 3, 40),
    ("C2_N5_K5_M100", 5, 5, 100),
    ("C3_N6_K8_M200", 6, 8, 200),
    ("C4_N5_K15_M150", 5, 15, 150),
    ("C5_N8_K6_M400", 8, 6, 400),
    ("C6_N10_K4_M1200", 10, 4, 1200),
)

SEEDS = (1, 2, 3)


def summarize(rows: list[dict], time_limit: float) -> str:
    lines = [
        f"Límite de tiempo: {time_limit} s por ejecución. Semillas: {', '.join(map(str, SEEDS))}.",
        "Valores: media ± desviación estándar entre semillas, sobre las ejecuciones que terminaron.",
        "",
        "| Configuración | Agente | Terminadas | Legales | Colocadas | Ocupadas | Tiempo (s) | Esfuerzo | Detalle |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name, _n, _k, m in CONFIGS:
        for agent in ("search", "evo"):
            group = [r for r in rows if r["caso"] == name and r["agente"] == agent]
            ok = [r for r in group if r["estado"] == "ok"]
            details = sorted({str(r["detalle"]) for r in group if r["detalle"]})
            unit = ok[0]["unidad_esfuerzo"] if ok else ""
            lines.append(
                f"| {name} | {agent} | {len(ok)}/{len(group)} "
                f"| {sum(1 for r in ok if r['legal'])}/{len(ok)} "
                f"| {mean_sd([r['colocadas'] for r in ok])} de {m} "
                f"| {mean_sd([r['ocupadas'] for r in ok])} "
                f"| {mean_sd([r['tiempo'] for r in ok], 2)} "
                f"| {mean_sd([r['esfuerzo'] for r in ok], 0)} {unit} "
                f"| {', '.join(details)} |"
            )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--time-limit", type=float, default=10.0)
    args = parser.parse_args()
    rows = run_battery(STUDY, CONFIGS, SEEDS, args.time_limit)
    summary = summarize(rows, args.time_limit)
    (STUDY / "summary.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
