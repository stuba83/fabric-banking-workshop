"""Funciones utilitarias de demostración para el taller de Microsoft Fabric.

Las mismas funciones se entregan de tres maneras (ver README-warehouse-librerias.md):
  1. celdas de un notebook compartido (%run / notebookutils.notebook.run),
  2. paquete .whl publicado en un Environment,
  3. módulo .py guardado en Files de un Lakehouse y cargado con sys.path.

ESTA ES LA FUENTE ÚNICA. Las otras variantes se generan con
herramientas/generar_variantes.py y una prueba comprueba que son idénticas.

Solo usa la biblioteca estándar. PySpark y notebookutils los aporta el runtime de
Fabric, por eso se importan dentro de cada función (así el módulo se puede importar
y probar fuera de Fabric).
"""

import hashlib
import json
import re
import unicodedata
from datetime import date, datetime, timezone

__version__ = "0.1.0"

SEPARADOR_HASH = "|"
SENTINELA_NULO = "~NULL~"
TABLA_BITACORA = "fac_bitacora_demo"
ESTADOS_BITACORA = ("OK", "ERROR", "AVISO")

__all__ = [
    "version",
    "normalizar_nombre",
    "nombres_unicos",
    "normalizar_columnas",
    "validar_rango_fechas",
    "hash_fila",
    "hash_fila_python",
    "escribir_bitacora",
    "leer_bitacora",
    "leer_tabla_delta",
]


def version():
    """Versión de las funciones; debe ser igual en las tres variantes."""
    return __version__


def _col(nombre):
    from pyspark.sql import functions as F

    return F.col("`" + str(nombre).replace("`", "``") + "`")


# ---------------------------------------------------------------------------
# 1. Normalizar nombres de columnas
# ---------------------------------------------------------------------------
def normalizar_nombre(nombre):
    """'Fecha de Alta (UTC)' -> 'fecha_de_alta_utc'. Quita tildes y símbolos."""
    if nombre is None:
        raise ValueError("normalizar_nombre: el nombre no puede ser None")
    texto = unicodedata.normalize("NFKD", str(nombre))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", texto)
    texto = re.sub(r"[^0-9A-Za-z]+", "_", texto).strip("_").lower()
    if not texto:
        texto = "columna"
    if texto[0].isdigit():
        texto = "c_" + texto
    return texto


def nombres_unicos(nombres):
    """Agrega _2, _3... a los nombres repetidos, conservando el orden."""
    usados = set()
    resultado = []
    for nombre in nombres:
        candidato = nombre
        contador = 1
        while candidato in usados:
            contador += 1
            candidato = f"{nombre}_{contador}"
        usados.add(candidato)
        resultado.append(candidato)
    return resultado


def normalizar_columnas(df):
    """Devuelve el DataFrame con las columnas en snake_case ASCII y sin repetidas."""
    nuevos = nombres_unicos([normalizar_nombre(c) for c in df.columns])
    return df.toDF(*nuevos)


# ---------------------------------------------------------------------------
# 2. Validar un rango de fechas
# ---------------------------------------------------------------------------
def _fecha_iso(valor, nombre):
    if isinstance(valor, datetime):
        valor = valor.date()
    if isinstance(valor, date):
        return valor.isoformat()
    try:
        return date.fromisoformat(str(valor)).isoformat()
    except ValueError:
        raise ValueError(
            f"{nombre}: se esperaba una fecha ISO yyyy-MM-dd; recibido {valor!r}"
        ) from None


def validar_rango_fechas(df, columna, desde, hasta, fallar=False):
    """Cuenta nulos y fechas fuera de [desde, hasta] en una sola pasada.

    Devuelve un dict con total, nulos, fuera_de_rango, validas y ok. Con
    fallar=True lanza ValueError si hay nulos o fechas fuera de rango.
    """
    from pyspark.sql import functions as F

    d = _fecha_iso(desde, "desde")
    h = _fecha_iso(hasta, "hasta")
    if d > h:
        raise ValueError(f"validar_rango_fechas: desde ({d}) es posterior a hasta ({h})")
    if columna not in df.columns:
        raise ValueError(f"validar_rango_fechas: la columna {columna!r} no existe")

    f = _col(columna).cast("date")
    fuera = f.isNotNull() & ((f < F.lit(d).cast("date")) | (f > F.lit(h).cast("date")))
    fila = df.agg(
        F.count(F.lit(1)).alias("total"),
        F.sum(F.when(f.isNull(), 1).otherwise(0)).alias("nulos"),
        F.sum(F.when(fuera, 1).otherwise(0)).alias("fuera_de_rango"),
    ).first()
    total = int(fila["total"] or 0)
    nulos = int(fila["nulos"] or 0)
    fuera_rango = int(fila["fuera_de_rango"] or 0)
    resultado = {
        "columna": columna,
        "desde": d,
        "hasta": h,
        "total": total,
        "nulos": nulos,
        "fuera_de_rango": fuera_rango,
        "validas": total - nulos - fuera_rango,
        "ok": nulos == 0 and fuera_rango == 0,
    }
    if fallar and not resultado["ok"]:
        raise ValueError("validar_rango_fechas: " + json.dumps(resultado, ensure_ascii=False))
    return resultado


# ---------------------------------------------------------------------------
# 3. Hash de fila para conciliación
# ---------------------------------------------------------------------------
def hash_fila(df, columnas=None, nombre="hash_fila"):
    """Agrega SHA-256 (hex en minúsculas) de las columnas indicadas.

    Regla: cada valor se convierte a texto, el nulo se reemplaza por '~NULL~' y se
    une con '|'. Úsese con columnas de texto o decimales; formatee antes las fechas.
    Límite conocido: si un valor puede contener '|', dos filas distintas podrían dar el
    mismo hash (['a|b', 'c'] y ['a', 'b|c']); en ese caso sanee o reemplace el separador.
    hash_fila_python aplica la misma regla fuera de Spark.
    """
    from pyspark.sql import functions as F

    columnas = list(columnas) if columnas else list(df.columns)
    if not columnas:
        raise ValueError("hash_fila: se necesita al menos una columna")
    faltan = [c for c in columnas if c not in df.columns]
    if faltan:
        raise ValueError(f"hash_fila: columnas inexistentes {faltan}")
    partes = [F.coalesce(_col(c).cast("string"), F.lit(SENTINELA_NULO)) for c in columnas]
    return df.withColumn(nombre, F.sha2(F.concat_ws(SEPARADOR_HASH, *partes), 256))


def hash_fila_python(valores):
    """Misma regla que hash_fila, para comprobar un valor sin Spark."""
    texto = SEPARADOR_HASH.join(SENTINELA_NULO if v is None else str(v) for v in valores)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# 4. Bitácora de ejecución
# ---------------------------------------------------------------------------
def _contexto_notebook():
    try:
        import notebookutils  # lo aporta el runtime de Fabric

        contexto = notebookutils.runtime.context
        return {"notebook": contexto.get("currentNotebookName")}
    except Exception:
        return {"notebook": None}


def escribir_bitacora(spark, proceso, estado, filas=None, mensaje="", tabla=TABLA_BITACORA):
    """Agrega una fila a la tabla Delta de bitácora del Lakehouse predeterminado."""
    if estado not in ESTADOS_BITACORA:
        raise ValueError(f"escribir_bitacora: estado {estado!r} no está en {ESTADOS_BITACORA}")

    from pyspark.sql.types import LongType, StringType, StructField, StructType, TimestampType

    esquema = StructType(
        [
            StructField("fecha_utc", TimestampType(), False),
            StructField("proceso", StringType(), False),
            StructField("estado", StringType(), False),
            StructField("filas", LongType(), True),
            StructField("mensaje", StringType(), True),
            StructField("notebook", StringType(), True),
            StructField("version_funciones", StringType(), False),
        ]
    )
    ahora = datetime.now(timezone.utc).replace(tzinfo=None)
    fila = (
        ahora,
        str(proceso),
        estado,
        None if filas is None else int(filas),
        str(mensaje)[:2000],
        _contexto_notebook()["notebook"],
        __version__,
    )
    spark.createDataFrame([fila], esquema).write.format("delta").mode("append").saveAsTable(tabla)
    return {"tabla": tabla, "proceso": proceso, "estado": estado, "filas": filas}


def leer_bitacora(spark, ultimas=5, tabla=TABLA_BITACORA):
    """Devuelve las últimas filas de la bitácora (más recientes primero)."""
    from pyspark.sql import functions as F

    return spark.table(tabla).orderBy(F.col("fecha_utc").desc()).limit(int(ultimas))


# ---------------------------------------------------------------------------
# 5. Leer una tabla Delta de otro Lakehouse del mismo workspace (solo lectura)
# ---------------------------------------------------------------------------
def leer_tabla_delta(spark, lakehouse, tabla, esquema="dbo", workspace_id=None):
    """Lee Tables/<esquema>/<tabla> o Tables/<tabla> por ruta ABFSS con GUID.

    Sirve tanto para Lakehouse con esquemas como sin ellos y no modifica nada.
    """
    import notebookutils  # lo aporta el runtime de Fabric

    ws = workspace_id or notebookutils.runtime.context["currentWorkspaceId"]
    item = notebookutils.lakehouse.get(lakehouse, ws)
    lakehouse_id = getattr(item, "id", None) or item["id"]
    try:
        endpoint = notebookutils.conf.get("trident.onelake.endpoint").replace("https://", "")
    except Exception:
        endpoint = "onelake.dfs.fabric.microsoft.com"
    base = f"abfss://{ws}@{endpoint}/{lakehouse_id}/Tables"
    candidatas = (f"{base}/{esquema}/{tabla}", f"{base}/{tabla}")
    for ruta in candidatas:
        if notebookutils.fs.exists(ruta):
            return spark.read.format("delta").load(ruta)
    raise FileNotFoundError(
        f"leer_tabla_delta: no existe la tabla {tabla!r} en {lakehouse!r} (probado: {candidatas})"
    )
