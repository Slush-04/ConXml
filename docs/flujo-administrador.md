# Integración con ConXml-UpdateManager

Este repositorio mantiene el producto ConXml: código fuente, builds locales para
Mac y Windows, el actualizador de la aplicación y el workflow que compila Windows.
El repositorio `ConXml-UpdateManager` mantiene la interfaz administrativa y el
token usado para solicitar y gestionar publicaciones.

## Solicitud de compilación

El Administrador debe iniciar `.github/workflows/windows-release.yml` en la rama
`main` mediante `workflow_dispatch`, enviando el input obligatorio `version` con
formato estable `X.Y.Z`. El run aparece con el título `ConXml release X.Y.Z`; el
Administrador puede consultar las ejecuciones de ese workflow hasta que su estado
sea `completed` y comprobar que la conclusión sea `success`. La llamada equivalente
a la API de GitHub es:

```http
POST /repos/Slush-04/ConXml/actions/workflows/windows-release.yml/dispatches
Accept: application/vnd.github+json
Authorization: Bearer <token del Administrador>
Content-Type: application/json

{"ref":"main","inputs":{"version":"0.2.13"}}
```

El token del Administrador requiere permiso `Actions: write` en este repositorio.
Se almacena en el almacén seguro del sistema operativo, nunca en el código, en
archivos de configuración versionados o en la app ConXml.

## Resultado y descarga

El Administrador debe mostrar el estado del run de Actions y, cuando termine,
considerar éxito solo si el run concluyó correctamente y existe la Release
`vX.Y.Z`. Los artefactos de distribución publicados son:

- `ConXml-Setup-X.Y.Z-windows-x64.exe` y su `.sha256` para instalación inicial.
- `ConXml-X.Y.Z-windows-x64.zip` y su `.sha256` para actualización directa.

El Administrador descarga el Setup desde la Release y permite guardarlo en una
ubicación elegida por la persona. La aplicación instalada consulta Releases
públicas y usa el ZIP verificado para actualizarse. Así el token administrativo
no se distribuye con el instalador ni con la aplicación.

## Builds locales

Los builds locales se hacen desde este repo con los scripts específicos de cada
sistema operativo. El build Mac produce `ConXml.app`; el build Windows produce
los ejecutables y, si se ejecuta `build_installer.ps1`, un Setup. Un build local
no crea una Release ni cambia lo que detectan las aplicaciones instaladas.
