"""Motor determinista de TileUp.

El tablero es una matriz N x N, inicialmente vacía. Hay una secuencia fija
de M fichas (color, valor) que se consumen en orden: el agente solo elige
la celda vacía donde colocar la ficha actual. No hay gravedad.

Tras colocar una ficha en p se calcula la componente conexa ortogonal del
mismo color que contiene a p. Si tiene tamaño >= 2, todas esas fichas se
retiran y en p queda una sola ficha del mismo color cuyo valor es la suma.
La fusión no se repite en el mismo turno.

Victoria: se colocaron las M fichas.
Derrota: quedan fichas y el tablero está lleno.

Los agentes deben ramificar con ``clone()`` y luego ``apply_action``.
``clone`` copia solo los arreglos del tablero; la secuencia de fichas es
inmutable y se comparte. No usa ``copy.deepcopy``.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass


class IllegalActionError(ValueError):
    """La acción no es aplicable al estado actual."""


@dataclass(frozen=True, slots=True)
class MoveResult:
    """Efecto de una colocación ya aplicada."""

    row: int
    col: int
    color: int
    placed_value: int
    merged: bool
    component_size: int
    value: int


def _positive_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} debe ser un entero >= 1, no {value!r}.")
    return value


def _parse_tile(tile: object, k: int | None) -> tuple[int, int]:
    if isinstance(tile, (str, bytes)) or not isinstance(tile, Sequence) or len(tile) != 2:
        raise ValueError(f"Cada ficha debe ser un par (color, valor), no {tile!r}.")
    color = _positive_int("color", tile[0])
    value = _positive_int("valor", tile[1])
    if k is not None and color > k:
        raise ValueError(f"El color {color} está fuera del rango 1..{k}.")
    return color, value


class TileUpEngine:
    """Estado de una partida de TileUp y las reglas que lo actualizan.

    Parámetros
    ----------
    n:
        Lado del tablero. Las coordenadas son 0-indexadas, fila y columna
        en ``0 .. n-1``.
    tiles:
        Secuencia fija de fichas ``(color, valor)``. Se copia al construir;
        el llamador puede modificar después su propia lista.
    k:
        Número de colores admitidos (1..k). Si es ``None``, se infiere como
        el color máximo de ``tiles`` (o 0 si no hay fichas).

    Representación
    --------------
    ``colors`` y ``values`` son listas planas de longitud ``n * n``.
    El índice de ``(r, c)`` es ``r * n + c``. Un color 0 indica celda vacía
    (y en ese caso el valor también es 0). Se pueden leer en una heurística;
    no deben escribirse: el único mutador válido es ``apply_action``.

    ``tile_colors`` y ``tile_values`` describen la secuencia completa y son
    compartidos por todos los clones de la misma partida.
    """

    __slots__ = (
        "n",
        "k",
        "m",
        "size",
        "tile_colors",
        "tile_values",
        "tile_index",
        "_empty",
        "colors",
        "values",
    )

    __hash__ = None

    def __init__(
        self,
        n: int,
        tiles: Iterable[tuple[int, int]],
        k: int | None = None,
    ) -> None:
        self.n = _positive_int("n", n)
        if isinstance(tiles, (str, bytes)):
            raise TypeError("tiles debe ser una secuencia de pares (color, valor).")
        if k is not None:
            k = _positive_int("k", k)
        parsed = tuple(_parse_tile(tile, k) for tile in tiles)
        if k is None:
            k = max((color for color, _value in parsed), default=0)
        self.k = k
        self.m = len(parsed)
        self.size = self.n * self.n
        self.tile_colors = tuple(color for color, _value in parsed)
        self.tile_values = tuple(value for _color, value in parsed)
        self.tile_index = 0
        self._empty = self.size
        self.colors = [0] * self.size
        self.values = [0] * self.size

    def clone(self) -> TileUpEngine:
        """Copia independiente del estado, en O(N^2), sin ``deepcopy``.

        La secuencia de fichas no se duplica: es inmutable y común a la
        partida. Mutar el clon no altera el original.
        """
        other = object.__new__(type(self))
        other.n = self.n
        other.k = self.k
        other.m = self.m
        other.size = self.size
        other.tile_colors = self.tile_colors
        other.tile_values = self.tile_values
        other.tile_index = self.tile_index
        other._empty = self._empty
        other.colors = self.colors[:]
        other.values = self.values[:]
        return other

    def copy(self) -> TileUpEngine:
        """Alias de ``clone``."""
        return self.clone()

    def __copy__(self) -> TileUpEngine:
        return self.clone()

    def __deepcopy__(self, memo: dict[int, object]) -> TileUpEngine:
        cloned = self.clone()
        memo[id(self)] = cloned
        return cloned

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TileUpEngine):
            return NotImplemented
        return (
            self.n == other.n
            and self.k == other.k
            and self.tile_colors == other.tile_colors
            and self.tile_values == other.tile_values
            and self.tile_index == other.tile_index
            and self._empty == other._empty
            and self.colors == other.colors
            and self.values == other.values
        )

    def __repr__(self) -> str:
        return (
            f"TileUpEngine(n={self.n}, k={self.k}, "
            f"tile_index={self.tile_index}/{self.m}, empty={self._empty})"
        )

    @property
    def empty_count(self) -> int:
        return self._empty

    @property
    def tiles_remaining(self) -> int:
        return self.m - self.tile_index

    def next_tile(self) -> tuple[int, int] | None:
        """Ficha que se colocará en la próxima acción, o ``None`` si no queda."""
        index = self.tile_index
        if index >= self.m:
            return None
        return (self.tile_colors[index], self.tile_values[index])

    def is_victory(self) -> bool:
        return self.tile_index >= self.m

    def is_defeat(self) -> bool:
        return self._empty == 0 and self.tile_index < self.m

    def is_terminal(self) -> bool:
        return self.is_victory() or self.is_defeat()

    def is_empty(self, row: int, col: int) -> bool:
        return self.colors[row * self.n + col] == 0

    def get_cell(self, row: int, col: int) -> tuple[int, int] | None:
        index = row * self.n + col
        color = self.colors[index]
        if color == 0:
            return None
        return (color, self.values[index])

    def get_valid_actions(self) -> list[tuple[int, int]]:
        """Celdas vacías en orden fila-mayor. Vacío si la partida terminó.

        El factor de ramificación es exactamente el número de celdas vacías.
        """
        if self.tile_index >= self.m or self._empty == 0:
            return []
        n = self.n
        colors = self.colors
        actions: list[tuple[int, int]] = []
        append = actions.append
        index = 0
        for row in range(n):
            for col in range(n):
                if colors[index] == 0:
                    append((row, col))
                index += 1
        return actions

    def apply_action(self, row: int, col: int) -> MoveResult:
        """Coloca la ficha actual en ``(row, col)``, fusiona una vez y avanza.

        La componente G es la de fichas del mismo color conectadas por
        arriba, abajo, izquierda o derecha que contiene a la celda recién
        ocupada. Si ``|G| >= 2``, G desaparece y en ``(row, col)`` queda la
        suma. Si ``|G| == 1``, el tablero no cambia más. No hay una segunda
        pasada de fusión en el mismo turno.
        """
        if isinstance(row, bool) or not isinstance(row, int):
            raise IllegalActionError(f"La fila debe ser un entero, no {row!r}.")
        if isinstance(col, bool) or not isinstance(col, int):
            raise IllegalActionError(f"La columna debe ser un entero, no {col!r}.")
        if self.is_victory():
            raise IllegalActionError("La partida ya terminó en victoria.")
        if self.is_defeat():
            raise IllegalActionError(
                "La partida ya terminó en derrota: el tablero está lleno."
            )
        n = self.n
        if row < 0 or col < 0 or row >= n or col >= n:
            raise IllegalActionError(
                f"La celda ({row}, {col}) está fuera del tablero {n}x{n}."
            )
        index = row * n + col
        if self.colors[index] != 0:
            raise IllegalActionError(f"La celda ({row}, {col}) está ocupada.")

        color = self.tile_colors[self.tile_index]
        placed_value = self.tile_values[self.tile_index]
        self.tile_index += 1
        self.colors[index] = color
        self.values[index] = placed_value
        self._empty -= 1

        cells, total = self._component_from(index, color)
        merged = len(cells) >= 2
        if merged:
            colors = self.colors
            values = self.values
            for cell in cells:
                colors[cell] = 0
                values[cell] = 0
            colors[index] = color
            values[index] = total
            self._empty += len(cells) - 1
            resulting = total
        else:
            resulting = placed_value

        return MoveResult(
            row=row,
            col=col,
            color=color,
            placed_value=placed_value,
            merged=merged,
            component_size=len(cells),
            value=resulting,
        )

    def _component_from(self, start: int, color: int) -> tuple[list[int], int]:
        """Índices de la componente de ``color`` que contiene a ``start``, y su suma.

        Recorre la componente completa (no solo los vecinos directos). Con
        estas reglas, al empezar un turno no hay dos fichas del mismo color
        ortogonalmente adyacentes, así que G tiene como máximo 5 celdas
        (la ficha nueva y sus vecinas). La inundación sigue siendo la regla
        correcta si ese invariante no se cumpliera.
        """
        n = self.n
        colors = self.colors
        values = self.values
        stack = [start]
        seen = {start}
        cells = [start]

        def consider(index: int) -> None:
            if index in seen or colors[index] != color:
                return
            seen.add(index)
            stack.append(index)
            cells.append(index)

        while stack:
            current = stack.pop()
            row, col = divmod(current, n)
            if row > 0:
                consider(current - n)
            if row + 1 < n:
                consider(current + n)
            if col > 0:
                consider(current - 1)
            if col + 1 < n:
                consider(current + 1)

        total = 0
        for cell in cells:
            total += values[cell]
        return cells, total

    def get_board_state(self) -> tuple[tuple[tuple[int, int] | None, ...], ...]:
        """Fotografía inmutable del tablero: ``None`` o ``(color, valor)``."""
        n = self.n
        colors = self.colors
        values = self.values
        rows: list[tuple[tuple[int, int] | None, ...]] = []
        index = 0
        for _row in range(n):
            row_cells: list[tuple[int, int] | None] = []
            for _col in range(n):
                color = colors[index]
                if color == 0:
                    row_cells.append(None)
                else:
                    row_cells.append((color, values[index]))
                index += 1
            rows.append(tuple(row_cells))
        return tuple(rows)

    def format_board(self) -> str:
        """Tablero legible: ``.`` en vacío y ``color:valor`` en ocupado."""
        n = self.n
        rendered: list[str] = []
        index = 0
        for _row in range(n):
            for _col in range(n):
                color = self.colors[index]
                if color == 0:
                    rendered.append(".")
                else:
                    rendered.append(f"{color}:{self.values[index]}")
                index += 1
        width = max(len(token) for token in rendered)
        lines = []
        for row in range(n):
            chunk = rendered[row * n : (row + 1) * n]
            lines.append(" ".join(token.rjust(width) for token in chunk))
        return "\n".join(lines)

    def state_key(self) -> tuple[int, int, tuple[int, ...], tuple[int, ...]]:
        """Clave hasheable para tablas de transposición.

        Solo es válida entre estados de la misma partida (mismo ``n`` y la
        misma secuencia de fichas). El índice de ficha ya determina el
        sufijo que falta por colocar.
        """
        return (self.n, self.tile_index, tuple(self.colors), tuple(self.values))

    def check_invariants(self) -> None:
        """Lanza ``AssertionError`` si el estado interno es incoherente.

        Pensado para pruebas. No forma parte del bucle de búsqueda.
        """
        if len(self.colors) != self.size or len(self.values) != self.size:
            raise AssertionError("El tamaño del tablero no coincide con n^2.")
        if not 0 <= self.tile_index <= self.m:
            raise AssertionError("Índice de ficha fuera de rango.")
        empties = 0
        for index, color in enumerate(self.colors):
            if color == 0:
                empties += 1
                if self.values[index] != 0:
                    raise AssertionError(f"Valor fantasma en la celda vacía {index}.")
                continue
            if color < 1 or (self.k >= 1 and color > self.k):
                raise AssertionError(f"Color inválido en la celda {index}: {color}.")
            if self.values[index] < 1:
                raise AssertionError(f"Valor inválido en la celda {index}.")
        if empties != self._empty:
            raise AssertionError(
                f"Contador de vacías ({self._empty}) != celdas vacías ({empties})."
            )
        n = self.n
        for index, color in enumerate(self.colors):
            if color == 0:
                continue
            row, col = divmod(index, n)
            if col + 1 < n and self.colors[index + 1] == color:
                raise AssertionError(
                    "Hay dos fichas del mismo color ortogonalmente adyacentes."
                )
            if row + 1 < n and self.colors[index + n] == color:
                raise AssertionError(
                    "Hay dos fichas del mismo color ortogonalmente adyacentes."
                )


GameState = TileUpEngine
