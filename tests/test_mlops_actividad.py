from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

LIBRERIAS = all(importlib.util.find_spec(m) for m in ("pandas", "numpy", "sklearn"))
MLFLOW = bool(importlib.util.find_spec("mlflow"))
AHORA = datetime(2026, 10, 30, 12, 0, 0, tzinfo=timezone.utc)
CONTEXTO = {
    "defaultLakehouseName": "AB_Lakehouse",
    "defaultLakehouseId": "lakehouse-id",
    "defaultLakehouseWorkspaceId": "workspace-id",
    "currentWorkspaceId": "workspace-id",
}

if LIBRERIAS:
    import numpy as np
    import pandas as pd

    from notebooks import plata_silver
    from notebooks.bonus_ml import ml_actividad as ml
    from test_plata_silver import bronce_real


@contextlib.contextmanager
def modulos_falsos(modulos: dict[str, types.ModuleType]):
    """Agrega modulos simulados a sys.modules y al salir quita solo esos.

    `patch.dict(sys.modules)` elimina tambien los modulos reales que se importen mientras
    esta activo (por ejemplo lightgbm), y los ganchos de MLflow siguen apuntando a ellos.
    """
    previos = {nombre: sys.modules.get(nombre) for nombre in modulos}
    sys.modules.update(modulos)
    try:
        yield
    finally:
        for nombre, anterior in previos.items():
            if anterior is None:
                sys.modules.pop(nombre, None)
            else:
                sys.modules[nombre] = anterior


class _Tipo:
    def __init__(self, nombre: str) -> None:
        self.nombre = nombre


class _Campo:
    def __init__(self, name: str, dataType: _Tipo, nullable: bool) -> None:
        self.name = name
        self.dataType = dataType
        self.nullable = nullable


class _Esquema:
    def __init__(self, fields: list[_Campo]) -> None:
        self.fields = fields


def _modulos_pyspark() -> dict[str, types.ModuleType]:
    pyspark = types.ModuleType("pyspark")
    sql = types.ModuleType("pyspark.sql")
    tipos = types.ModuleType("pyspark.sql.types")
    tipos.StringType = lambda: _Tipo("string")
    tipos.LongType = lambda: _Tipo("bigint")
    tipos.DoubleType = lambda: _Tipo("double")
    tipos.StructField = _Campo
    tipos.StructType = _Esquema
    pyspark.sql = sql
    sql.types = tipos
    return {"pyspark": pyspark, "pyspark.sql": sql, "pyspark.sql.types": tipos}


def _coincide(valor: object, tipo: str) -> bool:
    if valor is None:
        return True
    if tipo == "string":
        return isinstance(valor, str)
    if tipo == "bigint":
        return type(valor) is int
    return type(valor) is float


class SparkSimulado:
    """Valida que cada valor tenga el tipo exacto del esquema, como lo exige Spark."""

    def __init__(self) -> None:
        self.tablas: dict[str, "pd.DataFrame"] = {}
        self.escrituras: list[str] = []
        self.perder_filas_en: set[str] = set()
        self.catalog = types.SimpleNamespace(tableExists=lambda nombre: nombre in self.tablas)

    def createDataFrame(self, filas, schema):
        nombres = [campo.name for campo in schema.fields]
        for fila in filas:
            for valor, campo in zip(fila, schema.fields):
                if not _coincide(valor, campo.dataType.nombre):
                    raise TypeError(
                        f"{campo.name}: expected {campo.dataType.nombre}; observed {valor!r} ({type(valor).__name__})"
                    )
        datos = pd.DataFrame(list(filas), columns=nombres)
        for campo in schema.fields:
            if campo.dataType.nombre == "double":
                datos[campo.name] = pd.to_numeric(datos[campo.name]).astype("float64")
            elif campo.dataType.nombre == "bigint":
                datos[campo.name] = datos[campo.name].astype("int64")
        return _DataFrameSimulado(datos, self)

    def table(self, nombre: str):
        return _DataFrameSimulado(self.tablas[nombre], self)


class _DataFrameSimulado:
    def __init__(self, datos: "pd.DataFrame", spark: SparkSimulado) -> None:
        self.datos = datos
        self.spark = spark
        self.write = self

    def mode(self, modo: str) -> "_DataFrameSimulado":
        assert modo == "overwrite"
        return self

    def saveAsTable(self, nombre: str) -> None:
        guardado = self.datos
        if nombre in self.spark.perder_filas_en:
            guardado = guardado.iloc[:-1]
        self.spark.tablas[nombre] = guardado.reset_index(drop=True)
        self.spark.escrituras.append(nombre)

    def toPandas(self) -> "pd.DataFrame":
        return self.datos.copy()

    def count(self) -> int:
        return len(self.datos)


def _tabla_de_features() -> "pd.DataFrame":
    tablas = plata_silver.transformar(bronce_real(), "AB").tablas
    marco = lambda n: pd.DataFrame(tablas[n].filas, columns=[c for c, _ in tablas[n].columnas])
    return ml.construir_dataset(
        marco("silver_transacciones"), marco("silver_cuentas"), marco("silver_clientes"),
        ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09"],
    )


@unittest.skipUnless(LIBRERIAS, "requires pandas, numpy and scikit-learn")
class InfraestructuraTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.features = _tabla_de_features()

    def test_declared_spark_columns_match_the_feature_dataframe(self) -> None:
        self.assertEqual([c for c, _ in ml.COLUMNAS_FEATURES], list(self.features.columns))
        esperado = {"string": ("object", "str", "string"), "bigint": ("int64",), "double": ("float64",)}
        for columna, tipo in ml.COLUMNAS_FEATURES:
            with self.subTest(columna=columna):
                self.assertIn(str(self.features[columna].dtype), esperado[tipo])

    def test_table_names_use_the_lowercase_prefix(self) -> None:
        nombres = ml.nombres_ml("AB")
        self.assertEqual(nombres["features"], "ab_gold_ml_features_cuentas")
        self.assertEqual(nombres["modelo"], "ab_modelo_actividad")
        self.assertTrue(all(valor.startswith("ab_") for valor in nombres.values()))

    def test_silver_reader_checks_counts_before_loading(self) -> None:
        tablas = plata_silver.transformar(bronce_real(), "AB").tablas
        spark = SparkSimulado()
        for base in ml.CONTEOS_SILVER:
            nombre = f"silver_{base}"
            spark.tablas[f"ab_{nombre}"] = pd.DataFrame(
                tablas[nombre].filas, columns=[c for c, _ in tablas[nombre].columnas]
            )
        silver = ml.leer_silver(spark, "AB")
        self.assertEqual({k: len(v) for k, v in silver.items()}, ml.CONTEOS_SILVER)
        self.assertEqual(str(silver["transacciones"]["monto"].dtype), "float64")
        self.assertTrue(str(silver["transacciones"]["fecha_hora"].dtype).startswith("datetime64"))
        self.assertIsNone(silver["transacciones"]["fecha_hora"].dt.tz)
        self.assertEqual(str(silver["cuentas"]["saldo_inicial"].dtype), "float64")
        spark.tablas["ab_silver_cuentas"] = spark.tablas["ab_silver_cuentas"].iloc[:-1]
        with self.assertRaisesRegex(ValueError, "ab_silver_cuentas: expected row count 1800; observed 1799"):
            ml.leer_silver(spark, "AB")
        spark.tablas["ab_silver_cuentas"] = pd.DataFrame(
            tablas["silver_cuentas"].filas, columns=[c for c, _ in tablas["silver_cuentas"].columnas]
        )
        del spark.tablas["ab_silver_clientes"]
        with self.assertRaisesRegex(ValueError, "ab_silver_clientes: expected an existing table"):
            ml.leer_silver(spark, "AB")

    def test_write_roundtrip_keeps_types_and_missing_labels(self) -> None:
        spark = SparkSimulado()
        with modulos_falsos(_modulos_pyspark()):
            filas = ml.escribir_tabla(spark, "ab_gold_ml_features_cuentas", self.features, ml.COLUMNAS_FEATURES)
        self.assertEqual(filas, 9000)
        leido = ml.leer_tabla(spark, "ab_gold_ml_features_cuentas")
        self.assertEqual(ml.validar_features(leido, cuentas_esperadas=1800), [])
        self.assertTrue(leido.loc[leido[ml.CORTE] == "2026-09", ml.ETIQUETA].isna().all())
        self.assertEqual(int(leido[ml.ETIQUETA].sum()), 563 + 589 + 631 + 651)

    def test_write_detects_persisted_count_mismatch_and_bigint_nulls(self) -> None:
        spark = SparkSimulado()
        spark.perder_filas_en.add("tabla")
        with modulos_falsos(_modulos_pyspark()):
            with self.assertRaisesRegex(ValueError, "tabla: expected table count 9000; observed 8999"):
                ml.escribir_tabla(spark, "tabla", self.features, ml.COLUMNAS_FEATURES)
            roto = self.features.copy()
            roto["n_tipos"] = roto["n_tipos"].astype("float64")
            roto.loc[0, "n_tipos"] = float("nan")
            with self.assertRaisesRegex(ValueError, "expected no nulls in a bigint column"):
                ml.escribir_tabla(SparkSimulado(), "otra", roto, ml.COLUMNAS_FEATURES)
            with self.assertRaisesRegex(ValueError, "expected columns.*missing"):
                ml.escribir_tabla(SparkSimulado(), "otra", self.features.drop(columns=["segmento"]), ml.COLUMNAS_FEATURES)

    def test_replace_cutoff_is_idempotent_and_keeps_other_cutoffs(self) -> None:
        spark = SparkSimulado()
        columnas = (("corte", "string"), ("valor", "double"))
        with modulos_falsos(_modulos_pyspark()):
            for corte, valor in (("2026-07", 1.0), ("2026-08", 2.0), ("2026-08", 3.0)):
                ml.reemplazar_corte(
                    spark, "t", pd.DataFrame({"corte": [corte], "valor": [valor]}), columnas, "corte", corte
                )
        resultado = spark.tablas["t"].sort_values("corte").reset_index(drop=True)
        self.assertEqual(resultado["corte"].tolist(), ["2026-07", "2026-08"])
        self.assertEqual(resultado["valor"].tolist(), [1.0, 3.0])

    def test_cutoffs_for_a_monthly_run(self) -> None:
        disponibles = ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]
        self.assertEqual(
            ml.cortes_para("2026-09", disponibles),
            {"entrenamiento": ("2026-05", "2026-06"), "validacion": "2026-07",
             "prueba": "2026-08", "puntuacion": "2026-09"},
        )
        self.assertEqual(ml.cortes_para("2026-08", disponibles)["entrenamiento"], ("2026-05",))
        with self.assertRaisesRegex(ValueError, "at least one training cutoff"):
            ml.cortes_para("2026-07", disponibles)

    def test_registry_champion_is_the_latest_event_and_rollback_is_audited(self) -> None:
        spark = SparkSimulado()
        registro = None
        for version, auc in ((1, 0.84), (2, 0.86)):
            registro = ml._nuevo_evento(
                registro, "promocion", version, "logreg", auc, auc, "2026-08", f"run{version}", "m", AHORA
            )
        with modulos_falsos(_modulos_pyspark()):
            ml.escribir_tabla(spark, ml.nombres_ml("AB")["registro"], registro, ml.COLUMNAS_REGISTRO)
            self.assertEqual(ml.campeon_actual(registro)["version"], 2)
            nuevo = ml.revertir_campeon(spark, "AB", 1, "rollback por caida de calidad", ahora=AHORA)
            self.assertEqual(nuevo["version"], 1)
            self.assertAlmostEqual(nuevo["auc_prueba"], 0.84)
            guardado = spark.tablas[ml.nombres_ml("AB")["registro"]]
            self.assertEqual(guardado["evento"].tolist(), ["promocion", "promocion", "reversion"])
            self.assertEqual(guardado["secuencia"].tolist(), [1, 2, 3])
            with self.assertRaisesRegex(ValueError, "version: expected one of"):
                ml.revertir_campeon(spark, "AB", 9, "motivo")
            with self.assertRaisesRegex(ValueError, "non-empty reason"):
                ml.revertir_campeon(spark, "AB", 1, "  ")
        self.assertIsNone(ml.campeon_actual(None))

    def test_parameter_validation_never_touches_spark_or_mlflow(self) -> None:
        sin_id = {k: v for k, v in CONTEXTO.items() if k != "defaultLakehouseId"}
        casos = [
            (CONTEXTO, "AB_Lakehouse", "AB", "NO"),
            (CONTEXTO, "AB_Lakehouse", "1AB", "SI"),
            (CONTEXTO, "OTRO", "AB", "SI"),
            (sin_id, "AB_Lakehouse", "AB", "SI"),
            ({**CONTEXTO, "currentWorkspaceId": "otro"}, "AB_Lakehouse", "AB", "SI"),
        ]

        class Prohibido:
            def __getattr__(self, nombre: str):
                raise AssertionError(f"must not be touched: {nombre}")

        for contexto, esperado, prefijo, confirmacion in casos:
            with self.subTest(prefijo=prefijo, confirmacion=confirmacion, esperado=esperado):
                with self.assertRaises(ValueError):
                    ml.ejecutar_ciclo(Prohibido(), Prohibido(), contexto, esperado, prefijo, confirmacion)


@unittest.skipUnless(LIBRERIAS and MLFLOW, "requires pandas, scikit-learn and mlflow")
class CicloMlopsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import warnings

        warnings.simplefilter("ignore")
        cls.features = _tabla_de_features()

    def setUp(self) -> None:
        import os

        import mlflow

        # Las versiones recientes de MLflow desactivan por defecto el almacen en archivos;
        # solo se usa aqui, en un directorio temporal. En Fabric lo gestiona el servicio.
        entorno = patch.dict(os.environ, {"MLFLOW_ALLOW_FILE_STORE": "true"})
        entorno.start()
        self.addCleanup(entorno.stop)
        self.mlflow = mlflow
        self.directorio = tempfile.TemporaryDirectory()
        uri = Path(self.directorio.name).as_uri()
        mlflow.set_tracking_uri(uri)
        mlflow.set_registry_uri(uri)
        self.spark = SparkSimulado()
        with modulos_falsos(_modulos_pyspark()):
            ml.escribir_tabla(
                self.spark, ml.nombres_ml("AB")["features"], self.features, ml.COLUMNAS_FEATURES
            )
        self.addCleanup(self.directorio.cleanup)

    def _ciclo(self, corte: str = "2026-09", **kwargs):
        with modulos_falsos(_modulos_pyspark()):
            with contextlib.redirect_stdout(io.StringIO()):
                return ml.ejecutar_ciclo(
                    self.spark, self.mlflow, CONTEXTO, "AB_Lakehouse", "AB", "SI",
                    p_corte_puntuacion=corte, ahora=AHORA, **kwargs,
                )

    def _tabla(self, clave: str) -> "pd.DataFrame":
        return self.spark.tablas[ml.nombres_ml("AB")[clave]]

    def test_first_cycle_promotes_registers_scores_and_monitors(self) -> None:
        informe = self._ciclo()
        self.assertEqual(informe["status"], "success")
        self.assertEqual(informe["decision"], "promover")
        self.assertEqual(informe["version_campeon"], 1)
        self.assertIsNone(informe["campeon_previo"])
        self.assertGreater(informe["retador"]["auc"], 0.80)
        self.assertEqual(informe["cortes"]["entrenamiento"], ["2026-05", "2026-06"])
        self.assertEqual(len(self._tabla("registro")), 1)
        puntuacion = self._tabla("puntuacion")
        self.assertEqual(len(puntuacion), 1800)
        self.assertEqual(set(puntuacion["version_modelo"]), {1})
        self.assertEqual(len(self._tabla("deriva")), len(ml.FEATURES))
        self.assertNotIn(ml.nombres_ml("AB")["desempeno"], self.spark.tablas)
        self.assertEqual(informe["recomendacion"], "sin_accion")
        json.dumps(informe)
        versiones = self.mlflow.MlflowClient().search_model_versions(f"name='{ml.nombres_ml('AB')['modelo']}'")
        self.assertEqual([int(v.version) for v in versiones], [1])
        self.assertEqual(versiones[0].tags["tipo_modelo"], "logreg")

    def test_rerun_keeps_the_champion_and_does_not_duplicate_rows_or_versions(self) -> None:
        self._ciclo()
        informe = self._ciclo()
        self.assertEqual(informe["decision"], "mantener")
        self.assertEqual(informe["version_campeon"], 1)
        self.assertEqual(len(self._tabla("registro")), 1)
        self.assertEqual(len(self._tabla("puntuacion")), 1800)
        self.assertEqual(len(self._tabla("deriva")), len(ml.FEATURES))
        versiones = self.mlflow.MlflowClient().search_model_versions(f"name='{ml.nombres_ml('AB')['modelo']}'")
        self.assertEqual(len(versiones), 1)
        self.assertAlmostEqual(informe["retador"]["auc"], informe["campeon_previo"]["auc"], places=9)

    def test_labels_of_the_scoring_cutoff_are_hidden_in_a_retrospective_run(self) -> None:
        informe = self._ciclo("2026-08")
        self.assertEqual(informe["cortes"]["entrenamiento"], ["2026-05"])
        self.assertEqual(informe["cortes"]["prueba"], "2026-07")
        self.assertEqual(set(self._tabla("puntuacion")["corte"]), {"2026-08"})

    def test_next_month_measures_the_real_performance_of_the_previous_predictions(self) -> None:
        self._ciclo("2026-08")
        informe = self._ciclo("2026-09")
        desempeno = self._tabla("desempeno")
        self.assertEqual(len(desempeno), 1)
        fila = desempeno.iloc[0]
        self.assertEqual(fila["corte_prediccion"], "2026-08")
        self.assertEqual(fila["mes_evaluado"], "2026-09")
        self.assertEqual(int(fila["filas"]), 1800)
        self.assertTrue(0.75 < fila["auc"] < 0.95)
        self.assertAlmostEqual(fila["prevalencia_real"], 651 / 1800, places=6)
        self.assertAlmostEqual(informe["auc_real_mes_anterior"], fila["auc"], places=5)
        self.assertEqual(set(self._tabla("puntuacion")["corte"]), {"2026-08", "2026-09"})
        self.assertEqual(len(self._tabla("puntuacion")), 3600)

    def test_simulated_campaign_triggers_drift_alerts(self) -> None:
        self._ciclo()
        informe = self._ciclo(p_factor_deriva=1.6)
        self.assertTrue(informe["deriva_simulada"])
        self.assertGreaterEqual(informe["deriva"].get("alta", 0), 4)
        self.assertEqual(informe["recomendacion"], "revisar")
        deriva = self._tabla("deriva")
        self.assertEqual(set(deriva["simulada"]), {1})
        self.assertEqual(len(deriva), len(ml.FEATURES))

    def test_rejected_challenger_without_a_champion_stops_before_scoring(self) -> None:
        rechazo = {"decision": "rechazar", "motivo": "below the floor", "mejora": None}
        with patch.object(ml, "decidir_promocion", return_value=rechazo):
            with self.assertRaisesRegex(ValueError, "expected a champion model"):
                self._ciclo()
        self.assertNotIn(ml.nombres_ml("AB")["puntuacion"], self.spark.tablas)

    def test_missing_or_broken_feature_table_fails_before_training(self) -> None:
        spark_vacio = SparkSimulado()
        with self.assertRaisesRegex(ValueError, "ab_gold_ml_features_cuentas: expected an existing table"):
            ml.ejecutar_ciclo(spark_vacio, self.mlflow, CONTEXTO, "AB_Lakehouse", "AB", "SI")
        roto = self.features.copy()
        roto.loc[0, "pct_credito"] = 3.0
        self.spark.tablas[ml.nombres_ml("AB")["features"]] = roto
        with self.assertRaisesRegex(ValueError, "pct_credito"):
            self._ciclo()
        self.assertEqual(self.spark.escrituras, [ml.nombres_ml("AB")["features"]])


if __name__ == "__main__":
    unittest.main()
