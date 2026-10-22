"""Transformacion Bronze -> Silver y tabla Gold de consumo en Fabric.

Las seis tablas Bronze se leen completas en el proceso conductor (driver). Es una
simplificacion didactica adecuada para este conjunto (72.360 filas de
transacciones); no es un patron para GB o TB, donde las mismas reglas se
expresarian con Spark.
Las nueve escrituras no son atomicas: un error puede dejar una carga parcial.
Despues de resolverlo, se debe volver a ejecutar el lote entero.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any


PATRON_PREFIJO = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,19}\Z", re.ASCII)
PATRON_FECHA = re.compile(r"\d{4}-\d{2}-\d{2}\Z", re.ASCII)
PATRON_FECHA_HORA = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\Z", re.ASCII)
PATRON_ENTERO = re.compile(r"\d{1,9}\Z", re.ASCII)
PATRON_DECIMAL = re.compile(r"-?\d{1,16}(\.\d{1,2})?\Z", re.ASCII)

PERIODO_INICIO = date(2026, 4, 1)
PERIODO_FIN = date(2026, 9, 30)
MOTIVOS = ("cuenta_inexistente", "fecha_hora_invalida", "monto_negativo")
CANALES = ("BANCA_MOVIL", "WEB", "ATM", "SUCURSAL", "NO_INFORMADO")
DIRECCION_POR_TIPO = {
    "SALARIO": "CREDITO",
    "DEPOSITO": "CREDITO",
    "TRANSFERENCIA_RECIBIDA": "CREDITO",
    "INTERES": "CREDITO",
    "RETIRO": "DEBITO",
    "PAGO_SERVICIO": "DEBITO",
    "COMPRA": "DEBITO",
    "TRANSFERENCIA_ENVIADA": "DEBITO",
    "COMISION": "DEBITO",
}

# Las seis tablas Bronze que escribe la Sesion 2, con su numero de filas.
BRONCE_CONTEOS = {
    "clientes": 1200,
    "cuentas": 1800,
    "sucursales": 7,
    "productos": 5,
    "calendario": 183,
    "transacciones": 72360,
}

COLUMNAS_TRANSACCIONES_BRONCE = (
    "transaccion_id",
    "cuenta_id",
    "fecha_hora",
    "tipo_transaccion",
    "direccion",
    "canal",
    "monto",
    "moneda",
    "estado",
)

COLUMNAS_REFERENCIA = {
    "clientes": (
        ("cliente_id", "string"),
        ("nombre_sintetico", "string"),
        ("fecha_alta", "date"),
        ("segmento", "string"),
        ("grupo_edad", "string"),
        ("provincia", "string"),
        ("sucursal_id", "string"),
    ),
    "cuentas": (
        ("cuenta_id", "string"),
        ("cliente_id", "string"),
        ("producto_id", "string"),
        ("fecha_apertura", "date"),
        ("moneda", "string"),
        ("saldo_inicial", "decimal(18,2)"),
    ),
    "sucursales": (
        ("sucursal_id", "string"),
        ("nombre_sintetico", "string"),
        ("provincia", "string"),
    ),
    "productos": (
        ("producto_id", "string"),
        ("nombre_sintetico", "string"),
        ("familia", "string"),
        ("moneda", "string"),
    ),
    "calendario": (
        ("fecha", "date"),
        ("anio", "int"),
        ("trimestre", "int"),
        ("mes", "int"),
        ("nombre_mes", "string"),
        ("dia_mes", "int"),
        ("dia_semana", "int"),
        ("nombre_dia", "string"),
        ("es_fin_semana", "int"),
    ),
}

COLUMNAS_TEXTO_TRANSACCIONES = tuple(
    (columna, "string") for columna in COLUMNAS_TRANSACCIONES_BRONCE
)
COLUMNAS_SILVER_TRANSACCIONES = (
    ("transaccion_id", "string"),
    ("cuenta_id", "string"),
    ("fecha_hora", "timestamp"),
    ("fecha", "date"),
    ("tipo_transaccion", "string"),
    ("direccion", "string"),
    ("canal", "string"),
    ("monto", "decimal(18,2)"),
    ("moneda", "string"),
    ("estado", "string"),
)
COLUMNAS_CUARENTENA = COLUMNAS_TEXTO_TRANSACCIONES + (("motivo", "string"),)
COLUMNAS_ORO = (
    ("mes", "string"),
    ("canal", "string"),
    ("transacciones", "bigint"),
    ("monto_creditos", "decimal(18,2)"),
    ("monto_debitos", "decimal(18,2)"),
)

# Valores medidos sobre las 72.000 transacciones depuradas; coinciden con manifiesto.json.
CONTROLES_ESPERADOS: dict[str, Any] = {
    "filas": {
        "silver_clientes": 1200,
        "silver_cuentas": 1800,
        "silver_sucursales": 7,
        "silver_productos": 5,
        "silver_calendario": 183,
        "silver_transacciones": 72000,
        "silver_transacciones_cuarentena": 72,
        "silver_transacciones_duplicadas": 288,
        "gold_transacciones_mes_canal": 30,
    },
    "cuarentena_por_motivo": {
        "cuenta_inexistente": 24,
        "fecha_hora_invalida": 24,
        "monto_negativo": 24,
    },
    "transacciones_por_mes": {
        "2026-04": 11198,
        "2026-05": 11422,
        "2026-06": 11757,
        "2026-07": 12093,
        "2026-08": 12541,
        "2026-09": 12989,
    },
    "transacciones_por_canal": {
        "ATM": 8576,
        "BANCA_MOVIL": 41521,
        "NO_INFORMADO": 360,
        "SUCURSAL": 7218,
        "WEB": 14325,
    },
    "canal_normalizado": 720,
    "canal_vacio": 360,
    "monto_creditos": "14976153627.79",
    "monto_debitos": "4530373831.90",
    "oro_transacciones": 72000,
    "oro_monto_creditos": "14976153627.79",
    "oro_monto_debitos": "4530373831.90",
}


class _ValorInvalido(Exception):
    pass


@dataclass(frozen=True)
class TablaSalida:
    nombre: str
    columnas: tuple[tuple[str, str], ...]
    filas: list[tuple[Any, ...]]


@dataclass(frozen=True)
class ResultadoPlata:
    tablas: dict[str, TablaSalida]
    canal_normalizado: int
    canal_vacio: int


def nombre_tabla(prefijo: str, capa: str, base: str) -> str:
    return f"{prefijo.lower()}_{capa}_{base}"


def columnas_bronce(base: str) -> tuple[str, ...]:
    if base == "transacciones":
        return COLUMNAS_TRANSACCIONES_BRONCE
    return tuple(columna for columna, _ in COLUMNAS_REFERENCIA[base])


def _convertir(tipo: str, valor: str) -> Any:
    if tipo == "string":
        if valor and valor == valor.strip():
            return valor
        raise _ValorInvalido("non-empty text without leading or trailing spaces")
    if tipo == "date":
        if PATRON_FECHA.fullmatch(valor):
            try:
                return date.fromisoformat(valor)
            except ValueError:
                pass
        raise _ValorInvalido("an existing ISO date YYYY-MM-DD")
    if tipo == "int":
        if PATRON_ENTERO.fullmatch(valor):
            return int(valor)
        raise _ValorInvalido("a non-negative integer")
    if tipo == "decimal(18,2)":
        if PATRON_DECIMAL.fullmatch(valor):
            return Decimal(valor)
        raise _ValorInvalido("a decimal with at most two fraction digits")
    raise ValueError(f"unsupported type {tipo!r}")


def _convertir_referencia(
    prefijo: str, base: str, filas: Sequence[tuple[str, ...]]
) -> list[tuple[Any, ...]]:
    tabla = nombre_tabla(prefijo, "bronze", base)
    columnas = COLUMNAS_REFERENCIA[base]
    convertidas: list[tuple[Any, ...]] = []
    for numero, fila in enumerate(filas, start=1):
        valores = []
        for (columna, tipo), valor in zip(columnas, fila):
            try:
                valores.append(_convertir(tipo, valor))
            except _ValorInvalido as exc:
                raise ValueError(
                    f"{tabla}: row {numero} ({columnas[0][0]}={fila[0]!r}), "
                    f"column {columna}: expected {exc}; observed {valor!r}"
                ) from None
        convertidas.append(tuple(valores))

    claves = [fila[0] for fila in convertidas]
    if len(set(claves)) != len(claves):
        repetida = next(c for c, veces in Counter(claves).items() if veces > 1)
        raise ValueError(
            f"{tabla}: expected unique {columnas[0][0]}; observed duplicate {repetida!r}"
        )
    convertidas.sort(key=lambda fila: fila[0])
    return convertidas


def _parsear_fecha_hora(texto: str) -> datetime | None:
    if not PATRON_FECHA_HORA.fullmatch(texto):
        return None
    try:
        return datetime.strptime(texto, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None


def _separar_duplicadas(
    tabla: str, filas: Sequence[tuple[str, ...]]
) -> tuple[list[tuple[str, ...]], list[tuple[str, ...]]]:
    vistas: dict[str, tuple[str, ...]] = {}
    unicas: list[tuple[str, ...]] = []
    duplicadas: list[tuple[str, ...]] = []
    for fila in filas:
        previa = vistas.get(fila[0])
        if previa is None:
            vistas[fila[0]] = fila
            unicas.append(fila)
        elif previa == fila:
            duplicadas.append(fila)
        else:
            raise ValueError(
                f"{tabla}: expected identical rows for transaccion_id {fila[0]!r}; "
                "observed different contents"
            )
    return unicas, duplicadas


def _motivos(
    tabla: str, fila: tuple[str, ...], cuentas: set[str]
) -> tuple[list[str], datetime | None, Decimal]:
    transaccion_id, cuenta_id, fecha_hora, _, _, _, monto_texto, _, _ = fila
    if not PATRON_DECIMAL.fullmatch(monto_texto):
        raise ValueError(
            f"{tabla}: transaccion_id {transaccion_id!r}, column monto: expected "
            f"a decimal with at most two fraction digits; observed {monto_texto!r}"
        )
    monto = Decimal(monto_texto)
    momento = _parsear_fecha_hora(fecha_hora)
    motivos = []
    if cuenta_id not in cuentas:
        motivos.append("cuenta_inexistente")
    if momento is None:
        motivos.append("fecha_hora_invalida")
    if monto < 0:
        motivos.append("monto_negativo")
    return motivos, momento, monto


def _validar_transaccion_limpia(
    tabla: str, fila: tuple[str, ...], momento: datetime, monto: Decimal, canal: str
) -> None:
    transaccion_id, _, _, tipo, direccion, _, _, moneda, estado = fila
    esperado_direccion = DIRECCION_POR_TIPO.get(tipo)
    problemas = []
    if esperado_direccion is None or direccion != esperado_direccion:
        problemas.append(
            ("tipo_transaccion/direccion", f"{tipo!r}/{direccion!r}",
             "a known type with its matching direction")
        )
    if canal not in CANALES:
        problemas.append(("canal", repr(canal), f"one of {CANALES!r}"))
    if moneda != "CRC":
        problemas.append(("moneda", repr(moneda), "'CRC'"))
    if estado != "APLICADA":
        problemas.append(("estado", repr(estado), "'APLICADA'"))
    if not PERIODO_INICIO <= momento.date() <= PERIODO_FIN:
        problemas.append(
            ("fecha_hora", repr(fila[2]), f"a date from {PERIODO_INICIO} to {PERIODO_FIN}")
        )
    if monto <= 0:
        problemas.append(("monto", repr(fila[6]), "a positive amount"))
    if problemas:
        columna, observado, esperado = problemas[0]
        raise ValueError(
            f"{tabla}: transaccion_id {transaccion_id!r}, column {columna}: "
            f"expected {esperado}; observed {observado}"
        )


def transformar(
    bronce: Mapping[str, Sequence[tuple[str, ...]]], prefijo: str
) -> ResultadoPlata:
    """Aplica tipos y reglas de calidad sin escribir nada.

    `bronce` asocia cada tabla base con sus filas como tuplas de texto en el orden
    de columnas Bronze. Devuelve las nueve tablas de salida.
    """
    tablas: dict[str, TablaSalida] = {}
    for base, columnas in COLUMNAS_REFERENCIA.items():
        tablas[f"silver_{base}"] = TablaSalida(
            nombre=f"silver_{base}",
            columnas=columnas,
            filas=_convertir_referencia(prefijo, base, bronce[base]),
        )

    tabla_bronce = nombre_tabla(prefijo, "bronze", "transacciones")
    cuentas = {fila[0] for fila in tablas["silver_cuentas"].filas}
    unicas, duplicadas = _separar_duplicadas(tabla_bronce, bronce["transacciones"])

    limpias: list[tuple[Any, ...]] = []
    cuarentena: list[tuple[str, ...]] = []
    canal_normalizado = 0
    canal_vacio = 0
    for fila in unicas:
        motivos, momento, monto = _motivos(tabla_bronce, fila, cuentas)
        if len(motivos) > 1:
            raise ValueError(
                f"{tabla_bronce}: transaccion_id {fila[0]!r}: expected exactly one "
                f"quarantine reason; observed {motivos!r}"
            )
        if motivos:
            cuarentena.append(fila + (motivos[0],))
            continue

        canal_original = fila[5]
        canal = canal_original.strip().upper() or "NO_INFORMADO"
        _validar_transaccion_limpia(tabla_bronce, fila, momento, monto, canal)
        if canal_original == "":
            canal_vacio += 1
        elif canal_original != canal:
            canal_normalizado += 1
        limpias.append(
            (
                fila[0],
                fila[1],
                momento.replace(tzinfo=timezone.utc),
                momento.date(),
                fila[3],
                fila[4],
                canal,
                monto,
                fila[7],
                fila[8],
            )
        )

    limpias.sort(key=lambda fila: (fila[2], fila[0]))
    cuarentena.sort(key=lambda fila: (fila[-1], fila[0]))
    duplicadas.sort(key=lambda fila: fila[0])

    acumulado: dict[tuple[str, str], list[Any]] = {}
    for fila in limpias:
        mes = f"{fila[2].year:04d}-{fila[2].month:02d}"
        celda = acumulado.setdefault((mes, fila[6]), [0, Decimal("0.00"), Decimal("0.00")])
        celda[0] += 1
        celda[1 if fila[5] == "CREDITO" else 2] += fila[7]
    oro = [
        (mes, canal, celda[0], celda[1], celda[2])
        for (mes, canal), celda in sorted(acumulado.items())
    ]

    tablas["silver_transacciones"] = TablaSalida(
        "silver_transacciones", COLUMNAS_SILVER_TRANSACCIONES, limpias
    )
    tablas["silver_transacciones_cuarentena"] = TablaSalida(
        "silver_transacciones_cuarentena", COLUMNAS_CUARENTENA, cuarentena
    )
    tablas["silver_transacciones_duplicadas"] = TablaSalida(
        "silver_transacciones_duplicadas", COLUMNAS_TEXTO_TRANSACCIONES, duplicadas
    )
    tablas["gold_transacciones_mes_canal"] = TablaSalida(
        "gold_transacciones_mes_canal", COLUMNAS_ORO, oro
    )
    return ResultadoPlata(tablas, canal_normalizado, canal_vacio)


def medir_controles(resultado: ResultadoPlata) -> dict[str, Any]:
    tablas = resultado.tablas
    limpias = tablas["silver_transacciones"].filas
    oro = tablas["gold_transacciones_mes_canal"].filas

    def total(
        filas: Sequence[tuple[Any, ...]], indice: int, direccion: str | None = None
    ) -> str:
        suma = sum(
            (fila[indice] for fila in filas if direccion is None or fila[5] == direccion),
            Decimal("0.00"),
        )
        return f"{suma:.2f}"

    return {
        "filas": {nombre: len(tabla.filas) for nombre, tabla in tablas.items()},
        "cuarentena_por_motivo": dict(
            sorted(Counter(fila[-1] for fila in tablas["silver_transacciones_cuarentena"].filas).items())
        ),
        "transacciones_por_mes": dict(
            sorted(Counter(f"{fila[2].year:04d}-{fila[2].month:02d}" for fila in limpias).items())
        ),
        "transacciones_por_canal": dict(sorted(Counter(fila[6] for fila in limpias).items())),
        "canal_normalizado": resultado.canal_normalizado,
        "canal_vacio": resultado.canal_vacio,
        "monto_creditos": total(limpias, 7, "CREDITO"),
        "monto_debitos": total(limpias, 7, "DEBITO"),
        "oro_transacciones": sum(fila[2] for fila in oro),
        "oro_monto_creditos": total(oro, 3),
        "oro_monto_debitos": total(oro, 4),
    }


def verificar_controles(resultado: ResultadoPlata) -> dict[str, Any]:
    """Compara las mediciones con los valores de control; falla antes de escribir."""
    medidos = medir_controles(resultado)
    for clave, esperado in CONTROLES_ESPERADOS.items():
        if medidos[clave] != esperado:
            raise ValueError(
                f"control {clave}: expected {esperado!r}; observed {medidos[clave]!r}"
            )
    return medidos


def _validar_parametros_y_contexto(
    contexto: Mapping[str, Any],
    p_lakehouse_esperado: str,
    p_prefijo: str,
    p_confirmar_reemplazo: str,
) -> str:
    if p_confirmar_reemplazo != "SI":
        raise ValueError(
            "p_confirmar_reemplazo must be exactly 'SI' to replace the nine "
            "prefixed lab tables"
        )
    if not isinstance(p_prefijo, str) or PATRON_PREFIJO.fullmatch(p_prefijo) is None:
        raise ValueError(
            "p_prefijo must start with an ASCII letter and contain at most "
            "20 ASCII letters, digits, or underscores"
        )
    if not isinstance(p_lakehouse_esperado, str):
        raise ValueError("p_lakehouse_esperado must be a string")
    if not isinstance(contexto, Mapping):
        raise ValueError("notebook runtime context must be a mapping")

    for key in ("defaultLakehouseId", "defaultLakehouseWorkspaceId", "currentWorkspaceId"):
        value = contexto.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"notebook runtime context is missing {key}")

    lakehouse_name = contexto.get("defaultLakehouseName")
    if not isinstance(lakehouse_name, str) or not lakehouse_name.strip():
        raise ValueError("notebook runtime context is missing defaultLakehouseName")
    if p_lakehouse_esperado and p_lakehouse_esperado != lakehouse_name:
        raise ValueError(
            "p_lakehouse_esperado does not match the notebook default Lakehouse"
        )
    if contexto["currentWorkspaceId"] != contexto["defaultLakehouseWorkspaceId"]:
        raise ValueError(
            "the default Lakehouse and current notebook must be in the same workspace"
        )
    return lakehouse_name


def _esquema_observado(schema: Any) -> tuple[tuple[str, str], ...]:
    return tuple((campo.name, campo.dataType.simpleString()) for campo in schema.fields)


def _validar_schema(schema: Any, columnas: tuple[tuple[str, str], ...], tabla: str) -> None:
    if _esquema_observado(schema) != columnas:
        raise ValueError(
            f"{tabla}: expected columns {columnas!r}; "
            "observed an incompatible table schema"
        )


def _leer_bronce(spark: Any, prefijo: str) -> dict[str, list[tuple[str, ...]]]:
    bronce: dict[str, list[tuple[str, ...]]] = {}
    for base, esperado in BRONCE_CONTEOS.items():
        tabla = nombre_tabla(prefijo, "bronze", base)
        if not spark.catalog.tableExists(tabla):
            raise ValueError(f"{tabla}: expected an existing bronze table; observed missing")
        dataframe = spark.table(tabla)
        columnas = columnas_bronce(base)
        _validar_schema(
            dataframe.schema, tuple((columna, "string") for columna in columnas), tabla
        )
        observado = int(dataframe.count())
        if observado != esperado:
            raise ValueError(
                f"{tabla}: expected row count {esperado}; observed {observado}"
            )
        filas = [tuple(fila[columna] for columna in columnas) for fila in dataframe.collect()]
        for numero, fila in enumerate(filas, start=1):
            for columna, valor in zip(columnas, fila):
                if not isinstance(valor, str):
                    raise ValueError(
                        f"{tabla}: row {numero}, column {columna}: expected text; "
                        f"observed {valor!r}"
                    )
        bronce[base] = filas
    return bronce


def ejecutar_plata(
    spark: Any,
    contexto: Mapping[str, Any],
    p_lakehouse_esperado: str,
    p_prefijo: str,
    p_confirmar_reemplazo: str,
) -> dict[str, Any]:
    """Valida Bronze, transforma en memoria y escribe nueve tablas del Lakehouse.

    No escribe nada hasta que las seis tablas Bronze, los tipos, los controles y
    los esquemas de destino existentes han pasado. Informa exito solo despues de
    comprobar conteo, esquema y contenido de cada tabla persistida.
    """
    lakehouse_name = _validar_parametros_y_contexto(
        contexto,
        p_lakehouse_esperado,
        p_prefijo,
        p_confirmar_reemplazo,
    )
    bronce = _leer_bronce(spark, p_prefijo)
    resultado = transformar(bronce, p_prefijo)
    controles = verificar_controles(resultado)

    from pyspark.sql.types import (
        DateType,
        DecimalType,
        IntegerType,
        LongType,
        StringType,
        StructField,
        StructType,
        TimestampType,
    )

    tipos_spark = {
        "string": StringType(),
        "date": DateType(),
        "timestamp": TimestampType(),
        "int": IntegerType(),
        "bigint": LongType(),
        "decimal(18,2)": DecimalType(18, 2),
    }

    destinos: dict[str, str] = {}
    dataframes: dict[str, Any] = {}
    for nombre, tabla in resultado.tablas.items():
        capa, base = nombre.split("_", 1)
        destinos[nombre] = nombre_tabla(p_prefijo, capa, base)
        schema = StructType(
            [StructField(columna, tipos_spark[tipo], True) for columna, tipo in tabla.columnas]
        )
        dataframes[nombre] = spark.createDataFrame(tabla.filas, schema=schema)

    for nombre, tabla in resultado.tablas.items():
        destino = destinos[nombre]
        if spark.catalog.tableExists(destino):
            _validar_schema(spark.table(destino).schema, tabla.columnas, destino)

    informe_tablas: list[dict[str, Any]] = []
    for nombre, tabla in resultado.tablas.items():
        destino = destinos[nombre]
        esperado_df = dataframes[nombre]
        esperado_filas = len(tabla.filas)
        esperado_df.write.mode("overwrite").saveAsTable(destino)

        guardado = spark.table(destino)
        _validar_schema(guardado.schema, tabla.columnas, destino)
        observado = int(guardado.count())
        if observado != esperado_filas:
            raise ValueError(
                f"{destino}: expected table count {esperado_filas}; observed {observado}"
            )
        faltantes = esperado_df.exceptAll(guardado).limit(1).count()
        inesperadas = guardado.exceptAll(esperado_df).limit(1).count()
        if faltantes or inesperadas:
            raise ValueError(
                f"{destino}: expected the transformed row multiset; "
                "observed different persisted contents"
            )

        informe = {
            "lakehouse": lakehouse_name,
            "table": destino,
            "table_count": observado,
        }
        informe_tablas.append(informe)
        print(
            json.dumps(
                {"status": "table_validated", **informe},
                ensure_ascii=False,
                sort_keys=True,
            )
        )

    informe_final = {
        "status": "success",
        "lakehouse": lakehouse_name,
        "controls": controles,
        "tables": informe_tablas,
    }
    print(json.dumps(informe_final, ensure_ascii=False, sort_keys=True))
    return informe_final
