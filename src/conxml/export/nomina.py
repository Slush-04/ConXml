"""Export de recibos de nómina a Excel."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from conxml.catalog.db import Catalogo
from conxml.cfdi import parse_comprobante, parse_nomina
from conxml.export.listado import _fecha, _fill_estatus, _numero

ENCABEZADOS_NOMINA = [
    "Cliente",
    "Estado SAT",
    "EsCancelable",
    "EstatusCancelacion",
    "UUID",
    "Serie",
    "Folio",
    "FechaTimbradoXML",
    "FechaEmisionXML",
    "RFC Emisor",
    "Nombre Emisor",
    "Registro Patronal",
    "RFC Receptor",
    "Nombre Receptor",
    "CURP",
    "Num Empleado",
    "Puesto",
    "Tipo Nomina",
    "Fecha Pago",
    "Fecha Inicial Pago",
    "Fecha Final Pago",
    "Num Dias Pagados",
    "Periodicidad Pago",
    "Total Percepciones",
    "Total Deducciones",
    "Total Otros Pagos",
    "SubTotal",
    "Descuento",
    "Total",
    "Moneda",
    "Archivo XML",
]

ESTILO_ENCABEZADO = Font(bold=True)


def exportar_nomina(
    catalogo: Catalogo,
    destino: str | Path,
    cliente: str | None = None,
) -> Path:
    """Genera un Excel con los recibos de Nómina del catálogo."""
    destino = Path(destino)
    filas = list(catalogo.consulta(cliente=cliente, tipo="N"))

    wb = Workbook()
    ws = wb.active
    ws.title = "Nómina"
    ws.append(ENCABEZADOS_NOMINA)
    for celda in ws[1]:
        celda.font = ESTILO_ENCABEZADO

    for fila in filas:
        path_xml = Path(fila["ruta"])
        nom_data = None
        if path_xml.is_file():
            try:
                comp = parse_comprobante(path_xml)
                nom_data = parse_nomina(comp)
            except Exception:
                pass

        reg_patronal = nom_data.registro_patronal if nom_data else None
        curp = nom_data.curp if nom_data else None
        num_emp = nom_data.num_empleado if nom_data else None
        puesto = nom_data.puesto if nom_data else None
        tipo_nom = nom_data.tipo_nomina if nom_data else None
        f_pago = nom_data.fecha_pago.strftime("%Y-%m-%d") if (nom_data and nom_data.fecha_pago) else None
        f_ini = nom_data.fecha_inicial_pago.strftime("%Y-%m-%d") if (nom_data and nom_data.fecha_inicial_pago) else None
        f_fin = nom_data.fecha_final_pago.strftime("%Y-%m-%d") if (nom_data and nom_data.fecha_final_pago) else None
        dias_pag = float(nom_data.num_dias_pagados) if (nom_data and nom_data.num_dias_pagados) else None
        period = nom_data.periodicidad_pago if nom_data else None
        t_per = float(nom_data.total_percepciones) if (nom_data and nom_data.total_percepciones) else None
        t_ded = float(nom_data.total_deducciones) if (nom_data and nom_data.total_deducciones) else None
        t_otr = float(nom_data.total_otros_pagos) if (nom_data and nom_data.total_otros_pagos) else None

        ws.append([
            fila["cliente"],
            fila["estatus"],
            fila["es_cancelable"],
            fila["estatus_cancelacion"],
            fila["uuid"],
            fila["serie"],
            fila["folio"],
            _fecha(fila["fecha_timbrado"]),
            _fecha(fila["fecha"]),
            fila["emisor_rfc"],
            fila["emisor_nombre"],
            reg_patronal,
            fila["receptor_rfc"],
            fila["receptor_nombre"],
            curp,
            num_emp,
            puesto,
            tipo_nom,
            f_pago,
            f_ini,
            f_fin,
            dias_pag,
            period,
            t_per,
            t_ded,
            t_otr,
            _numero(fila["subtotal"]),
            _numero(fila["descuento"]),
            _numero(fila["total"]),
            fila["moneda"],
            fila["ruta"],
        ])
        n = ws.max_row
        fill = _fill_estatus(fila["estatus"])
        if fill is not None:
            ws.cell(row=n, column=2).fill = fill

    ws.auto_filter.ref = ws.dimensions
    ws.freeze_panes = "A2"
    destino.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(destino))
    return destino
