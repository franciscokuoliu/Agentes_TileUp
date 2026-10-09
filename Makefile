# Atajos para ejecutar el proyecto con Python 3.10+ (sin dependencias externas).
PYTHON ?= python3

.PHONY: test comparison scalability tuning experiments

test:
	$(PYTHON) -m unittest discover -v

comparison:
	$(PYTHON) experiments/run_comparison.py

scalability:
	$(PYTHON) experiments/run_scalability.py

tuning:
	$(PYTHON) experiments/tune_evo.py

experiments: tuning comparison scalability
