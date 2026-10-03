"""Pruebas de la política del agente evolutivo.

Ejecutar desde esta carpeta::

    python -m unittest test_evolutionary -v
"""

from __future__ import annotations

import unittest

from engine import TileUpEngine
from evolutionary_agent import (
    NUM_FEATURES,
    cell_features,
    neighbor_table,
    play,
)

# Pesos de referencia: priorizan la fusión y penalizan la adyacencia a otros colores.
PESOS_REFERENCIA = (10.0, -2.0, 0.5, 0.5, 1.0, -1.5)


class TestCaracteristicas(unittest.TestCase):
    def test_vecinos_de_esquina_y_centro(self) -> None:
        table = neighbor_table(3)
        self.assertEqual(sorted(table[0]), [1, 3])          # esquina
        self.assertEqual(sorted(table[4]), [1, 3, 5, 7])    # centro

    def test_vector_en_un_tablero_armado_a_mano(self) -> None:
        # Tablero 3x3:
        #   1 . .
        #   . . .
        #   . 2 .
        engine = TileUpEngine(3, [(1, 1), (2, 1), (1, 1), (2, 1)], k=2)
        engine.apply_action(0, 0)
        engine.apply_action(2, 1)
        table = neighbor_table(3)
        upcoming = frozenset({2})

        # Color 1 en (0,1): adyacente al 1 de (0,0).
        self.assertEqual(
            cell_features(engine, 1, 1, upcoming, table[1]),
            (1, 0, 2, 1, 0, 0),
        )
        # Color 1 en (1,1): adyacente al 2 de (2,1), color próximo en la secuencia.
        self.assertEqual(
            cell_features(engine, 4, 1, upcoming, table[4]),
            (0, 1, 3, 0, 0, 1),
        )


class TestPolitica(unittest.TestCase):
    def test_busca_la_fusion_cuando_absorbe_pesa_mucho(self) -> None:
        record = play(2, [(1, 2), (1, 5)], 1, PESOS_REFERENCIA)
        self.assertTrue(record.victory)
        self.assertEqual(record.occupied, 1)
        self.assertEqual(record.highest, 7)

    def test_es_determinista(self) -> None:
        tiles = [(1 + (i * 7) % 3, 1 + i % 5) for i in range(40)]
        first = play(4, tiles, 3, PESOS_REFERENCIA)
        second = play(4, tiles, 3, PESOS_REFERENCIA)
        self.assertEqual(first, second)

    def test_la_partida_es_legal_y_las_metricas_cuadran(self) -> None:
        tiles = [(1 + (i * 7) % 3, 1 + i % 5) for i in range(40)]
        record = play(4, tiles, 3, PESOS_REFERENCIA)
        engine = TileUpEngine(4, tiles, k=3)
        for row, col in record.actions:
            engine.apply_action(row, col)
            engine.check_invariants()
        self.assertEqual(record.placed, engine.tile_index)
        self.assertEqual(record.occupied, engine.size - engine.empty_count)
        self.assertEqual(record.highest, max(engine.values))

    def test_en_derrota_devuelve_las_jugadas_hechas(self) -> None:
        # 2x2 con cinco colores distintos: la quinta ficha no cabe.
        tiles = [(1, 1), (2, 1), (3, 1), (4, 1), (5, 1)]
        record = play(2, tiles, 5, PESOS_REFERENCIA)
        self.assertFalse(record.victory)
        self.assertEqual(record.placed, 4)
        self.assertEqual(len(record.actions), 4)

    def test_rechaza_pesos_de_largo_incorrecto(self) -> None:
        with self.assertRaises(ValueError):
            play(2, [(1, 1)], 1, [1.0] * (NUM_FEATURES - 1))


if __name__ == "__main__":
    unittest.main()
