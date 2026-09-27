"""Punto de entrada de TileUp.

Lee la instancia, muestra las reglas con ejemplos fijos o aplica una
secuencia de celdas sobre el motor. Las coordenadas son 0-indexadas.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from engine import IllegalActionError, TileUpEngine


@dataclass
class PlayResult:
    status: str
    steps: int
    engine: TileUpEngine
    message: str


def parse_tiles(text: str) -> list[tuple[int, int]]:
    """Parsea ``color:valor`` separados por comas. Ejemplo: ``1:2,1:5,2:4``."""
    text = text.strip()
    if not text:
        return []
    tiles: list[tuple[int, int]] = []
    for part in text.split(","):
        piece = part.strip()
        if ":" not in piece:
            raise ValueError(f"Ficha mal formada {piece!r}. Use color:valor.")
        color_text, value_text = piece.split(":", 1)
        tiles.append((int(color_text), int(value_text)))
    return tiles


def parse_actions(text: str) -> list[tuple[int, int]]:
    """Parsea ``fila,columna`` separados por espacio o punto y coma."""
    text = text.strip()
    if not text:
        return []
    actions: list[tuple[int, int]] = []
    for part in text.replace(";", " ").split():
        if "," not in part:
            raise ValueError(f"Acción mal formada {part!r}. Use fila,columna.")
        row_text, col_text = part.split(",", 1)
        actions.append((int(row_text), int(col_text)))
    return actions


def load_instance(path: Path) -> tuple[int, int, list[tuple[int, int]]]:
    """Carga un archivo de instancia.

    Formato::

        N K
        M
        color valor
        ...

    Se ignoran líneas en blanco y todo lo que sigue a ``#``.
    """
    lines: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            lines.append(line)
    if len(lines) < 2:
        raise ValueError("Instancia incompleta: se esperan al menos las líneas 'N K' y M.")
    header = lines[0].split()
    if len(header) != 2:
        raise ValueError("La primera línea debe ser 'N K'.")
    n = int(header[0])
    k = int(header[1])
    m = int(lines[1])
    body = lines[2:]
    if len(body) != m:
        raise ValueError(f"Se anunciaron {m} fichas y hay {len(body)}.")
    tiles: list[tuple[int, int]] = []
    for line in body:
        parts = line.split()
        if len(parts) != 2:
            raise ValueError(f"Ficha mal formada: {line!r}.")
        tiles.append((int(parts[0]), int(parts[1])))
    return n, k, tiles


def resolve_instance(args: argparse.Namespace) -> tuple[int, int | None, list[tuple[int, int]]]:
    has_inline = args.n is not None or args.tiles is not None or args.k is not None
    if args.instance and has_inline:
        raise ValueError("Use --instance o los parámetros --n/--k/--tiles, no ambos.")
    if args.instance:
        n, k, tiles = load_instance(Path(args.instance))
        return n, k, tiles
    if args.n is None or args.tiles is None:
        raise ValueError("Indique --instance o bien --n y --tiles.")
    return args.n, args.k, parse_tiles(args.tiles)


def play_first_cells(engine: TileUpEngine, verbose: bool = False, out=None) -> PlayResult:
    """Coloca siempre la primera celda libre, en orden fila-mayor, hasta terminar."""
    out = out or sys.stdout
    steps = 0
    while not engine.is_terminal():
        actions = engine.get_valid_actions()
        if not actions:
            break
        row, col = actions[0]
        move = engine.apply_action(row, col)
        steps += 1
        if verbose:
            detail = _move_detail(move)
            print(
                f"Paso {steps}: ({row},{col}) ficha {move.color}:{move.placed_value} {detail}",
                file=out,
            )
            print(engine.format_board(), file=out)
    return _result(engine, steps)


def replay(engine: TileUpEngine, actions: list[tuple[int, int]]) -> PlayResult:
    """Aplica una secuencia fija. Se detiene en la primera acción ilegal."""
    steps = 0
    for row, col in actions:
        try:
            engine.apply_action(row, col)
        except IllegalActionError as exc:
            return PlayResult("illegal", steps, engine, str(exc))
        steps += 1
    return _result(engine, steps)


def _move_detail(move) -> str:
    if move.merged:
        return f"fusión de {move.component_size} fichas -> {move.color}:{move.value}"
    return "sin fusión"


def _result(engine: TileUpEngine, steps: int) -> PlayResult:
    if engine.is_victory():
        return PlayResult(
            "victory",
            steps,
            engine,
            "Victoria: se colocaron todas las fichas.",
        )
    if engine.is_defeat():
        return PlayResult(
            "defeat",
            steps,
            engine,
            "Derrota: el tablero está lleno y quedan fichas por colocar.",
        )
    return PlayResult(
        "incomplete",
        steps,
        engine,
        "Secuencia legal incompleta: quedan fichas y celdas libres.",
    )


def print_result(result: PlayResult, out) -> None:
    labels = {
        "victory": "victoria",
        "defeat": "derrota",
        "illegal": "ilegal",
        "incomplete": "incompleta",
    }
    print(f"RESULTADO: {labels.get(result.status, result.status)}", file=out)
    print(result.message, file=out)
    print(f"pasos: {result.steps}", file=out)
    print(f"fichas_restantes: {result.engine.tiles_remaining}", file=out)
    print(result.engine.format_board(), file=out)


def demo(out=None) -> None:
    """Recorre las cuatro reglas con partidas escritas a mano."""
    out = out or sys.stdout
    scenarios = (
        (
            "1. Colocación sin fusión",
            3,
            3,
            [(3, 4), (1, 1)],
            [(2, 2)],
        ),
        (
            "2. Fusión de dos fichas",
            2,
            1,
            [(1, 5), (1, 7)],
            [(0, 0), (0, 1)],
        ),
        (
            "3. Fusión en L (la tercera ficha cierra la esquina)",
            2,
            1,
            [(1, 2), (1, 5), (1, 10)],
            [(0, 0), (1, 1), (1, 0)],
        ),
        (
            "4. Derrota con el tablero lleno",
            2,
            5,
            [(1, 1), (2, 1), (3, 1), (4, 1), (5, 1)],
            [(0, 0), (0, 1), (1, 0), (1, 1)],
        ),
    )
    for title, n, k, tiles, actions in scenarios:
        print(f"=== {title} ===", file=out)
        engine = TileUpEngine(n, tiles, k=k)
        for row, col in actions:
            move = engine.apply_action(row, col)
            print(
                f"({row},{col}) ficha {move.color}:{move.placed_value} {_move_detail(move)}",
                file=out,
            )
        if engine.is_victory():
            outcome = "victoria"
        elif engine.is_defeat():
            outcome = "derrota"
        else:
            outcome = "en curso"
        print(f"RESULTADO: {outcome}", file=out)
        print(engine.format_board(), file=out)
        print(file=out)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python main.py",
        description="TileUp: motor determinista.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    play = sub.add_parser("play", help="Coloca siempre la primera celda libre.")
    _add_instance_args(play)
    play.add_argument("--verbose", action="store_true")

    check = sub.add_parser("replay", help="Aplica una secuencia de celdas sobre el motor.")
    _add_instance_args(check)
    check.add_argument("--actions", required=True, help="Ejemplo: 0,0;1,1;1,0")

    sub.add_parser("demo", help="Muestra colocación, fusiones y derrota.")
    return parser


def _add_instance_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--instance", help="Archivo con N K, M y las fichas.")
    parser.add_argument("--n", type=int, help="Lado del tablero.")
    parser.add_argument("--k", type=int, help="Colores admitidos. Se infiere si se omite.")
    parser.add_argument("--tiles", help="Fichas color:valor separadas por comas.")


def main(argv: list[str] | None = None, out=None) -> int:
    out = out or sys.stdout
    args = build_parser().parse_args(argv)
    try:
        if args.command == "demo":
            demo(out)
            return 0
        n, k, tiles = resolve_instance(args)
        engine = TileUpEngine(n, tiles, k=k)
        if args.command == "play":
            print(f"TileUp n={engine.n} k={engine.k} fichas={engine.m}", file=out)
            result = play_first_cells(engine, verbose=args.verbose, out=out)
        else:
            result = replay(engine, parse_actions(args.actions))
        print_result(result, out)
        if result.status == "victory":
            return 0
        if result.status == "illegal":
            return 2
        return 1
    except (ValueError, TypeError, OSError) as exc:
        print(f"Error: {exc}", file=out)
        return 3


if __name__ == "__main__":
    sys.exit(main())
