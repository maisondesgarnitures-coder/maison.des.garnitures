@echo off
chcp 65001 > NUL
title Maison des Garnitures - Partage avec un collegue
cd /d "%~dp0"

where python > NUL 2>&1
if errorlevel 1 (
  echo.
  echo   Python est introuvable sur cet ordinateur.
  echo   Installe-le depuis https://www.python.org/downloads/
  echo   IMPORTANT : coche "Add Python to PATH" pendant l'installation.
  echo.
  pause
  exit /b
)

python lancer.py --partage
pause
