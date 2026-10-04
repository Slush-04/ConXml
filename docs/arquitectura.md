# Arquitectura funcional

ConXml trabaja con tres capas separadas:

- `src/conxml/cfdi/` contiene los modelos y el parser CFDI.
- `src/conxml/catalog/` mantiene el catálogo SQLite, los clientes y la importación.
- `src/conxml/boveda.py` administra el archivo físico de XML; solo los archivos
  que el usuario selecciona se cargan al catálogo.
- `src/conxml/ui/` contiene las pantallas: selección de clientes, resumen,
  bóveda, administración XML y configuración.

## Datos locales

La ruta base se define en `Config`. En desarrollo es `data/`; en un ejecutable
de macOS es `~/Library/Application Support/ConXml/`. La bóveda queda en:

```text
boveda/
└── <cliente>/
    ├── Emitidos/
    │   ├── Masivo/*.xml
    │   └── <año>/<mes>/*.xml
    └── Recibidos/
        ├── Masivo/*.xml
        └── <año>/<mes>/*.xml
```

El catálogo conserva la clave del cliente en cada comprobante. Las bases creadas
por versiones anteriores se migran automáticamente a la tabla editable de
clientes.

## Flujo de trabajo

1. Se selecciona o crea el cliente en una ventana independiente que aparece al iniciar.
2. Se pegan los XML descargados del SAT en `Emitidos/Masivo` o `Recibidos/Masivo`.
3. Bóveda permite examinar una carpeta externa o filtrar `Emitidos`, `Recibidos`
   y `Masivo` dentro de la estructura local.
4. El usuario filtra dirección, año y mes, y carga esa selección al catálogo.
5. Administración XML muestra el cliente activo y permite buscar por UUID, RFC,
   serie y folio.
6. **Cambiar cliente** abre de nuevo el selector independiente y conserva abierta la
   ventana principal.
