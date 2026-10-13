#!/bin/zsh
# Ejecuta la versión local actualizada, con los datos de este proyecto.
cd -- "$(dirname -- "$0")" || exit 1
exec .venv-mac/bin/conxml-gui
