/* ============================================================================
   FAC_WH_Gold  -  02_procedimientos.sql
   Procedimientos que cargan el oro del Warehouse desde las tablas plata/oro del
   Lakehouse AB_Lakehouse (mismo workspace) con INSERT ... SELECT / MERGE.

   Lectura entre bases (Learn: "Write a cross-database query"):
       AB_Lakehouse.dbo.<tabla>
   La parte 1 es el nombre del Lakehouse (su SQL analytics endpoint), la parte 2 el esquema
   y la parte 3 la tabla. Un Lakehouse con esquemas habilitados publica las tablas que
   Spark guarda sin esquema en dbo, y uno sin esquemas también las muestra en dbo; por eso
   el nombre es el mismo en ambos casos. Mayúsculas y minúsculas importan (BIN2).
   Para otro Lakehouse o prefijo, reemplace "AB_Lakehouse.dbo.ab_" (deploy.ps1 lo hace).

   Decisión de idempotencia (documentada en el README):
     * MERGE SÍ está soportado y es GA en Fabric Warehouse (T-SQL surface area, Learn).
     * Dimensiones (clave natural, pocas filas, la fuente es la verdad): MERGE con
       WHEN NOT MATCHED BY SOURCE THEN DELETE para reflejar exactamente la fuente.
       El parámetro @estrategia permite cambiar a DELETE_INSERT con el mismo resultado.
     * Hecho y resumen (reemplazo completo de una instantánea recalculada en el Lakehouse):
       DELETE + INSERT ... SELECT. Es más simple y no compara 72.000 filas columna a
       columna. Con MERGE o DELETE se bloquea la tabla completa y dos escritores
       simultáneos sobre la misma tabla generan el error 24556/24706: serialice las
       cargas y reintente (Learn: Transactions in Fabric Data Warehouse).

   Reglas de Fabric que se respetan:
     - Transacción explícita sobre dos tablas con TRY/CATCH y ROLLBACK; sin transacciones
       anidadas ni SAVE TRANSACTION (por eso el orquestador NO abre transacción propia).
     - Sin @@ROWCOUNT, XACT_STATE() ni SET XACT_ABORT (no están documentados para
       Warehouse): las filas se cuentan con COUNT_BIG(*) dentro de la transacción.
     - THROW y la instrucción anterior terminan en punto y coma.
     - Sin cursores, triggers ni tipos no soportados.
   ============================================================================ */

-- ============================================================================
-- A. clientes.usp_cargar_clientes : dim_sucursal + dim_cliente (una transacción)
-- ============================================================================
CREATE OR ALTER PROCEDURE clientes.usp_cargar_clientes
    @lote_id    varchar(36) = NULL,
    @estrategia varchar(15) = 'MERGE'          -- MERGE | DELETE_INSERT
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @ahora          datetime2(6) = SYSUTCDATETIME();
    DECLARE @filas_sucursal bigint = 0;
    DECLARE @filas_cliente  bigint = 0;
    DECLARE @mensaje        varchar(4000);

    IF @lote_id IS NULL SET @lote_id = CONVERT(varchar(36), NEWID());
    IF @estrategia NOT IN ('MERGE', 'DELETE_INSERT')
        THROW 50001, 'usp_cargar_clientes: @estrategia debe ser MERGE o DELETE_INSERT', 1;

    BEGIN TRY
        BEGIN TRANSACTION;

        IF @estrategia = 'MERGE'
        BEGIN
            MERGE clientes.dim_sucursal AS destino
            USING (
                SELECT sucursal_id, nombre_sintetico, provincia
                FROM AB_Lakehouse.dbo.ab_silver_sucursales
            ) AS origen
            ON destino.sucursal_id = origen.sucursal_id
            WHEN MATCHED AND (destino.nombre_sintetico <> origen.nombre_sintetico
                              OR destino.provincia <> origen.provincia) THEN
                UPDATE SET nombre_sintetico = origen.nombre_sintetico,
                           provincia        = origen.provincia,
                           fecha_carga      = @ahora,
                           lote_id          = @lote_id
            WHEN NOT MATCHED BY TARGET THEN
                INSERT (sucursal_id, nombre_sintetico, provincia, fecha_carga, lote_id)
                VALUES (origen.sucursal_id, origen.nombre_sintetico, origen.provincia, @ahora, @lote_id)
            WHEN NOT MATCHED BY SOURCE THEN
                DELETE;

            MERGE clientes.dim_cliente AS destino
            USING (
                SELECT cliente_id, nombre_sintetico, fecha_alta, segmento, grupo_edad, provincia, sucursal_id
                FROM AB_Lakehouse.dbo.ab_silver_clientes
            ) AS origen
            ON destino.cliente_id = origen.cliente_id
            WHEN MATCHED AND (destino.nombre_sintetico <> origen.nombre_sintetico
                              OR destino.fecha_alta    <> origen.fecha_alta
                              OR destino.segmento      <> origen.segmento
                              OR destino.grupo_edad    <> origen.grupo_edad
                              OR destino.provincia     <> origen.provincia
                              OR destino.sucursal_id   <> origen.sucursal_id) THEN
                UPDATE SET nombre_sintetico = origen.nombre_sintetico,
                           fecha_alta       = origen.fecha_alta,
                           segmento         = origen.segmento,
                           grupo_edad       = origen.grupo_edad,
                           provincia        = origen.provincia,
                           sucursal_id      = origen.sucursal_id,
                           fecha_carga      = @ahora,
                           lote_id          = @lote_id
            WHEN NOT MATCHED BY TARGET THEN
                INSERT (cliente_id, nombre_sintetico, fecha_alta, segmento, grupo_edad, provincia,
                        sucursal_id, fecha_carga, lote_id)
                VALUES (origen.cliente_id, origen.nombre_sintetico, origen.fecha_alta, origen.segmento,
                        origen.grupo_edad, origen.provincia, origen.sucursal_id, @ahora, @lote_id)
            WHEN NOT MATCHED BY SOURCE THEN
                DELETE;
        END
        ELSE
        BEGIN
            DELETE FROM clientes.dim_sucursal;
            INSERT INTO clientes.dim_sucursal (sucursal_id, nombre_sintetico, provincia, fecha_carga, lote_id)
            SELECT sucursal_id, nombre_sintetico, provincia, @ahora, @lote_id
            FROM AB_Lakehouse.dbo.ab_silver_sucursales;

            DELETE FROM clientes.dim_cliente;
            INSERT INTO clientes.dim_cliente (cliente_id, nombre_sintetico, fecha_alta, segmento, grupo_edad,
                                              provincia, sucursal_id, fecha_carga, lote_id)
            SELECT cliente_id, nombre_sintetico, fecha_alta, segmento, grupo_edad,
                   provincia, sucursal_id, @ahora, @lote_id
            FROM AB_Lakehouse.dbo.ab_silver_clientes;
        END;

        SELECT @filas_sucursal = COUNT_BIG(*) FROM clientes.dim_sucursal;
        SELECT @filas_cliente  = COUNT_BIG(*) FROM clientes.dim_cliente;

        COMMIT TRANSACTION;

        INSERT INTO operacion.bitacora_carga
            (lote_id, procedimiento, estado, filas_tabla_1, filas_tabla_2, mensaje, usuario, fecha_utc)
        VALUES
            (@lote_id, 'clientes.usp_cargar_clientes', 'OK', @filas_sucursal, @filas_cliente,
             CONCAT('dim_sucursal + dim_cliente; estrategia ', @estrategia), SUSER_SNAME(), SYSUTCDATETIME());
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;

        SET @mensaje = CONCAT('Error ', ERROR_NUMBER(), ': ', ERROR_MESSAGE());
        INSERT INTO operacion.bitacora_carga
            (lote_id, procedimiento, estado, filas_tabla_1, filas_tabla_2, mensaje, usuario, fecha_utc)
        VALUES
            (@lote_id, 'clientes.usp_cargar_clientes', 'ERROR', NULL, NULL, @mensaje, SUSER_SNAME(), SYSUTCDATETIME());
        THROW;
    END CATCH;
END;
GO

-- ============================================================================
-- B. cuentas.usp_cargar_cuentas : dim_producto + dim_cuenta (una transacción)
-- ============================================================================
CREATE OR ALTER PROCEDURE cuentas.usp_cargar_cuentas
    @lote_id    varchar(36) = NULL,
    @estrategia varchar(15) = 'MERGE'          -- MERGE | DELETE_INSERT
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @ahora          datetime2(6) = SYSUTCDATETIME();
    DECLARE @filas_producto bigint = 0;
    DECLARE @filas_cuenta   bigint = 0;
    DECLARE @mensaje        varchar(4000);

    IF @lote_id IS NULL SET @lote_id = CONVERT(varchar(36), NEWID());
    IF @estrategia NOT IN ('MERGE', 'DELETE_INSERT')
        THROW 50001, 'usp_cargar_cuentas: @estrategia debe ser MERGE o DELETE_INSERT', 1;

    BEGIN TRY
        BEGIN TRANSACTION;

        IF @estrategia = 'MERGE'
        BEGIN
            MERGE cuentas.dim_producto AS destino
            USING (
                SELECT producto_id, nombre_sintetico, familia, moneda
                FROM AB_Lakehouse.dbo.ab_silver_productos
            ) AS origen
            ON destino.producto_id = origen.producto_id
            WHEN MATCHED AND (destino.nombre_sintetico <> origen.nombre_sintetico
                              OR destino.familia <> origen.familia
                              OR destino.moneda  <> origen.moneda) THEN
                UPDATE SET nombre_sintetico = origen.nombre_sintetico,
                           familia          = origen.familia,
                           moneda           = origen.moneda,
                           fecha_carga      = @ahora,
                           lote_id          = @lote_id
            WHEN NOT MATCHED BY TARGET THEN
                INSERT (producto_id, nombre_sintetico, familia, moneda, fecha_carga, lote_id)
                VALUES (origen.producto_id, origen.nombre_sintetico, origen.familia, origen.moneda, @ahora, @lote_id)
            WHEN NOT MATCHED BY SOURCE THEN
                DELETE;

            MERGE cuentas.dim_cuenta AS destino
            USING (
                SELECT cuenta_id, cliente_id, producto_id, fecha_apertura, moneda, saldo_inicial
                FROM AB_Lakehouse.dbo.ab_silver_cuentas
            ) AS origen
            ON destino.cuenta_id = origen.cuenta_id
            WHEN MATCHED AND (destino.cliente_id     <> origen.cliente_id
                              OR destino.producto_id    <> origen.producto_id
                              OR destino.fecha_apertura <> origen.fecha_apertura
                              OR destino.moneda         <> origen.moneda
                              OR destino.saldo_inicial  <> origen.saldo_inicial) THEN
                UPDATE SET cliente_id     = origen.cliente_id,
                           producto_id    = origen.producto_id,
                           fecha_apertura = origen.fecha_apertura,
                           moneda         = origen.moneda,
                           saldo_inicial  = origen.saldo_inicial,
                           fecha_carga    = @ahora,
                           lote_id        = @lote_id
            WHEN NOT MATCHED BY TARGET THEN
                INSERT (cuenta_id, cliente_id, producto_id, fecha_apertura, moneda, saldo_inicial, fecha_carga, lote_id)
                VALUES (origen.cuenta_id, origen.cliente_id, origen.producto_id, origen.fecha_apertura,
                        origen.moneda, origen.saldo_inicial, @ahora, @lote_id)
            WHEN NOT MATCHED BY SOURCE THEN
                DELETE;
        END
        ELSE
        BEGIN
            DELETE FROM cuentas.dim_producto;
            INSERT INTO cuentas.dim_producto (producto_id, nombre_sintetico, familia, moneda, fecha_carga, lote_id)
            SELECT producto_id, nombre_sintetico, familia, moneda, @ahora, @lote_id
            FROM AB_Lakehouse.dbo.ab_silver_productos;

            DELETE FROM cuentas.dim_cuenta;
            INSERT INTO cuentas.dim_cuenta (cuenta_id, cliente_id, producto_id, fecha_apertura, moneda,
                                            saldo_inicial, fecha_carga, lote_id)
            SELECT cuenta_id, cliente_id, producto_id, fecha_apertura, moneda, saldo_inicial, @ahora, @lote_id
            FROM AB_Lakehouse.dbo.ab_silver_cuentas;
        END;

        SELECT @filas_producto = COUNT_BIG(*) FROM cuentas.dim_producto;
        SELECT @filas_cuenta   = COUNT_BIG(*) FROM cuentas.dim_cuenta;

        COMMIT TRANSACTION;

        INSERT INTO operacion.bitacora_carga
            (lote_id, procedimiento, estado, filas_tabla_1, filas_tabla_2, mensaje, usuario, fecha_utc)
        VALUES
            (@lote_id, 'cuentas.usp_cargar_cuentas', 'OK', @filas_producto, @filas_cuenta,
             CONCAT('dim_producto + dim_cuenta; estrategia ', @estrategia), SUSER_SNAME(), SYSUTCDATETIME());
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;

        SET @mensaje = CONCAT('Error ', ERROR_NUMBER(), ': ', ERROR_MESSAGE());
        INSERT INTO operacion.bitacora_carga
            (lote_id, procedimiento, estado, filas_tabla_1, filas_tabla_2, mensaje, usuario, fecha_utc)
        VALUES
            (@lote_id, 'cuentas.usp_cargar_cuentas', 'ERROR', NULL, NULL, @mensaje, SUSER_SNAME(), SYSUTCDATETIME());
        THROW;
    END CATCH;
END;
GO

-- ============================================================================
-- C. transacciones.usp_cargar_transacciones : fact_transaccion + resumen_mes_canal
--    Reemplazo completo con DELETE + INSERT ... SELECT. @simular_error = 1 lanza un error
--    DESPUÉS de cargar el hecho y ANTES del resumen para demostrar el ROLLBACK: el hecho
--    vuelve a su estado anterior aunque ya se había insertado.
-- ============================================================================
CREATE OR ALTER PROCEDURE transacciones.usp_cargar_transacciones
    @lote_id       varchar(36) = NULL,
    @simular_error bit = 0
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @ahora          datetime2(6) = SYSUTCDATETIME();
    DECLARE @filas_hecho    bigint = 0;
    DECLARE @filas_resumen  bigint = 0;
    DECLARE @mensaje        varchar(4000);

    IF @lote_id IS NULL SET @lote_id = CONVERT(varchar(36), NEWID());

    BEGIN TRY
        BEGIN TRANSACTION;

        -- Tabla 1: hecho (las 72.000 transacciones válidas de la capa plata)
        DELETE FROM transacciones.fact_transaccion;
        INSERT INTO transacciones.fact_transaccion
            (transaccion_id, cuenta_id, fecha_hora, fecha, tipo_transaccion, direccion, canal,
             monto, moneda, estado, fecha_carga, lote_id)
        SELECT transaccion_id, cuenta_id, fecha_hora, fecha, tipo_transaccion, direccion, canal,
               monto, moneda, estado, @ahora, @lote_id
        FROM AB_Lakehouse.dbo.ab_silver_transacciones;

        IF @simular_error = 1
            THROW 51000, 'Error simulado: el hecho ya se inserto, el resumen no; el ROLLBACK debe revertir ambos', 1;

        -- Tabla 2: resumen por mes y canal, recalculado desde el hecho en la misma transacción
        DELETE FROM transacciones.resumen_mes_canal;
        INSERT INTO transacciones.resumen_mes_canal
            (mes, canal, transacciones, monto_creditos, monto_debitos, fecha_carga, lote_id)
        SELECT m.mes,
               m.canal,
               COUNT_BIG(*),
               SUM(CASE WHEN m.direccion = 'CREDITO' THEN m.monto ELSE CAST(0 AS decimal(18,2)) END),
               SUM(CASE WHEN m.direccion = 'DEBITO'  THEN m.monto ELSE CAST(0 AS decimal(18,2)) END),
               @ahora,
               @lote_id
        FROM (
            SELECT CONCAT(CAST(YEAR(f.fecha) AS varchar(4)), '-',
                          RIGHT(CONCAT('0', CAST(MONTH(f.fecha) AS varchar(2))), 2)) AS mes,
                   f.canal, f.direccion, f.monto
            FROM transacciones.fact_transaccion AS f
        ) AS m
        GROUP BY m.mes, m.canal;

        SELECT @filas_hecho   = COUNT_BIG(*) FROM transacciones.fact_transaccion;
        SELECT @filas_resumen = COUNT_BIG(*) FROM transacciones.resumen_mes_canal;

        COMMIT TRANSACTION;

        INSERT INTO operacion.bitacora_carga
            (lote_id, procedimiento, estado, filas_tabla_1, filas_tabla_2, mensaje, usuario, fecha_utc)
        VALUES
            (@lote_id, 'transacciones.usp_cargar_transacciones', 'OK', @filas_hecho, @filas_resumen,
             'fact_transaccion + resumen_mes_canal; DELETE + INSERT', SUSER_SNAME(), SYSUTCDATETIME());
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;

        SET @mensaje = CONCAT('Error ', ERROR_NUMBER(), ': ', ERROR_MESSAGE());
        INSERT INTO operacion.bitacora_carga
            (lote_id, procedimiento, estado, filas_tabla_1, filas_tabla_2, mensaje, usuario, fecha_utc)
        VALUES
            (@lote_id, 'transacciones.usp_cargar_transacciones', 'ERROR', NULL, NULL, @mensaje, SUSER_SNAME(), SYSUTCDATETIME());
        THROW;
    END CATCH;
END;
GO

-- ============================================================================
-- D. operacion.usp_reconciliar : conteos, sumas de control y contenido (EXCEPT)
--    contra el Lakehouse y contra los valores del laboratorio.
--    Guarda el resultado en operacion.reconciliacion y devuelve un conjunto de filas.
-- ============================================================================
CREATE OR ALTER PROCEDURE operacion.usp_reconciliar
    @lote_id                    varchar(36) = NULL,
    @fallar_si_difiere          bit = 0,
    @mostrar                    bit = 1,
    @incluir_contenido          bit = 1,    -- EXCEPT en ambos sentidos (más lento)
    @usar_valores_laboratorio   bit = 1     -- 72.000 / 14.976.153.627,79 / 4.530.373.831,90 / ...
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @ahora    datetime2(6) = SYSUTCDATETIME();
    DECLARE @difieren int = 0;

    IF @lote_id IS NULL SET @lote_id = CONVERT(varchar(36), NEWID());

    -- Las tablas #temp no sirven aquí: en Fabric un INSERT ... SELECT hacia o desde una #temp con datos de
    -- otras tablas falla con el error 15816 ("not supported in distributed processing mode").
    -- Los resultados se escriben directamente en operacion.reconciliacion, una fila por control y lote.
    DELETE FROM operacion.reconciliacion WHERE lote_id = @lote_id;

    -- 1) Lakehouse (esperado) frente a Warehouse (observado)
    INSERT INTO operacion.reconciliacion (lote_id, orden, control, esperado, observado, estado, fecha_utc)
    SELECT @lote_id, c.orden, c.control, c.esperado, c.observado,
           CASE WHEN c.esperado = c.observado THEN 'OK' ELSE 'DIFIERE' END, @ahora
    FROM (
        SELECT 1 AS orden, CAST('filas dim_sucursal' AS varchar(100)) AS control,
               CAST((SELECT COUNT_BIG(*) FROM AB_Lakehouse.dbo.ab_silver_sucursales) AS decimal(38,2)) AS esperado,
               CAST((SELECT COUNT_BIG(*) FROM clientes.dim_sucursal) AS decimal(38,2)) AS observado
        UNION ALL
        SELECT 2, 'filas dim_cliente',
               CAST((SELECT COUNT_BIG(*) FROM AB_Lakehouse.dbo.ab_silver_clientes) AS decimal(38,2)),
               CAST((SELECT COUNT_BIG(*) FROM clientes.dim_cliente) AS decimal(38,2))
        UNION ALL
        SELECT 3, 'filas dim_producto',
               CAST((SELECT COUNT_BIG(*) FROM AB_Lakehouse.dbo.ab_silver_productos) AS decimal(38,2)),
               CAST((SELECT COUNT_BIG(*) FROM cuentas.dim_producto) AS decimal(38,2))
        UNION ALL
        SELECT 4, 'filas dim_cuenta',
               CAST((SELECT COUNT_BIG(*) FROM AB_Lakehouse.dbo.ab_silver_cuentas) AS decimal(38,2)),
               CAST((SELECT COUNT_BIG(*) FROM cuentas.dim_cuenta) AS decimal(38,2))
        UNION ALL
        SELECT 5, 'suma saldo_inicial dim_cuenta',
               CAST((SELECT SUM(saldo_inicial) FROM AB_Lakehouse.dbo.ab_silver_cuentas) AS decimal(38,2)),
               CAST((SELECT SUM(saldo_inicial) FROM cuentas.dim_cuenta) AS decimal(38,2))
        UNION ALL
        SELECT 6, 'filas fact_transaccion',
               CAST((SELECT COUNT_BIG(*) FROM AB_Lakehouse.dbo.ab_silver_transacciones) AS decimal(38,2)),
               CAST((SELECT COUNT_BIG(*) FROM transacciones.fact_transaccion) AS decimal(38,2))
        UNION ALL
        SELECT 7, 'suma monto CREDITO fact_transaccion',
               CAST((SELECT SUM(monto) FROM AB_Lakehouse.dbo.ab_silver_transacciones WHERE direccion = 'CREDITO') AS decimal(38,2)),
               CAST((SELECT SUM(monto) FROM transacciones.fact_transaccion WHERE direccion = 'CREDITO') AS decimal(38,2))
        UNION ALL
        SELECT 8, 'suma monto DEBITO fact_transaccion',
               CAST((SELECT SUM(monto) FROM AB_Lakehouse.dbo.ab_silver_transacciones WHERE direccion = 'DEBITO') AS decimal(38,2)),
               CAST((SELECT SUM(monto) FROM transacciones.fact_transaccion WHERE direccion = 'DEBITO') AS decimal(38,2))
        UNION ALL
        SELECT 9, 'filas resumen_mes_canal',
               CAST((SELECT COUNT_BIG(*) FROM AB_Lakehouse.dbo.ab_gold_transacciones_mes_canal) AS decimal(38,2)),
               CAST((SELECT COUNT_BIG(*) FROM transacciones.resumen_mes_canal) AS decimal(38,2))
        UNION ALL
        SELECT 10, 'suma transacciones resumen_mes_canal',
               CAST((SELECT SUM(transacciones) FROM AB_Lakehouse.dbo.ab_gold_transacciones_mes_canal) AS decimal(38,2)),
               CAST((SELECT SUM(transacciones) FROM transacciones.resumen_mes_canal) AS decimal(38,2))
        UNION ALL
        SELECT 11, 'suma monto_creditos resumen_mes_canal',
               CAST((SELECT SUM(monto_creditos) FROM AB_Lakehouse.dbo.ab_gold_transacciones_mes_canal) AS decimal(38,2)),
               CAST((SELECT SUM(monto_creditos) FROM transacciones.resumen_mes_canal) AS decimal(38,2))
        UNION ALL
        SELECT 12, 'suma monto_debitos resumen_mes_canal',
               CAST((SELECT SUM(monto_debitos) FROM AB_Lakehouse.dbo.ab_gold_transacciones_mes_canal) AS decimal(38,2)),
               CAST((SELECT SUM(monto_debitos) FROM transacciones.resumen_mes_canal) AS decimal(38,2))
    ) AS c;

    -- 2) Cuadre del laboratorio: bronce - duplicadas - cuarentena = plata = hecho del Warehouse
    INSERT INTO operacion.reconciliacion (lote_id, orden, control, esperado, observado, estado, fecha_utc)
    SELECT @lote_id, c.orden, c.control, c.esperado, c.observado,
           CASE WHEN c.esperado = c.observado THEN 'OK' ELSE 'DIFIERE' END, @ahora
    FROM (
        SELECT 20 AS orden, CAST('cuadre Lakehouse: bronce - duplicadas - cuarentena = plata' AS varchar(100)) AS control,
               CAST((SELECT COUNT_BIG(*) FROM AB_Lakehouse.dbo.ab_bronze_transacciones)
                  - (SELECT COUNT_BIG(*) FROM AB_Lakehouse.dbo.ab_silver_transacciones_duplicadas)
                  - (SELECT COUNT_BIG(*) FROM AB_Lakehouse.dbo.ab_silver_transacciones_cuarentena) AS decimal(38,2)) AS esperado,
               CAST((SELECT COUNT_BIG(*) FROM AB_Lakehouse.dbo.ab_silver_transacciones) AS decimal(38,2)) AS observado
        UNION ALL
        SELECT 21, 'cuadre Warehouse: bronce - duplicadas - cuarentena = fact_transaccion',
               CAST((SELECT COUNT_BIG(*) FROM AB_Lakehouse.dbo.ab_bronze_transacciones)
                  - (SELECT COUNT_BIG(*) FROM AB_Lakehouse.dbo.ab_silver_transacciones_duplicadas)
                  - (SELECT COUNT_BIG(*) FROM AB_Lakehouse.dbo.ab_silver_transacciones_cuarentena) AS decimal(38,2)),
               CAST((SELECT COUNT_BIG(*) FROM transacciones.fact_transaccion) AS decimal(38,2))
    ) AS c;

    -- 3) Valores publicados en la guía de la Sesión 3 (dataset sintético del laboratorio)
    IF @usar_valores_laboratorio = 1
    BEGIN
        INSERT INTO operacion.reconciliacion (lote_id, orden, control, esperado, observado, estado, fecha_utc)
        SELECT @lote_id, c.orden, c.control, c.esperado, c.observado,
               CASE WHEN c.esperado = c.observado THEN 'OK' ELSE 'DIFIERE' END, @ahora
        FROM (
            SELECT 30 AS orden, CAST('laboratorio: 72.360 - 288 - 72 = 72.000 filas en fact_transaccion' AS varchar(100)) AS control,
                   CAST(72000 AS decimal(38,2)) AS esperado,
                   CAST((SELECT COUNT_BIG(*) FROM transacciones.fact_transaccion) AS decimal(38,2)) AS observado
            UNION ALL
            SELECT 31, 'laboratorio: monto CREDITO = 14.976.153.627,79',
                   CAST(14976153627.79 AS decimal(38,2)),
                   CAST((SELECT SUM(monto) FROM transacciones.fact_transaccion WHERE direccion = 'CREDITO') AS decimal(38,2))
            UNION ALL
            SELECT 32, 'laboratorio: monto DEBITO = 4.530.373.831,90',
                   CAST(4530373831.90 AS decimal(38,2)),
                   CAST((SELECT SUM(monto) FROM transacciones.fact_transaccion WHERE direccion = 'DEBITO') AS decimal(38,2))
            UNION ALL
            SELECT 33, 'laboratorio: suma saldo_inicial = 2.306.760.167,48',
                   CAST(2306760167.48 AS decimal(38,2)),
                   CAST((SELECT SUM(saldo_inicial) FROM cuentas.dim_cuenta) AS decimal(38,2))
            UNION ALL
            SELECT 34, 'laboratorio: 30 filas en resumen_mes_canal (6 meses x 5 canales)',
                   CAST(30 AS decimal(38,2)),
                   CAST((SELECT COUNT_BIG(*) FROM transacciones.resumen_mes_canal) AS decimal(38,2))
        ) AS c;
    END;

    -- 4) Integridad que el motor no valida (las llaves son NOT ENFORCED)
    INSERT INTO operacion.reconciliacion (lote_id, orden, control, esperado, observado, estado, fecha_utc)
    SELECT @lote_id, c.orden, c.control, c.esperado, c.observado,
           CASE WHEN c.esperado = c.observado THEN 'OK' ELSE 'DIFIERE' END, @ahora
    FROM (
        SELECT 50 AS orden, CAST('integridad: transaccion_id repetidos en fact_transaccion' AS varchar(100)) AS control,
               CAST(0 AS decimal(38,2)) AS esperado,
               CAST((SELECT COUNT_BIG(*) - COUNT_BIG(DISTINCT transaccion_id) FROM transacciones.fact_transaccion) AS decimal(38,2)) AS observado
        UNION ALL
        SELECT 51, 'integridad: transacciones con cuenta inexistente en dim_cuenta',
               CAST(0 AS decimal(38,2)),
               CAST((SELECT COUNT_BIG(*) FROM transacciones.fact_transaccion AS f
                     WHERE NOT EXISTS (SELECT 1 FROM cuentas.dim_cuenta AS c WHERE c.cuenta_id = f.cuenta_id)) AS decimal(38,2))
        UNION ALL
        SELECT 52, 'integridad: cuentas con cliente inexistente en dim_cliente',
               CAST(0 AS decimal(38,2)),
               CAST((SELECT COUNT_BIG(*) FROM cuentas.dim_cuenta AS a
                     WHERE NOT EXISTS (SELECT 1 FROM clientes.dim_cliente AS c WHERE c.cliente_id = a.cliente_id)) AS decimal(38,2))
    ) AS c;

    -- 5) Contenido: diferencias de conjunto en ambos sentidos (0 = idéntico)
    IF @incluir_contenido = 1
    BEGIN
        INSERT INTO operacion.reconciliacion (lote_id, orden, control, esperado, observado, estado, fecha_utc)
        SELECT @lote_id, c.orden, c.control, c.esperado, c.observado,
               CASE WHEN c.esperado = c.observado THEN 'OK' ELSE 'DIFIERE' END, @ahora
        FROM (
            SELECT 60 AS orden, CAST('contenido fact: filas del Lakehouse que faltan en el Warehouse' AS varchar(100)) AS control,
                   CAST(0 AS decimal(38,2)) AS esperado,
                   CAST((SELECT COUNT_BIG(*) FROM (
                            SELECT transaccion_id, cuenta_id, fecha_hora, fecha, tipo_transaccion, direccion, canal, monto, moneda, estado
                            FROM AB_Lakehouse.dbo.ab_silver_transacciones
                            EXCEPT
                            SELECT transaccion_id, cuenta_id, fecha_hora, fecha, tipo_transaccion, direccion, canal, monto, moneda, estado
                            FROM transacciones.fact_transaccion) AS d) AS decimal(38,2)) AS observado
            UNION ALL
            SELECT 61, 'contenido fact: filas del Warehouse que no estan en el Lakehouse',
                   CAST(0 AS decimal(38,2)),
                   CAST((SELECT COUNT_BIG(*) FROM (
                            SELECT transaccion_id, cuenta_id, fecha_hora, fecha, tipo_transaccion, direccion, canal, monto, moneda, estado
                            FROM transacciones.fact_transaccion
                            EXCEPT
                            SELECT transaccion_id, cuenta_id, fecha_hora, fecha, tipo_transaccion, direccion, canal, monto, moneda, estado
                            FROM AB_Lakehouse.dbo.ab_silver_transacciones) AS d) AS decimal(38,2))
            UNION ALL
            SELECT 62, 'contenido resumen: filas del Lakehouse que faltan en el Warehouse',
                   CAST(0 AS decimal(38,2)),
                   CAST((SELECT COUNT_BIG(*) FROM (
                            SELECT mes, canal, transacciones, monto_creditos, monto_debitos
                            FROM AB_Lakehouse.dbo.ab_gold_transacciones_mes_canal
                            EXCEPT
                            SELECT mes, canal, transacciones, monto_creditos, monto_debitos
                            FROM transacciones.resumen_mes_canal) AS d) AS decimal(38,2))
            UNION ALL
            SELECT 63, 'contenido resumen: filas del Warehouse que no estan en el Lakehouse',
                   CAST(0 AS decimal(38,2)),
                   CAST((SELECT COUNT_BIG(*) FROM (
                            SELECT mes, canal, transacciones, monto_creditos, monto_debitos
                            FROM transacciones.resumen_mes_canal
                            EXCEPT
                            SELECT mes, canal, transacciones, monto_creditos, monto_debitos
                            FROM AB_Lakehouse.dbo.ab_gold_transacciones_mes_canal) AS d) AS decimal(38,2))
        ) AS c;
    END;

    SELECT @difieren = COUNT(*) FROM operacion.reconciliacion WHERE lote_id = @lote_id AND estado <> 'OK';

    IF @mostrar = 1
        SELECT orden, control, esperado, observado, estado
        FROM operacion.reconciliacion
        WHERE lote_id = @lote_id
        ORDER BY orden;

    IF @difieren > 0 AND @fallar_si_difiere = 1
        THROW 51001, 'Reconciliacion con diferencias: revise operacion.reconciliacion para el lote', 1;
END;
GO

-- ============================================================================
-- E. operacion.usp_cargar_gold : orquestador (lo invoca el pipeline)
--    No abre una transacción propia: cada procedimiento hijo es atómico sobre sus dos
--    tablas y Fabric no admite transacciones anidadas. Si falla un paso, los pasos
--    anteriores ya confirmados se conservan y la bitácora indica en cuál falló; al ser
--    idempotente basta con volver a ejecutarlo.
-- ============================================================================
CREATE OR ALTER PROCEDURE operacion.usp_cargar_gold
    @estrategia_dimensiones varchar(15) = 'MERGE',   -- MERGE | DELETE_INSERT
    @simular_error          bit = 0,                 -- 1 = falla a mitad de la carga de transacciones
    @lote_id                varchar(36) = NULL
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @paso    varchar(60) = 'inicio';
    DECLARE @mensaje varchar(4000);

    IF @lote_id IS NULL SET @lote_id = CONVERT(varchar(36), NEWID());

    BEGIN TRY
        INSERT INTO operacion.bitacora_carga
            (lote_id, procedimiento, estado, filas_tabla_1, filas_tabla_2, mensaje, usuario, fecha_utc)
        VALUES
            (@lote_id, 'operacion.usp_cargar_gold', 'INICIO', NULL, NULL,
             CONCAT('estrategia dimensiones ', @estrategia_dimensiones, '; simular_error ', @simular_error),
             SUSER_SNAME(), SYSUTCDATETIME());

        SET @paso = 'clientes.usp_cargar_clientes';
        EXEC clientes.usp_cargar_clientes @lote_id = @lote_id, @estrategia = @estrategia_dimensiones;

        SET @paso = 'cuentas.usp_cargar_cuentas';
        EXEC cuentas.usp_cargar_cuentas @lote_id = @lote_id, @estrategia = @estrategia_dimensiones;

        SET @paso = 'transacciones.usp_cargar_transacciones';
        EXEC transacciones.usp_cargar_transacciones @lote_id = @lote_id, @simular_error = @simular_error;

        SET @paso = 'operacion.usp_reconciliar';
        EXEC operacion.usp_reconciliar @lote_id = @lote_id, @fallar_si_difiere = 1, @mostrar = 0;

        INSERT INTO operacion.bitacora_carga
            (lote_id, procedimiento, estado, filas_tabla_1, filas_tabla_2, mensaje, usuario, fecha_utc)
        VALUES
            (@lote_id, 'operacion.usp_cargar_gold', 'OK', NULL, NULL,
             'carga y reconciliacion correctas', SUSER_SNAME(), SYSUTCDATETIME());
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;

        SET @mensaje = CONCAT('Fallo en el paso ', @paso, ': error ', ERROR_NUMBER(), ' - ', ERROR_MESSAGE());
        INSERT INTO operacion.bitacora_carga
            (lote_id, procedimiento, estado, filas_tabla_1, filas_tabla_2, mensaje, usuario, fecha_utc)
        VALUES
            (@lote_id, 'operacion.usp_cargar_gold', 'ERROR', NULL, NULL, @mensaje, SUSER_SNAME(), SYSUTCDATETIME());
        THROW;
    END CATCH;
END;
GO
