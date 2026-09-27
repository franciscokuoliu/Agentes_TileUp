"""Pruebas del motor y de la entrada por línea de comandos.

Ejecutar desde esta carpeta::

    python tests.py -v
    python -m unittest tests -v
"""

from __future__ import annotations

import copy
import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import GameState, IllegalActionError, TileUpEngine
from main import load_instance, main, parse_actions, parse_tiles


def colocar(engine: TileUpEngine, row: int, col: int):
    result = engine.apply_action(row, col)
    engine.check_invariants()
    return result


class TestColocacionSimple(unittest.TestCase):
    def test_colocacion_sin_fusion(self) -> None:
        engine = TileUpEngine(3, [(3, 4), (1, 1)], k=3)
        result = colocar(engine, 2, 2)

        self.assertFalse(result.merged)
        self.assertEqual(result.component_size, 1)
        self.assertEqual(result.value, 4)
        self.assertEqual(engine.get_cell(2, 2), (3, 4))
        self.assertEqual(engine.tile_index, 1)
        self.assertEqual(engine.tiles_remaining, 1)
        self.assertEqual(engine.next_tile(), (1, 1))
        self.assertEqual(engine.empty_count, 8)
        self.assertFalse(engine.is_terminal())
        self.assertNotIn((2, 2), engine.get_valid_actions())
        self.assertEqual(len(engine.get_valid_actions()), 8)

        occupied = [cell for row in engine.get_board_state() for cell in row if cell is not None]
        self.assertEqual(occupied, [(3, 4)])

    def test_la_diagonal_no_produce_fusion(self) -> None:
        engine = TileUpEngine(2, [(1, 2), (1, 5), (1, 10)], k=1)
        colocar(engine, 0, 0)
        result = colocar(engine, 1, 1)

        self.assertFalse(result.merged)
        self.assertEqual(engine.get_cell(0, 0), (1, 2))
        self.assertEqual(engine.get_cell(1, 1), (1, 5))
        self.assertEqual(engine.empty_count, 2)

    def test_acciones_validas_en_orden_fila_mayor(self) -> None:
        engine = TileUpEngine(2, [(1, 1), (2, 1)], k=2)
        self.assertEqual(engine.get_valid_actions(), [(0, 0), (0, 1), (1, 0), (1, 1)])
        colocar(engine, 1, 0)
        self.assertEqual(engine.get_valid_actions(), [(0, 0), (0, 1), (1, 1)])

    def test_rechaza_datos_y_acciones_invalidas(self) -> None:
        cases = (
            (0, [(1, 1)]),
            (2, [(0, 1)]),
            (2, [(1, 0)]),
            (2, [(True, 1)]),
            (2, ["1:2"]),
        )
        for n, tiles in cases:
            with self.subTest(n=n, tiles=tiles):
                with self.assertRaises(ValueError):
                    TileUpEngine(n, tiles)
        with self.assertRaises(ValueError):
            TileUpEngine(2, [(3, 1)], k=2)

        engine = TileUpEngine(2, [(1, 1), (2, 1)], k=2)
        for action in ((-1, 0), (0, 2), (1.5, 0), (True, 0)):
            with self.subTest(action=action):
                with self.assertRaises(IllegalActionError):
                    engine.apply_action(*action)
        colocar(engine, 0, 0)
        with self.assertRaises(IllegalActionError):
            engine.apply_action(0, 0)


class TestFusionDosFichas(unittest.TestCase):
    def test_fusion_simple_de_dos_fichas(self) -> None:
        engine = TileUpEngine(2, [(1, 5), (1, 7)], k=1)
        first = colocar(engine, 0, 0)
        self.assertFalse(first.merged)

        second = colocar(engine, 0, 1)
        self.assertTrue(second.merged)
        self.assertEqual(second.component_size, 2)
        self.assertEqual(second.color, 1)
        self.assertEqual(second.placed_value, 7)
        self.assertEqual(second.value, 12)
        self.assertEqual(
            engine.get_board_state(),
            (
                (None, (1, 12)),
                (None, None),
            ),
        )
        self.assertEqual(engine.empty_count, 3)
        self.assertTrue(engine.is_victory())
        self.assertFalse(engine.is_defeat())


class TestFusionComponente(unittest.TestCase):
    def test_fusion_de_ele(self) -> None:
        """La esquina se coloca al final y conecta dos fichas que solo se tocaban en diagonal.

        Antes de la tercera jugada::

            (1,2) .
            .     (1,5)

        La componente es la L (0,0)-(1,0)-(1,1). La suma queda en la esquina
        recién jugada, no en otra celda del grupo.
        """
        engine = TileUpEngine(2, [(1, 2), (1, 5), (1, 10)], k=1)
        colocar(engine, 0, 0)
        colocar(engine, 1, 1)
        result = colocar(engine, 1, 0)

        self.assertTrue(result.merged)
        self.assertEqual(result.component_size, 3)
        self.assertEqual(result.value, 17)
        self.assertEqual(
            engine.get_board_state(),
            (
                (None, None),
                ((1, 17), None),
            ),
        )
        self.assertTrue(engine.is_victory())

    def test_fusion_de_te(self) -> None:
        """T de cuatro fichas. El cruce se coloca al final.

        Antes::

            (1,1) .     (1,4)
            .     (1,8) .
            .     .     .

        (0,1) toca el brazo izquierdo, el derecho y el tallo. Suma 15.
        """
        engine = TileUpEngine(3, [(1, 1), (1, 4), (1, 8), (1, 2)], k=1)
        colocar(engine, 0, 0)
        colocar(engine, 0, 2)
        colocar(engine, 1, 1)
        result = colocar(engine, 0, 1)

        self.assertTrue(result.merged)
        self.assertEqual(result.component_size, 4)
        self.assertEqual(result.value, 15)
        self.assertEqual(engine.get_cell(0, 1), (1, 15))
        for cell in ((0, 0), (0, 2), (1, 1)):
            self.assertIsNone(engine.get_cell(*cell))
        self.assertEqual(engine.empty_count, 8)

    def test_no_absorbe_otra_componente_del_mismo_color(self) -> None:
        """Una sola fusión, sin barrer el resto del color ni encadenar otro grupo."""
        engine = TileUpEngine(3, [(1, 1), (1, 9), (1, 1)], k=1)
        colocar(engine, 0, 0)
        colocar(engine, 2, 2)
        result = colocar(engine, 0, 1)

        self.assertTrue(result.merged)
        self.assertEqual(result.component_size, 2)
        self.assertEqual(result.value, 2)
        self.assertIsNone(engine.get_cell(0, 0))
        self.assertEqual(engine.get_cell(0, 1), (1, 2))
        self.assertEqual(engine.get_cell(2, 2), (1, 9))


class TestDerrota(unittest.TestCase):
    def test_derrota_con_tablero_lleno_y_fichas_pendientes(self) -> None:
        tiles = [(1, 1), (2, 1), (3, 1), (4, 1), (5, 1)]
        engine = TileUpEngine(2, tiles, k=5)
        for action in ((0, 0), (0, 1), (1, 0)):
            colocar(engine, *action)
            self.assertFalse(engine.is_terminal())

        colocar(engine, 1, 1)
        self.assertTrue(engine.is_defeat())
        self.assertTrue(engine.is_terminal())
        self.assertFalse(engine.is_victory())
        self.assertEqual(engine.tiles_remaining, 1)
        self.assertEqual(engine.next_tile(), (5, 1))
        self.assertEqual(engine.get_valid_actions(), [])
        self.assertEqual(engine.empty_count, 0)
        with self.assertRaises(IllegalActionError):
            engine.apply_action(0, 0)

    def test_fusiones_permiten_colocar_mas_fichas_que_celdas(self) -> None:
        engine = TileUpEngine(2, [(1, 1)] * 5, k=1)
        colocar(engine, 0, 0)
        merged = colocar(engine, 0, 1)
        self.assertTrue(merged.merged)
        self.assertEqual(merged.value, 2)
        self.assertEqual(engine.empty_count, 3)
        self.assertFalse(engine.is_defeat())

        while not engine.is_terminal():
            row, col = engine.get_valid_actions()[0]
            colocar(engine, row, col)
        self.assertTrue(engine.is_victory())
        self.assertGreater(engine.m, engine.n * engine.n)

    def test_tablero_lleno_al_colocar_la_ultima_ficha_es_victoria(self) -> None:
        engine = TileUpEngine(2, [(1, 1), (2, 1), (3, 1), (4, 1)], k=4)
        for row, col in ((0, 0), (0, 1), (1, 0), (1, 1)):
            colocar(engine, row, col)
        self.assertTrue(engine.is_victory())
        self.assertFalse(engine.is_defeat())
        self.assertEqual(engine.empty_count, 0)
        self.assertEqual(engine.get_valid_actions(), [])


class TestVictoriaYClonado(unittest.TestCase):
    def test_victoria_con_celdas_libres(self) -> None:
        engine = TileUpEngine(3, [(2, 8)], k=2)
        colocar(engine, 0, 0)
        self.assertTrue(engine.is_victory())
        self.assertFalse(engine.is_defeat())
        self.assertEqual(engine.empty_count, 8)
        self.assertEqual(engine.get_valid_actions(), [])

    def test_clone_no_alias_el_tablero_y_comparte_la_secuencia(self) -> None:
        engine = TileUpEngine(3, [(1, 4), (1, 6), (2, 1)], k=2)
        colocar(engine, 0, 0)
        twin = engine.clone()
        via_copy = engine.copy()
        via_module = copy.copy(engine)
        via_deep = copy.deepcopy(engine)

        for other in (twin, via_copy, via_module, via_deep):
            self.assertEqual(other, engine)
            self.assertIs(other.tile_colors, engine.tile_colors)
            self.assertIs(other.tile_values, engine.tile_values)
            self.assertIsNot(other.colors, engine.colors)
            self.assertIsNot(other.values, engine.values)

        colocar(twin, 0, 1)
        self.assertIsNone(engine.get_cell(0, 1))
        self.assertEqual(engine.get_cell(0, 0), (1, 4))
        self.assertEqual(twin.get_cell(0, 1), (1, 10))
        self.assertEqual(engine.tile_index, 1)
        self.assertEqual(twin.tile_index, 2)
        self.assertNotEqual(engine.state_key(), twin.state_key())

    def test_alias_de_clase(self) -> None:
        self.assertIs(GameState, TileUpEngine)


class TestCli(unittest.TestCase):
    def test_carga_de_instancia_y_parsers(self) -> None:
        self.assertEqual(parse_tiles("1:2, 1:5,2:4"), [(1, 2), (1, 5), (2, 4)])
        self.assertEqual(parse_actions("0,0;1,1 1,0"), [(0, 0), (1, 1), (1, 0)])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "instancia.txt"
            path.write_text(
                "# ejemplo\n2 1\n\n3\n1 2\n1 5  # esquina\n1 10\n",
                encoding="utf-8",
            )
            self.assertEqual(load_instance(path), (2, 1, [(1, 2), (1, 5), (1, 10)]))

    def test_cli_demo_play_y_replay(self) -> None:
        demo_out = io.StringIO()
        self.assertEqual(main(["demo"], out=demo_out), 0)
        demo_text = demo_out.getvalue()
        self.assertIn("RESULTADO: victoria", demo_text)
        self.assertIn("RESULTADO: derrota", demo_text)
        self.assertIn("1:17", demo_text)
        self.assertIn("1:12", demo_text)

        play_out = io.StringIO()
        code = main(["play", "--n", "2", "--tiles", "1:1,2:1"], out=play_out)
        self.assertEqual(code, 0)
        self.assertIn("RESULTADO: victoria", play_out.getvalue())

        ok_out = io.StringIO()
        ok = main(
            [
                "replay",
                "--n",
                "2",
                "--k",
                "1",
                "--tiles",
                "1:2,1:5,1:10",
                "--actions",
                "0,0;1,1;1,0",
            ],
            out=ok_out,
        )
        self.assertEqual(ok, 0)
        self.assertIn("RESULTADO: victoria", ok_out.getvalue())

        bad_out = io.StringIO()
        bad = main(
            ["replay", "--n", "2", "--tiles", "1:1,2:1", "--actions", "0,0;0,0"],
            out=bad_out,
        )
        self.assertEqual(bad, 2)
        self.assertIn("RESULTADO: ilegal", bad_out.getvalue())


if __name__ == "__main__":
    unittest.main()
