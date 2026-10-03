"""Agente de búsqueda para TileUp.

Backtracking en profundidad sobre las celdas vacías. Una victoria coloca
exactamente las M fichas, así que la búsqueda decide si esa secuencia cabe,
no cuál camino es más corto. No modifica el estado que recibe: cada intento
sale de ``clone()`` y ``apply_action``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from engine import TileUpEngine


class _Deadline(Exception):
    """La búsqueda superó el instante límite."""


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Plan ganador, o la razón por la que no se devolvió uno."""

    status: str
    actions: tuple[tuple[int, int], ...]
    nodes: int

    @property
    def solved(self) -> bool:
        return self.status == "victory"


class SearchAgent:
    """Busca una secuencia de celdas que coloque todas las fichas.

    ``timeout`` es el límite en segundos cuando ``search`` no recibe un
    ``deadline``. El reloj es ``time.monotonic``.
    """

    def __init__(self, timeout: float = 5.0) -> None:
        if timeout <= 0:
            raise ValueError("timeout debe ser > 0.")
        self.timeout = timeout

    def search(
        self,
        state: TileUpEngine,
        deadline: float | None = None,
    ) -> SearchResult:
        """Devuelve un plan desde ``state`` hasta la victoria.

        ``status`` es ``victory``, ``unsolvable`` o ``timeout``. Un tiempo
        agotado no se guarda como fracaso: la instancia puede seguir teniendo
        solución.
        """
        if deadline is None:
            deadline = time.monotonic() + self.timeout
        failed: set[tuple[object, ...]] = set()
        nodes = 0

        def dfs(node: TileUpEngine) -> tuple[tuple[int, int], ...] | None:
            nonlocal nodes
            nodes += 1
            if time.monotonic() >= deadline:
                raise _Deadline
            if node.is_victory():
                return ()
            if node.is_defeat():
                return None
            key = node.state_key()
            if key in failed:
                return None
            for row, col in self._ordered_actions(node):
                child = node.clone()
                child.apply_action(row, col)
                tail = dfs(child)
                if tail is not None:
                    return ((row, col),) + tail
            failed.add(key)
            return None

        try:
            plan = dfs(state)
        except _Deadline:
            return SearchResult("timeout", (), nodes)
        if plan is None:
            return SearchResult("unsolvable", (), nodes)
        return SearchResult("victory", plan, nodes)

    def format_solution(
        self,
        actions: tuple[tuple[int, int], ...] | list[tuple[int, int]],
        engine: TileUpEngine,
    ) -> str:
        """Solución: una jugada ``indice fila columna`` y el resumen final.

        El resumen es ``# colocadas=N ocupadas=C mayor=V``, con las fichas
        colocadas, las celdas ocupadas al terminar y el mayor valor del tablero.
        """
        lines = [f"{index} {row} {col}" for index, (row, col) in enumerate(actions)]
        occupied = sum(color != 0 for color in engine.colors)
        highest = max(engine.values, default=0)
        lines.append(f"# colocadas={engine.tile_index} ocupadas={occupied} mayor={highest}")
        return "\n".join(lines) + "\n"

    def _ordered_actions(self, state: TileUpEngine) -> list[tuple[int, int]]:
        """Primero las celdas que fusionan con más vecinas del color actual."""
        tile = state.next_tile()
        actions = state.get_valid_actions()
        if tile is None or not actions:
            return actions
        color = tile[0]
        return sorted(actions, key=lambda action: self._same_color_neighbors(state, action, color), reverse=True)

    @staticmethod
    def _same_color_neighbors(
        state: TileUpEngine,
        action: tuple[int, int],
        color: int,
    ) -> int:
        row, col = action
        n = state.n
        colors = state.colors
        index = row * n + col
        count = 0
        if row > 0 and colors[index - n] == color:
            count += 1
        if row + 1 < n and colors[index + n] == color:
            count += 1
        if col > 0 and colors[index - 1] == color:
            count += 1
        if col + 1 < n and colors[index + 1] == color:
            count += 1
        return count
