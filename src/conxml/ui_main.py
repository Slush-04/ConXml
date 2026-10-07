"""Punto de entrada de la interfaz gráfica (usado por PyInstaller)."""

from conxml.startup import run_gui

if __name__ == "__main__":
    # La importación queda dentro de la función para que también se registren
    # fallos tempranos al cargar módulos o recursos dentro del ejecutable.
    def _entrypoint() -> None:
        from conxml.ui.app import main

        main()

    run_gui(_entrypoint)
