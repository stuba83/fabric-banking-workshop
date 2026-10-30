"""Caso de ML del bonus: propension de alta actividad de una cuenta bancaria.

Pregunta: dado el comportamiento de una cuenta hasta el cierre de un mes, ¿tendra
al menos `UMBRAL_ALTA_ACTIVIDAD` transacciones validas el mes siguiente?

Los datos son sinteticos: las metricas sirven para practicar el ciclo de vida,
no para estimar el rendimiento de un modelo real. Las funciones de datos y de
modelo usan pandas y scikit-learn, que forman parte del runtime de Fabric. La
seccion final (ciclo MLOps) recibe `spark` y `mlflow` como argumentos en lugar de
importarlos, para poder probarla fuera de Fabric.
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd


PATRON_PREFIJO = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,19}\Z", re.ASCII)
UMBRAL_ALTA_ACTIVIDAD = 9
ETIQUETA = "alta_actividad_siguiente"
CLAVE = "cuenta_id"
CORTE = "corte"

CANALES = ("BANCA_MOVIL", "WEB", "ATM", "SUCURSAL")
# Todas las variables de comportamiento usan una ventana fija de dos meses (el mes de
# corte y el anterior). Las variables acumuladas o la antigüedad crecen con el
# calendario y producirian una deriva artificial en el monitoreo.
VENTANA_MESES = 2
FEATURES_NUMERICAS = (
    "tx_mes_corte",
    "tx_mes_previo",
    "tx_ventana",
    "monto_ventana",
    "monto_prom_ventana",
    "pct_credito",
    "pct_fin_semana",
    "pct_banca_movil",
    "pct_web",
    "pct_atm",
    "pct_sucursal",
    "n_tipos",
    "dias_desde_ultima",
    "saldo_inicial",
)
FEATURES_CATEGORICAS = ("producto_id", "segmento")
FEATURES = FEATURES_NUMERICAS + FEATURES_CATEGORICAS
# Atributos que NO entran al modelo; se usan solo para auditar diferencias entre grupos.
VARIABLES_PARA_AUDITORIA = ("grupo_edad", "provincia")

CORTES_ENTRENAMIENTO = ("2026-05", "2026-06")
CORTE_VALIDACION = "2026-07"
CORTE_PRUEBA = "2026-08"
CORTE_PUNTUACION = "2026-09"

UMBRAL_PSI_MODERADO = 0.10
UMBRAL_PSI_ALTO = 0.25

_COLUMNAS_TRANSACCIONES = (
    "cuenta_id",
    "fecha_hora",
    "tipo_transaccion",
    "direccion",
    "canal",
    "monto",
)
_COLUMNAS_CUENTAS = ("cuenta_id", "cliente_id", "producto_id", "fecha_apertura", "saldo_inicial")
_COLUMNAS_CLIENTES = ("cliente_id", "segmento")


def _exigir_columnas(df: pd.DataFrame, columnas: Sequence[str], nombre: str) -> None:
    faltantes = [columna for columna in columnas if columna not in df.columns]
    if faltantes:
        raise ValueError(
            f"{nombre}: expected columns {list(columnas)!r}; observed missing {faltantes!r}"
        )


def _a_numerico(serie: pd.Series) -> pd.Series:
    # Spark entrega decimal(18,2) como objetos Decimal; se convierte a float.
    return pd.to_numeric(serie.astype(float), errors="raise")


def _fin_de_mes(periodo: pd.Period) -> pd.Timestamp:
    return periodo.end_time.normalize()


def construir_features(
    transacciones: pd.DataFrame,
    cuentas: pd.DataFrame,
    clientes: pd.DataFrame,
    corte: str,
    ultimo_dia_datos: str | None = None,
    umbral: int = UMBRAL_ALTA_ACTIVIDAD,
) -> pd.DataFrame:
    """Una fila por cuenta con el comportamiento de los dos ultimos meses hasta `corte` (AAAA-MM).

    Solo se usan movimientos con fecha dentro del mes de corte o el anterior. La
    etiqueta mira el mes siguiente y queda vacia (NaN) cuando ese mes no esta
    completo en los datos: son las filas que se puntuan, no las que se entrenan.
    `ultimo_dia_datos` (AAAA-MM-DD) indica hasta donde llegan los datos; si se omite,
    se toma la fecha del ultimo movimiento.
    """
    _exigir_columnas(transacciones, _COLUMNAS_TRANSACCIONES, "transacciones")
    _exigir_columnas(cuentas, _COLUMNAS_CUENTAS, "cuentas")
    _exigir_columnas(clientes, _COLUMNAS_CLIENTES, "clientes")

    corte_p = pd.Period(corte, freq="M")
    inicio_ventana = corte_p - (VENTANA_MESES - 1)
    tx = transacciones.loc[:, list(_COLUMNAS_TRANSACCIONES)].copy()
    tx["fecha_hora"] = pd.to_datetime(tx["fecha_hora"])
    if tx["fecha_hora"].dt.tz is not None:
        tx["fecha_hora"] = tx["fecha_hora"].dt.tz_localize(None)
    tx["monto"] = _a_numerico(tx["monto"])
    tx["periodo"] = tx["fecha_hora"].dt.to_period("M")

    ventana = tx.loc[(tx["periodo"] >= inicio_ventana) & (tx["periodo"] <= corte_p)].copy()
    ventana["es_credito"] = (ventana["direccion"] == "CREDITO").astype(float)
    ventana["fin_semana"] = (ventana["fecha_hora"].dt.day_of_week >= 5).astype(float)
    for canal in CANALES:
        ventana["pct_" + canal.lower()] = (ventana["canal"] == canal).astype(float)

    por_cuenta = ventana.groupby(CLAVE)
    features = pd.DataFrame(index=pd.Index(cuentas[CLAVE].unique(), name=CLAVE))
    features["tx_mes_corte"] = ventana.loc[ventana["periodo"] == corte_p].groupby(CLAVE).size()
    features["tx_mes_previo"] = ventana.loc[ventana["periodo"] == corte_p - 1].groupby(CLAVE).size()
    features["tx_ventana"] = por_cuenta.size()
    features["monto_ventana"] = por_cuenta["monto"].sum()
    features["monto_prom_ventana"] = por_cuenta["monto"].mean()
    features["pct_credito"] = por_cuenta["es_credito"].mean()
    features["pct_fin_semana"] = por_cuenta["fin_semana"].mean()
    for canal in CANALES:
        columna = "pct_" + canal.lower()
        features[columna] = por_cuenta[columna].mean()
    features["n_tipos"] = por_cuenta["tipo_transaccion"].nunique()

    fin_corte = _fin_de_mes(corte_p)
    dias_ventana = (fin_corte - inicio_ventana.start_time.normalize()).days
    features["dias_desde_ultima"] = (fin_corte - por_cuenta["fecha_hora"].max()).dt.days

    cero_si_vacio = [c for c in features.columns if c != "dias_desde_ultima"]
    features[cero_si_vacio] = features[cero_si_vacio].fillna(0.0)
    features["dias_desde_ultima"] = features["dias_desde_ultima"].fillna(dias_ventana)
    for columna in (
        "tx_mes_corte", "tx_mes_previo", "tx_ventana", "n_tipos", "dias_desde_ultima"
    ):
        features[columna] = features[columna].astype("int64")

    base = cuentas.loc[:, list(_COLUMNAS_CUENTAS)].drop_duplicates(CLAVE).merge(
        clientes.loc[:, list(_COLUMNAS_CLIENTES)], on="cliente_id", how="left", validate="m:1"
    )
    base["saldo_inicial"] = _a_numerico(base["saldo_inicial"])
    base = base.drop(columns=["cliente_id", "fecha_apertura"])

    resultado = features.reset_index().merge(base, on=CLAVE, how="left", validate="1:1")
    resultado.insert(1, CORTE, str(corte_p))

    siguiente = corte_p + 1
    ultimo_dia = (
        pd.Timestamp(ultimo_dia_datos).normalize()
        if ultimo_dia_datos is not None
        else tx["fecha_hora"].max().normalize()
    )
    if _fin_de_mes(siguiente) <= ultimo_dia:
        proximo = tx.loc[tx["periodo"] == siguiente].groupby(CLAVE).size()
        conteo = resultado[CLAVE].map(proximo).fillna(0)
        resultado[ETIQUETA] = (conteo >= umbral).astype("float64")
    else:
        resultado[ETIQUETA] = np.nan

    columnas = [CLAVE, CORTE, *FEATURES, ETIQUETA]
    return resultado.loc[:, columnas].sort_values(CLAVE).reset_index(drop=True)


def construir_dataset(
    transacciones: pd.DataFrame,
    cuentas: pd.DataFrame,
    clientes: pd.DataFrame,
    cortes: Sequence[str],
    ultimo_dia_datos: str | None = None,
    umbral: int = UMBRAL_ALTA_ACTIVIDAD,
) -> pd.DataFrame:
    partes = [
        construir_features(transacciones, cuentas, clientes, corte, ultimo_dia_datos, umbral)
        for corte in cortes
    ]
    return pd.concat(partes, ignore_index=True)


def validar_features(df: pd.DataFrame, cuentas_esperadas: int | None = None) -> list[str]:
    """Devuelve la lista de problemas; una lista vacia significa que pasa."""
    problemas: list[str] = []
    esperadas = [CLAVE, CORTE, *FEATURES, ETIQUETA]
    if list(df.columns) != esperadas:
        return [f"columns: expected {esperadas!r}; observed {list(df.columns)!r}"]
    if df.duplicated([CLAVE, CORTE]).any():
        problemas.append("expected one row per (cuenta_id, corte); observed duplicates")
    numericas = list(FEATURES_NUMERICAS)
    nulos = df[numericas + list(FEATURES_CATEGORICAS)].isna().sum()
    for columna, cantidad in nulos[nulos > 0].items():
        problemas.append(f"{columna}: expected no nulls; observed {int(cantidad)}")
    for columna in ("tx_mes_corte", "tx_mes_previo", "tx_ventana", "monto_ventana", "saldo_inicial"):
        if (df[columna] < 0).any():
            problemas.append(f"{columna}: expected non-negative values; observed negatives")
    for columna in ("pct_credito", "pct_fin_semana", *(f"pct_{c.lower()}" for c in CANALES)):
        if ((df[columna] < 0) | (df[columna] > 1)).any():
            problemas.append(f"{columna}: expected values between 0 and 1; observed outside")
    if not (df["tx_mes_corte"] + df["tx_mes_previo"] == df["tx_ventana"]).all():
        problemas.append("tx_mes_corte + tx_mes_previo = tx_ventana: expected to hold; observed violations")
    invalidas = df[ETIQUETA].dropna()
    if not invalidas.isin([0.0, 1.0]).all():
        problemas.append(f"{ETIQUETA}: expected 0, 1 or empty; observed other values")
    if cuentas_esperadas is not None:
        por_corte = df.groupby(CORTE).size()
        for corte, filas in por_corte.items():
            if filas != cuentas_esperadas:
                problemas.append(
                    f"corte {corte}: expected {cuentas_esperadas} rows; observed {int(filas)}"
                )
    return problemas


def dividir_temporal(
    df: pd.DataFrame,
    entrenamiento: Sequence[str] = CORTES_ENTRENAMIENTO,
    validacion: str = CORTE_VALIDACION,
    prueba: str = CORTE_PRUEBA,
    puntuacion: str = CORTE_PUNTUACION,
) -> dict[str, pd.DataFrame]:
    """Separa por tiempo, nunca al azar.

    Cada corte etiqueta el mes siguiente. Las etiquetas de entrenamiento deben
    ser anteriores a las de validacion, y estas a las de prueba, para que el
    modelo nunca vea el futuro que se usa para juzgarlo.
    """
    orden = [*sorted(entrenamiento), validacion, prueba, puntuacion]
    if orden != sorted(orden) or len(set(orden)) != len(orden):
        raise ValueError(
            f"cortes: expected strictly increasing training < validation < test < scoring; observed {orden!r}"
        )
    partes = {
        "entrenamiento": df[df[CORTE].isin(entrenamiento)],
        "validacion": df[df[CORTE] == validacion],
        "prueba": df[df[CORTE] == prueba],
        "puntuacion": df[df[CORTE] == puntuacion],
    }
    for nombre, parte in partes.items():
        if parte.empty:
            raise ValueError(f"{nombre}: expected at least one row; observed none")
        con_etiqueta = parte[ETIQUETA].notna().all()
        sin_etiqueta = parte[ETIQUETA].isna().all()
        if nombre == "puntuacion" and not sin_etiqueta:
            raise ValueError("puntuacion: expected an empty label; observed labelled rows")
        if nombre != "puntuacion" and not con_etiqueta:
            raise ValueError(f"{nombre}: expected labelled rows; observed missing labels")
    return {nombre: parte.reset_index(drop=True) for nombre, parte in partes.items()}


def crear_modelo(tipo: str, semilla: int = 42) -> Any:
    """Pipeline de scikit-learn: preparacion + modelo. `tipo`: logreg, rf o hgb."""
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    estimadores = {
        "logreg": lambda: LogisticRegression(max_iter=1000),
        "rf": lambda: RandomForestClassifier(
            n_estimators=200, min_samples_leaf=5, random_state=semilla, n_jobs=2
        ),
        "hgb": lambda: HistGradientBoostingClassifier(random_state=semilla),
    }
    if tipo not in estimadores:
        raise ValueError(f"tipo: expected one of {sorted(estimadores)!r}; observed {tipo!r}")
    preparacion = ColumnTransformer(
        [
            ("numericas", StandardScaler(), list(FEATURES_NUMERICAS)),
            ("categoricas", OneHotEncoder(handle_unknown="ignore"), list(FEATURES_CATEGORICAS)),
        ]
    )
    return Pipeline([("preparacion", preparacion), ("modelo", estimadores[tipo]())])


def evaluar_clasificador(y_real: Any, probabilidad: Any, umbral: float = 0.5) -> dict[str, float]:
    from sklearn.metrics import (
        average_precision_score,
        brier_score_loss,
        f1_score,
        precision_score,
        recall_score,
        roc_auc_score,
    )

    y = np.asarray(y_real, dtype=int)
    p = np.asarray(probabilidad, dtype=float)
    pred = (p >= umbral).astype(int)
    return {
        "auc": float(roc_auc_score(y, p)),
        "average_precision": float(average_precision_score(y, p)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "brier": float(brier_score_loss(y, p)),
        "prevalencia": float(y.mean()),
    }


def baseline_regla(df: pd.DataFrame, umbral: int = UMBRAL_ALTA_ACTIVIDAD) -> np.ndarray:
    """Regla sin aprendizaje: la actividad del mes de corte predice la del siguiente."""
    return (df["tx_mes_corte"].to_numpy() / float(umbral)).clip(0, 1)


def simular_deriva_actividad(df: pd.DataFrame, factor: float = 1.6) -> pd.DataFrame:
    """Copia de `df` con la actividad multiplicada por `factor` (por ejemplo, una campana).

    Sirve para comprobar que el monitoreo detecta un cambio de poblacion; no
    modifica las etiquetas.
    """
    if factor <= 0:
        raise ValueError(f"factor: expected a positive number; observed {factor!r}")
    simulado = df.copy()
    for columna in ("tx_mes_corte", "tx_mes_previo"):
        simulado[columna] = (simulado[columna] * factor).round().astype("int64")
    simulado["tx_ventana"] = simulado["tx_mes_corte"] + simulado["tx_mes_previo"]
    simulado["monto_ventana"] = simulado["monto_ventana"] * factor
    return simulado


def importancia_permutacion(
    modelo: Any, df: pd.DataFrame, repeticiones: int = 5, semilla: int = 42
) -> pd.DataFrame:
    from sklearn.inspection import permutation_importance

    resultado = permutation_importance(
        modelo,
        df[list(FEATURES)],
        df[ETIQUETA].astype(int),
        scoring="roc_auc",
        n_repeats=repeticiones,
        random_state=semilla,
    )
    tabla = pd.DataFrame(
        {
            "variable": list(FEATURES),
            "caida_auc": resultado.importances_mean,
            "desviacion": resultado.importances_std,
        }
    )
    return tabla.sort_values("caida_auc", ascending=False).reset_index(drop=True)


def metricas_por_grupo(
    y_real: Any, probabilidad: Any, grupo: Any, umbral: float = 0.5
) -> pd.DataFrame:
    """Auditoria por grupo (por ejemplo, grupo de edad), aunque no sea una variable del modelo."""
    from sklearn.metrics import roc_auc_score

    tabla = pd.DataFrame(
        {
            "y": np.asarray(y_real, dtype=int),
            "p": np.asarray(probabilidad, dtype=float),
            "grupo": np.asarray(grupo),
        }
    )
    filas = []
    for nombre, parte in tabla.groupby("grupo"):
        auc = float("nan")
        if parte["y"].nunique() == 2:
            auc = float(roc_auc_score(parte["y"], parte["p"]))
        filas.append(
            {
                "grupo": nombre,
                "filas": int(len(parte)),
                "prevalencia": float(parte["y"].mean()),
                "tasa_positivos_predichos": float((parte["p"] >= umbral).mean()),
                "auc": auc,
            }
        )
    return pd.DataFrame(filas)


def _proporciones(indices: np.ndarray, cantidad: int, epsilon: float) -> np.ndarray:
    conteos = np.bincount(indices, minlength=cantidad).astype(float)
    return np.clip(conteos / max(len(indices), 1), epsilon, None)


def psi_numerico(
    referencia: Any, actual: Any, particiones: int = 10, epsilon: float = 1e-4
) -> float:
    """Indice de estabilidad de la poblacion con cortes por cuantiles de la referencia."""
    ref = np.asarray(referencia, dtype=float)
    act = np.asarray(actual, dtype=float)
    if ref.size == 0 or act.size == 0:
        raise ValueError("psi_numerico: expected non-empty samples; observed an empty one")
    interiores = np.unique(np.quantile(ref, np.linspace(0, 1, particiones + 1)[1:-1]))
    cantidad = len(interiores) + 1
    # side="left": un valor igual a un corte queda en el intervalo de la izquierda; asi una
    # referencia constante tiene su propio intervalo y un cambio se detecta.
    p_ref = _proporciones(np.searchsorted(interiores, ref, side="left"), cantidad, epsilon)
    p_act = _proporciones(np.searchsorted(interiores, act, side="left"), cantidad, epsilon)
    return float(np.sum((p_act - p_ref) * np.log(p_act / p_ref)))


def psi_categorico(referencia: Any, actual: Any, epsilon: float = 1e-4) -> float:
    ref = pd.Series(referencia).astype(str)
    act = pd.Series(actual).astype(str)
    if ref.empty or act.empty:
        raise ValueError("psi_categorico: expected non-empty samples; observed an empty one")
    categorias = sorted(set(ref) | set(act))
    p_ref = np.clip(ref.value_counts(normalize=True).reindex(categorias).fillna(0).to_numpy(), epsilon, None)
    p_act = np.clip(act.value_counts(normalize=True).reindex(categorias).fillna(0).to_numpy(), epsilon, None)
    return float(np.sum((p_act - p_ref) * np.log(p_act / p_ref)))


def clasificar_psi(valor: float) -> str:
    if valor >= UMBRAL_PSI_ALTO:
        return "alta"
    if valor >= UMBRAL_PSI_MODERADO:
        return "moderada"
    return "estable"


def reporte_deriva(referencia: pd.DataFrame, actual: pd.DataFrame) -> pd.DataFrame:
    filas = []
    for columna in FEATURES_NUMERICAS:
        valor = psi_numerico(referencia[columna], actual[columna])
        filas.append({"variable": columna, "tipo": "numerica", "psi": valor, "deriva": clasificar_psi(valor)})
    for columna in FEATURES_CATEGORICAS:
        valor = psi_categorico(referencia[columna], actual[columna])
        filas.append({"variable": columna, "tipo": "categorica", "psi": valor, "deriva": clasificar_psi(valor)})
    return pd.DataFrame(filas).sort_values("psi", ascending=False).reset_index(drop=True)


def decidir_promocion(
    retador: Mapping[str, float],
    campeon: Mapping[str, float] | None = None,
    metrica: str = "auc",
    margen_minimo: float = 0.005,
    piso: float = 0.70,
) -> dict[str, Any]:
    """Regla explicita de promocion: piso de calidad y mejora minima sobre el campeon."""
    valor = float(retador[metrica])
    if not math.isfinite(valor):
        return {"decision": "rechazar", "motivo": f"{metrica} is not finite", "mejora": None}
    if valor < piso:
        return {
            "decision": "rechazar",
            "motivo": f"{metrica} {valor:.4f} is below the floor {piso:.4f}",
            "mejora": None,
        }
    if campeon is None:
        return {"decision": "promover", "motivo": "there is no champion yet", "mejora": None}
    mejora = valor - float(campeon[metrica])
    if mejora >= margen_minimo:
        return {
            "decision": "promover",
            "motivo": f"{metrica} improves by {mejora:.4f} (minimum {margen_minimo:.4f})",
            "mejora": mejora,
        }
    return {
        "decision": "mantener",
        "motivo": f"{metrica} improves by {mejora:.4f}, below the minimum {margen_minimo:.4f}",
        "mejora": mejora,
    }


def evaluar_alertas(
    deriva: pd.DataFrame,
    auc_actual: float | None = None,
    auc_referencia: float | None = None,
    caida_auc_maxima: float = 0.05,
    variables_alta_maxima: int = 2,
) -> dict[str, Any]:
    """Resume la salud del modelo. La caida de AUC solo se conoce cuando llegan las etiquetas."""
    alertas: list[str] = []
    altas = deriva.loc[deriva["deriva"] == "alta", "variable"].tolist()
    if len(altas) > variables_alta_maxima:
        alertas.append(f"{len(altas)} variables con deriva alta: {altas}")
    if auc_actual is not None and auc_referencia is not None:
        caida = auc_referencia - auc_actual
        if caida > caida_auc_maxima:
            alertas.append(f"auc fell {caida:.4f} (maximum {caida_auc_maxima:.4f})")
    if any(a.startswith("auc fell") for a in alertas):
        recomendacion = "reentrenar"
    elif alertas:
        recomendacion = "revisar"
    else:
        recomendacion = "sin_accion"
    return {"alertas": alertas, "recomendacion": recomendacion}


def puntuar(modelo: Any, df: pd.DataFrame, umbral: float = 0.5) -> pd.DataFrame:
    probabilidad = modelo.predict_proba(df[list(FEATURES)])[:, 1]
    return pd.DataFrame(
        {
            CLAVE: df[CLAVE].to_numpy(),
            CORTE: df[CORTE].to_numpy(),
            "probabilidad_alta_actividad": probabilidad.astype(float),
            "prediccion": (probabilidad >= umbral).astype("int64"),
        }
    )


def a_filas(df: pd.DataFrame) -> list[tuple[Any, ...]]:
    """Filas con tipos nativos de Python y None en lugar de NaN, para crear un DataFrame de Spark."""
    filas = []
    for fila in df.itertuples(index=False, name=None):
        nativa = []
        for valor in fila:
            if isinstance(valor, float) and math.isnan(valor):
                nativa.append(None)
            elif isinstance(valor, np.generic):
                nativa.append(valor.item())
            else:
                nativa.append(valor)
        filas.append(tuple(nativa))
    return filas


# ---------------------------------------------------------------------------
# Ciclo MLOps: validar, entrenar un retador, decidir, puntuar y monitorear.
# Recibe `spark` y `mlflow` como argumentos; el modulo no los importa.
# ---------------------------------------------------------------------------

COLUMNAS_FEATURES = (
    (CLAVE, "string"),
    (CORTE, "string"),
    ("tx_mes_corte", "bigint"),
    ("tx_mes_previo", "bigint"),
    ("tx_ventana", "bigint"),
    ("monto_ventana", "double"),
    ("monto_prom_ventana", "double"),
    ("pct_credito", "double"),
    ("pct_fin_semana", "double"),
    ("pct_banca_movil", "double"),
    ("pct_web", "double"),
    ("pct_atm", "double"),
    ("pct_sucursal", "double"),
    ("n_tipos", "bigint"),
    ("dias_desde_ultima", "bigint"),
    ("saldo_inicial", "double"),
    ("producto_id", "string"),
    ("segmento", "string"),
    (ETIQUETA, "double"),
)
COLUMNAS_PUNTUACION = (
    (CLAVE, "string"),
    (CORTE, "string"),
    ("probabilidad_alta_actividad", "double"),
    ("prediccion", "bigint"),
    ("version_modelo", "bigint"),
    ("fecha_utc", "string"),
)
COLUMNAS_REGISTRO = (
    ("secuencia", "bigint"),
    ("fecha_utc", "string"),
    ("evento", "string"),
    ("version", "bigint"),
    ("tipo_modelo", "string"),
    ("auc_validacion", "double"),
    ("auc_prueba", "double"),
    ("corte_prueba", "string"),
    ("run_id", "string"),
    ("motivo", "string"),
)
COLUMNAS_DERIVA = (
    ("corte", "string"),
    ("variable", "string"),
    ("tipo", "string"),
    ("psi", "double"),
    ("deriva", "string"),
    ("simulada", "bigint"),
    ("fecha_utc", "string"),
)
COLUMNAS_DESEMPENO = (
    ("corte_prediccion", "string"),
    ("mes_evaluado", "string"),
    ("version_modelo", "bigint"),
    ("filas", "bigint"),
    ("auc", "double"),
    ("average_precision", "double"),
    ("prevalencia_real", "double"),
    ("fecha_utc", "string"),
)


def nombres_ml(prefijo: str) -> dict[str, str]:
    p = prefijo.lower()
    return {
        "features": f"{p}_gold_ml_features_cuentas",
        "puntuacion": f"{p}_gold_ml_puntuacion_actividad",
        "registro": f"{p}_ml_registro_modelos",
        "deriva": f"{p}_ml_monitoreo_deriva",
        "desempeno": f"{p}_ml_monitoreo_desempeno",
        "experimento": f"{p}_exp_actividad",
        "modelo": f"{p}_modelo_actividad",
    }


def validar_parametros_ml(
    contexto: Mapping[str, Any],
    p_lakehouse_esperado: str,
    p_prefijo: str,
    p_confirmar_reemplazo: str,
    exigir_confirmacion: bool = True,
) -> str:
    """Mismas protecciones que las sesiones 2 y 3: confirmacion explicita y Lakehouse correcto.

    Con `exigir_confirmacion=False` solo se validan el prefijo y el Lakehouse; sirve para
    explorar sin escribir. Toda escritura vuelve a llamarla con la confirmacion exigida.
    """
    if exigir_confirmacion and p_confirmar_reemplazo != "SI":
        raise ValueError(
            "p_confirmar_reemplazo must be exactly 'SI' to replace the prefixed ML tables"
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
    for clave in ("defaultLakehouseId", "defaultLakehouseWorkspaceId", "currentWorkspaceId"):
        valor = contexto.get(clave)
        if not isinstance(valor, str) or not valor.strip():
            raise ValueError(f"notebook runtime context is missing {clave}")
    nombre = contexto.get("defaultLakehouseName")
    if not isinstance(nombre, str) or not nombre.strip():
        raise ValueError("notebook runtime context is missing defaultLakehouseName")
    if p_lakehouse_esperado and p_lakehouse_esperado != nombre:
        raise ValueError("p_lakehouse_esperado does not match the notebook default Lakehouse")
    if contexto["currentWorkspaceId"] != contexto["defaultLakehouseWorkspaceId"]:
        raise ValueError(
            "the default Lakehouse and current notebook must be in the same workspace"
        )
    return nombre


def _fecha_utc(ahora: datetime | None) -> str:
    momento = ahora if ahora is not None else datetime.now(timezone.utc)
    return momento.strftime("%Y-%m-%dT%H:%M:%SZ")


def leer_tabla(spark: Any, nombre: str, opcional: bool = False) -> pd.DataFrame | None:
    if not spark.catalog.tableExists(nombre):
        if opcional:
            return None
        raise ValueError(f"{nombre}: expected an existing table; observed missing")
    return spark.table(nombre).toPandas()


CONTEOS_SILVER = {"transacciones": 72000, "cuentas": 1800, "clientes": 1200}


def leer_silver(spark: Any, prefijo: str) -> dict[str, pd.DataFrame]:
    """Lee las tablas plata de la Sesion 3 y falla antes de cargar si no tienen el conteo esperado."""
    tablas: dict[str, pd.DataFrame] = {}
    for base, esperado in CONTEOS_SILVER.items():
        nombre = f"{prefijo.lower()}_silver_{base}"
        if not spark.catalog.tableExists(nombre):
            raise ValueError(f"{nombre}: expected an existing table; observed missing")
        observado = int(spark.table(nombre).count())
        if observado != esperado:
            raise ValueError(f"{nombre}: expected row count {esperado}; observed {observado}")
        tablas[base] = spark.table(nombre).toPandas()
    # Spark entrega decimal como objetos Decimal y el timestamp puede traer zona horaria.
    transacciones = tablas["transacciones"]
    fechas = pd.to_datetime(transacciones["fecha_hora"])
    if fechas.dt.tz is not None:
        fechas = fechas.dt.tz_localize(None)
    transacciones["fecha_hora"] = fechas
    transacciones["monto"] = _a_numerico(transacciones["monto"])
    tablas["cuentas"]["saldo_inicial"] = _a_numerico(tablas["cuentas"]["saldo_inicial"])
    return tablas


def escribir_tabla(
    spark: Any, nombre: str, df: pd.DataFrame, columnas: Sequence[tuple[str, str]]
) -> int:
    """Reemplaza la tabla Delta con tipos explicitos y comprueba el conteo escrito."""
    from pyspark.sql.types import DoubleType, LongType, StringType, StructField, StructType

    tipos = {"string": StringType(), "bigint": LongType(), "double": DoubleType()}
    nombres = [columna for columna, _ in columnas]
    faltantes = [columna for columna in nombres if columna not in df.columns]
    if faltantes:
        raise ValueError(f"{nombre}: expected columns {nombres!r}; observed missing {faltantes!r}")
    ordenado = df.loc[:, nombres].copy()
    for columna, tipo in columnas:
        if tipo == "double":
            ordenado[columna] = pd.to_numeric(ordenado[columna]).astype("float64")
        elif tipo == "bigint":
            serie = pd.to_numeric(ordenado[columna])
            if serie.isna().any():
                raise ValueError(f"{nombre}: column {columna}: expected no nulls in a bigint column")
            ordenado[columna] = serie.astype("int64")
    filas = a_filas(ordenado)
    esquema = StructType([StructField(c, tipos[t], True) for c, t in columnas])
    spark.createDataFrame(filas, schema=esquema).write.mode("overwrite").saveAsTable(nombre)
    observado = int(spark.table(nombre).count())
    if observado != len(filas):
        raise ValueError(f"{nombre}: expected table count {len(filas)}; observed {observado}")
    return observado


def reemplazar_corte(
    spark: Any,
    nombre: str,
    nuevo: pd.DataFrame,
    columnas: Sequence[tuple[str, str]],
    columna_corte: str,
    corte: str,
) -> int:
    """Idempotente: reemplaza solo las filas del corte y conserva las demas."""
    existente = leer_tabla(spark, nombre, opcional=True)
    if existente is not None and not existente.empty:
        existente = existente.loc[existente[columna_corte] != corte]
        nuevo = pd.concat([existente, nuevo], ignore_index=True)
    return escribir_tabla(spark, nombre, nuevo, columnas)


def cortes_para(corte_puntuacion: str, disponibles: Sequence[str]) -> dict[str, Any]:
    """Cortes de una ejecucion mensual: puntuar el corte, probar en el anterior, validar en el previo."""
    p = pd.Period(corte_puntuacion, freq="M")
    entrenamiento = tuple(sorted(c for c in disponibles if pd.Period(c, freq="M") < p - 2))
    if not entrenamiento:
        raise ValueError(
            f"cortes: expected at least one training cutoff before {p - 2}; observed none"
        )
    return {
        "entrenamiento": entrenamiento,
        "validacion": str(p - 2),
        "prueba": str(p - 1),
        "puntuacion": str(p),
    }


def campeon_actual(registro: pd.DataFrame | None) -> dict[str, Any] | None:
    """El campeon es el ultimo evento del registro (promocion o reversion)."""
    if registro is None or registro.empty:
        return None
    ultimo = registro.sort_values("secuencia").iloc[-1]
    return {
        "version": int(ultimo["version"]),
        "tipo_modelo": str(ultimo["tipo_modelo"]),
        "auc_validacion": float(ultimo["auc_validacion"]),
        "auc_prueba": float(ultimo["auc_prueba"]),
        "corte_prueba": str(ultimo["corte_prueba"]),
        "run_id": str(ultimo["run_id"]),
    }


def _nuevo_evento(
    registro: pd.DataFrame | None,
    evento: str,
    version: int,
    tipo_modelo: str,
    auc_validacion: float,
    auc_prueba: float,
    corte_prueba: str,
    run_id: str,
    motivo: str,
    ahora: datetime | None,
) -> pd.DataFrame:
    secuencia = 1 if registro is None or registro.empty else int(registro["secuencia"].max()) + 1
    fila = pd.DataFrame(
        [
            {
                "secuencia": secuencia,
                "fecha_utc": _fecha_utc(ahora),
                "evento": evento,
                "version": int(version),
                "tipo_modelo": tipo_modelo,
                "auc_validacion": float(auc_validacion),
                "auc_prueba": float(auc_prueba),
                "corte_prueba": corte_prueba,
                "run_id": run_id,
                "motivo": motivo,
            }
        ]
    )
    if registro is None or registro.empty:
        return fila
    return pd.concat([registro, fila], ignore_index=True)


def revertir_campeon(
    spark: Any, p_prefijo: str, version: int, motivo: str, ahora: datetime | None = None
) -> dict[str, Any]:
    """Reversion auditable: agrega un evento que vuelve a poner una version anterior como campeon."""
    if not motivo.strip():
        raise ValueError("motivo: expected a non-empty reason; observed an empty one")
    tabla = nombres_ml(p_prefijo)["registro"]
    registro = leer_tabla(spark, tabla)
    previos = registro.loc[registro["version"] == int(version)]
    if previos.empty:
        raise ValueError(
            f"version: expected one of {sorted(registro['version'].unique().tolist())!r}; "
            f"observed {version!r}"
        )
    base = previos.sort_values("secuencia").iloc[-1]
    actualizado = _nuevo_evento(
        registro, "reversion", int(version), str(base["tipo_modelo"]),
        float(base["auc_validacion"]), float(base["auc_prueba"]), str(base["corte_prueba"]),
        str(base["run_id"]), motivo, ahora,
    )
    escribir_tabla(spark, tabla, actualizado, COLUMNAS_REGISTRO)
    return campeon_actual(actualizado)  # type: ignore[return-value]


def _evaluar_en(modelo: Any, df: pd.DataFrame) -> dict[str, float]:
    probabilidad = modelo.predict_proba(df[list(FEATURES)])[:, 1]
    return evaluar_clasificador(df[ETIQUETA], probabilidad)


def ejecutar_ciclo(
    spark: Any,
    mlflow: Any,
    contexto: Mapping[str, Any],
    p_lakehouse_esperado: str,
    p_prefijo: str,
    p_confirmar_reemplazo: str,
    p_corte_puntuacion: str = CORTE_PUNTUACION,
    p_tipo_modelo: str = "logreg",
    p_factor_deriva: float = 0.0,
    ahora: datetime | None = None,
) -> dict[str, Any]:
    """Un ciclo mensual completo; se puede reejecutar sin duplicar filas ni versiones.

    1. Valida parametros y la tabla de features (compuerta de calidad de datos).
    2. Entrena un retador y lo compara con el campeon sobre el mismo corte de prueba.
    3. Promueve solo si cumple la regla; registra la version solo cuando se promueve.
    4. Puntua el corte con el campeon, mide la deriva y, si ya hay etiquetas del mes
       anterior, el desempeno real del modelo que puntuo ese mes.
    """
    lakehouse = validar_parametros_ml(
        contexto, p_lakehouse_esperado, p_prefijo, p_confirmar_reemplazo
    )
    nombres = nombres_ml(p_prefijo)
    fecha = _fecha_utc(ahora)

    features = leer_tabla(spark, nombres["features"])
    problemas = validar_features(features)
    if problemas:
        raise ValueError(f"{nombres['features']}: " + "; ".join(problemas))
    # Punto en el tiempo: al cierre del corte a puntuar no existen cortes posteriores ni se
    # conoce la etiqueta del propio corte. Asi una ejecucion retrospectiva no ve el futuro.
    visibles = features.loc[features[CORTE] <= p_corte_puntuacion].copy()
    visibles.loc[visibles[CORTE] == p_corte_puntuacion, ETIQUETA] = np.nan
    cortes = cortes_para(p_corte_puntuacion, sorted(visibles[CORTE].unique()))
    partes = dividir_temporal(
        visibles,
        entrenamiento=cortes["entrenamiento"],
        validacion=cortes["validacion"],
        prueba=cortes["prueba"],
        puntuacion=cortes["puntuacion"],
    )

    registro = leer_tabla(spark, nombres["registro"], opcional=True)
    campeon = campeon_actual(registro)

    entrenamiento, validacion, prueba = (
        partes["entrenamiento"], partes["validacion"], partes["prueba"]
    )
    mlflow.set_experiment(nombres["experimento"])
    version: int | None = None
    with mlflow.start_run(run_name=f"retador_{p_tipo_modelo}_{p_corte_puntuacion}") as corrida:
        run_id = corrida.info.run_id
        retador = crear_modelo(p_tipo_modelo).fit(
            entrenamiento[list(FEATURES)], entrenamiento[ETIQUETA].astype(int)
        )
        metricas_val = _evaluar_en(retador, validacion)
        metricas_prueba = _evaluar_en(retador, prueba)
        mlflow.log_params(
            {
                "tipo_modelo": p_tipo_modelo,
                "cortes_entrenamiento": ",".join(cortes["entrenamiento"]),
                "corte_validacion": cortes["validacion"],
                "corte_prueba": cortes["prueba"],
                "umbral_alta_actividad": UMBRAL_ALTA_ACTIVIDAD,
                "filas_entrenamiento": len(entrenamiento),
            }
        )
        mlflow.log_metrics(
            {
                **{f"{k}_validacion": v for k, v in metricas_val.items()},
                **{f"{k}_prueba": v for k, v in metricas_prueba.items()},
            }
        )

        metricas_campeon = None
        if campeon is not None:
            modelo_campeon = mlflow.sklearn.load_model(
                f"models:/{nombres['modelo']}/{campeon['version']}"
            )
            metricas_campeon = _evaluar_en(modelo_campeon, prueba)
            mlflow.log_metric("auc_prueba_campeon", metricas_campeon["auc"])
        decision = decidir_promocion(metricas_prueba, metricas_campeon)
        mlflow.set_tags(
            {"decision": decision["decision"], "corte_puntuacion": p_corte_puntuacion}
        )

        firma = mlflow.models.infer_signature(
            entrenamiento[list(FEATURES)], retador.predict(entrenamiento[list(FEATURES)])
        )
        mlflow.sklearn.log_model(
            retador, "model", signature=firma, serialization_format="cloudpickle"
        )
        if decision["decision"] == "promover":
            registrada = mlflow.register_model(
                f"runs:/{run_id}/model",
                nombres["modelo"],
                tags={
                    "tipo_modelo": p_tipo_modelo,
                    "corte_prueba": cortes["prueba"],
                    "auc_prueba": f"{metricas_prueba['auc']:.4f}",
                    "umbral_alta_actividad": str(UMBRAL_ALTA_ACTIVIDAD),
                },
            )
            version = int(registrada.version)

    if version is not None:
        registro = _nuevo_evento(
            registro, "promocion", version, p_tipo_modelo, metricas_val["auc"],
            metricas_prueba["auc"], cortes["prueba"], run_id, decision["motivo"], ahora,
        )
        escribir_tabla(spark, nombres["registro"], registro, COLUMNAS_REGISTRO)
        campeon = campeon_actual(registro)
    if campeon is None:
        raise ValueError(
            f"{nombres['modelo']}: expected a champion model; observed none "
            f"(the challenger was rejected: {decision['motivo']})"
        )

    modelo_activo = mlflow.sklearn.load_model(f"models:/{nombres['modelo']}/{campeon['version']}")
    por_puntuar = partes["puntuacion"]
    if p_factor_deriva and p_factor_deriva > 0:
        por_puntuar = simular_deriva_actividad(por_puntuar, p_factor_deriva)
    puntuacion = puntuar(modelo_activo, por_puntuar)
    puntuacion["version_modelo"] = campeon["version"]
    puntuacion["fecha_utc"] = fecha
    reemplazar_corte(
        spark, nombres["puntuacion"], puntuacion, COLUMNAS_PUNTUACION, CORTE,
        cortes["puntuacion"],
    )

    deriva = reporte_deriva(entrenamiento, por_puntuar)
    deriva_tabla = deriva.assign(
        corte=cortes["puntuacion"], simulada=int(bool(p_factor_deriva)), fecha_utc=fecha
    )
    reemplazar_corte(
        spark, nombres["deriva"], deriva_tabla, COLUMNAS_DERIVA, "corte", cortes["puntuacion"]
    )

    auc_real = None
    anterior = str(pd.Period(p_corte_puntuacion, freq="M") - 1)
    previas = leer_tabla(spark, nombres["puntuacion"], opcional=True)
    if previas is not None:
        previas = previas.loc[previas[CORTE] == anterior]
        reales = features.loc[(features[CORTE] == anterior) & features[ETIQUETA].notna()]
        union = previas.merge(reales[[CLAVE, ETIQUETA]], on=CLAVE, how="inner")
        if not union.empty:
            metricas_reales = evaluar_clasificador(
                union[ETIQUETA], union["probabilidad_alta_actividad"]
            )
            auc_real = metricas_reales["auc"]
            medicion = pd.DataFrame(
                [
                    {
                        "corte_prediccion": anterior,
                        "mes_evaluado": str(pd.Period(anterior, freq="M") + 1),
                        "version_modelo": int(union["version_modelo"].iloc[0]),
                        "filas": len(union),
                        "auc": auc_real,
                        "average_precision": metricas_reales["average_precision"],
                        "prevalencia_real": metricas_reales["prevalencia"],
                        "fecha_utc": fecha,
                    }
                ]
            )
            reemplazar_corte(
                spark, nombres["desempeno"], medicion, COLUMNAS_DESEMPENO,
                "corte_prediccion", anterior,
            )

    salud = evaluar_alertas(deriva, auc_actual=auc_real, auc_referencia=campeon["auc_prueba"])
    informe = {
        "status": "success",
        "lakehouse": lakehouse,
        "corte_puntuacion": cortes["puntuacion"],
        "cortes": {k: list(v) if isinstance(v, tuple) else v for k, v in cortes.items()},
        "decision": decision["decision"],
        "motivo": decision["motivo"],
        "version_campeon": campeon["version"],
        "retador": {k: round(v, 6) for k, v in metricas_prueba.items()},
        "campeon_previo": (
            None if metricas_campeon is None
            else {k: round(v, 6) for k, v in metricas_campeon.items()}
        ),
        "deriva": {k: int(v) for k, v in deriva["deriva"].value_counts().items()},
        "deriva_simulada": bool(p_factor_deriva),
        "auc_real_mes_anterior": None if auc_real is None else round(auc_real, 6),
        "alertas": salud["alertas"],
        "recomendacion": salud["recomendacion"],
    }
    print(json.dumps(informe, ensure_ascii=False, sort_keys=True))
    return informe
