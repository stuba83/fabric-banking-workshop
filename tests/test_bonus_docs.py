from __future__ import annotations

import importlib.util
import inspect
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import notebook_percent

LIBRERIAS = all(importlib.util.find_spec(m) for m in ("pandas", "numpy", "sklearn"))
if LIBRERIAS:
    from notebooks.bonus_ml import anomalias_tx as an
    from notebooks.bonus_ml import ml_actividad as ml

BONUS_DOCS = ROOT / "docs" / "bonus-ml"
BONUS_NB = ROOT / "notebooks" / "bonus_ml"
MODULOS = {
    "B1": ("modulo-1-preparacion.md", "b1_preparacion_datos.py", "B1_preparacion_datos.ipynb"),
    "B2": ("modulo-2-entrenamiento.md", "b2_entrenamiento_mlflow.py", "B2_entrenamiento_mlflow.ipynb"),
    "B3": ("modulo-3-registro-puntuacion.md", "b3_registro_puntuacion.py", "B3_registro_puntuacion.ipynb"),
    "B4": ("modulo-4-mlops.md", "b4_mlops.py", "B4_mlops.ipynb"),
    "B5": ("modulo-5-ia.md", "b5_ia_en_notebooks.py", "B5_ia_en_notebooks.ipynb"),
}
TERMINOS_PROHIBIDOS = re.compile(
    r"purview|coopenae|\bgbm\b|corripio|mariposa|bia foods|ficohsa|\bseti\b|dokka|\bmeco\b",
    re.IGNORECASE,
)


def _leer(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8")


def _parametros(fuente: Path) -> list[str]:
    for celda in notebook_percent.parsear(_leer(fuente), fuente.name):
        if celda.tipo == "parameters":
            return re.findall(r"^(p_\w+)\s*=", celda.contenido, re.MULTILINE)
    return []


class DocumentacionDelBonusTests(unittest.TestCase):
    def test_every_module_has_a_guide_a_source_and_a_rendered_notebook(self) -> None:
        guia = _leer(BONUS_DOCS / "guia.md")
        readme = _leer(ROOT / "README.md")
        for modulo, (doc, fuente, notebook) in MODULOS.items():
            with self.subTest(modulo=modulo):
                self.assertTrue((BONUS_DOCS / doc).is_file())
                self.assertTrue((BONUS_NB / fuente).is_file())
                self.assertTrue((BONUS_NB / notebook).is_file())
                self.assertIn(doc, guia)
                self.assertIn(notebook, guia)
                self.assertIn(f"docs/bonus-ml/{doc}", readme)
                self.assertIn(f"notebooks/bonus_ml/{notebook}", readme)
                self.assertIn(notebook, _leer(BONUS_DOCS / doc))

    def test_modules_chain_to_the_next_one_and_end_at_the_evidence_template(self) -> None:
        orden = [doc for doc, _, _ in MODULOS.values()]
        for actual, siguiente in zip(orden, orden[1:]):
            with self.subTest(actual=actual):
                self.assertIn(siguiente, _leer(BONUS_DOCS / actual))
        self.assertIn("evidencias.md", _leer(BONUS_DOCS / orden[-1]))
        self.assertTrue((BONUS_DOCS / "evidencias.md").is_file())

    def test_every_notebook_parameter_is_documented_in_the_guide(self) -> None:
        guia = _leer(BONUS_DOCS / "guia.md")
        for modulo, (_, fuente, _) in MODULOS.items():
            for parametro in _parametros(BONUS_NB / fuente):
                with self.subTest(modulo=modulo, parametro=parametro):
                    self.assertIn(f"`{parametro}`", guia)

    def test_bonus_files_do_not_mention_organizations_or_retired_products(self) -> None:
        archivos = [*BONUS_DOCS.glob("*.md"), *BONUS_NB.glob("*.py"), *BONUS_NB.glob("*.ipynb")]
        self.assertGreater(len(archivos), 12)
        for archivo in archivos:
            with self.subTest(archivo=archivo.name):
                self.assertIsNone(TERMINOS_PROHIBIDOS.search(_leer(archivo)))

    def test_trial_limits_are_stated_wherever_ai_features_are_described(self) -> None:
        for ruta in (
            BONUS_DOCS / "guia.md",
            BONUS_DOCS / "modulo-5-ia.md",
            ROOT / "README.md",
            BONUS_NB / "b5_ia_en_notebooks.py",
        ):
            texto = _leer(ruta)
            with self.subTest(archivo=ruta.name):
                self.assertIn("Trial", texto)
                self.assertRegex(texto, r"F2")

    def test_the_guide_tells_what_was_and_was_not_verified(self) -> None:
        guia = _leer(BONUS_DOCS / "guia.md")
        self.assertIn("No verificado en un tenant de Fabric", guia)
        self.assertIn("Estado de verificación", guia)

    def test_module_guides_end_with_blockers_and_a_next_step(self) -> None:
        for modulo, (doc, _, _) in MODULOS.items():
            texto = _leer(BONUS_DOCS / doc)
            with self.subTest(modulo=modulo):
                self.assertIn("## Bloqueos frecuentes", texto)
                self.assertIn("## Siguiente", texto)
                self.assertIn("## Qué documentar en las evidencias", texto)


@unittest.skipUnless(LIBRERIAS, "requires pandas, numpy and scikit-learn")
class DocumentacionFrenteAlCodigoTests(unittest.TestCase):
    def test_documented_controls_match_the_code_constants(self) -> None:
        guia = _leer(BONUS_DOCS / "guia.md")
        modulo1 = _leer(BONUS_DOCS / "modulo-1-preparacion.md")
        for conteo in ("563", "589", "631", "651", "9.000", "3.600", "1.800"):
            with self.subTest(conteo=conteo):
                self.assertIn(conteo, guia)
        for conteo in ("563", "589", "631", "651", "9.000"):
            self.assertIn(conteo, modulo1)
        self.assertEqual(ml.UMBRAL_ALTA_ACTIVIDAD, 9)
        self.assertIn("al menos 9 transacciones", guia)
        self.assertEqual(ml.CORTES_ENTRENAMIENTO, ("2026-05", "2026-06"))
        self.assertEqual((ml.CORTE_VALIDACION, ml.CORTE_PRUEBA, ml.CORTE_PUNTUACION), ("2026-07", "2026-08", "2026-09"))
        for corte in (*ml.CORTES_ENTRENAMIENTO, ml.CORTE_VALIDACION, ml.CORTE_PRUEBA, ml.CORTE_PUNTUACION):
            self.assertIn(corte, guia)

    def test_documented_promotion_rule_matches_the_function_defaults(self) -> None:
        parametros = inspect.signature(ml.decidir_promocion).parameters
        modulo4 = _leer(BONUS_DOCS / "modulo-4-mlops.md")
        self.assertEqual(parametros["margen_minimo"].default, 0.005)
        self.assertEqual(parametros["piso"].default, 0.70)
        self.assertIn("0,005", modulo4)
        self.assertIn("0,70", modulo4)
        self.assertEqual(ml.UMBRAL_PSI_ALTO, 0.25)
        self.assertEqual(ml.UMBRAL_PSI_MODERADO, 0.10)
        self.assertIn("0,25", modulo4)

    def test_every_created_table_experiment_and_model_is_documented(self) -> None:
        guia = _leer(BONUS_DOCS / "guia.md")
        for clave, nombre in ml.nombres_ml("AB").items():
            with self.subTest(clave=clave):
                self.assertIn(nombre, guia)

    def test_the_six_mlops_scenarios_are_documented_in_the_module_and_in_the_notebook(self) -> None:
        modulo4 = _leer(BONUS_DOCS / "modulo-4-mlops.md")
        notebook = _leer(BONUS_NB / "b4_mlops.py")
        for numero in range(1, 7):
            with self.subTest(escenario=numero):
                self.assertRegex(modulo4, rf"\|\s*{numero}\s*\|")
                self.assertIn(f"Escenario {numero}", notebook)

    def test_sensitive_attributes_are_documented_as_excluded_from_the_model(self) -> None:
        guia = _leer(BONUS_DOCS / "guia.md")
        for variable in ml.VARIABLES_PARA_AUDITORIA:
            with self.subTest(variable=variable):
                self.assertIn(f"`{variable}`", guia)
                self.assertNotIn(variable, ml.FEATURES)

@unittest.skipUnless(LIBRERIAS, "requires pandas, numpy and scikit-learn")
class DocumentacionDeB6FrenteAlCodigoTests(unittest.TestCase):
    modulo = BONUS_DOCS / "modulo-6-anomalias-en-linea.md"
    notebook = BONUS_NB / "b6_anomalias_en_linea.py"

    def test_documented_constants_match_the_code(self) -> None:
        texto = _leer(self.modulo)
        self.assertEqual(an.MESES_ENTRENAMIENTO, ("2026-05", "2026-06", "2026-07"))
        self.assertEqual((an.MES_VALIDACION, an.MES_PRUEBA), ("2026-08", "2026-09"))
        self.assertEqual((an.SEMILLA_VALIDACION, an.SEMILLA_PRUEBA), (11, 23))
        self.assertIn("semilla 11", texto)
        self.assertIn("semilla 23", texto)
        self.assertEqual(an.MINIMO_HISTORIAL, 10)
        self.assertIn("al menos **10 previas**", texto)
        self.assertEqual(an.VENTANA_CANAL, 10)
        self.assertIn("**últimas 10**", texto)
        self.assertEqual((an.TASA_REVISION, an.TASA_INYECCION, an.ENTRENAMIENTO_MAXIMO), (0.01, 0.01, 20000))
        self.assertIn("p_tasa_revision = 0.01", _leer(self.notebook))
        self.assertIn("muestra de 20 000 filas", texto)

    def test_every_anomaly_type_and_feature_is_documented_in_the_module_and_the_notebook(self) -> None:
        modulo, notebook = _leer(self.modulo), _leer(self.notebook)
        for tipo in an.TIPOS_ANOMALIA:
            with self.subTest(tipo=tipo):
                self.assertIn(f"`{tipo}`", modulo)
                self.assertIn(f"`{tipo}`", notebook)
        for variable in an.FEATURES_TX:
            with self.subTest(variable=variable):
                self.assertIn(f"`{variable}`", modulo)
                self.assertIn(f"`{variable}`", notebook)

    def test_every_created_table_experiment_and_model_is_documented_in_the_guide(self) -> None:
        guia = _leer(BONUS_DOCS / "guia.md")
        for clave, nombre in an.nombres_anomalias("AB").items():
            with self.subTest(clave=clave):
                self.assertIn(nombre, guia)
                if clave in ("referencia", "anomalias"):
                    self.assertIn(nombre.replace("ab_", "<prefijo>_", 1), _leer(self.modulo))

    def test_documented_counts_match_what_the_code_produces(self) -> None:
        from test_anomalias_tx import silver_transacciones

        tx = an.preparar_transacciones(silver_transacciones())
        meses = tx["fecha_hora"].dt.strftime("%Y-%m")
        referencia = an.calcular_referencia(tx.loc[meses.isin(an.MESES_ENTRENAMIENTO)])
        evaluacion = an.inyectar_anomalias(tx, {an.MES_VALIDACION: an.SEMILLA_VALIDACION, an.MES_PRUEBA: an.SEMILLA_PRUEBA})
        features = an.construir_features_tx(evaluacion, referencia)
        conteos = features.groupby("mes").size()
        entrenamiento = int(conteos.loc[list(an.MESES_ENTRENAMIENTO)].sum())
        inyectadas = features.groupby("mes")["es_anomalia_inyectada"].sum()
        miles = lambda n: f"{n:,}".replace(",", ".")
        modulo, guia = _leer(self.modulo), _leer(BONUS_DOCS / "guia.md")
        esperado = f"{miles(entrenamiento)} / {miles(int(conteos[an.MES_VALIDACION]))} / {miles(int(conteos[an.MES_PRUEBA]))}"
        for texto in (modulo, guia, _leer(BONUS_DOCS / "evidencias.md")):
            self.assertIn(esperado, texto)
        self.assertIn(miles(int(conteos.sum())), modulo)
        self.assertEqual((int(inyectadas["2026-08"]), int(inyectadas["2026-09"])), (125, 130))
        self.assertIn("125 (25 + 25 + 75) y 130 (26 + 26 + 78)", modulo)
        self.assertIn(miles(int(conteos[an.MES_PRUEBA])), modulo)
        self.assertEqual(len(referencia), 9)

    def test_the_module_documents_what_the_endpoint_notebook_never_does(self) -> None:
        modulo, notebook = _leer(self.modulo), _leer(self.notebook)
        self.assertIn("El notebook **no activa nada**", modulo)
        self.assertIn("**no activa nada**", notebook)
        self.assertIn("vista previa", modulo)
        self.assertIn("No prometas un SLA", modulo)


if __name__ == "__main__":
    unittest.main()
