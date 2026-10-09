#!/usr/bin/env sh
# Punto de entrada único con Docker. Construye la imagen si hace falta y
# ejecuta el programa con el directorio actual montado en /work.
#
#   ./tileup.sh solve --instance instancia.txt --agent evo --seed 1 --time-limit 10
#   ./tileup.sh test
set -e
IMAGE=tileup
cd "$(dirname "$0")"
docker build -q -t "$IMAGE" . > /dev/null
if [ "$1" = "test" ]; then
  exec docker run --rm -w /app --entrypoint python "$IMAGE" -m unittest discover -v
fi
exec docker run --rm -v "$PWD":/work "$IMAGE" "$@"
