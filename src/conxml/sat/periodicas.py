"""Horarios independientes de solicitud y revisión, ejecutables sin abrir la GUI."""
from __future__ import annotations

import argparse
import json
import os
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from conxml import estado_local
from conxml.catalog.db import Catalogo
from conxml.config import Config
from conxml.sat.archivo_solicitudes import limpiar_vencidas
from conxml.sat.autorizacion_periodica import cargar_firma
from conxml.sat.descarga_masiva import ClienteDescargaSAT, ErrorDescargaSAT, FiltroDescarga
from conxml.sat.seguimiento import procesar_solicitud

DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']


def plan_predeterminado() -> dict:
    return {
        'activo': False, 'zona': 'America/Merida', 'dias_xml': 7,
        'direccion': 'Ambos', 'tipo': '',
        'solicitar': {'frecuencia': 'Semanal', 'cada': 1, 'dia': 4, 'hora': '16:00'},
        'revisar': {'frecuencia': 'Semanal', 'cada': 1, 'dia': 0, 'hora': '08:00'},
    }


def planes(config: Config) -> dict:
    datos = estado_local.cargar(config.preferencias_path).get('sat_periodico', {})
    return datos if isinstance(datos, dict) else {}


def validar_plan(plan: dict) -> None:
    try:
        ZoneInfo(plan['zona'])
    except KeyError as exc:
        raise ValueError('Escribe una zona horaria válida, por ejemplo America/Merida.') from exc
    if not 1 <= int(plan['dias_xml']) <= 31:
        raise ValueError('El período debe abarcar entre 1 y 31 días completos.')
    if plan['direccion'] not in ('Emitidos', 'Recibidos', 'Ambos') or plan['tipo'] not in ('', 'I', 'E', 'T', 'N', 'P'):
        raise ValueError('Revisa dirección y tipo de comprobante.')
    for tarea in ('solicitar', 'revisar'):
        horario = plan[tarea]
        if horario['frecuencia'] not in ('Diario', 'Semanal') or not 1 <= int(horario['cada']) <= 52:
            raise ValueError('Elige una frecuencia diaria o semanal, con intervalo de 1 a 52.')
        if not 0 <= int(horario['dia']) <= 6:
            raise ValueError('El día de la semana no es válido.')
        hora = time.fromisoformat(horario['hora'])
        if hora.second or hora.microsecond or hora.tzinfo or len(horario['hora']) != 5:
            raise ValueError('Escribe la hora en formato de 24 horas: HH:MM.')


def guardar_plan(config: Config, cliente: str, plan: dict) -> None:
    validar_plan(plan)
    datos = planes(config)
    anterior = datos.get(cliente, {})
    nuevo = json.loads(json.dumps(plan))
    # Cambiar un horario establece un nuevo punto de inicio: no ejecuta
    # solicitudes retroactivas al guardar la configuración.
    claves = ('zona', 'solicitar', 'revisar', 'dias_xml', 'direccion', 'tipo')
    conservar = anterior.get('activo') and plan.get('activo') and all(anterior.get(k) == plan.get(k) for k in claves)
    nuevo['desde'] = anterior['desde'] if conservar else datetime.now(timezone.utc).isoformat()
    datos[cliente] = nuevo
    estado_local.guardar({'sat_periodico': datos}, config.preferencias_path)


def ocurrencia(plan: dict, tarea: str, ahora: datetime) -> datetime | None:
    zona = ZoneInfo(plan['zona'])
    ahora = ahora.astimezone(zona)
    inicio = datetime.fromisoformat(plan['desde']).astimezone(zona)
    horario = plan[tarea]
    cada = int(horario['cada'])
    if horario['frecuencia'] == 'Diario':
        diferencia = (ahora.date() - inicio.date()).days
        fecha = inicio.date() + timedelta(days=(diferencia // cada) * cada)
        paso = timedelta(days=cada)
    else:
        lunes = inicio.date() - timedelta(days=inicio.weekday())
        diferencia = (ahora.date() - lunes).days // 7
        fecha = lunes + timedelta(weeks=(diferencia // cada) * cada, days=int(horario['dia']))
        paso = timedelta(weeks=cada)
    instante = datetime.combine(fecha, time.fromisoformat(horario['hora']), zona)
    if instante > ahora:
        instante -= paso
    return instante if instante >= inicio else None


def proximas(plan: dict, tarea: str, ahora: datetime | None = None) -> datetime:
    ahora = (ahora or datetime.now(timezone.utc)).astimezone(ZoneInfo(plan['zona']))
    horario = plan[tarea]
    # La búsqueda por días mantiene la alineación de intervalos con 'desde'.
    for dias in range(370):
        candidato = datetime.combine(ahora.date() + timedelta(days=dias), time.fromisoformat(horario['hora']), ahora.tzinfo)
        if candidato > ahora and ocurrencia(plan, tarea, candidato) == candidato:
            return candidato
    raise ValueError('No se pudo calcular el próximo horario.')


@contextmanager
def bloqueo(config: Config):
    config.base.mkdir(parents=True, exist_ok=True)
    stream = (config.base / '.sat-periodico.lock').open('a+b')
    obtenido = False
    try:
        if os.name == 'nt':
            import msvcrt
            stream.seek(0); stream.write(b'0'); stream.flush(); stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1); obtenido = True
            except OSError:
                pass
        else:
            import fcntl
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB); obtenido = True
            except BlockingIOError:
                pass
        yield obtenido
    finally:
        if obtenido:
            if os.name == 'nt':
                stream.seek(0); msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)
        stream.close()


def _solicitar(sat, cat: Catalogo, cliente: str, rfc: str, plan: dict, instante: datetime) -> int:
    final = instante.date() - timedelta(days=1)
    inicial = final - timedelta(days=int(plan['dias_xml']) - 1)
    direcciones = ('Emitidos', 'Recibidos') if plan['direccion'] == 'Ambos' else (plan['direccion'],)
    cantidad = 0
    for direccion in direcciones:
        repetida = cat.conn.execute(
            'SELECT id_sat FROM solicitudes_descarga WHERE cliente=? AND rfc=? AND direccion=? '
            'AND fecha_inicial=? AND fecha_final=? AND tipo_comprobante=? AND (estado IN (1,2,3) OR estado IS NULL)',
            (cliente, rfc, direccion, inicial.isoformat(), final.isoformat(), plan['tipo']),
        ).fetchone()
        if repetida:
            continue
        filtro = FiltroDescarga(rfc=rfc, direccion=direccion, fecha_inicial=inicial,
                                fecha_final=final, tipo_comprobante=plan['tipo'])
        filtro.validar()
        respuesta = sat.solicitar(filtro)
        if not respuesta.id_solicitud:
            raise ErrorDescargaSAT(respuesta.mensaje or 'El SAT no entregó un identificador de solicitud.')
        cat.guardar_solicitud_descarga(
            cliente=cliente, rfc=rfc, direccion=direccion, fecha_inicial=inicial.isoformat(),
            fecha_final=final.isoformat(), tipo_comprobante=plan['tipo'], id_sat=respuesta.id_solicitud,
            cod_estatus=respuesta.cod_estatus, estado=1, mensaje=respuesta.mensaje,
        )
        cat.conn.execute('INSERT OR IGNORE INTO sat_solicitudes_periodicas VALUES (?)', (respuesta.id_solicitud,))
        cat.commit()
        cantidad += 1
    return cantidad


def ejecutar_pendientes(config: Config, ahora: datetime | None = None, *, firma=cargar_firma, fabrica_sat=ClienteDescargaSAT) -> list[dict]:
    """Un bloqueo entre procesos y un registro por horario impiden duplicados.

    Un fallo de envío se conserva para revisión, sin reenviar automáticamente
    una petición que el SAT podría haber aceptado antes de cortar la conexión.
    """
    from conxml.licensing_client import require_access
    require_access()
    ahora = ahora or datetime.now(timezone.utc)
    resultados = []
    with bloqueo(config) as adquirido:
        if not adquirido:
            return []
        limpiar_vencidas(config, config.db_path)
        for cliente, plan in planes(config).items():
            if not plan.get('activo'):
                continue
            try:
                validar_plan(plan)
            except (ValueError, KeyError, TypeError):
                continue
            with Catalogo(config.db_path) as cat:
                detalle = cat.obtener_cliente(cliente)
                if not detalle or not detalle['activo']:
                    continue
                for tarea in ('solicitar', 'revisar'):
                    instante = ocurrencia(plan, tarea, ahora)
                    if instante is None:
                        continue
                    require_access()  # La tarea previa termina; no iniciar otra tras el vencimiento.
                    clave = instante.astimezone(timezone.utc).isoformat()
                    # INSERT OR IGNORE es la exclusión definitiva entre ejecuciones.
                    cur = cat.conn.execute(
                        'INSERT OR IGNORE INTO sat_ejecuciones_periodicas VALUES (?,?,?,?,?)',
                        (cliente, tarea, clave, 'ejecutando', ''),
                    )
                    cat.commit()
                    if not cur.rowcount:
                        continue
                    sat = None
                    try:
                        fiel = firma(config, cliente, detalle['rfc'])
                        sat = fabrica_sat(fiel)
                        if tarea == 'solicitar':
                            cantidad = _solicitar(sat, cat, cliente, detalle['rfc'], plan, instante)
                            mensaje = f'{cantidad} solicitudes enviadas.'
                        else:
                            filas = [dict(f) for f in cat.solicitudes_descarga_pendientes({detalle['rfc']}) if f['cliente'] == cliente]
                            recuperadas = 0
                            for datos in filas:
                                resultado = procesar_solicitud(sat, config.db_path, datos, config, modo='organizado')
                                recuperadas += int(resultado.recuperada)
                            mensaje = f'{len(filas)} solicitudes revisadas; {recuperadas} recuperadas y organizadas.'
                        estado = 'completada'
                    except Exception as exc:
                        from conxml.diagnostico import sanitizar_texto
                        estado = 'error' if sat is not None else 'sin_autorizacion'
                        mensaje = sanitizar_texto(str(exc)) if isinstance(exc, ErrorDescargaSAT) else 'No se completó la tarea. Revisa la conexión, la autorización y el diagnóstico.'
                    finally:
                        if sat is not None:
                            sat.cerrar()
                    cat.conn.execute(
                        'UPDATE sat_ejecuciones_periodicas SET estado=?,mensaje=? WHERE cliente=? AND tarea=? AND instante=?',
                        (estado, mensaje, cliente, tarea, clave),
                    )
                    cat.commit()
                    resultados.append({'cliente': cliente, 'tarea': tarea, 'estado': estado, 'mensaje': mensaje})
    return resultados


def main() -> int:
    parser = argparse.ArgumentParser(description='Ejecutor de descargas SAT periódicas')
    parser.add_argument('--datos', required=True, type=Path)
    args = parser.parse_args()
    os.environ['CONXML_DATA_DIR'] = str(args.datos.resolve())
    ejecutar_pendientes(Config())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
