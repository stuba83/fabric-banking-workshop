# Módulo B1 — Preparar los datos para ML

**Notebook:** [B1_preparacion_datos.ipynb](../../notebooks/bonus_ml/B1_preparacion_datos.ipynb)  
**Dedicación orientativa:** 45–60 minutos  
**Capacidad:** funciona en Trial; solo la IA de Data Wrangler requiere capacidad de pago  
**Guía general:** [Bonus de ciencia de datos](guia.md)

## Objetivo

Convertir las tablas plata de la [Sesión 3](../sesion-03/guia.md) en una tabla de *features* lista para entrenar, y hacerlo **sin fuga de datos**. Se practica Data Wrangler y, de forma opcional, semantic link.

## Antes de empezar

- Las tablas `<prefijo>_silver_transacciones` (72.000 filas), `_cuentas` (1.800) y `_clientes` (1.200) existen. El notebook se detiene antes de cargar nada si los conteos no coinciden.
- Importa el notebook, renómbralo con tu prefijo y adjunta tu Lakehouse como predeterminado (ver [la guía general](guia.md#importar-y-ejecutar-los-notebooks)).
- Parámetros: `p_lakehouse_esperado`, `p_prefijo` y `p_confirmar_reemplazo`. Con `NO` puedes explorar sin escribir; con `SI` escribe la tabla. `p_modelo_semantico` es opcional.

## Qué hace cada sección

| Sección | Qué se hace | Qué aprender |
|---|---|---|
| 1. Leer las tablas plata | Carga a pandas y valida conteos | Las comprobaciones se hacen **antes** de trabajar |
| 2. Exploración | Forma, valores y mezcla de canales | Mirar los datos antes de modelar |
| 3. Data Wrangler | Agrupar por cuenta con la interfaz visual y exportar el código | Explorar rápido, y **revisar** el código que se genera |
| 4. Features | Una fila por cuenta y corte, con ventana fija de dos meses | Por qué las variables acumuladas producen deriva falsa |
| 5. Fuga de datos | Quitar los meses posteriores y comprobar que nada cambia | Una prueba concreta de que no se usa el futuro |
| 6. Guardar | Escribe `<prefijo>_gold_ml_features_cuentas` y verifica el conteo | Escritura con confirmación explícita |
| 7. Semantic link | Reconcilia la medida `Transacciones` de la Sesión 4 con pandas | Un modelo semántico y un notebook deben contar lo mismo |

### Práctica de Data Wrangler

1. Ejecuta la celda que deja el DataFrame `tx_dw` y **espera a que termine**: Data Wrangler no se abre con el kernel ocupado.
2. Abre **Data Wrangler** desde la cinta y elige `tx_dw`.
3. Revisa el resumen por columna (faltantes, distintos, distribución). Fíjate en `canal` y `monto`.
4. Aplica **agrupar y agregar**: por `cuenta_id`, contar filas.
5. **Agrega el código al notebook**, renombra el resultado a `conteo_dw` y la columna del conteo a `n_tx`.
6. Ejecuta la celda de verificación: debe decir `Coincide con pandas: 1800 cuentas, 72000 transacciones.`

Las sugerencias de IA y la caja de Copilot de Data Wrangler **requieren capacidad F2 o superior**. Si las tienes, prueba una transformación en lenguaje natural y **revisa el código** antes de aceptarlo.

## Resultado verificable

| Control | Esperado |
|---|---:|
| Filas de `<prefijo>_gold_ml_features_cuentas` | 9.000 |
| Filas por corte (mayo a septiembre) | 1.800 |
| Positivas en mayo, junio, julio y agosto | 563, 589, 631 y 651 |
| Positivas en septiembre | Sin etiqueta (octubre aún no ocurre) |
| Prueba de fuga de datos | `Sin fuga de datos: las variables de julio no cambian…` |
| Reconciliación con semantic link (opcional) | 6 meses coinciden |

Verifica con T-SQL en el SQL analytics endpoint de tu Lakehouse (reemplaza `ab_` por tu prefijo):

```sql
SELECT corte, COUNT(*) AS filas, SUM(alta_actividad_siguiente) AS positivas
FROM ab_gold_ml_features_cuentas
GROUP BY corte
ORDER BY corte;
```

## Qué documentar en las evidencias

- Los conteos medidos de las tres tablas plata y de la tabla de features, y las positivas por corte (medidas con T-SQL, no copiadas).
- El resultado de la comprobación de Data Wrangler y de la prueba de fuga de datos.
- Si probaste semantic link: el resultado de la reconciliación y, con el rol `Heredia`, el valor devuelto (8.971 si el rol se evaluó bien).
- Una explicación propia de por qué las variables usan una ventana fija.

## Bloqueos frecuentes

| Síntoma | Revisar |
|---|---|
| `expected an existing table` o `expected row count` | Que la Sesión 3 terminó y el prefijo coincide; vuelve a ejecutar el pipeline si hace falta |
| `p_confirmar_reemplazo must be exactly 'SI'` en la sección 6 | Es lo esperado con `NO`; fija `SI` para escribir |
| Data Wrangler no abre | El kernel debe estar libre; revisa que el DataFrame sea de pandas o Spark |
| `control positivas por corte` falla | Que las tablas plata no se hayan editado; reejecuta las Sesiones 2 y 3 |
| `No module named 'sempy'` | Que el notebook sea de PySpark en un runtime de Fabric |
| La reconciliación no coincide | Relaciones y medida `Transacciones` del modelo de la Sesión 4; nombre del modelo en `p_modelo_semantico` |
| El rol `Heredia` falla | Depende de tus permisos sobre el modelo; usa **Test as role** en el servicio |

## Siguiente

[Módulo B2: entrenar y comparar con MLflow](modulo-2-entrenamiento.md).
