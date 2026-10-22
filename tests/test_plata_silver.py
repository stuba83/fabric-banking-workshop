from __future__ import annotations

import calendar
import contextlib
import csv
import io
import json
import subprocess
import sys
import types
import unittest
from collections import Counter
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from notebooks import plata_silver


DATASET = ROOT / "dataset" / "csv"
MANIFEST = ROOT / "dataset" / "manifiesto.json"
VALID_CONTEXT = {
    "defaultLakehouseName": "AB_Lakehouse",
    "defaultLakehouseId": "lakehouse-id",
    "defaultLakehouseWorkspaceId": "workspace-id",
    "currentWorkspaceId": "workspace-id",
}
NINE_TABLES = {
    f"ab_{name}" for name in plata_silver.CONTROLES_ESPERADOS["filas"]
}

_BRONCE_CACHE: dict[str, list[tuple[str, ...]]] = {}


def bronce_real() -> dict[str, list[tuple[str, ...]]]:
    if not _BRONCE_CACHE:
        for base in plata_silver.BRONCE_CONTEOS:
            columnas = plata_silver.columnas_bronce(base)
            with (DATASET / f"{base}.csv").open(
                "r", encoding="utf-8-sig", newline=""
            ) as stream:
                _BRONCE_CACHE[base] = [
                    tuple(row[columna] for columna in columnas)
                    for row in csv.DictReader(stream)
                ]
    return {base: list(filas) for base, filas in _BRONCE_CACHE.items()}


def datos_minimos() -> dict[str, list[tuple[str, ...]]]:
    return {
        "clientes": [
            ("CLI1", "Cliente sintetico 0001", "2023-07-01", "ASALARIADO", "18-29",
             "Heredia", "SUC01")
        ],
        "cuentas": [("CTA1", "CLI1", "PRD01", "2025-01-19", "CRC", "1000.00")],
        "sucursales": [("SUC01", "Sucursal sintetica", "Heredia")],
        "productos": [("PRD01", "Ahorro sintetico", "AHORRO", "CRC")],
        "calendario": [
            ("2026-04-01", "2026", "2", "4", "abril", "1", "3", "miercoles", "0")
        ],
        "transacciones": [
            ("TX1", "CTA1", "2026-04-01T08:00:00", "DEPOSITO", "CREDITO", "  atm  ",
             "100.50", "CRC", "APLICADA")
        ],
    }


class FakeType:
    def __init__(self, simple: str) -> None:
        self.simple = simple

    def simpleString(self) -> str:
        return self.simple


class FakeStructField:
    def __init__(self, name: str, data_type: FakeType, nullable: bool) -> None:
        self.name = name
        self.dataType = data_type
        self.nullable = nullable


class FakeStructType:
    def __init__(self, fields: list[FakeStructField]) -> None:
        self.fields = fields


class FakeRow:
    def __init__(self, names: list[str], values: tuple[object, ...]) -> None:
        self.mapping = dict(zip(names, values))

    def __getitem__(self, name: str) -> object:
        return self.mapping[name]


class FakeDataFrame:
    def __init__(self, rows: list[tuple[object, ...]], schema: FakeStructType) -> None:
        self.rows = list(rows)
        self.schema = schema
        self.write = FakeWriter(self)
        self.spark: FakeSpark | None = None

    def count(self) -> int:
        return len(self.rows)

    def collect(self) -> list[FakeRow]:
        names = [field.name for field in self.schema.fields]
        return [FakeRow(names, row) for row in self.rows]

    def exceptAll(self, other: FakeDataFrame) -> FakeDataFrame:
        difference = Counter(self.rows) - Counter(other.rows)
        return FakeDataFrame(list(difference.elements()), self.schema)

    def limit(self, count: int) -> FakeDataFrame:
        return FakeDataFrame(self.rows[:count], self.schema)


class FakeWriter:
    def __init__(self, dataframe: FakeDataFrame) -> None:
        self.dataframe = dataframe
        self.mode_name: str | None = None

    def mode(self, mode_name: str) -> FakeWriter:
        self.mode_name = mode_name
        return self

    def saveAsTable(self, table_name: str) -> None:
        if self.mode_name != "overwrite":
            raise AssertionError("the writer must use overwrite mode")
        spark = self.dataframe.spark
        spark.write_events.append(table_name)
        rows = list(self.dataframe.rows)
        if table_name in spark.drop_row_in:
            rows = rows[:-1]
        if table_name in spark.alter_row_in:
            rows[0] = tuple("changed" if index == 0 else value
                            for index, value in enumerate(rows[0]))
        spark.tables[table_name] = FakeDataFrame(rows, self.dataframe.schema)


class FakeCatalog:
    def __init__(self, spark: FakeSpark) -> None:
        self.spark = spark

    def tableExists(self, table_name: str) -> bool:
        return table_name in self.spark.tables


class FakeSpark:
    def __init__(self) -> None:
        self.tables: dict[str, FakeDataFrame] = {}
        self.write_events: list[str] = []
        self.drop_row_in: set[str] = set()
        self.alter_row_in: set[str] = set()
        self.catalog = FakeCatalog(self)

    def createDataFrame(
        self, rows: list[tuple[object, ...]], schema: FakeStructType
    ) -> FakeDataFrame:
        dataframe = FakeDataFrame(rows, schema)
        dataframe.spark = self
        return dataframe

    def table(self, table_name: str) -> FakeDataFrame:
        dataframe = self.tables[table_name]
        dataframe.spark = self
        return dataframe


def _type_factory(simple: str):
    return lambda *args: FakeType(simple)


def _fake_pyspark_modules() -> dict[str, types.ModuleType]:
    pyspark = types.ModuleType("pyspark")
    sql = types.ModuleType("pyspark.sql")
    sql_types = types.ModuleType("pyspark.sql.types")
    sql_types.StringType = _type_factory("string")
    sql_types.DateType = _type_factory("date")
    sql_types.TimestampType = _type_factory("timestamp")
    sql_types.IntegerType = _type_factory("int")
    sql_types.LongType = _type_factory("bigint")
    sql_types.DecimalType = lambda precision, scale: FakeType(
        f"decimal({precision},{scale})"
    )
    sql_types.StructField = FakeStructField
    sql_types.StructType = FakeStructType
    pyspark.sql = sql
    sql.types = sql_types
    return {"pyspark": pyspark, "pyspark.sql": sql, "pyspark.sql.types": sql_types}


def _bronze_schema(base: str) -> FakeStructType:
    return FakeStructType(
        [
            FakeStructField(columna, FakeType("string"), True)
            for columna in plata_silver.columnas_bronce(base)
        ]
    )


def spark_con_bronce(
    bronce: dict[str, list[tuple[str, ...]]] | None = None,
) -> FakeSpark:
    spark = FakeSpark()
    for base, filas in (bronce or bronce_real()).items():
        spark.tables[f"ab_bronze_{base}"] = FakeDataFrame(filas, _bronze_schema(base))
    return spark


def ejecutar(spark: FakeSpark, confirmacion: str = "SI") -> dict[str, object]:
    with patch.dict(sys.modules, _fake_pyspark_modules()):
        with contextlib.redirect_stdout(io.StringIO()):
            return plata_silver.ejecutar_plata(
                spark, VALID_CONTEXT, "AB_Lakehouse", "AB", confirmacion
            )


class ForbiddenSpark:
    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"Spark must not be touched: {name}")


class TransformarConDatosRealesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.bronce = bronce_real()
        cls.resultado = plata_silver.transformar(cls.bronce, "AB")

    def test_all_controls_pass_and_match_the_manifest(self) -> None:
        medidos = plata_silver.verificar_controles(self.resultado)
        cleaning = self.manifest["expected_cleaning"]
        analytics = self.manifest["expected_analytics"]
        accounting = self.manifest["expected_accounting"]
        filas = medidos["filas"]
        self.assertEqual(filas["silver_transacciones"], cleaning["clean"])
        self.assertEqual(filas["silver_transacciones_cuarentena"], cleaning["quarantine"])
        self.assertEqual(filas["silver_transacciones_duplicadas"], cleaning["duplicates"])
        self.assertEqual(
            medidos["cuarentena_por_motivo"],
            {
                "cuenta_inexistente": cleaning["quarantine_by_reason"]["invalid_account"],
                "fecha_hora_invalida": cleaning["quarantine_by_reason"]["invalid_timestamp"],
                "monto_negativo": cleaning["quarantine_by_reason"]["negative_amount"],
            },
        )
        self.assertEqual(medidos["transacciones_por_mes"], analytics["monthly_transaction_counts"])
        self.assertEqual(
            medidos["transacciones_por_canal"], analytics["normalized_channel_counts"]
        )
        self.assertEqual(medidos["canal_normalizado"], cleaning["normalize"])
        self.assertEqual(medidos["canal_vacio"], cleaning["blanks"])
        self.assertEqual(medidos["monto_creditos"], accounting["credit_crc"])
        self.assertEqual(medidos["monto_debitos"], accounting["debit_crc"])
        self.assertEqual(medidos["oro_monto_creditos"], accounting["credit_crc"])
        self.assertEqual(medidos["oro_monto_debitos"], accounting["debit_crc"])

    def test_bronze_arithmetic_closes(self) -> None:
        tablas = self.resultado.tablas
        self.assertEqual(
            len(self.bronce["transacciones"])
            - len(tablas["silver_transacciones_duplicadas"].filas)
            - len(tablas["silver_transacciones_cuarentena"].filas),
            len(tablas["silver_transacciones"].filas),
        )

    def test_every_bronze_row_lands_in_exactly_one_place(self) -> None:
        tablas = self.resultado.tablas
        silver_ids = [fila[0] for fila in tablas["silver_transacciones"].filas]
        quarantine_ids = [fila[0] for fila in tablas["silver_transacciones_cuarentena"].filas]
        duplicate_ids = {fila[0] for fila in tablas["silver_transacciones_duplicadas"].filas}
        self.assertEqual(len(silver_ids), len(set(silver_ids)))
        self.assertFalse(set(silver_ids) & set(quarantine_ids))
        self.assertEqual(
            set(silver_ids) | set(quarantine_ids),
            {fila[0] for fila in self.bronce["transacciones"]},
        )
        self.assertTrue(duplicate_ids <= set(silver_ids))
        duplicadas = tablas["silver_transacciones_duplicadas"].filas
        self.assertTrue(
            all(tuple(fila) in set(self.bronce["transacciones"]) for fila in duplicadas)
        )

    def test_quarantine_keeps_original_text_with_exactly_one_reason(self) -> None:
        cuarentena = self.resultado.tablas["silver_transacciones_cuarentena"].filas
        originales = {fila[0]: fila for fila in self.bronce["transacciones"]}
        for fila in cuarentena:
            self.assertEqual(len(fila), 10)
            self.assertIn(fila[-1], plata_silver.MOTIVOS)
            self.assertEqual(fila[:-1], originales[fila[0]])
        self.assertEqual(
            [fila[-1] for fila in cuarentena],
            sorted(fila[-1] for fila in cuarentena),
        )

    def test_types_and_costa_rica_wall_clock_are_preserved(self) -> None:
        originales = {fila[0]: fila for fila in self.bronce["transacciones"]}
        for fila in self.resultado.tablas["silver_transacciones"].filas:
            momento = fila[2]
            self.assertIsInstance(momento, datetime)
            self.assertIs(momento.tzinfo, timezone.utc)
            self.assertEqual(fila[3], momento.date())
            self.assertIsInstance(fila[7], Decimal)
            texto = originales[fila[0]][2]
            self.assertEqual(momento.strftime("%Y-%m-%dT%H:%M:%S"), texto)
            self.assertEqual(
                int(momento.timestamp()),
                calendar.timegm(datetime.strptime(texto, "%Y-%m-%dT%H:%M:%S").timetuple()),
            )
        primer_calendario = self.resultado.tablas["silver_calendario"].filas[0]
        self.assertEqual(primer_calendario[0], date(2026, 4, 1))
        self.assertEqual(primer_calendario[1:4], (2026, 2, 4))
        self.assertIsInstance(
            self.resultado.tablas["silver_cuentas"].filas[0][5], Decimal
        )

    def test_channels_are_normalized_and_blank_becomes_not_informed(self) -> None:
        canales = Counter(
            fila[6] for fila in self.resultado.tablas["silver_transacciones"].filas
        )
        self.assertEqual(set(canales), set(plata_silver.CANALES))
        self.assertEqual(canales["NO_INFORMADO"], 360)

    def test_gold_table_has_one_row_per_month_and_channel(self) -> None:
        oro = self.resultado.tablas["gold_transacciones_mes_canal"].filas
        self.assertEqual(len(oro), 30)
        self.assertEqual(len({(fila[0], fila[1]) for fila in oro}), 30)
        self.assertEqual(oro, sorted(oro))
        self.assertEqual(sum(fila[2] for fila in oro), 72000)
        self.assertEqual({fila[0] for fila in oro}, set(
            self.manifest["expected_analytics"]["monthly_transaction_counts"]
        ))

    def test_source_rows_and_inputs_are_not_modified(self) -> None:
        self.assertEqual(self.bronce, bronce_real())


class TransformarCasosDeErrorTests(unittest.TestCase):
    def test_minimal_valid_data_transforms(self) -> None:
        resultado = plata_silver.transformar(datos_minimos(), "AB")
        fila = resultado.tablas["silver_transacciones"].filas[0]
        self.assertEqual(fila[6], "ATM")
        self.assertEqual(fila[7], Decimal("100.50"))
        self.assertEqual(resultado.canal_normalizado, 1)
        self.assertEqual(resultado.canal_vacio, 0)

    def test_blank_channel_is_kept_as_not_informed(self) -> None:
        datos = datos_minimos()
        fila = list(datos["transacciones"][0])
        fila[5] = ""
        datos["transacciones"] = [tuple(fila)]
        resultado = plata_silver.transformar(datos, "AB")
        self.assertEqual(resultado.tablas["silver_transacciones"].filas[0][6], "NO_INFORMADO")
        self.assertEqual(resultado.canal_vacio, 1)
        self.assertEqual(resultado.canal_normalizado, 0)

    def test_exact_copy_is_retired_but_different_copy_fails(self) -> None:
        datos = datos_minimos()
        datos["transacciones"] = datos["transacciones"] * 2
        resultado = plata_silver.transformar(datos, "AB")
        self.assertEqual(len(resultado.tablas["silver_transacciones"].filas), 1)
        self.assertEqual(len(resultado.tablas["silver_transacciones_duplicadas"].filas), 1)

        distinta = list(datos_minimos()["transacciones"][0])
        distinta[6] = "200.00"
        datos["transacciones"] = datos_minimos()["transacciones"] + [tuple(distinta)]
        with self.assertRaisesRegex(ValueError, "expected identical rows.*'TX1'"):
            plata_silver.transformar(datos, "AB")

    def test_each_invalid_record_gets_its_single_reason(self) -> None:
        casos = {
            "cuenta_inexistente": {1: "CTA_NO_EXISTE"},
            "fecha_hora_invalida": {2: "2026-09-31T25:61:00"},
            "monto_negativo": {6: "-10.00"},
        }
        for motivo, cambios in casos.items():
            with self.subTest(motivo=motivo):
                datos = datos_minimos()
                fila = list(datos["transacciones"][0])
                for indice, valor in cambios.items():
                    fila[indice] = valor
                datos["transacciones"] = [tuple(fila)]
                resultado = plata_silver.transformar(datos, "AB")
                self.assertEqual(resultado.tablas["silver_transacciones"].filas, [])
                self.assertEqual(
                    [fila[-1] for fila in resultado.tablas["silver_transacciones_cuarentena"].filas],
                    [motivo],
                )

    def test_a_record_with_two_reasons_fails_instead_of_picking_one(self) -> None:
        datos = datos_minimos()
        fila = list(datos["transacciones"][0])
        fila[1], fila[6] = "CTA_NO_EXISTE", "-10.00"
        datos["transacciones"] = [tuple(fila)]
        with self.assertRaisesRegex(ValueError, "exactly one quarantine reason"):
            plata_silver.transformar(datos, "AB")

    def test_unexpected_values_stop_the_run_instead_of_being_set_aside(self) -> None:
        casos = {
            "currency": (7, "USD"),
            "state": (8, "ANULADA"),
            "channel": (5, "telefono"),
            "type": (3, "OTRO"),
            "direction": (4, "DEBITO"),
            "out of period": (2, "2027-01-01T08:00:00"),
            "zero amount": (6, "0.00"),
            "non numeric amount": (6, "abc"),
            "three decimals": (6, "1.234"),
        }
        for nombre, (indice, valor) in casos.items():
            with self.subTest(caso=nombre):
                datos = datos_minimos()
                fila = list(datos["transacciones"][0])
                fila[indice] = valor
                datos["transacciones"] = [tuple(fila)]
                with self.assertRaises(ValueError) as raised:
                    plata_silver.transformar(datos, "AB")
                self.assertIn("TX1", str(raised.exception))
                self.assertIn("expected", str(raised.exception))
                self.assertIn("observed", str(raised.exception))

    def test_reference_conversion_errors_name_table_key_column_and_value(self) -> None:
        casos = [
            ("clientes", 0, 2, "2026-13-45", "ab_bronze_clientes", "CLI1", "fecha_alta"),
            ("cuentas", 0, 5, "mil", "ab_bronze_cuentas", "CTA1", "saldo_inicial"),
            ("calendario", 0, 1, "20x6", "ab_bronze_calendario", "2026-04-01", "anio"),
            ("sucursales", 0, 1, "", "ab_bronze_sucursales", "SUC01", "nombre_sintetico"),
            ("productos", 0, 2, " AHORRO", "ab_bronze_productos", "PRD01", "familia"),
        ]
        for base, fila_idx, col_idx, valor, tabla, clave, columna in casos:
            with self.subTest(tabla=tabla):
                datos = datos_minimos()
                fila = list(datos[base][fila_idx])
                fila[col_idx] = valor
                datos[base] = [tuple(fila)]
                with self.assertRaises(ValueError) as raised:
                    plata_silver.transformar(datos, "AB")
                mensaje = str(raised.exception)
                for esperado in (tabla, repr(clave), f"column {columna}", "expected",
                                 f"observed {valor!r}"):
                    self.assertIn(esperado, mensaje)

    def test_duplicate_reference_key_fails(self) -> None:
        datos = datos_minimos()
        datos["cuentas"] = datos["cuentas"] * 2
        with self.assertRaisesRegex(ValueError, "expected unique cuenta_id.*'CTA1'"):
            plata_silver.transformar(datos, "AB")

    def test_changed_control_values_report_expected_and_observed(self) -> None:
        resultado = plata_silver.transformar(bronce_real(), "AB")
        tablas = dict(resultado.tablas)
        silver = tablas["silver_transacciones"]
        tablas["silver_transacciones"] = type(silver)(
            silver.nombre, silver.columnas, silver.filas[:-1]
        )
        alterado = type(resultado)(tablas, resultado.canal_normalizado, resultado.canal_vacio)
        with self.assertRaisesRegex(ValueError, "control filas: expected"):
            plata_silver.verificar_controles(alterado)


class EjecutarPlataTests(unittest.TestCase):
    def test_bad_parameters_or_runtime_context_never_reach_spark(self) -> None:
        sin_id = {k: v for k, v in VALID_CONTEXT.items() if k != "defaultLakehouseId"}
        casos = [
            (VALID_CONTEXT, "AB_Lakehouse", "AB", "NO"),
            (VALID_CONTEXT, "AB_Lakehouse", "AB", "si"),
            (VALID_CONTEXT, "AB_Lakehouse", "", "SI"),
            (VALID_CONTEXT, "AB_Lakehouse", "1AB", "SI"),
            (VALID_CONTEXT, "AB_Lakehouse", "A" * 21, "SI"),
            (VALID_CONTEXT, "OTHER", "AB", "SI"),
            (sin_id, "AB_Lakehouse", "AB", "SI"),
            ({**VALID_CONTEXT, "currentWorkspaceId": "other"}, "AB_Lakehouse", "AB", "SI"),
        ]
        for contexto, esperado, prefijo, confirmacion in casos:
            with self.subTest(prefijo=prefijo, confirmacion=confirmacion, esperado=esperado):
                with self.assertRaises(ValueError):
                    plata_silver.ejecutar_plata(
                        ForbiddenSpark(), contexto, esperado, prefijo, confirmacion
                    )

    def test_successful_run_writes_exactly_nine_tables_and_leaves_bronze_alone(self) -> None:
        spark = spark_con_bronce()
        bronce_antes = {nombre: list(df.rows) for nombre, df in spark.tables.items()}
        informe = ejecutar(spark)

        self.assertEqual(informe["status"], "success")
        self.assertEqual(informe["lakehouse"], "AB_Lakehouse")
        self.assertEqual(set(spark.write_events), NINE_TABLES)
        self.assertEqual(len(spark.write_events), 9)
        for nombre, esperado in plata_silver.CONTROLES_ESPERADOS["filas"].items():
            self.assertEqual(spark.tables[f"ab_{nombre}"].count(), esperado, nombre)
        self.assertEqual(
            {nombre: df.rows for nombre, df in spark.tables.items() if nombre.startswith("ab_bronze_")},
            bronce_antes,
        )
        self.assertEqual(spark.tables["ab_bronze_transacciones"].count(), 72360)
        self.assertEqual(
            {tabla["table"]: tabla["table_count"] for tabla in informe["tables"]},
            {f"ab_{n}": c for n, c in plata_silver.CONTROLES_ESPERADOS["filas"].items()},
        )
        self.assertEqual(informe["controls"]["monto_creditos"], "14976153627.79")
        json.dumps(informe)

    def test_rerun_replaces_tables_without_duplicating_rows(self) -> None:
        spark = spark_con_bronce()
        ejecutar(spark)
        ejecutar(spark)
        self.assertEqual(len(spark.write_events), 18)
        self.assertEqual(
            Counter(spark.write_events), Counter({tabla: 2 for tabla in NINE_TABLES})
        )
        self.assertEqual(spark.tables["ab_silver_transacciones"].count(), 72000)
        self.assertEqual(spark.tables["ab_gold_transacciones_mes_canal"].count(), 30)

    def test_denied_confirmation_does_not_change_existing_tables(self) -> None:
        spark = spark_con_bronce()
        ejecutar(spark)
        antes = {nombre: list(df.rows) for nombre, df in spark.tables.items()}
        escrituras = len(spark.write_events)
        with self.assertRaisesRegex(ValueError, "p_confirmar_reemplazo must be exactly 'SI'"):
            ejecutar(spark, "NO")
        self.assertEqual(len(spark.write_events), escrituras)
        self.assertEqual({n: df.rows for n, df in spark.tables.items()}, antes)

    def test_missing_bronze_table_fails_before_any_write(self) -> None:
        spark = spark_con_bronce()
        del spark.tables["ab_bronze_calendario"]
        with self.assertRaisesRegex(ValueError, "ab_bronze_calendario.*expected an existing"):
            ejecutar(spark)
        self.assertEqual(spark.write_events, [])

    def test_bronze_with_other_row_count_fails_before_any_write(self) -> None:
        bronce = bronce_real()
        bronce["transacciones"] = bronce["transacciones"][:-1]
        spark = spark_con_bronce(bronce)
        with self.assertRaisesRegex(
            ValueError, "ab_bronze_transacciones: expected row count 72360; observed 72359"
        ):
            ejecutar(spark)
        self.assertEqual(spark.write_events, [])

    def test_bronze_with_typed_columns_fails_before_any_write(self) -> None:
        spark = spark_con_bronce()
        schema = FakeStructType(
            [FakeStructField("cliente_id", FakeType("int"), True)]
        )
        spark.tables["ab_bronze_clientes"] = FakeDataFrame([], schema)
        with self.assertRaisesRegex(ValueError, "incompatible table schema"):
            ejecutar(spark)
        self.assertEqual(spark.write_events, [])

    def test_bronze_null_value_fails_before_any_write(self) -> None:
        bronce = bronce_real()
        fila = list(bronce["sucursales"][0])
        fila[1] = None
        bronce["sucursales"][0] = tuple(fila)
        spark = spark_con_bronce(bronce)
        with self.assertRaisesRegex(ValueError, "ab_bronze_sucursales: row 1, column nombre_sintetico"):
            ejecutar(spark)
        self.assertEqual(spark.write_events, [])

    def test_changed_bronze_content_fails_a_control_before_any_write(self) -> None:
        bronce = bronce_real()
        limpios = {
            fila[0]
            for fila in plata_silver.transformar(bronce, "AB").tablas["silver_transacciones"].filas
        }
        veces = Counter(fila[0] for fila in bronce["transacciones"])
        indice = next(
            i for i, fila in enumerate(bronce["transacciones"])
            if fila[4] == "CREDITO" and fila[0] in limpios and veces[fila[0]] == 1
        )
        fila = list(bronce["transacciones"][indice])
        fila[6] = str(Decimal(fila[6]) + Decimal("0.01"))
        bronce["transacciones"][indice] = tuple(fila)
        spark = spark_con_bronce(bronce)
        with self.assertRaisesRegex(ValueError, "control monto_creditos: expected"):
            ejecutar(spark)
        self.assertEqual(spark.write_events, [])

    def test_existing_incompatible_destination_schema_blocks_every_write(self) -> None:
        spark = spark_con_bronce()
        schema = FakeStructType([FakeStructField("otra", FakeType("string"), True)])
        spark.tables["ab_silver_cuentas"] = FakeDataFrame([], schema)
        with self.assertRaisesRegex(ValueError, "ab_silver_cuentas.*incompatible table schema"):
            ejecutar(spark)
        self.assertEqual(spark.write_events, [])

    def test_persisted_count_mismatch_is_detected_after_a_partial_write(self) -> None:
        spark = spark_con_bronce()
        spark.drop_row_in.add("ab_silver_transacciones")
        with self.assertRaisesRegex(
            ValueError, "ab_silver_transacciones: expected table count 72000; observed 71999"
        ):
            ejecutar(spark)
        self.assertIn("ab_silver_clientes", spark.write_events)
        self.assertNotIn("ab_gold_transacciones_mes_canal", spark.write_events)

    def test_persisted_content_mismatch_is_detected(self) -> None:
        spark = spark_con_bronce()
        spark.alter_row_in.add("ab_silver_clientes")
        with self.assertRaisesRegex(ValueError, "ab_silver_clientes.*different persisted contents"):
            ejecutar(spark)


class NotebookTests(unittest.TestCase):
    def test_notebook_is_valid_self_contained_and_synchronized(self) -> None:
        notebook_path = ROOT / "notebooks" / "03_plata_silver.ipynb"
        notebook_text = notebook_path.read_text(encoding="utf-8")
        notebook = json.loads(notebook_text)
        self.assertEqual(notebook["nbformat"], 4)
        self.assertEqual(notebook["metadata"]["kernelspec"]["name"], "synapse_pyspark")
        self.assertEqual(notebook["metadata"]["language_info"]["name"], "python")
        self.assertNotIn("id", notebook["metadata"])
        parameter_cells = [
            cell for cell in notebook["cells"]
            if cell["metadata"].get("tags") == ["parameters"]
        ]
        self.assertEqual(len(parameter_cells), 1)
        self.assertEqual(
            "".join(parameter_cells[0]["source"]),
            "p_lakehouse_esperado = ''\n"
            "p_prefijo = ''\n"
            "p_confirmar_reemplazo = 'NO'\n",
        )
        code_cells = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]
        self.assertEqual(len(code_cells), 3)
        for cell in code_cells:
            self.assertIsNone(cell["execution_count"])
            self.assertEqual(cell["outputs"], [])
            compile("".join(cell["source"]), f"cell-{cell['id']}", "exec")
        self.assertEqual(
            "".join(code_cells[1]["source"]),
            (ROOT / "notebooks" / "plata_silver.py").read_text(encoding="utf-8"),
        )
        self.assertIn("ejecutar_plata(", "".join(code_cells[2]["source"]))
        self.assertNotIn(str(ROOT), notebook_text)
        self.assertNotIn("ingesta_bronce", notebook_text)
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "sincronizar_notebook.py"), "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
