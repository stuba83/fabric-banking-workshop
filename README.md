# Microsoft Fabric — laboratorio de banca sintética

Material de práctica en español para equipos de ingeniería de datos que se inician en Microsoft Fabric. El caso bancario es **completamente ficticio** y puede reutilizarse con distintos equipos sin introducir información de clientes reales.

El recorrido de referencia es: **CSV → Lakehouse / bronce → datos depurados / plata → tablas de consumo / oro → modelo semántico → Power BI**.

## Empezar

1. Revisar los [requisitos del laboratorio](docs/requisitos.md).
2. Descargar el repositorio mediante **Code → Download ZIP** o clonarlo:

   ```powershell
   git clone https://github.com/stuba83/fabric-banking-workshop.git
   Set-Location .\fabric-banking-workshop
   ```

3. Leer la [guía del dataset](dataset/README.md) y el [diccionario de datos](dataset/diccionario.md).
4. Completar el pre-work de la [Sesión 1: fundamentos](docs/sesion-01/guia.md).
5. Registrar los resultados propios en una copia de la [plantilla de evidencias](docs/sesion-01/evidencias.md), conservada dentro de la organización, no en este repositorio público.

No hace falta instalar Python para usar los CSV en Fabric.

## Material disponible

| Material | Contenido |
|---|---|
| [Requisitos](docs/requisitos.md) | Capacidad, Power BI Pro, roles, carpeta individual y nomenclatura |
| [Sesión 1](docs/sesion-01/guia.md) | Pre-work, agenda de 60 minutos, primera carga manual y accionables |
| [Evidencias](docs/sesion-01/evidencias.md) | Plantilla vacía para que cada participante documente su práctica |
| [Dataset](dataset/README.md) | Siete CSV, reglas de calidad, valores de control y scripts reproducibles |

**Esta versión incluye el material de la Sesión 1.** La guía sitúa la ingesta con pipelines, la transformación, el modelado y los reportes como pasos posteriores del recorrido; sus laboratorios específicos aún no están incluidos. No contiene un calendario ni compromisos de acompañamiento para una organización particular.

## Datos sintéticos

| Tabla | Registros |
|---|---:|
| Clientes | 1.200 |
| Cuentas | 1.800 |
| Transacciones bronce | 72.360 |
| Créditos, uso opcional | 400 |
| Productos | 5 |
| Sucursales | 7 |
| Calendario | 183 días |

Período: abril–septiembre de 2026. Moneda: CRC. Horas locales de Costa Rica (UTC-6). La geografía es una referencia pública; no describe la operación de una entidad real.

El archivo de transacciones incorpora anomalías deliberadas: **288 duplicados y 72 filas para cuarentena**, además de canales que requieren normalización. El resultado esperado de la limpieza es **72.000 movimientos válidos**.

Los registros, identificadores y distribuciones se generan por código; no se obtuvieron de sistemas ni de datos de clientes. Los patrones analíticos son didácticos, no evidencia de comportamiento real.

## Preparación del ambiente

- Capacidad Fabric activa: Trial cuando esté disponible y permitida, o una alternativa aprobada por el administrador.
- Licencia **Power BI Pro por participante** como requisito del taller para crear reportes.
- Un workspace de laboratorio aislado y rol **Member o Admin** por participante.
- Cada usuario crea **su carpeta y sus artefactos con nomenclatura propia**.
- Sin conexiones a producción, datos personales ni credenciales compartidas.

Los roles y las licencias indicados son requisitos de este taller, no una declaración de los permisos mínimos universales de cada función de Fabric. Trabajar únicamente en un entorno de práctica. Las carpetas organizan artefactos; no aíslan permisos entre participantes.

## Validar o regenerar

Los scripts usan la biblioteca estándar de Python. Para reproducir esta versión se utiliza **Python 3.14**.

Desde la raíz del repositorio:

```powershell
python .\dataset\validar_dataset.py
```

El resultado debe incluir `"status": "success"`. El validador comprueba hashes, esquemas, claves, relaciones, anomalías, saldos y señales analíticas.

Para regenerar los siete CSV y el manifiesto con la semilla fija `20261022`:

```powershell
python .\dataset\generar_dataset.py --overwrite
python .\dataset\validar_dataset.py
```

`--overwrite` reemplaza únicamente las salidas generadas del dataset. Conservar aparte cualquier modificación que se quiera mantener. El workflow de GitHub comprueba validación y regeneración sin diferencias.

## Uso responsable

No subir evidencias completadas, capturas del tenant, nombres de organizaciones, datos reales, credenciales o logs internos a issues, pull requests ni carpetas de este repositorio. Mantenerlos en la ubicación interna aprobada por cada organización.

Este es un recurso de práctica independiente, no documentación oficial de Microsoft ni una implementación bancaria productiva. No ofrece un core bancario, partida doble, amortización contractual ni validación regulatoria. Consultar las limitaciones del dataset y la documentación oficial enlazada en las guías.
