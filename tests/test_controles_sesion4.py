from __future__ import annotations

import re
import sys
import unittest
from collections import defaultdict
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from notebooks import plata_silver
from test_plata_silver import bronce_real


GUIA = ROOT / "docs" / "sesion-04" / "guia.md"
EVIDENCIAS = ROOT / "docs" / "sesion-04" / "evidencias.md"
FILA_SUCURSAL = re.compile(
    r"^\| \*{0,2}`(SUC\d\d)`\*{0,2} \| \*{0,2}`([^`]+)`\*{0,2} \| \*{0,2}([\d.]+)\*{0,2}"
    r" \| \*{0,2}([\d.,]+)\*{0,2} \| \*{0,2}([\d.,]+)\*{0,2} \|$",
    re.MULTILINE,
)


def _decimal(texto: str) -> Decimal:
    return Decimal(texto.replace(".", "").replace(",", "."))


def _formato(valor: Decimal) -> str:
    entero, decimales = f"{valor:.2f}".split(".")
    return f"{int(entero):,}".replace(",", ".") + "," + decimales


class ControlesSesion4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        resultado = plata_silver.transformar(bronce_real(), "AB")
        tablas = resultado.tablas
        clientes = {fila[0]: fila for fila in tablas["silver_clientes"].filas}
        cuentas = {fila[0]: fila for fila in tablas["silver_cuentas"].filas}
        cls.sucursales = {fila[0]: fila[2] for fila in tablas["silver_sucursales"].filas}
        cls.oro = tablas["gold_transacciones_mes_canal"].filas
        cls.medidos = plata_silver.medir_controles(resultado)

        acumulado: dict[str, list] = defaultdict(lambda: [0, Decimal("0.00"), Decimal("0.00")])
        for fila in tablas["silver_transacciones"].filas:
            sucursal = clientes[cuentas[fila[1]][1]][6]
            celda = acumulado[sucursal]
            celda[0] += 1
            celda[1 if fila[5] == "CREDITO" else 2] += fila[7]
        cls.por_sucursal = dict(acumulado)
        cls.guia = GUIA.read_text(encoding="utf-8")

    def test_branch_table_in_the_guide_matches_the_data(self) -> None:
        filas = FILA_SUCURSAL.findall(self.guia)
        self.assertEqual(len(filas), 7)
        for sucursal, provincia, transacciones, creditos, debitos in filas:
            with self.subTest(sucursal=sucursal):
                self.assertEqual(self.sucursales[sucursal], provincia)
                esperado = self.por_sucursal[sucursal]
                self.assertEqual(int(transacciones.replace(".", "")), esperado[0])
                self.assertEqual(_decimal(creditos), esperado[1])
                self.assertEqual(_decimal(debitos), esperado[2])

    def test_branches_add_up_to_the_global_controls(self) -> None:
        self.assertEqual(sum(valor[0] for valor in self.por_sucursal.values()), 72000)
        self.assertEqual(
            f"{sum(valor[1] for valor in self.por_sucursal.values()):.2f}",
            self.medidos["monto_creditos"],
        )
        self.assertEqual(
            f"{sum(valor[2] for valor in self.por_sucursal.values()):.2f}",
            self.medidos["monto_debitos"],
        )

    def test_global_and_role_values_quoted_in_the_guide_and_evidence(self) -> None:
        creditos = _formato(Decimal(self.medidos["monto_creditos"]))
        debitos = _formato(Decimal(self.medidos["monto_debitos"]))
        for texto in (self.guia, EVIDENCIAS.read_text(encoding="utf-8")):
            self.assertIn(creditos, texto)
            self.assertIn(debitos, texto)
            for provincia in ("SUC04", "SUC05"):
                esperado = self.por_sucursal[provincia]
                self.assertIn(f"{esperado[0]:,}".replace(",", "."), texto)
                self.assertIn(_formato(esperado[1]), texto)
                self.assertIn(_formato(esperado[2]), texto)

    def test_gold_cells_and_monthly_totals_quoted_in_the_guide(self) -> None:
        celdas = {(fila[0], fila[1]): fila[2] for fila in self.oro}
        self.assertEqual(celdas[("2026-04", "ATM")], 1365)
        self.assertEqual(celdas[("2026-09", "BANCA_MOVIL")], 7402)
        self.assertIn("**1.365**", self.guia)
        self.assertIn("**7.402**", self.guia)
        meses = self.medidos["transacciones_por_mes"]
        valores = [f"{meses[mes]:,}".replace(",", ".") for mes in sorted(meses)]
        self.assertIn(", ".join(valores[:-1]) + " y " + valores[-1], self.guia)

    def test_the_gold_table_has_no_branch_column(self) -> None:
        columnas = [nombre for nombre, _ in plata_silver.COLUMNAS_ORO]
        self.assertNotIn("sucursal_id", columnas)
        self.assertNotIn("provincia", columnas)


if __name__ == "__main__":
    unittest.main()
