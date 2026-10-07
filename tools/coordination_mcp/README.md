# ConXml Coordination MCP

Servidor MCP local para coordinar el trabajo de Antigravity con el repositorio
ConXml. Usa transporte `stdio`, no ejecuta comandos del sistema y solo lee o
escribe archivos dentro de `coordination/`.

No agrega dependencias a la aplicación ConXml: funciona con la biblioteca
estándar de Python.

## Configuración en Antigravity para Windows

En Antigravity abre `...` en el panel del agente → **MCP Servers** →
**Manage MCP Servers** → **View raw config**. Agrega este servidor ajustando
las rutas a la carpeta donde clonaste el repositorio:

```json
{
  "mcpServers": {
    "conxml-coordination": {
      "command": "C:\\Users\\TU_USUARIO\\ConXml\\.venv\\Scripts\\python.exe",
      "args": [
        "C:\\Users\\TU_USUARIO\\ConXml\\tools\\coordination_mcp\\server.py"
      ],
      "cwd": "C:\\Users\\TU_USUARIO\\ConXml",
      "env": {
        "CONXML_REPO_ROOT": "C:\\Users\\TU_USUARIO\\ConXml"
      }
    }
  }
}
```

Si no existe ese entorno virtual, cambia `command` por `py` y deja la ruta del
servidor en `args`.

## Herramientas disponibles

- `read_task`: lee `coordination/TASK.md`.
- `read_context`: lee tarea, estado, resultado y notas.
- `set_status`: registra `pending`, `in_progress`, `ready_for_review`,
  `blocked` o `done`.
- `publish_result`: escribe el resumen de trabajo en `coordination/RESULT.md`
  y marca el trabajo como `ready_for_review`.
- `add_note`: agrega una nota fechada en `coordination/NOTES.md`.

## Flujo de uso

1. Sincroniza la rama:

   ```powershell
   git pull origin antigravity/installer-fix
   ```

2. Pide a Antigravity que use `read_context` y siga `coordination/TASK.md`.
3. Cuando termine, pídele que use `publish_result`.
4. Haz commit y push de los archivos de coordinación junto con los cambios:

   ```powershell
   git add coordination
   git commit -m "Documentar resultado de Antigravity"
   git push origin antigravity/installer-fix
   ```

Este primer servidor es local (`stdio`). Para un canal en tiempo real entre
dos computadoras se necesitará después desplegarlo como servidor MCP remoto
por HTTPS y añadir autenticación.
