# Sesión 4 — Modelo semántico, seguridad por filas y gobernanza

**Audiencia:** Ingenieros de datos  
**Duración en vivo:** 60 minutos, sin extensión  
**Fecha y horario:** por definir en cada entrenamiento  
**Modalidad:** Demostración breve, ejecución individual y verificación con **Probar como rol** (*Test as role*)

## Resultado esperado

Cada participante creará un **modelo semántico Direct Lake** sobre las tablas plata de la [Sesión 3](../sesion-03/guia.md), con relaciones y tres medidas, y construirá un reporte de una página que responde la pregunta del caso: **¿cómo cambia la cantidad de transacciones por mes y por canal?** Después definirá una regla de **seguridad por filas** por sucursal y comprobará, con **Probar como rol**, que cada rol ve solo su parte. Por último, revisará el **linaje** de su trabajo, lo encontrará en el **catálogo de OneLake** y **promoverá** su modelo.

La comprobación que debe cuadrar:

```text
Sin rol:         72.000 transacciones
Rol Heredia:      8.971 transacciones
Rol Guanacaste:   4.963 transacciones
```

**El modelo expone los datos; el rol decide qué filas ve cada persona.** Las tablas del Lakehouse no se modifican en esta sesión.

## 1. Pre-work

### Ambiente y estado de partida

Completar la Sesión 3 y mantener los [requisitos del laboratorio](../requisitos.md):

- Las **nueve tablas** de la Sesión 3 existen en el Lakehouse propio, con los conteos medidos (`<prefijo>_silver_transacciones` con 72.000 filas).
- Licencia **Power BI Pro** activa: es necesaria para crear y editar reportes y modelos en un workspace compartido.
- Evidencias de la Sesión 3 completas o con los bloqueos registrados.

Si la Sesión 3 no terminó, completarla primero: esta sesión lee las tablas plata y no las genera.

### Lectura dirigida

- [Direct Lake: visión general](https://learn.microsoft.com/en-us/fabric/fundamentals/direct-lake-overview) (inglés).
- [Seguridad por filas (RLS) con Power BI](https://learn.microsoft.com/en-us/fabric/security/service-admin-row-level-security) (inglés). Leer el inicio y las secciones «Manage security on your semantic model» y «Validate the role within the Power BI service».

Llegar con respuestas breves:

1. ¿A qué roles del workspace **no** se les aplica la seguridad por filas y cómo se comprueba entonces una regla?
2. ¿Qué diferencia hay entre **promover** y **certificar** un elemento, y quién puede hacer cada cosa?
3. ¿Qué muestra el linaje de un workspace y qué no muestra?

**Preparación orientativa:** 25–40 minutos, además de resolver bloqueos de ambiente.

## 2. Agenda — 60 minutos

| Minutos | Actividad | Resultado |
|---|---|---|
| 00–10 | Revisar entregas de la Sesión 3 y dudas consolidadas | Confirmar las nueve tablas y los conteos; derivar bloqueos administrativos |
| 10–20 | Direct Lake y diseño del modelo: qué tablas entran y por qué | Entender relaciones, medidas y el papel de la tabla oro |
| 20–35 | Demostración: modelo, relaciones, medidas y un visual | Ver el flujo completo en el editor web |
| 35–48 | Seguridad: roles del workspace, seguridad por filas y **Probar como rol** | Entender a quién se aplica la regla y cómo se verifica |
| 48–55 | Gobernanza: linaje, catálogo de OneLake y elementos promovidos | Leer el recorrido de los datos y señalar elementos confiables |
| 55–60 | Asignar accionables y decisiones por documentar | Acordar evidencias para la Sesión 5 |

La creación del modelo y de los roles puede consumir más tiempo del previsto. Si algo sigue pendiente al cierre, completarlo como accionable; **en curso no equivale a completado**. La sesión no se extiende.

## 3. Diseño del modelo

```text
Lakehouse (tablas plata)
  -> Modelo semántico Direct Lake: 6 tablas, 5 relaciones, 3 medidas
      -> Reporte de una página
      -> Rol de seguridad por filas (sobre la tabla de sucursales)
```

### Qué tablas entran y cuáles no

| Tabla | ¿Entra? | Motivo |
|---|---|---|
| `<prefijo>_silver_transacciones` | Sí | Tabla de hechos: una fila por movimiento válido |
| `<prefijo>_silver_cuentas`, `_clientes`, `_sucursales`, `_productos` | Sí | Dimensiones para filtrar y para la seguridad por sucursal |
| `<prefijo>_silver_calendario` | Sí | Dimensión de fechas |
| `<prefijo>_silver_transacciones_cuarentena` y `_duplicadas` | **No** | Son tablas de auditoría, no de análisis |
| `<prefijo>_gold_transacciones_mes_canal` | **No** | Ver la advertencia siguiente |

**Advertencia sobre la tabla oro.** Resume por mes y canal y **no tiene columna de sucursal**. La seguridad por filas filtra a través de las relaciones del modelo: una tabla sin relación con la sucursal no se filtra, y un usuario restringido a Heredia vería en ella los totales de todo el país. Por eso el reporte se construye sobre la tabla de hechos y la tabla oro se usa solo como **control**: los valores del reporte deben coincidir con los de la oro.

### Relaciones

Todas son de muchos a uno, con filtro en **una sola dirección** (de la tabla «uno» hacia la tabla «muchos»). No activar el filtro bidireccional ni la opción de aplicar el filtro de seguridad en ambas direcciones.

| # | Desde (muchos) | Hacia (uno) |
|---|---|---|
| 1 | `<prefijo>_silver_transacciones[cuenta_id]` | `<prefijo>_silver_cuentas[cuenta_id]` |
| 2 | `<prefijo>_silver_cuentas[cliente_id]` | `<prefijo>_silver_clientes[cliente_id]` |
| 3 | `<prefijo>_silver_clientes[sucursal_id]` | `<prefijo>_silver_sucursales[sucursal_id]` |
| 4 | `<prefijo>_silver_cuentas[producto_id]` | `<prefijo>_silver_productos[producto_id]` |
| 5 | `<prefijo>_silver_transacciones[fecha]` | `<prefijo>_silver_calendario[fecha]` |

La sucursal filtra a los clientes, los clientes a las cuentas y las cuentas a las transacciones: así una regla sobre la tabla de sucursales restringe también los movimientos.

### Medidas

Reemplazar `ab_` por el prefijo propio, en minúsculas. Crearlas en la tabla de transacciones.

```dax
Transacciones = COUNTROWS ( ab_silver_transacciones )

Monto créditos =
CALCULATE (
    SUM ( ab_silver_transacciones[monto] ),
    ab_silver_transacciones[direccion] = "CREDITO"
)

Monto débitos =
CALCULATE (
    SUM ( ab_silver_transacciones[monto] ),
    ab_silver_transacciones[direccion] = "DEBITO"
)
```

El monto es una **magnitud positiva** y la dirección determina el efecto: no restar débitos con signo.

## 4. Práctica

### Paso 1. Crear el modelo desde el Lakehouse

1. Abrir el Lakehouse propio y seleccionar **New semantic model**.
2. Nombrarlo con el prefijo propio, por ejemplo `AB_SM_Transacciones`, y elegir el workspace de laboratorio.
3. Seleccionar **solo las seis tablas** de la sección anterior. Si el asistente pregunta el tipo de Direct Lake, aceptar el valor predeterminado.
4. Mantener el modelo y, más adelante, el reporte en la carpeta propia del workspace.

### Paso 2. Relaciones, fechas y medidas

1. Abrir el modelo y pasar a **modo de edición**. En **Manage relationships**, crear las cinco relaciones de la tabla anterior y revisar cardinalidad y dirección.
2. Marcar `<prefijo>_silver_calendario` como **tabla de fechas** (clic derecho → **Mark as date table**) usando la columna `fecha`.
3. En el panel de propiedades, ordenar `nombre_mes` por `mes` y `nombre_dia` por `dia_semana`, para evitar el orden alfabético.
4. Crear las tres medidas.

### Paso 3. Reporte de una página

Crear un reporte a partir del modelo, con:

- Una **matriz o gráfico**: filas `nombre_mes`, columnas `canal`, valor `Transacciones`.
- Tres **tarjetas**: `Transacciones`, `Monto créditos` y `Monto débitos`.
- Un **segmentador** por `provincia` (de la tabla de sucursales).

Guardar el reporte con el prefijo propio, por ejemplo `AB_RP_Transacciones`.

### Paso 4. Seguridad por filas y verificación

1. En el modelo, seleccionar **Manage roles** y crear el rol `Heredia`. Aplicarlo a `<prefijo>_silver_sucursales` con el filtro DAX:

   ```dax
   [provincia] = "Heredia"
   ```

2. Crear un segundo rol, `Guanacaste`, con `[provincia] = "Guanacaste"`. Guardar.
3. En el workspace, abrir el menú **More options** del modelo → **Security**. Para cada rol, abrir **More options** junto al rol → **Test as role**.
4. Comparar las tarjetas con la tabla de controles de la sección 5. Volver con **Back to Row-Level Security**.

**No agregar usuarios a los roles** y **no cambiar los roles del workspace compartido** en esta práctica: el objetivo es comprobar la regla, no publicarla.

**La seguridad por filas no se aplica a Admin, Member ni Contributor.** Todos los participantes tienen un rol de Member o Admin, así que el reporte normal siempre muestra todo; solo **Probar como rol** muestra el efecto de la regla. En un uso real, la regla actúa únicamente sobre quienes tienen el rol **Viewer**.

### Paso 5. Gobernanza

1. **Linaje.** En el workspace, abrir la **vista de linaje** (*Lineage view*) desde la barra del workspace. Localizar el Lakehouse, los notebooks, el pipeline, el modelo y el reporte propios. Usar la flecha de la tarjeta para resaltar el linaje de un elemento. El linaje muestra **elementos y sus conexiones**, no tablas ni columnas.
2. **Catálogo de OneLake.** Abrir el catálogo desde el panel de navegación, en la pestaña **Explore**, y encontrar el modelo propio por su prefijo. Revisar su detalle: propietario, workspace y sello de endoso.
3. **Descripción.** En la configuración del modelo, agregar una descripción breve: qué contiene y de qué tablas se alimenta.
4. **Promover.** En la configuración del modelo, expandir **Endorsement**, seleccionar **Promoted** y luego **Apply**. **No marcar «Make discoverable»** en esta práctica.

Promover indica que el elemento está **listo para compartirse y reutilizarse**. La certificación y la designación de datos maestros las otorgan únicamente los revisores que el administrador de Fabric autorice, por lo que no se practican aquí.

## 5. Resultado verificable

### Sin rol (como Member o Admin)

| Medida | Valor esperado |
|---|---:|
| `Transacciones` | 72.000 |
| `Monto créditos` | 14.976.153.627,79 |
| `Monto débitos` | 4.530.373.831,90 |

La matriz mes × canal debe coincidir con la tabla oro. Por ejemplo, abril con `ATM` suma **1.365** y septiembre con `BANCA_MOVIL` suma **7.402**. Los totales por mes deben ser 11.198, 11.422, 11.757, 12.093, 12.541 y 12.989, y los totales por canal, los de la Sesión 3.

### Probando cada rol

| Sucursal | `provincia` | Transacciones | Monto créditos | Monto débitos |
|---|---|---:|---:|---:|
| `SUC01` | `San Jose` | 20.708 | 4.306.335.336,20 | 1.294.151.130,20 |
| `SUC02` | `Alajuela` | 13.840 | 2.869.299.344,17 | 879.889.217,02 |
| `SUC03` | `Cartago` | 10.689 | 2.226.302.654,31 | 661.871.675,20 |
| **`SUC04`** | **`Heredia`** | **8.971** | **1.886.882.777,70** | **565.981.597,44** |
| **`SUC05`** | **`Guanacaste`** | **4.963** | **1.019.466.999,49** | **313.484.708,53** |
| `SUC06` | `Puntarenas` | 7.281 | 1.506.900.739,54 | 472.402.374,88 |
| `SUC07` | `Limon` | 5.548 | 1.160.965.776,38 | 342.593.128,63 |

Las siete filas suman 72.000 transacciones y los totales de la tabla anterior. **Estos valores son controles esperados:** el participante debe medirlos él mismo en **Probar como rol** y registrarlos en las evidencias. Con el rol `Heredia`, el segmentador de provincia solo debe ofrecer Heredia.

### Lo que no se practica en esta sesión

El facilitador mencionará, sin ejercicio ni evidencia, otros controles que dependen de la versión y del tenant: la seguridad a nivel de datos en OneLake, las etiquetas de confidencialidad y el acceso de los usuarios finales a un modelo Direct Lake (con identidad propia o con una conexión de identidad fija). Tampoco se comparten elementos con personas externas al laboratorio.

## 6. Accionables antes de la Sesión 5

**Responsable:** cada participante. **Plazo:** antes de la Sesión 5.  
**Dedicación orientativa:** 45–60 minutos de trabajo activo si se siguen los pasos; la primera vez en el editor web puede tomar más.

| Acción | Criterio de finalización |
|---|---|
| Crear el modelo con seis tablas, cinco relaciones y tres medidas | Medidas sin rol: 72.000 / 14.976.153.627,79 / 4.530.373.831,90 |
| Construir el reporte de una página | Matriz mes × canal que coincide con la tabla oro en al menos dos celdas |
| Crear los roles `Heredia` y `Guanacaste` y probarlos | Valores medidos en **Probar como rol** que coinciden con la tabla de controles |
| Revisar el linaje y encontrar el modelo en el catálogo | Descripción de lo que se ve y de qué elementos faltan |
| Agregar descripción y promover el modelo | Sello **Promoted** visible en el catálogo |
| Responder las preguntas de comprensión | Respuestas con sus propias palabras |

Usar la [plantilla de evidencias](evidencias.md). Las evidencias las completa cada participante y se conservan dentro de la organización. La práctica continúa en la [Sesión 5: cierre y revisión de entregables](../sesion-05/guia.md).

## 7. Bloqueos frecuentes

| Síntoma | Revisar |
|---|---|
| No aparece **New semantic model** o no se puede editar el modelo | Licencia Power BI Pro, rol en el workspace y que el Lakehouse esté en una capacidad Fabric |
| Faltan tablas al crear el modelo o aparecen vacías | Que la Sesión 3 terminó bien; esperar la sincronización y reintentar |
| Las medidas dan otro valor | Relaciones (cardinalidad y dirección), el prefijo en el DAX y que no entraron la oro ni las tablas de auditoría |
| El mes se ordena alfabéticamente | **Sort by column** de `nombre_mes` por `mes` |
| **Test as role** no aparece o muestra todo | Que el rol esté guardado y definido sobre la tabla de sucursales; que se use **Test as role** y no el reporte normal |
| El rol no filtra las transacciones | Relaciones 1 a 3 (sucursal → cliente → cuenta → transacción) y que sigan en una sola dirección |
| Todos los participantes ven todo | Es lo esperado para Admin, Member y Contributor; usar **Test as role** |
| El linaje no muestra el modelo | Que el modelo y el reporte estén en el mismo workspace |
| No puedo promover o certificar | Promover requiere permiso de escritura; certificar lo habilita el administrador |

Un bloqueo de identidad, licencia o configuración no se resuelve ampliando la sesión. El punto focal lo coordina con el administrador.

## Referencias

- [Direct Lake: visión general](https://learn.microsoft.com/en-us/fabric/fundamentals/direct-lake-overview).
- [Desarrollar modelos semánticos Direct Lake](https://learn.microsoft.com/en-us/fabric/fundamentals/direct-lake-develop).
- [Editar modelos semánticos en el servicio de Power BI](https://learn.microsoft.com/en-us/power-bi/transform-model/service-edit-data-models).
- [Seguridad por filas (RLS) con Power BI](https://learn.microsoft.com/en-us/fabric/security/service-admin-row-level-security).
- [Integrar la seguridad de Direct Lake](https://learn.microsoft.com/en-us/fabric/fundamentals/direct-lake-security-integration).
- [Linaje en Fabric](https://learn.microsoft.com/en-us/fabric/governance/lineage).
- [Catálogo de OneLake](https://learn.microsoft.com/en-us/fabric/governance/onelake-catalog-overview).
- [Endoso de elementos](https://learn.microsoft.com/en-us/fabric/governance/endorsement-overview).
- [Diccionario del dataset](../../dataset/diccionario.md) y [guía del dataset](../../dataset/README.md).

Los controles de este documento se calcularon con el dataset del repositorio, pero **los pasos en el editor web de Fabric y Power BI no se han comprobado en un tenant**: los nombres de los menús pueden variar con la versión. La creación del modelo, las relaciones, los roles y **Test as role** deben comprobarse en el tenant del participante; el repositorio no se conecta a ningún tenant ni despliega artefactos automáticamente.
