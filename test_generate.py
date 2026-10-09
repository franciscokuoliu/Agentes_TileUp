"""Pruebas del generador de instancias."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from generate import generate_tiles, main, write_instance
from main import load_instance


class TestGenerador(unittest.TestCase):
    def test_misma_semilla_misma_secuencia(self) -> None:
        self.assertEqual(generate_tiles(5, 50, seed=3), generate_tiles(5, 50, seed=3))
        self.assertNotEqual(generate_tiles(5, 50, seed=3), generate_tiles(5, 50, seed=4))

    def test_respeta_rangos(self) -> None:
        tiles = generate_tiles(4, 200, seed=1, max_value=7)
        self.assertEqual(len(tiles), 200)
        self.assertTrue(all(1 <= color <= 4 and 1 <= value <= 7 for color, value in tiles))

    def test_el_archivo_lo_lee_el_programa(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_instance(Path(tmp) / "x.txt", 6, 4, 30, seed=2)
            n, k, tiles = load_instance(path)
        self.assertEqual((n, k), (6, 4))
        self.assertEqual(tiles, generate_tiles(4, 30, seed=2))

    def test_cli_y_parametros_invalidos(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "y.txt"
            self.assertEqual(main(["--n", "3", "--k", "2", "--m", "5", "--seed", "1", "--output", str(out)]), 0)
            self.assertTrue(out.exists())
            self.assertEqual(main(["--n", "0", "--k", "2", "--m", "5", "--seed", "1", "--output", str(out)]), 3)


if __name__ == "__main__":
    unittest.main()
