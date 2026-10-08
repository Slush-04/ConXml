"""Consulta solicitudes SAT y recupera paquetes con avance persistente."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from conxml.catalog.db import Catalogo
from conxml.catalog.importer import importar_carpetas
from conxml.config import Config
from conxml.sat.almacenamiento import guardar_paquete
from conxml.sat.descarga_masiva import ClienteDescargaSAT, ErrorDescargaSAT, RespuestaSAT


@dataclass
class ResultadoSeguimiento:
    respuesta: RespuestaSAT
    copiados: int = 0
    errores: int = 0
    insertados: int = 0
    recuperada: bool = False


def procesar_solicitud(
    sat: ClienteDescargaSAT, db_path: Path, datos: dict, config: Config,
) -> ResultadoSeguimiento:
    """Consulta el SAT y guarda cada paquete completado antes de pedir otro.

    Sirve tanto para la acción manual como para el seguimiento automático.
    """
    respuesta = sat.verificar(datos["rfc"], datos["id_sat"])
    resultado = ResultadoSeguimiento(respuesta=respuesta, recuperada=bool(datos.get("recuperado")))
    modo = config.modo_descarga_sat
    with Catalogo(db_path) as catalogo:
        catalogo.guardar_solicitud_descarga(
            cliente=datos["cliente"], rfc=datos["rfc"], direccion=datos["direccion"],
            fecha_inicial=datos["fecha_inicial"], fecha_final=datos["fecha_final"],
            tipo_comprobante=datos["tipo_comprobante"], id_sat=datos["id_sat"],
            cod_estatus=respuesta.cod_estatus, estado=respuesta.estado,
            mensaje=(datos["mensaje"] if resultado.recuperada else respuesta.mensaje),
            numero_cfdis=respuesta.numero_cfdis,
            paquetes=respuesta.paquetes,
        )
        if respuesta.estado != 3 or resultado.recuperada:
            return resultado
        if not respuesta.paquetes and respuesta.numero_cfdis:
            # El SAT aún no entregó los identificadores: volver a consultar.
            return resultado
        fila = catalogo.obtener_solicitud_descarga(datos["id_sat"])
        recuperados = set(json.loads(fila["paquetes_recuperados_json"] or "[]"))
        for paquete_id in respuesta.paquetes:
            if paquete_id in recuperados:
                continue
            zip_bytes = sat.descargar_paquete(datos["rfc"], paquete_id)
            guardado = guardar_paquete(
                zip_bytes, config, datos["cliente"], datos["rfc"],
                datos["id_sat"], paquete_id, modo=modo,
            )
            resultado.copiados += 1 if guardado.zip_guardado else guardado.copiados
            resultado.errores += guardado.errores
            if modo == "organizado":
                importados = importar_carpetas(catalogo, guardado.archivos, datos["cliente"])
                resultado.insertados += importados.insertados
                resultado.errores += importados.errores
            if resultado.errores:
                raise ErrorDescargaSAT(
                    f"El paquete {paquete_id} se recibió, pero algunos XML no se pudieron incorporar. "
                    "Revisa el archivo de diagnóstico antes de reintentar."
                )
            catalogo.marcar_paquete_recuperado(datos["id_sat"], paquete_id)
            recuperados.add(paquete_id)
        resultado.recuperada = True
        mensaje = respuesta.mensaje
        destino = config.carpeta_zip_sat if modo == "zip" else config.carpeta_boveda
        mensaje = f"{mensaje} · {'ZIP sin extraer' if modo == 'zip' else 'XML organizados'}: {destino}"
        catalogo.guardar_solicitud_descarga(
            cliente=datos["cliente"], rfc=datos["rfc"], direccion=datos["direccion"],
            fecha_inicial=datos["fecha_inicial"], fecha_final=datos["fecha_final"],
            tipo_comprobante=datos["tipo_comprobante"], id_sat=datos["id_sat"],
            cod_estatus=respuesta.cod_estatus, estado=respuesta.estado, mensaje=mensaje,
            numero_cfdis=respuesta.numero_cfdis, paquetes=respuesta.paquetes, recuperado=True,
        )
    return resultado
