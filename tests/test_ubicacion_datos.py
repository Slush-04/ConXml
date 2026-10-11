from pathlib import Path
from unittest.mock import Mock

from conxml.config import Config
from conxml.ui.ubicacion_datos import preparar_ubicacion


def entorno(tmp_path, monkeypatch):
    monkeypatch.setattr('sys.frozen', True, raising=False)
    monkeypatch.setattr('sys.platform', 'win32')
    monkeypatch.setattr('sys.executable', str(tmp_path / 'programa/conxml.exe'))
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'Local'))
    monkeypatch.delenv('CONXML_DATA_DIR', raising=False)
    monkeypatch.setattr('conxml.ui.ubicacion_datos.messagebox.showinfo', Mock())


def test_eleccion_se_conserva_y_no_se_repite(tmp_path, monkeypatch):
    entorno(tmp_path, monkeypatch)
    destino = tmp_path / 'Mis clientes á'
    selector = Mock(return_value=str(destino))
    monkeypatch.setattr('conxml.ui.ubicacion_datos.filedialog.askdirectory', selector)
    assert preparar_ubicacion(None)
    Config().inicializar()
    assert Config().base == destino
    assert (destino / 'boveda').is_dir()
    assert preparar_ubicacion(None)
    selector.assert_called_once()
    assert Config().updates_dir == tmp_path / 'Local/ConXml/updates'


def test_cancelar_no_crea_datos_ni_registro(tmp_path, monkeypatch):
    entorno(tmp_path, monkeypatch)
    monkeypatch.setattr('conxml.ui.ubicacion_datos.filedialog.askdirectory', Mock(return_value=''))
    assert not preparar_ubicacion(None)
    assert not Config().ubicacion_path.exists()
    assert not Config().base.exists()


def test_instalacion_existente_conserva_catalogo(tmp_path, monkeypatch):
    entorno(tmp_path, monkeypatch)
    anterior = Config().base
    anterior.mkdir(parents=True)
    (anterior / 'catalogo.db').write_bytes(b'datos existentes')
    selector = Mock()
    monkeypatch.setattr('conxml.ui.ubicacion_datos.filedialog.askdirectory', selector)
    assert preparar_ubicacion(None)
    assert Config().base == anterior
    assert (anterior / 'catalogo.db').read_bytes() == b'datos existentes'
    selector.assert_not_called()


def test_unidad_ausente_no_crea_catalogo_vacio(tmp_path, monkeypatch):
    entorno(tmp_path, monkeypatch)
    destino = tmp_path / 'unidad'
    Config().guardar_ubicacion(destino)
    destino.rmdir()
    error = Mock()
    monkeypatch.setattr('conxml.ui.ubicacion_datos.messagebox.showerror', error)
    assert not preparar_ubicacion(None)
    assert not destino.exists()
    error.assert_called_once()
