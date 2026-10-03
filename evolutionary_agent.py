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
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

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
