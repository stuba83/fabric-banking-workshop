"""Caso de ML del bonus B6: deteccion de transacciones atipicas con puntuacion en linea.

Pregunta: dada una transaccion en el momento en que ocurre, ¿se parece a lo que esa
cuenta suele hacer? No hay etiquetas de fraude: se entrena un modelo no supervisado
(IsolationForest) solo con comportamiento normal y se mide con **anomalias inyectadas**
en los meses de validacion y prueba, cuya naturaleza y cantidad se conocen.

Los datos son sinteticos: las metricas sirven para practicar el ciclo de vida, no para
estimar el rendimiento de un detector real. El modulo solo usa pandas, numpy y
scikit-learn, que forman parte del runtime de Fabric, y no depende de `ml_actividad.py`.
Las variables se calculan con **una sola funcion** (`construir_features_tx`) tanto para
entrenar como para puntuar una transaccion en linea: esa es la forma de evitar que el
entrenamiento y el servicio calculen cosas distintas.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd


CLAVE_TX = "transaccion_id"
CUENTA = "cuenta_id"
FECHA = "fecha_hora"
MES = "mes"
ETIQUETA_INYECTADA = "es_anomalia_inyectada"
TIPO_INYECTADO = "tipo_anomalia"

# Los meses de entrenamiento se usan tal como estan (supuesto: casi todo es normal).
# Abril solo aporta historial: una transaccion necesita varias previas de su cuenta.
MESES_ENTRENAMIENTO = ("2026-05", "2026-06", "2026-07")
MES_VALIDACION = "2026-08"
MES_PRUEBA = "2026-09"
MINIMO_HISTORIAL = 10
VENTANA_CANAL = 10
TASA_REVISION = 0.01
ENTRENAMIENTO_MAXIMO = 20000
TASA_INYECCION = 0.01
SEMILLA_VALIDACION = 11
SEMILLA_PRUEBA = 23

TIPOS_ANOMALIA = ("monto_extremo", "madrugada", "rafaga")
MAXIMO_MINUTOS_SIN_ACTIVIDAD = 720.0 * 60.0
PISO_MAD = 0.05

FEATURES_NUMERICAS_TX = (
    "z_monto_tipo",
    "hora",
    "es_fin_semana",
    "log_minutos_desde_ultima",
    "tx_ultimas_24h",
    "pct_canal_historial",
)
FEATURES_CATEGORICAS_TX = ("canal", "tipo_transaccion")
FEATURES_TX = FEATURES_NUMERICAS_TX + FEATURES_CATEGORICAS_TX
# Columnas enteras: en la solicitud al endpoint deben viajar como enteros, no como decimales.
FEATURES_ENTERAS_TX = ("hora", "es_fin_semana", "tx_ultimas_24h")

_COLUMNAS_TX = (CLAVE_TX, CUENTA, FECHA, "tipo_transaccion", "direccion", "canal", "monto")

COLUMNAS_REFERENCIA_TX = (
    ("tipo_transaccion", "string"),
    ("mediana_log_monto", "double"),
    ("mad_log_monto", "double"),
    ("max_monto", "double"),
    ("filas", "bigint"),
    ("fecha_utc", "string"),
)
COLUMNAS_ANOMALIAS_TX = (
    (CLAVE_TX, "string"),
    (CUENTA, "string"),
    (MES, "string"),
    (FECHA, "string"),
    ("tipo_transaccion", "string"),
    ("canal", "string"),
    ("monto", "double"),
    ("score_anomalia", "double"),
    ("es_atipica", "bigint"),
    (ETIQUETA_INYECTADA, "bigint"),
    (TIPO_INYECTADO, "string"),
    ("version_modelo", "bigint"),
    ("fecha_utc", "string"),
)


def nombres_anomalias(prefijo: str) -> dict[str, str]:
    p = prefijo.lower()
    return {
        "referencia": f"{p}_gold_ml_referencia_tx",
        "anomalias": f"{p}_gold_ml_anomalias_tx",
        "experimento": f"{p}_exp_anomalias_tx",
        "modelo": f"{p}_modelo_anomalias_tx",
    }


def _exigir_columnas_tx(df: pd.DataFrame, columnas: Sequence[str], nombre: str) -> None:
    faltantes = [columna for columna in columnas if columna not in df.columns]
    if faltantes:
        raise ValueError(
            f"{nombre}: expected columns {list(columnas)!r}; observed missing {faltantes!r}"
        )


def preparar_transacciones(transacciones: pd.DataFrame) -> pd.DataFrame:
    """Copia ordenada, con fecha sin zona y monto decimal, lista para calcular variables."""
    _exigir_columnas_tx(transacciones, _COLUMNAS_TX, "transacciones")
    tx = transacciones.loc[:, list(_COLUMNAS_TX)].copy()
    tx[FECHA] = pd.to_datetime(tx[FECHA])
    if tx[FECHA].dt.tz is not None:
        tx[FECHA] = tx[FECHA].dt.tz_localize(None)
    tx[FECHA] = tx[FECHA].astype("datetime64[ns]")
    tx["monto"] = pd.to_numeric(tx["monto"].astype(float), errors="raise")
    if (tx["monto"] <= 0).any():
        raise ValueError("transacciones: expected positive amounts; observed non-positive values")
    if tx[CLAVE_TX].duplicated().any():
        raise ValueError(f"transacciones: expected unique {CLAVE_TX}; observed duplicates")
    return tx.sort_values([CUENTA, FECHA, CLAVE_TX], kind="mergesort").reset_index(drop=True)


def calcular_referencia(transacciones: pd.DataFrame, fecha_utc: str = "") -> pd.DataFrame:
    """Mediana y desviacion robusta (MAD) del logaritmo del monto por tipo, y el monto maximo.

    Se calcula **solo con los meses de entrenamiento**. Es la referencia que el servicio
    en linea necesita para calcular `z_monto_tipo` de una transaccion nueva.
    """
    tx = preparar_transacciones(transacciones)
    tx["log_monto"] = np.log(tx["monto"])
    filas = []
    for tipo, grupo in tx.groupby("tipo_transaccion"):
        mediana = float(grupo["log_monto"].median())
        mad = float((grupo["log_monto"] - mediana).abs().median() * 1.4826)
        filas.append(
            {
                "tipo_transaccion": str(tipo),
                "mediana_log_monto": mediana,
                "mad_log_monto": max(mad, PISO_MAD),
                "max_monto": float(grupo["monto"].max()),
                "filas": int(len(grupo)),
                "fecha_utc": fecha_utc,
            }
        )
    return pd.DataFrame(filas).sort_values("tipo_transaccion").reset_index(drop=True)


def construir_features_tx(
    transacciones: pd.DataFrame,
    referencia: pd.DataFrame,
    minimo_historial: int = MINIMO_HISTORIAL,
) -> pd.DataFrame:
    """Una fila por transaccion con variables que solo usan lo ocurrido **antes** de ella.

    `transacciones` debe traer todo el historial necesario (no solo el mes a puntuar).
    Se descartan las transacciones con menos de `minimo_historial` previas en su cuenta.
    Las columnas extra (por ejemplo, las etiquetas inyectadas) se conservan.
    """
    base = preparar_transacciones(transacciones)
    extras = [c for c in transacciones.columns if c not in _COLUMNAS_TX]
    if extras:
        base = base.merge(transacciones[[CLAVE_TX, *extras]], on=CLAVE_TX, how="left")
        base = base.sort_values([CUENTA, FECHA, CLAVE_TX], kind="mergesort").reset_index(drop=True)
    _exigir_columnas_tx(referencia, ("tipo_transaccion", "mediana_log_monto", "mad_log_monto"), "referencia")
    desconocidos = sorted(set(base["tipo_transaccion"]) - set(referencia["tipo_transaccion"]))
    if desconocidos:
        raise ValueError(
            f"referencia: expected every transaction type; observed missing {desconocidos!r}"
        )
    ref = referencia.set_index("tipo_transaccion")

    grupo = base.groupby(CUENTA, sort=False)
    base["n_previas"] = grupo.cumcount()
    # Parte de las ultimas VENTANA_CANAL transacciones previas de la cuenta que uso este mismo canal.
    # Una ventana de tamano fijo evita que la variable cambie solo porque el historial crece.
    misma = pd.Series(0.0, index=base.index)
    for canal in base["canal"].unique():
        es_canal = (base["canal"] == canal).astype(float)
        previas_canal = es_canal.groupby(base[CUENTA], sort=False).transform(
            lambda s: s.shift(1).rolling(VENTANA_CANAL, min_periods=1).sum()
        )
        misma = misma.where(base["canal"] != canal, previas_canal.fillna(0.0))
    base["pct_canal_historial"] = misma / base["n_previas"].clip(lower=1, upper=VENTANA_CANAL)
    segundos = base[FECHA].astype("datetime64[ns]").astype("int64") / 1e9
    base["_segundos"] = segundos
    anterior = base.groupby(CUENTA, sort=False)["_segundos"].shift(1)
    minutos = ((base["_segundos"] - anterior) / 60.0).clip(upper=MAXIMO_MINUTOS_SIN_ACTIVIDAD)
    base["log_minutos_desde_ultima"] = np.log1p(minutos)

    def _ultimas_24h(serie: pd.Series) -> np.ndarray:
        s = serie.to_numpy()
        return np.arange(len(s)) - np.searchsorted(s, s - 24 * 3600, side="left")

    base["tx_ultimas_24h"] = base.groupby(CUENTA, sort=False)["_segundos"].transform(_ultimas_24h)

    mediana = base["tipo_transaccion"].map(ref["mediana_log_monto"])
    mad = base["tipo_transaccion"].map(ref["mad_log_monto"])
    base["z_monto_tipo"] = (np.log(base["monto"]) - mediana) / mad
    base["hora"] = base[FECHA].dt.hour.astype("int64")
    base["es_fin_semana"] = (base[FECHA].dt.day_of_week >= 5).astype("int64")
    base["tx_ultimas_24h"] = base["tx_ultimas_24h"].astype("int64")
    base[MES] = base[FECHA].dt.strftime("%Y-%m")

    elegibles = base.loc[base["n_previas"] >= minimo_historial].copy()
    columnas = [CLAVE_TX, CUENTA, MES, FECHA, "monto", "n_previas", *FEATURES_TX, *extras]
    return elegibles.loc[:, columnas].reset_index(drop=True)


def inyectar_anomalias(
    transacciones: pd.DataFrame,
    semillas_por_mes: Mapping[str, int],
    tasa: float = TASA_INYECCION,
    minimo_historial: int = MINIMO_HISTORIAL,
) -> pd.DataFrame:
    """Copia de `transacciones` con anomalias conocidas en cada mes de `semillas_por_mes` (mes -> semilla).

    Tipos (se reparten por igual; `tasa` es la fraccion de filas del mes que queda etiquetada):

    * `monto_extremo`: el monto se multiplica por un factor entre 3 y 8.
    * `madrugada`: la hora pasa a la madrugada (0 a 5 h, que en estos datos nunca ocurre)
      y el monto se multiplica por un factor entre 1 y 2,5.
    * `rafaga`: tras la transaccion elegida se agregan tres mas de la misma cuenta, tipo y canal,
      en los siguientes 20 minutos y con montos parecidos. Las tres agregadas son las etiquetadas.
    """
    if not 0 < tasa < 0.2:
        raise ValueError(f"tasa: expected a number in (0, 0.2); observed {tasa!r}")
    tx = preparar_transacciones(transacciones)
    tx[ETIQUETA_INYECTADA] = np.int64(0)
    tx[TIPO_INYECTADO] = ""
    nuevas: list[dict[str, Any]] = []
    contador = 0

    previas = tx.groupby(CUENTA, sort=False).cumcount()
    mes_fila = tx[FECHA].dt.strftime("%Y-%m")
    # Margen extra: mover una transaccion a la madrugada la adelanta y puede quitarle historial.
    margen_historial = minimo_historial + 3
    for mes, semilla in semillas_por_mes.items():
        rng = np.random.default_rng(semilla)
        candidatas = np.flatnonzero(
            ((mes_fila == mes) & (previas >= margen_historial) & (tx[FECHA].dt.day <= 27)).to_numpy()
        )
        por_tipo = int(round(tasa * int((mes_fila == mes).sum()) / 5))
        if por_tipo * 3 > len(candidatas):
            raise ValueError(
                f"{mes}: expected at least {por_tipo * 3} eligible rows; observed {len(candidatas)}"
            )
        elegidas = rng.choice(candidatas, size=por_tipo * 3, replace=False)
        for tipo, indices in zip(TIPOS_ANOMALIA, np.split(elegidas, 3)):
            for i in indices:
                fila = tx.iloc[i]
                if tipo == "monto_extremo":
                    tx.at[i, "monto"] = round(float(fila["monto"]) * float(rng.uniform(3, 8)), 2)
                    tx.at[i, ETIQUETA_INYECTADA], tx.at[i, TIPO_INYECTADO] = 1, tipo
                elif tipo == "madrugada":
                    momento = fila[FECHA].normalize() + pd.Timedelta(
                        hours=int(rng.integers(0, 6)),
                        minutes=int(rng.integers(0, 60)),
                        seconds=int(rng.integers(0, 60)),
                    )
                    tx.at[i, FECHA] = momento
                    tx.at[i, "monto"] = round(float(fila["monto"]) * float(rng.uniform(1, 2.5)), 2)
                    tx.at[i, ETIQUETA_INYECTADA], tx.at[i, TIPO_INYECTADO] = 1, tipo
                else:
                    momento = fila[FECHA]
                    for _ in range(3):
                        contador += 1
                        momento = momento + pd.Timedelta(
                            minutes=float(rng.uniform(1, 6)), seconds=int(rng.integers(0, 60))
                        )
                        nuevas.append(
                            {
                                CLAVE_TX: f"TXR{contador:06d}",
                                CUENTA: fila[CUENTA],
                                FECHA: momento,
                                "tipo_transaccion": fila["tipo_transaccion"],
                                "direccion": fila["direccion"],
                                "canal": fila["canal"],
                                "monto": round(float(fila["monto"]) * float(rng.uniform(0.9, 1.1)), 2),
                                ETIQUETA_INYECTADA: np.int64(1),
                                TIPO_INYECTADO: tipo,
                            }
                        )
    if nuevas:
        tx = pd.concat([tx, pd.DataFrame(nuevas)], ignore_index=True)
    tx[ETIQUETA_INYECTADA] = tx[ETIQUETA_INYECTADA].astype("int64")
    return tx.sort_values([CUENTA, FECHA, CLAVE_TX], kind="mergesort").reset_index(drop=True)


def muestrear_entrenamiento(df: pd.DataFrame, maximo: int = ENTRENAMIENTO_MAXIMO, semilla: int = 42) -> pd.DataFrame:
    """Muestra aleatoria reproducible: LOF y OneClassSVM guardan o comparan contra los datos de entrenamiento."""
    if maximo < 1:
        raise ValueError(f"maximo: expected a positive integer; observed {maximo!r}")
    if len(df) <= maximo:
        return df.reset_index(drop=True)
    return df.sample(n=maximo, random_state=semilla).sort_index().reset_index(drop=True)


def crear_detector(tipo: str = "lof", vecinos: int = 100, semilla: int = 42) -> Any:
    """Pipeline de scikit-learn: escalado y one-hot + un detector no supervisado.

    `tipo`: `iforest` (IsolationForest) o `lof` (LocalOutlierFactor con `novelty=True`, que permite
    puntuar datos nuevos). Los dos exponen `offset_`, el umbral que usa `predict`.
    """
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import IsolationForest
    from sklearn.neighbors import LocalOutlierFactor
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    detectores = {
        "iforest": lambda: IsolationForest(n_estimators=200, random_state=semilla, n_jobs=1),
        "lof": lambda: LocalOutlierFactor(n_neighbors=vecinos, novelty=True),
    }
    if tipo not in detectores:
        raise ValueError(f"tipo: expected one of {sorted(detectores)!r}; observed {tipo!r}")
    preparacion = ColumnTransformer(
        [
            ("numericas", StandardScaler(), list(FEATURES_NUMERICAS_TX)),
            ("categoricas", OneHotEncoder(handle_unknown="ignore", sparse_output=False), list(FEATURES_CATEGORICAS_TX)),
        ]
    )
    return Pipeline([("preparacion", preparacion), ("detector", detectores[tipo]())])


def _puntaje_crudo(modelo: Any, df: pd.DataFrame) -> np.ndarray:
    """`score_samples` de scikit-learn: cuanto mas bajo, mas atipica la transaccion."""
    transformadas = modelo.named_steps["preparacion"].transform(df[list(FEATURES_TX)])
    return modelo.named_steps["detector"].score_samples(transformadas)


def fijar_umbral(modelo: Any, validacion: pd.DataFrame, tasa: float = TASA_REVISION) -> float:
    """Ajusta el umbral para marcar aproximadamente `tasa` de la validacion y lo guarda en el modelo.

    `predict` marca como atipica la transaccion cuyo puntaje es menor que `offset_`. Fijar
    `offset_` deja el umbral **dentro del modelo registrado**: el lote, `PREDICT` y el endpoint
    usan exactamente el mismo. La `tasa` es la capacidad de revision (cuantas se pueden revisar).
    """
    if not 0 < tasa < 0.2:
        raise ValueError(f"tasa: expected a number in (0, 0.2); observed {tasa!r}")
    umbral = float(np.quantile(_puntaje_crudo(modelo, validacion), tasa))
    modelo.named_steps["detector"].offset_ = umbral
    return umbral

def puntuar_anomalias(modelo: Any, df: pd.DataFrame) -> pd.DataFrame:
    """Puntaje de anomalia (mayor = mas atipica) y marca de atipica (1) segun el umbral del modelo."""
    puntaje = -modelo.decision_function(df[list(FEATURES_TX)])
    marca = (modelo.predict(df[list(FEATURES_TX)]) == -1).astype("int64")
    return pd.DataFrame(
        {
            CLAVE_TX: df[CLAVE_TX].to_numpy(),
            "score_anomalia": np.asarray(puntaje, dtype=float),
            "es_atipica": marca,
        }
    )


def evaluar_deteccion(y_real: Any, puntaje: Any, marcadas: Any) -> dict[str, float]:
    from sklearn.metrics import average_precision_score, roc_auc_score

    y = np.asarray(y_real, dtype=int)
    p = np.asarray(puntaje, dtype=float)
    m = np.asarray(marcadas, dtype=int)
    positivos_marcados = int(((y == 1) & (m == 1)).sum())
    return {
        "auc": float(roc_auc_score(y, p)),
        "average_precision": float(average_precision_score(y, p)),
        "precision": positivos_marcados / max(int(m.sum()), 1),
        "recall": positivos_marcados / max(int(y.sum()), 1),
        "tasa_marcadas": float(m.mean()),
        "prevalencia": float(y.mean()),
    }


def regla_maximo_por_tipo(df: pd.DataFrame, referencia: pd.DataFrame) -> pd.DataFrame:
    """Linea base sin aprendizaje: marca una transaccion si supera el monto maximo de su tipo en entrenamiento."""
    maximo = df["tipo_transaccion"].map(referencia.set_index("tipo_transaccion")["max_monto"])
    razon = df["monto"].to_numpy() / maximo.to_numpy()
    return pd.DataFrame(
        {CLAVE_TX: df[CLAVE_TX].to_numpy(), "score_anomalia": razon, "es_atipica": (razon > 1.0).astype("int64")}
    )


def recall_por_tipo(df: pd.DataFrame, marcadas: Any) -> pd.DataFrame:
    """Proporcion de anomalias inyectadas de cada tipo que quedaron marcadas."""
    marcado = pd.Series(np.asarray(marcadas, dtype=int), index=df.index)
    inyectadas = df.loc[df[ETIQUETA_INYECTADA] == 1]
    tabla = (
        pd.DataFrame({"tipo_anomalia": inyectadas[TIPO_INYECTADO], "marcada": marcado.loc[inyectadas.index]})
        .groupby("tipo_anomalia")["marcada"]
        .agg(inyectadas="size", marcadas="sum")
        .reindex(TIPOS_ANOMALIA)
        .fillna(0)
        .astype("int64")
    )
    tabla["recall"] = tabla["marcadas"] / tabla["inyectadas"].clip(lower=1)
    return tabla.reset_index()


def _nativo(valor: Any) -> Any:
    if isinstance(valor, np.generic):
        valor = valor.item()
    if isinstance(valor, float) and math.isnan(valor):
        raise ValueError("solicitud: expected no missing values; observed NaN")
    return valor


def solicitud_endpoint(df: pd.DataFrame) -> dict[str, Any]:
    """Cuerpo JSON para `.../endpoint/versions/<n>/score` con las columnas en el orden de la firma."""
    filas = []
    for _, fila in df[list(FEATURES_TX)].iterrows():
        valores = []
        for columna in FEATURES_TX:
            valor = _nativo(fila[columna])
            if columna in FEATURES_ENTERAS_TX:
                valor = int(valor)
            elif columna in FEATURES_CATEGORICAS_TX:
                valor = str(valor)
            else:
                valor = float(valor)
            valores.append(valor)
        filas.append(valores)
    return {"formatType": "dataframe", "orientation": "values", "inputs": filas}


def features_de_una_transaccion(
    historial: pd.DataFrame, nueva: Mapping[str, Any], referencia: pd.DataFrame
) -> pd.DataFrame:
    """Variables de una transaccion nueva, calculadas con el **mismo codigo** que el entrenamiento.

    `historial` son las transacciones previas de la cuenta (o de varias). La nueva se agrega al
    final; no se necesita nada del futuro.
    """
    _exigir_columnas_tx(pd.DataFrame([nueva]), _COLUMNAS_TX, "nueva")
    cuenta = nueva[CUENTA]
    previo = historial.loc[historial[CUENTA] == cuenta, list(_COLUMNAS_TX)]
    posterior = previo.loc[pd.to_datetime(previo[FECHA]) > pd.to_datetime(nueva[FECHA])]
    if not posterior.empty:
        raise ValueError("historial: expected only transactions before the new one; observed later ones")
    unido = pd.concat([previo, pd.DataFrame([dict(nueva)])[list(_COLUMNAS_TX)]], ignore_index=True)
    resultado = construir_features_tx(unido, referencia)
    fila = resultado.loc[resultado[CLAVE_TX] == nueva[CLAVE_TX]]
    if fila.empty:
        raise ValueError(
            f"historial: expected at least {MINIMO_HISTORIAL} previous transactions for {cuenta}; observed fewer"
        )
    return fila.reset_index(drop=True)


def elegir_candidato(candidatos: pd.DataFrame, margen: float = 0.01) -> str:
    """Entre los candidatos con AP de validacion a menos de `margen` del mejor, el menos complejo.

    `candidatos` trae `nombre`, `average_precision_validacion` y `complejidad` (cuanto menor, mas simple).
    """
    _exigir_columnas_tx(candidatos, ("nombre", "average_precision_validacion", "complejidad"), "candidatos")
    if candidatos.empty:
        raise ValueError("candidatos: expected at least one row; observed none")
    mejor = float(candidatos["average_precision_validacion"].max())
    cercanos = candidatos.loc[candidatos["average_precision_validacion"] >= mejor - margen]
    return str(cercanos.sort_values(["complejidad", "nombre"]).iloc[0]["nombre"])


def diferencias_entre_features(completas: pd.DataFrame, recortadas: pd.DataFrame) -> int:
    """Cuenta valores distintos en las filas comunes: debe ser 0 si no hay fuga de datos.

    `recortadas` se calcula con los datos cortados en una fecha; las variables de las transacciones
    anteriores a esa fecha no pueden cambiar.
    """
    comunes = completas.merge(recortadas, on=CLAVE_TX, suffixes=("", "_recortada"))
    if comunes.empty:
        raise ValueError("features: expected rows in common; observed none")
    distintos = 0
    for columna in FEATURES_TX:
        if columna in FEATURES_CATEGORICAS_TX:
            distintos += int((comunes[columna] != comunes[columna + "_recortada"]).sum())
        else:
            distintos += int((~np.isclose(comunes[columna], comunes[columna + "_recortada"])).sum())
    return distintos


def puntuar_en_linea(
    cliente: Any, id_workspace: str, id_modelo: str, cuerpo: Mapping[str, Any], version: int | None = None
) -> dict[str, Any]:
    """Llama al endpoint en tiempo real de una version activa; nunca activa ninguna por su cuenta.

    Sin `version`, usa la mas reciente de las versiones activas. `cliente` es un cliente REST de Fabric
    (`sempy.fabric.FabricRestClient`) o algo con la misma forma: `get(ruta)` y `post(ruta, json=...)`
    que devuelven un objeto con `status_code` y `json()`.
    """
    ruta = f"/v1/workspaces/{id_workspace}/mlmodels/{id_modelo}/endpoint/versions"
    respuesta = cliente.get(ruta)
    if respuesta.status_code != 200:
        return {"estado": f"consulta fallida (HTTP {respuesta.status_code})", "version": version, "predicciones": None}
    estados = {str(v.get("versionName")): v.get("status") for v in respuesta.json().get("value", [])}
    if version is None:
        activas = sorted(int(n) for n, estado in estados.items() if estado == "Active")
        if not activas:
            resumen = ", ".join(f"v{n}: {e}" for n, e in sorted(estados.items())) or "sin versiones"
            return {"estado": f"ninguna version activa ({resumen})", "version": None, "predicciones": None}
        version = activas[-1]
    estado = estados.get(str(version), "sin endpoint")
    if estado != "Active":
        return {"estado": estado, "version": version, "predicciones": None}
    from time import perf_counter

    inicio = perf_counter()
    resultado = cliente.post(f"{ruta}/{version}/score", json=dict(cuerpo))
    segundos = perf_counter() - inicio
    if resultado.status_code != 200:
        return {"estado": f"puntuacion fallida (HTTP {resultado.status_code})", "version": version, "predicciones": None}
    predicciones = [int(fila[0]) for fila in resultado.json()["predictions"]]
    return {"estado": estado, "version": version, "predicciones": predicciones, "segundos": segundos}