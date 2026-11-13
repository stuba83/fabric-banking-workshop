"""Genera las variantes de la biblioteca y los notebooks del demo desde la fuente única.

    python generar_variantes.py            # escribe los archivos
    python generar_variantes.py --check    # falla si algún archivo generado no coincide

Fuente única: librerias/fuente/funciones.py. Salidas:
  - librerias/B2_paquete_environment/fac_utils/src/fac_utils/funciones.py (copia exacta)
  - librerias/B3_modulo_files/fac_utils_lh.py                             (copia exacta)
  - librerias/B1_notebook_run/FAC_NB_Utils.ipynb          (el código dentro de una celda)
  - librerias/B1_notebook_run/FAC_NB_Demo_Libreria_A.ipynb
  - librerias/B2_paquete_environment/FAC_NB_Demo_Libreria_B.ipynb
  - librerias/B3_modulo_files/FAC_NB_Demo_Libreria_C.ipynb
  - comparacion/FAC_NB_Spark_vs_TSQL.ipynb
Los notebooks llevan marcadores {{WORKSPACE_ID}}, {{FAC_LH_ID}} y {{FAC_ENV_ID}} en
metadata.dependencies; deploy.ps1 los reemplaza al subirlos.
"""

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FUENTE = RAIZ / "librerias" / "fuente" / "funciones.py"
SALIDAS_COPIA = [
    RAIZ / "librerias" / "B2_paquete_environment" / "fac_utils" / "src" / "fac_utils" / "funciones.py",
    RAIZ / "librerias" / "B3_modulo_files" / "fac_utils_lh.py",
]

NOMBRE_LAKEHOUSE_FAC = "FAC_LH_Utils"


# ---------------------------------------------------------------------------
# Utilidades de notebook
# ---------------------------------------------------------------------------
def _lineas(texto):
    texto = texto.strip("\n")
    partes = texto.split("\n")
    return [p + "\n" for p in partes[:-1]] + [partes[-1]]


def md(id_, texto):
    return {"cell_type": "markdown", "id": id_, "metadata": {}, "source": _lineas(texto)}


def code(id_, texto, parametros=False):
    return {
        "cell_type": "code",
        "execution_count": None,
        "id": id_,
        "metadata": {"tags": ["parameters"]} if parametros else {},
        "outputs": [],
        "source": _lineas(texto),
    }


def notebook(celdas, lakehouse=True, environment=False):
    dependencias = {}
    if lakehouse:
        dependencias["lakehouse"] = {
            "default_lakehouse": "{{FAC_LH_ID}}",
            "default_lakehouse_name": NOMBRE_LAKEHOUSE_FAC,
            "default_lakehouse_workspace_id": "{{WORKSPACE_ID}}",
            "known_lakehouses": [{"id": "{{FAC_LH_ID}}"}],
        }
    if environment:
        dependencias["environment"] = {"environmentId": "{{FAC_ENV_ID}}", "workspaceId": "{{WORKSPACE_ID}}"}
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "cells": celdas,
        "metadata": {
            "kernelspec": {"display_name": "Synapse PySpark", "language": "Python", "name": "synapse_pyspark"},
            "language_info": {"name": "python"},
            "dependencies": dependencias,
        },
    }


def serializar(nb):
    return json.dumps(nb, ensure_ascii=False, indent=1) + "\n"


# ---------------------------------------------------------------------------
# Cuerpo común de los tres demos (idéntico en A, B y C)
# ---------------------------------------------------------------------------
IMPORTAR_NOMBRES = """from {modulo} import (
    version,
    normalizar_columnas,
    validar_rango_fechas,
    hash_fila,
    hash_fila_python,
    escribir_bitacora,
    leer_bitacora,
    leer_tabla_delta,
)"""


def cuerpo_comun(prefijo):
    return [
        md(f"{prefijo}-cuerpo-md", """
## Usar las funciones (este bloque es idéntico en las tres variantes)

Las cuatro utilidades de la demo: **normalizar columnas**, **validar un rango de fechas**,
**hash de fila para conciliar** y **escribir en la bitácora**. Los datos son sintéticos."""),
        code(f"{prefijo}-normalizar", """
import json

datos = [("TX1", "2026-04-01", 100.50, 1), ("TX2", "2026-09-30", 20.00, 2), ("TX3", "2026-10-05", 5.25, 3)]
df_sucio = spark.createDataFrame(datos, ["ID Transacción", "Fecha de Alta (UTC)", "Monto (CRC)", "Monto  CRC"])
df_limpio = normalizar_columnas(df_sucio)
print("Antes:  ", df_sucio.columns)
print("Después:", df_limpio.columns)   # esperado: id_transaccion, fecha_de_alta_utc, monto_crc, monto_crc_2
verificaciones["columnas_normalizadas"] = df_limpio.columns == ["id_transaccion", "fecha_de_alta_utc", "monto_crc", "monto_crc_2"]"""),
        code(f"{prefijo}-fechas", """
r_ejemplo = validar_rango_fechas(df_limpio, "fecha_de_alta_utc", "2026-04-01", "2026-09-30")
print(r_ejemplo)   # esperado: total 3, fuera_de_rango 1 (2026-10-05), ok False

tx = leer_tabla_delta(spark, p_lakehouse_origen, p_tabla_transacciones)   # solo lectura
r_tx = validar_rango_fechas(tx, "fecha_hora", "2026-04-01", "2026-09-30")
print(r_tx)        # esperado con el dataset del laboratorio: total 72000, nulos 0, fuera_de_rango 0, ok True
verificaciones["rango_ejemplo_fuera_de_rango"] = r_ejemplo["fuera_de_rango"]
verificaciones["rango_tx"] = {k: r_tx[k] for k in ("total", "nulos", "fuera_de_rango", "ok")}"""),
        code(f"{prefijo}-hash", """
columnas_hash = ["transaccion_id", "cuenta_id", "direccion", "canal", "monto"]
tx_h = hash_fila(tx, columnas_hash)

# SHA-256 esperado de las tres primeras transacciones (dataset sintético del laboratorio).
ESPERADO = {
    "TX00000001": "4d01750fa7d9891609de2ddfaca0af9f435d9037944b6d3d49948a8cbea76a50",
    "TX00000002": "967eb9eeb586c00246cccfccdd521ce6f72750fa24275b6850caf7ad9697ff99",
    "TX00000003": "bcec1f1f890d7e1d57e575cdf6fa6a5902f8c7d2061ff70e0e5fef85e0aff819",
}
coincidencias = []
for fila in tx_h.orderBy("transaccion_id").limit(3).collect():
    en_python = hash_fila_python([fila[c] for c in columnas_hash])
    igual_python = fila["hash_fila"] == en_python
    igual_referencia = fila["hash_fila"] == ESPERADO.get(fila["transaccion_id"])
    coincidencias.append(igual_python and igual_referencia)
    print(fila["transaccion_id"], fila["hash_fila"][:16] + "…",
          "| igual a hash_fila_python:", igual_python, "| igual al valor de referencia:", igual_referencia)
hashes_distintos = tx_h.select("hash_fila").distinct().count()
print("hashes distintos:", hashes_distintos, "de", r_tx["total"])
verificaciones["hash_tres_primeras_ok"] = all(coincidencias) and len(coincidencias) == 3
verificaciones["hashes_distintos"] = hashes_distintos"""),
        code(f"{prefijo}-bitacora", """
escribir_bitacora(spark, f"demo_libreria_{p_variante}", "OK", filas=r_tx["total"],
                  mensaje=json.dumps({"tiempos": tiempos, "verificaciones": verificaciones}))
display(leer_bitacora(spark, ultimas=3))"""),
        code(f"{prefijo}-resumen", """
resumen = {
    "variante": p_variante,
    "version_funciones": version(),
    "validacion_fechas_ok": r_tx["ok"],
    "filas": r_tx["total"],
    "tiempos": tiempos,
    "verificaciones": verificaciones,
}
print(json.dumps(resumen, indent=2, ensure_ascii=False))"""),
    ]


# ---------------------------------------------------------------------------
# Notebooks
# ---------------------------------------------------------------------------
def nb_utils(fuente):
    celdas = [
        md("utils-intro", """
# FAC_NB_Utils — funciones comunes (variante 1: notebook compartido)

Contiene las funciones utilitarias de la demo (normalizar columnas, validar rango de fechas,
hash de fila, bitácora, lectura de otro Lakehouse). Se usa de dos maneras:

| Forma | Qué pasa | Para qué |
|---|---|---|
| `%run FAC_NB_Utils` | Ejecuta este notebook **dentro de la sesión del que llama**: las funciones y variables quedan disponibles. | Compartir código. |
| `notebookutils.notebook.run("FAC_NB_Utils", 120, {"p_accion": "version"})` | Lo ejecuta como una llamada y **solo devuelve el valor de `exit()`** (texto). | Orquestar pasos, no compartir funciones. |

**No defina un Lakehouse predeterminado aquí**: la ejecución de referencia exige que el hijo use el mismo
Lakehouse que el padre, lo herede o no defina ninguno. No agregue `%pip` (no se admite en ejecuciones de
referencia). Fuente única: `librerias/fuente/funciones.py`."""),
        code("utils-parametros", """
# Celda de parámetros. "" solo define las funciones; "version" devuelve la versión como valor de salida.
p_accion = \"\"""", parametros=True),
        code("utils-funciones", fuente),
        code("utils-salida", """
import json

if p_accion == "version":
    notebookutils.notebook.exit(json.dumps({"fac_utils": __version__, "funciones": list(__all__)}))"""),
    ]
    return notebook(celdas, lakehouse=False, environment=False)


def nb_demo_a():
    celdas = [
        md("a-intro", """
# FAC_NB_Demo_Libreria_A — código compartido con %run / notebookutils.notebook.run

**Variante 1.** Las funciones viven en el notebook `FAC_NB_Utils` del mismo workspace.

Requisitos: `FAC_NB_Utils` existe en este workspace; el Lakehouse predeterminado de este notebook es
`FAC_LH_Utils` (aquí se escribe la bitácora); `AB_Lakehouse` tiene las tablas de la Sesión 3 (solo lectura).

Qué debe observar el facilitador:
1. `notebook.run` devuelve un texto pero **no** deja las funciones disponibles.
2. `%run` sí las deja disponibles, porque ejecuta el notebook en el contexto actual.
3. Cuánto tarda cada una (celdas de medición; no hay cifras prometidas)."""),
        code("a-parametros", """
p_variante = "A_run"
p_lakehouse_origen = "AB_Lakehouse"
p_tabla_transacciones = "ab_silver_transacciones\"""", parametros=True),
        md("a-run-md", "## Parte 1 — `notebookutils.notebook.run` (llamada; devuelve el valor de salida)"),
        code("a-run-codigo", """
import json
import time

t0 = time.perf_counter()
salida = notebookutils.notebook.run("FAC_NB_Utils", 120, {"p_accion": "version"})
t_notebook_run = time.perf_counter() - t0

print("Valor de salida del hijo:", json.loads(salida))
print(f"notebookutils.notebook.run: {t_notebook_run:.2f} s")
verificaciones = {"funciones_visibles_tras_notebook_run": "normalizar_columnas" in globals()}
print("¿normalizar_columnas quedó disponible en este notebook?", verificaciones["funciones_visibles_tras_notebook_run"])  # esperado: False"""),
        md("a-magic-md", """
## Parte 2 — `%run` (mismo contexto; las funciones quedan disponibles)

La medición va en tres celdas porque `%run` es una orden mágica y no se puede envolver en Python:
marca de tiempo → `%run` → diferencia. El resultado incluye el paso entre celdas; repita con la sesión
ya iniciada para no mezclar el arranque de Spark con la medición."""),
        code("a-marca", """
import time

_t0_run = time.perf_counter()"""),
        code("a-run-magic", "%run FAC_NB_Utils"),
        code("a-fin-run", """
t_run = time.perf_counter() - _t0_run
tiempos = {"notebook_run_s": round(t_notebook_run, 3), "run_magic_s": round(t_run, 3)}
print(f"%run FAC_NB_Utils: {t_run:.2f} s (incluye el paso entre celdas)")
verificaciones["funciones_visibles_tras_run"] = "normalizar_columnas" in globals()
print("¿normalizar_columnas disponible ahora?", verificaciones["funciones_visibles_tras_run"])   # esperado: True
print("Versión de las funciones:", version())"""),
    ] + cuerpo_comun("a")
    return notebook(celdas, lakehouse=True, environment=False)


def nb_demo_b():
    celdas = [
        md("b-intro", """
# FAC_NB_Demo_Libreria_B — paquete Python (.whl) en un Environment

**Variante 2.** El paquete `fac_utils` se publica en el Environment `FAC_ENV_Utils`, que este notebook tiene
adjunto. Basta con `import fac_utils`: no hay `%run` ni rutas.

Antes de ejecutar: el Environment debe estar **publicado** (Learn: Full mode tarda de 3 a 6 minutos y suma de
1 a 3 minutos al arranque de la sesión; Quick mode publica en unos 5 segundos e instala al arrancar la sesión)
y la sesión debe haberse iniciado **después** de la publicación."""),
        code("b-parametros", """
p_variante = "B_environment"
p_lakehouse_origen = "AB_Lakehouse"
p_tabla_transacciones = "ab_silver_transacciones\"""", parametros=True),
        md("b-contexto-md", """
## Contexto de la sesión

El arranque de la sesión con Environment se ve en el **Monitoring hub** (Spark application). Anote el
`applicationId` para localizarla y compare con una sesión sin Environment."""),
        code("b-contexto", """
contexto = notebookutils.runtime.context
print("Environment adjunto:", contexto.get("environmentId"), "| workspace:", contexto.get("environmentWorkspaceId"))
print("applicationId:", spark.sparkContext.applicationId)"""),
        md("b-import-md", "## Medir la importación"),
        code("b-import", """
import time

_t0 = time.perf_counter()
try:
    import fac_utils
except ModuleNotFoundError as exc:
    raise RuntimeError(
        "fac_utils no está instalado: adjunte FAC_ENV_Utils, publíquelo y reinicie la sesión"
    ) from exc
t_import = time.perf_counter() - _t0

tiempos = {"import_fac_utils_s": round(t_import, 3)}
verificaciones = {"environment_id": contexto.get("environmentId"), "fac_utils_version": fac_utils.__version__}
print(f"import fac_utils: {t_import:.3f} s (primera importación de la sesión)")
print("fac_utils", fac_utils.__version__, "->", fac_utils.__file__)"""),
        code("b-nombres", IMPORTAR_NOMBRES.format(modulo="fac_utils")),
    ] + cuerpo_comun("b")
    return notebook(celdas, lakehouse=True, environment=True)


def nb_demo_c():
    celdas = [
        md("c-intro", """
# FAC_NB_Demo_Libreria_C — módulo .py en Files del Lakehouse + sys.path

**Variante 3.** El archivo `fac_utils_lh.py` está en `Files/libs/` de `FAC_LH_Utils` (Lakehouse predeterminado
de este notebook, montado en `/lakehouse/default`). Se agrega esa carpeta a `sys.path` y se importa.

Límites que conviene mostrar: no hay versionado de Fabric para el archivo (Git del Lakehouse solo registra
metadatos, no el contenido de Files), `sys.path` solo afecta al intérprete del **driver** y cualquier cambio
al archivo requiere `importlib.reload` o reiniciar el intérprete."""),
        code("c-parametros", """
p_variante = "C_files"
p_lakehouse_origen = "AB_Lakehouse"
p_tabla_transacciones = "ab_silver_transacciones"
p_ruta_modulo = "/lakehouse/default/Files/libs\"""", parametros=True),
        md("c-import-md", "## Medir la importación"),
        code("c-import", """
import os
import sys
import time

sys.dont_write_bytecode = True   # evita que Python deje __pycache__ dentro de Files/libs
if not os.path.isdir(p_ruta_modulo):
    raise FileNotFoundError(
        f"{p_ruta_modulo} no existe: suba fac_utils_lh.py a Files/libs de FAC_LH_Utils y use ese Lakehouse como predeterminado"
    )
if p_ruta_modulo not in sys.path:
    sys.path.insert(0, p_ruta_modulo)

_t0 = time.perf_counter()
import fac_utils_lh
t_import = time.perf_counter() - _t0

tiempos = {"import_fac_utils_lh_s": round(t_import, 3)}
verificaciones = {"ruta_modulo": fac_utils_lh.__file__, "fac_utils_lh_version": fac_utils_lh.__version__}
print(f"import fac_utils_lh: {t_import:.3f} s")
print("fac_utils_lh", fac_utils_lh.__version__, "->", fac_utils_lh.__file__)"""),
        code("c-nombres", IMPORTAR_NOMBRES.format(modulo="fac_utils_lh")),
        md("c-reload-md", "Para ver un cambio del archivo en la misma sesión: `import importlib; importlib.reload(fac_utils_lh)`."),
    ] + cuerpo_comun("c")
    return notebook(celdas, lakehouse=True, environment=False)


SQL_SPARK = """SELECT date_format(t.fecha, 'yyyy-MM') AS mes,
       s.provincia,
       t.canal,
       COUNT(*) AS transacciones,
       SUM(CASE WHEN t.direccion = 'CREDITO' THEN t.monto ELSE 0 END) AS monto_creditos,
       SUM(CASE WHEN t.direccion = 'DEBITO'  THEN t.monto ELSE 0 END) AS monto_debitos,
       ROUND(AVG(t.monto), 2) AS ticket_promedio
FROM ab_silver_transacciones t
JOIN ab_silver_cuentas    c  ON c.cuenta_id   = t.cuenta_id
JOIN ab_silver_clientes   cl ON cl.cliente_id = c.cliente_id
JOIN ab_silver_sucursales s  ON s.sucursal_id = cl.sucursal_id
GROUP BY date_format(t.fecha, 'yyyy-MM'), s.provincia, t.canal
ORDER BY mes, s.provincia, t.canal"""

SQL_TSQL_BASE = """/* {etiqueta} */
SELECT m.mes, s.provincia, m.canal,
       COUNT_BIG(*) AS transacciones,
       SUM(CASE WHEN m.direccion = 'CREDITO' THEN m.monto ELSE CAST(0 AS decimal(18,2)) END) AS monto_creditos,
       SUM(CASE WHEN m.direccion = 'DEBITO'  THEN m.monto ELSE CAST(0 AS decimal(18,2)) END) AS monto_debitos,
       CAST(AVG(m.monto) AS decimal(18,2)) AS ticket_promedio
FROM (SELECT CONCAT(CAST(YEAR(t.fecha) AS varchar(4)), '-', RIGHT(CONCAT('0', CAST(MONTH(t.fecha) AS varchar(2))), 2)) AS mes,
             t.cuenta_id, t.canal, t.direccion, t.monto
      FROM {transacciones} AS t) AS m
JOIN {cuentas}    AS c  ON c.cuenta_id   = m.cuenta_id
JOIN {clientes}   AS cl ON cl.cliente_id = c.cliente_id
JOIN {sucursales} AS s  ON s.sucursal_id = cl.sucursal_id
GROUP BY m.mes, s.provincia, m.canal"""

SQL_TSQL_WH = SQL_TSQL_BASE.format(
    etiqueta="FAC_CMP_WH_conector",
    transacciones="transacciones.fact_transaccion",
    cuentas="cuentas.dim_cuenta",
    clientes="clientes.dim_cliente",
    sucursales="clientes.dim_sucursal",
)
SQL_TSQL_EP = SQL_TSQL_BASE.format(
    etiqueta="FAC_CMP_EP_conector",
    transacciones="dbo.ab_silver_transacciones",
    cuentas="dbo.ab_silver_cuentas",
    clientes="dbo.ab_silver_clientes",
    sucursales="dbo.ab_silver_sucursales",
)


def nb_comparacion():
    celdas = [
        md("cmp-intro", """
# FAC_NB_Spark_vs_TSQL — la misma agregación en Spark SQL y en T-SQL

**Pregunta de negocio:** por mes, provincia (de la sucursal) y canal, ¿cuántas transacciones, cuánto crédito,
cuánto débito y cuál es el ticket promedio? Une transacciones → cuentas → clientes → sucursales.

| Variante | Motor | Origen |
|---|---|---|
| 1 | Spark SQL (este notebook) | Tablas plata de `AB_Lakehouse` (Delta, solo lectura) |
| 2 | T-SQL en el Warehouse | `FAC_WH_Gold` (modelo estrella cargado por procedimientos) |
| 3 (opcional) | T-SQL en el SQL analytics endpoint del Lakehouse | Las mismas tablas plata de la variante 1 |

**Sobre la medición.** Cada variante se repite; la primera repetición se muestra aparte porque suele incluir
metadatos y lectura en frío. En las variantes 2 y 3 el tiempo medido aquí incluye red, conversión y
transferencia del conector de Spark para Warehouse; el tiempo del servidor está en
`queryinsights.exec_requests_history` (ver `comparacion_tsql.sql`). **No se promete ningún resultado de
rendimiento**: lo que sí debe coincidir son los resultados."""),
        code("cmp-parametros", """
p_lakehouse_origen = "AB_Lakehouse"
p_warehouse = "FAC_WH_Gold"
p_repeticiones = 3
p_medir_endpoint = True""", parametros=True),
        md("cmp-run-md", "## Paso 1 — Funciones comunes (`%run`)"),
        code("cmp-run", "%run FAC_NB_Utils"),
        md("cmp-vistas-md", "## Paso 2 — Registrar las tablas plata como vistas temporales de Spark"),
        code("cmp-vistas", """
import json
import statistics
import time
from decimal import Decimal

for tabla in ("ab_silver_transacciones", "ab_silver_cuentas", "ab_silver_clientes", "ab_silver_sucursales"):
    leer_tabla_delta(spark, p_lakehouse_origen, tabla).createOrReplaceTempView(tabla)

print("filas en ab_silver_transacciones:", spark.sql("SELECT COUNT(*) AS filas FROM ab_silver_transacciones").first()["filas"])  # esperado: 72000"""),
        code("cmp-medir", """
def medir(nombre, ejecutar, repeticiones):
    \"\"\"Ejecuta `ejecutar` varias veces y devuelve los segundos de cada repetición y las filas.\"\"\"
    segundos = []
    filas = None
    for _ in range(int(repeticiones)):
        t0 = time.perf_counter()
        filas = ejecutar()
        segundos.append(round(time.perf_counter() - t0, 3))
    return {"variante": nombre, "segundos": segundos, "filas": len(filas)}, filas


def clave(fila):
    return (fila["mes"], fila["provincia"], fila["canal"])"""),
        md("cmp-spark-md", "## Paso 3 — Variante 1: Spark SQL"),
        code("cmp-spark", "SQL_SPARK = \"\"\"\n" + SQL_SPARK + "\n\"\"\"\n\n"
             "res_spark, filas_spark = medir(\"Spark SQL (tablas plata del Lakehouse)\",\n"
             "                               lambda: spark.sql(SQL_SPARK).collect(), p_repeticiones)\n"
             "print(res_spark)"),
        md("cmp-wh-md", """
## Paso 4 — Variante 2: T-SQL en el Warehouse

Usa el conector de Spark para Fabric Warehouse con una consulta de paso (*passthrough*): el texto T-SQL se
ejecuta en el motor SQL y el resultado vuelve a Spark. Solo admite autenticación interactiva de usuario."""),
        code("cmp-wh", "import com.microsoft.spark.fabric\n"
             "from com.microsoft.spark.fabric.Constants import Constants\n\n"
             "SQL_TSQL_WH = \"\"\"\n" + SQL_TSQL_WH + "\n\"\"\"\n\n"
             "res_wh, filas_wh = medir(\"T-SQL Warehouse FAC_WH_Gold (conector)\",\n"
             "                         lambda: spark.read.option(Constants.DatabaseName, p_warehouse)\n"
             "                                      .synapsesql(SQL_TSQL_WH).collect(), p_repeticiones)\n"
             "print(res_wh)"),
        md("cmp-ep-md", "## Paso 5 (opcional) — Variante 3: T-SQL en el SQL analytics endpoint del Lakehouse"),
        code("cmp-ep", "SQL_TSQL_EP = \"\"\"\n" + SQL_TSQL_EP + "\n\"\"\"\n\n"
             "if p_medir_endpoint:\n"
             "    res_ep, filas_ep = medir(\"T-SQL endpoint SQL del Lakehouse (conector)\",\n"
             "                             lambda: spark.read.option(Constants.DatabaseName, p_lakehouse_origen)\n"
             "                                          .synapsesql(SQL_TSQL_EP).collect(), p_repeticiones)\n"
             "    print(res_ep)\n"
             "else:\n"
             "    res_ep, filas_ep = None, None"),
        md("cmp-verif-md", """
## Paso 6 — Los resultados deben coincidir

Se compara cada grupo (mes, provincia, canal) en transacciones y montos exactos. El ticket promedio queda fuera
de la igualdad porque el redondeo del promedio puede diferir entre motores."""),
        code("cmp-verif", """
ESPERADO = {
    "grupos": 210,
    "transacciones": 72000,
    "monto_creditos": Decimal("14976153627.79"),
    "monto_debitos": Decimal("4530373831.90"),
}


def firma(fila):
    return (int(fila["transacciones"]), Decimal(fila["monto_creditos"]), Decimal(fila["monto_debitos"]))


def resumen_totales(filas):
    return {
        "grupos": len(filas),
        "transacciones": sum(int(f["transacciones"]) for f in filas),
        "monto_creditos": sum((Decimal(f["monto_creditos"]) for f in filas), Decimal("0")),
        "monto_debitos": sum((Decimal(f["monto_debitos"]) for f in filas), Decimal("0")),
    }


motores = {"spark": filas_spark, "warehouse": filas_wh}
if filas_ep is not None:
    motores["endpoint"] = filas_ep

mapas = {nombre: {clave(f): firma(f) for f in filas} for nombre, filas in motores.items()}
for nombre, filas in motores.items():
    totales = resumen_totales(filas)
    print(f"{nombre:10s}", totales, "| coincide con el laboratorio:", totales == ESPERADO)

iguales = all(mapas[n] == mapas["spark"] for n in mapas)
print("Todos los motores devuelven exactamente los mismos grupos y montos:", iguales)
assert iguales, "Los motores no coinciden: revise la carga del Warehouse (operacion.usp_reconciliar)"
"""),
        md("cmp-resumen-md", "## Paso 7 — Tabla de tiempos (sin conclusiones automáticas)"),
        code("cmp-resumen", """
resultados = [r for r in (res_spark, res_wh, res_ep) if r]
for r in resultados:
    resto = r["segundos"][1:]
    print(f"{r['variante']:55s} primera: {r['segundos'][0]:7.3f} s | resto (mediana): "
          f"{(statistics.median(resto) if resto else float('nan')):7.3f} s | repeticiones: {r['segundos']}")

escribir_bitacora(spark, "spark_vs_tsql", "OK", filas=res_spark["filas"],
                  mensaje=json.dumps({"motores_iguales": iguales, "resultados": resultados}, ensure_ascii=False))
display(leer_bitacora(spark, ultimas=3))"""),
        md("cmp-lectura-md", """
## Cómo leer el resultado en la demo

- Compare **primera repetición** frente a las siguientes: muestra el efecto de lo frío frente a lo tibio, no de un motor.
- Los tiempos de las variantes 2 y 3 incluyen la transferencia del conector; para el tiempo del servidor use
  `queryinsights.exec_requests_history` con la etiqueta `FAC_CMP_*` (puede tardar hasta 15 minutos en aparecer).
- Cambie `p_repeticiones` y vuelva a ejecutar: conserve las cifras que mida, sin extrapolarlas a otros volúmenes.
- Mismo resultado, distinta herramienta: Spark escala horizontalmente y escribe Delta; T-SQL en Warehouse da
  transacciones entre tablas, procedimientos y seguridad en el motor SQL. Elija por el equipo y la carga, no por una cifra."""),
    ]
    return notebook(celdas, lakehouse=True, environment=False)


# ---------------------------------------------------------------------------
def main():
    comprobar = "--check" in sys.argv
    fuente = FUENTE.read_text(encoding="utf-8")
    salidas = {}
    for destino in SALIDAS_COPIA:
        salidas[destino] = fuente
    salidas[RAIZ / "librerias" / "B1_notebook_run" / "FAC_NB_Utils.ipynb"] = serializar(nb_utils(fuente.rstrip("\n")))
    salidas[RAIZ / "librerias" / "B1_notebook_run" / "FAC_NB_Demo_Libreria_A.ipynb"] = serializar(nb_demo_a())
    salidas[RAIZ / "librerias" / "B2_paquete_environment" / "FAC_NB_Demo_Libreria_B.ipynb"] = serializar(nb_demo_b())
    salidas[RAIZ / "librerias" / "B3_modulo_files" / "FAC_NB_Demo_Libreria_C.ipynb"] = serializar(nb_demo_c())
    salidas[RAIZ / "comparacion" / "FAC_NB_Spark_vs_TSQL.ipynb"] = serializar(nb_comparacion())

    distintos = []
    for ruta, contenido in salidas.items():
        ruta.parent.mkdir(parents=True, exist_ok=True)
        actual = ruta.read_text(encoding="utf-8") if ruta.exists() else None
        if actual != contenido:
            distintos.append(ruta)
            if not comprobar:
                ruta.write_text(contenido, encoding="utf-8", newline="\n")
    if comprobar:
        if distintos:
            print("Desactualizados:", *[str(r.relative_to(RAIZ)) for r in distintos], sep="\n  ")
            sys.exit(1)
        print("OK: las variantes generadas coinciden con la fuente")
    else:
        print(f"Generados {len(salidas)} archivos ({len(distintos)} cambiaron)")


if __name__ == "__main__":
    main()
