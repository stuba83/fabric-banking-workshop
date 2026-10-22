# Sesión 1 — Fundamentos de Fabric y primer contacto con el laboratorio

**Audiencia:** Ingenieros de datos  
**Duración en vivo:** 60 minutos, sin extensión  
**Fecha y horario:** por confirmar en el calendario del entrenamiento  
**Versión:** 22 de octubre de 2026

## Resultado esperado

Al terminar la sesión y sus accionables, cada participante podrá explicar el recorrido de los datos en Fabric, ubicar sus artefactos dentro del entorno compartido y conservar los archivos fuente del laboratorio en su propio Lakehouse.

Esta primera sesión no busca construir toda la solución. Los pipelines, la transformación de datos y los reportes se trabajan en las sesiones posteriores. Aquí se establece la base para que ese recorrido sea práctico y reproducible.

## 1. Antes de la sesión

### A. Ambiente listo — responsabilidad del equipo

Completar la checklist de [Requisitos del ambiente de laboratorio](../requisitos.md). No esperar a la hora de la sesión para resolver licencias, capacidad o permisos.

Cada participante debe comprobar personalmente:

- [ ] Acceso al [portal de Microsoft Fabric](https://app.fabric.microsoft.com) con su cuenta corporativa.
- [ ] Licencia **Power BI Pro** activa y rol **Member o Admin** en el workspace del laboratorio.
- [ ] Capacidad Fabric del laboratorio activa y asignada al workspace; confirmar su vigencia con el administrador.
- [ ] Creación de su propia carpeta dentro del workspace y elección de una nomenclatura que no se repita entre participantes.
- [ ] Creación de un Lakehouse dentro de su carpeta, por ejemplo `AB_Lakehouse`. Este será su artefacto de prueba y se reutilizará durante el entrenamiento.
- [ ] Descarga del repositorio mediante Code > Download ZIP, o clonación con Git; localizar los archivos en `dataset/csv`. Conservar los archivos originales, sin abrirlos y guardarlos de nuevo desde Excel.

Ejemplo de organización; reemplazar `AB` por el prefijo propio:

```text
Workspace: LAB-Fabric-Banca
  Carpeta del participante: AB
    AB_Lakehouse
    AB_Pipeline       (sesiones posteriores)
    AB_Notebook       (sesiones posteriores)
    AB_Modelo         (sesiones posteriores)
    AB_Reporte        (sesiones posteriores)
```

**Carpeta y nomenclatura son requisitos simultáneos.** Las carpetas organizan los artefactos, pero no constituyen una frontera de seguridad entre participantes: no modificar ni borrar el trabajo de los demás.

Si algo falla, registrar el mensaje exacto y coordinar con el administrador o punto focal técnico del equipo antes del encuentro. No incluir contraseñas, tokens ni capturas con información de otros proyectos.

### B. Lectura dirigida de Microsoft Learn

Revisar el módulo oficial [Introduction to end-to-end analytics using Microsoft Fabric](https://learn.microsoft.com/en-us/training/modules/introduction-end-analytics-use-microsoft-fabric/).

Enfocar la lectura en capacidades de la plataforma, funciones del equipo de datos y uso de Fabric. Las secciones sobre otras capacidades no agregan requisitos ni prácticas a este entrenamiento. La disponibilidad del contenido en español depende de Microsoft Learn.

**Tiempo orientativo de lectura:** 25–40 minutos, fuera de la sesión. Completar la evaluación del módulo como autoevaluación; no se requiere certificación ni aprobar un examen oficial para participar.

Llegar con respuestas breves a estas preguntas:

1. ¿Qué diferencia hay entre capacidad, workspace y Lakehouse?
2. ¿Qué función cumple OneLake?
3. ¿Dónde conservarías un CSV original y dónde una tabla depurada?
4. ¿Qué diferencia hay entre un modelo semántico y un reporte de Power BI?
5. ¿Qué parte del recorrido te resulta más familiar y cuál te genera más dudas?

### C. Conocer el caso de práctica

Leer el [README del dataset](../../dataset/README.md) y las secciones de clientes, cuentas y transacciones del [diccionario de datos](../../dataset/diccionario.md).

El caso simula actividad bancaria **completamente ficticia** entre abril y septiembre de 2026. La pregunta inicial será: **¿cómo cambia la cantidad de transacciones por mes y por canal?**

No usar información de una entidad real, conexiones productivas ni datos personales.

## 2. Agenda de la sesión — 60 minutos

| Minutos | Actividad | Resultado |
|---|---|---|
| 00–10 | Repaso del pre-work y dudas consolidadas | Identificar dudas conceptuales y bloqueos ya reportados |
| 10–20 | Mapa del recorrido: OneLake, Lakehouse, pipelines, notebooks, modelo semántico y Power BI | Entender qué hace cada componente |
| 20–30 | Demostración guiada sobre el caso bancario sintético | Distinguir carpeta del workspace, Files y Tables |
| 30–45 | Práctica individual: primeros archivos en el Lakehouse | Cada participante carga y ubica sus archivos |
| 45–55 | Preguntas y revisión de resultados | Comprobar comprensión y resolver dudas comunes |
| 55–60 | Accionables y criterios de entrega | Dejar claro qué debe estar listo antes de la Sesión 2 |

Los primeros 10 minutos no son una ventana de instalación. Un bloqueo administrativo se deriva al responsable del ambiente; no se extiende la sesión para configurarlo.

## 3. Mapa conceptual del recorrido

```text
CSV sintéticos
  -> Files del Lakehouse: originales / bronce
  -> Tablas Delta: datos depurados / plata
  -> Tablas de consumo: métricas y agregaciones / oro
  -> Modelo semántico
  -> Reporte de Power BI
```

Bronce, plata y oro describen etapas lógicas de tratamiento de los datos. No es obligatorio crear un workspace independiente por capa. Un pipeline orquesta tareas y movimiento de datos; un notebook permite programar lecturas y transformaciones. El modelo semántico define relaciones y medidas; el reporte presenta visualizaciones para responder preguntas del negocio.

En esta sesión solo se prepara la fuente en **Files**. Subir un CSV **no lo convierte automáticamente en una tabla Delta** ni lo deja listo para consultarlo con SQL.

## 4. Práctica en vivo — primeros archivos

### Paso 1. Abrir el artefacto correcto

Entrar al workspace compartido, abrir la carpeta propia y seleccionar el Lakehouse creado en el pre-work. Verificar el prefijo antes de cargar archivos.

Si la interfaz creó el Lakehouse en la raíz del workspace, moverlo a la carpeta propia mediante la opción disponible en el portal antes de continuar.

### Paso 2. Crear la ruta de archivos

Dentro del Lakehouse, abrir **Files** y crear esta estructura:

```text
Files
  bronze
    banca_sintetica
```

Esta ruta vive **dentro del almacenamiento del Lakehouse**; no es la carpeta que organiza los artefactos en el workspace.

### Paso 3. Cargar los dos primeros CSV

En `Files/bronze/banca_sintetica`, usar la opción de cargar archivos del Lakehouse para subir:

- `clientes.csv`
- `cuentas.csv`

Usar los archivos que están en la subcarpeta `csv` del paquete, no el ZIP. No crear un Dataflow ni usar una opción de convertir a tabla en este paso. Las etiquetas del portal pueden variar según el idioma.

### Paso 4. Inspeccionar sin transformar

Abrir la vista previa de los archivos cuando esté disponible. Identificar `cliente_id` en ambos y `cuenta_id` en cuentas. Consultar el diccionario para interpretar los campos; no eliminar ni corregir filas en bronce.

Controles del archivo fuente:

| Archivo | Registros esperados, sin encabezado | Columnas esperadas |
|---|---:|---:|
| `clientes.csv` | 1.200 | 7 |
| `cuentas.csv` | 1.800 | 6 |

**Una vista previa puede mostrar solo una muestra.** No reportar ese número como conteo total comprobado. Los valores de esta tabla y del manifiesto son controles esperados; los conteos completos se comprobarán en la práctica de ingesta de la Sesión 2.

### Paso 5. Explicar el resultado

Cada participante debe poder mostrar su carpeta, su Lakehouse y los dos archivos originales, y explicar:

1. Por qué subir el archivo no equivale a tener una tabla.
2. Cómo se relaciona una cuenta con un cliente.
3. Por qué se preserva el original antes de limpiar.

Registrar el resultado en la [plantilla de evidencias](evidencias.md).

## 5. Accionables antes de la Sesión 2

**Responsable:** cada participante. **Fecha límite:** antes de la Sesión 2, una vez acordado el calendario.  
**Dedicación orientativa adicional:** 45–60 minutos, sin contar la resolución de bloqueos administrativos.

| Acción | Evidencia / criterio de finalización |
|---|---|
| Completar cualquier punto pendiente del pre-work y de la práctica | Cuenta con Pro, rol Member/Admin, carpeta y Lakehouse propios; dos archivos iniciales cargados |
| Cargar `sucursales.csv`, `productos.csv`, `calendario.csv` y `transacciones.csv` en la misma ruta | Seis CSV del núcleo del laboratorio presentes; originales sin editar. `creditos.csv` es opcional |
| Leer los controles de calidad del README | Explicar por qué 72.360 filas bronce se convertirán en 72.000 movimientos plata; no realizar aún la limpieza |
| Responder las cinco preguntas conceptuales del pre-work | Respuestas propias, de 1–3 líneas cada una |
| Proponer una pregunta adicional para el reporte final | Una pregunta que pueda responderse con las columnas disponibles; por ejemplo, actividad por segmento |
| Completar la plantilla de evidencias y revisarla con el punto focal | Estado por participante, sin confundir conteos esperados con medidos |

**En esta entrega no se pide:** implementar pipelines, escribir notebooks de transformación, crear el modelo semántico ni publicar el reporte. Son pasos posteriores del recorrido, no tareas ocultas de la Sesión 1.

## 6. Cierre y dudas

El punto focal técnico revisa las entregas, ayuda a resolver los problemas de primer nivel y consolida **hasta tres dudas prioritarias** para el inicio de la Sesión 2. Los bloqueos de acceso deben escalarse al administrador tan pronto se detecten, no esperar al próximo encuentro.

El equipo conserva las evidencias en su ubicación interna acordada y facilita al instructor el estado consolidado. Las dudas se revisan dentro de las sesiones programadas; este formato no presupone tutorías ni revisión individual continua fuera de ellas.

## Referencias

- [Módulo introductorio de Microsoft Learn](https://learn.microsoft.com/en-us/training/modules/introduction-end-analytics-use-microsoft-fabric/).
- [Tutorial oficial de creación de un Lakehouse](https://learn.microsoft.com/en-us/fabric/data-engineering/tutorial-build-lakehouse). Usar como referencia de navegación: el tutorial completo emplea otro dataset y otro flujo de ingesta; no es un ejercicio adicional asignado.
- [Requisitos del laboratorio](../requisitos.md).
- [Guía del dataset](../../dataset/README.md).

Los enlaces oficiales se consultaron al preparar esta versión; la interfaz y el contenido de Microsoft Learn pueden cambiar.
