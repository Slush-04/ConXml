"""Envía una tarea a Muse en una copia y conserva el parche para revisión."""

from __future__ import annotations

import argparse
import difflib
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = {
    "free": "opencode/muse-spark-1.3-contributor-free",
    "standard": "opencode/muse-spark-1.3",
}


def sources() -> dict[str, bytes]:
    files = [ROOT / "README.md", ROOT / "pyproject.toml"]
    files += list((ROOT / "src").rglob("*.py"))
    files += list((ROOT / "tests").rglob("*.py"))
    files += list((ROOT / "tests" / "fixtures").glob("*.xml"))
    if any(p.is_symlink() for p in files):
        raise ValueError("La copia no admite archivos enlazados simbólicamente.")
    return {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in files}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", type=Path, help="Archivo Markdown con el encargo")
    parser.add_argument("--model", choices=MODELS, required=True)
    parser.add_argument("--dry-run", action="store_true", help="Preparar sin contactar al modelo")
    args = parser.parse_args()
    task = args.task.read_text(encoding="utf-8")
    cli = os.environ.get("CONXML_OPENCODE_BIN") or shutil.which("opencode")
    if not cli:
        bundled = Path("/Applications/OpenCode.app/Contents/Resources/opencode-cli")
        if bundled.is_file():
            cli = str(bundled)
    if not cli and not args.dry_run:
        parser.error("No se encontró OpenCode. Define CONXML_OPENCODE_BIN.")

    original = sources()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    output = ROOT / ".ai-work" / stamp
    output.mkdir(parents=True)
    prompt = (
        "Implementa únicamente el siguiente encargo en esta copia. "
        "Los XML incluidos son fixtures sintéticos. No ejecutes comandos, "
        "no consultes la red, no uses subagentes ni accedas fuera de esta carpeta. "
        "Modifica únicamente archivos Python en src/ y tests/, o README.md. "
        "Al terminar explica cambios, pruebas pendientes y limitaciones.\n\n" + task
    )
    (output / "encargo.md").write_text(task, encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="conxml-muse-") as tmp:
        work = Path(tmp).resolve()
        for relative, content in original.items():
            destination = work / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
        rules = [{"action": "*", "resource": "*", "effect": "ask"},
                 {"action": "external_directory", "resource": "*", "effect": "deny"}]
        for action in ("read", "glob"):
            for pattern in ("src/*", "tests/*", "README.md", "pyproject.toml"):
                rules.append({"action": action, "resource": pattern, "effect": "allow"})
        for directory in (".", str(work), "src", "tests"):
            rules.append({"action": "read", "resource": directory, "effect": "allow"})
        for pattern in ("src/*.py", "tests/*.py", "README.md"):
            rules.append({"action": "edit", "resource": pattern, "effect": "allow"})
        config = {
            "$schema": "https://opencode.ai/config.json",
            "model": MODELS[args.model],
            "default_agent": "build",
            "agents": {"build": {
                "permissions": rules,
            }},
        }
        (work / "opencode.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
        (output / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
        if args.dry_run:
            print(f"Copia preparada: {len(original)} archivos. Modelo: {MODELS[args.model]}")
            print(f"Preparación sin inferencia: {output}")
            return 0
        with (output / "respuesta.jsonl").open("w", encoding="utf-8") as log:
            worker_env = os.environ.copy()
            worker_env["PWD"] = str(work)
            result = subprocess.run(
                [cli, "run", "--standalone", "--agent", "build",
                 "--model", MODELS[args.model], "--format", "json", prompt],
                cwd=work, env=worker_env, stdout=log, stderr=subprocess.STDOUT, timeout=900,
            )
        changed = {p.relative_to(work).as_posix(): p.read_bytes()
                   for p in work.rglob("*") if p.is_file() and not p.is_symlink()
                   and (p.suffix == ".py" and p.parts[len(work.parts)] in ("src", "tests")
                        or p == work / "README.md")}
        allowed_original = {k: v for k, v in original.items()
                            if k.endswith(".py") or k == "README.md"}
        patch = []
        for relative in sorted(allowed_original.keys() | changed.keys()):
            before = allowed_original.get(relative, b"")
            after = changed.get(relative, b"")
            if before == after:
                continue
            lines = difflib.unified_diff(
                before.decode("utf-8").splitlines(keepends=True),
                after.decode("utf-8").splitlines(keepends=True),
                fromfile=f"a/{relative}" if relative in allowed_original else "/dev/null",
                tofile=f"b/{relative}" if relative in changed else "/dev/null",
            )
            for line in lines:
                patch.append(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n")
        (output / "cambios.patch").write_text("".join(patch), encoding="utf-8")
        print(f"Parche y respuesta para revisión: {output}")
        print("El código original permanece sin cambios. Codex debe revisar el parche.")
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
