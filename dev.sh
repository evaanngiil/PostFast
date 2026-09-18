#!/bin/bash
# Script de desarrollo para solucionar los problemas de hot-reload con Uvicorn + Poetry en MacOS/WSL
# 
# Si el puerto 8000 se queda "Address already in use", este comando restringe
# a uvicorn para que SOLO vigile la carpeta src/, en lugar de monitorizar toda la
# estructura del proyecto (como .venv, que tiene miles de archivos y causa timeouts/cuellos de botella).

echo "🚀 Iniciando Backend FastAPI con Uvicorn (Hot-Reload Safe Mode)..."

# Busca y mata procesos huérfanos que puedan tener ocupado el puerto 8000
lsof -ti:8000 | xargs kill -9 2>/dev/null || true

# Ejecuta uvicorn usando poetry run, limitando la vigilancia al directorio src
poetry run uvicorn src.main:app --reload --reload-dir src --host 0.0.0.0 --port 8000
