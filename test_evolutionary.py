"""Pruebas del agente evolutivo: política, aptitud y ciclo evolutivo.

Ejecutar desde esta carpeta::

    python -m unittest test_evolutionary -v
"""

from __future__ import annotations

import random
import time
import unittest

from engine import TileUpEngine
from evolutionary_agent import (
    NUM_FEATURES,
    REFERENCE_WEIGHTS,
    WEIGHT_LIMIT,
    EvolutionConfig,
    GameRecord,
    cell_features,
    evolve,
    fitness,
    neighbor_table,
    play,
)

def instancia_aleatoria(n: int, k: int, m: int, seed: int) -> list[tuple[int, int]]:
    rng = random.Random(seed)
    return [(rng.randint(1, k), rng.randint(1, 9)) for _ in range(m)]


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
        record = play(2, [(1, 2), (1, 5)], 1, REFERENCE_WEIGHTS)
        self.assertTrue(record.victory)
        self.assertEqual(record.occupied, 1)
        self.assertEqual(record.highest, 7)

    def test_es_determinista(self) -> None:
        tiles = [(1 + (i * 7) % 3, 1 + i % 5) for i in range(40)]
        first = play(4, tiles, 3, REFERENCE_WEIGHTS)
        second = play(4, tiles, 3, REFERENCE_WEIGHTS)
        self.assertEqual(first, second)

    def test_la_partida_es_legal_y_las_metricas_cuadran(self) -> None:
        tiles = [(1 + (i * 7) % 3, 1 + i % 5) for i in range(40)]
        record = play(4, tiles, 3, REFERENCE_WEIGHTS)
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
        record = play(2, tiles, 5, REFERENCE_WEIGHTS)
        self.assertFalse(record.victory)
        self.assertEqual(record.placed, 4)
        self.assertEqual(len(record.actions), 4)

    def test_rechaza_pesos_de_largo_incorrecto(self) -> None:
        with self.assertRaises(ValueError):
            play(2, [(1, 1)], 1, [1.0] * (NUM_FEATURES - 1))


class TestAptitud(unittest.TestCase):
    def test_una_ficha_mas_supera_cualquier_diferencia_de_ocupacion(self) -> None:
        n = 4
        mas_fichas = GameRecord((), placed=11, occupied=n * n, highest=1, victory=False)
        menos_fichas = GameRecord((), placed=10, occupied=1, highest=1, victory=False)
        self.assertGreater(fitness(mas_fichas, n), fitness(menos_fichas, n))

    def test_ante_igual_cantidad_gana_el_tablero_mas_despejado(self) -> None:
        a = GameRecord((), placed=10, occupied=3, highest=1, victory=True)
        b = GameRecord((), placed=10, occupied=5, highest=1, victory=True)
        self.assertGreater(fitness(a, 4), fitness(b, 4))


class TestEvolucion(unittest.TestCase):
    CONFIG = EvolutionConfig(population_size=12, max_generations=8, stall_generations=8)

    def setUp(self) -> None:
        self.tiles = instancia_aleatoria(4, 10, 100, seed=7)

    def test_misma_semilla_mismo_resultado(self) -> None:
        a = evolve(4, self.tiles, 10, seed=3, time_limit=30, config=self.CONFIG)
        b = evolve(4, self.tiles, 10, seed=3, time_limit=30, config=self.CONFIG)
        self.assertEqual(a, b)

    def test_nunca_empeora_a_la_referencia_y_el_historial_no_decrece(self) -> None:
        result = evolve(4, self.tiles, 10, seed=1, time_limit=30, config=self.CONFIG)
        reference = fitness(play(4, self.tiles, 10, REFERENCE_WEIGHTS), 4)
        self.assertGreaterEqual(result.fitness, reference)
        self.assertEqual(list(result.history), sorted(result.history))
        self.assertEqual(result.fitness, fitness(result.record, 4))

    def test_la_mejor_partida_es_legal_y_reproducible_con_sus_pesos(self) -> None:
        result = evolve(4, self.tiles, 10, seed=2, time_limit=30, config=self.CONFIG)
        self.assertEqual(play(4, self.tiles, 10, result.weights), result.record)
        engine = TileUpEngine(4, self.tiles, k=10)
        for row, col in result.record.actions:
            engine.apply_action(row, col)
        self.assertEqual(engine.tile_index, result.record.placed)
        self.assertTrue(all(abs(w) <= WEIGHT_LIMIT for w in result.weights))

    def test_respeta_el_limite_de_tiempo(self) -> None:
        tiles = instancia_aleatoria(10, 4, 1500, seed=4)
        started = time.monotonic()
        result = evolve(10, tiles, 4, seed=1, time_limit=0.5)
        self.assertLess(time.monotonic() - started, 0.5)
        self.assertEqual(result.stop_reason, "tiempo")
        self.assertEqual(result.record.placed, 1500)

    def test_detiene_al_alcanzar_el_optimo(self) -> None:
        result = evolve(2, [(1, 2), (1, 5)], 1, seed=0, time_limit=5)
        self.assertEqual(result.stop_reason, "optimo")
        self.assertEqual(result.record.occupied, 1)

    def test_rechaza_parametros_invalidos(self) -> None:
        with self.assertRaises(ValueError):
            EvolutionConfig(population_size=1)
        with self.assertRaises(ValueError):
            EvolutionConfig(tournament_size=50)
        with self.assertRaises(ValueError):
            evolve(2, [(1, 1)], 1, seed=0, time_limit=0)


if __name__ == "__main__":
    unittest.main()
