#!/usr/bin/env python3
"""Minimal stdio MCP server for ConXml agent coordination.

This server intentionally uses only the Python standard library so it can run
inside a Windows clone without changing ConXml's application dependencies.
It exposes coordination tools only; it does not execute shell commands.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SERVER_NAME = "conxml-coordination"
SERVER_VERSION = "0.1.0"
MAX_TEXT_LENGTH = 100_000


def repo_root() -> Path:
    configured = os.environ.get("CONXML_REPO_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    # server.py lives at <repo>/tools/coordination_mcp/server.py
    return Path(__file__).resolve().parents[2]


COORDINATION_DIR = repo_root() / "coordination"
TASK_FILE = COORDINATION_DIR / "TASK.md"
RESULT_FILE = COORDINATION_DIR / "RESULT.md"
STATUS_FILE = COORDINATION_DIR / "STATUS.json"
NOTES_FILE = COORDINATION_DIR / "NOTES.md"


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def ensure_directory() -> None:
    COORDINATION_DIR.mkdir(parents=True, exist_ok=True)


def read_text(path: Path, fallback: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return fallback


def write_text(path: Path, content: str) -> None:
    if len(content) > MAX_TEXT_LENGTH:
        raise ValueError(f"El contenido supera el límite de {MAX_TEXT_LENGTH} caracteres")
    ensure_directory()
    path.write_text(content, encoding="utf-8")


def default_status() -> dict[str, Any]:
    return {
        "status": "pending",
        "updated_at": now(),
        "updated_by": "coordination-mcp",
        "note": "Sin estado publicado todavía.",
    }


def read_status() -> dict[str, Any]:
    raw = read_text(STATUS_FILE)
    if not raw:
        return default_status()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {
            "status": "blocked",
            "updated_at": now(),
            "updated_by": "coordination-mcp",
            "note": "STATUS.json no contiene JSON válido.",
        }
    return value if isinstance(value, dict) else default_status()


def write_status(status: str, note: str, updated_by: str = "antigravity") -> dict[str, Any]:
    allowed = {"pending", "in_progress", "ready_for_review", "blocked", "done"}
    if status not in allowed:
        raise ValueError(f"status debe ser uno de: {', '.join(sorted(allowed))}")
    value = {
        "status": status,
        "updated_at": now(),
        "updated_by": updated_by,
        "note": note,
    }
    write_text(STATUS_FILE, json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    return value


def text_result(value: Any, is_error: bool = False) -> dict[str, Any]:
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, indent=2)
    return {"content": [{"type": "text", "text": value}], "isError": is_error}


TOOLS = [
    {
        "name": "read_task",
        "description": "Lee la tarea activa que el coordinador dejó para Antigravity.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "read_context",
        "description": "Lee tarea, estado, resultado y notas de coordinación.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "set_status",
        "description": "Actualiza el estado del trabajo sin ejecutar comandos.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["pending", "in_progress", "ready_for_review", "blocked", "done"],
                },
                "note": {"type": "string"},
            },
            "required": ["status", "note"],
        },
    },
    {
        "name": "publish_result",
        "description": "Publica el resumen del trabajo y deja el estado listo para revisión.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "tests": {"type": "string"},
                "changed_files": {"type": "string"},
                "blockers": {"type": "string"},
                "commit": {"type": "string"},
            },
            "required": ["summary", "tests"],
        },
    },
    {
        "name": "add_note",
        "description": "Agrega una nota de coordinación con fecha y autor.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "note": {"type": "string"},
                "author": {"type": "string"},
            },
            "required": ["note"],
        },
    },
]


def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    ensure_directory()

    if name == "read_task":
        task = read_text(TASK_FILE, "No hay una tarea activa en coordination/TASK.md.")
        return text_result(task)

    if name == "read_context":
        return text_result(
            {
                "task": read_text(TASK_FILE, ""),
                "status": read_status(),
                "result": read_text(RESULT_FILE, ""),
                "notes": read_text(NOTES_FILE, ""),
            }
        )

    if name == "set_status":
        status = str(arguments.get("status", ""))
        note = str(arguments.get("note", ""))
        return text_result(write_status(status, note))

    if name == "publish_result":
        summary = str(arguments.get("summary", ""))
        tests = str(arguments.get("tests", ""))
        changed_files = str(arguments.get("changed_files", "No especificado"))
        blockers = str(arguments.get("blockers", "Ninguno"))
        commit = str(arguments.get("commit", "No especificado"))
        content = (
            "# Resultado de Antigravity\n\n"
            f"- Fecha: {now()}\n"
            f"- Commit: {commit}\n\n"
            "## Resumen\n\n"
            f"{summary}\n\n"
            "## Pruebas\n\n"
            f"{tests}\n\n"
            "## Archivos modificados\n\n"
            f"{changed_files}\n\n"
            "## Bloqueos\n\n"
            f"{blockers}\n"
        )
        write_text(RESULT_FILE, content)
        status = write_status("ready_for_review", "Resultado publicado; requiere revisión del coordinador.")
        return text_result({"result_file": str(RESULT_FILE), "status": status})

    if name == "add_note":
        note = str(arguments.get("note", ""))
        author = str(arguments.get("author", "antigravity"))
        if not note.strip():
            raise ValueError("note no puede estar vacío")
        existing = read_text(NOTES_FILE)
        entry = f"- {now()} — {author}: {note.strip()}\n"
        write_text(NOTES_FILE, existing + entry)
        return text_result({"notes_file": str(NOTES_FILE), "added": entry.strip()})

    raise ValueError(f"Herramienta desconocida: {name}")


def response(request_id: Any, result: Any = None, error: dict[str, Any] | None = None) -> None:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id}
    if error is not None:
        payload["error"] = error
    else:
        payload["result"] = result
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def handle(message: dict[str, Any]) -> None:
    method = message.get("method")
    request_id = message.get("id")

    # Notifications do not receive a response.
    if request_id is None:
        return

    if method == "initialize":
        response(
            request_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        )
        return

    if method == "ping":
        response(request_id, {})
        return

    if method == "tools/list":
        response(request_id, {"tools": TOOLS})
        return

    if method == "tools/call":
        params = message.get("params") or {}
        name = str(params.get("name", ""))
        arguments = params.get("arguments") or {}
        try:
            response(request_id, call_tool(name, arguments))
        except Exception as exc:  # Keep protocol errors inside the MCP response.
            response(request_id, text_result(f"Error: {exc}", is_error=True))
        return

    response(request_id, error={"code": -32601, "message": f"Método no soportado: {method}"})


def main() -> None:
    ensure_directory()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
            if not isinstance(message, dict):
                raise ValueError("El mensaje MCP debe ser un objeto JSON")
            handle(message)
        except Exception as exc:
            # There may be no request id when parsing failed, so report to stderr.
            print(f"coordination-mcp: {exc}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
