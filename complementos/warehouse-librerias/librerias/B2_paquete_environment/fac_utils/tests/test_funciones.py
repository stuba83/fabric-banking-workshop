"""Pruebas locales de fac_utils (sin Spark): reglas puras y un DataFrame de mentira.

    python -m unittest discover -s tests -v        # desde B2_paquete_environment/fac_utils

Las funciones que usan PySpark (validar_rango_fechas, hash_fila) se prueban solo si pyspark
está instalado; la regla de hash se valida con hash_fila_python contra valores de referencia.
"""

import importlib.util
import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "src"))

import fac_utils  # noqa: E402
from fac_utils import funciones  # noqa: E402

HAY_PYSPARK = importlib.util.find_spec("pyspark") is not None
RAIZ = AQUI.parents[3]  # .../warehouse-librerias


class FakeDF:
    def __init__(self, columnas):
        self.columns = list(columnas)

    def toDF(self, *nuevos):
        return FakeDF(nuevos)


class NormalizarNombre(unittest.TestCase):
    def test_casos(self):
        casos = {
            "Fecha de Alta (UTC)": "fecha_de_alta_utc",
            "ID Transacción": "id_transaccion",
            "Monto (CRC)": "monto_crc",
            "FechaAlta": "fecha_alta",
            "clienteID": "cliente_id",
            "  Ñandú  ": "nandu",
            "2026 ventas": "c_2026_ventas",
            "###": "columna",
            "ya_normal": "ya_normal",
        }
        for entrada, esperado in casos.items():
            with self.subTest(entrada=entrada):
                self.assertEqual(funciones.normalizar_nombre(entrada), esperado)

    def test_none(self):
        with self.assertRaises(ValueError):
            funciones.normalizar_nombre(None)

    def test_unicos(self):
        self.assertEqual(
            funciones.nombres_unicos(["a", "b", "a", "a", "a_2"]),
            ["a", "b", "a_2", "a_3", "a_2_2"],
        )

    def test_normalizar_columnas(self):
        df = FakeDF(["ID Transacción", "Monto (CRC)", "Monto  CRC"])
        self.assertEqual(
            fac_utils.normalizar_columnas(df).columns, ["id_transaccion", "monto_crc", "monto_crc_2"]
        )


class HashPython(unittest.TestCase):
    def test_referencia(self):
        # Valores calculados con la implementación de referencia del dataset sintético.
        valores = ["TX00000001", "CTA001562", "DEBITO", "BANCA_MOVIL", Decimal("129883.86")]
        self.assertEqual(
            fac_utils.hash_fila_python(valores),
            "4d01750fa7d9891609de2ddfaca0af9f435d9037944b6d3d49948a8cbea76a50",
        )

    def test_nulo_y_separador(self):
        self.assertNotEqual(fac_utils.hash_fila_python(["a", None]), fac_utils.hash_fila_python(["a", ""]))
        # Límite documentado: el separador dentro de un valor puede producir colisiones.
        self.assertEqual(fac_utils.hash_fila_python(["a|b", "c"]), fac_utils.hash_fila_python(["a", "b|c"]))

    def test_decimal_conserva_escala(self):
        self.assertEqual(str(Decimal("20.00")), "20.00")
        self.assertEqual(fac_utils.hash_fila_python([Decimal("20.00")]), fac_utils.hash_fila_python(["20.00"]))


class Validaciones(unittest.TestCase):
    def test_fecha_iso(self):
        self.assertEqual(funciones._fecha_iso("2026-04-01", "d"), "2026-04-01")
        with self.assertRaises(ValueError):
            funciones._fecha_iso("01/04/2026", "d")

    def test_bitacora_estado_invalido(self):
        with self.assertRaises(ValueError):
            fac_utils.escribir_bitacora(None, "x", "MAL")

    def test_version_y_api_publica(self):
        self.assertEqual(fac_utils.version(), fac_utils.__version__)
        for nombre in fac_utils.__all__:
            self.assertTrue(hasattr(fac_utils, nombre), nombre)


@unittest.skipUnless(HAY_PYSPARK, "pyspark no instalado")
class ConSpark(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pyspark.sql import SparkSession

        cls.spark = SparkSession.builder.master("local[1]").appName("fac_utils_tests").getOrCreate()

    def test_rango_y_hash(self):
        df = self.spark.createDataFrame(
            [("TX1", "2026-04-01", "10.50"), ("TX2", "2026-10-05", None), ("TX3", None, "1.00")],
            ["id", "fecha", "monto"],
        )
        r = fac_utils.validar_rango_fechas(df, "fecha", "2026-04-01", "2026-09-30")
        self.assertEqual((r["total"], r["nulos"], r["fuera_de_rango"], r["ok"]), (3, 1, 1, False))
        h = fac_utils.hash_fila(df, ["id", "monto"]).orderBy("id").collect()
        self.assertEqual(h[0]["hash_fila"], fac_utils.hash_fila_python(["TX1", "10.50"]))
        self.assertEqual(h[1]["hash_fila"], fac_utils.hash_fila_python(["TX2", None]))


@unittest.skipUnless((RAIZ / "librerias" / "fuente" / "funciones.py").exists(), "fuera del árbol del demo")
class Variantes(unittest.TestCase):
    def test_copias_identicas(self):
        fuente = (RAIZ / "librerias" / "fuente" / "funciones.py").read_text(encoding="utf-8")
        copias = [
            RAIZ / "librerias" / "B2_paquete_environment" / "fac_utils" / "src" / "fac_utils" / "funciones.py",
            RAIZ / "librerias" / "B3_modulo_files" / "fac_utils_lh.py",
        ]
        for copia in copias:
            with self.subTest(copia=copia.name):
                self.assertEqual(copia.read_text(encoding="utf-8"), fuente)

    def test_notebook_utils_contiene_la_fuente(self):
        fuente = (RAIZ / "librerias" / "fuente" / "funciones.py").read_text(encoding="utf-8").rstrip("\n")
        nb = json.loads((RAIZ / "librerias" / "B1_notebook_run" / "FAC_NB_Utils.ipynb").read_text(encoding="utf-8"))
        codigos = ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]
        self.assertIn(fuente, codigos)


if __name__ == "__main__":
    unittest.main()
