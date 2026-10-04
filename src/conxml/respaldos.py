"""Respaldos autocontenidos de catálogo, XML, configuración y sesión.

La base se copia con SQLite Backup (incluye WAL). Cada archivo tiene hash;
restaurar valida todo antes de sustituir datos y conserva una copia previa.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath

MARCA = '__CONXML_BASE__/'
EXCLUIDOS = {'respaldos', 'cache', '__pycache__'}


@dataclass
class ResultadoRespaldo:
    ruta: Path
    archivos: int
    faltantes: list[str]


def _hash(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open('rb') as stream:
        for bloque in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(bloque)
    return h.hexdigest()


def _permitido(rel: Path) -> bool:
    return not any(p in EXCLUIDOS or p.startswith('.') for p in rel.parts) and rel.suffix.lower() not in {'.cer', '.key'} and not rel.name.endswith(('-wal', '-shm', '-journal'))


def crear_respaldo(base: Path, destino: Path | None = None) -> ResultadoRespaldo:
    base = base.resolve()
    base.mkdir(parents=True, exist_ok=True)
    destino = (destino or base / 'respaldos' / f'conxml_{datetime.now():%Y%m%d_%H%M%S_%f}.zip').resolve()
    if destino.suffix.lower() != '.zip':
        raise ValueError('El destino del respaldo debe ser un archivo .zip.')
    destino.parent.mkdir(parents=True, exist_ok=True)
    faltantes = []
    with tempfile.TemporaryDirectory(prefix='conxml-respaldo-') as temporal:
        stage = Path(temporal)
        db = base / 'catalogo.db'
        if not db.is_file():
            raise ValueError('No existe un catálogo para respaldar.')
        with closing(sqlite3.connect(f'{db.as_uri()}?mode=ro', uri=True)) as origen, closing(sqlite3.connect(stage / 'catalogo.db')) as copia:
            origen.backup(copia)
            rutas = copia.execute('SELECT uuid, ruta FROM comprobantes').fetchall()
            for uuid, valor in rutas:
                archivo = Path(valor).resolve()
                if not archivo.is_file() or archivo.is_symlink():
                    faltantes.append(str(archivo))
                    continue
                try:
                    rel = archivo.relative_to(base)
                    if not _permitido(rel):
                        raise ValueError()
                except ValueError:
                    rel = Path('documentos') / f'{_hash(archivo)}.xml'
                objetivo = stage / rel
                objetivo.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(archivo, objetivo)
                copia.execute('UPDATE comprobantes SET ruta=? WHERE uuid=?', (MARCA + rel.as_posix(), uuid))
            copia.commit()
        for archivo in base.rglob('*'):
            rel = archivo.relative_to(base)
            if archivo.is_file() and not archivo.is_symlink() and _permitido(rel) and archivo.resolve() != destino and rel.as_posix() not in {'catalogo.db', 'manifest.json'}:
                objetivo = stage / rel
                objetivo.parent.mkdir(parents=True, exist_ok=True)
                if not objetivo.exists():
                    shutil.copy2(archivo, objetivo)
        archivos = {p.relative_to(stage).as_posix(): _hash(p) for p in stage.rglob('*') if p.is_file()}
        manifest = {'formato': 'conxml-respaldo', 'version': 1, 'creado_en': datetime.now().isoformat(), 'archivos': archivos, 'xml_faltantes': faltantes}
        (stage / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        fd, temp_zip = tempfile.mkstemp(prefix='.respaldo-', suffix='.zip', dir=destino.parent)
        os.close(fd)
        try:
            with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as z:
                for p in stage.rglob('*'):
                    if p.is_file():
                        z.write(p, p.relative_to(stage).as_posix())
            os.replace(temp_zip, destino)
        finally:
            Path(temp_zip).unlink(missing_ok=True)
    return ResultadoRespaldo(destino, len(archivos), faltantes)


def restaurar_respaldo(archivo: Path, base: Path) -> Path:
    """Sustituye el expediente local; devuelve la carpeta de recuperación previa."""
    base = base.resolve()
    base.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.conxml-restaurar-', dir=base.parent))
    previa = base.with_name(base.name + f'_antes_restaurar_{datetime.now():%Y%m%d_%H%M%S_%f}')
    try:
        with zipfile.ZipFile(archivo) as z:
            nombres = z.namelist()
            if len(nombres) != len(set(nombres)) or 'manifest.json' not in nombres:
                raise ValueError('Respaldo inválido: manifiesto ausente o archivos duplicados.')
            for info in z.infolist():
                path = PurePosixPath(info.filename)
                if path.is_absolute() or '..' in path.parts or '\\' in info.filename or ':' in info.filename or info.is_dir():
                    raise ValueError('El respaldo contiene una ruta no permitida.')
            if sum(i.file_size for i in z.infolist()) > max(shutil.disk_usage(stage).free // 2, 0):
                raise ValueError('No hay suficiente espacio para restaurar con seguridad.')
            manifest = json.loads(z.read('manifest.json'))
            if manifest.get('formato') != 'conxml-respaldo' or manifest.get('version') != 1:
                raise ValueError('Formato de respaldo incompatible.')
            archivos = manifest.get('archivos', {})
            if not isinstance(archivos, dict) or set(nombres) != set(archivos) | {'manifest.json'} or 'catalogo.db' not in archivos:
                raise ValueError('El contenido no coincide con el manifiesto.')
            for nombre, esperado in archivos.items():
                destino = stage / nombre
                destino.parent.mkdir(parents=True, exist_ok=True)
                with z.open(nombre) as stream, destino.open('wb') as salida:
                    shutil.copyfileobj(stream, salida)
                if _hash(destino) != esperado:
                    raise ValueError(f'Archivo dañado: {nombre}')
        with closing(sqlite3.connect(stage / 'catalogo.db')) as db:
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('El catálogo del respaldo está dañado.')
            for uuid, ruta in db.execute('SELECT uuid, ruta FROM comprobantes').fetchall():
                if ruta.startswith(MARCA):
                    rel = ruta[len(MARCA):]
                    if rel not in archivos:
                        raise ValueError('El catálogo referencia un archivo ausente.')
                    db.execute('UPDATE comprobantes SET ruta=? WHERE uuid=?', (str(base / rel), uuid))
            db.commit()
            db.execute('PRAGMA journal_mode=DELETE')
        # No se modifica el expediente actual hasta haber validado todo.
        if base.exists():
            os.replace(base, previa)
        try:
            os.replace(stage, base)
        except Exception:
            if previa.exists():
                os.replace(previa, base)
            raise
        return previa
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def respaldo_automatico(base: Path, conservar: int = 10) -> ResultadoRespaldo:
    carpeta = base / 'respaldos'
    destino = carpeta / f'auto_{datetime.now():%Y%m%d_%H%M%S_%f}.zip'
    resultado = crear_respaldo(base, destino)
    for viejo in sorted(carpeta.glob('auto_*.zip'), reverse=True)[conservar:]:
        viejo.unlink()
    return resultado
