# Bóveda de XML

La bóveda es el archivo organizado de documentos originales. No sustituye al
catálogo SQLite: copiar archivos no los hace aparecer en las tablas hasta usar
`Cargar selección`.

Al seleccionar un cliente, ConXml crea automáticamente esta estructura:

```text
boveda/<cliente>/
├── Emitidos/
│   ├── Masivo/       ← pega aquí los XML descargados del SAT
│   └── <año>/<mes>/  ← archivos ordenados por ConXml
└── Recibidos/
    ├── Masivo/       ← pega aquí los XML descargados del SAT
    └── <año>/<mes>/  ← archivos ordenados por ConXml
```

En la pantalla **Bóveda** puedes pulsar **Examinar** para leer cualquier carpeta
con XML directamente. También puedes elegir `Emitidos`, `Recibidos` o `Masivo`
para revisar lo que ya existe dentro de la Bóveda. Después selecciona el periodo
y pulsa **Cargar selección** para llevar esos XML a Administración de XML.

La clasificación usa el RFC del cliente. Si el RFC emisor coincide con el RFC
del cliente, el archivo va a `Emitidos`; de lo contrario va a `Recibidos`.
Cuando un cliente heredado no tiene RFC, los archivos quedan en `Recibidos`
para que puedan revisarse y reclasificarse después.
