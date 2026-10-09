"""Generador de instancias de TileUp.

Produce archivos en el formato de la especificación a partir de N, K, M y
una semilla. La misma combinación de parámetros produce siempre el mismo
archivo.

Uso::

    python generate.py --n 6 --k 4 --m 120 --seed 1 --output instancia.txt

Cada ficha recibe un color uniforme en ``1..K`` y un valor uniforme en
``1..max_value``. Los valores no influyen en las decisiones de los agentes;
solo afectan la métrica de la ficha mayor.
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

DEFAULT_MAX_VALUE = 9


def generate_tiles(k: int, m: int, seed: int, max_value: int = DEFAULT_MAX_VALUE) -> list[tuple[int, int]]:
    """Secuencia de ``m`` fichas ``(color, valor)`` derivada de ``seed``."""
    if k < 1 or m < 0 or max_value < 1:
        raise ValueError("Se requiere K >= 1, M >= 0 y max_value >= 1.")
    rng = random.Random(seed)
    return [(rng.randint(1, k), rng.randint(1, max_value)) for _ in range(m)]


def format_instance(n: int, k: int, tiles: list[tuple[int, int]], seed: int | None = None) -> str:
    """Texto de la instancia en el formato de la especificación."""
    if n < 1:
        raise ValueError("Se requiere N >= 1.")
    header = f"# TileUp N={n} K={k} M={len(tiles)}"
    if seed is not None:
        header += f" semilla={seed}"
    lines = [header, f"{n} {k}", str(len(tiles))]
    lines += [f"{color} {value}" for color, value in tiles]
    return "\n".join(lines) + "\n"


def write_instance(
    path: Path,
    n: int,
    k: int,
    m: int,
    seed: int,
    max_value: int = DEFAULT_MAX_VALUE,
) -> Path:
    """Genera la instancia y la escribe en ``path``."""
    tiles = generate_tiles(k, m, seed, max_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(format_instance(n, k, tiles, seed), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python generate.py", description="Genera una instancia de TileUp.")
    parser.add_argument("--n", type=int, required=True, help="Lado del tablero.")
    parser.add_argument("--k", type=int, required=True, help="Cantidad de colores.")
    parser.add_argument("--m", type=int, required=True, help="Cantidad de fichas.")
    parser.add_argument("--seed", type=int, required=True, help="Semilla de generación.")
    parser.add_argument("--max-value", type=int, default=DEFAULT_MAX_VALUE, help="Valor máximo de una ficha.")
    parser.add_argument("--output", required=True, help="Archivo de salida.")
    args = parser.parse_args(argv)
    try:
        write_instance(Path(args.output), args.n, args.k, args.m, args.seed, args.max_value)
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
