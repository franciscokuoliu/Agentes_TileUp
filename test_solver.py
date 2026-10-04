"""Pruebas del comando ``solve`` e integración con el validador.

Ejecutar desde esta carpeta::

    python -m unittest test_solver -v
"""

from __future__ import annotations

import io
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from main import main
from solver import decode_fitness
from evolutionary_agent import GameRecord, fitness

ROOT = Path(__file__).resolve().parent


def escribir_instancia(path: Path, n: int, k: int, m: int, seed: int) -> None:
    rng = random.Random(seed)
    lines = ["# instancia de prueba", f"{n} {k}   # N K", f"{m}   # M"]
    lines += [f"{rng.randint(1, k)} {rng.randint(1, 9)}" for _ in range(m)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def validar(instance: Path, solution: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "validator.py"), str(instance), str(solution)],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )


class TestSolve(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.instance = self.dir / "instancia.txt"
        escribir_instancia(self.instance, 4, 6, 60, seed=11)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def solve(self, agent: str, output: str, *extra: str) -> tuple[int, str]:
        out = io.StringIO()
        code = main(
            [
                "solve", "--instance", str(self.instance), "--agent", agent,
                "--seed", "1", "--time-limit", "5", "--output", str(self.dir / output),
                *extra,
            ],
            out=out,
        )
        return code, out.getvalue()

    def test_evolutivo_produce_una_solucion_que_el_validador_acepta(self) -> None:
        code, text = self.solve("evo", "evo.txt", "--generations", "10")
        self.assertEqual(code, 0)
        solution = self.dir / "evo.txt"
        summary = solution.read_text(encoding="utf-8").strip().splitlines()[-1]
        self.assertTrue(summary.startswith("# colocadas="))
        self.assertIn(summary[2:], text)

        checked = validar(self.instance, solution)
        self.assertIn("LEGAL", checked.stdout)
        self.assertNotEqual(checked.returncode, 2)

    def test_busqueda_produce_una_solucion_que_el_validador_acepta(self) -> None:
        code, _text = self.solve("search", "search.txt")
        self.assertEqual(code, 0)
        checked = validar(self.instance, self.dir / "search.txt")
        self.assertIn("LEGAL", checked.stdout)

    def test_misma_semilla_mismo_archivo(self) -> None:
        self.solve("evo", "a.txt", "--generations", "10")
        self.solve("evo", "b.txt", "--generations", "10")
        self.assertEqual(
            (self.dir / "a.txt").read_text(encoding="utf-8"),
            (self.dir / "b.txt").read_text(encoding="utf-8"),
        )

    def test_escribe_la_solucion_aunque_la_partida_sea_derrota(self) -> None:
        escribir_instancia(self.instance, 2, 30, 40, seed=3)
        code, text = self.solve("evo", "derrota.txt", "--generations", "3")
        self.assertEqual(code, 0)
        self.assertIn("resultado=derrota", text)
        lines = (self.dir / "derrota.txt").read_text(encoding="utf-8").splitlines()
        self.assertGreater(len(lines), 1)
        self.assertIn("LEGAL", validar(self.instance, self.dir / "derrota.txt").stdout)

    def test_metricas_obligatorias_en_salida_estandar(self) -> None:
        _code, text = self.solve("evo", "m.txt", "--generations", "5")
        for token in ("colocadas=", "ocupadas=", "mayor=", "tiempo=", "esfuerzo="):
            self.assertIn(token, text)

    def test_historial_csv(self) -> None:
        csv_path = self.dir / "historial.csv"
        self.solve("evo", "h.txt", "--generations", "5", "--history-csv", str(csv_path))
        rows = csv_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(rows[0], "generacion,aptitud,colocadas,ocupadas")
        self.assertGreater(len(rows), 1)

    def test_instancia_mal_formada_da_error_legible(self) -> None:
        self.instance.write_text("4 x\n", encoding="utf-8")
        code, text = self.solve("evo", "x.txt")
        self.assertEqual(code, 3)
        self.assertTrue(text.startswith("Error:"))

    def test_parametros_invalidos_dan_error_legible(self) -> None:
        code, text = self.solve("evo", "x.txt", "--population", "1")
        self.assertEqual(code, 3)
        self.assertIn("Error:", text)


class TestDecodificarAptitud(unittest.TestCase):
    def test_es_la_inversa_de_fitness(self) -> None:
        for placed, occupied in ((0, 0), (10, 1), (10, 16), (57, 9)):
            record = GameRecord((), placed=placed, occupied=occupied, highest=1, victory=False)
            self.assertEqual(decode_fitness(fitness(record, 4), 4), (placed, occupied))


if __name__ == "__main__":
    unittest.main()
