# Imagen mínima para ejecutar TileUp sin instalar nada en la máquina anfitriona.
# El proyecto solo usa la biblioteca estándar de Python.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY . /app

# El directorio de trabajo del usuario se monta en /work para leer
# instancias y escribir soluciones con rutas relativas.
WORKDIR /work
ENTRYPOINT ["python", "/app/main.py"]
CMD ["--help"]
