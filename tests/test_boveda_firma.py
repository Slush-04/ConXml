"""La e.firma local se aísla por cliente y excluye la contraseña."""
from __future__ import annotations

import os
from pathlib import Path

from conxml.config import Config
from conxml.sat.boveda_firma import archivos_guardados, carpeta_firma, guardar_archivos, quitar_archivos


def test_firma_local_por_cliente(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CONXML_DATA_DIR", str(tmp_path))
    config = Config()
    cer = tmp_path / "entrada.cer"
    key = tmp_path / "entrada.key"
    cer.write_bytes(b"certificado")
    key.write_bytes(b"llave")

    guardados = guardar_archivos(config, "CLI-1", cer, key)
    assert archivos_guardados(config, "CLI-1") == guardados
    assert archivos_guardados(config, "CLI-2") is None
    assert guardados[0].read_bytes() == b"certificado"
    assert guardados[1].read_bytes() == b"llave"
    assert sorted(p.name for p in carpeta_firma(config, "CLI-1").iterdir()) == ["certificado.cer", "llave_privada.key"]
    if os.name == "posix":
        assert guardados[1].stat().st_mode & 0o077 == 0

    quitar_archivos(config, "CLI-1")
    assert archivos_guardados(config, "CLI-1") is None
