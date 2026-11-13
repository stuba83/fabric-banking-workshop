/* ============================================================================
   FAC_WH_Gold  -  04_estado_inicial.sql
   Deja el Warehouse en el estado inicial reproducible de la demo en vivo:
     1. vacía la bitácora y la reconciliación (TRUNCATE conserva la tabla y su time travel),
     2. ejecuta UNA carga completa (operacion.usp_cargar_gold),
     3. devuelve los conteos, el lote y las últimas filas de la bitácora.
   Resultado esperado: 72.000 filas en fact_transaccion, 30 en resumen_mes_canal, un solo lote_id en el
   hecho, 1 corrida INICIO/OK en la bitácora y 26 controles OK en la reconciliación.
   Ejecutar con deploy.ps1 -RestablecerDemo (o a mano en el editor SQL). No modifica AB_*.
   ============================================================================ */

TRUNCATE TABLE operacion.bitacora_carga;
TRUNCATE TABLE operacion.reconciliacion;
GO

EXEC operacion.usp_cargar_gold;
GO

SELECT 'E1 estado inicial: hecho, resumen y lotes' AS prueba,
       CASE WHEN (SELECT COUNT_BIG(*) FROM transacciones.fact_transaccion) = 72000
             AND (SELECT COUNT_BIG(*) FROM transacciones.resumen_mes_canal) = 30
             AND (SELECT COUNT(DISTINCT lote_id) FROM transacciones.fact_transaccion) = 1
            THEN 'OK' ELSE 'FALLA' END AS estado,
       CONCAT('hecho=', (SELECT COUNT_BIG(*) FROM transacciones.fact_transaccion),
              '; resumen=', (SELECT COUNT_BIG(*) FROM transacciones.resumen_mes_canal),
              '; lotes en el hecho=', (SELECT COUNT(DISTINCT lote_id) FROM transacciones.fact_transaccion)) AS detalle;
GO

SELECT 'E2 bitacora y reconciliacion de una sola corrida' AS prueba,
       CASE WHEN (SELECT COUNT_BIG(*) FROM operacion.bitacora_carga WHERE estado = 'ERROR') = 0
             AND (SELECT COUNT_BIG(*) FROM operacion.reconciliacion) = 26
             AND (SELECT COUNT_BIG(*) FROM operacion.reconciliacion WHERE estado <> 'OK') = 0
            THEN 'OK' ELSE 'FALLA' END AS estado,
       CONCAT('filas en bitacora=', (SELECT COUNT_BIG(*) FROM operacion.bitacora_carga),
              '; controles=', (SELECT COUNT_BIG(*) FROM operacion.reconciliacion)) AS detalle;
GO
