/* ============================================================================
   comparacion_tsql.sql  -  Demo C: la misma agregación de negocio en T-SQL
   (la versión Spark SQL está en FAC_NB_Spark_vs_TSQL.ipynb)

   Pregunta de negocio: por mes, provincia (de la sucursal) y canal, ¿cuántas transacciones,
   cuánto crédito, cuánto débito y cuál es el ticket promedio? Une 4 tablas:
   transacciones -> cuentas -> clientes -> sucursales.

   Se ejecuta conectado a FAC_WH_Gold después de 01, 02 y la carga (operacion.usp_cargar_gold).
   Tres formas de ejecutar la MISMA consulta:
     1) Sobre las tablas del Warehouse (modelo estrella cargado por los procedimientos).
     2) Sobre las tablas plata del Lakehouse, leídas con nombre de tres partes desde el
        Warehouse (el motor de consulta es el mismo, el origen cambia).
     3) Spark SQL en el notebook (otro motor).

   Medición: el lote 3 repite la consulta y mide con SYSUTCDATETIME(). No se asume ni se
   promete ningún resultado de tiempo: la primera repetición suele diferir de las
   siguientes (caché y metadatos) y la medición incluye escribir 210 filas en una tabla
   temporal. El tiempo del servidor está en queryinsights (lote 5; puede tardar hasta
   15 minutos en aparecer según Learn).
   ============================================================================ */

-- 1) Consulta sobre el Warehouse ---------------------------------------------------
SELECT m.mes, s.provincia, m.canal,
       COUNT_BIG(*) AS transacciones,
       SUM(CASE WHEN m.direccion = 'CREDITO' THEN m.monto ELSE CAST(0 AS decimal(18,2)) END) AS monto_creditos,
       SUM(CASE WHEN m.direccion = 'DEBITO'  THEN m.monto ELSE CAST(0 AS decimal(18,2)) END) AS monto_debitos,
       CAST(AVG(m.monto) AS decimal(18,2)) AS ticket_promedio
FROM (SELECT CONCAT(CAST(YEAR(t.fecha) AS varchar(4)), '-', RIGHT(CONCAT('0', CAST(MONTH(t.fecha) AS varchar(2))), 2)) AS mes,
             t.cuenta_id, t.canal, t.direccion, t.monto
      FROM transacciones.fact_transaccion AS t) AS m
JOIN cuentas.dim_cuenta    AS c  ON c.cuenta_id    = m.cuenta_id
JOIN clientes.dim_cliente  AS cl ON cl.cliente_id  = c.cliente_id
JOIN clientes.dim_sucursal AS s  ON s.sucursal_id  = cl.sucursal_id
GROUP BY m.mes, s.provincia, m.canal
ORDER BY m.mes, s.provincia, m.canal
OPTION (LABEL = 'FAC_CMP_WH_manual');
GO

-- 2) La misma consulta sobre las tablas plata del Lakehouse (tres partes) -----------
SELECT m.mes, s.provincia, m.canal,
       COUNT_BIG(*) AS transacciones,
       SUM(CASE WHEN m.direccion = 'CREDITO' THEN m.monto ELSE CAST(0 AS decimal(18,2)) END) AS monto_creditos,
       SUM(CASE WHEN m.direccion = 'DEBITO'  THEN m.monto ELSE CAST(0 AS decimal(18,2)) END) AS monto_debitos,
       CAST(AVG(m.monto) AS decimal(18,2)) AS ticket_promedio
FROM (SELECT CONCAT(CAST(YEAR(t.fecha) AS varchar(4)), '-', RIGHT(CONCAT('0', CAST(MONTH(t.fecha) AS varchar(2))), 2)) AS mes,
             t.cuenta_id, t.canal, t.direccion, t.monto
      FROM AB_Lakehouse.dbo.ab_silver_transacciones AS t) AS m
JOIN AB_Lakehouse.dbo.ab_silver_cuentas    AS c  ON c.cuenta_id    = m.cuenta_id
JOIN AB_Lakehouse.dbo.ab_silver_clientes   AS cl ON cl.cliente_id  = c.cliente_id
JOIN AB_Lakehouse.dbo.ab_silver_sucursales AS s  ON s.sucursal_id  = cl.sucursal_id
GROUP BY m.mes, s.provincia, m.canal
ORDER BY m.mes, s.provincia, m.canal
OPTION (LABEL = 'FAC_CMP_EP_manual');
GO

-- 3) Medición: repite cada variante N veces ---------------------------------------------------
-- Las tablas #temp NO sirven para guardar el resultado: en Fabric un INSERT ... SELECT hacia una #temp con
-- datos de otras tablas falla con el error 15816 ("not supported in distributed processing mode").
-- Por eso la consulta se ejecuta completa dentro de un SELECT que agrega sus columnas a variables
-- (no se transfiere el resultado al cliente: se mide el cómputo) y solo los tiempos van a una #temp con VALUES.
DECLARE @repeticiones int = 3;
DECLARE @i            int = 1;
DECLARE @t0           datetime2(6);
DECLARE @ms           int;
DECLARE @grupos       bigint;
DECLARE @tx           bigint;
DECLARE @cre          decimal(38,2);
DECLARE @deb          decimal(38,2);
DECLARE @tkt          decimal(38,2);
DECLARE @wh_grupos bigint, @wh_tx bigint, @wh_cre decimal(38,2), @wh_deb decimal(38,2);
DECLARE @ep_grupos bigint, @ep_tx bigint, @ep_cre decimal(38,2), @ep_deb decimal(38,2);

DROP TABLE IF EXISTS #tiempos;
CREATE TABLE #tiempos (
    repeticion   int           NOT NULL,
    variante     varchar(60)   NOT NULL,
    milisegundos int           NOT NULL
);

WHILE @i <= @repeticiones
BEGIN
    SET @t0 = SYSUTCDATETIME();
    SELECT @grupos = COUNT_BIG(*), @tx = SUM(q.transacciones), @cre = SUM(q.monto_creditos),
           @deb = SUM(q.monto_debitos), @tkt = SUM(q.ticket_promedio)
    FROM (
        SELECT m.mes, s.provincia, m.canal,
               COUNT_BIG(*) AS transacciones,
               SUM(CASE WHEN m.direccion = 'CREDITO' THEN m.monto ELSE CAST(0 AS decimal(18,2)) END) AS monto_creditos,
               SUM(CASE WHEN m.direccion = 'DEBITO'  THEN m.monto ELSE CAST(0 AS decimal(18,2)) END) AS monto_debitos,
               CAST(AVG(m.monto) AS decimal(18,2)) AS ticket_promedio
        FROM (SELECT CONCAT(CAST(YEAR(t.fecha) AS varchar(4)), '-', RIGHT(CONCAT('0', CAST(MONTH(t.fecha) AS varchar(2))), 2)) AS mes,
                     t.cuenta_id, t.canal, t.direccion, t.monto
              FROM transacciones.fact_transaccion AS t) AS m
        JOIN cuentas.dim_cuenta AS c  ON c.cuenta_id   = m.cuenta_id
        JOIN clientes.dim_cliente AS cl ON cl.cliente_id = c.cliente_id
        JOIN clientes.dim_sucursal AS s  ON s.sucursal_id = cl.sucursal_id
        GROUP BY m.mes, s.provincia, m.canal
    ) AS q
    OPTION (LABEL = 'FAC_CMP_WH_medicion');
    SET @ms = DATEDIFF(MILLISECOND, @t0, SYSUTCDATETIME());
    INSERT INTO #tiempos (repeticion, variante, milisegundos) VALUES (@i, 'T-SQL Warehouse (FAC_WH_Gold)', @ms);
    SET @wh_grupos = @grupos; SET @wh_tx = @tx; SET @wh_cre = @cre; SET @wh_deb = @deb;

    SET @t0 = SYSUTCDATETIME();
    SELECT @grupos = COUNT_BIG(*), @tx = SUM(q.transacciones), @cre = SUM(q.monto_creditos),
           @deb = SUM(q.monto_debitos), @tkt = SUM(q.ticket_promedio)
    FROM (
        SELECT m.mes, s.provincia, m.canal,
               COUNT_BIG(*) AS transacciones,
               SUM(CASE WHEN m.direccion = 'CREDITO' THEN m.monto ELSE CAST(0 AS decimal(18,2)) END) AS monto_creditos,
               SUM(CASE WHEN m.direccion = 'DEBITO'  THEN m.monto ELSE CAST(0 AS decimal(18,2)) END) AS monto_debitos,
               CAST(AVG(m.monto) AS decimal(18,2)) AS ticket_promedio
        FROM (SELECT CONCAT(CAST(YEAR(t.fecha) AS varchar(4)), '-', RIGHT(CONCAT('0', CAST(MONTH(t.fecha) AS varchar(2))), 2)) AS mes,
                     t.cuenta_id, t.canal, t.direccion, t.monto
              FROM AB_Lakehouse.dbo.ab_silver_transacciones AS t) AS m
        JOIN AB_Lakehouse.dbo.ab_silver_cuentas AS c  ON c.cuenta_id   = m.cuenta_id
        JOIN AB_Lakehouse.dbo.ab_silver_clientes AS cl ON cl.cliente_id = c.cliente_id
        JOIN AB_Lakehouse.dbo.ab_silver_sucursales AS s  ON s.sucursal_id = cl.sucursal_id
        GROUP BY m.mes, s.provincia, m.canal
    ) AS q
    OPTION (LABEL = 'FAC_CMP_EP_medicion');
    SET @ms = DATEDIFF(MILLISECOND, @t0, SYSUTCDATETIME());
    INSERT INTO #tiempos (repeticion, variante, milisegundos) VALUES (@i, 'T-SQL sobre tablas plata del Lakehouse', @ms);
    SET @ep_grupos = @grupos; SET @ep_tx = @tx; SET @ep_cre = @cre; SET @ep_deb = @deb;

    SET @i += 1;
END;

-- 4) Tiempos y verificación de resultados (columnas prueba | estado | detalle) --------------------
SELECT CONCAT('tiempo ', variante, ' #', repeticion) AS prueba,
       'INFO' AS estado,
       CONCAT(milisegundos, ' ms (cliente: computo completo sin transferir filas)') AS detalle
FROM #tiempos
ORDER BY variante, repeticion;

SELECT 'C1 Warehouse: 210 grupos, 72000 transacciones y totales del laboratorio' AS prueba,
       CASE WHEN @wh_grupos = 210 AND @wh_tx = 72000
             AND @wh_cre = CAST(14976153627.79 AS decimal(38,2))
             AND @wh_deb = CAST(4530373831.90  AS decimal(38,2))
            THEN 'OK' ELSE 'FALLA' END AS estado,
       CONCAT('grupos=', @wh_grupos, '; transacciones=', @wh_tx, '; creditos=', @wh_cre, '; debitos=', @wh_deb) AS detalle;

SELECT 'C2 Lakehouse: mismos 210 grupos y totales' AS prueba,
       CASE WHEN @ep_grupos = 210 AND @ep_tx = 72000
             AND @ep_cre = CAST(14976153627.79 AS decimal(38,2))
             AND @ep_deb = CAST(4530373831.90  AS decimal(38,2))
            THEN 'OK' ELSE 'FALLA' END AS estado,
       CONCAT('grupos=', @ep_grupos, '; transacciones=', @ep_tx) AS detalle;

DROP TABLE IF EXISTS #tiempos;
GO

-- 4b) C3: el Warehouse y el Lakehouse devuelven exactamente las mismas filas (sin el ticket) ----
SELECT 'C3 Warehouse y Lakehouse devuelven exactamente las mismas filas (sin ticket)' AS prueba,
       CASE WHEN a.solo_wh = 0 AND b.solo_ep = 0 THEN 'OK' ELSE 'FALLA' END AS estado,
       CONCAT('solo en Warehouse=', a.solo_wh, '; solo en Lakehouse=', b.solo_ep) AS detalle
FROM (SELECT COUNT_BIG(*) AS solo_wh FROM (
          SELECT w.mes, w.provincia, w.canal, w.transacciones, w.monto_creditos, w.monto_debitos FROM (
        SELECT m.mes, s.provincia, m.canal,
               COUNT_BIG(*) AS transacciones,
               SUM(CASE WHEN m.direccion = 'CREDITO' THEN m.monto ELSE CAST(0 AS decimal(18,2)) END) AS monto_creditos,
               SUM(CASE WHEN m.direccion = 'DEBITO'  THEN m.monto ELSE CAST(0 AS decimal(18,2)) END) AS monto_debitos,
               CAST(AVG(m.monto) AS decimal(18,2)) AS ticket_promedio
        FROM (SELECT CONCAT(CAST(YEAR(t.fecha) AS varchar(4)), '-', RIGHT(CONCAT('0', CAST(MONTH(t.fecha) AS varchar(2))), 2)) AS mes,
                     t.cuenta_id, t.canal, t.direccion, t.monto
              FROM transacciones.fact_transaccion AS t) AS m
        JOIN cuentas.dim_cuenta AS c  ON c.cuenta_id   = m.cuenta_id
        JOIN clientes.dim_cliente AS cl ON cl.cliente_id = c.cliente_id
        JOIN clientes.dim_sucursal AS s  ON s.sucursal_id = cl.sucursal_id
        GROUP BY m.mes, s.provincia, m.canal
          ) AS w
          EXCEPT
          SELECT e.mes, e.provincia, e.canal, e.transacciones, e.monto_creditos, e.monto_debitos FROM (
        SELECT m.mes, s.provincia, m.canal,
               COUNT_BIG(*) AS transacciones,
               SUM(CASE WHEN m.direccion = 'CREDITO' THEN m.monto ELSE CAST(0 AS decimal(18,2)) END) AS monto_creditos,
               SUM(CASE WHEN m.direccion = 'DEBITO'  THEN m.monto ELSE CAST(0 AS decimal(18,2)) END) AS monto_debitos,
               CAST(AVG(m.monto) AS decimal(18,2)) AS ticket_promedio
        FROM (SELECT CONCAT(CAST(YEAR(t.fecha) AS varchar(4)), '-', RIGHT(CONCAT('0', CAST(MONTH(t.fecha) AS varchar(2))), 2)) AS mes,
                     t.cuenta_id, t.canal, t.direccion, t.monto
              FROM AB_Lakehouse.dbo.ab_silver_transacciones AS t) AS m
        JOIN AB_Lakehouse.dbo.ab_silver_cuentas AS c  ON c.cuenta_id   = m.cuenta_id
        JOIN AB_Lakehouse.dbo.ab_silver_clientes AS cl ON cl.cliente_id = c.cliente_id
        JOIN AB_Lakehouse.dbo.ab_silver_sucursales AS s  ON s.sucursal_id = cl.sucursal_id
        GROUP BY m.mes, s.provincia, m.canal
          ) AS e) AS x) AS a
CROSS JOIN (SELECT COUNT_BIG(*) AS solo_ep FROM (
          SELECT e.mes, e.provincia, e.canal, e.transacciones, e.monto_creditos, e.monto_debitos FROM (
        SELECT m.mes, s.provincia, m.canal,
               COUNT_BIG(*) AS transacciones,
               SUM(CASE WHEN m.direccion = 'CREDITO' THEN m.monto ELSE CAST(0 AS decimal(18,2)) END) AS monto_creditos,
               SUM(CASE WHEN m.direccion = 'DEBITO'  THEN m.monto ELSE CAST(0 AS decimal(18,2)) END) AS monto_debitos,
               CAST(AVG(m.monto) AS decimal(18,2)) AS ticket_promedio
        FROM (SELECT CONCAT(CAST(YEAR(t.fecha) AS varchar(4)), '-', RIGHT(CONCAT('0', CAST(MONTH(t.fecha) AS varchar(2))), 2)) AS mes,
                     t.cuenta_id, t.canal, t.direccion, t.monto
              FROM AB_Lakehouse.dbo.ab_silver_transacciones AS t) AS m
        JOIN AB_Lakehouse.dbo.ab_silver_cuentas AS c  ON c.cuenta_id   = m.cuenta_id
        JOIN AB_Lakehouse.dbo.ab_silver_clientes AS cl ON cl.cliente_id = c.cliente_id
        JOIN AB_Lakehouse.dbo.ab_silver_sucursales AS s  ON s.sucursal_id = cl.sucursal_id
        GROUP BY m.mes, s.provincia, m.canal
          ) AS e
          EXCEPT
          SELECT w.mes, w.provincia, w.canal, w.transacciones, w.monto_creditos, w.monto_debitos FROM (
        SELECT m.mes, s.provincia, m.canal,
               COUNT_BIG(*) AS transacciones,
               SUM(CASE WHEN m.direccion = 'CREDITO' THEN m.monto ELSE CAST(0 AS decimal(18,2)) END) AS monto_creditos,
               SUM(CASE WHEN m.direccion = 'DEBITO'  THEN m.monto ELSE CAST(0 AS decimal(18,2)) END) AS monto_debitos,
               CAST(AVG(m.monto) AS decimal(18,2)) AS ticket_promedio
        FROM (SELECT CONCAT(CAST(YEAR(t.fecha) AS varchar(4)), '-', RIGHT(CONCAT('0', CAST(MONTH(t.fecha) AS varchar(2))), 2)) AS mes,
                     t.cuenta_id, t.canal, t.direccion, t.monto
              FROM transacciones.fact_transaccion AS t) AS m
        JOIN cuentas.dim_cuenta AS c  ON c.cuenta_id   = m.cuenta_id
        JOIN clientes.dim_cliente AS cl ON cl.cliente_id = c.cliente_id
        JOIN clientes.dim_sucursal AS s  ON s.sucursal_id = cl.sucursal_id
        GROUP BY m.mes, s.provincia, m.canal
          ) AS w) AS y) AS b;
GO

-- 5) Tiempo del servidor según Query Insights (puede tardar hasta 15 min en aparecer) --
SELECT TOP 20 label, start_time, total_elapsed_time_ms
FROM queryinsights.exec_requests_history
WHERE label LIKE 'FAC_CMP%'
ORDER BY start_time DESC;
GO
