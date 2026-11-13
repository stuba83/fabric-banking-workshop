/* ============================================================================
   FAC_WH_Gold  -  03_pruebas.sql
   Pruebas del demo A. Cada lote (separado por GO) devuelve filas con las columnas
       prueba | estado (OK / FALLA) | detalle
   y el script completo es seguro de repetir. Orden: objetos -> lectura entre bases ->
   rollback -> carga -> reconciliación -> cuadre del laboratorio -> idempotencia ->
   estrategias -> deriva -> diferencia inducida -> restauración -> rollback con datos ->
   llaves NOT ENFORCED -> hash.

   Prerrequisitos: 01 y 02 ejecutados en FAC_WH_Gold y las tablas AB_* de la Sesión 3
   existentes y visibles en el SQL analytics endpoint de AB_Lakehouse.
   Los valores esperados (72.000 filas, 30 filas, 14.976.153.627,79 de créditos,
   4.530.373.831,90 de débitos) salen de la guía de la Sesión 3 y se recalcularon con la
   implementación de referencia del repo (valores_esperados.json).
   ============================================================================ */

-- T00. Objetos creados ---------------------------------------------------------
SELECT 'T00 esquemas, tablas y procedimientos creados' AS prueba,
       CASE WHEN e.esquemas = 4 AND tb.tablas = 8 AND pr.procedimientos = 5 THEN 'OK' ELSE 'FALLA' END AS estado,
       CONCAT('esquemas=', e.esquemas, ' (4); tablas=', tb.tablas, ' (8); procedimientos=', pr.procedimientos, ' (5)') AS detalle
FROM (SELECT COUNT(*) AS esquemas FROM sys.schemas
      WHERE name IN ('clientes', 'cuentas', 'transacciones', 'operacion')) AS e
CROSS JOIN (SELECT COUNT(*) AS tablas FROM sys.tables AS t
            JOIN sys.schemas AS s ON s.schema_id = t.schema_id
            WHERE s.name IN ('clientes', 'cuentas', 'transacciones', 'operacion')) AS tb
CROSS JOIN (SELECT COUNT(*) AS procedimientos FROM sys.procedures AS p
            JOIN sys.schemas AS s ON s.schema_id = p.schema_id
            WHERE s.name IN ('clientes', 'cuentas', 'transacciones', 'operacion')
              AND p.name LIKE 'usp%') AS pr;
GO

-- T01. Lectura entre bases con nombre de tres partes ---------------------------
SELECT 'T01 el Warehouse lee AB_Lakehouse.dbo.ab_silver_transacciones' AS prueba,
       CASE WHEN x.filas = 72000 THEN 'OK' ELSE 'FALLA' END AS estado,
       CONCAT('filas leidas=', x.filas, ' (72000)') AS detalle
FROM (SELECT COUNT_BIG(*) AS filas FROM AB_Lakehouse.dbo.ab_silver_transacciones) AS x;
GO

-- T02. ROLLBACK atómico: el error simulado ocurre con el hecho ya insertado -----
DECLARE @hecho_antes     bigint = (SELECT COUNT_BIG(*) FROM transacciones.fact_transaccion);
DECLARE @resumen_antes   bigint = (SELECT COUNT_BIG(*) FROM transacciones.resumen_mes_canal);
DECLARE @error_numero    int = 0;

BEGIN TRY
    EXEC transacciones.usp_cargar_transacciones @simular_error = 1;
END TRY
BEGIN CATCH
    SET @error_numero = ERROR_NUMBER();
END CATCH;

DECLARE @hecho_despues   bigint = (SELECT COUNT_BIG(*) FROM transacciones.fact_transaccion);
DECLARE @resumen_despues bigint = (SELECT COUNT_BIG(*) FROM transacciones.resumen_mes_canal);

SELECT 'T02 ROLLBACK atomico con error simulado' AS prueba,
       CASE WHEN @error_numero = 51000 AND @hecho_despues = @hecho_antes AND @resumen_despues = @resumen_antes
            THEN 'OK' ELSE 'FALLA' END AS estado,
       CONCAT('error=', @error_numero, ' (51000); hecho ', @hecho_antes, '->', @hecho_despues,
              '; resumen ', @resumen_antes, '->', @resumen_despues) AS detalle;
GO

-- T03. Carga completa con el orquestador ---------------------------------------
DECLARE @error varchar(4000) = NULL;

BEGIN TRY
    EXEC operacion.usp_cargar_gold;
END TRY
BEGIN CATCH
    SET @error = CONCAT(ERROR_NUMBER(), ': ', ERROR_MESSAGE());
END CATCH;

SELECT 'T03 carga completa (operacion.usp_cargar_gold)' AS prueba,
       CASE WHEN @error IS NULL
             AND (SELECT COUNT_BIG(*) FROM transacciones.fact_transaccion) = 72000
             AND (SELECT COUNT_BIG(*) FROM transacciones.resumen_mes_canal) = 30
            THEN 'OK' ELSE 'FALLA' END AS estado,
       CONCAT('error=', ISNULL(@error, 'ninguno'),
              '; hecho=', (SELECT COUNT_BIG(*) FROM transacciones.fact_transaccion), ' (72000)',
              '; resumen=', (SELECT COUNT_BIG(*) FROM transacciones.resumen_mes_canal), ' (30)') AS detalle;
GO

-- T04. Reconciliación del último lote (resumen y detalle) -----------------------
SELECT 'T04 reconciliacion del ultimo lote sin diferencias' AS prueba,
       CASE WHEN COUNT(*) > 0 AND SUM(CASE WHEN r.estado <> 'OK' THEN 1 ELSE 0 END) = 0 THEN 'OK' ELSE 'FALLA' END AS estado,
       CONCAT('controles=', COUNT(*), '; difieren=', SUM(CASE WHEN r.estado <> 'OK' THEN 1 ELSE 0 END)) AS detalle
FROM operacion.reconciliacion AS r
WHERE r.lote_id = (SELECT TOP 1 b.lote_id FROM operacion.bitacora_carga AS b
                   WHERE b.procedimiento = 'operacion.usp_cargar_gold' AND b.estado = 'OK'
                   ORDER BY b.fecha_utc DESC);
GO

SELECT CONCAT('T04.', r.orden, ' ', r.control) AS prueba,
       r.estado AS estado,
       CONCAT('esperado=', r.esperado, '; observado=', r.observado) AS detalle
FROM operacion.reconciliacion AS r
WHERE r.lote_id = (SELECT TOP 1 b.lote_id FROM operacion.bitacora_carga AS b
                   WHERE b.procedimiento = 'operacion.usp_cargar_gold' AND b.estado = 'OK'
                   ORDER BY b.fecha_utc DESC)
ORDER BY r.orden;
GO

-- T05. Cuadre del laboratorio: 72.360 - 288 - 72 = 72.000 ------------------------
SELECT 'T05 cuadre del laboratorio 72360 - 288 - 72 = 72000' AS prueba,
       CASE WHEN x.bronce = 72360 AND x.duplicadas = 288 AND x.cuarentena = 72
             AND x.bronce - x.duplicadas - x.cuarentena = 72000
             AND x.plata = 72000 AND x.hecho = 72000
            THEN 'OK' ELSE 'FALLA' END AS estado,
       CONCAT('bronce=', x.bronce, '; duplicadas=', x.duplicadas, '; cuarentena=', x.cuarentena,
              '; plata=', x.plata, '; fact_transaccion=', x.hecho) AS detalle
FROM (SELECT
        (SELECT COUNT_BIG(*) FROM AB_Lakehouse.dbo.ab_bronze_transacciones) AS bronce,
        (SELECT COUNT_BIG(*) FROM AB_Lakehouse.dbo.ab_silver_transacciones_duplicadas) AS duplicadas,
        (SELECT COUNT_BIG(*) FROM AB_Lakehouse.dbo.ab_silver_transacciones_cuarentena) AS cuarentena,
        (SELECT COUNT_BIG(*) FROM AB_Lakehouse.dbo.ab_silver_transacciones) AS plata,
        (SELECT COUNT_BIG(*) FROM transacciones.fact_transaccion) AS hecho) AS x;
GO

-- T06. Idempotencia: una segunda carga deja exactamente el mismo resultado ------
DECLARE @hecho_antes     bigint = (SELECT COUNT_BIG(*) FROM transacciones.fact_transaccion);
DECLARE @resumen_antes   bigint = (SELECT COUNT_BIG(*) FROM transacciones.resumen_mes_canal);
DECLARE @dims_antes      bigint = (SELECT COUNT_BIG(*) FROM clientes.dim_sucursal)
                                + (SELECT COUNT_BIG(*) FROM clientes.dim_cliente)
                                + (SELECT COUNT_BIG(*) FROM cuentas.dim_producto)
                                + (SELECT COUNT_BIG(*) FROM cuentas.dim_cuenta);
DECLARE @creditos_antes  decimal(38,2) = (SELECT SUM(monto) FROM transacciones.fact_transaccion WHERE direccion = 'CREDITO');
DECLARE @error           varchar(4000) = NULL;

BEGIN TRY
    EXEC operacion.usp_cargar_gold;
END TRY
BEGIN CATCH
    SET @error = CONCAT(ERROR_NUMBER(), ': ', ERROR_MESSAGE());
END CATCH;

DECLARE @dims_despues bigint = (SELECT COUNT_BIG(*) FROM clientes.dim_sucursal)
                             + (SELECT COUNT_BIG(*) FROM clientes.dim_cliente)
                             + (SELECT COUNT_BIG(*) FROM cuentas.dim_producto)
                             + (SELECT COUNT_BIG(*) FROM cuentas.dim_cuenta);

SELECT 'T06 idempotencia: la segunda carga no duplica ni pierde filas' AS prueba,
       CASE WHEN @error IS NULL
             AND (SELECT COUNT_BIG(*) FROM transacciones.fact_transaccion) = @hecho_antes
             AND (SELECT COUNT_BIG(*) FROM transacciones.resumen_mes_canal) = @resumen_antes
             AND @dims_despues = @dims_antes
             AND (SELECT SUM(monto) FROM transacciones.fact_transaccion WHERE direccion = 'CREDITO') = @creditos_antes
             AND (SELECT COUNT(DISTINCT lote_id) FROM transacciones.fact_transaccion) = 1
            THEN 'OK' ELSE 'FALLA' END AS estado,
       CONCAT('error=', ISNULL(@error, 'ninguno'),
              '; hecho ', @hecho_antes, '->', (SELECT COUNT_BIG(*) FROM transacciones.fact_transaccion),
              '; resumen ', @resumen_antes, '->', (SELECT COUNT_BIG(*) FROM transacciones.resumen_mes_canal),
              '; dimensiones ', @dims_antes, '->', @dims_despues,
              '; lotes distintos en el hecho=', (SELECT COUNT(DISTINCT lote_id) FROM transacciones.fact_transaccion)) AS detalle;
GO

-- T07. La estrategia DELETE_INSERT produce el mismo resultado que MERGE ---------
DECLARE @error varchar(4000) = NULL;

BEGIN TRY
    EXEC clientes.usp_cargar_clientes @estrategia = 'DELETE_INSERT';
    EXEC cuentas.usp_cargar_cuentas   @estrategia = 'DELETE_INSERT';
    EXEC operacion.usp_reconciliar @mostrar = 0, @fallar_si_difiere = 1, @incluir_contenido = 0;
END TRY
BEGIN CATCH
    SET @error = CONCAT(ERROR_NUMBER(), ': ', ERROR_MESSAGE());
END CATCH;

SELECT 'T07 estrategia DELETE_INSERT equivalente a MERGE' AS prueba,
       CASE WHEN @error IS NULL
             AND (SELECT COUNT_BIG(*) FROM clientes.dim_sucursal) = 7
             AND (SELECT COUNT_BIG(*) FROM clientes.dim_cliente) = 1200
             AND (SELECT COUNT_BIG(*) FROM cuentas.dim_producto) = 5
             AND (SELECT COUNT_BIG(*) FROM cuentas.dim_cuenta) = 1800
            THEN 'OK' ELSE 'FALLA' END AS estado,
       CONCAT('error=', ISNULL(@error, 'ninguno'), '; filas dimensiones 7/1200/5/1800') AS detalle;
GO

-- T08. MERGE corrige la deriva: valor cambiado, fila borrada y fila sobrante ----
UPDATE clientes.dim_sucursal SET provincia = 'Deriva' WHERE sucursal_id = 'SUC01';
DELETE FROM clientes.dim_sucursal WHERE sucursal_id = 'SUC02';
INSERT INTO clientes.dim_sucursal (sucursal_id, nombre_sintetico, provincia, fecha_carga, lote_id)
VALUES ('SUC99', 'Sucursal sobrante', 'Deriva', SYSUTCDATETIME(), 'prueba_deriva');
GO

DECLARE @error varchar(4000) = NULL;

BEGIN TRY
    EXEC clientes.usp_cargar_clientes @estrategia = 'MERGE';
END TRY
BEGIN CATCH
    SET @error = CONCAT(ERROR_NUMBER(), ': ', ERROR_MESSAGE());
END CATCH;

SELECT 'T08 MERGE restaura valores, repone filas y elimina sobrantes' AS prueba,
       CASE WHEN @error IS NULL
             AND (SELECT COUNT_BIG(*) FROM clientes.dim_sucursal) = 7
             AND (SELECT COUNT_BIG(*) FROM clientes.dim_sucursal WHERE sucursal_id = 'SUC99') = 0
             AND (SELECT COUNT_BIG(*) FROM clientes.dim_sucursal WHERE sucursal_id = 'SUC02') = 1
             AND (SELECT provincia FROM clientes.dim_sucursal WHERE sucursal_id = 'SUC01')
               = (SELECT provincia FROM AB_Lakehouse.dbo.ab_silver_sucursales WHERE sucursal_id = 'SUC01')
            THEN 'OK' ELSE 'FALLA' END AS estado,
       CONCAT('error=', ISNULL(@error, 'ninguno'),
              '; filas=', (SELECT COUNT_BIG(*) FROM clientes.dim_sucursal), ' (7)') AS detalle;
GO

-- T09. La reconciliación detecta una diferencia inducida en el hecho ------------
UPDATE transacciones.fact_transaccion
SET monto = monto + 1
WHERE transaccion_id = (SELECT MIN(transaccion_id) FROM transacciones.fact_transaccion);
GO

DECLARE @error_numero int = 0;

BEGIN TRY
    EXEC operacion.usp_reconciliar @mostrar = 0, @fallar_si_difiere = 1;
END TRY
BEGIN CATCH
    SET @error_numero = ERROR_NUMBER();
END CATCH;

SELECT 'T09 la reconciliacion detecta una diferencia inducida' AS prueba,
       CASE WHEN @error_numero = 51001 THEN 'OK' ELSE 'FALLA' END AS estado,
       CONCAT('error=', @error_numero, ' (51001)') AS detalle;
GO

-- T10. Restauración: recargar el hecho y volver a reconciliar -------------------
DECLARE @error varchar(4000) = NULL;

BEGIN TRY
    EXEC transacciones.usp_cargar_transacciones;
    EXEC operacion.usp_reconciliar @mostrar = 0, @fallar_si_difiere = 1;
END TRY
BEGIN CATCH
    SET @error = CONCAT(ERROR_NUMBER(), ': ', ERROR_MESSAGE());
END CATCH;

SELECT 'T10 recarga del hecho y reconciliacion sin diferencias' AS prueba,
       CASE WHEN @error IS NULL THEN 'OK' ELSE 'FALLA' END AS estado,
       CONCAT('error=', ISNULL(@error, 'ninguno')) AS detalle;
GO

-- T11. ROLLBACK con datos ya cargados: nada cambia, ni el lote del hecho --------
DECLARE @hecho_antes   bigint = (SELECT COUNT_BIG(*) FROM transacciones.fact_transaccion);
DECLARE @resumen_antes bigint = (SELECT COUNT_BIG(*) FROM transacciones.resumen_mes_canal);
DECLARE @lote_antes    varchar(36) = (SELECT MAX(lote_id) FROM transacciones.fact_transaccion);
DECLARE @error_numero  int = 0;

BEGIN TRY
    EXEC transacciones.usp_cargar_transacciones @simular_error = 1;
END TRY
BEGIN CATCH
    SET @error_numero = ERROR_NUMBER();
END CATCH;

SELECT 'T11 ROLLBACK conserva el estado anterior (cantidad y lote)' AS prueba,
       CASE WHEN @error_numero = 51000
             AND (SELECT COUNT_BIG(*) FROM transacciones.fact_transaccion) = @hecho_antes
             AND (SELECT COUNT_BIG(*) FROM transacciones.resumen_mes_canal) = @resumen_antes
             AND (SELECT MAX(lote_id) FROM transacciones.fact_transaccion) = @lote_antes
            THEN 'OK' ELSE 'FALLA' END AS estado,
       CONCAT('error=', @error_numero, '; hecho=', @hecho_antes, '; resumen=', @resumen_antes) AS detalle;
GO

-- T12. Las llaves NOT ENFORCED no impiden duplicados (la prueba se revierte) -----
DECLARE @filas_con_duplicado bigint = -1;

BEGIN TRY
    BEGIN TRANSACTION;
    INSERT INTO clientes.dim_sucursal (sucursal_id, nombre_sintetico, provincia, fecha_carga, lote_id)
    SELECT TOP 1 sucursal_id, nombre_sintetico, provincia, fecha_carga, lote_id
    FROM clientes.dim_sucursal
    ORDER BY sucursal_id;
    SET @filas_con_duplicado = (SELECT COUNT_BIG(*) FROM clientes.dim_sucursal);
    ROLLBACK TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
END CATCH;

SELECT 'T12 PRIMARY KEY NOT ENFORCED acepta un duplicado (se revierte)' AS prueba,
       CASE WHEN @filas_con_duplicado = 8 AND (SELECT COUNT_BIG(*) FROM clientes.dim_sucursal) = 7
            THEN 'OK' ELSE 'FALLA' END AS estado,
       CONCAT('filas dentro de la transaccion=', @filas_con_duplicado, ' (8); despues del ROLLBACK=',
              (SELECT COUNT_BIG(*) FROM clientes.dim_sucursal), ' (7)') AS detalle;
GO

-- T13. (Opcional) el SHA-256 de T-SQL coincide con hash_fila de la biblioteca ---
-- Columnas y orden: transaccion_id | cuenta_id | direccion | canal | monto. Los valores
-- esperados los calculó hash_fila_python con la implementación de referencia.
SELECT 'T13 HASHBYTES SHA2_256 igual a hash_fila (Spark/Python)' AS prueba,
       CASE WHEN COUNT(*) = 3 AND SUM(CASE WHEN h.hash_tsql = m.esperado THEN 1 ELSE 0 END) = 3
            THEN 'OK' ELSE 'FALLA' END AS estado,
       CONCAT('coinciden ', SUM(CASE WHEN h.hash_tsql = m.esperado THEN 1 ELSE 0 END), ' de ', COUNT(*)) AS detalle
FROM (
    SELECT transaccion_id,
           LOWER(CONVERT(varchar(64),
                 HASHBYTES('SHA2_256', CONCAT_WS('|', transaccion_id, cuenta_id, direccion, canal, CAST(monto AS varchar(30)))),
                 2)) AS hash_tsql
    FROM transacciones.fact_transaccion
    WHERE transaccion_id IN ('TX00000001', 'TX00000002', 'TX00000003')
) AS h
JOIN (
    SELECT 'TX00000001' AS transaccion_id, '4d01750fa7d9891609de2ddfaca0af9f435d9037944b6d3d49948a8cbea76a50' AS esperado
    UNION ALL
    SELECT 'TX00000002', '967eb9eeb586c00246cccfccdd521ce6f72750fa24275b6850caf7ad9697ff99'
    UNION ALL
    SELECT 'TX00000003', 'bcec1f1f890d7e1d57e575cdf6fa6a5902f8c7d2061ff70e0e5fef85e0aff819'
) AS m
  ON m.transaccion_id = h.transaccion_id;
GO
