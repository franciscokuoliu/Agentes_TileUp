"""Estudio de escalabilidad: degradación de ambos agentes al crecer N y K.

Batería en malla: N en {4, 6, 8} × K en {3, 6, 12}, con M = 5·N² para que
la carga por celda sea constante y el efecto del tamaño del tablero no se
confunda con instancias más holgadas. Tres semillas por configuración y el
mismo límite de tiempo para ambos agentes.

Uso (desde la raíz del repositorio)::

    python experiments/run_scalability.py [--time-limit 5]

Escribe en ``experiments/scalability/``: ``results.csv``, ``summary.md`` y
cuatro gráficas SVG (porcentaje de fichas colocadas y tiempo, en función de
N y de K). Las ejecuciones ya guardadas se omiten al volver a correrlo.
"""

from __future__ import annotations

import argparse
import statistics

from common import ROOT, mean_sd, run_battery
from svgplot import line_chart

STUDY = ROOT / "experiments" / "scalability"
N_VALUES = (4, 6, 8)
K_VALUES = (3, 6, 12)
LOAD = 5
SEEDS = (1, 2, 3)
LABELS = {"search": "búsqueda", "evo": "evolutivo"}


def cases() -> list[tuple[str, int, int, int]]:
    return [(f"N{n}_K{k}", n, k, LOAD * n * n) for n in N_VALUES for k in K_VALUES]


def placed_pct(row: dict) -> float:
    """Porcentaje de fichas colocadas; una ejecución fallida cuenta como 0."""
    return 100 * row["colocadas"] / row["m"] if row["estado"] == "ok" else 0.0


def elapsed(row: dict, time_limit: float) -> float:
    """Tiempo usado; una ejecución fallida cuenta como el límite completo."""
    return row["tiempo"] if row["estado"] == "ok" else time_limit


def finished_in_time(row: dict, time_limit: float) -> bool:
    """La ejecución terminó por sí misma antes del límite.

    Para la búsqueda significa decidir la instancia (``victory`` o
    ``unsolvable``) sin agotar el tiempo.
    """
    if row["estado"] != "ok" or row["tiempo"] > time_limit:
        return False
    return row["detalle"] != "timeout" and row["detalle"] != "tiempo"


def summarize(rows: list[dict], time_limit: float) -> str:
    lines = [
        f"M = {LOAD}·N². Límite de tiempo: {time_limit} s. Semillas: {', '.join(map(str, SEEDS))}.",
        "Colocadas en % de M y tiempo: media ± desviación estándar entre semillas (una ejecución fallida cuenta como 0 % y como el límite completo).",
        "\"Termina\" es la cantidad de semillas en que el agente terminó por sí mismo antes del límite.",
        "",
        "| N | K | M | Agente | Colocadas (%) | Ocupadas | Tiempo (s) | Termina | Detalle |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name, n, k, m in cases():
        for agent in ("search", "evo"):
            group = [r for r in rows if r["caso"] == name and r["agente"] == agent]
            ok = [r for r in group if r["estado"] == "ok"]
            details = sorted({str(r["detalle"]).split(":")[0] for r in group if r["detalle"]})
            lines.append(
                f"| {n} | {k} | {m} | {LABELS[agent]} "
                f"| {mean_sd([placed_pct(r) for r in group])} "
                f"| {mean_sd([r['ocupadas'] for r in ok])} "
                f"| {mean_sd([elapsed(r, time_limit) for r in group], 2)} "
                f"| {sum(finished_in_time(r, time_limit) for r in group)}/{len(group)} "
                f"| {', '.join(details)} |"
            )
    return "\n".join(lines) + "\n"


def plot(rows: list[dict], time_limit: float) -> None:
    def points(agent: str, key: str, values: tuple[int, ...], metric) -> list[tuple[float, float]]:
        result = []
        for value in values:
            sample = [metric(r) for r in rows if r["agente"] == agent and r[key] == value]
            result.append((statistics.mean(sample), statistics.pstdev(sample)))
        return result

    pct = placed_pct
    seconds = lambda row: elapsed(row, time_limit)  # noqa: E731
    for key, values, x_label in (("n", N_VALUES, "N (lado del tablero)"), ("k", K_VALUES, "K (colores)")):
        other = "todas las K" if key == "n" else "todos los N"
        line_chart(
            STUDY / f"colocadas_vs_{key}.svg",
            f"Fichas colocadas según {key.upper()} (promedio sobre {other})",
            x_label, "% de M colocado",
            [str(v) for v in values],
            {LABELS[a]: points(a, key, values, pct) for a in ("search", "evo")},
            y_max=100,
        )
        line_chart(
            STUDY / f"tiempo_vs_{key}.svg",
            f"Tiempo según {key.upper()} (promedio sobre {other})",
            x_label, "segundos",
            [str(v) for v in values],
            {LABELS[a]: points(a, key, values, seconds) for a in ("search", "evo")},
            y_max=time_limit * 1.2,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--time-limit", type=float, default=5.0)
    args = parser.parse_args()
    rows = run_battery(STUDY, cases(), SEEDS, args.time_limit)
    summary = summarize(rows, args.time_limit)
    (STUDY / "summary.md").write_text(summary, encoding="utf-8")
    plot(rows, args.time_limit)
    print(summary)


if __name__ == "__main__":
    main()
