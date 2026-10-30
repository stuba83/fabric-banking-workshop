from __future__ import annotations

import ast
import importlib.util
import sys
import unittest
import warnings
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

LIBRERIAS = all(importlib.util.find_spec(m) for m in ("pandas", "numpy", "sklearn"))
FUENTE = ROOT / "notebooks" / "bonus_ml" / "ml_actividad.py"
CORTES = ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]
POSITIVOS_ESPERADOS = {"2026-05": 563, "2026-06": 589, "2026-07": 631, "2026-08": 651}

if LIBRERIAS:
    import numpy as np
    import pandas as pd

    from notebooks import plata_silver
    from notebooks.bonus_ml import ml_actividad as ml
    from test_plata_silver import bronce_real


def _tablas() -> dict[str, "pd.DataFrame"]:
    tablas = plata_silver.transformar(bronce_real(), "AB").tablas
    return {
        nombre: pd.DataFrame(tablas[nombre].filas, columns=[c for c, _ in tablas[nombre].columnas])
        for nombre in ("silver_transacciones", "silver_cuentas", "silver_clientes")
    }


class SintaxisTests(unittest.TestCase):
    def test_module_uses_syntax_available_in_python_3_10(self) -> None:
        ast.parse(FUENTE.read_text(encoding="utf-8"), feature_version=(3, 10))


@unittest.skipUnless(LIBRERIAS, "requires pandas, numpy and scikit-learn")
class FeaturesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.t = _tablas()
        cls.ds = ml.construir_dataset(
            cls.t["silver_transacciones"], cls.t["silver_cuentas"], cls.t["silver_clientes"], CORTES
        )

    def test_one_row_per_account_and_cutoff_with_the_documented_columns(self) -> None:
        self.assertEqual(list(self.ds.columns), [ml.CLAVE, ml.CORTE, *ml.FEATURES, ml.ETIQUETA])
        self.assertEqual(len(self.ds), 1800 * len(CORTES))
        self.assertEqual(ml.validar_features(self.ds, cuentas_esperadas=1800), [])

    def test_label_counts_are_deterministic_and_the_last_cutoff_is_unlabelled(self) -> None:
        for corte, esperado in POSITIVOS_ESPERADOS.items():
            parte = self.ds[self.ds[ml.CORTE] == corte][ml.ETIQUETA]
            with self.subTest(corte=corte):
                self.assertEqual(int(parte.sum()), esperado)
                self.assertEqual(int(parte.notna().sum()), 1800)
        ultimo = self.ds[self.ds[ml.CORTE] == "2026-09"][ml.ETIQUETA]
        self.assertTrue(ultimo.isna().all())

    def test_features_never_use_data_after_the_cutoff(self) -> None:
        # Si se eliminan los movimientos posteriores al corte, las variables no cambian.
        tx = self.t["silver_transacciones"]
        fin = pd.Timestamp("2026-07-31 23:59:59")
        recortadas = ml.construir_features(
            tx[pd.to_datetime(tx["fecha_hora"]).dt.tz_localize(None) <= fin],
            self.t["silver_cuentas"],
            self.t["silver_clientes"],
            "2026-07",
        )
        completas = self.ds[self.ds[ml.CORTE] == "2026-07"].reset_index(drop=True)
        pd.testing.assert_frame_equal(
            recortadas[[ml.CLAVE, *ml.FEATURES]], completas[[ml.CLAVE, *ml.FEATURES]]
        )
        # Sin datos de agosto no se puede etiquetar: la etiqueta queda vacia.
        self.assertTrue(recortadas[ml.ETIQUETA].isna().all())

    def test_label_matches_a_manual_count_of_the_next_month(self) -> None:
        tx = self.t["silver_transacciones"].copy()
        tx["mes"] = pd.to_datetime(tx["fecha_hora"]).dt.strftime("%Y-%m")
        agosto = tx[tx["mes"] == "2026-08"].groupby("cuenta_id").size()
        julio = self.ds[self.ds[ml.CORTE] == "2026-07"].set_index(ml.CLAVE)
        for cuenta in ("CTA000001", "CTA000002", "CTA000500", "CTA001800"):
            esperado = float(agosto.get(cuenta, 0) >= ml.UMBRAL_ALTA_ACTIVIDAD)
            with self.subTest(cuenta=cuenta):
                self.assertEqual(julio.loc[cuenta, ml.ETIQUETA], esperado)

    def test_window_features_are_consistent_with_the_data(self) -> None:
        tx = self.t["silver_transacciones"].copy()
        tx["mes"] = pd.to_datetime(tx["fecha_hora"]).dt.strftime("%Y-%m")
        julio = self.ds[self.ds[ml.CORTE] == "2026-07"].set_index(ml.CLAVE)
        jul = tx[tx["mes"] == "2026-07"].groupby("cuenta_id").size()
        jun = tx[tx["mes"] == "2026-06"].groupby("cuenta_id").size()
        cuenta = "CTA000001"
        self.assertEqual(julio.loc[cuenta, "tx_mes_corte"], jul.get(cuenta, 0))
        self.assertEqual(julio.loc[cuenta, "tx_mes_previo"], jun.get(cuenta, 0))
        self.assertTrue((julio["tx_ventana"] == julio["tx_mes_corte"] + julio["tx_mes_previo"]).all())
        self.assertEqual(int(julio["tx_ventana"].sum()), int(jul.sum() + jun.sum()))

    def test_sensitive_attributes_are_not_model_features(self) -> None:
        for variable in ml.VARIABLES_PARA_AUDITORIA:
            self.assertNotIn(variable, ml.FEATURES)
            self.assertNotIn(variable, self.ds.columns)

    def test_missing_input_columns_are_reported(self) -> None:
        with self.assertRaisesRegex(ValueError, r"transacciones: expected columns.*'canal'"):
            ml.construir_features(
                self.t["silver_transacciones"].drop(columns=["canal"]),
                self.t["silver_cuentas"],
                self.t["silver_clientes"],
                "2026-06",
            )

    def test_validator_reports_broken_data(self) -> None:
        roto = self.ds.copy()
        roto.loc[0, "tx_mes_corte"] = -1
        roto.loc[1, "pct_credito"] = 1.5
        roto.loc[2, "segmento"] = None
        roto = pd.concat([roto, roto.iloc[[3]]], ignore_index=True)
        problemas = " | ".join(ml.validar_features(roto, cuentas_esperadas=1800))
        for esperado in ("duplicates", "tx_mes_corte", "pct_credito", "segmento", "expected 1800 rows"):
            self.assertIn(esperado, problemas)
        self.assertIn("columns: expected", ml.validar_features(self.ds.drop(columns=["segmento"]))[0])


@unittest.skipUnless(LIBRERIAS, "requires pandas, numpy and scikit-learn")
class DivisionTemporalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        t = _tablas()
        cls.ds = ml.construir_dataset(
            t["silver_transacciones"], t["silver_cuentas"], t["silver_clientes"], CORTES
        )

    def test_default_split_is_temporal_and_has_the_expected_sizes(self) -> None:
        partes = ml.dividir_temporal(self.ds)
        self.assertEqual(
            {nombre: len(parte) for nombre, parte in partes.items()},
            {"entrenamiento": 3600, "validacion": 1800, "prueba": 1800, "puntuacion": 1800},
        )
        self.assertEqual(set(partes["entrenamiento"][ml.CORTE]), {"2026-05", "2026-06"})
        self.assertEqual(set(partes["validacion"][ml.CORTE]), {"2026-07"})
        self.assertEqual(set(partes["prueba"][ml.CORTE]), {"2026-08"})
        self.assertTrue(partes["puntuacion"][ml.ETIQUETA].isna().all())

    def test_overlapping_or_unordered_cutoffs_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            ml.dividir_temporal(self.ds, entrenamiento=("2026-05", "2026-07"), validacion="2026-07")
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            ml.dividir_temporal(self.ds, validacion="2026-08", prueba="2026-07")

    def test_labelled_scoring_rows_or_unlabelled_training_rows_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "puntuacion: expected an empty label"):
            ml.dividir_temporal(
                self.ds, entrenamiento=("2026-05",), validacion="2026-06", prueba="2026-07",
                puntuacion="2026-08",
            )
        with self.assertRaisesRegex(ValueError, "entrenamiento: expected labelled rows"):
            ml.dividir_temporal(
                self.ds, entrenamiento=("2026-08", "2026-09"), validacion="2026-10",
                prueba="2026-11", puntuacion="2026-12",
            )


@unittest.skipUnless(LIBRERIAS, "requires pandas, numpy and scikit-learn")
class ModeloTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        warnings.simplefilter("ignore")
        t = _tablas()
        cls.t = t
        ds = ml.construir_dataset(
            t["silver_transacciones"], t["silver_cuentas"], t["silver_clientes"], CORTES
        )
        cls.partes = ml.dividir_temporal(ds)
        entrenamiento = cls.partes["entrenamiento"]
        cls.modelo = ml.crear_modelo("logreg").fit(
            entrenamiento[list(ml.FEATURES)], entrenamiento[ml.ETIQUETA].astype(int)
        )

    def test_logistic_model_beats_chance_and_is_close_to_the_documented_value(self) -> None:
        prueba = self.partes["prueba"]
        probabilidad = self.modelo.predict_proba(prueba[list(ml.FEATURES)])[:, 1]
        metricas = ml.evaluar_clasificador(prueba[ml.ETIQUETA], probabilidad)
        self.assertGreater(metricas["auc"], 0.80)
        self.assertLess(metricas["auc"], 0.92)
        self.assertAlmostEqual(metricas["prevalencia"], 651 / 1800, places=6)
        self.assertTrue(0 <= metricas["brier"] <= 0.25)

    def test_simple_rule_is_a_meaningful_baseline(self) -> None:
        prueba = self.partes["prueba"]
        metricas = ml.evaluar_clasificador(prueba[ml.ETIQUETA], ml.baseline_regla(prueba))
        self.assertGreater(metricas["auc"], 0.75)

    def test_every_model_type_trains_and_unknown_types_fail(self) -> None:
        entrenamiento = self.partes["entrenamiento"].head(600)
        for tipo in ("logreg", "rf", "hgb"):
            with self.subTest(tipo=tipo):
                modelo = ml.crear_modelo(tipo).fit(
                    entrenamiento[list(ml.FEATURES)], entrenamiento[ml.ETIQUETA].astype(int)
                )
                self.assertEqual(modelo.predict_proba(entrenamiento[list(ml.FEATURES)]).shape, (600, 2))
        with self.assertRaisesRegex(ValueError, "tipo: expected one of"):
            ml.crear_modelo("xgb")

    def test_permutation_importance_lists_every_feature(self) -> None:
        tabla = ml.importancia_permutacion(self.modelo, self.partes["validacion"], repeticiones=2)
        self.assertEqual(set(tabla["variable"]), set(ml.FEATURES))
        self.assertIn(tabla.iloc[0]["variable"], ("tx_ventana", "tx_mes_previo", "tx_mes_corte"))

    def test_scoring_output_has_probability_prediction_and_keys(self) -> None:
        puntuacion = ml.puntuar(self.modelo, self.partes["puntuacion"])
        self.assertEqual(
            list(puntuacion.columns),
            [ml.CLAVE, ml.CORTE, "probabilidad_alta_actividad", "prediccion"],
        )
        self.assertEqual(len(puntuacion), 1800)
        self.assertTrue(puntuacion["probabilidad_alta_actividad"].between(0, 1).all())
        self.assertTrue(set(puntuacion["prediccion"]) <= {0, 1})
        self.assertEqual(set(puntuacion[ml.CORTE]), {"2026-09"})

    def test_group_audit_covers_every_group_and_handles_single_class_groups(self) -> None:
        prueba = self.partes["prueba"]
        clientes = self.t["silver_cuentas"].merge(
            self.t["silver_clientes"][["cliente_id", "grupo_edad"]], on="cliente_id"
        )[["cuenta_id", "grupo_edad"]]
        tabla = prueba.merge(clientes, on="cuenta_id")
        probabilidad = self.modelo.predict_proba(tabla[list(ml.FEATURES)])[:, 1]
        auditoria = ml.metricas_por_grupo(tabla[ml.ETIQUETA], probabilidad, tabla["grupo_edad"])
        self.assertEqual(set(auditoria["grupo"]), {"18-29", "30-44", "45-59", "60+"})
        self.assertEqual(int(auditoria["filas"].sum()), 1800)
        unico = ml.metricas_por_grupo([1, 1, 1], [0.9, 0.8, 0.7], ["a", "a", "a"])
        self.assertTrue(np.isnan(unico.loc[0, "auc"]))


@unittest.skipUnless(LIBRERIAS, "requires pandas, numpy and scikit-learn")
class MonitoreoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        t = _tablas()
        ds = ml.construir_dataset(
            t["silver_transacciones"], t["silver_cuentas"], t["silver_clientes"], CORTES
        )
        cls.partes = ml.dividir_temporal(ds)

    def test_psi_is_zero_for_identical_samples_and_large_for_a_shift(self) -> None:
        muestra = np.random.default_rng(1).normal(size=2000)
        self.assertAlmostEqual(ml.psi_numerico(muestra, muestra), 0.0, places=9)
        self.assertGreater(ml.psi_numerico(muestra, muestra + 1.5), ml.UMBRAL_PSI_ALTO)
        self.assertAlmostEqual(ml.psi_categorico(["a", "b"] * 50, ["a", "b"] * 50), 0.0, places=9)
        self.assertGreater(ml.psi_categorico(["a"] * 90 + ["b"] * 10, ["a"] * 10 + ["b"] * 90), 1.0)

    def test_psi_handles_constant_reference_new_categories_and_empty_samples(self) -> None:
        self.assertGreater(ml.psi_numerico([0.0] * 100, [0.0] * 50 + [5.0] * 50), ml.UMBRAL_PSI_ALTO)
        self.assertGreater(ml.psi_categorico(["a"] * 100, ["a"] * 50 + ["nueva"] * 50), ml.UMBRAL_PSI_ALTO)
        with self.assertRaisesRegex(ValueError, "non-empty"):
            ml.psi_numerico([], [1.0])
        with self.assertRaisesRegex(ValueError, "non-empty"):
            ml.psi_categorico(["a"], [])

    def test_real_months_are_stable_and_the_simulated_campaign_is_detected(self) -> None:
        real = ml.reporte_deriva(self.partes["entrenamiento"], self.partes["puntuacion"])
        self.assertEqual(len(real), len(ml.FEATURES))
        self.assertLess(real["psi"].max(), ml.UMBRAL_PSI_ALTO)
        self.assertEqual(ml.evaluar_alertas(real)["recomendacion"], "sin_accion")

        simulada = ml.simular_deriva_actividad(self.partes["puntuacion"], factor=1.6)
        reporte = ml.reporte_deriva(self.partes["entrenamiento"], simulada)
        altas = set(reporte.loc[reporte["deriva"] == "alta", "variable"])
        self.assertTrue({"tx_mes_corte", "tx_mes_previo", "tx_ventana", "monto_ventana"} <= altas)
        self.assertEqual(ml.evaluar_alertas(reporte)["recomendacion"], "revisar")
        self.assertTrue(
            (simulada["tx_ventana"] == simulada["tx_mes_corte"] + simulada["tx_mes_previo"]).all()
        )
        with self.assertRaisesRegex(ValueError, "factor: expected a positive number"):
            ml.simular_deriva_actividad(self.partes["puntuacion"], factor=0)

    def test_psi_bands(self) -> None:
        self.assertEqual(ml.clasificar_psi(0.05), "estable")
        self.assertEqual(ml.clasificar_psi(0.10), "moderada")
        self.assertEqual(ml.clasificar_psi(0.25), "alta")

    def test_alerts_recommend_retraining_only_when_performance_falls(self) -> None:
        reporte = ml.reporte_deriva(self.partes["entrenamiento"], self.partes["puntuacion"])
        caida = ml.evaluar_alertas(reporte, auc_actual=0.78, auc_referencia=0.85)
        self.assertEqual(caida["recomendacion"], "reentrenar")
        estable = ml.evaluar_alertas(reporte, auc_actual=0.84, auc_referencia=0.85)
        self.assertEqual(estable["recomendacion"], "sin_accion")


class PromocionTests(unittest.TestCase):
    @unittest.skipUnless(LIBRERIAS, "requires pandas, numpy and scikit-learn")
    def test_promotion_rule(self) -> None:
        casos = [
            ({"auc": 0.86}, None, "promover"),
            ({"auc": 0.86}, {"auc": 0.855}, "promover"),
            ({"auc": 0.856}, {"auc": 0.855}, "mantener"),
            ({"auc": 0.84}, {"auc": 0.855}, "mantener"),
            ({"auc": 0.65}, {"auc": 0.60}, "rechazar"),
            ({"auc": float("nan")}, None, "rechazar"),
        ]
        for retador, campeon, esperado in casos:
            with self.subTest(retador=retador, campeon=campeon):
                decision = ml.decidir_promocion(retador, campeon)
                self.assertEqual(decision["decision"], esperado)
                self.assertTrue(decision["motivo"])

    @unittest.skipUnless(LIBRERIAS, "requires pandas, numpy and scikit-learn")
    def test_rows_for_spark_use_native_types_and_none(self) -> None:
        df = pd.DataFrame(
            {
                "a": np.array([1, 2], dtype="int64"),
                "b": [0.5, float("nan")],
                "c": ["x", "y"],
            }
        )
        filas = ml.a_filas(df)
        self.assertEqual(filas, [(1, 0.5, "x"), (2, None, "y")])
        self.assertIs(type(filas[0][0]), int)
        self.assertIs(type(filas[0][1]), float)


if __name__ == "__main__":
    unittest.main()
