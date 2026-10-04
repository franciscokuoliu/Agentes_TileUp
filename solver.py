"""Comando ``solve``: ejecuta un agente sobre una instancia y escribe la solución.

Contrato de ejecución::

    python main.py solve --instance RUTA --agent {search,evo} --seed S --time-limit T

Siempre escribe el archivo de solución, también en derrota o si se agota el
tiempo, con las colocaciones alcanzadas. Las métricas que se imprimen se
recalculan reproduciendo la solución sobre el motor, de modo que coinciden
con lo que reporta el validador.

Códigos de salida: ``0`` si el agente terminó y se escribió la solución
(gane o pierda la partida), ``3`` ante un error de entrada.
"""

from __future__ import annotations

import argparse
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from engine import TileUpEngine
from evolutionary_agent import FEATURE_NAMES, EvolutionConfig, evolve
from search_agent import SearchAgent

DEFAULT_TIME_LIMIT = 10.0
DEFAULT_OUTPUT = "solucion.txt"


@dataclass(frozen=True, slots=True)
class Metrics:
    """Métricas de una solución reproducida sobre el motor."""

    placed: int
    occupied: int
    highest: int
    victory: bool
    board: str


def add_solve_arguments(parser: argparse.ArgumentParser) -> None:
    """Argumentos propios de ``solve`` (los de la instancia los agrega ``main``)."""
    parser.add_argument("--agent", required=True, choices=("search", "evo"), help="Agente a ejecutar.")
    parser.add_argument("--seed", type=int, default=0, help="Semilla de toda fuente de azar (default: 0).")
    parser.add_argument(
        "--time-limit",
        type=float,
        default=DEFAULT_TIME_LIMIT,
        help=f"Límite de tiempo en segundos (default: {DEFAULT_TIME_LIMIT}).",
    )
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help=f"Archivo de solución (default: {DEFAULT_OUTPUT}).")

    view = parser.add_argument_group("visualización")
    view.add_argument("--show-board", action="store_true", help="Imprime el tablero final.")
    view.add_argument(
        "--show-progress",
        action="store_true",
        help="Evolutivo: imprime las generaciones en que mejoró la mejor partida.",
    )
    view.add_argument("--history-csv", help="Evolutivo: guarda la mejor aptitud por generación en un CSV.")

    defaults = EvolutionConfig()
    evo = parser.add_argument_group("parámetros del agente evolutivo")
    evo.add_argument("--population", type=int, default=defaults.population_size, help="Tamaño de la población.")
    evo.add_argument("--generations", type=int, default=defaults.max_generations, help="Máximo de generaciones.")
    evo.add_argument("--stall", type=int, default=defaults.stall_generations, help="Generaciones sin mejora antes de parar.")
    evo.add_argument("--tournament", type=int, default=defaults.tournament_size, help="Tamaño del torneo.")
    evo.add_argument("--elite", type=int, default=defaults.elite, help="Individuos que pasan intactos.")
    evo.add_argument("--crossover-rate", type=float, default=defaults.crossover_rate, help="Probabilidad de cruce.")
    evo.add_argument("--mutation-rate", type=float, default=defaults.mutation_rate, help="Probabilidad de mutar cada peso.")
    evo.add_argument("--mutation-sigma", type=float, default=defaults.mutation_sigma, help="Desviación de la mutación gaussiana.")
    evo.add_argument("--lookahead", type=int, default=defaults.lookahead, help="Fichas futuras que mira la política.")


def evolution_config(args: argparse.Namespace) -> EvolutionConfig:
    return EvolutionConfig(
        population_size=args.population,
        tournament_size=args.tournament,
        crossover_rate=args.crossover_rate,
        mutation_rate=args.mutation_rate,
        mutation_sigma=args.mutation_sigma,
        elite=args.elite,
        max_generations=args.generations,
        stall_generations=args.stall,
        lookahead=args.lookahead,
    )


def replay_metrics(
    n: int,
    tiles: Sequence[tuple[int, int]],
    k: int | None,
    actions: Sequence[tuple[int, int]],
) -> Metrics:
    """Reproduce ``actions`` sobre un motor nuevo y mide el resultado."""
    engine = TileUpEngine(n, tiles, k=k)
    for row, col in actions:
        engine.apply_action(row, col)
    return Metrics(
        placed=engine.tile_index,
        occupied=engine.size - engine.empty_count,
        highest=max(engine.values, default=0),
        victory=engine.is_victory(),
        board=engine.format_board(),
    )


def format_solution(actions: Sequence[tuple[int, int]], metrics: Metrics) -> str:
    """Formato de la especificación: ``indice fila columna`` y línea resumen."""
    lines = [f"{index} {row} {col}" for index, (row, col) in enumerate(actions)]
    lines.append(f"# colocadas={metrics.placed} ocupadas={metrics.occupied} mayor={metrics.highest}")
    return "\n".join(lines) + "\n"


def decode_fitness(score: int, n: int) -> tuple[int, int]:
    """Inversa de ``fitness``: devuelve ``(colocadas, ocupadas)``."""
    base = n * n + 1
    placed = -(-score // base)
    return placed, placed * base - score


def run_solve(
    n: int,
    k: int | None,
    tiles: Sequence[tuple[int, int]],
    args: argparse.Namespace,
    out,
) -> int:
    """Ejecuta el agente pedido, escribe la solución e imprime las métricas."""
    if args.time_limit <= 0:
        raise ValueError("--time-limit debe ser > 0.")
    tiles = list(tiles)
    extra: list[str] = []
    started = time.monotonic()
    if args.agent == "evo":
        result = evolve(n, tiles, k, args.seed, args.time_limit, evolution_config(args))
        elapsed = time.monotonic() - started
        actions = result.record.actions
        effort = f"{result.evaluations} evaluaciones"
        extra.append(f"generaciones={result.generations} paro={result.stop_reason}")
        extra.append(
            "pesos: " + " ".join(f"{name}={weight:.2f}" for name, weight in zip(FEATURE_NAMES, result.weights))
        )
    else:
        engine = TileUpEngine(n, tiles, k=k)
        found = SearchAgent(timeout=args.time_limit).search(engine)
        elapsed = time.monotonic() - started
        actions = found.actions
        effort = f"{found.nodes} nodos"
        extra.append(f"estado_busqueda={found.status}")
        result = None

    metrics = replay_metrics(n, tiles, k, actions)
    Path(args.output).write_text(format_solution(actions, metrics), encoding="utf-8")

    print(f"agente={args.agent} semilla={args.seed} limite={args.time_limit}s", file=out)
    print(f"colocadas={metrics.placed} ocupadas={metrics.occupied} mayor={metrics.highest}", file=out)
    print(f"tiempo={elapsed:.3f}s esfuerzo={effort}", file=out)
    print(f"resultado={'victoria' if metrics.victory else 'derrota'}", file=out)
    for line in extra:
        print(line, file=out)
    print(f"solucion={args.output}", file=out)

    if result is not None and args.show_progress:
        print("progreso (generación: colocadas/ocupadas):", file=out)
        last = None
        for generation, score in enumerate(result.history):
            if score != last:
                placed, occupied = decode_fitness(score, n)
                print(f"  gen {generation:4d}: {placed}/{len(tiles)} fichas, {occupied} ocupadas", file=out)
                last = score
    if result is not None and args.history_csv:
        rows = ["generacion,aptitud,colocadas,ocupadas"]
        for generation, score in enumerate(result.history):
            placed, occupied = decode_fitness(score, n)
            rows.append(f"{generation},{score},{placed},{occupied}")
        Path(args.history_csv).write_text("\n".join(rows) + "\n", encoding="utf-8")
    if args.show_board:
        print(metrics.board, file=out)
    return 0
