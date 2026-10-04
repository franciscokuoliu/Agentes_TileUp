"""Barrido de parámetros del agente evolutivo.

Procedimiento: se parte de la configuración base (``EvolutionConfig()``) y se
varía un parámetro a la vez, dejando los demás en su valor base. Cada
variante se ejecuta sobre las instancias de ajuste con varias semillas.

Las instancias de ajuste se generan aquí con semillas propias y son
distintas de las que se usan en la comparación experimental, para no
ajustar los parámetros sobre los mismos datos con que se evalúa.

Uso (desde la raíz del repositorio)::

    python experiments/tune_evo.py [--time-limit 5]

Cada variante se guarda al terminar en ``experiments/results/tuning/``; al
volver a ejecutar el script se omiten las variantes ya guardadas, de modo
que el barrido puede reanudarse. Al final se unen en
``experiments/results/tuning.csv`` y se imprime un resumen por variante
en Markdown: rango promedio entre variantes (1 = mejor; los empates
reciben el promedio de sus posiciones) y, por instancia, fichas colocadas y
celdas ocupadas con media y desviación estándar entre semillas.
"""

from __future__ import annotations

import argparse
import csv
import random
import statistics
import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evolutionary_agent import EvolutionConfig, evolve, fitness  # noqa: E402

#: (N, K, M, semilla de generación). Con los pesos de referencia, dos de ellas
#: terminan en derrota y las otras dos ganan con margen para reducir la ocupación.
TUNING_INSTANCES = (
    (4, 10, 100, 101),
    (5, 12, 150, 102),
    (5, 20, 150, 103),
    (6, 15, 300, 104),
)

SEEDS = (1, 2, 3)

#: Valores alternativos por parámetro; el valor base se agrega aparte.
VARIATIONS = {
    "population_size": (15, 50),
    "tournament_size": (2, 5),
    "mutation_rate": (0.1, 0.5),
    "mutation_sigma": (0.5, 3.0),
    "stall_generations": (10, 50),
    "lookahead": (0, 8),
}


def make_instance(n: int, k: int, m: int, seed: int) -> list[tuple[int, int]]:
    rng = random.Random(seed)
    return [(rng.randint(1, k), rng.randint(1, 9)) for _ in range(m)]


def variants() -> list[tuple[str, EvolutionConfig]]:
    base = EvolutionConfig()
    result = [("base", base)]
    for name, values in VARIATIONS.items():
        for value in values:
            result.append((f"{name}={value}", replace(base, **{name: value})))
    return result


FIELDS = (
    "variante", "instancia", "m", "semilla", "colocadas", "ocupadas",
    "aptitud", "evaluaciones", "generaciones", "paro", "tiempo",
)


def run_variant(label: str, config: EvolutionConfig, time_limit: float) -> list[dict]:
    rows = []
    for n, k, m, gen_seed in TUNING_INSTANCES:
        tiles = make_instance(n, k, m, gen_seed)
        for seed in SEEDS:
            started = time.monotonic()
            result = evolve(n, tiles, k, seed, time_limit, config)
            rows.append({
                "variante": label,
                "instancia": f"N{n}_K{k}_M{m}",
                "m": m,
                "semilla": seed,
                "colocadas": result.record.placed,
                "ocupadas": result.record.occupied,
                "aptitud": fitness(result.record, n),
                "evaluaciones": result.evaluations,
                "generaciones": result.generations,
                "paro": result.stop_reason,
                "tiempo": round(time.monotonic() - started, 3),
            })
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    numeric = ("m", "semilla", "colocadas", "ocupadas", "aptitud", "evaluaciones", "generaciones")
    for row in rows:
        for key in numeric:
            row[key] = int(row[key])
        row["tiempo"] = float(row["tiempo"])
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--time-limit", type=float, default=5.0)
    args = parser.parse_args()

    results = ROOT / "experiments" / "results"
    rows: list[dict] = []
    for label, config in variants():
        part = results / "tuning" / f"{label}.csv"
        if not part.exists():
            write_csv(part, run_variant(label, config, args.time_limit))
            print(f"listo: {label}", file=sys.stderr, flush=True)
        rows += read_csv(part)

    write_csv(results / "tuning.csv", rows)
    print_summary(rows)


def print_summary(rows: list[dict]) -> None:
    labels = list(dict.fromkeys(row["variante"] for row in rows))
    instances = list(dict.fromkeys(row["instancia"] for row in rows))

    def runs(label: str, instance: str | None = None) -> list[dict]:
        return [r for r in rows if r["variante"] == label and (instance is None or r["instancia"] == instance)]

    ranks = {label: [] for label in labels}
    for instance in instances:
        means = {label: statistics.mean(r["aptitud"] for r in runs(label, instance)) for label in labels}
        # Rango fraccional: las variantes empatadas reciben el promedio de sus posiciones.
        for label in labels:
            better = sum(1 for other in labels if means[other] > means[label])
            tied = sum(1 for other in labels if means[other] == means[label])
            ranks[label].append(better + (tied + 1) / 2)

    def cell(selected: list[dict]) -> str:
        placed = [r["colocadas"] for r in selected]
        occupied = [r["ocupadas"] for r in selected]
        return (
            f"{statistics.mean(placed):.1f} ± {statistics.pstdev(placed):.1f} / "
            f"{statistics.mean(occupied):.1f} ± {statistics.pstdev(occupied):.1f}"
        )

    header = ["Variante", "Rango promedio", *instances, "Evaluaciones", "Tiempo (s)"]
    print("Celdas por instancia: colocadas / ocupadas, media ± desviación estándar entre semillas.")
    print()
    print("| " + " | ".join(header) + " |")
    print("| " + " | ".join("---" for _ in header) + " |")
    for label in sorted(labels, key=lambda label: statistics.mean(ranks[label])):
        selected = runs(label)
        cells = [cell(runs(label, instance)) for instance in instances]
        print(
            f"| {label} | {statistics.mean(ranks[label]):.2f} | " + " | ".join(cells)
            + f" | {statistics.mean(r['evaluaciones'] for r in selected):.0f}"
            + f" | {statistics.mean(r['tiempo'] for r in selected):.2f} |"
        )

if __name__ == "__main__":
    main()
