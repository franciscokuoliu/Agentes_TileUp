# TileUp

Puzzle determinista de un jugador. El motor coloca una secuencia fija de fichas en un tablero `N x N` y fusiona componentes ortogonales del mismo color. El motor aplica las reglas. El agente de búsqueda prueba celdas hasta colocar todas las fichas.

## Reglas

- El tablero empieza vacío. Una ficha es un par `(color, valor)`: el color está en `1..K` y el valor es un entero positivo.
- En cada turno se coloca la siguiente ficha de la secuencia en cualquier celda vacía. No hay gravedad. El factor de ramificación es el número de celdas libres.
- Tras colocar en `p`, se toma la componente conexa ortogonal (arriba, abajo, izquierda, derecha) de fichas del mismo color que contiene a `p`.
- Si esa componente tiene tamaño 1, no pasa nada más.
- Si tiene tamaño 2 o más, todas sus fichas salen del tablero y en `p` queda una sola ficha del mismo color con la suma de los valores. La fusión no se repite en ese turno.
- La diagonal no conecta.
- Victoria: se colocaron las `M` fichas, aunque queden celdas libres.
- Derrota: quedan fichas y no hay celdas libres.
- Una fusión libera celdas, así que se pueden colocar más fichas que casillas.

Las coordenadas de la CLI y del código son 0-indexadas.

## Requisitos

Python 3.10 o superior. No hay dependencias externas.

```text
pip install -r requirements.txt
```

## Estructura

```text
Agentes_TileUp/
├── main.py                 # CLI: demo, play, search y replay
├── engine.py               # TileUpEngine / GameState
├── search_agent.py         # Búsqueda en profundidad de una solución
├── evolutionary_agent.py   # Agente evolutivo: política por características y ciclo evolutivo
├── solver.py               # Comando solve: ejecuta un agente y escribe la solución
├── test_evolutionary.py
├── test_solver.py          # Integración: solve + validador
├── tests.py
├── requirements.txt
├── README.md
└── INFORME.md              # Plantilla del informe
```

## Ejecución

Desde esta carpeta:

```text
python main.py demo
```

`solve` es el punto de entrada oficial. Recibe la instancia, el agente (`search` o `evo`), la semilla y el límite de tiempo en segundos, y escribe siempre el archivo de solución, también en derrota:

```text
python main.py solve --instance instancia.txt --agent evo --seed 1 --time-limit 10 --output solucion.txt
```

Imprime por salida estándar las fichas colocadas, las celdas ocupadas, la ficha mayor, el tiempo y el esfuerzo (nodos expandidos en la búsqueda, evaluaciones de aptitud en el evolutivo). Termina con código `0` si escribió la solución y `3` ante un error de entrada.

Opciones de visualización:

| Opción | Efecto |
| --- | --- |
| `--show-board` | Imprime el tablero final. |
| `--show-progress` | Evolutivo: generaciones en que mejoró la mejor partida. |
| `--history-csv RUTA` | Evolutivo: mejor aptitud por generación, en CSV. |

Parámetros del agente evolutivo (valores por defecto entre paréntesis): `--population` (30), `--generations` (100), `--stall` (25), `--tournament` (3), `--elite` (2), `--crossover-rate` (0.9), `--mutation-rate` (0.3), `--mutation-sigma` (1.5), `--lookahead` (4). `python main.py solve --help` muestra la lista completa.

`search` busca una secuencia que coloque todas las fichas:

```text
python main.py search --n 2 --k 1 --tiles 1:2,1:5,1:10 --timeout 5
```

`play` coloca siempre la primera celda libre, en orden fila-mayor:

```text
python main.py play --n 2 --k 2 --tiles 1:1,2:1
```

Reaplicar una secuencia sobre el motor. Códigos de salida: `0` victoria, `1` legal pero no ganadora, `2` ilegal, `3` error de uso.

```text
python main.py replay --n 2 --k 1 --tiles 1:2,1:5,1:10 --actions 0,0;1,1;1,0
```

Esa secuencia es la L: las dos primeras fichas solo se tocan en diagonal y la tercera, en `(1,0)`, las fusiona en `1:17`.

## Archivo de instancia

```text
N K
M
color valor
...
```

Las líneas en blanco y el texto tras `#` se ignoran.

```text
2 1
3
1 2
1 5
1 10
```

## Pruebas

```text
python -m unittest discover -v
```

Ejecuta las pruebas del motor (`tests.py`), del agente evolutivo (`test_evolutionary.py`) y las de integración del comando `solve` con el validador (`test_solver.py`).

Cubren colocación sin fusión, fusión de dos fichas, componentes en L y en T, derrota con tablero lleno y el clonado.

## API del motor

```python
from engine import TileUpEngine

state = TileUpEngine(n, [(1, 2), (1, 5), (1, 10)], k=1)
for row, col in state.get_valid_actions():
    child = state.clone()
    child.apply_action(row, col)
```

| Método | Rol |
| --- | --- |
| `get_valid_actions()` | Celdas vacías `(fila, columna)` en orden fila-mayor. |
| `apply_action(fila, columna)` | Coloca la ficha actual, fusiona una vez y avanza. |
| `clone()` / `copy()` | Copia el tablero en O(N²) sin `deepcopy`. |
| `is_terminal()` / `is_victory()` / `is_defeat()` | Condiciones de término. |
| `get_board_state()` | Tupla de tuplas: `None` o `(color, valor)`. |
| `state_key()` | Clave para tablas de transposición de una misma partida. |

`colors` y `values` son listas planas de longitud `N²` (índice `fila * N + columna`, color `0` = vacío). Se pueden leer; no hay que escribirlas.

`clone` comparte `tile_colors` y `tile_values` porque la secuencia no cambia. `copy.deepcopy` también delega en `clone`.

## Complejidad

- `clone`: O(N²), dos copias de lista.
- `apply_action`: O(|G|). Al empezar el turno no quedan fichas del mismo color ortogonalmente pegadas, así que `|G|` es como máximo 5. Aun así el motor recorre la componente entera.
- `get_valid_actions`: O(N²).

El árbol crece con las celdas libres de cada posición. El clonado barato es lo que hace viable explorarlo.
