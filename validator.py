"""validator.py

Independent validator for TileUp deterministic board game.

Usage::
    python validator.py <instance_file> <solution_file>

The validator reads the instance description, replays the sequence of moves
provided in the solution file and checks whether each placement is legal
according to the TileUp rules. It does **not** reuse the decision logic of the
agents (e.g., the ``play`` command in ``main.py``); instead it directly uses the
engine implementation from ``engine.py``.

Solution file format:
    <tile_index> <row> <col>
    ...
    # summary line (optional)

The script prints a concise report and exits with the same codes used by the
CLI (0 = victory, 1 = legal but incomplete/defeat, 2 = illegal move, 3 = usage
error, 4 = instance load error, 5 = solution parse error, 6 = argument error).
"""

import sys
from pathlib import Path
from typing import List, Tuple

from engine import TileUpEngine, IllegalActionError

def _positive_int(name: str, value: object) -> int:
    """Validate that *value* is a positive integer (>= 1)."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be an integer >= 1, got {value!r}")
    return value


def load_instance(path: Path) -> Tuple[int, int, List[Tuple[int, int]]]:
    """Parse a TileUp instance file.

    Returns ``(N, K, tiles)`` where ``tiles`` is a list of ``(color, value)``.
    Blank lines and anything after a ``#`` comment are ignored.
    """
    lines: List[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            lines.append(line)

    if len(lines) < 2:
        raise ValueError("Instance file must contain at least two header lines")

    header = lines[0].split()
    if len(header) != 2:
        raise ValueError("First line must contain N and K")
    n = _positive_int("N", int(header[0]))
    k = _positive_int("K", int(header[1]))

    m = _positive_int("M", int(lines[1]))
    body = lines[2:]
    if len(body) != m:
        raise ValueError(f"Expected {m} tile lines, found {len(body)}")

    tiles: List[Tuple[int, int]] = []
    for line in body:
        parts = line.split()
        if len(parts) != 2:
            raise ValueError(f"Invalid tile line: {line!r}")
        color = _positive_int("color", int(parts[0]))
        value = _positive_int("valor", int(parts[1]))
        if color > k:
            raise ValueError(f"Color {color} exceeds K={k}")
        tiles.append((color, value))
    return n, k, tiles


def parse_solution(path: Path) -> Tuple[List[Tuple[int, int, int]], str]:
    """Parse a solution file.

    Returns a tuple ``(moves, summary_line)`` where ``moves`` is a list of
    ``(tile_idx, row, col)`` and ``summary_line`` is the final comment line
    (without the leading ``#``).
    """
    moves: List[Tuple[int, int, int]] = []
    summary = ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            summary = stripped[1:].strip()
            continue
        parts = stripped.split()
        if len(parts) != 3:
            raise ValueError(f"Invalid move line: {raw!r}")
        idx, row, col = map(int, parts)
        moves.append((idx, row, col))
    return moves, summary


def occupied_cells(engine: TileUpEngine) -> int:
    """Count occupied cells on the board.

    The engine stores the board as a flat list ``colors`` of length N*N.
    A colour value of 0 means the cell is empty.
    """
    return sum(1 for c in engine.colors if c != 0)


def validate(instance_path: Path, solution_path: Path) -> None:
    """Run validation and print a human‑readable report."""
    try:
        n, k, tiles = load_instance(instance_path)
    except Exception as exc:
        print(f"ERROR loading instance: {exc}")
        sys.exit(4)

    try:
        moves, summary = parse_solution(solution_path)
    except Exception as exc:
        print(f"ERROR parsing solution: {exc}")
        sys.exit(5)

    engine = TileUpEngine(n, tiles, k=k)
    placed = 0
    legal = True
    illegal_reason = ""

    for idx, row, col in moves:
        if idx != placed:
            legal = False
            illegal_reason = f"Unexpected tile index {idx}, expected {placed}."
            break
        try:
            engine.apply_action(row, col)
            placed += 1
        except IllegalActionError as exc:
            legal = False
            illegal_reason = str(exc)
            break
        except Exception as exc:
            legal = False
            illegal_reason = f"Unexpected error: {exc}"
            break

    occupied = occupied_cells(engine)
    status = "LEGAL" if legal else "ILEGAL"
    print(status)
    if summary:
        print(f"Resumen solución: {summary}")
    if not legal:
        print(f"Motivo: {illegal_reason}")
    print("Tablero final:")
    print(engine.format_board())
    
    if not legal:
        print("RESULTADO: ILEGAL")
        sys.exit(2)
    if engine.is_victory():
        print(f"RESULTADO: VICTORIA ({placed}/{engine.m} fichas colocadas, {occupied} celdas ocupadas)")
        sys.exit(0)
    if engine.is_defeat():
        print(f"RESULTADO: DERROTA (tablero lleno, {placed}/{engine.m} fichas colocadas)")
        sys.exit(1)
    print(f"RESULTADO: INCOMPLETA (la solucion termina con celdas libres, {placed}/{engine.m} fichas colocadas)")
    sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python validator.py <instance_file> <solution_file>")
        sys.exit(6)
    validate(Path(sys.argv[1]), Path(sys.argv[2]))
