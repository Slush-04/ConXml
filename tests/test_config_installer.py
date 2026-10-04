from pathlib import Path
from conxml.config import Config, migrar_datos_windows


def test_windows_persistent_path_and_legacy_copy(tmp_path, monkeypatch):
    exe = tmp_path / 'Programs' / 'ConXml' / 'conxml.exe'
    old = exe.parent / 'data'
    old.mkdir(parents=True)
    for name in ['catalogo.db', 'preferencias.json', 'cliente/Emitidos/a.xml', 'respaldos/a.zip']:
        path = old / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(name.encode())
    monkeypatch.delenv('CONXML_DATA_DIR', raising=False)
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'Local'))
    monkeypatch.setattr('sys.platform', 'win32')
    monkeypatch.setattr('sys.frozen', True, raising=False)
    monkeypatch.setattr('sys.executable', str(exe))
    config = Config()
    assert config.base == tmp_path / 'Local/ConXml/data'
    config.inicializar()
    for file in old.rglob('*'):
        if file.is_file():
            assert (config.base / file.relative_to(old)).read_bytes() == file.read_bytes()
    (config.base / 'preferencias.json').write_text('nueva')
    assert config.base.joinpath('preferencias.json').read_text() == 'nueva'
    assert old.joinpath('preferencias.json').read_text() == 'preferencias.json'


def test_override_is_preserved_and_initialized(tmp_path, monkeypatch):
    monkeypatch.setenv('CONXML_DATA_DIR', str(tmp_path / 'datos'))
    config = Config()
    config.inicializar()
    assert config.base == tmp_path / 'datos'
    assert config.carpeta_boveda.is_dir()
    assert config.respaldos.is_dir()


def test_failed_migration_does_not_leave_partial_data(tmp_path, monkeypatch):
    import pytest
    import shutil
    old = tmp_path / 'old'
    old.mkdir()
    def fail(*args, **kwargs):
        raise OSError('disco lleno')
    monkeypatch.setattr(shutil, 'copytree', fail)
    target = tmp_path / 'new/data'
    with pytest.raises(OSError):
        migrar_datos_windows(old, target)
    assert not target.exists()
    assert list(target.parent.iterdir()) == []
