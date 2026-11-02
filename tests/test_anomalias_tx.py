from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

LIBRERIAS = all(importlib.util.find_spec(m) for m in ("pandas", "numpy", "sklearn"))
if LIBRERIAS:
    import numpy as np
    import pandas as pd

    from notebooks import plata_silver
    from notebooks.bonus_ml import anomalias_tx as an
    from test_plata_silver import bronce_real

_SILVER: dict[str, "pd.DataFrame"] = {}


def silver_transacciones() -> "pd.DataFrame":
    if "tx" not in _SILVER:
        tablas = plata_silver.transformar(bronce_real(), "AB").tablas
        origen = tablas["silver_transacciones"]
        _SILVER["tx"] = pd.DataFrame(origen.filas, columns=[c for c, _ in origen.columnas])
    return _SILVER["tx"].copy()


def _referencia_manual(mediana: float = 7.0, mad: float = 0.5) -> "pd.DataFrame":
    return pd.DataFrame(
        {"tipo_transaccion": ["COMPRA"], "mediana_log_monto": [mediana], "mad_log_monto": [mad], "max_monto": [5000.0]}
    )


def _cuenta_de_ejemplo() -> "pd.DataFrame":
    """Doce compras de una cuenta, una por hora; los canales y montos se conocen de antemano."""
    canales = ["WEB"] * 8 + ["ATM"] * 2 + ["WEB", "ATM"]
    return pd.DataFrame(
        {
            "transaccion_id": [f"T{i:02d}" for i in range(12)],
            "cuenta_id": "CTA1",
            "fecha_hora": pd.date_range("2026-05-01 08:00:00", periods=12, freq="h"),
            "tipo_transaccion": "COMPRA",
            "direccion": "DEBITO",
            "canal": canales,
            "monto": [100.0 * (i + 1) for i in range(12)],
        }
    )


@unittest.skipUnless(LIBRERIAS, "requires pandas, numpy and scikit-learn")
class PrepararYReferenciaTests(unittest.TestCase):
    def test_transactions_are_sorted_and_the_timezone_is_dropped(self) -> None:
        desordenadas = _cuenta_de_ejemplo().iloc[::-1].copy()
        desordenadas["fecha_hora"] = pd.to_datetime(desordenadas["fecha_hora"]).dt.tz_localize("UTC")
        preparadas = an.preparar_transacciones(desordenadas)
        self.assertEqual(preparadas["transaccion_id"].tolist(), [f"T{i:02d}" for i in range(12)])
        self.assertIsNone(preparadas["fecha_hora"].dt.tz)

    def test_invalid_inputs_are_rejected_with_a_clear_message(self) -> None:
        with self.assertRaisesRegex(ValueError, "transacciones: expected columns"):
            an.preparar_transacciones(_cuenta_de_ejemplo().drop(columns=["canal"]))
        negativa = _cuenta_de_ejemplo()
        negativa.loc[0, "monto"] = -5.0
        with self.assertRaisesRegex(ValueError, "expected positive amounts"):
            an.preparar_transacciones(negativa)
        duplicada = pd.concat([_cuenta_de_ejemplo(), _cuenta_de_ejemplo().head(1)])
        with self.assertRaisesRegex(ValueError, "expected unique transaccion_id"):
            an.preparar_transacciones(duplicada)

    def test_reference_has_one_row_per_type_with_robust_statistics_and_a_floor(self) -> None:
        tx = silver_transacciones()
        referencia = an.calcular_referencia(tx, fecha_utc="2026-11-01T00:00:00Z")
        self.assertEqual(len(referencia), 9)
        self.assertEqual(int(referencia["filas"].sum()), len(tx))
        self.assertTrue((referencia["mad_log_monto"] >= an.PISO_MAD).all())
        compra = referencia.set_index("tipo_transaccion").loc["COMPRA"]
        montos = tx.loc[tx["tipo_transaccion"] == "COMPRA", "monto"].astype(float)
        self.assertAlmostEqual(compra["max_monto"], montos.max())
        self.assertAlmostEqual(compra["mediana_log_monto"], float(np.log(montos).median()))
        constante = _cuenta_de_ejemplo().assign(monto=500.0)
        self.assertEqual(an.calcular_referencia(constante)["mad_log_monto"].iloc[0], an.PISO_MAD)

    def test_table_names_use_the_lowercase_prefix(self) -> None:
        nombres = an.nombres_anomalias("AB")
        self.assertEqual(set(nombres), {"referencia", "anomalias", "experimento", "modelo"})
        self.assertTrue(all(v.startswith("ab_") for v in nombres.values()))


@unittest.skipUnless(LIBRERIAS, "requires pandas, numpy and scikit-learn")
class VariablesTests(unittest.TestCase):
    def test_features_of_a_known_account_are_computed_by_hand(self) -> None:
        referencia = _referencia_manual()
        features = an.construir_features_tx(_cuenta_de_ejemplo(), referencia)
        self.assertEqual(features["transaccion_id"].tolist(), ["T10", "T11"])
        self.assertEqual(features["n_previas"].tolist(), [10, 11])
        # T10 (WEB): de las 10 previas, 8 fueron WEB. T11 (ATM): de las 10 ultimas (T01 a T10), 2 fueron ATM.
        self.assertEqual(features["pct_canal_historial"].round(6).tolist(), [0.8, 0.2])
        self.assertEqual(features["tx_ultimas_24h"].tolist(), [10, 11])
        self.assertEqual(features["log_minutos_desde_ultima"].round(6).tolist(), [round(float(np.log1p(60)), 6)] * 2)
        self.assertEqual(features["hora"].tolist(), [18, 19])
        self.assertEqual(features["es_fin_semana"].tolist(), [0, 0])
        esperado = (np.log(np.array([1100.0, 1200.0])) - 7.0) / 0.5
        np.testing.assert_allclose(features["z_monto_tipo"], esperado)
        self.assertEqual(features["canal"].tolist(), ["WEB", "ATM"])

    def test_a_transaction_needs_enough_history_in_its_own_account(self) -> None:
        referencia = _referencia_manual()
        self.assertTrue(an.construir_features_tx(_cuenta_de_ejemplo().head(10), referencia).empty)
        self.assertEqual(len(an.construir_features_tx(_cuenta_de_ejemplo().head(10), referencia, minimo_historial=3)), 7)

    def test_the_window_only_counts_the_last_24_hours(self) -> None:
        espaciadas = _cuenta_de_ejemplo()
        espaciadas["fecha_hora"] = pd.date_range("2026-05-01 08:00:00", periods=12, freq="12h")
        features = an.construir_features_tx(espaciadas, _referencia_manual())
        self.assertEqual(features["tx_ultimas_24h"].tolist(), [2, 2])

    def test_unknown_transaction_types_are_rejected(self) -> None:
        tx = _cuenta_de_ejemplo().assign(tipo_transaccion="OTRO")
        with self.assertRaisesRegex(ValueError, "referencia: expected every transaction type"):
            an.construir_features_tx(tx, _referencia_manual())

    def test_extra_columns_such_as_labels_are_kept(self) -> None:
        tx = _cuenta_de_ejemplo().assign(es_anomalia_inyectada=[0] * 11 + [1])
        features = an.construir_features_tx(tx, _referencia_manual())
        self.assertEqual(features["es_anomalia_inyectada"].tolist(), [0, 1])

    def test_cutting_the_data_does_not_change_the_features_before_the_cut(self) -> None:
        tx = silver_transacciones()
        referencia = an.calcular_referencia(tx)
        completas = an.construir_features_tx(tx, referencia)
        corte = pd.Timestamp("2026-08-15")
        fechas = pd.to_datetime(tx["fecha_hora"]).dt.tz_localize(None)
        recortadas = an.construir_features_tx(tx.loc[fechas < corte], referencia)
        self.assertGreater(len(recortadas), 10000)
        self.assertEqual(an.diferencias_entre_features(completas, recortadas), 0)

    def test_the_leakage_check_detects_a_feature_that_uses_the_future(self) -> None:
        tx = silver_transacciones().head(30000)
        referencia = an.calcular_referencia(tx)
        completas = an.construir_features_tx(tx, referencia)
        trampa = completas.copy()
        trampa.loc[trampa.index[:5], "tx_ultimas_24h"] += 1
        self.assertEqual(an.diferencias_entre_features(trampa, completas), 5)
        with self.assertRaisesRegex(ValueError, "expected rows in common"):
            an.diferencias_entre_features(completas.head(2), completas.tail(2))


@unittest.skipUnless(LIBRERIAS, "requires pandas, numpy and scikit-learn")
class InyeccionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base = an.preparar_transacciones(silver_transacciones())
        cls.inyectada = an.inyectar_anomalias(cls.base, {"2026-08": 11, "2026-09": 23})

    def _mes(self, df: "pd.DataFrame", mes: str) -> "pd.DataFrame":
        return df.loc[df["fecha_hora"].dt.strftime("%Y-%m") == mes]

    def test_each_evaluation_month_gets_about_one_percent_split_across_three_types(self) -> None:
        for mes in ("2026-08", "2026-09"):
            etiquetadas = self._mes(self.inyectada, mes)
            etiquetadas = etiquetadas.loc[etiquetadas["es_anomalia_inyectada"] == 1]
            conteo = etiquetadas.groupby("tipo_anomalia").size()
            self.assertEqual(set(conteo.index), set(an.TIPOS_ANOMALIA))
            self.assertEqual(conteo["monto_extremo"], conteo["madrugada"])
            self.assertEqual(conteo["rafaga"], 3 * conteo["monto_extremo"])
            self.assertAlmostEqual(len(etiquetadas) / len(self._mes(self.base, mes)), an.TASA_INYECCION, delta=0.002)

    def test_months_outside_the_request_are_not_touched(self) -> None:
        for mes in ("2026-04", "2026-05", "2026-06", "2026-07"):
            sin_cambios = self._mes(self.inyectada, mes)
            self.assertEqual(int(sin_cambios["es_anomalia_inyectada"].sum()), 0)
            original = self._mes(self.base, mes).reset_index(drop=True)
            pd.testing.assert_frame_equal(
                sin_cambios.drop(columns=["es_anomalia_inyectada", "tipo_anomalia"]).reset_index(drop=True), original
            )

    def test_the_injection_is_reproducible_and_depends_on_the_seed(self) -> None:
        igual = an.inyectar_anomalias(self.base, {"2026-08": 11, "2026-09": 23})
        pd.testing.assert_frame_equal(igual, self.inyectada)
        otra = an.inyectar_anomalias(self.base, {"2026-08": 12})
        agosto = self._mes(self.inyectada, "2026-08").set_index("transaccion_id")["es_anomalia_inyectada"]
        distinto = self._mes(otra, "2026-08").set_index("transaccion_id")["es_anomalia_inyectada"]
        self.assertFalse(agosto.reindex(distinto.index).equals(distinto))

    def test_every_type_changes_what_it_says_it_changes(self) -> None:
        originales = self.base.set_index("transaccion_id")
        etiquetadas = self.inyectada.loc[self.inyectada["es_anomalia_inyectada"] == 1]

        extremos = etiquetadas.loc[etiquetadas["tipo_anomalia"] == "monto_extremo"].set_index("transaccion_id")
        factor = extremos["monto"] / originales.loc[extremos.index, "monto"]
        self.assertGreaterEqual(factor.min(), 2.99)
        self.assertLessEqual(factor.max(), 8.01)
        self.assertTrue((extremos["fecha_hora"] == originales.loc[extremos.index, "fecha_hora"]).all())

        madrugada = etiquetadas.loc[etiquetadas["tipo_anomalia"] == "madrugada"]
        self.assertTrue(madrugada["fecha_hora"].dt.hour.between(0, 5).all())
        self.assertFalse(self.base["fecha_hora"].dt.hour.between(0, 5).any())

        rafaga = etiquetadas.loc[etiquetadas["tipo_anomalia"] == "rafaga"]
        self.assertTrue(rafaga["transaccion_id"].str.startswith("TXR").all())
        self.assertTrue(self.inyectada["transaccion_id"].is_unique)
        self.assertEqual(len(self.inyectada) - len(self.base), len(rafaga))

    def test_injected_rows_have_enough_history_to_be_scored(self) -> None:
        referencia = an.calcular_referencia(self.base)
        features = an.construir_features_tx(self.inyectada, referencia)
        etiquetadas = self.inyectada.loc[self.inyectada["es_anomalia_inyectada"] == 1]
        puntuables = features.loc[features["es_anomalia_inyectada"] == 1]
        self.assertEqual(len(puntuables), len(etiquetadas))

    def test_invalid_requests_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "tasa: expected a number in"):
            an.inyectar_anomalias(self.base, {"2026-08": 1}, tasa=0.5)
        sin_historial = self.base.loc[self.base["fecha_hora"].dt.strftime("%Y-%m") == "2026-08"].groupby("cuenta_id").head(1)
        with self.assertRaisesRegex(ValueError, "expected at least"):
            an.inyectar_anomalias(sin_historial, {"2026-08": 1}, tasa=0.15)


@unittest.skipUnless(LIBRERIAS, "requires pandas, numpy and scikit-learn")
class ModeloTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        base = an.preparar_transacciones(silver_transacciones())
        meses = base["fecha_hora"].dt.strftime("%Y-%m")
        cls.referencia = an.calcular_referencia(base.loc[meses.isin(an.MESES_ENTRENAMIENTO)])
        inyectada = an.inyectar_anomalias(base, {an.MES_VALIDACION: an.SEMILLA_VALIDACION, an.MES_PRUEBA: an.SEMILLA_PRUEBA})
        features = an.construir_features_tx(inyectada, cls.referencia)
        cls.entrenamiento = features.loc[features["mes"].isin(an.MESES_ENTRENAMIENTO)]
        cls.validacion = features.loc[features["mes"] == an.MES_VALIDACION].reset_index(drop=True)
        cls.prueba = features.loc[features["mes"] == an.MES_PRUEBA].reset_index(drop=True)
        cls.muestra = an.muestrear_entrenamiento(cls.entrenamiento, maximo=8000)
        cls.lof = an.crear_detector("lof", 100).fit(cls.muestra[list(an.FEATURES_TX)])
        cls.iforest = an.crear_detector("iforest").fit(cls.muestra[list(an.FEATURES_TX)])

    def test_training_months_carry_no_injected_anomalies(self) -> None:
        self.assertEqual(int(self.entrenamiento["es_anomalia_inyectada"].sum()), 0)
        self.assertGreater(int(self.validacion["es_anomalia_inyectada"].sum()), 100)
        self.assertGreater(int(self.prueba["es_anomalia_inyectada"].sum()), 100)

    def test_unknown_detector_types_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "tipo: expected one of"):
            an.crear_detector("svm")

    def test_the_sample_is_reproducible_ordered_and_never_larger_than_the_data(self) -> None:
        igual = an.muestrear_entrenamiento(self.entrenamiento, maximo=8000)
        pd.testing.assert_frame_equal(igual, self.muestra)
        self.assertEqual(len(self.muestra), 8000)
        self.assertEqual(len(an.muestrear_entrenamiento(self.muestra.head(50), maximo=8000)), 50)
        with self.assertRaisesRegex(ValueError, "maximo: expected a positive integer"):
            an.muestrear_entrenamiento(self.entrenamiento, maximo=0)

    def test_the_threshold_flags_the_review_capacity_and_lives_inside_the_model(self) -> None:
        for tipo, modelo in (("lof", self.lof), ("iforest", self.iforest)):
            copia = an.crear_detector(tipo, 100).fit(self.muestra[list(an.FEATURES_TX)])
            umbral = an.fijar_umbral(copia, self.validacion, 0.01)
            self.assertEqual(copia.named_steps["detector"].offset_, umbral)
            marcadas = an.puntuar_anomalias(copia, self.validacion)["es_atipica"].mean()
            with self.subTest(tipo=tipo):
                self.assertAlmostEqual(float(marcadas), 0.01, delta=0.0015)
        copia = an.crear_detector("lof", 100).fit(self.muestra[list(an.FEATURES_TX)])
        an.fijar_umbral(copia, self.validacion, 0.05)
        self.assertGreater(an.puntuar_anomalias(copia, self.validacion)["es_atipica"].mean(), 0.04)
        with self.assertRaisesRegex(ValueError, "tasa: expected a number in"):
            an.fijar_umbral(copia, self.validacion, 0.0)

    def test_scores_are_higher_for_more_atypical_transactions_and_flags_follow_the_threshold(self) -> None:
        modelo = an.crear_detector("lof", 100).fit(self.muestra[list(an.FEATURES_TX)])
        an.fijar_umbral(modelo, self.validacion, 0.01)
        puntos = an.puntuar_anomalias(modelo, self.prueba)
        self.assertEqual(list(puntos.columns), ["transaccion_id", "score_anomalia", "es_atipica"])
        self.assertTrue(
            puntos.loc[puntos["es_atipica"] == 1, "score_anomalia"].min()
            >= puntos.loc[puntos["es_atipica"] == 0, "score_anomalia"].max()
        )
        self.assertEqual(set(puntos["es_atipica"]), {0, 1})
        self.assertTrue(np.array_equal(puntos["es_atipica"].to_numpy() == 1, modelo.predict(self.prueba[list(an.FEATURES_TX)]) == -1))
        metricas = an.evaluar_deteccion(self.prueba["es_anomalia_inyectada"], puntos["score_anomalia"], puntos["es_atipica"])
        self.assertGreater(metricas["auc"], 0.9)

    def test_lof_ranks_anomalies_far_better_than_isolation_forest_on_these_data(self) -> None:
        def ap(modelo) -> float:
            puntaje = -modelo.score_samples(self.validacion[list(an.FEATURES_TX)])
            return an.evaluar_deteccion(self.validacion["es_anomalia_inyectada"], puntaje, np.zeros(len(puntaje)))["average_precision"]

        self.assertGreater(ap(self.lof), 3 * ap(self.iforest))

    def test_detection_metrics_on_a_known_example(self) -> None:
        y = [1, 1, 0, 0, 0, 0, 0, 0, 0, 0]
        puntaje = [0.9, 0.2, 0.8, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1]
        marcadas = [1, 0, 1, 0, 0, 0, 0, 0, 0, 0]
        m = an.evaluar_deteccion(y, puntaje, marcadas)
        self.assertEqual((m["precision"], m["recall"], m["tasa_marcadas"], m["prevalencia"]), (0.5, 0.5, 0.2, 0.2))
        self.assertGreater(m["auc"], 0.5)

    def test_recall_by_type_reports_zero_for_the_types_that_were_missed(self) -> None:
        df = pd.DataFrame({"es_anomalia_inyectada": [1, 1, 1, 0], "tipo_anomalia": ["rafaga", "rafaga", "madrugada", ""]})
        tabla = an.recall_por_tipo(df, [1, 0, 0, 1]).set_index("tipo_anomalia")
        self.assertEqual(tabla.loc["rafaga", "recall"], 0.5)
        self.assertEqual(tabla.loc["madrugada", "recall"], 0.0)
        self.assertEqual(tabla.loc["monto_extremo", "inyectadas"], 0)

    def test_the_baseline_only_flags_amounts_above_the_training_maximum_of_the_type(self) -> None:
        df = pd.DataFrame({"transaccion_id": ["a", "b"], "tipo_transaccion": ["COMPRA", "COMPRA"], "monto": [100.0, 5000.01]})
        regla = an.regla_maximo_por_tipo(df, _referencia_manual())
        self.assertEqual(regla["es_atipica"].tolist(), [0, 1])
        self.assertLess(regla["score_anomalia"].iloc[0], regla["score_anomalia"].iloc[1])

    def test_candidate_selection_prefers_the_simplest_one_close_to_the_best(self) -> None:
        tabla = pd.DataFrame(
            {
                "nombre": ["iforest", "lof_20", "lof_100", "lof_200"],
                "average_precision_validacion": [0.11, 0.37, 0.55, 0.56],
                "complejidad": [0, 20, 100, 200],
            }
        )
        self.assertEqual(an.elegir_candidato(tabla), "lof_100")
        self.assertEqual(an.elegir_candidato(tabla, margen=0.0), "lof_200")
        self.assertEqual(an.elegir_candidato(tabla, margen=1.0), "iforest")
        with self.assertRaisesRegex(ValueError, "at least one row"):
            an.elegir_candidato(tabla.head(0))
        with self.assertRaisesRegex(ValueError, "candidatos: expected columns"):
            an.elegir_candidato(tabla.drop(columns=["complejidad"]))


@unittest.skipUnless(LIBRERIAS, "requires pandas, numpy and scikit-learn")
class SolicitudesTests(unittest.TestCase):
    def test_the_request_keeps_the_signature_order_and_native_types(self) -> None:
        df = an.construir_features_tx(_cuenta_de_ejemplo(), _referencia_manual())
        cuerpo = an.solicitud_endpoint(df)
        self.assertEqual((cuerpo["formatType"], cuerpo["orientation"]), ("dataframe", "values"))
        fila = cuerpo["inputs"][0]
        self.assertEqual(len(fila), len(an.FEATURES_TX))
        for columna, valor in zip(an.FEATURES_TX, fila):
            with self.subTest(columna=columna):
                if columna in an.FEATURES_ENTERAS_TX:
                    self.assertIs(type(valor), int)
                elif columna in an.FEATURES_CATEGORICAS_TX:
                    self.assertIs(type(valor), str)
                else:
                    self.assertIs(type(valor), float)

    def test_a_missing_value_never_reaches_the_endpoint(self) -> None:
        df = an.construir_features_tx(_cuenta_de_ejemplo(), _referencia_manual())
        df.loc[0, "z_monto_tipo"] = np.nan
        with self.assertRaisesRegex(ValueError, "expected no missing values"):
            an.solicitud_endpoint(df)

    def test_a_single_transaction_gets_the_same_features_as_the_batch(self) -> None:
        tx = an.preparar_transacciones(silver_transacciones())
        referencia = an.calcular_referencia(tx)
        por_lotes = an.construir_features_tx(tx, referencia).set_index("transaccion_id")
        cuenta = tx.groupby("cuenta_id").size().loc[lambda s: s >= 30].index[0]
        historial = tx.loc[tx["cuenta_id"] == cuenta].reset_index(drop=True)
        for posicion in (12, 20, 29):
            nueva = historial.iloc[posicion].to_dict()
            una = an.features_de_una_transaccion(historial.iloc[:posicion], nueva, referencia).iloc[0]
            esperado = por_lotes.loc[nueva["transaccion_id"]]
            for columna in an.FEATURES_TX:
                with self.subTest(posicion=posicion, columna=columna):
                    if columna in an.FEATURES_CATEGORICAS_TX:
                        self.assertEqual(una[columna], esperado[columna])
                    else:
                        self.assertAlmostEqual(float(una[columna]), float(esperado[columna]), places=9)

    def test_a_new_transaction_needs_a_history_that_ends_before_it(self) -> None:
        historial = _cuenta_de_ejemplo()
        nueva = {**historial.iloc[5].to_dict(), "transaccion_id": "NUEVA"}
        with self.assertRaisesRegex(ValueError, "expected only transactions before the new one"):
            an.features_de_una_transaccion(historial, nueva, _referencia_manual())
        nueva = {**historial.iloc[11].to_dict(), "transaccion_id": "NUEVA"}
        with self.assertRaisesRegex(ValueError, "expected at least 10 previous transactions"):
            an.features_de_una_transaccion(historial.iloc[:5], nueva, _referencia_manual())
        with self.assertRaisesRegex(ValueError, "nueva: expected columns"):
            an.features_de_una_transaccion(historial, {"cuenta_id": "CTA1"}, _referencia_manual())


class _Cliente:
    def __init__(self, get, post=None) -> None:
        self._get, self._post, self.llamadas = get, post, []

    def get(self, ruta):
        self.llamadas.append(("GET", ruta))
        return self._get

    def post(self, ruta, json):
        self.llamadas.append(("POST", ruta, json))
        return self._post


def _resp(codigo, cuerpo=None):
    return types.SimpleNamespace(status_code=codigo, json=lambda: cuerpo or {})


@unittest.skipUnless(LIBRERIAS, "requires pandas, numpy and scikit-learn")
class PuntuarEnLineaTests(unittest.TestCase):
    cuerpo = {"formatType": "dataframe", "orientation": "values", "inputs": [[1]]}

    @staticmethod
    def _versiones(**estados) -> "types.SimpleNamespace":
        return _resp(200, {"value": [{"versionName": nombre[1:], "status": estado} for nombre, estado in estados.items()]})

    def test_without_a_version_the_most_recent_active_one_is_scored_and_timed(self) -> None:
        cliente = _Cliente(self._versiones(v1="Active", v2="Deactivated", v3="Active"), _resp(200, {"predictions": [[1], [-1]]}))
        resultado = an.puntuar_en_linea(cliente, "ws", "mod", self.cuerpo)
        self.assertEqual((resultado["version"], resultado["predicciones"]), (3, [1, -1]))
        self.assertGreaterEqual(resultado["segundos"], 0)
        self.assertEqual(cliente.llamadas[1][1], "/v1/workspaces/ws/mlmodels/mod/endpoint/versions/3/score")
        self.assertEqual(cliente.llamadas[1][2], self.cuerpo)

    def test_a_requested_version_is_scored_only_if_it_is_active(self) -> None:
        activa = _Cliente(self._versiones(v1="Active", v2="Active"), _resp(200, {"predictions": [[1]]}))
        self.assertEqual(an.puntuar_en_linea(activa, "ws", "mod", self.cuerpo, version=1)["version"], 1)
        self.assertTrue(activa.llamadas[1][1].endswith("/versions/1/score"))
        for estado in ("Deactivated", "Activating", "Failed"):
            cliente = _Cliente(self._versiones(v1="Active", v2=estado))
            with self.subTest(estado=estado):
                resultado = an.puntuar_en_linea(cliente, "ws", "mod", self.cuerpo, version=2)
                self.assertEqual((resultado["estado"], resultado["version"], resultado["predicciones"]), (estado, 2, None))
                self.assertEqual([c[0] for c in cliente.llamadas], ["GET"])

    def test_with_no_active_version_nothing_is_called_or_activated(self) -> None:
        cliente = _Cliente(self._versiones(v1="Deactivated", v2="Activating"))
        resultado = an.puntuar_en_linea(cliente, "ws", "mod", self.cuerpo)
        self.assertEqual(resultado["estado"], "ninguna version activa (v1: Deactivated, v2: Activating)")
        self.assertEqual([c[0] for c in cliente.llamadas], ["GET"])
        vacio = an.puntuar_en_linea(_Cliente(self._versiones()), "ws", "mod", self.cuerpo)
        self.assertEqual(vacio["estado"], "ninguna version activa (sin versiones)")

    def test_a_missing_version_and_http_errors_are_reported_without_raising(self) -> None:
        sin_version = _Cliente(self._versiones(v1="Active"))
        self.assertEqual(an.puntuar_en_linea(sin_version, "ws", "mod", self.cuerpo, version=3)["estado"], "sin endpoint")
        self.assertIn("HTTP 403", an.puntuar_en_linea(_Cliente(_resp(403)), "ws", "mod", self.cuerpo)["estado"])
        falla = _Cliente(self._versiones(v3="Active"), _resp(500))
        self.assertIn("HTTP 500", an.puntuar_en_linea(falla, "ws", "mod", self.cuerpo)["estado"])

if __name__ == "__main__":
    unittest.main()
