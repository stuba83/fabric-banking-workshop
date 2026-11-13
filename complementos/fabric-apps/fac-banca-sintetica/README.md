# Banca sintética: Fabric App sobre un Warehouse

Aplicación de datos de **Microsoft Fabric (Fabric Apps, framework Rayfin)** hecha con React, Vite y TypeScript. Muestra un panel de transacciones bancarias **sintéticas** que se leen en vivo de un **Warehouse de Fabric**. Sirve como demostración para un facilitador en un taller didáctico: no contiene datos reales de ninguna entidad.

> **Datos sintéticos · Taller de Microsoft Fabric.** El rótulo aparece de forma permanente en el encabezado de la aplicación.

> **Estado del servicio: vista previa.** Fabric Apps y Rayfin están en vista previa pública; los comandos, paquetes y comportamientos pueden cambiar. Verifica el estado actual en [Fabric Apps (versión preliminar)](https://learn.microsoft.com/en-us/fabric/apps/overview), en [Crear y desplegar tu primera app con la CLI de Rayfin](https://learn.microsoft.com/en-us/fabric/apps/create-app-with-cli) y en [github.com/microsoft/rayfin](https://github.com/microsoft/rayfin). Esta app se construyó con Rayfin CLI `1.36.2`.

## Qué muestra

- **Encabezado** con el nombre «Banca sintética», el rótulo de datos sintéticos y el usuario conectado con el inicio de sesión de Fabric (SSO). Incluye un botón de tema claro/oscuro.
- **Filtros** por canal y por provincia. Afectan a las tarjetas, a los dos gráficos mensuales y a la tabla; el gráfico por provincia resalta la provincia elegida y atenúa las demás.
- **Tarjetas**: transacciones, monto total, ticket promedio, canal principal (con su participación) y neto de créditos menos débitos.
- **Gráficos**: transacciones por mes y canal, monto por mes y canal, y monto por provincia.
- **Tabla** por sucursal, ordenable (clic en el encabezado) y paginada.
- **Control de cuadre**: compara lo calculado desde la tabla de hechos con la tabla resumen `transacciones.resumen_mes_canal` y lo muestra al pie.

Montos en colones costarricenses (₡); «M» significa millones.

## Requisitos

- Acceso a Fabric y un área de trabajo (workspace) donde tengas el rol **Contributor, Member o Admin**.
- La carga de trabajo **Fabric Apps (versión preliminar) habilitada en el tenant** (la activa un administrador en el portal de administración, en *Tenant settings*).
- Una **capacidad de Fabric activa** asignada al workspace. Fabric Apps tampoco está disponible en todas las regiones todavía.
- **Node.js** 20, 22 o 24 y **npm**. La CLI de Rayfin declara ese rango; con una versión más nueva `npm install` solo muestra una advertencia.
- Un **Warehouse** (o el endpoint SQL de un Lakehouse) con el modelo descrito en [Modelo de datos esperado](#modelo-de-datos-esperado).

## Estructura

```text
rayfin/rayfin.yml                      Servicios de Rayfin y declaración del conector
rayfin/connectors/fac_wh_gold/         Entidades tipadas de las tablas que lee la app
packages/frontend/                     La aplicación (React + Vite)
  src/data/warehouse.ts                Consultas agregadas al Warehouse
  src/hooks/use-banking-data.ts        Carga, caché por provincia y estados de error
  src/lib/banking-metrics.ts           Cálculos puros (KPI, filtros, conciliación)
  src/lib/banking-format.ts            Formatos y etiquetas en español
  src/components/dashboard/            Encabezado, filtros, tarjetas, gráficos y tabla
packages/data, packages/shared         Paquetes base del scaffold (sin entidades propias)
.agents/skills/                        Guías para agentes de código incluidas por el scaffold
```

## Cómo se creó

1. Se generó el proyecto con el scaffold oficial (plantilla por defecto, *Universal App*):

   ```bash
   npm create @microsoft/rayfin@latest -- <nombre-del-proyecto> --workspace <nombre-del-workspace>
   cd <nombre-del-proyecto>
   ```

2. Se aplicaron los paquetes de capacidades **uno por comando** y se conectó el Warehouse existente:

   ```bash
   npm run pack:add -- connectors
   npx rayfin connector search "<nombre-del-warehouse>" --type fabric-warehouse --all-workspaces --json
   npx rayfin connector add --type fabric-warehouse \
     --workspace-id <id-del-workspace> --item-id <id-del-warehouse> \
     --name fac_wh_gold --operations read
   npm install -w @rayfin-app/frontend <paquetes-y-versiones-que-imprime-connector-add>
   npm run pack:add -- visuals
   ```

3. Se generaron las entidades de las tablas necesarias en `rayfin/connectors/fac_wh_gold/`, se escribió el `schema.ts` agregado y se cableó `packages/frontend/src/lib/connectors.ts` (se sigue el contrato de las guías instaladas en `node_modules/@microsoft/rayfin-connector-fabric-graphql/assets/docs`).

4. Se cambió `auth.type` del conector a `delegated` en `rayfin/rayfin.yml` (consulta con la identidad del usuario) y se habilitaron los decoradores TC39 en `packages/frontend/vite.config.ts` (`useAtYourOwnRisk_mutateSwcOptions`, igual que ya hacía `vitest.config.ts`), porque las clases de entidad de `rayfin/connectors/` entran al paquete del navegador.

5. El resto lo escribió GitHub Copilot a partir de un prompt como este, basado en el de la [documentación](https://learn.microsoft.com/en-us/fabric/apps/create-app-with-cli):

   ```text
   Configura un nuevo proyecto de Fabric App llamado "<nombre-del-proyecto>".

   1. Ejecuta: npx -y @microsoft/create-rayfin@latest --project-name <nombre-del-proyecto> --template blankapp
   2. Abre el directorio del proyecto y lee AGENTS.md y los skills de .agents/skills
      (empieza por capability-router). Aplica un paquete por comando.
   3. Conecta el Warehouse "<nombre-del-warehouse>" del workspace "<nombre-del-workspace>"
      con el conector fabric-warehouse, solo lectura e identidad delegada. No inventes IDs,
      esquemas ni datos: descubre los nombres reales consultando el Warehouse.
   4. Construye, en español y con estilo sobrio, una app de datos sintéticos con:
      - encabezado «Banca sintética» y el rótulo «Datos sintéticos · Taller de Microsoft Fabric»;
      - tarjetas de transacciones, monto total, ticket promedio y una más con sentido;
      - gráfico de transacciones y monto por mes separado por canal, y gráfico por provincia;
      - filtros por canal y provincia que afecten a todos los visuales;
      - tabla paginada y ordenable por sucursal;
      - el inicio de sesión de Fabric que deja el scaffold, mostrando el usuario conectado;
      - accesibilidad básica y buen aspecto a 1440 y 1280 px.
   5. Añade pruebas de los cálculos y ejecuta: npm run typecheck, npm run lint, npm test, npm run build:fabric.
   6. Previsualiza con: npx rayfin up --dry-run
      y, cuando yo confirme el workspace, despliega con: npx rayfin up
   ```

## Modelo de datos esperado

La app lee estas tablas (esquema `schema.tabla`; nombres en minúsculas, porque la intercalación por defecto de un Warehouse distingue mayúsculas):

| Tabla | Columnas que usa | Para qué |
| --- | --- | --- |
| `transacciones.fact_transaccion` | `cuenta_id`, `fecha` (date), `canal`, `direccion` (`CREDITO`/`DEBITO`), `monto` (decimal) | Todos los cálculos |
| `cuentas.dim_cuenta` | `cuenta_id`, `cliente_id` | Llegar de la transacción a la sucursal |
| `clientes.dim_cliente` | `cliente_id`, `sucursal_id` | Ídem |
| `clientes.dim_sucursal` | `sucursal_id`, `nombre_sintetico`, `provincia` | Filtro por provincia y tabla por sucursal |
| `transacciones.resumen_mes_canal` | `mes` (`yyyy-MM`), `canal`, `transacciones`, `monto_creditos`, `monto_debitos` | Control de cuadre |

`monto` es una magnitud positiva; `direccion` define si es entrada (`CREDITO`) o salida (`DEBITO`). Las llaves foráneas entre tablas son metadatos (`NOT ENFORCED`) y los conectores las usan para generar las relaciones entre entidades.

## Conectar un Warehouse o un endpoint SQL propio

1. Obtén los IDs del workspace y del elemento:

   ```bash
   npx rayfin connector search "<nombre-del-warehouse>" --type fabric-warehouse --all-workspaces --json
   ```

   Para un Lakehouse usa `--type fabric-sqlanalytics` (solo lectura; es su endpoint SQL, no sus archivos). Ese endpoint suele no traer llaves foráneas: las consultas filtran a través de las relaciones `dimCuenta → dimCliente`, así que tendrías que declarar los `@one`/`@many` a mano en las entidades.
2. En `rayfin/rayfin.yml` sustituye los marcadores `<id-del-workspace>` e `<id-del-warehouse>` por los valores literales (`connector add` no acepta variables). Si usas el endpoint SQL de un Lakehouse, cambia también `type` a `fabric-sqlanalytics` y `connector: 'fabric-warehouse'` por `'fabric-sqlanalytics'` en `rayfin/connectors/fac_wh_gold/schema.ts`.
3. Si tus tablas o columnas tienen otros nombres, edita los `Source({ schema, table, primaryKey })` y las columnas de las cinco clases en `rayfin/connectors/fac_wh_gold/`. Para regenerar `metadata.json` (se obtiene al volver a declarar el conector) y las entidades desde cero, sigue las guías de `node_modules/@microsoft/rayfin-connector-fabric-graphql/assets/docs`. No ejecutes `connector add --yes` sobre un conector ya escrito a mano: reemplaza el `schema.ts` por un marcador.
4. Si cambias nombres de entidad o de propiedad, ajusta las consultas de `packages/frontend/src/data/warehouse.ts`.
5. Para otro conjunto de datos con la misma forma (hechos con canal y monto, dimensiones de sucursal y provincia) no hace falta tocar la interfaz.

## Cómo consulta los datos

Rayfin expone cada tabla como una API GraphQL tipada (Data API Builder) con identidad **delegada**: la consulta corre con el usuario que inició sesión, no con una identidad compartida de la aplicación.

- Las cifras salen de **agregaciones en el Warehouse** (`groupBy` + `sum`/`count`), no de descargar las filas. Descargar las ~72 000 transacciones tarda más de 12 s; las consultas agregadas terminan en unos 4–5 s en total.
- Una consulta agregada devuelve **como máximo 100 grupos**. Por eso cada consulta agrupa solo por `canal` y `direccion` (10 grupos como máximo) y se parte por sucursal (7 consultas) o por mes (6 consultas), con filtros sobre la relación `fact → cuenta → cliente → sucursal`. Si tu modelo tiene más canales o direcciones, parte las consultas con más criterios para no pasar de 100 grupos; un resultado truncado se vería como cifras que no cuadran, y el control de cuadre lo delata.
- El **filtro de canal** se aplica en memoria. El **filtro de provincia** se empuja al Warehouse para la serie mensual (6 consultas la primera vez que se elige una provincia, y se guardan en caché); las tarjetas, la tabla y el gráfico por provincia se calculan con los datos ya cargados.
- Los meses se derivan de la fecha mínima y máxima de la tabla de hechos, no de una lista fija.

## Ejecutar en local

```bash
npm install
npx rayfin login            # abre el navegador; inicia sesión con tu cuenta de Fabric
npx rayfin up               # una vez, para crear/actualizar el elemento y publicar el conector
npm run dev:frontend        # http://localhost:5173
```

Los conectores **solo corren en la nube** (`rayfin dev` los ignora). Con el elemento ya desplegado, `npm run dev:frontend` abre la interfaz local con tu sesión de la CLI y consulta el backend publicado. Sin ese primer `rayfin up` la pantalla muestra un aviso de configuración incompleta, por diseño.

## Validar y desplegar

```bash
npm run typecheck
npm run lint
npm test
npm run build:fabric
npm run validate:visual:preview   # los gráficos se construyen en ejecución: solo valida lo estático

npx rayfin up --dry-run --workspace "<nombre-del-workspace>"
npx rayfin up --workspace "<nombre-del-workspace>" --item-name <nombre-del-proyecto>
npx rayfin up status
```

`rayfin up` imprime la URL de alojamiento y el enlace del portal de Fabric. La aplicación desplegada exige iniciar sesión (`assetAccess: protected`); sin sesión de Fabric responde 401. No se agregan contraseñas ni se desactiva esa protección.

Pruebas: `npm test` ejecuta las del scaffold (sesión, temas, cliente) y las de esta app: cálculo de KPI, filtros, ordenamiento, meses, conciliación con el resumen y pantalla principal con datos de ejemplo con la forma de la respuesta real.

## Seguridad por filas (RLS) por provincia

**No está implementada** porque exige cambiar el Warehouse. Así se aplicaría:

- El conector usa `auth.type: delegated`, de modo que la consulta llega al Warehouse con la identidad de cada usuario. Con `application` todos compartirían la identidad de la app y no se podría distinguir a las personas.
- El Warehouse admite [seguridad a nivel de fila](https://learn.microsoft.com/en-us/fabric/data-warehouse/row-level-security): un predicado escrito como función en línea y una `SECURITY POLICY` por tabla. Un esquema posible (no ejecutado):

  ```sql
  CREATE SCHEMA seguridad;
  CREATE TABLE seguridad.usuario_provincia (usuario varchar(128) NOT NULL, provincia varchar(30) NOT NULL);

  CREATE FUNCTION seguridad.fn_sucursal(@sucursal_id varchar(20))
  RETURNS TABLE WITH SCHEMABINDING AS
  RETURN SELECT 1 AS permitido
  FROM clientes.dim_sucursal s
  JOIN seguridad.usuario_provincia up ON up.provincia = s.provincia
  WHERE s.sucursal_id = @sucursal_id AND up.usuario = USER_NAME();

  CREATE SECURITY POLICY seguridad.politica_sucursal
    ADD FILTER PREDICATE seguridad.fn_sucursal(sucursal_id) ON clientes.dim_sucursal;
  -- Repetir con una función que llegue a la sucursal desde cliente, cuenta y transacción
  -- (cada tabla necesita su propia política).
  ```

- Los roles Admin, Member y Contributor del workspace también quedan sujetos a la política: si necesitan ver todo, la función debe permitirlo. Pruébalo con usuarios de rol Viewer o con acceso compartido.
- La aplicación no cambia: al ver menos filas, las agregaciones, los filtros y el control de cuadre se calculan sobre lo permitido (el control de cuadre dejaría de coincidir con un resumen que no tenga la misma política; habría que aplicarla también a `resumen_mes_canal` o retirar ese control).
- Rayfin también permite políticas por fila en la propia entidad (`@role(..., { policy })` con `claims`), pero necesitan una columna que identifique al usuario; este modelo no la tiene.

## Límites conocidos

- Fabric Apps está en **vista previa**: puede cambiar sin aviso y no está disponible en todas las regiones.
- La interfaz desplegada exige sesión de Fabric; se verificó con el *build*, las pruebas y la interfaz local contra el backend publicado. Revisa a mano la URL desplegada con tu usuario antes de presentar.
- Que el Warehouse reciba la identidad del usuario (y por tanto que RLS filtre por persona) **no se verificó**; lo documenta la guía de Rayfin para `delegated`.
- La carga inicial son ~17 consultas (≈4–5 s). La primera selección de cada provincia agrega ~1–2 s para la serie mensual.
- El filtro de provincia **resalta** en el gráfico por provincia en lugar de dejar una sola barra; el resto de los visuales sí se filtran.
- Los montos están en colones; no hay conversión de moneda. El canal `NO_INFORMADO` se muestra tal cual viene del origen.
- El paquete del navegador pesa ~1,4 MB (~480 kB comprimido) por la biblioteca de gráficos; no se dividió en partes.
- No hay datos de muestra de reserva: si el Warehouse no responde, la app muestra el error y un botón para reintentar.

## Licencia

MIT (ver `LICENSE`). Datos y nombres de sucursales y clientes son ficticios.

