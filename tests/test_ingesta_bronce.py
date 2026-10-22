from __future__ import annotations

import contextlib
import csv
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import types
import unittest
from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from notebooks import ingesta_bronce


DATASET = ROOT / "dataset" / "csv"
MANIFEST = ROOT / "dataset" / "manifiesto.json"
VALID_CONTEXT = {
    "defaultLakehouseName": "AB_Lakehouse",
    "defaultLakehouseId": "lakehouse-id",
    "defaultLakehouseWorkspaceId": "workspace-id",
    "currentWorkspaceId": "workspace-id",
}


class FakeStringType:
    pass


class FakeStructField:
    def __init__(self, name: str, data_type: FakeStringType, nullable: bool) -> None:
        self.name = name
        self.dataType = data_type
        self.nullable = nullable


class FakeStructType:
    def __init__(self, fields: list[FakeStructField]) -> None:
        self.fields = fields


class FakeDataFrame:
    def __init__(self, rows: list[tuple[str, ...]], schema: FakeStructType) -> None:
        self.rows = list(rows)
        self.schema = schema
        self.write = FakeWriter(self)

    def count(self) -> int:
        return len(self.rows)

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
        self.dataframe.spark.write_events.append(table_name)
        self.dataframe.spark.tables[table_name] = FakeDataFrame(
            self.dataframe.rows, self.dataframe.schema
        )


class FakeCatalog:
    def __init__(self, spark: FakeSpark) -> None:
        self.spark = spark

    def tableExists(self, table_name: str) -> bool:
        return table_name in self.spark.tables


class FakeSpark:
    def __init__(self) -> None:
        self.tables: dict[str, FakeDataFrame] = {}
        self.write_events: list[str] = []
        self.dataframe_creations = 0
        self.catalog = FakeCatalog(self)

    def createDataFrame(
        self, rows: list[tuple[str, ...]], schema: FakeStructType
    ) -> FakeDataFrame:
        self.dataframe_creations += 1
        dataframe = FakeDataFrame(rows, schema)
        dataframe.spark = self
        return dataframe

    def table(self, table_name: str) -> FakeDataFrame:
        dataframe = self.tables[table_name]
        dataframe.spark = self
        return dataframe


def _fake_pyspark_modules() -> dict[str, types.ModuleType]:
    pyspark = types.ModuleType("pyspark")
    sql = types.ModuleType("pyspark.sql")
    sql_types = types.ModuleType("pyspark.sql.types")
    sql_types.StringType = FakeStringType
    sql_types.StructField = FakeStructField
    sql_types.StructType = FakeStructType
    pyspark.sql = sql
    sql.types = sql_types
    return {
        "pyspark": pyspark,
        "pyspark.sql": sql,
        "pyspark.sql.types": sql_types,
    }


def _write_fake_sources(directory: Path) -> dict[str, ingesta_bronce.FuenteEsperada]:
    fuentes: dict[str, ingesta_bronce.FuenteEsperada] = {}
    for filename, original in ingesta_bronce.FUENTES.items():
        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(original.headers)
        values = [" " if index == 0 else "" for index in range(len(original.headers))]
        writer.writerow(values)
        row_count = 1
        if filename == "transacciones.csv":
            writer.writerow(values)
            row_count = 2
        content = output.getvalue().encode("utf-8")
        (directory / filename).write_bytes(content)
        fuentes[filename] = ingesta_bronce.FuenteEsperada(
            headers=original.headers,
            row_count=row_count,
            sha256=hashlib.sha256(content).hexdigest(),
        )
    return fuentes


def _execute_with_fake_spark(
    spark: FakeSpark, directory: Path, fuentes: dict[str, ingesta_bronce.FuenteEsperada]
) -> dict[str, object]:
    with patch.object(ingesta_bronce, "FUENTES", fuentes):
        with patch.dict(sys.modules, _fake_pyspark_modules()):
            with contextlib.redirect_stdout(io.StringIO()):
                return ingesta_bronce.ejecutar_ingesta(
                    spark,
                    VALID_CONTEXT,
                    "AB_Lakehouse",
                    "AB",
                    "SI",
                    base_path=directory,
                )


class IngestaBronceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_real_sources_match_allowlisted_manifest_and_keep_raw_anomalies(self) -> None:
        fuentes = ingesta_bronce.cargar_fuentes(DATASET)
        self.assertEqual(
            set(fuentes),
            {
                "clientes.csv",
                "cuentas.csv",
                "sucursales.csv",
                "productos.csv",
                "calendario.csv",
                "transacciones.csv",
            },
        )
        self.assertNotIn("creditos.csv", fuentes)
        for filename, fuente in fuentes.items():
            metadata = self.manifest["files"][filename]
            self.assertEqual(list(fuente.headers), metadata["headers"])
            self.assertEqual(fuente.row_count, metadata["row_count"])
            self.assertEqual(fuente.sha256, metadata["sha256"])
            self.assertTrue(
                all(isinstance(value, str) for row in fuente.rows for value in row.values())
            )

        transacciones = fuentes["transacciones.csv"]
        rows = transacciones.rows
        self.assertEqual(transacciones.row_count, 72360)
        self.assertEqual(
            sum(count - 1 for count in Counter(
                tuple(row[column] for column in transacciones.headers) for row in rows
            ).values()),
            288,
        )
        self.assertEqual(sum(row["canal"] == "" for row in rows), 360)
        self.assertEqual(
            sum(row["canal"] != row["canal"].strip().upper() for row in rows if row["canal"]),
            720,
        )
        account_ids = {row["cuenta_id"] for row in fuentes["cuentas.csv"].rows}
        self.assertEqual(
            sum(row["cuenta_id"] not in account_ids for row in rows),
            24,
        )
        invalid_timestamps = 0
        for row in rows:
            try:
                datetime.strptime(row["fecha_hora"], "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                invalid_timestamps += 1
        self.assertEqual(invalid_timestamps, 24)
        self.assertEqual(
            sum(Decimal(row["monto"]) < 0 for row in rows),
            24,
        )

    def _run_single_source_failure(
        self, content: bytes, expected: ingesta_bronce.FuenteEsperada
    ) -> ValueError:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            (base / "clientes.csv").write_bytes(content)
            with patch.object(
                ingesta_bronce, "FUENTES", {"clientes.csv": expected}
            ):
                with self.assertRaises(ValueError) as raised:
                    ingesta_bronce.cargar_fuentes(base)
        self.assertIn("clientes.csv", str(raised.exception))
        return raised.exception

    def test_hash_mismatch_fails_closed_with_filename_and_hashes(self) -> None:
        original = ingesta_bronce.FUENTES["clientes.csv"]
        changed = (DATASET / "clientes.csv").read_bytes() + b"\n"
        error = self._run_single_source_failure(changed, original)
        self.assertIn("expected SHA-256", str(error))
        self.assertIn("observed", str(error))

    def test_header_mismatch_reports_expected_and_observed(self) -> None:
        original = ingesta_bronce.FUENTES["clientes.csv"]
        lines = (DATASET / "clientes.csv").read_text(encoding="utf-8-sig").splitlines(
            keepends=True
        )
        lines[0] = lines[0].replace("cliente_id", "cliente_x", 1)
        content = "".join(lines).encode("utf-8")
        expected = ingesta_bronce.FuenteEsperada(
            headers=original.headers,
            row_count=original.row_count,
            sha256=hashlib.sha256(content).hexdigest(),
        )
        error = self._run_single_source_failure(content, expected)
        self.assertIn("expected headers", str(error))
        self.assertIn("observed", str(error))

    def test_row_count_mismatch_reports_expected_and_observed(self) -> None:
        original = ingesta_bronce.FUENTES["clientes.csv"]
        lines = (DATASET / "clientes.csv").read_text(encoding="utf-8-sig").splitlines(
            keepends=True
        )
        content = "".join(lines[:-1]).encode("utf-8")
        expected = ingesta_bronce.FuenteEsperada(
            headers=original.headers,
            row_count=original.row_count,
            sha256=hashlib.sha256(content).hexdigest(),
        )
        error = self._run_single_source_failure(content, expected)
        self.assertIn("expected row count 1200", str(error))
        self.assertIn("observed 1199", str(error))

    def test_column_width_mismatch_fails_before_row_count_check(self) -> None:
        original = ingesta_bronce.FUENTES["clientes.csv"]
        lines = (DATASET / "clientes.csv").read_text(encoding="utf-8-sig").splitlines(
            keepends=True
        )
        lines[1] = lines[1].rstrip("\r\n") + ",EXTRA\n"
        content = "".join(lines).encode("utf-8")
        expected = ingesta_bronce.FuenteEsperada(
            headers=original.headers,
            row_count=original.row_count,
            sha256=hashlib.sha256(content).hexdigest(),
        )
        error = self._run_single_source_failure(content, expected)
        self.assertIn("expected 7 columns", str(error))
        self.assertIn("observed 8", str(error))

    def test_bad_parameters_or_runtime_context_never_reach_spark_or_sources(self) -> None:
        cases = [
            (VALID_CONTEXT, "AB_Lakehouse", "AB", "NO"),
            (VALID_CONTEXT, "AB_Lakehouse", "", "SI"),
            (VALID_CONTEXT, "AB_Lakehouse", "1AB", "SI"),
            (VALID_CONTEXT, "OTHER", "AB", "SI"),
            ({key: value for key, value in VALID_CONTEXT.items() if key != "defaultLakehouseId"},
             "AB_Lakehouse", "AB", "SI"),
            ({key: value for key, value in VALID_CONTEXT.items() if key != "defaultLakehouseWorkspaceId"},
             "AB_Lakehouse", "AB", "SI"),
            ({**VALID_CONTEXT, "currentWorkspaceId": "other-workspace"},
             "AB_Lakehouse", "AB", "SI"),
        ]
        for context, expected_name, prefix, confirmation in cases:
            spark = FakeSpark()
            with self.subTest(context=context, prefix=prefix, confirmation=confirmation):
                with patch.object(ingesta_bronce, "cargar_fuentes") as load:
                    with self.assertRaises(ValueError):
                        ingesta_bronce.ejecutar_ingesta(
                            spark,
                            context,
                            expected_name,
                            prefix,
                            confirmation,
                        )
                load.assert_not_called()
                self.assertEqual(spark.dataframe_creations, 0)
                self.assertEqual(spark.write_events, [])

    def test_failed_source_preflight_never_creates_or_writes_spark_dataframes(self) -> None:
        original = ingesta_bronce.FUENTES["clientes.csv"]
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            (base / "clientes.csv").write_bytes(b"modified")
            spark = FakeSpark()
            with patch.object(
                ingesta_bronce, "FUENTES", {"clientes.csv": original}
            ):
                with self.assertRaisesRegex(ValueError, "expected SHA-256"):
                    ingesta_bronce.ejecutar_ingesta(
                        spark,
                        VALID_CONTEXT,
                        "AB_Lakehouse",
                        "AB",
                        "SI",
                        base_path=base,
                    )
            self.assertEqual(spark.dataframe_creations, 0)
            self.assertEqual(spark.write_events, [])

    def test_repeated_run_replaces_full_multiset_without_appending(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            fuentes = _write_fake_sources(base)
            spark = FakeSpark()
            first = _execute_with_fake_spark(spark, base, fuentes)
            second = _execute_with_fake_spark(spark, base, fuentes)

        expected_tables = {
            f"ab_bronze_{Path(filename).stem}" for filename in fuentes
        }
        self.assertEqual({table["table"] for table in first["tables"]}, expected_tables)
        self.assertEqual(second["status"], "success")
        self.assertEqual(set(spark.tables), expected_tables)
        self.assertEqual(len(spark.write_events), 12)
        self.assertEqual(Counter(spark.write_events), Counter({name: 2 for name in expected_tables}))
        tx_table = spark.tables["ab_bronze_transacciones"]
        self.assertEqual(tx_table.count(), 2)
        self.assertEqual(tx_table.rows[0], tx_table.rows[1])
        self.assertEqual(tx_table.rows[0][0], " ")
        self.assertEqual(tx_table.rows[0][1], "")

    def test_existing_unexpected_schema_blocks_every_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            fuentes = _write_fake_sources(base)
            spark = FakeSpark()
            wrong_schema = FakeStructType(
                [FakeStructField("unexpected", FakeStringType(), True)]
            )
            spark.tables["ab_bronze_clientes"] = FakeDataFrame([], wrong_schema)
            with self.assertRaisesRegex(ValueError, "incompatible table schema"):
                _execute_with_fake_spark(spark, base, fuentes)
        self.assertEqual(spark.write_events, [])

    def test_notebook_is_valid_self_contained_and_renderer_is_synchronized(self) -> None:
        notebook_path = ROOT / "notebooks" / "02_ingesta_bronce.ipynb"
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
        parameter_source = "".join(parameter_cells[0]["source"])
        self.assertEqual(
            parameter_source,
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
            (ROOT / "notebooks" / "ingesta_bronce.py").read_text(encoding="utf-8"),
        )
        self.assertNotIn(str(ROOT), notebook_text)
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
