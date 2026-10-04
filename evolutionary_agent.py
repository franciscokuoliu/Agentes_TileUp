"""
Agente evolutivo para TileUp.

Representación indirecta: un individuo es un vector de pesos, uno por
característica de ``FEATURE_NAMES``. La política asociada asigna a cada
celda vacía el puntaje ``sum(peso_i * caracteristica_i)`` y coloca la ficha
actual en la celda de mayor puntaje. El algoritmo evolutivo optimiza los
pesos, no la secuencia de jugadas.

Propiedades de la representación:

* Toda partida generada es legal, porque solo se consideran celdas vacías.
* La longitud del individuo es independiente de N y de M.
* La política es determinista: el azar del agente se limita al ciclo
  evolutivo y se deriva de la semilla.

Algoritmo evolutivo (``evolve``):

* Aptitud: ``colocadas * (N^2 + 1) - ocupadas``. Como las celdas ocupadas
  nunca superan N^2, el orden coincide con el del concurso: primero más
  fichas colocadas y, ante empate, menos celdas ocupadas.
* Población inicial: el vector ``REFERENCE_WEIGHTS`` más individuos con pesos
  uniformes en ``[-WEIGHT_LIMIT, WEIGHT_LIMIT]``.
* Selección: torneo de tamaño ``tournament_size``.
* Variación: cruce uniforme (cada gen se toma de uno de los dos padres) con
  probabilidad ``crossover_rate``, y mutación gaussiana por gen con
  probabilidad ``mutation_rate`` y desviación ``mutation_sigma``. Los pesos
  se recortan a ``[-WEIGHT_LIMIT, WEIGHT_LIMIT]``.
* Reemplazo: generacional con elitismo; los ``elite`` mejores pasan intactos.
* Paro: ``max_generations`` generaciones, ``stall_generations`` generaciones
  sin mejora, o el límite de tiempo, lo que ocurra primero.

Determinismo: con la misma semilla, la secuencia de individuos generados es
la misma. Los criterios de paro por generaciones son deterministas; el
límite de tiempo actúa como salvaguarda y, si llega a cortar la ejecución,
el resultado depende de cuántas generaciones alcanzaron a completarse.
"""

from __future__ import annotations

import random
import time
from collections.abc import Sequence
from dataclasses import dataclass, field

from engine import TileUpEngine

#: Nombre de cada característica, en el mismo orden que los pesos.
FEATURE_NAMES: tuple[str, ...] = (
    "absorbe",          # fichas absorbidas por la fusión, |G| - 1
    "vecinos_otro",     # vecinos ocupados por fichas de otro color
    "vecinos_vacios",   # vecinos vacíos
    "borde",            # lados de la celda sobre el borde del tablero (0, 1 o 2)
    "reserva",          # vecinos vacíos si no hay fusión y el color está en la ventana
    "bloqueo",          # vecinos de otro color cuyo color está en la ventana
)

NUM_FEATURES = len(FEATURE_NAMES)

#: Pesos de referencia: priorizan la fusión y penalizan la adyacencia a otros colores.
REFERENCE_WEIGHTS: tuple[float, ...] = (10.0, -2.0, 0.5, 0.5, 1.0, -1.5)

#: Cota absoluta de cada peso. La política solo depende del orden de los
#: puntajes, así que acotar los pesos no reduce su capacidad expresiva.
WEIGHT_LIMIT = 10.0

#: Tamaño de la ventana de anticipación (fichas futuras) usada por "reserva" y "bloqueo".
DEFAULT_LOOKAHEAD = 4


@dataclass(frozen=True, slots=True)
class GameRecord:
    """Resultado de jugar una partida con una política.

    ``actions`` son las celdas elegidas, en el orden de la secuencia.
    ``placed`` es la cantidad de fichas colocadas, ``occupied`` las celdas
    ocupadas al terminar y ``highest`` el valor de la ficha mayor.
    """

    actions: tuple[tuple[int, int], ...]
    placed: int
    occupied: int
    highest: int
    victory: bool


def neighbor_table(n: int) -> tuple[tuple[int, ...], ...]:
    """Para cada celda (índice plano), los índices de sus vecinos ortogonales.

    Se precalcula una vez por partida para evitar comprobar bordes en cada
    evaluación de celda.
    """
    table = []
    for index in range(n * n):
        row, col = divmod(index, n)
        neighbors = []
        if row > 0:
            neighbors.append(index - n)
        if row + 1 < n:
            neighbors.append(index + n)
        if col > 0:
            neighbors.append(index - 1)
        if col + 1 < n:
            neighbors.append(index + 1)
        table.append(tuple(neighbors))
    return tuple(table)


def upcoming_colors(engine: TileUpEngine, lookahead: int) -> frozenset[int]:
    """Colores de las próximas ``lookahead`` fichas, sin contar la actual.

    La secuencia es conocida de antemano (problema completamente observable).
    """
    start = engine.tile_index + 1
    return frozenset(engine.tile_colors[start : start + lookahead])


def cell_features(
    engine: TileUpEngine,
    index: int,
    color: int,
    upcoming: frozenset[int],
    neighbors: tuple[int, ...],
) -> tuple[int, int, int, int, int, int]:
    """Vector de características de colocar una ficha ``color`` en ``index``.

    Invariante del motor: al inicio de cada turno no hay dos fichas del mismo
    color ortogonalmente adyacentes. Cada vecino del mismo color es entonces
    una componente de tamaño 1 y ``absorbe`` es igual a ``|G| - 1``.
    """
    colors = engine.colors
    same = other = empty = blocking = 0
    for neighbor in neighbors:
        neighbor_color = colors[neighbor]
        if neighbor_color == 0:
            empty += 1
        elif neighbor_color == color:
            same += 1
        else:
            other += 1
            if neighbor_color in upcoming:
                blocking += 1
    edges = 4 - len(neighbors)
    reserve = empty if same == 0 and color in upcoming else 0
    return (same, other, empty, edges, reserve, blocking)


def check_weights(weights: Sequence[float]) -> tuple[float, ...]:
    """Valida que haya un peso numérico por característica."""
    if len(weights) != NUM_FEATURES:
        raise ValueError(
            f"Se esperan {NUM_FEATURES} pesos ({', '.join(FEATURE_NAMES)}), "
            f"no {len(weights)}."
        )
    return tuple(float(weight) for weight in weights)


def choose_cell(
    engine: TileUpEngine,
    weights: tuple[float, ...],
    neighbors_of: tuple[tuple[int, ...], ...],
    lookahead: int = DEFAULT_LOOKAHEAD,
) -> int:
    """Índice plano de la celda vacía con mayor puntaje para la ficha actual.

    ``puntaje = sum(peso_i * caracteristica_i)``. Ante un empate gana la
    primera celda en orden fila-mayor, lo que hace la decisión determinista.
    """
    color = engine.tile_colors[engine.tile_index]
    upcoming = upcoming_colors(engine, lookahead)
    colors = engine.colors
    best_index = -1
    best_score = float("-inf")
    for index in range(engine.size):
        if colors[index] != 0:
            continue
        features = cell_features(engine, index, color, upcoming, neighbors_of[index])
        score = 0.0
        for weight, value in zip(weights, features):
            score += weight * value
        if score > best_score:
            best_score = score
            best_index = index
    return best_index


def play(
    n: int,
    tiles: Sequence[tuple[int, int]],
    k: int | None,
    weights: Sequence[float],
    lookahead: int = DEFAULT_LOOKAHEAD,
) -> GameRecord:
    """Juega una partida completa siguiendo la política definida por ``weights``.

    Termina en victoria (M fichas colocadas) o en derrota (tablero lleno con
    fichas pendientes). En ambos casos devuelve las jugadas realizadas, de
    modo que la solución parcial también puede escribirse.

    No usa azar: los mismos pesos producen siempre la misma partida.
    """
    weights = check_weights(weights)
    engine = TileUpEngine(n, tiles, k=k)
    neighbors_of = neighbor_table(engine.n)
    actions: list[tuple[int, int]] = []
    while not engine.is_terminal():
        index = choose_cell(engine, weights, neighbors_of, lookahead)
        row, col = divmod(index, engine.n)
        engine.apply_action(row, col)
        actions.append((row, col))
    return GameRecord(
        actions=tuple(actions),
        placed=engine.tile_index,
        occupied=engine.size - engine.empty_count,
        highest=max(engine.values, default=0),
        victory=engine.is_victory(),
    )


def fitness(record: GameRecord, n: int) -> int:
    """Aptitud de una partida en un tablero de lado ``n``.

    ``colocadas * (n^2 + 1) - ocupadas``: una ficha colocada adicional
    siempre supera cualquier diferencia en celdas ocupadas.
    """
    return record.placed * (n * n + 1) - record.occupied


@dataclass(frozen=True, slots=True)
class EvolutionConfig:
    """Parámetros del algoritmo evolutivo."""

    population_size: int = 30
    tournament_size: int = 3
    crossover_rate: float = 0.9
    mutation_rate: float = 0.3
    mutation_sigma: float = 1.5
    elite: int = 2
    max_generations: int = 100
    stall_generations: int = 25
    lookahead: int = DEFAULT_LOOKAHEAD

    def __post_init__(self) -> None:
        if self.population_size < 2:
            raise ValueError("population_size debe ser >= 2.")
        if not 1 <= self.tournament_size <= self.population_size:
            raise ValueError("tournament_size debe estar en 1..population_size.")
        if not 0 <= self.elite < self.population_size:
            raise ValueError("elite debe estar en 0..population_size-1.")
        if not 0.0 <= self.crossover_rate <= 1.0:
            raise ValueError("crossover_rate debe estar en [0, 1].")
        if not 0.0 <= self.mutation_rate <= 1.0:
            raise ValueError("mutation_rate debe estar en [0, 1].")
        if self.mutation_sigma <= 0:
            raise ValueError("mutation_sigma debe ser > 0.")
        if self.max_generations < 0 or self.stall_generations < 1:
            raise ValueError("max_generations >= 0 y stall_generations >= 1.")
        if self.lookahead < 0:
            raise ValueError("lookahead debe ser >= 0.")


@dataclass(frozen=True, slots=True)
class EvolutionResult:
    """Mejor partida encontrada y estadísticas de la ejecución.

    ``evaluations`` es la medida de esfuerzo: partidas simuladas (las
    repetidas se resuelven con caché y no cuentan). ``history`` guarda la
    mejor aptitud al cierre de cada generación, empezando por la inicial.
    ``stop_reason`` es ``generaciones``, ``estancamiento``, ``tiempo`` u
    ``optimo``.
    """

    record: GameRecord
    weights: tuple[float, ...]
    fitness: int
    evaluations: int
    generations: int
    stop_reason: str
    history: tuple[int, ...] = field(default=())


class _Deadline(Exception):
    """Se alcanzó el límite de tiempo durante la evaluación."""


def evolve(
    n: int,
    tiles: Sequence[tuple[int, int]],
    k: int | None,
    seed: int,
    time_limit: float,
    config: EvolutionConfig | None = None,
) -> EvolutionResult:
    """Busca los pesos de la política que maximizan la aptitud.

    Toda fuente de azar es un ``random.Random(seed)`` local. El primer
    individuo evaluado es ``REFERENCE_WEIGHTS``, de modo que siempre existe
    una partida completa que devolver aunque el tiempo sea muy corto.

    Una evaluación nueva solo empieza si la más lenta observada hasta el
    momento cabe en el tiempo restante; así la ejecución no rebasa el límite
    por la duración de la última partida simulada.
    """
    if time_limit <= 0:
        raise ValueError("time_limit debe ser > 0.")
    config = config or EvolutionConfig()
    tiles = tuple(tiles)
    deadline = time.monotonic() + time_limit
    rng = random.Random(seed)
    cache: dict[tuple[float, ...], tuple[int, GameRecord]] = {}
    best: tuple[int, tuple[float, ...], GameRecord] | None = None
    target = (len(tiles) * (n * n + 1) - 1) if tiles else 0

    slowest = 0.0

    def evaluate(weights: tuple[float, ...], forced: bool = False) -> int:
        nonlocal best, slowest
        cached = cache.get(weights)
        if cached is not None:
            return cached[0]
        started = time.monotonic()
        if not forced and started + slowest >= deadline:
            raise _Deadline
        record = play(n, tiles, k, weights, config.lookahead)
        slowest = max(slowest, time.monotonic() - started)
        score = fitness(record, n)
        cache[weights] = (score, record)
        if best is None or score > best[0]:
            best = (score, weights, record)
        return score

    def random_individual() -> tuple[float, ...]:
        return tuple(rng.uniform(-WEIGHT_LIMIT, WEIGHT_LIMIT) for _ in range(NUM_FEATURES))

    def tournament(scored: list[tuple[int, tuple[float, ...]]]) -> tuple[float, ...]:
        contenders = rng.sample(scored, config.tournament_size)
        return max(contenders, key=lambda item: item[0])[1]

    def crossover(a: tuple[float, ...], b: tuple[float, ...]) -> tuple[float, ...]:
        if rng.random() >= config.crossover_rate:
            return a
        return tuple(x if rng.random() < 0.5 else y for x, y in zip(a, b))

    def mutate(weights: tuple[float, ...]) -> tuple[float, ...]:
        mutated = []
        for weight in weights:
            if rng.random() < config.mutation_rate:
                weight += rng.gauss(0.0, config.mutation_sigma)
                weight = max(-WEIGHT_LIMIT, min(WEIGHT_LIMIT, weight))
            mutated.append(weight)
        return tuple(mutated)

    population = [tuple(REFERENCE_WEIGHTS)]
    population += [random_individual() for _ in range(config.population_size - 1)]

    history: list[int] = []
    generations = 0
    stall = 0
    stop_reason = "generaciones"
    try:
        scored = [(evaluate(population[0], forced=True), population[0])]
        scored += [(evaluate(ind), ind) for ind in population[1:]]
        history.append(best[0])
        while True:
            if best[0] >= target:
                stop_reason = "optimo"
                break
            if generations >= config.max_generations:
                stop_reason = "generaciones"
                break
            if stall >= config.stall_generations:
                stop_reason = "estancamiento"
                break
            scored.sort(key=lambda item: item[0], reverse=True)
            next_population = [ind for _score, ind in scored[: config.elite]]
            while len(next_population) < config.population_size:
                child = mutate(crossover(tournament(scored), tournament(scored)))
                next_population.append(child)
            previous_best = best[0]
            scored = [(evaluate(ind), ind) for ind in next_population]
            generations += 1
            history.append(best[0])
            stall = 0 if best[0] > previous_best else stall + 1
    except _Deadline:
        stop_reason = "tiempo"

    score, weights, record = best
    return EvolutionResult(
        record=record,
        weights=weights,
        fitness=score,
        evaluations=len(cache),
        generations=generations,
        stop_reason=stop_reason,
        history=tuple(history),
    )
