"""Punto de entrada de la interfaz gráfica (usado por PyInstaller)."""

from conxml.startup import run_gui

if __name__ == "__main__":
    import sys
    if '--sat-periodico' in sys.argv:
        from conxml.sat.periodicas import main
        sys.argv.remove('--sat-periodico')
        raise SystemExit(main())
    # La importación queda dentro de la función para que también se registren
    # fallos tempranos al cargar módulos o recursos dentro del ejecutable.
    def _entrypoint() -> None:
        from conxml.ui.app import main

        main()

    run_gui(_entrypoint)
