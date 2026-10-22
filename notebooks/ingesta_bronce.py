"""Carga estricta del conjunto didactico CSV a tablas Delta Bronze en Fabric.

La lectura con csv.DictReader en el driver es adecuada para este conjunto,
menor de 7 MB; no es una estrategia escalable para archivos de varios GB.
Las escrituras de varias tablas no son atomicas: un error puede dejar una
carga parcial. Despues de resolverlo, se debe volver a ejecutar el lote entero.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_BASE_PATH = Path("/lakehouse/default/Files/bronze/banca_sintetica")
PATRON_PREFIJO = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,19}\Z", re.ASCII)


@dataclass(frozen=True)
class FuenteEsperada:
    headers: tuple[str, ...]
    row_count: int
    sha256: str


@dataclass(frozen=True)
class FuenteCargada:
    headers: tuple[str, ...]
    rows: list[dict[str, str]]
    row_count: int
    sha256: str


FUENTES: dict[str, FuenteEsperada] = {
    "clientes.csv": FuenteEsperada(
        headers=(
            "cliente_id",
            "nombre_sintetico",
            "fecha_alta",
            "segmento",
            "grupo_edad",
            "provincia",
            "sucursal_id",
        ),
        row_count=1200,
        sha256="aa08d19a3a308922aa7748fe42a7aa64e9259df6fb307c313e7c2882cac7fbf0",
    ),
    "cuentas.csv": FuenteEsperada(
        headers=(
            "cuenta_id",
            "cliente_id",
            "producto_id",
            "fecha_apertura",
            "moneda",
            "saldo_inicial",
        ),
        row_count=1800,
        sha256="4564835b8a8a289683ddf1f0adb8521b629e4ad1344787018661b8f1b8b57126",
    ),
    "sucursales.csv": FuenteEsperada(
        headers=("sucursal_id", "nombre_sintetico", "provincia"),
        row_count=7,
        sha256="18f33bcc3c946ac3d2533af016c774437bacc34caafcad1ce037f2e24ff3a334",
    ),
    "productos.csv": FuenteEsperada(
        headers=("producto_id", "nombre_sintetico", "familia", "moneda"),
        row_count=5,
        sha256="f1bb632b70d87de163f0e22e16c776911e6803b550a2f7d2f70fe9260cccbd2f",
    ),
    "calendario.csv": FuenteEsperada(
        headers=(
            "fecha",
            "anio",
            "trimestre",
            "mes",
            "nombre_mes",
            "dia_mes",
            "dia_semana",
            "nombre_dia",
            "es_fin_semana",
        ),
        row_count=183,
        sha256="d4210301ed071b42e20ef7ee040625610df94a1f82098a08a1c921f1e88773d8",
    ),
    "transacciones.csv": FuenteEsperada(
        headers=(
            "transaccion_id",
            "cuenta_id",
            "fecha_hora",
            "tipo_transaccion",
            "direccion",
            "canal",
            "monto",
            "moneda",
            "estado",
        ),
        row_count=72360,
        sha256="3d98785e9fa9d0ec1c3e0ad80c57b6ee1ae393ddb1659e3bfd79b7f37088229a",
    ),
}


def cargar_fuentes(
    base_path: str | Path = DEFAULT_BASE_PATH,
) -> dict[str, FuenteCargada]:
    """Valida la version fijada y devuelve las filas sin normalizar ni castear."""
    base = Path(base_path)
    cargadas: dict[str, FuenteCargada] = {}

    for filename, esperada in FUENTES.items():
        source_path = base / filename
        try:
            contenido = source_path.read_bytes()
        except FileNotFoundError as exc:
            raise ValueError(
                f"{filename}: expected readable source file; observed missing"
            ) from exc

        digest = hashlib.sha256(contenido).hexdigest()
        if digest != esperada.sha256:
            raise ValueError(
                f"{filename}: expected SHA-256 {esperada.sha256}; observed {digest}"
            )

        filas: list[dict[str, str]] = []
        try:
            with source_path.open("r", encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream, strict=True)
                observed_headers = tuple(reader.fieldnames or ())
                if observed_headers != esperada.headers:
                    raise ValueError(
                        f"{filename}: expected headers {esperada.headers!r}; "
                        f"observed {observed_headers!r}"
                    )

                for row in reader:
                    extra_values = row.get(None)
                    missing_values = [
                        header
                        for header in esperada.headers
                        if row.get(header) is None
                    ]
                    if extra_values is not None or missing_values:
                        extra_width = (
                            len(extra_values)
                            if isinstance(extra_values, list)
                            else 0
                        )
                        observed_width = (
                            len(esperada.headers) + extra_width - len(missing_values)
                        )
                        raise ValueError(
                            f"{filename}: expected {len(esperada.headers)} columns; "
                            f"observed {observed_width}"
                        )
                    filas.append(
                        {header: row[header] for header in esperada.headers}
                    )
        except csv.Error as exc:
            raise ValueError(
                f"{filename}: expected strict CSV with "
                f"{len(esperada.headers)} columns; observed parse error: {exc}"
            ) from exc

        observed_count = len(filas)
        if observed_count != esperada.row_count:
            raise ValueError(
                f"{filename}: expected row count {esperada.row_count}; "
                f"observed {observed_count}"
            )

        cargadas[filename] = FuenteCargada(
            headers=esperada.headers,
            rows=filas,
            row_count=observed_count,
            sha256=digest,
        )

    return cargadas


def _validar_parametros_y_contexto(
    contexto: Mapping[str, Any],
    p_lakehouse_esperado: str,
    p_prefijo: str,
    p_confirmar_reemplazo: str,
) -> str:
    if p_confirmar_reemplazo != "SI":
        raise ValueError(
            "p_confirmar_reemplazo must be exactly 'SI' to replace the six "
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

    required_ids = (
        "defaultLakehouseId",
        "defaultLakehouseWorkspaceId",
        "currentWorkspaceId",
    )
    for key in required_ids:
        value = contexto.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"notebook runtime context is missing {key}")

    lakehouse_name = contexto.get("defaultLakehouseName")
    if not isinstance(lakehouse_name, str) or not lakehouse_name.strip():
        raise ValueError(
            "notebook runtime context is missing defaultLakehouseName"
        )
    if (
        p_lakehouse_esperado
        and p_lakehouse_esperado != lakehouse_name
    ):
        raise ValueError(
            "p_lakehouse_esperado does not match the notebook default Lakehouse"
        )
    if contexto["currentWorkspaceId"] != contexto["defaultLakehouseWorkspaceId"]:
        raise ValueError(
            "the default Lakehouse and current notebook must be in the same workspace"
        )

    return lakehouse_name


def _validar_schema(schema: Any, headers: tuple[str, ...], table_name: str, string_type: Any) -> None:
    observed_columns = tuple(field.name for field in schema.fields)
    observed_are_strings = all(
        isinstance(field.dataType, string_type) for field in schema.fields
    )
    if observed_columns != headers or not observed_are_strings:
        raise ValueError(
            f"{table_name}: expected columns {headers!r} with all StringType; "
            "observed an incompatible table schema"
        )


def ejecutar_ingesta(
    spark: Any,
    contexto: Mapping[str, Any],
    p_lakehouse_esperado: str,
    p_prefijo: str,
    p_confirmar_reemplazo: str,
    base_path: str | Path = DEFAULT_BASE_PATH,
) -> dict[str, Any]:
    """Preflight all sources, then overwrite and verify six default-Lakehouse tables.

    Returns and prints a success report only after all six table counts, schemas,
    and duplicate-preserving row multisets match their validated CSV sources.
    """
    lakehouse_name = _validar_parametros_y_contexto(
        contexto,
        p_lakehouse_esperado,
        p_prefijo,
        p_confirmar_reemplazo,
    )
    fuentes = cargar_fuentes(base_path)

    from pyspark.sql.types import StringType, StructField, StructType

    schemas: dict[str, Any] = {}
    dataframes: dict[str, Any] = {}
    table_names: dict[str, str] = {}
    for filename, fuente in fuentes.items():
        target = f"{p_prefijo.lower()}_bronze_{Path(filename).stem}"
        table_names[filename] = target
        schema = StructType(
            [StructField(column, StringType(), True) for column in fuente.headers]
        )
        schemas[filename] = schema
        rows = [
            tuple(row[column] for column in fuente.headers)
            for row in fuente.rows
        ]
        dataframes[filename] = spark.createDataFrame(rows, schema=schema)

    for filename, fuente in fuentes.items():
        target = table_names[filename]
        if spark.catalog.tableExists(target):
            _validar_schema(
                spark.table(target).schema,
                fuente.headers,
                target,
                StringType,
            )

    report_tables: list[dict[str, Any]] = []
    for filename, fuente in fuentes.items():
        target = table_names[filename]
        source_df = dataframes[filename]
        source_df.write.mode("overwrite").saveAsTable(target)

        stored_df = spark.table(target)
        _validar_schema(stored_df.schema, fuente.headers, target, StringType)
        table_count = int(stored_df.count())
        if table_count != fuente.row_count:
            raise ValueError(
                f"{target}: expected table count {fuente.row_count}; "
                f"observed {table_count}"
            )

        missing_from_table = source_df.exceptAll(stored_df).limit(1).count()
        unexpected_in_table = stored_df.exceptAll(source_df).limit(1).count()
        if missing_from_table or unexpected_in_table:
            raise ValueError(
                f"{target}: expected the source row multiset from {filename}; "
                "observed different persisted contents"
            )

        table_report = {
            "lakehouse": lakehouse_name,
            "source_file": filename,
            "source_sha": fuente.sha256,
            "source_count": fuente.row_count,
            "table": target,
            "table_count": table_count,
        }
        report_tables.append(table_report)
        print(
            json.dumps(
                {"status": "table_validated", **table_report},
                ensure_ascii=False,
                sort_keys=True,
            )
        )

    final_report = {
        "status": "success",
        "lakehouse": lakehouse_name,
        "tables": report_tables,
    }
    print(json.dumps(final_report, ensure_ascii=False, sort_keys=True))
    return final_report
