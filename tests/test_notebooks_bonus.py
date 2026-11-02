from __future__ import annotations

import ast
import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

BONUS = ROOT / "notebooks" / "bonus_ml"
LIBRERIAS = all(importlib.util.find_spec(m) for m in ("pandas", "numpy", "sklearn"))
MLFLOW = bool(importlib.util.find_spec("mlflow"))
FLAML = bool(importlib.util.find_spec("flaml"))

import notebook_percent

if LIBRERIAS:
    import pandas as pd

    from notebooks import plata_silver
    from notebooks.bonus_ml import anomalias_tx as an
    from notebooks.bonus_ml import ml_actividad as ml
    from test_mlops_actividad import CONTEXTO, SparkSimulado, _modulos_pyspark, modulos_falsos
    from test_plata_silver import bronce_real


def _fuentes_percent() -> list[Path]:
    return sorted(BONUS.glob("b[0-9]_*.py"))


def _es_magia(codigo: str) -> bool:
    """Las celdas que empiezan con % o ! son comandos de Jupyter, no codigo Python."""
    return codigo.lstrip().startswith(("%", "!"))


class SintaxisDeLosNotebooksTests(unittest.TestCase):
    def test_every_code_cell_uses_syntax_available_in_python_3_10(self) -> None:
        fuentes = _fuentes_percent()
        self.assertTrue(fuentes)
        for fuente in fuentes:
            for indice, codigo in enumerate(notebook_percent.celdas_codigo(fuente)):
                if _es_magia(codigo):
                    continue
                with self.subTest(notebook=fuente.name, celda=indice):
                    arbol = ast.parse(codigo, feature_version=(3, 10))
                    compile(arbol, f"{fuente.name}[{indice}]", "exec")

    def test_magic_cells_are_only_package_installs(self) -> None:
        for fuente in _fuentes_percent():
            for codigo in notebook_percent.celdas_codigo(fuente):
                if _es_magia(codigo):
                    with self.subTest(notebook=fuente.name):
                        self.assertRegex(codigo.strip(), r"^%pip install -q [\w.\-]+( [\w.\-]+)*( 2>/dev/null)?$")

    def test_markdown_cells_follow_the_percent_format(self) -> None:
        for fuente in _fuentes_percent():
            celdas = notebook_percent.parsear(fuente.read_text(encoding="utf-8"), fuente.name)
            with self.subTest(notebook=fuente.name):
                self.assertEqual(celdas[0].tipo, "markdown")
                self.assertEqual(sum(c.tipo == "parameters" for c in celdas), 1)
                for celda in celdas:
                    if celda.tipo == "markdown":
                        notebook_percent._markdown(celda.contenido, fuente.name)

    def test_percent_parser_rejects_malformed_sources(self) -> None:
        with self.assertRaisesRegex(ValueError, "expected a '# %%' marker"):
            notebook_percent.parsear("x = 1\n# %%\ny = 2\n")
        with self.assertRaisesRegex(ValueError, "known cell header"):
            notebook_percent.parsear("# %% [raw]\nx\n")
        with self.assertRaisesRegex(ValueError, "at least one cell"):
            notebook_percent.parsear("\n\n")
        with self.assertRaisesRegex(ValueError, "starting with '# '"):
            notebook_percent._markdown("sin marca", "prueba")


class Recorder:
    def __init__(self) -> None:
        self.salidas: list[str] = []
        self.mostrados: list[object] = []


def ejecutar_notebook(
    fuente: Path, parametros: dict, spark: object, extra_modulos: dict | None = None,
    globales: dict | None = None, con_pyspark: bool = True,
) -> tuple[dict, Recorder]:
    """Ejecuta las celdas de codigo en orden, cada una por separado, como lo hace un notebook."""
    registro = Recorder()
    notebookutils = types.SimpleNamespace(
        runtime=types.SimpleNamespace(context=CONTEXTO),
        notebook=types.SimpleNamespace(exit=registro.salidas.append),
    )
    espacio: dict = {"__name__": "__main__", "spark": spark, "display": registro.mostrados.append}
    espacio.update(globales or {})
    modulos = {
        **(_modulos_pyspark() if con_pyspark else {}),
        "notebookutils": notebookutils,
        **(extra_modulos or {}),
    }
    with modulos_falsos(modulos):
        with contextlib.redirect_stdout(io.StringIO()) as salida:
            for indice, celda in enumerate(notebook_percent.parsear(fuente.read_text(encoding="utf-8"), fuente.name)):
                if celda.tipo == "embed":
                    codigo = (fuente.parent / celda.argumento).read_text(encoding="utf-8")
                elif celda.tipo in ("code", "parameters"):
                    codigo = celda.contenido + "\n"
                else:
                    continue
                if _es_magia(codigo):
                    continue
                exec(compile(codigo, f"{fuente.name}[{indice}]", "exec"), espacio)
                if celda.tipo == "parameters":
                    espacio.update(parametros)
    registro.texto = salida.getvalue()  # type: ignore[attr-defined]
    return espacio, registro


def _spark_con_silver() -> "SparkSimulado":
    tablas = plata_silver.transformar(bronce_real(), "AB").tablas
    spark = SparkSimulado()
    for base in ml.CONTEOS_SILVER:
        origen = tablas[f"silver_{base}"]
        marco = pd.DataFrame(origen.filas, columns=[c for c, _ in origen.columnas])
        if base == "transacciones":
            marco["fecha_hora"] = pd.to_datetime(marco["fecha_hora"], utc=True)
        spark.tablas[f"ab_silver_{base}"] = marco
    spark.tablas["ab_silver_calendario"] = pd.DataFrame({"mes": range(4, 10)})
    return spark


def _sempy_simulado(tx: "pd.DataFrame") -> dict[str, types.ModuleType]:
    paquete = types.ModuleType("sempy")
    fabric = types.ModuleType("sempy.fabric")
    llamadas: list[dict] = []

    def evaluate_dax(dataset, dax_string, workspace=None, role=None, **kwargs):
        llamadas.append({"dataset": dataset, "role": role, "dax": dax_string})
        if "SUMMARIZECOLUMNS" in dax_string:
            por_mes = tx.groupby(tx["fecha_hora"].dt.month).size().reset_index()
            por_mes.columns = ["ab_silver_calendario[mes]", "[Transacciones]"]
            return por_mes
        return pd.DataFrame({"[Transacciones]": [8971 if role == "Heredia" else 72000]})

    fabric.evaluate_dax = evaluate_dax
    fabric.llamadas = llamadas
    paquete.fabric = fabric
    return {"sempy": paquete, "sempy.fabric": fabric}


@unittest.skipUnless(LIBRERIAS, "requires pandas, numpy and scikit-learn")
class B1Tests(unittest.TestCase):
    fuente = BONUS / "b1_preparacion_datos.py"
    parametros = {"p_lakehouse_esperado": "AB_Lakehouse", "p_prefijo": "AB", "p_confirmar_reemplazo": "SI"}

    def test_notebook_writes_the_feature_table_with_the_documented_controls(self) -> None:
        spark = _spark_con_silver()
        espacio, registro = ejecutar_notebook(self.fuente, self.parametros, spark)
        tabla = spark.tablas["ab_gold_ml_features_cuentas"]
        self.assertEqual(len(tabla), 9000)
        self.assertEqual(tabla.groupby("corte").size().unique().tolist(), [1800])
        self.assertEqual(
            tabla.groupby("corte")["alta_actividad_siguiente"].sum().astype(int).to_dict(),
            {"2026-05": 563, "2026-06": 589, "2026-07": 631, "2026-08": 651, "2026-09": 0},
        )
        self.assertTrue(tabla.loc[tabla["corte"] == "2026-09", "alta_actividad_siguiente"].isna().all())
        self.assertIn("Sin fuga de datos", registro.texto)
        self.assertIn("Aún no existe conteo_dw", registro.texto)
        self.assertEqual(spark.escrituras, ["ab_gold_ml_features_cuentas"])

    def test_without_confirmation_it_explores_but_never_writes(self) -> None:
        spark = _spark_con_silver()
        parametros = {**self.parametros, "p_confirmar_reemplazo": "NO"}
        with self.assertRaisesRegex(ValueError, "p_confirmar_reemplazo must be exactly 'SI'"):
            ejecutar_notebook(self.fuente, parametros, spark)
        self.assertEqual(spark.escrituras, [])

    def test_missing_silver_tables_stop_the_notebook_before_any_work(self) -> None:
        spark = _spark_con_silver()
        del spark.tablas["ab_silver_cuentas"]
        with self.assertRaisesRegex(ValueError, "ab_silver_cuentas: expected an existing table"):
            ejecutar_notebook(self.fuente, self.parametros, spark)
        self.assertEqual(spark.escrituras, [])

    def test_data_wrangler_check_accepts_a_matching_result_and_flags_a_wrong_one(self) -> None:
        spark = _spark_con_silver()
        tx = ml.leer_silver(spark, "AB")["transacciones"]
        correcto = tx.groupby("cuenta_id").size().rename("n_tx").reset_index()
        _, registro = ejecutar_notebook(self.fuente, self.parametros, spark, globales={"conteo_dw": correcto})
        self.assertIn("Coincide con pandas: 1800 cuentas, 72000 transacciones", registro.texto)
        incorrecto = correcto.copy()
        incorrecto.loc[0, "n_tx"] += 1
        _, registro = ejecutar_notebook(self.fuente, self.parametros, spark, globales={"conteo_dw": incorrecto})
        self.assertIn("No coincide", registro.texto)

    def test_semantic_link_reconciliation_and_role_check(self) -> None:
        spark = _spark_con_silver()
        tx = ml.leer_silver(spark, "AB")["transacciones"]
        sempy = _sempy_simulado(tx)
        parametros = {**self.parametros, "p_modelo_semantico": "AB_SM_Transacciones"}
        _, registro = ejecutar_notebook(self.fuente, parametros, spark, extra_modulos=sempy)
        self.assertIn("El modelo semántico coincide con las tablas plata en los 6 meses", registro.texto)
        llamadas = sempy["sempy.fabric"].llamadas
        self.assertEqual([c["role"] for c in llamadas], [None, "Heredia"])
        self.assertTrue(all(c["dataset"] == "AB_SM_Transacciones" for c in llamadas))
        self.assertIn("'ab_silver_calendario'[mes]", llamadas[0]["dax"])

    def test_semantic_link_reconciliation_fails_when_the_model_differs(self) -> None:
        spark = _spark_con_silver()
        tx = ml.leer_silver(spark, "AB")["transacciones"]
        sempy = _sempy_simulado(tx.iloc[:-5])
        parametros = {**self.parametros, "p_modelo_semantico": "AB_SM_Transacciones"}
        with self.assertRaisesRegex(ValueError, "reconciliacion"):
            ejecutar_notebook(self.fuente, parametros, spark, extra_modulos=sempy)


@unittest.skipUnless(LIBRERIAS and MLFLOW and FLAML, "requires pandas, scikit-learn, mlflow and flaml")
class B2Tests(unittest.TestCase):
    fuente = BONUS / "b2_entrenamiento_mlflow.py"

    def test_notebook_logs_every_run_compares_them_and_registers_explainability(self) -> None:
        import mlflow

        with tempfile.TemporaryDirectory() as directorio:
            with patch.dict(os.environ, {"MLFLOW_ALLOW_FILE_STORE": "true"}):
                mlflow.set_tracking_uri(Path(directorio).as_uri())
                spark = _spark_con_silver()
                spark.tablas["ab_gold_ml_features_cuentas"] = _features(spark)
                parametros = {"p_lakehouse_esperado": "AB_Lakehouse", "p_prefijo": "AB", "p_presupuesto_automl_s": 5}
                try:
                    espacio, registro = ejecutar_notebook(self.fuente, parametros, spark, con_pyspark=False)
                finally:
                    mlflow.autolog(disable=True)

                comparacion = espacio["comparacion"]
                nombres = set(comparacion["tags.mlflow.runName"])
                self.assertTrue({"logreg", "rf", "hgb"} <= nombres)
                self.assertTrue(comparacion["metrics.auc_validacion"].between(0.78, 0.95).all())
                self.assertIn(espacio["elegido"], ("logreg", "rf", "hgb"))
                self.assertTrue(0.78 < espacio["metricas_prueba"]["auc"] < 0.95)
                self.assertGreater(espacio["metricas_prueba"]["auc"], espacio["metricas_baseline"]["auc"] - 0.02)
                self.assertEqual(set(espacio["auditoria"]["grupo"]), {"18-29", "30-44", "45-59", "60+"})
                self.assertEqual(len(espacio["importancia"]), len(ml.FEATURES))
                self.assertTrue(0.78 < espacio["auc_automl"] < 0.95)
                self.assertIn("C", espacio["analisis"].best_config)

                cliente = mlflow.MlflowClient()
                artefactos = [a.path for a in cliente.list_artifacts(espacio["resultados"][espacio["elegido"]]["run_id"])]
                self.assertIn("explicabilidad.json", artefactos)
                corrida = cliente.get_run(espacio["resultados"][espacio["elegido"]]["run_id"])
                self.assertIn("auc_prueba", corrida.data.metrics)
                self.assertEqual(corrida.data.tags["seleccionado"], "si")
                self.assertEqual(spark.escrituras, [])


class _ClienteSimulado:
    def __init__(self) -> None:
        self.llamadas: list[dict] = []
        self.responses = self

    def create(self, **kwargs):
        self.llamadas.append(kwargs)
        return types.SimpleNamespace(output_text="Respuesta simulada.")


def _registrar_accesores_ia() -> None:
    """Accesor `.ai` de pandas con respuestas deterministas; solo existe en las pruebas."""

    class Disponibilidad:
        activa = True
        mensaje = "AI functions are not supported on a trial capacity"

    def _exigir() -> None:
        if not Disponibilidad.activa:
            raise RuntimeError(Disponibilidad.mensaje)

    @pd.api.extensions.register_series_accessor("ai")
    class _ServiciosSerie:
        def __init__(self, serie: "pd.Series") -> None:
            self.serie = serie

        def analyze_sentiment(self, *etiquetas):
            _exigir()
            return self.serie.map(lambda t: "positive" if any(p in t.lower() for p in ("gracias", "excelente", "cómoda", "gustó", "bien", "rápido")) else "negative")

        def classify(self, *etiquetas):
            _exigir()
            return self.serie.map(lambda t: next((e for e in etiquetas if e.split()[0] in t.lower()), "otro"))

        def extract(self, *etiquetas):
            _exigir()
            return pd.DataFrame({e: [None] * len(self.serie) for e in etiquetas}, index=self.serie.index)

        def summarize(self, instructions=None):
            _exigir()
            return self.serie.map(lambda t: " ".join(t.split()[:6]))

        def translate(self, idioma):
            _exigir()
            return self.serie.map(lambda t: f"[{idioma}] {t}")

        def similarity(self, otro):
            _exigir()
            return self.serie.map(lambda t: float(sum(p in t.lower() for p in str(otro).lower().split())))

    @pd.api.extensions.register_dataframe_accessor("ai")
    class _ServiciosMarco:
        def __init__(self, marco: "pd.DataFrame") -> None:
            self.marco = marco

        def generate_response(self, prompt, is_prompt_template=False, **kwargs):
            _exigir()
            assert is_prompt_template
            return self.marco.apply(lambda fila: prompt.format(**fila.to_dict())[:60], axis=1)

    _registrar_accesores_ia.disponibilidad = Disponibilidad  # type: ignore[attr-defined]


def _aifunc_simulado() -> tuple[dict[str, types.ModuleType], _ClienteSimulado]:
    cliente = _ClienteSimulado()
    sinapsis = types.ModuleType("synapse")
    ml_pkg = types.ModuleType("synapse.ml")
    modulo = types.ModuleType("synapse.ml.aifunc")
    modulo.default_conf = types.SimpleNamespace(
        model_deployment_name=None, reasoning_effort=None, temperature=1.0, progress_bar_mode=None
    )
    # En el runtime 2.0 `aifunc.session.client` es asincrono: el notebook no debe usarlo.
    modulo.session = types.SimpleNamespace(client=object())
    fabric_pkg = types.ModuleType("synapse.ml.fabric")
    credenciales = types.ModuleType("synapse.ml.fabric.credentials")
    credenciales.get_openai_httpx_sync_client = lambda: object()
    paquete_openai = types.ModuleType("openai")
    paquete_openai.AzureOpenAI = lambda **kwargs: cliente
    sinapsis.ml = ml_pkg
    ml_pkg.aifunc = modulo
    ml_pkg.fabric = fabric_pkg
    fabric_pkg.credentials = credenciales
    return {
        "synapse": sinapsis, "synapse.ml": ml_pkg, "synapse.ml.aifunc": modulo,
        "synapse.ml.fabric": fabric_pkg, "synapse.ml.fabric.credentials": credenciales,
        "openai": paquete_openai,
    }, cliente


@unittest.skipUnless(LIBRERIAS, "requires pandas, numpy and scikit-learn")
class B5Tests(unittest.TestCase):
    fuente = BONUS / "b5_ia_en_notebooks.py"
    parametros = {"p_lakehouse_esperado": "AB_Lakehouse", "p_prefijo": "AB"}

    @classmethod
    def setUpClass(cls) -> None:
        _registrar_accesores_ia()
        cls.disponibilidad = _registrar_accesores_ia.disponibilidad

    def setUp(self) -> None:
        self.disponibilidad.activa = True
        self.mensaje_original = self.disponibilidad.mensaje
        self.addCleanup(setattr, self.disponibilidad, "activa", True)
        self.addCleanup(setattr, self.disponibilidad, "mensaje", self.mensaje_original)
        self.spark = _spark_con_silver()

    def _tablas_de_ml(self) -> None:
        features = _features(self.spark)
        self.spark.tablas["ab_gold_ml_features_cuentas"] = features
        septiembre = features[features["corte"] == "2026-09"].head(8)
        self.spark.tablas["ab_gold_ml_puntuacion_actividad"] = pd.DataFrame({
            "cuenta_id": septiembre["cuenta_id"].to_numpy(),
            "corte": "2026-09",
            "probabilidad_alta_actividad": [0.9 - 0.05 * i for i in range(len(septiembre))],
            "prediccion": 1,
            "version_modelo": 1,
            "fecha_utc": "2026-10-30T12:00:00Z",
        })

    def test_with_ai_available_every_function_adds_its_columns_and_explains_predictions(self) -> None:
        self._tablas_de_ml()
        modulos, cliente = _aifunc_simulado()
        espacio, registro = ejecutar_notebook(self.fuente, self.parametros, self.spark, extra_modulos=modulos)
        self.assertIn("Funciones de IA disponibles:", registro.texto)
        comentarios = espacio["comentarios"]
        self.assertEqual(len(comentarios), 12)
        for columna in ("sentimiento", "tema", "producto", "monto", "ciudad"):
            self.assertIn(columna, comentarios.columns)
        self.assertTrue(set(comentarios["tema"]) <= {"tarjeta", "app o web", "sucursal", "cajero", "comisiones", "otro"})
        top = espacio["top"]
        self.assertEqual(len(top), 5)
        self.assertTrue(top["explicacion"].notna().all())
        self.assertTrue(top["probabilidad_alta_actividad"].is_monotonic_decreasing)
        self.assertEqual(len(cliente.llamadas), 1)
        self.assertEqual(cliente.llamadas[0]["model"], "gpt-5-mini")
        self.assertIs(cliente.llamadas[0]["store"], False)
        conf = modulos["synapse.ml.aifunc"].default_conf
        self.assertEqual((conf.model_deployment_name, conf.reasoning_effort, conf.temperature, conf.progress_bar_mode),
                         ("gpt-5-mini", "low", None, "stats"))
        self.assertEqual(self.spark.escrituras, [])

    def test_on_runtime_1_3_the_temporary_runtime_2_0_setting_is_not_applied(self) -> None:
        modulos, _ = _aifunc_simulado()
        ejecutar_notebook(self.fuente, {**self.parametros, "p_runtime_2_0": "NO"}, self.spark, extra_modulos=modulos)
        self.assertEqual(modulos["synapse.ml.aifunc"].default_conf.temperature, 1.0)

    def test_on_a_trial_capacity_the_notebook_skips_the_ai_cells_instead_of_failing(self) -> None:
        self.disponibilidad.activa = False
        modulos, cliente = _aifunc_simulado()
        espacio, registro = ejecutar_notebook(self.fuente, self.parametros, self.spark, extra_modulos=modulos)
        self.assertIn("Funciones de IA NO disponibles:", registro.texto)
        self.assertIn("RuntimeError", registro.texto)
        self.assertIn("Se omiten las celdas de IA", registro.texto)
        self.assertEqual(list(espacio["comentarios"].columns), ["comentario"])
        self.assertNotIn("top", espacio)
        self.assertEqual(cliente.llamadas, [])

    def test_a_missing_nest_asyncio_is_not_reported_as_a_capacity_problem(self) -> None:
        self.disponibilidad.activa = False
        self.disponibilidad.mensaje = "This event loop is already running"
        modulos, _ = _aifunc_simulado()
        _, registro = ejecutar_notebook(self.fuente, self.parametros, self.spark, extra_modulos=modulos)
        self.assertIn("Falta nest_asyncio", registro.texto)
        self.assertIn("No es un problema de capacidad", registro.texto)
        self.assertNotIn("Requiere capacidad F2", registro.texto)

    def test_the_llm_call_uses_the_synchronous_azure_client_not_the_async_session_client(self) -> None:
        modulos, cliente = _aifunc_simulado()
        ejecutar_notebook(self.fuente, self.parametros, self.spark, extra_modulos=modulos)
        self.assertEqual(len(cliente.llamadas), 1)
        codigo = "\n".join(notebook_percent.celdas_codigo(self.fuente))
        self.assertNotIn("client_sync", codigo)
        self.assertNotIn("aifunc.session", codigo)

    def test_missing_ml_tables_only_skip_the_prediction_explanations(self) -> None:
        modulos, _ = _aifunc_simulado()
        espacio, registro = ejecutar_notebook(self.fuente, self.parametros, self.spark, extra_modulos=modulos)
        self.assertIn("Faltan las tablas de B1 y B3", registro.texto)
        self.assertIn("sentimiento", espacio["comentarios"].columns)
        self.assertNotIn("top", espacio)

    def test_ai_calls_never_receive_real_account_identifiers_outside_the_synthetic_data(self) -> None:
        self._tablas_de_ml()
        modulos, _ = _aifunc_simulado()
        espacio, _ = ejecutar_notebook(self.fuente, self.parametros, self.spark, extra_modulos=modulos)
        self.assertTrue(espacio["top"]["cuenta_id"].str.startswith("CTA").all())


def _features(spark: "SparkSimulado") -> "pd.DataFrame":
    silver = ml.leer_silver(spark, "AB")
    return ml.construir_dataset(
        silver["transacciones"], silver["cuentas"], silver["clientes"],
        ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09"],
    )


class _ConMlflow(unittest.TestCase):
    """Directorio de seguimiento aislado y Spark simulado con la tabla de features."""

    def setUp(self) -> None:
        import mlflow

        self.mlflow = mlflow
        entorno = patch.dict(os.environ, {"MLFLOW_ALLOW_FILE_STORE": "true"})
        entorno.start()
        self.addCleanup(entorno.stop)
        self.directorio = tempfile.TemporaryDirectory()
        self.addCleanup(self.directorio.cleanup)
        uri = Path(self.directorio.name).as_uri()
        mlflow.set_tracking_uri(uri)
        mlflow.set_registry_uri(uri)
        # MLflow recuerda si ya vio `pyspark`; como aqui es un modulo simulado, se olvida al terminar.
        self.addCleanup(self._olvidar_pyspark)
        self.spark = _spark_con_silver()
        self.spark.tablas["ab_gold_ml_features_cuentas"] = _features(self.spark)

    @staticmethod
    def _olvidar_pyspark() -> None:
        from mlflow.utils import import_hooks

        import_hooks._post_import_hooks.pop("pyspark", None)

    def correr(self, fuente: Path, **parametros):
        base = {"p_lakehouse_esperado": "AB_Lakehouse", "p_prefijo": "AB", "p_confirmar_reemplazo": "SI"}
        return ejecutar_notebook(fuente, {**base, **parametros}, self.spark)

    def versiones(self) -> list[int]:
        encontradas = self.mlflow.MlflowClient().search_model_versions("name='ab_modelo_actividad'")
        return sorted(int(v.version) for v in encontradas)


@unittest.skipUnless(LIBRERIAS and MLFLOW, "requires pandas, scikit-learn and mlflow")
class B3Tests(_ConMlflow):
    fuente = BONUS / "b3_registro_puntuacion.py"

    def test_notebook_registers_a_version_scores_the_cutoff_and_reproduces_the_model(self) -> None:
        espacio, registro = self.correr(self.fuente)
        self.assertEqual(self.versiones(), [1])
        version = self.mlflow.MlflowClient().get_model_version("ab_modelo_actividad", "1")
        self.assertEqual(version.tags["tipo_modelo"], "logreg")
        self.assertEqual(version.tags["corte_prueba"], "2026-08")
        self.assertEqual(version.tags["umbral_alta_actividad"], "9")
        self.assertIn("La versión registrada reproduce las probabilidades", registro.texto)
        self.assertIn("MLFlowTransformer no disponible", registro.texto)

        puntuacion = self.spark.tablas["ab_gold_ml_puntuacion_actividad"]
        self.assertEqual(len(puntuacion), 1800)
        self.assertEqual(set(puntuacion["version_modelo"]), {1})
        self.assertEqual(set(puntuacion["corte"]), {"2026-09"})

        umbrales = espacio["tabla_umbrales"]
        self.assertEqual(umbrales["umbral"].tolist(), [0.3, 0.4, 0.5, 0.6, 0.7])
        self.assertTrue(umbrales["marcadas"].is_monotonic_decreasing)
        self.assertTrue(umbrales["recall"].is_monotonic_decreasing)
        self.assertEqual(espacio["firma"].inputs.input_names(), list(ml.FEATURES))

    def test_running_it_again_registers_another_version_but_does_not_duplicate_scores(self) -> None:
        self.correr(self.fuente)
        self.correr(self.fuente)
        self.assertEqual(self.versiones(), [1, 2])
        puntuacion = self.spark.tablas["ab_gold_ml_puntuacion_actividad"]
        self.assertEqual(len(puntuacion), 1800)
        self.assertEqual(set(puntuacion["version_modelo"]), {2})

    def test_without_confirmation_it_trains_but_registers_and_writes_nothing(self) -> None:
        with self.assertRaisesRegex(ValueError, "p_confirmar_reemplazo must be exactly 'SI'"):
            self.correr(self.fuente, p_confirmar_reemplazo="NO")
        self.assertEqual(self.versiones(), [])
        self.assertNotIn("ab_gold_ml_puntuacion_actividad", self.spark.tablas)


@unittest.skipUnless(LIBRERIAS and MLFLOW, "requires pandas, scikit-learn and mlflow")
class B4Tests(_ConMlflow):
    fuente = BONUS / "b4_mlops.py"

    def test_guided_mode_walks_through_the_six_scenarios(self) -> None:
        espacio, registro = self.correr(self.fuente)
        self.assertEqual(espacio["informe_agosto"]["decision"], "promover")
        self.assertEqual(espacio["informe_agosto"]["cortes"]["entrenamiento"], ["2026-05"])
        self.assertIn(espacio["informe_septiembre"]["decision"], ("mantener", "promover"))
        self.assertIsNotNone(espacio["informe_septiembre"]["auc_real_mes_anterior"])
        self.assertIn("Sin duplicados: el ciclo es idempotente.", registro.texto)

        deriva = espacio["informe_deriva"]
        self.assertTrue(deriva["deriva_simulada"])
        self.assertGreaterEqual(deriva["deriva"].get("alta", 0), 4)
        self.assertEqual(deriva["recomendacion"], "revisar")
        self.assertIn(espacio["informe_rf"]["decision"], ("mantener", "promover", "rechazar"))

        tablas = self.spark.tablas
        self.assertEqual(len(tablas["ab_gold_ml_puntuacion_actividad"]), 3600)
        self.assertEqual(set(tablas["ab_gold_ml_puntuacion_actividad"]["corte"]), {"2026-08", "2026-09"})
        derivas = tablas["ab_ml_monitoreo_deriva"]
        self.assertEqual(len(derivas), 2 * len(ml.FEATURES))
        self.assertEqual(set(derivas.loc[derivas["corte"] == "2026-09", "simulada"]), {0})
        desempeno = tablas["ab_ml_monitoreo_desempeno"]
        self.assertEqual(desempeno["corte_prediccion"].tolist(), ["2026-08"])
        eventos = tablas["ab_ml_registro_modelos"]
        self.assertEqual(eventos["secuencia"].tolist(), list(range(1, len(eventos) + 1)))
        self.assertEqual(eventos.iloc[0]["evento"], "promocion")
        self.assertEqual(set(eventos["evento"]) - {"promocion", "reversion"}, set())
        self.assertEqual(self.versiones(), sorted(set(eventos.loc[eventos["evento"] == "promocion", "version"])))

    def test_cycle_mode_runs_one_cycle_and_returns_the_summary_to_the_pipeline(self) -> None:
        _, registro = self.correr(self.fuente, p_modo="ciclo", p_corte_puntuacion="2026-09")
        self.assertEqual(len(registro.salidas), 1)
        resumen = json.loads(registro.salidas[0])
        self.assertEqual(resumen["status"], "success")
        self.assertEqual(resumen["decision"], "promover")
        self.assertEqual(resumen["corte_puntuacion"], "2026-09")
        self.assertEqual(self.versiones(), [1])
        self.assertEqual(len(self.spark.tablas["ab_gold_ml_puntuacion_actividad"]), 1800)
        self.assertNotIn("ab_ml_monitoreo_desempeno", self.spark.tablas)

    def test_cycle_mode_accepts_a_simulated_drift_factor(self) -> None:
        _, registro = self.correr(self.fuente, p_modo="ciclo", p_factor_deriva=1.6)
        resumen = json.loads(registro.salidas[0])
        self.assertTrue(resumen["deriva_simulada"])
        self.assertEqual(resumen["recomendacion"], "revisar")

    def test_without_confirmation_nothing_runs(self) -> None:
        with self.assertRaisesRegex(ValueError, "p_confirmar_reemplazo must be exactly 'SI'"):
            self.correr(self.fuente, p_confirmar_reemplazo="NO")
        self.assertEqual(self.versiones(), [])


class _ClienteRestSimulado:
    """Imita `sempy.fabric.FabricRestClient` para el endpoint de un modelo con una version."""

    def __init__(self, estado: str, mlflow_mod: object, modelo: str, version: int, adulterar: bool = False) -> None:
        self.estado, self.mlflow, self.modelo, self.version, self.adulterar = estado, mlflow_mod, modelo, version, adulterar
        self.llamadas: list[tuple[str, str]] = []

    @staticmethod
    def _respuesta(codigo: int, cuerpo: dict) -> types.SimpleNamespace:
        return types.SimpleNamespace(status_code=codigo, json=lambda: cuerpo)

    def get(self, ruta: str):
        self.llamadas.append(("GET", ruta))
        return self._respuesta(200, {"value": [{"versionName": str(self.version), "status": self.estado}]})

    def post(self, ruta: str, json: dict):
        self.llamadas.append(("POST", ruta))
        entradas = pd.DataFrame(json["inputs"], columns=list(an.FEATURES_TX))
        modelo = self.mlflow.sklearn.load_model(f"models:/{self.modelo}/{self.version}")
        marcas = modelo.predict(entradas)
        if self.adulterar:
            marcas = -marcas
        return self._respuesta(200, {"predictions": [[int(m)] for m in marcas]})


def _sempy_con_endpoint(cliente: "_ClienteRestSimulado", modelo: str) -> dict[str, types.ModuleType]:
    paquete = types.ModuleType("sempy")
    fabric = types.ModuleType("sempy.fabric")
    fabric.list_items = lambda type=None: pd.DataFrame({"Id": ["id-del-modelo"], "Display Name": [modelo], "Type": ["MLModel"]})
    fabric.FabricRestClient = lambda: cliente
    paquete.fabric = fabric
    return {"sempy": paquete, "sempy.fabric": fabric}


def _celda_del_endpoint() -> str:
    for celda in notebook_percent.parsear((BONUS / "b6_anomalias_en_linea.py").read_text(encoding="utf-8"), "b6"):
        if celda.tipo == "code" and celda.contenido.startswith("if p_probar_endpoint"):
            return celda.contenido + "\n"
    raise AssertionError("the endpoint cell was not found")


@unittest.skipUnless(LIBRERIAS and MLFLOW, "requires pandas, scikit-learn and mlflow")
class B6Tests(unittest.TestCase):
    """El notebook completo tarda minutos con el seguimiento en archivos: se ejecuta dos veces y las pruebas leen los resultados."""

    fuente = BONUS / "b6_anomalias_en_linea.py"
    modelo = "ab_modelo_atipicas_tx"
    parametros = {"p_lakehouse_esperado": "AB_Lakehouse", "p_prefijo": "AB", "p_confirmar_reemplazo": "SI"}

    @classmethod
    def setUpClass(cls) -> None:
        import mlflow

        cls.mlflow = mlflow
        cls._entorno = patch.dict(os.environ, {"MLFLOW_ALLOW_FILE_STORE": "true"})
        cls._entorno.start()
        cls._directorio = tempfile.TemporaryDirectory()
        uri = Path(cls._directorio.name).as_uri()
        mlflow.set_tracking_uri(uri)
        mlflow.set_registry_uri(uri)
        cls.spark = _spark_con_silver()
        cls.cliente = _ClienteRestSimulado("Active", mlflow, cls.modelo, 1)
        cls.espacio1, cls.registro1 = ejecutar_notebook(
            cls.fuente, cls.parametros, cls.spark, extra_modulos=_sempy_con_endpoint(cls.cliente, cls.modelo)
        )
        cls.versiones_tras_1 = cls.versiones_b6()
        cls.anomalias_tras_1 = cls.spark.tablas["ab_gold_ml_anomalias_tx"].copy()
        cls.espacio2, cls.registro2 = ejecutar_notebook(cls.fuente, cls.parametros, cls.spark)

    @classmethod
    def tearDownClass(cls) -> None:
        from mlflow.utils import import_hooks

        cls._entorno.stop()
        cls._directorio.cleanup()
        import_hooks._post_import_hooks.pop("pyspark", None)

    @classmethod
    def versiones_b6(cls) -> list[int]:
        return sorted(int(v.version) for v in cls.mlflow.MlflowClient().search_model_versions(f"name='{cls.modelo}'"))

    def _correr_celda_del_endpoint(self, cliente: "_ClienteRestSimulado", **cambios) -> str:
        espacio = {**self.espacio2, **cambios}
        with modulos_falsos(_sempy_con_endpoint(cliente, self.modelo)):
            with contextlib.redirect_stdout(io.StringIO()) as salida:
                exec(compile(_celda_del_endpoint(), "b6[endpoint]", "exec"), espacio)
        return salida.getvalue()

    def test_notebook_trains_registers_scores_and_reproduces_the_model(self) -> None:
        self.assertEqual(self.versiones_tras_1, [1])
        version = self.mlflow.MlflowClient().get_model_version(self.modelo, "1")
        self.assertEqual(version.tags["tipo_detector"], "lof")
        self.assertEqual(version.tags["evaluacion"], "anomalias_inyectadas")
        self.assertEqual(self.espacio1["firma"].inputs.input_names(), list(an.FEATURES_TX))
        self.assertIn("Sin fuga de datos", self.registro1.texto)
        self.assertIn("La versión registrada reproduce los puntajes y las marcas", self.registro1.texto)
        self.assertIn("MLFlowTransformer no disponible", self.registro1.texto)

    def test_the_tables_hold_the_reference_and_the_scored_september_transactions(self) -> None:
        referencia = self.spark.tablas["ab_gold_ml_referencia_tx"]
        self.assertEqual(len(referencia), 9)
        anomalias = self.anomalias_tras_1
        prueba = self.espacio1["prueba"]
        self.assertEqual(set(anomalias["mes"]), {an.MES_PRUEBA})
        self.assertEqual(set(anomalias["version_modelo"]), {1})
        self.assertEqual(len(anomalias), len(prueba))
        self.assertTrue(anomalias["transaccion_id"].is_unique)
        self.assertEqual(int(anomalias["es_anomalia_inyectada"].sum()), int(prueba["es_anomalia_inyectada"].sum()))
        self.assertEqual(set(anomalias.loc[anomalias["es_anomalia_inyectada"] == 1, "tipo_anomalia"]), set(an.TIPOS_ANOMALIA))

    def test_candidate_comparison_prefers_lof_and_explains_why_isolation_forest_fails(self) -> None:
        candidatos = self.espacio1["candidatos"].set_index("nombre")
        self.assertEqual(len(candidatos), 5)
        self.assertTrue(self.espacio1["elegido"].startswith("lof"))
        self.assertGreater(
            candidatos.loc[self.espacio1["elegido"], "average_precision_validacion"],
            3 * candidatos.loc["iforest", "average_precision_validacion"],
        )
        corridas = self.mlflow.search_runs(experiment_names=["ab_exp_atipicas_tx"])
        self.assertEqual(len(corridas), 12)  # cinco candidatos y la corrida final, dos veces

    def test_model_beats_the_baseline_and_sees_every_anomaly_type(self) -> None:
        modelo, base = self.espacio1["metricas_prueba"], self.espacio1["metricas_base_prueba"]
        self.assertGreater(modelo["auc"], 0.9)
        self.assertGreater(modelo["average_precision"], base["average_precision"])
        self.assertGreater(modelo["recall"], base["recall"])
        self.assertGreater(modelo["precision"], 5 * modelo["prevalencia"])
        por_tipo = self.espacio1["por_tipo"].set_index("tipo_anomalia")
        self.assertTrue((por_tipo["recall_modelo"] > 0).all())
        self.assertEqual(por_tipo.loc["rafaga", "recall_linea_base"], 0.0)
        self.assertGreater(por_tipo.loc["rafaga", "recall_modelo"], 0.3)
        self.assertGreater(por_tipo.loc["monto_extremo", "recall_linea_base"], por_tipo.loc["monto_extremo", "recall_modelo"])

    def test_flag_rate_is_close_to_the_review_capacity(self) -> None:
        self.assertAlmostEqual(self.espacio1["metricas_validacion"]["tasa_marcadas"], 0.01, delta=0.002)
        self.assertGreater(self.espacio1["metricas_prueba"]["tasa_marcadas"], 0.003)
        self.assertLess(self.espacio1["metricas_prueba"]["tasa_marcadas"], 0.02)

    def test_monitoring_without_labels_detects_a_simulated_change_in_amounts(self) -> None:
        tasas = self.espacio1["marcadas_por_mes"]["tasa_marcadas"].tolist()
        self.assertGreater(tasas[2], 2.5 * tasas[1])
        simulada = self.espacio1["deriva_simulada"].set_index("variable")
        normal = self.espacio1["deriva_normal"].set_index("variable")
        self.assertEqual(simulada.loc["z_monto_tipo", "deriva"], "alta")
        self.assertEqual(normal.loc["z_monto_tipo", "deriva"], "estable")

    def test_the_single_transaction_request_matches_the_signature_and_ranks_the_suspicious_one_higher(self) -> None:
        cuerpo = self.espacio1["cuerpo"]
        self.assertEqual(cuerpo["formatType"], "dataframe")
        self.assertEqual(len(cuerpo["inputs"]), 2)
        self.assertEqual(len(cuerpo["inputs"][0]), len(an.FEATURES_TX))
        local = self.espacio1["local"]
        self.assertEqual(local["es_atipica"].tolist(), [0, 1])
        self.assertGreater(local["score_anomalia"].iloc[1], local["score_anomalia"].iloc[0])

    def test_an_active_endpoint_is_called_and_agrees_with_the_local_scores(self) -> None:
        self.assertIn("El endpoint coincide con la puntuación local de la misma versión.", self.registro1.texto)
        self.assertEqual([metodo for metodo, _ in self.cliente.llamadas], ["GET", "POST"])
        self.assertTrue(self.cliente.llamadas[1][1].endswith("/mlmodels/id-del-modelo/endpoint/versions/1/score"))

    def test_without_semantic_link_the_notebook_says_so_and_keeps_going(self) -> None:
        self.assertIn("Endpoint del modelo ab_modelo_atipicas_tx → no disponible", self.registro2.texto)

    def test_an_endpoint_that_disagrees_with_the_local_model_stops_the_cell(self) -> None:
        cliente = _ClienteRestSimulado("Active", self.mlflow, self.modelo, 2, adulterar=True)
        with self.assertRaisesRegex(ValueError, "endpoint: expected"):
            self._correr_celda_del_endpoint(cliente)

    def test_an_inactive_endpoint_is_reported_but_never_activated(self) -> None:
        cliente = _ClienteRestSimulado("Deactivated", self.mlflow, self.modelo, 2)
        texto = self._correr_celda_del_endpoint(cliente)
        self.assertIn("Endpoint del modelo ab_modelo_atipicas_tx → ninguna version activa (v2: Deactivated)", texto)
        self.assertEqual([metodo for metodo, _ in cliente.llamadas], ["GET"])

    def test_the_endpoint_check_can_be_switched_off(self) -> None:
        cliente = _ClienteRestSimulado("Active", self.mlflow, self.modelo, 2)
        texto = self._correr_celda_del_endpoint(cliente, p_probar_endpoint="NO")
        self.assertIn("Prueba del endpoint omitida", texto)
        self.assertEqual(cliente.llamadas, [])

    def test_running_it_again_registers_another_version_but_does_not_duplicate_scores(self) -> None:
        self.assertEqual(self.versiones_b6(), [1, 2])
        anomalias = self.spark.tablas["ab_gold_ml_anomalias_tx"]
        self.assertEqual(len(anomalias), len(self.espacio2["prueba"]))
        self.assertEqual(set(anomalias["version_modelo"]), {2})
        self.assertTrue(anomalias["transaccion_id"].is_unique)


@unittest.skipUnless(LIBRERIAS and MLFLOW, "requires pandas, scikit-learn and mlflow")
class B6ProteccionesTests(_ConMlflow):
    fuente = BONUS / "b6_anomalias_en_linea.py"

    def test_without_confirmation_it_trains_but_registers_and_writes_nothing(self) -> None:
        with self.assertRaisesRegex(ValueError, "p_confirmar_reemplazo must be exactly 'SI'"):
            self.correr(self.fuente, p_confirmar_reemplazo="NO")
        encontradas = self.mlflow.MlflowClient().search_model_versions("name='ab_modelo_atipicas_tx'")
        self.assertEqual(list(encontradas), [])
        self.assertNotIn("ab_gold_ml_anomalias_tx", self.spark.tablas)
        self.assertNotIn("ab_gold_ml_referencia_tx", self.spark.tablas)

    def test_missing_silver_tables_stop_the_notebook_before_any_work(self) -> None:
        del self.spark.tablas["ab_silver_transacciones"]
        with self.assertRaisesRegex(ValueError, "ab_silver_transacciones: expected an existing table"):
            self.correr(self.fuente)
        self.assertEqual(self.spark.escrituras, [])

if __name__ == "__main__":
    unittest.main()
