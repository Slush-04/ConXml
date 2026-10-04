from pathlib import Path
import zipfile

from lxml import etree
from pypdf import PdfReader
import pytest

from conxml.export.pdf import generar_pdf, exportar_lote

FIXTURES = Path(__file__).parent / 'fixtures'


@pytest.mark.parametrize('nombre,esperado', [('ingreso_iva.xml', '1,160.00'), ('pago_rep_multiple.xml', 'ImpSaldoInsoluto'), ('nomina_basica.xml', 'Percepciones')])
def test_pdf_conserva_datos_y_complementos(tmp_path, nombre, esperado):
    ruta = generar_pdf(FIXTURES / nombre, tmp_path / 'prueba.pdf')
    reader = PdfReader(ruta)
    texto = '\n'.join(p.extract_text() for p in reader.pages)
    assert esperado in texto
    assert 'UUID:' in texto
    assert 'representación impresa' in texto
    assert len(reader.pages) > 0


def test_lote_deduplica_y_reporta_error_sin_perder_validos(tmp_path):
    invalido = tmp_path / 'invalido.xml'
    invalido.write_text('no xml')
    resultado = exportar_lote([FIXTURES / 'ingreso_iva.xml', FIXTURES / 'ingreso_iva.xml', FIXTURES / 'nomina_basica.xml', invalido], tmp_path / 'lote.zip')
    assert resultado.generados == 2
    assert len(resultado.errores) == 1
    with zipfile.ZipFile(resultado.ruta) as z:
        assert len([n for n in z.namelist() if n.endswith('.pdf')]) == 2
        assert 'errores.json' in z.namelist()


def test_muchos_conceptos_paginar_sin_perder_el_ultimo(tmp_path):
    tree = etree.parse(str(FIXTURES / 'ingreso_iva.xml'))
    ns = {'c': 'http://www.sat.gob.mx/cfd/4'}
    conceptos = tree.find('c:Conceptos', ns)
    modelo = conceptos[0]
    import copy
    for i in range(80):
        nuevo = copy.deepcopy(modelo)
        nuevo.set('Descripcion', f'Concepto-{i} con descripción larga y caracteres & < > para comprobar el ajuste de líneas. ' * 3)
        conceptos.append(nuevo)
    xml = tmp_path / 'largo.xml'
    tree.write(str(xml), encoding='utf-8')
    reader = PdfReader(generar_pdf(xml, tmp_path / 'largo.pdf'))
    assert len(reader.pages) > 3
    assert 'Concepto-79' in '\n'.join(p.extract_text() for p in reader.pages)


def test_lote_totalmente_invalido_no_sustituye_destino(tmp_path):
    destino = tmp_path / 'lote.zip'
    destino.write_bytes(b'original')
    with pytest.raises(ValueError):
        exportar_lote([tmp_path / 'ausente.xml'], destino)
    assert destino.read_bytes() == b'original'


def test_qr_y_cadena_timbre_siguen_secuencia_sat():
    from urllib.parse import urlparse, parse_qs
    from conxml.export.pdf import url_verificacion, cadena_timbre
    root = etree.parse(str(FIXTURES / 'ingreso_iva.xml')).getroot()
    root.set('Sello', 'prueba+/ABC==')
    query = parse_qs(urlparse(url_verificacion(root, 'UUID-PRUEBA')).query)
    assert query == {'id': ['UUID-PRUEBA'], 're': ['EKU9003173C9'], 'rr': ['XAXX010101000'], 'tt': ['1160'], 'fe': ['a+/ABC==']}
    timbre = root.find('.//{http://www.sat.gob.mx/TimbreFiscalDigital}TimbreFiscalDigital')
    assert cadena_timbre(timbre) == '||1.1|123E4567-E89B-12D3-A456-426614174000|2024-02-01T09:20:00|SAT970701NX3|U2VsbG9DRkQ=|20001000000300022323||'
    timbre.set('Leyenda', '  Texto   de prueba  ')
    assert '|Texto de prueba|U2VsbG9DRkQ=|' in cadena_timbre(timbre)
    timbre.attrib.pop('SelloCFD')
    assert cadena_timbre(timbre) is None
    root.attrib.pop('Sello')
    assert url_verificacion(root, 'UUID-PRUEBA') is None


def test_factura_simple_es_compacta_y_conserva_sellos(tmp_path):
    pdf = PdfReader(generar_pdf(FIXTURES / 'ingreso_iva.xml', tmp_path / 'factura.pdf'))
    assert len(pdf.pages) == 1
    texto = pdf.pages[0].extract_text()
    for dato in ('20001000000300022323', 'Sello digital del SAT', 'Cadena original', '160.00', '1,160.00', 'P001'):
        assert dato in texto


def test_diseno_sat_conserva_pedimento_predial_y_sellos_largos(tmp_path):
    tree = etree.parse(str(FIXTURES / 'ingreso_iva.xml'))
    ns = '{http://www.sat.gob.mx/cfd/4}'
    concepto = tree.find(f'.//{ns}Concepto')
    etree.SubElement(concepto, ns + 'InformacionAduanera', NumeroPedimento='24  16  1234  4000001')
    etree.SubElement(concepto, ns + 'CuentaPredial', Numero='PREDIAL123')
    concepto.set('ValorUnitario', '500.123456')
    sello = 'QUJD' * 85 + 'FINSELLO'
    tree.getroot().set('Sello', sello)
    xml = tmp_path / 'aduana.xml'
    tree.write(str(xml), encoding='UTF-8')
    pdf = PdfReader(generar_pdf(xml, tmp_path / 'aduana.pdf'))
    texto = '\n'.join(p.extract_text() for p in pdf.pages)
    assert '24 16 1234 4000001' in ' '.join(texto.split())
    assert 'PREDIAL123' in texto
    assert '500.123456' in texto
    assert sello in ''.join(texto.split())
    assert pdf.pages[0].mediabox.width > pdf.pages[0].mediabox.height
