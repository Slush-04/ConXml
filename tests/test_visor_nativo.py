from pathlib import Path
from types import SimpleNamespace
from conxml.ui import visor_pdf


def test_visor_nativo_conserva_archivo_hasta_cierre_y_limpia(tmp_path, monkeypatch):
    ejecutable = tmp_path / 'assets' / 'conxml-pdf-viewer'
    ejecutable.parent.mkdir()
    ejecutable.touch()
    ruta = tmp_path / 'vista.pdf'
    ruta.write_bytes(b'pdf-original')
    pendientes = []
    parent = SimpleNamespace(after=lambda tiempo, callback: pendientes.append(callback))
    estados = iter([None, 0])
    proceso = SimpleNamespace(poll=lambda: next(estados))
    argumentos = []
    monkeypatch.setattr(visor_pdf.sys, 'platform', 'darwin')
    monkeypatch.setattr(visor_pdf.sys, 'frozen', True, raising=False)
    monkeypatch.setattr(visor_pdf.sys, '_MEIPASS', str(tmp_path), raising=False)
    monkeypatch.setattr(visor_pdf.subprocess, 'Popen', lambda args: argumentos.append(args) or proceso)
    assert visor_pdf.abrir_vista_previa(parent, ruta) is proceso
    assert argumentos == [[str(ejecutable), str(ruta)]]
    pendientes.pop(0)()
    assert ruta.exists()
    pendientes.pop(0)()
    assert not ruta.exists()


def test_visor_nativo_falla_y_recupera_vista(tmp_path, monkeypatch):
    ejecutable = tmp_path / 'assets' / 'conxml-pdf-viewer'
    ejecutable.parent.mkdir()
    ejecutable.touch()
    ruta = tmp_path / 'vista.pdf'
    ruta.write_bytes(b'pdf-original')
    pendientes = []
    parent = SimpleNamespace(after=lambda tiempo, callback: pendientes.append(callback))
    monkeypatch.setattr(visor_pdf.sys, 'platform', 'darwin')
    monkeypatch.setattr(visor_pdf.sys, 'frozen', True, raising=False)
    monkeypatch.setattr(visor_pdf.sys, '_MEIPASS', str(tmp_path), raising=False)
    monkeypatch.setattr(visor_pdf.subprocess, 'Popen', lambda args: SimpleNamespace(poll=lambda: 3))
    recuperados = []
    monkeypatch.setattr(visor_pdf, 'VisorPDF', lambda parent, archivo: recuperados.append(archivo))
    visor_pdf.abrir_vista_previa(parent, ruta)
    pendientes.pop(0)()
    assert recuperados == [ruta]
    assert ruta.exists()
