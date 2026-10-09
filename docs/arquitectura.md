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
    │   └── <año>/<mes>/*.xml
    └── Recibidos/
        └── <año>/<mes>/*.xml
```

La e.firma que el usuario decide guardar permanece en
`<datos-locales>/clientes/<cliente>/efirma/`. La contraseña no se guarda.

El catálogo conserva la clave del cliente en cada comprobante. Las bases creadas
por versiones anteriores se migran automáticamente a la tabla editable de
clientes.

## Flujo de trabajo

1. Se selecciona o crea el cliente en una ventana independiente que aparece al iniciar.
2. Se importa una carpeta externa con XML o se recuperan paquetes desde Descarga SAT.
3. Bóveda permite examinar esa carpeta externa o filtrar `Emitidos` y `Recibidos`
   dentro de la estructura local. Los meses se presentan como `09-Sep`, `10-Oct`.
4. El usuario filtra dirección, año y mes, y carga esa selección al catálogo.
5. Administración XML muestra el cliente activo y permite buscar por UUID, RFC,
   serie y folio.
6. **Cambiar cliente** abre de nuevo el selector independiente y conserva abierta la
   ventana principal.
