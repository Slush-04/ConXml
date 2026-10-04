"""Representación PDF local del XML original, individual o ZIP por lote."""
from __future__ import annotations

import json
import os
import re
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape

from lxml import etree
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle

from conxml.cfdi.parser import NSMAP, parse_comprobante


def nombre_pdf(uuid: str) -> str:
    return re.sub(r'[^A-Za-z0-9_-]', '_', uuid) + '.pdf'


def url_verificacion(root, uuid: str) -> str | None:
    """Expresión del QR de CFDI según Anexo 20 (sin consultar la red)."""
    from decimal import Decimal
    from urllib.parse import urlencode
    emisor = root.find('cfdi:Emisor', NSMAP)
    receptor = root.find('cfdi:Receptor', NSMAP)
    sello = root.get('Sello', '')
    if not uuid or emisor is None or receptor is None or len(sello) < 8:
        return None
    if not emisor.get('Rfc') or not receptor.get('Rfc') or root.get('Total') is None:
        return None
    total = format(Decimal(root.get('Total')), 'f')
    if '.' in total:
        total = total.rstrip('0').rstrip('.')
    return 'https://verificacfdi.facturaelectronica.sat.gob.mx/default.aspx?' + urlencode(
        {'id': uuid, 're': emisor.get('Rfc'), 'rr': receptor.get('Rfc'), 'tt': total, 'fe': sello[-8:]})


def cadena_timbre(timbre) -> str | None:
    """Secuencia TFD 1.1 del Anexo 20; no sustituye validación de firmas."""
    claves = ('Version', 'UUID', 'FechaTimbrado', 'RfcProvCertif', 'Leyenda', 'SelloCFD', 'NoCertificadoSAT')
    if timbre is None or timbre.get('Version') != '1.1':
        return None
    if any(not timbre.get(k) for k in claves if k != 'Leyenda'):
        return None
    return '||' + '|'.join(' '.join(timbre.get(k).split()) for k in claves if timbre.get(k)) + '||'


def generar_pdf(xml: Path, destino: Path) -> Path:
    """Factura legible con organización inspirada en representaciones del SAT."""
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics.barcode.qr import QrCodeWidget
    from reportlab.platypus import Table, KeepTogether
    from conxml.cfdi.catalogos import FORMA_PAGO, METODO_PAGO, REGIMEN_FISCAL, describir

    if Path(xml).resolve() == Path(destino).resolve() or Path(destino).suffix.lower() != '.pdf':
        raise ValueError('Elige un archivo .pdf distinto del XML original.')
    c = parse_comprobante(xml)
    root = etree.parse(str(xml), etree.XMLParser(resolve_entities=False, no_network=True)).getroot()
    timbre = root.find('.//tfd:TimbreFiscalDigital', NSMAP)
    azul = colors.black
    gris = colors.HexColor('#c5c5c5')
    borde = colors.HexColor('#555555')
    pagina = landscape(A4)
    ancho = pagina[0] - 60
    estilos = getSampleStyleSheet()
    cuerpo = ParagraphStyle('FacturaTexto', parent=estilos['BodyText'], fontSize=8.5, leading=10.5, spaceAfter=2, textColor=colors.black, splitLongWords=True)
    pequeno = ParagraphStyle('FacturaSello', parent=cuerpo, fontSize=7, leading=8.5)
    heading = ParagraphStyle('FacturaSeccion', parent=cuerpo, fontSize=9, leading=12, textColor=azul, spaceBefore=10, spaceAfter=5, fontName='Helvetica-Bold', keepWithNext=True)
    story = []

    def texto(valor, estilo=cuerpo):
        return Paragraph(escape(str(valor)).replace('\n', '<br/>'), estilo)

    def campo(nombre, valor):
        return Paragraph(f'<b>{escape(nombre)}:</b> {escape(str(valor or "No especificado"))}', cuerpo)

    def tabla(filas, anchos=None, encabezado=False, lineas=True, estilo_encabezado=None, estilo_celda=None):
        t = LongTable([[v if hasattr(v, 'wrap') or isinstance(v, list) else texto(v, (estilo_encabezado if i == 0 and encabezado else estilo_celda) or cuerpo) for v in fila] for i, fila in enumerate(filas)], colWidths=anchos or (ancho * .3, ancho * .7), repeatRows=int(encabezado), splitInRow=1, hAlign='LEFT')
        estilo = [('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6), ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2)]
        if lineas:
            estilo.append(('LINEBELOW', (0, 0), (-1, -1), .3, borde))
        if encabezado:
            estilo += [('BACKGROUND', (0, 0), (-1, 0), gris), ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#fafbfc')])]
        t.setStyle(TableStyle(estilo))
        story.append(t)
        return t

    def seccion(nombre):
        story.append(Paragraph(escape(nombre), heading))

    tipos = {'I': 'Factura de ingreso', 'E': 'Nota de crédito', 'T': 'Comprobante de traslado', 'P': 'Recibo de pagos', 'N': 'Recibo de nómina'}
    emisor = root.find('cfdi:Emisor', NSMAP)
    receptor = root.find('cfdi:Receptor', NSMAP)
    def attr(el, key):
        return el.get(key, '') if el is not None else ''
    def etiqueta(nombre):
        return Paragraph('<b>' + escape(nombre) + ':</b>', cuerpo)
    usos = {'G01':'Adquisición de mercancías','G02':'Devoluciones, descuentos o bonificaciones','G03':'Gastos en general','I01':'Construcciones','I02':'Mobiliario y equipo de oficina por inversiones','I03':'Equipo de transporte','I04':'Equipo de cómputo y accesorios','I05':'Dados, troqueles, moldes, matrices y herramental','I06':'Comunicaciones telefónicas','I07':'Comunicaciones satelitales','I08':'Otra maquinaria y equipo','CP01':'Pagos','CN01':'Nómina','S01':'Sin efectos fiscales'}
    izquierda = [('RFC emisor', attr(emisor,'Rfc')), ('Nombre emisor',attr(emisor,'Nombre')), ('RFC receptor',attr(receptor,'Rfc')), ('Nombre receptor',attr(receptor,'Nombre')), ('Uso CFDI',describir(usos,attr(receptor,'UsoCFDI'))), ('Régimen fiscal receptor',describir(REGIMEN_FISCAL,attr(receptor,'RegimenFiscalReceptor'))), ('Código postal receptor',attr(receptor,'DomicilioFiscalReceptor'))]
    derecha = [('Folio fiscal / UUID',c.uuid or 'Sin timbre'), ('No. de serie del CSD',root.get('NoCertificado')), ('Código postal, fecha y hora de emisión', f'{root.get("LugarExpedicion", "")} {root.get("Fecha", "")}'), ('Efecto de comprobante',tipos.get(c.tipo_comprobante,c.tipo_comprobante)), ('Régimen fiscal emisor',describir(REGIMEN_FISCAL,attr(emisor,'RegimenFiscal'))), ('Serie y folio',f'{root.get("Serie", "")} {root.get("Folio", "")}'), ('Exportación',root.get('Exportacion'))]
    tabla([(etiqueta(k),texto(v or 'No especificado'),etiqueta(k2),texto(v2 or 'No especificado')) for (k,v),(k2,v2) in zip(izquierda,derecha)], (116,ancho/2-116,158,ancho/2-158), lineas=False)
    conceptos = root.findall('cfdi:Conceptos/cfdi:Concepto', NSMAP)
    def dinero(valor):
        from decimal import Decimal, InvalidOperation
        if valor is None or valor == '':
            return ''
        try:
            numero = Decimal(valor)
            decimales = max(2, -numero.as_tuple().exponent)
            return f'{numero:,.{decimales}f}'
        except InvalidOperation:
            return str(valor)

    if conceptos:
        seccion('Conceptos')
        estilo_cabecera = ParagraphStyle('CabeceraConceptos', parent=cuerpo, fontName='Helvetica-Bold', fontSize=7.3, leading=9, alignment=1)
        estilo_celda = ParagraphStyle('CeldaConceptos', parent=cuerpo, fontSize=8, leading=10, alignment=1)
        anchos = [77,94,55,62,71,85,75,72,91,ancho-682]
        for el in conceptos:
            pedimentos = el.xpath('.//cfdi:InformacionAduanera/@NumeroPedimento',namespaces=NSMAP)
            prediales = el.xpath('./cfdi:CuentaPredial/@Numero',namespaces=NSMAP)
            t = tabla([('Clave del producto y/o servicio','No. identificación','Cantidad','Clave de unidad','Unidad','Valor unitario','Importe','Descuento','No. de pedimento','No. de cuenta predial'), (el.get('ClaveProdServ',''),el.get('NoIdentificacion',''),el.get('Cantidad',''),el.get('ClaveUnidad',''),el.get('Unidad',''),dinero(el.get('ValorUnitario')),dinero(el.get('Importe')),dinero(el.get('Descuento')),' / '.join(pedimentos),' / '.join(prediales))],anchos,True, estilo_encabezado=estilo_cabecera, estilo_celda=estilo_celda)
            t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.5,borde),('ALIGN',(0,0),(-1,-1),'CENTER')]))
            tax_width = ancho*.53
            impuestos_concepto = [('Impuesto','Tipo','Base','Tipo factor','Tasa o cuota','Importe')]
            for impuesto in el.xpath('./cfdi:Impuestos/*/*', namespaces=NSMAP):
                nombre = {'001':'ISR','002':'IVA','003':'IEPS'}.get(impuesto.get('Impuesto'),impuesto.get('Impuesto',''))
                tasa = impuesto.get('TasaOCuota','')
                if tasa and impuesto.get('TipoFactor') == 'Tasa':
                    from decimal import Decimal
                    tasa = f'{Decimal(tasa)*100:.6f}%'
                impuestos_concepto.append((nombre,etree.QName(impuesto).localname,dinero(impuesto.get('Base')),impuesto.get('TipoFactor',''),tasa,dinero(impuesto.get('Importe'))))
            tax = LongTable([[texto(v,pequeno) for v in fila] for fila in impuestos_concepto], colWidths=[(tax_width-12)*x for x in (.14,.16,.17,.16,.19,.18)], repeatRows=1, splitInRow=1)
            tax.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3)]))
            descripcion = el.get('Descripcion','')
            if el.get('ObjetoImp'):
                descripcion += '\nObjeto de impuesto: ' + el.get('ObjetoImp')
            t = tabla([(etiqueta('Descripción'),texto(descripcion),tax)], (65,ancho*.47-65,tax_width), lineas=False)
            t.setStyle(TableStyle([('BACKGROUND',(0,0),(0,-1),gris),('BOX',(0,0),(1,-1),.5,borde),('LINEAFTER',(0,0),(0,-1),.5,borde)]))
            story.append(Spacer(1,7))

    story.append(Spacer(1, 7))
    info = [campo('Moneda', {'MXN':'Peso Mexicano','USD':'Dólar estadounidense','EUR':'Euro','XXX':'Sin moneda'}.get(root.get('Moneda'),root.get('Moneda'))), campo('Forma de pago', describir(FORMA_PAGO, root.get('FormaPago'))), campo('Método de pago', describir(METODO_PAGO, root.get('MetodoPago')))]
    for k in ('TipoCambio', 'CondicionesDePago'):
        if root.get(k):
            info.append(campo(k, root.get(k)))
    numero = ParagraphStyle('Numero', parent=cuerpo, alignment=2)
    def total_fila(nombre, valor):
        return [etiqueta(nombre), texto(valor, numero)]
    totales = [total_fila('Subtotal', '$ ' + dinero(str(c.subtotal)))]
    if c.descuento:
        totales.append(total_fila('Descuento', '$ ' + dinero(str(c.descuento))))
    impuestos = root.find('cfdi:Impuestos', NSMAP)
    if impuestos is not None:
        for el in impuestos.xpath('./*/*'):
            nombre = {'001':'ISR','002':'IVA','003':'IEPS'}.get(el.get('Impuesto'), el.get('Impuesto',''))
            label = f'{etree.QName(el).localname} {nombre}'
            if el.get('TasaOCuota'):
                from decimal import Decimal
                label += ' ' + f'{Decimal(el.get("TasaOCuota"))*100:.6f}%'
            totales.append(total_fila(label, '$ ' + dinero(el.get('Importe')) if el.get('Importe') is not None else el.get('TipoFactor')))
    totales.append(total_fila('Total', '$ ' + dinero(str(c.total))))
    resumen = Table(totales, colWidths=(ancho*.35-6,ancho*.14-6))
    resumen.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),2),('BOTTOMPADDING',(0,0),(-1,-1),2)]))
    tabla([(info, resumen)], (ancho*.51, ancho*.49), lineas=False)
    story.append(Spacer(1, 15))

    def detalle(el, path=''):
        if not isinstance(el.tag, str):
            return
        local = etree.QName(el).localname
        path = f'{path} / {local}' if path else local
        datos = '   |   '.join(f'{k}: {v}' for k,v in el.attrib.items())
        if el.text and el.text.strip():
            datos += ' ' + el.text.strip()
        if datos:
            tabla([(path, datos)])
        for hijo in el:
            detalle(hijo, path)

    # Conservar complementos, relaciones y atributos adicionales sin volcar el timbre dos veces.
    extras = [(k,v) for k,v in root.attrib.items() if not k.startswith('{') and k not in {'Version','Serie','Folio','Fecha','Sello','Certificado','NoCertificado','SubTotal','Descuento','Moneda','Total','TipoDeComprobante','Exportacion','MetodoPago','FormaPago','LugarExpedicion','TipoCambio','CondicionesDePago'}]
    if extras:
        seccion('Datos adicionales del comprobante')
        tabla(extras)
    for el, conocidos in ((emisor, {'Rfc','Nombre','RegimenFiscal'}), (receptor, {'Rfc','Nombre','DomicilioFiscalReceptor','RegimenFiscalReceptor','UsoCFDI'})):
        if el is not None:
            extra = [(k,v) for k,v in el.attrib.items() if k not in conocidos]
            if extra:
                seccion('Datos adicionales: ' + etree.QName(el).localname)
                tabla(extra)
    for i, el in enumerate(conceptos,1):
        extra = [(k,v) for k,v in el.attrib.items() if k not in {'Cantidad','Unidad','ClaveUnidad','ClaveProdServ','Descripcion','ValorUnitario','Importe','Descuento','ObjetoImp','NoIdentificacion'}]
        if extra:
            seccion(f'Concepto {i}: datos adicionales')
            tabla(extra)
        for hijo in el:
            if isinstance(hijo.tag,str) and etree.QName(hijo).localname not in {'Impuestos','InformacionAduanera','CuentaPredial'}:
                seccion(f'Concepto {i}: información adicional')
                detalle(hijo)
    for hijo in root:
        if not isinstance(hijo.tag,str):
            continue
        local = etree.QName(hijo).localname
        if local == 'Complemento':
            for complemento in hijo:
                if isinstance(complemento.tag,str) and complemento.tag != '{' + NSMAP['tfd'] + '}TimbreFiscalDigital':
                    seccion('Complemento: ' + etree.QName(complemento).localname)
                    detalle(complemento)
        elif local not in {'Emisor','Receptor','Conceptos','Impuestos'}:
            seccion(local)
            detalle(hijo)

    url = url_verificacion(root, c.uuid)
    qr = texto('QR no disponible: faltan datos en el XML.', pequeno)
    if url:
        widget = QrCodeWidget(url, barLevel='M')
        x0,y0,x1,y1 = widget.getBounds()
        qr = Drawing(96,96, transform=[96/(x1-x0),0,0,96/(y1-y0),-x0*96/(x1-x0),-y0*96/(y1-y0)])
        qr.add(widget)
    for nombre, valor in [('Sello digital del CFDI', root.get('Sello')), ('Sello digital del SAT', attr(timbre,'SelloSAT'))]:
        etiqueta_sello = Paragraph('<b>' + escape(nombre) + ':</b>', cuerpo)
        contenido = texto(valor or 'No disponible en el XML', pequeno)
        story.extend([KeepTogether([etiqueta_sello, contenido]), Spacer(1,8)])
    metadata = Table([[campo('RFC del proveedor de certificación',attr(timbre,'RfcProvCertif')), campo('Fecha y hora de certificación',attr(timbre,'FechaTimbrado'))], [campo('No. de serie del certificado SAT',attr(timbre,'NoCertificadoSAT')), texto('')]], colWidths=((ancho-120)*.53,(ancho-120)*.47))
    metadata.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),12),('TOPPADDING',(0,0),(-1,-1),2),('BOTTOMPADDING',(0,0),(-1,-1),2)]))
    certificacion = [Paragraph('<b>Cadena original del complemento de certificación digital del SAT:</b>', cuerpo), texto(cadena_timbre(timbre) or 'No disponible en el XML', pequeno), Spacer(1,6), metadata]
    bloque = Table([[qr, certificacion]], colWidths=(115,ancho-115), hAlign='LEFT')
    bloque.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),5)]))
    if bloque.wrap(ancho, pagina[1])[1] < 350:
        story.append(KeepTogether([bloque]))
    else:
        story.append(qr)
        story.extend(certificacion)

    def pie(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(azul)
        canvas.setFont('Helvetica-Bold', 8)
        canvas.drawCentredString(pagina[0]/2, 23, 'Este documento es una representación impresa de un CFDI')
        canvas.setFont('Helvetica', 6)
        canvas.drawCentredString(pagina[0]/2, 12, 'ConXml | Generado a partir del XML original, sin consulta de estatus SAT')
        canvas.setFont('Helvetica', 7)
        canvas.drawRightString(pagina[0]-30, 23, f'Página {doc.page}')
        canvas.restoreState()

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    fd, temporal = tempfile.mkstemp(prefix='.pdf-', suffix='.pdf', dir=destino.parent)
    os.close(fd)
    try:
        SimpleDocTemplate(temporal, pagesize=pagina, rightMargin=30, leftMargin=30, topMargin=25, bottomMargin=40, title=f'CFDI {c.uuid or ""}', author='ConXml').build(story, onFirstPage=pie, onLaterPages=pie)
        os.replace(temporal, destino)
    finally:
        Path(temporal).unlink(missing_ok=True)
    return destino


@dataclass
class ResultadoPDFLote:
    ruta: Path
    generados: int = 0
    errores: list[dict] = field(default_factory=list)


def exportar_lote(xmls: list[Path], destino: Path) -> ResultadoPDFLote:
    resultado = ResultadoPDFLote(Path(destino))
    destino = Path(destino)
    if destino.suffix.lower() != '.zip':
        raise ValueError('El destino del lote debe ser un archivo .zip.')
    destino.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='conxml-pdfs-') as temporal:
        stage = Path(temporal)
        archivos = []
        vistos = set()
        for xml in dict.fromkeys(xmls):
            try:
                c = parse_comprobante(xml)
                if not c.uuid:
                    raise ValueError('El comprobante no tiene UUID.')
                if c.uuid in vistos:
                    continue
                nombre = nombre_pdf(c.uuid)
                generar_pdf(xml, stage / nombre)
                vistos.add(c.uuid)
                archivos.append(nombre)
                resultado.generados += 1
            except Exception as exc:
                resultado.errores.append({'xml': str(xml), 'error': str(exc)})
        if not archivos:
            raise ValueError('No se pudo generar ningún PDF. ' + '; '.join(e['error'] for e in resultado.errores[:3]))
        with zipfile.ZipFile(stage / 'lote.zip', 'w', zipfile.ZIP_DEFLATED) as z:
            for nombre in archivos:
                z.write(stage / nombre, nombre)
            if resultado.errores:
                z.writestr('errores.json', json.dumps(resultado.errores, ensure_ascii=False, indent=2))
        fd, tmp_zip = tempfile.mkstemp(prefix='.pdf-lote-', suffix='.zip', dir=destino.parent)
        os.close(fd)
        try:
            import shutil
            shutil.copyfile(stage / 'lote.zip', tmp_zip)
            os.replace(tmp_zip, destino)
        finally:
            Path(tmp_zip).unlink(missing_ok=True)
    return resultado
