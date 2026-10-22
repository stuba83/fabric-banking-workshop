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
6. Con las fuentes preparadas, continuar con la [Sesión 2: ingesta y pipelines](docs/sesion-02/guia.md) y después con la [Sesión 3: capa plata](docs/sesion-03/guia.md).

No hace falta instalar Python para usar los CSV en Fabric.

## Material disponible

| Material | Contenido |
|---|---|
| [Requisitos](docs/requisitos.md) | Capacidad, Power BI Pro, roles, carpeta individual y nomenclatura |
| [Sesión 1](docs/sesion-01/guia.md) | Pre-work, agenda de 60 minutos, primera carga manual y accionables |
| [Evidencias](docs/sesion-01/evidencias.md) | Plantilla vacía para que cada participante documente su práctica |
| [Sesión 2](docs/sesion-02/guia.md) | Ingesta CSV a tablas bronce mediante un notebook orquestado por pipeline |
| [Evidencias S2](docs/sesion-02/evidencias.md) | Conteos, reejecución y recuperación tras una prueba de error |
| [Notebook S2](notebooks/02_ingesta_bronce.ipynb) | Notebook PySpark importable, sin conexión a un tenant preconfigurada |
| [Sesión 3](docs/sesion-03/guia.md) | Capa plata: tipos, cuarentena, duplicadas y una tabla oro, con verificación en T-SQL |
| [Evidencias S3](docs/sesion-03/evidencias.md) | Conteos medidos, reejecución, prueba de error y decisiones de calidad |
| [Notebook S3](notebooks/03_plata_silver.ipynb) | Notebook PySpark importable que transforma bronce en plata y oro |
| [Sesión 4](docs/sesion-04/guia.md) | Modelo semántico Direct Lake, reporte, seguridad por filas y gobernanza |
| [Evidencias S4](docs/sesion-04/evidencias.md) | Medidas, roles probados con «Probar como rol», linaje y elemento promovido |
| [Dataset](dataset/README.md) | Siete CSV, reglas de calidad, valores de control y scripts reproducibles |

**Esta versión incluye las sesiones 1 a 4.** El laboratorio de cierre aún no está incluido. No contiene un calendario ni compromisos de acompañamiento para una organización particular.

En la Sesión 2, el pipeline ejecuta una actividad Notebook que carga seis CSV en tablas Delta bronce. No usa Copy Data ni fuentes externas. Conserva duplicados y errores deliberados como texto para tratarlos en la siguiente sesión. El reemplazo es por lote completo y requiere confirmar explícitamente el Lakehouse y el prefijo de destino; no ejecutar sobre producción.

En la Sesión 3, una segunda actividad Notebook lee esas seis tablas, aplica tipos y reglas de calidad, aparta los duplicados y los registros inválidos, y publica seis tablas plata, dos de auditoría y una tabla oro. No escribe nada si las tablas bronce o los controles no cuadran, y los resultados se comprueban con T-SQL en el SQL analytics endpoint.

En la Sesión 4, cada participante crea un modelo semántico Direct Lake sobre las tablas plata, un reporte de una página y dos roles de seguridad por filas que verifica con «Probar como rol»; después revisa el linaje y el catálogo de OneLake y promueve su modelo. Los pasos en el editor web no se prueban automáticamente: deben comprobarse en el tenant del participante.

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

### Notebooks de las Sesiones 2 y 3

El código fuente está en [`notebooks/ingesta_bronce.py`](notebooks/ingesta_bronce.py) (Sesión 2) y [`notebooks/plata_silver.py`](notebooks/plata_silver.py) (Sesión 3). Para mantener sincronizados los notebooks importables y ejecutar las pruebas locales:

```powershell
python .\tools\sincronizar_notebook.py
python .\tools\sincronizar_notebook.py --check
python -m unittest discover -s tests -v
```

El participante importa cada `.ipynb` en **Fabric PySpark**, adjunta su Lakehouse y configura su pipeline según la guía. No necesita instalar Python localmente. El runtime de Fabric aporta Spark; la versión 3.14 indicada arriba corresponde al generador local del dataset.

Las pruebas locales comprueban la lógica y los contratos documentados, pero no acreditan una ejecución en un tenant. La importación, identidad ejecutora, parámetros del pipeline y persistencia Delta requieren la comprobación de integración en Fabric.

## Uso responsable

No subir evidencias completadas, capturas del tenant, nombres de organizaciones, datos reales, credenciales o logs internos a issues, pull requests ni carpetas de este repositorio. Mantenerlos en la ubicación interna aprobada por cada organización.

Este es un recurso de práctica independiente, no documentación oficial de Microsoft ni una implementación bancaria productiva. No ofrece un core bancario, partida doble, amortización contractual ni validación regulatoria. Consultar las limitaciones del dataset y la documentación oficial enlazada en las guías.
