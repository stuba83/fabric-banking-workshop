"""Calcula los valores esperados del demo con la implementación de referencia del repo.

Uso (solo lectura sobre el repo del taller):
    python calcular_esperados.py --repo <ruta-del-repo> [--salida valores_esperados.json]

Reutiliza notebooks/plata_silver.py (transformar) sobre los CSV para obtener, sin
necesidad de Fabric, los mismos conteos y sumas que debe medir el Warehouse. También
ejecuta en SQLite la consulta de negocio de la comparación para comprobar que la lógica
de los joins reproduce los controles por sucursal de la Sesión 4.
"""

import argparse
import csv
import importlib.util
import json
import sqlite3
import sys
from decimal import Decimal
from pathlib import Path

sys.dont_write_bytecode = True  # no dejar __pycache__ dentro del repo

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "librerias" / "fuente"))
import funciones  # noqa: E402

CSV_POR_TABLA = {
    "clientes": "clientes.csv",
    "cuentas": "cuentas.csv",
    "sucursales": "sucursales.csv",
    "productos": "productos.csv",
    "calendario": "calendario.csv",
    "transacciones": "transacciones.csv",
}

# Controles por sucursal publicados en la guía de la Sesión 4 (transacciones, créditos, débitos).
CONTROL_S4 = {
    "San Jose": (20708, "4306335336.20", "1294151130.20"),
    "Alajuela": (13840, "2869299344.17", "879889217.02"),
    "Cartago": (10689, "2226302654.31", "661871675.20"),
    "Heredia": (8971, "1886882777.70", "565981597.44"),
    "Guanacaste": (4963, "1019466999.49", "313484708.53"),
    "Puntarenas": (7281, "1506900739.54", "472402374.88"),
    "Limon": (5548, "1160965776.38", "342593128.63"),
}

SQL_NEGOCIO_SQLITE = """
SELECT substr(t.fecha, 1, 7) AS mes, s.provincia, t.canal,
       COUNT(*) AS transacciones,
       SUM(CASE WHEN t.direccion = 'CREDITO' THEN t.monto_centimos ELSE 0 END) AS creditos_centimos,
       SUM(CASE WHEN t.direccion = 'DEBITO' THEN t.monto_centimos ELSE 0 END) AS debitos_centimos
FROM transacciones t
JOIN cuentas c ON c.cuenta_id = t.cuenta_id
JOIN clientes cl ON cl.cliente_id = c.cliente_id
JOIN sucursales s ON s.sucursal_id = cl.sucursal_id
GROUP BY 1, 2, 3
ORDER BY 1, 2, 3
"""


def cargar_modulo(repo):
    ruta = repo / "notebooks" / "plata_silver.py"
    especificacion = importlib.util.spec_from_file_location("plata_silver_ref", ruta)
    modulo = importlib.util.module_from_spec(especificacion)
    sys.modules[especificacion.name] = modulo  # los dataclass del módulo lo necesitan
    especificacion.loader.exec_module(modulo)
    return modulo


def leer_csv(repo, base, modulo):
    ruta = repo / "dataset" / "csv" / CSV_POR_TABLA[base]
    with ruta.open(newline="", encoding="utf-8-sig") as archivo:
        lector = csv.reader(archivo)
        encabezado = next(lector)
        esperado = list(modulo.columnas_bronce(base))
        if encabezado != esperado:
            raise SystemExit(f"{ruta.name}: encabezado {encabezado} distinto de {esperado}")
        return [tuple(fila) for fila in lector]


def centimos(valor):
    return int((Decimal(valor) * 100).to_integral_value())


def dinero(centimos_):
    return f"{Decimal(centimos_) / 100:.2f}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--salida", type=Path, default=AQUI.parent / "valores_esperados.json")
    args = parser.parse_args()

    modulo = cargar_modulo(args.repo)
    bronce = {base: leer_csv(args.repo, base, modulo) for base in CSV_POR_TABLA}
    resultado = modulo.transformar(bronce, "ab")
    controles = modulo.verificar_controles(resultado)  # falla si algo no cuadra con el laboratorio
    tablas = resultado.tablas

    limpias = tablas["silver_transacciones"].filas
    cuentas = tablas["silver_cuentas"].filas
    clientes = tablas["silver_clientes"].filas
    sucursales = tablas["silver_sucursales"].filas
    oro = tablas["gold_transacciones_mes_canal"].filas

    # Cuadre del laboratorio.
    cuadre = {
        "bronce_transacciones": len(bronce["transacciones"]),
        "duplicadas": len(tablas["silver_transacciones_duplicadas"].filas),
        "cuarentena": len(tablas["silver_transacciones_cuarentena"].filas),
        "plata_transacciones": len(limpias),
    }
    assert cuadre["bronce_transacciones"] - cuadre["duplicadas"] - cuadre["cuarentena"] == cuadre["plata_transacciones"]

    saldo_inicial = sum(centimos(f[5]) for f in cuentas)
    creditos = sum(centimos(f[7]) for f in limpias if f[5] == "CREDITO")
    debitos = sum(centimos(f[7]) for f in limpias if f[5] == "DEBITO")

    # Consulta de negocio en SQLite (misma lógica de joins que Spark SQL y T-SQL).
    conexion = sqlite3.connect(":memory:")
    conexion.executescript(
        "CREATE TABLE transacciones (transaccion_id, cuenta_id, fecha, direccion, canal, monto_centimos);"
        "CREATE TABLE cuentas (cuenta_id, cliente_id);"
        "CREATE TABLE clientes (cliente_id, sucursal_id);"
        "CREATE TABLE sucursales (sucursal_id, provincia);"
    )
    conexion.executemany(
        "INSERT INTO transacciones VALUES (?,?,?,?,?,?)",
        [(f[0], f[1], f[3].isoformat(), f[5], f[6], centimos(f[7])) for f in limpias],
    )
    conexion.executemany("INSERT INTO cuentas VALUES (?,?)", [(f[0], f[1]) for f in cuentas])
    conexion.executemany("INSERT INTO clientes VALUES (?,?)", [(f[0], f[6]) for f in clientes])
    conexion.executemany("INSERT INTO sucursales VALUES (?,?)", [(f[0], f[2]) for f in sucursales])
    filas_negocio = conexion.execute(SQL_NEGOCIO_SQLITE).fetchall()

    por_provincia = {}
    for _, provincia, _, n, cre, deb in filas_negocio:
        acumulado = por_provincia.setdefault(provincia, [0, 0, 0])
        acumulado[0] += n
        acumulado[1] += cre
        acumulado[2] += deb
    for provincia, (n, cre, deb) in CONTROL_S4.items():
        medido = por_provincia[provincia]
        assert medido[0] == n, (provincia, medido[0], n)
        assert dinero(medido[1]) == cre and dinero(medido[2]) == deb, (provincia, medido, cre, deb)

    # Hash de las primeras filas por transaccion_id (columnas y orden de la demo).
    columnas_hash = ("transaccion_id", "cuenta_id", "direccion", "canal", "monto")
    muestra = sorted(limpias, key=lambda f: f[0])[:3]
    hashes = [
        {
            "transaccion_id": f[0],
            "valores": [f[0], f[1], f[5], f[6], str(f[7])],
            "hash_sha256": funciones.hash_fila_python([f[0], f[1], f[5], f[6], str(f[7])]),
        }
        for f in muestra
    ]

    esperados = {
        "origen": "implementacion de referencia del repo (plata_silver.transformar) sobre los CSV",
        "cuadre_laboratorio": {
            **cuadre,
            "formula": "72360 - 288 - 72 = 72000",
        },
        "tablas_lakehouse_filas": controles["filas"],
        "dimensiones_warehouse_filas": {
            "clientes.dim_sucursal": len(sucursales),
            "clientes.dim_cliente": len(clientes),
            "cuentas.dim_producto": len(tablas["silver_productos"].filas),
            "cuentas.dim_cuenta": len(cuentas),
        },
        "fact_transaccion": {
            "filas": len(limpias),
            "monto_creditos": dinero(creditos),
            "monto_debitos": dinero(debitos),
            "cuentas_con_movimiento": len({f[1] for f in limpias}),
            "fecha_hora_min": min(f[2] for f in limpias).replace(tzinfo=None).isoformat(sep=" "),
            "fecha_hora_max": max(f[2] for f in limpias).replace(tzinfo=None).isoformat(sep=" "),
        },
        "cuentas_saldo_inicial": dinero(saldo_inicial),
        "saldo_final_calculado": dinero(saldo_inicial + creditos - debitos),
        "resumen_mes_canal": {
            "filas": len(oro),
            "transacciones": sum(f[2] for f in oro),
            "monto_creditos": f"{sum((f[3] for f in oro), Decimal('0.00')):.2f}",
            "monto_debitos": f"{sum((f[4] for f in oro), Decimal('0.00')):.2f}",
        },
        "negocio_mes_provincia_canal": {
            "grupos": len(filas_negocio),
            "transacciones": sum(f[3] for f in filas_negocio),
            "monto_creditos": dinero(sum(f[4] for f in filas_negocio)),
            "monto_debitos": dinero(sum(f[5] for f in filas_negocio)),
            "primeras_filas": [
                {"mes": f[0], "provincia": f[1], "canal": f[2], "transacciones": f[3],
                 "monto_creditos": dinero(f[4]), "monto_debitos": dinero(f[5])}
                for f in filas_negocio[:5]
            ],
            "por_provincia_coincide_con_guia_sesion_4": True,
        },
        "hash_fila": {"columnas": list(columnas_hash), "separador": funciones.SEPARADOR_HASH,
                      "sentinela_nulo": funciones.SENTINELA_NULO, "muestras": hashes},
    }
    args.salida.write_text(json.dumps(esperados, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: esperados[k] for k in ("cuadre_laboratorio", "fact_transaccion", "resumen_mes_canal")},
                     indent=2, ensure_ascii=False))
    print("negocio grupos:", esperados["negocio_mes_provincia_canal"]["grupos"], "| salida:", args.salida)


if __name__ == "__main__":
    main()
