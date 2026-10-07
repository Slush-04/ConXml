# Integración con ConXml-UpdateManager

Este repositorio mantiene ConXml: código fuente, builds locales para Mac y
Windows, el actualizador de la aplicación y los workflows Windows. El repo
`ConXml-UpdateManager` mantiene la interfaz administrativa y el token para pedir
compilaciones y publicar Releases.

## Fase 1: compilar y descargar

El Administrador inicia `.github/workflows/windows-release.yml` en `main` mediante
`workflow_dispatch`, enviando `version` en formato `X.Y.Z`. El workflow ejecuta las
pruebas y genera el Setup, el ZIP de actualización y sus hashes como artefacto
privado `ConXml-Windows-dist`. No crea una Release y la app instalada todavía no
detecta esa versión.

El Administrador sigue el run hasta `completed/success`, descarga el artefacto del
run y extrae únicamente `ConXml-Setup-X.Y.Z-windows-x64.exe`, verificando el SHA-256
del sidecar. Debe conservar el `run_id` y la versión para la fase de publicación.

## Fase 2: publicar

Solo después de probar y aprobar el Setup, el Administrador inicia
`.github/workflows/windows-publish.yml`, enviando `version` y `build_run_id`. El
workflow vuelve a verificar que el build elegido terminó correctamente en `main`,
descarga su artefacto, valida los hashes y publica `vX.Y.Z` con el Setup y el ZIP.
Desde ese momento la app instalada puede detectar la Release.

La llamada para compilar usa:

```http
POST /repos/Slush-04/ConXml/actions/workflows/windows-release.yml/dispatches
{"ref":"main","inputs":{"version":"0.2.13"}}
```

La llamada para publicar usa:

```http
POST /repos/Slush-04/ConXml/actions/workflows/windows-publish.yml/dispatches
{"ref":"main","inputs":{"version":"0.2.13","build_run_id":"123456789"}}
```

El token fine-grained del Administrador necesita `Actions: Read and write` y
`Contents: Read` en este repo. `GITHUB_TOKEN` de Actions tiene `actions: read` y
`contents: write` para transferir el artefacto y publicar. El token administrativo
se guarda en el almacén seguro del sistema, nunca en el código ni en ConXml.

## Builds locales

Los builds locales usan los scripts de este repositorio. Mac produce `ConXml.app`;
Windows produce sus ejecutables y puede generar un Setup local. Un build local no
publica una Release. La instalación inicial y las actualizaciones de producción
usan los archivos de una Release publicada.
