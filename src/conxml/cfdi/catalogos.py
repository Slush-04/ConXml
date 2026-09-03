"""Catálogos oficiales del SAT (descripciones).

Fuente: catálogos c_* del SAT para CFDI 4.0 (c_UsoCFDI, c_RegimenFiscal,
c_FormaPago, c_TipoDeComprobante). Revisión 2026-09.
Si el SAT publica una clave nueva, agrégala aquí con su descripción oficial;
`describir()` devuelve el código solo cuando no lo conoce (sin inventar).
"""

from __future__ import annotations

from types import MappingProxyType

TIPO_COMPROBANTE: dict[str, str] = {
    "I": "Ingreso",
    "E": "Egreso",
    "T": "Traslado",
    "N": "Nómina",
    "P": "Pago",
}

METODO_PAGO: dict[str, str] = {
    "PUE": "Pago en una sola exhibición",
    "PPD": "Pago en parcialidades o diferido",
}

# c_UsoCFDI vigente (25 claves). No agregar G04-G99/D11-D40/I09-I46: no existen.
USO_CFDI: dict[str, str] = MappingProxyType({  # type: ignore[assignment]
    "G01": "Adquisición de mercancías",
    "G02": "Devoluciones, descuentos o bonificaciones",
    "G03": "Gastos en general",
    "I01": "Construcciones",
    "I02": "Mobiliario y equipo de oficina por inversiones",
    "I03": "Equipo de transporte",
    "I04": "Equipo de cómputo y accesorios",
    "I05": "Dados, troqueles, moldes, matrices y herramental",
    "I06": "Comunicaciones telefónicas",
    "I07": "Comunicaciones satelitales",
    "I08": "Otra maquinaria y equipo",
    "D01": "Honorarios médicos, dentales y gastos hospitalarios",
    "D02": "Gastos médicos por incapacidad o discapacidad",
    "D03": "Gastos funerales",
    "D04": "Donativos",
    "D05": "Intereses reales efectivamente pagados por créditos hipotecarios",
    "D06": "Aportaciones voluntarias al SAR",
    "D07": "Primas por seguros de gastos médicos",
    "D08": "Gastos de transportación escolar obligatoria",
    "D09": "Depósitos en cuentas para el ahorro, primas que tengan como base planes de pensiones",
    "D10": "Pagos por servicios educativos (colegiaturas)",
    "S01": "Sin efectos fiscales",
    "CP01": "Pagos",
    "CN01": "Nómina",
    "P01": "Por definir",
})

REGIMEN_FISCAL: dict[str, str] = {
    "601": "General de Ley Personas Morales",
    "603": "Personas Morales con Fines no Lucrativos",
    "605": "Sueldos y Salarios e Ingresos Asimilados a Salarios",
    "606": "Arrendamiento",
    "607": "Régimen de Enajenación o Adquisición de Bienes",
    "608": "Demás ingresos",
    "609": "Consolidación",
    "610": "Residentes en el Extranjero sin Establecimiento Permanente en México",
    "611": "Ingresos por Dividendos (socios y accionistas)",
    "612": "Personas Físicas con Actividades Empresariales y Profesionales",
    "613": "Ingresos por intereses",
    "614": "Ingresos por arrendamiento",
    "615": "Demás ingresos",
    "616": "Sin obligaciones fiscales",
    "620": "Sociedades Cooperativas de Producción",
    "621": "Incorporación Fiscal",
    "622": "Actividades Agrícolas, Ganaderas, Silvícolas y Pesqueras",
    "623": "Opcional para Grupos de Sociedades",
    "624": "Coordinados",
    "625": "Régimen de las Actividades Empresariales con Ingresos a través de Plataformas Tecnológicas",
    "626": "Régimen Simplificado de Confianza",
    "628": "Hidrocarburos",
    "629": "De los regímenes fiscales preferentes y de las empresas multinacionales",
    "630": "Enajenación de acciones en bolsa de valores",
    "631": "Régimen de las empresas que tributan en el extranjero",
}

FORMA_PAGO: dict[str, str] = {
    "01": "Efectivo",
    "02": "Cheque nominativo",
    "03": "Transferencia electrónica de fondos",
    "04": "Tarjeta de crédito",
    "05": "Monedero electrónico",
    "06": "Dinero electrónico",
    "08": "Vales de despensa",
    "12": "Dación en pago",
    "13": "Pago por subrogación",
    "14": "Pago por consignación",
    "15": "Condonación",
    "17": "Compensación",
    "23": "Novación",
    "24": "Confusión",
    "25": "Remisión de deuda",
    "26": "Prescripción o caducidad",
    "27": "A satisfacción del acreedor",
    "28": "Tarjeta de débito",
    "29": "Tarjeta de servicios",
    "30": "Aplicación de anticipos",
    "31": "Intermediario pagos",
    "32": "Pagos con tarjeta de crédito",
    "99": "Por definir",
}


def describir(catalogo: dict[str, str], codigo: str | None) -> str:
    """Devuelve 'CÓDIGO - Descripción' o el código solo si no está en el catálogo."""
    if not codigo:
        return ""
    descripcion = catalogo.get(codigo)
    return f"{codigo} - {descripcion}" if descripcion else codigo
