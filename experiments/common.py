"""Utilidades compartidas por los guiones de experimentos.

Cada ejecución pasa por el mismo contrato que usará el evaluador: se invoca
``python main.py solve`` como proceso aparte, se leen las métricas de su
salida estándar y la solución se verifica con ``validator.py``. Así los
experimentos miden el sistema tal como se entrega.

Los resultados de cada ejecución se guardan en un JSON propio; al volver a
correr un guion se omiten las ejecuciones ya guardadas, de modo que una
batería larga puede reanudarse.
"""

from __future__ import annotations

import csv
import json
import statistics
import subprocess
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from generate import write_instance  # noqa: E402

AGENTS = ("search", "evo")

#: Margen sobre el límite de tiempo antes de abortar el proceso del agente.
PROCESS_GRACE = 15.0

FIELDS = (
    "agente", "caso", "n", "k", "m", "semilla", "estado", "legal",
    "colocadas", "ocupadas", "mayor", "tiempo", "esfuerzo", "unidad_esfuerzo",
    "dentro_del_limite", "detalle",
)


def parse_metrics(stdout: str) -> dict[str, str]:
    """Pares ``clave=valor`` de la salida de ``solve``."""
    metrics: dict[str, str] = {}
    for line in stdout.splitlines():
        for token in line.split():
            if "=" in token:
                key, value = token.split("=", 1)
                metrics.setdefault(key, value)
    return metrics


def run_case(
    instance: Path,
    agent: str,
    seed: int,
    time_limit: float,
    solution: Path,
) -> dict:
    """Ejecuta un agente sobre una instancia y valida la solución producida."""
    solution.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable, str(ROOT / "main.py"), "solve",
        "--instance", str(instance), "--agent", agent,
        "--seed", str(seed), "--time-limit", str(time_limit),
        "--output", str(solution),
    ]
    row = {field: "" for field in FIELDS}
    row.update(agente=agent, semilla=seed)
    try:
        done = subprocess.run(command, capture_output=True, text=True, cwd=ROOT, timeout=time_limit + PROCESS_GRACE)
    except subprocess.TimeoutExpired:
        row.update(estado="proceso_abortado", legal=False, detalle="superó el límite más el margen")
        return row
    if done.returncode != 0 or not solution.exists():
        last = (done.stderr or done.stdout).strip().splitlines()
        row.update(estado="error", legal=False, detalle=last[-1] if last else f"código {done.returncode}")
        return row

    metrics = parse_metrics(done.stdout)
    effort, _, unit = done.stdout.partition("esfuerzo=")[2].partition("\n")[0].partition(" ")
    elapsed = float(metrics["tiempo"].rstrip("s"))
    checked = subprocess.run(
        [sys.executable, str(ROOT / "validator.py"), str(instance), str(solution)],
        capture_output=True, text=True, cwd=ROOT,
    )
    legal = checked.stdout.startswith("LEGAL")
    row.update(
        estado="ok",
        legal=legal,
        colocadas=int(metrics["colocadas"]),
        ocupadas=int(metrics["ocupadas"]),
        mayor=int(metrics["mayor"]),
        tiempo=elapsed,
        esfuerzo=int(effort),
        unidad_esfuerzo=unit.strip(),
        dentro_del_limite=elapsed <= time_limit,
        detalle=metrics.get("estado_busqueda") or metrics.get("paro", ""),
    )
    return row


def run_battery(
    study: Path,
    cases: Iterable[tuple[str, int, int, int]],
    seeds: Sequence[int],
    time_limit: float,
    agents: Sequence[str] = AGENTS,
) -> list[dict]:
    """Corre todas las combinaciones caso × semilla × agente.

    ``cases`` son tuplas ``(nombre, N, K, M)``. Para cada semilla se genera
    una instancia distinta (semilla de generación = semilla de ejecución),
    de modo que la dispersión refleja tanto la variación entre instancias de
    la misma configuración como el azar propio del agente.
    """
    rows = []
    for name, n, k, m in cases:
        for seed in seeds:
            instance = study / "instances" / f"{name}_s{seed}.txt"
            if not instance.exists():
                write_instance(instance, n, k, m, seed)
            for agent in agents:
                cache = study / "runs" / f"{agent}__{name}__s{seed}.json"
                if cache.exists():
                    row = json.loads(cache.read_text(encoding="utf-8"))
                else:
                    solution = study / "solutions" / agent / f"{name}_s{seed}.txt"
                    row = run_case(instance, agent, seed, time_limit, solution)
                    row.update(caso=name, n=n, k=k, m=m)
                    cache.parent.mkdir(parents=True, exist_ok=True)
                    cache.write_text(json.dumps(row, ensure_ascii=False), encoding="utf-8")
                    print(f"{agent:6} {name} s{seed}: {row['estado']} {row['colocadas']}/{m} "
                          f"ocupadas={row['ocupadas']} t={row['tiempo']}", file=sys.stderr, flush=True)
                rows.append(row)
    write_csv(study / "results.csv", rows)
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def mean_sd(values: Sequence[float], digits: int = 1) -> str:
    """``media ± desviación estándar`` (poblacional) de ``values``."""
    if not values:
        return "n/d"
    return f"{statistics.mean(values):.{digits}f} ± {statistics.pstdev(values):.{digits}f}"
